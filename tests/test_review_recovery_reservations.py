"""Regressions for the remaining reservations in the fourth CCR of PR 19."""
from pathlib import Path
import argparse
import copy
import json
import shutil
import unittest
from unittest.mock import patch

import test_review_restart_resources as resource_tests
import test_review_artifacts as archive
from recovery_fixtures import legacy_prepare, selection_input
import review_recovery as recovery
import review_resource_claims as claims

artifacts = resource_tests.artifacts


class RecoveryReservationTests(unittest.TestCase):
    setUp = resource_tests.RestartResourceReplayTests.setUp
    git = resource_tests.RestartResourceReplayTests.git
    write = resource_tests.RestartResourceReplayTests.write
    read = resource_tests.RestartResourceReplayTests.read
    snapshot = resource_tests.RestartResourceReplayTests.snapshot
    profile_input = resource_tests.RestartResourceReplayTests.profile_input
    prepare7 = resource_tests.RestartResourceReplayTests.prepare7
    current = resource_tests.RestartResourceReplayTests.current
    controller = resource_tests.RestartResourceReplayTests.controller
    restart_request = resource_tests.RestartResourceReplayTests.restart_request
    registered_session = resource_tests.RestartResourceReplayTests.registered_session
    resource_fixture = resource_tests.RestartResourceReplayTests.resource_fixture
    superseded_checkpoint = resource_tests.RestartResourceReplayTests.superseded_checkpoint

    def context(self, run):
        manifest = self.read(run / 'cierre.json')
        selection = manifest['profile_history'][0]
        return {'profile': selection['profile'], 'selection_source': selection['selection_source'],
                'profile_reference': selection['reference'], 'profile_history': [selection],
                'execution_plan': [], 'executors': [], 'review_inputs': manifest['review_inputs']}

    def test_abandon_reconstructs_missing_intent_from_exact_active_descriptor(self):
        source = self.prepare7()
        request = self.restart_request(source)
        with patch.object(artifacts, '_write_restart_intent', side_effect=KeyboardInterrupt('after descriptor')):
            with self.assertRaises(KeyboardInterrupt):
                artifacts.restart(source, **request)
        active = artifacts._active_restart_operation(source, self.read(source / 'cierre.json'))
        self.assertFalse(Path(active['intent_path']).exists())
        kwargs = dict(intent_path=active['intent_path'], controller=self.controller(),
                      authority='User requested abandonment', reason='Collect corrected inputs')
        before = self.snapshot(self.output)
        with self.assertRaises(ValueError):
            artifacts.abandon_restart(source, **dict(kwargs, intent_path=str(source / 'foreign.json')))
        self.assertEqual(self.snapshot(self.output), before)
        receipt = artifacts.abandon_restart(source, **kwargs)
        self.assertTrue(Path(active['intent_path']).is_file())
        self.assertEqual(receipt['operation_id'], active['operation_id'])
        before = self.snapshot(self.output)
        self.assertEqual(artifacts.abandon_restart(source, **kwargs), receipt)
        self.assertEqual(self.snapshot(self.output), before)
        request['profile_input']['reason'] = 'New selection after cancellation'
        artifacts.validate(Path(artifacts.restart(source, **request)))

    def test_successor_recovery_points_to_exact_restart_source(self):
        source, session, request = self.resource_fixture(True)
        replace = artifacts.os.replace
        def interrupted(stage, target):
            result = replace(stage, target)
            if Path(target) == session / claims.CLAIM_NAME:
                raise KeyboardInterrupt('after transferred claim')
            return result
        with patch.object(artifacts.os, 'replace', side_effect=interrupted):
            with self.assertRaises(KeyboardInterrupt):
                artifacts.restart(source, **request)
        active = artifacts._active_restart_operation(source, self.read(source / 'cierre.json'))
        successor = Path(active['successor_run_dir'])
        before = self.snapshot(self.output), self.snapshot(session)
        inspected = recovery.inspect_run(successor)
        candidates = recovery.find_candidates(self.repo, self.read(source / 'cierre.json')['scope'],
                                              archive_root=self.output, current_inputs=self.current(source))
        candidate = next(row for row in candidates['candidates'] if row['run_dir'] == str(successor))
        recovered = artifacts.recover(successor, controller=self.controller(), authority=request['authority'],
                                      current_inputs=request['current_inputs'])
        for result in (inspected, candidate, recovered):
            actions = result['actions']
            self.assertEqual(actions[0]['action'], 'recover_source')
            self.assertEqual(actions[0]['run_dir'], str(source))
            self.assertEqual(actions[0]['operation_id'], active['operation_id'])
        self.assertEqual((self.snapshot(self.output), self.snapshot(session)), before)
        with self.assertRaises(ValueError) as error:
            artifacts.begin_resource_cleanup(successor, session)
        self.assertIn(str(source), str(error.exception))
        self.assertIn(active['operation_id'], str(error.exception))
        result = artifacts.recover(source, controller=self.controller(), authority=request['authority'],
                                   current_inputs=request['current_inputs'])
        self.assertEqual(result['status'], 'restarted')
        artifacts.validate(source)
        artifacts.validate(successor)

    def legacy(self, schema):
        source = legacy_prepare(artifacts, self.repo, self.scope, output_root=self.output)
        manifest = self.read(source / 'cierre.json')
        manifest['schema_version'] = schema
        if schema <= 2:
            manifest.pop('run_id')
            manifest.pop('repository_identity')
        if schema <= 3:
            manifest.pop('trace')
            manifest['hashes'].pop('trazabilidad.jsonl')
            (source / 'trazabilidad.jsonl').unlink()
        artifacts._save_manifest(source, manifest, self.read(source / artifacts.MARKER))
        return source

    def test_exact_restart_recovery_with_unknown_identities_preserves_freshness(self):
        for schema in range(1, 8):
            with self.subTest(schema=schema):
                source = self.legacy(schema) if schema < 7 else self.prepare7(capture_inputs=False)
                request = self.restart_request(source)
                before = self.snapshot(source)
                with patch.object(artifacts, '_prepare_from_restart_intent', side_effect=KeyboardInterrupt('before prepare')):
                    with self.assertRaises(KeyboardInterrupt):
                        artifacts.restart(source, **request)
                result = artifacts.recover(source, controller=self.controller(), authority=request['authority'],
                                           current_inputs=request['current_inputs'])
                self.assertEqual(result['status'], 'restarted')
                self.assertEqual(result['input_appraisal']['applicability'], 'unknown')
                self.assertTrue(result['replay_inputs_match'])
                artifacts.validate(Path(result['successor_run_dir']))
                if schema < 7:
                    self.assertEqual(self.snapshot(source), before)

    def test_changed_restart_inputs_do_not_replay_an_unknown_intent(self):
        source = self.prepare7(capture_inputs=False)
        request = self.restart_request(source)
        with patch.object(artifacts, '_prepare_from_restart_intent', side_effect=KeyboardInterrupt('before prepare')):
            with self.assertRaises(KeyboardInterrupt):
                artifacts.restart(source, **request)
        changed = copy.deepcopy(request['current_inputs'])
        changed['requirements_identity'] = 'new observed requirements'
        before = self.snapshot(self.output)
        result = artifacts.recover(source, controller=self.controller(), authority=request['authority'], current_inputs=changed)
        self.assertEqual(result['status'], 'restart_pending')
        self.assertFalse(result['replay_inputs_match'])
        self.assertEqual(self.snapshot(self.output), before)

    def test_superseded_pending_checkpoint_errors_name_registered_successor(self):
        source, successor, _, context = self.superseded_checkpoint()
        selection = selection_input('deep', phase='discovery', reason='Another review flow was observed')
        operations = (
            lambda: artifacts.resume(source, controller=self.controller(), authority='Continue', current_inputs=self.current(source)),
            lambda: artifacts.pause(source, authority='Pause', reason='Stop', phase='discovery'),
            lambda: artifacts.block(source, source='Observed error', reason='Blocked', phase='discovery'),
            lambda: artifacts.register(source, [], context_input=context),
            lambda: artifacts.select_profile(source, selection),
            lambda: artifacts.record_event(source, self.write('superseded-event.json',
                {'kind': 'discovery', 'status': 'started', 'summary': 'Observed start'})),
            lambda: artifacts.retain(source, self.final),
            lambda: artifacts.validate(source, require_retained=True),
            lambda: artifacts.validate(source, require_complete=True),
        )
        before = self.snapshot(source)
        for operation in operations:
            with self.subTest(operation=operation):
                with self.assertRaisesRegex(ValueError, 'superseded.*successor') as error:
                    operation()
                self.assertIn(str(successor), str(error.exception))
                self.assertEqual(self.snapshot(source), before)

    def adoption_conflict(self):
        source, session, request = self.resource_fixture(False)
        with patch.object(artifacts, 'register', side_effect=KeyboardInterrupt('before adoption')):
            with self.assertRaises(KeyboardInterrupt):
                artifacts.restart(source, **request)
        active = artifacts._active_restart_operation(source, self.read(source / 'cierre.json'))
        successor = Path(active['successor_run_dir'])
        foreign = self.prepare7('deep')
        artifacts.register(foreign, [str(session)], context_input=self.context(foreign))
        kwargs = dict(intent_path=active['intent_path'], controller=self.controller(),
                      authority='User cancels the conflicted adoption', reason='Another review owns the session')
        return source, successor, session, foreign, request, kwargs

    def assert_abandoned_history(self, source, successor, session, foreign, request, kwargs):
        foreign_before = self.snapshot(foreign), self.snapshot(session)
        receipt = artifacts.abandon_restart(source, **kwargs)
        manifest = self.read(successor / 'cierre.json')
        self.assertEqual(manifest['restart_abandonment'], receipt)
        self.assertEqual(manifest['state'], 'prepared')
        self.assertEqual(manifest['operation']['disposition'], 'blocked')
        self.assertFalse(artifacts.validate(successor)['retained'])
        self.assertEqual(self.snapshot(foreign), foreign_before[0])
        self.assertEqual(self.snapshot(session), foreign_before[1])
        self.assertEqual(claims.verify_claim(session, foreign)['run_id'], self.read(foreign / 'cierre.json')['run_id'])
        self.assertIsNone(artifacts._active_restart_operation(source, self.read(source / 'cierre.json')))
        before = self.snapshot(self.output), self.snapshot(session)
        self.assertEqual(artifacts.abandon_restart(source, **kwargs), receipt)
        recovered = artifacts.recover(successor, controller=self.controller(), authority='Inspect canceled history',
                                      current_inputs=self.current(successor))
        self.assertEqual(recovered['status'], 'abandoned')
        inspected = recovery.inspect_run(successor)
        candidates = recovery.find_candidates(self.repo, manifest['scope'], archive_root=self.output)
        candidate = next(row for row in candidates['candidates'] if row['run_dir'] == str(successor))
        for result in (inspected, candidate, recovered):
            self.assertEqual(result['actions'][0]['action'], 'inspect_source')
            self.assertEqual(result['actions'][0]['run_dir'], str(source))
        operations = (
            lambda: artifacts.resume(successor, controller=self.controller(), authority='Continue', current_inputs=self.current(successor)),
            lambda: artifacts.register(successor, [], context_input=self.context(successor)),
            lambda: artifacts.checkpoint(successor, context_input=self.write('abandoned-context.json', self.context(successor)), phase='discovery'),
            lambda: artifacts.select_profile(successor, selection_input('standard', phase='discovery')),
            lambda: artifacts.pause(successor, authority='Pause', reason='Stop', phase='discovery'),
            lambda: artifacts.block(successor, source='Observed', reason='Stop', phase='discovery'),
            lambda: artifacts.retain(successor, self.final),
            lambda: artifacts.close(successor, cleanup='not_needed'),
            lambda: artifacts.validate(successor, record_checkpoint=True),
            lambda: artifacts.record_event(successor, self.write('abandoned-event.json',
                {'kind': 'discovery', 'status': 'started', 'summary': 'Observed start'})),
            lambda: artifacts.restart(successor, **self.restart_request(successor)),
            lambda: artifacts.transfer_resources(foreign, successor, [str(session)],
                authority='Transfer into canceled successor', controller=self.controller()),
        )
        for operation in operations:
            with self.subTest(operation=operation):
                with self.assertRaisesRegex(ValueError, 'abandoned'):
                    operation()
                self.assertEqual((self.snapshot(self.output), self.snapshot(session)), before)
        for gate in ({'require_retained': True}, {'require_complete': True}):
            with self.assertRaises(ValueError):
                artifacts.validate(successor, **gate)
        request['profile_input']['reason'] = 'Fresh review after explicit cancellation'
        request['transfer_paths'] = []
        fresh = Path(artifacts.restart(source, **request))
        self.assertNotEqual(fresh, successor)
        newer_before = self.snapshot(fresh), self.snapshot(foreign), self.snapshot(session)
        self.assertEqual(artifacts.abandon_restart(source, **kwargs), receipt)
        self.assertEqual((self.snapshot(fresh), self.snapshot(foreign), self.snapshot(session)), newer_before)
        artifacts.validate(fresh)

    def test_foreign_claim_allows_explicit_empty_successor_abandonment(self):
        self.assert_abandoned_history(*self.adoption_conflict())

    def test_sidecar_owned_by_successor_without_manifest_row_cannot_be_abandoned(self):
        source, session, request = self.resource_fixture(False)
        replace = artifacts.os.replace
        def interrupted(stage, target):
            result = replace(stage, target)
            if Path(target) == session / claims.CLAIM_NAME:
                raise KeyboardInterrupt('claim exists before manifest row')
            return result
        with patch.object(artifacts.os, 'replace', side_effect=interrupted):
            with self.assertRaises(KeyboardInterrupt):
                artifacts.restart(source, **request)
        active = artifacts._active_restart_operation(source, self.read(source / 'cierre.json'))
        self.assertEqual(self.read(Path(active['successor_run_dir']) / 'cierre.json')['resource_claims'], [])
        before = self.snapshot(self.output), self.snapshot(session)
        with self.assertRaises(ValueError):
            artifacts.abandon_restart(source, intent_path=active['intent_path'], controller=self.controller(),
                authority='User cancellation', reason='Stop this restart')
        self.assertEqual((self.snapshot(self.output), self.snapshot(session)), before)
        self.assertEqual(artifacts.recover(source, controller=self.controller(), authority=request['authority'],
            current_inputs=request['current_inputs'])['status'], 'restarted')

    def test_started_or_nonempty_successor_cannot_be_abandoned(self):
        for case in ('started', 'evidence'):
            with self.subTest(case=case):
                self.output = self.root / ('archive-' + case)
                source, successor, session, foreign, _, kwargs = self.adoption_conflict()
                if case == 'started':
                    artifacts.record_event(successor, self.write('work-started.json',
                        {'kind': 'discovery', 'status': 'started', 'summary': 'Observed actual discovery start'}))
                else:
                    (successor / 'evidence').mkdir()
                    (successor / 'evidence' / 'worker.md').write_text('Preserve actual work', encoding='utf-8')
                before = tuple(self.snapshot(run) for run in (source, successor, foreign, session))
                with self.assertRaises(ValueError):
                    artifacts.abandon_restart(source, **kwargs)
                self.assertEqual(tuple(self.snapshot(run) for run in (source, successor, foreign, session)), before)
                self.assertEqual(claims.verify_claim(session, foreign)['run_id'], self.read(foreign / 'cierre.json')['run_id'])

    def test_interrupted_prepared_cancellation_replays_original_receipt(self):
        source, successor, session, foreign, request, kwargs = self.adoption_conflict()
        baseline = self.root / 'cancellation-baseline'
        shutil.copytree(self.output, baseline)
        session_before = self.snapshot(session)
        replace = artifacts.os.replace
        boundaries = [('successor_manifest', 'after'), ('successor_trace', 'before'), ('successor_trace', 'after'),
                      ('source_receipt', 'before'), ('source_receipt', 'after'),
                      ('source_trace', 'before'), ('source_trace', 'after'),
                      ('retirement', 'before'), ('retirement', 'after')]
        for target_phase, boundary in boundaries:
            for route in ('abandon', 'recover_source', 'recover_successor'):
                with self.subTest(phase=target_phase, boundary=boundary, route=route):
                    self.assertTrue(self.output.is_relative_to(self.root))
                    shutil.rmtree(self.output)
                    shutil.copytree(baseline, self.output)
                    hit = False
                    def interrupted(stage, target):
                        nonlocal hit
                        path = Path(target)
                        phase = None
                        if path == successor / 'cierre.json' and 'restart_abandonment' in json.loads(Path(stage).read_bytes()):
                            phase = 'successor_manifest'
                        elif path == successor / 'trazabilidad.jsonl':
                            phase = 'successor_trace'
                        elif path.name.endswith('.abandoned.json'):
                            phase = 'source_receipt'
                        elif path == source / 'trazabilidad.jsonl':
                            phase = 'source_trace'
                        elif path.name == 'active.json' and json.loads(Path(stage).read_bytes()).get('status') == 'complete':
                            phase = 'retirement'
                        selected = phase == target_phase and not hit
                        if selected:
                            hit = True
                            if boundary == 'before':
                                raise KeyboardInterrupt('before cancellation boundary')
                        result = replace(stage, target)
                        if selected and boundary == 'after':
                            raise KeyboardInterrupt('after cancellation boundary')
                        return result
                    with patch.object(artifacts.os, 'replace', side_effect=interrupted):
                        with self.assertRaises(KeyboardInterrupt):
                            artifacts.abandon_restart(source, **kwargs)
                    self.assertTrue(hit)
                    receipt = self.read(successor / 'cierre.json')['restart_abandonment']
                    if route == 'abandon':
                        result = artifacts.abandon_restart(source, **kwargs)
                        self.assertEqual(result, receipt)
                    else:
                        if route == 'recover_successor':
                            directed = artifacts.recover(successor, controller=self.controller(), authority='Recover cancellation',
                                current_inputs=self.current(successor))
                            if directed['status'] != 'abandoned':
                                self.assertEqual(directed['actions'][0]['run_dir'], str(source))
                        # A cancellation is already authorized, independent of freshness.
                        changed = copy.deepcopy(request['current_inputs'])
                        changed['requirements_identity'] = 'Requirements changed after cancellation'
                        artifacts.recover(source, controller=self.controller(), authority='Recover cancellation', current_inputs=changed)
                    self.assertEqual(artifacts.abandon_restart(source, **kwargs), receipt)
                    self.assertIsNone(artifacts._active_restart_operation(source, self.read(source / 'cierre.json')))
                    self.assertEqual(self.snapshot(session), session_before)
                    artifacts.validate(source)
                    artifacts.validate(successor)
                    artifacts.validate(foreign)
                    for run, text in ((source, 'Restart abandoned after blocked adoption:'),
                                      (successor, 'Empty adoption successor explicitly abandoned:')):
                        events = [json.loads(line) for line in (run / 'trazabilidad.jsonl').read_bytes().splitlines()]
                        self.assertEqual(sum(row['summary'].startswith(text) for row in events), 1)

    def test_old_abandonment_replay_does_not_retire_a_new_active_restart(self):
        source, successor, _, _, request, kwargs = self.adoption_conflict()
        receipt = artifacts.abandon_restart(source, **kwargs)
        request['profile_input']['reason'] = 'A different user-authorized restart'
        request['transfer_paths'] = []
        with patch.object(artifacts, '_prepare_from_restart_intent', side_effect=KeyboardInterrupt('new active restart')):
            with self.assertRaises(KeyboardInterrupt):
                artifacts.restart(source, **request)
        active = artifacts._active_restart_operation(source, self.read(source / 'cierre.json'))
        before = self.snapshot(self.output)
        inspected = recovery.inspect_run(successor)
        self.assertEqual(inspected['integrity']['status'], 'verified')
        self.assertEqual(inspected['actions'][0]['action'], 'inspect_source')
        recovered = artifacts.recover(successor, controller=self.controller(), authority='Inspect old cancellation',
                                      current_inputs=self.current(successor))
        self.assertEqual(recovered['status'], 'abandoned')
        self.assertEqual(artifacts.abandon_restart(source, **kwargs), receipt)
        self.assertEqual(self.snapshot(self.output), before)
        self.assertEqual(artifacts._active_restart_operation(source, self.read(source / 'cierre.json')), active)
        artifacts.recover(source, controller=self.controller(), authority=request['authority'], current_inputs=request['current_inputs'])
        self.assertEqual(self.read(successor / 'cierre.json')['restart_abandonment'], receipt)

    def test_foreign_owner_pending_work_does_not_block_safe_cancellation(self):
        source, successor, session, foreign, _, kwargs = self.adoption_conflict()
        with patch.object(artifacts, '_checkpoint_commit', side_effect=KeyboardInterrupt('foreign checkpoint interrupted')):
            with self.assertRaises(KeyboardInterrupt):
                artifacts.checkpoint(foreign, context_input=self.write('foreign-pending-context.json', self.context(foreign)), phase='discovery')
        before = self.snapshot(foreign), self.snapshot(session)
        with self.assertRaisesRegex(ValueError, 'checkpoint transaction is pending'):
            claims.verify_claim(session, foreign)
        artifacts.abandon_restart(source, **kwargs)
        self.assertEqual((self.snapshot(foreign), self.snapshot(session)), before)
        self.assertIsNotNone(self.read(successor / 'cierre.json')['restart_abandonment'])

    def test_outgoing_transfer_error_does_not_route_to_an_old_restart_ancestor(self):
        ancestor, session, request = self.resource_fixture(True)
        source = Path(artifacts.restart(ancestor, **request))
        successor = self.prepare7('deep')
        replace = artifacts.os.replace
        def interrupted(stage, target):
            result = replace(stage, target)
            if Path(target) == session / claims.CLAIM_NAME:
                raise KeyboardInterrupt('outgoing standalone transfer')
            return result
        with patch.object(artifacts.os, 'replace', side_effect=interrupted):
            with self.assertRaises(KeyboardInterrupt):
                artifacts.transfer_resources(source, successor, [str(session)],
                    authority='Transfer the existing review session', controller=self.controller())
        before = self.snapshot(source), self.snapshot(successor), self.snapshot(session)
        with self.assertRaisesRegex(ValueError, 'resource transfer is pending') as error:
            artifacts.begin_resource_cleanup(source, session)
        self.assertIn(str(source), str(error.exception))
        self.assertNotIn(str(ancestor), str(error.exception))
        self.assertEqual((self.snapshot(source), self.snapshot(successor), self.snapshot(session)), before)
        artifacts.recover(source, controller=self.controller(), authority='Transfer the existing review session',
                          current_inputs=self.current(source))
        self.assertEqual(claims.verify_claim(session, successor)['run_id'], self.read(successor / 'cierre.json')['run_id'])
