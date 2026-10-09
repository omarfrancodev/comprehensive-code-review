import copy
import unittest
from test_review_contract import clean_record, finding, contract


def record6():
    record = clean_record()
    record.update(schema_version=6, review_id='CR-' + 'a' * 20,
                  previous_reviews=[], grandfathered_ids={'findings': [], 'checks': []},
                  change_authors=[], presentation={'kind': 'review', 'subject': 'Validación de respuestas'})
    record['coverage']['areas'] = [dict(area=area, status='covered', details='Inspección del contrato',
                                          material=False, finding_ids=[]) for area in 'ABCDE']
    return record


def check(identifier='C001'):
    return dict(id=identifier, command='python C:\\private\\regression.py --token SECRET', revision='head-456',
                status='passed', failure_kind=None, evidence='Consumer returned expected id', reused=False,
                reuse_reason=None, rerun_reason=None, reference=None)


class TraceabilityContractTests(unittest.TestCase):
    def test_schema6_strict_ids_and_legacy_unchanged(self):
        record = record6()
        item = finding()
        item['id'] = 'F001'
        record['findings'] = [item]
        record['checks'] = [check()]
        self.assertEqual(contract.validate(record), [])
        for bad in ['F1', 'F-01', 'f001', 'D01-F001']:
            record['findings'][0]['id'] = bad
            self.assertTrue(any('canonical' in error for error in contract.validate(record)))
        self.assertEqual(contract.validate(clean_record()), [])
        record['surprise'] = True
        self.assertTrue(any('unknown field' in error for error in contract.validate(record)))

    def test_projections_have_counts_check_evidence_and_no_public_secrets(self):
        record = record6()
        record['checks'] = [check()]
        for audience in ('user', 'comment'):
            output = contract.render(record, audience)
            self.assertIn('### Hallazgos', output)
            for priority in ('P0', 'P1', 'P2', 'P3'):
                self.assertIn(priority + ': 0', output)
            self.assertIn('Consumer returned expected id', output)
            self.assertIn(record['review_id'], output)
            self.assertIn('<a id="C001"></a>', output)
        self.assertIn('SECRET', contract.render(record, 'user'))
        record['checks'][0]['evidence'] += ' at C:\\private\\file; command python C:\\private\\regression.py --token SECRET'
        public = contract.render(record, 'comment')
        self.assertNotIn('SECRET', public)
        self.assertNotIn('C:\\private', public)
        self.assertNotIn('python ', public)
        record['checks'][0]['evidence'] = 'Expected result stored at /srv/private/result.log'
        public = contract.render(record, 'comment')
        self.assertNotIn('/srv/private', public)
        self.assertIn('https://example.test/pr/12', public)

    def test_rereview_preserves_source_identity_and_not_reevaluated(self):
        record = record6()
        record['previous_reviews'] = [dict(review_id='CR-' + 'b' * 20,
                                           reference='https://example.test/reviews/old', verified=True)]
        record['grandfathered_ids']['findings'] = ['F-01']
        record['rereview'] = [dict(id='F-01', status='not_reevaluated', details='No cubierto por el nuevo alcance',
            previous_review_id='CR-' + 'b' * 20, previous_reference='https://example.test/reviews/old', previous_finding_id='F-01', previous_title='Contrato anterior',
            previous_url='https://example.test/reviews/old#F-01', check_ids=[])]
        self.assertEqual(contract.validate(record), [])
        output = contract.render(record, 'comment')
        self.assertIn('Contrato anterior', output)
        self.assertIn('F-01', output)
        self.assertIn('no reevaluado', output)
        record['rereview'][0]['previous_review_id'] = 'CR-' + 'c' * 20
        self.assertTrue(contract.validate(record))

    def test_same_cause_rereview_never_renames_previous_published_ids(self):
        for status in ('still_valid', 'resolved', 'withdrawn', 'not_reevaluated'):
            with self.subTest(status=status):
                record = record6()
                record['previous_reviews'] = [dict(review_id='CR-' + 'b' * 20,
                    reference='https://example.test/reviews/old', verified=True)]
                record['rereview'] = [dict(id='F999', status=status, details='Seguimiento del hallazgo publicado',
                    previous_review_id='CR-' + 'b' * 20, previous_reference='https://example.test/reviews/old',
                    previous_finding_id='F001', previous_title='Título anterior',
                    previous_url='https://example.test/reviews/old#F001', check_ids=[])]
                self.assertTrue(any('preserve' in error for error in contract.validate(record)))
                record['rereview'][0]['id'] = 'F001'
                self.assertEqual(contract.validate(record), [])

    def test_handoff_is_compact_context_without_authorization(self):
        record = record6()
        item = finding(blocking=True)
        item['id'] = 'F001'
        record['findings'] = [item]
        record['verdict'] = 'not_approvable'
        output = contract.render_handoff(record, context={'source_record': 'record.json',
            'source_report': 'report.md', 'requirements': ['https://example.test/spec'],
            'plan': ['plan.md'], 'decisions_pending': ['Elegir estrategia de migración']})
        self.assertIn('F001', output)
        self.assertIn(item['correction'], output)
        self.assertNotIn(item['scenario'], output)
        self.assertNotIn(item['impact'], output)
        self.assertIn('base-123', output)
        self.assertIn('head-456', output)
        self.assertIn('Elegir estrategia', output)
        self.assertIn('report.md#F001', output)
        self.assertIn('id="F001"', contract.render(record))

    def test_atomic_mapping_preserves_refs_and_never_aliases_number_matches(self):
        record = record6()
        item = finding()
        item['id'] = 'D01-F001'
        item['evidence'] = [dict(kind='executed', details='Observed failure', check_id='D01-C001')]
        record['findings'] = [item]
        record['checks'] = [check('D01-C001')]
        record['coverage']['areas'][0]['finding_ids'] = ['D01-F001']
        original = copy.deepcopy(record)
        result, mapping = contract.canonicalize_ids(record)
        self.assertEqual(record, original)
        self.assertEqual(mapping['findings'], {'D01-F001': 'F001'})
        self.assertEqual(mapping['checks'], {'D01-C001': 'C001'})
        self.assertEqual(result['findings'][0]['evidence'][0]['check_id'], 'C001')
        self.assertEqual(result['coverage']['areas'][0]['finding_ids'], ['F001'])
        self.assertEqual(result['aliases'], {})
        self.assertEqual(contract.validate(result), [])
        result['findings'][0]['priority'] = 'P0'
        remapped, _ = contract.canonicalize_ids(result)
        self.assertEqual(remapped['findings'][0]['id'], 'F001')

    def test_allocator_reserves_known_chain_and_remaps_aliases_atomically(self):
        record = record6()
        item = finding()
        item['id'] = 'D01-F001'
        record['findings'] = [item]
        record['aliases'] = {'D02-F001': 'D01-F001'}
        result, mapping = contract.canonicalize_ids(record,
            reserved_ids={'findings': ['F001', 'F005', 'F009'], 'checks': ['C007']})
        self.assertEqual(result['findings'][0]['id'], 'F010')
        self.assertEqual(result['aliases'], {'F011': 'F010'})
        self.assertNotEqual(mapping['findings']['D01-F001'], mapping['findings']['D02-F001'])
        result['findings'][0].update(priority='P1', status='unresolved')
        self.assertEqual(contract.canonicalize_ids(result)[0]['findings'][0]['id'], 'F010')

    def test_historical_identity_requires_exact_prior_provenance(self):
        record = record6()
        item = finding()
        item['id'] = 'F-01'
        record['findings'] = [item]
        record['grandfathered_ids']['findings'] = ['F-01']
        self.assertTrue(contract.validate(record))
        record['previous_reviews'] = [dict(review_id=None, reference='archive/old/record.json', verified=True)]
        record['rereview'] = [dict(id='F-01', status='still_valid', details='Verificado de nuevo',
            previous_review_id=None, previous_reference='archive/old/record.json', previous_finding_id='F-01',
            previous_title='Contrato anterior', previous_url=None, check_ids=[])]
        self.assertEqual(contract.validate(record), [])
        record['rereview'][0]['previous_finding_id'] = 'F1'
        self.assertTrue(contract.validate(record))

    def test_local_scope_has_exact_snapshot_and_public_authors_without_private_paths(self):
        record = record6()
        record['scope'].update(mode='working', snapshot='sha256:captured', target=None, reference=None)
        record['description'].update(status='not_applicable', identity=None, details='')
        record['change_authors'] = [dict(name='Ana', username='ana', verified=True,
                                          source='commit metadata', commits=['sha256:captured'])]
        public = contract.render(record, 'comment')
        self.assertIn('Autores del cambio', public)
        self.assertIn('@ana', public)
        handoff = contract.render_handoff(record)
        self.assertIn('sha256:captured', handoff)
        self.assertNotIn('MR/PR', handoff)

    def test_canonical_ids_reject_zero_lowercase_hyphen_and_check_reuse_keeps_source(self):
        record = record6()
        record['checks'] = [check()]
        for identifier in ('C000', 'c001', 'C1', 'C-01', 'D01-C001'):
            record['checks'][0]['id'] = identifier
            self.assertTrue(contract.validate(record))
        record['checks'][0].update(id='C001', reused=True, revision='actual-prior-head',
                                  reuse_reason='Inputs unchanged', reference='archive/old/execution.log')
        self.assertEqual(contract.validate(record), [])
        self.assertIn('actual-prior-head', contract.render(record))
        record['checks'][0]['rerun_reason'] = 'Reran changed input'
        self.assertTrue(contract.validate(record))

    def test_canonical_padding_is_unique_and_oversized_malformed_input_does_not_crash(self):
        record = record6()
        item = finding()
        record['findings'] = [item]
        for identifier in ('F0001', 'F000001', 'F' + '0' * 5000 + '1'):
            item['id'] = identifier
            self.assertTrue(any('canonical' in error for error in contract.validate(record)))
        for identifier in ('F001', 'F010', 'F100', 'F1000'):
            item['id'] = identifier
            self.assertEqual(contract.validate(record), [])

    def test_validation_check_anchors_do_not_consume_commonmark_lists(self):
        record = record6()
        record['checks'] = [check(), check('C002')]
        for audience in ('user', 'comment'):
            output = contract.render(record, audience)
            for identifier in ('C001', 'C002'):
                self.assertIn('\n\n<a id="' + identifier + '"></a>\n\n- ' + identifier + ':', output)
            self.assertIn('\n  - **Evidencia:** Consumer returned expected id', output)

    def test_malformed_schema6_collections_return_errors_without_crashing(self):
        variants = [('grandfathered_ids', {'findings': [[]], 'checks': []}),
                    ('grandfathered_ids', {'findings': [], 'checks': [[]]}),
                    ('grandfathered_ids', {'findings': {}, 'checks': None}),
                    ('previous_reviews', [dict(review_id=[], reference=[], verified=True)]),
                    ('previous_reviews', [None]),
                    ('rereview', [dict(id=[], status='new', details='Malformed ID', previous_review_id=None,
                        previous_reference=None, previous_finding_id=None, previous_title=None,
                        previous_url=None, check_ids=[])])]
        for field, value in variants:
            with self.subTest(field=field, value=value):
                record = record6()
                record[field] = value
                original = copy.deepcopy(record)
                self.assertTrue(contract.validate(record))
                self.assertEqual(record, original)

    def test_check_evidence_is_literal_text_not_tool_supplied_markdown_or_html(self):
        record = record6()
        record['checks'] = [check()]
        record['checks'][0]['evidence'] = '[All checks passed](https://evil.example/claim) <script>alert(1)</script>'
        for audience in ('user', 'comment'):
            output = contract.render(record, audience)
            self.assertNotIn('[All checks passed](', output)
            self.assertNotIn('<script>', output)
            self.assertIn('&lt;script&gt;', output)

    def test_allocator_rejects_malformed_collections_with_value_error(self):
        record = record6()
        record['grandfathered_ids']['findings'] = [[]]
        with self.assertRaises(ValueError):
            contract.canonicalize_ids(record)

    def test_complement_links_previous_review_even_without_rereview_rows(self):
        record = record6()
        record['presentation']['kind'] = 'complement'
        record['previous_reviews'] = [dict(review_id='CR-' + 'b' * 20,
            reference='https://example.test/reviews/prior', verified=True)]
        for audience in ('user', 'comment'):
            for output in (contract.render(record, audience), contract.render_handoff(record, audience=audience)):
                self.assertIn('ID de revisión', output)
                self.assertIn('Revisiones previas', output)
                self.assertIn('https://example.test/reviews/prior', output)
                self.assertIn('CR-' + 'b' * 20, output)

    def test_public_prior_metadata_preserves_known_id_without_private_reference(self):
        record = record6()
        prior_reference = 'private/archive/prior/record.json'
        prior_id = 'CR-' + 'b' * 20
        record['previous_reviews'] = [dict(review_id=prior_id, reference=prior_reference, verified=True)]
        record['rereview'] = [dict(id='F001', status='resolved', details='Resuelto',
            previous_review_id=prior_id, previous_reference=prior_reference, previous_finding_id='F001',
            previous_title='Título anterior', previous_url=None, check_ids=[])]
        for output in (contract.render(record, 'comment'), contract.render_handoff(record, audience='comment')):
            self.assertIn(prior_id, output)
            self.assertNotIn(prior_reference, output)
        self.assertIn(prior_reference, contract.render(record, 'user'))

    def test_declared_historical_alias_survives_with_verified_survivor_provenance(self):
        record = record6()
        item = finding()
        item['id'] = 'F-01'
        record['findings'] = [item]
        record['grandfathered_ids']['findings'] = ['F-01', 'A-02']
        record['aliases'] = {'A-02': 'F-01'}
        prior_reference = 'archive/old/record.json'
        record['previous_reviews'] = [dict(review_id=None, reference=prior_reference, verified=True)]
        record['rereview'] = [dict(id='F-01', status='still_valid', details='Conserva la causa anterior',
            previous_review_id=None, previous_reference=prior_reference, previous_finding_id='F-01',
            previous_title='Título anterior', previous_url=None, check_ids=[])]
        self.assertEqual(contract.validate(record), [])
        result, mapping = contract.canonicalize_ids(record)
        self.assertEqual(result['aliases'], {'A-02': 'F-01'})
        self.assertEqual(mapping['findings']['A-02'], 'A-02')
        self.assertEqual(result['findings'][0]['id'], 'F-01')
        for aliases in ({'A-03': 'F-01'}, {'A-02': 'A-02'}, {'A-02': 'A-03', 'A-03': 'F-01'}):
            with self.subTest(aliases=aliases):
                invalid = copy.deepcopy(record)
                invalid['aliases'] = aliases
                self.assertTrue(contract.validate(invalid))
        record['previous_reviews'][0]['verified'] = False
        self.assertTrue(contract.validate(record))


if __name__ == '__main__':
    unittest.main()
