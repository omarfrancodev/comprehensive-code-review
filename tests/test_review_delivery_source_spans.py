"""Sensitive copies keep their source identity across quoted-member boundaries."""
import json
import shlex
import unittest

import test_review_delivery_privacy_regressions as privacy
from test_review_coverage13 import record13
from test_review_traceability_contract import record6, check
from ccr.contracts.check_disclosure import EXPLANATION_COMMAND, private_values, safe_text, sensitive_text_ranges
from ccr.reporting import delivery
from ccr.workflow.builders import build_check_disclosure


class DeliverySourceSpanTests(unittest.TestCase):
    complete_archive = privacy.DeliveryPrivacyRegressionTests.complete_archive
    snapshot = privacy.DeliveryPrivacyRegressionTests.snapshot

    def assert_retained_copy_hidden(self, kind):
        marker = 'credential314159' if kind == 'secret' else 'script314159'
        def update(record, repo):
            member = '"' + repo.as_posix() + '/' + marker + '.py"'
            if kind == 'secret':
                secret = 'prefix ' + member
                command = shlex.join(['probe', '--token', secret])
                record['checks'][0]['command'] = command
                self.assertIn(secret, private_values(record, None, {}))
                copy = secret
            else:
                copy = 'probe314159 ' + member + ' --flag'
                record['checks'][0]['command'] = copy
            prose = ('GET /api/orders; Observed ' + copy
                     + '; GET /v2/orders; https://public.example.test/guide')
            record['verdict_reason'] = prose
            record['checks'][0]['evidence'] = prose
            record['coverage']['flows'] = [prose]
        case, run = self.complete_archive(with_checks=True, repository_record_update=update)
        record = json.loads((run / 'review.json').read_bytes())
        context = {'pending': [{'text': record['verdict_reason'], 'references': ['C001'],
                               'version': 'retained-head'}]}
        before = self.snapshot(run)
        outputs = []
        for mode in ('full', 'brief'):
            target = delivery.deliver(run, mode, case.repo, case.root / mode, context=context)
            outputs.extend((path.name, path.read_text(encoding='utf-8')) for path in target.glob('*')
                           if path.suffix in ('.md', '.json'))
            for name in ('contexto.md', 'informe.md' if mode == 'full' else 'resumen.md'):
                text = (target / name).read_text(encoding='utf-8')
                for neighbor in ('/api/orders', '/v2/orders', 'https://public.example.test/guide'):
                    self.assertIn(neighbor, text)
            if mode == 'full':
                portable = json.loads((target / 'review.json').read_bytes())
                self.assertEqual(portable['checks'][0]['command'], EXPLANATION_COMMAND)
            self.assertEqual(before, self.snapshot(run))
        for name, text in outputs:
            with self.subTest(output=name):
                self.assertNotIn(marker, text)
                if kind == 'command':
                    self.assertNotIn('probe314159', text)
                    self.assertNotIn('--flag', text)

    def test_secret_crossing_ordinary_and_quoted_members_stays_hidden_in_deliveries(self):
        self.assert_retained_copy_hidden('secret')

    def test_full_command_crossing_quoted_member_is_omitted_in_deliveries(self):
        self.assert_retained_copy_hidden('command')

    def test_source_copies_cross_quoted_members_with_all_root_and_quote_spellings(self):
        for root in ('/known/repo', r'C:\known\repo', r'\\server\known\repo'):
            for quote in ('"', "'", '`'):
                member = quote + root + '/credential314159' + quote
                secret = 'prefix ' + member + ' suffix'
                record = record13()
                record['checks'][0]['command'] = shlex.join(['probe', '--token', secret])
                identity = {'head': record['scope']['head'], 'snapshot': record['scope']['snapshot']}
                disclosure = build_check_disclosure(record, identity, {}, {})
                projection = delivery._Projection(record, {'repository_path': root}, None, 'a' * 64,
                    check_disclosure_context=disclosure)
                for copy in (secret, secret.replace('credential', '%63redential')):
                    with self.subTest(root=root, quote=quote, copy=copy):
                        text = 'GET /api/orders, ' + copy + ', /v2/orders; https://public.example.test/guide'
                        result = projection.text(text)
                        self.assertNotIn('314159', result)
                        self.assertIn('/api/orders', result)
                        self.assertIn('https://public.example.test/guide', result)

    def test_historical_command_copy_is_omitted_before_member_relativization(self):
        for quote in ('"', "'", '`'):
            record = record6()
            command = 'probe314159 ' + quote + '/known/repo/script314159.py' + quote + ' --flag'
            record['checks'] = [dict(check(), command=command)]
            projection = delivery._Projection(record, {'repository_path': '/known/repo'}, None, 'a' * 64)
            result = projection.text('Observed ' + command + '; https://public.example.test/guide')
            with self.subTest(quote=quote):
                self.assertNotIn('probe314159', result)
                self.assertNotIn('script314159', result)
                self.assertNotIn('--flag', result)
                self.assertIn('comando omitido', result)
                self.assertIn('https://public.example.test/guide', result)

    def test_sensitive_intervals_keep_original_offsets_and_merge_overlaps(self):
        text = 'ñ prefix "' + '/known/repo/%63redential314159' + '" suffix'
        secret = 'prefix "/known/repo/credential314159" suffix'
        ranges = list(sensitive_text_ranges(text, {secret}))
        self.assertEqual(ranges, [(2, len(text))])
        self.assertEqual(list(sensitive_text_ranges('x ababa y', {'aba', 'bab'})), [(2, 7)])
        self.assertEqual(list(sensitive_text_ranges('a' * 10000, {'a'})), [(0, 10000)])
        self.assertEqual(list(sensitive_text_ranges(text, set())), [])

    def test_hidden_member_keeps_adjacent_http_routes(self):
        record = record13()
        record['checks'][0]['command'] = 'probe --token credential314159'
        identity = {'head': record['scope']['head'], 'snapshot': record['scope']['snapshot']}
        disclosure = build_check_disclosure(record, identity, {}, {})
        projection = delivery._Projection(record, {}, None, 'a' * 64, check_disclosure_context=disclosure)
        text = 'GET /api/orders, "/private/credential314159,/api/private.txt", /v2/orders'
        result = projection.text(text)
        self.assertNotIn('314159', result)
        self.assertNotIn('private.txt', result)
        self.assertIn('/api/orders', result)
        self.assertIn('/v2/orders', result)

    def assert_retained_observation(self, prose, secret, *, neighbor=None):
        def update(record):
            record['checks'][0]['command'] = shlex.join(['probe', '--token', secret])
            record['checks'][0]['evidence'] = prose
            record['verdict_reason'] = prose
            record['coverage']['flows'] = [prose]
            self.assertIn(secret, private_values(record, None, {}))
        case, run = self.complete_archive(with_checks=True, record_update=update)
        context = {'pending': [{'text': prose, 'references': ['C001'], 'version': 'retained-head'}]}
        before = self.snapshot(run)
        for mode in ('full', 'brief'):
            target = delivery.deliver(run, mode, case.repo, case.root / mode, context=context)
            for path in target.glob('*'):
                if path.suffix not in ('.md', '.json'):
                    continue
                text = path.read_text(encoding='utf-8')
                with self.subTest(mode=mode, output=path.name):
                    self.assertNotIn('314159', text)
                    self.assertNotIn('private.key', text)
                    if path.name != '.ccr-delivery.json':
                        self.assertIn('https://public.example.test/guide', text)
                        if neighbor:
                            self.assertIn(neighbor, text)
            self.assertEqual(before, self.snapshot(run))

    def test_encoded_overlapping_copies_are_fully_hidden_in_deliveries(self):
        self.assert_retained_observation(
            'Observed %6Bey314159%6Bey314159%6Bey; https://public.example.test/guide', 'key314159key')

    def test_omitted_first_http_member_keeps_its_public_neighbor_in_deliveries(self):
        self.assert_retained_observation(
            'GET "/api/credential314159", /v2/orders, /srv/private.key; https://public.example.test/guide',
            'credential314159', neighbor='/v2/orders')

    def test_encoded_ranges_enumerate_all_overlaps_without_changing_legacy_redaction(self):
        secret = 'key314159key'
        encoded = '%6Bey314159%6Bey314159%6Bey'
        self.assertEqual(safe_text(encoded, {secret}), '[omitido]314159%6Bey')
        for copy in (encoded, '&#107;ey314159&#107;ey314159&#107;ey',
                     '%6Bey314159&#107;ey314159%6Bey'):
            with self.subTest(copy=copy):
                self.assertEqual(list(sensitive_text_ranges('ñ ' + copy + ' tail', {secret})),
                                 [(2, 2 + len(copy))])
        copy = '%C3%B1314159%C3%B1314159%C3%B1'
        self.assertEqual(list(sensitive_text_ranges(copy, {'ñ314159ñ'})), [(0, len(copy))])

    def test_original_http_context_survives_first_omission_without_admitting_local_paths(self):
        record = record13()
        record['checks'][0]['command'] = 'probe --token credential314159'
        identity = {'head': record['scope']['head'], 'snapshot': record['scope']['snapshot']}
        disclosure = build_check_disclosure(record, identity, {}, {})
        projection = delivery._Projection(record, {}, None, 'a' * 64, check_disclosure_context=disclosure)
        for quote in ('"', "'", '`'):
            for context in ('GET ', 'Endpoint ', 'Ruta HTTP '):
                text = (context + quote + '/api/credential314159' + quote
                        + ', /v2/orders, /srv/private.key; archivo local /api/local.key; '
                        'https://public.example.test/guide')
                with self.subTest(quote=quote, context=context):
                    result = projection.text(text)
                    self.assertNotIn('314159', result)
                    self.assertNotIn('private.key', result)
                    self.assertNotIn('local.key', result)
                    self.assertIn('/v2/orders', result)
                    self.assertIn('https://public.example.test/guide', result)
        self.assertNotIn('/v2/', projection.text('Archivo "/api/credential314159", /v2/local.key'))
        for text in ('GET [omitido], /v2/local.key',
                     'https://public.example.test/GET /api/local.key',
                     '"/private/GET " /v2/local.key'):
            with self.subTest(ambiguous=text):
                self.assertNotIn('local.key', projection.text(text))
