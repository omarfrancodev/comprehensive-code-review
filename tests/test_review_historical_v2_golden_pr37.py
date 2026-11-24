"""A real 7f05898 writer's v2 payload remains readable and usable by v3."""
import json
from pathlib import Path
import tempfile
import unittest

from legacy_v2_fixture import unpack_legacy_v2
from ccr.archive import compact
from ccr.contracts import review
import test_review_assessment as assessment_fixtures
from test_review_assessment import followup, guided_current, source


def snapshot(run):
    return {str(path.relative_to(run)): path.read_bytes() for path in run.rglob('*') if path.is_file()}


class HistoricalV2GoldenPr37Tests(unittest.TestCase):
    def test_actual_7f_payload_reads_without_retroactive_history_flag(self):
        with tempfile.TemporaryDirectory() as scratch:
            run = unpack_legacy_v2(Path(scratch) / 'archive')
            before = snapshot(run)
            value = compact.read_compact(run)['record']
            self.assertEqual(value['assessment']['schema_version'], 2)
            self.assertNotIn('history_incomplete', value['assessment'])
            prior = json.loads((run / 'evidence/prior.json').read_bytes())
            self.assertEqual(prior['assessment']['schema_version'], 1)
            self.assertIsNotNone(prior['assessment']['previous'])
            self.assertEqual(review.validate(value), [])
            self.assertEqual(snapshot(run), before)

    def test_actual_7f_payload_is_a_verified_baseline_for_new_guided_v3(self):
        fixture = assessment_fixtures.AssessmentCompactTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        run = unpack_legacy_v2(fixture.root / 'historical')
        before = snapshot(run)
        prior = compact.read_compact(run)['record']
        prepared = fixture.prepare(operation_id='current-after-golden')
        fresh, selected = fixture.record_and_sources(prepared)
        current, sources = followup(prior)
        current.pop('compact_identity', None)
        current['review_id'] = fresh['review_id']
        current['coverage']['execution'] = fresh['coverage']['execution']
        current['previous_reviews'][0]['reference'] = str(run / 'review.json')
        current['rereview'][0]['previous_reference'] = str(run / 'review.json')
        sources['evidence/prior.json'] = (run / 'review.json').read_bytes()
        current['assessment']['previous']['source'] = source('prior.json', sources['evidence/prior.json'])
        guided_current(current, prior)
        self.assertTrue(current['assessment']['history_incomplete'])
        kept = compact.create_compact(prepared, current, current_inputs=fixture.inputs,
                                      sources={**selected, **sources})
        result = compact.read_compact(kept['run_dir'])['record']
        self.assertEqual(result['assessment']['schema_version'], 3)
        self.assertTrue(result['assessment']['history_incomplete'])
        self.assertEqual(result['assessment']['authorizations'][0]['review_id'], prior['review_id'])
        self.assertEqual(snapshot(run), before)

    def test_historical_compatibility_keeps_selected_byte_integrity(self):
        with tempfile.TemporaryDirectory() as scratch:
            run = unpack_legacy_v2(Path(scratch) / 'archive')
            proof = run / 'evidence/prior.json'
            proof.write_bytes(proof.read_bytes() + b' ')
            with self.assertRaisesRegex(ValueError, 'hash differs'):
                compact.read_compact(run)
