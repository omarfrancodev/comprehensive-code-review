"""Published identity, material outcome and member decisions survive follow-ups."""
import copy
import hashlib
import unittest

from test_review_assessment import NOTE, PROOF, assessed, followup, guided_current, source, two_published_findings
from ccr.contracts import review
from ccr.contracts.assessment import verify_sources
from ccr.shared.encoding import archive_bytes


SECOND_NOTE = b'Owner also accepts the duplicate while the subscriber remains read-only.'
FRESH = b'New supported caller now writes and exposes the duplicate event.'


def root_v2(*, debt=True, two=False):
    record = two_published_findings() if two else assessed()
    rows = record['assessment']['findings']
    if not debt:
        rows[0]['resolution'] = None
    if two:
        rows[1]['resolution'].update(source=source('second-note.txt', SECOND_NOTE),
                                     conditions=['Subscriber remains read-only'])
    record['assessment'].update(schema_version=2, lineage=[dict(
        id=row['id'], cause=row['cause'], survivor=row['id'],
        title=record['findings'][i]['title'], last_status='confirmed',
        resolution=copy.deepcopy(row['resolution'])) for i, row in enumerate(rows)],
        observed_hashes=sorted({hashlib.sha256(PROOF).hexdigest()}
            | ({hashlib.sha256(NOTE).hexdigest()} if debt else set())
            | ({hashlib.sha256(SECOND_NOTE).hexdigest()} if two else set())))
    return record


def following(previous, digit):
    raw = archive_bytes(previous)
    current = copy.deepcopy(previous)
    current['review_id'] = 'CR-' + digit * 20
    current['presentation']['kind'] = 'rereview'
    reference = 'https://example.org/pr/42#previous'
    current['previous_reviews'] = [dict(review_id=previous['review_id'], reference=reference, verified=True)]
    current['rereview'] = [dict(id=row['id'], status='still_valid', details='Inspected the same claim',
        previous_review_id=previous['review_id'], previous_reference=reference,
        previous_finding_id=row['id'], previous_title=row['title'], previous_url=None, check_ids=[])
        for row in previous['findings']]
    current['assessment']['previous'] = dict(review_id=previous['review_id'], source=source('prior.json', raw))
    current['assessment']['observed_hashes'] = sorted(
        set(previous['assessment']['observed_hashes']) | {hashlib.sha256(raw).hexdigest()})
    return current, {'evidence/prior.json': raw, 'evidence/proof.txt': PROOF,
                     'evidence/note.txt': NOTE, 'evidence/second-note.txt': SECOND_NOTE}


def root_current(*, debt=True, two=False):
    return guided_current(root_v2(debt=debt, two=two))


def track(current, previous, status):
    current['rereview'] = [dict(id='F001', status=status, details='Published claim follow-up',
        previous_review_id=previous['review_id'], previous_reference=current['previous_reviews'][0]['reference'],
        previous_finding_id='F001', previous_title=previous['assessment']['lineage'][0]['title'],
        previous_url=None, check_ids=[])]


def terminal_chain(status):
    original = root_current(debt=False)
    terminal, sources = following(original, 'd')
    terminal['findings'] = []
    terminal['rereview'][0]['status'] = status
    terminal['assessment']['lineage'][0]['last_status'] = status
    return terminal, sources


