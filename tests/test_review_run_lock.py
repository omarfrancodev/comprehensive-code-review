"""Cross-process exclusive mutation locks with reentrancy and stable ordering."""
from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from ccr.execution.locks import run_locks


class ReviewRunLockTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[1]

    def test_mutating_lock_conflicts_between_processes(self):
        with self.subTest(lock='held by another process'):
            from tempfile import TemporaryDirectory
            with TemporaryDirectory() as directory:
                run = Path(directory) / 'run'
                run.mkdir()
                code = ("import sys;sys.path.insert(0," + repr(str(self.root / 'scripts')) + ");"
                        "from pathlib import Path;from ccr.execution.locks import run_locks;"
                        "run=Path(" + repr(str(run)) + ");"
                        "\ntry:\n with run_locks([run]): print('acquired')\n"
                        "except ValueError as exc:\n print('conflict' if 'conflict' in str(exc) else str(exc))")
                with run_locks([run]):
                    result = subprocess.run([sys.executable, '-B', '-X', 'utf8', '-c', code],
                                            capture_output=True, text=True, encoding='utf-8')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), 'conflict')

    def test_lock_releases_after_exception_and_allows_same_context_reentry(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory:
            run = Path(directory) / 'run'
            run.mkdir()
            with self.assertRaisesRegex(RuntimeError, 'injected'):
                with run_locks([run]):
                    with run_locks([run]):
                        raise RuntimeError('injected')
            with run_locks([run]):
                pass

    def test_multi_run_locks_use_stable_order_and_unique_paths(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory:
            first, second = Path(directory) / 'a', Path(directory) / 'b'
            first.mkdir()
            second.mkdir()
            with run_locks([second, first, second]):
                with run_locks([first, second]):
                    pass
            with run_locks([first, second]):
                pass


if __name__ == '__main__':
    unittest.main()
