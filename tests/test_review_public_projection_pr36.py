"""Regressions from the public projection review of PR 36."""
import copy
import tracemalloc
import unittest

from script_test_support import enable_package_imports

enable_package_imports()
from ccr.contracts.check_disclosure import input_identity_for, safe_text, sensitive_text_ranges
from ccr.contracts.review import validate
from ccr.reporting import comment, render
from ccr.reporting.projections import publication_digest
from ccr.workflow.builders import build_check_disclosure
from publication_fixtures import check_classification, coverage_classification
from test_review_contract import clean_record
from test_review_coverage13 import record13
from test_review_finding_publication import record_and_context


class PublicProjectionReviewTests(unittest.TestCase):
    def draft(self, record, **kwargs):
        self.assertEqual(validate(record), [])
        draft = comment.prepare_public_comment(
            record, coverage_publication_context=coverage_classification(record), **kwargs)
        self.assertTrue(comment.verify_public_comment(
            record, draft, draft['body'],
            check_disclosure_context=kwargs.get('check_disclosure_context'))['verified'])
        return draft['body']

    def test_finding_location_checks_full_destination_and_keeps_relative_label(self):
        for url, expected in (
            ('/private/work/hidden.py', None),
            ('file:///private/work/hidden.py', None),
            ('https://localhost/hidden.py', None),
            ('https://example.test/view(x)?token=LOCATORSECRET', None),
            ('https://example.test/view(x)#L42', 'https://example.test/view%28x%29#L42'),
        ):
            with self.subTest(url=url):
                record, _ = record_and_context()
                record['findings'][0]['location'].update(path='archive/handler.py', line=42, url=url)
                body = self.draft(record)
                self.assertIn('archive/handler.py:42', body)
                if expected is None:
                    self.assertNotIn(url, body)
                    self.assertNotIn('LOCATORSECRET', body)
                    self.assertNotIn('[archive/handler.py:42](', body)
                else:
                    self.assertIn('[archive/handler.py:42](' + expected + ')', body)
        record['findings'][0]['location'].update(path='/private/work/hidden.py', url=None)
        self.assertNotIn('/private/work/hidden.py', self.draft(record))

    def test_explicit_assignments_survive_lexical_classification_and_hide_copies(self):
        for source in (
            'La operación usa token=`ASSIGNSECRET`',
            'La operación usa token=`` ASSIGNSECRET ``',
            'Una nota sobre el token: password=ASSIGNSECRET',
            '``inside token=`ASSIGNSECRET` ``',
            '```\ninside token=`ASSIGNSECRET`\n```',
        ):
            with self.subTest(source=source):
                record = clean_record()
                record['verdict_reason'] = source + '\nLa regla por token: puede borrar'
                record['description']['details'] = 'Otra copia ASSIGNSECRET puede aparecer'
                body = self.draft(record)
                self.assertNotIn('ASSIGNSECRET', body)
                self.assertIn('por token: puede borrar', body)
                self.assertIn('puede aparecer', body)

    def test_fence_ends_at_container_boundary_and_prose_never_teaches_secret(self):
        tick = '```'
        for fenced in (
            f'> {tick}text\n> dentro token: FENCESECRET',
            f'- {tick}text\n  dentro token: FENCESECRET',
            f'- lista\n  {tick}text\n  dentro token: FENCESECRET',
            f'- lista\n  - interna\n  {tick}text\n  dentro token: FENCESECRET',
            f'- lista\n  > {tick}text\n  > dentro token: FENCESECRET',
            f'- - {tick}text\n    dentro token: FENCESECRET',
            f'- > {tick}text\n  > dentro token: FENCESECRET',
            f'> - {tick}text\n>   dentro token: FENCESECRET',
        ):
            with self.subTest(fenced=fenced):
                record = clean_record()
                record['verdict_reason'] = fenced + '\nLa regla por token: puede borrar'
                record['description']['details'] = 'Otra regla puede aparecer y cita FENCESECRET'
                body = self.draft(record)
                self.assertNotIn('FENCESECRET', body)
                self.assertIn('por token: puede borrar', body)
                self.assertIn('puede aparecer', body)

    def test_fence_in_list_quote_ends_when_only_the_outer_quote_remains(self):
        tick = '```'
        text = (f'- lista\n  > {tick}\n  > dentro token: FENCESECRET\n'
                '> La regla por token: puede borrar')
        self.assertNotIn('FENCESECRET', safe_text(text))
        self.assertIn('por token: puede borrar', safe_text(text))

    def test_evidence_grouping_uses_original_rows_for_comment_and_handoff(self):
        record, context = record_and_context()
        same = record['findings'][0]['evidence'][0]['details']
        context['findings'][0]['evidence'][0]['summary'] = same
        original = copy.deepcopy(record)
        kwargs = dict(finding_publication_context=context)
        body = self.draft(record, **kwargs)
        handoff = render.render_handoff(record, audience='comment',
            coverage_publication_context=coverage_classification(record), **kwargs)
        for output in (body, handoff):
            self.assertEqual(output.count('**Inspección estática**'), 2)
        self.assertEqual(record, original)

    def test_reused_revision_collision_is_rejected(self):
        record = record13()
        revision = 'ab' * 20
        check = record['checks'][0]
        check.update(reused=True, revision=revision, reuse_reason='Same functional inputs',
                     reference='evidence/previous-run.log', execution=dict(kind='reused', executor=None))

        def contexts():
            classification = check_classification(record)
            classification['checks'][0]['purpose'] = check['purpose']
            return dict(check_publication_context=classification,
                        check_disclosure_context=build_check_disclosure(
                            record, input_identity_for(record), {}, {}))

        self.assertIn(revision, self.draft(record, **contexts()))
        record['verdict_reason'] = 'token=' + revision
        kwargs = contexts()
        with self.assertRaisesRegex(ValueError, 'private structural value'):
            self.draft(record, **kwargs)
        with self.assertRaisesRegex(ValueError, 'private structural value'):
            render.render_handoff(record, audience='comment',
                coverage_publication_context=coverage_classification(record), **kwargs)

    def test_resolved_finding_identity_collision_is_rejected(self):
        record = record13()
        record['checks'] = []
        identity = 'F991'
        prior = dict(review_id='CR-' + 'b'*20, reference='https://example.test/previous', verified=True)
        record['previous_reviews'] = [prior]
        record['rereview'] = [dict(id=identity, status='resolved', details='Resolved in this head',
            previous_review_id=prior['review_id'], previous_reference=prior['reference'],
            previous_finding_id=identity, previous_title='Original finding', previous_url=None, check_ids=[])]
        self.assertIn(identity, self.draft(record))
        record['verdict_reason'] = 'token=' + identity
        with self.assertRaisesRegex(ValueError, 'private structural value'):
            self.draft(record)

    def test_encoded_overlaps_do_not_allocate_one_interval_per_match(self):
        text = '&#120;' * 2400
        secrets = ['x' * length for length in range(2, 58)]
        tracemalloc.start()
        try:
            self.assertEqual(list(sensitive_text_ranges(text, secrets)), [(0, len(text))])
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        self.assertLess(peak, 4 * 1024 * 1024)
        self.assertEqual(list(sensitive_text_ranges('a&#98;cd', ('ab', 'bc'))), [(0, 7)])

    def test_invalid_record_rejects_matching_editorial_context_in_prepare_and_verify(self):
        record, context = record_and_context()
        draft = comment.prepare_public_comment(record, finding_publication_context=context,
            coverage_publication_context=coverage_classification(record))
        del record['findings']
        digest = publication_digest(record)
        context['source_sha256'] = digest
        draft.update(source_sha256=digest, finding_publication_context=context,
                     finding_publication_sha256=publication_digest(context))
        for operation in (
            lambda: comment.prepare_public_comment(record, finding_publication_context=context),
            lambda: comment.verify_public_comment(record, draft, draft['body']),
        ):
            with self.subTest(operation=operation), self.assertRaisesRegex(ValueError, 'findings'):
                operation()
