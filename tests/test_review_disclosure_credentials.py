"""Selected argv credentials stay private across every disclosure consumer."""
import json
import unittest

from test_review_check_disclosure import fixture
from test_review_topology_integration import contexts12
from ccr.workflow.builders import build_check_disclosure
from ccr.reporting import comment, delivery, render
from ccr.reporting.markdown import markdown_text


class DisclosureCredentialTests(unittest.TestCase):
    def test_fragment_credentials_are_learned_in_wire_and_decoded_spellings(self):
        from ccr.reporting.check_disclosure import disclosure_view
        for fragment, wire in (('access_token=FRAGMENTSECRET123', 'FRAGMENTSECRET123'),
                               ('%61ccess_token=FRAGMENT%53ECRET123', 'FRAGMENT%53ECRET123'),
                               ('/route?%61ccess_token=FRAGMENT%53ECRET123', 'FRAGMENT%53ECRET123')):
            with self.subTest(fragment=fragment):
                decoded = 'FRAGMENTSECRET123'
                path = 'tests/' + decoded + '.py'
                record, identity, observations, sources = fixture(
                    ['pytest', path, '-k', decoded, 'https://example.com/callback#' + fragment],
                    {path: b'assert retry()\n'})
                repeated = 'Observed ' + wire + ' and ' + decoded
                record['verdict_reason'] += ' ' + repeated
                record['checks'][0]['evidence'] = repeated
                observations[record['checks'][0]['id']]['explanation'] = repeated
                disclosure = build_check_disclosure(record, identity, observations, sources)
                kwargs = dict(check_disclosure_context=disclosure, check_disclosure_sources=sources)
                contexts = contexts12(record)
                contexts['check_publication_context']['checks'][0]['evidence'] = repeated
                portable = delivery._Projection(record, {}, None, 'a' * 64, **kwargs).value(record)
                outputs = (
                    json.dumps(disclosure_view(record, disclosure, sources)),
                    render.render(record, 'comment', **contexts, **kwargs),
                    render.render_handoff(record, {'decisions_pending': [repeated]},
                        audience='comment', **contexts, **kwargs),
                    json.dumps(portable), render.render_portable(portable, {}),
                    delivery._brief(portable),
                    comment.prepare_public_comment(record, **contexts, **kwargs)['body'],
                )
                for index, output in enumerate(outputs):
                    with self.subTest(output=index):
                        for spelling in (wire, decoded):
                            self.assertNotIn(spelling, output)

    def test_encoded_userinfo_password_spellings_stay_private_in_every_view(self):
        from ccr.contracts.check_disclosure import safe_text, sensitive_values
        from ccr.reporting.check_disclosure import disclosure_view
        for wire, decoded in (('USER%5FPASSWORD123', 'USER_PASSWORD123'),
                              ('USER+PASSWORD%5F123', 'USER+PASSWORD_123')):
            with self.subTest(wire=wire):
                path = 'tests/' + decoded + '.py'
                record, identity, observations, sources = fixture(
                    ['pytest', 'tests/test_queue.py', '-k', decoded,
                     'https://user:' + wire + '@example.com/'],
                    {'tests/test_queue.py': b'assert retry()\n', path: b'assert retry()\n'})
                repeated = 'Observed ' + wire + ' and ' + decoded
                record['verdict_reason'] += ' ' + repeated
                record['checks'][0]['evidence'] = repeated
                observations[record['checks'][0]['id']]['explanation'] = repeated
                disclosure = build_check_disclosure(record, identity, observations, sources)
                kwargs = dict(check_disclosure_context=disclosure, check_disclosure_sources=sources)
                contexts = contexts12(record)
                contexts['check_publication_context']['checks'][0]['evidence'] = repeated
                portable = delivery._Projection(record, {}, None, 'a' * 64, **kwargs).value(record)
                outputs = (
                    json.dumps(disclosure_view(record, disclosure, sources)),
                    render.render(record, 'comment', **contexts, **kwargs),
                    render.render_handoff(record, {'decisions_pending': [repeated]},
                        audience='comment', **contexts, **kwargs),
                    json.dumps(portable), render.render_portable(portable, {}),
                    delivery._brief(portable),
                    comment.prepare_public_comment(record, **contexts, **kwargs)['body'],
                )
                for index, output in enumerate(outputs):
                    with self.subTest(output=index):
                        for spelling in (wire, decoded, markdown_text(wire), markdown_text(decoded)):
                            self.assertNotIn(spelling, output)
                # Userinfo plus signs are literal, unlike form query values.
                self.assertEqual(safe_text('USER PASSWORD_123', sensitive_values(sources)),
                                 'USER PASSWORD_123')

    def test_encoded_query_credential_wire_spelling_stays_private_when_repeated(self):
        from ccr.reporting.check_disclosure import disclosure_view
        wire = '%48%45%41%44%45%52%5F%50%52%49%56%41%54%45%5F%56%41%4C%55%45'
        for query in ('page=1&token=', 'page=1&amp;%74oken='):
            with self.subTest(query=query):
                path = 'tests/' + wire + '.py'
                record, identity, observations, sources = fixture(
                    ['pytest', path, '-k', wire, 'https://example.com/?' + query + wire],
                    {path: b'assert retry()\n'})
                repeated = 'Observed ' + wire + ' and HEADER_PRIVATE_VALUE'
                observations[record['checks'][0]['id']]['explanation'] = repeated
                record['verdict_reason'] += ' ' + repeated
                record['checks'][0]['evidence'] = repeated
                disclosure = build_check_disclosure(record, identity, observations, sources)
                kwargs = dict(check_disclosure_context=disclosure, check_disclosure_sources=sources)
                contexts = contexts12(record)
                contexts['check_publication_context']['checks'][0]['evidence'] = repeated
                portable = delivery._Projection(record, {}, None, 'a' * 64, **kwargs).value(record)
                outputs = (
                    json.dumps(disclosure_view(record, disclosure, sources)),
                    render.render(record, 'comment', **contexts, **kwargs),
                    render.render_handoff(record, {'decisions_pending': [repeated]},
                        audience='comment', **contexts, **kwargs),
                    json.dumps(portable), render.render_portable(portable, {}),
                    delivery._brief(portable),
                    comment.prepare_public_comment(record, **contexts, **kwargs)['body'],
                )
                for output in outputs:
                    for spelling in (wire, 'HEADER_PRIVATE_VALUE', markdown_text('HEADER_PRIVATE_VALUE')):
                        self.assertNotIn(spelling, output)

    def test_header_and_later_query_credentials_do_not_reappear_in_public_deliveries(self):
        for argv in (
            ['pytest', 'tests/HEADER_PRIVATE_VALUE.py', '-k', 'HEADER_PRIVATE_VALUE',
             '--header', 'Authorization: Bearer HEADER_PRIVATE_VALUE'],
            ['pytest', 'tests/HEADER_PRIVATE_VALUE.py', '-k', 'HEADER_PRIVATE_VALUE',
             'https://example.com/?page=1&token=HEADER_PRIVATE_VALUE'],
        ):
            with self.subTest(argv=argv):
                record, identity, observations, sources = fixture(argv,
                    {'tests/HEADER_PRIVATE_VALUE.py': b'assert retry()\n'})
                record['verdict_reason'] += ' Observed HEADER_PRIVATE_VALUE in the result.'
                record['checks'][0]['evidence'] = 'Observed HEADER_PRIVATE_VALUE in output.'
                observations[record['checks'][0]['id']]['explanation'] = 'Validated HEADER_PRIVATE_VALUE.'
                disclosure = build_check_disclosure(record, identity, observations, sources)
                kwargs = dict(check_disclosure_context=disclosure, check_disclosure_sources=sources)
                contexts = contexts12(record)
                contexts['check_publication_context']['checks'][0]['evidence'] = record['checks'][0]['evidence']
                portable = delivery._Projection(record, {}, None, 'a' * 64, **kwargs).value(record)
                draft = comment.prepare_public_comment(record, **contexts, **kwargs)
                outputs = (
                    render.render(record, 'comment', **contexts, **kwargs),
                    render.render_handoff(record, {'decisions_pending': ['Inspect HEADER_PRIVATE_VALUE']},
                        audience='comment', **contexts, **kwargs),
                    json.dumps(portable), render.render_portable(portable, {}),
                    delivery._brief(portable), draft['body'],
                )
                for output in outputs:
                    self.assertNotIn('HEADER_PRIVATE_VALUE', output)
                    self.assertNotIn(markdown_text('HEADER_PRIVATE_VALUE'), output)
                    self.assertIn('omitido', output)
