"""Dimension evidence has the same semantic check-ID gate as area evidence."""
import copy
import unittest
from script_test_support import enable_package_imports
enable_package_imports()
from ccr.contracts import review
from ccr.contracts.semantic_references import validate_semantic_references
from traceability_fixtures import record11


class DimensionReferenceTests(unittest.TestCase):
    def test_each_dimension_rejects_unretained_check_claims(self):
        source = record11()
        for area_index, area in enumerate(source['coverage']['areas']):
            for dimension_index, dimension in enumerate(area['dimensions']):
                with self.subTest(dimension=dimension['id']):
                    value = copy.deepcopy(source)
                    value['coverage']['areas'][area_index]['dimensions'][dimension_index]['details'] = 'Observed pass of C999 proves this coverage'
                    self.assertEqual(review.validate(value), [])
                    issues = validate_semantic_references(value, [], None, {})
                    field = f'coverage.areas[{area_index}].dimensions[{dimension_index}].details'
                    self.assertTrue(any(row['code'] == 'unknown_check' and row['field'] == field
                                        and row['reference'] == 'C999' for row in issues))

    def test_retained_check_and_static_dimension_details_remain_valid(self):
        value = record11()
        value['coverage']['areas'][0]['dimensions'][0]['details'] = 'C001 observed; adjacent code inspected statically'
        issues = validate_semantic_references(value, [], None, {})
        self.assertNotIn('unknown_check', {row['code'] for row in issues})
