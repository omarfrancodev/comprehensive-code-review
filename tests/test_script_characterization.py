import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from script_test_support import enable_package_imports

enable_package_imports()
ROOT = Path(__file__).resolve().parents[1]


class ScriptCharacterizationTests(unittest.TestCase):
    def test_cli_inventory_matches_the_locked_base(self):
        from script_test_support import cli_inventory

        expected = json.loads(
            (ROOT / 'tests/fixtures/scripts_cli_contracts.json').read_text(encoding='utf-8')
        )
        self.assertEqual(cli_inventory(), expected)
        self.assertEqual(
            set(expected),
            {
                'artifacts', 'contract', 'delivery', 'history', 'metrics', 'packets',
                'recovery', 'runner', 'workspace', 'setup', 'checks', 'comment',
            },
        )

    def test_encoding_inventory_matches_original_bytes(self):
        from script_test_support import encoding_inventory

        expected = json.loads(
            (ROOT / 'tests/fixtures/scripts_encoding_contracts.json').read_text(encoding='utf-8')
        )
        self.assertEqual(encoding_inventory(), expected['expected_bytes_hex'])

    def test_run_cli_executes_the_selected_legacy_command(self):
        from script_test_support import run_cli

        with TemporaryDirectory() as directory:
            result = run_cli('metrics', ['--help'], cwd=Path(directory))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('usage:', result.stdout.lower())

    def test_module_dependencies_resolves_local_imports_from_ast(self):
        from script_test_support import module_dependencies

        dependencies = module_dependencies('review_artifacts')
        self.assertIn('review_contract', dependencies)
        self.assertIn('review_run_lock', dependencies)
