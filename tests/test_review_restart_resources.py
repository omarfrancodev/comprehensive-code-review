"""Restart replay covers writes inside workspace transfer/adoption, not just around them."""
from pathlib import Path
import argparse
import shutil
import threading
import unittest
from unittest.mock import patch

import test_review_recovery_followup as followup
import review_recovery as recovery
import review_resource_claims as claims
import review_workspace

artifacts = followup.artifacts


class RestartResourceReplayTests(unittest.TestCase):
    setUp = followup.RecoveryFollowupTests.setUp
    git = followup.RecoveryFollowupTests.git
    write = followup.RecoveryFollowupTests.write
    read = followup.RecoveryFollowupTests.read
    snapshot = followup.RecoveryFollowupTests.snapshot
    profile_input = followup.RecoveryFollowupTests.profile_input
    prepare7 = followup.RecoveryFollowupTests.prepare7
    current = followup.RecoveryFollowupTests.current
    controller = followup.RecoveryFollowupTests.controller
    restart_request = followup.RecoveryFollowupTests.restart_request
    registered_session = followup.RecoveryFollowupTests.registered_session

    def resource_fixture(self, claimed, legacy=False):
        if claimed:
            source, session, _ = self.registered_session()
        else:
            source = self.prepare7('deep')
            session = Path(review_workspace.prepare(argparse.Namespace(
                repo=str(self.repo), ref='HEAD', mode='commit', role=['review'],
                include_untracked=[]))['session_dir'])
            if legacy:
                (session / claims.CLAIM_NAME).unlink()
        request = self.restart_request(source, transfer_paths=[str(session)])
        return source, session, request

    def replay(self, source, request, route):
        active = artifacts._active_restart_operation(source, self.read(source / 'cierre.json'))
        reserved = active['successor_run_dir']
        if route == 'recover':
            result = artifacts.recover(source, controller=self.controller(),
                authority=request['authority'], current_inputs=request['current_inputs'])
            self.assertEqual(result['status'], 'restarted')
            successor = result['successor_run_dir']
        else:
            successor = artifacts.restart(source, **request)
        self.assertEqual(successor, reserved)
        return Path(successor)

    def assert_completed_restart(self, source, successor, session, request):
        self.assertEqual(self.read(source / 'cierre.json')['operation']['disposition'], 'superseded')
        self.assertEqual(claims.verify_claim(session, successor)['run_id'],
                         self.read(successor / 'cierre.json')['run_id'])
        artifacts.validate(source)
        artifacts.validate(successor)
        self.assertIsNone(artifacts._active_restart_operation(source, self.read(source / 'cierre.json')))
        self.assertEqual(len(list(self.output.rglob('cierre.json'))), 2)
        before = self.snapshot(self.output), self.snapshot(session)
        self.assertEqual(artifacts.restart(source, **request), str(successor))
        self.assertEqual((self.snapshot(self.output), self.snapshot(session)), before)

    def test_sidecar_replaced_restart_retries_and_recovers(self):
        for claimed, legacy in ((True, False), (False, False), (False, True)):
            for route in ('retry', 'recover'):
                with self.subTest(claimed=claimed, legacy=legacy, route=route):
                    # Each subcase has a fresh archive; no previous candidate can mask an orphan.
                    self.output = self.root / ('archive-' + str(claimed) + '-' + str(legacy) + '-' + route)
                    source, session, request = self.resource_fixture(claimed, legacy)
                    original = artifacts.os.replace
                    def interrupt(stage, target):
                        result = original(stage, target)
                        if Path(target) == session / claims.CLAIM_NAME:
                            raise KeyboardInterrupt('process interrupted after sidecar replacement')
                        return result
                    with patch.object(artifacts.os, 'replace', side_effect=interrupt):
                        with self.assertRaises(KeyboardInterrupt):
                            artifacts.restart(source, **request)
                    successor = self.replay(source, request, route)
                    self.assert_completed_restart(source, successor, session, request)

    def resource_write_matrix(self, claimed):
        source, session, request = self.resource_fixture(claimed)
        # Restore only disposable fixture archives and the one helper-owned claim sidecar.
        # Git worktrees and workspace evidence remain untouched throughout the matrix.
        baseline = self.root / 'archive-baseline'
        shutil.copytree(self.output, baseline)
        sidecar = session / claims.CLAIM_NAME
        sidecar_before = sidecar.read_bytes() if sidecar.exists() else None
        helper_name = 'transfer_resources' if claimed else 'register'
        helper = getattr(artifacts, helper_name)
        replace = artifacts.os.replace
        writes = []
        enabled = False

        def wrapped(*args, **kwargs):
            nonlocal enabled
            enabled = True
            try:
                return helper(*args, **kwargs)
            finally:
                enabled = False

        def observed(stage, target):
            if enabled:
                writes.append(Path(target).name)
            return replace(stage, target)

        with patch.object(artifacts, helper_name, side_effect=wrapped), \
                patch.object(artifacts.os, 'replace', side_effect=observed):
            artifacts.restart(source, **request)
        self.assertIn(claims.CLAIM_NAME, writes)
        self.assertIn('cierre.json', writes)
        self.assertIn('trazabilidad.jsonl', writes)

        for index in range(1, len(writes) + 1):
            for boundary in ('before', 'after'):
                for route in ('retry', 'recover'):
                    with self.subTest(write=index, target=writes[index - 1], boundary=boundary, route=route):
                        self.assertTrue(self.output.is_relative_to(self.root))
                        shutil.rmtree(self.output)
                        shutil.copytree(baseline, self.output)
                        if sidecar_before is None:
                            sidecar.unlink(missing_ok=True)
                        else:
                            sidecar.write_bytes(sidecar_before)
                        count = 0

                        def interrupted(stage, target):
                            nonlocal count
                            if enabled:
                                count += 1
                                if count == index and boundary == 'before':
                                    raise KeyboardInterrupt('before durable replacement')
                            result = replace(stage, target)
                            if enabled and count == index and boundary == 'after':
                                raise KeyboardInterrupt('after durable replacement')
                            return result

                        with patch.object(artifacts, helper_name, side_effect=wrapped), \
                                patch.object(artifacts.os, 'replace', side_effect=interrupted):
                            with self.assertRaises(KeyboardInterrupt):
                                artifacts.restart(source, **request)
                        successor = self.replay(source, request, route)
                        self.assert_completed_restart(source, successor, session, request)

    def test_claimed_workspace_all_transfer_replacements(self):
        self.resource_write_matrix(True)

    def test_unclaimed_workspace_all_adoption_replacements(self):
        self.resource_write_matrix(False)

    def test_reserved_successor_trace_replay_respects_its_mutation_lock(self):
        source, session, request = self.resource_fixture(True)
        transfer = artifacts.transfer_resources
        replace = artifacts.os.replace
        enabled = False
        def wrapped(*args, **kwargs):
            nonlocal enabled
            enabled = True
            try:
                return transfer(*args, **kwargs)
            finally:
                enabled = False
        def interrupted(stage, target):
            result = replace(stage, target)
            if enabled and Path(target).name == 'trazabilidad.jsonl' and Path(target).parent != source:
                raise KeyboardInterrupt('successor trace not committed to closure yet')
            return result
        with patch.object(artifacts, 'transfer_resources', side_effect=wrapped), \
                patch.object(artifacts.os, 'replace', side_effect=interrupted):
            with self.assertRaises(KeyboardInterrupt):
                artifacts.restart(source, **request)
        active = artifacts._active_restart_operation(source, self.read(source / 'cierre.json'))
        successor = Path(active['successor_run_dir'])
        self.assertIn('pending_trace', self.read(successor / 'cierre.json'))
        acquired, release = threading.Event(), threading.Event()
        def holder():
            with artifacts.run_locks([successor]):
                acquired.set()
                release.wait(30)
        thread = threading.Thread(target=holder)
        thread.start()
        try:
            self.assertTrue(acquired.wait(5))
            before = self.snapshot(successor)
            from review_run_lock import LockConflictError
            with self.assertRaisesRegex(LockConflictError, 'mutation lock conflict'):
                artifacts.restart(source, **request)
            self.assertEqual(self.snapshot(successor), before)
        finally:
            release.set()
            thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(self.replay(source, request, 'retry'), successor)
        self.assert_completed_restart(source, successor, session, request)

    def superseded_checkpoint(self, staged=False):
        source = self.prepare7()
        manifest = self.read(source / 'cierre.json')
        selection = manifest['profile_history'][0]
        context = self.write('interrupted-context.json', {
            'profile': selection['profile'], 'selection_source': selection['selection_source'],
            'profile_reference': selection['reference'], 'profile_history': [selection],
            'execution_plan': [], 'executors': [], 'review_inputs': manifest['review_inputs']})
        def interrupted(run, manifest, marker, transaction, payloads):
            if staged:
                for name, data in payloads.items():
                    path = run / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)
            raise KeyboardInterrupt('interrupted checkpoint commit')
        with patch.object(artifacts, '_checkpoint_commit', side_effect=interrupted):
            with self.assertRaises(KeyboardInterrupt):
                artifacts.checkpoint(source, context_input=context, phase='discovery')
        successor = Path(artifacts.restart(source, **self.restart_request(source)))
        return source, successor, manifest, context

    def assert_superseded_checkpoint(self, source, successor, manifest):
        before = self.snapshot(source)
        self.assertFalse(artifacts.validate(source)['retained'])
        for gate in ({'require_retained': True}, {'require_complete': True}, {'record_checkpoint': True}):
            with self.assertRaises(ValueError):
                artifacts.validate(source, **gate)
        inspected = recovery.inspect_run(source, current_inputs=self.current(source))
        self.assertEqual(inspected['integrity']['status'], 'verified')
        checkpoint = next(row for row in inspected['pending_transaction'] if row['kind'] == 'checkpoint')
        self.assertEqual(checkpoint['status'], 'superseded')
        candidates = recovery.find_candidates(self.repo, manifest['scope'], archive_root=self.output,
                                              current_inputs=self.current(source))
        candidate = next(row for row in candidates['candidates'] if row['run_dir'] == str(source))
        recovered = artifacts.recover(source, controller=self.controller(), authority='Inspect superseded run',
                                      current_inputs=self.current(source))
        self.assertEqual(recovered['status'], 'superseded')
        for result in (inspected, candidate, recovered):
            actions = [row['action'] for row in result['actions']]
            self.assertIn('inspect_successor', actions)
            self.assertFalse(set(actions) & {'recover', 'inspect_recover', 'continue', 'resume', 'retry_checkpoint', 'show'})
        self.assertEqual(self.snapshot(source), before)
        self.assertIn('checkpoint_transaction', self.read(source / 'cierre.json'))
        self.assertFalse((source / 'review.json').exists())
        artifacts.validate(successor)

    def test_superseded_pending_checkpoint_is_historical_not_retryable(self):
        source, successor, manifest, _ = self.superseded_checkpoint()
        self.assert_superseded_checkpoint(source, successor, manifest)

    def test_superseded_checkpoint_with_staged_bytes_is_not_committed(self):
        source, successor, manifest, _ = self.superseded_checkpoint(staged=True)
        self.assertTrue((source / 'pending/context.json').is_file())
        self.assert_superseded_checkpoint(source, successor, manifest)

    def test_superseded_checkpoint_still_rejects_modified_bytes(self):
        source, _, _, _ = self.superseded_checkpoint(staged=True)
        (source / 'pending/context.json').write_text('{"modified": true}', encoding='utf-8')
        before = self.snapshot(source)
        with self.assertRaises(ValueError):
            artifacts.validate(source)
        with self.assertRaises(ValueError):
            artifacts.recover(source, controller=self.controller(), authority='Inspect superseded run',
                              current_inputs=self.current(source))
        inspected = recovery.inspect_run(source)
        self.assertEqual(inspected['integrity']['status'], 'invalid')
        self.assertEqual([row['action'] for row in inspected['actions']], ['preserve'])
        self.assertEqual(self.snapshot(source), before)

    def test_superseded_checkpoint_keeps_remaining_claim_cleanup_usable(self):
        source, session, context = self.registered_session()
        with patch.object(artifacts, '_checkpoint_commit', side_effect=KeyboardInterrupt('before staging')):
            with self.assertRaises(KeyboardInterrupt):
                artifacts.checkpoint(source, context_input=self.write('pending-claimed-context.json', context),
                                     phase='discovery')
        transaction = self.read(source / 'cierre.json')['checkpoint_transaction']
        changed = dict(self.read(source / 'cierre.json')['scope'], head='changed-reviewed-head')
        successor = Path(artifacts.restart(source, **self.restart_request(source, scope=changed)))
        for result in (recovery.inspect_run(source), artifacts.recover(source,
                controller=self.controller(), authority='Inspect historical source', current_inputs=self.current(source))):
            self.assertIn('cleanup', [row['action'] for row in result['actions']])
        with patch('review_artifacts._finish_resource_cleanup_locked', side_effect=KeyboardInterrupt('after removal')):
            with self.assertRaises(KeyboardInterrupt):
                review_workspace.cleanup(argparse.Namespace(manifest=str(session / 'manifest.json'), run_dir=str(source)))
        self.assertFalse(session.exists())
        self.assertEqual(artifacts.recover_resource_cleanup(source)['status'], 'released')
        self.assertEqual(self.read(source / 'cierre.json')['checkpoint_transaction'], transaction)
        self.assertEqual(self.read(source / 'cierre.json')['operation']['disposition'], 'superseded')
        self.assertNotIn('checkpoint', self.read(source / 'cierre.json')['hashes'])
        artifacts.validate(source)
        artifacts.validate(successor)

    def test_pending_checkpoint_workspace_transfer_recovers_without_promoting_inputs(self):
        source, session, context = self.registered_session()
        with patch.object(artifacts, '_checkpoint_commit', side_effect=KeyboardInterrupt('before staging')):
            with self.assertRaises(KeyboardInterrupt):
                artifacts.checkpoint(source, context_input=self.write('pending-transfer-context.json', context),
                                     phase='discovery')
        transaction = self.read(source / 'cierre.json')['checkpoint_transaction']
        request = self.restart_request(source, transfer_paths=[str(session)])
        replace = artifacts.os.replace
        def interrupted(stage, target):
            result = replace(stage, target)
            if Path(target) == session / claims.CLAIM_NAME:
                raise KeyboardInterrupt('transfer checkpoint source after sidecar')
            return result
        with patch.object(artifacts.os, 'replace', side_effect=interrupted):
            with self.assertRaises(KeyboardInterrupt):
                artifacts.restart(source, **request)
        successor = self.replay(source, request, 'recover')
        self.assertEqual(self.read(source / 'cierre.json')['checkpoint_transaction'], transaction)
        self.assertNotIn('checkpoint_transaction', self.read(successor / 'cierre.json'))
        self.assertFalse((successor / 'pending').exists())
        self.assert_completed_restart(source, successor, session, request)
