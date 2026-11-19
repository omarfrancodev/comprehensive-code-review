"""Published assessment contracts and authorization lifetime regressions."""
import copy
import hashlib
import json
from pathlib import Path
import unittest

from test_review_assessment import NOTE, PROOF, assessed, guided_current, source
from test_review_assessment_followup_pr37 import historical, migrate
from test_review_assessment_lineage import following, root_v2
from ccr.contracts import review
from ccr.contracts.assessment import verify_sources
from ccr.shared.encoding import archive_bytes
import test_review_compact_archive as compact_fixtures


def root_v3(*, two=False, exclusion=False, debt=True):
    record = root_v2(two=two, debt=debt)
    assessment = record['assessment']
    assessment.update(schema_version=3, history_incomplete=False, authorizations=[])
    if exclusion:
        for row in (assessment['findings'][0], assessment['lineage'][0]):
            row['resolution'].update(status='out_of_scope', scope='this_review')
    for index, member in enumerate(assessment['lineage'], 1):
        if member['resolution'] is None:
            continue
        identifier = 'AU' + str(index).zfill(3)
        decision = copy.deepcopy(member['resolution'])
        assessment['authorizations'].append(dict(id=identifier, member_id=member['id'],
            review_id=record['review_id'],
            scope={key: record['scope'][key] for key in ('base', 'head', 'snapshot')},
            decision=decision))
        member['resolution']['authorization_id'] = identifier
        assessment['findings'][index - 1]['resolution']['authorization_id'] = identifier
    return record


def expire(previous, digit='b'):
    current, sources = following(previous, digit)
    current['assessment']['findings'][0]['resolution'] = None
    current['assessment']['lineage'][0]['resolution'] = None
    return current, sources


def assign_authorization(record, decision, *, identifier='AU002', member_id='F001'):
    """Author a claimed new authority, independently of production derivation."""
    plain = copy.deepcopy(decision)
    plain.pop('authorization_id', None)
    record['assessment']['authorizations'].append(dict(id=identifier, member_id=member_id,
        review_id=record['review_id'],
        scope={key: record['scope'][key] for key in ('base', 'head', 'snapshot')}, decision=plain))
    active = dict(copy.deepcopy(plain), authorization_id=identifier)
    next(row for row in record['assessment']['findings'] if row['id'] == member_id)['resolution'] = active
    next(row for row in record['assessment']['lineage'] if row['id'] == member_id)['resolution'] = copy.deepcopy(active)


class PublishedV2ReadingTests(unittest.TestCase):
    def test_v2_without_later_history_flag_keeps_its_published_read_contract(self):
        # This is the v2 shape emitted before the history flag existed. Its
        # selected v1 baseline is itself a follow-up, so ancestral hashes are
        # unknown. Reading these exact historical bytes must remain possible.
        record, sources = migrate(historical())
        record['assessment'].pop('history_incomplete')
        published = archive_bytes(record)
        self.assertEqual(review.validate(record), [])
        verify_sources(record, sources.__getitem__)
        self.assertEqual(archive_bytes(record), published)

    def test_both_published_v2_terminal_interpretations_remain_readable_without_a_flag(self):
        previous = historical('resolved')
        for published_outcome in ('resolved', 'unknown'):
            with self.subTest(published_outcome=published_outcome):
                record, sources = migrate(previous)
                record['assessment'].pop('history_incomplete')
                record['assessment']['lineage'][0]['last_status'] = published_outcome
                self.assertEqual(review.validate(record), [])
                verify_sources(record, sources.__getitem__)

    def test_unknown_legacy_history_survives_v2_to_v3_and_another_v3_generation(self):
        legacy, _ = migrate(historical())
        legacy['assessment'].pop('history_incomplete')
        current, sources = following(legacy, 'c')
        current['rereview'] = copy.deepcopy(legacy['rereview'])
        current['rereview'][0]['previous_review_id'] = legacy['review_id']
        guided_current(current, legacy)
        self.assertTrue(current['assessment']['history_incomplete'])
        verify_sources(current, sources.__getitem__)
        later, sources = following(current, 'd')
        later['rereview'] = copy.deepcopy(current['rereview'])
        later['rereview'][0]['previous_review_id'] = current['review_id']
        self.assertTrue(later['assessment']['history_incomplete'])
        verify_sources(later, sources.__getitem__)
        for record in (current, later):
            altered = copy.deepcopy(record)
            altered['assessment']['history_incomplete'] = False
            selected = sources if record is later else following(legacy, 'c')[1]
            with self.assertRaisesRegex(ValueError, 'history_incomplete'):
                verify_sources(altered, selected.__getitem__)


