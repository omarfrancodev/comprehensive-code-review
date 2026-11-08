"""URL delimiters and archived detail regressions from PR 36."""
import copy
import unittest

from script_test_support import enable_package_imports

enable_package_imports()
from ccr.contracts import check_disclosure as contract
from ccr.reporting import comment
from ccr.reporting.check_disclosure import project_check_disclosure
from ccr.reporting.projections import publication_digest
from ccr.reporting.text_projection import _Projection
from ccr.workflow.builders import build_check_disclosure
from publication_fixtures import check_classification, coverage_classification
from test_review_check_disclosure import fixture
from test_review_coverage13 import record13


class URLBoundaryReviewTests(unittest.TestCase):
    def public_outputs(self, source, copy_text='Independent copy'):
        record = record13()
        record['checks'] = []
        record['verdict_reason'] = source
        record['description']['details'] = copy_text
        draft = comment.prepare_public_comment(
            record, coverage_publication_context=coverage_classification(record))
        self.assertTrue(comment.verify_public_comment(record, draft, draft['body'])['verified'])
        projected = _Projection(record, {}, '', publication_digest(record)).value(record)
        return (draft['body'], str(projected))

    def disclosure_outputs(self, explanation, *, historical=None, copy_text='Independent copy'):
        path = 'tests/probe.py'
        record, identity, observations, sources = fixture(
            ['pytest', '/private/home/repo/' + path, '--token', 'ARGSECRET'],
            {path: b'assert True\n'})
        record['description']['details'] = copy_text
        observation = next(iter(observations.values()))
        observation['explanation'] = explanation
        sidecar = build_check_disclosure(record, identity, observations, sources)
        if historical is not None:
            sidecar['checks'][0]['explanation'] = historical
        before = copy.deepcopy(sidecar)
        sources['evidence/check-disclosure.json'] = contract.canonical(sidecar)
        original_sources = copy.deepcopy(sources)
        self.assertEqual(contract.validate_check_disclosure(record, sidecar, sources, identity), [])
        view = project_check_disclosure(record, sidecar, sources, identity)
        kwargs = dict(check_disclosure_context=sidecar, check_disclosure_sources=sources)
        classification = check_classification(record)
        for row, check in zip(classification['checks'], record['checks']):
            row['purpose'] = check['purpose']
        draft = comment.prepare_public_comment(record,
            coverage_publication_context=coverage_classification(record),
            check_publication_context=classification, **kwargs)
        self.assertTrue(comment.verify_public_comment(record, draft, draft['body'], **kwargs)['verified'])
        projection = _Projection(record, {}, '', publication_digest(record), **kwargs)
        self.assertEqual(sidecar, before)
        self.assertEqual(sources, original_sources)
        self.assertIn(path, view['checks'][0]['command'])
        outputs = (str(view), draft['body'],
                   str(projection.value(record)) + str(projection.disclosure_rows))
        if historical is None:
            return (sidecar['checks'][0]['explanation'], *outputs)
        return outputs

    def test_external_quotes_and_sentence_punctuation_do_not_enter_learned_values(self):
        for source in (
            'URL “https://example.test/?api\\_key=COPIEDSECRET”.',
            'URL ‘https://example.test/?api\\_key=COPIEDSECRET’.',
            'URL https://example.test/?api\\_key=COPIEDSECRET.',
            'URL "https://example.test/?api\\_key=COPIEDSECRET".',
        ):
            with self.subTest(source=source):
                for output in self.public_outputs(source, 'Independent copy COPIEDSECRET'):
                    self.assertNotIn('COPIEDSECRET', output)

    def test_adjacent_destinations_have_independent_authorities(self):
        public = 'https://example.test/public'
        private = 'https://alice:NEIGHBORSECRET@example.test/private'
        for source in (public + '(' + private + ')', public + ';' + private,
                       '(' + public + '),' + private):
            with self.subTest(source=source):
                for output in (*self.public_outputs(source), *self.disclosure_outputs(source)):
                    self.assertNotIn('NEIGHBORSECRET', output)
                    self.assertIn(public, output)

    def test_markdown_destination_keeps_sensitive_query_with_comma_and_scheme(self):
        source = '[source](https://example.test/?api_key=FIRSTPART,https://example.test/SECRETTAIL)'
        for output in (*self.public_outputs(source), *self.disclosure_outputs(source)):
            self.assertNotIn('FIRSTPART', output)
            self.assertNotIn('SECRETTAIL', output)
        value = 'FIRSTPART,https://example.test/SECRETTAIL'
        self.assertIn(value, contract.projected_url_secrets(source))

    def test_prose_url_lists_inside_quotes_or_parentheses_check_every_authority(self):
        public = 'https://example.test/public?redirect=/public/target'
        for opening, closing in (('', ''), ('(', ')'), ('"', '"'), ("'", "'"), ('“', '”'), ('`', '`')):
            for separator in (',', ';'):
                source = (opening + public + separator +
                          'https://dev:GROUPPASSWORD@example.test/private' + closing)
                with self.subTest(opening=opening, separator=separator):
                    for output in (*self.public_outputs(source), *self.disclosure_outputs(source)):
                        self.assertNotIn('GROUPPASSWORD', output)
                        self.assertIn(public, output)

    def test_sensitive_query_value_owns_embedded_scheme_before_prose_list_splitting(self):
        for key in ('api_key', r'api\_key', '%61pi%5Fkey', 'api&#95;key', 'api&lowbar;key'):
            for separator in (',', ';', '('):
                source = 'https://example.test/?' + key + '=FIRSTPART' + separator + 'https://example.test/SECRETTAIL'
                with self.subTest(key=key, separator=separator):
                    self.assertIn('FIRSTPART' + separator + 'https://example.test/SECRETTAIL',
                                  contract.projected_url_secrets(source))
                    for output in (*self.public_outputs(source), *self.disclosure_outputs(source)):
                        self.assertNotIn('FIRSTPART', output)
                        self.assertNotIn('SECRETTAIL', output)

    def test_sensitive_fragment_values_keep_nested_scheme_and_query_as_one_value(self):
        for prefix in ('#token=', '#/route?password=', '?authorization='):
            for separator in (',', ';', '('):
                source = ('https://example.test/' + prefix + 'FIRSTPART' + separator +
                          'https://example.test/SECRETTAIL?next=public')
                with self.subTest(prefix=prefix, separator=separator):
                    for output in (*self.public_outputs(source), *self.disclosure_outputs(source)):
                        self.assertNotIn('FIRSTPART', output)
                        self.assertNotIn('SECRETTAIL', output)

    def test_quoted_url_list_teaches_query_values_without_group_closing_quote(self):
        for opening, closing in (('"', '"'), ('“', '”'), ('"(', ')"'), ('(“', '”)')):
            source = (opening + 'https://example.test/public,' +
                      r'https://example.test/private?api\_key=GROUPSECRET' + closing)
            with self.subTest(opening=opening):
                self.assertIn('GROUPSECRET', contract.projected_url_secrets(source))
                for output in self.public_outputs(source, 'Independent copy GROUPSECRET'):
                    self.assertNotIn('GROUPSECRET', output)
        source = '"https://example.test/public" https://example.test/?api\\_key=GROUPSECRET.'
        self.assertIn('GROUPSECRET', contract.projected_url_secrets(source))
        for output in self.public_outputs(source, 'Independent copy GROUPSECRET'):
            self.assertNotIn('GROUPSECRET', output)

    def test_completed_sensitive_parameter_preserves_independent_public_neighbor(self):
        for ending in ('&next=public', '&amp;next=public', '#next=public'):
            source = ('https://example.test/?api_key=FIRSTPART' + ending +
                      ',https://example.test/public?redirect=/public/target')
            with self.subTest(ending=ending):
                for output in (*self.public_outputs(source), *self.disclosure_outputs(source)):
                    self.assertNotIn('FIRSTPART', output)
                    self.assertIn('https://example.test/public?redirect=/public/target', output)

    def test_html_entities_do_not_change_original_markdown_destination_delimiters(self):
        for opening, closing in (('&#40;', '&#41;'), ('&#x28;', '&#x29;'), ('&lpar;', '&rpar;')):
            sources = (
                '[source](https://dev:ENTITYSECRET' + closing + '@example.test/private)',
                '[source](https://example.test/a' + opening + 'b),'
                'https://dev:ENTITYSECRET@example.test/private',
                '[source](https://example.test/?api_key=FIRST' + closing + 'SECRETTAIL)',
            )
            for source in sources:
                private = 'ENTITYSECRET' if 'ENTITYSECRET' in source else 'SECRETTAIL'
                copy_text = source + '\nIndependent copy ENTITYSECRET) FIRST)SECRETTAIL'
                with self.subTest(source=source):
                    for output in (*self.public_outputs(source, copy_text),
                                   *self.disclosure_outputs(source, copy_text=copy_text)):
                        self.assertNotIn(private, output)

    def test_expired_quote_after_interior_space_cannot_open_next_url(self):
        for opening, closing in (('"', '"'), ("'", "'"), ('“', '”'), ('`', '`')):
            for interior in (' text', ''):
                source = (opening + 'https://example.test/public' + interior + closing +
                          r' https://example.test/private?api\_key=OUTSIDESECRET.')
                with self.subTest(opening=opening, interior=interior):
                    self.assertIn('OUTSIDESECRET', contract.projected_url_secrets(source))
                    for output in self.public_outputs(source, 'Independent copy OUTSIDESECRET'):
                        self.assertNotIn('OUTSIDESECRET', output)

    def test_quotes_in_prose_before_first_url_cannot_bound_an_outside_url(self):
        for prefix in ('The literal "public" ', "The literal 'public' ", 'The literal “public” ',
                       'The literal `public` ', 'The literal "public" (', "Users' literal 'public' "):
            for key in ('api_key', r'api\_key'):
                ending = ').' if prefix.endswith('(') else '.'
                source = prefix + 'https://example.test/?' + key + '=OUTSIDESECRET' + ending
                with self.subTest(prefix=prefix, key=key):
                    self.assertIn('OUTSIDESECRET', contract.projected_url_secrets(source))
                    for output in self.public_outputs(source, 'Independent copy OUTSIDESECRET'):
                        self.assertNotIn('OUTSIDESECRET', output)

    def test_html_prose_separators_classify_every_authority_and_its_copies(self):
        for separator in ('&comma;', '&#44;', '&#x2c;', '&semi;', '&#59;', '&lpar;', '&#40;'):
            source = ('https://example.test/public' + separator +
                      'https://dev:ENTITYLISTSECRET@example.test/private')
            with self.subTest(separator=separator):
                self.assertIn('ENTITYLISTSECRET', contract.projected_url_secrets(source))
                selected = source + '\nIndependent copy ENTITYLISTSECRET'
                for output in (*self.public_outputs(source, selected),
                               *self.disclosure_outputs(source, copy_text=selected)):
                    self.assertNotIn('ENTITYLISTSECRET', output)
                    self.assertIn('https://example.test/public', output)

    def test_html_separators_preserve_complete_sensitive_values_and_markdown_targets(self):
        from html import unescape

        for separator in ('&comma;', '&#44;', '&#x2c;', '&semi;', '&#59;', '&lpar;', '&#40;'):
            source = 'https://example.test/?api_key=FIRST' + separator + 'https://example.test/SECRETTAIL'
            complete = 'FIRST' + unescape(separator) + 'https://example.test/SECRETTAIL'
            with self.subTest(separator=separator):
                self.assertIn(complete, contract.projected_url_secrets(source))
                selected = source + '\nIndependent copy ' + complete
                for variant in (source, '[source](' + source + ')'):
                    for output in (*self.public_outputs(variant, selected),
                                   *self.disclosure_outputs(variant, copy_text=selected)):
                        self.assertNotIn('SECRETTAIL', output)

    def test_actual_quoted_url_keeps_punctuation_owned_by_its_sensitive_value(self):
        for opening, closing in (('"', '"'), ("'", "'"), ('“', '”'), ('`', '`')):
            source = ('The literal "public" precedes ' + opening +
                      'https://example.test/?api_key=FULLSECRET.' + closing + '.')
            with self.subTest(opening=opening):
                self.assertIn('FULLSECRET.', contract.projected_url_secrets(source))
                for output in self.public_outputs(source, 'Independent copy FULLSECRET.'):
                    self.assertNotIn('FULLSECRET', output)

    def test_nested_destination_quotes_exclude_the_inner_closing_delimiter(self):
        for key in ('api_key', r'api\_key'):
            url = 'https://example.test/?' + key + '=NESTEDSECRET'
            sources = (
                'The result is "go to ‘' + url + '’. now"',
                'The result is "go to \'' + url + '\'. now"',
                'The result is ‘go to "' + url + '". now’',
                'Unclosed " prefix ‘' + url + '’.',
                'Unclosed \' prefix "' + url + '".',
                'Unclosed " prefix "' + url + '".',
                'The result is "go to ' + url + '. now"',
                'The result is "' + url + '. now"',
                'The result is "' + url + '. now ‘https://example.test/next’"',
                'The result is "go to ‘visit ' + url + '’. now"',
            )
            for source in sources:
                with self.subTest(source=source):
                    self.assertIn('NESTEDSECRET', contract.projected_url_secrets(source))
                    selected = source + '\nIndependent copy NESTEDSECRET'
                    for output in (*self.public_outputs(source, selected),
                                   *self.disclosure_outputs(source, copy_text=selected)):
                        self.assertNotIn('NESTEDSECRET', output)

    def test_nested_immediate_url_quotes_keep_the_punctuation_in_the_value(self):
        source = 'The result is "go to ‘https://example.test/?api_key=FULLSECRET.’. now"'
        self.assertIn('FULLSECRET.', contract.projected_url_secrets(source))
        for output in self.public_outputs(source, 'Independent copy FULLSECRET.'):
            self.assertNotIn('FULLSECRET', output)

    def test_quoted_url_list_whitespace_separates_complete_sensitive_values(self):
        for separator in (', ', '; ', '&comma; ', '&#44; '):
            source = ('"https://example.test/?api\\_key=FULLSECRET.' + separator +
                      'https://example.test/public"')
            with self.subTest(separator=separator):
                self.assertIn('FULLSECRET.', contract.projected_url_secrets(source))
                selected = source + '\nIndependent copy FULLSECRET.'
                for output in (*self.public_outputs(source, selected),
                               *self.disclosure_outputs(source, copy_text=selected)):
                    self.assertNotIn('FULLSECRET', output)
                    self.assertIn('https://example.test/public', output)

    def test_completed_quoted_destination_does_not_borrow_the_next_authority(self):
        for quote in ('"', "'"):
            source = (quote + 'https://example.test/public/' + quote +
                      'https://dev:ADJACENTSECRET@example.test/private')
            with self.subTest(quote=quote):
                for output in (*self.public_outputs(source), *self.disclosure_outputs(source)):
                    self.assertNotIn('ADJACENTSECRET', output)

    def test_markdown_tick_runs_bound_encoded_query_values_and_selected_copies(self):
        for length in (1, 2, 3, 4, 8):
            for key in ('api_key', '%61pi%5Fkey', r'api\_key'):
                ticks = '`' * length
                source = 'Observed ' + ticks + 'https://example.test/?' + key + '=MULTITICKSECRET' + ticks + '.'
                with self.subTest(length=length, key=key):
                    self.assertIn('MULTITICKSECRET', contract.projected_url_secrets(source))
                    selected = source + '\nIndependent copy MULTITICKSECRET'
                    for output in (*self.public_outputs(source, selected),
                                   *self.disclosure_outputs(source, copy_text=selected)):
                        self.assertNotIn('MULTITICKSECRET', output)

    def test_markdown_tick_runs_end_before_an_adjacent_private_authority(self):
        for length in (1, 2, 3, 4, 8):
            ticks = '`' * length
            for tail in ('/', '/\\'):
                source = ('Observed ' + ticks + 'https://example.test/public' + tail + ticks +
                          'https://dev:TICKNEIGHBORSECRET@example.test/private')
                with self.subTest(length=length, tail=tail):
                    self.assertIn('TICKNEIGHBORSECRET', contract.projected_url_secrets(source))
                    selected = source + '\nIndependent copy TICKNEIGHBORSECRET'
                    for output in (*self.public_outputs(source, selected),
                                   *self.disclosure_outputs(source, copy_text=selected)):
                        self.assertNotIn('TICKNEIGHBORSECRET', output)

    def test_markdown_code_uses_matching_run_lengths_and_keeps_literal_inner_ticks(self):
        for value in ('LEFT`MIDDLE`RIGHT', 'LEFT```MIDDLE`RIGHT'):
            source = 'Observed ``https://example.test/?%61pi%5Fkey=' + value + '``.'
            with self.subTest(value=value):
                self.assertIn(value, contract.projected_url_secrets(source))
                selected = source + '\nIndependent copy ' + value
                for output in (*self.public_outputs(source, selected),
                               *self.disclosure_outputs(source, copy_text=selected)):
                    self.assertNotIn('MIDDLE', output)
        unmatched = 'Observed ``https://example.test/?%61pi%5Fkey=MISMATCHSECRET`'
        self.assertIn('MISMATCHSECRET`', contract.projected_url_secrets(unmatched))

    def test_markdown_fences_and_escaped_openers_share_existing_code_boundaries(self):
        sources = (
            '```text\nhttps://example.test/?%61pi%5Fkey=BLOCKSECRET.\n```',
            '```text\nhttps://example.test/?%61pi%5Fkey=BLOCKSECRET.\n````',
            '~~~text\nhttps://example.test/?%61pi%5Fkey=BLOCKSECRET.\n~~~',
            'Observed \\``https://example.test/?%61pi%5Fkey=BLOCKSECRET.`',
        )
        for source in sources:
            with self.subTest(source=source):
                self.assertIn('BLOCKSECRET.', contract.projected_url_secrets(source))
                selected = source + '\nIndependent copy BLOCKSECRET.'
                for output in (*self.public_outputs(source, selected),
                               *self.disclosure_outputs(source, copy_text=selected)):
                    self.assertNotIn('BLOCKSECRET', output)

    def test_code_literals_keep_the_full_value_inside_quote_and_list_containers(self):
        url = 'https://example.test/?%61pi%5Fkey=FULLSECRET.'
        sources = (
            '~~~text\n' + url + '\n~~~',
            '> ~~~text\n> ' + url + '\n> ~~~',
            '> > ~~~text\n> > ' + url + '\n> > ~~~',
            '- ~~~text\n  ' + url + '\n  ~~~',
            '- > ~~~text\n  > ' + url + '\n  > ~~~',
            '> - ~~~text\n>   ' + url + '\n>   ~~~',
            '- item\n  > ~~~text\n  > ' + url + '\n  > ~~~',
            '\t> ~~~text\n\t> ' + url + '\n\t> ~~~',
            'Observed ``literal ' + url + '``',
        )
        context = 'Business identifier FULLSECRET; complete private copy FULLSECRET.'
        for source in sources:
            with self.subTest(source=source):
                secrets = contract.projected_url_secrets(source)
                self.assertIn('FULLSECRET.', secrets)
                self.assertNotIn('FULLSECRET', secrets)
                selected = source + '\n' + context
                disclosure_outputs = self.disclosure_outputs(source, copy_text=selected)
                for output in (*self.public_outputs(source, context), *disclosure_outputs[2:]):
                    self.assertIn('Business identifier FULLSECRET', output)
                    self.assertNotIn('complete private copy FULLSECRET', output)
                    self.assertNotIn('FULLSECRET.', output)

    def test_code_url_value_closers_are_literal_and_do_not_erase_public_identifiers(self):
        cases = (
            ('Observed ``https://example.test/?{key}=FULLSECRET)``', 'FULLSECRET)'),
            ('Observed ``https://example.test/?{key}=FULLSECRET]``', 'FULLSECRET]'),
            ('> ~~~text\n> https://example.test/?{key}=FULLSECRET)\n> ~~~', 'FULLSECRET)'),
            ('Observed ``x · [label](https://example.test/?{key}=FULLSECRET)TAIL)``', 'FULLSECRET)TAIL)'),
            ('Observed ``https://example.test/?{key}=FULLSECRET%29``', 'FULLSECRET)'),
        )
        for key in ('%61pi%5Fkey', 'api_key'):
            for template, complete in cases:
                source = template.format(key=key)
                context = 'Business identifier FULLSECRET; complete private copy ' + complete
                with self.subTest(source=source):
                    self.assertIn(complete, contract.projected_url_secrets(source))
                    selected = source + '\n' + context
                    views = self.disclosure_outputs(source, copy_text=selected)
                    for output in (*self.public_outputs(source, context), *views[2:]):
                        self.assertIn('Business identifier FULLSECRET', output)
                        self.assertNotIn('complete private copy FULLSECRET', output)

    def test_code_semantics_take_priority_over_an_interior_prose_quote(self):
        for key in ('%61pi%5Fkey', 'api_key'):
            url = 'https://example.test/?' + key + '=FULLSECRET.'
            sources = ('Observed ``"observed ' + url + '"``',
                       'Observed ``observed ' + url + '``',
                       'Observed ``"' + url + '"``')
            context = 'Business identifier FULLSECRET; complete private copy FULLSECRET.'
            for source in sources:
                with self.subTest(source=source):
                    self.assertIn('FULLSECRET.', contract.projected_url_secrets(source))
                    selected = source + '\n' + context
                    views = self.disclosure_outputs(source, copy_text=selected)
                    for output in (*self.public_outputs(source, context), *views[2:]):
                        self.assertIn('Business identifier FULLSECRET', output)
                        self.assertNotIn('complete private copy FULLSECRET', output)

    def test_literal_url_key_ownership_preserves_independent_and_nested_assignments(self):
        sources = (
            '``https://example.test/?api_key=FULLSECRET]`` token=EXPLICITSECRET',
            '``https://example.test/?api_key=FULLSECRET]&search=token=EXPLICITSECRET``',
            '~~~text\nhttps://example.test/?api_key=FULLSECRET]\ninside token: EXPLICITSECRET\n~~~',
        )
        context = 'Business identifier FULLSECRET; independent copy EXPLICITSECRET'
        for source in sources:
            with self.subTest(source=source):
                learned = contract.projected_sensitive_values(source)
                self.assertIn('FULLSECRET]', learned)
                self.assertNotIn('FULLSECRET', learned)
                self.assertIn('EXPLICITSECRET', learned)
                for output in (*self.public_outputs(source, context),
                               *self.disclosure_outputs(source, copy_text=source + '\n' + context)[2:]):
                    self.assertIn('Business identifier FULLSECRET', output)
                    self.assertNotIn('EXPLICITSECRET', output)
        source = '``https://example.test/?api_key=FULLSECRET]`` token=FULLSECRET'
        self.assertIn('FULLSECRET', contract.projected_sensitive_values(source))
        for output in self.public_outputs(source, 'Independent copy FULLSECRET'):
            self.assertNotIn('FULLSECRET', output)

    def test_unparseable_code_url_does_not_disable_assignment_learning(self):
        source = '``https://[broken/?api_key=INVALIDSECRET]``'
        self.assertIn('INVALIDSECRET', contract.projected_sensitive_values(source))
        for output in self.public_outputs(source, 'Independent copy INVALIDSECRET'):
            self.assertNotIn('INVALIDSECRET', output)

    def test_url_key_ownership_requires_its_complete_interpreted_assignment(self):
        urls = (
            'https://example.test&lbrack;/&quest;api_key=ENTITYSECRET',
            'https://example.test&#91;=OTHER/?api_key=ENTITYSECRET',
            'https://example.test&#91;token=OTHER/?api_key=ENTITYSECRET',
        )
        for url in urls:
            for source in ('Observed ``' + url + '``', '> ~~~text\n> ' + url + '\n> ~~~'):
                with self.subTest(source=source):
                    self.assertIn('ENTITYSECRET', contract.projected_sensitive_values(source))
                    context = 'Independent copy ENTITYSECRET'
                    for output in (*self.public_outputs(source, context),
                                   *self.disclosure_outputs(source + '\n' + context,
                                                            copy_text=source + '\n' + context)):
                        self.assertNotIn('ENTITYSECRET', output)

    def test_coherent_entity_parameters_keep_complete_values_without_short_prefixes(self):
        urls = (
            'https://example.test/&quest;api_key=FULLSECRET]',
            'https://example.test/?public=ok&amp;api_key=FULLSECRET]',
            'https://example.test/?token=OTHER&amp;api_key=FULLSECRET]',
            'https://example.test/&num;api_key=FULLSECRET]',
        )
        context = 'Business identifier FULLSECRET; complete private copy FULLSECRET]'
        for url in urls:
            source = 'Observed ``' + url + '``'
            with self.subTest(source=source):
                learned = contract.projected_sensitive_values(source)
                self.assertIn('FULLSECRET]', learned)
                self.assertNotIn('FULLSECRET', learned)
                for output in (*self.public_outputs(source, context),
                               *self.disclosure_outputs(source, copy_text=source + '\n' + context)[2:]):
                    self.assertIn('Business identifier FULLSECRET', output)
                    self.assertNotIn('complete private copy FULLSECRET', output)

    def test_exact_91fddf9_rows_keep_proof_and_redact_unlearned_credential_copies(self):
        # These exact retained rows were generated with the previous writer.
        historical = 'Observed ``[omitido]``\nIndependent copy ENTITYSECRET'
        for url in (
            'https://example.test&lbrack;/&quest;api_key=ENTITYSECRET',
            'https://example.test&#91;=OTHER/?api_key=ENTITYSECRET',
            'https://example.test&#91;token=OTHER/?api_key=ENTITYSECRET',
        ):
            source = 'Observed ``' + url + '``\nIndependent copy ENTITYSECRET'
            with self.subTest(source=source):
                for output in self.disclosure_outputs(source, historical=historical,
                                                      copy_text=source):
                    self.assertNotIn('ENTITYSECRET', output)

    def test_exact_4070520_rows_keep_proof_with_literal_url_projection(self):
        cases = (
            ('Observed ``x · [label](https://example.test/?api_key=FULLSECRET)TAIL)``',
             'Observed ``x · [label]([omitido]``', 'FULLSECRET)TAIL)'),
            ('Observed ``"observed https://example.test/?api_key=FULLSECRET."``',
             'Observed ``"observed [omitido]``', 'FULLSECRET.'),
            ('Observed ``https://example.test/?api_key=FULLSECRET]``',
             'Observed ``[omitido]]``', 'FULLSECRET]'),
        )
        for source, historical, complete in cases:
            with self.subTest(source=source):
                context = ('Business identifier FULLSECRET; complete private copy ' + complete)
                outputs = self.disclosure_outputs(source, historical=historical,
                                                  copy_text=source + '\n' + context)
                for output in outputs[1:]:
                    self.assertIn('Business identifier FULLSECRET', output)
                    self.assertNotIn('complete private copy FULLSECRET', output)

    def test_backslash_before_space_does_not_join_private_destination(self):
        for neighbor, private in (
            ('https://alice:NEIGHBORSECRET@example.test/private', 'NEIGHBORSECRET'),
            (r'C:\private folder\LOCALFILE.py', 'LOCALFILE'),
        ):
            source = 'URL https://example.test/public\\ ' + neighbor
            if neighbor.startswith('C:'):
                source = 'URL https://example.test/public\\ "' + neighbor + '"'
            with self.subTest(neighbor=neighbor):
                for output in self.disclosure_outputs(source):
                    self.assertNotIn(private, output)

    def test_archived_query_learns_copy_and_each_path_marker_has_its_own_boundary(self):
        source = '"https://example.test/ARGSECRET(view)?api\\_key=QUERYSECRET".'
        historical = '"[URL omitida])?api\\_key=QUERYSECRET".'
        for output in self.disclosure_outputs(source, historical=historical,
                                              copy_text='Independent copy QUERYSECRET'):
            self.assertNotIn('QUERYSECRET', output)
        paths = '"/private/FIRST.py" "/private folder/SECOND.py"'
        old_paths = '"[ruta privada] "[ruta privada] folder/SECOND.py"'
        for output in self.disclosure_outputs(paths, historical=old_paths):
            self.assertNotIn('SECOND.py', output)

    def test_each_public_url_preserves_redirect_query_in_projection(self):
        for separator in (',', ';'):
            source = ('https://example.test/first' + separator +
                      'https://example.test/second?redirect=/public/target')
            with self.subTest(separator=separator):
                for output in (*self.public_outputs(source), *self.disclosure_outputs(source)):
                    self.assertIn('https://example.test/second?redirect=/public/target', output)

    def test_exact_139a175_rows_keep_proof_and_get_current_privacy_projection(self):
        cases = (
            ('https://example.test/public;https://alice:NEIGHBORSECRET@example.test/private',
             'https://example.test/public;https://alice:NEIGHBORSECRET@example.test/private',
             'NEIGHBORSECRET'),
            ('[source](https://example.test/?api_key=FIRSTPART,https://example.test/SECRETTAIL)',
             '[source]([omitido],https://example.test/SECRETTAIL)', None),
            (r'URL https://example.test/public\ https://alice:NEIGHBORSECRET@example.test/private',
             r'URL https://example.test/public\ https://alice:NEIGHBORSECRET@example.test/private',
             'NEIGHBORSECRET'),
            ('URL “https://example.test/?api\\_key=COPIEDSECRET”.', 'URL “[omitido]', None),
        )
        for source, historical, private in cases:
            with self.subTest(source=source):
                outputs = self.disclosure_outputs(source, historical=historical)
                if private is not None:
                    for output in outputs:
                        self.assertNotIn(private, output)

    def test_exact_75f50e0_list_rows_keep_proof_and_protect_copies(self):
        for opening, closing in (('(', ')'), ('"', '"'), ('“', '”')):
            source = (opening + 'https://example.test/public,' +
                      'https://dev:GROUPPASSWORD@example.test/private' + closing)
            with self.subTest(opening=opening):
                for output in self.disclosure_outputs(source, historical=source,
                                                      copy_text='Independent copy GROUPPASSWORD'):
                    self.assertNotIn('GROUPPASSWORD', output)
                    self.assertIn('https://example.test/public', output)

    def test_exact_7806fd9_rows_keep_proof_and_current_selected_copy_protection(self):
        cases = (
            ('[source](https://dev:ENTITYSECRET&#41;@example.test/private)',
             '[source](https://dev:ENTITYSECRET&#41;@example.test/private)', 'ENTITYSECRET'),
            ('[source](https://example.test/a&#40;b),https://dev:ENTITYSECRET@example.test/private',
             '[source](https://example.test/a&#40;b),https://dev:ENTITYSECRET@example.test/private',
             'ENTITYSECRET'),
            ('"https://example.test/public text" https://example.test/?api\\_key=OUTSIDESECRET.',
             '"https://example.test/public text" [omitido]', 'OUTSIDESECRET'),
        )
        for source, historical, private in cases:
            with self.subTest(source=source):
                copy_text = source + '\nIndependent copy ENTITYSECRET) OUTSIDESECRET'
                for output in self.disclosure_outputs(source, historical=historical, copy_text=copy_text):
                    self.assertNotIn(private, output)

    def test_exact_4ed296c_rows_keep_proof_and_project_selected_sources_safely(self):
        cases = (
            ('https://example.test/public&comma;https://dev:ENTITYLISTSECRET@example.test/private',
             'https://example.test/public&comma;https://dev:ENTITYLISTSECRET@example.test/private',
             'ENTITYLISTSECRET'),
            ('The literal "public" https://example.test/?api\\_key=OUTSIDESECRET.',
             'The literal "public" [omitido]', 'OUTSIDESECRET'),
        )
        for source, historical, private in cases:
            with self.subTest(source=source):
                selected = source + '\nIndependent copy ' + private
                for output in self.disclosure_outputs(source, historical=historical, copy_text=selected):
                    self.assertNotIn(private, output)

    def test_exact_25108bc_nested_quote_row_keeps_proof_and_hides_the_outside_path(self):
        source = 'The result is "go to ‘https://example.test/public’/private/LOCALFILE.py now"'
        for output in self.disclosure_outputs(source, historical=source, copy_text=source):
            self.assertNotIn('LOCALFILE', output)
            self.assertIn('https://example.test/public', output)

    def test_exact_a6eeb21_code_row_keeps_proof_and_hides_its_neighbor(self):
        source = ('Observed ``https://example.test/public/``'
                  'https://dev:TICKNEIGHBORSECRET@example.test/private')
        selected = source + '\nIndependent copy TICKNEIGHBORSECRET'
        for output in self.disclosure_outputs(source, historical=source, copy_text=selected):
            self.assertNotIn('TICKNEIGHBORSECRET', output)
            self.assertIn('https://example.test/public', output)

    def test_existing_1c57bb5_quoted_code_sidecar_keeps_its_bytes_and_current_precision(self):
        source = '> ~~~text\n> https://example.test/?%61pi%5Fkey=FULLSECRET.\n> ~~~'
        historical = '> ~~~text\n> [omitido].\n> ~~~'
        selected = source + '\nBusiness identifier FULLSECRET; complete private copy FULLSECRET.'
        outputs = self.disclosure_outputs(source, historical=historical, copy_text=selected)
        for output in outputs[1:]:
            self.assertIn('Business identifier FULLSECRET', output)
            self.assertNotIn('complete private copy FULLSECRET', output)
            self.assertNotIn('FULLSECRET.', output)
