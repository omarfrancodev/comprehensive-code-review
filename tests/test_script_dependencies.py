import unittest
from pathlib import Path

from script_test_support import enable_package_imports

enable_package_imports()
ROOT = Path(__file__).resolve().parents[1]


class ScriptDependencyTests(unittest.TestCase):
    def test_dependency_detector_finds_cycles_and_self_loops(self):
        from script_test_support import cyclic_components

        self.assertEqual(cyclic_components({'a': {'b'}, 'b': {'a'}}), [('a', 'b')])
        self.assertEqual(cyclic_components({'a': {'b'}, 'b': set()}), [])
        self.assertEqual(cyclic_components({'a': {'a'}}), [('a',)])

    def test_implementation_graph_has_no_cycles_or_legacy_nodes(self):
        from script_test_support import import_graph, cyclic_components

        graph = import_graph(ROOT / 'scripts')
        self.assertEqual(cyclic_components(graph), [])
        self.assertFalse(list((ROOT / 'scripts').glob('review_*.py')))
        self.assertFalse(any(dep.startswith('review_') for deps in graph.values() for dep in deps))
        forbidden = (
            'ccr.execution.', 'ccr.cli.', 'ccr.shared.json_io', 'ccr.shared.git',
            'ccr.shared.paths', 'ccr.archive.reader', 'ccr.archive.integrity',
            'ccr.archive.transactions', 'ccr.archive.resources', 'ccr.archive.restart_state',
            'ccr.archive.lifecycle', 'ccr.archive.retention', 'ccr.archive.restart',
            'ccr.archive.coordination', 'ccr.archive.checkpoints', 'ccr.archive.evidence',
            'ccr.archive.history', 'ccr.archive.inspection', 'ccr.archive.lookup',
            'ccr.workflow.setup',
        )
        for module, dependencies in graph.items():
            if module.startswith('ccr.contracts.'):
                self.assertFalse(any(
                    dep == blocked or dep.startswith(blocked + '.')
                    for dep in dependencies for blocked in forbidden
                ), module)

    def test_static_cli_registry_edges_are_in_the_graph(self):
        from ccr.cli.main import AREAS
        from script_test_support import import_graph

        graph = import_graph(ROOT / 'scripts')
        self.assertEqual(graph['ccr.cli.main'] & set(AREAS.values()), set(AREAS.values()))
