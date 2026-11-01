import hashlib
import json
from pathlib import Path
import unittest

import test_review_checkpoints as checkpoints
from ccr.archive import lifecycle, retention
from test_review_coverage13 import areas
from traceability_fixtures import PURPOSE
from ccr.reporting import delivery
from ccr.contracts.check_disclosure import EXPLANATION_COMMAND
from test_review_traceability_contract import check as static_check


class Full13ArchiveTests(unittest.TestCase):
    def complete_archive(self, with_checks=False, record_update=None):
        class Checkpoint13(checkpoints.CheckpointTests):
            def final_record(self, run, profile='focused', late_profile=False):
                value = super().final_record(run, profile, late_profile)
                value['schema_version'] = 13
                value['coverage']['areas'] = areas()
                value['coverage']['evidence'] = [
                    {'id': 'EV001', 'kind': 'static', 'detail': 'Flujo inspeccionado',
                     'check_id': None, 'reference': None}]
                if with_checks:
                    value['checks'] = [dict(static_check(), command='Static flow inspection',
                        revision=value['scope']['head'], execution={'kind': 'static', 'executor': None})]
                for check in value['checks']:
                    check['purpose'] = PURPOSE
                if record_update is not None:
                    record_update(value)
                return value

        case = Checkpoint13('test_valid_final_checkpoint_can_be_promoted_without_external_files')
        self.addCleanup(case.doCleanups)
        case.setUp()
        run, _, _ = case.prepare_promotable_checkpoint()
        retention.retain(run, expected_schema=13)
        self.assertTrue(lifecycle.validate(run, require_retained=True)['retained'])
        lifecycle.close(run, case.write('cleanup13.json', {'cleanup': 'not_needed', 'residuals': []}))
        self.assertEqual(lifecycle.validate(run, require_complete=True)['state'], 'complete')
        return case, Path(run)

    def test_full13_checkpoint_retain_close_and_validate(self):
        self.complete_archive()

    def test_full_and_brief_deliver_full13_without_selected_disclosure(self):
        case, run = self.complete_archive(with_checks=True)
        record = json.loads((run / 'review.json').read_bytes())
        self.assertTrue(record['checks'])
        context = json.loads((run / 'evidence/context.json').read_bytes())
        self.assertNotIn('check_disclosure_reference', context)
        before = {p.relative_to(run): p.read_bytes() for p in run.rglob('*') if p.is_file()}
        for mode in ('full', 'brief'):
            target = delivery.deliver(run, mode, case.repo, case.root / mode)
            report = (target / ('informe.md' if mode == 'full' else 'resumen.md')).read_text(encoding='utf-8')
            self.assertIn('Detalle acreditado de checks', report)
            receipt = json.loads((target / '.ccr-delivery.json').read_bytes())
            self.assertEqual(receipt['source_hash'], hashlib.sha256(before[Path('review.json')]).hexdigest())
            self.assertIsNotNone(receipt['check_disclosure_sha256'])
            if mode == 'full':
                portable = json.loads((target / 'review.json').read_bytes())
                self.assertEqual(portable['checks'][0]['command'], EXPLANATION_COMMAND)
            self.assertEqual(before, {p.relative_to(run): p.read_bytes() for p in run.rglob('*') if p.is_file()})
