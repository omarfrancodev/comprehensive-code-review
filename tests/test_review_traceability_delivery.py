"""Portable schema-11 deliveries preserve traceability and source bytes."""
import copy
from pathlib import Path
import unittest
import test_review_traceability_archive as archives
from script_test_support import enable_package_imports
enable_package_imports()

from ccr.reporting import delivery, render as renderer
from traceability_fixtures import record11, publication_contexts, PURPOSE, set_dimension


class DeliveryTraceTests(unittest.TestCase):
    def test_full_and_brief_group_before_sanitizing_distinct_observations(self):
        from test_review_contract import finding
        fixture = archives.Archive11Tests()
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        run = fixture.prepare()
        value = record11()
        check = value['checks'][0]
        check.update(evidence=r'Run C:\one\state.txt', reference='https://example.test/checks/1',
                     execution=dict(kind='external', executor=None))
        item = finding()
        item.update(id='F001', evidence=[
            dict(kind='static', check_id=None, details=r'Static C:\one\state.txt'),
            dict(kind='static', check_id=None, details=r'Static C:\two\state.txt'),
            dict(kind='static', check_id=None, details=r'Static C:\one\state.txt'),
            dict(kind='executed', check_id='C001', details=check['evidence']),
            dict(kind='executed', check_id='C001', details=r'Run C:\two\state.txt')])
        value['findings'] = [item]
        set_dimension(value, 'B01', finding_ids=['F001'])
        fixture.final = fixture.write('observations11.json', value)
        fixture.retain(run, expected_schema=11)
        fixture.close(run)
        before = fixture.snapshot(run)
        for mode in ('full', 'brief'):
            with self.subTest(mode=mode):
                target = delivery.deliver(run, mode, fixture.repo, fixture.root/mode)
                text = (target/('informe.md' if mode == 'full' else 'resumen.md')).read_text(encoding='utf-8')
                findings = text.split('### Validación')[0]
                self.assertEqual(sum(line.strip().startswith('- **Inspección estática**')
                                     for line in findings.splitlines()), 2)
                self.assertIn(r'Run \[ruta privada\]', findings)
                self.assertIn('**[C001](#C001)**', findings)
                self.assertNotIn('C:\\one', text)
                self.assertNotIn('C:\\two', text)
        self.assertEqual(fixture.snapshot(run), before)

    def test_portable_policy_preserves_purpose_ids_and_sanitizes_prose(self):
        value = record11()
        value['checks'][0]['purpose'] = PURPOSE + r' C:\private\notes.txt'
        value['coverage']['areas'][0]['dimensions'][0]['details'] = r'Observed C:\private\notes.txt'
        before = copy.deepcopy(value)
        projection = delivery._Projection(value, {'repository_path': 'C:/repo', 'archive_root': 'C:/archive'}, Path('C:/repo'), 'a'*64)
        portable = projection.value(value)
        self.assertIn(PURPOSE, portable['checks'][0]['purpose'])
        self.assertNotIn('C:\\private', str(portable))
        self.assertEqual(portable['checks'][0]['id'], 'C001')
        self.assertEqual(sum(len(a['dimensions']) for a in portable['coverage']['areas']), 27)
        self.assertEqual(value, before)
        value['checks'][0]['unknown'] = 'unclassified'
        with self.assertRaisesRegex(ValueError, 'unclassified portable field'):
            projection.value(value)

    def test_private_and_public_handoff_keep_objectives_and_indexed_coverage(self):
        value = record11()
        value['coverage']['flows'] = ['Internal E05 path']
        text = renderer.render_handoff(value)
        self.assertIn(PURPOSE, text)
        self.assertIn('- **Cobertura:**\n  - Internal E05 path', text)
        contexts = publication_contexts(value)
        contexts['coverage_publication_context']['flows'][0]['summary'] = 'Recuperación de trabajos'
        text = renderer.render_handoff(value, audience='comment', **contexts)
        self.assertIn('Recuperación de trabajos', text)
        self.assertNotIn('Internal E05 path', text)
        self.assertIn(PURPOSE, text)

    def test_full_and_brief_keep_source_identity_and_all_dimensions(self):
        fixture = archives.Archive11Tests()
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        run = fixture.prepare()
        value = record11()
        value['coverage']['flows'] = ['Creación de jobs', 'Reintento de jobs']
        set_dimension(value, 'A01', status='not_applicable', details='Sin componente de larga duración')
        fixture.final = fixture.write('final11.json', value)
        fixture.retain(run, expected_schema=11)
        fixture.close(run)
        before = fixture.snapshot(run)
        source = fixture.read(run/'review.json')
        for mode in ('full', 'brief'):
            target = delivery.deliver(run, mode, fixture.repo, fixture.root/mode)
            text = (target/('informe.md' if mode == 'full' else 'resumen.md')).read_text(encoding='utf-8')
            self.assertIn(PURPOSE, text)
            for flow in value['coverage']['flows']:
                self.assertIn('  - '+flow, text)
            self.assertIn('A01', text)
            self.assertIn('Sin componente de larga duración', text)
            receipt = fixture.read(target/'.ccr-delivery.json')
            self.assertEqual(receipt['source_schema_version'], 11)
            self.assertEqual(receipt['source_id'], source['review_id'])
            if mode == 'full':
                portable = fixture.read(target/'review.json')
                self.assertEqual(portable['schema_version'], 11)
                self.assertEqual(sum(len(a['dimensions']) for a in portable['coverage']['areas']), 27)
        self.assertEqual(fixture.snapshot(run), before)
