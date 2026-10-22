"""End-to-end archive-8 recovery sequences using owned synthetic repositories."""
import argparse
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from unittest.mock import patch

import test_review_recovery as recovery_tests
from ccr.archive import checkpoints as checkpoint_ops
from recovery_fixtures import context10, current_inputs, record10, selection_input, source_events

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
artifacts = recovery_tests.artifacts
recovery = recovery_tests.recovery
review_workspace = recovery_tests.review_workspace


class _RecoveryFixture:
    setUp = recovery_tests.ReviewRecoveryTests.setUp
    git = recovery_tests.ReviewRecoveryTests.git
    snapshot = recovery_tests.ReviewRecoveryTests.snapshot
    read = recovery_tests.ReviewRecoveryTests.read
    write = recovery_tests.ReviewRecoveryTests.write
    profile_input = recovery_tests.ReviewRecoveryTests.profile_input
    prepare7 = recovery_tests.ReviewRecoveryTests.prepare7
    current = recovery_tests.ReviewRecoveryTests.current
    controller = recovery_tests.ReviewRecoveryTests.controller
    events = recovery_tests.ReviewRecoveryTests.events
    restart_request = recovery_tests.ReviewRecoveryTests.restart_request
    close = recovery_tests.ReviewRecoveryTests.close

    def session(self):
        result = review_workspace.prepare(argparse.Namespace(
            repo=str(self.repo), ref='HEAD', mode='commit', role=['review'], include_untracked=[]))
        return Path(result['session_dir'])

    def empty_context(self, run):
        manifest = self.read(run / 'cierre.json')
        history = copy.deepcopy(manifest['profile_history'])
        return self.write('empty-context-' + manifest['run_id'] + '.json', {
            'profile': history[-1]['profile'],
            'selection_source': history[0]['selection_source'],
            'profile_reference': history[-1]['reference'],
            'profile_history': history,
            'execution_plan': copy.deepcopy(manifest.get('assignment_registry', [])),
            'executors': [],
            'review_inputs': copy.deepcopy(manifest['review_inputs']),
        })

    def final_material(self, run, *, previous_reviews=None):
        manifest = self.read(run / 'cierre.json')
        if manifest['scope']['mode'] in {'commit', 'staged', 'unstaged', 'working'}:
            manifest['review_inputs']['description_identity'] = None
            artifacts._save_manifest(run, manifest, self.read(run / artifacts.MARKER))
            manifest = self.read(run / 'cierre.json')
        history = copy.deepcopy(manifest['profile_history'])
        selection_source = history[0]['selection_source']
        final = record10(history[-1]['profile'], selection_source)
        final['scope'] = copy.deepcopy(manifest['scope'])
        if final['scope']['mode'] not in {'mr', 'pr'}:
            final['description'] = {'status': 'not_applicable', 'identity': None, 'details': ''}
        final['review_id'] = 'CR-' + manifest['run_id']
        final['previous_reviews'] = copy.deepcopy(previous_reviews or [])
        final['coverage']['execution']['profile_history'] = history
        for row in final['coverage']['execution']['plan']:
            row['selection_id'] = history[-1]['id']
            row['superseded_by'] = None
        context = context10(final)
        context.update(profile_history=history, profile_reference=history[-1]['reference'],
                       review_inputs=copy.deepcopy(manifest['review_inputs']))
        context_path = self.write('context-' + manifest['run_id'] + '.json', context)
        artifacts.register(run, manifest.get('temporary_paths', []), context_input=context_path)
        for index, event in enumerate(source_events(final)):
            if event['kind'] == 'profile':
                continue
            identity = event.get('actor', {'name': 'coordinator', 'provider_id': None})
            observed = {
                'kind': event['kind'], 'status': event['status'],
                'summary': 'Observed synthetic review step',
                'actor': dict(identity, kind='agent'), 'executor': event.get('executor'),
                'provenance': {'kind': 'tool', 'source': 'recovery sequence test'},
                'evidence': event['evidence'], 'relations': [], 'authority': None,
                'occurred_at': None,
            }
            artifacts.record_event(run, self.write(
                'event-' + manifest['run_id'] + '-' + str(index) + '.json', observed))
        plan = final['coverage']['execution']['plan']
        briefs = self.write('briefs.json',
                            {row['id']: {'questions': ['Check invariant']} for row in plan})
        results = self.write('results.json',
                             {row['id']: {'result': 'completed'} for row in plan})
        review = self.write('final.json', final)
        return final, context_path, review, [briefs, results]

    def cli(self, area, *args):
        result = subprocess.run([sys.executable, '-B', '-X', 'utf8', str(SCRIPTS), area,
                                 *map(str, args)], cwd=self.repo, capture_output=True,
                                text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0,
                         f'CLI failed: {area} {args}\n{result.stderr}\n{result.stdout}')
        return json.loads(result.stdout)


