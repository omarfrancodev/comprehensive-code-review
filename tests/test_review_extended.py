"""Versioned extended profile, inherited report gates and durable retention."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import test_review_artifacts as archive_tests
from test_review_areas import area_record
from test_review_contract import MODULE_PATH, clean_record, contract
from test_review_flow_v24 import presented
from test_review_presentation import current_record


def extended_record():
    value = presented()
    value['schema_version'] = 5
    value['profile'] = 'extended'
    value['profile_reason'] = 'Automatic: five separately required discovery assignments'
    return value


class ExtendedContractTests(unittest.TestCase):
    def test_schema5_accepts_all_profiles_without_mutating_input(self):
        for profile in ('economy', 'balanced', 'deep', 'extended'):
            with self.subTest(profile=profile):
                value = extended_record()
                value['profile'] = profile
                original = copy.deepcopy(value)
                self.assertEqual(contract.validate(value), [])
                self.assertEqual(value, original)

    def test_invalid_profile_types_report_errors_without_raising(self):
        for profile in ([], {}):
            with self.subTest(profile=profile):
                value = extended_record()
                value['profile'] = profile
                self.assertIn('profile: invalid value', contract.validate(value))

    def test_legacy_schemas_keep_their_profile_enums(self):
        for value in (clean_record(), area_record(), current_record(), presented()):
            with self.subTest(version=value['schema_version']):
                self.assertEqual(contract.validate(value), [])
                value['profile'] = 'extended'
                self.assertIn('profile: invalid value', contract.validate(value))

    def test_schema5_inherits_required_presentation_authors_and_areas(self):
        for field in ('presentation', 'change_authors', 'areas'):
            with self.subTest(field=field):
                value = extended_record()
                del (value['coverage'] if field == 'areas' else value)[field]
                self.assertTrue(any(field in error for error in contract.validate(value)))

    def test_deep_and_extended_cannot_skip_invariant_verification_without_findings(self):
        for profile in ('deep', 'extended'):
            with self.subTest(profile=profile):
                value = extended_record()
                value.update(profile=profile, change_authors=[])
                value['coverage']['verification'] = 'skipped'
                self.assertTrue(any('coverage.verification' in error
                                    for error in contract.validate(value)))

    def test_extended_discloses_unavailable_verification_and_material_gap(self):
        value = extended_record()
        value['coverage'].update(verification='unavailable', adequate=False)
        value['coverage']['limitations'] = [{'detail': 'Independent sessions unavailable',
                                             'material': True}]
        value['verdict'] = 'insufficient_evidence'
        self.assertEqual(contract.validate(value), [])
        output = contract.render(value, 'comment')
        self.assertIn('Independent sessions unavailable', output)
        self.assertIn('EVIDENCIA INSUFICIENTE', output)
        value['verdict'] = 'approvable'
        self.assertTrue(contract.validate(value))

    def test_extended_user_label_and_public_projection_preserve_presentation(self):
        value = extended_record()
        before = copy.deepcopy(value)
        user, comment = contract.render(value), contract.render(value, 'comment')
        self.assertIn('- **Perfil:** extendido', user)
        self.assertIn('### Matriz ABCDE', user)
        self.assertNotIn('Matriz ABCDE', comment)
        self.assertNotIn('**Perfil:**', comment)
        self.assertIn('**Autores del cambio:** @ana; Luis', user)
        self.assertEqual(user.splitlines()[0], comment.splitlines()[0])
        self.assertEqual(value, before)

    def test_cli_validates_and_renders_schema5_both_audiences(self):
        with tempfile.TemporaryDirectory(prefix='review-extended-') as directory:
            path = Path(directory)/'review.json'
            path.write_text(json.dumps(extended_record()), encoding='utf-8')
            for command in ('validate', 'render-user', 'render-comment'):
                with self.subTest(command=command):
                    result = subprocess.run([sys.executable, '-B', str(MODULE_PATH),
                                             command, '--input', str(path)],
                                            capture_output=True, text=True, encoding='utf-8')
                    self.assertEqual(result.returncode, 0, result.stderr)
                    if command == 'validate':
                        self.assertTrue(json.loads(result.stdout)['valid'])
                    else:
                        self.assertEqual('Matriz ABCDE' in result.stdout,
                                         command == 'render-user')


class ExtendedArchiveTests(unittest.TestCase):
    def test_retention_validation_and_closure_keep_schema5_extended(self):
        fixture = archive_tests.ArchiveTests()
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        value = extended_record()
        value['scope'] = archive_tests.record()['scope']
        value['description'] = archive_tests.record()['description']
        value['responsible'] = archive_tests.record()['responsible']
        value['change_authors'] = []
        value['resources']['publication'] = 'not_requested'
        final = fixture.write('extended.json', value)
        run = Path(archive_tests.artifacts.prepare(fixture.repo, fixture.scope, '2.6.0',
                                                  'codex', output_root=fixture.output))
        archive_tests.artifacts.retain(run, final)
        archive_tests.artifacts.validate(run, require_retained=True)
        archive_tests.artifacts.close(run, cleanup='not_needed', residuals=[])
        retained = fixture.read(run/'review.json')
        closure = fixture.read(run/'cierre.json')
        self.assertEqual((retained['schema_version'], retained['profile']), (5, 'extended'))
        self.assertEqual(closure['schema_version'], 5)
        self.assertEqual(closure['cleanup'], 'not_needed')
        self.assertFalse((run/'measurements.json').exists())


if __name__ == '__main__':
    unittest.main()
