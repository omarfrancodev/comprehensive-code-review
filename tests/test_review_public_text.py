"""Privacy decisions use original prose, not Markdown-created paths."""
import unittest
from script_test_support import enable_package_imports

enable_package_imports()
from ccr.contracts.check_disclosure import safe_text
from ccr.reporting.markdown import markdown_text
from ccr.reporting.render import render
from test_review_contract import clean_record, finding
from publication_fixtures import coverage_classification


class PublicTextTests(unittest.TestCase):
    def test_prose_token_colon_does_not_consume_next_word(self):
        value = 'sin comprobar propiedad por token: puede borrar la reserva'
        self.assertEqual(safe_text(value), value)

    def test_markdown_escape_does_not_create_local_path(self):
        from test_review_check_disclosure import fixture
        from test_review_topology_integration import contexts12
        from ccr.workflow.builders import build_check_disclosure
        record, identity, observations, sources = fixture()
        value = 'jobs_service.py:_publish_pending_job'
        record['verdict_reason'] = value
        disclosure = build_check_disclosure(record, identity, observations, sources)
        body = render(record, 'comment', **contexts12(record), check_disclosure_context=disclosure, check_disclosure_sources=sources)
        self.assertIn(markdown_text(value), body)
        self.assertNotIn('[ruta privada]', body)

    def test_structured_credentials_and_overlapping_known_values_remain_private(self):
        for value in ('token: demo', 'token=demo', 'token:"demo"', '{"token": "demo"}',
                      'Authorization: Bearer demo', 'prefix Authorization: Bearer demo'):
            with self.subTest(value=value):
                self.assertNotIn('demo', safe_text(value))
        self.assertNotIn('demo', safe_text('prefix token: demo', syntax='structured'))
        self.assertNotIn('demo', safe_text('La respuesta demo', {'demo'}))
        self.assertNotIn('demo', safe_text('https://example.test/?token=demo'))
        self.assertNotIn('demo', safe_text('--token demo', syntax='structured'))

    def test_original_marked_values_are_collected_without_learning_prose_words(self):
        from ccr.contracts.disclosure_text import sensitive_values_from_text
        from ccr.reporting.projections import public_sensitive_values
        self.assertIn('SECRETO', sensitive_values_from_text('token=SECRETO'))
        self.assertEqual(sensitive_values_from_text('por token: puede borrar'), set())
        record = clean_record()
        record['findings'] = [finding()]
        record['findings'][0]['evidence'][0]['details'] = 'token=SECRETO'
        self.assertIn('SECRETO', public_sensitive_values(record))

    def test_shared_source_projection_has_no_delivery_io_dependency(self):
        from script_test_support import module_dependencies
        self.assertNotIn('ccr.reporting.delivery', module_dependencies('ccr.reporting.public_text'))
        self.assertFalse(any(name.startswith('ccr.archive') for name in module_dependencies('ccr.reporting.text_projection')))
