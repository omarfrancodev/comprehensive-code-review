"""Read and replay already reserved native v2 requests without rewriting them."""
import copy
import hashlib
from pathlib import Path
import unittest
from unittest.mock import patch

import test_review_recovery as recovery_tests
from restart_v2_fixtures import previous_v2_producer
import review_restart

artifacts = recovery_tests.artifacts


class PreviousV2RestartTests(unittest.TestCase):
    setUp = recovery_tests.ReviewRecoveryTests.setUp
    git = recovery_tests.ReviewRecoveryTests.git
    write = recovery_tests.ReviewRecoveryTests.write
    read = recovery_tests.ReviewRecoveryTests.read
    snapshot = recovery_tests.ReviewRecoveryTests.snapshot
    profile_input = recovery_tests.ReviewRecoveryTests.profile_input
    prepare7 = recovery_tests.ReviewRecoveryTests.prepare7
    current = recovery_tests.ReviewRecoveryTests.current
    controller = recovery_tests.ReviewRecoveryTests.controller
    restart_request = recovery_tests.ReviewRecoveryTests.restart_request

    def pending(self, boundary='_prepare_from_restart_intent'):
        source = self.prepare7()
        scope = dict(self.read(source / 'cierre.json')['scope'], head='another-reviewed-head')
        request = self.restart_request(source, scope=scope)
        with previous_v2_producer(artifacts), patch.object(artifacts, boundary, side_effect=OSError('interrupted')):
            with self.assertRaisesRegex(OSError, 'interrupted'):
                artifacts.restart(source, **request)
        active_path, _ = artifacts._active_restart_paths(source, self.read(source / 'cierre.json'))
        active = self.read(active_path)
        self.assertEqual(active['intent']['schema_version'], 2)
        self.assertNotIn('logical_scope_identity', active['intent']['request']['current_inputs'])
        return source, request, active, Path(active['intent_path'])

    def assert_completed(self, source, request, active, intent_path, original_bytes):
        intent = active['intent']
        successor = Path(active['successor_run_dir'])
        self.assertEqual(intent_path.read_bytes(), original_bytes)
        self.assertEqual(self.read(successor / 'cierre.json')['restart_operation'],
                         artifacts._restart_operation_row(intent))
        self.assertEqual(self.read(source / 'cierre.json')['operation']['successor'], str(successor))
        artifacts.validate(source)
        artifacts.validate(successor)
        self.assertIsNone(artifacts._active_restart_operation(source, self.read(source / 'cierre.json')))
        before = self.snapshot(self.output)
        self.assertEqual(artifacts.restart(source, **request), str(successor))
        self.assertEqual(self.snapshot(self.output), before)
        self.assertEqual(len(list(self.output.rglob('cierre.json'))), 2)

    def test_previous_v2_recover_preserves_reservation_before_and_after_prepare(self):
        for boundary in ('_prepare_from_restart_intent', '_link_restart'):
            with self.subTest(boundary=boundary):
                self.output = self.root / boundary
                source, request, active, intent_path = self.pending(boundary)
                original_bytes = intent_path.read_bytes()
                result = artifacts.recover(source, controller=request['controller'],
                    authority=request['authority'], current_inputs=request['current_inputs'])
                self.assertEqual(result['status'], 'restarted', result)
                self.assertEqual(result['successor_run_dir'], active['successor_run_dir'])
                self.assert_completed(source, request, active, intent_path, original_bytes)

    def test_previous_v2_retry_preserves_reservation_and_reconstructs_only_missing_file(self):
        for missing in (False, True):
            with self.subTest(missing=missing):
                self.output = self.root / ('retry-' + str(missing))
                source, request, active, intent_path = self.pending()
                original_bytes = intent_path.read_bytes()
                if missing:
                    intent_path.unlink()
                self.assertEqual(artifacts.restart(source, **request), active['successor_run_dir'])
                self.assert_completed(source, request, active, intent_path, original_bytes)

    def test_previous_v2_changed_inputs_do_not_replay_or_replace_intent(self):
        source, request, active, intent_path = self.pending()
        before = self.snapshot(self.output)
        for field, value in (
                ('scope', dict(request['current_inputs']['scope'], head='different-head')),
                ('sources', {'evidence/changed.md': 'a' * 64}),
                ('description_identity', 'different-description'),
                ('requirements_identity', 'different-requirements'),
                ('plan_identity', 'different-plan'),
                ('configuration_identity', 'different-configuration'),
                ('logical_scope_identity', '0' * 64)):
            with self.subTest(field=field):
                changed = copy.deepcopy(request)
                changed['current_inputs'][field] = value
                result = artifacts.recover(source, controller=request['controller'],
                    authority=request['authority'], current_inputs=changed['current_inputs'])
                self.assertFalse(result['replay_inputs_match'])
                with self.assertRaisesRegex(ValueError, 'different restart request|logical scope differs'):
                    artifacts.restart(source, **changed)
                self.assertEqual(self.snapshot(self.output), before)
        self.assertEqual(self.read(intent_path), active['intent'])

    def test_previous_v2_validator_preserves_bytes_and_rejects_hash_tampering(self):
        source, request, active, intent_path = self.pending()
        before = intent_path.read_bytes()
        self.assertEqual(review_restart.validate_restart_intent(active['intent']), [])
        for field in ('request_sha256', 'intent_sha256', 'operation_id'):
            with self.subTest(field=field):
                changed = copy.deepcopy(active['intent'])
                changed[field] = '0' * len(changed[field])
                self.assertTrue(review_restart.validate_restart_intent(changed))
        self.assertEqual(intent_path.read_bytes(), before)

    def test_previous_v2_still_rejects_resigned_noncanonical_or_contradictory_request(self):
        _, _, active, _ = self.pending()
        for mutation in ('controller', 'logical_scope_identity'):
            with self.subTest(mutation=mutation):
                changed = copy.deepcopy(active['intent'])
                if mutation == 'controller':
                    changed['request']['controller']['identity']['name'] += ' '
                else:
                    changed['request']['current_inputs']['logical_scope_identity'] = '0' * 64
                changed['request_sha256'] = review_restart._sha(review_restart._request_identity(changed['request']))
                changed['operation_id'] = hashlib.sha256((review_restart._source_key(changed['source'])
                    + '\n' + changed['source']['owner_id'] + '\n' + changed['request_sha256']).encode('utf-8')).hexdigest()[:32]
                changed.pop('intent_sha256')
                changed['intent_sha256'] = review_restart._sha(changed)
                errors = review_restart.validate_restart_intent(changed)
                self.assertTrue(errors)
                self.assertFalse(any('digest differs' in error for error in errors), errors)

    def test_completed_retry_preserves_ambiguous_encoding_collision(self):
        source, request, active, _ = self.pending()
        artifacts.recover(source, controller=request['controller'], authority=request['authority'],
                          current_inputs=request['current_inputs'])
        normalized = review_restart.normalize_restart_request(
            request['profile_input'], request['controller'], request['authority'],
            request['current_inputs'], [], None, None)
        canonical_path = artifacts._restart_intent_path(source, self.read(source / 'cierre.json'), normalized)
        canonical_path.write_bytes(b'occupied destination')
        before = self.snapshot(self.output)
        with self.assertRaisesRegex(ValueError, 'multiple restart intents'):
            artifacts.restart(source, **request)
        self.assertEqual(self.snapshot(self.output), before)


if __name__ == '__main__':
    unittest.main()
