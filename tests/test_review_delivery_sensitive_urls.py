"""Portable links follow the same secret policy as prose and check commands."""
import json
from pathlib import Path
import unittest

from script_test_support import enable_package_imports

enable_package_imports()
from ccr.reporting import comment, delivery, render
from ccr.contracts.check_disclosure import safe_text
from ccr.workflow.builders import build_check_disclosure
from test_review_check_disclosure import fixture
from test_review_topology_integration import contexts12
from test_review_traceability_contract import record6


class DeliverySensitiveUrlTests(unittest.TestCase):
    def test_fragment_reference_credentials_without_argv_are_private_in_every_view(self):
        for fragment in ('access_token=FRAGMENTSECRET123',
                         '%61ccess_token=FRAGMENT%53ECRET123',
                         '/route?%61ccess_token=FRAGMENT%53ECRET123'):
            with self.subTest(fragment=fragment):
                data = fixture()
                record, identity, observations, sources = data
                url = 'https://example.com/callback#' + fragment
                record['scope']['reference'] = url
                record['checks'][0]['reference'] = url
                record['verdict_reason'] += ' Observed ' + url
                sidecar = build_check_disclosure(record, identity, observations, sources)
                kwargs = dict(check_disclosure_context=sidecar, check_disclosure_sources=sources)
                contexts = contexts12(record)
                contexts['check_publication_context']['checks'][0]['reference'] = url
                projection = self.projection(data)
                portable = projection.value(record)
                context = dict(decisions=[dict(text='Observed ' + url, references=[url],
                                              version='synthetic-v1')])
                outputs = (
                    render.render(record, 'comment', **contexts, **kwargs),
                    render.render_handoff(record, {'decisions_pending': ['Inspect ' + url]},
                        audience='comment', **contexts, **kwargs),
                    json.dumps(portable), render.render_portable(portable, {}),
                    delivery._brief(portable),
                    comment.prepare_public_comment(record, **contexts, **kwargs)['body'],
                    delivery._context_markdown(context, projection).decode(),
                )
                for index, output in enumerate(outputs):
                    with self.subTest(output=index):
                        for spelling in ('FRAGMENTSECRET123', 'FRAGMENT%53ECRET123'):
                            self.assertNotIn(spelling, output)
                self.assertEqual(safe_text(url), '[URL omitida]')

    def projection(self, record=None, *, disclosure=True):
        if not disclosure:
            return delivery._Projection(record6(), {}, Path('/project'), 'a' * 64)
        record, identity, observations, sources = fixture() if record is None else record
        sidecar = build_check_disclosure(record, identity, observations, sources)
        return delivery._Projection(record, {}, Path('/project'), 'a' * 64,
            check_disclosure_context=sidecar, check_disclosure_sources=sources)

    def test_sensitive_check_and_scope_links_never_reappear_in_portable_views(self):
        for scheme in ('https', 'HTTPS'):
            with self.subTest(scheme=scheme):
                data = fixture()
                record = data[0]
                url = scheme + '://example.com/check?page=1&token=DELIVERY_SECRET'
                record['checks'][0]['reference'] = url
                record['scope']['reference'] = url
                projection = self.projection(data)
                portable = projection.value(record)
                for output in (json.dumps(portable), delivery._brief(portable),
                               render.render_portable(portable, {})):
                    self.assertNotIn('DELIVERY_SECRET', output)
                self.assertIn('tests/test_queue.py', portable['checks'][0]['command'])

    def test_all_reference_and_optional_url_fields_use_the_publication_policy(self):
        for disclosure in (False, True):
            with self.subTest(disclosure=disclosure):
                url = 'https://example.com/resource?api_key=REFERENCE_SECRET'
                payload = dict(scope=dict(reference=url), checks=[dict(reference=url)],
                    findings=[dict(location=dict(url=url))],
                    previous_reviews=[dict(reference=url)],
                    rereview=[dict(previous_url=url, previous_reference=url)])
                projection = self.projection(disclosure=disclosure)
                portable = projection.value(payload)
                self.assertNotIn('REFERENCE_SECRET', json.dumps(portable))
                self.assertIsNone(portable['findings'][0]['location']['url'])
                self.assertIsNone(portable['rereview'][0]['previous_url'])

    def test_collected_context_links_and_prose_are_sanitized(self):
        for disclosure in (False, True):
            with self.subTest(disclosure=disclosure):
                url = 'https://example.com/source?token=CONTEXT_SECRET'
                context = dict(decisions=[dict(text='Observed ' + url,
                    references=[url], version='synthetic-v1')])
                output = delivery._context_markdown(context, self.projection(disclosure=disclosure))
                self.assertNotIn(b'CONTEXT_SECRET', output)

    def test_benign_public_links_are_preserved(self):
        for url in ('https://example.com/check?page=1', 'HTTPS://example.com/check?page=1',
                    'https://example.com/docs#installation',
                    'https://example.com/docs#token-reference',
                    'https://example.com/docs#/route?page=1'):
            projection = self.projection()
            payload = dict(scope=dict(reference=url), checks=[dict(reference=url)],
                findings=[dict(location=dict(url=url))])
            self.assertEqual(projection.value(payload), payload)
            self.assertEqual(safe_text(url), url)

    def test_sensitive_structural_url_is_rejected_instead_of_rewritten(self):
        projection = self.projection()
        with self.assertRaisesRegex(ValueError, 'private structural value'):
            projection.value(dict(scope=dict(snapshot='https://example.com/snapshot?token=IDENTITY_SECRET')))
