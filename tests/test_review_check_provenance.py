"""Schema 9 separates checks from observed isolated execution provenance."""
import copy
import argparse
import importlib
import json
from pathlib import Path
import shlex
import sys
import unittest
from unittest.mock import patch

from test_review_contract import contract
from test_review_traceability_contract import check
import test_review_execution_policy as policy_tests
from test_review_delivery import delivery
from ccr.execution import checks as review_check_receipts
from script_test_support import workspace_api
review_workspace = workspace_api()
from ccr.contracts import provenance as check_provenance

record8 = policy_tests.record8


def record9(profile='focused', selection='explicit'):
    value = record8(profile, selection)
    value['schema_version'] = 9
    return value


class CheckProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.provenance = check_provenance

    def test_local_completed_check_requires_executor(self):
        for status in ('passed', 'failed'):
            for identity in (None, '', '   '):
                value = record9()
                value['checks'] = [dict(check(), status=status, execution=dict(kind='local', executor=identity))]
                self.assertTrue(any('executor' in error for error in self.provenance.validate_check_execution(value)))
                value['checks'][0]['execution']['executor'] = 'X1'
                self.assertEqual(self.provenance.validate_check_execution(value), [])
                self.assertTrue(self.provenance.validate_check_sources(value, []))

    def test_nonlocal_and_unexecuted_checks_do_not_invent_executors(self):
        for kind, status in [('static', 'passed'), ('external', 'passed'), ('reused', 'passed'),
                             ('local', 'blocked'), ('local', 'not_run')]:
            value = record9()
            value['checks'] = [dict(check(), status=status, reused=kind == 'reused',
                reference='https://example.test/ci/123', execution=dict(kind=kind, executor=None))]
            self.assertEqual(self.provenance.validate_check_execution(value), [])
            self.assertEqual(self.provenance.validate_check_sources(value, []), [])
            if kind != 'local':
                value['checks'][0]['execution']['executor'] = 'X1'
                self.assertTrue(self.provenance.validate_check_execution(value))

    def test_reuse_and_external_source_are_explicit(self):
        value = record9()
        for kind, reused in [('local', True), ('reused', False)]:
            value['checks'] = [dict(check(), reused=reused, execution=dict(kind=kind, executor='X1' if kind == 'local' else None))]
            self.assertTrue(self.provenance.validate_check_execution(value))
        value['checks'] = [dict(check(), execution=dict(kind='external', executor=None))]
        self.assertTrue(self.provenance.validate_check_execution(value))
        value['checks'][0]['reference'] = 'https://example.test/ci/123'
        self.assertEqual(self.provenance.validate_check_execution(value), [])

    def test_executor_binding_covers_head_baseline_and_snapshot(self):
        value = record9()
        value['checks'] = [dict(check(), execution=dict(kind='local', executor='X1'))]
        for revision in (value['scope']['head'], value['scope']['base']):
            value['checks'][0]['revision'] = revision
            executors = [dict(executor='X1', revision=revision, snapshot=None)]
            self.assertEqual(self.provenance.validate_check_sources(value, executors), [])
            executors[0]['revision'] = 'unrelated'
            self.assertTrue(self.provenance.validate_check_sources(value, executors))
        value['scope']['snapshot'] = 'snapshot-123'
        value['checks'][0]['revision'] = 'snapshot-123'
        executors = [dict(executor='X1', revision=value['scope']['head'], snapshot='snapshot-123')]
        self.assertEqual(self.provenance.validate_check_sources(value, executors), [])
        executors[0]['snapshot'] = 'another-snapshot'
        self.assertTrue(self.provenance.validate_check_sources(value, executors))
        value['checks'][0]['execution']['executor'] = 'unknown'
        self.assertTrue(self.provenance.validate_check_sources(value, executors))

    def test_schema9_shape_and_legacy_checks(self):
        value = record9()
        value['checks'] = [dict(check(), execution=dict(kind='static', executor=None))]
        self.assertEqual(contract.validate(value), [])
        del value['checks'][0]['execution']
        self.assertTrue(contract.validate(value))
        value = record8()
        value['checks'] = [check()]
        self.assertEqual(contract.validate(value), [])

    def test_snapshot_executor_cannot_claim_clean_revision(self):
        value = record9()
        value['scope']['snapshot'] = 'snapshot-123'
        for revision in (value['scope']['base'], value['scope']['head']):
            with self.subTest(revision=revision):
                value['checks'] = [dict(check(), revision=revision, execution=dict(kind='local', executor='X1'))]
                self.assertEqual(contract.validate(value), [])
                executors = [dict(executor='X1', revision=revision, snapshot='snapshot-123')]
                self.assertTrue(self.provenance.validate_check_sources(value, executors))


class ArchiveCheckProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.policy = policy_tests.ArchiveExecutionPolicyTests()
        self.addCleanup(self.policy.doCleanups)
        self.policy.setUp()
        self.fixture = self.policy.fixture
        self.artifacts = self.policy.artifacts

    def prepared(self, profile='focused'):
        return self.policy.prepared(profile)

    def test_schema10_archive_binds_checks_before_writing(self):
        run, value, context, inputs = self.prepared()
        value['checks'] = [dict(check(), execution=dict(kind='local', executor='X1'))]
        before = self.fixture.snapshot(run)
        with self.assertRaises(ValueError):
            self.artifacts.retain(run, self.fixture.write('final.json', value), context_input=context, evidence_inputs=inputs)
        self.assertEqual(before, self.fixture.snapshot(run))
        value['checks'][0]['execution'] = dict(kind='static', executor=None)
        self.artifacts.retain(run, self.fixture.write('final.json', value), context_input=context, evidence_inputs=inputs)
        self.assertTrue(self.artifacts.validate(run, require_retained=True)['retained'])

    def test_retention_preflight_and_gate_verify_selected_receipt_bytes(self):
        repo = self.fixture.repo
        (repo / 'source.txt').write_text('baseline', encoding='utf-8')
        self.artifacts._git(repo, 'add', 'source.txt')
        self.artifacts._git(repo, '-c', 'user.name=Test', '-c', 'user.email=test@example.test',
                            'commit', '-m', 'baseline')
        head = self.artifacts._git(repo, 'rev-parse', 'HEAD')
        from recovery_fixtures import record10
        source = record10('focused')
        source['scope'].update(head=head, base=head)
        with patch('recovery_fixtures.record10', return_value=source):
            run, value, context_file, evidence_inputs = self.prepared('focused')

        workspace_manifest = review_workspace.prepare(argparse.Namespace(
            repo=str(repo), mode='commit', ref=head, role=['executor'], include_untracked=[]))
        session = Path(workspace_manifest['session_dir'])
        evidence_dir = session / 'evidence'
        evidence_dir.mkdir()
        workspace = Path(workspace_manifest['workspaces'][0]['path'])
        context = json.loads(context_file.read_text(encoding='utf-8'))
        context['executors'] = [dict(executor='X1', method='git-worktree', workspace=str(workspace),
            revision=head, snapshot=None, manifest=workspace_manifest['manifest'],
            dependencies='none', dependency_reason='No dependencies')]
        context_file = self.fixture.write('context-with-receipt-executor.json', context)
        (evidence_dir / 'context.json').write_text(
            json.dumps(context, ensure_ascii=False), encoding='utf-8')
        self.artifacts.register(run, [str(session)], context_input=context_file)

        output_dir = evidence_dir / 'attempt-1'
        argv = [sys.executable, '-c', "print('verified')"]
        receipt = review_check_receipts.capture_check(
            check_id='C001', argv=argv, command=shlex.join(argv), cwd=str(workspace),
            executor_workspace=str(workspace), revision=head, executor='X1',
            output_dir=str(output_dir))
        receipt_reference = review_check_receipts.receipt_reference('C001', output_dir)
        value['checks'] = [dict(check(), command=shlex.join(argv), revision=head,
            reference=receipt_reference,
            execution=dict(kind='local', executor='X1'))]
        final_file = self.fixture.write('receipt-final.json', value)
        receipt_path = output_dir / Path(receipt_reference).name
        stdout_path = output_dir / Path(receipt['stdout']['reference']).name
        stderr_path = output_dir / Path(receipt['stderr']['reference']).name
        selected = evidence_inputs + [receipt_path, stdout_path, stderr_path]

        preflight, code = self.artifacts.preflight_run(
            run, context_file, phase='retain', input_file=final_file, evidence_inputs=selected)
        self.assertEqual(code, 0, preflight)
        self.assertTrue(preflight['ready'], preflight)

        before = self.fixture.snapshot(run)
        original_stdout = stdout_path.read_bytes()
        stdout_path.write_bytes(original_stdout + b'tampered')
        with self.assertRaisesRegex(ValueError, 'receipt|stream|digest|byte count'):
            self.artifacts.retain(run, final_file, context_input=context_file,
                                  evidence_inputs=selected, temporary_paths=[str(session)])
        self.assertEqual(before, self.fixture.snapshot(run))
        stdout_path.write_bytes(original_stdout)

        self.artifacts.retain(run, final_file, context_input=context_file,
                              evidence_inputs=selected, temporary_paths=[str(session)])
        self.assertTrue(self.artifacts.validate(run, require_retained=True)['retained'])

    def test_closed_schema10_source_survives_executor_cleanup(self):
        from recovery_fixtures import record10
        repo = self.fixture.repo
        (repo / 'code.txt').write_text('baseline', encoding='utf-8')
        self.artifacts._git(repo, 'add', 'code.txt')
        self.artifacts._git(repo, '-c', 'user.name=Test', '-c', 'user.email=test@example.test', 'commit', '-m', 'baseline')
        head = self.artifacts._git(repo, 'rev-parse', 'HEAD')
        source = record10()
        source['scope'].update(head=head, base=head)
        with patch('recovery_fixtures.record10', return_value=source):
            run, value, context, inputs = self.prepared()
        workspace = repo / '.worktrees' / 'executor'
        self.artifacts._git(repo, 'worktree', 'add', '--detach', str(workspace), head)
        captured = self.artifacts.read_json(context)
        captured['executors'] = [dict(executor='X1', method='git-worktree', workspace=str(workspace),
            revision=head, snapshot=None, manifest=None, dependencies='none', dependency_reason='No dependencies')]
        context = self.fixture.write('context.json', captured)
        value['checks'] = [dict(check(), revision=head, execution=dict(kind='local', executor='X1'))]
        self.artifacts.retain(run, self.fixture.write('final.json', value), context_input=context,
                              evidence_inputs=inputs, temporary_paths=[str(workspace)])
        self.artifacts._git(repo, 'worktree', 'remove', str(workspace))
        self.artifacts.close(run, cleanup='complete')
        self.assertTrue(self.artifacts.validate(run, require_retained=True)['retained'])
        self.assertFalse(workspace.exists())
        portable = delivery._Projection(value, self.artifacts.read_json(run / 'cierre.json'), repo, 'a' * 64).value(value)
        self.assertEqual(portable['checks'][0]['execution']['executor'], 'X1')

    def test_schema10_delivery_keeps_execution_ids_and_public_report_omits_workspaces(self):
        run, value, context, inputs = self.prepared()
        value['checks'] = [dict(check(), execution=dict(kind='static', executor=None))]
        self.artifacts.retain(run, self.fixture.write('final.json', value), context_input=context, evidence_inputs=inputs)
        self.artifacts.close(run, cleanup='not_needed')
        for mode in ('full', 'brief'):
            destination = delivery.deliver(run, mode, self.fixture.repo, output_root=self.fixture.root / mode)
            text = (Path(destination) / ('informe.md' if mode == 'full' else 'resumen.md')).read_text(encoding='utf-8')
            self.assertNotIn(str(self.fixture.root), text)
            self.assertIn('C001', text)
        portable = self.artifacts.read_json(Path(self.fixture.root / 'full').rglob('review.json').__next__())
        self.assertEqual(portable['checks'][0]['execution'], dict(kind='static', executor=None))

    def test_close_rechecks_execution_sources_before_completion(self):
        run, value, context, inputs = self.prepared()
        value['checks'] = [dict(check(), execution=dict(kind='static', executor=None))]
        self.artifacts.retain(run, self.fixture.write('final.json', value), context_input=context,
                              evidence_inputs=inputs)
        value['checks'][0]['execution'] = dict(kind='local', executor='missing')
        data = self.artifacts._json_bytes(value)
        self.artifacts.atomic_write(run / 'review.json', data)
        _, manifest, marker = self.artifacts._load_run(run)
        manifest['hashes']['review.json'] = self.artifacts._digest(data)
        self.artifacts._save_manifest(run, manifest, marker)
        before = self.fixture.snapshot(run)
        with self.assertRaises(ValueError):
            self.artifacts.close(run, cleanup='not_needed')
        self.assertEqual(before, self.fixture.snapshot(run))

    def test_expected_schema8_rejected_but_legacy_read_remains_valid(self):
        run, value, context, inputs = self.policy.prepared('focused')
        before = self.fixture.snapshot(run)
        with self.assertRaises(ValueError):
            self.artifacts.retain(run, self.fixture.write('final.json', value), context_input=context,
                                  evidence_inputs=inputs, expected_schema=9)
        self.assertEqual(before, self.fixture.snapshot(run))
        self.artifacts.retain(run, self.fixture.write('final.json', value), context_input=context, evidence_inputs=inputs)
        self.artifacts.close(run, cleanup='not_needed')
        self.assertTrue(self.artifacts.validate(run, require_complete=True)['retained'])
        delivery.deliver(run, 'brief', self.fixture.repo, output_root=self.fixture.root / 'legacy')
