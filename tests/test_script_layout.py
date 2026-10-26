import unittest
from pathlib import Path

from script_test_support import enable_package_imports

enable_package_imports()
ROOT = Path(__file__).resolve().parents[1]


class ScriptLayoutTests(unittest.TestCase):
    def test_cli_registry_has_the_twelve_supported_areas(self):
        from ccr.cli.main import AREAS

        self.assertEqual(set(AREAS), {
            'artifacts', 'contract', 'delivery', 'history', 'metrics', 'packets',
            'recovery', 'runner', 'workspace', 'setup', 'checks', 'comment',
        })

    def test_every_implementation_module_is_registered_in_the_index(self):
        index = (ROOT / 'scripts/README.md').read_text(encoding='utf-8')
        for module in (ROOT / 'scripts/ccr').rglob('*.py'):
            if module.name != '__init__.py':
                with self.subTest(module=module):
                    self.assertIn(module.relative_to(ROOT).as_posix(), index)

    def test_legacy_script_entrypoints_are_gone(self):
        self.assertEqual(list((ROOT / 'scripts').glob('review_*.py')), [])
