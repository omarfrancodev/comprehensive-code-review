"""Regressions from the public projection review of PR 36."""
import copy
import tracemalloc
import unittest
from unittest.mock import patch

from script_test_support import enable_package_imports

enable_package_imports()
from ccr.contracts import check_disclosure
from ccr.contracts.check_disclosure import input_identity_for, safe_text, sensitive_text_ranges
from ccr.contracts.review import validate
from ccr.reporting import comment, render
from ccr.reporting.projections import publication_digest
from ccr.workflow.builders import build_check_disclosure
from publication_fixtures import check_classification, coverage_classification
from test_review_contract import clean_record
from test_review_coverage13 import record13
from test_review_finding_publication import record_and_context


class PublicProjectionReviewTests(unittest.TestCase):
    def draft(self, record, **kwargs):
        self.assertEqual(validate(record), [])
        draft = comment.prepare_public_comment(
            record, coverage_publication_context=coverage_classification(record), **kwargs)
        self.assertTrue(comment.verify_public_comment(
            record, draft, draft['body'],
            check_disclosure_context=kwargs.get('check_disclosure_context'),
            check_disclosure_sources=kwargs.get('check_disclosure_sources'))['verified'])
        return draft['body']

    def test_finding_location_checks_full_destination_and_keeps_relative_label(self):
        for url, expected in (
            ('/private/work/hidden.py', None),
            ('file:///private/work/hidden.py', None),
            ('https://localhost/hidden.py', None),
            ('https://example.test/view(x)?token=LOCATORSECRET', None),
            ('https://example.test/view(x)#L42', 'https://example.test/view%28x%29#L42'),
        ):
            with self.subTest(url=url):
                record, _ = record_and_context()
                record['findings'][0]['location'].update(path='archive/handler.py', line=42, url=url)
                body = self.draft(record)
                self.assertIn('archive/handler.py:42', body)
                if expected is None:
                    self.assertNotIn(url, body)
                    self.assertNotIn('LOCATORSECRET', body)
                    self.assertNotIn('[archive/handler.py:42](', body)
                else:
                    self.assertIn('[archive/handler.py:42](' + expected + ')', body)
        record['findings'][0]['location'].update(path='/private/work/hidden.py', url=None)
        self.assertNotIn('/private/work/hidden.py', self.draft(record))

    def test_explicit_assignments_survive_lexical_classification_and_hide_copies(self):
        for source in (
            'La operación usa token=`ASSIGNSECRET`',
            'La operación usa token=`` ASSIGNSECRET ``',
            'Una nota sobre el token: password=ASSIGNSECRET',
            '``inside token=`ASSIGNSECRET` ``',
            '```\ninside token=`ASSIGNSECRET`\n```',
        ):
            with self.subTest(source=source):
                record = clean_record()
                record['verdict_reason'] = source + '\nLa regla por token: puede borrar'
                record['description']['details'] = 'Otra copia ASSIGNSECRET puede aparecer'
                body = self.draft(record)
                self.assertNotIn('ASSIGNSECRET', body)
                self.assertIn('por token: puede borrar', body)
                self.assertIn('puede aparecer', body)

    def test_fence_ends_at_container_boundary_and_prose_never_teaches_secret(self):
        tick = '```'
        for fenced in (
            f'> {tick}text\n> dentro token: FENCESECRET',
            f'- {tick}text\n  dentro token: FENCESECRET',
            f'- lista\n  {tick}text\n  dentro token: FENCESECRET',
            f'- lista\n  - interna\n  {tick}text\n  dentro token: FENCESECRET',
            f'- lista\n  > {tick}text\n  > dentro token: FENCESECRET',
            f'- - {tick}text\n    dentro token: FENCESECRET',
            f'- > {tick}text\n  > dentro token: FENCESECRET',
            f'> - {tick}text\n>   dentro token: FENCESECRET',
        ):
            with self.subTest(fenced=fenced):
                record = clean_record()
                record['verdict_reason'] = fenced + '\nLa regla por token: puede borrar'
                record['description']['details'] = 'Otra regla puede aparecer y cita FENCESECRET'
                body = self.draft(record)
                self.assertNotIn('FENCESECRET', body)
                self.assertIn('por token: puede borrar', body)
                self.assertIn('puede aparecer', body)

    def test_fence_in_list_quote_ends_when_only_the_outer_quote_remains(self):
        tick = '```'
        text = (f'- lista\n  > {tick}\n  > dentro token: FENCESECRET\n'
                '> La regla por token: puede borrar')
        self.assertNotIn('FENCESECRET', safe_text(text))
        self.assertIn('por token: puede borrar', safe_text(text))

    def test_evidence_grouping_uses_original_rows_for_comment_and_handoff(self):
        record, context = record_and_context()
        same = record['findings'][0]['evidence'][0]['details']
        context['findings'][0]['evidence'][0]['summary'] = same
        original = copy.deepcopy(record)
        kwargs = dict(finding_publication_context=context)
        body = self.draft(record, **kwargs)
        handoff = render.render_handoff(record, audience='comment',
            coverage_publication_context=coverage_classification(record), **kwargs)
        for output in (body, handoff):
            self.assertEqual(output.count('**Inspección estática**'), 2)
        self.assertEqual(record, original)

    def test_private_location_labels_reject_padded_and_home_paths(self):
        for path in ('  /private/LOCALFILE.py', r'   \private\LOCALFILE.py',
                     '~/LOCALFILE.py', r'~user\LOCALFILE.py', " '/private/LOCALFILE.py' "):
            with self.subTest(path=path):
                record, _ = record_and_context()
                record['findings'][0]['location']['path'] = path
                body = self.draft(record)
                self.assertNotIn('LOCALFILE', body)
                self.assertIn(r'\[ruta privada\]:12', body)

    def test_quoted_code_values_can_contain_shorter_backtick_runs(self):
        record = clean_record()
        secret = 'first`last'
        record['verdict_reason'] = f'~~~text\ninside token=``{secret}``\n~~~'
        record['description']['details'] = f'Copy of {secret} in the report'
        self.assertNotIn(secret, safe_text(record['verdict_reason']))
        self.assertNotIn(r'first\`last', self.draft(record))

    def test_unclosed_backtick_value_does_not_consume_the_next_field(self):
        record = clean_record()
        record['verdict_reason'] = '~~~\ntoken=`unfinished\npassword=`SECONDSECRET`\n~~~'
        record['description']['details'] = 'Copy SECONDSECRET elsewhere'
        self.assertNotIn('SECONDSECRET', self.draft(record))

    def test_tabs_in_quote_fences_follow_original_columns(self):
        for prefix, closing in (('>\t', '> '), ('> >\t', '> > '), (' >\t', '> '),
                                ('-\t>\t', '    > ')):
            with self.subTest(prefix=prefix):
                record = clean_record()
                record['verdict_reason'] = (prefix + '~~~\n' + closing + 'inside token: TABSECRET\n'
                                            + closing + '~~~\npor token: puede borrar')
                record['description']['details'] = 'Copy TABSECRET and prose puede appear'
                body = self.draft(record)
                self.assertNotIn('TABSECRET', body)
                self.assertIn('por token: puede borrar', body)
                self.assertIn('puede appear', body)

    def test_incomplete_credential_field_cannot_read_prose_outside_its_block(self):
        for text in ('> ~~~\n> inside token:\npuede borrar la reserva',
                     '- ~~~\n  inside token=\npuede borrar la reserva',
                     '`inside token: "partial` puede borrar la reserva"'):
            with self.subTest(text=text):
                record = clean_record()
                record['verdict_reason'] = text
                record['description']['details'] = 'También puede borrar aquí'
                self.assertEqual(safe_text(text), text)
                body = self.draft(record)
                self.assertIn('puede borrar la reserva', body)
                self.assertIn('puede borrar aquí', body)

    def test_explicit_evidence_edits_survive_original_deduplication(self):
        for repeated_kind in ('static', 'executed'):
            with self.subTest(repeated_kind=repeated_kind):
                record, context = record_and_context()
                evidence = record['findings'][0]['evidence']
                if repeated_kind == 'static':
                    evidence[1] = dict(evidence[0])
                else:
                    detail = 'Result from the verification'
                    record['checks'] = [dict(id='C001', command='pytest', revision=record['scope']['head'],
                        status='passed', failure_kind=None, evidence=detail, reused=False,
                        reuse_reason=None, rerun_reason=None)]
                    evidence[1] = dict(kind='executed', check_id='C001', details=detail)
                context['source_sha256'] = publication_digest(record)
                kwargs = dict(finding_publication_context=context)
                outputs = (self.draft(record, **kwargs),
                           render.render_handoff(record, audience='comment',
                               coverage_publication_context=coverage_classification(record), **kwargs))
                for output in outputs:
                    self.assertIn('Public second detail', output)

    def test_public_identity_does_not_use_prose_path_heuristics(self):
        record = clean_record()
        record['scope'].update(repository='archive/tool', target='evidence/integration')
        body = self.draft(record)
        handoff = render.render_handoff(record, audience='comment',
            coverage_publication_context=coverage_classification(record))
        for output in (body, handoff):
            self.assertIn('archive/tool', output)
            self.assertIn('evidence/integration', output)

    def test_private_home_directory_is_rejected_as_a_public_identity(self):
        record = clean_record()
        for repository in ('~/local-repository', '~user/local-repository'):
            with self.subTest(repository=repository):
                record['scope']['repository'] = repository
                with self.assertRaisesRegex(ValueError, 'private structural value'):
                    self.draft(record)

    def test_fragment_redaction_prepares_secret_spellings_once(self):
        from ccr.reporting.public_text import PublicText

        record = clean_record()
        count = 120
        record['verdict_reason'] = '\n'.join(
            f'token=MASK{i:04d} https://example.test/check/{i}' for i in range(count))
        formatter = PublicText(record, None, None)
        with patch.object(check_disclosure, '_secret_spellings', wraps=check_disclosure._secret_spellings) as prepare:
            output = formatter.text(record['verdict_reason'])
        self.assertNotIn('MASK', output)
        self.assertEqual(output.count('[omitido]'), count)
        self.assertIn('https://example.test/check/119', output)
        self.assertEqual(prepare.call_count, 1)

    def test_all_markdown_line_endings_protect_marked_values_and_copies(self):
        for ending in ('\r', '\r\n', '\n'):
            with self.subTest(ending=ending):
                record = record13()
                record['checks'] = []
                record['verdict_reason'] = ending.join(('~~~', 'inside token: CRSECRET', '~~~',
                                                        'Una nota por token: puede borrar'))
                record['description']['details'] = 'Copy CRSECRET, and puede belongs to prose'
                body = self.draft(record)
                self.assertNotIn('CRSECRET', body)
                self.assertIn('por token: puede borrar', body)
                self.assertNotIn('FIELDSECRET', safe_text('Un campo' + ending + '1. token: FIELDSECRET'))

    def test_editing_either_duplicate_index_preserves_the_inherited_detail(self):
        for index in (0, 1):
            with self.subTest(index=index):
                record, context = record_and_context()
                rows = record['findings'][0]['evidence']
                rows[1] = dict(rows[0])
                context['source_sha256'] = publication_digest(record)
                context['findings'][0]['evidence'][0]['index'] = index
                kwargs = dict(finding_publication_context=context)
                body = self.draft(record, **kwargs)
                handoff = render.render_handoff(record, audience='comment',
                    coverage_publication_context=coverage_classification(record), **kwargs)
                for output in (body, handoff):
                    self.assertIn('Public second detail', output)
                    self.assertIn(rows[0]['details'], output)

    def test_home_paths_are_private_in_prose_and_portable_locations(self):
        from ccr.reporting.text_projection import _Projection

        for path in ('~user/private/LOCALFILE.py', r'~user\private\LOCALFILE.py',
                     '~/private/LOCALFILE.py', '"~user/private folder/LOCALFILE.py"'):
            with self.subTest(path=path):
                record, _ = record_and_context()
                finding = record['findings'][0]
                finding['scenario'] = 'Archivo ' + path
                finding['location']['path'] = path
                self.assertNotIn('LOCALFILE', self.draft(record))
                projected = _Projection(record, {}, '', publication_digest(record)).value(record)
                self.assertNotIn('LOCALFILE', projected['findings'][0]['location']['path'])
                self.assertNotIn('LOCALFILE', projected['findings'][0]['scenario'])

    def test_proven_resources_and_operands_are_rendered_as_typed_values(self):
        from test_review_check_disclosure import fixture

        for path in ('tests/probe.py', 'archive/probe.py', 'evidence/probe.py'):
            with self.subTest(path=path):
                record, identity, observations, sources = fixture(
                    ['pytest', '/private/home/repo/' + path, '--token', 'PROOFSECRET'],
                    {path: b'assert retry()\n'})
                classification = check_classification(record)
                classification['checks'][0]['purpose'] = record['checks'][0]['purpose']
                kwargs = dict(check_publication_context=classification, check_disclosure_sources=sources,
                              check_disclosure_context=build_check_disclosure(record, identity, observations, sources))
                body = self.draft(record, **kwargs)
                handoff = render.render_handoff(record, audience='comment',
                    coverage_publication_context=coverage_classification(record), **kwargs)
                for output in (body, handoff):
                    self.assertIn('pytest ' + path, output)
                    self.assertIn('**Recursos del proyecto:** ' + path, output)
                    self.assertNotIn('PROOFSECRET', output)

    def test_fragments_do_not_repeat_full_secret_matching(self):
        from ccr.reporting.public_text import PublicText

        count = 160
        record = clean_record()
        record['verdict_reason'] = '\n'.join(
            f'token=MASK{i:04d} https://example.test/resource/{i}' for i in range(count))
        formatter = PublicText(record, None, None)
        sanitize = check_disclosure._sanitize_spellings
        visited = 0

        class CountedSpellings(tuple):
            def __iter__(self):
                nonlocal visited
                for item in super().__iter__():
                    visited += 1
                    yield item

        def tracked(value, spellings, **kwargs):
            return sanitize(value, CountedSpellings(spellings), **kwargs)

        with patch.object(check_disclosure, '_sanitize_spellings', side_effect=tracked):
            result = formatter.text(record['verdict_reason'])
        self.assertNotIn('MASK', result)
        self.assertIn('https://example.test/resource/159', result)
        self.assertLess(visited, 8 * count)

    def test_known_value_in_partially_escaped_url_is_private(self):
        from ccr.reporting.text_projection import _Projection

        for link in (r'https://example.test/path/ALPHA\*BETA_GAMMA',
                     r'https://example.test/path/ALPHA%2ABETA\_GAMMA',
                     r'https://example.test/path/ALPHA&#42;BETA\_GAMMA'):
            with self.subTest(link=link):
                record = record13()
                record['checks'] = []
                record['verdict_reason'] = 'token="ALPHA*BETA_GAMMA"'
                record['description']['details'] = 'Refer to ' + link + ' and https://example.test/public'
                self.assertNotIn('ALPHA', self.draft(record))
                projected = _Projection(record, {}, '', publication_digest(record)).value(record)
                self.assertNotIn('ALPHA', projected['description']['details'])
                self.assertIn('https://example.test/public', projected['description']['details'])

    def test_tilde_component_in_relative_paths_is_not_a_home_directory(self):
        from ccr.reporting.text_projection import _Projection

        for path in ('tests/~fixture/probe.py', r'tests\~fixture\probe.py'):
            with self.subTest(path=path):
                record, _ = record_and_context()
                finding = record['findings'][0]
                finding['scenario'] = 'Use ' + path + ' instead of ~user/private/LOCALFILE.py'
                finding['location']['path'] = path
                projection = _Projection(record, {}, '', publication_digest(record))
                projected = projection.value(record)['findings'][0]
                self.assertIn(path, projected['scenario'])
                self.assertEqual(projected['location']['path'], 'tests/~fixture/probe.py')
                self.assertNotIn('LOCALFILE', self.draft(record))

    def test_runs_of_tildes_are_not_named_home_paths(self):
        from ccr.reporting.text_projection import _SOURCE_TOKENS
        for text in ('~' * 4096, '~' * 4096 + '/api/v1'):
            with self.subTest(has_route=text.endswith('/api/v1')):
                self.assertFalse(any(match['local'] for match in _SOURCE_TOKENS.finditer(text)))

    def test_pre_cr_editorial_sidecar_is_accepted_but_projected_with_current_privacy(self):
        from test_review_check_disclosure import fixture
        from ccr.reporting.check_disclosure import project_check_disclosure

        record, identity, observations, sources = fixture()
        original = '~~~\rinside token: OLDROWSECRET\r~~~'
        next(iter(observations.values()))['explanation'] = original
        sidecar = build_check_disclosure(record, identity, observations, sources)
        self.assertNotIn('OLDROWSECRET', sidecar['checks'][0]['explanation'])
        # 8ddb505 retained this explanation verbatim with its LF-only lexer.
        sidecar['checks'][0]['explanation'] = original
        archived = copy.deepcopy(sidecar)
        self.assertEqual(check_disclosure.validate_check_disclosure(record, sidecar, sources, identity), [])
        view = project_check_disclosure(record, sidecar, sources, identity)
        self.assertNotIn('OLDROWSECRET', view['checks'][0]['explanation'])
        self.assertEqual(sidecar, archived)
        tampered = copy.deepcopy(sidecar)
        tampered['checks'][0]['command'] += ' --unproved'
        self.assertTrue(check_disclosure.validate_check_disclosure(record, tampered, sources, identity))

    def test_typed_urls_and_prose_keep_sensitive_query_attached_to_full_url(self):
        from ccr.reporting.text_projection import _Projection

        record, _ = record_and_context()
        known = 'ALPHA*BETA_GAMMA'
        locator = r'https://example.test/(view)/ALPHA\*BETA_GAMMA'
        record['verdict_reason'] = 'token="' + known + '"'
        record['scope']['reference'] = locator
        record['findings'][0]['location']['url'] = locator
        record['description']['details'] = (
            locator + r'?api\_key=QUERYSECRET and https://example.test/public')
        body = self.draft(record)
        projected = _Projection(record, {}, '', publication_digest(record),
                                editorial_texts=(record['description'],)).value(record)
        self.assertNotIn('QUERYSECRET', body)
        self.assertNotIn('QUERYSECRET', projected['description']['details'])
        self.assertNotIn('ALPHA', projected['scope']['reference'])
        self.assertIsNone(projected['findings'][0]['location']['url'])
        self.assertIn('https://example.test/public', body)
        record['description']['details'] = (
            r'https://example.test/path)/ALPHA\*BETA_GAMMA?api\_key=QUERYSECRET')
        self.assertNotIn('QUERYSECRET', self.draft(record))

    def test_tilde_inside_punctuated_components_remains_relative(self):
        from ccr.reporting.text_projection import _Projection

        for path in ('tests/generated-~fixture/probe.py', 'tests/gen.~fixture/probe.py',
                     r'tests\gen-~fixture\probe.py', 'tests/gen:~fixture/probe.py'):
            with self.subTest(path=path):
                record, _ = record_and_context()
                finding = record['findings'][0]
                finding['location']['path'] = path
                finding['scenario'] = 'Use ' + path + ' before (~user/LOCALFILE.py)'
                projected = _Projection(record, {}, '', publication_digest(record)).value(record)['findings'][0]
                self.assertEqual(path.replace('\\', '/'), projected['location']['path'])
                self.assertIn(path, projected['scenario'])
                self.assertNotIn('LOCALFILE', projected['scenario'])

    def test_archived_f6b_explanation_is_valid_and_new_details_are_private(self):
        from test_review_check_disclosure import fixture
        from ccr.reporting.check_disclosure import project_check_disclosure
        from ccr.reporting.text_projection import _Projection

        record, identity, observations, sources = fixture()
        explanation = '~~~\ninside token=``EARLY`SECRET``\n~~~'
        next(iter(observations.values()))['explanation'] = explanation
        sidecar = build_check_disclosure(record, identity, observations, sources)
        sidecar['checks'][0]['explanation'] = explanation  # Exact f6b083e spelling.
        self.assertEqual(check_disclosure.validate_check_disclosure(record, sidecar, sources, identity), [])
        view = project_check_disclosure(record, sidecar, sources, identity)
        self.assertNotIn('EARLY`SECRET', view['checks'][0]['explanation'])

        record['verdict_reason'] = 'token="ALPHA*BETA_GAMMA"'
        original = r'Observed https://example.test/view/ALPHA\*BETA_GAMMA'
        next(iter(observations.values()))['explanation'] = original
        sidecar = build_check_disclosure(record, identity, observations, sources)
        self.assertEqual(sidecar['checks'][0]['explanation'], original)
        projected = _Projection(record, {}, '', publication_digest(record),
            check_disclosure_context=sidecar, check_disclosure_sources=sources)
        self.assertNotIn('ALPHA', projected.disclosure_rows[record['checks'][0]['id']]['explanation'])
        self.assertEqual(sidecar['checks'][0]['explanation'], original)

    def test_partially_escaped_known_secret_rejects_structural_identity(self):
        from ccr.reporting.text_projection import _Projection

        record = clean_record()
        record['verdict_reason'] = 'token="ALPHA*BETA_GAMMA"'
        record['responsible'].update(name=r'ALPHA\*BETA_GAMMA', username=None)
        with self.assertRaisesRegex(ValueError, 'private structural value'):
            self.draft(record)
        with self.assertRaisesRegex(ValueError, 'private structural value'):
            _Projection(record, {}, '', publication_digest(record)).value(record)

    def test_escaped_url_parameter_teaches_secret_to_all_fields(self):
        from ccr.reporting.text_projection import _Projection

        record = record13()
        record['checks'] = []
        record['verdict_reason'] = r'https://example.test/(view)/page?api\_key=COPIEDSECRET'
        record['description']['details'] = 'Independent copy COPIEDSECRET'
        self.assertNotIn('COPIEDSECRET', self.draft(record))
        projected = _Projection(record, {}, '', publication_digest(record)).value(record)
        self.assertNotIn('COPIEDSECRET', projected['description']['details'])

    def test_home_assignments_hide_paths_without_truncating_relative_components(self):
        from ccr.reporting.text_projection import _Projection

        record, _ = record_and_context()
        record['findings'][0]['scenario'] = (
            r'HOME=~dev/LOCAL1 --config=~dev\LOCAL2 carpeta:~dev/LOCAL3 '
            r'tests/path=~fixture/probe.py tests/path:~fixture/probe.py')
        projected = _Projection(record, {}, '', publication_digest(record)).value(record)
        for output in (self.draft(record), projected['findings'][0]['scenario']):
            for private in ('LOCAL1', 'LOCAL2', 'LOCAL3'):
                self.assertNotIn(private, output)
            self.assertIn('fixture/probe.py', output)

    def test_adjacent_links_and_balanced_url_are_preserved_independently(self):
        from ccr.reporting.text_projection import _Projection

        record = record13()
        record['checks'] = []
        record['description']['details'] = (
            '[private](https://example.test/private?api_key=LINKSECRET),'
            '[public](https://example.test/(view)/next)')
        projected = _Projection(record, {}, '', publication_digest(record)).value(record)
        self.assertNotIn('LINKSECRET', projected['description']['details'])
        self.assertIn('https://example.test/(view)/next', projected['description']['details'])
        self.assertIn(r'https://example.test/\(view\)/next', self.draft(record))

    def test_sidecar_writer_and_current_detail_hide_full_urls_and_private_paths(self):
        from test_review_check_disclosure import fixture
        from ccr.reporting.check_disclosure import project_check_disclosure
        from ccr.reporting.text_projection import _Projection

        path = 'tests/probe.py'
        record, identity, observations, sources = fixture(
            ['pytest', '/private/home/repo/' + path, '--token', 'ARGSECRET'],
            {path: b'assert retry()\n'})
        observation = next(iter(observations.values()))
        observation['explanation'] = (
            r'https://example.test/(view)/ARGSECRET?api\_key=QUERYSECRET '
            r'~dev/HOMEFILE //server/share/UNCFILE https://example.test/(view)/next')
        sidecar = build_check_disclosure(record, identity, observations, sources)
        self.assertNotIn('QUERYSECRET', sidecar['checks'][0]['explanation'])
        self.assertIn('https://example.test/(view)/next', sidecar['checks'][0]['explanation'])
        view = project_check_disclosure(record, sidecar, sources, identity)
        projected = _Projection(record, {}, '', publication_digest(record),
            check_disclosure_context=sidecar, check_disclosure_sources=sources)
        for explanation in (view['checks'][0]['explanation'],
                            projected.disclosure_rows[record['checks'][0]['id']]['explanation']):
            for hidden in ('QUERYSECRET', 'HOMEFILE', 'UNCFILE'):
                self.assertNotIn(hidden, explanation)
        self.assertIn(path, view['checks'][0]['command'])

        legacy_row = check_disclosure.build_disclosure_row(
            record['checks'][0], observation, sources, identity, _pre_atomic=True)
        self.assertIn('QUERYSECRET', legacy_row['explanation'])
        archived = dict(sidecar, checks=[legacy_row])
        view = project_check_disclosure(record, archived, sources, identity)
        self.assertNotIn('QUERYSECRET', view['checks'][0]['explanation'])
        self.assertIn('QUERYSECRET', archived['checks'][0]['explanation'])

    def test_quoted_url_escapes_teach_unquoted_secret_copies(self):
        from ccr.reporting.text_projection import _Projection

        for quote, key in (('"', r'api\_key'), ("'", r'api\_key'), ('"', r'api\-key')):
            with self.subTest(quote=quote, key=key):
                record = record13()
                record['checks'] = []
                record['verdict_reason'] = f'URL {quote}https://example.test/?{key}=COPIEDSECRET{quote}.'
                record['description']['details'] = 'Unquoted copy COPIEDSECRET'
                self.assertNotIn('COPIEDSECRET', self.draft(record))
                projected = _Projection(record, {}, '', publication_digest(record)).value(record)
                self.assertNotIn('COPIEDSECRET', projected['description']['details'])

    def test_parenthesized_prose_url_preserves_privacy_of_adjacent_destinations(self):
        from ccr.reporting.text_projection import _Projection

        for neighbor, private in (('https://alice:NEIGHBORSECRET@example.test/other','NEIGHBORSECRET'),
                                  ('https://localhost/private','localhost'),
                                  (r'C:\private\LOCALFILE.py','LOCALFILE')):
            with self.subTest(neighbor=neighbor):
                record = record13()
                record['checks'] = []
                record['description']['details'] = '(https://example.test/(view)/next),' + neighbor
                projected = _Projection(record, {}, '', publication_digest(record)).value(record)
                self.assertNotIn(private, projected['description']['details'])
                self.assertNotIn(private, self.draft(record))
                self.assertIn('https://example.test/(view)/next', projected['description']['details'])

    def test_home_assignment_inside_parentheses_is_private(self):
        from ccr.reporting.text_projection import _Projection

        record = record13()
        record['checks'] = []
        record['description']['details'] = 'Use (HOME=~dev/LOCALFILE) with tests/path=~fixture/probe.py'
        body = self.draft(record)
        projected = _Projection(record, {}, '', publication_digest(record)).value(record)
        for output in (body, projected['description']['details']):
            self.assertNotIn('LOCALFILE', output)
            self.assertIn('fixture/probe.py', output)

    def test_historical_query_after_closing_parenthesis_and_quoted_paths(self):
        from test_review_check_disclosure import fixture
        from ccr.reporting.check_disclosure import project_check_disclosure
        from ccr.reporting.text_projection import _Projection

        path = 'tests/probe.py'
        record, identity, observations, sources = fixture(
            ['pytest', '/private/home/repo/' + path, '--token', 'ARGSECRET'],
            {path: b'assert True\n'})
        observation = next(iter(observations.values()))
        observation['explanation'] = (
            r'https://example.test/ARGSECRET(view)?api\_key=QUERYSECRET '
            r'"C:\private folder\WINFILE.py" "/private folder/POSIXFILE.py"')
        sidecar = build_check_disclosure(record, identity, observations, sources)
        row = check_disclosure.build_disclosure_row(
            record['checks'][0], observation, sources, identity, _pre_atomic=True)
        self.assertIn('QUERYSECRET', row['explanation'])
        archived = dict(sidecar, checks=[row])
        before = copy.deepcopy(archived)
        for selected in (sidecar, archived):
            view = project_check_disclosure(record, selected, sources, identity)
            portable = _Projection(record, {}, '', publication_digest(record),
                check_disclosure_context=selected, check_disclosure_sources=sources)
            for explanation in (view['checks'][0]['explanation'],
                                portable.disclosure_rows[record['checks'][0]['id']]['explanation']):
                for hidden in ('QUERYSECRET', 'WINFILE', 'POSIXFILE'):
                    self.assertNotIn(hidden, explanation)
            self.assertIn(path, view['checks'][0]['command'])
        self.assertEqual(archived, before)

    def test_reused_revision_collision_is_rejected(self):
        record = record13()
        revision = 'ab' * 20
        check = record['checks'][0]
        check.update(reused=True, revision=revision, reuse_reason='Same functional inputs',
                     reference='evidence/previous-run.log', execution=dict(kind='reused', executor=None))

        def contexts():
            classification = check_classification(record)
            classification['checks'][0]['purpose'] = check['purpose']
            return dict(check_publication_context=classification,
                        check_disclosure_context=build_check_disclosure(
                            record, input_identity_for(record), {}, {}))

        self.assertIn(revision, self.draft(record, **contexts()))
        record['verdict_reason'] = 'token=' + revision
        kwargs = contexts()
        with self.assertRaisesRegex(ValueError, 'private structural value'):
            self.draft(record, **kwargs)
        with self.assertRaisesRegex(ValueError, 'private structural value'):
            render.render_handoff(record, audience='comment',
                coverage_publication_context=coverage_classification(record), **kwargs)

    def test_resolved_finding_identity_collision_is_rejected(self):
        record = record13()
        record['checks'] = []
        identity = 'F991'
        prior = dict(review_id='CR-' + 'b'*20, reference='https://example.test/previous', verified=True)
        record['previous_reviews'] = [prior]
        record['rereview'] = [dict(id=identity, status='resolved', details='Resolved in this head',
            previous_review_id=prior['review_id'], previous_reference=prior['reference'],
            previous_finding_id=identity, previous_title='Original finding', previous_url=None, check_ids=[])]
        self.assertIn(identity, self.draft(record))
        record['verdict_reason'] = 'token=' + identity
        with self.assertRaisesRegex(ValueError, 'private structural value'):
            self.draft(record)

    def test_encoded_overlaps_do_not_allocate_one_interval_per_match(self):
        text = '&#120;' * 2400
        secrets = ['x' * length for length in range(2, 58)]
        tracemalloc.start()
        try:
            self.assertEqual(list(sensitive_text_ranges(text, secrets)), [(0, len(text))])
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        self.assertLess(peak, 4 * 1024 * 1024)
        self.assertEqual(list(sensitive_text_ranges('a&#98;cd', ('ab', 'bc'))), [(0, 7)])

    def test_invalid_record_rejects_matching_editorial_context_in_prepare_and_verify(self):
        record, context = record_and_context()
        draft = comment.prepare_public_comment(record, finding_publication_context=context,
            coverage_publication_context=coverage_classification(record))
        del record['findings']
        digest = publication_digest(record)
        context['source_sha256'] = digest
        draft.update(source_sha256=digest, finding_publication_context=context,
                     finding_publication_sha256=publication_digest(context))
        for operation in (
            lambda: comment.prepare_public_comment(record, finding_publication_context=context),
            lambda: comment.verify_public_comment(record, draft, draft['body']),
        ):
            with self.subTest(operation=operation), self.assertRaisesRegex(ValueError, 'findings'):
                operation()
