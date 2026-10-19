"""Archive 8 creation and refusal boundaries."""
import json
import base64
from pathlib import Path
import unittest

import test_review_artifacts as archive_tests
from recovery_fixtures import context10, record10, selection_input, historical_prepare
import review_recovery
import review_inputs


artifacts = archive_tests.artifacts


class Archive8Tests(unittest.TestCase):
    setUp = archive_tests.ArchiveTests.setUp
    git = archive_tests.ArchiveTests.git
    write = archive_tests.ArchiveTests.write
    read = archive_tests.ArchiveTests.read
    snapshot = archive_tests.ArchiveTests.snapshot

    def prepare_scope(self, scope, selector=None):
        scope_file = self.write('scope-' + str(len(list(self.root.glob('scope-*.json'))) + 1) + '.json', scope)
        return Path(artifacts.prepare(self.repo, scope_file, '2.13.0', 'codex', output_root=self.output,
                                      profile_input=selection_input(), logical_scope_input=selector))

    def test_same_mr_versions_are_grouped_and_each_run_shows_its_head(self):
        scope = {'repository': 'example/service', 'mode': 'mr', 'base': 'base-one',
                 'head': '90e54abb1234567890abcdef', 'snapshot': None, 'target': 'develop',
                 'reference': 'https://git.example/acme/api/merge_requests/1010'}
        first = self.prepare_scope(scope)
        changed = dict(scope, base='base-two', head='fedcba9876543210fedcba98')
        second = self.prepare_scope(changed)
        self.assertEqual(first.parent.name, 'mr-1010')
        self.assertEqual(second.parent, first.parent)
        self.assertIn('--head-90e54abb1234--', first.name)
        self.assertIn('--head-fedcba987654--', second.name)
        self.assertNotEqual(first, second)

    def test_module_boundary_change_creates_a_distinct_group(self):
        scope = {'repository': 'example/service', 'mode': 'module', 'base': 'base-one',
                 'head': '90e54abb1234567890abcdef', 'snapshot': None, 'target': None,
                 'reference': 'feature/refactor'}
        first = self.prepare_scope(scope, {'mode': 'module', 'selector': {'reference': 'feature/refactor', 'boundaries': ['src/a']}})
        second = self.prepare_scope(scope, {'mode': 'module', 'selector': {'reference': 'feature/refactor', 'boundaries': ['src/b']}})
        self.assertNotEqual(first.parent, second.parent)

    def test_uncaptured_inputs_can_be_captured_before_work_without_inventing_sources(self):
        run = self.prepare_scope(self.read(self.scope))
        manifest = self.read(run / 'cierre.json')
        self.assertIsNone(manifest['review_inputs'])
        final = record10()
        final['scope'] = manifest['scope']
        final['coverage']['execution']['profile_history'] = manifest['profile_history']
        context = context10(final)
        context['profile_reference'] = manifest['profile_history'][-1]['reference']
        registered = artifacts.register(run, [], context_input=self.write('captured.json', context))
        self.assertEqual(registered['review_inputs'], context['review_inputs'])
        self.assertEqual(registered['review_inputs']['logical_scope_identity'],
                         manifest['logical_scope']['identity'])

    def test_supplied_logical_identity_cannot_be_silently_replaced(self):
        with self.assertRaisesRegex(ValueError, 'logical scope'):
            artifacts.prepare(self.repo, self.scope, '2.12.1', 'codex', output_root=self.output,
                profile_input=selection_input(), current_inputs={
                    'scope': self.read(self.scope), 'sources': {},
                    'logical_scope_identity': '0' * 64})
        self.assertFalse(self.output.exists())

    def test_old_layout_is_rejected_without_changing_any_source_bytes(self):
        run = historical_prepare(artifacts, self.repo, self.scope, output_root=self.output)
        before = self.snapshot(run)
        with self.assertRaisesRegex(ValueError, 'unsupported_layout'):
            artifacts.validate(run)
        with self.assertRaisesRegex(ValueError, 'unsupported_layout'):
            artifacts.retain(run, self.final)
        self.assertEqual(before, self.snapshot(run))

    def test_lookup_reports_old_layout_without_trying_to_recover_it(self):
        run = historical_prepare(artifacts, self.repo, self.scope, output_root=self.output)
        before = self.snapshot(run)
        result = review_recovery.find_candidates(self.repo, self.read(self.scope), archive_root=self.output)
        repo_group = artifacts._repository_group(artifacts.repository_identity(self.repo))
        self.assertTrue(any(row['run_dir'] == str(run) for row in result['candidates']),
                        {'result': result, 'repo_group': repo_group, 'run': str(run),
                         'groups': [p.name for p in (self.output / repo_group).iterdir()],
                         'legacy_prefix': review_recovery._legacy_scope_prefix(self.read(self.scope))})
        candidate = next(row for row in result['candidates'] if row['run_dir'] == str(run))
        self.assertEqual(candidate['kind'], 'historical_source')
        self.assertEqual(candidate['status'], 'unsupported_layout')
        self.assertIn('port_history', {row['action'] for row in candidate['actions']})
        diagnostic = review_recovery.inspect_run(run)
        self.assertEqual(diagnostic['integrity']['status'], 'unsupported_layout')
        self.assertEqual(before, self.snapshot(run))

    def test_lookup_cursor_v1_is_rejected_and_logical_identity_compares_as_known(self):
        raw = json.dumps({'v': 1, 'repository_group': 'repo-01234567890123456789',
                          'scope_sha256': 'a' * 64, 'group': 'mr-1010',
                          'run': '20261018T150000-0123456789abcdefabcd'}, sort_keys=True).encode()
        cursor = base64.urlsafe_b64encode(raw).decode().rstrip('=')
        with self.assertRaisesRegex(ValueError, 'unsupported shape'):
            review_recovery._cursor_decode(cursor, 'repo-01234567890123456789', 'a' * 64, 'mr-1010')
        scope = self.read(self.scope)
        base = {'scope': scope, 'sources': {}, 'source_set_complete': True,
                'logical_scope_identity': 'a' * 64}
        changed = dict(base, logical_scope_identity='b' * 64)
        self.assertEqual(review_inputs.compare_inputs(base, changed)['applicability'], 'changed')
        missing = {'scope': scope, 'sources': {}, 'source_set_complete': True}
        self.assertEqual(review_inputs.compare_inputs(base, missing)['applicability'], 'unknown')


if __name__ == '__main__':
    unittest.main()
