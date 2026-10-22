"""Operational projections are read-only and never invent continuation work."""
import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import test_review_recovery as recovery_fixtures

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import review_recovery as recovery
from ccr.archive import inspection as inspection_ops
import test_review_artifacts as archive


class OperationalSummaryTests(unittest.TestCase):
    setUp = recovery_fixtures.ReviewRecoveryTests.setUp
    prepare7 = recovery_fixtures.ReviewRecoveryTests.prepare7
    profile_input = recovery_fixtures.ReviewRecoveryTests.profile_input
    retained_claimed_run = recovery_fixtures.ReviewRecoveryTests.retained_claimed_run
    git = recovery_fixtures.ReviewRecoveryTests.git
    read = recovery_fixtures.ReviewRecoveryTests.read
    write = recovery_fixtures.ReviewRecoveryTests.write
    snapshot = recovery_fixtures.ReviewRecoveryTests.snapshot
    events = recovery_fixtures.ReviewRecoveryTests.events
    current = recovery_fixtures.ReviewRecoveryTests.current

    def test_unknown_inputs_with_pending_transfer_preserve_state(self):
        manifest = {'schema_version': 8, 'layout_version': 2,
                    'state': 'processing', 'operation': {'disposition': 'open'}}
        before = copy.deepcopy(manifest)
        decision = recovery.continuation_decision(
            manifest, input_appraisal={'applicability': 'unknown'},
            pending_operation={'kind': 'transfer', 'can_complete': False}, candidate_issues=[])
        self.assertEqual(decision['action'], 'preserve')
        self.assertFalse(decision['new_work'])
        self.assertEqual(manifest, before)

    def test_changed_inputs_propose_authorized_linked_restart(self):
        manifest = {'schema_version': 8, 'layout_version': 2,
                    'state': 'processing', 'operation': {'disposition': 'open'}}
        before = copy.deepcopy(manifest)
        decision = recovery.continuation_decision(
            manifest, input_appraisal={'applicability': 'changed'}, pending_operation=None,
            candidate_issues=[])
        self.assertEqual(decision['action'], 'restart')
        self.assertTrue(decision['requires_authority'])
        self.assertTrue(decision['new_work'])
        self.assertEqual(manifest, before)

    def test_exact_pending_operation_recovers_without_new_work(self):
        manifest = {'schema_version': 8, 'layout_version': 2,
                    'state': 'processing', 'operation': {'disposition': 'open'}}
        decision = recovery.continuation_decision(
            manifest, input_appraisal={'applicability': 'unknown'},
            pending_operation={'kind': 'checkpoint', 'can_complete': True}, candidate_issues=[])
        self.assertEqual(decision['action'], 'recover')
        self.assertFalse(decision['new_work'])

    def test_non_candidate_gate_requires_linked_restart(self):
        manifest = {'schema_version': 8, 'layout_version': 2,
                    'state': 'processing', 'retained': False,
                    'operation': {'disposition': 'open'}}
        decision = recovery.continuation_decision(
            manifest, input_appraisal={'applicability': 'applicable'}, pending_operation=None,
            candidate_issues=[{'code': 'missing_plan', 'field': 'context.plan',
                              'message': 'No durable plan', 'expected': 'captured plan'}])
        self.assertEqual(decision['action'], 'restart')
        self.assertTrue(decision['requires_authority'])
        self.assertTrue(decision['new_work'])

    def test_candidate_rebuild_requires_no_new_review(self):
        manifest = {'schema_version': 8, 'layout_version': 2,
                    'state': 'processing', 'retained': False,
                    'operation': {'disposition': 'open'}}
        decision = recovery.continuation_decision(
            manifest, input_appraisal={'applicability': 'applicable'}, pending_operation=None,
            candidate_issues=[{'code': 'missing_source', 'field': 'candidate.reference',
                'reference': 'evidence/result.json', 'message': 'Candidate incomplete',
                'expected': 'Regenerate the unretained candidate'}])
        self.assertEqual(decision['action'], 'rebuild_candidate')
        self.assertFalse(decision['new_work'])

    def test_publication_after_retain_preserves_snapshot(self):
        run, _ = self.retained_claimed_run()
        record_path = run / 'review.json'
        before_snapshot = record_path.read_bytes()
        record = self.read(record_path)
        original_publication = record['resources']['publication']
        manifest = self.read(run / 'cierre.json')
        event_file = self.write('publication.json', {
            'kind': 'authorized-publication', 'status': 'completed',
            'summary': 'Synthetic publication observation',
            'authority': 'User authorized publication',
            'provenance': {'kind': 'tool', 'source': 'synthetic publication connector'},
            'occurred_at': '2026-10-20T12:00:00Z'})
        archive.artifacts.record_event(run, event_file)
        after_snapshot = record_path.read_bytes()
        events = self.events(run)
        publication_event = events[-1]
        updated_manifest = self.read(run / 'cierre.json')
        manifest_before_summary = copy.deepcopy(updated_manifest)
        events_before_summary = copy.deepcopy(events)
        record_before_summary = copy.deepcopy(record)

        summary = recovery.operational_summary(updated_manifest, events, record)

        self.assertEqual(summary['publication']['status'], 'published')
        self.assertEqual(summary['publication']['source'], publication_event['event_id'])
        self.assertEqual(summary['publication']['occurred_at'], publication_event['occurred_at'])
        self.assertEqual(record['resources']['publication'], original_publication)
        self.assertEqual(after_snapshot, before_snapshot)
        self.assertEqual(updated_manifest, manifest_before_summary)
        self.assertEqual(events, events_before_summary)
        self.assertEqual(record, record_before_summary)

    def test_historical_source_never_gets_native_summary(self):
        from recovery_fixtures import historical_prepare
        run = historical_prepare(archive.artifacts, self.repo, self.scope,
                                 output_root=self.output)
        inspected = recovery.inspect_run(run)
        self.assertEqual(inspected['integrity']['status'], 'unsupported_layout')
        self.assertNotIn('operational_summary', inspected)

    def test_complete_source_never_resumes_or_rebuilds(self):
        manifest = {'schema_version': 8, 'layout_version': 2,
                    'state': 'complete', 'retained': True,
                    'operation': {'disposition': 'complete'}}
        decision = recovery.continuation_decision(
            manifest, input_appraisal={'applicability': 'applicable'}, pending_operation=None,
            candidate_issues=[{'code': 'missing_source', 'field': 'candidate.reference',
                'reference': 'evidence/result.json', 'message': 'Candidate incomplete',
                'expected': 'Regenerate the unretained candidate'}])
        self.assertEqual(decision['action'], 'show_history')
        self.assertNotIn(decision['action'], {'resume', 'rebuild_candidate'})

    def test_inspect_adds_summary_only_to_verified_native_runs_without_writes(self):
        run = self.prepare7()
        before = self.snapshot(run)
        inspected = recovery.inspect_run(run, current_inputs=self.current(run))
        self.assertEqual(inspected['integrity']['status'], 'verified')
        self.assertEqual(set(inspected['operational_summary']),
                         {'disposition', 'phase', 'successor', 'cleanup', 'publication'})
        self.assertEqual(before, self.snapshot(run))

    def test_summary_failure_does_not_claim_completed_activity(self):
        run, session = self.retained_claimed_run()
        archive.artifacts.close(run, cleanup='pending', residuals=[str(session)])
        recovery_fixtures.review_workspace.cleanup(
            recovery_fixtures.argparse.Namespace(manifest=str(session / 'manifest.json'),
                                                 run_dir=str(run)))
        archive.artifacts.close(run, cleanup='complete')
        with patch.object(inspection_ops, 'operational_summary', side_effect=ValueError('synthetic mismatch')):
            inspected = recovery.inspect_run(run)
        self.assertEqual(inspected['integrity']['status'], 'invalid')
        self.assertEqual(inspected['activity'], 'unknown')
        self.assertNotIn('operational_summary', inspected)

    def test_trace_changed_after_integrity_check_cannot_feed_summary(self):
        run = self.prepare7()
        trace_path = run / inspection_ops.review_trace.NAME
        original = trace_path.read_bytes()
        verify_files = inspection_ops._verify_files

        def verify_then_change(run_path, manifest, **kwargs):
            result = verify_files(run_path, manifest, **kwargs)
            trace_path.write_bytes(original + b'{}\n')
            return result

        try:
            with patch.object(inspection_ops, '_verify_files', side_effect=verify_then_change):
                inspected = recovery.inspect_run(run)
            self.assertEqual(inspected['integrity']['status'], 'invalid')
            self.assertEqual(inspected['activity'], 'unknown')
            self.assertNotIn('operational_summary', inspected)
        finally:
            trace_path.write_bytes(original)


if __name__ == '__main__':
    unittest.main()
