"""PR 23 / F001: every refusal observes both durable transfer commits."""
from pathlib import Path
import json
import shutil
import subprocess
import sys
import threading
import unittest
from unittest.mock import patch

import test_review_restart_refusals as refusals

from ccr.archive import resources as resource_ops

artifacts = refusals.artifacts
recovery = refusals.recovery


class RestartPhaseConsistencyTests(unittest.TestCase):
    setUp = refusals.RestartRefusalTests.setUp
    git = refusals.RestartRefusalTests.git
    write = refusals.RestartRefusalTests.write
    read = refusals.RestartRefusalTests.read
    snapshot = refusals.RestartRefusalTests.snapshot
    profile_input = refusals.RestartRefusalTests.profile_input
    prepare7 = refusals.RestartRefusalTests.prepare7
    current = refusals.RestartRefusalTests.current
    controller = refusals.RestartRefusalTests.controller
    restart_request = refusals.RestartRefusalTests.restart_request
    registered_session = refusals.RestartRefusalTests.registered_session
    resource_fixture = refusals.RestartRefusalTests.resource_fixture
    context = refusals.RestartRefusalTests.context

    def transfer_commit_cut(self, after_successor=False):
        source, session, request = self.resource_fixture(True)
        save = resource_ops._save_manifest
        def interrupted(run, manifest, marker):
            result = save(run, manifest, marker)
            target = Path(run)
            transfers = artifacts.normalize_transfer_history(manifest)
            if (any(row['source_run'] == str(source) and row['status'] == 'complete' for row in transfers)
                    and (target != source if after_successor else target == source)):
                raise KeyboardInterrupt('durable transfer completion interrupted')
            return result
        with patch.object(resource_ops, '_save_manifest', side_effect=interrupted):
            with self.assertRaises(KeyboardInterrupt):
                artifacts.restart(source, **request)
        active = artifacts._active_restart_operation(source, self.read(source / 'cierre.json'))
        successor = Path(active['successor_run_dir'])
        self.assertEqual(self.read(source / 'cierre.json')['resource_transfers'][0]['status'], 'complete')
        self.assertEqual(self.read(successor / 'cierre.json')['resource_transfers'][0]['status'],
                         'complete' if after_successor else 'pending')
        self.assertTrue(session.is_relative_to(self.root))
        shutil.rmtree(session)
        kwargs = dict(intent_path=active['intent_path'], controller=self.controller(),
                      authority='User requests phase-consistent refusal', reason='Missing selected workspace')
        return source, successor, request, kwargs

    def test_partial_and_complete_transfer_phases_agree_across_all_routes(self):
        for committed in (False, True):
            with self.subTest(successor_complete=committed):
                source, successor, request, kwargs = self.transfer_commit_cut(committed)
                expected = 'transfer_committed' if committed else 'transfer_durable'
                before = self.snapshot(self.output)
                phases = {}
                for label, run in (('source', source), ('successor', successor)):
                    inspected = recovery.inspect_run(run)
                    found = recovery.find_candidates(self.repo, self.read(run / 'cierre.json')['scope'],
                        archive_root=self.output, current_inputs=request['current_inputs'])
                    candidate = next(row for row in found['candidates'] if row['run_dir'] == str(run))
                    recovered = artifacts.recover(run, controller=kwargs['controller'], authority=kwargs['authority'],
                                                  current_inputs=request['current_inputs'])
                    for route, result in (('inspect', inspected), ('lookup', candidate), ('recover', recovered)):
                        phases[label + ':' + route] = result['recovery']['cancellation_denial']['phase']
                with self.assertRaises(ValueError) as caught:
                    artifacts.abandon_restart(source, **kwargs)
                phases['abandon-api'] = getattr(caught.exception, 'phase', None)
                actor = self.write('phase-controller.json', kwargs['controller'])
                authority = self.write('phase-authority.json', {'authority': kwargs['authority']})
                result = subprocess.run([sys.executable, '-B', '-X', 'utf8', str(Path(artifacts.__file__).parent),
                    'artifacts', 'abandon-restart', '--run-dir', str(source), '--intent-input', kwargs['intent_path'],
                    '--controller-input', str(actor), '--authority-input', str(authority), '--reason', kwargs['reason']],
                    capture_output=True, text=True, encoding='utf-8')
                self.assertEqual(result.returncode, 1, result.stderr)
                phases['abandon-cli'] = json.loads(result.stderr)['cancellation_denial']['phase']
                self.assertEqual(self.snapshot(self.output), before)
                successor_before = self.snapshot(successor)
                receipt = artifacts.record_restart_refusal(source, **kwargs)
                phases['receipt'] = receipt['phase']
                self.assertEqual(self.snapshot(successor), successor_before)
                self.assertEqual(artifacts.record_restart_refusal(source, **kwargs), receipt)
                self.assertIsNotNone(artifacts._active_restart_operation(source, self.read(source / 'cierre.json')))
                for run in (source, successor):
                    self.assertFalse(self.read(run / 'cierre.json').get('cleanup_receipts'))
                    self.assertNotIn('restart_abandonment', self.read(run / 'cierre.json'))
                self.assertEqual(phases, {route: expected for route in phases})

    def test_abandon_observes_successor_under_its_mutation_lock(self):
        from ccr.execution.locks import LockConflictError
        source, successor, _, kwargs = self.transfer_commit_cut()
        acquired, release = threading.Event(), threading.Event()
        def holder():
            with artifacts.run_locks([successor]):
                acquired.set()
                release.wait(30)
        thread = threading.Thread(target=holder)
        thread.start()
        try:
            self.assertTrue(acquired.wait(5))
            before = self.snapshot(source), self.snapshot(successor)
            with self.assertRaises(ValueError) as caught:
                artifacts.abandon_restart(source, **kwargs)
            self.assertIsInstance(caught.exception, LockConflictError)
            self.assertEqual((self.snapshot(source), self.snapshot(successor)), before)
        finally:
            release.set()
            thread.join(5)
        self.assertFalse(thread.is_alive())

    def test_corrupt_successor_cannot_be_classified_from_source_alone(self):
        source, successor, _, kwargs = self.transfer_commit_cut()
        marker = self.read(successor / artifacts.MARKER)
        marker['owner_id'] = 'f' * 32
        (successor / artifacts.MARKER).write_bytes(artifacts._json_bytes(marker))
        before = self.snapshot(self.output)
        with self.assertRaises(ValueError) as caught:
            artifacts.abandon_restart(source, **kwargs)
        self.assertIsNone(getattr(caught.exception, 'phase', None))
        self.assertEqual(self.snapshot(self.output), before)

    def test_absent_successor_keeps_source_transfer_proof_and_phase(self):
        source, successor, _, kwargs = self.transfer_commit_cut()
        preserved = successor.with_name(successor.name + '-preserved')
        self.assertTrue(successor.is_relative_to(self.output))
        successor.rename(preserved)
        before = self.snapshot(self.output)
        phase = recovery.inspect_run(source)['recovery']['cancellation_denial']['phase']
        with self.assertRaises(ValueError) as caught:
            artifacts.abandon_restart(source, **kwargs)
        self.assertEqual(getattr(caught.exception, 'phase', None), phase)
        self.assertEqual(phase, 'transfer_committed')
        self.assertEqual(self.snapshot(self.output), before)
        self.assertEqual(artifacts.record_restart_refusal(source, **kwargs)['phase'], phase)
