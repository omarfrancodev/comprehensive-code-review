"""Sparse editorial changes retain all source facts and evidence members."""
import copy
import unittest
from script_test_support import enable_package_imports

enable_package_imports()
from ccr.reporting.projections import publication_digest
from test_review_contract import clean_record, finding


def record_and_context():
    record = clean_record()
    record['findings'] = [finding(blocking=True)]
    record['verdict'] = 'not_approvable'
    record['findings'][0]['evidence'].append(dict(kind='static', check_id=None, details='Second original detail'))
    context = dict(schema_version=1, source_sha256=publication_digest(record),
                   findings=[dict(id='R001', evidence=[dict(index=1, summary='Public second detail')])])
    return record, context


class FindingPublicationTests(unittest.TestCase):
    def test_sparse_edits_inherit_all_unedited_source_fields(self):
        from ccr.reporting.finding_publication import project_public_findings
        record, context = record_and_context()
        original = copy.deepcopy(record)
        view = project_public_findings(record, context)
        expected = copy.deepcopy(record['findings'])
        expected[0]['evidence'][1]['details'] = 'Public second detail'
        self.assertEqual(view, expected)
        view[0]['evidence'][0]['details'] = 'Mutated copy'
        self.assertEqual(record, original)

    def test_invalid_contexts_fail_without_mutation(self):
        from ccr.reporting.finding_publication import normalize_finding_publication_context
        record, context = record_and_context()
        mutations = [dict(id='new', title='text'), dict(id='R001'), dict(id='R001', priority='P3'),
                     dict(id='R001', blocking_reason=None), dict(id='R001', title=''),
                     dict(id='R001', evidence=[]), dict(id='R001', evidence=[dict(index=True, summary='x')]),
                     dict(id='R001', evidence=[dict(index=-1, summary='x')]),
                     dict(id='R001', evidence=[dict(index=2, summary='x')]),
                     dict(id='R001', evidence=[dict(index=0, summary='x'),dict(index=0,summary='y')])]
        before = copy.deepcopy(record)
        for row in mutations:
            with self.subTest(row=row):
                bad = dict(context, findings=[row])
                with self.assertRaisesRegex(ValueError, 'invalid_finding_context'):
                    normalize_finding_publication_context(record, bad)
        with self.assertRaisesRegex(ValueError, 'finding_context_mismatch'):
            normalize_finding_publication_context(record, dict(context, source_sha256='0'*64))
        self.assertEqual(record, before)

    def test_normalization_sizes_types_and_unicode(self):
        from ccr.reporting.finding_publication import normalize_finding_publication_context, finding_publication_digest
        record, context = record_and_context()
        normalized = normalize_finding_publication_context(record, context)
        self.assertEqual(finding_publication_digest(normalized), publication_digest(normalized))
        for change in ({'schema_version':True}, {'extra':'x'}, {'findings':None},
                       {'findings':[dict(id='R001',title='é'*9000)]},
                       {'findings':[dict(id='R001',title='\ud800')]}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                normalize_finding_publication_context(record, dict(context, **change))

    def test_conditions_and_public_handoff_share_edited_correction(self):
        from ccr.reporting.render import render, render_handoff
        from publication_fixtures import coverage_classification
        record, context = record_and_context()
        context['findings'][0]['correction'] = 'Preservar el identificador requerido.'
        kwargs = dict(coverage_publication_context=coverage_classification(record), finding_publication_context=context)
        body = render(record, 'comment', **kwargs)
        handoff = render_handoff(record, audience='comment', **kwargs)
        self.assertEqual(body.count('Preservar el identificador requerido.'), 2)
        self.assertIn('Preservar el identificador requerido.', handoff)
        with self.assertRaises(ValueError):
            render(record, 'user', finding_publication_context=context)

    def test_values_marked_only_in_original_prose_are_learned_before_projection(self):
        from ccr.reporting.render import render
        from publication_fixtures import coverage_classification
        record, context = record_and_context()
        record['findings'][0]['evidence'][0]['details'] = 'token=SOURCESECRET'
        context['source_sha256'] = publication_digest(record)
        context['findings'][0].update(title='La respuesta SOURCESECRET', evidence=[dict(index=0,summary='Copia SOURCESECRET')])
        body = render(record,'comment',coverage_publication_context=coverage_classification(record),finding_publication_context=context)
        self.assertNotIn('SOURCESECRET',body)
