"""Canonical public goals and coverage remain bound to their source."""
import copy
import unittest
from script_test_support import enable_package_imports
enable_package_imports()

from ccr.reporting import comment as comments, projections
from traceability_fixtures import record11, publication_contexts


class CommentTraceTests(unittest.TestCase):
    def test_draft2_contains_public_goal_and_each_flow(self):
        value = record11()
        value['coverage']['flows'] = ['Creación de jobs', 'Reintento de jobs']
        before = copy.deepcopy(value)
        draft = comments.prepare_public_comment(value, **publication_contexts(value))
        self.assertEqual(draft['schema_version'], 2)
        self.assertIn(value['checks'][0]['purpose'], draft['body'])
        self.assertIn('  - Creación de jobs\n', draft['body'])
        self.assertIn('  - Reintento de jobs\n', draft['body'])
        self.assertNotIn('### Matriz ABCDE', draft['body'])
        self.assertNotIn('### Dimensiones de cobertura', draft['body'])
        self.assertTrue(comments.verify_public_comment(value, draft, draft['body'])['verified'])
        self.assertEqual(value, before)

    def test_coverage_context_cannot_omit_duplicate_or_bind_other_source(self):
        value = record11()
        value['coverage']['flows'] = ['Mismo flujo', 'Mismo flujo']
        contexts = publication_contexts(value)
        for mutation in ('missing', 'duplicate', 'source', 'boolean', 'blank', 'extra'):
            context = copy.deepcopy(contexts['coverage_publication_context'])
            if mutation == 'missing':
                context['flows'].pop()
            elif mutation == 'duplicate':
                context['flows'].append(copy.deepcopy(context['flows'][0]))
            elif mutation == 'source':
                context['source_sha256'] = '0' * 64
            elif mutation == 'boolean':
                context['flows'][0]['index'] = False
            elif mutation == 'blank':
                context['flows'][0]['summary'] = ' '
            else:
                context['flows'][0]['extra'] = True
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                projections.public_coverage(value, context)
        self.assertEqual(projections.public_coverage(value, contexts['coverage_publication_context']), value['coverage']['flows'])
        with self.assertRaises(ValueError):
            projections.public_coverage(value)

    def test_old_draft_is_stale_and_changed_goal_invalidates_source(self):
        value = record11()
        draft = comments.prepare_public_comment(value, **publication_contexts(value))
        legacy = {k: v for k, v in draft.items() if k != 'coverage_publication_context'}
        legacy['schema_version'] = 1
        with self.assertRaisesRegex(ValueError, 'stale_draft'):
            comments.verify_public_comment(value, legacy, legacy['body'])
        value['checks'][0]['purpose'] = 'Otro objetivo'
        with self.assertRaisesRegex(ValueError, 'source_mismatch'):
            comments.verify_public_comment(value, draft, draft['body'])

    def test_editorial_changes_require_fresh_body_and_goal_cannot_be_omitted(self):
        value = record11()
        value['coverage']['flows'] = ['Ruta interna A01']
        contexts = publication_contexts(value)
        contexts['coverage_publication_context']['flows'][0]['summary'] = 'Creación de trabajos'
        contexts['check_publication_context']['checks'][0]['purpose'] = 'Comprobar exclusión mutua'
        draft = comments.prepare_public_comment(value, **contexts)
        self.assertNotIn('Ruta interna A01', draft['body'])
        for context, field, name in [('check_publication_context', 'checks', 'purpose'),
                                     ('coverage_publication_context', 'flows', 'summary')]:
            bad = copy.deepcopy(draft)
            bad[context][field][0][name] = 'Texto modificado'
            with self.assertRaisesRegex(ValueError, 'body_mismatch'):
                comments.verify_public_comment(value, bad, bad['body'])
        del contexts['check_publication_context']['checks'][0]['purpose']
        with self.assertRaises(ValueError):
            comments.prepare_public_comment(value, **contexts)
