"""Issues 20/21: authorized refusal is durable; it never releases ownership."""
from pathlib import Path
import argparse
import json
import subprocess
import sys
import shutil
import unittest
from unittest.mock import patch

import test_review_recovery_exit_guidance as exits
import test_review_recovery_diagnostics as diagnostics

artifacts = exits.artifacts
claims = exits.claims
recovery = exits.recovery


class RestartRefusalTests(unittest.TestCase):
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
    partial_adoption_conflict = diagnostics.RecoveryDiagnosticTests.partial_adoption_conflict
    missing_after_transfer_intent = exits.RecoveryExitGuidanceTests.missing_after_transfer_intent

    def arguments(self, source):
        active = artifacts._active_restart_operation(source, self.read(source / 'cierre.json'))
        return dict(intent_path=active['intent_path'], controller=self.controller(),
                    authority='User requests a recorded refusal', reason='Preserve the blocked restart')

    def writer(self):
        self.assertTrue(callable(getattr(artifacts, 'record_restart_refusal', None)),
                        'record_restart_refusal must record an authorized phase-specific decision')
        return artifacts.record_restart_refusal

    def assert_refusal(self, source, successor, preserved, phase, kwargs):
        writer = self.writer()
        before = [self.snapshot(path) for path in preserved]
        initial = self.read(source / 'cierre.json')
        receipt = writer(source, **kwargs)
        self.assertEqual(receipt['decision'], 'refused')
        self.assertEqual(receipt['phase'], phase)
        self.assertEqual(receipt['authority'], kwargs['authority'])
        self.assertEqual(receipt['reason'], kwargs['reason'])
        self.assertTrue(receipt['cancellation_reason'])
        self.assertEqual(receipt['status'], 'recorded')
        self.assertTrue(receipt['transaction_pending'])
        self.assertEqual([self.snapshot(path) for path in preserved], before)
        after = self.read(source / 'cierre.json')
        for field in ('resource_claims', 'resource_transfers', 'operation', 'temporary_paths', 'state'):
            self.assertEqual(after.get(field), initial.get(field))
        self.assertEqual(writer(source, **kwargs), receipt)
        self.assertEqual(self.read(source / 'cierre.json'), after)
        trace = [json.loads(line) for line in (source / artifacts.review_trace.NAME).read_bytes().splitlines()]
        event = next(row for row in trace if row['event_id'] == receipt['event_id'])
        self.assertEqual(event['authority'], kwargs['authority'])
        self.assertEqual(event['status'], 'blocked')
        self.assertTrue(event['evidence'])
        active = artifacts._active_restart_operation(source, after)
        self.assertIsNotNone(active)
        self.assertEqual(recovery.inspect_run(source)['recovery']['cancellation_denial']['phase'], phase)
        return receipt

    def test_partial_adoption_records_refusal_without_touching_either_owner(self):
        source, successor, foreign, first, second, request, active = self.partial_adoption_conflict()
        receipt = self.assert_refusal(source, successor, [successor, foreign, first, second],
                                      'adoption_committed', self.arguments(source))
        self.assertEqual(receipt['operation_id'], active['operation_id'])
        self.assertEqual(self.read(first / claims.CLAIM_NAME)['archive_path'], str(successor))
        self.assertEqual(claims.verify_claim(second, foreign)['archive_path'], str(foreign))
        before = tuple(self.snapshot(path) for path in (source, successor, foreign, first, second))
        with self.assertRaises(ValueError) as caught:
            artifacts.abandon_restart(source, **self.arguments(source))
        self.assertEqual(getattr(caught.exception, 'phase', None), 'adoption_committed')
        self.assertEqual(tuple(self.snapshot(path) for path in (source, successor, foreign, first, second)), before)

    def test_missing_durable_transfer_records_refusal_without_cleanup_evidence(self):
        source, successor, missing, request, _ = self.missing_after_transfer_intent()
        self.assert_refusal(source, successor, [successor], 'transfer_durable', self.arguments(source))
        self.assertFalse(missing.exists())
        resources = recovery.inspect_run(source)['resources']
        self.assertIn('missing_unknown', [row['availability'] for row in resources])
        self.assertFalse(self.read(source / 'cierre.json').get('cleanup_receipts'))
        with self.assertRaises(ValueError):
            artifacts.validate(source, require_complete=True)

    def test_unknown_intent_and_missing_authority_do_not_write(self):
        source, successor, foreign, first, second, _, _ = self.partial_adoption_conflict()
        writer = self.writer()
        kwargs = self.arguments(source)
        before = tuple(self.snapshot(path) for path in (source, successor, foreign, first, second))
        for altered in (dict(kwargs, authority=''), dict(kwargs, intent_path=str(source / 'unknown.json'))):
            with self.assertRaises(ValueError):
                writer(source, **altered)
            self.assertEqual(tuple(self.snapshot(path) for path in (source, successor, foreign, first, second)), before)

    def test_missing_committed_adoption_records_refusal_without_releasing_claim(self):
        source, session, request = self.resource_fixture(False)
        replace = artifacts.os.replace
        def interrupted(stage, target):
            result = replace(stage, target)
            target = Path(target)
            if target.name == 'cierre.json' and target.parent != source:
                manifest = self.read(target)
                if manifest.get('resource_claims'):
                    raise KeyboardInterrupt('adoption claim row committed')
            return result
        with patch.object(artifacts.os, 'replace', side_effect=interrupted):
            with self.assertRaises(KeyboardInterrupt):
                artifacts.restart(source, **request)
        successor = Path(artifacts._active_restart_operation(source, self.read(source / 'cierre.json'))['successor_run_dir'])
        self.assertTrue(session.is_relative_to(self.root))
        shutil.rmtree(session)
        self.assert_refusal(source, successor, [successor], 'adoption_committed', self.arguments(source))
        self.assertIn('missing_unknown', [row['availability'] for row in recovery.inspect_run(successor)['resources']])

    def test_cli_exposes_typed_denial_and_explicit_recorded_receipt(self):
        source, successor, missing, request, kwargs = self.missing_after_transfer_intent()
        script = str(Path(artifacts.__file__))
        actor = self.write('refusal-controller.json', kwargs['controller'])
        authority = self.write('refusal-authority.json', {'authority': kwargs['authority']})
        args = ['--run-dir', str(source), '--intent-input', kwargs['intent_path'],
                '--controller-input', str(actor), '--authority-input', str(authority), '--reason', kwargs['reason']]
        before = self.snapshot(source), self.snapshot(successor)
        refused = subprocess.run([sys.executable, '-B', '-X', 'utf8', script, 'abandon-restart', *args],
                                 capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(refused.returncode, 1, refused.stderr)
        self.assertEqual(json.loads(refused.stderr)['cancellation_denial']['phase'], 'transfer_durable')
        self.assertEqual((self.snapshot(source), self.snapshot(successor)), before)
        recorded = subprocess.run([sys.executable, '-B', '-X', 'utf8', script, 'record-restart-refusal', *args],
                                  capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(recorded.returncode, 0, recorded.stderr)
        self.assertEqual(json.loads(recorded.stdout)['decision'], 'refused')
        self.assertEqual(json.loads(recorded.stdout)['phase'], 'transfer_durable')

    def test_missing_successor_cannot_downgrade_a_durable_transfer_to_unprepared(self):
        source, successor, missing, _, kwargs = self.missing_after_transfer_intent()
        preserved = successor.with_name(successor.name + '-preserved')
        self.assertTrue(successor.is_relative_to(self.output))
        successor.rename(preserved)
        before = self.snapshot(self.output)
        with self.assertRaises(ValueError) as caught:
            artifacts.abandon_restart(source, **kwargs)
        self.assertEqual(getattr(caught.exception, 'phase', None), 'transfer_durable')
        self.assertEqual(self.snapshot(self.output), before)
        self.assertIsNotNone(artifacts._active_restart_operation(source, self.read(source / 'cierre.json')))

    def test_invalid_ownership_cannot_be_certified_as_a_refusal(self):
        source, successor, foreign, first, second, _, _ = self.partial_adoption_conflict()
        sidecar = self.read(second / claims.CLAIM_NAME)
        sidecar['owner_id'] = 'f' * 32
        (second / claims.CLAIM_NAME).write_bytes(artifacts._json_bytes(sidecar))
        before = tuple(self.snapshot(path) for path in (source, successor, foreign, first, second))
        with self.assertRaises(ValueError):
            self.writer()(source, **self.arguments(source))
        self.assertEqual(tuple(self.snapshot(path) for path in (source, successor, foreign, first, second)), before)

    def test_present_transfer_owner_cannot_lose_or_downgrade_its_sidecar(self):
        source, first, context = self.registered_session()
        request = self.restart_request(source)
        second = Path(diagnostics.review_workspace.prepare(argparse.Namespace(
            repo=str(self.repo), ref='HEAD', mode='commit', role=['review'], include_untracked=[]))['session_dir'])
        artifacts.register(source, [str(first), str(second)], context_input=context)
        request['transfer_paths'] = [str(first), str(second)]
        replace = artifacts.os.replace
        def interrupted(stage, target):
            if Path(target).name == claims.CLAIM_NAME:
                raise KeyboardInterrupt('both transfer intents durable')
            return replace(stage, target)
        with patch.object(artifacts.os, 'replace', side_effect=interrupted):
            with self.assertRaises(KeyboardInterrupt):
                artifacts.restart(source, **request)
        successor = Path(artifacts._active_restart_operation(source, self.read(source / 'cierre.json'))['successor_run_dir'])
        self.assertTrue(first.is_relative_to(self.root))
        shutil.rmtree(first)
        sidecar = second / claims.CLAIM_NAME
        owned = self.read(sidecar)
        for altered in (None, dict(owned, status='bootstrap')):
            with self.subTest(status='missing' if altered is None else 'bootstrap'):
                if altered is None:
                    sidecar.unlink()
                else:
                    sidecar.write_bytes(artifacts._json_bytes(altered))
                before = tuple(self.snapshot(path) for path in (source, successor, second))
                with self.assertRaises(ValueError):
                    self.writer()(source, **self.arguments(source))
                self.assertEqual(tuple(self.snapshot(path) for path in (source, successor, second)), before)
                sidecar.write_bytes(artifacts._json_bytes(owned))

    def test_refusal_replays_after_every_source_replace_boundary(self):
        source, successor, foreign, first, second, _, _ = self.partial_adoption_conflict()
        writer = self.writer()
        kwargs = self.arguments(source)
        # Each run uses a new authority observation and checks every atomic replace
        # of its source trace/ownership transition, including real post-write cuts.
        for boundary in range(1, 8):
            kwargs['reason'] = 'Observe boundary ' + str(boundary)
            before = [self.snapshot(path) for path in (successor, foreign, first, second)]
            replace = artifacts.os.replace
            seen = []
            def interrupted(stage, target):
                result = replace(stage, target)
                if Path(target).parent == source:
                    seen.append(str(target))
                    if len(seen) == boundary:
                        raise KeyboardInterrupt('source decision interrupted')
                return result
            with patch.object(artifacts.os, 'replace', side_effect=interrupted):
                try:
                    writer(source, **kwargs)
                except KeyboardInterrupt:
                    pass
            receipt = writer(source, **kwargs)
            self.assertEqual(writer(source, **kwargs), receipt)
            self.assertEqual([self.snapshot(path) for path in (successor, foreign, first, second)], before)
            trace = [json.loads(line) for line in (source / artifacts.review_trace.NAME).read_bytes().splitlines()]
            self.assertEqual(sum(receipt['refusal_id'] in row['summary'] for row in trace), 1)
