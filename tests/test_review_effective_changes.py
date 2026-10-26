"""Content equivalence is distinct from commit provenance and exact recovery."""
import base64
import copy
import hashlib
import json
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from ccr.contracts.effective_changes import (
    normalize_effective_changes, effective_projection, compare_effective_changes,
)


def b64(value):
    return base64.b64encode(value).decode('ascii')


def descriptor(**updates):
    value = dict(schema_version=1, algorithm='ccr-effective-diff-v1',
        logical_scope_identity='a' * 64,
        comparison=dict(kind='merge-base-to-head', base='1' * 40, head='2' * 40,
                        target_head='1' * 40, diff_base='1' * 40, object_format='sha1'),
        complete=True, entries=[dict(old_path_b64=b64(b'file.txt'), new_path_b64=b64(b'file.txt'),
            old_mode='100644', new_mode='100644', kind='text', old_blob='3' * 40,
            new_blob='4' * 40, payload={'patch_b64': b64(b'@@\n-old\n+new\n')})],
        diagnostics=[])
    value.update(updates)
    projection = [{k: v for k, v in row.items() if k not in ('old_blob', 'new_blob')}
                  for row in value['entries']]
    value['changes_sha256'] = hashlib.sha256(json.dumps(projection, sort_keys=True,
        separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
    return value


class EffectiveChangeTests(unittest.TestCase):
    def test_equal_payload_with_different_commits_is_equivalent(self):
        old, new = descriptor(), descriptor()
        new['comparison']['head'] = '5' * 40
        new['entries'][0]['new_blob'] = '6' * 40
        result = compare_effective_changes(old, new)
        self.assertEqual(result['code_equivalence'], 'equivalent')
        self.assertTrue(result['metadata_only'])
        self.assertEqual(effective_projection(old), effective_projection(new))

    def test_changed_hunk_path_mode_or_binary_is_different(self):
        for field, content in [('payload', {'patch_b64': b64(b'@@\n-old\n+other\n')}),
                               ('new_mode', '100755'), ('new_path_b64', b64(b'other.txt'))]:
            with self.subTest(field=field):
                new = descriptor()
                new['entries'][0][field] = content
                new = descriptor(entries=new['entries'])
                self.assertEqual(compare_effective_changes(descriptor(), new)['code_equivalence'], 'different')
        binary = copy.deepcopy(descriptor()['entries'])
        binary[0].update(kind='binary', payload={'old_sha256': '1'*64, 'new_sha256': '2'*64})
        changed = copy.deepcopy(binary)
        changed[0]['payload']['new_sha256'] = '3'*64
        self.assertEqual(compare_effective_changes(descriptor(entries=binary),
            descriptor(entries=changed))['code_equivalence'], 'different')

    def test_absent_or_incomplete_descriptor_is_unknown(self):
        for old in (None, descriptor(complete=False), {'schema_version': 99}):
            self.assertEqual(compare_effective_changes(old, descriptor())['code_equivalence'], 'unknown')
        self.assertEqual(compare_effective_changes(descriptor(), descriptor(complete=False))['code_equivalence'], 'unknown')

    def test_digest_and_payload_must_agree(self):
        value = descriptor()
        value['changes_sha256'] = '0'*64
        with self.assertRaises(ValueError):
            normalize_effective_changes(value)

    def test_duplicate_entries_and_unsupported_algorithm_are_unknown_or_invalid(self):
        value = descriptor()
        for bad in (descriptor(entries=value['entries']*2), descriptor(algorithm='patch-id')):
            with self.assertRaises(ValueError):
                normalize_effective_changes(bad)

    def test_paths_and_modes_cannot_hide_a_change(self):
        for raw in (b'../outside', b'/root', b'a\0b', b'C:/escape'):
            entries = copy.deepcopy(descriptor()['entries'])
            entries[0]['new_path_b64'] = b64(raw)
            with self.assertRaises(ValueError):
                normalize_effective_changes(descriptor(entries=entries))
        entries = copy.deepcopy(descriptor()['entries'])
        entries[0]['new_path_b64'] = b64(b'path\twith\n\xff')
        self.assertEqual(normalize_effective_changes(descriptor(entries=entries))['entries'], entries)


if __name__ == '__main__':
    unittest.main()
