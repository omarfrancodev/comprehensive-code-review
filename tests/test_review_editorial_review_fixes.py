"""Four review findings: structured text, identities and delivery-wide privacy."""
import copy
import json
import unittest

from script_test_support import enable_package_imports

enable_package_imports()
from ccr.contracts.check_disclosure import safe_text
from ccr.contracts.review import validate
from ccr.reporting import comment, delivery, render
from publication_fixtures import coverage_classification
import test_review_archive_full13 as full13
from test_review_coverage13 import record13


class EditorialReviewFixTests(unittest.TestCase):
    def public_record(self):
        record = record13()
        record['checks'] = []
        return record

    def assert_public_secret_hidden(self, source, secret):
        self.assertNotIn(secret, safe_text(source))
        record = self.public_record()
        record['verdict_reason'] = source
        self.assertEqual(validate(record), [])
        draft = comment.prepare_public_comment(
            record, coverage_publication_context=coverage_classification(record))
        self.assertNotIn(secret, draft['body'])
        self.assertTrue(comment.verify_public_comment(record, draft, draft['body'])['verified'])

    def test_numbered_credential_fields_are_private(self):
        for prefix in ('1. ', '23) ', '  002. ', '- '):
            with self.subTest(prefix=prefix):
                self.assert_public_secret_hidden(prefix + 'token: NUMBEREDSECRET', 'NUMBEREDSECRET')

    def test_matching_code_delimiters_protect_credentials(self):
        for source in ('``token: CODESECRET``',
                       '``literal ` and token: CODESECRET``',
                       '````token: CODESECRET````',
                       '```text\ninside token: CODESECRET\n```',
                       '```text\ninside token: CODESECRET\n````',
                       '~~~text\ninside token: CODESECRET\n~~~',
                       '```text\ninside token: CODESECRET',
                       '- outer\n  - inner\n    ```text\n    inside token: CODESECRET\n    ````',
                       '> ```text\n> inside token: CODESECRET\n> ````',
                       '1. ```text\n   inside token: CODESECRET\n   ````',
                       '```text\n- ````\ninside token: CODESECRET\n```',
                       '```text\n    ````\ninside token: CODESECRET\n```',
                       '> ```text\n> - ````\n> inside token: CODESECRET\n> ```'):
            with self.subTest(source=source):
                self.assert_public_secret_hidden(source, 'CODESECRET')

    def test_code_boundaries_do_not_turn_neighboring_prose_into_credentials(self):
        for source in ('1. por token: puede borrar',
                       '``literal ` token: CODESECRET`` por token: puede borrar',
                       '```text\ninside token: CODESECRET\n````\npor token: puede borrar',
                       '> ```text\n> inside token: CODESECRET\n> ````\npor token: puede borrar',
                       'Unmatched `` marker, por token: puede borrar',
                       r'Literal \` marker, por token: puede borrar'):
            with self.subTest(source=source):
                self.assertIn('por token: puede borrar', safe_text(source))

    def test_sensitive_previous_identity_rejects_all_public_projections(self):
        record = self.public_record()
        identifier = 'CR-' + 'b' * 20
        record['previous_reviews'] = [dict(
            review_id=identifier, reference='https://example.test/previous', verified=True)]
        record['verdict_reason'] = 'token=' + identifier
        self.assertEqual(validate(record), [])
        before = copy.deepcopy(record)
        kwargs = dict(coverage_publication_context=coverage_classification(record))
        operations = (
            lambda: render.render(record, 'comment', **kwargs),
            lambda: render.render_handoff(record, audience='comment', **kwargs),
            lambda: comment.prepare_public_comment(record, **kwargs),
        )
        for operation in operations:
            with self.subTest(operation=operation), self.assertRaises(ValueError):
                operation()
            self.assertEqual(record, before)

    def test_non_sensitive_previous_identity_is_preserved(self):
        record = self.public_record()
        identifier = 'CR-' + 'b' * 20
        record['previous_reviews'] = [dict(
            review_id=identifier, reference='https://example.test/previous', verified=True)]
        body = render.render(record, 'comment',
                             coverage_publication_context=coverage_classification(record))
        self.assertIn(identifier, body)
        self.assertIn('https://example.test/previous', body)


