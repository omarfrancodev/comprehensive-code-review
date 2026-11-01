import unittest

from script_test_support import enable_package_imports
enable_package_imports()

from ccr.reporting import check_disclosure, comment, delivery, projections, render
from test_review_coverage13 import group, record13
from traceability_fixtures import publication_contexts


class Coverage13RenderingTests(unittest.TestCase):
    def test_report_renders_one_matrix_and_no_repeated_evidence(self):
        record = record13()
        report = render.render(record)
        self.assertEqual(report.count('### Matriz ABCDE'), 1)
        self.assertNotIn('### Dimensiones de cobertura', report)
        self.assertLessEqual(report.count('Inspección del flujo'), 1)
        self.assertIn('A — Arquitectura y diseño', report)

    def test_material_gap_is_visible_without_expanded_dimension_table(self):
        record = record13()
        record['coverage']['areas'][0]['groups'] = [
            group(['A01']), group(['A02', 'A03', 'A04', 'A05'],
                                 status='not_evaluated', reason='No se verificó el fallback',
                                 evidence_ids=[], material=True)]
        record['verdict'] = 'insufficient_evidence'
        report = render.render(record)
        self.assertIn('No se verificó el fallback', report)
        self.assertIn('[material]', report)

    def test_public_checks_require_schema12_disclosure_and_editorial_context(self):
        record = record13()
        with self.assertRaises(ValueError):
            check_disclosure.disclosure_view(record, None, None)
        with self.assertRaises(ValueError):
            projections.public_checks(record)

    def test_material_group_is_visible_to_public_limitations(self):
        record = record13()
        record['coverage']['areas'][0]['groups'] = [
            group(['A01']), group(['A02', 'A03', 'A04', 'A05'],
                                 status='not_evaluated', reason='No se verificó el fallback',
                                 evidence_ids=[], material=True)]
        with self.assertRaises(ValueError):
            projections.public_limitations(record)
        record['coverage']['limitations'] = [{'kind': 'execution', 'detail': 'No se verificó el fallback',
            'material': True, 'public_summary': 'El fallback no está acreditado'}]
        rows = projections.public_limitations(record)
        self.assertTrue(any(row['material'] and 'fallback' in row['detail'] for row in rows))

    def test_nonmaterial_private_group_is_not_exposed_with_material_gap(self):
        record = record13()
        record['coverage']['areas'][0]['groups'] = [
            group(['A01']), group(['A02'], status='not_evaluated',
                reason='Cuota interna agotada', evidence_ids=[], material=False),
            group(['A03', 'A04', 'A05'], status='not_evaluated',
                reason='Fallback pendiente', evidence_ids=[], material=True)]
        record['coverage']['limitations'] = [{'kind': 'execution', 'detail': 'Fallback pendiente',
            'material': True, 'public_summary': 'El fallback no está acreditado'}]
        rows = projections.public_limitations(record)
        self.assertNotIn('Cuota interna', str(rows))
        self.assertIn('fallback', str(rows))

    def test_portable_projection_classifies_grouped_fields_and_removes_private_paths(self):
        record = record13()
        record['checks'] = []
        record['coverage']['evidence'][0]['detail'] = 'Revisado en C:\\private\\source.py password=hunter2'
        projection = delivery._Projection(record, {'repository_path': '', 'archive_root': ''},
                                          'C:/work/project', 'a' * 64)
        value = projection.value(record)
        self.assertEqual(value['coverage']['areas'][0]['groups'][0]['ids'],
                         record['coverage']['areas'][0]['groups'][0]['ids'])
        self.assertNotIn('C:\\private', value['coverage']['evidence'][0]['detail'])
        self.assertNotIn('hunter2', value['coverage']['evidence'][0]['detail'])

    def test_brief_projection_renders_grouped_gaps_without_dimensions(self):
        record = record13()
        record['coverage']['areas'][0]['groups'] = [
            group(['A01']), group(['A02', 'A03', 'A04', 'A05'],
                                 status='not_evaluated', reason='Fallback pendiente',
                                 evidence_ids=[], material=True)]
        record['verdict'] = 'insufficient_evidence'
        text = delivery._brief(record)
        self.assertIn('Fallback pendiente', text)
        self.assertNotIn('### Dimensiones de cobertura', text)

    def test_public_no_checks_still_uses_new_privacy_policy(self):
        record = record13()
        record['checks'] = []
        record['coverage']['areas'][0]['groups'] = [
            group(['A01']), group(['A02', 'A03', 'A04', 'A05'],
                                 status='not_evaluated', reason='password=hunter2',
                                 evidence_ids=[], material=True)]
        record['verdict'] = 'insufficient_evidence'
        record['coverage']['limitations'] = [{'kind': 'execution', 'detail': 'password=hunter2',
            'material': True, 'public_summary': 'Una ruta crítica permanece sin verificar'}]
        draft = comment.prepare_public_comment(record, **publication_contexts(record))
        self.assertEqual(draft['schema_version'], 3)
        self.assertNotIn('hunter2', draft['body'])


if __name__ == '__main__':
    unittest.main()
