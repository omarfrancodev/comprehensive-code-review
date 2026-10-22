"""Standalone entrypoint and forwarding contracts for ccr CLI areas."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch

from script_test_support import enable_package_imports
enable_package_imports()
ROOT = Path(__file__).resolve().parents[1]


class ScriptCliTests(unittest.TestCase):
    def test_root_forwards_the_suffix_without_requoting(self):
        from types import SimpleNamespace
        from ccr.cli.main import main
        handler = Mock(return_value=7)
        suffix = ['--prompt-file', 'a b.txt', '--', 'literal value']
        with patch('ccr.cli.main.import_module', return_value=SimpleNamespace(main=handler)):
            self.assertEqual(main(['runner', *suffix]), 7)
        handler.assert_called_once_with(suffix, prog='ccr runner')

    def test_root_help_does_not_load_work_services(self):
        import io
        from ccr.cli.main import main
        with patch('ccr.cli.main.import_module', side_effect=AssertionError('unexpected service import')):
            with patch('sys.stdout', new=io.StringIO()):
                try:
                    code = main(['--help'])
                except SystemExit as result:
                    code = result.code
        self.assertEqual(code, 0)

    def test_installed_copy_works_from_foreign_cwd(self):
        from tempfile import TemporaryDirectory
        from ccr.cli.main import AREAS
        with TemporaryDirectory() as directory:
            installed = Path(directory) / 'skill with spaces'
            shutil.copytree(ROOT, installed, ignore=shutil.ignore_patterns(
                '.git', '.worktrees', '__pycache__'))
            env = {key: value for key, value in os.environ.items()
                   if key.upper() != 'PYTHONPATH'}
            original_files = {p.relative_to(installed) for p in installed.rglob('*') if p.is_file()}
            probe_code = (
                "import json, re, sys, os\n"
                "sys.path.insert(0, sys.argv[1])\n"
                "from ccr.shared.installation import skill_root\n"
                "from ccr.execution import harness\n"
                "import ccr.archive.reader as reader\n"
                "root = skill_root()\n"
                "catalog = harness.load_catalog()\n"
                "reader._git = lambda *args: ''\n"
                "os.environ['CCR_ARTIFACTS_DIR'] = str(root / 'archive')\n"
                "rejected = False\n"
                "try:\n"
                "    reader.select_output_root(root / 'repo')\n"
                "except ValueError:\n"
                "    rejected = True\n"
                "version = re.search(r'^  version: \"([^\"]+)\"$', "
                "(root / 'SKILL.md').read_text(encoding='utf-8'), re.M).group(1)\n"
                "print(json.dumps({'root': str(root), 'catalog': str(harness.CATALOG), "
                "'catalog_version': catalog['catalog_version'], 'skill_version': version, "
                "'rejected': rejected}))\n"
            )
            probe = subprocess.run(
                [sys.executable, '-B', '-c', probe_code, str(installed / 'scripts')],
                cwd=directory, env=env, capture_output=True, text=True)
            self.assertEqual(probe.returncode, 0, probe.stderr)
            installed_state = json.loads(probe.stdout)
            self.assertEqual(Path(installed_state['root']), installed)
            self.assertEqual(Path(installed_state['catalog']),
                             installed / 'references' / 'archive' / 'harness-catalog.json')
            self.assertEqual(installed_state['catalog_version'], 1)
            self.assertEqual(installed_state['skill_version'], '2.14.0')
            self.assertTrue(installed_state['rejected'])
            for area in AREAS:
                result = subprocess.run(
                    [sys.executable, '-B', str(installed / 'scripts'), area, '--help'],
                    cwd=directory, env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, (area, result.stderr))
                self.assertIn('ccr ' + area, result.stdout)
            for args, expected in [([], 2), (['unknown-area'], 2), (['--help'], 0)]:
                result = subprocess.run(
                    [sys.executable, '-B', str(installed / 'scripts'), *args],
                    cwd=directory, env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode, expected)
            self.assertEqual({p.relative_to(installed) for p in installed.rglob('*') if p.is_file()}, original_files)

    def test_checks_cli_reports_successful_capture_of_exit_seven(self):
        import json
        from tempfile import TemporaryDirectory
        from script_test_support import owned_check_request
        with TemporaryDirectory() as directory:
            request = owned_check_request(Path(directory), exit_code=7)
            output_dir = request.pop('output_dir')
            request_path = Path(directory) / 'request.json'
            request_path.write_text(json.dumps(request), encoding='utf-8')
            result = subprocess.run(
                [sys.executable, '-B', str(ROOT / 'scripts'), 'checks', 'run',
                 '--request', str(request_path), '--output-dir', output_dir],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['receipt']['exit_code'], 7)


if __name__ == '__main__':
    unittest.main()
