"""Sixth CCR: distinguish supported cancellation from an independent review."""
from pathlib import Path
import copy
import json
import shutil
import subprocess
import sys
import unittest
from unittest.mock import patch

import test_review_recovery_diagnostics as diagnostics

artifacts = diagnostics.artifacts
from ccr.archive import restart as restart_ops
recovery = diagnostics.recovery
claims = diagnostics.claims


class RecoveryExitGuidanceTests(unittest.TestCase):
    setUp = diagnostics.RecoveryDiagnosticTests.setUp
    git = diagnostics.RecoveryDiagnosticTests.git
    write = diagnostics.RecoveryDiagnosticTests.write
    read = diagnostics.RecoveryDiagnosticTests.read
    snapshot = diagnostics.RecoveryDiagnosticTests.snapshot
    profile_input = diagnostics.RecoveryDiagnosticTests.profile_input
    prepare7 = diagnostics.RecoveryDiagnosticTests.prepare7
    current = diagnostics.RecoveryDiagnosticTests.current
    controller = diagnostics.RecoveryDiagnosticTests.controller
    restart_request = diagnostics.RecoveryDiagnosticTests.restart_request
    registered_session = diagnostics.RecoveryDiagnosticTests.registered_session
    resource_fixture = diagnostics.RecoveryDiagnosticTests.resource_fixture
    context = diagnostics.RecoveryDiagnosticTests.context
    missing_session_restart = diagnostics.RecoveryDiagnosticTests.missing_session_restart

    def missing_after_transfer_intent(self):
        source, session, request = self.resource_fixture(True)
        replace = artifacts.os.replace
        def interrupted(stage, target):
            # The first sidecar write occurs after both durable transfer intents.
            if Path(target) == session / claims.CLAIM_NAME:
                raise KeyboardInterrupt('transfer intent durable, sidecar not replaced')
            return replace(stage, target)
        with patch.object(artifacts.os, 'replace', side_effect=interrupted):
            with self.assertRaises(KeyboardInterrupt):
                artifacts.restart(source, **request)
        active = artifacts._active_restart_operation(source, self.read(source / 'cierre.json'))
        successor = Path(active['successor_run_dir'])
        self.assertTrue(self.read(source / 'cierre.json')['resource_transfers'])
        self.assertTrue(session.is_relative_to(self.root))
        shutil.rmtree(session)
        kwargs = dict(intent_path=active['intent_path'], controller=self.controller(),
                      authority='User requests cancellation', reason='Workspace disappeared during transfer')
        return source, successor, session, request, kwargs

    def diagnostics_for(self, source, request):
        inspected = recovery.inspect_run(source)
        candidates = recovery.find_candidates(self.repo, self.read(source / 'cierre.json')['scope'],
            archive_root=self.output, current_inputs=request['current_inputs'])
        candidate = next(row for row in candidates['candidates'] if row['run_dir'] == str(source))
        recovered = artifacts.recover(source, controller=self.controller(), authority=request['authority'],
                                      current_inputs=request['current_inputs'])
        self.assertEqual(recovered['status'], 'restart_pending')
        return inspected, candidate, recovered

    def test_missing_before_transfer_exposes_exact_abandonment_without_writes(self):
        source, successor, _, request, kwargs = self.missing_session_restart()
        before = self.snapshot(source), self.snapshot(successor)
        active = artifacts._active_restart_operation(source, self.read(source / 'cierre.json'))
        for result in self.diagnostics_for(source, request):
            action = result['actions'][0]
            self.assertEqual(action['action'], 'abandon_restart')
            self.assertEqual(action['run_dir'], str(source))
            self.assertEqual(action['intent_path'], active['intent_path'])
            self.assertEqual(action['operation_id'], active['operation_id'])
            self.assertTrue(action['requires_explicit_authority'])
        command = [sys.executable, '-B', str(Path(artifacts.__file__).parent), 'artifacts', 'recover', '--run-dir', str(source),
            '--controller-input', str(self.write('controller-guidance.json', self.controller())),
            '--authority-input', str(self.write('authority-guidance.json', request['authority'])),
            '--current-inputs', str(self.write('current-guidance.json', request['current_inputs']))]
        process = subprocess.run(command, capture_output=True, encoding='utf-8', check=True)
        result = json.loads(process.stdout)
        self.assertEqual(result['actions'][0]['action'], 'abandon_restart')
        self.assertEqual((self.snapshot(source), self.snapshot(successor)), before)
        receipt = artifacts.abandon_restart(source, **kwargs)
        self.assertEqual(self.read(successor / 'cierre.json')['restart_abandonment'], receipt)

    def test_missing_after_transfer_intent_exposes_independent_review_without_release(self):
        source, successor, _, request, kwargs = self.missing_after_transfer_intent()
        before = self.snapshot(source), self.snapshot(successor)
        for result in self.diagnostics_for(source, request):
            action = result['actions'][0]
            self.assertEqual(action['action'], 'new_independent_review')
            self.assertIsNone(action['previous_run'])
            self.assertTrue(action['requires_explicit_authority'])
            self.assertTrue(action['use_fresh_resources'])
            self.assertNotIn('abandon_restart', [row['action'] for row in result['actions']])
        with self.assertRaises(ValueError):
            artifacts.abandon_restart(source, **kwargs)
        self.assertEqual((self.snapshot(source), self.snapshot(successor)), before)
        fresh, fresh_session, _ = self.registered_session()
        self.assertIsNone(self.read(fresh / 'cierre.json').get('previous_run'))
        self.assertEqual(claims.verify_claim(fresh_session, fresh)['archive_path'], str(fresh))
        self.assertEqual((self.snapshot(source), self.snapshot(successor)), before)
        self.assertIsNotNone(artifacts._active_restart_operation(source, self.read(source / 'cierre.json')))
        self.assertFalse(self.read(source / 'cierre.json').get('cleanup_receipts'))

    def test_changed_inputs_do_not_receive_an_exact_request_exit(self):
        source, successor, _, request, _ = self.missing_session_restart()
        changed = copy.deepcopy(request['current_inputs'])
        changed['description_identity'] = 'Different description after the interruption'
        before = self.snapshot(source), self.snapshot(successor)
        result = artifacts.recover(source, controller=self.controller(), authority=request['authority'], current_inputs=changed)
        self.assertFalse(result['replay_inputs_match'])
        self.assertEqual([row['action'] for row in result['actions']], ['retry_restart'])
        self.assertEqual((self.snapshot(source), self.snapshot(successor)), before)

    def test_missing_unclaimed_session_still_completes_the_exact_restart(self):
        source, session, request = self.resource_fixture(False)
        with patch.object(restart_ops, 'register', side_effect=KeyboardInterrupt('before any adoption claim')):
            with self.assertRaises(KeyboardInterrupt):
                artifacts.restart(source, **request)
        self.assertTrue(session.is_relative_to(self.root))
        shutil.rmtree(session)
        result = artifacts.recover(source, controller=self.controller(), authority=request['authority'],
                                   current_inputs=request['current_inputs'])
        self.assertEqual(result['status'], 'restarted')
        artifacts.validate(result['successor_run_dir'])
        self.assertEqual(recovery.inspect_run(result['successor_run_dir'])['resources'][0]['availability'], 'missing_unclaimed')

    @unittest.skipUnless(sys.platform == 'win32', 'Windows case alias')
    def test_missing_claim_with_case_alias_still_offers_abandonment(self):
        source, session, request = self.resource_fixture(True)
        request['transfer_paths'] = [str(session).upper()]
        with patch.object(restart_ops, 'transfer_resources', side_effect=KeyboardInterrupt('prepared alias before transfer')):
            with self.assertRaises(KeyboardInterrupt):
                artifacts.restart(source, **request)
        self.assertTrue(session.is_relative_to(self.root))
        shutil.rmtree(session)
        result = artifacts.recover(source, controller=self.controller(), authority=request['authority'],
                                   current_inputs=request['current_inputs'])
        self.assertEqual(result['actions'][0]['action'], 'abandon_restart')

    def test_local_corruption_is_not_converted_to_an_alternative_review(self):
        for target in ('source', 'successor', 'reservation', 'reservation_after_transfer', 'reservation_with_work'):
            with self.subTest(target=target):
                self.output = self.root / ('archive-corrupt-' + target)
                fixture = self.missing_after_transfer_intent if target == 'reservation_after_transfer' else self.missing_session_restart
                source, successor, _, request, _ = fixture()
                if target.startswith('reservation'):
                    (successor / '.review-restart-reservation.json').write_text('{}', encoding='utf-8')
                    if target == 'reservation_with_work':
                        (successor / 'evidence').mkdir()
                        (successor / 'evidence' / 'work.txt').write_text('Actual work', encoding='utf-8')
                else:
                    run = source if target == 'source' else successor
                    with (run / 'trazabilidad.jsonl').open('ab') as stream:
                        stream.write(b'corrupt bytes\n')
                before = self.snapshot(source), self.snapshot(successor)
                result = recovery.inspect_run(source)
                self.assertEqual(result['integrity']['status'], 'invalid')
                self.assertEqual([row['action'] for row in result['actions']], ['preserve'])
                with self.assertRaises(ValueError):
                    artifacts.recover(source, controller=self.controller(), authority=request['authority'],
                                      current_inputs=request['current_inputs'])
                self.assertEqual((self.snapshot(source), self.snapshot(successor)), before)
