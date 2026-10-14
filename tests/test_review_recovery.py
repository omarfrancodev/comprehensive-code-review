"""Review recovery inspection and lifecycle operations never invent execution."""
import copy
import json
from pathlib import Path
import shutil
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
from recovery_fixtures import context10, current_inputs, legacy_prepare, record10, source_events


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

    def prepare7(self, profile='standard', *, controller=None, capture_inputs=True):
        captured = (current_inputs(self.read(self.scope), source_set_complete=True,
                                   description_identity=record10(profile)['description']['identity'],
                                   requirements_identity=None,
                                   plan_identity=None, configuration_identity=None, profile=profile)
                    if capture_inputs else None)
        return Path(artifacts.prepare(self.repo, self.scope, '2.12.0', 'codex', output_root=self.output,
                                      profile_input=self.profile_input(profile), controller=controller,
                                      current_inputs=captured))

    def current(self, run, *, scope=None, sources=None):
        manifest = self.read(run / 'cierre.json')
        captured = manifest.get('review_inputs') or {}
        identities = {field: captured[field] for field in ('description_identity', 'requirements_identity',
                      'plan_identity', 'configuration_identity') if field in captured}
        history = manifest.get('profile_history', [])
        if history:
            identities['profile'] = history[-1]['profile']
        return current_inputs(scope if scope is not None else manifest['scope'],
                              sources if sources is not None else captured.get('sources', {}),
                              source_set_complete=True, **identities)

    def retained_claimed_run(self):
        session = Path(review_workspace.prepare(argparse.Namespace(
            repo=str(self.repo), ref='HEAD', mode='commit', role=['review'], include_untracked=[]))['session_dir'])
        run = self.prepare7('focused')
        manifest = self.read(run / 'cierre.json')
        manifest['review_inputs']['description_identity'] = None
        artifacts._save_manifest(run, manifest, self.read(run / artifacts.MARKER))
        manifest = self.read(run / 'cierre.json')
        history = manifest['profile_history']
        final = record10('focused', 'automatic')
        final['scope'] = manifest['scope']
        final['description'] = {'status': 'not_applicable', 'identity': None, 'details': ''}
        final['review_id'] = 'CR-' + manifest['run_id']
        final['coverage']['execution']['profile_history'] = history
        context = context10(final)
        context['profile_history'] = history
        context['profile_reference'] = history[-1]['reference']
        context_path = self.write('claimed-context.json', context)
        artifacts.register(run, [str(session)], context_input=context_path)
        for event in source_events(final):
            if event['kind'] == 'profile':
                continue
            identity = event.get('actor', {'name': 'coordinator', 'provider_id': None})
            observed = {'kind': event['kind'], 'status': event['status'],
                        'summary': 'Observed synthetic review step',
                        'actor': dict(identity, kind='agent'), 'executor': event.get('executor'),
                        'provenance': {'kind': 'tool', 'source': 'synthetic cleanup test'},
                        'evidence': event['evidence'], 'relations': [], 'authority': None,
                        'occurred_at': None}
            artifacts.record_event(run, self.write('cleanup-event.json', observed))
        plan = final['coverage']['execution']['plan']
        briefs = self.write('briefs.json', {row['id']: {'questions': ['Check invariant']} for row in plan})
        results = self.write('results.json', {row['id']: {'result': 'completed'} for row in plan})
        artifacts.retain(run, self.write('cleanup-final.json', final), context_input=context_path,
                         evidence_inputs=[briefs, results])
        return run, session

    def test_same_inputs_shape_for_lookup_inspect_and_resume(self):
        run = self.prepare7()
        manifest = self.read(run / 'cierre.json')
        current = self.current(run)
        scope = manifest['scope']

        found = recovery.find_candidates(self.repo, scope, archive_root=self.output,
                                         current_inputs=current)
        inspected = recovery.inspect_run(run, current_inputs=current)
        resumed = artifacts.resume(run, controller=manifest['controller'], authority=None,
                                   current_inputs=current)

        self.assertEqual(found['candidates'][0]['applicability'], 'applicable')
        self.assertEqual(inspected['freshness']['status'], 'verified')
        self.assertEqual(resumed['operation']['disposition'], 'open')

    def test_known_description_identity_omitted_is_unknown(self):
        scope = self.read(self.prepare7() / 'cierre.json')['scope']
        retained = current_inputs(scope, source_set_complete=True, description_identity='desc-v1')
        run = self.prepare7(capture_inputs=False)
        manifest = self.read(run / 'cierre.json')
        manifest['review_inputs'] = retained
        marker = self.read(run / artifacts.MARKER)
        artifacts._save_manifest(run, manifest, marker)

        inspected = recovery.inspect_run(run, current_inputs=current_inputs(scope, source_set_complete=True))

        self.assertEqual(inspected['freshness']['status'], 'unknown')
        self.assertIn('description_identity', {row['field'] for row in inspected['freshness']['differences']})

    def test_unknown_inputs_cannot_resume(self):
        run = self.prepare7(capture_inputs=False)
        manifest = self.read(run / 'cierre.json')
        incomplete = current_inputs(manifest['scope'])
        with self.assertRaisesRegex(ValueError, 'unknown|applicable'):
            artifacts.resume(run, controller=manifest['controller'], authority=None,
                             current_inputs=incomplete)

    def test_prepare_captures_external_review_inputs_without_replacing_profile_history(self):
        inputs = current_inputs(self.read(self.scope), {'evidence/requirements.md': 'a' * 64},
            source_set_complete=True, description_identity='description-v1',
            requirements_identity='requirements-v1', plan_identity=None,
            configuration_identity=None, profile='standard')
        run = Path(artifacts.prepare(self.repo, self.scope, '2.12.0', 'codex', output_root=self.output,
            profile_input=self.profile_input('standard'), current_inputs=inputs))

        manifest = self.read(run / 'cierre.json')
        self.assertEqual(manifest['review_inputs']['sources'], inputs['sources'])
        self.assertNotIn('profile', manifest['review_inputs'])
        self.assertEqual(manifest['profile_history'][0]['profile'], 'standard')

    def test_register_can_capture_external_inputs_before_assignment_work(self):
        run = self.prepare7('focused', capture_inputs=False)
        final = record10('focused')
        manifest = self.read(run / 'cierre.json')
        final['scope'] = manifest['scope']
        context = context10(final)
        context['profile_history'] = manifest['profile_history']
        context['profile_reference'] = manifest['profile_history'][-1]['reference']

        manifest = artifacts.register(run, [], context_input=self.write('input-context.json', context))

        self.assertEqual(manifest['review_inputs']['scope'], final['scope'])
        self.assertTrue(manifest['review_inputs']['source_set_complete'])

    def test_internal_outputs_are_not_external_sources(self):
        manifest = {'scope': copy.deepcopy(self.read(self.prepare7() / 'cierre.json')['scope']),
                    'hashes': {f'evidence/result-{index}.json': 'a' * 64 for index in range(70)},
                    'review_inputs': current_inputs(self.read(self.scope), {'requirements.md': 'b' * 64},
                                                    source_set_complete=True)}

        retained = recovery._candidate_inputs(manifest)

        self.assertEqual(retained['sources'], {'requirements.md': 'b' * 64})

    def test_unknown_legacy_inputs_remain_unknown(self):
        run = self.prepare_legacy()
        self.retain_legacy(run)
        self.close(run)
        scope = self.read(run / 'cierre.json')['scope']
        result = recovery.find_candidates(self.repo, scope, archive_root=self.output,
            current_inputs=current_inputs(scope, source_set_complete=True))
        self.assertEqual(result['candidates'][0]['applicability'], 'unknown')

    def test_nonobject_final_retention_is_structured_error(self):
        run = self.prepare7()
        with self.assertRaisesRegex(ValueError, 'object|record|review'):
            artifacts.retain(run, self.write('list-final.json', []), context_input=self.write('ctx.json', {}))

    def test_schema1_and_schema2_inspect_without_run_id(self):
        run = self.root / 'historical-run'
        run.mkdir()
        for schema in (1, 2):
            manifest = {'schema_version': schema, 'state': 'complete', 'hashes': {},
                        'pending_hashes': {}, 'temporary_paths': [], 'resource_claims': [],
                        'operation': {'disposition': 'complete', 'phase': 'complete'}}
            with self.subTest(schema=schema), patch.object(recovery_artifacts, '_load_run', return_value=(run, manifest, {})), \
                    patch.object(recovery_artifacts, '_verify_files'):
                inspected = recovery.inspect_run(run)
                self.assertIsNone(inspected['review_id'])

    def controller(self, name='new controller', provider='codex'):
        return {'identity': {'kind': 'coordinator', 'name': name, 'provider_id': provider},
                'source': 'test harness context'}

    def events(self, run):
        return [json.loads(line) for line in (run / 'trazabilidad.jsonl').read_text(encoding='utf-8').splitlines()]

    def restart_request(self, source, *, scope=None, controller_name='Restart coordinator', authority=None, **extra):
        return {'profile_input': self.profile_input('deep'),
                'controller': self.controller(controller_name),
                'authority': authority or 'User requested a fresh linked review',
                'current_inputs': self.current(source, scope=scope), **extra}

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
        self.assertEqual(candidate['applicability'], 'unknown')
        actions = {row['action'] for row in candidate['actions']}
        self.assertIn('show_historical_report', actions)
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

    def test_legacy_description_identity_is_not_reconstructed_as_current_input(self):
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

        self.assertEqual(candidate['applicability'], 'unknown')
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
        # Keep the same controller so this read/plan assertion does not also
        # request the durable takeover behavior covered by the test below.
        run = self.prepare7(controller=self.controller())
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

        def fail_after_selected_bytes(path, data, **kwargs):
            nonlocal interrupted
            if not interrupted and Path(path).as_posix().endswith('/pending/context.json'):
                original(path, data, **kwargs)
                interrupted = True
                raise OSError('simulated crash after checkpoint context write')
            original(path, data, **kwargs)

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
        context_value = self.read(context)
        context_value['review_inputs'] = copy.deepcopy(manifest['review_inputs'])
        context = self.write('late-profile-context.json', context_value)
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
                   'profile_reference': selection['reference'], 'profile_history': [selection],
                   'execution_plan': [], 'executors': []}
        artifacts.register(source, [str(session)], context_input=self.write('source-context.json', context))
        before = self.snapshot(session)
        with self.assertRaisesRegex(ValueError, 'transfer paths'):
            artifacts.restart(source, profile_input=self.profile_input('deep'), controller=self.controller(),
                              authority='User requested a restart', current_inputs=self.current(source))
        self.assertEqual(before, self.snapshot(session))

        request = self.restart_request(source, controller_name='Successor coordinator',
                                       authority='User requested a restart after stopping the source',
                                       transfer_paths=[str(session)])
        original_transfer = artifacts.transfer_resources

        def interrupt_after_transfer(*args, **kwargs):
            original_transfer(*args, **kwargs)
            raise OSError('transfer committed before restart interruption')

        with patch.object(artifacts, 'transfer_resources', side_effect=interrupt_after_transfer):
            with self.assertRaisesRegex(OSError, 'transfer committed'):
                artifacts.restart(source, **request)

        successor = Path(artifacts.restart(source, **request))

        self.assertEqual(review_resource_claims.verify_claim(session, successor)['run_id'],
                         self.read(successor / 'cierre.json')['run_id'])
        self.assertEqual(self.read(source / 'cierre.json')['operation']['disposition'], 'superseded')
        self.assertEqual(self.read(successor / 'cierre.json')['resource_claims'][0]['status'], 'owned')
        review_workspace.cleanup(argparse.Namespace(manifest=str(session / 'manifest.json'),
                                                      run_dir=str(successor)))

    def test_restart_link_failure_retry_reuses_reserved_successor(self):
        source = self.prepare7('standard')
        request = self.restart_request(source)
        with patch.object(artifacts, '_link_restart', side_effect=OSError('link interrupted')):
            with self.assertRaisesRegex(OSError, 'link interrupted'):
                artifacts.restart(source, **request)

        result = Path(artifacts.restart(source, **request))
        successors = [path.parent for path in self.output.rglob('cierre.json')
                      if self.read(path).get('previous_run') == str(source)]
        self.assertEqual(successors, [result])
        self.assertEqual(Path(artifacts.restart(source, **request)), result)

    def test_restart_missing_owned_resource_links_without_claiming_cleanup(self):
        session = Path(review_workspace.prepare(argparse.Namespace(
            repo=str(self.repo), ref='HEAD', mode='commit', role=['review'], include_untracked=[]))['session_dir'])
        source = self.prepare7('standard')
        selection = self.read(source / 'cierre.json')['profile_history'][0]
        context = {'profile': selection['profile'], 'selection_source': selection['selection_source'],
                   'profile_reference': selection['reference'], 'profile_history': [selection],
                   'execution_plan': [], 'executors': []}
        artifacts.register(source, [str(session)], context_input=self.write('missing-context.json', context))
        session_manifest = self.read(session / 'manifest.json')
        workspace = Path(session_manifest['workspaces'][0]['path'])
        removed = subprocess.run(['git', 'worktree', 'remove', '--force', str(workspace)], cwd=self.repo,
                                 capture_output=True, text=True)
        self.assertEqual(removed.returncode, 0, removed.stderr)
        shutil.rmtree(session, ignore_errors=True)

        successor = Path(artifacts.restart(source, **self.restart_request(source)))

        old = self.read(source / 'cierre.json')
        self.assertEqual(old['resource_claims'][0]['status'], 'owned')
        self.assertIsNone(old.get('resource_cleanup'))
        inspected = recovery.inspect_run(source)
        self.assertEqual(inspected['resources'][0]['availability'], 'missing_unknown')
        self.assertEqual(self.read(successor / 'cierre.json')['previous_run'], str(source))
        self.assertEqual(self.read(successor / 'cierre.json')['resource_claims'], [])

    def test_pending_restart_blocks_other_source_mutations(self):
        source = self.prepare7('standard')
        transfer_target = self.prepare7('standard')
        request = self.restart_request(source)
        with patch.object(artifacts, '_link_restart', side_effect=OSError('link interrupted')):
            with self.assertRaisesRegex(OSError, 'link interrupted'):
                artifacts.restart(source, **request)
        before = self.snapshot(source)

        with self.assertRaisesRegex(ValueError, 'restart|pending|intent'):
            artifacts.transfer_resources(source, transfer_target, [str(self.root)],
                                         authority='User requested unrelated transfer',
                                         controller=self.controller())

        with self.assertRaisesRegex(ValueError, 'restart|pending|intent'):
            artifacts.recover_resource_cleanup(source)

        with self.assertRaisesRegex(ValueError, 'restart|pending|intent'):
            artifacts.pause(source, authority='User requested pause', reason='Wait for input', phase='discovery')

        self.assertEqual(before, self.snapshot(source))

    def test_recover_records_controller_takeover(self):
        run = self.prepare7('standard')
        artifacts.pause(run, authority='User requested pause', reason='Waiting for input', phase='discovery')

        result = artifacts.recover(run, controller=self.controller('Recovery coordinator'),
                                   authority='User authorized controller takeover',
                                   current_inputs=self.current(run))

        manifest = self.read(run / 'cierre.json')
        self.assertEqual(result['status'], 'paused')
        self.assertEqual(manifest['controller']['identity']['name'], 'Recovery coordinator')
        self.assertTrue(any('prior controller recorded as' in event['summary'] for event in self.events(run)))

    def test_restart_uses_current_harness_identity(self):
        source = self.prepare7('standard')

        successor = Path(artifacts.restart(
            source, **self.restart_request(source),
            harness={'harness': 'Claude Code Desktop', 'harness_id': 'claude-code-desktop',
                     'harness_source': {'kind': 'user', 'reference': '--harness-id'}}))

        manifest = self.read(successor / 'cierre.json')
        self.assertEqual(manifest['harness'], 'Claude Code Desktop')
        self.assertEqual(manifest['harness_id'], 'claude-code-desktop')
        self.assertEqual(manifest['harness_source'], {'kind': 'user', 'reference': '--harness-id'})

    def test_complete_and_legacy_source_bytes_remain_unchanged_on_restart(self):
        current_run, current_session = self.retained_claimed_run()
        review_workspace.cleanup(argparse.Namespace(manifest=str(current_session / 'manifest.json'),
                                                     run_dir=str(current_run)))
        artifacts.close(current_run, cleanup='complete')
        current_before = self.snapshot(current_run)
        current_successor = artifacts.restart(
            current_run, **self.restart_request(current_run, controller_name='Current successor'))
        self.assertEqual(current_before, self.snapshot(current_run))
        self.assertEqual(self.read(Path(current_successor) / 'cierre.json')['previous_run'], str(current_run))

        legacy_run = self.prepare_legacy()
        self.retain_legacy(legacy_run)
        self.close(legacy_run)
        legacy_before = self.snapshot(legacy_run)
        legacy_current = current_inputs(self.read(legacy_run / 'cierre.json')['scope'], source_set_complete=True)
        legacy_successor = artifacts.restart(
            legacy_run, profile_input=self.profile_input('deep'), controller=self.controller('Legacy successor'),
            authority='User requested a new linked review', current_inputs=legacy_current)
        self.assertEqual(legacy_before, self.snapshot(legacy_run))
        self.assertEqual(self.read(Path(legacy_successor) / 'cierre.json')['previous_run'], str(legacy_run))

    def test_two_process_restarts_have_one_successor(self):
        source = self.prepare7('standard')
        request = self.restart_request(source)
        profile = self.write('restart-profile.json', request['profile_input'])
        controller = self.write('restart-controller.json', request['controller'])
        authority = self.write('restart-authority.json', {'authority': request['authority']})
        current = self.write('restart-current.json', request['current_inputs'])
        harness_source = self.write('restart-harness-source.json',
                                    {'kind': 'user', 'reference': '--harness-id'})
        command = [sys.executable, '-B', str(SCRIPTS / 'review_artifacts.py'), 'restart',
                   '--run-dir', str(source), '--profile-input', str(profile),
                   '--controller-input', str(controller), '--authority-input', str(authority),
                   '--current-inputs', str(current), '--harness', 'Claude Code Desktop',
                   '--harness-id', 'claude-code-desktop', '--harness-source-input', str(harness_source)]
        processes = [subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                      encoding='utf-8') for _ in range(2)]
        outputs = [process.communicate(timeout=60) for process in processes]

        self.assertEqual([process.returncode for process in processes], [0, 0], outputs)
        paths = {json.loads(stdout)['run_dir'] for stdout, _ in outputs}
        self.assertEqual(len(paths), 1, outputs)
        self.assertEqual(sum(1 for path in self.output.rglob('cierre.json')
                             if self.read(path).get('previous_run') == str(source)), 1)
        successor = self.read(Path(next(iter(paths))) / 'cierre.json')
        self.assertEqual(successor['harness_id'], 'claude-code-desktop')
        self.assertEqual(successor['harness_source'], {'kind': 'user', 'reference': '--harness-id'})

    def test_restart_each_reservation_boundary_reuses_the_same_destination(self):
        source = self.prepare7('standard')
        request = self.restart_request(source)
        with patch.object(artifacts, '_write_active_restart', side_effect=OSError('intent boundary')):
            with self.assertRaisesRegex(OSError, 'intent boundary'):
                artifacts.restart(source, **request)
        self.assertFalse(any(self.read(path).get('previous_run') == str(source)
                             for path in self.output.rglob('cierre.json')))
        with patch.object(artifacts, '_prepare_from_restart_intent', side_effect=OSError('reservation boundary')):
            with self.assertRaisesRegex(OSError, 'reservation boundary'):
                artifacts.restart(source, **request)

        result = Path(artifacts.restart(source, **request))
        successors = [path.parent for path in self.output.rglob('cierre.json')
                      if self.read(path).get('previous_run') == str(source)]
        self.assertEqual(successors, [result])
        self.assertEqual(Path(artifacts.restart(source, **request)), result)

    def test_active_descriptor_retry_after_commit_and_retirement(self):
        source = self.prepare7('standard')
        request = self.restart_request(source)
        with patch.object(artifacts, '_retire_active_restart', side_effect=OSError('retirement interrupted')):
            with self.assertRaisesRegex(OSError, 'retirement interrupted'):
                artifacts.restart(source, **request)

        result = Path(artifacts.restart(source, **request))
        source_manifest = self.read(source / 'cierre.json')
        active_dir = source.parent / '.restart-intents' / source_manifest['run_id']
        self.assertFalse((active_dir / 'active.json').exists())
        self.assertFalse((active_dir / 'active.owner.json').exists())
        self.assertEqual(self.read(result / 'cierre.json')['restart_operation']['source_run'], str(source))

    def test_recover_completes_the_exact_pending_restart(self):
        source = self.prepare7('standard')
        request = self.restart_request(source)
        with patch.object(artifacts, '_prepare_from_restart_intent', side_effect=OSError('restart interrupted')):
            with self.assertRaisesRegex(OSError, 'restart interrupted'):
                artifacts.restart(source, **request)

        outcome = artifacts.recover(source, controller=request['controller'], authority=request['authority'],
                                    current_inputs=request['current_inputs'])

        successor = Path(outcome['successor_run_dir'])
        self.assertEqual(outcome['status'], 'restarted', outcome)
        self.assertEqual(self.read(successor / 'cierre.json')['previous_run'], str(source))
        self.assertEqual(self.read(source / 'cierre.json')['operation']['disposition'], 'superseded')

    def test_adopt_context_object_before_successor_creation(self):
        session = Path(review_workspace.prepare(argparse.Namespace(
            repo=str(self.repo), ref='HEAD', mode='commit', role=['review'], include_untracked=[]))['session_dir'])
        source = self.prepare7('standard')

        successor = Path(artifacts.restart(source, **self.restart_request(source),
                                           transfer_paths=[str(session)]))

        claim = review_resource_claims.verify_claim(session, successor)
        self.assertEqual(claim['archive_path'], str(successor))
        successor_manifest = self.read(successor / 'cierre.json')
        self.assertEqual(successor_manifest['resource_claims'][0]['session_dir'], str(session))
        self.assertEqual(successor_manifest['resource_claims'][0]['status'], 'owned')
        review_workspace.cleanup(argparse.Namespace(manifest=str(session / 'manifest.json'),
                                                     run_dir=str(successor)))

    def test_pending_checkpoint_with_changed_head_can_restart(self):
        source = self.prepare7('standard')
        manifest = self.read(source / 'cierre.json')
        selection = manifest['profile_history'][0]
        context = {'profile': selection['profile'], 'selection_source': selection['selection_source'],
                   'profile_reference': selection['reference'], 'profile_history': [selection],
                   'execution_plan': [], 'executors': [], 'review_inputs': manifest['review_inputs']}
        context_path = self.write('pending-restart-context.json', context)
        with patch.object(artifacts, '_checkpoint_commit', side_effect=OSError('checkpoint commit interrupted')):
            with self.assertRaisesRegex(OSError, 'checkpoint commit interrupted'):
                artifacts.checkpoint(source, context_input=context_path, phase='discovery')
        pending_before = self.read(source / 'cierre.json')
        self.assertIn('checkpoint_transaction', pending_before)
        new_scope = copy.deepcopy(manifest['scope'])
        new_scope['head'] = 'new-reviewed-head'

        successor = Path(artifacts.restart(source, **self.restart_request(source, scope=new_scope)))

        self.assertEqual(self.read(successor / 'cierre.json')['scope'], new_scope)
        self.assertEqual(self.read(source / 'cierre.json')['checkpoint_transaction'],
                         pending_before['checkpoint_transaction'])
        self.assertFalse(self.read(successor / 'cierre.json').get('checkpoint'))

    def test_recover_owned_bytes_with_changed_inputs_cannot_continue(self):
        source = self.prepare7('standard')
        manifest = self.read(source / 'cierre.json')
        selection = manifest['profile_history'][0]
        context_path = self.write('pending-recovery-context.json', {
            'profile': selection['profile'], 'selection_source': selection['selection_source'],
            'profile_reference': selection['reference'], 'profile_history': [selection],
            'execution_plan': [], 'executors': [], 'review_inputs': manifest['review_inputs']})
        with patch.object(artifacts, '_checkpoint_commit', side_effect=OSError('checkpoint commit interrupted')):
            with self.assertRaisesRegex(OSError, 'checkpoint commit interrupted'):
                artifacts.checkpoint(source, context_input=context_path, phase='discovery')
        changed_scope = copy.deepcopy(manifest['scope'])
        changed_scope['head'] = 'different-head'

        outcome = artifacts.recover(source, controller=self.controller('Recovery coordinator'),
                                    authority='User authorized exact-byte recovery',
                                    current_inputs=self.current(source, scope=changed_scope))

        self.assertEqual(outcome['input_appraisal']['applicability'], 'changed')
        self.assertNotIn('continue', {row['action'] for row in outcome['actions']})
        self.assertIn('restart', {row['action'] for row in outcome['actions']})

    def test_foreign_reserved_target_is_not_adopted(self):
        source = self.prepare7('standard')
        request = self.restart_request(source)

        def occupy(intent_path):
            intent = self.read(intent_path)
            target = Path(intent['successor']['run_dir'])
            target.parent.mkdir(parents=True, exist_ok=True)
            target.mkdir()
            (target / 'foreign.txt').write_text('foreign bytes', encoding='utf-8')
            raise OSError('simulated stop after destination collision')

        with patch.object(artifacts, '_prepare_from_restart_intent', side_effect=occupy):
            with self.assertRaisesRegex(OSError, 'destination collision'):
                artifacts.restart(source, **request)
        operation_files = list((source.parent / '.restart-intents').rglob('*.json'))
        intent = next(self.read(path) for path in operation_files if path.name != 'active.json'
                      and path.name != 'active.owner.json' and not path.name.endswith('.complete.json'))
        target = Path(intent['successor']['run_dir'])
        before = (target / 'foreign.txt').read_bytes()

        with self.assertRaisesRegex(ValueError, 'foreign|reserved|occupied'):
            artifacts.restart(source, **request)

        self.assertEqual((target / 'foreign.txt').read_bytes(), before)
        self.assertFalse((target / 'cierre.json').exists())

    def test_cleanup_records_receipt_before_return(self):
        session = Path(review_workspace.prepare(argparse.Namespace(
            repo=str(self.repo), ref='HEAD', mode='commit', role=['review'], include_untracked=[]))['session_dir'])
        run = self.prepare7('focused')
        selection = self.read(run / 'cierre.json')['profile_history'][0]
        context = {'profile': selection['profile'], 'selection_source': selection['selection_source'],
                   'profile_reference': selection['reference'], 'profile_history': [selection],
                   'execution_plan': [], 'executors': []}
        artifacts.register(run, [str(session)], context_input=self.write('cleanup-register-context.json', context))

        result = review_workspace.cleanup(argparse.Namespace(manifest=str(session / 'manifest.json'),
                                                               run_dir=str(run)))

        manifest = self.read(run / 'cierre.json')
        self.assertFalse(session.exists())
        self.assertEqual(result['released_claims'], manifest['cleanup_receipts'])
        self.assertEqual(manifest['resource_claims'][0]['status'], 'released')

    def test_close_same_cleanup_observation_after_interruption_and_complete(self):
        run, session = self.retained_claimed_run()
        review_workspace.cleanup(argparse.Namespace(manifest=str(session / 'manifest.json'),
                                                     run_dir=str(run)))
        receipts = self.read(run / 'cierre.json')['cleanup_receipts']
        self.assertEqual(len(receipts), 1)

        receipts_input = self.write('released-claims.json', receipts)
        original = artifacts.atomic_write
        interrupted = False

        def fail_report_once(path, data):
            nonlocal interrupted
            if Path(path).name == 'informe.md' and not interrupted:
                interrupted = True
                raise OSError('simulated close interruption after review.json')
            original(path, data)

        with patch.object(artifacts, 'atomic_write', side_effect=fail_report_once), self.assertRaisesRegex(
                OSError, 'simulated close interruption'):
            artifacts.close(run, cleanup='complete', released_claims=receipts)

        interrupted_snapshot = self.snapshot(run)
        with self.assertRaisesRegex(ValueError, 'differs from the exact durable cleanup observation'):
            artifacts.close(run, cleanup='pending')
        self.assertEqual(interrupted_snapshot, self.snapshot(run))

        closed = subprocess.run([sys.executable, '-B', str(SCRIPTS / 'review_artifacts.py'), 'close',
                                 '--run-dir', str(run), '--cleanup', 'complete',
                                 '--released-claims-input', str(receipts_input)],
                                capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(closed.returncode, 0, closed.stderr)
        before_replay = self.snapshot(run)
        artifacts.close(run, cleanup='complete')

        self.assertEqual(self.snapshot(run), before_replay)

        altered = dict(receipts[0], claim_sha256='0' * 64)
        with self.assertRaisesRegex(ValueError, 'receipt|cleanup|closed|complete'):
            artifacts.close(run, cleanup='complete', released_claims=[altered])

    def test_close_refuses_reappeared_released_workspace(self):
        run, session = self.retained_claimed_run()
        review_workspace.cleanup(argparse.Namespace(manifest=str(session / 'manifest.json'),
                                                     run_dir=str(run)))
        session.mkdir()
        before = self.snapshot(run)

        with self.assertRaisesRegex(ValueError, 'released resource path exists again'):
            artifacts.close(run, cleanup='pending', residuals=[str(session)])

        self.assertEqual(before, self.snapshot(run))
        shutil.rmtree(session)

    def test_cleanup_crash_after_delete_recovers_own_intent(self):
        run, session = self.retained_claimed_run()
        original = shutil.rmtree

        def delete_then_interrupt(path, *args, **kwargs):
            original(path, *args, **kwargs)
            if Path(path) == session:
                raise OSError('simulated stop after session deletion')

        with patch.object(review_workspace.shutil, 'rmtree', side_effect=delete_then_interrupt):
            with self.assertRaisesRegex(OSError, 'simulated stop'):
                review_workspace.cleanup(argparse.Namespace(manifest=str(session / 'manifest.json'),
                                                              run_dir=str(run)))

        manifest = self.read(run / 'cierre.json')
        recovered = artifacts.recover(run, controller=manifest['controller'],
                                      authority='User requested cleanup recovery',
                                      current_inputs=self.current(run))
        manifest = self.read(run / 'cierre.json')
        self.assertEqual(recovered['status'], 'plan')
        self.assertEqual(recovered['actions'][0]['action'], 'retry_close')
        self.assertEqual(len(manifest['cleanup_receipts']), 1)
        self.assertEqual(manifest['resource_claims'][0]['status'], 'released')

    def test_pending_cleanup_is_visible_and_recovery_does_not_delete(self):
        run, session = self.retained_claimed_run()
        artifacts.begin_resource_cleanup(run, session)
        before_run = self.snapshot(run)
        before_session = self.snapshot(session)

        inspected = recovery.inspect_run(run, current_inputs=self.current(run))
        recovered = artifacts.recover(run, controller=self.read(run / 'cierre.json')['controller'],
                                      authority='User requested cleanup recovery',
                                      current_inputs=self.current(run))

        resource = next(row for row in inspected['resources'] if row['path'] == str(session))
        self.assertEqual(resource['availability'], 'cleanup_pending')
        self.assertIn({'kind': 'resource_cleanup', 'status': 'pending',
                       'operation_id': self.read(run / 'cierre.json')['resource_cleanup']['operation_id']},
                      inspected['pending_transaction'])
        self.assertEqual(recovered['actions'][0]['action'], 'retry_cleanup')
        self.assertEqual(before_run, self.snapshot(run))
        self.assertEqual(before_session, self.snapshot(session))

    def test_pending_close_advances_after_cleanup_receipt(self):
        run, session = self.retained_claimed_run()
        artifacts.close(run, cleanup='pending', residuals=[str(session)])
        self.assertEqual(self.read(run / 'cierre.json')['state'], 'closing')

        review_workspace.cleanup(argparse.Namespace(manifest=str(session / 'manifest.json'),
                                                     run_dir=str(run)))
        closed = artifacts.close(run, cleanup='complete')

        self.assertEqual(closed['state'], 'complete')
        self.assertEqual(closed['resource_claims'][0]['status'], 'released')
        self.assertEqual(closed['close_observation']['cleanup'], 'complete')

    def test_cleanup_conflicts_with_transfer(self):
        session = Path(review_workspace.prepare(argparse.Namespace(
            repo=str(self.repo), ref='HEAD', mode='commit', role=['review'], include_untracked=[]))['session_dir'])
        source = self.prepare7('focused')
        selection = self.read(source / 'cierre.json')['profile_history'][0]
        context = {'profile': selection['profile'], 'selection_source': selection['selection_source'],
                   'profile_reference': selection['reference'], 'profile_history': [selection],
                   'execution_plan': [], 'executors': []}
        artifacts.register(source, [str(session)], context_input=self.write('cleanup-conflict-context.json', context))
        successor = self.prepare7('focused')
        artifacts.register(successor, [], context_input=self.write('cleanup-successor-context.json', {
            'profile': self.read(successor / 'cierre.json')['profile_history'][0]['profile'],
            'selection_source': 'automatic',
            'profile_reference': self.read(successor / 'cierre.json')['profile_history'][0]['reference'],
            'profile_history': self.read(successor / 'cierre.json')['profile_history'],
            'execution_plan': [], 'executors': []}))
        artifacts.begin_resource_cleanup(source, session)
        before = (self.snapshot(source), self.snapshot(successor), self.snapshot(session))

        with self.assertRaisesRegex(ValueError, 'cleanup|releasing'):
            artifacts.transfer_resources(source, successor, [str(session)], authority='User requested transfer',
                                         controller=self.controller())

        self.assertEqual(before, (self.snapshot(source), self.snapshot(successor), self.snapshot(session)))

    def test_missing_without_receipt_is_reported_as_unknown(self):
        session = Path(review_workspace.prepare(argparse.Namespace(
            repo=str(self.repo), ref='HEAD', mode='commit', role=['review'], include_untracked=[]))['session_dir'])
        run = self.prepare7('focused')
        selection = self.read(run / 'cierre.json')['profile_history'][0]
        context = {'profile': selection['profile'], 'selection_source': selection['selection_source'],
                   'profile_reference': selection['reference'], 'profile_history': [selection],
                   'execution_plan': [], 'executors': []}
        artifacts.register(run, [str(session)], context_input=self.write('missing-context.json', context))
        shutil.rmtree(session)

        inspected = recovery.inspect_run(run, current_inputs=self.current(run))

        resource = next(row for row in inspected['resources'] if row['path'] == str(session))
        self.assertEqual(resource['availability'], 'missing_unknown')
        self.assertEqual(resource['claim_status'], 'owned')

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
