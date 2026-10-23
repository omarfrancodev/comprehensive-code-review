"""Portable Git coordination and exclusive workspace artifact registration."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

import test_review_authority_and_claim_safety as safety
from ccr.execution import claims as claim_ops, workspaces as workspace_ops

workspace = safety.resources.review_workspace
claims = safety.claims
artifacts = safety.artifacts


class SessionOperationTests(unittest.TestCase):
    setUp = safety.SessionClaimSafetyTests.setUp
    git = safety.SessionClaimSafetyTests.git
    write = safety.SessionClaimSafetyTests.write
    read = safety.SessionClaimSafetyTests.read
    snapshot = safety.SessionClaimSafetyTests.snapshot
    profile_input = safety.SessionClaimSafetyTests.profile_input
    workspace_session = safety.SessionClaimSafetyTests.workspace_session
    create_run = safety.SessionClaimSafetyTests.create_run
    context = safety.SessionClaimSafetyTests.context
    register = safety.SessionClaimSafetyTests.register
    controller = safety.SessionClaimSafetyTests.controller
    held_session = safety.SessionClaimSafetyTests.held_session

    def test_claim_lifecycle_works_without_git_path_format_option(self):
        real_git = claim_ops._git
        for absolute in (False, True):
            with self.subTest(absolute=absolute):
                session = self.workspace_session()
                source, successor = self.create_run(), self.create_run()

                def portable_git(repo, *args):
                    if any(arg.startswith('--path-format') for arg in args):
                        raise ValueError('Git rev-parse failed: unknown option --path-format')
                    if args == ('rev-parse', '--git-common-dir'):
                        return str(self.repo / '.git') if absolute else '.git'
                    return real_git(repo, *args)

                with patch.object(claim_ops, '_git', side_effect=portable_git):
                    self.register(source, session, 'portable-context.json')
                    artifacts.transfer_resources(source, successor, [str(session)],
                        authority='User requests transfer', controller=self.controller())
                    self.assertEqual(claims.verify_claim(session, successor)['archive_path'], str(successor))
                    result = workspace.cleanup(argparse.Namespace(
                        manifest=str(session / 'manifest.json'), run_dir=str(successor)))
                self.assertTrue(result['all_registered_removed'])
                self.assertFalse(session.exists())

    def fixture(self, session, name):
        worktree = Path(self.read(session / 'manifest.json')['workspaces'][0]['path'])
        path = worktree / name
        path.write_text('review-created reproduction\n', encoding='utf-8')
        return path

    def test_record_artifact_conflicting_with_session_lock_preserves_manifest(self):
        session = self.workspace_session()
        path = self.fixture(session, 'reproduction.py')
        before = self.snapshot(session)
        with self.held_session(session):
            with self.assertRaisesRegex(workspace.ReviewError, 'lock conflict'):
                workspace.record_artifact(argparse.Namespace(manifest=str(session / 'manifest.json'), path=str(path)))
        self.assertEqual(self.snapshot(session), before)
        result = workspace.record_artifact(argparse.Namespace(manifest=str(session / 'manifest.json'), path=str(path)))
        self.assertEqual(result['status'], 'recorded')
        self.assertEqual(self.read(session / 'manifest.json')['artifacts'], [result['artifact']])

    def test_record_artifact_reloads_a_record_committed_after_its_initial_read(self):
        session = self.workspace_session()
        first = self.fixture(session, 'first.py')
        second = self.fixture(session, 'second.py')
        original_load = workspace_ops.load
        initial_read = True

        def another_writer_commits(path):
            nonlocal initial_read
            value = original_load(path)
            if initial_read:
                initial_read = False
                workspace.record_artifact(argparse.Namespace(manifest=str(session / 'manifest.json'), path=str(first)))
            return value

        with patch.object(workspace_ops, 'load', side_effect=another_writer_commits):
            workspace.record_artifact(argparse.Namespace(manifest=str(session / 'manifest.json'), path=str(second)))
        entries = self.read(session / 'manifest.json')['artifacts']
        self.assertEqual({entry['path'] for entry in entries}, {str(first), str(second)})
        self.assertEqual(len(entries), 2)

    def test_record_artifact_excludes_cleanup_and_preserves_both_records_after_retry(self):
        session = self.workspace_session()
        first = self.fixture(session, 'first.py')
        second = self.fixture(session, 'second.py')
        ready, release = self.root / 'artifact-ready', self.root / 'artifact-release'
        code = r'''
from pathlib import Path
import argparse, json, sys, time
from unittest.mock import patch
sys.path[:0] = sys.argv[1:3]
from script_test_support import workspace_api
workspace = workspace_api()
from ccr.execution import workspaces as workspace_ops
manifest, artifact, ready, release = map(Path, sys.argv[3:7])
original = workspace_ops.save
def delayed_save(value):
    ready.touch()
    deadline = time.monotonic() + 30
    while not release.exists():
        if time.monotonic() > deadline:
            raise RuntimeError('artifact release timed out')
        time.sleep(0.02)
    return original(value)
with patch.object(workspace_ops, 'save', side_effect=delayed_save):
    print(json.dumps(workspace.record_artifact(argparse.Namespace(manifest=str(manifest), path=str(artifact)))), flush=True)
'''
        child = subprocess.Popen([sys.executable, '-B', '-X', 'utf8', '-c', code,
            str(safety.resources.SCRIPTS), str(Path(__file__).resolve().parent),
            str(session / 'manifest.json'), str(first), str(ready), str(release)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8')
        try:
            deadline = time.monotonic() + 30
            while not ready.exists() and child.poll() is None:
                self.assertLess(time.monotonic(), deadline, 'artifact writer did not reach commit')
                time.sleep(0.02)
            self.assertTrue(ready.exists(), 'artifact writer must reach the real manifest save')
            before = self.snapshot(session)
            with self.assertRaisesRegex(workspace.ReviewError, 'lock conflict'):
                workspace.record_artifact(argparse.Namespace(manifest=str(session / 'manifest.json'), path=str(second)))
            with self.assertRaisesRegex(workspace.ReviewError, 'lock conflict'):
                workspace.cleanup(argparse.Namespace(manifest=str(session / 'manifest.json'), run_dir=None))
            self.assertEqual(self.snapshot(session), before)
        finally:
            release.touch()
            try:
                output, error = child.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.communicate(timeout=10)
                raise
            self.assertEqual(child.returncode, 0, error + output)
        self.assertEqual(json.loads(output)['status'], 'recorded')
        workspace.record_artifact(argparse.Namespace(manifest=str(session / 'manifest.json'), path=str(second)))
        entries = self.read(session / 'manifest.json')['artifacts']
        self.assertEqual({entry['path'] for entry in entries}, {str(first), str(second)})
        result = workspace.cleanup(argparse.Namespace(manifest=str(session / 'manifest.json'), run_dir=None))
        self.assertTrue(result['all_registered_removed'])
        self.assertFalse(session.exists())
