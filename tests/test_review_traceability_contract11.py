import copy
import unittest
from script_test_support import enable_package_imports

enable_package_imports()
from ccr.contracts import review, identifiers, packets, provenance, receipts
from traceability_fixtures import record11, set_dimension, receipt2_bundle
from recovery_fixtures import record10
from test_review_contract import finding


class Contract11Tests(unittest.TestCase):
    def test_new_contract_requires_purpose_and_dimensions_without_changing_10(self):
        self.assertEqual(review.validate(record10()), [])
        for profile in ('focused', 'standard', 'deep', 'extended'):
            for source in ('automatic', 'explicit'):
                self.assertEqual(review.validate(record11(profile, source)), [])
        value = record11()
        del value['checks'][0]['purpose']
        self.assertTrue(any('purpose' in e for e in review.validate(value)))
        value = record11()
        value['coverage']['areas'][0]['dimensions'].pop()
        self.assertTrue(any('dimensions' in e for e in review.validate(value)))

    def test_material_gap_and_typed_identifier_allocation(self):
        value = record11()
        set_dimension(value, 'E05', status='partial', material=True)
        self.assertTrue(any('verdict' in e for e in review.validate(value)))
        value['verdict'] = 'insufficient_evidence'
        self.assertEqual(review.validate(value), [])
        value = record11()
        value['findings'] = [dict(finding(), id='D1-F001')]
        set_dimension(value, 'B01', finding_ids=['D1-F001'])
        allocated, sources = identifiers.canonicalize_ids(value)
        self.assertEqual(sources['findings']['D1-F001'], 'F001')
        self.assertEqual(allocated['coverage']['areas'][1]['dimensions'][0]['finding_ids'], ['F001'])
        self.assertEqual(review.validate(allocated), [])

    def test_profile_and_executor_guards_are_not_skipped_for_11(self):
        value = record11()
        value['coverage']['execution']['profile_history'] = []
        self.assertTrue(review.validate(value))
        value = record11()
        value['checks'][0]['execution'] = {'kind': 'local', 'executor': 'X1'}
        self.assertTrue(provenance.validate_check_sources(value, []))

    def test_historical_reuse_does_not_require_a_new_local_receipt(self):
        value = record11()
        url = 'https://example.test/reviews/previous/review.json'
        value['previous_reviews'] = [dict(review_id='CR-' + 'b' * 20, reference=url, verified=True)]
        value['checks'][0].update(reused=True, reuse_reason='Mismos inputs verificados',
            reference=url + '#C001', execution={'kind': 'reused', 'executor': None})
        self.assertEqual(review.validate(value), [])

    def test_merge11_keeps_purpose_without_changing_packet1(self):
        value = record11()
        context = dict(context_id='ctx', scope=value['scope'], checks=value['checks'], check_schema_version=11)
        packet = dict(packet_version=1, stage='discovery', context_id='ctx', findings=[],
            check_ids=['C001'], coverage=dict(flows=['Inspección'], limitations=[]))
        original = copy.deepcopy(context)
        result = packets.merge(context, [packet])
        self.assertEqual(result['checks'][0]['purpose'], value['checks'][0]['purpose'])
        self.assertEqual(context, original)
        del context['checks'][0]['purpose']
        with self.assertRaises(ValueError):
            packets.merge(context, [packet])
        context['check_schema_version'] = True
        with self.assertRaises(ValueError):
            packets.merge(context, [packet])

    def test_new_local_cannot_accredit_purpose_with_receipt1(self):
        import json
        receipt, sources, check, executors = receipt2_bundle()
        receipt['schema_version'] = 1
        del receipt['purpose']
        reference = 'evidence/attempt-C001-receipt.json'
        check.update(reused=False, reference=reference)
        sources[reference] = json.dumps(receipt).encode()
        issues = receipts.validate_record_receipts({'schema_version': 11, 'checks': [check]}, sources, executors)
        self.assertTrue(any('purpose' in issue['message'] for issue in issues))
