import copy
import unittest

from script_test_support import enable_package_imports

enable_package_imports()
from ccr.contracts import dimensions
from ccr.contracts import execution, identifiers, provenance, receipts, review
from ccr.contracts.semantic_references import validate_semantic_references
from profile_topology_fixtures import record12, source_fixture12


def group(ids, status='covered', reason=None, evidence_ids=None, finding_ids=None, material=False):
    return {'ids': list(ids), 'status': status, 'reason': reason,
            'evidence_ids': ['EV001'] if evidence_ids is None else evidence_ids,
            'finding_ids': [] if finding_ids is None else finding_ids, 'material': material}


def areas():
    return [{'area': code, 'applicability': 'applicable', 'applicability_reason': None,
             'groups': [group(ids)]} for code, ids in dimensions.DIMENSIONS.items()]


def record13(profile='focused'):
    value = record12(profile, discovery=1 if profile == 'focused' else 2, verification=1)
    value['schema_version'] = 13
    value['coverage']['areas'] = areas()
    value['coverage']['evidence'] = [
        {'id': 'EV001', 'kind': 'static', 'detail': 'Inspección del flujo',
         'check_id': None, 'reference': 'src/handler.py:12'}]
    return value


class Coverage13Tests(unittest.TestCase):
    def validate(self, value, finding_ids=None, evidence_ids=None):
        return dimensions.validate_coverage13(value, finding_ids or set(),
                                               {'EV001'} if evidence_ids is None else evidence_ids)

    def test_grouped_decisions_cover_all_catalog_ids_with_shared_evidence(self):
        value = areas()
        self.assertEqual(self.validate(value), [])
        self.assertEqual(dimensions.summarize_area13(value[0]),
                         {'status': 'covered', 'material': False, 'finding_ids': []})

    def test_missing_and_duplicate_ids_cannot_certify_coverage(self):
        value = areas()
        value[0]['groups'][0]['ids'] = ['A01']
        self.assertTrue(self.validate(value))
        value = areas()
        value[0]['groups'].append(group(['A01']))
        self.assertTrue(self.validate(value))
        value = areas()
        value[0]['groups'][0]['ids'][0] = 'B01'
        self.assertTrue(self.validate(value))

    def test_unknown_aspects_prevent_covered_and_material_gap_is_preserved(self):
        value = areas()
        value[0]['groups'] = [group(['A01'], finding_ids=['F001']),
                              group(['A02', 'A03', 'A04', 'A05'], status='not_evaluated',
                                    reason='Pendiente', evidence_ids=[], material=True)]
        self.assertEqual(self.validate(value, {'F001'}), [])
        self.assertEqual(dimensions.summarize_area13(value[0]),
                         {'status': 'partial', 'material': True, 'finding_ids': ['F001']})

    def test_nonapplicable_groups_need_reason_and_have_no_findings_or_material_gap(self):
        value = areas()
        value[3].update(applicability='not_applicable', applicability_reason='Sin persistencia',
                        groups=[group(dimensions.DIMENSIONS['D'], status='not_applicable',
                                      reason='Sin cambios de datos', evidence_ids=[])])
        self.assertEqual(self.validate(value), [])
        self.assertEqual(dimensions.summarize_area13(value[3])['status'], 'not_applicable')
        for invalid in ({'reason': None}, {'material': True}, {'finding_ids': ['F001']}):
            changed = copy.deepcopy(value)
            changed[3]['groups'][0].update(invalid)
            self.assertTrue(self.validate(changed, {'F001'}))

    def test_missing_evidence_and_unknown_finding_are_rejected(self):
        value = areas()
        self.assertTrue(self.validate(value, evidence_ids=set()))
        value[0]['groups'][0]['finding_ids'] = ['F999']
        self.assertTrue(self.validate(value))

    def test_undetermined_area_remains_not_evaluated(self):
        value = areas()
        value[0].update(applicability='undetermined', applicability_reason='Faltan requisitos')
        self.assertEqual(dimensions.summarize_area13(value[0])['status'], 'not_evaluated')

    def test_invalid_input_is_diagnostic_not_exception(self):
        for value in (None, {}, [None], [{'area': []}], [{'area': 'A', 'groups': None}]):
            with self.subTest(value=value):
                self.assertTrue(self.validate(value))

    def test_shared_evidence_has_canonical_identity_and_real_check_reference(self):
        rows = [{'id': 'EV001', 'kind': 'static', 'detail': 'Inspección del flujo',
                 'check_id': None, 'reference': 'src/handler.py:12'},
                {'id': 'EV002', 'kind': 'check', 'detail': 'Prueba del flujo',
                 'check_id': 'C001', 'reference': None}]
        self.assertEqual(dimensions.validate_evidence13(rows, {'C001'}), [])
        for index, updates in ((0, {'id': 'EV000'}), (0, {'check_id': 'C001'}),
                               (1, {'check_id': 'C002'}), (1, {'detail': ' '}),
                               (1, {'reference': 42}), (1, {'id': 'EV001'})):
            changed = copy.deepcopy(rows)
            changed[index].update(updates)
            with self.subTest(updates=updates):
                self.assertTrue(dimensions.validate_evidence13(changed, {'C001'}))

    def test_shared_evidence_malformed_values_produce_diagnostics(self):
        for value in (None, {}, [None], [{'id': 'EV001'}]):
            with self.subTest(value=value):
                self.assertTrue(dimensions.validate_evidence13(value, set()))

    def test_canonical_record_inherits_schema12_guards(self):
        value = record13()
        self.assertEqual(review.validate(value), [])
        invalid = copy.deepcopy(value)
        invalid['checks'][0]['execution'] = {'kind': 'local', 'executor': None}
        self.assertTrue(any('executor' in error for error in review.validate(invalid)))
        self.assertTrue(provenance.validate_check_execution(invalid))
        invalid = copy.deepcopy(value)
        invalid['coverage']['execution']['profile_history'] = []
        self.assertTrue(execution.validate_profile_execution(invalid))

    def test_record_material_gap_and_missing_evidence(self):
        value = record13()
        value['coverage']['areas'][0]['groups'] = [
            group(['A01']), group(['A02', 'A03', 'A04', 'A05'],
                                 status='not_evaluated', reason='Pendiente',
                                 evidence_ids=[], material=True)]
        self.assertTrue(any('verdict' in error for error in review.validate(value)))
        value['verdict'] = 'insufficient_evidence'
        self.assertEqual(review.validate(value), [])
        value['coverage']['evidence'] = []
        self.assertTrue(review.validate(value))

    def test_undetermined_area_with_covered_group_is_not_inferred_covered(self):
        value = record13()
        value['coverage']['areas'][0].update(applicability='undetermined',
                                               applicability_reason='Faltan requisitos')
        self.assertEqual(review.validate(value), [])
        self.assertEqual(dimensions.summarize_area13(value['coverage']['areas'][0])['status'],
                         'not_evaluated')

    def test_semantic_gate_checks_group_and_shared_evidence_claims(self):
        value = record13()
        value['coverage']['evidence'][0]['detail'] = 'C999 proves the flow'
        value['coverage']['areas'][0]['groups'][0].update(
            status='partial', reason='C998 was unavailable')
        issues = validate_semantic_references(value, [], None, {})
        self.assertTrue(any(row['reference'] == 'C999' for row in issues))
        self.assertTrue(any(row['reference'] == 'C998' for row in issues))

    def test_atomic_identifier_allocation_updates_group_findings_and_evidence_checks(self):
        from test_review_contract import finding
        value = record13()
        value['findings'] = [dict(finding(), id='D1-F001')]
        value['coverage']['areas'][0]['groups'][0]['finding_ids'] = ['D1-F001']
        value['checks'][0]['id'] = 'D1-C001'
        value['coverage']['evidence'][0].update(kind='check', check_id='D1-C001')
        result, mapping = identifiers.canonicalize_ids(value)
        self.assertEqual(result['coverage']['areas'][0]['groups'][0]['finding_ids'], [mapping['findings']['D1-F001']])
        self.assertEqual(result['coverage']['evidence'][0]['check_id'], mapping['checks']['D1-C001'])

    def test_local_schema13_check_requires_purpose_bound_receipt(self):
        import json
        from traceability_fixtures import receipt2_bundle
        receipt, sources, check, executors = receipt2_bundle()
        receipt['schema_version'] = 1
        del receipt['purpose']
        reference = 'evidence/attempt-C001-receipt.json'
        check.update(reused=False, reference=reference)
        sources[reference] = json.dumps(receipt).encode()
        issues = receipts.validate_record_receipts({'schema_version': 13, 'checks': [check]}, sources, executors)
        self.assertTrue(any('purpose' in issue['message'] for issue in issues))

    def test_standard_material_group_requires_independent_verification(self):
        value = record13()
        source = record12('standard', discovery=1, verification=0)
        value.update(profile='standard', profile_reason=source['profile_reason'])
        value['coverage']['execution'] = source['coverage']['execution']
        value['coverage']['verification'] = 'skipped'
        value['coverage']['areas'][0]['groups'] = [
            group(['A01']), group(['A02', 'A03', 'A04', 'A05'],
                                 status='not_evaluated', reason='Pendiente',
                                 evidence_ids=[], material=True)]
        value['verdict'] = 'insufficient_evidence'
        self.assertTrue(any('independence' in error or 'verification' in error
                            for error in execution.validate_execution(value)))
        context, events, refs = source_fixture12(value)
        self.assertTrue(execution.validate_execution_sources(value, context, events, refs))

if __name__ == '__main__':
    unittest.main()
