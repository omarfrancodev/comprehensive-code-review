"""Restart mutations stay behind a dedicated archive service."""
import unittest


class RestartBoundaryTests(unittest.TestCase):
    def test_restart_service_has_no_legacy_or_cli_dependencies(self):
        from script_test_support import module_dependencies
        deps = module_dependencies('ccr.archive.restart')
        self.assertFalse(any(name.startswith(('review_', 'ccr.cli.')) for name in deps))

    def test_restart_state_is_independent_of_reader_and_mutators(self):
        from script_test_support import module_dependencies
        deps = module_dependencies('ccr.archive.restart_state')
        self.assertFalse(deps & {'ccr.archive.reader', 'ccr.archive.restart', 'ccr.archive.lifecycle'})
        self.assertFalse(any(name.startswith('review_') for name in deps))


if __name__ == '__main__':
    unittest.main()
