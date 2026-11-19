"""Historical readers and current lineage gates remain separate contracts."""
import copy
import hashlib
from pathlib import Path
import unittest

from test_review_assessment import NOTE, PROOF, assessed, followup, source
from test_review_assessment_lineage import following, root_v2
from ccr.contracts import review
from ccr.contracts.assessment import _verify_lineage_continuity, verify_sources
from ccr.shared.encoding import archive_bytes
import test_review_compact_archive as compact_fixtures


def historical(outcome='still_valid', *, unbound=False):
    seed = assessed()
    seed['assessment']['findings'][0]['resolution'] = None
    previous, _ = followup(seed)
    previous['findings'] = []
    previous['rereview'][0]['status'] = outcome
    if outcome in ('resolved', 'withdrawn'):
        previous['checks'][0]['status'] = 'blocked'
        previous['coverage']['evidence'][0].update(kind='check', check_id='C001')
    if unbound:
        previous['assessment']['scope']['delta'][0]['sources'] = []
    return previous


def migrate(previous):
    current, sources = following(root_v2(debt=False), 'b')
    raw = archive_bytes(previous)
    current['assessment']['previous'] = dict(review_id=previous['review_id'], source=source('prior.json', raw))
    current['previous_reviews'][0]['review_id'] = previous['review_id']
    current['rereview'][0].update(status='not_reevaluated', previous_review_id=previous['review_id'])
    current['findings'] = []
    current['assessment']['findings'][0].update(relation='outside_scope', verification=None)
    current['assessment']['lineage'][0]['last_status'] = 'unknown'
    if (previous['assessment']['previous'] is not None
            or any(not entry['sources'] for entry in previous['assessment']['scope']['delta'])):
        current['assessment']['history_incomplete'] = True
    hashes = {hashlib.sha256(PROOF).hexdigest(), hashlib.sha256(raw).hexdigest(),
              previous['assessment']['previous']['source']['sha256']}
    current['assessment']['observed_hashes'] = sorted(hashes)
    sources['evidence/prior.json'] = raw
    return current, sources


