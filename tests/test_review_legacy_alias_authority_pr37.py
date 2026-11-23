"""Historical aliases preserve claim continuity and the original authority."""
import copy
import unittest

from test_review_assessment import NOTE, PROOF, assessed, followup, guided_current, rendered
from test_review_assessment_lineage import following, root_v2
from ccr.contracts import review
from ccr.contracts.assessment import verify_sources


def authorization(previous, identifier, member, decision):
    return dict(id=identifier, member_id=member, review_id=previous['review_id'],
                scope={key: previous['scope'][key] for key in ('base', 'head', 'snapshot')},
                decision=copy.deepcopy(decision))


def adopt_v1(previous):
    current, sources = followup(previous)
    assessment = current['assessment']
    resolution = assessment['findings'][0]['resolution']
    grant = authorization(previous, 'AU001', 'F001', resolution)
    resolution['authorization_id'] = 'AU001'
    assessment.update(schema_version=3, history_incomplete=False, authorizations=[grant],
        observed_hashes=sorted({assessment['previous']['source']['sha256'],
                                assessment['scope']['delta'][0]['sources'][0]['sha256'],
                                resolution['source']['sha256']}),
        lineage=[dict(id='F001', cause='duplicate-delivery', survivor='F001',
                      title=current['findings'][0]['title'], last_status='confirmed',
                      resolution=copy.deepcopy(resolution))]
                 + [dict(id=alias, cause=None, survivor='F001', title=None, last_status='confirmed',
                         resolution=copy.deepcopy(resolution)) for alias in previous['aliases']])
    return current, sources


class LegacyAliasAuthorityTests(unittest.TestCase):
    def test_guided_fixture_keeps_one_debt_from_v1_through_two_v3_generations(self):
        previous = assessed()
        previous['aliases'] = {'F002': 'F001'}
        current, sources = followup(previous)
        guided_current(current, previous)
        later, later_sources = following(current, 'c')
        guided_current(later, current)
        for record, selected in ((current, sources), (later, later_sources)):
            with self.subTest(review_id=record['review_id']):
                self.assertEqual([(item['id'], item['member_id'])
                                  for item in record['assessment']['authorizations']], [('AU001', 'F001')])
                self.assertEqual(review.validate(record), [])
                verify_sources(record, selected.__getitem__, captured_inputs={'sources': {}})
                self.assertEqual(rendered(record, 'user').count('Writes stay disabled'), 1)

    def test_guided_fixture_preserves_an_existing_v3_alias_authorization_link(self):
        previous = assessed()
        previous['aliases'] = {'F002': 'F001'}
        adopted, _ = adopt_v1(previous)
        current, sources = following(adopted, 'c')
        guided_current(current, adopted)
        self.assertEqual(review.validate(current), [])
        verify_sources(current, sources.__getitem__, captured_inputs={'sources': {}})
        self.assertEqual(current['assessment']['authorizations'], adopted['assessment']['authorizations'])

    def test_single_original_authorization_survives_followups_and_renders_one_debt(self):
        previous = assessed()
        previous['aliases'] = {'F002': 'F001', 'F003': 'F001'}
        self.assertEqual(review.validate(previous), [])
        verify_sources(previous, {'evidence/note.txt': NOTE, 'evidence/proof.txt': PROOF}.__getitem__)
        current, sources = adopt_v1(previous)
        later, later_sources = following(current, 'c')
        for record, selected in ((current, sources), (later, later_sources)):
            with self.subTest(review_id=record['review_id']):
                self.assertEqual(review.validate(record), [])
                verify_sources(record, selected.__getitem__, captured_inputs={'sources': {}})
                self.assertEqual(record['aliases'], {'F002': 'F001', 'F003': 'F001'})
                report = rendered(record, 'user')
                self.assertEqual(report.count('Deuda aceptada'), 1)
                self.assertEqual(report.count('Writes stay disabled'), 1)

    def test_copied_v1_alias_disposition_cannot_accredit_its_own_grant(self):
        previous = assessed()
        previous['aliases'] = {'F002': 'F001'}
        current, sources = adopt_v1(previous)
        assessment = current['assessment']
        original = assessment['authorizations'][0]
        copied = dict(copy.deepcopy(original), id='AU002', member_id='F002')
        assessment['authorizations'].append(copied)
        assessment['lineage'][1]['resolution']['authorization_id'] = 'AU002'
        resolution = assessment['findings'][0]['resolution']
        assessment['findings'][0]['resolution'] = [
            resolution, dict(copy.deepcopy(resolution), authorization_id='AU002')]
        self.assertEqual(review.validate(current), [])
        with self.assertRaisesRegex(ValueError, 'reopening|authorization'):
            verify_sources(current, sources.__getitem__, captured_inputs={'sources': {}})

    def test_v2_published_member_decisions_keep_separate_grants_even_when_identical(self):
        original = root_v2(two=True)
        first, second = original['assessment']['lineage']
        second['resolution'] = copy.deepcopy(first['resolution'])
        original['assessment']['findings'][1]['resolution'] = copy.deepcopy(first['resolution'])
        original['assessment']['observed_hashes'] = sorted(
            {first['resolution']['source']['sha256'],
             original['assessment']['scope']['delta'][0]['sources'][0]['sha256']})
        previous, published_sources = following(original, 'b')
        previous['assessment']['lineage'][1]['survivor'] = 'F001'
        previous['findings'].pop()
        previous['rereview'].pop()
        previous['assessment']['findings'].pop()
        previous['aliases'] = {'F002': 'F001'}
        self.assertEqual(review.validate(previous), [])
        verify_sources(previous, published_sources.__getitem__, captured_inputs={'sources': {}})

        current, sources = following(previous, 'c')
        assessment = current['assessment']
        assessment.update(schema_version=3, history_incomplete=True,
            authorizations=[authorization(previous, 'AU001', 'F001', first['resolution']),
                            authorization(previous, 'AU002', 'F002', second['resolution'])])
        for member, identifier in zip(assessment['lineage'], ('AU001', 'AU002')):
            member['resolution']['authorization_id'] = identifier
        assessment['findings'][0]['resolution'] = [
            copy.deepcopy(member['resolution']) for member in assessment['lineage']]
        self.assertEqual(review.validate(current), [])
        verify_sources(current, sources.__getitem__, captured_inputs={'sources': {}})


if __name__ == '__main__':
    unittest.main()
