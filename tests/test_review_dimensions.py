import unittest
from script_test_support import enable_package_imports

enable_package_imports()
from ccr.contracts import dimensions as dims
from traceability_fixtures import dimension_row, dimension_areas


class DimensionTests(unittest.TestCase):
    def test_catalog_completeness_and_hostile_ids(self):
        expected = {a: tuple(f'{a}{i:02d}' for i in range(1, n + 1))
                    for a, n in [('A', 5), ('B', 5), ('C', 5), ('D', 5), ('E', 7)]}
        self.assertEqual(dims.DIMENSIONS, expected)
        self.assertEqual(dims.validate_dimensions(dimension_areas(), set()), [])
        for index, area in enumerate(dimension_areas()):
            for item in area['dimensions']:
                rows = dimension_areas()
                rows[index]['dimensions'] = [d for d in rows[index]['dimensions'] if d['id'] != item['id']]
                self.assertTrue(dims.validate_dimensions(rows, set()))
        for invalid in ([], {}, None, 'Z99', 'E01', 'A02'):
            rows = dimension_areas()
            rows[0]['dimensions'][0]['id'] = invalid
            self.assertTrue(dims.validate_dimensions(rows, set()))

    def test_summary_states_and_no_hidden_material_gap(self):
        for states, expected in [(['not_applicable'], 'not_applicable'),
            (['covered', 'not_applicable'], 'covered'), (['not_evaluated'], 'not_evaluated'),
            (['covered', 'not_evaluated'], 'partial'), (['partial'], 'partial')]:
            rows = [dimension_row(f'A{i:02d}', status=s) for i, s in enumerate(states, 1)]
            self.assertEqual(dims.dimension_summary(rows)['status'], expected)
        rows = dimension_areas()
        rows[0]['dimensions'][0].update(status='partial', material=True, finding_ids=['F001'])
        self.assertTrue(dims.validate_dimensions(rows, {'F001'}))
        rows[0].update(dims.dimension_summary(rows[0]['dimensions']))
        self.assertEqual(dims.validate_dimensions(rows, {'F001'}), [])
        rows[0]['dimensions'][0].update(status='not_applicable')
        self.assertTrue(dims.validate_dimensions(rows, {'F001'}))

    def test_exact_fields_and_details_are_required(self):
        for mutation in ({'details': ' '}, {'extra': 1}, {'material': 'true'}):
            rows = dimension_areas()
            rows[0]['dimensions'][0].update(mutation)
            self.assertTrue(dims.validate_dimensions(rows, set()))

    def test_malformed_collections_are_diagnostics(self):
        for areas in (None, {}, [None], [{'area': []}], [{'area': 'A', 'dimensions': None}]):
            self.assertTrue(dims.validate_dimensions(areas, set()))
