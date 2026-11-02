"""Sensitive copies keep their source identity across quoted-member boundaries."""
import json
import shlex
import unittest

import test_review_delivery_privacy_regressions as privacy
from test_review_coverage13 import record13
from test_review_traceability_contract import record6, check
from ccr.contracts.check_disclosure import EXPLANATION_COMMAND, private_values, sensitive_text_ranges
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