class HistoricalAssessmentTests(unittest.TestCase):
    def test_hashed_v1_followup_still_has_unknown_ancestral_observations(self):
        previous = historical()
        self.assertTrue(previous['assessment']['scope']['delta'][0]['sources'])
        current, sources = migrate(previous)
        current['assessment']['history_incomplete'] = False
        with self.assertRaisesRegex(ValueError, 'history_incomplete'):
            verify_sources(current, sources.__getitem__)
        current['assessment']['history_incomplete'] = True
        verify_sources(current, sources.__getitem__)

    def test_v1_reader_retains_the_published_validation_contract(self):
        for outcome in ('still_valid', 'resolved', 'withdrawn'):
            for unbound in (False, True):
                with self.subTest(outcome=outcome, unbound=unbound):
                    self.assertEqual(review.validate(historical(outcome, unbound=unbound)), [])

    def test_v1_inconclusive_material_outcome_seeds_unknown_lineage(self):
        for outcome in ('still_valid', 'resolved', 'withdrawn'):
            with self.subTest(outcome=outcome):
                previous = historical(outcome, unbound=True)
                current, sources = migrate(previous)
                self.assertEqual(review.validate(current), [])
                verify_sources(current, sources.__getitem__)
                claimed = copy.deepcopy(current)
                claimed['assessment']['lineage'][0]['last_status'] = 'resolved'
                with self.assertRaisesRegex(ValueError, 'material outcome'):
                    verify_sources(claimed, sources.__getitem__)

    def test_unbound_v1_evidence_is_not_proven_new_by_its_missing_hash(self):
        previous = historical('still_valid', unbound=True)
        current, sources = migrate(previous)
        seed = root_v2(debt=False)
        current['findings'] = copy.deepcopy(seed['findings'])
        current['rereview'][0]['status'] = 'still_valid'
        current['assessment']['findings'] = copy.deepcopy(seed['assessment']['findings'])
        current['assessment']['findings'][0]['reopening'] = dict(reason='new_evidence',
            detail='Claims the old unbound proof is new', condition=None, evidence_id='EV001',
            source=source('proof.txt', PROOF))
        current['assessment']['lineage'][0]['last_status'] = 'confirmed'
        with self.assertRaisesRegex(ValueError, 'unknown|historical|already'):
            verify_sources(current, sources.__getitem__)

    def test_unknown_observation_history_survives_another_generation(self):
        current, sources = migrate(historical(unbound=True))
        verify_sources(current, sources.__getitem__)
        later, sources = following(current, 'c')
        later['rereview'] = copy.deepcopy(current['rereview'])
        later['rereview'][0]['previous_review_id'] = current['review_id']
        verify_sources(later, sources.__getitem__)
        omitted = copy.deepcopy(later)
        omitted['presentation']['kind'] = 'review'
        omitted['rereview'] = []
        omitted['assessment']['findings'] = []
        verify_sources(omitted, sources.__getitem__)
        for value in (False, None):
            altered = copy.deepcopy(later)
            if value is None:
                altered['assessment'].pop('history_incomplete')
            else:
                altered['assessment']['history_incomplete'] = value
            with self.assertRaisesRegex(ValueError, 'history|unknown'):
                verify_sources(altered, sources.__getitem__)
        seed = root_v2(debt=False)
        later['findings'] = copy.deepcopy(seed['findings'])
        later['rereview'][0]['status'] = 'still_valid'
        later['assessment']['findings'] = copy.deepcopy(seed['assessment']['findings'])
        later['assessment']['lineage'][0]['last_status'] = 'confirmed'
        later['coverage']['evidence'][0]['reference'] = 'evidence/renamed.txt'
        later['assessment']['scope']['delta'][0]['sources'] = [source('renamed.txt', PROOF)]
        later['assessment']['findings'][0]['reopening'] = dict(reason='new_evidence',
            detail='Renamed an observation with unknown historical hashes', condition=None,
            evidence_id='EV001', source=source('renamed.txt', PROOF))
        sources['evidence/renamed.txt'] = PROOF
        with self.assertRaisesRegex(ValueError, 'unknown|historical'):
            verify_sources(later, sources.__getitem__)

    def test_unknown_history_still_allows_a_decisive_current_pending_gate(self):
        current, sources = migrate(historical(unbound=True))
        seed = root_v2(debt=False)
        proof = b'Current producer and consumer demonstrate the pending obligation fails.'
        current['findings'] = copy.deepcopy(seed['findings'])
        current['rereview'][0]['status'] = 'still_valid'
        current['assessment']['findings'] = copy.deepcopy(seed['assessment']['findings'])
        current['assessment']['lineage'][0]['last_status'] = 'confirmed'
        current['coverage']['evidence'][0]['reference'] = 'evidence/current.txt'
        current['assessment']['scope']['delta'][0]['sources'] = [source('current.txt', proof)]
        current['assessment']['observed_hashes'].remove(hashlib.sha256(PROOF).hexdigest())
        current['assessment']['observed_hashes'].append(hashlib.sha256(proof).hexdigest())
        current['assessment']['findings'][0]['reopening'] = dict(reason='pending_gate',
            detail='Current inspection resolves the previously pending obligation', condition=None,
            evidence_id='EV001', source=source('current.txt', proof))
        sources['evidence/current.txt'] = proof
        verify_sources(current, sources.__getitem__)

    def test_unknown_history_allows_a_decisive_current_condition_change(self):
        previous, _ = followup(assessed())
        previous['assessment']['scope']['delta'][0]['sources'] = []
        raw = archive_bytes(previous)
        current, sources = following(root_v2(), 'b')
        current['assessment']['previous'] = dict(review_id=previous['review_id'], source=source('prior.json', raw))
        current['previous_reviews'][0]['review_id'] = previous['review_id']
        current['rereview'][0]['previous_review_id'] = previous['review_id']
        proof = b'Current supported consumer now writes; acceptance condition no longer holds.'
        current['coverage']['evidence'][0]['reference'] = 'evidence/current.txt'
        current['assessment']['scope']['delta'][0]['sources'] = [source('current.txt', proof)]
        current['assessment']['history_incomplete'] = True
        current['assessment']['observed_hashes'] = sorted({hashlib.sha256(raw).hexdigest(),
            hashlib.sha256(proof).hexdigest(), hashlib.sha256(NOTE).hexdigest(),
            previous['assessment']['previous']['source']['sha256']})
        current['assessment']['findings'][0].update(resolution=None, reopening=dict(reason='condition_changed',
            detail='Inspected the now writable consumer', condition='Writes stay disabled',
            evidence_id='EV001', source=source('current.txt', proof)))
        current['assessment']['lineage'][0]['resolution'] = None
        sources.update({'evidence/prior.json': raw, 'evidence/current.txt': proof})
        verify_sources(current, sources.__getitem__)