class ReviewRecoverySequenceTests(_RecoveryFixture, unittest.TestCase):
    def test_a_b_register_c_retain_cleanup_close_replay(self):
        session = self.session()
        a = self.prepare7('standard')
        artifacts.register(a, [str(session)], context_input=self.empty_context(a))
        events_a_before = self.events(a)
        current_harness = {
            'harness': 'Claude Code Desktop',
            'harness_id': 'claude-code-desktop',
            'harness_source': {'kind': 'user', 'reference': '--harness-id'},
        }

        b = Path(artifacts.restart(a, **self.restart_request(
            a, controller_name='Sequence coordinator', transfer_paths=[str(session)],
            harness=current_harness)))
        artifacts.register(b, [str(session)], context_input=self.empty_context(b))
        c = Path(artifacts.restart(b, **self.restart_request(
            b, controller_name='Sequence coordinator', transfer_paths=[str(session)],
            harness=current_harness)))

        transfer_history = artifacts.normalize_transfer_history(self.read(b / 'cierre.json'))
        self.assertEqual(len(transfer_history), 2)
        self.assertTrue(all(row['status'] == 'complete' for row in transfer_history))
        final, context_path, review_path, evidence = self.final_material(c)
        cleanup_intent = artifacts.begin_resource_cleanup(c, str(session))
        cleanup = review_workspace.cleanup(argparse.Namespace(
            manifest=str(session / 'manifest.json'), run_dir=str(c)))
        receipts = cleanup['released_claims']
        self.assertEqual(receipts[0]['run_id'], self.read(c / 'cierre.json')['run_id'])

        artifacts.retain(c, review_path, context_input=context_path, evidence_inputs=evidence,
                         expected_schema=10)
        current_controller = self.read(c / 'cierre.json')['controller']
        self.assertEqual(current_controller['identity']['name'], 'Sequence coordinator')
        self.assertEqual(self.read(c / 'cierre.json')['harness_id'], 'claude-code-desktop')
        artifacts.close(c, cleanup='complete', released_claims=receipts)
        self.assertEqual(artifacts.validate(c, require_complete=True)['state'], 'complete')
        complete_snapshot = self.snapshot(c)
        artifacts.close(c, cleanup='complete', released_claims=receipts)

        self.assertEqual(complete_snapshot, self.snapshot(c))
        self.assertEqual(self.events(a)[:len(events_a_before)], events_a_before)
        self.assertEqual(self.read(a / 'cierre.json')['operation']['disposition'], 'superseded')
        self.assertEqual(self.read(b / 'cierre.json')['resource_claims'][0]['status'], 'transferred')
        self.assertEqual(self.read(c / 'cierre.json')['resource_claims'][0]['status'], 'released')
        self.assertEqual(final['review_id'], 'CR-' + self.read(c / 'cierre.json')['run_id'])
        self.assertEqual(cleanup_intent['status'], 'pending')

    def test_interrupted_checkpoint_changed_head_missing_session_new_harness_restart(self):
        session = self.session()
        source = self.prepare7('standard')
        artifacts.register(source, [str(session)], context_input=self.empty_context(source))
        source_before = self.read(source / 'cierre.json')
        context_path = self.empty_context(source)
        with patch.object(checkpoint_ops, '_checkpoint_commit',
                          side_effect=OSError('checkpoint commit interrupted')):
            with self.assertRaisesRegex(OSError, 'checkpoint commit interrupted'):
                artifacts.checkpoint(source, context_input=context_path, phase='discovery')
        pending = self.read(source / 'cierre.json')
        self.assertIn('checkpoint_transaction', pending)
        source_events = self.events(source)
        shutil.rmtree(session)
        changed_scope = copy.deepcopy(source_before['scope'])
        changed_scope['head'] = 'changed-head-after-interruption'
        current = self.current(source, scope=changed_scope)
        controller = self.controller('Replacement coordinator')

        recovered = artifacts.recover(source, controller=controller,
                                       authority='User authorized maintenance and restart',
                                       current_inputs=current)
        self.assertEqual(recovered['input_appraisal']['applicability'], 'changed')
        self.assertIn('restart', {item['action'] for item in recovered['actions']})
        self.assertNotIn('continue', {item['action'] for item in recovered['actions']})
        successor = Path(artifacts.restart(source, **self.restart_request(
            source, scope=changed_scope, controller_name='Replacement coordinator',
            authority='User authorized a fresh review',
            harness={'harness': 'Claude Code Desktop', 'harness_id': 'claude-code-desktop',
                     'harness_source': {'kind': 'user', 'reference': '--harness-id'}})))

        successor_manifest = self.read(successor / 'cierre.json')
        source_manifest = self.read(source / 'cierre.json')
        self.assertEqual(successor_manifest['scope'], changed_scope)
        self.assertEqual(successor_manifest['harness_id'], 'claude-code-desktop')
        self.assertEqual(successor_manifest['harness_source']['reference'], '--harness-id')
        self.assertEqual(successor_manifest['previous_run'], str(source))
        self.assertEqual(successor_manifest['resource_claims'], [])
        self.assertFalse(successor_manifest.get('checkpoint'))
        self.assertEqual(source_manifest['resource_claims'][0]['status'], 'owned')
        self.assertIsNone(source_manifest.get('resource_cleanup'))
        self.assertEqual(self.events(source)[:len(source_events)], source_events)
        inspected = recovery.inspect_run(source, current_inputs=current)
        self.assertEqual(inspected['resources'][0]['availability'], 'missing_unknown')

    def test_archive8_commands_end_to_end(self):
        helper = 'artifacts'
        scope = self.read(self.scope)
        record = record10('standard', 'automatic')
        inputs = current_inputs(scope, {}, source_set_complete=True,
            description_identity=record['description']['identity'], requirements_identity=None,
            plan_identity=None, configuration_identity=None, profile='standard')
        profile = selection_input('standard', 'automatic')
        controller = self.controller('CLI coordinator')
        selection_file = self.write('cli-initial-selection.json', profile)
        controller_file = self.write('cli-controller.json', controller)
        inputs_file = self.write('cli-inputs.json', inputs)
        harness_source = self.write('cli-harness-source.json',
                                    {'kind': 'user', 'reference': '--harness-source-file'})
        prepared = self.cli(helper, 'prepare', '--repo', self.repo, '--scope-file', self.scope,
                            '--skill-version', '2.12.1', '--harness', 'Codex', '--harness-id', 'codex-cli',
                            '--harness-source-file', harness_source, '--output-root', self.output,
                            '--profile-input', selection_file, '--controller-input', controller_file,
                            '--current-inputs', inputs_file)
        run = Path(prepared['run_dir'])

        lookup = self.cli(helper, 'lookup', '--repo', self.repo, '--scope-file', self.scope,
                          '--archive-root', self.output, '--current-inputs', inputs_file)
        self.assertEqual(lookup['candidates'][0]['run_dir'], str(run))
        inspected = self.cli(helper, 'inspect', '--run-dir', run, '--current-inputs', inputs_file)
        self.assertEqual(inspected['run_id'], self.read(run / 'cierre.json')['run_id'])
        authority = self.write('cli-authority.json', {'authority': 'User requested the documented transition'})
        self.cli(helper, 'pause', '--run-dir', run, '--authority-input', authority,
                 '--reason', 'Documented lifecycle test', '--phase', 'discovery')
        resumed = self.cli(helper, 'resume', '--run-dir', run, '--controller-input', controller_file,
                            '--authority-input', authority, '--current-inputs', inputs_file)
        self.assertEqual(resumed['operation']['disposition'], 'open')
        recovered = self.cli(helper, 'recover', '--run-dir', run, '--controller-input', controller_file,
                             '--authority-input', authority, '--current-inputs', inputs_file)
        self.assertNotIn('dispatch', recovered)

        deep_selection = self.write('cli-deep-selection.json', selection_input('deep', 'automatic'))
        replacement = self.controller('CLI restart coordinator')
        replacement_file = self.write('cli-replacement-controller.json', replacement)
        current_harness_source = self.write('cli-restart-harness-source.json',
                                            {'kind': 'user', 'reference': '--harness-source-input'})
        restarted = self.cli(helper, 'restart', '--run-dir', run, '--profile-input', deep_selection,
                             '--controller-input', replacement_file, '--authority-input', authority,
                             '--current-inputs', inputs_file, '--harness', 'Claude Code Desktop',
                             '--harness-id', 'claude-code-desktop',
                             '--harness-source-input', current_harness_source)
        successor = Path(restarted['run_dir'])
        gate = self.cli(helper, 'validate', '--run-dir', successor)
        successor_manifest = self.read(successor / 'cierre.json')
        self.assertEqual(gate['schema_version'], 8)
        self.assertEqual(successor_manifest['harness_id'], 'claude-code-desktop')
        self.assertEqual(successor_manifest['controller'], replacement)
        docs = (Path(__file__).resolve().parents[1] / 'references' / 'archive' / 'recovery.md').read_text(encoding='utf-8')
        self.assertIn('--harness-id', docs)
        self.assertIn('--harness-source-input', docs)


if __name__ == '__main__':
    unittest.main()
