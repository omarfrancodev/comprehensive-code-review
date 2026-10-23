"""Provisional checkpoints preserve selected review inputs without certifying them."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import test_review_artifacts as archive

artifacts = archive.artifacts
SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))

from recovery_fixtures import context10, record10, selection, source_events
from ccr.reporting import delivery as review_delivery
from ccr.contracts import model_usage as review_model_usage


class CheckpointTests(unittest.TestCase):
    setUp = archive.ArchiveTests.setUp
    git = archive.ArchiveTests.git
    write = archive.ArchiveTests.write
    read = archive.ArchiveTests.read
    snapshot = archive.ArchiveTests.snapshot
    profile_input = archive.Archive7Tests.profile_input
    prepare7 = archive.Archive7Tests.prepare7

    def start_run(self):
        run = self.prepare7()
        context = context10(self.final_record(run))
        context_file = self.write('context.json', context)
        artifacts.register(run, [], context_input=context_file)
        return run, context_file

    def packet_files(self, profile='focused'):
        if profile == 'deep':
            names = ['D1', 'D2', 'V1']
        else:
            names = ['D1', 'V1']
        briefs = self.write('briefs.json', {name: {'question': 'Check the invariant'} for name in names})
        results = self.write('results.json', {name: {'result': 'reviewed'} for name in names})
        return [briefs, results]

    def final_record(self, run, profile='focused', late_profile=False):
        from recovery_fixtures import record10
        value = record10(profile, 'automatic')
        value['scope'] = archive.record()['scope']
        value['description'] = {'status': 'not_applicable', 'identity': None, 'details': ''}
        manifest = self.read(run / 'cierre.json')
        value['review_id'] = 'CR-' + manifest['run_id']
        value['coverage']['execution']['profile_history'] = copy.deepcopy(manifest['profile_history'])
        for row in value['coverage']['execution']['plan']:
            row['selection_id'] = 'S001'
            row['superseded_by'] = None
        if late_profile:
            row = selection('deep', 'automatic',
                            reference='evidence/context.json#profile_history/0/profile',
                            event_id='E000005')
            value['coverage']['execution']['profile_history'] = [row]
        return value

    def prepare_promotable_checkpoint(self, *, external_source=None, captured_hash=None,
                                      expected_gate_error=None):
        run = self.prepare7()
        final = self.final_record(run)
        context_file = self.write('valid-context.json', context10(final))
        if external_source is not None:
            context = self.read(context_file)
            context['review_inputs']['sources']['evidence/requirements.md'] = captured_hash
            context_file = self.write('valid-context.json', context)
        artifacts.register(run, [], context_input=context_file)
        for raw in source_events(final):
            if raw['kind'] == 'profile':
                continue
            identity = raw.get('actor')
            event = {'kind': raw['kind'], 'status': raw['status'],
                     'summary': 'Observed synthetic review execution',
                     'provenance': {'kind': 'agent', 'source': 'synthetic checkpoint promotion test'},
                     'evidence': raw['evidence']}
            if identity is not None:
                event['actor'] = {'kind': 'agent', **identity}
            if raw.get('executor') is not None:
                event['executor'] = raw['executor']
            artifacts.record_event(run, self.write('milestone.json', event))
        packets = self.packet_files()
        if external_source is not None:
            packets.append(external_source)
        result = artifacts.checkpoint(run, context_input=context_file, evidence_inputs=packets,
                                      input_record=self.write('valid-final.json', final), phase='report')
        if expected_gate_error is None:
            self.assertEqual(result['gate_errors'], [])
        else:
            self.assertTrue(any(expected_gate_error in error for error in result['gate_errors']),
                            result['gate_errors'])
        return run, context_file, packets

    def test_packet_checkpoint_without_verdict(self):
        run, context = self.start_run()
        artifacts.record_event(run, self.write('work-start.json',
            {'kind': 'discovery', 'status': 'started', 'summary': 'Discovery started',
             'evidence': ['evidence/briefs.json#D1']}))
        packets = self.packet_files()
        checkpoint = artifacts.checkpoint(run, context_input=context, evidence_inputs=packets,
                                          phase='discovery')
        manifest = self.read(run / 'cierre.json')
        self.assertEqual(checkpoint['id'], 'K001')
        self.assertFalse(manifest['retained'])
        self.assertEqual(manifest['state'], 'processing')
        self.assertTrue((run / 'pending' / 'context.json').is_file())
        self.assertTrue((run / 'pending' / 'evidence' / 'briefs.json').is_file())
        self.assertFalse((run / 'review.json').exists())
        self.assertFalse((run / 'pending' / 'review.json').exists())
        self.assertEqual(artifacts.validate(run)['retained'], False)
        before = self.snapshot(run)
        replay = artifacts.checkpoint(run, context_input=context, evidence_inputs=packets,
                                      phase='discovery')
        self.assertEqual(replay['id'], 'K001')
        self.assertEqual(self.snapshot(run), before)

    def test_final_checkpoint_with_profile_source_gate_error_is_not_retained(self):
        run, _ = self.start_run()
        packets = self.packet_files('deep')
        final = self.final_record(run, 'deep', late_profile=True)
        self.assertEqual(artifacts.review_contract.validate(final), [])
        context = context10(final)
        context_file = self.write('late-context.json', context)
        result = artifacts.checkpoint(run, context_input=context_file, evidence_inputs=packets,
                                     input_record=self.write('late-final.json', final), phase='verification')
        manifest = self.read(run / 'cierre.json')
        self.assertTrue((run / 'pending' / 'review.json').is_file())
        self.assertTrue((run / 'pending' / 'informe.md').is_file())
        self.assertFalse((run / 'review.json').exists())
        self.assertFalse((run / 'informe.md').exists())
        self.assertFalse(manifest['retained'])
        self.assertEqual(manifest['profile_history'][0]['profile'], 'focused')
        self.assertTrue(any('archive profile history' in item for item in result['gate_errors']))
        with self.assertRaisesRegex(ValueError, 'retained evidence'):
            artifacts.validate(run, require_retained=True)

    def test_valid_final_checkpoint_can_be_promoted_without_external_files(self):
        run, _, _ = self.prepare_promotable_checkpoint()
        retained = artifacts.retain(run)
        self.assertTrue(retained['retained'])
        self.assertTrue((run / 'review.json').is_file())
        self.assertEqual(artifacts.validate(run, require_retained=True)['retained'], True)

    def test_private_model_usage_sidecar_is_selected_and_retained_by_link(self):
        run, context_file, packets = self.prepare_promotable_checkpoint()
        manifest = self.read(run / 'cierre.json')
        observation = review_model_usage.observation_from_metadata(
            {'model': 'configured-coordinator'},
            actor={'kind': 'coordinator', 'name': 'coordinator', 'provider_id': None},
            phase='report', activity='reporting')
        ledger = review_model_usage.append_model_observation(
            None, observation, review_id='CR-' + manifest['run_id'],
            harness_id=manifest['harness_id'])
        context = self.read(context_file)
        context['model_usage_reference'] = 'evidence/model-usage.json'
        linked_context = self.write('model-context.json', context)
        model_usage_file = self.write('model-usage.json', ledger)

        artifacts.checkpoint(run, context_input=linked_context,
            evidence_inputs=packets + [model_usage_file],
            input_record=run / 'pending' / 'review.json', phase='report')
        pending = self.read(run / 'cierre.json')
        self.assertIn('pending/evidence/model-usage.json', pending['pending_hashes'])
        pending_context = self.read(run / 'pending' / 'context.json')
        self.assertEqual(pending_context['model_usage_reference'], 'evidence/model-usage.json')
        self.assertNotIn('model-usage', pending_context['review_inputs']['sources'])

        artifacts.retain(run)
        retained = self.read(run / 'cierre.json')
        self.assertIn('evidence/model-usage.json', retained['hashes'])
        self.assertEqual(self.read(run / 'evidence' / 'model-usage.json'), ledger)

    def test_model_usage_link_with_wrong_review_binding_fails_before_checkpoint_write(self):
        run, context_file = self.start_run()
        context = self.read(context_file)
        context['model_usage_reference'] = 'evidence/model-usage.json'
        linked_context = self.write('wrong-model-context.json', context)
        manifest = self.read(run / 'cierre.json')
        observation = review_model_usage.observation_from_metadata(
            {'model': 'configured-coordinator'},
            actor={'kind': 'coordinator', 'name': 'coordinator', 'provider_id': None},
            phase='discovery', activity='coordination')
        wrong_ledger = review_model_usage.append_model_observation(
            None, observation, review_id='CR-' + 'b' * 20,
            harness_id=manifest['harness_id'])
        sidecar = self.write('model-usage.json', wrong_ledger)
        before = self.snapshot(run)
        with self.assertRaisesRegex(ValueError, 'another review'):
            artifacts.checkpoint(run, context_input=linked_context,
                evidence_inputs=[sidecar], phase='discovery')
        self.assertEqual(self.snapshot(run), before)

    def test_captured_external_source_hash_is_checked_before_retention(self):
        requirements = self.write('requirements.md', {'revision': 'current'})
        run, _, _ = self.prepare_promotable_checkpoint(
            external_source=requirements, captured_hash='0' * 64,
            expected_gate_error='selected external review input differs')

        manifest = self.read(run / 'cierre.json')
        self.assertFalse(manifest['retained'])
        self.assertTrue((run / 'pending' / 'review.json').is_file())
        self.assertTrue(any('selected external review input differs'
                            in error for error in manifest['checkpoint']['gate_errors']))

    def test_new_checkpoint_without_final_invalidates_previous_provisional_report(self):
        run, context, packets = self.prepare_promotable_checkpoint()
        self.assertTrue((run / 'pending' / 'review.json').is_file())
        self.assertTrue((run / 'pending' / 'informe.md').is_file())

        artifacts.checkpoint(run, context_input=context, evidence_inputs=packets, phase='discovery')

        manifest = self.read(run / 'cierre.json')
        self.assertNotIn('pending/review.json', manifest['pending_hashes'])
        self.assertNotIn('pending/informe.md', manifest['pending_hashes'])
        self.assertFalse((run / 'pending' / 'review.json').exists())
        self.assertFalse((run / 'pending' / 'informe.md').exists())
        with self.assertRaisesRegex(ValueError, 'no structurally valid final review'):
            artifacts.retain(run)

    def test_checkpoint_retry_recovers_owned_report_invalidation(self):
        original_unlink = Path.unlink
        for name in ('review.json', 'informe.md'):
            for timing in ('before', 'after'):
                with self.subTest(name=name, timing=timing):
                    run, context, packets = self.prepare_promotable_checkpoint()
                    interrupted = False

                    def fail_once(path, *args, **kwargs):
                        nonlocal interrupted
                        if (not interrupted and Path(path).name == name
                                and 'pending' in Path(path).parts):
                            interrupted = True
                            if timing == 'after':
                                original_unlink(path, *args, **kwargs)
                            raise OSError('injected checkpoint invalidation boundary')
                        return original_unlink(path, *args, **kwargs)

                    with patch.object(Path, 'unlink', autospec=True, side_effect=fail_once), self.assertRaises(OSError):
                        artifacts.checkpoint(run, context_input=context, evidence_inputs=packets,
                                             phase='discovery')
                    artifacts.checkpoint(run, context_input=context, evidence_inputs=packets, phase='discovery')
                    manifest = self.read(run / 'cierre.json')
                    self.assertNotIn('pending/review.json', manifest['pending_hashes'])
                    self.assertNotIn('pending/informe.md', manifest['pending_hashes'])
                    self.assertFalse((run / 'pending' / 'review.json').exists())
                    self.assertFalse((run / 'pending' / 'informe.md').exists())
                    self.assertFalse(artifacts.validate(run)['retained'])

    def test_checkpoint_retry_after_each_write_boundary(self):
        original = artifacts.atomic_write
        for name in ('context.json', 'briefs.json', 'review.json', 'informe.md'):
            for timing in ('before', 'after'):
                with self.subTest(name=name, timing=timing):
                    run, context = self.start_run()
                    packets = self.packet_files()
                    final = self.final_record(run)
                    final_file = self.write('final.json', final)
                    interrupted = False

                    def fail_once(path, data, **kwargs):
                        nonlocal interrupted
                        selected = Path(path)
                        if (not interrupted and selected.name == name
                                and 'pending' in selected.parts):
                            interrupted = True
                            if timing == 'after':
                                original(path, data, **kwargs)
                            raise OSError('injected checkpoint boundary')
                        original(path, data, **kwargs)

                    with archive.patch_archive_atomic_write(fail_once), self.assertRaises(OSError):
                        artifacts.checkpoint(run, context_input=context, evidence_inputs=packets,
                                             input_record=final_file, phase='verification')
                    result = artifacts.checkpoint(run, context_input=context, evidence_inputs=packets,
                                                 input_record=final_file, phase='verification')
                    self.assertEqual(result['id'], 'K001')
                    self.assertIsNone(self.read(run / 'cierre.json').get('checkpoint_transaction'))
                    self.assertTrue(artifacts.validate(run)['retained'] is False)

    def test_checkpoint_retry_recovers_marker_and_manifest_boundaries(self):
        original = artifacts.atomic_write
        boundaries = [(artifacts.MARKER, index, timing)
                      for index in (1, 2, 3, 4) for timing in ('before', 'after')]
        boundaries += [('cierre.json', index, timing)
                       for index in (1, 2) for timing in ('before', 'after')]
        for filename, target_write, timing in boundaries:
            with self.subTest(filename=filename, write=target_write, timing=timing):
                run, context = self.start_run()
                packets = self.packet_files()
                calls = 0

                def fail_once(path, data, **kwargs):
                    nonlocal calls
                    if Path(path).name == filename:
                        calls += 1
                        if calls == target_write:
                            if timing == 'after':
                                original(path, data, **kwargs)
                            raise OSError('injected checkpoint ownership boundary')
                    original(path, data, **kwargs)

                with archive.patch_archive_atomic_write(fail_once), self.assertRaises(OSError):
                    artifacts.checkpoint(run, context_input=context, evidence_inputs=packets, phase='discovery')
                result = artifacts.checkpoint(run, context_input=context, evidence_inputs=packets, phase='discovery')
                self.assertEqual(result['id'], 'K001')
                self.assertIsNone(self.read(run / 'cierre.json').get('checkpoint_transaction'))
                self.assertEqual(artifacts.validate(run)['retained'], False)

    def test_modified_or_foreign_pending_bytes_are_refused(self):
        run, context = self.start_run()
        artifacts.checkpoint(run, context_input=context, evidence_inputs=self.packet_files(), phase='discovery')
        (run / 'pending' / 'context.json').write_text('{}', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'pending'):
            artifacts.validate(run)
        run, context = self.start_run()
        artifacts.checkpoint(run, context_input=context, evidence_inputs=self.packet_files(), phase='discovery')
        (run / 'pending' / 'foreign.txt').write_text('foreign', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'foreign'):
            artifacts.validate(run)

    def test_checkpoint_duplicate_names_links_and_size_limits(self):
        run, context = self.start_run()
        first_dir, second_dir = self.root / 'a', self.root / 'b'
        first_dir.mkdir()
        second_dir.mkdir()
        first, second = first_dir / 'same.json', second_dir / 'same.json'
        first.write_text('{}', encoding='utf-8')
        second.write_text('{}', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            artifacts.checkpoint(run, context_input=context, evidence_inputs=[first, second], phase='discovery')
        link = self.root / 'linked.bin'
        try:
            link.symlink_to(first)
        except OSError:
            pass
        else:
            with self.assertRaisesRegex(ValueError, 'links/reparse'):
                artifacts.checkpoint(run, context_input=context, evidence_inputs=[link], phase='discovery')
        huge = self.write('too-large.bin', {'content': 'x' * 64})
        with self.assertRaisesRegex(ValueError, 'limit'):
            artifacts.checkpoint(run, context_input=context, evidence_inputs=[huge], phase='discovery',
                                 max_evidence_bytes=8)
        oversized = self.write('oversized-context.json', {'value': 'x' * 140000})
        with self.assertRaisesRegex(ValueError, 'context exceeds'):
            artifacts.checkpoint(run, context_input=oversized, phase='discovery')

    def test_pending_cannot_close_deliver_or_publish(self):
        run, context = self.start_run()
        artifacts.checkpoint(run, context_input=context, evidence_inputs=self.packet_files(), phase='discovery')
        with self.assertRaises(ValueError):
            artifacts.close(run, cleanup='not_needed', residuals=[])
        with self.assertRaises(ValueError):
            review_delivery.deliver(run, 'brief', self.repo)
        with self.assertRaises(ValueError):
            artifacts.validate(run, require_retained=True)
        self.assertFalse((self.repo / 'docs').exists())

    def test_cli_checkpoint_accepts_context_packets_phase_and_diagnostics(self):
        run, context = self.start_run()
        diagnostic = self.write('diagnostic.json', {'gate_errors': ['synthetic source gate unavailable']})
        args = [sys.executable, '-B', '-X', 'utf8', str(SCRIPTS), 'artifacts', 'checkpoint',
                '--run-dir', str(run), '--context-input', str(context), '--phase', 'verification',
                '--diagnostic-input', str(diagnostic)]
        for evidence in self.packet_files():
            args += ['--evidence-input', str(evidence)]
        process = subprocess.run(args, capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(process.returncode, 0, process.stderr)
        result = json.loads(process.stdout)
        self.assertEqual(result['id'], 'K001')
        self.assertEqual(result['gate_errors'], ['synthetic source gate unavailable'])


if __name__ == '__main__':
    unittest.main()
