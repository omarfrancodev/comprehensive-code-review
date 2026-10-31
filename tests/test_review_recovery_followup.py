"""Regressions from the second independent review of PR 19."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import re
import shlex
import subprocess
import sys
import unittest
from unittest.mock import patch

import test_review_artifacts as archive
import test_review_checkpoints as checkpoint_tests
import test_review_recovery as recovery_tests
from recovery_fixtures import context10, legacy_prepare, record10, selection_input
from ccr.contracts import execution as review_execution
from script_test_support import recovery_api
recovery = recovery_api()
from script_test_support import workspace_api
review_workspace = workspace_api()

artifacts = archive.artifacts
from ccr.archive import lifecycle as lifecycle_ops, restart as restart_ops, transactions as transactions_ops


class RecoveryFollowupTests(unittest.TestCase):
    setUp = archive.Archive7Tests.setUp
    git = archive.ArchiveTests.git
    write = archive.ArchiveTests.write
    read = archive.ArchiveTests.read
    snapshot = archive.ArchiveTests.snapshot
    profile_input = archive.Archive7Tests.profile_input
    prepare7 = recovery_tests.ReviewRecoveryTests.prepare7
    current = recovery_tests.ReviewRecoveryTests.current
    controller = recovery_tests.ReviewRecoveryTests.controller
    restart_request = recovery_tests.ReviewRecoveryTests.restart_request
    final_record = checkpoint_tests.CheckpointTests.final_record
    def start_run(self):
        run = archive.Archive7Tests.prepare7(self)
        context = self.write('context.json', context10(self.final_record(run)))
        artifacts.register(run, [], context_input=context)
        return run, context

    def test_checkpoint_case_collision_across_calls_is_read_only_rejection(self):
        run, context = self.start_run()
        first = self.root / 'first' / 'Brief.json'
        second = self.root / 'second' / 'brief.json'
        for source in (first, second):
            source.parent.mkdir()
            source.write_text('{}', encoding='utf-8')
        artifacts.checkpoint(run, context_input=context, evidence_inputs=[first], phase='discovery')
        before = self.snapshot(run)
        with self.assertRaisesRegex(ValueError, 'case-insensitive|capitalization'):
            artifacts.checkpoint(run, context_input=context, evidence_inputs=[second], phase='discovery')
        self.assertEqual(self.snapshot(run), before)
        self.assertNotIn('checkpoint_transaction', self.read(run / 'cierre.json'))
        artifacts.validate(run)

    def test_foreign_restart_transfer_and_link_create_no_locks(self):
        foreign = self.root / 'foreign-parent' / 'run'
        foreign.mkdir(parents=True)
        owned = self.prepare7()
        operations = [
            lambda: artifacts.restart(foreign, **self.restart_request(owned)),
            lambda: artifacts.transfer_resources(foreign, owned, [], authority='User requested transfer',
                                                controller=self.controller()),
            lambda: artifacts._link_restart(foreign, owned, authority='User requested restart',
                                            controller=self.controller()),
        ]
        for operation in operations:
            with self.subTest(operation=operation):
                with self.assertRaises(ValueError):
                    operation()
                self.assertFalse((foreign.parent / '.review-locks').exists())

    def test_nested_malformed_final_has_structured_cli_error(self):
        run = self.prepare7()
        for coverage in ([], {'execution': []}):
            with self.subTest(coverage=coverage):
                malformed = self.write('malformed.json', {'schema_version': 10, 'coverage': coverage})
                before = self.snapshot(run)
                result = subprocess.run([sys.executable, '-B', '-X', 'utf8', str(Path(artifacts.__file__).parent),
                    'artifacts', 'retain', '--run-dir', str(run), '--input', str(malformed)],
                    capture_output=True, text=True, encoding='utf-8')
                self.assertEqual(result.returncode, 1)
                self.assertIn('error', json.loads(result.stderr))
                self.assertNotIn('Traceback', result.stderr)
                self.assertEqual(self.snapshot(run), before)

    def test_extended_unhashable_assignment_id_returns_errors(self):
        for identifier in ([1], {'a': 1}):
            with self.subTest(identifier=identifier):
                record = record10('extended')
                record['coverage']['execution']['plan'][0]['id'] = identifier
                self.assertTrue(review_execution.validate_profile_execution(record))
                self.assertTrue(artifacts.review_contract.validate(record))

    def test_historical_record_cannot_supply_native_context_as_selected_evidence(self):
        run = legacy_prepare(artifacts, self.repo, self.scope, output_root=self.output)
        context = self.write('context.json', {'source': 'legacy evidence'})
        before = self.snapshot(run)
        with self.assertRaisesRegex(ValueError, 'schema 10'):
            artifacts.retain(run, self.write('final.json', archive.record()),
                             evidence_inputs=[context], unavailable_reason='Not requested')
        self.assertEqual(self.snapshot(run), before)

    def test_schema1_and_schema2_refuse_restart_and_recovery_without_synthetic_id(self):
        for schema in (1, 2):
            with self.subTest(schema=schema):
                source = legacy_prepare(artifacts, self.repo, self.scope, output_root=self.output)
                manifest = self.read(source / 'cierre.json')
                manifest['schema_version'] = schema
                manifest.pop('run_id')
                manifest.pop('repository_identity')
                manifest.pop('trace')
                manifest['hashes'].pop('trazabilidad.jsonl')
                (source / 'trazabilidad.jsonl').unlink()
                if schema == 1:
                    measurements = {'schema_version': 1, 'status': 'unavailable', 'executions': [],
                                    'aggregate': {}, 'unavailable_reason': 'Not requested'}
                    (source / 'measurements.json').write_bytes(artifacts._json_bytes(measurements))
                    manifest['hashes']['measurements.json'] = artifacts._digest((source / 'measurements.json').read_bytes())
                artifacts._save_manifest(source, manifest, self.read(source / artifacts.MARKER))
                before = self.snapshot(source)
                inspected = recovery.inspect_run(source)
                self.assertEqual(inspected['integrity']['status'], 'unsupported_layout')
                for operation in (
                    lambda: artifacts.recover(source, controller=self.controller(),
                        authority='User requested recovery', current_inputs=self.current(source)),
                    lambda: artifacts.restart(source, **self.restart_request(source))):
                    with self.assertRaisesRegex(ValueError, 'unsupported_layout'):
                        operation()
                self.assertEqual(self.snapshot(source), before)

    def test_reserved_prepare_survives_baseexception_at_ownership_boundaries(self):
        for boundary in ('.review-restart-reservation.json', '.review-ownership.json', 'cierre.json'):
            with self.subTest(boundary=boundary):
                source = self.prepare7()
                request = self.restart_request(source)
                owner_ops = (lifecycle_ops if boundary == '.review-restart-reservation.json'
                             else transactions_ops)
                original = owner_ops.atomic_write
                def interrupt(path, data, **kwargs):
                    if Path(path).name == boundary and Path(path).parent != source:
                        raise KeyboardInterrupt('simulated process exit')
                    return original(path, data, **kwargs)
                with patch.object(owner_ops, 'atomic_write', side_effect=interrupt):
                    with self.assertRaises(KeyboardInterrupt):
                        artifacts.restart(source, **request)
                active = artifacts._active_restart_operation(source, self.read(source / 'cierre.json'))
                reserved_path = active['successor_run_dir']
                successor = artifacts.restart(source, **request)
                self.assertEqual(successor, reserved_path)
                artifacts.validate(successor)
                self.assertEqual(artifacts.restart(source, **request), successor)

    def test_recover_pending_restart_takes_source_lock_before_prepare(self):
        source = self.prepare7()
        request = self.restart_request(source)
        with patch.object(restart_ops, '_link_restart', side_effect=OSError('interrupted')):
            with self.assertRaises(OSError):
                artifacts.restart(source, **request)
        original_lock = artifacts._restart_lock
        from contextlib import contextmanager
        held = []
        @contextmanager
        def observed_lock(path, **kwargs):
            with original_lock(path, **kwargs):
                held.append(path)
                try:
                    yield
                finally:
                    held.pop()
        original_prepare = artifacts._prepare_from_restart_intent
        def assert_locked(path):
            self.assertTrue(held, 'recover prepared the reserved run outside the source lock')
            return original_prepare(path)
        with patch.object(restart_ops, '_restart_lock', side_effect=observed_lock), \
                patch.object(restart_ops, '_prepare_from_restart_intent', side_effect=assert_locked):
            result = artifacts.recover(source, controller=self.controller(), authority=request['authority'],
                                       current_inputs=request['current_inputs'])
        self.assertEqual(result['status'], 'restarted')

    def test_invalid_restart_sources_leave_no_durable_intent(self):
        source = self.prepare7()
        request = self.restart_request(source)
        request['current_inputs']['sources'] = {'docs/spec.md': 'a' * 64}
        before = self.snapshot(source)
        with self.assertRaisesRegex(ValueError, 'retained local evidence'):
            artifacts.restart(source, **request)
        self.assertEqual(self.snapshot(source), before)
        self.assertFalse((source.parent / '.restart-intents').exists())
        self.assertIsNone(artifacts._active_restart_operation(source, self.read(source / 'cierre.json')))

    def test_changed_repository_identity_rejected_before_restart_intent(self):
        source = self.prepare7()
        request = self.restart_request(source)
        self.git('remote', 'add', 'origin', 'https://example.test/changed/repository.git')
        with self.assertRaisesRegex(ValueError, 'repository'):
            artifacts.restart(source, **request)
        self.assertFalse((source.parent / '.restart-intents').exists())

    def test_adoption_cannot_contain_archive_root_before_restart_intent(self):
        session = Path(review_workspace.prepare(argparse.Namespace(
            repo=str(self.repo), ref='HEAD', mode='commit', role=['review'], include_untracked=[]))['session_dir'])
        source = Path(artifacts.prepare(self.repo, self.scope, '2.12.0', 'unknown',
            output_root=session / 'archive', profile_input=self.profile_input('standard')))
        request = self.restart_request(source)
        request['transfer_paths'] = [str(session)]
        with self.assertRaisesRegex(ValueError, 'retained archive|temporary'):
            artifacts.restart(source, **request)
        self.assertFalse((source.parent / '.restart-intents').exists())

    def test_foreign_repository_adoption_rejected_before_successor_or_intent(self):
        other = self.root / 'other-repo'
        other.mkdir()
        (other / 'code.txt').write_text('another repository', encoding='utf-8')
        for args in (['init'], ['config', 'user.email', 'fixtures@example.test'],
                     ['config', 'user.name', 'Fixture'], ['add', 'code.txt'], ['commit', '-m', 'fixture']):
            process = subprocess.run(['git', *args], cwd=other, capture_output=True, text=True)
            self.assertEqual(process.returncode, 0, process.stderr)
        session = Path(review_workspace.prepare(argparse.Namespace(
            repo=str(other), ref='HEAD', mode='commit', role=['review'], include_untracked=[]))['session_dir'])
        source = self.prepare7()
        request = self.restart_request(source)
        request['transfer_paths'] = [str(session)]
        before = self.snapshot(source)
        with self.assertRaisesRegex(ValueError, 'different repository'):
            artifacts.restart(source, **request)
        self.assertEqual(self.snapshot(source), before)
        self.assertFalse((source.parent / '.restart-intents').exists())
        self.assertEqual(len(list(self.output.rglob('cierre.json'))), 1)

    def test_reserved_prepare_recovers_actual_process_exit_with_staging_left(self):
        code = '''
import json, os, sys
from pathlib import Path
sys.path[:0] = sys.argv[1:3]
from script_test_support import archive_api
a = archive_api()
source = Path(sys.argv[3])
request = json.loads(Path(sys.argv[4]).read_text(encoding='utf-8'))
replace = os.replace
def interrupted(stage, target):
    if Path(target).name == sys.argv[5] and Path(target).parent != source:
        os._exit(73)
    return replace(stage, target)
os.replace = interrupted
a.restart(source, **request)
'''
        for boundary in ('.review-restart-reservation.json', 'cierre.json'):
            with self.subTest(boundary=boundary):
                source = self.prepare7()
                request = self.restart_request(source)
                request_path = self.write('hard-exit-request.json', request)
                process = subprocess.run([sys.executable, '-B', '-X', 'utf8', '-c', code,
                    str(Path(artifacts.__file__).parent), str(Path(__file__).resolve().parent),
                    str(source), str(request_path), boundary],
                    capture_output=True, text=True, encoding='utf-8')
                self.assertEqual(process.returncode, 73, process.stderr)
                active = artifacts._active_restart_operation(source, self.read(source / 'cierre.json'))
                self.assertTrue(list(Path(active['successor_run_dir']).glob('*.tmp')))
                successor = artifacts.restart(source, **request)
                self.assertEqual(successor, active['successor_run_dir'])
                self.assertEqual(list(Path(successor).glob('*.tmp')), [])
                artifacts.validate(successor)

    def test_abandon_unprepared_restart_is_authorized_durable_and_idempotent(self):
        source = self.prepare7()
        request = self.restart_request(source)
        with patch.object(restart_ops, '_prepare_from_restart_intent', side_effect=OSError('before prepare')):
            with self.assertRaises(OSError):
                artifacts.restart(source, **request)
        active = artifacts._active_restart_operation(source, self.read(source / 'cierre.json'))
        kwargs = {'intent_path': active['intent_path'], 'controller': self.controller(),
                  'authority': 'User requested abandonment', 'reason': 'Inputs must be collected again'}
        with self.assertRaises(ValueError):
            artifacts.abandon_restart(source, **dict(kwargs, authority=None))
        receipt = artifacts.abandon_restart(source, **kwargs)
        self.assertEqual(receipt['operation_id'], active['operation_id'])
        before = self.snapshot(source)
        self.assertEqual(artifacts.abandon_restart(source, **kwargs), receipt)
        self.assertEqual(self.snapshot(source), before)
        self.assertFalse(Path(active['successor_run_dir']).exists())
        self.assertIsNone(artifacts._active_restart_operation(source, self.read(source / 'cierre.json')))
        with self.assertRaisesRegex(ValueError, 'abandoned'):
            artifacts.restart(source, **request)
        request['profile_input']['reason'] = 'New scope evaluation after explicit abandonment'
        self.assertTrue(Path(artifacts.restart(source, **request)).is_dir())

    def test_abandon_cannot_orphan_prepared_successor(self):
        source = self.prepare7()
        with patch.object(restart_ops, '_link_restart', side_effect=OSError('after prepare')):
            with self.assertRaises(OSError):
                artifacts.restart(source, **self.restart_request(source))
        active = artifacts._active_restart_operation(source, self.read(source / 'cierre.json'))
        before = self.snapshot(source)
        with self.assertRaisesRegex(ValueError, 'prepared successor|recover'):
            artifacts.abandon_restart(source, intent_path=active['intent_path'], controller=self.controller(),
                authority='User requested abandonment', reason='Stop this restart')
        self.assertEqual(self.snapshot(source), before)

    def test_pending_restart_is_visible_in_inspect_and_lookup(self):
        source = self.prepare7()
        request = self.restart_request(source)
        with patch.object(restart_ops, '_link_restart', side_effect=OSError('interrupted')):
            with self.assertRaises(OSError):
                artifacts.restart(source, **request)
        inspected = recovery.inspect_run(source, current_inputs=self.current(source))
        restart = next(row for row in inspected['pending_transaction'] if row['kind'] == 'restart')
        self.assertTrue(restart['operation_id'])
        self.assertTrue(restart['successor_run_dir'])
        self.assertNotIn('continue', [row['action'] for row in inspected['actions']])
        candidates = recovery.find_candidates(self.repo, self.read(source / 'cierre.json')['scope'],
                                              archive_root=self.output, current_inputs=self.current(source))
        candidate = next(row for row in candidates['candidates'] if row['run_dir'] == str(source))
        self.assertTrue(any(row['kind'] == 'restart' for row in candidate['pending_transaction']))

    def registered_session(self, profile='deep'):
        session = Path(review_workspace.prepare(argparse.Namespace(
            repo=str(self.repo), ref='HEAD', mode='commit', role=['review'], include_untracked=[]))['session_dir'])
        source = self.prepare7(profile)
        history = self.read(source / 'cierre.json')['profile_history']
        final = record10(profile)
        context = context10(final)
        context['profile_history'] = history
        context['profile_reference'] = history[-1]['reference']
        context['review_inputs'] = self.read(source / 'cierre.json')['review_inputs']
        artifacts.register(source, [str(session)], context_input=self.write('claim-context.json', context))
        return source, session, context

    def test_missing_session_diagnostics_match_recover_and_resume(self):
        source, session, _ = self.registered_session()
        workspace = self.read(session / 'manifest.json')['workspaces'][0]['path']
        self.git('worktree', 'remove', '--force', workspace)
        shutil.rmtree(session)
        artifacts.pause(source, authority='User requested pause', reason='Explicit pause', phase='discovery')
        inspected = recovery.inspect_run(source, current_inputs=self.current(source))
        self.assertEqual(inspected['resources'][0]['availability'], 'missing_unknown')
        result = artifacts.recover(source, controller=self.controller(), authority='User requested recovery',
                                   current_inputs=self.current(source))
        self.assertNotIn('continue', [row['action'] for row in result['actions']])
        self.assertNotIn('resume', [row['action'] for row in inspected['actions']])
        before = self.snapshot(source)
        with self.assertRaisesRegex(ValueError, 'missing_unknown|restart'):
            artifacts.resume(source, controller=self.controller(), authority='User requested continuation',
                             current_inputs=self.current(source))
        self.assertEqual(self.snapshot(source), before)

    def test_superseded_source_can_cleanup_its_remaining_claim(self):
        source, session, _ = self.registered_session()
        request = self.restart_request(source)
        request['current_inputs']['scope']['head'] = 'b' * 40
        successor = artifacts.restart(source, **request)
        self.assertEqual(self.read(source / 'cierre.json')['operation']['disposition'], 'superseded')
        review_workspace.cleanup(argparse.Namespace(manifest=str(session / 'manifest.json'), run_dir=str(source)))
        self.assertFalse(session.exists())
        self.assertTrue(self.read(source / 'cierre.json')['cleanup_receipts'])
        artifacts.validate(successor)

    def test_started_assignment_cannot_be_affected_by_selection(self):
        source, session, context = self.registered_session()
        reference = context['execution_plan'][0]['reference']
        artifacts.record_event(source, self.write('started.json', {'kind': 'agent', 'status': 'started',
            'summary': 'Observed dispatch', 'executor': {'name': 'observed-worker', 'provider_id': None},
            'evidence': [reference]}))
        candidate = selection_input('standard', phase='discovery', affected_assignments=['D1'],
            reason='Only one independent flow remains in the verified scope', reference='evidence/scope.md#decision')
        before = self.snapshot(source)
        with self.assertRaisesRegex(ValueError, 'started assignment'):
            artifacts.select_profile(source, candidate)
        self.assertEqual(self.snapshot(source), before)
        review_workspace.cleanup(argparse.Namespace(manifest=str(session / 'manifest.json'), run_dir=str(source)))

    def test_superseded_assignment_cannot_start(self):
        source, session, context = self.registered_session()
        candidate = selection_input('standard', 'explicit', phase='discovery', affected_assignments=['D2'],
            reason='Only one independent flow remains in the verified scope',
            reference='evidence/context.json#profile_history/1/profile')
        manifest = artifacts.select_profile(source, candidate)
        context['profile'] = 'standard'
        context['profile_history'] = manifest['profile_history']
        context['profile_reference'] = manifest['profile_history'][-1]['reference']
        row = next(row for row in context['execution_plan'] if row['id'] == 'D2')
        row.update(required=False, superseded_by='S002')
        artifacts.register(source, [], context_input=self.write('updated-context.json', context))
        before = self.snapshot(source)
        active_reference = context['execution_plan'][0]['reference']
        for status in ('started', 'completed'):
            for evidence in ([row['reference']], [active_reference, row['reference']]):
                with self.subTest(status=status, evidence=evidence):
                    with self.assertRaisesRegex(ValueError, 'superseded|active|required'):
                        event = {'kind': 'agent', 'status': status,
                                 'summary': 'Rejected assignment work', 'evidence': evidence}
                        if status == 'started':
                            event['executor'] = {'name': 'observed-worker', 'provider_id': None}
                        artifacts.record_event(source, self.write('inactive-start.json', event))
                    self.assertEqual(self.snapshot(source), before)
        review_workspace.cleanup(argparse.Namespace(manifest=str(session / 'manifest.json'), run_dir=str(source)))

    def test_extracted_documented_archive8_commands_execute_end_to_end(self):
        skill = Path(artifacts.__file__).resolve().parents[1]
        document = (skill / 'docs/examples/archive8-lifecycle.md').read_text(encoding='utf-8')
        blocks = dict(re.findall(r'```sh\n# ccr-example: ([\w-]+)\n(.*?)\n```', document, re.S))
        session = self.root / 'owned-session'
        evidence = session / 'evidence'
        evidence.mkdir(parents=True)
        def write(name, value):
            path = evidence / name
            path.write_text(json.dumps(value), encoding='utf-8')
            return path
        write('scope.json', self.read(self.scope))
        write('profile-selection.json', self.profile_input('standard'))
        index_path = write('reference-index.json', {'schema_version': 1, 'aliases': {}, 'inputs': []})
        write('current-inputs.json', {
            'scope': self.read(self.scope),
            'sources': {'evidence/reference-index.json': hashlib.sha256(index_path.read_bytes()).hexdigest()},
            'source_set_complete': True,
        })
        substitutions = {'/absolute/skill': skill, '/absolute/project': self.repo,
                         '/absolute/owned/session': session, '/absolute/archive': self.output}
        def execute(name):
            command = blocks[name]
            self.assertNotIn('\\\\\n', command, 'Documented command uses a literal backslash instead of continuation')
            command = command.replace('\\\n', '')
            # Substitute complete tokens after POSIX parsing; no shell quoting of
            # local Windows paths and no independently constructed CLI flags.
            tokens = shlex.split(command)
            args = [sys.executable]
            for token in tokens[1:]:
                for prefix, path in sorted(substitutions.items(), key=lambda item: -len(item[0])):
                    if token == prefix or token.startswith(prefix + '/'):
                        token = str(path) + token[len(prefix):]
                        break
                args.append(token)
            result = subprocess.run(args, capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(result.returncode, 0, name + ': ' + result.stderr)
            return json.loads(result.stdout)
        source = Path(execute('prepare')['run_dir'])
        substitutions['/absolute/returned/run'] = source
        from profile_topology_fixtures import record12
        final = record12('standard', 'automatic', discovery=1)
        # This case executes the maintained current-producer example with no
        # executed checks; frozen record10 scenarios remain unchanged above.
        final['checks'] = []
        final.update(scope=self.read(self.scope), review_id='CR-' + self.read(source / 'cierre.json')['run_id'])
        final['description'] = {'status': 'not_applicable', 'identity': None, 'details': ''}
        def refresh_context():
            final['coverage']['execution']['profile_history'] = self.read(source / 'cierre.json')['profile_history']
            context = context10(final)
            context['review_inputs'] = self.read(source / 'cierre.json')['review_inputs']
            context['reference_index'] = 'evidence/reference-index.json'
            write('context.json', context)
        refresh_context()
        execute('preflight-register')
        execute('register')
        execute('preflight-discovery')
        from recovery_fixtures import source_events
        for event in source_events(final):
            if event['kind'] == 'profile':
                continue
            raw = {key: event[key] for key in ('kind', 'status', 'evidence')}
            raw.update(summary='Observed synthetic step from documented CLI test',
                       provenance={'kind': 'tool', 'source': 'documented CLI fixture'})
            if event.get('actor'):
                raw['actor'] = dict(event['actor'], kind='agent')
            if event.get('executor'):
                raw['executor'] = event['executor']
            write('dispatch-event.json', raw)
            execute('record-event')
        write('briefs.json', {row['id']: {'question': 'Check invariant'} for row in final['coverage']['execution']['plan']})
        write('results.json', {row['id']: {'result': 'reviewed'} for row in final['coverage']['execution']['plan']})
        write('final-review.json', final)
        checkpoint = execute('checkpoint')
        self.assertEqual(checkpoint['gate_errors'], [])
        execute('preflight-retain')
        execute('retain')
        execute('validate-retained')
        shutil.rmtree(session)
        execute('close')
        self.assertEqual(execute('validate-complete')['state'], 'complete')

    def test_extracted_recovery_restart_example_executes(self):
        skill = Path(artifacts.__file__).resolve().parents[1]
        document = (skill / 'references/archive/recovery.md').read_text(encoding='utf-8')
        command = next(block for block in re.findall(r'```(?:text|sh)\n(.*?)\n```', document, re.S)
                       if block.splitlines()[0].startswith('python /absolute/skill/scripts artifacts restart ')
                       and '--harness-source-input' in block)
        self.assertNotIn('\\\\\n', command)
        source = self.prepare7()
        request = self.restart_request(source)
        inputs = self.root / 'example-inputs'
        inputs.mkdir()
        values = {'profile-selection.json': request['profile_input'], 'controller.json': request['controller'],
                  'authority.json': {'authority': request['authority']}, 'current-inputs.json': request['current_inputs'],
                  'harness-source.json': {'kind': 'user', 'reference': 'User observed desktop'}}
        for name, value in values.items():
            (inputs / name).write_text(json.dumps(value), encoding='utf-8')
        tokens = shlex.split(command.replace('\\\n', ''))
        replacements = {'/absolute/skill': skill, '/absolute/archive/exact-source-run': source,
                        '/absolute/owned/session': inputs}
        args = [sys.executable]
        for token in tokens[1:]:
            for prefix, path in replacements.items():
                if token == prefix or token.startswith(prefix + '/'):
                    token = str(path) + token[len(prefix):]
                    break
            args.append(token)
        result = subprocess.run(args, capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(Path(json.loads(result.stdout)['run_dir']).is_dir())


if __name__ == '__main__':
    unittest.main()
