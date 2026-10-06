"""Portable metadata, exact attribution and legacy canonical input support."""
import copy
import unittest

from test_review_areas import area_record
from test_review_contract import contract, finding


def current_record():
    record = area_record()
    record['schema_version'] = 3
    record['responsible'] = {'name': 'Omar', 'username': 'omar', 'verified': True,
                             'source': 'MR assignee at head-456'}
    record['change_authors'] = [
        {'name': 'Ana', 'username': 'ana', 'verified': True,
         'source': 'Platform commit/account mapping', 'commits': ['commit-ana']},
        {'name': 'Luis', 'username': None, 'verified': True,
         'source': 'Git author metadata at commit-luis', 'commits': ['commit-luis']},
    ]
    return record


class AttributionTests(unittest.TestCase):
    def test_schema3_accepts_separate_assignee_and_version_bound_authors(self):
        self.assertEqual(contract.validate(current_record()), [])

    def test_schema3_requires_author_slot_and_accepts_explicit_unknown(self):
        record = current_record()
        del record['change_authors']
        self.assertTrue(any('change_authors' in error for error in contract.validate(record)))
        record['change_authors'] = []
        self.assertEqual(contract.validate(record), [])
        self.assertIn('Autores del cambio:** No identificados', contract.render(record))

    def test_authors_need_commit_provenance_not_just_assignee_metadata(self):
        for change in ({'commits': []}, {'commits': ['']}, {'commits': 'head-456'},
                       {'commits': ['head-456', 'head-456']}, {'source': None},
                       {'username': '@invented'}, {'verified': 'yes'}):
            with self.subTest(change=change):
                record = current_record()
                record['change_authors'][0].update(change)
                self.assertTrue(contract.validate(record))

    def test_malformed_or_duplicate_authors_are_rejected_without_crash(self):
        for authors in (None, {}, [None], [{}], [['bad']],
                        [current_record()['change_authors'][0]] * 2):
            with self.subTest(authors=authors):
                record = current_record()
                record['change_authors'] = copy.deepcopy(authors)
                self.assertTrue(contract.validate(record))

    def test_assignee_never_becomes_author_and_unmapped_names_do_not_become_mentions(self):
        for audience in ('user', 'comment'):
            output = contract.render(current_record(), audience)
            self.assertIn('- **Responsable del MR/PR:** @omar', output)
            self.assertIn('- **Autores del cambio:** @ana; Luis', output)
            self.assertNotIn('@Luis', output)
            self.assertNotIn('Autores del cambio:** @omar', output)

    def test_unverified_account_is_never_mentioned(self):
        record = current_record()
        record['change_authors'][0]['verified'] = False
        self.assertNotIn('@ana', contract.render(record, 'comment'))

    def test_verified_account_mentions_preserve_platform_username_characters(self):
        record = current_record()
        record['responsible']['username'] = 'Omar_Franco'
        record['change_authors'][0]['username'] = 'ana_dev'
        output = contract.render(record, 'comment')
        self.assertIn('**Responsable del MR/PR:** @Omar_Franco', output)
        self.assertIn('**Autores del cambio:** @ana_dev; Luis', output)

    def test_legacy_records_validate_without_inventing_authors(self):
        for version in (1, 2):
            record = area_record()
            record['schema_version'] = version
            if version == 1:
                del record['coverage']['areas']
            self.assertEqual(contract.validate(record), [])
            self.assertNotIn('Autores del cambio', contract.render(record))


class PortableMarkdownTests(unittest.TestCase):
    def test_metadata_are_separate_list_blocks_for_both_audiences(self):
        record = area_record()
        for audience in ('user', 'comment'):
            output = contract.render(record, audience)
            header = output.split('No se confirmaron')[0]
            for label in ('Alcance', 'Versión', 'Destino', 'Responsable del MR/PR', 'MR/PR', 'Descripción'):
                self.assertTrue(any(line.startswith('- **' + label + ':**')
                                    for line in header.splitlines()), label)
            self.assertIn('defectos bloqueantes', output)
            self.assertIn('**Veredicto:** APROBABLE', output)

    def test_local_fields_translate_values_and_do_not_invent_remote_description(self):
        record = current_record()
        record['scope'].update(mode='feature', reference='feature/documents')
        record['description'] = {'status': 'not_applicable', 'identity': None, 'details': ''}
        output = contract.render(record)
        self.assertIn('implementación de funcionalidad', output)
        self.assertIn('- **Perfil:** equilibrado', output)
        self.assertIn('- **Verificación:** independiente', output)
        self.assertIn('- **Descripción:** No aplica; revisión local', output)
        self.assertIn('- **Responsable:** @omar', output)
        public = contract.render(record, 'comment')
        self.assertNotIn('**Perfil:**', public)
        self.assertNotIn('**Verificación:**', public)
        self.assertNotIn('Matriz ABCDE', public)

    def test_metadata_cannot_inject_html_or_extra_markdown_blocks(self):
        record = area_record()
        record['scope']['repository'] = '<script>alert(1)</script>\n## Fake heading'
        record['responsible'].update(name='[Ana](https://evil.test)', username=None)
        output = contract.render(record)
        self.assertNotIn('<script>', output)
        self.assertNotIn('\n## Fake heading', output)
        self.assertNotIn('[Ana](https://evil.test)', output)

    def test_finding_fields_have_explicit_block_boundaries(self):
        record = area_record()
        record['findings'] = [finding()]
        for audience in ('user', 'comment'):
            output = contract.render(record, audience)
            for label in ('Ubicación', 'Escenario e impacto', 'Evidencia', 'Corrección requerida', 'Bloqueante'):
                self.assertIn('\n- **' + label + ':**', output)


if __name__ == '__main__':
    unittest.main()
