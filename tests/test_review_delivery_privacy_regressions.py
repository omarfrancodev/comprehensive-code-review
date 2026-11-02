"""Retained commands teach redaction only; HTTP context distinguishes paths."""
import json
import copy
import shlex
import unittest

import test_review_archive_full13 as full13
from ccr.contracts.check_disclosure import EXPLANATION_COMMAND, private_values, safe_text
from ccr.reporting import delivery
from ccr.reporting.markdown import markdown_text
from ccr.workflow.builders import build_check_disclosure
from ccr.reporting.check_disclosure import disclosure_view
import test_review_check_disclosure as disclosure_fixtures
from test_review_coverage13 import record13


class DeliveryPrivacyRegressionTests(unittest.TestCase):
    complete_archive = full13.Full13ArchiveTests.complete_archive

    def snapshot(self, run):
        return {p.relative_to(run): p.read_bytes() for p in run.rglob('*') if p.is_file()}

    def assert_command_secret_redacted(self, command, secret='SYNTHETIC_COMMAND_TOKEN_6789'):
        def update(record):
            record['checks'][0]['command'] = command
            record['checks'][0]['evidence'] = 'Observed ' + secret
            record['verdict_reason'] = 'Observed ' + secret
            record['coverage']['flows'] = ['Response carrying ' + secret]
        case, run = self.complete_archive(with_checks=True, record_update=update)
        before = self.snapshot(run)
        context = {'pending': [{'text': 'Inspect ' + secret,
                               'references': ['C001'], 'version': 'retained-head'}]}
        for mode in ('full', 'brief'):
            target = delivery.deliver(run, mode, case.repo, case.root / mode, context=context)
            for path in target.glob('*'):
                if path.is_file():
                    output = path.read_text(encoding='utf-8')
                    for spelling in (secret, markdown_text(secret)):
                        self.assertNotIn(spelling, output, path.name)
            if mode == 'full':
                portable = json.loads((target / 'review.json').read_bytes())
                self.assertEqual(portable['checks'][0]['command'], EXPLANATION_COMMAND)
                self.assertIn('[omitido]', portable['checks'][0]['evidence'])
            self.assertEqual(before, self.snapshot(run))

    def test_full13_fallback_redacts_loose_command_secrets_in_reports_json_and_context(self):
        self.assert_command_secret_redacted('probe --token SYNTHETIC_COMMAND_TOKEN_6789')

    def test_full13_fallback_redacts_secret_inside_a_quoted_shell_script(self):
        self.assert_command_secret_redacted("sh -c 'probe --token SYNTHETIC_COMMAND_TOKEN_6789; printf done'")

    def test_full13_fallback_redacts_lexically_escaped_sensitive_flag(self):
        secret = 'Q7r8P2m9'
        self.assert_command_secret_redacted("sh -c 'probe --to\\ken " + secret + "'", secret)

    def test_shell_learning_normalizes_before_selecting_sensitive_keys(self):
        secret = 'Q7r8P2m9'
        script = r'probe --to\ken ' + secret
        for command in (shlex.join(['sh', '-c', script]),
                        shlex.join(['sh', '-c', shlex.join(['sh', '-c', script])]),
                        "sh -c 'probe --to\"ke\"n " + secret + "'",
                        "sh -c '--to\\ken=" + secret + "'"):
            with self.subTest(command=command):
                record = record13()
                record['checks'][0]['command'] = command
                self.assertIn(secret, private_values(record, None, {}))

    def test_quoted_private_path_does_not_export_a_filename_suffix(self):
        private = '/private/cache,/api/Q7r8P2m9.txt'
        prose = 'GET /api/orders, "' + private + '", /v2/orders'
        def update(record):
            record['verdict_reason'] = prose
            record['coverage']['flows'] = [prose]
        case, run = self.complete_archive(record_update=update)
        before = self.snapshot(run)
        context = {'pending': [{'text': prose, 'references': ['retained-review'], 'version': 'retained-head'}]}
        for mode in ('full', 'brief'):
            target = delivery.deliver(run, mode, case.repo, case.root / mode, context=context)
            for path in target.glob('*'):
                if path.suffix in ('.md', '.json'):
                    text = path.read_text(encoding='utf-8')
                    self.assertNotIn('Q7r8P2m9', text)
            for name in ('contexto.md', 'informe.md' if mode == 'full' else 'resumen.md'):
                text = (target / name).read_text(encoding='utf-8')
                self.assertIn('/api/orders', text)
                self.assertIn('/v2/orders', text)
            self.assertEqual(before, self.snapshot(run))

    def test_quoted_path_units_keep_internal_commas_private(self):
        record = record13()
        record['checks'] = []
        projection = delivery._Projection(record, {}, None, 'a' * 64)
        for quote in ('"', "'", '`'):
            for separator in (', ', ','):
                for private in ('/private/cache,/api/Q7r8P2m9.txt',
                                '/private/cache,/v2/Q7r8P2m9.txt',
                                '/private cache,/api/Q7r8P2m9.txt'):
                    text = 'GET /api/orders' + separator + quote + private + quote + separator + quote + '/v2/orders' + quote
                    with self.subTest(quote=quote, separator=separator, private=private):
                        projected = projection.text(text)
                        self.assertNotIn('Q7r8P2m9', projected)
                        self.assertIn('/api/orders', projected)
                        self.assertIn('/v2/orders', projected)
        for text in ('GET /api/orders, "/private/cache,/api/Q7r8P2m9.txt',
                     'GET "/api/orders Q7r8P2m9'):
            self.assertNotIn('Q7r8P2m9', projection.text(text))

    def test_http_lists_preserve_comma_delimited_endpoints_in_both_deliveries(self):
        prose = ('GET /api/orders, /v2/orders y /v3/orders; '
                 'Archivo local /api/private,secret.key')
        def update(record):
            record['verdict_reason'] = prose
            record['coverage']['flows'] = [prose]
        case, run = self.complete_archive(record_update=update)
        before = self.snapshot(run)
        context = {'pending': [{'text': prose, 'references': ['retained-review'], 'version': 'retained-head'}]}
        for mode in ('full', 'brief'):
            target = delivery.deliver(run, mode, case.repo, case.root / mode, context=context)
            for name in ('contexto.md', 'informe.md' if mode == 'full' else 'resumen.md'):
                text = (target / name).read_text(encoding='utf-8')
                for endpoint in ('/api/orders', '/v2/orders', '/v3/orders'):
                    self.assertIn(endpoint, text)
                self.assertNotIn('secret.key', text)
            if mode == 'full':
                portable = json.loads((target / 'review.json').read_bytes())
                self.assertIn('/v2/orders', portable['verdict_reason'])
            self.assertEqual(before, self.snapshot(run))

    def test_local_api_and_versioned_paths_are_private_while_http_routes_survive(self):
        private = ('/api/private/secrets.conf', '/v2/private/runtime')
        prose = ('Archivo local ' + private[0] + '; archivo local ' + private[1]
                 + '; GET /api/orders devuelve 500; endpoint HTTP /v2/orders responde 200')
        def update(record):
            record['verdict_reason'] = prose
            record['coverage']['flows'] = [prose]
        case, run = self.complete_archive(record_update=update)
        before = self.snapshot(run)
        context = {'pending': [{'text': prose, 'references': ['C001'], 'version': 'retained-head'}]}
        for mode in ('full', 'brief'):
            target = delivery.deliver(run, mode, case.repo, case.root / mode, context=context)
            for name in ('contexto.md', 'informe.md' if mode == 'full' else 'resumen.md'):
                text = (target / name).read_text(encoding='utf-8')
                for path in private:
                    self.assertNotIn(path, text)
                for endpoint in ('/api/orders', '/v2/orders'):
                    self.assertIn(endpoint, text)
            if mode == 'full':
                portable = json.loads((target / 'review.json').read_bytes())
                for path in private:
                    self.assertNotIn(path, json.dumps(portable))
                self.assertIn('/api/orders', portable['verdict_reason'])
            self.assertEqual(before, self.snapshot(run))

    def test_retained_command_learning_is_redaction_only_and_preserves_encoded_copies(self):
        secret = 'SYNTHETIC_COMMAND_TOKEN_6789'
        for command in (
                'probe --token ' + secret,
                'probe --password="' + secret + '"',
                'probe API_KEY=' + secret,
                "probe --authorization 'Bearer " + secret + "'",
                "probe -H 'Authorization: Bearer " + secret + "'",
                'probe https://example.test/?token=' + secret,
                "sh -c 'probe --token " + secret + "'",
                "sh -c 'probe --token " + secret + "; printf done'",
                'bash -lc "probe --password=\'' + secret + '\'"',
                shlex.join(['sh', '-c', shlex.join(['sh', '-c', 'probe --token ' + secret])]),
                'cmd /c "probe --token ' + secret + '"',
                "sh -c 'API_KEY=" + secret + " probe'",
                'probe --token ' + secret + ' "unfinished'):
            with self.subTest(command=command):
                record = record13()
                record['checks'][0]['command'] = command
                learned = private_values(record, None, {})
                self.assertIn(secret, learned)
                for copy in (secret, secret.replace('_', '&#95;'), secret.replace('_', '%5F'), markdown_text(secret)):
                    self.assertNotIn('6789', safe_text('Observed ' + copy, learned))

    def test_path_classification_requires_http_context_instead_of_a_prefix_or_suffix(self):
        record = record13()
        record['checks'] = []
        projection = delivery._Projection(record, {'repository_path': '/known/repo'}, None, 'a' * 64)
        for text in ('Archivo /api/orders', 'archivo /v2/orders', '/api/orders', 'Archivo HTTP /api/local.json',
                     'Ruta HTTP /api/orders y archivo /v2/private.json',
                     'GET /api/orders; /v2/private.json'):
            with self.subTest(text=text):
                result = projection.text(text)
                private = '/v2/' if '/v2/' in text else '/api/'
                self.assertNotIn(private, result)
        for text in ('GET /api/orders.json', 'Endpoint /v2/orders', 'HTTP route /api/orders',
                     'GET /api/orders, /v2/orders, /v3/orders',
                     'GET `/api/orders`, `/v2/orders`', 'GET "/api/orders", "/v2/orders"',
                     'GET /api/orders,/v2/orders',
                     'Ruta HTTP /api/orders y /v2/orders'):
            self.assertEqual(projection.text(text), text)
        self.assertEqual(projection.text('Archivo /known/repo/src/api.py'), 'Archivo src/api.py')
        self.assertEqual(projection.text('GET /api/orders,/srv/private/file,/v2/orders'),
                         'GET /api/orders,[ruta privada],/v2/orders')
        self.assertEqual(projection.text('GET /api/orders, /srv/private/file, /v2/orders'),
                         'GET /api/orders, [ruta privada], /v2/orders')

    def test_a_secret_in_a_structural_identity_is_refused_instead_of_exported(self):
        record = record13()
        secret = 'SYNTHETIC_STRUCTURAL_TOKEN'
        record['checks'][0]['command'] = 'probe --token ' + secret
        record['responsible']['name'] = secret
        identity = {'head': record['scope']['head'], 'snapshot': record['scope']['snapshot']}
        disclosure = build_check_disclosure(record, identity, {}, {})
        projection = delivery._Projection(record, {}, None, 'a' * 64, check_disclosure_context=disclosure)
        with self.assertRaisesRegex(ValueError, 'responsible.name'):
            projection.value(record)

    def test_a_command_secret_also_redacts_copies_in_another_proved_check_view(self):
        secret = 'SYNTHETIC_CROSS_CHECK_TOKEN'
        record, identity, observations, sources = disclosure_fixtures.fixture(
            ['pytest', 'tests/test_queue.py', '-k', secret])
        extra = copy.deepcopy(record['checks'][0])
        extra.update(id='C002', command='inspect --token ' + secret,
                     execution={'kind': 'static', 'executor': None})
        record['checks'].append(extra)
        disclosure = build_check_disclosure(record, identity, observations, sources)
        before = copy.deepcopy(disclosure)
        self.assertIn(secret, disclosure['checks'][0]['command'])
        view = disclosure_view(record, disclosure, sources)
        self.assertNotIn(secret, json.dumps(view))
        projection = delivery._Projection(record, {}, None, 'a' * 64,
            check_disclosure_context=disclosure, check_disclosure_sources=sources)
        self.assertNotIn(secret, json.dumps(projection.value(record)))
        self.assertEqual(disclosure, before)
