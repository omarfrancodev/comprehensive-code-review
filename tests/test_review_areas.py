"""ABCDE is coverage metadata in user reports; public review content stays unchanged."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from publication_fixtures import coverage_classification

from test_review_contract import MODULE_PATH, clean_record, contract, finding


def area_record():
    record = clean_record()
    record['schema_version'] = 2
    record['coverage']['areas'] = [
        {'area': 'A', 'status': 'covered', 'details': 'Inspected producer responsibilities',
         'material': False, 'finding_ids': []},
        {'area': 'B', 'status': 'covered', 'details': 'Inspected validation and consumer behavior',
         'material': False, 'finding_ids': []},
        {'area': 'C', 'status': 'covered', 'details': 'Inspected response and consumer contract',
         'material': False, 'finding_ids': []},
        {'area': 'D', 'status': 'not_applicable', 'details': 'No persistence in the selected flow',
         'material': False, 'finding_ids': []},
        {'area': 'E', 'status': 'not_applicable', 'details': 'No security or operational mechanism affected',
         'material': False, 'finding_ids': []},
    ]
    return record


class ReviewAreaValidationTests(unittest.TestCase):
    def test_named_subaspects_route_to_optional_dimension_references_without_schema_fields(self):
        root = Path(__file__).resolve().parents[1]
        catalog = (root / 'references/workflow/review-areas.md').read_text(encoding='utf-8')
        for name in ('design-testability.md', 'contracts-data.md', 'security-operation.md'):
            self.assertTrue((root / 'references/dimensions' / name).is_file())
            self.assertIn(name, catalog)
        record = area_record()
        self.assertEqual(contract.validate(record), [])
        self.assertNotIn('aspects', record['coverage']['areas'][0])

    def test_current_final_requires_one_row_per_area_and_accepts_no_score(self):
        record = area_record()
        self.assertEqual(contract.validate(record), [])
        del record['coverage']['areas']
        self.assertTrue(contract.validate(record))

    def test_incomplete_duplicate_and_malformed_rows_are_rejected(self):
        variants = [[], [None], [{'area': []}], area_record()['coverage']['areas'][:-1],
                    area_record()['coverage']['areas'] + [area_record()['coverage']['areas'][0]]]
        for rows in variants:
            with self.subTest(rows=rows):
                record = area_record()
                record['coverage']['areas'] = rows
                self.assertTrue(contract.validate(record))

    def test_nonapplicability_requires_reason_and_cannot_hide_material_gap(self):
        record = area_record()
        record['coverage']['areas'][3]['details'] = ''
        self.assertTrue(contract.validate(record))
        record = area_record()
        record['coverage']['areas'][3]['material'] = True
        self.assertTrue(contract.validate(record))

    def test_material_pending_area_precludes_approval_without_a_code_finding(self):
        record = area_record()
        record['coverage']['areas'][3].update(status='partial', material=True,
                                              details='Required transaction recovery remains unverified')
        self.assertTrue(any('verdict' in error for error in contract.validate(record)))
        record['verdict'] = 'insufficient_evidence'
        self.assertEqual(contract.validate(record), [])
        record['coverage']['verification'] = 'skipped'
        self.assertTrue(contract.validate(record))

    def test_confirmed_blocker_takes_precedence_over_material_area_gap(self):
        record = area_record()
        record['findings'] = [finding(blocking=True)]
        record['coverage']['areas'][1]['finding_ids'] = ['R001']
        record['coverage']['areas'][2].update(status='not_evaluated', material=True,
                                              details='Additional required consumer inaccessible')
        record['verdict'] = 'not_approvable'
        self.assertEqual(contract.validate(record), [])

    def test_covered_area_can_have_a_finding_without_duplicate_finding_objects(self):
        record = area_record()
        record['findings'] = [finding()]
        for row in record['coverage']['areas'][1:3]:
            row['finding_ids'] = ['R001']
        self.assertEqual(contract.validate(record), [])
        self.assertEqual(len(record['findings']), 1)
        record['coverage']['areas'][1]['finding_ids'] = ['missing']
        self.assertTrue(contract.validate(record))

    def test_rejected_or_duplicate_finding_references_are_not_matrix_evidence(self):
        for identifiers, status in ((['R001'], 'rejected'), (['R001', 'R001'], 'confirmed')):
            record = area_record()
            record['findings'] = [finding(status=status)]
            record['coverage']['areas'][1]['finding_ids'] = identifiers
            self.assertTrue(contract.validate(record))

    def test_no_risk_or_quality_rating_is_added_to_contract(self):
        record = area_record()
        record['risk'] = 'high'
        self.assertTrue(contract.validate(record))

    def test_current_workers_remain_minimal_without_full_matrix(self):
        record = area_record()
        packet = {key: record[key] for key in ('schema_version', 'scope', 'findings', 'checks')}
        packet.update(stage='discovery', coverage={'flows': ['consumer'], 'limitations': []})
        self.assertEqual(contract.validate(packet), [])

    def test_legacy_records_remain_valid_without_invented_coverage(self):
        legacy = clean_record()
        self.assertEqual(contract.validate(legacy), [])
        self.assertNotIn('ABCDE', contract.render(legacy))


class ReviewAreaRenderingTests(unittest.TestCase):
    def test_same_gap_in_matrix_and_limits_is_disclosed_once_as_material_without_mutation(self):
        record = area_record()
        detail = 'Required transaction recovery remains unverified'
        record['coverage']['areas'][3].update(status='partial', material=True, details=detail)
        record['coverage']['limitations'] = [{'detail': detail, 'material': False}]
        record['verdict'] = 'insufficient_evidence'
        snapshot = copy.deepcopy(record)
        from ccr.reporting.projections import publication_digest
        output = contract.render(record, audience='comment', publication_context={
            'source_sha256': publication_digest(record),
            'limitations': [{'index': 0, 'kind': 'validation', 'public_summary': None}]}, coverage_publication_context=coverage_classification(record))
        self.assertEqual(output.count(detail), 1)
        self.assertIn(detail + ' [material]', output)
        self.assertEqual(record, snapshot)

    def test_only_user_report_has_matrix_and_comment_is_unchanged(self):
        record = area_record()
        output = contract.render(record, audience='user')
        self.assertIn('### Matriz ABCDE', output)
        self.assertIn('Inspected producer responsibilities', output)
        self.assertLess(output.index('### Validación'), output.index('### Matriz ABCDE'))
        self.assertNotIn('Riesgo del cambio', output)
        self.assertEqual(contract.render(record, audience='comment', coverage_publication_context=coverage_classification(record)),
                         contract.render(clean_record(), audience='comment', coverage_publication_context=coverage_classification(clean_record())))

    def test_area_gap_still_appears_in_public_uncertainties(self):
        record = area_record()
        detail = 'Required transaction recovery remains unverified'
        record['coverage']['areas'][3].update(status='partial', material=True, details=detail)
        record['verdict'] = 'insufficient_evidence'
        output = contract.render(record, audience='comment', coverage_publication_context=coverage_classification(record))
        self.assertIn(detail, output)
        self.assertNotIn('### Matriz ABCDE', output)

    def test_matrix_orders_rows_escapes_cells_and_preserves_record(self):
        record = area_record()
        record['coverage']['areas'].reverse()
        record['coverage']['areas'][0]['details'] = 'static | path\nsecond line'
        snapshot = copy.deepcopy(record)
        output = contract.render(record)
        self.assertIn('static \\| path second line', output)
        self.assertLess(output.index('| A —'), output.index('| E —'))
        self.assertEqual(record, snapshot)


class ReviewAreaCLITests(unittest.TestCase):
    def test_current_record_renders_matrix_for_user_only_and_rejects_incomplete_matrix(self):
        with tempfile.TemporaryDirectory(prefix='review-areas-') as directory:
            path = Path(directory) / 'record.json'
            record = area_record()
            path.write_text(json.dumps(record), encoding='utf-8')
            prefix = [sys.executable, '-B', str(MODULE_PATH), 'contract']
            coverage_path = Path(directory) / 'coverage.json'
            coverage_path.write_text(json.dumps(coverage_classification(record)), encoding='utf-8')
            for audience, present in (('render-user', True), ('render-comment', False)):
                extra = ['--coverage-publication-context', str(coverage_path)] if audience == 'render-comment' else []
                result = subprocess.run(prefix + [audience, '--input', str(path)] + extra,
                                        capture_output=True, text=True, encoding='utf-8')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual('### Matriz ABCDE' in result.stdout, present)
            record['coverage']['areas'].pop()
            path.write_text(json.dumps(record), encoding='utf-8')
            result = subprocess.run(prefix + ['render-user', '--input', str(path)],
                                    capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, '')


if __name__ == '__main__':
    unittest.main()
