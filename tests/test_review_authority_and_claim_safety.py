"""Explicit authority survives recapture; a session has one concurrent owner."""
import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import subprocess
import sys
import time
import unittest

import test_review_resource_claims as resources
from recovery_fixtures import record10, selection, selection_input

artifacts = resources.artifacts
claims = resources.claims
profiles = artifacts.profile_execution


class ProfileAuthorityTests(unittest.TestCase):
    def bypass_history(self):
        return [selection('deep', 'explicit'),
                selection('deep', 'automatic', id='S002', changed_from='deep',
                          phase='discovery', event_id='E000002', reference='evidence/reassess.json#deep'),
                selection('focused', 'automatic', id='S003', changed_from='deep',
                          phase='verification', event_id='E000003', reference='evidence/narrow.json#focused',
                          reason='The retained call graph disproves the broader trigger')]

    def test_authority_cannot_be_erased_by_same_automatic_profile(self):
        history = self.bypass_history()
        raw = {key: history[1][key] for key in profiles.INPUT_FIELDS}
        with self.assertRaisesRegex(ValueError, 'later explicit user source'):
            profiles.validate_selection(raw, previous=history[0])

    def test_authority_continuity_is_checked_in_history_and_final_gate(self):
        history = self.bypass_history()
        self.assertTrue(any('later explicit user source' in error for error in profiles.validate_history(history)))
        value = record10('focused', 'explicit')
        value['coverage']['execution']['profile_history'] = history
        value['coverage']['execution']['plan'][0]['selection_id'] = 'S003'
        self.assertTrue(any('later explicit user source' in error for error in profiles.validate_profile_execution(value)))
        self.assertTrue(any('later explicit user source' in error for error in artifacts.review_contract.validate(value)))

    def test_later_explicit_selection_keeps_authority_against_same_profile_recapture(self):
        first = selection('deep', 'explicit')
        later = selection('focused', 'explicit', id='S002', changed_from='deep',
                          phase='verification', event_id='E000002',
                          authority='User requested focused')
        self.assertEqual(profiles.validate_history([first, later]), [])
        for authority in (None, 'An automatic reassessment cannot replace the user decision'):
            with self.subTest(authority=authority):
                recapture = selection('focused', 'automatic', id='S003', changed_from='focused',
                                      phase='verification', event_id='E000003', authority=authority)
                raw = {key: recapture[key] for key in profiles.INPUT_FIELDS}
                with self.assertRaisesRegex(ValueError, 'later explicit user source'):
                    profiles.validate_selection(raw, previous=later)
                errors = profiles.validate_history([first, later, recapture])
                self.assertTrue(any('profile_history[2]' in error and
                                    'later explicit user source' in error for error in errors), errors)

    def test_authority_allows_a_later_explicit_user_selection(self):
        first = selection('deep', 'explicit')
        later = selection('focused', 'explicit', id='S002', changed_from='deep',
                          phase='verification', event_id='E000002', reference='evidence/user.json#focused',
                          authority='User explicitly requested focused after reassessing scope')
        self.assertEqual(profiles.validate_history([first, later]), [])


CHILD_REGISTER = r'''
import json
from pathlib import Path
import sys
import time
from unittest.mock import patch
sys.path[:0] = sys.argv[1:3]
from script_test_support import archive_api
from ccr.archive import lifecycle as lifecycle_ops
artifacts = archive_api()
run, session, context, ready, release = map(Path, sys.argv[3:8])
requested = [] if sys.argv[8] == 'existing' else [str(session)]
original = lifecycle_ops.atomic_write
def delayed_write(path, data, **kwargs):
    if Path(path) == session / '.review-run-owner.json':
        ready.write_text('digest checked', encoding='utf-8')
        deadline = time.monotonic() + 30
        while not release.exists():
            if time.monotonic() > deadline:
                raise RuntimeError('test release timed out')
            time.sleep(0.02)
    return original(path, data, **kwargs)
try:
    with patch.object(lifecycle_ops, 'atomic_write', side_effect=delayed_write):
        artifacts.register(run, requested, context_input=context)
    print(json.dumps({'status': 'registered'}), flush=True)
except ValueError as exc:
    print(json.dumps({'status': 'refused', 'error': str(exc)}), flush=True)
'''


