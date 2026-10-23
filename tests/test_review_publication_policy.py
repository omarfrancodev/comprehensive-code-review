"""Audience policy preserves product evidence without publishing review mechanics."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_review_execution_policy import record8, limit
from test_review_profile_names import record7
from test_review_contract import contract, MODULE_PATH
from publication_fixtures import publication_record, check_classification
from ccr.reporting import projections as review_publication


def classification(value, kind='validation', summary=None):
    digest = hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()
    return dict(source_sha256=digest, limitations=[dict(index=i, kind=kind, public_summary=summary)
        for i, _ in enumerate(value['coverage']['limitations'])])


class PublicationPolicyTests(unittest.TestCase):
    def test_public_checks_do_not_publish_internal_execution_data(self):
        value = publication_record()
        original = copy.deepcopy(value)
        context = check_classification(value)
        public = contract.render(value, audience='comment', check_publication_context=context)
        private = contract.render(value, audience='user')
        for internal in ('evidence/', 'CS2012', '-m:1'):
            self.assertNotIn(internal, public)
            self.assertIn(internal, private)
        rows = review_publication.public_checks(value, context)
        self.assertEqual(rows[1]['status'], 'failed')
        self.assertEqual(rows[1]['failure_kind'], 'product')
        self.assertEqual(rows[2]['revision'], value['scope']['base'])
        self.assertEqual(value, original)

    def test_relative_local_reference_is_suppressed_without_extra_classification(self):
        value = publication_record()
        value['checks'] = value['checks'][:1]
        output = contract.render(value, audience='comment')
        self.assertNotIn('evidence/test-scheduling.log', output)
        self.assertIn('C001', output)

    def test_free_reuse_reason_requires_bound_public_summary(self):
        value = publication_record()
        value['checks'][0].update(reused=True, reuse_reason='Los inputs funcionales no cambiaron')
        value['checks'][0]['execution'] = {'kind': 'reused', 'executor': None}
        with self.assertRaisesRegex(ValueError, 'check publication context'):
            contract.render(value, audience='comment')
        context = check_classification(value)
        self.assertIn('Los inputs funcionales no cambiaron', contract.render(
            value, audience='comment', check_publication_context=context))

    def test_check_classification_cannot_change_status_or_add_evidence_url(self):
        value = publication_record()
        context = check_classification(value)
        for mutation in (
                {'status': 'passed'},
                {'reference': 'https://evil.example.test/new'},
                {'id': 'C999'},
                {'private_note': 'extra'}):
            bad = copy.deepcopy(context)
            bad['checks'][1].update(mutation)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                review_publication.public_checks(value, bad)

    def test_material_execution_gap_remains_public_with_check_projection(self):
        value = publication_record()
        value['coverage']['limitations'] = [dict(kind='execution', material=True,
            public_summary='La validación de compatibilidad requerida sigue pendiente.',
            detail='Runner agotó recursos al compilar el proyecto')]
        value['verdict'] = 'insufficient_evidence'
        output = contract.render(value, audience='comment',
                                 check_publication_context=check_classification(value))
        self.assertIn('La validación de compatibilidad requerida sigue pendiente.', output)
        self.assertNotIn('Runner agotó recursos', output)

    def test_private_report_explicitly_discloses_degraded_profile(self):
        value = record8('deep')
        value['coverage']['execution'].update(status='degraded', results=[], fallbacks=[dict(
            assignments=['D1', 'D2', 'V1'], reason='explicit_restriction', detail='Delegation prohibited',
            source='evidence/context.json#restriction')])
        value['coverage'].update(verification='unavailable', adequate=False)
        value['coverage']['limitations'] = [limit(material=True, summary='Required validation incomplete')]
        value['verdict'] = 'insufficient_evidence'
        self.assertIn('**Ejecución del perfil:** degradada', contract.render(value))
        self.assertNotIn('Ejecución del perfil', contract.render(value, 'comment'))

    def test_internal_execution_detail_stays_private(self):
        value = record8()
        value['coverage']['limitations'] = [limit(detail='Worker tool denied by local harness')]
        before = copy.deepcopy(value)
        self.assertIn('Worker tool denied', contract.render(value))
        self.assertNotIn('Worker tool denied', contract.render(value, 'comment'))
        self.assertEqual(value, before)

    def test_material_execution_publishes_impact(self):
        value = record8()
        value['coverage']['limitations'] = [limit(material=True, summary='Required compatibility check remains incomplete',
                                                detail='Worker tool denied by local harness')]
        value['verdict'] = 'insufficient_evidence'
        output = contract.render(value, 'comment')
        self.assertIn('Required compatibility check remains incomplete', output)
        self.assertNotIn('Worker tool denied', output)
        self.assertIn('EVIDENCIA INSUFICIENTE', output)

    def test_product_session_text_survives(self):
        value = record8()
        value['coverage']['limitations'] = [limit('behavior', detail='User session expiry remains untested')]
        self.assertIn('User session expiry remains untested', contract.render(value, 'comment'))

    def test_material_abcde_gap_survives_without_duplicates(self):
        value = record8()
        text = 'Consumer compatibility remains incomplete'
        value['coverage']['limitations'] = [limit('validation', True, detail=text)]
        value['coverage']['areas'][2].update(status='partial', material=True, details=text)
        value['verdict'] = 'insufficient_evidence'
        output = contract.render(value, 'comment')
        self.assertEqual(output.count(text), 1)
        value['reservations'] = [text]
        self.assertEqual(contract.render(value, 'comment').count(text), 1)

    def test_legacy_publication_needs_bound_classification(self):
        value = record7()
        value['coverage']['limitations'] = [dict(detail='Harness mechanics', material=False)]
        before = copy.deepcopy(value)
        with self.assertRaises(ValueError):
            contract.render(value, 'comment')
        context = classification(value, 'execution')
        self.assertNotIn('Harness mechanics', contract.render(value, 'comment', publication_context=context))
        for mutation in [dict(source_sha256='0' * 64), dict(limitations=[]),
                         dict(limitations=context['limitations'] * 2)]:
            bad = copy.deepcopy(context)
            bad.update(mutation)
            with self.assertRaises(ValueError):
                contract.render(value, 'comment', publication_context=bad)
        self.assertEqual(value, before)

    def test_public_reservations_deduplicate_original_detail_without_hiding_other_conditions(self):
        for legacy in (False, True):
            with self.subTest(legacy=legacy):
                value = record7() if legacy else record8()
                detail = 'The optional consumer scenario remains unverified'
                summary = 'Optional consumer compatibility remains pending'
                condition = 'Deployment requires a coordinated restart'
                value['coverage']['limitations'] = ([dict(detail=detail, material=False)] if legacy else
                                                    [limit('validation', False, summary, detail)])
                value['reservations'] = [detail, summary, condition]
                value['verdict'] = 'approvable_with_reservations'
                context = classification(value, 'validation', summary) if legacy else None
                before = copy.deepcopy(value)
                self.assertEqual(contract.validate(value), [])
                for renderer in (contract.render, contract.render_handoff):
                    output = renderer(value, audience='comment', publication_context=context)
                    self.assertNotIn(detail, output)
                    self.assertEqual(output.count(summary), 1)
                    self.assertEqual(output.count(condition), 1)
                    self.assertIn(detail, renderer(value))
                self.assertEqual(value, before)

    def test_classified_summary_covers_duplicate_material_area_in_both_public_formats(self):
        for legacy in (False, True):
            with self.subTest(legacy=legacy):
                value = record7() if legacy else record8()
                detail = 'Native worker denied by harness'
                summary = 'Required consumer compatibility verification remains incomplete'
                value['coverage']['limitations'] = ([dict(detail=detail, material=True)] if legacy else
                                                    [limit('execution', True, summary, detail)])
                value['coverage']['areas'][2].update(status='partial', material=True, details=detail)
                value['verdict'] = 'insufficient_evidence'
                context = classification(value, 'execution', summary) if legacy else None
                before = copy.deepcopy(value)
                for renderer in (contract.render, contract.render_handoff):
                    output = renderer(value, audience='comment', publication_context=context)
                    self.assertNotIn(detail, output)
                    self.assertEqual(output.count(summary), 1)
                self.assertEqual(value, before)

    def test_material_area_cannot_disappear_behind_nonmaterial_execution_classification(self):
        value = record8()
        detail = 'Native worker unavailable'
        value['coverage']['limitations'] = [limit(detail=detail)]
        value['coverage']['areas'][2].update(status='partial', material=True, details=detail)
        value['verdict'] = 'insufficient_evidence'
        for renderer in (contract.render, contract.render_handoff):
            with self.assertRaises(ValueError):
                renderer(value, audience='comment')

    def test_public_handoff_uses_same_policy(self):
        value = record8()
        value['coverage']['limitations'] = [limit(detail='Worker tool denied by local harness')]
        self.assertNotIn('Worker tool denied', contract.render_handoff(value, audience='comment'))
        self.assertIn('Worker tool denied', contract.render_handoff(value))
        value = record7()
        value['coverage']['limitations'] = [dict(detail='Unclassified', material=False)]
        with self.assertRaises(ValueError):
            contract.render_handoff(value, audience='comment')

    def test_cli_classification_is_explicit_and_bound(self):
        value = record7()
        value['coverage']['limitations'] = [dict(detail='Harness mechanics', material=False)]
        with tempfile.TemporaryDirectory(prefix='ccr-publication-') as directory:
            record = Path(directory) / 'review.json'
            context = Path(directory) / 'classification.json'
            record.write_text(json.dumps(value), encoding='utf-8')
            context.write_text(json.dumps(classification(value, 'execution')), encoding='utf-8')
            command = [sys.executable, '-B', '-X', 'utf8', str(MODULE_PATH), 'contract']
            args = ['--input', str(record), '--publication-context', str(context)]
            result = subprocess.run(command + ['render-comment'] + args, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn('Harness mechanics', result.stdout)
            result = subprocess.run(command + ['render-user'] + args, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            context.write_text(json.dumps(dict(classification(value), source_sha256='bad')), encoding='utf-8')
            result = subprocess.run(command + ['render-comment'] + args, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, '')

    def test_cli_check_context_is_separate_from_legacy_limitation_context(self):
        value = publication_record()
        check_context = check_classification(value)
        with tempfile.TemporaryDirectory(prefix='ccr-check-publication-') as directory:
            record = Path(directory) / 'review.json'
            context = Path(directory) / 'check-classification.json'
            record.write_text(json.dumps(value), encoding='utf-8')
            context.write_text(json.dumps(check_context), encoding='utf-8')
            command = [sys.executable, '-B', '-X', 'utf8', str(MODULE_PATH), 'contract']
            result = subprocess.run(command + ['render-comment', '--input', str(record),
                '--check-publication-context', str(context)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn('evidence/', result.stdout)
            result = subprocess.run(command + ['render-comment', '--input', str(record),
                '--publication-context', str(context)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, '')
            result = subprocess.run(command + ['render-user', '--input', str(record),
                '--check-publication-context', str(context)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, '')


if __name__ == '__main__':
    unittest.main()
