from pathlib import Path
import unittest
from unittest.mock import patch
from script_test_support import enable_package_imports
enable_package_imports()
import test_review_compact_archive as fixtures
from test_review_coverage13 import record13, group
from profile_topology_fixtures import record12
from ccr.reporting.render import render
from ccr.workflow.reuse import coverage_reuse_issue
from ccr.archive import compact
from ccr.shared.encoding import archive_bytes

class CompactOutputLimitTests(unittest.TestCase):
    setUp = fixtures.CompactPrepareTests.setUp
    prepare = fixtures.CompactPrepareTests.prepare
    record_and_sources = fixtures.CompactPrepareTests.record_and_sources

    def test_reader_writer_limits_accept_boundaries_and_reject_overflow(self):
        mib = 1024 * 1024
        sizes = {'review.json': 16*mib, 'informe.md': 1*mib, 'evidence/log.txt': 63*mib}
        compact._validate_content_sizes(sizes)
        for path in sizes:
            changed = dict(sizes)
            changed[path] += 1
            with self.assertRaises(ValueError):
                compact._validate_content_sizes(changed)
        with self.assertRaises(ValueError):
            compact._validate_content_sizes({'review.json': 1, 'informe.md': 1, 'evidence/log.txt': 64*mib+1})

    def test_metadata_overflow_is_rejected_before_intent(self):
        prepared = self.prepare()
        record, sources = self.record_and_sources(prepared)
        with patch.object(compact, 'METADATA_BYTES_LIMIT', 100):
            with self.assertRaises(ValueError):
                compact.create_compact(prepared, record, render(record), self.inputs, sources)
        self.assertFalse(Path(prepared['run_dir']).exists())
        self.assertFalse((Path(prepared['staging_dir']) / 'payload-intent.json').exists())

    def test_aggregate_overflow_rejected_before_intent_and_exact_retry_remains_possible(self):
        prepared = self.prepare()
        record, sources = self.record_and_sources(prepared)
        sources['evidence/large.log'] = b'x' * 2048
        with patch.object(compact, 'CONTENT_BYTES_LIMIT', 2048, create=True):
            for _ in range(2):
                with self.assertRaises(ValueError):
                    compact.create_compact(prepared, record, render(record), self.inputs, sources)
        self.assertFalse(Path(prepared['run_dir']).exists())
        self.assertFalse((Path(prepared['staging_dir']) / 'payload-intent.json').exists())
        result = compact.create_compact(prepared, record, render(record), self.inputs, sources)
        self.assertEqual(compact.read_compact(result['run_dir'])['record']['review_id'], prepared['review_id'])

    def test_final_record_size_checked_before_publication(self):
        prepared = self.prepare()
        record, sources = self.record_and_sources(prepared)
        limit = len(archive_bytes(record))
        with patch.object(compact, 'RECORD_BYTES_LIMIT', limit, create=True):
            with self.assertRaises(ValueError):
                compact.create_compact(prepared, record, render(record), self.inputs, sources)
        self.assertFalse(Path(prepared['run_dir']).exists())
        self.assertFalse((Path(prepared['staging_dir']) / 'payload-intent.json').exists())

class GroupedReuseTests(unittest.TestCase):
    def test_complete_12_and_13_have_same_admission(self):
        old = record12('focused', discovery=1, verification=1)
        new = record13()
        self.assertIsNone(coverage_reuse_issue(old))
        self.assertIsNone(coverage_reuse_issue(new))

    def test_justified_nonapplicable_area_is_allowed(self):
        record = record13()
        area = record['coverage']['areas'][3]
        area.update(applicability='not_applicable', applicability_reason='No persistence')
        area['groups'][0].update(status='not_applicable', reason='No persistence', evidence_ids=[])
        self.assertIsNone(coverage_reuse_issue(record))

    def test_unknown_partial_and_material_coverage_remain_ineligible(self):
        for change in ('unknown', 'partial', 'material', 'limitation'):
            record = record13()
            area = record['coverage']['areas'][0]
            if change == 'unknown': area.update(applicability='undetermined', applicability_reason='Unknown')
            elif change in ('partial', 'material'):
                area['groups'] = [group(['A01']), group(['A02','A03','A04','A05'], status='not_evaluated', reason='Pending', evidence_ids=[], material=change=='material')]
            else: record['coverage']['limitations'] = [{'detail':'Pending', 'kind':'validation', 'material':True, 'public_summary':None}]
            self.assertEqual(coverage_reuse_issue(record)['code'], 'previous_coverage_incomplete', change)

    def test_rereview_requires_verified_ordinary_lineage(self):
        record = record13()
        record['presentation']['kind'] = 'rereview'
        self.assertEqual(coverage_reuse_issue(record)['code'], 'ordinary_coverage_unproven')
        self.assertIsNone(coverage_reuse_issue(record, ordinary_coverage_verified=True))
        record['coverage']['areas'][0]['applicability'] = 'undetermined'
        self.assertEqual(coverage_reuse_issue(record, ordinary_coverage_verified=True)['code'], 'previous_coverage_incomplete')
