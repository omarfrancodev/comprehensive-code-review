"""Dependency boundaries for verified read-only archive flows."""
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))


class ScriptReadOnlyFlowTests(unittest.TestCase):
    def test_initial_profile_selection_is_owned_by_builders(self):
        from recovery_fixtures import selection_input
        from ccr.workflow.builders import initial_selection
        selected = initial_selection(selection_input())
        self.assertEqual(selected['id'], 'S001')
        self.assertEqual(selected['phase'], 'prepare')

    def test_history_inventory_stays_exactly_three_files(self):
        from ccr.archive.history import HISTORY_FILES
        self.assertEqual(set(HISTORY_FILES), {'informe.md', 'consulta.json', '.ccr-history.json'})

    def test_lookup_and_inspection_do_not_import_mutators(self):
        from script_test_support import module_dependencies
        forbidden = {'ccr.archive.restart', 'ccr.archive.lifecycle', 'ccr.archive.resources'}
        for name in ('ccr.archive.inspection', 'ccr.archive.lookup', 'ccr.archive.restart_observations'):
            with self.subTest(module=name):
                self.assertFalse(module_dependencies(name) & forbidden)


if __name__ == '__main__':
    unittest.main()