class ConsolidationExpiryTests(unittest.TestCase):
    def test_this_review_cannot_move_to_a_survivor_and_become_inherited(self):
        previous = root_v2(two=True)
        previous['assessment']['findings'][1]['resolution'] = None
        previous['assessment']['lineage'][1]['resolution'] = None
        for row in (previous['assessment']['findings'][0], previous['assessment']['lineage'][0]):
            row['resolution'].update(status='out_of_scope', scope='this_review')
        previous['assessment']['observed_hashes'] = sorted({hashlib.sha256(PROOF).hexdigest(),
            previous['assessment']['findings'][0]['resolution']['source']['sha256']})
        current, sources = following(previous, 'b')
        decision = copy.deepcopy(current['assessment']['findings'][0]['resolution'])
        current['findings'] = current['findings'][1:]
        current['rereview'] = current['rereview'][1:]
        current['assessment']['findings'] = current['assessment']['findings'][1:]
        current['assessment']['findings'][0]['resolution'] = decision
        current['aliases'] = {'F001': 'F002'}
        current['assessment']['lineage'][0].update(survivor='F002', resolution=None)
        current['assessment']['lineage'][1]['resolution'] = copy.deepcopy(decision)
        self.assertEqual(review.validate(current), [])
        for captured in ({}, {'evidence/note.txt': hashlib.sha256(NOTE).hexdigest()}):
            with self.subTest(captured=captured):
                with self.assertRaisesRegex(ValueError, 'this_review'):
                    verify_sources(current, sources.__getitem__, captured_inputs={'sources': captured})
        renewed = b'Owner currently excludes the consolidated report from this review.'
        replacement = dict(copy.deepcopy(decision), source=source('renewed.txt', renewed))
        current['assessment']['findings'][0]['resolution'] = replacement
        current['assessment']['lineage'][1]['resolution'] = copy.deepcopy(replacement)
        current['assessment']['observed_hashes'].append(hashlib.sha256(renewed).hexdigest())
        sources['evidence/renewed.txt'] = renewed
        with self.assertRaisesRegex(ValueError, 'initially captured'):
            verify_sources(current, sources.__getitem__, captured_inputs={'sources': {}})
        verify_sources(current, sources.__getitem__, captured_inputs={'sources': {
            'evidence/renewed.txt': hashlib.sha256(renewed).hexdigest()}})


