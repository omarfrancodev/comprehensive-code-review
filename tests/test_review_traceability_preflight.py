import json
import unittest
from script_test_support import enable_package_imports

enable_package_imports()
from ccr.contracts import preflight
from recovery_fixtures import context10
from traceability_fixtures import record11, receipt2_bundle


class Preflight11Tests(unittest.TestCase):
    def evaluate(self, record, extra_sources=None, executors=None):
        context = context10(record)
        context['executors'] = executors or []
        manifest = dict(schema_version=8, layout_version=2, scope=record['scope'],
            profile_history=context['profile_history'], assignment_registry=context['execution_plan'],
            review_inputs=context['review_inputs'],
            logical_scope={'identity': context['review_inputs']['logical_scope_identity']})
        sources = {'evidence/context.json': json.dumps(context).encode()}
        sources.update(extra_sources or {})
        return preflight.validate_preflight(phase='retain', manifest=manifest,
            logical_scope=manifest['logical_scope'], selection=context['profile_history'][-1],
            context=context, record=record, sources=sources)

    def test_retain_preflight_rejects_missing_purpose_or_dimension(self):
        value = record11()
        del value['checks'][0]['purpose']
        result = self.evaluate(value)
        self.assertFalse(result['ready'])
        self.assertTrue(any('purpose' in issue['message'] for issue in result['issues']))
        value = record11()
        value['coverage']['areas'][0]['dimensions'].pop()
        self.assertTrue(any('dimension' in issue['message'] for issue in self.evaluate(value)['issues']))

    def test_receipt2_still_requires_selected_receipt_and_both_streams(self):
        value = record11()
        receipt, streams, binding, executors = receipt2_bundle()
        reference = 'evidence/attempt-C001-receipt.json'
        value['checks'][0].update(binding, reference=reference, reused=False)
        result = self.evaluate(value, executors=executors)
        self.assertIn('invalid_receipt', {issue['code'] for issue in result['issues']})
        sources = {**streams, reference: json.dumps(receipt).encode()}
        result = self.evaluate(value, sources, executors)
        self.assertNotIn('invalid_receipt', {issue['code'] for issue in result['issues']})

    def test_missing_purpose_is_rebuildable_candidate_not_a_new_review(self):
        from ccr.archive.inspection import continuation_decision
        value = record11()
        del value['checks'][0]['purpose']
        issues = self.evaluate(value)['issues']
        manifest = dict(schema_version=8, layout_version=2, state='processing',
                        retained=False, operation={'disposition': 'open'})
        decision = continuation_decision(manifest, input_appraisal={'applicability': 'applicable'},
                                         pending_operation=None, candidate_issues=issues)
        self.assertEqual(decision['action'], 'rebuild_candidate')