class AuthorizationLifetimeTests(unittest.TestCase):
    def test_new_writes_require_version_three_while_both_old_versions_still_validate(self):
        from ccr.contracts.guided_writes import require_followup_assessment
        for version in (1, 2):
            old = root_v2()
            if version == 1:
                for field in ('lineage', 'observed_hashes'):
                    old['assessment'].pop(field)
                old['assessment']['schema_version'] = 1
            self.assertEqual(review.validate(old), [])
            with self.assertRaisesRegex(ValueError, 'version 3'):
                require_followup_assessment(old)
        current = root_v3()
        self.assertEqual(review.validate(current), [])
        require_followup_assessment(current)
        verify_sources(current, {'evidence/note.txt': NOTE, 'evidence/proof.txt': PROOF}.__getitem__)

    def test_same_note_can_expire_one_authorization_and_preserve_independent_debt(self):
        previous = root_v3(two=True, exclusion=True)
        assessment = previous['assessment']
        for row in (assessment['findings'][1], assessment['lineage'][1]):
            row['resolution']['source'] = source('note.txt', NOTE)
        assessment['authorizations'][1]['decision']['source'] = source('note.txt', NOTE)
        assessment['observed_hashes'] = sorted({hashlib.sha256(NOTE).hexdigest(), hashlib.sha256(PROOF).hexdigest()})
        current, sources = following(previous, 'b')
        current['findings'] = current['findings'][1:]
        current['rereview'] = current['rereview'][1:]
        current['assessment']['findings'] = current['assessment']['findings'][1:]
        current['aliases'] = {'F001': 'F002'}
        current['assessment']['lineage'][0].update(survivor='F002', resolution=None)
        self.assertEqual(review.validate(current), [])
        verify_sources(current, sources.__getitem__, captured_inputs={'sources': {}})
        later, sources = following(current, 'c')
        self.assertEqual(review.validate(later), [])
        verify_sources(later, sources.__getitem__, captured_inputs={'sources': {}})

    def test_expired_authorization_cannot_be_reactivated_after_multiple_generations(self):
        original = root_v3(exclusion=True)
        previous, sources = expire(original)
        verify_sources(previous, sources.__getitem__)
        for digit in ('c', 'd'):
            current, sources = following(previous, digit)
            claimed = copy.deepcopy(current)
            old = copy.deepcopy(original['assessment']['findings'][0]['resolution'])
            claimed['assessment']['findings'][0]['resolution'] = old
            claimed['assessment']['lineage'][0]['resolution'] = copy.deepcopy(old)
            with self.assertRaisesRegex(ValueError, 'this_review|expired|authorization'):
                verify_sources(claimed, sources.__getitem__, captured_inputs={'sources': {
                    'evidence/note.txt': hashlib.sha256(NOTE).hexdigest()}})
            verify_sources(current, sources.__getitem__)
            previous = current

    def test_recapture_rename_and_condition_edits_cannot_mint_fresh_authority(self):
        original = root_v3(exclusion=True)
        expired, _ = expire(original)
        for change in ('recapture', 'rename', 'conditions', 'logical_scope', 'accepted_debt', 'authority', 'channel'):
            with self.subTest(change=change):
                current, sources = following(expired, 'c')
                claimed = copy.deepcopy(original['assessment']['authorizations'][0]['decision'])
                if change == 'rename':
                    claimed['source'] = source('renamed-note.txt', NOTE)
                    sources['evidence/renamed-note.txt'] = NOTE
                if change == 'conditions':
                    claimed['conditions'] = ['A copied decision with edited applicability']
                if change in ('logical_scope', 'accepted_debt'):
                    claimed['scope'] = 'logical_scope'
                if change == 'accepted_debt':
                    claimed['status'] = 'accepted_debt'
                if change == 'authority':
                    claimed['authority'] = 'user'
                if change == 'channel':
                    claimed['channel'] = 'document'
                assign_authorization(current, claimed)
                with self.assertRaisesRegex(ValueError, 'this_review|expired|authorization|already'):
                    verify_sources(current, sources.__getitem__, captured_inputs={'sources': {
                        claimed['source']['reference']: hashlib.sha256(NOTE).hexdigest()}})

    def test_expired_authorization_history_cannot_be_dropped_or_rewritten(self):
        original = root_v3(exclusion=True)
        expired, _ = expire(original)
        for change in ('drop', 'origin', 'conditions', 'scope'):
            with self.subTest(change=change):
                current, sources = following(expired, 'c')
                ledger = current['assessment']['authorizations']
                if change == 'drop':
                    ledger.clear()
                elif change == 'origin':
                    ledger[0]['review_id'] = current['review_id']
                elif change == 'scope':
                    ledger[0]['scope']['head'] = 'invented-original-head'
                else:
                    ledger[0]['decision']['conditions'] = ['Rewritten historic condition']
                with self.assertRaisesRegex(ValueError, 'authorization|history'):
                    verify_sources(current, sources.__getitem__)

    def test_renewal_requires_a_current_authority_and_preserves_the_expired_entry(self):
        original = root_v3(exclusion=True)
        expired, _ = expire(original)
        current, sources = following(expired, 'c')
        renewed = b'Owner authorizes exclusion again for this current review only.'
        decision = copy.deepcopy(original['assessment']['authorizations'][0]['decision'])
        decision['source'] = source('renewed.txt', renewed)
        assign_authorization(current, decision)
        current['assessment']['observed_hashes'].append(hashlib.sha256(renewed).hexdigest())
        sources['evidence/renewed.txt'] = renewed
        self.assertEqual(review.validate(current), [])
        with self.assertRaisesRegex(ValueError, 'initially captured'):
            verify_sources(current, sources.__getitem__, captured_inputs={'sources': {}})
        verify_sources(current, sources.__getitem__, captured_inputs={'sources': {
            'evidence/renewed.txt': hashlib.sha256(renewed).hexdigest()}})
        self.assertEqual(current['assessment']['authorizations'][0], original['assessment']['authorizations'][0])

    def test_expired_authority_cannot_move_to_another_published_survivor(self):
        original = root_v3(two=True, exclusion=True)
        expired, _ = expire(original)
        current, sources = following(expired, 'c')
        old = copy.deepcopy(original['assessment']['findings'][0]['resolution'])
        debt = copy.deepcopy(current['assessment']['findings'][1]['resolution'])
        current['findings'] = current['findings'][1:]
        current['rereview'] = current['rereview'][1:]
        current['assessment']['findings'] = current['assessment']['findings'][1:]
        current['assessment']['findings'][0]['resolution'] = [debt, old]
        current['aliases'] = {'F001': 'F002'}
        current['assessment']['lineage'][0].update(survivor='F002', resolution=old)
        self.assertEqual(review.validate(current), [])
        with self.assertRaisesRegex(ValueError, 'this_review|expired|authorization'):
            verify_sources(current, sources.__getitem__, captured_inputs={'sources': {
                'evidence/note.txt': hashlib.sha256(NOTE).hexdigest()}})

    def test_inactive_authority_keeps_provenance_without_requiring_old_source_bytes(self):
        original = root_v3(exclusion=True)
        expired, sources = expire(original)
        del sources['evidence/note.txt']
        verify_sources(expired, sources.__getitem__)
        later, sources = following(expired, 'c')
        del sources['evidence/note.txt']
        verify_sources(later, sources.__getitem__)
        self.assertEqual(later['assessment']['authorizations'], original['assessment']['authorizations'])

    def test_new_authority_must_be_bound_to_the_current_review_and_pinned_scope(self):
        for field, value in (('review_id', 'CR-' + 'e' * 20), ('scope', dict(base=None, head='other-head', snapshot=None))):
            with self.subTest(field=field):
                current = root_v3()
                current['assessment']['authorizations'][0][field] = value
                with self.assertRaisesRegex(ValueError, 'current review|pinned scope'):
                    verify_sources(current, {'evidence/note.txt': NOTE, 'evidence/proof.txt': PROOF}.__getitem__)

    def test_previous_review_bytes_cannot_be_relabelled_as_a_new_authority_document(self):
        original = root_v3(exclusion=True)
        expired, _ = expire(original)
        current, sources = following(expired, 'c')
        decision = copy.deepcopy(original['assessment']['authorizations'][0]['decision'])
        decision['source'] = copy.deepcopy(current['assessment']['previous']['source'])
        assign_authorization(current, decision)
        with self.assertRaisesRegex(ValueError, 'authorization.*already|already observed'):
            verify_sources(current, sources.__getitem__, captured_inputs={'sources': {
                'evidence/prior.json': decision['source']['sha256']}})

    def test_another_fragment_of_the_same_document_cannot_renew_expired_authority(self):
        note = b'{"first":"Exclude this review","copied":"Exclude this review"}'
        original = root_v3(exclusion=True)
        descriptor = dict(source('note.json', note), reference='evidence/note.json#/first')
        for row in (original['assessment']['findings'][0], original['assessment']['lineage'][0]):
            row['resolution']['source'] = copy.deepcopy(descriptor)
        original['assessment']['authorizations'][0]['decision']['source'] = copy.deepcopy(descriptor)
        original['assessment']['observed_hashes'] = sorted({hashlib.sha256(PROOF).hexdigest(), descriptor['sha256']})
        expired, _ = expire(original)
        current, sources = following(expired, 'c')
        decision = copy.deepcopy(original['assessment']['authorizations'][0]['decision'])
        decision['source']['reference'] = 'evidence/note.json#/copied'
        assign_authorization(current, decision)
        sources['evidence/note.json'] = note
        with self.assertRaisesRegex(ValueError, 'already observed|expired'):
            verify_sources(current, sources.__getitem__, captured_inputs={'sources': {
                'evidence/note.json': descriptor['sha256']}})

    def test_authorization_shape_reports_malformed_references_instead_of_crashing(self):
        for field, value in (('authorization_id', []), ('member_id', []), ('id', 'AU000')):
            with self.subTest(field=field):
                record = root_v3()
                if field == 'authorization_id':
                    record['assessment']['findings'][0]['resolution'][field] = value
                else:
                    record['assessment']['authorizations'][0][field] = value
                self.assertTrue(any('authorization' in error for error in review.validate(record)))

    def test_distinct_ids_cannot_duplicate_the_same_authority_grant(self):
        record = root_v3()
        clone = copy.deepcopy(record['assessment']['authorizations'][0])
        clone['id'] = 'AU002'
        record['assessment']['authorizations'].append(clone)
        original = record['assessment']['findings'][0]['resolution']
        duplicate = dict(copy.deepcopy(original), authorization_id='AU002')
        for row in (record['assessment']['findings'][0], record['assessment']['lineage'][0]):
            row['resolution'] = [copy.deepcopy(original), copy.deepcopy(duplicate)]
        self.assertTrue(any('duplicate authorization grant' in error for error in review.validate(record)))
        with self.assertRaisesRegex(ValueError, 'duplicate authorization grant'):
            verify_sources(record, {'evidence/note.txt': NOTE, 'evidence/proof.txt': PROOF}.__getitem__)

    def test_identical_decisions_for_distinct_original_members_remain_distinct_grants(self):
        record = root_v3(two=True)
        decision = copy.deepcopy(record['assessment']['authorizations'][0]['decision'])
        record['assessment']['authorizations'][1]['decision'] = copy.deepcopy(decision)
        for row in (record['assessment']['findings'][1], record['assessment']['lineage'][1]):
            row['resolution'] = dict(copy.deepcopy(decision), authorization_id='AU002')
        record['assessment']['observed_hashes'] = sorted({hashlib.sha256(NOTE).hexdigest(), hashlib.sha256(PROOF).hexdigest()})
        self.assertEqual(review.validate(record), [])
        verify_sources(record, {'evidence/note.txt': NOTE, 'evidence/proof.txt': PROOF}.__getitem__)

    def test_authorization_ids_are_canonical_positive_identifiers(self):
        for identifier in ('AU000', 'AU0001', 'AU01'):
            with self.subTest(identifier=identifier):
                record = root_v3()
                record['assessment']['authorizations'][0]['id'] = identifier
                record['assessment']['findings'][0]['resolution']['authorization_id'] = identifier
                record['assessment']['lineage'][0]['resolution']['authorization_id'] = identifier
                self.assertTrue(any('authorization' in error for error in review.validate(record)))

    def test_unknown_authorization_history_cannot_be_hidden_by_downgrading_to_v2(self):
        previous = root_v3(exclusion=True)
        current, sources = expire(previous)
        current['assessment']['schema_version'] = 2
        current['assessment'].pop('authorizations')
        current['assessment'].pop('history_incomplete')
        self.assertEqual(review.validate(current), [])
        with self.assertRaisesRegex(ValueError, 'version 3|downgrade|authorization'):
            verify_sources(current, sources.__getitem__)

    def test_authorization_source_digest_cannot_be_removed_from_observed_history(self):
        original = root_v3(exclusion=True)
        expired, _ = expire(original)
        expired['assessment']['observed_hashes'].remove(hashlib.sha256(NOTE).hexdigest())
        self.assertTrue(any('observed_hashes' in error for error in review.validate(expired)))

    def test_allocator_maps_authorization_members_atomically_with_new_finding_ids(self):
        from ccr.contracts.identifiers import canonicalize_ids
        record = root_v3()
        record['findings'][0]['id'] = 'D1-F001'
        record['assessment']['findings'][0]['id'] = 'D1-F001'
        record['assessment']['lineage'][0].update(id='D1-F001', survivor='D1-F001')
        record['assessment']['authorizations'][0]['member_id'] = 'D1-F001'
        result, mapping = canonicalize_ids(record)
        self.assertEqual(mapping['findings']['D1-F001'], 'F001')
        self.assertEqual(result['assessment']['authorizations'][0]['member_id'], 'F001')
        self.assertEqual(result['assessment']['authorizations'][0]['id'], 'AU001')


