"""Boundary tests for archive transaction recovery."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from script_test_support import enable_package_imports

enable_package_imports()


class ArchiveTransactionBoundaryTests(unittest.TestCase):
    def test_trace_without_pending_returns_marker_without_writes(self):
        from ccr.archive.transactions import recover_trace
        marker = {'owner_id': 'test-owner'}
        with TemporaryDirectory() as directory:
            with patch('ccr.archive.transactions.save_manifest',
                       side_effect=AssertionError('unexpected commit')):
                self.assertIs(recover_trace(Path(directory), {}, marker), marker)
            self.assertEqual(list(Path(directory).iterdir()), [])


if __name__ == '__main__':
    unittest.main()
