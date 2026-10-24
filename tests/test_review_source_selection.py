"""Bounded, deterministic selection and capture for reference-index inputs."""
import hashlib
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

from ccr.contracts import material_inputs as material, reference_index as refs
from ccr.workflow import builders


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


class SourceSelectionTests(unittest.TestCase):
    def test_capture_includes_material_inputs_not_output_aliases(self):
        description, notes, output = b'description-v1', b'notes-v1', b'worker-result'
        index = {'schema_version': 1,
                 'aliases': {'evidence/worker/result.json': {
                     'reference': 'evidence/result.json', 'sha256': digest(output)}},
                 'inputs': [
                     {'reference': 'evidence/description.md', 'purpose': 'description',
                      'sha256': digest(description)},
                     {'reference': 'evidence/notes.json', 'purpose': 'notes',
                      'sha256': digest(notes)}]}
        raw = json.dumps(index, sort_keys=True, separators=(',', ':')).encode()
        sources = {'evidence/reference-index.json': raw,
                   'evidence/description.md': description,
                   'evidence/notes.json': notes, 'evidence/result.json': output}

        self.assertEqual(refs.reference_source_paths(index), [
            'evidence/description.md', 'evidence/notes.json', 'evidence/result.json'])
        self.assertEqual(builders.capture_input_sources(raw, sources), {
            'evidence/reference-index.json': digest(raw),
            'evidence/description.md': digest(description),
            'evidence/notes.json': digest(notes)})
        self.assertTrue(material.validate_captured_material_sources(
            {'sources': {'evidence/reference-index.json': digest(raw)}}, index, sources))

    def test_missing_or_changed_input_is_rejected(self):
        content = b'notes-v1'
        index = {'schema_version': 1, 'aliases': {}, 'inputs': [
            {'reference': 'evidence/notes.json', 'purpose': 'notes', 'sha256': digest(content)}]}
        raw = json.dumps(index, sort_keys=True, separators=(',', ':')).encode()
        with self.assertRaisesRegex(ValueError, 'notes.json'):
            builders.capture_input_sources(raw, {'evidence/reference-index.json': raw})
        with self.assertRaisesRegex(ValueError, 'notes.json'):
            builders.capture_input_sources(raw, {'evidence/reference-index.json': raw,
                                                'evidence/notes.json': b'changed'})

    def test_captured_material_accepts_only_hash_matching_one_hop_alias(self):
        description = b'description-v1'
        checksum = digest(description)
        alias_path = 'evidence/source/description.md'
        index = {'schema_version': 1, 'aliases': {alias_path: {
                    'reference': 'evidence/description.md', 'sha256': checksum}},
                 'inputs': [{'reference': 'evidence/description.md',
                             'purpose': 'description', 'sha256': checksum}]}
        sources = {'evidence/description.md': description, alias_path: description}
        self.assertEqual(material.validate_captured_material_sources(
            {'sources': {alias_path: checksum}}, index, sources), [])

        mismatch = dict(index, aliases={alias_path: {
            'reference': 'evidence/description.md', 'sha256': '0' * 64}})
        self.assertTrue(material.validate_captured_material_sources(
            {'sources': {alias_path: checksum}}, mismatch, sources))
        for invalid_aliases in (
                {alias_path: {'reference': 'evidence/second/description.md', 'sha256': checksum},
                 'evidence/second/description.md': {'reference': 'evidence/description.md',
                                                    'sha256': checksum}},
                {'evidence/../description.md': {'reference': 'evidence/description.md',
                                                'sha256': checksum}}):
            with self.subTest(aliases=invalid_aliases):
                invalid = dict(index, aliases=invalid_aliases)
                self.assertTrue(refs.validate_reference_index(invalid, sources))
                self.assertTrue(material.validate_captured_material_sources(
                    {'sources': {alias_path: checksum}}, invalid, sources))


if __name__ == '__main__':
    unittest.main()
