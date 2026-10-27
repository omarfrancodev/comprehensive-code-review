"""Contract tests for the extracted script infrastructure."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
ROOT = Path(__file__).resolve().parents[1]


class ScriptSharedTests(unittest.TestCase):
    def test_encodings_preserve_distinct_bytes(self):
        from ccr.shared.encoding import archive_bytes, compact_bytes, receipt_bytes
        self.assertEqual(archive_bytes({'x': 1}), b'{\n  "x": 1\n}\n')
        self.assertEqual(compact_bytes({'x': 1}), b'{"x":1}')
        self.assertEqual(receipt_bytes({'x': 1}), b'{"x":1}\n')

    def test_installation_root_ignores_cwd(self):
        import os
        from tempfile import TemporaryDirectory
        from ccr.shared.installation import skill_root
        previous = Path.cwd()
        with TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                self.assertEqual(skill_root(), ROOT)
            finally:
                os.chdir(previous)