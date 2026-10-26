"""Readable evidence and coverage, without changing review semantics."""
import copy
import unittest

from script_test_support import enable_package_imports
enable_package_imports()

from ccr.reporting import blocks, render as renderer
from ccr.contracts.dimensions import DIMENSIONS
from traceability_fixtures import record11


class RenderingTests(unittest.TestCase):
    def test_same_origin_keeps_delta_static_and_distinct_check(self):
        ledger = {'C001': {'evidence': 'Resultado observado'}, 'C002': {'evidence': 'Otro resultado'}}
        evidence = [dict(kind='executed', check_id='C001', details='Resultado observado'),
            dict(kind='executed', check_id='C001', details='Delta del caso'),
            dict(kind='executed', check_id='C001', details='Delta del caso'),
            dict(kind='static', check_id=None, details='src/jobs.py:claim'),
            dict(kind='static', check_id=None, details='Otra observación'),
            dict(kind='static', check_id=None, details='src/jobs.py:claim'),
            dict(kind='executed', check_id='C002', details='Resultado observado')]
        groups = blocks.evidence_groups(evidence, ledger)
        self.assertEqual(groups[0], {'check_id': 'C001', 'details': ['Delta del caso']})
        self.assertEqual(groups[1], {'check_id': None, 'details': ['src/jobs.py:claim']})
        self.assertEqual(groups[2], {'check_id': None, 'details': ['Otra observación']})
        self.assertEqual(groups[3]['check_id'], 'C002')
        lines = '\n'.join(blocks.evidence_lines(groups))
        self.assertEqual(lines.count('**[C001](#C001)**'), 1)
        self.assertIn('**Inspección estática**', lines)
        empty = blocks.evidence_groups(evidence[:1], ledger)
        self.assertEqual(empty[0]['details'], [])
        self.assertIn('Resultado en Validación', '\n'.join(blocks.evidence_lines(empty)))

    def test_coverage_preserves_order_duplicates_and_escapes(self):
        lines = blocks.coverage_lines(['Flujo A', 'Flujo A', '<script>'])
        self.assertEqual(lines.count('  - Flujo A'), 2)
        self.assertNotIn('<script>', '\n'.join(lines))
        self.assertIn('Sin flujos de cobertura registrados', '\n'.join(blocks.coverage_lines([])))

    def test_legacy_identifier_cannot_inject_a_link(self):
        text = '\n'.join(blocks.evidence_lines([{'check_id': 'x](javascript:alert(1))', 'details': ['<script>']}]))
        self.assertNotIn('](javascript:', text)
        self.assertIn('#x%5D%28javascript%3Aalert%281%29%29', text)
        self.assertNotIn('<script>', text)

    def test_full_report_preserves_input_and_exposes_objective(self):
        value = record11()
        before = copy.deepcopy(value)
        text = renderer.render(value)
        self.assertIn('  - **Propósito:**', text)
        self.assertIn('  - **Resultado:**', text)
        self.assertIn('- **Cobertura:**\n', text)
        for ids in DIMENSIONS.values():
            for identifier in ids:
                self.assertIn(f'| {identifier} |', text)
        self.assertEqual(value, before)
