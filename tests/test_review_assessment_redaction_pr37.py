"""Redacted accepted conditions retain each source decision's identity."""
import copy
import json
from pathlib import Path
import subprocess
import unittest

from test_review_assessment import NOTE, PROOF, source
from test_review_assessment_projection2 import grouped_record
import test_review_compact_archive as fixtures
from ccr.archive import compact
from ccr.contracts import review
from ccr.contracts.check_disclosure import input_identity_for
from ccr.reporting import delivery
from ccr.reporting.text_projection import _Projection
from ccr.shared.git import repository_identity
from ccr.workflow.builders import build_check_disclosure


PRIVATE_PATHS = ('/private/tenant-alpha/settings', '/private/tenant-beta/settings')


def private_conditions_record():
    record = grouped_record()
    decisions = record['assessment']['findings'][0]['resolution']
    for index, decision in enumerate(decisions):
        decision['source'] = source('note.txt', NOTE)
        decision['conditions'] = ['Writes stay disabled at ' + PRIVATE_PATHS[index],
                                  'Keep the existing read-only policy']
        record['assessment']['lineage'][index]['resolution'] = copy.deepcopy(decision)
    record['assessment']['observed_hashes'] = sorted({
        source('note.txt', NOTE)['sha256'], source('proof.txt', PROOF)['sha256']})
    return record


class AssessmentRedactionPr37Tests(unittest.TestCase):
    def test_portable_conditions_distinguish_same_note_decisions_and_match_lineage(self):
        record = private_conditions_record()
        original = copy.deepcopy(record)
        self.assertEqual(review.validate(record), [])
        disclosure = build_check_disclosure(record, input_identity_for(record), {}, {})
        portable = _Projection(record, {}, '', 'a' * 64, check_disclosure_context=disclosure,
                               check_disclosure_sources={}).value(record)
        self.assertEqual(review.validate(portable), [])
        decisions = portable['assessment']['findings'][0]['resolution']
        self.assertNotEqual(decisions[0], decisions[1])
        self.assertEqual(decisions[0]['source'], decisions[1]['source'])
        for index, decision in enumerate(decisions):
            self.assertEqual(len(decision['conditions']), 2)
            self.assertEqual(decision['conditions'][1], 'Keep the existing read-only policy')
            self.assertEqual(decision, portable['assessment']['lineage'][index]['resolution'])
            self.assertIn('Writes stay disabled at', decision['conditions'][0])
        for private in PRIVATE_PATHS:
            self.assertNotIn(private, json.dumps(portable))
        self.assertEqual(record, original)
        duplicate = copy.deepcopy(portable)
        duplicate['assessment']['findings'][0]['resolution'][1] = copy.deepcopy(decisions[0])
        self.assertTrue(any('distinct list' in error for error in review.validate(duplicate)))


class AssessmentRedactionDeliveryPr37Tests(unittest.TestCase):
    setUp = fixtures.CompactPrepareTests.setUp
    prepare = fixtures.CompactPrepareTests.prepare
    record_and_sources = fixtures.CompactPrepareTests.record_and_sources

    def test_full_and_brief_export_each_private_condition_without_changing_source(self):
        repo = self.root / 'repo'
        repo.mkdir()
        subprocess.run(['git', 'init', '-q', str(repo)], check=True, capture_output=True)
        inputs = dict(self.inputs, sources={'evidence/note.txt': source('note.txt', NOTE)['sha256']})
        prepared = self.prepare(inputs=inputs, repo_identity=repository_identity(repo),
                                archive_root=self.root / 'archive')
        fresh, selected = self.record_and_sources(prepared)
        record = private_conditions_record()
        record['aliases'] = {}
        record['assessment']['lineage'] = record['assessment']['lineage'][:1]
        record['assessment']['lineage'][0]['resolution'] = copy.deepcopy(
            record['assessment']['findings'][0]['resolution'])
        record['review_id'] = fresh['review_id']
        record['coverage']['execution'] = fresh['coverage']['execution']
        selected.update({'evidence/note.txt': NOTE, 'evidence/proof.txt': PROOF})
        saved = compact.create_compact(prepared, record, current_inputs=inputs, sources=selected)
        run = Path(saved['run_dir'])
        before = {str(path.relative_to(run)): path.read_bytes() for path in run.rglob('*') if path.is_file()}
        for mode in ('full', 'brief'):
            with self.subTest(mode=mode):
                target = delivery.deliver(run, mode, repo, repo / mode)
                report = (target / ('informe.md' if mode == 'full' else 'resumen.md')).read_text(encoding='utf-8')
                self.assertEqual(report.count('Condición: Writes stay disabled at'), 2)
                self.assertEqual(report.count('Condición: Keep the existing read-only policy'), 2)
                conditions = [line for line in report.splitlines() if 'Condición: Writes stay disabled at' in line]
                self.assertNotEqual(conditions[0], conditions[1])
                contents = '\n'.join(path.read_text(encoding='utf-8') for path in target.iterdir())
                for private in (*PRIVATE_PATHS, 'tenant-alpha', 'tenant-beta', 'evidence/note.txt'):
                    self.assertNotIn(private, contents)
                if mode == 'full':
                    portable = json.loads((target / 'review.json').read_bytes())
                    self.assertEqual(review.validate(portable), [])
                self.assertEqual(before, {str(path.relative_to(run)): path.read_bytes()
                                          for path in run.rglob('*') if path.is_file()})
