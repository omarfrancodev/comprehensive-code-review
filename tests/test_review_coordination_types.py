"""Issue 22: callers classify coordination by type, never by message."""
from contextlib import contextmanager
from pathlib import Path
import argparse
import json
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import sys

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))

from ccr.archive import coordination as archive_coordination
from ccr.archive import resources as archive_resources
from ccr.execution import claims, locks, workspaces as workspace_ops
from script_test_support import archive_api
artifacts = archive_api()
from script_test_support import workspace_api
workspace = workspace_api()


class CoordinationTypeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def test_unsafe_lock_inputs_are_coordination_errors(self):
        file = self.root / 'not-a-directory'
        file.write_bytes(b'unchanged')
        cases = [(Path('relative'), None), (self.root / 'missing', None),
                 (file, None), (self.root, Path('relative')),
                 (self.root, self.root / '..' / 'locks'), (self.root, file)]
        for run, root in cases:
            with self.subTest(run=run, root=root), self.assertRaises(locks.CoordinationError):
                locks._lock_identity(run, coordination_root=root)
        self.assertEqual(file.read_bytes(), b'unchanged')

    def test_lock_root_creation_keeps_the_os_cause(self):
        error = PermissionError('cannot create coordination root')
        with patch.object(Path, 'mkdir', side_effect=error):
            with self.assertRaises(locks.CoordinationError) as caught:
                locks._lock_identity(self.root)
        self.assertIs(caught.exception.__cause__, error)

    def test_nonregular_final_lock_is_typed_and_unchanged(self):
        lock = self.root / 'lock'
        lock.mkdir()
        with self.assertRaises(locks.CoordinationError):
            locks._open_lock_file(lock)
        self.assertTrue(lock.is_dir())

    def test_reparse_roots_are_coordination_errors(self):
        original = Path.lstat
        def reparse(path, *args, **kwargs):
            if path == self.root:
                return SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x400)
            return original(path, *args, **kwargs)
        with patch.object(Path, 'lstat', reparse):
            with self.assertRaises(locks.CoordinationError):
                locks._lock_identity(self.root)

    def test_archive_cleanup_preserves_noncontention_context(self):
        (self.root / claims.CLAIM_NAME).write_text(json.dumps({'status': 'owned'}), encoding='utf-8')
        failure = locks.CoordinationError('archive lock identity changed')
        @contextmanager
        def lock(*args):
            raise failure
            yield
        args = argparse.Namespace(manifest='manifest', run_dir=str(self.root / 'run'))
        with patch.object(workspace_ops, 'load', return_value={'session_dir': str(self.root)}), \
                patch.object(archive_resources, 'owned_run_locks', side_effect=lock):
            with self.assertRaises(workspace.ReviewError) as caught:
                workspace.cleanup(args)
        self.assertIn('Review archive cleanup failed; preserve the session', str(caught.exception))
        self.assertIs(caught.exception.__cause__, failure)

    def test_session_identity_is_rechecked_inside_lock_and_typed(self):
        identity = (self.root, {'session_id': 'original', 'repo': str(self.root)}, 'token')
        changed = (self.root, {'session_id': 'changed', 'repo': str(self.root)}, 'token')
        held = []
        @contextmanager
        def lock(*args, **kwargs):
            held.append(True)
            try:
                yield
            finally:
                held.pop()
        def read(path):
            return changed if held else identity
        with patch.object(claims, '_workspace', side_effect=read), \
                patch.object(claims, '_git', return_value='.git'), \
                patch.object(locks, 'run_locks', side_effect=lock):
            with self.assertRaises(locks.CoordinationError):
                with claims.session_claim_locks([self.root]):
                    self.fail('changed session identity must never enter the body')

    def test_restart_retries_typed_contention_with_an_unrelated_message(self):
        attempts = []
        @contextmanager
        def lock(*args):
            attempts.append(True)
            if len(attempts) == 1:
                raise locks.LockConflictError('occupied by another process')
            yield
        with patch.object(archive_coordination, '_load_run', return_value=(self.root, {}, {})), \
                patch.object(archive_coordination, 'run_locks', side_effect=lock), patch('time.sleep'):
            with artifacts._restart_lock(self.root):
                pass
        self.assertEqual(len(attempts), 2)

    def test_restart_never_retries_plain_value_error_that_mentions_contention(self):
        failure = ValueError('not a mutation lock conflict: invalid data')
        @contextmanager
        def lock(*args):
            raise failure
            yield
        with patch.object(archive_coordination, '_load_run', return_value=(self.root, {}, {})), \
                patch.object(archive_coordination, 'run_locks', side_effect=lock), patch('time.sleep') as sleep, \
                patch('time.monotonic', side_effect=[0, 0, 1]):
            with self.assertRaises(ValueError) as caught:
                with artifacts._restart_lock(self.root, timeout=0.01):
                    self.fail('invalid lock request must not enter the body')
        self.assertIs(caught.exception, failure)
        sleep.assert_not_called()

    def test_operation_wrappers_preserve_coordination_context(self):
        import argparse
        args = argparse.Namespace(manifest='manifest', path='artifact', run_dir='run')
        for function, label in [(workspace.record_artifact, 'Artifact registration'),
                                (workspace.cleanup, 'Workspace cleanup')]:
            failure = locks.CoordinationError('identity changed')
            @contextmanager
            def lock(*args):
                raise failure
                yield
            with self.subTest(function=function.__name__), \
                    patch.object(workspace_ops, 'load', return_value={'session_dir': str(self.root)}), \
                    patch.object(claims, 'session_claim_locks', side_effect=lock):
                with self.assertRaises(workspace.ReviewError) as caught:
                    function(args)
                self.assertIn(label + ' failed; preserve the session', str(caught.exception))
                self.assertNotIn('retry', str(caught.exception))
                self.assertIs(caught.exception.__cause__, failure)
