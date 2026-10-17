"""Coordination must never write to a linked final lock target."""
from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch

import test_review_run_lock as locks_fixture
import review_run_lock as locks


class LockFileSafetyTests(unittest.TestCase):
    def fixture(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name).resolve()
        run = root / 'run'
        run.mkdir()
        target = root / 'foreign-empty.bin'
        target.write_bytes(b'')
        return run, target

    def symlink(self, target, link):
        try:
            link.symlink_to(target)
        except OSError as exc:
            self.skipTest('file symlink privilege unavailable: ' + str(exc))

    def test_existing_final_symlink_is_refused_without_touching_target(self):
        run, target = self.fixture()
        _, lock_path = locks._lock_identity(run)
        self.symlink(target, lock_path)
        with self.assertRaises(ValueError):
            with locks.run_locks([run]):
                self.fail('unsafe lock acquired')
        self.assertEqual(target.read_bytes(), b'')

    def test_final_link_replacement_after_identity_check_is_refused(self):
        run, target = self.fixture()
        original = locks._lock_identity
        def replaced(path):
            identity, lock_path = original(path)
            self.symlink(target, lock_path)
            return identity, lock_path
        with patch.object(locks, '_lock_identity', side_effect=replaced):
            with self.assertRaises(ValueError):
                with locks.run_locks([run]):
                    self.fail('replaced lock acquired')
        self.assertEqual(target.read_bytes(), b'')

    def test_final_hardlink_is_refused_before_writing_foreign_bytes(self):
        run, target = self.fixture()
        _, lock_path = locks._lock_identity(run)
        os.link(target, lock_path)
        with self.assertRaises(ValueError):
            with locks.run_locks([run]):
                self.fail('foreign inode acquired')
        self.assertEqual(target.read_bytes(), b'')

    def test_hardlink_inserted_after_precheck_is_refused_by_opened_identity(self):
        run, target = self.fixture()
        _, lock_path = locks._lock_identity(run)
        if os.name == 'nt':
            original = locks._windows_lock_fd
            def replaced(path):
                os.link(target, path)
                return original(path)
            context = patch.object(locks, '_windows_lock_fd', side_effect=replaced)
        else:
            original = os.open
            def replaced(path, *args, **kwargs):
                if Path(path) == lock_path:
                    os.link(target, path)
                return original(path, *args, **kwargs)
            context = patch.object(os, 'open', side_effect=replaced)
        with context, self.assertRaises(ValueError):
            with locks.run_locks([run]):
                self.fail('changed foreign inode acquired')
        self.assertEqual(target.read_bytes(), b'')
