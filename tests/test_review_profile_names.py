"""Renamed strategies preserve verification gates and immutable historical records."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_review_contract import contract, finding, MODULE_PATH
import test_review_delivery as delivery_tests
from test_review_extended import extended_record
from test_review_traceability_contract import record6

delivery = delivery_tests.delivery
artifacts = delivery_tests.artifacts


def record7(profile='standard'):
    value = record6()
    value.update(schema_version=7, profile=profile)
    return value


class ProfileNameTests(unittest.TestCase):
    def test_request_aliases_normalize_without_selecting_a_different_strategy(self):
        for requested, canonical in [('economy', 'focused'), ('balanced', 'standard'),
                                     ('focused', 'focused'), ('standard', 'standard'),
                                     ('deep', 'deep'), ('extended', 'extended')]:
            self.assertEqual(contract.normalize_profile(requested), canonical)
        for invalid in ('auto', 'multi', 'economic', '', None, [], {}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                contract.normalize_profile(invalid)

    def test_schema7_accepts_only_new_canonical_names_without_mutation(self):
        for profile in ('focused', 'standard', 'deep', 'extended'):
            value = record7(profile)
            before = copy.deepcopy(value)
            self.assertEqual(contract.validate(value), [])
            self.assertEqual(value, before)
        for invalid in ('economy', 'balanced', 'multi', [], {}):
            value = record7(invalid)
            self.assertIn('profile: invalid value', contract.validate(value))

    def test_historical_schema6_keeps_old_names_and_rendering(self):
        for profile, label in [('economy', 'económico'), ('balanced', 'equilibrado')]:
            value = record6()
            value['profile'] = profile
            before = copy.deepcopy(value)
            self.assertEqual(contract.validate(value), [])
            self.assertIn('- **Perfil:** ' + label, contract.render(value))
            self.assertEqual(value, before)
            value['profile'] = contract.normalize_profile(profile)
            self.assertIn('profile: invalid value', contract.validate(value))
        for profile in ('focused', 'standard'):
            value = extended_record()
            value['profile'] = profile
            self.assertIn('profile: invalid value', contract.validate(value))

    def test_standard_keeps_substantive_code_verification_even_for_p3(self):
        value = record7()
        value['coverage']['verification'] = 'skipped'
        item = finding()
        item.update(id='F001', priority='P3')
        value['findings'] = [item]
        self.assertTrue(any('coverage.verification' in error for error in contract.validate(value)))

    def test_standard_keeps_material_question_verification(self):
        value = record7()
        value['coverage'].update(verification='skipped', adequate=False)
        value['coverage']['limitations'] = [{'detail': 'Expected consumer behavior unknown', 'material': True}]
        value['verdict'] = 'insufficient_evidence'
        self.assertTrue(any('coverage.verification' in error for error in contract.validate(value)))

    def test_deep_extended_keep_invariant_verification_with_no_candidates(self):
        for profile in ('deep', 'extended'):
            value = record7(profile)
            value['coverage']['verification'] = 'skipped'
            self.assertTrue(any('coverage.verification' in error for error in contract.validate(value)))
            value['coverage'].update(verification='unavailable', adequate=False)
            value['coverage']['limitations'] = [{'detail': 'Independent sessions unavailable', 'material': True}]
            value['verdict'] = 'insufficient_evidence'
            self.assertEqual(contract.validate(value), [])

    def test_schema7_preserves_identity_and_canonical_id_gates(self):
        value = record7('focused')
        value['findings'] = [dict(finding(), id='F1')]
        self.assertTrue(any('expected canonical' in error for error in contract.validate(value)))
        value['findings'][0]['id'] = 'D-F001'
        allocated, mapping = contract.canonicalize_ids(value)
        self.assertEqual(allocated['findings'][0]['id'], 'F001')
        self.assertEqual(mapping['findings']['D-F001'], 'F001')
        self.assertEqual(allocated['profile'], 'focused')
        self.assertEqual(contract.validate(allocated), [])
        for field in ('review_id', 'previous_reviews', 'grandfathered_ids', 'change_authors', 'presentation'):
            invalid = record7()
            del invalid[field]
            self.assertTrue(any(field in error for error in contract.validate(invalid)))

    def test_schema7_cli_and_public_projection(self):
        with tempfile.TemporaryDirectory(prefix='ccr-names-') as directory:
            path = Path(directory) / 'review.json'
            value = record7('focused')
            path.write_text(json.dumps(value), encoding='utf-8')
            for command in ('validate', 'render-user', 'render-comment'):
                result = subprocess.run([sys.executable, '-B', '-X', 'utf8', str(MODULE_PATH),
                                         command, '--input', str(path)], capture_output=True, text=True, encoding='utf-8')
                self.assertEqual(result.returncode, 0, result.stderr)
                if command == 'render-user':
                    self.assertIn('focused', result.stdout)
                elif command == 'render-comment':
                    self.assertNotIn('**Perfil:**', result.stdout)


class ProfileNameArchiveTests(unittest.TestCase):
    def setUp(self):
        self.fixture = delivery_tests.DeliveryTests()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()

    def prepare(self, value):
        fixture = self.fixture
        run = Path(artifacts.prepare(fixture.repo, fixture.write('scope.json', value['scope']),
                                     '2.8.0', 'codex', output_root=fixture.archive))
        value['review_id'] = 'CR-' + artifacts.read_json(run / 'cierre.json')['run_id']
        return run

    def test_schema7_retention_closure_and_full_delivery_preserve_identity(self):
        value = record7()
        run = self.prepare(value)
        artifacts.retain(run, self.fixture.write('final.json', value))
        artifacts.close(run, cleanup='not_needed', residuals=[])
        before = self.fixture.snapshot(run)
        target = Path(delivery.deliver(run, 'full', self.fixture.repo))
        projected = artifacts.read_json(target / 'review.json')
        receipt = artifacts.read_json(target / '.ccr-delivery.json')
        self.assertEqual((projected['schema_version'], projected['profile']), (7, 'standard'))
        self.assertEqual(projected['review_id'], value['review_id'])
        self.assertEqual(target.name, value['review_id'])
        self.assertEqual((receipt['source_id_kind'], receipt['source_id']), ('review_id', value['review_id']))
        self.assertEqual(contract.validate(projected), [])
        self.assertEqual(before, self.fixture.snapshot(run))

    def test_schema7_retention_rejects_review_identity_from_another_run(self):
        value = record7('focused')
        run = self.prepare(value)
        value['review_id'] = 'CR-' + 'b' * 20
        with self.assertRaises(ValueError):
            artifacts.retain(run, self.fixture.write('final.json', value))
        self.assertFalse((run / 'review.json').exists())


if __name__ == '__main__':
    unittest.main()
