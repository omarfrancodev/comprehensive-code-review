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
import review_artifacts as recovery_artifacts
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

    def test_same_scope_complete_offers_show_or_new(self):
        run = self.prepare_legacy()
        self.retain_legacy(run)
        self.close(run)
        scope = self.read(run / 'cierre.json')['scope']
        current = {'scope': scope, 'sources': {}, 'source_set_complete': True}

        result = recovery.find_candidates(self.repo, scope, archive_root=self.output, current_inputs=current)

        self.assertEqual(len(result['candidates']), 1)
        candidate = result['candidates'][0]
        self.assertEqual(candidate['applicability'], 'applicable')
        actions = {row['action'] for row in candidate['actions']}
        self.assertIn('show_report', actions)
        self.assertIn('new_review', actions)
        self.assertNotIn('selected_run', result)

    def test_incomplete_offers_resume_or_restart(self):
        run = self.prepare7()
        scope = self.read(run / 'cierre.json')['scope']
        current = {'scope': scope, 'sources': {}, 'source_set_complete': True}
        result = recovery.find_candidates(self.repo, scope, archive_root=self.output, current_inputs=current)
        candidate = next(row for row in result['candidates'] if row['run_dir'] == str(run))
        self.assertEqual(candidate['operation']['disposition'], 'open')
        actions = {row['action'] for row in candidate['actions']}
        self.assertIn('inspect_recover', actions)
        self.assertIn('restart', actions)

    def test_base_description_requirements_or_profile_change_visible(self):
        scope = self.read(self.prepare7() / 'cierre.json')['scope']
        retained = {'scope': copy.deepcopy(scope), 'sources': {'evidence/spec.md': 'a' * 64},
                    'source_set_complete': True, 'description_identity': 'desc-1',
                    'requirements_identity': 'req-1', 'plan_identity': 'plan-1',
                    'configuration_identity': 'config-1', 'profile': 'standard'}
        current = copy.deepcopy(retained)
        current['scope']['base'] = 'new-base'
        current['description_identity'] = 'desc-2'
        current['requirements_identity'] = 'req-2'
        current['plan_identity'] = 'plan-2'
        current['configuration_identity'] = 'config-2'
        current['profile'] = 'deep'

        result = recovery.classify_candidate({'scope': scope}, retained, current)

        self.assertEqual(result['applicability'], 'changed')
        self.assertEqual({row['field'] for row in result['differences']},
                         {'scope.base', 'description_identity', 'requirements_identity',
                          'plan_identity', 'configuration_identity', 'profile'})

    def test_verified_candidate_compares_retained_description_identity(self):
        final = archive.record()
        final['description']['identity'] = 'description-v1'
        self.final = self.write('description-final.json', final)
        run = self.prepare_legacy()
        self.retain_legacy(run)
        self.close(run)
        scope = self.read(run / 'cierre.json')['scope']
        current = {'scope': scope, 'sources': {}, 'source_set_complete': True,
                   'description_identity': 'description-v2'}

        candidate = recovery.find_candidates(self.repo, scope, archive_root=self.output,
                                             current_inputs=current)['candidates'][0]

        self.assertEqual(candidate['applicability'], 'changed')
        self.assertIn('description_identity', {row['field'] for row in candidate['differences']})

    def test_multiple_candidates_are_not_selected_by_timestamp(self):
        first = self.prepare_legacy()
        self.retain_legacy(first)
        self.close(first)
        second = self.prepare_legacy()
        self.retain_legacy(second)
        self.close(second)
        scope = self.read(first / 'cierre.json')['scope']
        result = recovery.find_candidates(self.repo, scope, archive_root=self.output,
                                          current_inputs={'scope': scope, 'sources': {}, 'source_set_complete': True})
        self.assertEqual(len(result['candidates']), 2)
        self.assertNotIn('selected_run', result)
        self.assertEqual({row['run_dir'] for row in result['candidates']}, {str(first), str(second)})

    def test_lookup_cursor_is_scoped_and_truncation_visible(self):
        runs = [self.prepare_legacy() for _ in range(3)]
        for run in runs:
            self.retain_legacy(run)
            self.close(run)
        scope = self.read(runs[0] / 'cierre.json')['scope']
        current = {'scope': scope, 'sources': {}, 'source_set_complete': True}
        first_page = recovery.find_candidates(self.repo, scope, archive_root=self.output, limit=1,
                                              current_inputs=current)
        self.assertEqual(len(first_page['candidates']), 1)
        self.assertTrue(first_page['truncated'])
        self.assertIsNotNone(first_page['next_cursor'])
        second_page = recovery.find_candidates(self.repo, scope, archive_root=self.output, limit=1,
                                               cursor=first_page['next_cursor'], current_inputs=current)
        self.assertEqual(len(second_page['candidates']), 1)
        self.assertNotEqual(first_page['candidates'][0]['run_id'], second_page['candidates'][0]['run_id'])
        changed_scope = copy.deepcopy(scope)
        changed_scope['head'] = 'different-head'
        with self.assertRaisesRegex(ValueError, 'cursor|scope|group'):
            recovery.find_candidates(self.repo, changed_scope, archive_root=self.output, limit=1,
                                     cursor=first_page['next_cursor'],
                                     current_inputs={'scope': changed_scope, 'sources': {}, 'source_set_complete': True})

    def test_unknown_freshness_is_not_current(self):
        scope = self.read(self.prepare7() / 'cierre.json')['scope']
        retained = {'scope': copy.deepcopy(scope), 'sources': {'evidence/spec.md': 'a' * 64},
                    'source_set_complete': True}
        current = {'scope': copy.deepcopy(scope), 'sources': {}}
        result = recovery.classify_candidate({'scope': scope}, retained, current)
        self.assertEqual(result['applicability'], 'unknown')
        self.assertTrue(any(row['field'] == 'source_set_complete' for row in result['differences']))

    def test_show_report_has_no_review_or_cleanup_side_effects(self):
        run = self.prepare_legacy()
        self.retain_legacy(run)
        self.close(run)
        scope = self.read(run / 'cierre.json')['scope']
        before = self.snapshot(run)
        recovery.find_candidates(self.repo, scope, archive_root=self.output,
                                 current_inputs={'scope': scope, 'sources': {}, 'source_set_complete': True})
        result = recovery.inspect_run(run)
        record = recovery_artifacts.read_json(run / 'review.json')
        self.assertEqual(result['integrity']['status'], 'verified')
        self.assertEqual(record['stage'], 'final')
        self.assertEqual(before, self.snapshot(run))

    def test_lookup_never_opens_another_repository_group(self):
        run = self.prepare_legacy()
        self.retain_legacy(run)
        self.close(run)
        other = self.root / 'other-repo'
        other.mkdir()
        for args in (('init',), ('config', 'user.email', 'other@example.test'),
                     ('config', 'user.name', 'Other')):
            result = subprocess.run(['git', *args], cwd=other, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
        (other / 'code.txt').write_text('other', encoding='utf-8')
        subprocess.run(['git', 'add', 'code.txt'], cwd=other, check=True, capture_output=True)
        subprocess.run(['git', 'commit', '-m', 'other fixture'], cwd=other, check=True, capture_output=True)
        other_scope = self.write('other-scope.json', self.read(self.scope))
        artifacts.prepare(other, other_scope, '2.12.0', 'codex', output_root=self.output,
                          profile_input=self.profile_input())

        loaded = []
        original = recovery_artifacts._load_run
        def tracked(path):
            loaded.append(str(path))
            return original(path)
        with patch.object(recovery_artifacts, '_load_run', side_effect=tracked):
            result = recovery.find_candidates(self.repo, self.read(run / 'cierre.json')['scope'],
                archive_root=self.output,
                current_inputs={'scope': self.read(run / 'cierre.json')['scope'], 'sources': {},
                                'source_set_complete': True})
        self.assertEqual([row['run_dir'] for row in result['candidates']], [str(run)])
        self.assertNotIn(str(other), '\n'.join(loaded))

    def test_lookup_finds_changed_head_by_stable_merge_request_reference(self):
        scope = self.read(self.scope)
        scope['reference'] = 'https://gitlab.example/group/project/-/merge_requests/42'
        scope_file = self.write('mr-scope.json', scope)
        run = Path(artifacts.prepare(self.repo, scope_file, '2.12.0', 'codex',
                    output_root=self.output, profile_input=self.profile_input()))
        current_scope = copy.deepcopy(scope)
        current_scope['head'] = 'new-reviewed-head'
        current = {'scope': current_scope, 'sources': {}, 'source_set_complete': True}

        result = recovery.find_candidates(self.repo, current_scope, archive_root=self.output,
                                          current_inputs=current)

        self.assertEqual([row['run_dir'] for row in result['candidates']], [str(run)])
        self.assertEqual(result['candidates'][0]['applicability'], 'changed')
        self.assertIn('scope.head', {row['field'] for row in result['candidates'][0]['differences']})

    def test_lookup_cli_returns_json_page_without_selecting_candidate(self):
        run = self.prepare_legacy()
        self.retain_legacy(run)
        self.close(run)
        scope = self.read(run / 'cierre.json')['scope']
        scope_file = self.write('lookup-scope.json', scope)
        current_file = self.write('lookup-current.json', {
            'scope': scope, 'sources': {}, 'source_set_complete': True})

        result = subprocess.run([sys.executable, '-B', str(SCRIPTS / 'review_artifacts.py'), 'lookup',
                                 '--repo', str(self.repo), '--scope-file', str(scope_file),
                                 '--archive-root', str(self.output), '--current-inputs', str(current_file),
                                 '--limit', '5'], capture_output=True, text=True, encoding='utf-8')

        self.assertEqual(result.returncode, 0, result.stderr)
        value = json.loads(result.stdout)
        self.assertEqual(value['candidates'][0]['run_dir'], str(run))
        self.assertNotIn('selected_run', value)

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
