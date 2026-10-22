"""Explicit latest selection over verified native archive results."""
from pathlib import Path
import unittest
from unittest.mock import patch

import test_review_archive8 as archive8
import review_recovery
from ccr.archive import history as history_ops, lookup as lookup_ops
from recovery_fixtures import selection_input


class LatestSelectionTests(unittest.TestCase):
    setUp = archive8.Archive8Tests.setUp
    git = archive8.Archive8Tests.git
    write = archive8.Archive8Tests.write
    read = archive8.Archive8Tests.read
    retain = archive8.archive_tests.ArchiveTests.retain
    close = archive8.archive_tests.ArchiveTests.close

    def test_lookup_lists_by_default_and_explicit_selection_returns_verified_result(self):
        scope = self.read(self.scope)
        run = Path(archive8.artifacts.prepare(self.repo, self.scope, '2.13.0', 'codex',
            output_root=self.output, profile_input=selection_input()))
        self.retain(run)
        self.close(run)
        inputs = {'scope': scope, 'sources': {}, 'source_set_complete': True}
        listed = review_recovery.find_candidates(self.repo, scope, archive_root=self.output,
                                                 current_inputs=inputs)
        self.assertEqual(len(listed['candidates']), 1)
        self.assertNotIn('selected', listed)
        result = review_recovery.select_latest(self.repo, scope, archive_root=self.output,
                                              current_inputs=inputs)
        self.assertEqual(result['status'], 'selected', result)
        self.assertEqual(result['selected']['run_dir'], str(run))
        self.assertEqual(result['selected']['integrity'], 'report_verified')

    def test_requested_rebuild_does_not_require_identical_mr_head_to_reuse_latest(self):
        original = {'repository': 'example/service', 'mode': 'mr', 'base': 'base-one',
                    'head': '90e54abb1234567890abcdef', 'snapshot': None, 'target': 'develop',
                    'reference': 'https://git.example/acme/api/merge_requests/1010'}
        scope_file = self.write('mr-scope.json', original)
        run = Path(archive8.artifacts.prepare(self.repo, scope_file, '2.13.0', 'codex',
            output_root=self.output, profile_input=selection_input()))
        self.retain(run)
        self.close(run)
        newer = dict(original, base='different-base', head='fedcba9876543210')
        inputs = {'scope': newer, 'sources': {}, 'source_set_complete': True}
        result = review_recovery.select_latest(self.repo, newer, archive_root=self.output,
                                              current_inputs=inputs)
        self.assertEqual(result['status'], 'selected', result)
        self.assertEqual(result['selected']['run_dir'], str(run))
        self.assertEqual(result['selected']['applicability'], 'changed')

    def test_same_timestamp_is_ambiguous(self):
        base = {'kind': 'native', 'integrity': 'report_verified', 'scope': {},
                'logical_scope': {'identity': 'same'}, 'state': 'complete',
                'operation': {'disposition': 'complete'}, 'created_at': '2026-10-18T15:00:00Z',
                'run_dir': 'a', 'review_id': 'CR-a'}
        second = dict(base, run_dir='b', review_id='CR-b')
        with patch.object(lookup_ops, 'find_candidates', return_value={
                'candidates': [base, second], 'truncated': False, 'next_cursor': None}):
            with patch.object(review_recovery.review_layout, 'logical_scope', return_value={'identity': 'same'}):
                result = review_recovery.select_latest('repo', {'mode': 'mr'}, current_inputs={'scope': {'mode': 'mr'}})
        self.assertEqual(result['status'], 'ambiguous')
        self.assertIsNone(result['selected'])

    def test_metadata_timestamp_wins_over_candidate_order_and_run_id(self):
        scope = {'repository': 'example/service', 'mode': 'mr', 'base': 'base-one',
                 'head': 'abc1234567890', 'snapshot': None, 'target': 'develop',
                 'reference': 'https://git.example/acme/api/merge_requests/1010'}
        logical = review_recovery.review_layout.logical_scope(scope)
        old = {'kind': 'native', 'integrity': 'report_verified', 'scope': scope,
               'logical_scope': logical, 'state': 'complete',
               'operation': {'disposition': 'complete'}, 'created_at': '2026-10-10T15:00:00Z',
               'run_dir': 'z-first', 'run_id': 'f' * 20, 'review_id': 'CR-' + 'f' * 20}
        new = dict(old, created_at='2026-10-12T15:00:00Z', run_dir='a-second',
                   run_id='0' * 20, review_id='CR-' + '0' * 20)
        fake_artifacts = type('Artifacts', (), {
            'repository_identity': staticmethod(lambda repo: 'synthetic-repository'),
            'select_output_root': staticmethod(lambda repo, root: Path(root)),
            '_load_run': staticmethod(lambda run: (Path(run), {'logical_scope': logical}, {})),
        })
        inputs = {'scope': scope, 'sources': {}, 'source_set_complete': True}
        with patch.object(lookup_ops, 'find_candidates', return_value={
                'candidates': [old, new], 'truncated': False, 'next_cursor': None}), \
             patch.object(lookup_ops, 'repository_identity', return_value='synthetic-repository'),\
             patch.object(lookup_ops, 'select_output_root', side_effect=lambda repo, root: Path(root)),\
             patch.object(lookup_ops, '_load_run', side_effect=lambda run: (Path(run), {'logical_scope': logical}, {})), \
             patch.object(lookup_ops, '_candidate', side_effect=lambda run, *args: new if str(run) == 'a-second' else old):
            result = review_recovery.select_latest('repo', scope, archive_root='archive', current_inputs=inputs)
        self.assertEqual(result['status'], 'selected')
        self.assertEqual(result['selected']['run_dir'], 'a-second')

    def test_scan_limit_does_not_return_partial_selection(self):
        row = {'kind': 'native', 'integrity': 'report_verified', 'scope': {},
               'logical_scope': {'identity': 'same'}, 'state': 'complete',
               'operation': {'disposition': 'complete'}}
        with patch.object(lookup_ops, 'find_candidates', return_value={
                'candidates': [row], 'truncated': True, 'next_cursor': 'next'}):
            with patch.object(review_recovery.review_layout, 'logical_scope', return_value={'identity': 'same'}):
                result = review_recovery.select_latest('repo', {'mode': 'mr'},
                    current_inputs={'scope': {'mode': 'mr'}}, max_scan=1)
        self.assertEqual(result['status'], 'incomplete_search')
        self.assertIsNone(result['selected'])

    def test_unreadable_native_candidate_blocks_selection_of_an_older_result(self):
        scope = self.read(self.scope)
        run = Path(archive8.artifacts.prepare(self.repo, self.scope, '2.12.1', 'codex',
            output_root=self.output, profile_input=selection_input()))
        self.retain(run)
        self.close(run)
        broken = Path(archive8.artifacts.prepare(self.repo, self.scope, '2.12.1', 'codex',
            output_root=self.output, profile_input=selection_input()))
        (broken / 'cierre.json').write_bytes(b'{broken')
        before = archive8.archive_tests.ArchiveTests.snapshot(self, self.output)
        result = review_recovery.select_latest(self.repo, scope, archive_root=self.output,
            current_inputs={'scope': scope, 'sources': {}, 'source_set_complete': True})
        self.assertEqual(result['status'], 'incomplete_search')
        self.assertIsNone(result['selected'])
        self.assertEqual(archive8.archive_tests.ArchiveTests.snapshot(self, self.output), before)

    def test_unreadable_logical_group_is_an_incomplete_search(self):
        scope = self.read(self.scope)
        run = Path(archive8.artifacts.prepare(self.repo, self.scope, '2.12.1', 'codex',
            output_root=self.output, profile_input=selection_input()))
        original = Path.iterdir
        def unreadable(path):
            if path == run.parent:
                raise PermissionError('synthetic unreadable logical scope')
            return original(path)
        with patch.object(Path, 'iterdir', unreadable):
            result = review_recovery.select_latest(self.repo, scope, archive_root=self.output,
                current_inputs={'scope': scope, 'sources': {}, 'source_set_complete': True})
        self.assertEqual(result['status'], 'incomplete_search')
        self.assertIsNone(result['selected'])

    def test_selected_result_is_revalidated_and_disappearance_is_incomplete(self):
        scope = self.read(self.scope)
        run = Path(archive8.artifacts.prepare(self.repo, self.scope, '2.12.1', 'codex',
            output_root=self.output, profile_input=selection_input()))
        self.retain(run)
        self.close(run)
        inputs = {'scope': scope, 'sources': {}, 'source_set_complete': True}
        page = review_recovery.find_candidates(self.repo, scope, archive_root=self.output,
                                                current_inputs=inputs)
        with patch.object(lookup_ops, 'find_candidates', return_value=page), \
             patch.object(lookup_ops, '_load_run', side_effect=ValueError('selected source disappeared')):
            result = review_recovery.select_latest(self.repo, scope, archive_root=self.output, current_inputs=inputs)
        self.assertEqual(result['status'], 'incomplete_search')
        self.assertIsNone(result['selected'])

    def test_history_is_included_only_on_request_and_never_selected_as_current(self):
        scope = self.read(self.scope)
        identity = archive8.artifacts.repository_identity(self.repo)
        repository_group = archive8.artifacts._repository_group(identity)
        native_group = self.output / repository_group
        native_group.mkdir(parents=True)
        history_root = self.output / '.historical' / repository_group
        history_dir = history_root / 'old-port'
        history_dir.mkdir(parents=True)
        package = {'status': 'verified_package', 'port_id': 'HP-example',
                   'consultation': {'scope': scope}}
        inputs = {'scope': scope, 'sources': {}, 'source_set_complete': True}
        with patch.object(history_ops, 'verify_history', return_value=package):
            omitted = review_recovery.find_candidates(self.repo, scope, archive_root=self.output)
            included = review_recovery.find_candidates(self.repo, scope, archive_root=self.output,
                                                       include_history=True)
        self.assertEqual(omitted['candidates'], [])
        self.assertEqual(included['candidates'][0]['kind'], 'historical_port')
        latest = review_recovery.select_latest(self.repo, scope, archive_root=self.output, current_inputs=inputs)
        self.assertEqual(latest['status'], 'no_match')


if __name__ == '__main__':
    unittest.main()