class AssessmentLineageTests(unittest.TestCase):
    def test_v3_preserves_terminal_material_outcome_through_not_reevaluated(self):
        for status in ('resolved', 'withdrawn'):
            with self.subTest(status=status):
                terminal, sources = terminal_chain(status)
                self.assertEqual(review.validate(terminal), [])
                verify_sources(terminal, sources.__getitem__)
                bounded, sources = following(terminal, 'b')
                track(bounded, terminal, 'not_reevaluated')
                bounded['assessment']['findings'][0].update(relation='outside_scope', verification=None)
                verify_sources(bounded, sources.__getitem__)
                self.assertEqual(bounded['assessment']['lineage'][0]['last_status'], status)
                revived, sources = following(bounded, 'c')
                revived['findings'] = copy.deepcopy(root_current(debt=False)['findings'])
                revived['assessment']['findings'] = copy.deepcopy(root_current(debt=False)['assessment']['findings'])
                track(revived, bounded, 'still_valid')
                revived['assessment']['lineage'][0]['last_status'] = 'confirmed'
                self.assertEqual(review.validate(revived), [])
                with self.assertRaisesRegex(ValueError, 'reopening'):
                    verify_sources(revived, sources.__getitem__)

    def test_omitted_terminal_keeps_its_id_and_cause_reserved(self):
        terminal, _ = terminal_chain('resolved')
        omitted, sources = following(terminal, 'b')
        omitted['assessment']['findings'] = []
        verify_sources(omitted, sources.__getitem__)
        self.assertEqual(omitted['assessment']['lineage'][0]['last_status'], 'resolved')
        for identifier, cause in (('F001', 'unrelated-cause'), ('F002', 'duplicate-delivery')):
            with self.subTest(identifier=identifier, cause=cause):
                current, sources = following(omitted, 'c')
                seed = root_current(debt=False)
                current['findings'] = [dict(seed['findings'][0], id=identifier)]
                current['assessment']['findings'] = [dict(seed['assessment']['findings'][0],
                    id=identifier, cause=cause)]
                current['rereview'] = [dict(id=identifier, status='new', details='New independent report',
                    previous_review_id=None, previous_reference=None, previous_finding_id=None,
                    previous_title=None, previous_url=None, check_ids=[])]
                entry = dict(seed['assessment']['lineage'][0], id=identifier, survivor=identifier, cause=cause)
                if identifier == 'F001':
                    current['assessment']['lineage'] = [entry]
                else:
                    current['assessment']['lineage'].append(entry)
                with self.assertRaisesRegex(ValueError, 'cause|published ID'):
                    verify_sources(current, sources.__getitem__)

    def test_two_member_decisions_survive_consolidation_and_another_generation(self):
        previous = root_current(two=True)
        current, sources = following(previous, 'b')
        first, second = [copy.deepcopy(row['resolution']) for row in previous['assessment']['findings']]
        current['findings'] = current['findings'][:1]
        current['rereview'] = current['rereview'][:1]
        current['assessment']['findings'] = current['assessment']['findings'][:1]
        current['aliases'] = {'F002': 'F001'}
        current['assessment']['findings'][0]['resolution'] = [first, second]
        current['assessment']['lineage'][1]['survivor'] = 'F001'
        self.assertEqual(review.validate(current), [])
        verify_sources(current, sources.__getitem__, captured_inputs={'sources': {}})
        later, sources = following(current, 'c')
        later['assessment']['findings'][0]['resolution'] = [second, first]
        self.assertEqual(review.validate(later), [])
        verify_sources(later, sources.__getitem__, captured_inputs={'sources': {}})
        self.assertEqual(later['assessment']['lineage'][0]['resolution']['conditions'], ['Writes stay disabled'])
        self.assertEqual(later['assessment']['lineage'][1]['resolution']['conditions'], ['Subscriber remains read-only'])
        self.assertEqual(later['assessment']['lineage'][1]['resolution']['source']['reference'],
                         'evidence/second-note.txt')
        dropped = copy.deepcopy(later)
        dropped['assessment']['findings'][0]['resolution'] = first
        dropped['assessment']['lineage'][1]['resolution'] = None
        with self.assertRaisesRegex(ValueError, 'reopening'):
            verify_sources(dropped, sources.__getitem__, captured_inputs={'sources': {}})

    def test_older_observation_is_not_new_after_an_intermediate_generation(self):
        previous = root_current()
        current, sources = following(previous, 'b')
        verify_sources(current, sources.__getitem__)
        current['coverage']['evidence'][0]['reference'] = 'evidence/fresh.txt'
        current['assessment']['scope']['delta'][0]['sources'] = [source('fresh.txt', FRESH)]
        current['assessment']['observed_hashes'].append(hashlib.sha256(FRESH).hexdigest())
        sources['evidence/fresh.txt'] = FRESH
        verify_sources(current, sources.__getitem__)
        later, sources = following(current, 'c')
        later['coverage']['evidence'][0]['reference'] = 'evidence/proof.txt'
        later['assessment']['scope']['delta'][0]['sources'] = [source('proof.txt', PROOF)]
        later['assessment']['findings'][0].update(resolution=None, reopening=dict(
            reason='condition_changed', detail='Writes became reachable', condition='Writes stay disabled',
            evidence_id='EV001', source=source('proof.txt', PROOF)))
        later['assessment']['lineage'][0]['resolution'] = None
        with self.assertRaisesRegex(ValueError, 'already used'):
            verify_sources(later, sources.__getitem__)

    def test_lineage_and_observed_hashes_cannot_drop_or_invent_history(self):
        previous = root_current()
        current, sources = following(previous, 'b')
        for field, value in (('lineage', []), ('observed_hashes', []),
                             ('observed_hashes', current['assessment']['observed_hashes'] + ['0' * 64])):
            with self.subTest(field=field, value=value):
                altered = copy.deepcopy(current)
                altered['assessment'][field] = value
                with self.assertRaises(ValueError):
                    verify_sources(altered, sources.__getitem__)

    def test_expanding_a_members_debt_still_requires_material_reopening(self):
        previous = root_current()
        current, sources = following(previous, 'b')
        extra = dict(copy.deepcopy(previous['assessment']['findings'][0]['resolution']),
                     conditions=['Subscriber remains read-only'], source=source('second-note.txt', SECOND_NOTE))
        both = [current['assessment']['findings'][0]['resolution'], extra]
        current['assessment']['findings'][0]['resolution'] = both
        current['assessment']['lineage'][0]['resolution'] = copy.deepcopy(both)
        current['assessment']['observed_hashes'].append(hashlib.sha256(SECOND_NOTE).hexdigest())
        guided_current(current, previous)
        with self.assertRaisesRegex(ValueError, 'reopening'):
            verify_sources(current, sources.__getitem__, captured_inputs={'sources': {
                'evidence/second-note.txt': hashlib.sha256(SECOND_NOTE).hexdigest()}})

    def test_published_alias_cannot_leave_its_survivor_group(self):
        original = root_current(two=True)
        original['findings'].append(dict(original['findings'][0], id='F003', title='Third report'))
        original['assessment']['findings'].append(dict(copy.deepcopy(original['assessment']['findings'][0]),
                                                     id='F003', cause='third-report'))
        original['assessment']['lineage'].append(dict(copy.deepcopy(original['assessment']['lineage'][0]),
            id='F003', cause='third-report', survivor='F003', title='Third report'))
        guided_current(original)
        merged, sources = following(original, 'b')
        second = merged['assessment']['findings'][1]['resolution']
        merged['assessment']['findings'][0]['resolution'] = [merged['assessment']['findings'][0]['resolution'], second]
        merged['findings'].pop(1)
        merged['rereview'].pop(1)
        merged['assessment']['findings'].pop(1)
        merged['aliases'] = {'F002': 'F001'}
        merged['assessment']['lineage'][1]['survivor'] = 'F001'
        verify_sources(merged, sources.__getitem__, captured_inputs={'sources': {}})
        altered, sources = following(merged, 'c')
        altered['aliases']['F002'] = 'F003'
        altered['assessment']['lineage'][1]['survivor'] = 'F003'
        altered['assessment']['findings'][0]['resolution'] = original['assessment']['findings'][0]['resolution']
        altered['assessment']['findings'][1]['resolution'] = [
            original['assessment']['findings'][2]['resolution'], second]
        with self.assertRaisesRegex(ValueError, 'alias|survivor'):
            verify_sources(altered, sources.__getitem__, captured_inputs={'sources': {}})

    def test_unknown_v1_outcome_is_preserved_without_inventing_a_terminal_state(self):
        previous, _ = followup(assessed())
        previous['review_id'] = 'CR-' + 'e' * 20
        previous['findings'] = []
        previous['rereview'][0]['status'] = 'not_reevaluated'
        previous['assessment']['findings'][0].update(relation='outside_scope', verification=None)
        previous['assessment']['findings'][0]['resolution'] = None
        raw = archive_bytes(previous)
        current, sources = following(root_current(debt=False), 'b')
        current['assessment']['previous'] = dict(review_id=previous['review_id'], source=source('prior.json', raw))
        current['previous_reviews'][0]['review_id'] = previous['review_id']
        current['findings'] = []
        current['assessment']['lineage'][0]['last_status'] = 'unknown'
        track(current, dict(previous, assessment=dict(previous['assessment'], lineage=current['assessment']['lineage'])),
              'not_reevaluated')
        current['assessment']['findings'][0].update(relation='outside_scope', verification=None)
        current['assessment']['history_incomplete'] = True
        current['assessment']['observed_hashes'] = sorted({hashlib.sha256(PROOF).hexdigest(),
            previous['assessment']['previous']['source']['sha256'], hashlib.sha256(raw).hexdigest()})
        sources['evidence/prior.json'] = raw
        verify_sources(current, sources.__getitem__)
        revived, sources = following(current, 'c')
        revived['findings'] = copy.deepcopy(root_current(debt=False)['findings'])
        revived['assessment']['findings'] = copy.deepcopy(root_current(debt=False)['assessment']['findings'])
        track(revived, current, 'still_valid')
        revived['assessment']['lineage'][0]['last_status'] = 'confirmed'
        with self.assertRaisesRegex(ValueError, 'reopening'):
            verify_sources(revived, sources.__getitem__)

    def test_material_reopening_accepts_a_fresh_static_source(self):
        terminal, _ = terminal_chain('resolved')
        current, sources = following(terminal, 'b')
        current['findings'] = copy.deepcopy(root_current(debt=False)['findings'])
        current['assessment']['findings'] = copy.deepcopy(root_current(debt=False)['assessment']['findings'])
        track(current, terminal, 'still_valid')
        current['assessment']['lineage'][0]['last_status'] = 'confirmed'
        current['coverage']['evidence'][0]['reference'] = 'evidence/fresh.txt'
        current['assessment']['scope']['delta'][0]['sources'] = [source('fresh.txt', FRESH)]
        current['assessment']['findings'][0]['reopening'] = dict(reason='new_evidence',
            detail='A supported caller now writes', condition=None, evidence_id='EV001', source=source('fresh.txt', FRESH))
        current['assessment']['observed_hashes'].append(hashlib.sha256(FRESH).hexdigest())
        sources['evidence/fresh.txt'] = FRESH
        self.assertEqual(review.validate(current), [])
        verify_sources(current, sources.__getitem__)

    def test_this_review_disposition_expires_without_becoming_inherited_debt(self):
        previous = root_current()
        for row in (previous['assessment']['findings'][0], previous['assessment']['lineage'][0]):
            row['resolution'].update(status='out_of_scope', scope='this_review')
        guided_current(previous)
        current, sources = following(previous, 'b')
        with self.assertRaisesRegex(ValueError, 'this_review'):
            verify_sources(current, sources.__getitem__)
        current['assessment']['findings'][0]['resolution'] = None
        current['assessment']['lineage'][0]['resolution'] = None
        verify_sources(current, sources.__getitem__, captured_inputs={'sources': {}})

    def test_new_decision_requires_initial_capture_while_unchanged_debt_does_not(self):
        previous = root_current(debt=False)
        current, sources = following(previous, 'b')
        disposition = copy.deepcopy(root_current()['assessment']['findings'][0]['resolution'])
        current['assessment']['findings'][0]['resolution'] = disposition
        current['assessment']['lineage'][0]['resolution'] = copy.deepcopy(disposition)
        current['assessment']['observed_hashes'].append(hashlib.sha256(NOTE).hexdigest())
        guided_current(current, previous)
        with self.assertRaisesRegex(ValueError, 'initially captured'):
            verify_sources(current, sources.__getitem__, captured_inputs={'sources': {}})
        verify_sources(current, sources.__getitem__, captured_inputs={'sources': {
            'evidence/note.txt': hashlib.sha256(NOTE).hexdigest()}})

    def test_omitted_terminal_alias_remains_reserved_and_can_return_under_its_survivor(self):
        root = root_current(two=True)
        for row in root['assessment']['findings'] + root['assessment']['lineage']:
            row['resolution'] = None
        root['assessment']['observed_hashes'] = [hashlib.sha256(PROOF).hexdigest()]
        guided_current(root)
        merged, sources = following(root, 'b')
        merged['findings'] = []
        merged['rereview'] = merged['rereview'][:1]
        merged['rereview'][0]['status'] = 'resolved'
        merged['assessment']['findings'] = merged['assessment']['findings'][:1]
        merged['aliases'] = {'F002': 'F001'}
        for member in merged['assessment']['lineage']:
            member.update(survivor='F001', last_status='resolved')
        verify_sources(merged, sources.__getitem__)
        omitted, sources = following(merged, 'c')
        omitted['assessment']['findings'] = []
        omitted['aliases'] = {}
        verify_sources(omitted, sources.__getitem__)
        revived, sources = following(omitted, 'd')
        revived['findings'] = copy.deepcopy(root['findings'][:1])
        revived['assessment']['findings'] = copy.deepcopy(root['assessment']['findings'][:1])
        revived['aliases'] = {'F002': 'F001'}
        track(revived, omitted, 'still_valid')
        for member in revived['assessment']['lineage']:
            member['last_status'] = 'confirmed'
        revived['coverage']['evidence'][0]['reference'] = 'evidence/fresh.txt'
        revived['assessment']['scope']['delta'][0]['sources'] = [source('fresh.txt', FRESH)]
        revived['assessment']['findings'][0]['reopening'] = dict(reason='new_evidence',
            detail='Material new caller observation', condition=None, evidence_id='EV001', source=source('fresh.txt', FRESH))
        revived['assessment']['observed_hashes'].append(hashlib.sha256(FRESH).hexdigest())
        sources['evidence/fresh.txt'] = FRESH
        verify_sources(revived, sources.__getitem__)
        reused = copy.deepcopy(revived)
        reused['findings'][0]['id'] = 'F002'
        reused['assessment']['findings'][0].update(id='F002', cause='second-report-of-duplicate-delivery')
        reused['rereview'][0].update(id='F002', previous_finding_id='F002')
        reused['aliases'] = {}
        reused['assessment']['lineage'][1]['survivor'] = 'F002'
        reused['assessment']['lineage'][1]['title'] = reused['findings'][0]['title']
        with self.assertRaisesRegex(ValueError, 'alias'):
            verify_sources(reused, sources.__getitem__)

    def test_v1_alias_of_a_confirmed_target_keeps_known_disposition_without_reopening(self):
        previous = assessed()
        previous['aliases'] = {'F003': 'F001'}
        current, sources = following(root_current(), 'b')
        raw = archive_bytes(previous)
        current['assessment']['previous']['source'] = source('prior.json', raw)
        current['assessment']['observed_hashes'] = sorted({hashlib.sha256(NOTE).hexdigest(),
            hashlib.sha256(PROOF).hexdigest(), hashlib.sha256(raw).hexdigest()})
        current['aliases'] = {'F003': 'F001'}
        current['assessment']['lineage'].append(dict(id='F003', cause=None, survivor='F001',
            title=None, last_status='confirmed', resolution=copy.deepcopy(
                previous['assessment']['findings'][0]['resolution'])))
        sources['evidence/prior.json'] = raw
        guided_current(current, previous)
        self.assertEqual(review.validate(current), [])
        verify_sources(current, sources.__getitem__, captured_inputs={'sources': {}})

    def test_v1_alias_retains_a_targets_terminal_or_unknown_material_state(self):
        for old_status in ('resolved', 'not_reevaluated'):
            with self.subTest(old_status=old_status):
                seed = assessed()
                seed['assessment']['findings'][0]['resolution'] = None
                previous, _ = followup(seed)
                previous['findings'] = []
                previous['rereview'][0]['status'] = old_status
                previous['aliases'] = {'F003': 'F001'}
                if old_status == 'not_reevaluated':
                    previous['assessment']['findings'][0].update(relation='outside_scope', verification=None)
                raw = archive_bytes(previous)
                current, sources = following(root_current(debt=False), 'b')
                current['assessment']['previous'] = dict(review_id=previous['review_id'], source=source('prior.json', raw))
                current['previous_reviews'][0]['review_id'] = previous['review_id']
                current['rereview'][0]['previous_review_id'] = previous['review_id']
                current['aliases'] = {'F003': 'F001'}
                current['assessment']['lineage'].append(dict(id='F003', cause=None, survivor='F001',
                    title=None, last_status='confirmed', resolution=None))
                current['assessment']['history_incomplete'] = True
                current['assessment']['observed_hashes'] = sorted({hashlib.sha256(PROOF).hexdigest(),
                    previous['assessment']['previous']['source']['sha256'], hashlib.sha256(raw).hexdigest()})
                sources['evidence/prior.json'] = raw
                with self.assertRaisesRegex(ValueError, 'reopening'):
                    verify_sources(current, sources.__getitem__)


if __name__ == '__main__':
    unittest.main()
