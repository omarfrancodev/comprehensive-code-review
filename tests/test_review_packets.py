"""Compact records must preserve evidence and reject unbound or missing decisions."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_review_contract import clean_record


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'review_packets.py'
sys.path.insert(0, str(SCRIPT.parent))
spec = importlib.util.spec_from_file_location('review_packets', SCRIPT) if SCRIPT.exists() else None
packets = importlib.util.module_from_spec(spec) if spec else None
if spec:
    spec.loader.exec_module(packets)


def inputs():
    context = {'context_id': 'scope-head-456', 'scope': clean_record()['scope'], 'checks': []}
    evidence = {'kind': 'static', 'details': 'Consumer reads the absent id'}
    discovery = {'packet_version': 1, 'stage': 'discovery', 'context_id': 'scope-head-456',
                 'findings': [{'id': 'D1-F1', 'type': 'code',
                               'location': {'path': 'src/api.py', 'line': 2},
                               'scenario': 'Existing consumer indexes the returned id',
                               'impact': 'Navigation raises KeyError', 'evidence': [evidence]}],
                 'check_ids': [], 'coverage': {'flows': ['create → navigate'], 'limitations': []}}
    verification = {'packet_version': 1, 'stage': 'verification', 'context_id': 'scope-head-456',
                    'decisions': [{'id': 'D1-F1', 'status': 'confirmed',
                                   'evidence': [{'kind': 'static', 'details': 'Compared base and head; consumer unchanged'}]}],
                    'check_ids': [], 'coverage': {'flows': ['base/head consumer contract'], 'limitations': []}}
    return context, discovery, verification


class PacketTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(packets, 'compact packet helper is missing')

    def test_minimal_discovery_and_decision_delta_are_valid(self):
        _, discovery, verification = inputs()
        self.assertEqual(packets.validate(discovery), [])
        self.assertEqual(packets.validate(verification), [])

    def test_merge_keeps_scenario_and_evidence_without_guessing_final_judgments(self):
        context, discovery, verification = inputs()
        originals = copy.deepcopy((context, discovery, verification))
        result = packets.merge(context, [discovery], verification)
        item = result['findings'][0]
        self.assertEqual(item['scenario'], 'Existing consumer indexes the returned id')
        self.assertEqual(item['status'], 'confirmed')
        self.assertEqual(len(item['evidence']), 2)
        self.assertEqual(item['location'], {'path': 'src/api.py', 'line': 2, 'url': None, 'section': None})
        self.assertNotIn('priority', item)
        self.assertNotIn('origin', item)
        self.assertNotIn('correction', item)
        self.assertNotIn('verdict', result)
        self.assertNotIn('schema_version', result)
        self.assertEqual((context, discovery, verification), originals)

    def test_merging_requires_an_explicit_decision_for_each_candidate(self):
        context, discovery, verification = inputs()
        verification['decisions'] = []
        with self.assertRaisesRegex(ValueError, 'decision'):
            packets.merge(context, [discovery], verification)
        verification['decisions'] = [{'id': 'D1-F1', 'status': 'unresolved',
                                      'evidence': [{'kind': 'static', 'details': 'Required interface contract unavailable'}]}]
        self.assertEqual(packets.merge(context, [discovery], verification)['findings'][0]['status'], 'unresolved')

    def test_clean_scope_can_omit_verification_but_candidates_and_material_gaps_cannot(self):
        context, discovery, _ = inputs()
        with self.assertRaises(ValueError):
            packets.merge(context, [discovery])
        discovery['findings'] = []
        self.assertEqual(packets.merge(context, [discovery])['findings'], [])
        discovery['coverage']['limitations'] = [{'detail': 'Required tenant contract unknown', 'material': True}]
        with self.assertRaisesRegex(ValueError, 'material'):
            packets.merge(context, [discovery])

    def test_amended_claims_keep_the_previous_scenario_for_consolidation(self):
        context, discovery, verification = inputs()
        verification['decisions'][0]['updates'] = {'scenario': 'Only the legacy navigation consumer fails'}
        result = packets.merge(context, [discovery], verification)
        self.assertEqual(result['findings'][0]['scenario'], 'Only the legacy navigation consumer fails')
        self.assertEqual(result['amendments'][0]['previous']['scenario'], 'Existing consumer indexes the returned id')

    def test_cross_context_unknown_ids_and_role_id_collisions_are_rejected(self):
        context, discovery, verification = inputs()
        for change in ('context', 'unknown', 'collision'):
            with self.subTest(change=change):
                d, v = copy.deepcopy(discovery), copy.deepcopy(verification)
                ds = [d]
                if change == 'context':
                    v['context_id'] = 'another-head'
                elif change == 'unknown':
                    v['decisions'][0]['id'] = 'another-finding'
                else:
                    ds.append(copy.deepcopy(d))
                with self.assertRaises(ValueError):
                    packets.merge(context, ds, v)

    def test_referenced_checks_keep_actual_revision_and_require_ledger_entries(self):
        context, discovery, verification = inputs()
        discovery['check_ids'] = ['C1']
        discovery['findings'][0]['evidence'] = [{'kind': 'executed', 'details': 'Navigation fails', 'check_id': 'C1'}]
        with self.assertRaisesRegex(ValueError, 'check'):
            packets.merge(context, [discovery], verification)
        context['checks'] = [{'id': 'C1', 'command': 'python regression.py', 'revision': 'base-123',
                              'status': 'passed', 'failure_kind': None, 'evidence': 'Base navigation works',
                              'reused': False, 'reuse_reason': None, 'rerun_reason': None}]
        result = packets.merge(context, [discovery], verification)
        self.assertEqual(result['checks'][0]['revision'], 'base-123')

    def test_fixture_failure_cannot_be_the_verifiers_confirmation_evidence(self):
        context, discovery, verification = inputs()
        context['checks'] = [{'id': 'C1', 'command': 'python broken_fixture.py', 'revision': 'head-456',
                              'status': 'failed', 'failure_kind': 'fixture', 'evidence': 'Fixture cannot import',
                              'reused': False, 'reuse_reason': None, 'rerun_reason': None}]
        verification['check_ids'] = ['C1']
        verification['decisions'][0]['evidence'] = [{'kind': 'executed', 'details': 'Import failed', 'check_id': 'C1'}]
        with self.assertRaisesRegex(ValueError, 'confirm'):
            packets.merge(context, [discovery], verification)

    def test_delta_updates_are_explicit_and_cannot_change_the_candidate_identity(self):
        context, discovery, verification = inputs()
        verification['decisions'][0]['updates'] = {'priority': 'P1', 'origin': 'introduced',
                                                  'title': 'Missing response id', 'correction': 'Preserve id',
                                                  'blocking': True, 'blocking_reason': 'Required navigation fails'}
        self.assertEqual(packets.merge(context, [discovery], verification)['findings'][0]['priority'], 'P1')
        verification['decisions'][0]['updates']['id'] = 'replacement'
        self.assertTrue(packets.validate(verification))

    def test_malformed_packets_locations_and_evidence_fail_without_crashing(self):
        _, discovery, verification = inputs()
        variants = [None, [], {'packet_version': []}, {**discovery, 'findings': [None]},
                    {**verification, 'decisions': [{'id': [], 'status': [], 'evidence': [None]}]}]
        for packet in variants:
            self.assertTrue(packets.validate(packet))
        discovery['findings'][0]['location']['line'] = True
        self.assertTrue(packets.validate(discovery))

    def test_cli_merge_emits_a_bundle_that_requires_final_consolidation(self):
        context, discovery, verification = inputs()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, value in [('context', context), ('discovery', discovery), ('verification', verification)]:
                (root / f'{name}.json').write_text(json.dumps(value), encoding='utf-8')
            result = subprocess.run([sys.executable, '-B', str(SCRIPT), 'merge',
                                     '--context', str(root / 'context.json'), '--discovery', str(root / 'discovery.json'),
                                     '--verification', str(root / 'verification.json')], capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['findings'][0]['status'], 'confirmed')


if __name__ == '__main__':
    unittest.main()
