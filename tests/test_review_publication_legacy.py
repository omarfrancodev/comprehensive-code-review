"""Frozen synthetic drafts must rerender, including their old false positives."""
import copy
import hashlib
import json
from pathlib import Path
import unittest
from script_test_support import enable_package_imports

enable_package_imports()
from ccr.reporting.comment import verify_public_comment


class LegacyPublicationTests(unittest.TestCase):
    def test_legacy_drafts_rerender_under_their_policy(self):
        for version in (2, 3):
            with self.subTest(version=version):
                fixture = Path(__file__).parent / 'fixtures/publication_legacy' / f'draft{version}.json'
                data = json.loads(fixture.read_text(encoding='utf-8'))
                record, draft = data['record'], data['draft']
                before = copy.deepcopy(data)
                kwargs = dict(check_disclosure_context=data['disclosure'],
                              check_disclosure_sources={k: bytes.fromhex(v) for k, v in data['sources'].items()})
                self.assertTrue(verify_public_comment(record, draft, draft['body'], **kwargs)['verified'])
                edited = copy.deepcopy(draft)
                edited['body'] += '\nManual edit'
                edited['body_sha256'] = hashlib.sha256(edited['body'].encode()).hexdigest()
                with self.assertRaisesRegex(ValueError, 'body_mismatch'):
                    verify_public_comment(record, edited, edited['body'], **kwargs)
                self.assertEqual(data, before)
