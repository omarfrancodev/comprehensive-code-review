"""Seventh CCR: the same recovery decision on source, successor and CLI errors."""
from pathlib import Path
import argparse
import json
import unittest
from unittest.mock import patch
import shutil

import test_review_recovery_exit_guidance as guidance
import test_review_recovery_diagnostics as diagnostics

artifacts = guidance.artifacts
from ccr.archive import restart as restart_ops
recovery = guidance.recovery
claims = guidance.claims
workspace = diagnostics.review_workspace


class RecoveryRouteConsistencyTests(unittest.TestCase):
    setUp = guidance.RecoveryExitGuidanceTests.setUp
    git = guidance.RecoveryExitGuidanceTests.git
    write = guidance.RecoveryExitGuidanceTests.write
    read = guidance.RecoveryExitGuidanceTests.read
    snapshot = guidance.RecoveryExitGuidanceTests.snapshot
    profile_input = guidance.RecoveryExitGuidanceTests.profile_input
    prepare7 = guidance.RecoveryExitGuidanceTests.prepare7
    current = guidance.RecoveryExitGuidanceTests.current
    controller = guidance.RecoveryExitGuidanceTests.controller
    restart_request = guidance.RecoveryExitGuidanceTests.restart_request
    registered_session = guidance.RecoveryExitGuidanceTests.registered_session
    resource_fixture = guidance.RecoveryExitGuidanceTests.resource_fixture
    context = guidance.RecoveryExitGuidanceTests.context
    missing_after_transfer_intent = guidance.RecoveryExitGuidanceTests.missing_after_transfer_intent
    adoption_conflict = diagnostics.RecoveryDiagnosticTests.adoption_conflict
    partial_adoption_conflict = diagnostics.RecoveryDiagnosticTests.partial_adoption_conflict

    def views(self, run):
        inspected = recovery.inspect_run(run)
        found = recovery.find_candidates(self.repo, self.read(run / 'cierre.json')['scope'], archive_root=self.output)
        candidate = next(row for row in found['candidates'] if row['run_dir'] == str(run))
        result = artifacts.recover(run, controller=self.controller(), authority='User requested diagnostic',
                                   current_inputs=self.current(run))
        return inspected, candidate, result

    def assert_route(self, runs, action, state):
        for run in runs:
            for result in self.views(run):
                self.assertEqual(result['actions'][0]['action'], action)
                self.assertEqual(result['recovery']['status'], state)
                self.assertFalse(result['recovery']['can_complete'])

    def test_foreign_claim_shares_exact_abandonment_on_source_and_successor(self):
        source, successor, session, foreign, _, kwargs = self.adoption_conflict()
        paths = (source, successor, session, foreign)
        before = tuple(self.snapshot(path) for path in paths)
        self.assert_route((source, successor), 'abandon_restart', 'cancellation_available')
        self.assertEqual(tuple(self.snapshot(path) for path in paths), before)
        artifacts.abandon_restart(source, **kwargs)
        self.assertEqual(self.snapshot(session), before[2])
        self.assertEqual(self.snapshot(foreign), before[3])

    def test_partial_foreign_claim_shares_independent_route_and_exact_retry_hint(self):
        source, successor, foreign, first, second, request, _ = self.partial_adoption_conflict()
        paths = (source, successor, foreign, first, second)
        before = tuple(self.snapshot(path) for path in paths)
        self.assert_route((source, successor), 'new_independent_review', 'independent_review_required')
        with self.assertRaises(ValueError) as caught:
            artifacts.restart(source, **request)
        self.assertIn('inspect/recover', str(caught.exception))
        self.assertIn(str(source), str(caught.exception))
        self.assertEqual(tuple(self.snapshot(path) for path in paths), before)

    def test_missing_durable_transfer_propagates_feasibility_without_a_hop(self):
        source, successor, _, request, _ = self.missing_after_transfer_intent()
        before = self.snapshot(source), self.snapshot(successor)
        self.assert_route((source, successor), 'new_independent_review', 'independent_review_required')
        self.assertEqual((self.snapshot(source), self.snapshot(successor)), before)
        with self.assertRaises(ValueError) as caught:
            artifacts.restart(source, **request)
        self.assertIn('inspect/recover', str(caught.exception))
        # Exact restart is a mutator: replaying its transfer intent can refresh
        # updated_at and its ownership digest before the missing workspace stops progression.
        for run, original in zip((source, successor), before):
            current = self.snapshot(run)
            changed = {name for name in set(current) | set(original) if current.get(name) != original.get(name)}
            self.assertTrue(changed.issubset({artifacts.MARKER, 'cierre.json'}), changed)
            prior_manifest = json.loads(original['cierre.json'])
            current_manifest = self.read(run / 'cierre.json')
            prior_manifest.pop('updated_at', None)
            current_manifest.pop('updated_at', None)
            self.assertEqual(current_manifest, prior_manifest)
            artifacts._load_run(run)

    def test_present_source_claim_is_named_separately(self):
        source, first, context = self.registered_session()
        second = Path(workspace.prepare(argparse.Namespace(repo=str(self.repo), ref='HEAD', mode='commit',
            role=['review'], include_untracked=[]))['session_dir'])
        artifacts.register(source, [str(first), str(second)], context_input=context)
        request = self.restart_request(source, transfer_paths=[str(first), str(second)])
        with patch.object(restart_ops, 'transfer_resources', side_effect=KeyboardInterrupt('prepared before transfer')):
            with self.assertRaises(KeyboardInterrupt):
                artifacts.restart(source, **request)
        successor = Path(artifacts._active_restart_operation(source, self.read(source / 'cierre.json'))['successor_run_dir'])
        self.assertTrue(first.is_relative_to(self.root))
        shutil.rmtree(first)
        before = self.snapshot(source), self.snapshot(successor), self.snapshot(second)
        for run in (source, successor):
            for result in self.views(run):
                self.assertIn('source_claims_present', result['recovery']['blocked_by'])
                self.assertIn('source claim', result['actions'][0]['reason'].lower())
        self.assertEqual((self.snapshot(source), self.snapshot(successor), self.snapshot(second)), before)

    def unavailable_transfer_fixture(self):
        source, session, request = self.resource_fixture(True)
        replace = artifacts.os.replace
        def interrupted(stage, target):
            result = replace(stage, target)
            if Path(target) == session / claims.CLAIM_NAME:
                raise KeyboardInterrupt('incoming transfer pending')
            return result
        with patch.object(artifacts.os, 'replace', side_effect=interrupted):
            with self.assertRaises(KeyboardInterrupt):
                artifacts.restart(source, **request)
        successor = Path(artifacts._active_restart_operation(source, self.read(source / 'cierre.json'))['successor_run_dir'])
        self.assertTrue(source.is_relative_to(self.root))
        source.rename(source.with_name(source.name + '-unavailable'))
        return successor, session

    def test_unavailable_transfer_source_offers_preservation_instead_of_failing_recover(self):
        successor, session = self.unavailable_transfer_fixture()
        before = self.snapshot(successor), self.snapshot(session)
        self.assert_route((successor,), 'preserve', 'source_unavailable')
        self.assertEqual((self.snapshot(successor), self.snapshot(session)), before)

    def test_unverifiable_foreign_owner_never_becomes_an_abandonment_offer(self):
        source, successor, session, foreign, _, _ = self.adoption_conflict()
        (foreign / artifacts.MARKER).write_text('{}', encoding='utf-8')
        paths = (source, successor, session, foreign)
        before = tuple(self.snapshot(path) for path in paths)
        self.assertEqual(recovery.inspect_run(source)['actions'][0]['action'], 'preserve')
        with self.assertRaises(ValueError):
            artifacts.recover(source, controller=self.controller(), authority='Inspect', current_inputs=self.current(source))
        self.assertEqual(tuple(self.snapshot(path) for path in paths), before)

    def assert_preserve_without_writes(self, run):
        before = self.snapshot(run)
        inspected = recovery.inspect_run(run)
        self.assertEqual(inspected['integrity']['status'], 'invalid')
        self.assertEqual([row['action'] for row in inspected['actions']], ['preserve'])
        self.assertNotIn('recovery', inspected)
        with self.assertRaises(ValueError):
            artifacts.recover(run, controller=self.controller(), authority='Inspect', current_inputs=self.current(run))
        self.assertEqual(self.snapshot(run), before)

    def test_corrupt_local_sidecar_is_not_an_independent_review_plan(self):
        source, successor, foreign, first, second, _, _ = self.partial_adoption_conflict()
        sidecar_path = first / claims.CLAIM_NAME
        sidecar = self.read(sidecar_path)
        sidecar['owner_id'] = '0' * 32
        sidecar_path.write_bytes(artifacts._json_bytes(sidecar))
        paths = (source, successor, foreign, first, second)
        before = tuple(self.snapshot(path) for path in paths)
        for run in (source, successor):
            self.assert_preserve_without_writes(run)
        self.assertEqual(tuple(self.snapshot(path) for path in paths), before)

    def test_corrupt_local_reservation_is_not_a_source_unavailable_plan(self):
        successor, session = self.unavailable_transfer_fixture()
        (successor / '.review-restart-reservation.json').write_text('{}', encoding='utf-8')
        before = self.snapshot(session)
        self.assert_preserve_without_writes(successor)
        self.assertEqual(self.snapshot(session), before)

    def test_corrupt_source_trace_does_not_invalidate_intact_successor(self):
        source, successor, _, _, _ = self.missing_after_transfer_intent()
        with (source / 'trazabilidad.jsonl').open('ab') as stream:
            stream.write(b'corrupt bytes\n')
        before = self.snapshot(source), self.snapshot(successor)
        self.assertEqual(recovery.inspect_run(source)['integrity']['status'], 'invalid')
        self.assert_route((successor,), 'preserve', 'source_unavailable')
        self.assertEqual((self.snapshot(source), self.snapshot(successor)), before)
