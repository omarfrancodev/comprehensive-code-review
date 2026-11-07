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
