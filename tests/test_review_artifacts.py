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
        self.final = self.write('final.json', record())
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
        return Path(artifacts.prepare(self.repo, self.scope, '2.3.0', 'codex',
                                     output_root=kwargs.pop('output_root', self.output), **kwargs))

    def read(self, path):
        return json.loads(path.read_text(encoding='utf-8'))

    def retain(self, run, **kwargs):
        return artifacts.retain(run, self.final, unavailable_reason='Provider exposes no counters', **kwargs)

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
        second = Path(artifacts.prepare(worktree, self.scope, '2.3.0', 'codex',
                                      output_root=self.output, previous_run=first))
        self.assertEqual(first.parent.parent, second.parent.parent)
        self.assertEqual(self.read(second / 'cierre.json')['previous_run'], str(first))

    def test_retention_keeps_registered_cleanup_pending_before_observed_close(self):
        temporary = self.root / 'temporary-workspace'
        temporary.mkdir()
        for claimed in ('complete', 'not_needed'):
            with self.subTest(claimed=claimed):
                value = record()
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
        self.assertEqual(self.read(run / 'review.json'), record())
        self.assertIn('APROBABLE', (run / 'informe.md').read_text(encoding='utf-8'))
        manifest = self.read(run / 'cierre.json')
        self.assertEqual(manifest['state'], 'closing')
        self.assertEqual(set(manifest['hashes']), {'review.json', 'informe.md', 'measurements.json'})
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
        artifacts.retain(run, self.final, measurement_inputs=inputs)
        usage = self.read(run / 'measurements.json')
        self.assertEqual(usage['status'], 'partial')
        self.assertEqual(usage['runs'], [measured, unknown])
        self.assertEqual(usage['summary']['total_tokens']['known_subtotal'], 12)
        self.assertEqual(usage['summary']['total_tokens']['unknown_runs'], 1)

    def test_unknown_usage_requires_a_reason_and_measured_zero_is_reported(self):
        run = self.prepare()
        unknown = self.write('unknown.json', {'usage': None})
        with self.assertRaises(ValueError):
            artifacts.retain(run, self.final, measurement_inputs=[unknown])
        usage = {key: 0 for key in ('input_tokens', 'output_tokens', 'cached_input_tokens', 'reasoning_tokens', 'credits', 'cost')}
        usage['currency'] = 'USD'
        counters = {key: 0 for key in ('sessions', 'tool_calls', 'repeated_reads', 'tool_output_chars')}
        path = self.write('zero.json', dict(counters, execution_id='zero', usage=usage))
        artifacts.retain(run, self.final, measurement_inputs=[path])
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
        artifacts.retain(run, self.final, unavailable_reason='Native counters unavailable', temporary_paths=[residual])
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
            artifacts.prepare(subdirectory, self.scope, '2.3.0', 'codex',
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

    def test_schema_two_records_are_retained_through_canonical_contract(self):
        value = record()
        value['schema_version'] = 2
        value['coverage']['areas'] = [{'area': area, 'status': 'not_applicable',
                                      'details': 'Outside bounded scope', 'material': False,
                                      'finding_ids': []} for area in 'ABCDE']
        self.final = self.write('final.json', value)
        run = self.prepare()
        self.retain(run)
        self.assertEqual(self.read(run / 'review.json'), value)

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
        def invoke(*args):
            return subprocess.run([sys.executable, '-B', str(SCRIPTS / 'review_artifacts.py'), *map(str, args)],
                                  capture_output=True, text=True, encoding='utf-8')
        result = invoke('prepare', '--repo', self.repo, '--scope-file', self.scope,
                        '--skill-version', '2.3.0', '--harness', 'codex', '--output-root', self.output)
        self.assertEqual(result.returncode, 0, result.stderr)
        run = Path(json.loads(result.stdout)['run_dir'])
        result = invoke('retain', '--run-dir', run, '--input', self.final,
                        '--unavailable-reason', 'Native counters unavailable')
        self.assertEqual(result.returncode, 0, result.stderr)
        cleanup = self.write('cleanup.json', {'cleanup': 'not_needed', 'residuals': []})
        result = invoke('close', '--run-dir', run, '--cleanup-file', cleanup)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['state'], 'complete')
        result = invoke('retain', '--run-dir', self.root, '--input', self.final)
        self.assertEqual(result.returncode, 1)
        self.assertIn('error', json.loads(result.stderr))


if __name__ == '__main__':
    unittest.main()
