"""A local review survives handoff, closure and an independent archive check."""
import json
from pathlib import Path
import subprocess
import sys
import unittest

import test_review_artifacts as fixtures
from test_review_traceability_contract import record6, check


class LocalReviewTransferTests(unittest.TestCase):
    setUp = fixtures.ArchiveTests.setUp
    git = fixtures.ArchiveTests.git
    write = fixtures.ArchiveTests.write
    prepare = fixtures.ArchiveTests.prepare
    read = fixtures.ArchiveTests.read

    def final_record(self, run):
        value = record6()
        value['scope'] = self.read(self.scope)
        value['scope']['mode'] = 'range'
        value['scope']['reference'] = 'feature/local-change'
        value['description'] = {'status': 'not_applicable', 'identity': None, 'details': ''}
        value['review_id'] = 'CR-' + self.read(run / 'cierre.json')['run_id']
        value['checks'] = [check()]
        value['checks'][0].update(command='test relevant behavior', revision=value['scope']['head'],
                                  evidence='37 passed; 2 skipped because the optional service was unavailable.')
        return value

    def test_local_handoff_context_survives_close_and_cli_validation_is_read_only(self):
        scope = self.read(self.scope)
        scope.update(mode='range', reference='feature/local-change')
        self.scope.write_text(json.dumps(scope), encoding='utf-8')
        run = self.prepare()
        final = self.write('final6.json', self.final_record(run))
        context = self.write('handoff-context.json', {
            'source_record': 'review.json', 'source_report': 'informe.md',
            'requirements': [{'title': 'Spec captured at the reviewed revision',
                              'reference': 'https://example.test/spec', 'identity': 'reviewed revision'}],
            'plan': [{'title': 'Implementation plan captured at the reviewed revision',
                      'reference': 'https://example.test/plan', 'identity': 'reviewed revision'}],
            'decisions_pending': ['Confirm the optional-service scenario before deployment']})
        fixtures.artifacts.retain(run, final, handoff=True, handoff_context_input=context)
        fixtures.artifacts.validate(run, require_retained=True)
        fixtures.artifacts.close(run, cleanup='not_needed', residuals=[])
        handoff = (run / 'handoff.md').read_text(encoding='utf-8')
        report = (run / 'informe.md').read_text(encoding='utf-8')
        self.assertIn('Spec captured', handoff)
        self.assertIn('Confirm the optional-service', handoff)
        self.assertIn('37 passed; 2 skipped', report)
        self.assertIn('### Hallazgos', report)
        self.assertNotIn('Responsable del MR/PR', handoff)
        self.assertNotIn('**MR/PR:**', handoff)
        inventory = {path.name: path.read_bytes() for path in run.iterdir() if path.is_file()}
        result = subprocess.run([sys.executable, str(Path(fixtures.artifacts.__file__)),
                                 'validate', '--run-dir', str(run), '--require-retained'],
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(inventory, {path.name: path.read_bytes() for path in run.iterdir() if path.is_file()})

    def test_wrong_report_identity_is_refused_without_replacing_retained_report(self):
        run = self.prepare()
        value = record6()
        value['scope'] = self.read(self.scope)
        value['description'] = {'status': 'not_applicable', 'identity': None, 'details': ''}
        value['review_id'] = 'CR-' + self.read(run / 'cierre.json')['run_id']
        final = self.write('correct6.json', value)
        fixtures.artifacts.retain(run, final)
        before = (run / 'review.json').read_bytes()
        value['review_id'] = 'CR-' + 'f' * 20
        wrong = self.write('wrong6.json', value)
        with self.assertRaisesRegex(ValueError, 'identity|review_id'):
            fixtures.artifacts.retain(run, wrong)
        self.assertEqual(before, (run / 'review.json').read_bytes())
        fixtures.artifacts.validate(run, require_retained=True)


if __name__ == '__main__':
    unittest.main()
