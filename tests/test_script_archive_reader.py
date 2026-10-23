"""Boundary tests for read-only archive loading."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from script_test_support import enable_package_imports

enable_package_imports()


class ArchiveReaderBoundaryTests(unittest.TestCase):
    def test_foreign_archive_is_refused_without_writes(self):
        from ccr.archive.reader import load_run
        with TemporaryDirectory() as directory:
            run = Path(directory)
            before = sorted(run.rglob('*'))
            with self.assertRaisesRegex(ValueError, 'ownership manifest is missing'):
                load_run(run)
            self.assertEqual(sorted(run.rglob('*')), before)

    def test_reader_does_not_depend_on_mutators(self):
        from script_test_support import module_dependencies
        forbidden = {'ccr.archive.lifecycle', 'ccr.archive.restart',
                     'ccr.archive.resources', 'ccr.workflow.setup'}
        self.assertFalse(module_dependencies('ccr.archive.reader') & forbidden)


if __name__ == '__main__':
    unittest.main()
