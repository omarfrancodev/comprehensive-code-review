import unittest

import test_review_checkpoints as checkpoints
from ccr.archive import lifecycle, retention
from test_review_coverage13 import areas
from traceability_fixtures import PURPOSE


class Full13ArchiveTests(unittest.TestCase):
    def test_full13_checkpoint_retain_close_and_validate(self):
        class Checkpoint13(checkpoints.CheckpointTests):
            def final_record(self, run, profile='focused', late_profile=False):
                value = super().final_record(run, profile, late_profile)
                value['schema_version'] = 13
                value['coverage']['areas'] = areas()
                value['coverage']['evidence'] = [
                    {'id': 'EV001', 'kind': 'static', 'detail': 'Flujo inspeccionado',
                     'check_id': None, 'reference': None}]
                for check in value['checks']:
                    check['purpose'] = PURPOSE
                return value

        case = Checkpoint13('test_valid_final_checkpoint_can_be_promoted_without_external_files')
        self.addCleanup(case.doCleanups)
        case.setUp()
        run, _, _ = case.prepare_promotable_checkpoint()
        retention.retain(run, expected_schema=13)
        self.assertTrue(lifecycle.validate(run, require_retained=True)['retained'])
        lifecycle.close(run, case.write('cleanup13.json', {'cleanup': 'not_needed', 'residuals': []}))
        self.assertEqual(lifecycle.validate(run, require_complete=True)['state'], 'complete')
