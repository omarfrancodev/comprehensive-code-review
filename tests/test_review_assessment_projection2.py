"""Consumer regressions for independently sourced member dispositions."""
import copy
import hashlib
import json
import unittest

from test_review_assessment import assessed, NOTE, PROOF, source
from ccr.contracts import review
from ccr.contracts.check_disclosure import input_identity_for
from ccr.reporting.projections import assessment_lines
from ccr.reporting.text_projection import _Projection
from ccr.workflow.builders import build_check_disclosure


def grouped_record():
    record = assessed()
    first = record['assessment']['findings'][0]['resolution']
    second = copy.deepcopy(first)
    second.update(source=source('second-note.txt', b'Second owner decision'),
                  conditions=['Consumer remains read-only'])
    record['assessment']['schema_version'] = 2
    record['assessment']['findings'][0]['resolution'] = [first, second]
    record['aliases'] = {'F002': 'F001'}
    record['assessment']['lineage'] = [
        dict(id='F001', cause='duplicate-delivery', survivor='F001',
             title='Duplicate delivery in a read-only consumer',
             last_status='confirmed', resolution=copy.deepcopy(first)),
        dict(id='F002', cause='second-report-of-duplicate-delivery', survivor='F001',
             title='Second report of duplicate delivery',
             last_status='confirmed', resolution=copy.deepcopy(second))]
    record['assessment']['observed_hashes'] = sorted({
        hashlib.sha256(PROOF).hexdigest(), hashlib.sha256(NOTE).hexdigest(),
        hashlib.sha256(b'Second owner decision').hexdigest()})
    return record


class AssessmentProjection2Tests(unittest.TestCase):
    def test_new_guided_writes_require_v2_while_v1_remains_readable(self):
        from ccr.archive.assessment import require_followup_assessment
        legacy = assessed()
        self.assertEqual(review.validate(legacy), [])
        with self.assertRaisesRegex(ValueError, 'version 2'):
            require_followup_assessment(legacy)
        require_followup_assessment(grouped_record())

    def test_member_conditions_with_distinct_sources_are_both_presented(self):
        output = '\n'.join(assessment_lines(grouped_record()))
        self.assertEqual(output.count('Writes stay disabled'), 1)
        self.assertEqual(output.count('Consumer remains read-only'), 1)
        self.assertNotIn('evidence/second-note.txt', output)

    def test_portable_projection_preserves_each_decision_and_hides_each_locator(self):
        record = grouped_record()
        disclosure = build_check_disclosure(record, input_identity_for(record), {}, {})
        portable = _Projection(record, {}, '', 'a' * 64,
            check_disclosure_context=disclosure, check_disclosure_sources={}).value(record)
        self.assertEqual(review.validate(portable), [])
        decisions = portable['assessment']['findings'][0]['resolution']
        self.assertEqual([item['conditions'] for item in decisions],
                         [['Writes stay disabled'], ['Consumer remains read-only']])
        serialized = json.dumps(portable)
        self.assertNotIn('evidence/note.txt', serialized)
        self.assertNotIn('evidence/second-note.txt', serialized)
        self.assertEqual(portable['assessment']['lineage'][1]['id'], 'F002')
        self.assertEqual(portable['assessment']['lineage'][1]['survivor'], 'F001')

    def test_allocator_reserves_terminal_ids_absent_from_current_findings(self):
        from ccr.contracts.identifiers import canonicalize_ids
        record = assessed()
        record['assessment']['schema_version'] = 2
        record['assessment']['lineage'] = [
            dict(id='D1-F001', cause='duplicate-delivery', survivor='D1-F001',
                 title=record['findings'][0]['title'], last_status='confirmed',
                 resolution=copy.deepcopy(record['assessment']['findings'][0]['resolution'])),
            dict(id='F009', cause='old-terminal-cause', survivor='F009',
                 title='Earlier corrected cause', last_status='resolved', resolution=None)]
        record['assessment']['observed_hashes'] = sorted({
            hashlib.sha256(PROOF).hexdigest(), hashlib.sha256(NOTE).hexdigest()})
        record['findings'][0]['id'] = 'D1-F001'
        record['assessment']['findings'][0]['id'] = 'D1-F001'
        result, mapping = canonicalize_ids(record)
        self.assertEqual(mapping['findings']['D1-F001'], 'F010')
        self.assertEqual(result['assessment']['lineage'][0]['id'], 'F010')
        self.assertEqual(result['assessment']['lineage'][0]['survivor'], 'F010')
        self.assertEqual(result['assessment']['lineage'][1]['id'], 'F009')
