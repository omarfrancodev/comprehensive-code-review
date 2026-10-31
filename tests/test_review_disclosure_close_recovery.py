"""Interrupted cleanup close must recover only the owned coherent disclosure pair."""
import argparse
import base64
import copy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from script_test_support import enable_package_imports, workspace_api

enable_package_imports()
from ccr.archive import lifecycle, retention
from ccr.shared.encoding import archive_bytes
from profile_topology_fixtures import record12
import test_review_topology_integration as topology_tests

workspace = workspace_api()


class DisclosureCloseRecoveryTests(unittest.TestCase):
    def retained_cleaned_run(self, optional_evidence=False, disclosure_format=None):
        helper = topology_tests.TopologyIntegrationTests()
        case = helper.archive()
        self.addCleanup(case.doCleanups)
        session = Path(workspace.prepare(argparse.Namespace(
            repo=str(case.repo), ref='HEAD', mode='commit', role=['review'], include_untracked=[]))['session_dir'])
        run = case.prepare(temporary_paths=[str(session)])
        real_retain = topology_tests.artifacts.retain
        selected_disclosure = []
        def retain_with_optional_evidence(*args, **kwargs):
            if disclosure_format is not None:
                path = next(path for path in kwargs['evidence_inputs']
                            if Path(path).name == 'check-disclosure.json')
                value = case.read(path)
                if disclosure_format == 'compact':
                    raw = json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
                elif disclosure_format in ('at_bound', 'over_bound'):
                    from ccr.contracts.check_disclosure import MAX_BYTES
                    raw = json.dumps(value).encode('utf-8')
                    size = MAX_BYTES + (disclosure_format == 'over_bound')
                    raw += b' ' * (size - len(raw))
                else:
                    raw = (' \n' + json.dumps(value, ensure_ascii=False, indent=3) + '\n\t').encode('utf-8')
                Path(path).write_bytes(raw)
                selected_disclosure.append(raw)
            if optional_evidence:
                from ccr.workflow.builders import build_model_usage_update
                manifest = case.read(run / 'cierre.json')
                context = case.read(kwargs['context_input'])
                context, ledger = build_model_usage_update(context, None, {'model': 'test-model'},
                    actor={'kind': 'coordinator', 'name': 'coordinator', 'provider_id': None},
                    phase='coordination', activity='coordination', review_id='CR-' + manifest['run_id'],
                    harness_id=manifest['harness_id'])
                kwargs['context_input'] = case.write('with-model-context.json', context)
                kwargs['evidence_inputs'].append(case.write('model-usage.json', ledger))
                kwargs['handoff'] = True
            return real_retain(*args, **kwargs)
        with patch.object(topology_tests.artifacts, 'retain', side_effect=retain_with_optional_evidence):
            value = record12('focused', 'automatic', discovery=1)
            if disclosure_format is not None:
                value['resources'].update(cleanup='pending', residuals=[str(session)])
            helper.retain12(case, run, value)
        self.assertTrue(lifecycle.validate(run, require_retained=True)['retained'])
        if selected_disclosure:
            self.assertEqual((run / 'evidence/check-disclosure.json').read_bytes(), selected_disclosure[0])
        previous = case.read(run / 'review.json')
        self.assertEqual(previous['resources']['cleanup'], 'pending')
        self.assertEqual(previous['resources']['residuals'], [str(session)])
        workspace.cleanup(argparse.Namespace(manifest=str(session / 'manifest.json'), run_dir=str(run)))
        self.assertFalse(session.exists())
        self.assertEqual(case.read(run / 'cierre.json')['resource_cleanup']['status'], 'complete')
        return case, run, previous

    def interrupt(self, case, run, boundary):
        original = retention.atomic_write
        def stop(path, data, **kwargs):
            if Path(path).name == 'check-disclosure.json':
                if boundary == 'after':
                    original(path, data, **kwargs)
                raise OSError('close disclosure boundary')
            return original(path, data, **kwargs)
        with patch.object(retention, 'atomic_write', side_effect=stop):
            with self.assertRaisesRegex(OSError, 'close disclosure boundary'):
                lifecycle.close(run, cleanup='complete')
        self.assertEqual(case.read(run / 'cierre.json')['state'], 'retaining')
        self.assertEqual(case.read(run / 'review.json')['resources']['cleanup'], 'complete')

    def test_close_recovers_before_disclosure_replacement(self):
        self.assert_recovers('before')

    def test_close_recovers_after_disclosure_replacement(self):
        self.assert_recovers('after')

    def test_close_recovers_with_selected_model_sidecar_and_handoff(self):
        self.assert_recovers('before', optional_evidence=True)

    def test_close_recovers_exact_noncanonical_selected_disclosure(self):
        for formatting in ('compact', 'noncanonical'):
            for boundary in ('before', 'after'):
                with self.subTest(formatting=formatting, boundary=boundary):
                    self.assert_recovers(boundary, disclosure_format=formatting)

    def test_close_recovers_padded_selected_disclosure_at_byte_bound(self):
        self.assert_recovers('after', disclosure_format='at_bound')

    def test_oversized_selected_disclosure_close_refuses_before_intent_writes(self):
        case, run, _ = self.retained_cleaned_run(disclosure_format='over_bound')
        before = case.snapshot(run)
        with self.assertRaisesRegex(ValueError, 'previous disclosure.*byte.*limit'):
            lifecycle.close(run, cleanup='complete')
        self.assertEqual(case.snapshot(run), before)
        self.assertTrue(lifecycle.validate(run, require_retained=True)['retained'])

    def assert_recovers(self, boundary, optional_evidence=False, disclosure_format=None):
        case, run, previous = self.retained_cleaned_run(optional_evidence, disclosure_format)
        model_bytes = (run / 'evidence/model-usage.json').read_bytes() if optional_evidence else None
        old_disclosure = case.read(run / 'evidence/check-disclosure.json')
        self.interrupt(case, run, boundary)
        interrupted = case.snapshot(run)
        with patch.object(lifecycle, '_retain_data', side_effect=AssertionError('premature recovery write')):
            with self.assertRaisesRegex(ValueError, 'exact durable cleanup observation'):
                lifecycle.close(run, cleanup='pending')
            receipts = case.read(run / 'cierre.json')['cleanup_receipts']
            altered = [dict(receipts[0], claim_sha256='0' * 64)]
            with self.assertRaisesRegex(ValueError, 'durable cleanup receipt'):
                lifecycle.close(run, cleanup='complete', released_claims=altered)
        self.assertEqual(case.snapshot(run), interrupted)
        result = lifecycle.close(run, cleanup='complete')
        self.assertEqual(result['state'], 'complete')
        self.assertEqual(lifecycle.validate(run, require_complete=True)['state'], 'complete')
        current = case.read(run / 'review.json')
        expected = copy.deepcopy(previous)
        expected['resources'].update(cleanup='complete', residuals=[])
        self.assertEqual(current, expected)
        new_disclosure = case.read(run / 'evidence/check-disclosure.json')
        self.assertEqual(new_disclosure['checks'], old_disclosure['checks'])
        self.assertNotEqual(new_disclosure['source_sha256'], old_disclosure['source_sha256'])
        if optional_evidence:
            self.assertEqual((run / 'evidence/model-usage.json').read_bytes(), model_bytes)
            self.assertTrue((run / 'handoff.md').is_file())
        complete = case.snapshot(run)
        lifecycle.close(run, cleanup='complete')
        self.assertEqual(case.snapshot(run), complete)

    def test_tampered_disclosure_cannot_be_recovered(self):
        case, run, _ = self.retained_cleaned_run()
        self.interrupt(case, run, 'before')
        path = run / 'evidence/check-disclosure.json'
        path.write_bytes(path.read_bytes() + b' ')
        before = case.snapshot(run)
        with self.assertRaises(ValueError):
            lifecycle.close(run, cleanup='complete')
        self.assertEqual(case.snapshot(run), before)

    def test_invalid_previous_disclosure_evidence_is_rejected_without_writes(self):
        case, run, _ = self.retained_cleaned_run()
        old_bytes = (run / 'evidence/check-disclosure.json').read_bytes()
        self.interrupt(case, run, 'after')
        manifest = case.read(run / 'cierre.json')
        interrupted = case.snapshot(run)
        from ccr.contracts.check_disclosure import MAX_BYTES
        invalid = [
            None,
            {'reference': 'evidence/check-disclosure.json', 'base64': '!invalid!'},
            {'reference': 'evidence/check-disclosure.json', 'base64': 'A' * (4 * ((MAX_BYTES + 2) // 3) + 4)},
            {'reference': 'evidence/check-disclosure.json', 'base64': base64.b64encode(old_bytes + b' ').decode('ascii')},
            {'reference': 'evidence/unselected.json', 'base64': base64.b64encode(old_bytes).decode('ascii')},
        ]
        for evidence in invalid:
            with self.subTest(evidence_kind=type(evidence).__name__, reference=(evidence or {}).get('reference')):
                for name, raw in interrupted.items():
                    (run / name).write_bytes(raw)
                changed = copy.deepcopy(manifest)
                changed['close_previous_disclosure'] = evidence
                lifecycle._save_manifest(run, changed, case.read(run / '.review-ownership.json'))
                before = case.snapshot(run)
                with self.assertRaises(ValueError):
                    lifecycle.close(run, cleanup='complete')
                self.assertEqual(case.snapshot(run), before)

    def test_repeated_close_interruption_keeps_exact_previous_disclosure(self):
        case, run, _ = self.retained_cleaned_run(disclosure_format='noncanonical')
        old_bytes = (run / 'evidence/check-disclosure.json').read_bytes()
        self.interrupt(case, run, 'after')
        self.interrupt(case, run, 'before')
        self.assertEqual(base64.b64decode(case.read(run / 'cierre.json')[
            'close_previous_disclosure']['base64']), old_bytes)
        lifecycle.close(run, cleanup='complete')
        self.assertEqual(lifecycle.validate(run, require_complete=True)['state'], 'complete')
        self.assertNotIn('close_previous_disclosure', case.read(run / 'cierre.json'))

    def test_changed_planned_inventory_cannot_be_adopted(self):
        case, run, _ = self.retained_cleaned_run()
        self.interrupt(case, run, 'after')
        manifest = case.read(run / 'cierre.json')
        manifest['planned_hashes']['evidence/check-disclosure.json'] = '0' * 64
        lifecycle._save_manifest(run, manifest, case.read(run / '.review-ownership.json'))
        before = case.snapshot(run)
        with self.assertRaises(ValueError):
            lifecycle.close(run, cleanup='complete')
        self.assertEqual(case.snapshot(run), before)

    def test_rehashed_unrelated_review_mutation_cannot_be_recovered(self):
        case, run, _ = self.retained_cleaned_run()
        self.interrupt(case, run, 'before')
        value = case.read(run / 'review.json')
        value['checks'][0]['command'] = 'invented command'
        payload = archive_bytes(value)
        (run / 'review.json').write_bytes(payload)
        manifest = case.read(run / 'cierre.json')
        manifest['planned_hashes']['review.json'] = hashlib.sha256(payload).hexdigest()
        lifecycle._save_manifest(run, manifest, case.read(run / '.review-ownership.json'))
        before = case.snapshot(run)
        with self.assertRaisesRegex(ValueError, 'owned previous review'):
            lifecycle.close(run, cleanup='complete')
        self.assertEqual(case.snapshot(run), before)

    def test_rehashed_extra_planned_file_cannot_expand_close_inventory(self):
        case, run, _ = self.retained_cleaned_run()
        self.interrupt(case, run, 'before')
        payload = b'{}'
        (run / 'evidence/unrequested.json').write_bytes(payload)
        manifest = case.read(run / 'cierre.json')
        manifest['planned_hashes']['evidence/unrequested.json'] = hashlib.sha256(payload).hexdigest()
        lifecycle._save_manifest(run, manifest, case.read(run / '.review-ownership.json'))
        before = case.snapshot(run)
        with self.assertRaisesRegex(ValueError, 'exact planned inventory'):
            lifecycle.close(run, cleanup='complete')
        self.assertEqual(case.snapshot(run), before)


if __name__ == '__main__':
    unittest.main()
