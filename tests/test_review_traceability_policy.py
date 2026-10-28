"""Current producer instructions expose the required traceability slots."""
from pathlib import Path
import unittest
from script_test_support import enable_package_imports
enable_package_imports()

from ccr.contracts.dimensions import DIMENSIONS
from ccr.contracts.packets import validate as validate_packet

ROOT = Path(__file__).resolve().parents[1]


class PolicyTests(unittest.TestCase):
    def test_workflow_requires_new_contract_and_keeps_packet1(self):
        skill = (ROOT/'SKILL.md').read_text(encoding='utf-8')
        self.assertIn('--expected-schema 12', skill)
        artifacts = (ROOT/'references/archive/artifacts.md').read_text(encoding='utf-8')
        profiles = (ROOT/'references/workflow/profiles.md').read_text(encoding='utf-8')
        self.assertNotIn('--expected-schema 10', artifacts)
        self.assertIn('New final records use schema 12', profiles)
        rules = (ROOT/'references/contracts/result-contract.md').read_text(encoding='utf-8')
        self.assertIn('checks[].purpose', rules)
        packet = dict(packet_version=1, stage='discovery', context_id='synthetic', findings=[], check_ids=[],
                      coverage=dict(flows=['E05 inspected'], limitations=[dict(detail='D05 pending recovery boundary', material=True)]))
        self.assertEqual(validate_packet(packet), [])

    def test_dimension_ids_are_documented_in_their_area(self):
        files = {'A': 'design-testability.md', 'B': 'design-testability.md',
                 'C': 'contracts-data.md', 'D': 'contracts-data.md', 'E': 'security-operation.md'}
        for area, filename in files.items():
            text = (ROOT/'references/dimensions'/filename).read_text(encoding='utf-8')
            for identifier in DIMENSIONS[area]:
                self.assertIn(identifier, text)

    def test_purpose_precedes_capture_and_bound_check_ids_are_stable(self):
        workspaces = (ROOT/'references/execution/workspaces.md').read_text(encoding='utf-8')
        packets = (ROOT/'references/execution/worker-packets.md').read_text(encoding='utf-8')
        self.assertIn('before execution', workspaces)
        self.assertIn('receipt schema 2', workspaces)
        self.assertIn('never rename', packets)
        self.assertIn('check_schema_version', packets)
