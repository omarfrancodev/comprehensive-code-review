import copy
from pathlib import Path
import unittest
from script_test_support import enable_package_imports

enable_package_imports()
import test_review_artifacts as old
import test_review_checkpoints as checkpoints
from ccr.archive import retention, lifecycle
from traceability_fixtures import record11, dimension_areas, PURPOSE


class TraceabilityCheckpointTests(checkpoints.CheckpointTests):
    def final_record(self, run, profile='focused', late_profile=False):
        value = super().final_record(run, profile, late_profile)
        value['schema_version'] = 11
        value['coverage']['areas'] = dimension_areas()
        for check in value['checks']:
            check['purpose'] = PURPOSE
        return value


class Archive11Tests(unittest.TestCase):
    git = old.ArchiveTests.git
    write = old.ArchiveTests.write
    read = old.ArchiveTests.read
    snapshot = old.ArchiveTests.snapshot
    prepare = old.ArchiveTests.prepare
    retain = old.ArchiveTests.retain
    close = old.ArchiveTests.close

    def setUp(self):
        old.ArchiveTests.setUp(self)
        self.scope = self.write('scope11.json', record11()['scope'])

    def test_checkpoint_promotes_exact_11_bytes(self):
        case = TraceabilityCheckpointTests('test_valid_final_checkpoint_can_be_promoted_without_external_files')
        self.addCleanup(case.doCleanups)
        case.setUp()
        run, _, _ = case.prepare_promotable_checkpoint()
        before = (run / 'pending' / 'review.json').read_bytes()
        retention.retain(run, expected_schema=11)
        self.assertEqual((run / 'review.json').read_bytes(), before)
        self.assertEqual(case.read(run / 'review.json')['schema_version'], 11)

    def test_missing_purpose_rejected_without_retained_output(self):
        run = self.prepare()
        value = record11()
        del value['checks'][0]['purpose']
        self.final = self.write('invalid11.json', value)
        with self.assertRaisesRegex(ValueError, 'purpose'):
            self.retain(run, expected_schema=11)
        self.assertFalse((run / 'review.json').exists())

    def test_valid_11_can_close_and_validate(self):
        run = self.prepare()
        self.final = self.write('final11.json', record11())
        self.retain(run, expected_schema=11)
        self.assertTrue(lifecycle.validate(run, require_retained=True)['retained'])
        self.close(run)
        self.assertEqual(lifecycle.validate(run, require_complete=True)['state'], 'complete')
