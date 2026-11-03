"""Local filename tokens cannot supply authority to a following HTTP-looking path."""
import unittest

import test_review_delivery_privacy_regressions as privacy
from test_review_coverage13 import record13
from test_review_traceability_contract import record6
from ccr.reporting import delivery


CARRIERS = (r'C:\private\GET', 'C:/private/GET', r'\\server\share\GET',
            '//server/share/GET', 'file:/private/GET', 'file:///C:/private/GET')


class DeliveryLocalAuthorityTests(unittest.TestCase):
    complete_archive = privacy.DeliveryPrivacyRegressionTests.complete_archive
    snapshot = privacy.DeliveryPrivacyRegressionTests.snapshot

    def projection(self, factory=record13, manifest=None):
        record = factory()
        record['checks'] = []
        return delivery._Projection(record, manifest or {}, None, 'a' * 64)

    def test_local_get_suffix_does_not_export_neighbor_in_retained_deliveries(self):
        prose = ('Archivo C:\\private\\GET /api/windows314159.key; '
                 'Archivo \\\\server\\share\\GET /api/unc314159.key; '
                 'Archivo file:/private/GET /api/file314159.key; '
                 'GET /api/orders; https://public.example.test/guide')
        def update(record):
            record['verdict_reason'] = prose
            record['coverage']['flows'] = [prose]
        case, run = self.complete_archive(record_update=update)
        before = self.snapshot(run)
        context = {'pending': [{'text': prose, 'references': ['retained-review'], 'version': 'retained-head'}]}
        for mode in ('full', 'brief'):
            target = delivery.deliver(run, mode, case.repo, case.root / mode, context=context)
            for path in target.glob('*'):
                if path.suffix not in ('.md', '.json'):
                    continue
                with self.subTest(mode=mode, output=path.name):
                    text = path.read_text(encoding='utf-8')
                    self.assertNotIn('314159', text)
                    if path.name != '.ccr-delivery.json':
                        self.assertIn('/api/orders', text)
                        self.assertIn('https://public.example.test/guide', text)
            self.assertEqual(before, self.snapshot(run))

    def test_unquoted_local_tokens_cannot_lend_methods_in_current_or_historical_prose(self):
        for factory in (record13, record6):
            projection = self.projection(factory)
            for carrier in CARRIERS:
                for method in ('GET', 'POST', 'HEAD'):
                    text = 'Archivo ' + carrier[:-3] + method + ' /api/local314159.key'
                    with self.subTest(schema=factory.__name__, carrier=carrier, method=method):
                        self.assertNotIn('314159', projection.text(text))
            self.assertNotIn('314159', projection.text('Archivo cache/GET /api/local314159.key'))

    def test_independent_methods_and_known_roots_survive_local_tokens(self):
        projection = self.projection(manifest={'repository_path': 'C:/known/repo',
                                               'archive_root': 'C:/known/repo/_archive'})
        for carrier in CARRIERS:
            with self.subTest(carrier=carrier):
                for text in ('GET ' + carrier + ', /v2/orders',
                             carrier + ' GET /v2/orders'):
                    self.assertIn('/v2/orders', projection.text(text))
        self.assertEqual(projection.text(r'Archivo C:\known\repo\module.py'), 'Archivo module.py')
        self.assertIn('retained:', projection.text(r'Archivo C:\known\repo\_archive\private.log'))
        self.assertNotIn('private.log', projection.text(r'Archivo C:\known\repo\_archive\private.log'))

    def test_url_substring_inside_local_token_is_not_an_independent_reference(self):
        projection = self.projection()
        for carrier in (r'C:\private\https://files.example.test/local314159.key',
                        r'\\server\share\https://files.example.test/local314159.key',
                        'file:/private/https://files.example.test/local314159.key'):
            with self.subTest(carrier=carrier):
                result = projection.text('Archivo ' + carrier + '; https://public.example.test/guide')
                self.assertNotIn('314159', result)
                self.assertIn('https://public.example.test/guide', result)
