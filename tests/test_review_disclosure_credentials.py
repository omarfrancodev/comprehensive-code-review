"""Selected argv credentials stay private across every disclosure consumer."""
import json
import unittest

from test_review_check_disclosure import fixture
from test_review_topology_integration import contexts12
from ccr.workflow.builders import build_check_disclosure
from ccr.reporting import comment, delivery, render
from ccr.reporting.markdown import markdown_text


class DisclosureCredentialTests(unittest.TestCase):
    def test_long_numeric_entities_preserve_prose_and_redact_other_credentials(self):
        from ccr.contracts.check_disclosure import safe_text
        secret = 'CREDENTIAL)123'
        for entity in ('&#' + '9' * 5000 + ';', '&#' + '9' * 5000,
                       '&#x' + 'F' * 5000 + ';'):
            with self.subTest(entity_prefix=entity[:4], semicolon=entity.endswith(';')):
                repeated = 'Observed ' + entity + ' and %43REDENTIAL%29123'
                self.assertEqual(safe_text(repeated, {secret}),
                                 'Observed ' + entity + ' and [omitido]')
                record, identity, observations, sources = fixture(
                    ['pytest', 'tests/test_queue.py', '--token', secret])
                record['verdict_reason'] += ' ' + repeated
                record['checks'][0]['evidence'] = repeated
                observations[record['checks'][0]['id']]['explanation'] = repeated
                disclosure = build_check_disclosure(record, identity, observations, sources)
                contexts = contexts12(record)
                contexts['check_publication_context']['checks'][0]['evidence'] = repeated
                kwargs = dict(check_disclosure_context=disclosure, check_disclosure_sources=sources)
                portable = delivery._Projection(record, {}, None, 'a' * 64, **kwargs).value(record)
                outputs = (
                    render.render(record, 'comment', **contexts, **kwargs),
                    render.render_handoff(record, {'decisions_pending': [repeated]}, audience='comment', **contexts, **kwargs),
                    comment.prepare_public_comment(record, **contexts, **kwargs)['body'],
                    json.dumps(portable), render.render_portable(portable, {}), delivery._brief(portable))
                for index, output in enumerate(outputs):
                    with self.subTest(view=index):
                        self.assertIn('9' * 5000 if entity.startswith('&#9') else 'F' * 5000, output)
                        self.assertNotIn(secret, output)
                        self.assertNotIn('%43REDENTIAL%29123', output)
                        self.assertIn('omitido', output)

    def test_zero_padded_numeric_entities_cannot_hide_known_credentials(self):
        from ccr.contracts.check_disclosure import safe_text
        for entity in ('&#' + '0' * 5000 + '67;', '&#x' + '0' * 5000 + '43;'):
            with self.subTest(hexadecimal=entity.startswith('&#x')):
                value = 'prefix ' + entity + 'REDENTIAL)123 suffix'
                self.assertEqual(safe_text(value, {'CREDENTIAL)123'}),
                                 'prefix [omitido] suffix')

    def test_encoded_redaction_preserves_source_text_outside_matching_runs(self):
        from urllib.parse import quote
        from ccr.contracts.check_disclosure import safe_text
        cases = (
            ('ñ prefix %43REDENTIAL%29123 suffix', {'CREDENTIAL)123'}, 'ñ prefix [omitido] suffix'),
            ('prefix %41%42%43 suffix', {'B'}, 'prefix [omitido] suffix'),
            ('prefix aXYZb)123 suffix', {'a.*b)123'}, 'prefix aXYZb)123 suffix'),
            ('prefix %61.*b%29123 suffix', {'a.*b)123'}, 'prefix [omitido] suffix'),
            ('prefix %broken%2 text', {'CREDENTIAL)123'}, 'prefix %broken%2 text'),
            ('prefix %43RED&amp;ENT%29123 suffix', {'CRED&amp;ENT)123'}, 'prefix [omitido] suffix'),
            (r'prefix %43RED\_ENT%29123 suffix', {r'CRED\_ENT)123'}, 'prefix [omitido] suffix'),
            ('prefix &#37;43REDENTIAL&#37;29123 suffix', {'CREDENTIAL)123'}, 'prefix [omitido] suffix'),
            ('prefix %61baba suffix', {'aba'}, 'prefix [omitido]ba suffix'),
        )
        for value, secrets, expected in cases:
            with self.subTest(value=value):
                self.assertEqual(safe_text(value, secrets), expected)
        unmatched = 'prefix ' + quote('\\' * 64 + 'Y', safe='') + ' suffix'
        self.assertEqual(safe_text(unmatched, {'\\' * 32 + 'Z'}), unmatched)
        # Either overlapping copy may be withheld first; neither can survive.
        import html
        from urllib.parse import unquote
        overlapping = safe_text('a&#98;a%62&#97;', {'aba'})
        self.assertNotIn('aba', html.unescape(unquote(overlapping)))

    def test_encoded_known_credentials_in_prose_ignore_url_delimiter_boundaries(self):
        from urllib.parse import quote
        from ccr.contracts.check_disclosure import safe_text, sensitive_values
        for secret in ('CREDENTIAL)123', 'CREDENTIAL]123', 'CREDENTIAL+123',
                       'CREDENTIAL%5F123', 'CREDÉNTIAL)123', 'CRED_ENT)123',
                       'CRED&<ENT)123', r'CRED\ENT)123', 'CRED🔑)123',
                       'CRED&amp;ENT)123', r'CRED\_ENT)123'):
            encoded = ''.join('%%%02X' % byte for byte in secret.encode('utf-8'))
            for spelling in (encoded, encoded.lower(), quote(secret, safe=''),
                             quote(markdown_text(secret), safe=';'), encoded.replace('%', '&#37;')):
                with self.subTest(secret=secret, spelling=spelling):
                    record, identity, observations, sources = fixture(
                        ['pytest', 'tests/test_queue.py', '--token', secret])
                    repeated = 'https://example.com/result/' + secret + '?note=' + spelling
                    record['verdict_reason'] += ' Observed ' + repeated
                    record['checks'][0]['evidence'] = 'Observed ' + repeated
                    observations[record['checks'][0]['id']]['explanation'] = 'Observed ' + repeated
                    disclosure = build_check_disclosure(record, identity, observations, sources)
                    contexts = contexts12(record)
                    contexts['check_publication_context']['checks'][0]['evidence'] = record['checks'][0]['evidence']
                    kwargs = dict(check_disclosure_context=disclosure, check_disclosure_sources=sources)
                    portable = delivery._Projection(record, {}, None, 'a' * 64, **kwargs).value(record)
                    outputs = (safe_text(repeated, sensitive_values(sources)),
                        render.render(record, 'comment', **contexts, **kwargs),
                        render.render_handoff(record, {'decisions_pending': [repeated]}, audience='comment', **contexts, **kwargs),
                        comment.prepare_public_comment(record, **contexts, **kwargs)['body'],
                        json.dumps(portable, ensure_ascii=False), render.render_portable(portable, {}), delivery._brief(portable))
                    for index, output in enumerate(outputs):
                        with self.subTest(view=index):
                            self.assertNotIn(secret, output)
                            self.assertNotIn(spelling, output)
                            self.assertNotIn(markdown_text(spelling), output)
                    benign = 'prefix https://example.com/help?note=OTHER%20VALUE suffix'
                    self.assertEqual(safe_text(benign, sensitive_values(sources)), benign)
                    # A second encoding layer is not recursively decoded.
                    self.assertEqual(safe_text('%2543REDENTIAL%2529123', {'CREDENTIAL)123'}),
                                     '%2543REDENTIAL%2529123')

    def test_literal_encoded_credential_in_url_is_checked_before_normalization(self):
        from ccr.contracts.check_disclosure import safe_text, sensitive_values
        for secret in ('CREDENTIAL%5F123', 'CREDENTIAL&amp;123', r'CREDENTIAL\_123',
                       'CREDENTIAL)123', 'CREDENTIAL]123'):
            with self.subTest(secret=secret):
                record, identity, observations, sources = fixture(
                    ['pytest', 'tests/test_queue.py', '--token', secret])
                reference = 'https://example.com/result/' + secret
                record['checks'][0]['reference'] = reference
                disclosure = build_check_disclosure(record, identity, observations, sources)
                contexts = contexts12(record)
                contexts['check_publication_context']['checks'][0]['reference'] = reference
                kwargs = dict(check_disclosure_context=disclosure, check_disclosure_sources=sources)
                portable = delivery._Projection(record, {}, None, 'a' * 64, **kwargs).value(record)
                outputs = (safe_text(reference, sensitive_values(sources)),
                    render.render(record, 'comment', **contexts, **kwargs),
                    render.render_handoff(record, {}, audience='comment', **contexts, **kwargs),
                    comment.prepare_public_comment(record, **contexts, **kwargs)['body'],
                    json.dumps(portable), render.render_portable(portable, {}), delivery._brief(portable))
                for index, output in enumerate(outputs):
                    with self.subTest(view=index):
                        self.assertNotIn(secret, output)
                        self.assertNotIn(reference, output)

    def test_literal_redaction_cannot_split_a_url_before_encoded_secret_check(self):
        from ccr.contracts.check_disclosure import safe_text, sensitive_values
        secret = 'CREDENTIAL_123'
        encoded = '%43REDENTIAL_123'
        for reference in (
                'https://example.com/result/' + secret + '?note=' + encoded,
                'https://example.com/result/' + encoded + '?note=' + secret,
                'https://example.com/result/' + encoded + '?first=' + secret + '&last=' + encoded):
            with self.subTest(reference=reference):
                record, identity, observations, sources = fixture(
                    ['pytest', 'tests/test_queue.py', '--token', secret])
                record['checks'][0]['reference'] = reference
                disclosure = build_check_disclosure(record, identity, observations, sources)
                contexts = contexts12(record)
                contexts['check_publication_context']['checks'][0]['reference'] = reference
                kwargs = dict(check_disclosure_context=disclosure, check_disclosure_sources=sources)
                portable = delivery._Projection(record, {}, None, 'a' * 64, **kwargs).value(record)
                outputs = (safe_text(reference, sensitive_values(sources)),
                    render.render(record, 'comment', **contexts, **kwargs),
                    render.render_handoff(record, {}, audience='comment', **contexts, **kwargs),
                    comment.prepare_public_comment(record, **contexts, **kwargs)['body'],
                    json.dumps(portable), render.render_portable(portable, {}), delivery._brief(portable))
                for index, output in enumerate(outputs):
                    with self.subTest(view=index):
                        self.assertNotIn(secret, output)
                        self.assertNotIn(encoded, output)
                benign = 'https://example.com/result/OTHER_VALUE?note=%4FTHER_VALUE'
                # An earlier redaction must not affect a later URL's boundaries.
                output = safe_text(secret + ' ' + reference + ' ' + benign,
                                   sensitive_values(sources))
                self.assertNotIn(encoded, output)
                self.assertIn(benign, output)

    def test_known_password_in_encoded_public_reference_is_not_reintroduced(self):
        from urllib.parse import quote
        from ccr.contracts.check_disclosure import safe_text, sensitive_values
        password = 'USER+PASSWORD_123'
        for suffix in (password, 'USER%2bPASSWORD_123', '%55SER%2BPASSWORD_123'):
            with self.subTest(suffix=suffix):
                record, identity, observations, sources = fixture(
                    ['pytest', 'tests/test_queue.py',
                     'https://user:USER+PASSWORD%5F123@example.com/'])
                reference = 'https://example.com/result/' + suffix
                record['checks'][0]['reference'] = reference
                disclosure = build_check_disclosure(record, identity, observations, sources)
                contexts = contexts12(record)
                # Publication contexts must describe the exact updated source.
                contexts['check_publication_context']['checks'][0]['reference'] = reference
                kwargs = dict(check_disclosure_context=disclosure, check_disclosure_sources=sources)
                portable = delivery._Projection(record, {}, None, 'a' * 64, **kwargs).value(record)
                outputs = (render.render(record, 'comment', **contexts, **kwargs),
                    render.render_handoff(record, {}, audience='comment', **contexts, **kwargs),
                    comment.prepare_public_comment(record, **contexts, **kwargs)['body'],
                    json.dumps(portable), render.render_portable(portable, {}), delivery._brief(portable))
                for index, output in enumerate(outputs):
                    with self.subTest(view=index):
                        for spelling in (password, quote(password, safe='/:#?&=%-._~'), suffix):
                            self.assertNotIn(spelling, output)
                secrets = sensitive_values(sources)
                for benign in ('https://example.com/result/OTHER+VALUE_123',
                               'https://example.com/result/USER%20PASSWORD_123'):
                    self.assertEqual(safe_text(benign, secrets), benign)

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
