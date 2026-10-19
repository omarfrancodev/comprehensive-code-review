"""Pure contracts for readable, logical archive paths."""
from datetime import datetime, timezone
import re
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import review_layout


def mr(head="abc1234567890", base="def9876543210", reference="https://git.example/acme/api/merge_requests/1010"):
    return {'repository': 'https://git.example/acme/api', 'mode': 'mr', 'base': base,
            'head': head, 'snapshot': None, 'target': 'develop', 'reference': reference}


class LogicalLayoutTests(unittest.TestCase):
    def test_same_mr_different_heads_share_logical_group(self):
        first, second = review_layout.logical_scope(mr()), review_layout.logical_scope(mr(head='fedcba9876543'))
        self.assertEqual(review_layout.scope_group(first), review_layout.scope_group(second))
        self.assertEqual(first['identity'], second['identity'])

    def test_different_boundaries_same_head_do_not_share_group(self):
        scope = {'repository': 'repo', 'mode': 'module', 'base': None, 'head': 'abc123456789',
                 'snapshot': None, 'target': None, 'reference': 'feature/file-cleanup'}
        a = review_layout.logical_scope(scope, {'mode': 'module', 'selector': {'reference': 'feature/file-cleanup', 'boundaries': ['src/a']}})
        b = review_layout.logical_scope(scope, {'mode': 'module', 'selector': {'reference': 'feature/file-cleanup', 'boundaries': ['src/b']}})
        self.assertNotEqual(review_layout.scope_group(a), review_layout.scope_group(b))

    def test_local_snapshots_share_group_only_for_equal_boundaries(self):
        def desc(snapshot, boundaries):
            scope = {'repository': 'repo', 'mode': 'working', 'base': 'abc', 'head': None,
                     'snapshot': snapshot, 'target': None, 'reference': None}
            return review_layout.logical_scope(scope, {'mode': 'working', 'selector': {'boundaries': boundaries}})
        self.assertEqual(review_layout.scope_group(desc('one', ['src/a'])), review_layout.scope_group(desc('two', ['src/a'])))
        self.assertNotEqual(review_layout.scope_group(desc('one', ['src/a'])), review_layout.scope_group(desc('two', ['src/b'])))

    def test_sha_only_range_has_no_invented_branch_identity(self):
        scope = {'repository': 'repo', 'mode': 'range', 'base': 'a' * 40, 'head': 'b' * 40,
                 'snapshot': None, 'target': None, 'reference': None}
        value = review_layout.logical_scope(scope)
        self.assertEqual(value['selector'], {'kind': 'commits', 'base': 'a' * 40, 'head': 'b' * 40})

    def test_windows_reserved_traversal_length_and_prefix_collision(self):
        scope = {'repository': 'repo', 'mode': 'module', 'base': None, 'head': 'a' * 40,
                 'snapshot': None, 'target': None, 'reference': 'module'}
        for boundary in ('../secret', '/absolute', 'CON', 'a' * 501):
            with self.subTest(boundary=boundary), self.assertRaises(ValueError):
                review_layout.logical_scope(scope, {'mode': 'module', 'selector': {'reference': 'module', 'boundaries': [boundary]}})
        def commit(head):
            scope = {'repository': 'repo', 'mode': 'commit', 'base': None, 'head': head,
                     'snapshot': None, 'target': None, 'reference': None}
            return review_layout.logical_scope(scope)
        a, b = commit('1' * 40), commit('1' * 12 + '2' * 28)
        self.assertEqual(a['hint'], b['hint'])
        self.assertNotEqual(a['identity'], b['identity'])
        self.assertNotEqual(review_layout.scope_group(a), review_layout.scope_group(b))

    def test_timestamp_hint_and_unique_id_are_bound(self):
        run_id = '0123456789abcdefabcd'
        name = review_layout.run_name(mr(head='90e54abb1234567890'), '2026-10-18T15:00:00-05:00', run_id)
        self.assertEqual(name, '20261018T200000Z--head-90e54abb1234--' + run_id)
        self.assertLessEqual(len(name), 128)
        with self.assertRaises(ValueError):
            review_layout.run_name(mr(), '2026-10-18T15:00:00', run_id)


if __name__ == '__main__':
    unittest.main()
