"""Durable review archives preserve scope, real usage and observed closure."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))
spec = importlib.util.spec_from_file_location('review_artifacts', SCRIPTS / 'review_artifacts.py') if (SCRIPTS / 'review_artifacts.py').exists() else None
artifacts = importlib.util.module_from_spec(spec) if spec else None
if spec:
    spec.loader.exec_module(artifacts)


def record():
    return {'schema_version': 1, 'stage': 'final',
            'scope': {'repository': 'example/service', 'mode': 'commit', 'base': None,
                      'head': 'abc123', 'snapshot': None, 'target': None, 'reference': None},
            'profile': 'economy', 'profile_reason': 'Bounded inspection',
            'responsible': {'name': None, 'username': None, 'verified': False, 'source': None},
            'findings': [], 'checks': [],
            'description': {'status': 'not_applicable', 'identity': None, 'details': ''},
            'coverage': {'adequate': True, 'flows': [], 'limitations': [],
                         'verification': 'skipped', 'stale': False},
            'verdict': 'approvable', 'verdict_reason': 'No confirmed blockers',
            'reservations': [], 'rereview': [], 'aliases': {},
            'resources': {'cleanup': 'not_needed', 'residuals': [], 'publication': 'not_requested'}}


class ArchiveTests(unittest.TestCase):
    def test_close_recovers_owned_marker_manifest_interruption(self):
        for boundary in ('before', 'after'):
            with self.subTest(boundary=boundary):
                run = self.prepare()
                self.retain(run)
                original = artifacts.atomic_write
                interrupted = False
                def interrupt(path, data):
                    nonlocal interrupted
                    if Path(path).name == 'cierre.json' and not interrupted:
                        interrupted = True
                        if boundary == 'after':
                            original(path, data)
                        raise OSError('owned close manifest interrupted')
                    original(path, data)
                with patch.object(artifacts, 'atomic_write', side_effect=interrupt), self.assertRaises(OSError):
                    self.close(run)
                before = self.snapshot(run)
                with self.assertRaises(ValueError):
                    artifacts.validate(run, require_complete=True)
                self.assertEqual(before, self.snapshot(run))
                self.close(run)
                self.assertEqual(artifacts.validate(run, require_complete=True)['state'], 'complete')
                self.assertNotIn('previous_manifest_sha256', self.read(run / artifacts.MARKER))
                before = self.snapshot(run)
                self.close(run)
                self.assertEqual(before, self.snapshot(run))

    def test_close_recovery_refuses_foreign_manifest_bytes(self):
        run = self.prepare()
        self.retain(run)
        original = artifacts.atomic_write
        def interrupt(path, data):
            if Path(path).name == 'cierre.json':
                raise OSError('owned close manifest interrupted')
            original(path, data)
        with patch.object(artifacts, 'atomic_write', side_effect=interrupt), self.assertRaises(OSError):
            self.close(run)
        value = self.read(run / 'cierre.json')
        value['updated_at'] = 'foreign modification'
        (run / 'cierre.json').write_text(json.dumps(value), encoding='utf-8')
        before = self.snapshot(run)
        with self.assertRaises(ValueError):
            self.close(run)
        self.assertEqual(before, self.snapshot(run))

    def snapshot(self, run):
        return {str(path.relative_to(run)): path.read_bytes() for path in run.rglob('*') if path.is_file()}

    def test_trace_without_final_result_cannot_pass_complete_gate(self):
        run = self.prepare()
        artifacts.record_event(run, self.write('event.json', dict(kind='check', status='completed', summary='Static check completed')))
        before = self.snapshot(run)
        with self.assertRaises(ValueError):
            artifacts.validate(run, require_complete=True)
        self.assertEqual(before, self.snapshot(run))
        self.assertFalse((run / 'review.json').exists())

    def test_expected_schema_blocks_legacy_emission_without_rewriting_history(self):
        run = self.prepare()
        before = self.snapshot(run)
        with self.assertRaises(ValueError):
            self.retain(run, expected_schema=9)
        self.assertEqual(before, self.snapshot(run))
        self.retain(run)
        self.close(run)
        before = self.snapshot(run)
        self.assertTrue(artifacts.validate(run, require_complete=True)['retained'])
        self.assertEqual(before, self.snapshot(run))

    def test_pending_and_interrupted_runs_are_not_complete(self):
        run = self.prepare()
        with self.assertRaises(ValueError):
            artifacts.validate(run, require_complete=True)
        original = artifacts.atomic_write
        def interrupt(path, data):
            if Path(path).name == 'informe.md':
                raise OSError('interrupted')
            original(path, data)
        with patch.object(artifacts, 'atomic_write', side_effect=interrupt), self.assertRaises(OSError):
            self.retain(run)
        before = self.snapshot(run)
        with self.assertRaises(ValueError):
            artifacts.validate(run, require_complete=True)
        self.assertEqual(before, self.snapshot(run))
        self.retain(run)
        with self.assertRaises(ValueError):
            artifacts.validate(run, require_complete=True)
        self.close(run)
        self.assertEqual(artifacts.validate(run, require_complete=True)['state'], 'complete')

    def test_complete_gate_is_read_only_and_matches_resources(self):
        run = self.prepare()
        self.retain(run)
        self.close(run)
        before = self.snapshot(run)
        artifacts.validate(run, require_complete=True)
        with self.assertRaises(ValueError):
            artifacts.validate(run, require_complete=True, record_checkpoint=True)
        self.assertEqual(before, self.snapshot(run))
        value = self.read(run / 'review.json')
        value['resources']['cleanup'] = 'pending'
        data = artifacts._json_bytes(value)
        artifacts.atomic_write(run / 'review.json', data)
        _, manifest, marker = artifacts._load_run(run)
        manifest['hashes']['review.json'] = artifacts._digest(data)
        artifacts._save_manifest(run, manifest, marker)
        before = self.snapshot(run)
        with self.assertRaises(ValueError):
            artifacts.validate(run, require_complete=True)
        with self.assertRaises(ValueError):
            self.close(run)
        self.assertEqual(before, self.snapshot(run))

    def test_complete_cli_and_expected_schema_cli(self):
        run = self.prepare()
        def invoke(*args):
            return subprocess.run([sys.executable, '-B', str(SCRIPTS / 'review_artifacts.py'), *map(str, args)],
                                  capture_output=True, text=True, encoding='utf-8')
        refused = invoke('retain', '--run-dir', run, '--input', self.final, '--expected-schema', 9)
        self.assertEqual(refused.returncode, 1, refused.stderr)
        self.assertIn('expected schema', json.loads(refused.stderr)['error'])
        self.retain(run)
        before = self.snapshot(run)
        refused = invoke('validate', '--run-dir', run, '--require-complete')
        self.assertEqual(refused.returncode, 1)
        self.assertEqual(before, self.snapshot(run))
        self.close(run)
        result = invoke('validate', '--run-dir', run, '--require-complete')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['state'], 'complete')

    def setUp(self):
        self.assertIsNotNone(artifacts, 'persistent archive helper is missing')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.git('init')
        self.git('config', 'user.email', 'fixtures@example.test')
        self.git('config', 'user.name', 'Fixture')
        (self.repo / 'code.txt').write_text('fixture', encoding='utf-8')
        self.git('add', 'code.txt')
        self.git('commit', '-m', 'fixture')
        self.scope = self.write('scope.json', record()['scope'])
        from recovery_fixtures import record10
        self.final = self.write('final.json', record10())
        self.output = self.root / 'archive'

    def git(self, *args):
        result = subprocess.run(['git', *args], cwd=self.repo, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def write(self, name, value):
        path = self.root / name
        path.write_text(json.dumps(value), encoding='utf-8')
        return path

    def prepare(self, **kwargs):
        from recovery_fixtures import selection_input
        return Path(artifacts.prepare(self.repo, self.scope, skill_version='2.3.0', harness='codex',
                                      profile_input=kwargs.pop('profile_input', selection_input()),
                                      current_inputs={'scope': self.read(self.scope), 'sources': {},
                                                      'source_set_complete': True},
                                      output_root=kwargs.pop('output_root', self.output), **kwargs))

    def read(self, path):
        return json.loads(path.read_text(encoding='utf-8'))

    def retain(self, run, **kwargs):
        from recovery_fixtures import context10, record10
        source_final = self.read(self.final) if Path(self.final).is_file() else record10()
        manifest = self.read(Path(run) / 'cierre.json')
        final = copy.deepcopy(source_final) if source_final.get('schema_version') == 10 else source_final
        context_record = copy.deepcopy(final) if final.get('schema_version') == 10 else record10()
        if context_record.get('schema_version') == 10:
            targets = (final, context_record) if final.get('schema_version') == 10 else (context_record,)
            for target in targets:
                target['scope'] = manifest['scope']
                target['review_id'] = 'CR-' + manifest['run_id']
                target['description'] = {'status': 'unverified' if manifest['scope']['mode'] in ('mr', 'pr')
                                         else 'not_applicable', 'identity': None,
                                         'details': 'Descripción no capturada' if manifest['scope']['mode'] in ('mr', 'pr')
                                         else 'Revisión local'}
                target['profile'] = manifest['profile_history'][-1]['profile']
                target['coverage']['execution']['selection_source'] = manifest['profile_history'][0]['selection_source']
                target['coverage']['execution']['profile_history'] = manifest['profile_history']
                for row in target['coverage']['execution']['plan']:
                    row['selection_id'] = manifest['profile_history'][-1]['id']
        briefs = {row['id']: {'assignment_id': row['id'], 'scope': context_record['scope']}
                  for row in context_record['coverage']['execution']['plan']}
        results = {row['assignment_id']: {'assignment_id': row['assignment_id'], 'status': 'completed'}
                   for row in context_record['coverage']['execution']['results']}
        context = context10(context_record)
        context['review_inputs'] = manifest['review_inputs']
        custom_context = kwargs.pop('context_input', None)
        if custom_context is not None:
            context.update(self.read(Path(custom_context)))
        evidence_inputs = list(kwargs.pop('evidence_inputs', []))
        evidence_inputs.extend([self.write('briefs.json', briefs), self.write('results.json', results)])
        if (kwargs.get('expected_schema') in (None, 10)
                and manifest.get('state') in ('prepared', 'processing')):
            artifacts.register(run, [], context_input=self.write('context-register.json', context))
            for index, (assignment, result) in enumerate(zip(context_record['coverage']['execution']['plan'],
                                                               context_record['coverage']['execution']['results']), 1):
                identity = {'name': result['reviewer_context'], 'provider_id': result['provider_id']}
                role = assignment['role']
                artifacts.record_event(run, self.write(f'event-start-{index}.json', {
                    'kind': 'agent', 'status': 'started', 'summary': 'Synthetic assigned reviewer started',
                    'executor': identity, 'evidence': [assignment['reference']]}))
                artifacts.record_event(run, self.write(f'event-result-{index}.json', {
                    'kind': 'discovery' if role == 'discovery' else 'grouped-verification',
                    'status': 'completed', 'summary': 'Synthetic assignment completed',
                    'actor': {'kind': 'agent', **identity},
                    'evidence': [assignment['reference'], result['reference']]}))
        if 'unavailable_reason' not in kwargs and not kwargs.get('measurement_inputs'):
            kwargs['unavailable_reason'] = 'Provider exposes no counters'
        return artifacts.retain(run, self.write('final-current.json', final),
                                context_input=self.write('context.json', context),
                                evidence_inputs=evidence_inputs,
                                **kwargs)

    def close(self, run, cleanup='not_needed', residuals=None):
        return artifacts.close(run, self.write('cleanup.json', {'cleanup': cleanup, 'residuals': residuals or []}))

    def test_prepare_binds_scope_without_automatic_measurements(self):
        run = self.prepare()
        manifest = self.read(run / 'cierre.json')
        self.assertEqual(manifest['scope'], record()['scope'])
        self.assertEqual(manifest['skill_version'], '2.3.0')
        self.assertEqual(manifest['state'], 'prepared')
        self.assertEqual(manifest['cleanup'], 'pending')
        self.assertFalse((run / 'measurements.json').exists())

    def test_root_priority_and_home_default_are_durable(self):
        with patch.dict(os.environ, {'CCR_ARTIFACTS_DIR': str(self.root / 'env')}), patch.object(Path, 'home', return_value=self.root / 'home'):
            self.assertEqual(artifacts.select_output_root(self.repo, self.output), self.output)
            self.assertEqual(artifacts.select_output_root(self.repo), self.root / 'env')
        environment = {key: value for key, value in os.environ.items() if key != 'CCR_ARTIFACTS_DIR'}
        with patch.dict(os.environ, environment, clear=True), patch.object(Path, 'home', return_value=self.root / 'home'):
            self.assertEqual(artifacts.select_output_root(self.repo), self.root / 'home' / '.comprehensive-code-review' / 'reviews')

    def test_default_root_inside_checkout_is_rejected_but_explicit_root_is_allowed(self):
        with patch.dict(os.environ, {'CCR_ARTIFACTS_DIR': str(self.repo / 'archive')}):
            with self.assertRaises(ValueError):
                artifacts.select_output_root(self.repo)
        self.assertTrue(self.prepare(output_root=self.repo / 'authorized').is_dir())

    def test_worktrees_share_repository_group_with_and_without_origin(self):
        worktree = self.root / 'worktree'
        self.git('worktree', 'add', '--detach', str(worktree), 'HEAD')
        self.assertEqual(artifacts.repository_identity(self.repo), artifacts.repository_identity(worktree))
        self.git('remote', 'add', 'origin', 'https://user:secret@EXAMPLE.test/team/project.git')
        identity = artifacts.repository_identity(self.repo)
        self.assertEqual(identity, artifacts.repository_identity(worktree))
        self.assertNotIn('secret', identity)
        self.git('remote', 'set-url', 'origin', 'git@example.test:team/project.git')
        self.assertEqual(identity, artifacts.repository_identity(self.repo))

    def test_relative_local_origin_preserves_nested_worktree_rereview_group(self):
        remote = self.root / 'remote.git'
        result = subprocess.run(['git', 'init', '--bare', str(remote)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.git('remote', 'add', 'origin', '../remote.git')
        worktree = self.repo / '.worktrees' / 'worker'
        self.git('worktree', 'add', '--detach', str(worktree), 'HEAD')
        self.assertEqual(artifacts.repository_identity(self.repo), artifacts.repository_identity(worktree))
        first = self.prepare()
        from recovery_fixtures import legacy_prepare
        second = legacy_prepare(artifacts, worktree, self.scope, skill_version='2.3.0', harness='codex',
                                output_root=self.output, previous_run=first)
        self.assertEqual(first.parent.parent, second.parent.parent)
        self.assertEqual(self.read(second / 'cierre.json')['previous_run'], str(first))

    def test_retention_keeps_registered_cleanup_pending_before_observed_close(self):
        temporary = self.root / 'temporary-workspace'
        temporary.mkdir()
        from recovery_fixtures import record10
        for claimed in ('complete', 'not_needed'):
            with self.subTest(claimed=claimed):
                value = record10()
                value['resources']['cleanup'] = claimed
                self.final = self.write('final.json', value)
                run = self.prepare(temporary_paths=[temporary])
                self.retain(run)
                saved = self.read(run / 'review.json')
                closure = self.read(run / 'cierre.json')
                self.assertEqual(saved['resources']['cleanup'], 'pending')
                self.assertEqual(saved['resources']['residuals'], [str(temporary)])
                self.assertEqual(closure['residuals'], [str(temporary)])
                self.assertEqual(closure['cleanup'], 'pending')
                self.assertEqual(self.read(self.final), value)
                self.assertEqual(artifacts.review_contract.validate(saved), [])
                self.assertIn(str(temporary).replace('\\', '/'),
                              (run / 'informe.md').read_text(encoding='utf-8').replace('\\', '/'))

    def test_collisions_and_hostile_scope_names_are_bounded_and_distinct(self):
        value = record()['scope']
        value['repository'] = '../CON<>:"/\\?*' + 'x' * 300
        self.scope = self.write('scope.json', value)
        first, second = self.prepare(), self.prepare()
        self.assertNotEqual(first, second)
        self.assertEqual(first.parent, second.parent)
        for component in first.relative_to(self.output).parts:
            self.assertLessEqual(len(component), 80)
            self.assertFalse(any(char in component for char in '<>:"/\\|?*'))

    def test_previous_run_must_be_owned_and_same_repository(self):
        first = self.prepare()
        second = self.prepare(previous_run=first)
        self.assertEqual(self.read(second / 'cierre.json')['previous_run'], str(first))
        self.git('remote', 'add', 'origin', 'https://example.test/other.git')
        with self.assertRaises(ValueError):
            self.prepare(previous_run=first)

    def test_retain_persists_validated_report_hashes_and_close(self):
        run = self.prepare()
        self.retain(run)
        retained = self.read(run / 'review.json')
        self.assertEqual(retained['schema_version'], 10)
        self.assertEqual(retained['scope'], self.read(run / 'cierre.json')['scope'])
        self.assertIn('APROBABLE', (run / 'informe.md').read_text(encoding='utf-8'))
        manifest = self.read(run / 'cierre.json')
        self.assertEqual(manifest['state'], 'closing')
        self.assertEqual(set(manifest['hashes']), {'review.json', 'informe.md', 'measurements.json',
                         'trazabilidad.jsonl', 'evidence/context.json', 'evidence/briefs.json',
                         'evidence/results.json'})
        self.close(run)
        self.assertEqual(self.read(run / 'cierre.json')['state'], 'complete')
        self.assertTrue((run / 'review.json').is_file())

    def test_bad_record_and_mismatched_scope_never_retain(self):
        for mutate in ('invalid', 'scope', 'cleanup'):
            with self.subTest(mutate=mutate):
                run = self.prepare()
                value = record()
                if mutate == 'invalid':
                    value['verdict'] = 'not_approvable'
                elif mutate == 'scope':
                    value['scope']['head'] = 'other'
                else:
                    value['resources'].update(cleanup='complete', residuals=[str(self.root)])
                self.final = self.write('final.json', value)
                with self.assertRaises(ValueError):
                    self.retain(run)
                self.assertFalse((run / 'review.json').exists())

    def test_partial_usage_keeps_raw_identity_subtotals_and_reasons(self):
        measured = {'execution_id': 'one', 'phase': 'verification', 'role': 'verifier',
                    'model': 'example', 'harness': 'codex', 'sessions': 1,
                    'usage': {'input_tokens': 10, 'output_tokens': 2},
                    'unavailable_reason': 'Provider does not expose cache or credits'}
        unknown = {'execution_id': 'two', 'role': 'coordinator', 'usage': None,
                   'unavailable_reason': 'Native usage unavailable'}
        inputs = [self.write('one.json', measured), self.write('two.json', unknown)]
        run = self.prepare()
        self.retain(run, measurement_inputs=inputs)
        usage = self.read(run / 'measurements.json')
        self.assertEqual(usage['status'], 'partial')
        self.assertEqual(usage['runs'], [measured, unknown])
        self.assertEqual(usage['summary']['total_tokens']['known_subtotal'], 12)
        self.assertEqual(usage['summary']['total_tokens']['unknown_runs'], 1)

    def test_unknown_usage_requires_a_reason_and_measured_zero_is_reported(self):
        run = self.prepare()
        unknown = self.write('unknown.json', {'usage': None})
        with self.assertRaises(ValueError):
            self.retain(run, measurement_inputs=[unknown])
        usage = {key: 0 for key in ('input_tokens', 'output_tokens', 'cached_input_tokens', 'reasoning_tokens', 'credits', 'cost')}
        usage['currency'] = 'USD'
        counters = {key: 0 for key in ('sessions', 'tool_calls', 'repeated_reads', 'tool_output_chars')}
        path = self.write('zero.json', dict(counters, execution_id='zero', usage=usage))
        self.retain(run, measurement_inputs=[path])
        self.assertEqual(self.read(run / 'measurements.json')['status'], 'reported')

    def test_duplicate_paths_and_execution_ids_are_rejected(self):
        one = self.write('one.json', {'execution_id': 'same', 'usage': None})
        two = self.write('two.json', {'execution_id': 'same', 'usage': None})
        for paths in ([one, one], [one, two]):
            with self.subTest(paths=paths), self.assertRaises(ValueError):
                self.retain(self.prepare(), measurement_inputs=paths)

    def test_close_before_retain_and_missing_evidence_cannot_claim_complete(self):
        run = self.prepare()
        with self.assertRaises(ValueError):
            self.close(run)
        self.assertEqual(self.read(run / 'cierre.json')['cleanup'], 'pending')
        self.retain(run)
        (run / 'informe.md').unlink()
        with self.assertRaises(ValueError):
            self.close(run)

    def test_observed_pending_cleanup_synchronizes_review_and_preserves_residual(self):
        run = self.prepare()
        self.retain(run)
        residual = self.root / 'temporary-checkout'
        residual.mkdir()
        self.retain(run, unavailable_reason='Native counters unavailable', temporary_paths=[residual])
        self.close(run, 'pending', [str(residual)])
        manifest = self.read(run / 'cierre.json')
        self.assertEqual(manifest['state'], 'closing')
        self.assertEqual(manifest['residuals'], [str(residual)])
        self.assertEqual(self.read(run / 'review.json')['resources']['cleanup'], 'pending')
        self.assertTrue(residual.exists())
        residual.rmdir()
        self.close(run, 'complete')
        self.assertEqual(self.read(run / 'review.json')['resources']['cleanup'], 'complete')
        self.assertEqual(self.read(run / 'cierre.json')['state'], 'complete')

    def test_registered_resources_must_be_observed_exactly_and_not_deleted(self):
        temporary = self.root / 'temporary-workspace'
        temporary.mkdir()
        run = self.prepare(temporary_paths=[temporary])
        self.retain(run)
        for cleanup, residuals in [('complete', []), ('not_needed', []), ('pending', []),
                                   ('pending', [str(self.repo)])]:
            with self.subTest(cleanup=cleanup, residuals=residuals), self.assertRaises(ValueError):
                self.close(run, cleanup, residuals)
        self.assertTrue(temporary.is_dir())
        self.close(run, 'pending', [str(temporary)])
        temporary.rmdir()
        self.close(run, 'complete')

    def test_user_checkout_and_archive_cannot_be_registered_as_temporary(self):
        for target in (self.repo, self.repo / 'code.txt', self.output):
            with self.subTest(target=target), self.assertRaises(ValueError):
                self.prepare(temporary_paths=[target])

    def test_repository_subdirectory_does_not_hide_checkout_ownership(self):
        subdirectory = self.repo / 'source'
        subdirectory.mkdir()
        with self.assertRaises(ValueError):
            from recovery_fixtures import legacy_prepare
            legacy_prepare(artifacts, subdirectory, self.scope, skill_version='2.3.0', harness='codex',
                           output_root=self.output, temporary_paths=[self.repo / 'code.txt'])

    def test_interrupted_manifest_marker_transition_can_be_retried(self):
        run = self.prepare()
        original = artifacts.atomic_write
        calls = 0
        def interrupt(path, data):
            nonlocal calls
            if Path(path).name == artifacts.MARKER:
                calls += 1
                if calls == 2:
                    raise OSError('interrupted final marker write')
            original(path, data)
        with patch.object(artifacts, 'atomic_write', side_effect=interrupt), self.assertRaises(OSError):
            self.retain(run)
        self.retain(run)
        self.close(run)
        self.assertEqual(self.read(run / 'cierre.json')['state'], 'complete')

    def test_inaccessible_registered_resource_blocks_successful_close(self):
        temporary = self.root / 'temporary-workspace'
        temporary.mkdir()
        run = self.prepare(temporary_paths=[temporary])
        self.retain(run)
        original = Path.stat
        def denied(path, *args, **kwargs):
            if path == temporary:
                raise PermissionError('cannot observe registered resource')
            return original(path, *args, **kwargs)
        with patch.object(Path, 'stat', denied), self.assertRaises(PermissionError):
            self.close(run, 'complete')
        self.assertEqual(self.read(run / 'cierre.json')['cleanup'], 'pending')

    def test_schema_two_records_are_not_adopted_by_new_archive(self):
        value = record()
        value['schema_version'] = 2
        value['coverage']['areas'] = [{'area': area, 'status': 'not_applicable',
                                      'details': 'Outside bounded scope', 'material': False,
                                      'finding_ids': []} for area in 'ABCDE']
        self.final = self.write('final.json', value)
        run = self.prepare()
        with self.assertRaises(ValueError):
            self.retain(run)
        self.assertFalse((run / 'review.json').exists())

    def test_windows_junction_root_is_refused(self):
        if os.name != 'nt':
            self.skipTest('Windows junction test')
        link = self.root / 'junction'
        result = subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(self.repo)],
                                capture_output=True, text=True)
        if result.returncode:
            self.skipTest('Host does not permit junctions: ' + result.stderr)
        with self.assertRaises(ValueError):
            self.prepare(output_root=link / 'archive')

    def test_nested_review_owned_git_session_retains_original_manifest_location(self):
        session = self.repo / '.worktrees' / 'code-review-owned'
        session.mkdir(parents=True)
        workspace = session / 'functional'
        self.git('worktree', 'add', '--detach', str(workspace), 'HEAD')
        original_manifest = session / 'manifest.json'
        original_manifest.write_text('{"private":"do not copy this"}', encoding='utf-8')
        run = self.prepare(temporary_paths=[session])
        self.retain(run)
        manifest = self.read(run / 'cierre.json')
        self.assertEqual(manifest['temporary_manifests'], [str(original_manifest)])
        self.assertNotIn('do not copy this', (run / 'cierre.json').read_text(encoding='utf-8'))
        self.close(run, 'pending', [str(session)])
        self.git('worktree', 'remove', str(workspace))
        original_manifest.unlink()
        session.rmdir()
        self.close(run, 'complete')
        self.assertEqual(self.read(run / 'cierre.json')['temporary_manifests'], [str(original_manifest)])

    def test_readable_repository_and_scope_reference_names(self):
        self.git('remote', 'add', 'origin', 'https://example.test/team/service.git')
        value = record()['scope']
        value.update(mode='pr', reference='https://example.test/team/service/pull/128')
        self.scope = self.write('scope.json', value)
        run = self.prepare()
        self.assertIn('service', run.parent.parent.name)
        self.assertIn('128', run.parent.name)

    def test_git_structural_environment_cannot_change_grouping(self):
        original = artifacts.repository_identity(self.repo)
        with patch.dict(os.environ, {'GIT_DIR': str(self.root / 'foreign-git'),
                                     'GIT_WORK_TREE': str(self.root / 'foreign-worktree'),
                                     'GIT_CONFIG_COUNT': '1', 'GIT_CONFIG_KEY_0': 'remote.origin.url',
                                     'GIT_CONFIG_VALUE_0': 'https://foreign.test/wrong.git'}):
            self.assertEqual(artifacts.repository_identity(self.repo), original)
            self.assertTrue(self.prepare().exists())

    def test_global_root_rejects_the_main_checkout_when_repo_is_temporary_worktree(self):
        workspace = self.root / 'worker'
        self.git('worktree', 'add', '--detach', str(workspace), 'HEAD')
        with patch.dict(os.environ, {'CCR_ARTIFACTS_DIR': str(self.repo / 'global')}):
            with self.assertRaises(ValueError):
                artifacts.select_output_root(workspace)

    def test_measurement_projection_excludes_context_argv_and_credentials(self):
        raw = {'execution_id': 'one', 'phase': 'verification', 'role': 'worker', 'usage': None,
               'workspace': str(self.repo), 'elapsed_seconds': 1.5, 'stdout_bytes': 42,
               'usage_status': 'unavailable', 'unavailable_reason': 'Native counters unavailable',
               'argv': ['tool', 'secret'], 'context': 'private history', 'credentials': 'secret'}
        run = self.prepare()
        self.retain(run, measurement_inputs=[self.write('measurement.json', raw)])
        saved = self.read(run / 'measurements.json')['runs'][0]
        self.assertEqual(saved['elapsed_seconds'], 1.5)
        self.assertEqual(saved['stdout_bytes'], 42)
        self.assertFalse(set(saved) & {'argv', 'context', 'credentials'})

    def test_unexpected_usage_fields_are_rejected(self):
        path = self.write('measurement.json', {'usage': {'private_tokens': 3}})
        with self.assertRaises(ValueError):
            self.retain(self.prepare(), measurement_inputs=[path])

    def test_selected_evidence_survives_source_removal_and_has_verified_hashes(self):
        source = self.root / 'reproduction.py'
        source.write_text('assert 1 + 1 == 2\n', encoding='utf-8')
        run = self.prepare()
        self.retain(run, evidence_inputs=[source])
        source.unlink()
        evidence = run / 'evidence' / 'reproduction.py'
        self.assertEqual(evidence.read_text(encoding='utf-8'), 'assert 1 + 1 == 2\n')
        self.assertIn('evidence/reproduction.py', self.read(run / 'cierre.json')['hashes'])
        self.close(run)
        self.assertTrue(evidence.is_file())

    def test_missing_modified_duplicate_and_foreign_evidence_block_retention_or_close(self):
        source = self.root / 'reproduction.py'
        source.write_text('evidence', encoding='utf-8')
        for mutation in ('missing', 'modified'):
            run = self.prepare()
            self.retain(run, evidence_inputs=[source])
            evidence = run / 'evidence' / source.name
            if mutation == 'missing':
                evidence.unlink()
            else:
                evidence.write_text('user edit', encoding='utf-8')
            with self.assertRaises(ValueError):
                self.close(run)
        other = self.root / 'other'
        other.mkdir()
        duplicate = other / source.name
        duplicate.write_text('other', encoding='utf-8')
        with self.assertRaises(ValueError):
            self.retain(self.prepare(), evidence_inputs=[source, duplicate])
        run = self.prepare()
        (run / 'evidence').mkdir()
        (run / 'evidence' / source.name).write_text('user file', encoding='utf-8')
        with self.assertRaises(ValueError):
            self.retain(run, evidence_inputs=[source])

    def test_interrupted_evidence_retention_cannot_close_and_can_retry(self):
        source = self.root / 'reproduction.py'
        source.write_text('evidence', encoding='utf-8')
        run = self.prepare()
        original = artifacts.atomic_write
        def interrupt(path, data):
            if Path(path).parent.name == 'evidence':
                raise OSError('interrupted evidence copy')
            original(path, data)
        with patch.object(artifacts, 'atomic_write', side_effect=interrupt), self.assertRaises(OSError):
            self.retain(run, evidence_inputs=[source])
        with self.assertRaises(ValueError):
            self.close(run)
        with self.assertRaises(ValueError):
            self.retain(run)
        self.retain(run, evidence_inputs=[source])
        self.close(run)

    def test_completed_run_is_immutable_and_previous_run_preserves_bytes(self):
        run = self.prepare()
        self.retain(run)
        self.close(run)
        before = {path.name: path.read_bytes() for path in run.iterdir() if path.is_file()}
        with self.assertRaises(ValueError):
            self.retain(run)
        self.close(run)
        with self.assertRaises(ValueError):
            self.close(run, 'complete')
        self.prepare(previous_run=run)
        after = {path.name: path.read_bytes() for path in run.iterdir() if path.is_file()}
        self.assertEqual(before, after)
        self.assertTrue(self.read(run / 'cierre.json')['closed_at'])
        self.assertTrue(self.read(run / 'cierre.json')['updated_at'])

    def test_cleanup_must_be_concrete_absolute_and_consistent(self):
        for cleanup in ({'cleanup': 'complete', 'residuals': [str(self.root)]},
                        {'cleanup': 'pending', 'residuals': ['../escape']},
                        {'cleanup': 'maybe', 'residuals': []},
                        {'cleanup': 'not_needed', 'residuals': [], 'scope': {}}):
            run = self.prepare()
            self.retain(run)
            with self.subTest(cleanup=cleanup), self.assertRaises(ValueError):
                artifacts.close(run, self.write('cleanup.json', cleanup))

    def test_clobber_foreign_runs_and_manifest_scope_tampering_are_refused(self):
        for filename in ('review.json', 'informe.md', 'measurements.json'):
            run = self.prepare()
            self.retain(run)
            (run / filename).write_text('user edits', encoding='utf-8')
            with self.assertRaises(ValueError):
                self.close(run)
            with self.assertRaises(ValueError):
                self.retain(run)
        foreign = self.root / 'foreign'
        foreign.mkdir()
        with self.assertRaises(ValueError):
            self.close(foreign)
        run = self.prepare()
        manifest = self.read(run / 'cierre.json')
        manifest['scope']['head'] = 'other'
        (run / 'cierre.json').write_text(json.dumps(manifest), encoding='utf-8')
        with self.assertRaises(ValueError):
            self.retain(run)

    def test_symlink_roots_inputs_and_archived_files_are_refused(self):
        link = self.root / 'link'
        try:
            link.symlink_to(self.repo, target_is_directory=True)
        except OSError as exc:
            self.skipTest('Host does not permit symlinks: ' + str(exc))
        with self.assertRaises(ValueError):
            self.prepare(output_root=link / 'archive')
        run = self.prepare()
        self.retain(run)
        (run / 'informe.md').unlink()
        (run / 'informe.md').symlink_to(self.final)
        with self.assertRaises(ValueError):
            self.close(run)

    def test_blocked_root_has_no_fallback_and_traversal_is_rejected(self):
        blocked = self.root / 'blocked'
        blocked.write_text('occupied', encoding='utf-8')
        with self.assertRaises((ValueError, OSError)):
            self.prepare(output_root=blocked)
        with self.assertRaises(ValueError):
            self.prepare(output_root=self.root / 'archive' / '..' / 'escape')

    def test_interrupted_retention_stays_pending_and_cannot_close(self):
        run = self.prepare()
        original = artifacts.atomic_write
        def interrupt(path, data):
            if Path(path).name == 'informe.md':
                raise OSError('interrupted')
            original(path, data)
        with patch.object(artifacts, 'atomic_write', side_effect=interrupt), self.assertRaises(OSError):
            self.retain(run)
        self.assertEqual(self.read(run / 'cierre.json')['cleanup'], 'pending')
        with self.assertRaises(ValueError):
            self.close(run)
        self.retain(run)
        self.close(run)

    def test_cli_prepare_retain_close_and_invalid_input_are_json(self):
        from recovery_fixtures import selection_input
        def invoke(*args):
            return subprocess.run([sys.executable, '-B', str(SCRIPTS / 'review_artifacts.py'), *map(str, args)],
                                  capture_output=True, text=True, encoding='utf-8')
        profile = self.write('profile.json', selection_input())
        result = invoke('prepare', '--repo', self.repo, '--scope-file', self.scope,
                        '--skill-version', '2.12.0', '--harness', 'codex', '--output-root', self.output,
                        '--profile-input', profile)
        self.assertEqual(result.returncode, 0, result.stderr)
        run = Path(json.loads(result.stdout)['run_dir'])
        self.assertEqual(self.read(run / 'cierre.json')['schema_version'], 8)
        legacy = record()
        legacy['schema_version'] = 9
        legacy_input = self.write('legacy-final.json', legacy)
        result = invoke('retain', '--run-dir', run, '--input', legacy_input,
                        '--unavailable-reason', 'Native counters unavailable')
        self.assertEqual(result.returncode, 1)
        self.assertIn('archive 8 requires final review schema 10', json.loads(result.stderr)['error'])
        result = invoke('retain', '--run-dir', self.root, '--input', self.final)
        self.assertEqual(result.returncode, 1)
        self.assertIn('error', json.loads(result.stderr))


class Archive7Tests(unittest.TestCase):
    setUp = ArchiveTests.setUp
    git = ArchiveTests.git
    write = ArchiveTests.write
    read = ArchiveTests.read
    snapshot = ArchiveTests.snapshot

    def profile_input(self, profile='focused', source='automatic', **updates):
        from recovery_fixtures import selection_input
        value = selection_input(profile, source, reference='evidence/context.json#profile')
        value.update(updates)
        return value

    def prepare7(self, profile='focused', source='automatic'):
        return Path(artifacts.prepare(self.repo, self.scope, '2.12.0', 'codex', output_root=self.output,
                                      profile_input=self.profile_input(profile, source)))

    def events(self, run):
        return [json.loads(line) for line in (run / 'trazabilidad.jsonl').read_text(encoding='utf-8').splitlines()]

    def test_prepare_requires_selection_before_directory_creation(self):
        with self.assertRaisesRegex(ValueError, 'profile selection'):
            artifacts.prepare(self.repo, self.scope, '2.12.0', 'codex', output_root=self.output)
        self.assertFalse(self.output.exists())

    def test_prepare_records_selection_atomically(self):
        run = self.prepare7('deep')
        manifest = self.read(run / 'cierre.json')
        history = manifest['profile_history']
        self.assertEqual(history[0]['id'], 'S001')
        self.assertEqual(history[0]['profile'], 'deep')
        self.assertEqual([event['kind'] for event in self.events(run)][:2], ['prepare', 'profile'])
        self.assertEqual(self.events(run)[1]['event_id'], history[0]['event_id'])

    def test_prepare_crash_boundaries_keep_the_selection_and_event_pair(self):
        import re
        original = artifacts.atomic_write
        boundaries = [(artifacts.MARKER, 1, 'before'), (artifacts.MARKER, 1, 'after'),
                      ('cierre.json', 1, 'before'), ('cierre.json', 1, 'after'),
                      (artifacts.MARKER, 2, 'before'), (artifacts.MARKER, 2, 'after'),
                      ('trazabilidad.jsonl', 1, 'before'), ('trazabilidad.jsonl', 1, 'after')]
        for filename, target_write, timing in boundaries:
            with self.subTest(filename=filename, write=target_write, timing=timing):
                self.output = self.root / ('archive-' + filename.replace('.', '-') + str(target_write) + timing)
                profile = self.profile_input()
                writes = 0

                def interrupt(path, data):
                    nonlocal writes
                    if Path(path).name == filename:
                        writes += 1
                        if writes == target_write:
                            if timing == 'after':
                                original(path, data)
                            raise OSError('injected prepare boundary')
                    original(path, data)

                unrecoverable = ((filename == artifacts.MARKER and target_write == 1)
                                 or (filename == 'cierre.json' and timing == 'before'))
                with patch.object(artifacts, 'atomic_write', side_effect=interrupt):
                    if unrecoverable:
                        with self.assertRaises(OSError):
                            artifacts.prepare(self.repo, self.scope, '2.12.0', 'codex',
                                              output_root=self.output, profile_input=profile)
                        self.assertFalse(any(re.fullmatch(r'[0-9]{8}T[0-9]{6}Z--[A-Za-z0-9_-]{1,36}--[0-9a-f]{20}', path.name)
                                             for path in self.output.rglob('*') if path.is_dir()))
                        continue
                    result = artifacts.prepare(self.repo, self.scope, '2.12.0', 'codex',
                                               output_root=self.output, profile_input=profile)
                run = Path(result)
                manifest = self.read(run / 'cierre.json')
                events = self.events(run)
                self.assertEqual([event['kind'] for event in events], ['prepare', 'profile'])
                self.assertEqual(manifest['profile_history'][0]['event_id'], events[1]['event_id'])

    def test_select_profile_idempotent_retry(self):
        run = self.prepare7()
        selected_input = self.profile_input('deep', 'automatic', phase='discovery',
            reference='evidence/context.json#profile_history/1/profile', changed_from='focused',
            affected_assignments=['D1', 'D2'])
        selected = artifacts.select_profile(run, selected_input)
        snapshot = self.snapshot(run)
        replay = artifacts.select_profile(run, selected_input)
        self.assertEqual(replay['profile_history'], selected['profile_history'])
        self.assertEqual(len(replay['profile_history']), 2)
        self.assertEqual(self.snapshot(run), snapshot)

    def test_work_start_without_profile_is_refused_without_changes(self):
        run = self.prepare7()
        manifest = self.read(run / 'cierre.json')
        marker = self.read(run / artifacts.MARKER)
        manifest['profile_history'] = []
        artifacts._save_manifest(run, manifest, marker)
        before = self.snapshot(run)
        with self.assertRaisesRegex(ValueError, 'profile selection'):
            artifacts.record_event(run, self.write('start.json',
                dict(kind='discovery', status='started', summary='Synthetic work start')))
        self.assertEqual(self.snapshot(run), before)

    def test_paused_operation_cannot_start_work(self):
        run = self.prepare7()
        manifest = self.read(run / 'cierre.json')
        marker = self.read(run / artifacts.MARKER)
        manifest['operation'].update(disposition='paused', reason='Synthetic user stop', source='fixture')
        artifacts._save_manifest(run, manifest, marker)
        before = self.snapshot(run)
        with self.assertRaisesRegex(ValueError, 'paused'):
            artifacts.record_event(run, self.write('start.json',
                dict(kind='discovery', status='started', summary='Synthetic work start')))
        self.assertEqual(self.snapshot(run), before)

    def test_register_executor_survives_retention_failure(self):
        from recovery_fixtures import record10
        run = self.prepare7()
        workspace = self.root / 'authorized-copy'
        workspace.mkdir()
        manifest = self.read(run / 'cierre.json')
        history = manifest['profile_history']
        final = record10('focused', 'automatic')
        final['scope'] = record()['scope']
        final['review_id'] = 'CR-' + manifest['run_id']
        context = {'profile': 'focused', 'selection_source': 'automatic',
                   'profile_reference': history[0]['reference'], 'profile_history': history,
                   'execution_plan': copy.deepcopy(final['coverage']['execution']['plan']),
                   'review_inputs': manifest['review_inputs'],
                   'executors': [{'executor': 'X1', 'method': 'authorized-copy', 'workspace': str(workspace),
                       'revision': final['scope']['head'], 'snapshot': None, 'manifest': None,
                       'dependencies': 'none', 'dependency_reason': 'Synthetic isolated fixture',
                       'authorization': 'User authorized the synthetic test copy'}]}
        context_file = self.write('context.json', context)
        artifacts.register(run, [workspace], context_input=context_file)
        with self.assertRaises(ValueError):
            artifacts.retain(run, self.write('final.json', final), context_input=context_file)
        retained_manifest = self.read(run / 'cierre.json')
        self.assertEqual([row['executor'] for row in retained_manifest['executors']], ['X1'])

    def test_register_requires_context_even_for_static_execution(self):
        run = self.prepare7()
        before = self.snapshot(run)
        with self.assertRaisesRegex(ValueError, 'requires captured context'):
            artifacts.register(run, [])
        self.assertEqual(self.snapshot(run), before)
        history = self.read(run / 'cierre.json')['profile_history']
        context = {'profile': 'focused', 'selection_source': 'automatic',
                   'profile_reference': history[0]['reference'], 'profile_history': history,
                   'executors': [], 'review_inputs': self.read(run / 'cierre.json')['review_inputs']}
        with self.assertRaisesRegex(ValueError, 'execution_plan'):
            artifacts.register(run, [], context_input=self.write('missing-plan.json', context))
        self.assertEqual(self.snapshot(run), before)
        context['execution_plan'] = []
        manifest = artifacts.register(run, [], context_input=self.write('static-context.json', context))
        self.assertEqual(manifest['executors'], [])
        self.assertEqual(manifest['assignment_registry'], [])
        before = self.snapshot(run)
        with self.assertRaisesRegex(ValueError, 'brief captured in the execution plan'):
            artifacts.record_event(run, self.write('unknown-start.json', {
                'kind': 'discovery', 'status': 'started', 'summary': 'Unknown assignment start',
                'evidence': ['evidence/briefs.json#D1']}))
        self.assertEqual(self.snapshot(run), before)

    def test_register_captures_plan_and_retention_rejects_omitted_started_assignment(self):
        from recovery_fixtures import record10

        run = self.prepare7('deep')
        manifest = self.read(run / 'cierre.json')
        history = manifest['profile_history']
        final = record10('deep', 'automatic')
        final['scope'] = manifest['scope']
        final['description'] = record()['description']
        final['review_id'] = 'CR-' + manifest['run_id']
        final['coverage']['execution']['profile_history'] = history
        plan = copy.deepcopy(final['coverage']['execution']['plan'])
        context = {'profile': 'deep', 'selection_source': 'automatic',
                   'profile_reference': history[-1]['reference'], 'profile_history': history,
                   'execution_plan': plan, 'executors': []}
        context['review_inputs'] = manifest['review_inputs']
        context_file = self.write('context.json', context)
        registered = artifacts.register(run, [], context_input=context_file)
        self.assertEqual(registered['assignment_registry'], plan)

        artifacts.record_event(run, self.write('assignment-start.json', {
            'kind': 'discovery', 'status': 'started', 'summary': 'D1 started',
            'evidence': [plan[0]['reference']]}))

        execution = final['coverage']['execution']
        omitted = plan[0]
        extra = dict(plan[1], id='D3', reference='evidence/briefs.json#D3')
        execution['plan'] = [plan[1], extra, plan[2]]
        old_results = {row['assignment_id']: row for row in execution['results']}
        extra_result = dict(old_results['D1'], assignment_id='D3', reference='evidence/results.json#D3')
        execution['results'] = [old_results['D2'], extra_result, old_results['V1']]
        briefs = self.write('briefs.json', {'D1': {}, 'D2': {}, 'D3': {}, 'V1': {}})
        results = self.write('results.json', {'D2': {}, 'D3': {}, 'V1': {}})
        with self.assertRaisesRegex(ValueError, 'started/completed assignment.*D1'):
            artifacts.retain(run, self.write('review.json', final), context_input=context_file,
                             evidence_inputs=[briefs, results])


if __name__ == '__main__':
    unittest.main()
