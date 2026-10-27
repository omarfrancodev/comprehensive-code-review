"""Existing contracts carry priority justification without a schema migration."""
import copy
from pathlib import Path
import unittest
from script_test_support import enable_package_imports

enable_package_imports()
from ccr.contracts import packets, review
from ccr.contracts.dimensions import DIMENSIONS
from ccr.reporting import render as renderer, comment, delivery
from test_review_packets import inputs
from test_review_contract import finding
from traceability_fixtures import record11, set_dimension, publication_contexts
from recovery_fixtures import record10

IMPACT = ('La alteración persistente impide el flujo principal de una entidad; '
          'corresponde P1 por requerir reconciliar sus datos, sin cadena catastrófica demostrada.')


def current_record():
    value = record11()
    value['findings'] = [dict(finding(), id='F001', priority='P1', origin='preexisting', impact=IMPACT)]
    value.update(verdict='approvable_with_reservations',
                 verdict_reason='El alcance permite integrar con la reserva explícita.',
                 reservations=['Corregir la alteración preexistente en su flujo afectado.'])
    set_dimension(value, 'B01', finding_ids=['F001'])
    return value


class PriorityRoundtripTests(unittest.TestCase):
    def test_packet1_merge11_preserves_judgment_delta(self):
        context, discovery, verification = inputs()
        value = record11()
        context.update(scope=value['scope'], checks=value['checks'], check_schema_version=11)
        discovery['check_ids'] = ['C001']
        verification['decisions'][0]['updates'] = dict(priority='P1', impact=IMPACT)
        original = copy.deepcopy((context, discovery, verification))
        result = packets.merge(context, [discovery], verification)
        self.assertEqual(result['findings'][0]['priority'], 'P1')
        self.assertEqual(result['findings'][0]['impact'], IMPACT)
        self.assertEqual(result['checks'][0]['purpose'], value['checks'][0]['purpose'])
        self.assertNotIn('priority', discovery['findings'][0])
        self.assertNotIn('schema_version', result)
        self.assertEqual((context, discovery, verification), original)

    def test_render11_preserves_impact_and_traceability(self):
        value = current_record()
        original = copy.deepcopy(value)
        self.assertEqual(review.validate(value), [])
        text = renderer.render(value)
        self.assertEqual(text.count('- **Impacto:** ' + IMPACT), 1)
        self.assertIn('  - **Propósito:**', text)
        self.assertIn('  - **Resultado:**', text)
        self.assertNotEqual(value['checks'][0]['purpose'], IMPACT)
        for ids in DIMENSIONS.values():
            for identifier in ids:
                self.assertIn(f'| {identifier} |', text)
        self.assertEqual(value, original)

    def test_priority_origin_and_blocking_remain_independent(self):
        for priority in ('P1', 'P2'):
            for origin in ('introduced', 'preexisting'):
                with self.subTest(priority=priority, origin=origin):
                    value = current_record()
                    value['findings'][0].update(priority=priority, origin=origin)
                    self.assertEqual(review.validate(value), [])
                    value['findings'][0].update(blocking=True, blocking_reason='El contrato requerido del alcance falla.')
                    self.assertTrue(any('verdict' in error for error in review.validate(value)))
                    value['verdict'] = 'not_approvable'
                    self.assertEqual(review.validate(value), [])

    def test_unresolved_does_not_enter_confirmed_counts(self):
        value = current_record()
        value['findings'][0].update(status='unresolved', priority='P1', impact='El guard previo no está disponible.')
        value['coverage']['limitations'] = [dict(kind='behavior', detail='No se conoce si el guard permite la acción.',
            material=True, public_summary='Falta confirmar la autorización previa.')]
        value['verdict'] = 'insufficient_evidence'
        original = copy.deepcopy(value)
        self.assertEqual(review.validate(value), [])
        text = renderer.render(value)
        self.assertIn('🔴 P0: 0 · 🟠 P1: 0 · 🟡 P2: 0 · 🔵 P3: 0', text)
        self.assertEqual(value['findings'][0]['status'], 'unresolved')
        self.assertEqual(value, original)

    def test_final10_without_new_justification_stays_readable(self):
        legacy = record10()
        legacy['findings'] = [dict(finding(), id='F001', impact='El consumidor no puede navegar al objeto.')]
        legacy.update(verdict='approvable_with_reservations', reservations=['Resolver la navegación.'])
        original = copy.deepcopy(legacy)
        self.assertEqual(review.validate(legacy), [])
        self.assertIn('El consumidor no puede navegar al objeto.', renderer.render(legacy))
        self.assertEqual(legacy, original)
        for mutation in ('extra', 'purpose', 'dimension'):
            value = current_record()
            if mutation == 'extra':
                value['findings'][0]['priority_reason'] = 'Not a field in final 11'
            elif mutation == 'purpose':
                del value['checks'][0]['purpose']
            else:
                value['coverage']['areas'][0]['dimensions'].pop()
            with self.subTest(mutation=mutation):
                self.assertTrue(review.validate(value))

    def test_public_draft_and_portable_outputs_preserve_impact(self):
        value = current_record()
        original = copy.deepcopy(value)
        draft = comment.prepare_public_comment(value, **publication_contexts(value))
        self.assertEqual(draft['schema_version'], 2)
        self.assertTrue(comment.verify_public_comment(value, draft, draft['body'])['verified'])
        self.assertIn(IMPACT, draft['body'])
        self.assertNotIn('### Matriz ABCDE', draft['body'])
        self.assertNotIn('### Dimensiones de cobertura', draft['body'])
        projection = delivery._Projection(value, {'repository_path': 'C:/repo', 'archive_root': 'C:/archive'},
                                          Path('C:/repo'), 'a' * 64)
        portable = projection.value(value)
        self.assertEqual(portable['findings'][0]['priority'], 'P1')
        self.assertEqual(portable['findings'][0]['impact'], IMPACT)
        self.assertEqual(sum(len(a['dimensions']) for a in portable['coverage']['areas']), 27)
        self.assertEqual(portable['checks'][0]['purpose'], value['checks'][0]['purpose'])
        self.assertIn(IMPACT, delivery._brief(portable))
        self.assertEqual(value, original)
