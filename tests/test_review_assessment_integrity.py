"""Regression coverage for current claims and source-bound terminal decisions."""
import unittest

from test_review_assessment import NOTE, PROOF, assessed, followup, source
from ccr.contracts import review
from ccr.contracts.assessment import verify_sources


def terminal_followup(status):
    previous = assessed()
    previous['assessment']['findings'][0]['resolution'] = None
    current, sources = followup(previous)
    current['findings'] = []
    current['rereview'][0]['status'] = status
    return current, sources


class AssessmentIntegrityTests(unittest.TestCase):
    def test_still_valid_requires_a_retained_confirmed_finding(self):
        current, _ = followup()
        self.assertEqual(review.validate(current), [])
        current['findings'] = []
        self.assertTrue(any('follow-up outcome' in error for error in review.validate(current)))

    def test_terminal_outcomes_reject_only_inconclusive_check_evidence(self):
        unusable = [('blocked', None, False), ('not_run', None, False),
                    ('failed', 'fixture', False), ('failed', 'environment', False),
                    ('passed', None, True), ('failed', 'product', True)]
        for outcome in ('resolved', 'withdrawn'):
            for status, failure_kind, reused in unusable:
                with self.subTest(outcome=outcome, status=status, failure_kind=failure_kind, reused=reused):
                    current, _ = terminal_followup(outcome)
                    check = current['checks'][0]
                    check.update(status=status, failure_kind=failure_kind, reused=reused,
                        reuse_reason='Previously observed execution' if reused else None,
                        reference='evidence/proof.txt' if reused else None)
                    current['coverage']['evidence'][0].update(kind='check', check_id='C001')
                    self.assertTrue(any('decisive' in error for error in review.validate(current)))

    def test_terminal_outcomes_accept_a_decisive_static_observation(self):
        for outcome in ('resolved', 'withdrawn'):
            with self.subTest(outcome=outcome):
                current, sources = terminal_followup(outcome)
                self.assertEqual(review.validate(current), [])
                verify_sources(current, sources.__getitem__)

    def test_terminal_outcomes_accept_a_current_product_check(self):
        for outcome in ('resolved', 'withdrawn'):
            for status, failure_kind in (('passed', None), ('failed', 'product')):
                with self.subTest(outcome=outcome, status=status):
                    current, sources = terminal_followup(outcome)
                    current['checks'][0].update(status=status, failure_kind=failure_kind)
                    current['coverage']['evidence'][0].update(kind='check', check_id='C001')
                    self.assertEqual(review.validate(current), [])
                    verify_sources(current, sources.__getitem__)

    def test_static_proof_suffices_alongside_a_blocked_check(self):
        current, sources = terminal_followup('resolved')
        current['checks'][0]['status'] = 'blocked'
        current['coverage']['evidence'].append(dict(current['coverage']['evidence'][0],
            id='EV002', kind='check', check_id='C001'))
        current['assessment']['scope']['delta'][0]['evidence_ids'].append('EV002')
        current['assessment']['findings'][0]['verification']['evidence_ids'].append('EV002')
        self.assertEqual(review.validate(current), [])
        verify_sources(current, sources.__getitem__)

    def test_every_local_delta_observation_requires_its_source_descriptor(self):
        current = assessed()
        current['coverage']['evidence'].append(dict(current['coverage']['evidence'][0],
            id='EV002', reference='evidence/second.txt'))
        delta = current['assessment']['scope']['delta'][0]
        delta['evidence_ids'].append('EV002')
        self.assertTrue(any('.sources' in error for error in review.validate(current)))
        delta['sources'].append(source('second.txt', b'A second inspected source.'))
        self.assertEqual(review.validate(current), [])
        delta['sources'] = []
        self.assertTrue(any('.sources' in error for error in review.validate(current)))

    def test_source_binding_preserves_exact_observation_fragments(self):
        current = assessed()
        current['coverage']['evidence'][0]['reference'] = 'evidence/proof.json#/first'
        current['coverage']['evidence'].append(dict(current['coverage']['evidence'][0],
            id='EV002', reference='evidence/proof.json#/second'))
        delta = current['assessment']['scope']['delta'][0]
        delta['evidence_ids'].append('EV002')
        proof = b'{"first": "inspected", "second": "also inspected"}'
        descriptor = source('proof.json', proof)
        descriptor['reference'] += '#/first'
        delta['sources'] = [descriptor]
        self.assertTrue(any('.sources' in error for error in review.validate(current)))
        delta['sources'].append(dict(descriptor, reference='evidence/proof.json#/second'))
        self.assertEqual(review.validate(current), [])
        verify_sources(current, {'evidence/proof.json': proof, 'evidence/note.txt': NOTE}.__getitem__)

    def test_delta_descriptor_hash_must_match_selected_bytes(self):
        current = assessed()
        self.assertEqual(review.validate(current), [])
        with self.assertRaisesRegex(ValueError, 'SHA-256'):
            verify_sources(current, {'evidence/proof.txt': b'Other bytes',
                                     'evidence/note.txt': NOTE}.__getitem__)

    def test_unbound_prior_observation_cannot_be_replayed_as_new_reopening_proof(self):
        previous = assessed()
        previous['assessment']['scope']['delta'][0]['sources'] = []
        current, sources = followup(previous)
        row = current['assessment']['findings'][0]
        row['resolution'] = None
        row['reopening'] = dict(reason='condition_changed', detail='Writes were enabled',
            condition='Writes stay disabled', evidence_id='EV001', source=source('proof.txt', PROOF))
        with self.assertRaises(ValueError):
            verify_sources(current, sources.__getitem__)


if __name__ == '__main__':
    unittest.main()
