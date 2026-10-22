"""Private, passive model observations remain separate from harness identity."""
import copy
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
from ccr.contracts import model_usage as models


REVIEW_ID = 'CR-' + 'a' * 20
ACTOR = {'kind': 'agent', 'name': 'reviewer', 'provider_id': 'ctx-1'}


class ModelUsageTests(unittest.TestCase):
    def test_runner_argument_is_configured_not_observed(self):
        item = models.observation_from_metadata(
            {'model': 'configured-A'}, actor=ACTOR, phase='discovery',
            activity='discovery', assignment_id='D1')
        self.assertEqual(item['configured_model'], 'configured-A')
        self.assertIsNone(item['observed_model'])
        self.assertEqual(item['status'], 'configured_only')
        self.assertEqual(item['actor']['provider_id'], 'ctx-1')

    def test_observed_claim_from_runner_argument_is_not_promoted(self):
        item = models.observation_from_metadata(
            {'model': 'configured-A', 'observed_model': 'claimed-B',
             'model_source': {'kind': 'runner_argument', 'reference': None}},
            actor=ACTOR, phase='discovery', activity='discovery')
        self.assertEqual(item['configured_model'], 'configured-A')
        self.assertIsNone(item['observed_model'])
        self.assertEqual(item['status'], 'configured_only')

    def test_explicit_observed_source_and_runner_configuration_are_both_preserved(self):
        item = models.observation_from_metadata(
            {'model': 'configured-A', 'observed_model': 'observed-B',
             'model_source': {'kind': 'platform', 'reference': 'call-17'}},
            actor=ACTOR, phase='verification', activity='verification', check_id='C001')
        self.assertEqual(item['configured_model'], 'configured-A')
        self.assertEqual(item['observed_model'], 'observed-B')
        self.assertEqual(item['status'], 'observed')
        self.assertEqual(item['source'], {'kind': 'platform', 'reference': 'call-17'})

    def test_missing_model_is_unknown_without_extra_work(self):
        with patch.object(subprocess, 'run') as run:
            item = models.observation_from_metadata(
                {}, actor={'kind': 'coordinator', 'name': 'coordinator', 'provider_id': None},
                phase='report', activity='reporting')
        run.assert_not_called()
        self.assertEqual(item['status'], 'unknown')
        self.assertIsNone(item['observed_model'])
        self.assertIsNone(item['configured_model'])

    def test_not_applicable_does_not_inherit_a_model(self):
        item = models.observation_from_metadata(
            {'model': 'configured-A', 'source': {'kind': 'not_applicable', 'reference': None}},
            actor={'kind': 'process', 'name': 'dotnet test', 'provider_id': None},
            phase='verification', activity='check')
        self.assertEqual(item['status'], 'not_applicable')
        self.assertIsNone(item['configured_model'])
        self.assertIsNone(item['observed_model'])

    def test_model_switch_preserves_each_observation_and_assignment(self):
        first = models.observation_from_metadata(
            {'observed_model': 'observed-A', 'model_source': {
                'kind': 'platform', 'reference': 'call-1'}}, actor=ACTOR,
            phase='discovery', activity='discovery', assignment_id='D1')
        second = models.observation_from_metadata(
            {'observed_model': 'observed-B', 'model_source': {
                'kind': 'platform', 'reference': 'call-2'}}, actor=ACTOR,
            phase='verification', activity='verification', assignment_id='V1')
        ledger = models.append_model_observation(
            None, first, review_id=REVIEW_ID, harness_id='codex-desktop')
        before = copy.deepcopy(ledger)
        updated = models.append_model_observation(
            ledger, second, review_id=ledger['review_id'], harness_id=ledger['harness_id'])
        self.assertEqual(ledger, before)
        self.assertEqual(updated['entries'][:-1], before['entries'])
        self.assertEqual([row['observed_model'] for row in updated['entries']],
                         ['observed-A', 'observed-B'])
        self.assertEqual([row['assignment_id'] for row in updated['entries']], ['D1', 'V1'])
        self.assertEqual([row['id'] for row in updated['entries']], ['M0001', 'M0002'])

    def test_observed_conflict_is_preserved_as_a_new_row(self):
        metadata = {'observed_model': 'model-A', 'model_source': {
            'kind': 'adapter_observed', 'reference': 'call-1'}}
        first = models.observation_from_metadata(metadata, actor=ACTOR,
            phase='discovery', activity='discovery', assignment_id='D1')
        second = models.observation_from_metadata(
            {'observed_model': 'model-B', 'model_source': metadata['model_source']}, actor=ACTOR,
            phase='discovery', activity='discovery', assignment_id='D1')
        ledger = models.append_model_observation(None, first, review_id=REVIEW_ID,
                                                  harness_id='codex-desktop')
        updated = models.append_model_observation(ledger, second, review_id=REVIEW_ID,
                                                   harness_id='codex-desktop')
        self.assertEqual([row['observed_model'] for row in updated['entries']],
                         ['model-A', 'model-B'])
        self.assertEqual([row['status'] for row in updated['entries']], ['observed', 'conflict'])

    def test_validation_binds_review_harness_schema_and_limits(self):
        item = models.observation_from_metadata({'model': 'configured-A'}, actor=ACTOR,
            phase='discovery', activity='discovery', assignment_id='D1')
        ledger = models.append_model_observation(None, item, review_id=REVIEW_ID,
                                                  harness_id='codex-desktop')
        self.assertEqual(models.validate_model_usage(
            ledger, review_id=REVIEW_ID, harness_id='codex-desktop'), [])
        self.assertTrue(models.validate_model_usage(
            ledger, review_id='CR-' + 'b' * 20, harness_id='codex-desktop'))
        self.assertTrue(models.validate_model_usage(
            ledger, review_id=REVIEW_ID, harness_id='claude-code-desktop'))
        too_many = copy.deepcopy(ledger)
        too_many['entries'] *= 257
        self.assertTrue(models.validate_model_usage(
            too_many, review_id=REVIEW_ID, harness_id='codex-desktop'))
        large_observation = models.normalize_model_observation({
            'phase': 'p' * 64, 'activity': 'other', 'assignment_id': 'a' * 120,
            'check_id': 'c' * 120,
            'actor': {'kind': 'k' * 64, 'name': 'n' * 120, 'provider_id': 'v' * 256},
            'configured_model': 'm' * 200, 'observed_model': None,
            'source': {'kind': 'dispatch', 'reference': 'r' * 500}, 'occurred_at': None})
        large_ledger = {'schema_version': 1, 'review_id': REVIEW_ID,
                        'harness_id': 'codex-desktop', 'entries': []}
        for index in range(256):
            row = dict(large_observation, id='M' + str(index + 1).zfill(4))
            row['assignment_id'] = 'a' * 119 + chr(65 + index % 26)
            large_ledger['entries'].append(row)
        self.assertTrue(any('256 KiB' in issue['message'] for issue in
            models.validate_model_usage(large_ledger, review_id=REVIEW_ID,
                                        harness_id='codex-desktop')))
        too_large = copy.deepcopy(ledger)
        too_large['entries'][0]['configured_model'] = 'm' * 201
        with self.assertRaises(ValueError):
            models.normalize_model_observation({key: value for key, value in
                too_large['entries'][0].items() if key not in {'id', 'status'}})

    def test_sidecar_is_private_and_never_added_to_public_comment(self):
        from script_test_support import contract_api
        review_contract = contract_api()
        from publication_fixtures import check_classification, publication_record
        record = publication_record()
        comment = review_contract.render(record, audience='comment',
                                         check_publication_context=check_classification(record))
        self.assertNotIn('model-usage', comment)
        self.assertNotIn('configured_model', comment)


if __name__ == '__main__':
    unittest.main()
