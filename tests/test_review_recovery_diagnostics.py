"""Fifth CCR: local successor integrity and read-only cancellation preflight."""
from pathlib import Path
import argparse
import copy
import json
import shutil
import unittest
from unittest.mock import patch

import test_review_recovery_reservations as reservations
import review_workspace

artifacts = reservations.artifacts
claims = reservations.claims
recovery = reservations.recovery


class RecoveryDiagnosticTests(unittest.TestCase):
    setUp = reservations.RecoveryReservationTests.setUp
    git = reservations.RecoveryReservationTests.git
    write = reservations.RecoveryReservationTests.write
    read = reservations.RecoveryReservationTests.read
    snapshot = reservations.RecoveryReservationTests.snapshot
    profile_input = reservations.RecoveryReservationTests.profile_input
    prepare7 = reservations.RecoveryReservationTests.prepare7
    current = reservations.RecoveryReservationTests.current
    controller = reservations.RecoveryReservationTests.controller
    restart_request = reservations.RecoveryReservationTests.restart_request
    registered_session = reservations.RecoveryReservationTests.registered_session
    resource_fixture = reservations.RecoveryReservationTests.resource_fixture
    context = reservations.RecoveryReservationTests.context
    adoption_conflict = reservations.RecoveryReservationTests.adoption_conflict

    def test_live_successor_does_not_require_readable_historical_source(self):
        for case in ('missing', 'invalid'):
            with self.subTest(case=case):
                self.output = self.root / ('archive-' + case)
                source, session, request = self.resource_fixture(True)
                successor = Path(artifacts.restart(source, **request))
                if case == 'missing':
                    self.assertTrue(source.is_relative_to(self.root))
                    source.rename(source.with_name(source.name + '-unavailable'))
                else:
                    (source / artifacts.MARKER).write_text('{}', encoding='utf-8')
                before = self.snapshot(successor), self.snapshot(session)
                inspected = recovery.inspect_run(successor)
                self.assertEqual(inspected['integrity']['status'], 'verified')
                self.assertIn('continue', [row['action'] for row in inspected['actions']])
                candidates = recovery.find_candidates(self.repo, self.read(successor / 'cierre.json')['scope'],
                    archive_root=self.output, current_inputs=self.current(successor))
                candidate = next(row for row in candidates['candidates'] if row['run_dir'] == str(successor))
                self.assertEqual(candidate['integrity'], 'manifest_verified')
                result = artifacts.recover(successor, controller=self.read(successor / 'cierre.json')['controller'], authority='Recover this review',
                                           current_inputs=self.current(successor))
                self.assertEqual(result['status'], 'ready')
                artifacts.validate(successor)
                self.assertEqual((self.snapshot(successor), self.snapshot(session)), before)
                # The optional historical lookup must not mask local corruption.
                with (successor / 'trazabilidad.jsonl').open('ab') as stream:
                    stream.write(b'corruption\n')
                self.assertEqual(recovery.inspect_run(successor)['integrity']['status'], 'invalid')
                with self.assertRaises(ValueError):
                    artifacts.recover(successor, controller=self.controller(), authority='Recover this review',
                                      current_inputs=self.current(successor))

    def pending_source_trace(self, source):
        run, manifest, marker = artifacts._load_run(source)
        with patch.object(artifacts, '_recover_trace', side_effect=KeyboardInterrupt('pending helper event')):
            with self.assertRaises(KeyboardInterrupt):
                artifacts._append_trace(run, manifest, marker,
                    artifacts._milestone('interruption', 'Owned pending event before cancellation'))
        self.assertIsNotNone(self.read(source / 'cierre.json')['pending_trace'])

    def test_rejected_abandon_preserves_pending_source_trace_and_successor(self):
        source, successor, session, foreign, _, kwargs = self.adoption_conflict()
        (successor / 'evidence').mkdir()
        (successor / 'evidence' / 'work.txt').write_text('Actual review work', encoding='utf-8')
        self.pending_source_trace(source)
        paths = (source, successor, session, foreign)
        before = tuple(self.snapshot(path) for path in paths)
        with self.assertRaises(ValueError):
            artifacts.abandon_restart(source, **kwargs)
        self.assertEqual(tuple(self.snapshot(path) for path in paths), before)
        self.assertIsNotNone(self.read(source / 'cierre.json')['pending_trace'])

    def test_accepted_abandon_replays_owned_source_event_once(self):
        source, successor, session, foreign, _, kwargs = self.adoption_conflict()
        self.pending_source_trace(source)
        foreign_before = self.snapshot(foreign), self.snapshot(session)
        receipt = artifacts.abandon_restart(source, **kwargs)
        self.assertEqual(artifacts.abandon_restart(source, **kwargs), receipt)
        self.assertEqual((self.snapshot(foreign), self.snapshot(session)), foreign_before)
        self.assertNotIn('pending_trace', self.read(source / 'cierre.json'))
        events = [json.loads(line) for line in (source / 'trazabilidad.jsonl').read_bytes().splitlines()]
        self.assertEqual(sum(row['summary'] == 'Owned pending event before cancellation' for row in events), 1)
        artifacts.validate(source)
        artifacts.validate(successor)

    def test_abandon_rejects_modified_pending_trace_without_writing(self):
        source, successor, session, foreign, _, kwargs = self.adoption_conflict()
        self.pending_source_trace(source)
        with (source / 'trazabilidad.jsonl').open('ab') as stream:
            stream.write(b'modified\n')
        paths = (source, successor, session, foreign)
        before = tuple(self.snapshot(path) for path in paths)
        with self.assertRaisesRegex(ValueError, 'modified trace'):
            artifacts.abandon_restart(source, **kwargs)
        self.assertEqual(tuple(self.snapshot(path) for path in paths), before)

    def test_prepared_successor_pending_trace_is_verified_before_cancellation(self):
        source, session, request = self.resource_fixture(False)
        recover_trace = artifacts._recover_trace
        def interrupted(run, manifest, marker):
            if Path(run) != source and manifest.get('pending_trace'):
                raise KeyboardInterrupt('initial successor trace not written')
            return recover_trace(run, manifest, marker)
        with patch.object(artifacts, '_recover_trace', side_effect=interrupted):
            with self.assertRaises(KeyboardInterrupt):
                artifacts.restart(source, **request)
        active = artifacts._active_restart_operation(source, self.read(source / 'cierre.json'))
        successor = Path(active['successor_run_dir'])
        self.assertFalse((successor / 'trazabilidad.jsonl').exists())
        foreign = self.prepare7('deep')
        artifacts.register(foreign, [str(session)], context_input=self.context(foreign))
        foreign_before = self.snapshot(foreign), self.snapshot(session)
        artifacts.abandon_restart(source, intent_path=active['intent_path'], controller=self.controller(),
            authority='User cancels before successor work', reason='Foreign claim after preparation')
        self.assertEqual((self.snapshot(foreign), self.snapshot(session)), foreign_before)
        self.assertNotIn('pending_trace', self.read(successor / 'cierre.json'))
        artifacts.validate(successor)

    def missing_session_restart(self):
        source, session, request = self.resource_fixture(True)
        with patch.object(artifacts, 'transfer_resources', side_effect=KeyboardInterrupt('prepared, not transferred')):
            with self.assertRaises(KeyboardInterrupt):
                artifacts.restart(source, **request)
        active = artifacts._active_restart_operation(source, self.read(source / 'cierre.json'))
        successor = Path(active['successor_run_dir'])
        # Only a disposable fixture directory below this test's root is removed.
        self.assertTrue(session.is_relative_to(self.root))
        shutil.rmtree(session)
        kwargs = dict(intent_path=active['intent_path'], controller=self.controller(),
                      authority='User cancels missing workspace restart', reason='Selected workspace disappeared')
        return source, successor, session, request, kwargs

    def test_empty_missing_workspace_cancellation_preserves_unknown_claim(self):
        source, successor, session, request, kwargs = self.missing_session_restart()
        source_claims = copy.deepcopy(self.read(source / 'cierre.json')['resource_claims'])
        receipt = artifacts.abandon_restart(source, **kwargs)
        self.assertEqual(self.read(successor / 'cierre.json')['restart_abandonment'], receipt)
        self.assertEqual(self.read(source / 'cierre.json')['resource_claims'], source_claims)
        self.assertFalse(session.exists())
        self.assertEqual(recovery.inspect_run(source)['resources'][0]['availability'], 'missing_unknown')
        self.assertFalse(self.read(source / 'cierre.json').get('cleanup_receipts'))
        self.assertIsNone(artifacts._active_restart_operation(source, self.read(source / 'cierre.json')))
        self.assertEqual(artifacts.abandon_restart(source, **kwargs), receipt)
        request['profile_input']['reason'] = 'Fresh selection excluding unavailable workspace'
        request['transfer_paths'] = []
        artifacts.validate(artifacts.restart(source, **request))
        artifacts.validate(source)
        artifacts.validate(successor)

    def test_missing_workspace_cancellation_recovers_durable_decision(self):
        source, successor, _, request, kwargs = self.missing_session_restart()
        source_claims = copy.deepcopy(self.read(source / 'cierre.json')['resource_claims'])
        with patch.object(artifacts, '_finish_restart_abandonment', side_effect=KeyboardInterrupt('terminal successor committed')):
            with self.assertRaises(KeyboardInterrupt):
                artifacts.abandon_restart(source, **kwargs)
        receipt = self.read(successor / 'cierre.json')['restart_abandonment']
        result = artifacts.recover(source, controller=self.controller(), authority='Finish cancellation',
                                   current_inputs=request['current_inputs'])
        self.assertEqual(result['status'], 'restart_abandoned')
        self.assertEqual(artifacts.abandon_restart(source, **kwargs), receipt)
        self.assertEqual(self.read(source / 'cierre.json')['resource_claims'], source_claims)
        self.assertFalse(self.read(source / 'cierre.json').get('cleanup_receipts'))
        artifacts.validate(source)
        artifacts.validate(successor)

    def test_present_source_claim_prevents_empty_successor_cancellation(self):
        source, session, request = self.resource_fixture(True)
        with patch.object(artifacts, 'transfer_resources', side_effect=KeyboardInterrupt('before transfer')):
            with self.assertRaises(KeyboardInterrupt):
                artifacts.restart(source, **request)
        active = artifacts._active_restart_operation(source, self.read(source / 'cierre.json'))
        successor = Path(active['successor_run_dir'])
        before = tuple(self.snapshot(path) for path in (source, successor, session))
        with self.assertRaises(ValueError):
            artifacts.abandon_restart(source, intent_path=active['intent_path'], controller=self.controller(),
                authority='Requested cancellation', reason='Must preserve a present owned session')
        self.assertEqual(tuple(self.snapshot(path) for path in (source, successor, session)), before)

    def test_missing_origin_does_not_block_local_checkpoint_recovery_plan(self):
        source, _, request = self.resource_fixture(True)
        successor = Path(artifacts.restart(source, **request))
        self.assertTrue(source.is_relative_to(self.root))
        source.rename(source.with_name(source.name + '-unavailable'))
        with patch.object(artifacts, '_checkpoint_commit', side_effect=KeyboardInterrupt('checkpoint intent persisted')):
            with self.assertRaises(KeyboardInterrupt):
                artifacts.checkpoint(successor, context_input=self.write('pending-context.json', self.context(successor)), phase='discovery')
        before = self.snapshot(successor)
        result = artifacts.recover(successor, controller=self.read(successor / 'cierre.json')['controller'],
            authority='Recover local checkpoint', current_inputs=self.current(successor))
        self.assertEqual(result['status'], 'plan')
        self.assertEqual(result['actions'][0]['action'], 'retry_checkpoint')
        self.assertEqual(self.snapshot(successor), before)

    def test_partial_two_session_adoption_preserves_both_owners_on_refusal(self):
        source, first, request = self.resource_fixture(False)
        second = Path(review_workspace.prepare(argparse.Namespace(repo=str(self.repo), ref='HEAD', mode='commit',
            role=['review'], include_untracked=[]))['session_dir'])
        first, second = sorted([first, second], key=lambda path: artifacts.os.path.normcase(str(path)))
        request['transfer_paths'] = [str(first), str(second)]
        replace = artifacts.os.replace
        def interrupted(stage, target):
            result = replace(stage, target)
            if Path(target) == first / claims.CLAIM_NAME:
                raise KeyboardInterrupt('first claim committed before second')
            return result
        with patch.object(artifacts.os, 'replace', side_effect=interrupted):
            with self.assertRaises(KeyboardInterrupt):
                artifacts.restart(source, **request)
        active = artifacts._active_restart_operation(source, self.read(source / 'cierre.json'))
        successor = Path(active['successor_run_dir'])
        foreign = self.prepare7('deep')
        artifacts.register(foreign, [str(second)], context_input=self.context(foreign))
        paths = (source, successor, foreign, first, second)
        before = tuple(self.snapshot(path) for path in paths)
        operations = (
            lambda: artifacts.restart(source, **request),
            lambda: artifacts.recover(source, controller=self.controller(), authority=request['authority'],
                                      current_inputs=request['current_inputs']),
            lambda: artifacts.abandon_restart(source, intent_path=active['intent_path'], controller=self.controller(),
                authority='User requests cancellation', reason='Foreign claim after partial adoption'))
        for operation in operations:
            with self.assertRaises(ValueError):
                operation()
            self.assertEqual(tuple(self.snapshot(path) for path in paths), before)
        self.assertEqual(self.read(first / claims.CLAIM_NAME)['archive_path'], str(successor))
        self.assertEqual(claims.verify_claim(second, foreign)['run_id'], self.read(foreign / 'cierre.json')['run_id'])