class HistoricalIdentifierLineageTests(unittest.TestCase):
    def invented_current_historical_id(self):
        previous = root_v2(debt=False)
        current, sources = following(previous, 'b')
        finding = dict(copy.deepcopy(current['findings'][0]), id='F-01', title='Invented historical finding')
        current['findings'].append(finding)
        current['assessment']['findings'].append(dict(copy.deepcopy(current['assessment']['findings'][0]),
            id='F-01', cause='invented-history'))
        current['rereview'].append(dict(id='F-01', status='new', details='Invented ID claimed as new',
            previous_review_id=None, previous_reference=None, previous_finding_id=None,
            previous_title=None, previous_url=None, check_ids=[]))
        current['assessment']['lineage'].append(dict(id='F-01', cause='invented-history', survivor='F-01',
            title=finding['title'], last_status='confirmed', resolution=None))
        current['grandfathered_ids']['findings'] = ['F-01']
        return previous, current, sources

    def test_lineage_does_not_certify_a_new_historical_current_finding(self):
        _, current, sources = self.invented_current_historical_id()
        self.assertTrue(any('historical ID' in error for error in review.validate(current)))
        with self.assertRaisesRegex(ValueError, 'historical ID'):
            verify_sources(current, sources.__getitem__)

    def test_source_continuity_requires_actual_published_historical_ids(self):
        previous, current, _ = self.invented_current_historical_id()
        # Exercise continuity independently of the shape gate: a declaration
        # cannot establish that an ID existed in the selected previous bytes.
        with self.assertRaisesRegex(ValueError, 'historical ID'):
            _verify_lineage_continuity(current, current['assessment'], previous)

    def test_new_historical_alias_requires_its_own_published_provenance(self):
        previous = root_v2(debt=False)
        current, sources = following(previous, 'b')
        current['aliases'] = {'F-01': 'F001'}
        current['grandfathered_ids']['findings'] = ['F-01']
        current['assessment']['lineage'].append(dict(id='F-01', cause=None, survivor='F001',
            title=None, last_status='confirmed', resolution=None))
        self.assertEqual(review.validate(current), [])
        with self.assertRaisesRegex(ValueError, 'historical ID'):
            verify_sources(current, sources.__getitem__)

    def terminal_previous(self):
        previous = historical('resolved')
        previous['coverage']['evidence'][0].update(kind='static', check_id=None)
        previous['grandfathered_ids']['findings'] = ['F-01']
        previous['rereview'][0].update(id='F-01', previous_finding_id='F-01')
        previous['assessment']['findings'][0]['id'] = 'F-01'
        return previous

    def test_verified_historical_id_survives_as_lineage_only(self):
        previous = self.terminal_previous()
        current, sources = migrate(previous)
        current['grandfathered_ids']['findings'] = ['F-01']
        current['rereview'] = []
        current['assessment']['findings'] = []
        current['assessment']['lineage'][0].update(id='F-01', survivor='F-01', last_status='resolved')
        self.assertEqual(review.validate(current), [])
        verify_sources(current, sources.__getitem__)

    def test_unpublished_historical_id_cannot_be_added_to_lineage(self):
        current, sources = migrate(historical('resolved'))
        current['grandfathered_ids']['findings'] = ['F-01']
        current['assessment']['lineage'].append(dict(id='F-01', survivor='F-01', cause=None,
            title='Invented historical identity', last_status='resolved', resolution=None))
        with self.assertRaisesRegex(ValueError, 'historical ID'):
            verify_sources(current, sources.__getitem__)


