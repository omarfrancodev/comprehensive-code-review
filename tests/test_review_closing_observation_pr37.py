"""A durable terminal observation must yield the same action in inspect and finish."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from script_test_support import enable_package_imports, run_cli

enable_package_imports()
from ccr.archive import lifecycle, reader, resources, retention, transactions
from ccr.cli import artifacts
from ccr.shared.encoding import archive_bytes
import test_review_closure_consistency as guided


class ClosingObservationPR37Tests(unittest.TestCase):
    def retained_run(self, *, owned_session=False, initial_cleanup=None):
        fixture = guided.ClosureConsistencyTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        case = fixture.make_guided_run(complete_capture=True, explicit_identities=True,
                                       owned_session=owned_session)
        if initial_cleanup is not None:
            value = fixture.read(case['record'])
            value['resources']['cleanup'] = initial_cleanup
            case['record'] = fixture.write('final.json', value)
        fixture.retain(case)
        return fixture, case

    def interrupted_run(self, *, owned_session=False, before_replacement=False):
        fixture, case = self.retained_run(owned_session=owned_session)
        run = case['run']
        if owned_session:
            resources.cleanup_workspace(argparse.Namespace(
                manifest=str(case['session'] / 'manifest.json'), run_dir=str(run)))
        original = lifecycle._append_trace

        def stop_before_close(path, manifest, marker, event, **kwargs):
            if event['kind'] == 'close':
                raise OSError('before final close intent')
            return original(path, manifest, marker, event, **kwargs)

        cleanup = 'complete' if owned_session else 'not_needed'
        target = '_retain_data' if before_replacement else '_append_trace'
        failure = OSError('before final close intent') if before_replacement else stop_before_close
        with patch.object(lifecycle, target, side_effect=failure):
            with self.assertRaisesRegex(OSError, 'before final close intent'):
                lifecycle.close(run, cleanup=cleanup)
        manifest = fixture.read(run / 'cierre.json')
        self.assertEqual(manifest['state'], 'closing')
        self.assertNotIn('pending_trace', manifest)
        self.assertEqual(manifest['close_observation']['cleanup'], cleanup)
        return fixture, case

    def cli(self, fixture, *args):
        result = run_cli('artifacts', [str(arg) for arg in args], cwd=fixture.root)
        return result.returncode, json.loads(result.stdout or result.stderr)

    def save(self, fixture, run, manifest):
        transactions.save_manifest(run, manifest, fixture.read(run / transactions.MARKER))

    def test_summary_recommends_replaying_verified_terminal_observation(self):
        # Omitting terminal closing observations strands an already captured close.
        for owned_session in (False, True):
            with self.subTest(owned_session=owned_session):
                fixture, case = self.interrupted_run(owned_session=owned_session)
                run = case['run']
                observation = copy.deepcopy(reader.load_run(run)[1]['close_observation'])
                sources = {name: (run / name).read_bytes() for name in
                           fixture.read(run / 'cierre.json')['hashes']}
                before = fixture.snapshot(run)
                code, summary = self.cli(fixture, 'inspect', '--run-dir', run, '--summary')
                self.assertEqual(code, 0)
                self.assertEqual((summary['status'], summary['gate'], summary['next_action']),
                                 ('pending', 'close', 'retry_close'))
                self.assertEqual(fixture.snapshot(run), before)
                code, completed = self.cli(fixture, 'finish', '--run-dir', run)
                self.assertEqual((code, completed['status']), (0, 'complete'))
                self.assertEqual(lifecycle.validate(run, require_complete=True)['state'], 'complete')
                self.assertEqual(reader.load_run(run)[1]['close_observation'], observation)
                events = [json.loads(line) for line in
                          (run / 'trazabilidad.jsonl').read_bytes().splitlines()]
                self.assertEqual(len([row for row in events if row['kind'] == 'close']), 1)
                for name, raw in sources.items():
                    if name != 'trazabilidad.jsonl':
                        self.assertEqual((run / name).read_bytes(), raw, name)
                completed_bytes = fixture.snapshot(run)
                self.assertEqual(self.cli(fixture, 'finish', '--run-dir', run)[0], 0)
                self.assertEqual(self.cli(fixture, 'inspect', '--run-dir', run, '--summary')[1]['status'],
                                 'complete')
                self.assertEqual(fixture.snapshot(run), completed_bytes)

    def assert_preserved(self, fixture, run, *, action='preserve'):
        before = fixture.snapshot(run)
        code, summary = self.cli(fixture, 'inspect', '--run-dir', run, '--summary')
        self.assertEqual(code, 0)
        self.assertEqual(summary['next_action'], action)
        self.assertEqual(fixture.snapshot(run), before)
        code, status = self.cli(fixture, 'finish', '--run-dir', run)
        self.assertEqual(code, 1)
        self.assertEqual(status['next_action'], action)
        self.assertEqual(fixture.snapshot(run), before)

    def test_nonterminal_observation_still_requires_current_cleanup(self):
        fixture, case = self.interrupted_run()
        run = case['run']
        manifest = fixture.read(run / 'cierre.json')
        manifest['close_observation']['cleanup'] = 'pending'
        self.save(fixture, run, manifest)
        self.assert_preserved(fixture, run, action='supply_cleanup_observation')

    def test_observation_persisted_before_replacement_can_still_be_replayed(self):
        # Saving the durable observation precedes the old/planned replacement intent.
        fixture, case = self.interrupted_run(owned_session=True, before_replacement=True)
        run = case['run']
        self.assertEqual(fixture.read(run / 'review.json')['resources']['cleanup'], 'pending')
        before = fixture.snapshot(run)
        code, summary = self.cli(fixture, 'inspect', '--run-dir', run, '--summary')
        self.assertEqual((code, summary['next_action']), (0, 'retry_close'))
        self.assertEqual(fixture.snapshot(run), before)
        code, status = self.cli(fixture, 'finish', '--run-dir', run)
        self.assertEqual((code, status['status']), (0, 'complete'))
        self.assertEqual(lifecycle.validate(run, require_complete=True)['state'], 'complete')

    def interrupt_planned_close(self, run, *, marker_boundary=None):
        if marker_boundary is not None:
            original = transactions.atomic_write

            def interrupt(path, data, **kwargs):
                if json.loads((run / 'cierre.json').read_bytes())['state'] == 'retaining':
                    if (marker_boundary == 'planned' and Path(path).name == transactions.MARKER
                            and 'previous_manifest_sha256' not in json.loads(data)):
                        raise OSError('interrupted while committing the planned close marker')
                    if (marker_boundary == 'previous' and Path(path).name == 'cierre.json'
                            and json.loads(data)['state'] == 'closing'):
                        raise OSError('interrupted before committing the planned close replacement')
                return original(path, data, **kwargs)

            target = transactions
        else:
            original = retention.atomic_write

            def interrupt(path, data, **kwargs):
                if Path(path).name == 'review.json':
                    raise OSError('interrupted before planned close record replacement')
                return original(path, data, **kwargs)

            target = retention

        with patch.object(target, 'atomic_write', side_effect=interrupt):
            with self.assertRaisesRegex(OSError, 'interrupted .* planned close'):
                lifecycle.close(run, cleanup='not_needed')

    def test_planned_close_without_disclosure_can_replay_the_prior_terminal_record(self):
        marker_digest_field = {None: 'manifest_sha256', 'planned': 'manifest_sha256',
                               'previous': 'previous_manifest_sha256'}
        for marker_boundary, digest_field in marker_digest_field.items():
            for entry in ('automatic', 'explicit'):
                with self.subTest(marker_boundary=marker_boundary, entry=entry):
                    fixture, case = self.retained_run(initial_cleanup='complete')
                    run = case['run']
                    self.interrupt_planned_close(run, marker_boundary=marker_boundary)
                    _, manifest, marker = reader.load_run(run)
                    self.assertEqual(manifest['state'], 'retaining')
                    self.assertEqual('previous_manifest_sha256' in marker, marker_boundary is not None)
                    self.assertEqual(hashlib.sha256((run / 'cierre.json').read_bytes()).hexdigest(),
                                     marker[digest_field])
                    cleanup = 'not_needed' if marker_boundary == 'previous' else 'complete'
                    self.assertEqual(fixture.read(run / 'review.json')['resources']['cleanup'], cleanup)
                    self.assertEqual(set(manifest['planned_hashes']), {'review.json', 'informe.md'})
                    self.assertNotIn('check_disclosure_reference', fixture.read(run / 'evidence/context.json'))
                    before = fixture.snapshot(run)

                    code, summary = self.cli(fixture, 'inspect', '--run-dir', run, '--summary')
                    self.assertEqual((code, summary['gate'], summary['next_action']), (0, 'close', 'retry_close'))
                    self.assertEqual(fixture.snapshot(run), before)
                    rejected, code = artifacts.finish_run(run, cleanup='complete')
                    self.assertEqual(code, 1)
                    self.assertIn('exact durable cleanup observation', rejected['reason'])
                    self.assertEqual(fixture.snapshot(run), before)

                    args = [] if entry == 'automatic' else ['--cleanup', 'not_needed']
                    code, result = self.cli(fixture, 'finish', '--run-dir', run, *args)
                    self.assertEqual((code, result['status'], result['cleanup']), (0, 'complete', 'not_needed'))
                    self.assertEqual(lifecycle.validate(run, require_complete=True)['state'], 'complete')
                    _, final, marker = reader.load_run(run)
                    self.assertNotIn('previous_manifest_sha256', marker)
                    self.assertNotIn('planned_hashes', final)
                    self.assertEqual(final['close_observation'], manifest['close_observation'])
                    for name, raw in before.items():
                        if name not in manifest['planned_hashes'] and name not in {
                                'cierre.json', transactions.MARKER, 'trazabilidad.jsonl'}:
                            self.assertEqual((run / name).read_bytes(), raw, name)
                    trace = [json.loads(line) for line in (run / 'trazabilidad.jsonl').read_bytes().splitlines()]
                    self.assertEqual(sum(event['kind'] == 'close' for event in trace), 1)
                    completed = fixture.snapshot(run)
                    self.assertEqual(artifacts.finish_run(run)[1], 0)
                    self.assertEqual(fixture.snapshot(run), completed)

    def test_planned_close_without_disclosure_rejects_different_report_hash(self):
        fixture, case = self.retained_run(initial_cleanup='complete')
        run = case['run']
        self.interrupt_planned_close(run)
        manifest = fixture.read(run / 'cierre.json')
        manifest['planned_hashes']['informe.md'] = '0' * 64
        self.save(fixture, run, manifest)
        self.assert_preserved(fixture, run)
        before = fixture.snapshot(run)
        with self.assertRaisesRegex(ValueError, 'exact planned inventory'):
            lifecycle.close(run, cleanup='not_needed')
        self.assertEqual(fixture.snapshot(run), before)

    def test_planned_close_needs_surviving_canonical_review_bytes(self):
        fixture, case = self.retained_run(initial_cleanup='complete')
        run = case['run']
        self.interrupt_planned_close(run, marker_boundary='planned')
        self.assertIn('review.json', fixture.read(run / 'cierre.json')['planned_hashes'])
        (run / 'review.json').unlink()
        self.assert_preserved(fixture, run)
        before = fixture.snapshot(run)
        result, code = artifacts.finish_run(run, cleanup='not_needed')
        self.assertEqual((code, result['next_action']), (1, 'preserve'))
        self.assertEqual(fixture.snapshot(run), before)

    def test_live_claim_requires_actual_workspace_cleanup(self):
        fixture, case = self.retained_run(owned_session=True)
        self.assert_preserved(fixture, case['run'], action='workspace_cleanup')

    def test_pending_cleanup_intent_requires_actual_cleanup_recovery(self):
        fixture, case = self.retained_run(owned_session=True)
        with patch.object(resources.workspace_ops, 'remove_workspaces',
                          side_effect=OSError('cleanup interrupted before removal')):
            with self.assertRaisesRegex(OSError, 'cleanup interrupted before removal'):
                resources.cleanup_workspace(argparse.Namespace(
                    manifest=str(case['session'] / 'manifest.json'), run_dir=str(case['run'])))
        self.assert_preserved(fixture, case['run'], action='recover_cleanup')

    def test_detached_or_malformed_terminal_observation_is_preserved(self):
        fixture, case = self.interrupted_run()
        run = case['run']
        initial = fixture.read(run / 'cierre.json')
        for observation in (
                {'cleanup': 'complete', 'residuals': [], 'released_claims': []},
                {'cleanup': 'not_needed', 'residuals': [str(fixture.root)], 'released_claims': []},
                {'cleanup': 'not_needed', 'residuals': [], 'released_claims': [{'claim_id': 'foreign'}]},
                {'residuals': [], 'released_claims': []}):
            with self.subTest(observation=observation):
                manifest = copy.deepcopy(initial)
                manifest['close_observation'] = observation
                self.save(fixture, run, manifest)
                self.assert_preserved(fixture, run)

    def test_resource_reappearing_after_observation_is_preserved(self):
        fixture, case = self.interrupted_run(owned_session=True)
        case['session'].mkdir()
        try:
            self.assert_preserved(fixture, case['run'])
        finally:
            case['session'].rmdir()

    def test_changed_retained_proof_is_preserved(self):
        fixture, case = self.interrupted_run()
        path = case['run'] / 'evidence/context.json'
        path.write_bytes(path.read_bytes() + b' ')
        self.assert_preserved(fixture, case['run'])

    def test_invalid_retained_execution_plan_is_preserved(self):
        fixture, case = self.interrupted_run()
        run = case['run']
        self.invalidate_execution_plan(fixture, run)
        self.assert_preserved(fixture, run)

    def invalidate_execution_plan(self, fixture, run):
        context = fixture.read(run / 'evidence/context.json')
        context['execution_plan'] = []
        raw = archive_bytes(context)
        (run / 'evidence/context.json').write_bytes(raw)
        manifest = fixture.read(run / 'cierre.json')
        manifest['hashes']['evidence/context.json'] = hashlib.sha256(raw).hexdigest()
        self.save(fixture, run, manifest)

    def final_pending_run(self, boundary, *, invalid_plan=True, owned_session=False):
        fixture, case = self.retained_run(owned_session=owned_session)
        if owned_session:
            resources.cleanup_workspace(argparse.Namespace(
                manifest=str(case['session'] / 'manifest.json'), run_dir=str(case['run'])))
        original = transactions.atomic_write

        def interrupt(path, data, **kwargs):
            if Path(path).name == 'trazabilidad.jsonl':
                if boundary == 'after':
                    original(path, data, **kwargs)
                raise OSError('interrupted final trace replacement')
            return original(path, data, **kwargs)

        run = case['run']
        with patch.object(transactions, 'atomic_write', side_effect=interrupt):
            with self.assertRaisesRegex(OSError, 'interrupted final trace replacement'):
                lifecycle.close(run, cleanup='complete' if owned_session else 'not_needed')
        manifest = reader.load_run(run)[1]
        self.assertEqual(manifest['state'], 'complete')
        self.assertIn('pending_trace', manifest)
        if invalid_plan:
            self.invalidate_execution_plan(fixture, run)
        return fixture, run

    def test_final_pending_summary_verifies_execution_before_recommending_replay(self):
        for boundary in ('before', 'after'):
            with self.subTest(boundary=boundary):
                fixture, run = self.final_pending_run(boundary)
                before = fixture.snapshot(run)
                code, summary = self.cli(fixture, 'inspect', '--run-dir', run, '--summary')
                self.assertEqual(code, 0)
                self.assertEqual(fixture.snapshot(run), before)
                self.assertEqual(summary['next_action'], 'preserve')

    def test_final_pending_finish_verifies_execution_before_any_replay_write(self):
        for boundary in ('before', 'after'):
            with self.subTest(boundary=boundary):
                fixture, run = self.final_pending_run(boundary)
                before = fixture.snapshot(run)
                code, status = self.cli(fixture, 'finish', '--run-dir', run)
                self.assertEqual((code, status['next_action']), (1, 'preserve'))
                self.assertEqual(fixture.snapshot(run), before)

    def explicit_cleanup_args(self, fixture, run, variant):
        if variant == 'inline':
            return ['--cleanup', 'not_needed']
        observation = reader.load_run(run)[1]['close_observation']
        return ['--cleanup-file', fixture.write('cleanup-observation.json', observation)]

    def test_final_pending_explicit_finish_cannot_bypass_execution_validation(self):
        for boundary in ('before', 'after'):
            for variant in ('inline', 'file'):
                with self.subTest(boundary=boundary, variant=variant):
                    fixture, run = self.final_pending_run(boundary)
                    args = self.explicit_cleanup_args(fixture, run, variant)
                    before = fixture.snapshot(run)
                    code, status = self.cli(fixture, 'finish', '--run-dir', run, *args)
                    self.assertEqual((code, status['next_action']), (1, 'preserve'))
                    self.assertEqual(fixture.snapshot(run), before)

    def test_final_pending_explicit_finish_replays_valid_observation(self):
        for boundary in ('before', 'after'):
            for variant in ('inline', 'file'):
                with self.subTest(boundary=boundary, variant=variant):
                    fixture, run = self.final_pending_run(boundary, invalid_plan=False)
                    args = self.explicit_cleanup_args(fixture, run, variant)
                    observation = copy.deepcopy(reader.load_run(run)[1]['close_observation'])
                    sources = {name: (run / name).read_bytes() for name in
                               fixture.read(run / 'cierre.json')['hashes']
                               if name != 'trazabilidad.jsonl'}
                    code, status = self.cli(fixture, 'finish', '--run-dir', run, *args)
                    self.assertEqual((code, status['status']), (0, 'complete'))
                    self.assertEqual(lifecycle.validate(run, require_complete=True)['state'], 'complete')
                    self.assertEqual(reader.load_run(run)[1]['close_observation'], observation)
                    for name, raw in sources.items():
                        self.assertEqual((run / name).read_bytes(), raw, name)
                    before = fixture.snapshot(run)
                    self.assertEqual(self.cli(fixture, 'finish', '--run-dir', run, *args)[0], 0)
                    self.assertEqual(fixture.snapshot(run), before)

    def test_final_pending_rejects_changed_or_malformed_requests_before_replay(self):
        for boundary in ('before', 'after'):
            fixture, run = self.final_pending_run(boundary, invalid_plan=False)
            foreign = [{'claim_id': 'foreign'}]
            malformed_file = fixture.root / 'malformed-cleanup.json'
            malformed_file.write_text('{', encoding='utf-8')
            variants = {
                'inline-cleanup': ['--cleanup', 'complete'],
                'inline-residual': ['--cleanup', 'not_needed', '--residual', fixture.root],
                'inline-receipts': ['--cleanup', 'not_needed', '--released-claims-input',
                                    fixture.write('foreign-receipts.json', foreign)],
                'file-malformed-json': ['--cleanup-file', malformed_file],
            }
            for name, value in {
                    'null': None,
                    'cleanup': {'cleanup': 'complete', 'residuals': []},
                    'residuals': {'cleanup': 'not_needed', 'residuals': 'not-an-array'},
                    'extra': {'cleanup': 'not_needed', 'residuals': [], 'unexpected': True},
                    'receipts': {'cleanup': 'not_needed', 'residuals': [], 'released_claims': foreign},
                    'receipts-shape': {'cleanup': 'not_needed', 'residuals': [], 'released_claims': {}},
            }.items():
                variants['file-' + name] = ['--cleanup-file', fixture.write('cleanup-' + name + '.json', value)]
            before = fixture.snapshot(run)
            for variant, args in variants.items():
                with self.subTest(boundary=boundary, variant=variant):
                    for name, raw in before.items():
                        (run / name).write_bytes(raw)
                    code, status = self.cli(fixture, 'finish', '--run-dir', run, *args)
                    self.assertEqual((code, status['next_action']), (1, 'preserve'))
                    self.assertEqual(fixture.snapshot(run), before)

    def test_final_pending_real_release_receipts_preserve_optional_request_defaults(self):
        for boundary in ('before', 'after'):
            for variant in ('inline-omitted', 'inline-exact', 'file-omitted', 'file-null', 'file-exact'):
                with self.subTest(boundary=boundary, variant=variant):
                    fixture, run = self.final_pending_run(boundary, invalid_plan=False, owned_session=True)
                    observation = copy.deepcopy(reader.load_run(run)[1]['close_observation'])
                    self.assertTrue(observation['released_claims'])
                    if variant.startswith('inline'):
                        args = ['--cleanup', 'complete']
                        if variant == 'inline-exact':
                            args.extend(['--released-claims-input', fixture.write(
                                'exact-receipts.json', observation['released_claims'])])
                    else:
                        requested = copy.deepcopy(observation)
                        if variant == 'file-omitted':
                            requested.pop('released_claims')
                        elif variant == 'file-null':
                            requested['released_claims'] = None
                        args = ['--cleanup-file', fixture.write('cleanup-receipts.json', requested)]
                    sources = {name: (run / name).read_bytes() for name in
                               fixture.read(run / 'cierre.json')['hashes']
                               if name != 'trazabilidad.jsonl'}
                    code, status = self.cli(fixture, 'finish', '--run-dir', run, *args)
                    self.assertEqual((code, status['status']), (0, 'complete'))
                    self.assertEqual(lifecycle.validate(run, require_complete=True)['state'], 'complete')
                    self.assertEqual(reader.load_run(run)[1]['close_observation'], observation)
                    for name, raw in sources.items():
                        self.assertEqual((run / name).read_bytes(), raw, name)

    def test_final_pending_all_entry_points_require_the_full_retained_record_gate(self):
        for boundary in ('before', 'after'):
            fixture, run = self.final_pending_run(boundary, invalid_plan=False)
            baseline = fixture.snapshot(run)
            for variant in ('shape', 'stage', 'scope', 'review_id', 'schema'):
                for name, raw in baseline.items():
                    (run / name).write_bytes(raw)
                value = fixture.read(run / 'review.json')
                if variant == 'shape':
                    value['unexpected'] = True
                elif variant == 'stage':
                    value['stage'] = 'discovery'
                elif variant == 'scope':
                    value['scope']['head'] = 'f' * 40
                elif variant == 'review_id':
                    value['review_id'] = 'CR-' + 'f' * 20
                else:
                    value['schema_version'] = 9
                raw = archive_bytes(value)
                (run / 'review.json').write_bytes(raw)
                manifest = fixture.read(run / 'cierre.json')
                manifest['hashes']['review.json'] = hashlib.sha256(raw).hexdigest()
                self.save(fixture, run, manifest)
                cleanup_file = fixture.write('same-cleanup.json', manifest['close_observation'])
                changed = fixture.snapshot(run)
                commands = {
                    'summary': ['inspect', '--run-dir', run, '--summary'],
                    'automatic': ['finish', '--run-dir', run],
                    'inline': ['finish', '--run-dir', run, '--cleanup', 'not_needed'],
                    'file': ['finish', '--run-dir', run, '--cleanup-file', cleanup_file],
                }
                for entry, args in commands.items():
                    with self.subTest(boundary=boundary, variant=variant, entry=entry):
                        for name, raw in changed.items():
                            (run / name).write_bytes(raw)
                        code, status = self.cli(fixture, *args)
                        self.assertEqual(code, 0 if entry == 'summary' else 1)
                        self.assertEqual(fixture.snapshot(run), changed)
                        self.assertEqual(status['next_action'], 'preserve')

    def test_final_pending_all_entry_points_require_the_full_complete_record_gate(self):
        for boundary in ('before', 'after'):
            fixture, run = self.final_pending_run(boundary, invalid_plan=False)
            manifest = fixture.read(run / 'cierre.json')
            manifest['cleanup'] = 'complete'
            self.save(fixture, run, manifest)
            cleanup_file = fixture.write('same-cleanup.json', manifest['close_observation'])
            before = fixture.snapshot(run)
            commands = {
                'summary': ['inspect', '--run-dir', run, '--summary'],
                'automatic': ['finish', '--run-dir', run],
                'inline': ['finish', '--run-dir', run, '--cleanup', 'not_needed'],
                'file': ['finish', '--run-dir', run, '--cleanup-file', cleanup_file],
            }
            for entry, args in commands.items():
                with self.subTest(boundary=boundary, entry=entry):
                    for name, raw in before.items():
                        (run / name).write_bytes(raw)
                    code, status = self.cli(fixture, *args)
                    self.assertEqual(code, 0 if entry == 'summary' else 1)
                    self.assertEqual(fixture.snapshot(run), before)
                    self.assertEqual(status['next_action'], 'preserve')

    def test_final_pending_file_replay_uses_the_validated_observation_snapshot(self):
        for boundary in ('before', 'after'):
            with self.subTest(boundary=boundary):
                fixture, run = self.final_pending_run(boundary, invalid_plan=False)
                observation = copy.deepcopy(reader.load_run(run)[1]['close_observation'])
                cleanup_file = fixture.write('captured-cleanup.json',
                                             {'cleanup': 'not_needed', 'residuals': []})
                original = artifacts.close

                def change_request_after_preflight(*args, **kwargs):
                    cleanup_file.write_text('{', encoding='utf-8')
                    return original(*args, **kwargs)

                with patch.object(artifacts, 'close', side_effect=change_request_after_preflight):
                    code, status = fixture.archive_command('finish', '--run-dir', run,
                                                           '--cleanup-file', cleanup_file)
                self.assertEqual((code, status['status']), (0, 'complete'))
                self.assertEqual(lifecycle.validate(run, require_complete=True)['state'], 'complete')
                self.assertEqual(reader.load_run(run)[1]['close_observation'], observation)


if __name__ == '__main__':
    unittest.main()
