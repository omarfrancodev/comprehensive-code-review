"""Shared grammar and resolution tests for retained evidence references."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import review_references as refs
import review_artifacts

from recovery_fixtures import record10, selection_input


class ReferenceTests(unittest.TestCase):
    def test_references_and_profile(self):
        self.assertEqual(refs.parse_reference('evidence/context.json#profile',
            field='reference'), ('evidence/context.json', 'profile'))
        for bad in ('https://example.test/pr/1', 'evidence/a/b.cs',
                    'evidence/../x', 'evidence/CON', 'evidence/a%2Fb'):
            with self.subTest(reference=bad), self.assertRaises(ValueError):
                refs.parse_reference(bad, field='reference')
        selected = selection_input()
        self.assertEqual(refs.validate_selection_reference(selected, None), [])
        self.assertEqual(refs.validate_selection_reference(selected, {
            'evidence/context.json': b'{"profile":"focused"}'}), [])
        self.assertTrue(refs.validate_selection_reference(
            dict(selected, reference='evidence/scope.json'), None))

    def test_json_fragment_escapes_and_indices(self):
        data = {'evidence/a.json': b'{"a/b":[{"~key":"focused"}]}'}
        self.assertEqual(refs.resolve_reference('evidence/a.json#a~1b/0/~0key',
            data, field='reference'), 'focused')
        markdown = {'evidence/guide.md': b'# Heading?\n'}
        self.assertEqual(refs.resolve_reference(
            'evidence/guide.md#Heading?', markdown, field='reference'),
            b'# Heading?\n')

    def test_input_capture_rejects_traversal_even_under_evidence_prefix(self):
        record = record10()
        raw = {'scope': record['scope'],
               'sources': {'evidence/../outside.md': 'a' * 64},
               'source_set_complete': True}
        with self.assertRaisesRegex(ValueError, 'unsafe path component'):
            review_artifacts._capture_review_inputs(
                raw, record['scope'], 'focused', 'test inputs')


if __name__ == '__main__':
    unittest.main()
