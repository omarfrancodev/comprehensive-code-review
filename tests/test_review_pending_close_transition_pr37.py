"""Interrupted close transitions must be verified before replay changes the archive."""
import argparse
import copy
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from script_test_support import enable_package_imports

enable_package_imports()
from ccr.archive import coordination, inspection, lifecycle, reader, resources, retention, transactions
from ccr.cli import artifacts
import test_review_closure_consistency as guided
import test_review_closing_observation_pr37 as fixtures


class PendingCloseTransitionTests(unittest.TestCase):
    retained_run = fixtures.ClosingObservationPR37Tests.retained_run
    interrupted_run = fixtures.ClosingObservationPR37Tests.interrupted_run
    final_pending_run = fixtures.ClosingObservationPR37Tests.final_pending_run
    invalidate_execution_plan = fixtures.ClosingObservationPR37Tests.invalidate_execution_plan
    save = fixtures.ClosingObservationPR37Tests.save

    def interrupt_before_final_manifest(self, run):
        original = transactions.atomic_write

        def interrupt(path, data, **kwargs):
            if Path(path).name == 'cierre.json' and json.loads(data)['state'] == 'complete':
                raise OSError('interrupted before final close manifest replacement')
            return original(path, data, **kwargs)

        with patch.object(transactions, 'atomic_write', side_effect=interrupt):
            with self.assertRaisesRegex(OSError, 'interrupted before final close manifest replacement'):
                lifecycle.close(run, cleanup='not_needed')

    def interrupt_close_trace(self, run, cleanup, boundary, *, residuals=None):
        original = transactions.atomic_write

        def interrupt(path, data, **kwargs):
            if Path(path).name == 'trazabilidad.jsonl':
                if boundary == 'after':
                    original(path, data, **kwargs)
                raise OSError('interrupted during close trace')
            return original(path, data, **kwargs)

        with patch.object(transactions, 'atomic_write', side_effect=interrupt):
            with self.assertRaisesRegex(OSError, 'interrupted during close trace'):
                lifecycle.close(run, cleanup=cleanup, residuals=residuals)

    def interrupted_chained_close(self, boundary, *, noncanonical=False, prior_trace_intent=False,
                                  session_already_cleaned=False):
        fixture = guided.ClosureConsistencyTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        case = fixture.make_guided_run(complete_capture=True, explicit_identities=True,
                                       owned_session=True)
        run, session = case['run'], case['session']
        extra = fixture.root / 'temporary'
        extra.mkdir()
        lifecycle.register(run, [str(extra)], context_input=case['context'])
        fixture.retain(case)
        self.assertNotIn('evidence/check-disclosure.json', fixture.read(run / 'cierre.json')['hashes'])
        extra.rmdir()
        cleanup_args = argparse.Namespace(manifest=str(session / 'manifest.json'), run_dir=str(run))
        if session_already_cleaned:
            resources.cleanup_workspace(cleanup_args)
        previous_residuals = [] if session_already_cleaned else [str(session)]
        if prior_trace_intent:
            self.interrupt_close_trace(run, 'pending', 'before', residuals=previous_residuals)
        else:
            with patch.object(lifecycle, '_append_trace', side_effect=OSError('before pending close intent')):
                with self.assertRaisesRegex(OSError, 'before pending close intent'):
                    lifecycle.close(run, cleanup='pending', residuals=previous_residuals)
        manifest = fixture.read(run / 'cierre.json')
        if prior_trace_intent:
            self.assertEqual(manifest['residuals'], previous_residuals)
        else:
            self.assertCountEqual(manifest['residuals'], [str(session), str(extra)])
        review = run / 'review.json'
        previous = fixture.read(review)
        self.assertEqual(previous['resources']['residuals'], previous_residuals)
        if noncanonical:
            raw = (' \n' + json.dumps(previous, ensure_ascii=False) + '\n\t').encode('utf-8')
            review.write_bytes(raw)
            manifest['hashes']['review.json'] = hashlib.sha256(raw).hexdigest()
            self.save(fixture, run, manifest)
        old_bytes = review.read_bytes()

        if prior_trace_intent:
            lifecycle.close(run, cleanup='pending', residuals=previous_residuals)
        if not session_already_cleaned:
            resources.cleanup_workspace(cleanup_args)
        original = retention.atomic_write

        def interrupt(path, data, **kwargs):
            if Path(path).name == 'review.json':
                if boundary == 'after':
                    original(path, data, **kwargs)
                raise OSError('interrupted at the final review replacement')
            return original(path, data, **kwargs)

        replacement = (patch.object(lifecycle, '_retain_data',
                                    side_effect=OSError('interrupted at the final review replacement'))
                       if boundary == 'before_intent'
                       else patch.object(retention, 'atomic_write', side_effect=interrupt))
        with replacement:
            with self.assertRaisesRegex(OSError, 'interrupted at the final review replacement'):
                lifecycle.close(run, cleanup='complete')
        manifest = fixture.read(run / 'cierre.json')
        self.assertEqual(manifest['state'], 'closing' if boundary == 'before_intent' else 'retaining')
        self.assertEqual('planned_hashes' in manifest, boundary != 'before_intent')
        self.assertEqual(manifest['hashes']['review.json'], hashlib.sha256(old_bytes).hexdigest())
        self.assertEqual(fixture.read(review)['resources']['cleanup'],
                         'complete' if boundary == 'after' else 'pending')
        if boundary != 'after':
            self.assertEqual(review.read_bytes(), old_bytes)
        return fixture, run

    def test_chained_close_replays_terminal_observation_before_replacement_intent(self):
        fixture, run = self.interrupted_chained_close('before_intent', noncanonical=True)
        manifest = fixture.read(run / 'cierre.json')
        observation = manifest['close_observation']
        self.assertEqual(observation['cleanup'], 'complete')
        self.assertEqual(len(observation['released_claims']), 1)
        self.assertNotEqual(fixture.read(run / 'review.json')['resources']['residuals'],
                            manifest['residuals'])
        before = fixture.snapshot(run)

        summary = artifacts._finish_status(run)
        self.assertEqual(fixture.snapshot(run), before)
        self.assertEqual((summary['gate'], summary['next_action']), ('close', 'retry_close'), summary)
        result, code = artifacts.finish_run(run)
        self.assertEqual((code, result['status'], result.get('cleanup')),
                         (0, 'complete', 'complete'), result)
        self.assertEqual(lifecycle.validate(run, require_complete=True)['state'], 'complete')
        final = fixture.read(run / 'cierre.json')
        self.assertEqual(final['close_observation'], observation)
        self.assertEqual(final['cleanup_receipts'], observation['released_claims'])
        trace = [json.loads(line) for line in (run / 'trazabilidad.jsonl').read_bytes().splitlines()]
        self.assertEqual(sum(event['kind'] == 'close' and event['status'] == 'completed'
                             for event in trace), 1)
        completed = fixture.snapshot(run)
        self.assertEqual(artifacts.finish_run(run)[1], 0)
        self.assertEqual(fixture.snapshot(run), completed)

    def test_chained_close_replays_with_verified_previous_review(self):
        cases = (('before', False, False), ('before', True, False), ('after', False, True))
        for boundary, noncanonical, prior_trace_intent in cases:
            for observation in ({}, {'cleanup': 'complete'}):
                with self.subTest(boundary=boundary, noncanonical=noncanonical, explicit=bool(observation)):
                    fixture, run = self.interrupted_chained_close(
                        boundary, noncanonical=noncanonical, prior_trace_intent=prior_trace_intent)
                    before = fixture.snapshot(run)
                    summary = artifacts._finish_status(run)
                    self.assertEqual(fixture.snapshot(run), before)
                    self.assertEqual((summary['gate'], summary['next_action']), ('close', 'retry_close'), summary)
                    result, code = artifacts.finish_run(run, **observation)
                    self.assertEqual((code, result['status'], result.get('cleanup')),
                                     (0, 'complete', 'complete'), result)
                    self.assertEqual(lifecycle.validate(run, require_complete=True)['state'], 'complete')
                    trace = [json.loads(line) for line in (run / 'trazabilidad.jsonl').read_bytes().splitlines()]
                    self.assertEqual(sum(event['kind'] == 'close' and event['status'] == 'completed'
                                         for event in trace), 1)
                    completed = fixture.snapshot(run)
                    self.assertEqual(artifacts.finish_run(run, **observation)[1], 0)
                    self.assertEqual(fixture.snapshot(run), completed)

    def test_chained_close_recovers_from_verified_planned_residuals(self):
        fixture, run = self.interrupted_chained_close('after', session_already_cleaned=True)
        before = fixture.snapshot(run)
        summary = artifacts._finish_status(run)
        self.assertEqual(fixture.snapshot(run), before)
        self.assertEqual((summary['gate'], summary['next_action']), ('close', 'retry_close'), summary)
        result, code = artifacts.finish_run(run)
        self.assertEqual((code, result['status']), (0, 'complete'), result)
        self.assertEqual(lifecycle.validate(run, require_complete=True)['cleanup'], 'complete')

    def test_chained_close_preserves_archive_if_previous_review_cannot_be_verified(self):
        fixture, run = self.interrupted_chained_close('after')
        before = fixture.snapshot(run)
        summary = artifacts._finish_status(run)
        self.assertEqual(summary['next_action'], 'preserve')
        for observation in ({}, {'cleanup': 'complete'}):
            with self.subTest(explicit=bool(observation)):
                result, code = artifacts.finish_run(run, **observation)
                self.assertEqual((code, result['next_action']), (1, 'preserve'))
                self.assertIn('owned previous review', result['reason'])
                self.assertEqual(fixture.snapshot(run), before)

    @contextmanager
    def before_finish_lock(self, compete):
        original_lock = coordination._owned_run_locks

        @contextmanager
        def compete_before_lock(paths):
            # Run the competing mutation before finish takes the real lock.
            with patch.object(coordination, '_owned_run_locks', original_lock):
                compete()
                with original_lock(paths) as loaded:
                    yield loaded

        with patch.object(coordination, '_owned_run_locks', compete_before_lock):
            yield

    def test_summary_and_automatic_finish_replay_owned_previous_closing_manifest(self):
        fixture, case = self.retained_run()
        run = case['run']
        self.interrupt_before_final_manifest(run)
        _, manifest, marker = reader.load_run(run)
        self.assertEqual(manifest['state'], 'closing')
        self.assertIn('previous_manifest_sha256', marker)
        self.assertEqual(inspection.inspect_run(run)['integrity']['status'], 'recoverable')
        before = fixture.snapshot(run)
        with self.assertRaisesRegex(ValueError, 'ownership transition is pending'):
            lifecycle.validate(run, require_retained=True)

        summary = artifacts._finish_status(run)
        self.assertEqual((summary['gate'], summary['next_action']), ('close', 'retry_close'))
        self.assertEqual(fixture.snapshot(run), before)

        result, code = artifacts.finish_run(run)
        self.assertEqual((code, result['status']), (0, 'complete'))
        self.assertEqual(lifecycle.validate(run, require_complete=True)['state'], 'complete')
        _, final, marker = reader.load_run(run)
        self.assertNotIn('previous_manifest_sha256', marker)
        self.assertEqual(final['close_observation'], manifest['close_observation'])
        trace = [json.loads(line) for line in (run / 'trazabilidad.jsonl').read_bytes().splitlines()]
        self.assertEqual(sum(event['kind'] == 'close' for event in trace), 1)

    def test_direct_close_rejects_a_conflicting_request_before_pinning_previous_manifest(self):
        fixture, case = self.retained_run()
        run = case['run']
        self.interrupt_before_final_manifest(run)
        before = fixture.snapshot(run)
        with self.assertRaisesRegex(ValueError, 'exact durable cleanup observation'):
            lifecycle.close(run, cleanup='complete')
        self.assertEqual(fixture.snapshot(run), before)

    def test_direct_close_rejects_a_conflicting_request_before_recovering_final_trace(self):
        for boundary in ('before', 'after'):
            with self.subTest(boundary=boundary):
                fixture, case = self.retained_run()
                run = case['run']
                self.interrupt_close_trace(run, 'not_needed', boundary)
                before = fixture.snapshot(run)
                with self.assertRaisesRegex(ValueError, 'exact durable cleanup observation'):
                    lifecycle.close(run, cleanup='complete')
                self.assertEqual(fixture.snapshot(run), before)

    def test_explicit_finish_checks_the_durable_observation_after_another_close(self):
        for boundary in ('before', 'after'):
            with self.subTest(boundary=boundary):
                fixture, case = self.retained_run()
                run = case['run']
                after_competitor = None

                def compete():
                    nonlocal after_competitor
                    self.interrupt_close_trace(run, 'not_needed', boundary)
                    after_competitor = fixture.snapshot(run)

                with self.before_finish_lock(compete):
                    result, code = artifacts.finish_run(run, cleanup='complete')

                self.assertIsNotNone(after_competitor)
                self.assertEqual(code, 1)
                self.assertIn('exact durable cleanup observation', result['reason'])
                self.assertEqual(fixture.snapshot(run), after_competitor)

    def test_automatic_finish_does_not_adopt_a_different_ownership_snapshot(self):
        fixture, case = self.retained_run()
        run = case['run']
        before_close = fixture.snapshot(run)
        self.interrupt_close_trace(run, 'not_needed', 'before')
        after_competitor = None

        def compete():
            nonlocal after_competitor
            # Model an independently owned archive replacing the observed path.
            for name, raw in before_close.items():
                (run / name).write_bytes(raw)
            _, manifest, marker = reader.load_run(run)
            manifest['owner_id'] = 'independent-owner'
            marker['owner_id'] = manifest['owner_id']
            transactions.save_manifest(run, manifest, marker)
            self.interrupt_close_trace(run, 'complete', 'after')
            after_competitor = fixture.snapshot(run)

        with self.before_finish_lock(compete):
            result, code = artifacts.finish_run(run)

        self.assertIsNotNone(after_competitor)
        self.assertEqual((code, result['status'], result['next_action']), (1, 'pending', 'preserve'))
        self.assertEqual(fixture.snapshot(run), after_competitor)

    def test_pending_trace_retry_with_a_live_claim_checks_cleanup_before_recovery(self):
        fixture, case = self.retained_run(owned_session=True)
        run = case['run']
        residuals = [str(case['session'])]
        self.interrupt_close_trace(run, 'pending', 'before', residuals=residuals)
        before = fixture.snapshot(run)
        with self.assertRaisesRegex(ValueError, 'every existing registered resource'):
            lifecycle.close(run, cleanup='pending')
        self.assertEqual(fixture.snapshot(run), before)
        with self.assertRaisesRegex(ValueError, 'durable cleanup receipt'):
            lifecycle.close(run, cleanup='pending', residuals=residuals,
                            released_claims=[{'claim_id': 'foreign'}])
        self.assertEqual(fixture.snapshot(run), before)
        completed = lifecycle.close(run, cleanup='pending', residuals=residuals)
        self.assertEqual((completed['state'], completed['residuals']), ('closing', residuals))
        self.assertNotIn('pending_trace', completed)

    def test_direct_close_preserves_final_trace_when_retained_execution_plan_is_invalid(self):
        fixture, run = self.final_pending_run('after')
        before = fixture.snapshot(run)
        with self.assertRaisesRegex(ValueError, 'execution_plan'):
            lifecycle.close(run, cleanup='not_needed')
        self.assertEqual(fixture.snapshot(run), before)

    def test_preserves_final_trace_when_pending_event_differs_from_already_written_bytes(self):
        fixture, run = self.final_pending_run('after', invalid_plan=False)
        manifest = fixture.read(run / 'cierre.json')
        manifest['pending_trace']['events'][0]['summary'] = 'Different than the owned event'
        self.save(fixture, run, manifest)
        before = fixture.snapshot(run)
        self.assertEqual(artifacts._finish_status(run)['next_action'], 'preserve')
        cleanup_file = fixture.write('recorded-cleanup.json', manifest['close_observation'])
        for args in ({}, {'cleanup_file': cleanup_file}):
            result, code = artifacts.finish_run(run, **args)
            self.assertEqual((code, result['next_action']), (1, 'preserve'))
        with self.assertRaisesRegex(ValueError, 'owned trace transition'):
            lifecycle.close(run, cleanup='not_needed')
        self.assertEqual(fixture.snapshot(run), before)

    def test_recorded_close_requires_exact_durable_cleanup_metadata(self):
        fixture, case = self.interrupted_run()
        run = case['run']
        original = fixture.read(run / 'cierre.json')
        variants = [
            {'resource_cleanup'}, {'cleanup_receipts'}, {'resource_cleanup', 'cleanup_receipts'},
        ]
        for removed in variants:
            with self.subTest(removed=removed):
                manifest = {key: value for key, value in original.items() if key not in removed}
                self.save(fixture, run, manifest)
                before = fixture.snapshot(run)
                self.assertEqual(artifacts._finish_status(run)['next_action'], 'preserve')
                result, code = artifacts.finish_run(run)
                self.assertEqual((code, result['next_action']), (1, 'preserve'))
                with self.assertRaises(ValueError):
                    lifecycle.close(run, cleanup='not_needed')
                self.assertEqual(fixture.snapshot(run), before)

        for changed in ({'unexpected': True}, {'released_claims': [{'claim_id': 'foreign'}]}):
            with self.subTest(observation=changed):
                manifest = copy.deepcopy(original)
                manifest['close_observation'].update(changed)
                self.save(fixture, run, manifest)
                before = fixture.snapshot(run)
                self.assertEqual(artifacts._finish_status(run)['next_action'], 'preserve')
                result, code = artifacts.finish_run(run)
                self.assertEqual((code, result['next_action']), (1, 'preserve'))
                with self.assertRaises(ValueError):
                    lifecycle.close(run, cleanup='not_needed')
                self.assertEqual(fixture.snapshot(run), before)

    def test_explicit_close_can_replay_early_observation_without_inferring_old_cleanup(self):
        fixture, case = self.retained_run()
        run = case['run']
        self.assertEqual(fixture.read(run / 'review.json')['resources']['cleanup'], 'not_needed')
        with patch.object(lifecycle, '_retain_data', side_effect=OSError('before close replacement')):
            with self.assertRaisesRegex(OSError, 'before close replacement'):
                lifecycle.close(run, cleanup='complete')
        before = fixture.snapshot(run)
        self.assertEqual(artifacts._finish_status(run)['next_action'], 'preserve')
        result, code = artifacts.finish_run(run)
        self.assertEqual((code, result['next_action']), (1, 'preserve'))
        self.assertEqual(fixture.snapshot(run), before)

        result, code = artifacts.finish_run(run, cleanup='complete')
        self.assertEqual((code, result['status'], result.get('cleanup')), (0, 'complete', 'complete'), result)
        self.assertEqual(lifecycle.validate(run, require_complete=True)['state'], 'complete')

    def test_explicit_close_can_replay_a_legacy_final_trace_without_recorded_observation(self):
        fixture, case = self.retained_run()
        run = case['run']
        manifest = fixture.read(run / 'cierre.json')
        manifest.pop('resource_cleanup')
        manifest.pop('cleanup_receipts')
        self.save(fixture, run, manifest)
        self.interrupt_close_trace(run, 'not_needed', 'before')
        self.assertNotIn('close_observation', fixture.read(run / 'cierre.json'))
        before = fixture.snapshot(run)
        result, code = artifacts.finish_run(run)
        self.assertEqual((code, result['next_action']), (1, 'preserve'))
        self.assertEqual(fixture.snapshot(run), before)
        self.assertEqual(lifecycle.close(run, cleanup='not_needed')['state'], 'complete')
        self.assertEqual(lifecycle.validate(run, require_complete=True)['state'], 'complete')


if __name__ == '__main__':
    unittest.main()
