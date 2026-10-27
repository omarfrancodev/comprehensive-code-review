"""Instruction routing checks; semantic calibration is a separate experiment."""
from pathlib import Path
import re
import unittest
from script_test_support import enable_package_imports

enable_package_imports()
from ccr.contracts import packets, review
from traceability_fixtures import record11

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / 'references/contracts/priority-calibration.md'


def destinations(file, text):
    return {((ROOT / file).parent / target).resolve()
            for target in re.findall(r'\[[^\]]+\]\(([^)#]+)(?:#[^)]*)?\)', text)}


class PriorityPolicyTests(unittest.TestCase):
    def test_canonical_reference_is_reachable_from_verification_and_consolidation(self):
        self.assertTrue(CANONICAL.is_file(), 'Missing canonical priority-calibration reference')
        files = ['SKILL.md', 'references/execution/reviewers.md',
                 'references/execution/worker-packets.md', 'references/contracts/result-contract.md',
                 'references/reporting/report-format.md', 'references/workflow/profiles.md']
        for file in files:
            with self.subTest(file=file):
                self.assertIn(CANONICAL.resolve(), destinations(file, (ROOT / file).read_text(encoding='utf-8')))

    def test_focused_and_independent_verification_routes_share_the_reference(self):
        file = 'SKILL.md'
        text = (ROOT / file).read_text(encoding='utf-8')
        for step in ('2. **Discovery/verification.**', '3. **Report/close.**'):
            paragraph = next(line for line in text.splitlines() if line.startswith(step))
            self.assertIn(CANONICAL.resolve(), destinations(file, paragraph))
        file = 'references/execution/reviewers.md'
        verification = (ROOT / file).read_text(encoding='utf-8').split('## Verification packet', 1)[1]
        self.assertIn(CANONICAL.resolve(), destinations(file, verification))

    def test_policy_preserves_current_contract_boundaries(self):
        value = record11()
        self.assertEqual(review.validate(value), [])
        self.assertEqual(sum(len(a['dimensions']) for a in value['coverage']['areas']), 27)
        self.assertTrue(value['checks'][0]['purpose'])
        packet = dict(packet_version=1, stage='discovery', context_id='synthetic',
                      findings=[], check_ids=[], coverage=dict(flows=[], limitations=[]))
        self.assertEqual(packets.validate(packet), [])
        self.assertIn('--expected-schema 11', (ROOT / 'SKILL.md').read_text(encoding='utf-8'))
        self.assertIn('check_schema_version', (ROOT / 'references/execution/worker-packets.md').read_text(encoding='utf-8'))
