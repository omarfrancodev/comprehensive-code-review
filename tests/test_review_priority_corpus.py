"""Fixture integrity and reference separation, not model-judgment tests."""
import hashlib
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parent / 'fixtures' / 'priority_calibration'
CASE_FIELDS = {'id', 'obligation', 'trigger', 'observed_flow', 'consequence',
               'affected_scope', 'recovery', 'controls', 'proof', 'unknowns'}
REFERENCE_FIELDS = {'id', 'expected_status', 'accepted_priorities', 'rationale', 'pair', 'invariant'}


class PriorityCorpusTests(unittest.TestCase):
    def load(self, split, kind):
        file = ROOT / f'{split}-{kind}.json'
        self.assertTrue(file.is_file(), f'Missing calibration corpus: {file.name}')
        return json.loads(file.read_text(encoding='utf-8'))

    def test_case_and_reference_shapes_are_exact(self):
        for split in ('development', 'acceptance'):
            cases, references = self.load(split, 'cases'), self.load(split, 'reference')
            for case in cases:
                self.assertEqual(set(case), CASE_FIELDS)
                for field in CASE_FIELDS - {'proof', 'unknowns'}:
                    self.assertIsInstance(case[field], str)
                    self.assertTrue(case[field].strip())
                self.assertIsInstance(case['proof'], list)
                self.assertTrue(case['proof'])
                self.assertIsInstance(case['unknowns'], list)
                for text in case['proof'] + case['unknowns']:
                    self.assertIsInstance(text, str)
                    self.assertTrue(text.strip())
            for ref in references:
                self.assertEqual(set(ref), REFERENCE_FIELDS)
                self.assertIn(ref['expected_status'], ('confirmed', 'rejected', 'unresolved'))
                self.assertIsInstance(ref['accepted_priorities'], list)
                self.assertEqual(len(ref['accepted_priorities']), len(set(ref['accepted_priorities'])))
                self.assertTrue(set(ref['accepted_priorities']) <= {'P0', 'P1', 'P2', 'P3'})
                self.assertEqual(bool(ref['accepted_priorities']), ref['expected_status'] == 'confirmed')
                self.assertTrue(isinstance(ref['rationale'], str) and ref['rationale'].strip())

    def test_ids_split_and_pairs_are_complete(self):
        all_ids = set()
        for split, first, last in (('development', 1, 20), ('acceptance', 21, 28)):
            cases, refs = self.load(split, 'cases'), self.load(split, 'reference')
            expected = {f'PC{i:02}' for i in range(first, last + 1)}
            self.assertEqual(len(cases), len(expected))
            self.assertEqual(len(refs), len(expected))
            self.assertEqual({c['id'] for c in cases}, expected)
            self.assertEqual({r['id'] for r in refs}, expected)
            self.assertFalse(all_ids & expected)
            all_ids |= expected
            if split == 'development':
                groups = {}
                for ref in refs:
                    self.assertIsInstance(ref['pair'], str)
                    self.assertIn(ref['invariant'], ('same_priority', 'contrast'))
                    groups.setdefault(ref['pair'], []).append(ref)
                self.assertEqual(len(groups), 10)
                for group in groups.values():
                    self.assertEqual(len(group), 2)
                    self.assertEqual(len({r['invariant'] for r in group}), 1)
                    if group[0]['invariant'] == 'same_priority':
                        self.assertEqual(group[0]['accepted_priorities'], group[1]['accepted_priorities'])
            else:
                self.assertTrue(all(r['pair'] is None and r['invariant'] is None for r in refs))

    def test_inputs_do_not_contain_reference_fields(self):
        forbidden = (REFERENCE_FIELDS - {'id'}) | {'priority', 'status', 'expected_priority', 'review_id'}
        for split in ('development', 'acceptance'):
            for case in self.load(split, 'cases'):
                self.assertFalse(set(case) & forbidden)
                self.assertNotRegex(json.dumps(case, ensure_ascii=False), r'CR-[0-9a-f]{20}|\bP[0-3]\b')

    def test_reference_matches_spec_boundaries(self):
        expected = ['P1', 'P1', 'P1', 'P1', 'P1', 'P1', 'P1', 'P2', 'P1', 'P3',
                    'P0', 'rejected', 'P1', 'unresolved', 'rejected', 'P2',
                    'rejected', 'P2', 'P3', 'P2', 'P0', 'P0', 'P1', 'P1',
                    'P2', 'P2', 'P3', 'unresolved']
        refs = self.load('development', 'reference') + self.load('acceptance', 'reference')
        observed = {r['id']: r for r in refs}
        for index, outcome in enumerate(expected, 1):
            row = observed[f'PC{index:02}']
            self.assertEqual(row['expected_status'], 'confirmed' if outcome.startswith('P') else outcome)
            self.assertEqual(row['accepted_priorities'], [outcome] if outcome.startswith('P') else [])

    def test_git_retains_hashed_evaluation_bytes(self):
        repo = Path(__file__).resolve().parents[1]
        evidence = repo / 'docs/validation/priority-calibration-evidence'
        self.assertTrue(evidence.is_dir())
        for file in sorted(evidence.iterdir()):
            if not file.is_file():
                continue
            relative = file.relative_to(repo).as_posix()
            raw = subprocess.check_output(['git', 'hash-object', '--no-filters', str(file)], cwd=repo)
            retained = subprocess.check_output(['git', 'hash-object', f'--path={relative}', str(file)], cwd=repo)
            self.assertEqual(retained.strip(), raw.strip(), f'Git would change frozen evidence bytes: {relative}')

    def test_retained_evidence_matches_declared_sha256(self):
        evidence = Path(__file__).resolve().parents[1] / 'docs/validation/priority-calibration-evidence'
        inventory = json.loads((evidence / 'retained-inventory.json').read_text(encoding='utf-8'))
        for name, expected in inventory['files'].items():
            with self.subTest(file=name):
                self.assertEqual(hashlib.sha256((evidence / name).read_bytes()).hexdigest(), expected,
                                 f'Retained SHA-256 mismatch: {name}')
        assessment = json.loads((evidence / 'acceptance-assessment.json').read_text(encoding='utf-8'))
        for condition in assessment['conditions']:
            name = Path(condition['source']).name
            self.assertEqual(condition['source_sha256'].lower(), inventory['files'][name])

    def test_indexed_evidence_matches_declared_sha256(self):
        repo = Path(__file__).resolve().parents[1]
        relative = 'docs/validation/priority-calibration-evidence'
        inventory = json.loads((repo / relative / 'retained-inventory.json').read_text(encoding='utf-8'))
        for name, expected in inventory['files'].items():
            with self.subTest(file=name):
                blob = subprocess.check_output(['git', 'show', f':{relative}/{name}'], cwd=repo)
                self.assertEqual(hashlib.sha256(blob).hexdigest(), expected,
                                 f'Indexed SHA-256 mismatch: {name}')
