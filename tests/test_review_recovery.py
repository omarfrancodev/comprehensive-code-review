"""Review recovery inspection and lifecycle operations never invent execution."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
import argparse

import test_review_artifacts as archive

artifacts = archive.artifacts
SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))

import review_recovery as recovery
import review_workspace
import review_resource_claims
from recovery_fixtures import context10, current_inputs, legacy_prepare, record10


class ReviewRecoveryTests(unittest.TestCase):
    setUp = archive.Archive7Tests.setUp
    profile_input = archive.Archive7Tests.profile_input
    git = archive.ArchiveTests.git
    snapshot = archive.ArchiveTests.snapshot
    read = archive.ArchiveTests.read
    write = archive.ArchiveTests.write
    prepare_legacy = archive.ArchiveTests.prepare
    retain_legacy = archive.ArchiveTests.retain
    close = archive.ArchiveTests.close

    def prepare7(self, profile='standard', *, controller=None):
        return Path(artifacts.prepare(self.repo, self.scope, '2.12.0', 'codex', output_root=self.output,
                                      profile_input=self.profile_input(profile), controller=controller))

    def current(self, run, *, scope=None, sources=None):
        manifest = self.read(run / 'cierre.json')
        return current_inputs(scope if scope is not None else manifest['scope'], sources)

    def controller(self, name='new controller', provider='codex'):
        return {'identity': {'kind': 'coordinator', 'name': name, 'provider_id': provider},
                'source': 'test harness context'}

    def events(self, run):
        return [json.loads(line) for line in (run / 'trazabilidad.jsonl').read_text(encoding='utf-8').splitlines()]

    def test_inspect_is_read_only_for_all_states(self):
        prepared = self.prepare7()
        processing = self.prepare7()
        artifacts.record_event(processing, self.write('worker-start.json', {
            'kind': 'agent', 'status': 'started', 'summary': 'Observed worker start',
            'executor': {'name': 'worker-1', 'provider_id': 'codex'}}))
        paused = self.prepare7()
        artifacts.pause(paused, authority='User requested pause', reason='Waiting for input', phase='verification')
        blocked = self.prepare7()
        artifacts.block(blocked, source='observed test failure', reason='Fixture failed', phase='verification')
        complete = self.prepare_legacy()
        self.retain_legacy(complete)
        self.close(complete)

        for run in (prepared, processing, paused, blocked, complete):
            with self.subTest(state=self.read(run / 'cierre.json')['state']):
                before = self.snapshot(run)
                value = recovery.inspect_run(run)
                self.assertEqual(value['integrity']['status'], 'verified')
                expected_activity = 'completed' if self.read(run / 'cierre.json')['state'] == 'complete' else 'unknown'
                self.assertEqual(value['activity'], expected_activity)
                self.assertEqual(before, self.snapshot(run))

    def test_explicit_pause_requires_continue_authority(self):
        run = self.prepare7()
        artifacts.pause(run, authority='User requested stop', reason='Wait for clarification', phase='discovery')
        before = self.snapshot(run)
        with self.assertRaisesRegex(ValueError, 'authority|continue|explicit'):
            artifacts.resume(run, controller=self.controller(), authority=None, current_inputs=self.current(run))
        self.assertEqual(before, self.snapshot(run))

    def test_cli_pause_reads_structured_authority_without_shell_execution(self):
        run = self.prepare7()
        authority_file = self.write('authority.json', {'authority': 'User requested pause'})
        result = subprocess.run([sys.executable, '-B', str(SCRIPTS / 'review_artifacts.py'), 'pause',
                                 '--run-dir', str(run), '--authority-input', str(authority_file),
                                 '--reason', 'Waiting for review input', '--phase', 'discovery'],
                                capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.read(run / 'cierre.json')['operation']['disposition'], 'paused')

    def test_cross_harness_resume_preserves_prior_worker_identity(self):
        old_controller = self.controller('Codex coordinator', 'codex')
        run = self.prepare7(controller=old_controller)
        artifacts.record_event(run, self.write('worker.json', {
            'kind': 'agent', 'status': 'completed', 'summary': 'Worker completed discovery',
            'executor': {'name': 'claude-worker', 'provider_id': 'claude-code'}}))
        prior_events = self.events(run)
        prior_executors = copy.deepcopy(self.read(run / 'cierre.json')['executors'])

        artifacts.resume(run, controller=self.controller('Claude Desktop coordinator', 'claude-code'),
                         authority='User confirmed the previous coordinator stopped',
                         current_inputs=self.current(run))

        manifest = self.read(run / 'cierre.json')
        self.assertEqual(manifest['controller']['identity']['name'], 'Claude Desktop coordinator')
        self.assertEqual(manifest['executors'], prior_executors)
        self.assertEqual(self.events(run)[:len(prior_events)], prior_events)

    def test_unknown_concurrent_controller_blocks_takeover(self):
        run = self.prepare7(controller=self.controller('Original coordinator'))
        before = self.snapshot(run)
        with self.assertRaisesRegex(ValueError, 'authority|concurrent|takeover|controller'):
            artifacts.resume(run, controller=self.controller('Different coordinator'), authority=None,
                             current_inputs=self.current(run))
        self.assertEqual(before, self.snapshot(run))

    def test_resume_rejects_changed_scope_without_mutation(self):
        run = self.prepare7()
        changed_scope = self.current(run)['scope']
        changed_scope['head'] = 'changed-head'
        before = self.snapshot(run)
        with self.assertRaisesRegex(ValueError, 'scope|restart'):
            artifacts.resume(run, controller=self.controller(), authority='User confirmed continuation',
                             current_inputs=self.current(run, scope=changed_scope))
        self.assertEqual(before, self.snapshot(run))

    def test_recovery_plan_does_not_dispatch_or_execute(self):
        run = self.prepare7()
        before = self.snapshot(run)
        with patch.object(subprocess, 'run', side_effect=AssertionError('recovery must not execute commands')):
            result = artifacts.recover(run, controller=self.controller(),
                                       authority='User requested recovery', current_inputs=self.current(run))
        self.assertIn(result['status'], {'ready', 'plan'})
        self.assertEqual(before, self.snapshot(run))

    def test_recover_original_pending_bytes_without_backdating(self):
        run = self.prepare7()
        final = record10('standard', 'automatic')
        final['scope'] = self.read(run / 'cierre.json')['scope']
        context = self.write('recovery-context.json', context10(final))
        original = artifacts.atomic_write
        interrupted = False

        def fail_after_selected_bytes(path, data):
            nonlocal interrupted
            if not interrupted and Path(path).as_posix().endswith('/pending/context.json'):
                original(path, data)
                interrupted = True
                raise OSError('simulated crash after checkpoint context write')
            original(path, data)

        with patch.object(artifacts, 'atomic_write', side_effect=fail_after_selected_bytes), self.assertRaises(OSError):
            artifacts.checkpoint(run, context_input=context, phase='discovery')
        pending = self.read(run / 'cierre.json')['checkpoint_transaction']['checkpoint']
        recorded_at = pending['recorded_at']
        preserved_context = (run / 'pending/context.json').read_bytes()

        result = artifacts.recover(run, controller=self.controller(), authority='User requested recovery',
                                   current_inputs=self.current(run))

        manifest = self.read(run / 'cierre.json')
        self.assertEqual(result['status'], 'recovered')
        self.assertEqual(manifest['checkpoint']['recorded_at'], recorded_at)
        self.assertEqual((run / 'pending/context.json').read_bytes(), preserved_context)
        self.assertNotIn('checkpoint_transaction', manifest)

    def test_tampered_run_is_not_adopted(self):
        run = self.prepare7()
        closure = self.read(run / 'cierre.json')
        closure['updated_at'] = 'foreign edit'
        (run / 'cierre.json').write_text(json.dumps(closure), encoding='utf-8')
        before = self.snapshot(run)

        value = recovery.inspect_run(run)
        self.assertEqual(value['integrity']['status'], 'invalid')
        self.assertIn('preserve', [row['action'] for row in value['actions']])
        with self.assertRaises(ValueError):
            artifacts.recover(run, controller=self.controller(), authority='User requested recovery',
                              current_inputs=self.current(run))
        self.assertEqual(before, self.snapshot(run))

    def test_late_profile_remains_provisional(self):
        run = self.prepare7('standard')
        final = record10('deep', 'automatic')
        final['scope'] = self.read(run / 'cierre.json')['scope']
        final['description'] = {'status': 'not_applicable', 'identity': None, 'details': ''}
        manifest = self.read(run / 'cierre.json')
        final['review_id'] = 'CR-' + manifest['run_id']
        context = self.write('late-profile-context.json', context10(final))
        artifacts.checkpoint(run, context_input=context, input_record=self.write('late-profile.json', final),
                             phase='retain')
        history_before = copy.deepcopy(self.read(run / 'cierre.json')['profile_history'])

        result = artifacts.recover(run, controller=self.controller(), authority='User requested recovery',
                                   current_inputs=self.current(run))

        current = self.read(run / 'cierre.json')
        self.assertEqual(result['status'], 'provisional')
        self.assertFalse(current['retained'])
        self.assertEqual(current['profile_history'], history_before)
        self.assertTrue((run / 'pending/review.json').is_file(),
                        (result, self.read(run / 'cierre.json').get('checkpoint'),
                         self.read(run / 'cierre.json').get('pending_hashes')))
        with self.assertRaises(ValueError):
            artifacts.validate(run, require_retained=True)

    def test_restart_links_source_without_relabelling_results(self):
        source = self.prepare7('standard')
        artifacts.record_event(source, self.write('old-worker.json', {
            'kind': 'agent', 'status': 'completed', 'summary': 'Original independent discovery',
            'executor': {'name': 'worker-original', 'provider_id': 'codex'}}))
        source_before = self.read(source / 'cierre.json')
        worker_before = self.events(source)[-1]
        successor_scope = self.current(source)['scope']
        successor_scope['head'] = 'new-reviewed-head'

        successor = Path(artifacts.restart(
            source, profile_input=self.profile_input('deep'), controller=self.controller('Restart coordinator'),
            authority='User requested a fresh review', current_inputs=self.current(source, scope=successor_scope)))

        old_after = self.read(source / 'cierre.json')
        new = self.read(successor / 'cierre.json')
        self.assertEqual(new['previous_run'], str(source))
        self.assertEqual(new['scope'], successor_scope)
        self.assertEqual(new['lineage'], {'kind': 'restart', 'source_run': str(source)})
        self.assertEqual(new['profile_history'][0]['profile'], 'deep')
        self.assertEqual(new['run_id'], self.read(successor / 'cierre.json')['run_id'])
        self.assertEqual(old_after['profile_history'], source_before['profile_history'])
        self.assertEqual(self.events(source)[-2 if self.events(source)[-1]['kind'] == 'handoff' else -1], worker_before)
        self.assertNotIn('Original independent discovery', [event['summary'] for event in self.events(successor)])
        self.assertEqual(old_after['operation']['disposition'], 'superseded')
        snapshots = (self.snapshot(source), self.snapshot(successor))
        repeated = artifacts.restart(
            source, profile_input=self.profile_input('deep'), controller=self.controller('Restart coordinator'),
            authority='Retry the same restart request', current_inputs=self.current(source, scope=successor_scope))
        self.assertEqual(Path(repeated), successor)
        with self.assertRaisesRegex(ValueError, 'successor'):
            artifacts.restart(
                source, profile_input=self.profile_input('standard'), controller=self.controller('Restart coordinator'),
                authority='Different restart request', current_inputs=self.current(source, scope=successor_scope))
        self.assertEqual(snapshots, (self.snapshot(source), self.snapshot(successor)))

    def test_restart_requires_and_transfers_the_exact_owned_workspace(self):
        session = Path(review_workspace.prepare(argparse.Namespace(
            repo=str(self.repo), ref='HEAD', mode='commit', role=['review'], include_untracked=[]))['session_dir'])
        source = self.prepare7()
        selection = self.read(source / 'cierre.json')['profile_history'][0]
        context = {'profile': selection['profile'], 'selection_source': selection['selection_source'],
                   'profile_reference': selection['reference'], 'profile_history': [selection], 'executors': []}
        artifacts.register(source, [str(session)], context_input=self.write('source-context.json', context))
        before = self.snapshot(session)
        with self.assertRaisesRegex(ValueError, 'transfer paths'):
            artifacts.restart(source, profile_input=self.profile_input('deep'), controller=self.controller(),
                              authority='User requested a restart', current_inputs=self.current(source))
        self.assertEqual(before, self.snapshot(session))

        successor = Path(artifacts.restart(
            source, profile_input=self.profile_input('deep'), controller=self.controller('Successor coordinator'),
            authority='User requested a restart after stopping the source', current_inputs=self.current(source),
            transfer_paths=[str(session)]))

        self.assertEqual(review_resource_claims.verify_claim(session, successor)['run_id'],
                         self.read(successor / 'cierre.json')['run_id'])
        self.assertEqual(self.read(source / 'cierre.json')['operation']['disposition'], 'superseded')
        self.assertEqual(self.read(successor / 'cierre.json')['resource_claims'][0]['status'], 'owned')
        review_workspace.cleanup(argparse.Namespace(manifest=str(session / 'manifest.json'),
                                                      run_dir=str(successor)))

    def test_legacy_recovery_creates_linked7_without_migration(self):
        source = self.prepare_legacy()
        source_snapshot = self.snapshot(source)
        successor = Path(artifacts.restart(
            source, profile_input=self.profile_input('standard'), controller=self.controller(),
            authority='User requested a linked archive-7 restart', current_inputs=self.current(source)))
        manifest = self.read(successor / 'cierre.json')
        self.assertEqual(manifest['schema_version'], 7)
        self.assertEqual(manifest['previous_run'], str(source))
        self.assertEqual(manifest['lineage'], {'kind': 'restart', 'source_run': str(source)})
        self.assertEqual(self.snapshot(source), source_snapshot)

    def test_completed_repeat_preserves_original(self):
        source = self.prepare_legacy()
        self.retain_legacy(source)
        self.close(source)
        source_snapshot = self.snapshot(source)

        successor = Path(artifacts.restart(
            source, profile_input=self.profile_input('deep'), controller=self.controller(),
            authority='User requested a repeat of the completed review', current_inputs=self.current(source)))

        self.assertNotEqual(self.read(successor / 'cierre.json')['run_id'],
                            self.read(source / 'cierre.json')['run_id'])
        self.assertEqual(self.read(successor / 'cierre.json')['previous_run'], str(source))
        self.assertEqual(self.snapshot(source), source_snapshot)


if __name__ == '__main__':
    unittest.main()
