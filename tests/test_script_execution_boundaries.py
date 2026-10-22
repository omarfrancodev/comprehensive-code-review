"""Architectural boundaries for execution setup, checks and candidates."""
from pathlib import Path
import tempfile
import unittest

from script_test_support import enable_package_imports
enable_package_imports()


class ScriptExecutionBoundaryTests(unittest.TestCase):
    def test_execution_modules_do_not_import_cli_facades(self):
        from script_test_support import module_dependencies
        forbidden = {'review_artifacts', 'review_setup', 'review_check_receipts',
                     'review_workspace', 'review_metrics'}
        modules = ('ccr.workflow.builders', 'ccr.workflow.setup',
                   'ccr.execution.candidates', 'ccr.execution.checks',
                   'ccr.execution.runner')
        for name in modules:
            with self.subTest(module=name):
                self.assertFalse(module_dependencies(name) & forbidden)

    def test_candidate_never_overwrites_existing_output(self):
        from ccr.execution.candidates import write_new_json
        with tempfile.TemporaryDirectory() as directory:
            session = Path(directory)
            target = session / 'evidence' / 'candidate.json'
            self.assertEqual(write_new_json(session, str(target), {'x': 1}), target)
            original = target.read_bytes()
            self.assertEqual(original, b'{"x":1}\n')
            with self.assertRaises(FileExistsError):
                write_new_json(session, str(target), {'x': 2})
            self.assertEqual(target.read_bytes(), original)

    def test_capture_keeps_the_observed_nonzero_exit(self):
        from script_test_support import owned_check_request
        from ccr.execution.checks import capture_check
        with tempfile.TemporaryDirectory() as directory:
            request = owned_check_request(Path(directory), exit_code=7)
            receipt = capture_check(**request)
            self.assertEqual(receipt['exit_code'], 7)
            self.assertEqual(receipt['schema_version'], 1)
            self.assertIsNotNone(receipt['finished_at'])


if __name__ == '__main__':
    unittest.main()
