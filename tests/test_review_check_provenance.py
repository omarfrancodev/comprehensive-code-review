"""Schema 9 separates checks from observed isolated execution provenance."""
import copy
import importlib
from pathlib import Path
import unittest
from unittest.mock import patch

from test_review_contract import contract
from test_review_traceability_contract import check
import test_review_execution_policy as policy_tests
from test_review_delivery import delivery

record8 = policy_tests.record8


def record9(profile='focused', selection='explicit'):
    value = record8(profile, selection)
    value['schema_version'] = 9
    return value


class CheckProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.provenance = importlib.import_module('review_check_provenance')

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


class ArchiveCheckProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.policy = policy_tests.ArchiveExecutionPolicyTests()
        self.addCleanup(self.policy.doCleanups)
        self.policy.setUp()
        self.fixture = self.policy.fixture
        self.artifacts = self.policy.artifacts

    def prepared(self):
        run, value, context, inputs = self.policy.prepared('focused')
        value['schema_version'] = 9
        return run, value, context, inputs

    def test_schema9_archive_binds_checks_before_writing(self):
        run, value, context, inputs = self.prepared()
        value['checks'] = [dict(check(), execution=dict(kind='local', executor='X1'))]
        before = self.fixture.snapshot(run)
        with self.assertRaises(ValueError):
            self.artifacts.retain(run, self.fixture.write('final.json', value), context_input=context, evidence_inputs=inputs)
        self.assertEqual(before, self.fixture.snapshot(run))
        value['checks'][0]['execution'] = dict(kind='static', executor=None)
        self.artifacts.retain(run, self.fixture.write('final.json', value), context_input=context, evidence_inputs=inputs)
        self.assertTrue(self.artifacts.validate(run, require_retained=True)['retained'])

    def test_closed_schema9_source_survives_executor_cleanup(self):
        repo = self.fixture.repo
        (repo / 'code.txt').write_text('baseline', encoding='utf-8')
        self.artifacts._git(repo, 'add', 'code.txt')
        self.artifacts._git(repo, '-c', 'user.name=Test', '-c', 'user.email=test@example.test', 'commit', '-m', 'baseline')
        head = self.artifacts._git(repo, 'rev-parse', 'HEAD')
        source = record8()
        source['scope'].update(head=head, base=head)
        with patch('test_review_execution_policy.record8', return_value=source):
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

    def test_schema9_delivery_keeps_execution_ids_and_public_report_omits_workspaces(self):
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
