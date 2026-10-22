"""Only lock contention gets contention guidance; other causes stay actionable."""
import argparse
import errno
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import test_review_session_operations as operations
from ccr.execution import claims as claim_ops
from ccr.execution import locks
from ccr.execution import workspaces as workspace_ops

workspace = operations.workspace
claims = operations.claims


class CoordinationErrorTests(unittest.TestCase):
    setUp = operations.SessionOperationTests.setUp
    git = operations.SessionOperationTests.git
    write = operations.SessionOperationTests.write
    read = operations.SessionOperationTests.read
    snapshot = operations.SessionOperationTests.snapshot
    workspace_session = operations.SessionOperationTests.workspace_session
    fixture = operations.SessionOperationTests.fixture

    def commands(self, session, path):
        args = argparse.Namespace(manifest=str(session / 'manifest.json'), path=str(path), run_dir=None)
        return [(workspace.record_artifact, args), (workspace.cleanup, args)]

    def test_git_coordination_errors_keep_operation_context_without_lock_advice(self):
        session = self.workspace_session()
        path = self.fixture(session, 'reproduction.py')
        before = self.snapshot(session)
        original_out = claim_ops._git

        def git_failure(repo, *args):
            if args == ('rev-parse', '--git-common-dir'):
                raise ValueError('Git rev-parse failed (128): unreadable Git directory')
            return original_out(repo, *args)

        for command, args in self.commands(session, path):
            with self.subTest(command=command.__name__), patch.object(claim_ops, '_git', side_effect=git_failure):
                with self.assertRaises(Exception) as caught:
                    command(args)
                self.assertIsInstance(caught.exception, workspace.ReviewError)
                self.assertIsInstance(caught.exception.__cause__, locks.CoordinationError)
                self.assertIn('session coordination directory', str(caught.exception))
                self.assertIn('unreadable Git directory', str(caught.exception))
                self.assertIn('preserve the session', str(caught.exception))
                self.assertNotIn('and retry', str(caught.exception))
        self.assertEqual(self.snapshot(session), before)

    def test_lock_open_permissions_keep_the_os_cause_without_contention_advice(self):
        session = self.workspace_session()
        path = self.fixture(session, 'reproduction.py')
        before = self.snapshot(session)
        target = '_windows_lock_fd' if os.name == 'nt' else 'os.open'
        for command, args in self.commands(session, path):
            with self.subTest(command=command.__name__), patch('ccr.execution.locks.' + target,
                    side_effect=PermissionError(errno.EACCES, 'coordination access denied')):
                with self.assertRaises(Exception) as caught:
                    command(args)
                self.assertIn('coordination access denied', str(caught.exception))
                self.assertIn('preserve the session', str(caught.exception))
                self.assertIsInstance(caught.exception.__cause__.__cause__, PermissionError)
                self.assertNotIn('and retry', str(caught.exception))
        self.assertEqual(self.snapshot(session), before)

    def test_unsafe_final_lock_is_not_reported_as_contention(self):
        session = self.workspace_session()
        path = self.fixture(session, 'reproduction.py')
        root = self.repo / '.git' / 'ccr-session-locks'
        _, lock_path = locks._lock_identity(session, coordination_root=root)
        foreign = self.root / 'foreign-lock.bin'
        foreign.write_bytes(b'')
        try:
            os.link(foreign, lock_path)
        except OSError as exc:
            self.skipTest(f"Host does not permit hardlinks: {exc}")
        before = self.snapshot(session)
        for command, args in self.commands(session, path):
            with self.subTest(command=command.__name__), self.assertRaises(Exception) as caught:
                command(args)
            self.assertIn('regular, unlinked and singly owned', str(caught.exception))
            self.assertIn('preserve the session', str(caught.exception))
            self.assertIsInstance(caught.exception.__cause__, locks.CoordinationError)
            self.assertNotIn('and retry', str(caught.exception))
        self.assertEqual(foreign.read_bytes(), b'')
        self.assertEqual(self.snapshot(session), before)

    def test_non_contention_os_lock_failure_keeps_its_cause_and_releases_the_handle(self):
        run = self.root / 'coordination-run'
        run.mkdir()
        failure = OSError(errno.EIO, 'coordination device failure')
        primitive = 'msvcrt.locking' if os.name == 'nt' else 'fcntl.flock'
        with patch(primitive, side_effect=failure):
            with self.assertRaises(OSError) as caught:
                with locks.run_locks([run]):
                    self.fail('failed OS lock must not be acquired')
        self.assertIs(caught.exception, failure)
        with locks.run_locks([run]):
            pass

    def test_body_decode_and_io_errors_are_not_reclassified(self):
        session = self.workspace_session()
        path = self.fixture(session, 'reproduction.py')
        before = self.snapshot(session)
        errors = [json.JSONDecodeError('invalid manifest JSON', '{', 1),
                  UnicodeDecodeError('utf-8', b'\xff', 0, 1, 'invalid manifest encoding'),
                  OSError(errno.ENOSPC, 'manifest save has no space')]
        for command, args in self.commands(session, path):
            helper = 'record_artifact' if command is workspace.record_artifact else 'plan_cleanup'
            for error in errors:
                with self.subTest(command=command.__name__, error=type(error).__name__), \
                        patch.object(workspace_ops, helper, side_effect=error):
                    with self.assertRaises(Exception) as caught:
                        command(args)
                    self.assertIs(caught.exception, error)
        self.assertEqual(self.snapshot(session), before)

    def test_cli_git_coordination_error_is_json_without_a_traceback(self):
        session = self.workspace_session()
        path = self.fixture(session, 'reproduction.py')
        code = r'''
import runpy, sys
from unittest.mock import patch
sys.path.insert(0, sys.argv[1])
from script_test_support import workspace_api
workspace = workspace_api()
import ccr.execution.claims as claim_ops
script, manifest, artifact = sys.argv[2:5]
original = claim_ops._git
def failed(repo, *args):
    if args == ('rev-parse', '--git-common-dir'):
        raise ValueError('Git rev-parse failed (128): unreadable Git directory')
    return original(repo, *args)
sys.argv = [script, 'workspace', 'record-artifact', '--manifest', manifest, '--path', artifact]
with patch.object(claim_ops, '_git', side_effect=failed):
    runpy.run_path(script, run_name='__main__')
'''
        scripts = Path(workspace.__file__).parent
        script = scripts / '__main__.py'
        result = subprocess.run([sys.executable, '-B', '-X', 'utf8', '-c', code, str(scripts),
            str(script), str(session / 'manifest.json'), str(path)],
            capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 1)
        self.assertTrue(result.stderr.startswith('{'), result.stderr)
        error = json.loads(result.stderr)['error']
        self.assertIn('session coordination directory', error)
        self.assertIn('unreadable Git directory', error)
        self.assertIn('preserve the session', error)
        self.assertNotIn('and retry', error)