class InactiveAuthorizationArchiveTests(unittest.TestCase):
    def compact_fixture(self):
        fixture = compact_fixtures.CompactPrepareTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        return fixture

    def retained_authority(self, fixture, *, repository_identity=None):
        from ccr.archive import compact
        inputs = dict(fixture.inputs, sources={'evidence/note.txt': hashlib.sha256(NOTE).hexdigest()})
        prepared = fixture.prepare(inputs=inputs, repo_identity=repository_identity)
        original, selected = fixture.record_and_sources(prepared)
        assessed(original)
        original['assessment']['findings'][0]['resolution'].update(status='out_of_scope', scope='this_review')
        guided_current(original)
        retained = compact.create_compact(prepared, original, current_inputs=inputs,
            sources={**selected, 'evidence/note.txt': NOTE, 'evidence/proof.txt': PROOF})
        path = Path(retained['run_dir']) / 'review.json'
        return path, compact.read_compact(path.parent)['record']

    def test_compact_retains_expired_authority_without_selecting_its_old_source(self):
        from ccr.archive import compact
        fixture = self.compact_fixture()
        previous_path, previous = self.retained_authority(fixture)
        prepared = fixture.prepare(operation_id='expired-authority')
        fresh, selected = fixture.record_and_sources(prepared)
        current, _ = expire(previous)
        current.pop('compact_identity')
        current['review_id'] = fresh['review_id']
        current['coverage']['execution'] = fresh['coverage']['execution']
        current['previous_reviews'][0]['reference'] = str(previous_path)
        current['rereview'][0]['previous_reference'] = str(previous_path)
        current['coverage']['evidence'][0]['reference'] = 'evidence/current-proof.txt'
        current['assessment']['scope']['delta'][0]['sources'] = [source('current-proof.txt', PROOF)]
        selected.update({'evidence/prior.json': previous_path.read_bytes(), 'evidence/current-proof.txt': PROOF})
        self.assertNotIn('evidence/note.txt', selected)
        result = compact.create_compact(prepared, current, current_inputs=fixture.inputs, sources=selected)
        run = Path(result['run_dir'])
        self.assertFalse((run / 'evidence/note.txt').exists())
        self.assertEqual(compact.read_compact(run)['record']['assessment']['authorizations'],
                         previous['assessment']['authorizations'])

    def test_full_retains_closes_and_validates_without_reopening_inactive_authority(self):
        from ccr.archive import lifecycle, retention
        from ccr.shared.git import repository_identity
        import test_review_closure_consistency as guided

        native = guided.ClosureConsistencyTests()
        native.setUp()
        self.addCleanup(native.doCleanups)
        case = native.make_guided_run(complete_capture=True, explicit_identities=True)
        fixture = self.compact_fixture()
        previous_path, previous = self.retained_authority(fixture,
            repository_identity=repository_identity(native.repo))
        fresh = native.read(case['record'])
        current, _ = expire(previous)
        current.pop('compact_identity')
        for field in ('scope', 'review_id', 'description', 'profile'):
            current[field] = fresh[field]
        current['coverage']['execution'] = fresh['coverage']['execution']
        current['checks'] = []
        current['previous_reviews'][0]['reference'] = str(previous_path)
        current['rereview'][0]['previous_reference'] = str(previous_path)
        current['coverage']['evidence'][0]['reference'] = 'evidence/notes.json'
        current['assessment']['scope']['delta'][0]['sources'] = [source('notes.json', case['notes'])]
        current['assessment']['observed_hashes'].append(hashlib.sha256(case['notes']).hexdigest())
        case['record'] = native.write('expired-authority-final.json', current)
        prior_file = native.root / 'prior.json'
        prior_file.write_bytes(previous_path.read_bytes())
        case['evidence_inputs'].append(prior_file)
        self.assertEqual(review.validate(current), [])
        self.assertFalse((native.root / 'note.txt').exists())
        self.assertFalse(any(path.name == 'note.txt' for path in case['evidence_inputs']))
        retention.retain(case['run'], case['record'], context_input=case['context'],
            evidence_inputs=case['evidence_inputs'], expected_schema=13,
            unavailable_reason='Fixture has no provider counters')
        lifecycle.close(case['run'], cleanup='not_needed')
        self.assertEqual(lifecycle.validate(case['run'], require_complete=True)['state'], 'complete')
        self.assertFalse((case['run'] / 'evidence/note.txt').exists())
        retained = json.loads((case['run'] / 'review.json').read_bytes())
        self.assertEqual(retained['assessment']['authorizations'], previous['assessment']['authorizations'])


if __name__ == '__main__':
    unittest.main()