class DeliveryContextPrivacyTests(unittest.TestCase):
    complete_archive = full13.Full13ArchiveTests.complete_archive

    def inventory(self, run):
        return {p.relative_to(run): p.read_bytes() for p in run.rglob('*') if p.is_file()}

    def test_context_secret_is_learned_before_every_full_and_brief_field(self):
        def update(record):
            record['verdict_reason'] = 'Original evidence contains CONTEXTSECRET'
        case, run = self.complete_archive(record_update=update)
        before = self.inventory(run)
        context = dict(pending=[
            dict(text='First copy CONTEXTSECRET', references=['https://example.test/case'], version='head'),
            dict(text='token=CONTEXTSECRET', references=['https://example.test/case'], version='head')])
        original_context = copy.deepcopy(context)
        for mode in ('full', 'brief'):
            with self.subTest(mode=mode):
                target = delivery.deliver(run, mode, case.repo, case.root / mode, context=context)
                for path in target.iterdir():
                    if path.suffix in ('.md', '.json'):
                        self.assertNotIn('CONTEXTSECRET', path.read_text(encoding='utf-8'), path.name)
                self.assertIn('First copy', (target / 'contexto.md').read_text(encoding='utf-8'))
                self.assertEqual(context, original_context)
                self.assertEqual(self.inventory(run), before)

    def test_context_secret_cannot_rewrite_a_source_identity(self):
        case, run = self.complete_archive()
        before = self.inventory(run)
        source = json.loads((run / 'review.json').read_bytes())
        context = dict(pending=[dict(text='token=' + source['scope']['head'],
                                    references=['https://example.test/case'], version='head')])
        for mode in ('full', 'brief'):
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                delivery.deliver(run, mode, case.repo, case.root / mode, context=context)
            self.assertFalse((case.root / mode).exists())
            self.assertEqual(self.inventory(run), before)

    def test_context_secret_protects_proved_commands_resources_and_explanations(self):
        from test_review_check_disclosure import fixture
        from ccr.workflow.builders import build_check_disclosure
        secret = 'CONTEXTSECRET'
        path = 'tests/' + secret + '.py'
        record, identity, observations, sources = fixture(
            ['pytest', path, '-k', secret], {path: b'assert True\n'})
        observations[record['checks'][0]['id']]['explanation'] = 'Observed ' + secret
        disclosure = build_check_disclosure(record, identity, observations, sources)
        before = copy.deepcopy(disclosure)
        context = dict(pending=[dict(text='token=' + secret,
                                    references=['https://example.test/case'], version='head')])
        projection = delivery._Projection(record, {}, '', 'a' * 64,
            check_disclosure_context=disclosure, check_disclosure_sources=sources,
            editorial_texts=(context,))
        self.assertNotIn(secret, json.dumps(projection.value(record)))
        self.assertNotIn(secret, json.dumps(projection.disclosure))
        self.assertEqual(disclosure, before)

    def test_context_secret_protects_appended_check_detail_in_both_deliveries(self):
        case, run = self.complete_archive(with_checks=True)
        before = self.inventory(run)
        # This literal is in the actual generated disclosure explanation. A
        # declared credential has authority even when it is an ordinary word.
        context = dict(pending=[dict(text='token=argv',
                                    references=['https://example.test/case'], version='head')])
        for mode in ('full', 'brief'):
            with self.subTest(mode=mode):
                target = delivery.deliver(run, mode, case.repo, case.root / mode, context=context)
                name = 'informe.md' if mode == 'full' else 'resumen.md'
                report = (target / name).read_text(encoding='utf-8')
                self.assertIn('Explicación del check', report)
                self.assertNotIn('argv', report)
                self.assertEqual(self.inventory(run), before)
