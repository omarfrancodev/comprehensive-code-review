"""Confirmed final-review cases: crossed fields, derived links and legacy proof."""
import copy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from script_test_support import enable_package_imports

enable_package_imports()
from ccr.reporting import comment, render
from ccr.reporting.projections import publication_digest
from ccr.contracts import check_disclosure as disclosure_contract
from ccr.reporting.check_disclosure import disclosure_view
from publication_fixtures import coverage_classification
from test_review_finding_publication import record_and_context


class FinalEditorialRegressionTests(unittest.TestCase):
    def test_json_escaped_source_credential_remains_private_in_editorial_copy(self):
        record, context=record_and_context()
        record['findings'][0]['evidence'][0]['details']=r'{"token":"\u0053OURCESECRET"}'
        context['source_sha256']=publication_digest(record)
        context['findings'][0]['evidence']=[dict(index=0,summary='La respuesta contiene SOURCESECRET')]
        body=render.render(record,'comment',finding_publication_context=context,
                           coverage_publication_context=coverage_classification(record))
        self.assertNotIn('SOURCESECRET',body)

    def test_handoff_own_context_learns_values_before_formatting_other_fields(self):
        record, _=record_and_context()
        context=dict(decisions_pending=['token=HIDDENSECRET','La respuesta HIDDENSECRET'])
        body=render.render_handoff(record,context,audience='comment',
                                   coverage_publication_context=coverage_classification(record))
        self.assertNotIn('HIDDENSECRET',body)

    def test_handoff_derived_links_withhold_private_source_report(self):
        record, _=record_and_context()
        from publication_fixtures import publication_record,check_classification
        for source in ('/private/reports/review.md',r'C:\private\reports\review.md',
                       'file:///private/reports/review.md'):
            with self.subTest(source=source):
                body=render.render_handoff(record,dict(source_report=source),audience='comment',
                    coverage_publication_context=coverage_classification(record))
                self.assertNotIn('private',body)
                self.assertNotIn('reports/review.md',body)
        with_checks=publication_record()
        body=render.render_handoff(with_checks,dict(source_report='/private/reports/review.md'),audience='comment',
            coverage_publication_context=coverage_classification(with_checks),
            check_publication_context=check_classification(with_checks))
        self.assertNotIn('reports/review.md',body)
        public='https://example.test/reviews/report.md'
        body=render.render_handoff(record,dict(source_report=public),audience='comment',
            coverage_publication_context=coverage_classification(record))
        self.assertIn(public+'#R001',body)

    def test_legacy_disclosure_json_explanation_keeps_proof_and_rerender(self):
        fixture=Path(__file__).parent/'fixtures/publication_legacy/draft3.json'
        data=json.loads(fixture.read_text(encoding='utf-8'))
        record=data['record'];disclosure=data['disclosure']
        disclosure['checks'][0]['explanation']='JSON data {"token":"LEGACYSECRET"}'
        sources={k:bytes.fromhex(v) for k,v in data['sources'].items()}
        sources['evidence/check-disclosure.json']=json.dumps(disclosure,sort_keys=True,separators=(',',':')).encode()
        draft=copy.deepcopy(data['draft'])
        kwargs=dict(check_disclosure_context=disclosure,check_disclosure_sources=sources)
        # Generate a legitimate historical body using only the frozen sanitizer,
        # retaining all original resource-proof verification and selected bytes.
        def old_text(value,secrets=(),**options):
            return disclosure_contract._legacy_safe_text(value,secrets,redact_paths=options.get('redact_paths',True))
        with patch.object(disclosure_contract,'safe_text',old_text):
            draft['check_disclosure_context']=disclosure_view(record,disclosure,sources,_legacy=True)
            draft['body']=render._render(record,'comment',
                check_publication_context=draft['check_publication_context'],
                coverage_publication_context=draft['coverage_publication_context'],_legacy=True,**kwargs)
        draft['body_sha256']=hashlib.sha256(draft['body'].encode()).hexdigest()
        self.assertIn('LEGACYSECRET',draft['body'])
        self.assertEqual(disclosure_contract.validate_check_disclosure(record,disclosure,sources,disclosure['input_identity']),[])
        self.assertTrue(comment.verify_public_comment(record,draft,draft['body'],**kwargs)['verified'])
        current=comment.prepare_public_comment(record,
            check_publication_context=draft['check_publication_context'],
            coverage_publication_context=draft['coverage_publication_context'],**kwargs)
        self.assertNotIn('LEGACYSECRET',current['body'])