class HistoricalCompactReaderTests(unittest.TestCase):
    setUp = compact_fixtures.CompactPrepareTests.setUp
    prepare = compact_fixtures.CompactPrepareTests.prepare
    record_and_sources = compact_fixtures.CompactPrepareTests.record_and_sources

    def test_archived_historical_terminal_id_needs_no_redundant_tracking_row(self):
        from ccr.archive import compact
        from ccr.reporting.render import render
        from ccr.contracts.identifiers import canonicalize_ids

        prepared = self.prepare()
        seed, selected = self.record_and_sources(prepared)
        assessed(seed)
        legacy, _ = followup(seed)
        legacy.pop('assessment')
        legacy['review_id'] = seed['review_id']
        legacy['findings'][0]['id'] = 'F-01'
        legacy['rereview'][0].update(id='F-01', previous_finding_id='F-01')
        legacy['previous_reviews'][0]['review_id'] = 'CR-' + 'a' * 20
        legacy['rereview'][0]['previous_review_id'] = 'CR-' + 'a' * 20
        legacy['grandfathered_ids']['findings'] = ['F-01']
        self.assertEqual(review.validate(legacy), [])
        saved = compact.create_compact(prepared, legacy, render(legacy), current_inputs=self.inputs,
            sources={**selected, 'evidence/proof.txt': PROOF})
        legacy = compact.read_compact(saved['run_dir'])['record']
        legacy_file = Path(saved['run_dir']) / 'review.json'
        raw = legacy_file.read_bytes()
        prepared = self.prepare(operation_id='terminal-historical-id')
        fresh, selected = self.record_and_sources(prepared)
        old = copy.deepcopy(legacy)
        old.pop('compact_identity')
        assessed(old)
        old['review_id'] = fresh['review_id']
        old['coverage']['execution'] = fresh['coverage']['execution']
        old['findings'] = []
        old['previous_reviews'] = [dict(review_id=legacy['review_id'], reference=str(legacy_file), verified=True)]
        old['rereview'][0].update(status='resolved', previous_review_id=legacy['review_id'],
            previous_reference=str(legacy_file))
        old['assessment']['findings'][0].update(id='F-01', resolution=None)
        old['assessment']['previous'] = dict(review_id=legacy['review_id'], source=source('prior.json', raw))
        sources = {**selected, 'evidence/proof.txt': PROOF, 'evidence/prior.json': raw}
        saved = compact.create_compact(prepared, old, render(old), current_inputs=self.inputs, sources=sources)
        previous = compact.read_compact(saved['run_dir'])['record']
        prior_file = Path(saved['run_dir']) / 'review.json'
        prepared = self.prepare(operation_id='lineage-only-historical-id')
        fresh, selected = self.record_and_sources(prepared)
        current, sources = migrate(previous)
        current['review_id'] = fresh['review_id']
        current['coverage']['execution'] = fresh['coverage']['execution']
        current['grandfathered_ids']['findings'] = ['F-01']
        current['previous_reviews'][0]['reference'] = str(prior_file)
        current['rereview'] = []
        current['assessment']['findings'] = []
        current['assessment']['lineage'][0].update(id='F-01', survivor='F-01', last_status='resolved')
        canonical, mapping = canonicalize_ids(current)
        self.assertEqual(mapping['findings']['F-01'], 'F-01')
        saved = compact.create_compact(prepared, canonical, current_inputs=self.inputs,
            sources={**selected, **sources})
        result = compact.read_compact(saved['run_dir'])['record']
        self.assertEqual(result['rereview'], [])
        self.assertEqual(result['assessment']['lineage'][0]['id'], 'F-01')

    def test_historical_v1_archive_remains_readable_and_seeds_guided_v2(self):
        from ccr.archive import compact
        from ccr.reporting.render import render

        prepared = self.prepare()
        seed, selected = self.record_and_sources(prepared)
        assessed(seed)
        seed['assessment']['findings'][0]['resolution'] = None
        seed['assessment']['scope']['delta'][0]['sources'] = []
        # The explicit report entry point preserves historical writing behavior;
        # the guided entry point continues to require v2 for new work.
        kept = compact.create_compact(prepared, seed, render(seed), current_inputs=self.inputs,
            sources={**selected, 'evidence/proof.txt': PROOF})
        baseline = compact.read_compact(kept['run_dir'])['record']
        baseline_file = Path(kept['run_dir']) / 'review.json'
        for outcome in ('still_valid', 'resolved', 'withdrawn'):
            with self.subTest(outcome=outcome):
                prepared = self.prepare(operation_id='historical-' + outcome)
                fresh, selected = self.record_and_sources(prepared)
                old, sources = followup(baseline)
                old.pop('compact_identity')
                old['review_id'] = fresh['review_id']
                old['coverage']['execution'] = fresh['coverage']['execution']
                old['previous_reviews'][0]['reference'] = str(baseline_file)
                old['rereview'][0].update(status=outcome, previous_reference=str(baseline_file))
                old['findings'] = []
                if outcome in ('resolved', 'withdrawn'):
                    old['checks'][0]['status'] = 'blocked'
                    old['coverage']['evidence'][0].update(kind='check', check_id='C001')
                saved = compact.create_compact(prepared, old, render(old), current_inputs=self.inputs,
                    sources={**selected, **sources})
                previous = compact.read_compact(saved['run_dir'])['record']
                self.assertEqual(previous['rereview'][0]['status'], outcome)
                old_file = Path(saved['run_dir']) / 'review.json'
                old_bytes = old_file.read_bytes()
                prepared = self.prepare(operation_id='guided-' + outcome)
                fresh, selected = self.record_and_sources(prepared)
                current, sources = migrate(previous)
                current['review_id'] = fresh['review_id']
                current['coverage']['execution'] = fresh['coverage']['execution']
                current['previous_reviews'][0]['reference'] = str(old_file)
                current['rereview'][0]['previous_reference'] = str(old_file)
                saved = compact.create_compact(prepared, current, current_inputs=self.inputs,
                    sources={**selected, **sources})
                result = compact.read_compact(saved['run_dir'])['record']
                self.assertEqual(result['assessment']['lineage'][0]['last_status'], 'unknown')
                self.assertTrue(result['assessment']['history_incomplete'])
                self.assertEqual(old_file.read_bytes(), old_bytes)


if __name__ == '__main__':
    unittest.main()
