"""Pure normalization and freshness appraisal for review inputs."""
import copy
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import review_inputs

from recovery_fixtures import record10


class ReviewInputTests(unittest.TestCase):
    def setUp(self):
        self.scope = copy.deepcopy(record10('standard')['scope'])

    def current(self, **updates):
        value = {'scope': copy.deepcopy(self.scope), 'sources': {}, 'source_set_complete': True,
                 'description_identity': None, 'requirements_identity': None,
                 'plan_identity': None, 'configuration_identity': None, 'profile': 'standard'}
        value.update(updates)
        return value

    def test_normalize_preserves_the_common_input_shape(self):
        value = self.current(sources={'evidence/spec.md': 'a' * 64},
                             description_identity='description-v1', profile='balanced')
        normalized = review_inputs.normalize_inputs(value)
        self.assertEqual(normalized['scope'], self.scope)
        self.assertEqual(normalized['sources'], value['sources'])
        self.assertTrue(normalized['source_set_complete'])
        self.assertEqual(normalized['description_identity'], 'description-v1')
        self.assertEqual(normalized['profile'], 'standard')

    def test_empty_sources_without_completeness_are_unknown(self):
        retained = {'scope': copy.deepcopy(self.scope), 'sources': {}}
        current = {'scope': copy.deepcopy(self.scope), 'sources': {}}
        self.assertEqual(review_inputs.compare_inputs(retained, current)['applicability'], 'unknown')

    def test_explicit_complete_empty_source_set_is_applicable(self):
        retained = self.current()
        current = self.current()
        self.assertEqual(review_inputs.compare_inputs(retained, current),
                         {'applicability': 'applicable', 'differences': []})

    def test_omitted_known_description_identity_is_unknown(self):
        retained = self.current(description_identity='description-v1')
        current = self.current()
        current.pop('description_identity')
        result = review_inputs.compare_inputs(retained, current)
        self.assertEqual(result['applicability'], 'unknown')
        self.assertIn('description_identity', {row['field'] for row in result['differences']})

    def test_changed_description_and_spec_are_detected_at_same_head(self):
        retained = self.current(sources={'spec.md': 'a' * 64},
                                description_identity='description-v1', requirements_identity='req-v1')
        current = self.current(sources={'spec.md': 'b' * 64},
                               description_identity='description-v2', requirements_identity='req-v2')
        result = review_inputs.compare_inputs(retained, current)
        self.assertEqual(result['applicability'], 'changed')
        self.assertEqual({row['field'] for row in result['differences']},
                         {'sources.spec.md', 'description_identity', 'requirements_identity'})

    def test_caller_limit_does_not_limit_retained_inventory(self):
        many = {f'evidence/{index}.md': f'{index:064x}' for index in range(70)}
        with self.assertRaisesRegex(ValueError, '64'):
            review_inputs.normalize_inputs(self.current(sources=many))
        normalized = review_inputs.normalize_inputs(self.current(sources=many), caller=False)
        self.assertEqual(len(normalized['sources']), 70)

    def test_unknown_retained_inputs_remain_unknown(self):
        self.assertEqual(review_inputs.compare_inputs(None, self.current())['applicability'], 'unknown')


if __name__ == '__main__':
    unittest.main()
