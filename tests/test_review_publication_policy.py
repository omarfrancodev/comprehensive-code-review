"""Audience policy preserves product evidence without publishing review mechanics."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_review_execution_policy import record8, limit
from test_review_profile_names import record7
from test_review_contract import contract, MODULE_PATH


def classification(value, kind='validation', summary=None):
    digest = hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()
    return dict(source_sha256=digest, limitations=[dict(index=i, kind=kind, public_summary=summary)
        for i, _ in enumerate(value['coverage']['limitations'])])


class PublicationPolicyTests(unittest.TestCase):
    def test_internal_execution_detail_stays_private(self):
        value = record8()
        value['coverage']['limitations'] = [limit(detail='Worker tool denied by local harness')]
        before = copy.deepcopy(value)
        self.assertIn('Worker tool denied', contract.render(value))
        self.assertNotIn('Worker tool denied', contract.render(value, 'comment'))
        self.assertEqual(value, before)

    def test_material_execution_publishes_impact(self):
        value = record8()
        value['coverage']['limitations'] = [limit(material=True, summary='Required compatibility check remains incomplete',
                                                detail='Worker tool denied by local harness')]
        value['verdict'] = 'insufficient_evidence'
        output = contract.render(value, 'comment')
        self.assertIn('Required compatibility check remains incomplete', output)
        self.assertNotIn('Worker tool denied', output)
        self.assertIn('EVIDENCIA INSUFICIENTE', output)

    def test_product_session_text_survives(self):
        value = record8()
        value['coverage']['limitations'] = [limit('behavior', detail='User session expiry remains untested')]
        self.assertIn('User session expiry remains untested', contract.render(value, 'comment'))

    def test_material_abcde_gap_survives_without_duplicates(self):
        value = record8()
        text = 'Consumer compatibility remains incomplete'
        value['coverage']['limitations'] = [limit('validation', True, detail=text)]
        value['coverage']['areas'][2].update(status='partial', material=True, details=text)
        value['verdict'] = 'insufficient_evidence'
        output = contract.render(value, 'comment')
        self.assertEqual(output.count(text), 1)
        value['reservations'] = [text]
        self.assertEqual(contract.render(value, 'comment').count(text), 1)

    def test_legacy_publication_needs_bound_classification(self):
        value = record7()
        value['coverage']['limitations'] = [dict(detail='Harness mechanics', material=False)]
        before = copy.deepcopy(value)
        with self.assertRaises(ValueError):
            contract.render(value, 'comment')
        context = classification(value, 'execution')
        self.assertNotIn('Harness mechanics', contract.render(value, 'comment', publication_context=context))
        for mutation in [dict(source_sha256='0' * 64), dict(limitations=[]),
                         dict(limitations=context['limitations'] * 2)]:
            bad = copy.deepcopy(context)
            bad.update(mutation)
            with self.assertRaises(ValueError):
                contract.render(value, 'comment', publication_context=bad)
        self.assertEqual(value, before)

    def test_public_handoff_uses_same_policy(self):
        value = record8()
        value['coverage']['limitations'] = [limit(detail='Worker tool denied by local harness')]
        self.assertNotIn('Worker tool denied', contract.render_handoff(value, audience='comment'))
        self.assertIn('Worker tool denied', contract.render_handoff(value))
        value = record7()
        value['coverage']['limitations'] = [dict(detail='Unclassified', material=False)]
        with self.assertRaises(ValueError):
            contract.render_handoff(value, audience='comment')

    def test_cli_classification_is_explicit_and_bound(self):
        value = record7()
        value['coverage']['limitations'] = [dict(detail='Harness mechanics', material=False)]
        with tempfile.TemporaryDirectory(prefix='ccr-publication-') as directory:
            record = Path(directory) / 'review.json'
            context = Path(directory) / 'classification.json'
            record.write_text(json.dumps(value), encoding='utf-8')
            context.write_text(json.dumps(classification(value, 'execution')), encoding='utf-8')
            command = [sys.executable, '-B', '-X', 'utf8', str(MODULE_PATH)]
            args = ['--input', str(record), '--publication-context', str(context)]
            result = subprocess.run(command + ['render-comment'] + args, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn('Harness mechanics', result.stdout)
            result = subprocess.run(command + ['render-user'] + args, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            context.write_text(json.dumps(dict(classification(value), source_sha256='bad')), encoding='utf-8')
            result = subprocess.run(command + ['render-comment'] + args, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, '')


if __name__ == '__main__':
    unittest.main()