class SessionClaimSafetyTests(unittest.TestCase):
    setUp = resources.ResourceClaimTests.setUp
    git = resources.ResourceClaimTests.git
    write = resources.ResourceClaimTests.write
    read = resources.ResourceClaimTests.read
    snapshot = resources.ResourceClaimTests.snapshot
    profile_input = resources.ResourceClaimTests.profile_input
    workspace_session = resources.ResourceClaimTests.workspace_session
    create_run = resources.ResourceClaimTests.create_run
    context = resources.ResourceClaimTests.context
    register = resources.ResourceClaimTests.register
    controller = resources.ResourceClaimTests.controller

    def test_authority_rejection_preserves_selected_run(self):
        run = Path(artifacts.prepare(self.repo, self.scope, '2.12.0', 'codex', output_root=self.output,
                                    profile_input=selection_input('deep', 'explicit')))
        before = self.snapshot(run)
        with self.assertRaisesRegex(ValueError, 'later explicit user source'):
            artifacts.select_profile(run, selection_input('deep', 'automatic', phase='discovery',
                                     reference='evidence/reassess.json#deep'))
        self.assertEqual(self.snapshot(run), before)

    def test_select_profile_accepts_later_explicit_authority_and_records_transition(self):
        run = Path(artifacts.prepare(self.repo, self.scope, '2.12.0', 'codex', output_root=self.output,
                                    profile_input=selection_input('deep', 'explicit')))
        first = self.read(run / 'cierre.json')['profile_history'][0]
        artifacts.select_profile(run, selection_input('focused', 'explicit', phase='verification',
                                 authority='User requested focused after reassessing the scope'))
        history = self.read(run / 'cierre.json')['profile_history']
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0], first)
        self.assertEqual(history[-1]['profile'], 'focused')
        self.assertEqual(history[-1]['selection_source'], 'explicit')
        self.assertEqual(history[-1]['changed_from'], 'deep')
        events = [json.loads(line) for line in (run / 'trazabilidad.jsonl').read_text(encoding='utf-8').splitlines()]
        transitions = [event for event in events if event['kind'] == 'profile']
        self.assertEqual(len(transitions), 2)
        self.assertEqual(transitions[-1]['event_id'], history[-1]['event_id'])

    def test_concurrent_registration_commits_only_one_session_owner(self):
        self.concurrent_registration(False)

    def test_concurrent_registration_also_locks_predeclared_sessions(self):
        self.concurrent_registration(True)

    def test_claim_coordination_does_not_change_checkout_baseline(self):
        session = self.workspace_session()
        baseline = self.read(session / 'manifest.json')['main_baseline']
        run = self.create_run()
        self.register(run, session, 'baseline-context.json')
        self.assertEqual(resources.review_workspace.state(self.repo, session), baseline)

    def register_repository_views(self, other):
        first = self.workspace_session()
        second = Path(resources.review_workspace.prepare(argparse.Namespace(repo=str(other), ref='HEAD',
                      mode='commit', role=['review'], include_untracked=[]))['session_dir'])
        run = self.create_run()
        artifacts.register(run, [str(first), str(second)], context_input=self.context(run, 'views-context.json'))
        for session in (first, second):
            self.assertEqual(claims.verify_claim(session, run)['archive_path'], str(run))

    def test_registration_accepts_sessions_from_two_worktrees(self):
        other = self.root / 'other-worktree'
        self.git('worktree', 'add', '--detach', str(other), 'HEAD')
        self.register_repository_views(other)

    def test_registration_accepts_sessions_from_two_clones_of_same_repository(self):
        origin = 'https://example.invalid/ccr-concurrency-fixture.git'
        self.git('remote', 'add', 'origin', origin)
        other = self.root / 'other-clone'
        try:
            self.git('clone', '--local', str(self.repo), str(other))
        except AssertionError as exc:
            message = str(exc)
            if sys.platform == 'win32' and (
                    ('NtCreateDirectoryObject' in message and '0xC0000022' in message)
                    or 'Could not read from remote repository' in message):
                self.skipTest('Git Bash cannot create its Win32 synchronization object in this host')
            raise
        changed = subprocess.run(['git', 'remote', 'set-url', 'origin', origin], cwd=other,
                                 capture_output=True, text=True)
        self.assertEqual(changed.returncode, 0, changed.stderr)
        self.register_repository_views(other)

    @contextmanager
    def held_session(self, session):
        ready, release = self.root / 'held-ready', self.root / 'held-release'
        code = r'''
from pathlib import Path
import sys, time
sys.path.insert(0, sys.argv[1])
from ccr.execution.claims import session_claim_locks
with session_claim_locks([sys.argv[2]]):
    Path(sys.argv[3]).touch()
    deadline = time.monotonic() + 30
    while not Path(sys.argv[4]).exists():
        if time.monotonic() > deadline:
            raise RuntimeError('test release timed out')
        time.sleep(0.02)
'''
        child = subprocess.Popen([sys.executable, '-B', '-X', 'utf8', '-c', code,
            str(resources.SCRIPTS), str(session), str(ready), str(release)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8')
        try:
            deadline = time.monotonic() + 30
            while not ready.exists() and child.poll() is None:
                self.assertLess(time.monotonic(), deadline, 'session lock was not acquired')
                time.sleep(0.02)
            self.assertTrue(ready.exists(), 'child must acquire a real session lock')
            yield
        finally:
            release.touch()
            try:
                output, error = child.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.communicate(timeout=10)
                raise
            self.assertEqual(child.returncode, 0, error + output)

    def test_transfer_conflicting_with_session_lock_preserves_both_runs(self):
        session = self.workspace_session()
        source, successor = self.create_run(), self.create_run()
        self.register(source, session, 'transfer-context.json')
        paths = (source, successor, session)
        before = tuple(self.snapshot(path) for path in paths)
        with self.held_session(session):
            with self.assertRaisesRegex(ValueError, 'lock conflict'):
                artifacts.transfer_resources(source, successor, [str(session)],
                    authority='User requests transfer', controller=self.controller())
        self.assertEqual(tuple(self.snapshot(path) for path in paths), before)
        self.assertEqual(claims.verify_claim(session, source)['archive_path'], str(source))

    def test_bootstrap_cleanup_conflicting_with_session_lock_preserves_session(self):
        session = self.workspace_session()
        before = self.snapshot(session)
        args = argparse.Namespace(manifest=str(session / 'manifest.json'), run_dir=None)
        with self.held_session(session):
            with self.assertRaisesRegex(resources.review_workspace.ReviewError, 'lock conflict'):
                resources.review_workspace.cleanup(args)
        self.assertEqual(self.snapshot(session), before)
        closed = resources.review_workspace.cleanup(args)
        self.assertFalse(closed['main_changed'])
        self.assertFalse(session.exists())

    def test_session_locks_release_after_baseexception_and_reenter_in_stable_order(self):
        first, second = self.workspace_session(), self.workspace_session()
        with self.assertRaises(KeyboardInterrupt):
            with claims.session_claim_locks([second, first, second]):
                with claims.session_claim_locks([first, second]):
                    raise KeyboardInterrupt('injected while session locks are held')
        with claims.session_claim_locks([first, second]):
            pass

    def concurrent_registration(self, predeclared):
        session = self.workspace_session()
        paths = [session] if predeclared else []
        first, second = self.create_run(paths), self.create_run(paths)
        contexts = [self.context(first, 'first-context.json'), self.context(second, 'second-context.json')]
        before_second = self.snapshot(second)
        ready = [self.root / ('ready-' + name) for name in ('a', 'b')]
        release = [self.root / ('release-' + name) for name in ('a', 'b')]
        children = []
        try:
            for index, run in enumerate((first, second)):
                child = subprocess.Popen([sys.executable, '-B', '-X', 'utf8', '-c', CHILD_REGISTER,
                    str(resources.SCRIPTS), str(Path(__file__).resolve().parent),
                    str(run), str(session), str(contexts[index]),
                    str(ready[index]), str(release[index]), 'existing' if predeclared else 'new'],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, encoding='utf-8')
                children.append(child)
                deadline = time.monotonic() + 30
                while not ready[index].exists() and child.poll() is None:
                    self.assertLess(time.monotonic(), deadline, 'child did not reach claim boundary')
                    time.sleep(0.02)
                if index == 0:
                    self.assertTrue(ready[0].exists(), 'first process must reach the real sidecar write')
            release[0].touch()
            first_out, first_err = children[0].communicate(timeout=30)
            self.assertEqual(children[0].returncode, 0, first_err)
            self.assertEqual(json.loads(first_out)['status'], 'registered')
            committed_sidecar = (session / claims.CLAIM_NAME).read_bytes()
            release[1].touch()
            second_out, second_err = children[1].communicate(timeout=30)
            self.assertEqual(children[1].returncode, 0, second_err)
            self.assertEqual(json.loads(second_out)['status'], 'refused')
            self.assertEqual((session / claims.CLAIM_NAME).read_bytes(), committed_sidecar)
            self.assertEqual(claims.verify_claim(session, first)['archive_path'], str(first))
            self.assertEqual(self.snapshot(second), before_second)
            self.assertEqual(self.read(second / 'cierre.json')['resource_claims'], [])
        finally:
            for path in release:
                path.touch()
            for child in children:
                if child.poll() is None:
                    child.kill()
                child.communicate(timeout=10)
