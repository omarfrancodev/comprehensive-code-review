"""Shared grammar and resolution tests for retained evidence references."""
import json
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

    def test_profile_transition_reference_resolves_its_stable_history_row(self):
        selected = selection_input(profile='standard', id='S002',
            reference='evidence/context.json#profile_history/1/profile')
        selected['id'] = 'S002'
        context = {'profile': 'standard', 'profile_history': [
            {'id': 'S001', 'profile': 'focused'},
            {'id': 'S002', 'profile': 'standard'},
        ]}
        sources = {'evidence/context.json': json.dumps(context).encode('utf-8')}

        self.assertEqual(refs.validate_selection_reference(selected, sources), [])
        self.assertTrue(refs.validate_selection_reference(dict(
            selected, reference='evidence/context.json#profile_history/0/profile'), sources))

    def test_initial_profile_reference_stays_stable_after_profile_transition(self):
        selected = selection_input(profile='focused', id='S001',
            reference='evidence/context.json#profile_history/0/profile')
        selected['id'] = 'S001'
        context = {'profile': 'deep', 'profile_history': [
            {'id': 'S001', 'profile': 'focused'},
            {'id': 'S002', 'profile': 'deep'},
        ]}
        sources = {'evidence/context.json': json.dumps(context).encode('utf-8')}

        self.assertEqual(refs.validate_selection_reference(selected, sources), [])

    def test_legacy_initial_profile_reference_uses_history_after_transition(self):
        selected = selection_input(profile='focused', id='S001',
            reference='evidence/context.json#profile')
        selected['id'] = 'S001'
        context = {'profile': 'deep', 'profile_history': [
            {'id': 'S001', 'profile': 'focused'},
            {'id': 'S002', 'profile': 'deep'},
        ]}
        sources = {'evidence/context.json': json.dumps(context).encode('utf-8')}

        self.assertEqual(refs.validate_selection_reference(selected, sources), [])

    def test_prepared_initial_selection_uses_immutable_history_reference(self):
        selected = review_artifacts._initial_selection(selection_input(profile='focused'))

        self.assertEqual(selected['reference'],
                         'evidence/context.json#profile_history/0/profile')

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
