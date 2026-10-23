"""Phase preflight and assignment barrier contracts."""
import copy
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ccr.contracts import preflight
from script_test_support import archive_api
review_artifacts = archive_api()
from ccr.archive import trace as review_trace

from recovery_fixtures import (context10, current_inputs, historical_prepare,
                               record10, selection_input)


class PreflightTests(unittest.TestCase):
    def test_completed_without_assignment_is_rejected(self):
        event = review_trace.event_input({'kind': 'discovery', 'status': 'completed',
            'summary': 'Observed completion', 'evidence': []})
        issues = preflight.validate_assignment_event(event, [])
        self.assertIn('missing_assignment', {i['code'] for i in issues})

    def _guided_preflight_inputs(self, *, state='prepared', captured_notes=False, changed_notes=False):
        record = record10()
        context = context10(record)
        notes = b'notes-v1'
        index = {'schema_version': 1, 'aliases': {}, 'inputs': [
            {'reference': 'evidence/notes.json', 'purpose': 'notes',
             'sha256': hashlib.sha256(notes).hexdigest()}]}
        index_bytes = json.dumps(index, sort_keys=True, separators=(',', ':')).encode()
        context['reference_index'] = 'evidence/reference-index.json'
        context['review_inputs']['sources'] = {
            'evidence/reference-index.json': hashlib.sha256(index_bytes).hexdigest()}
        if captured_notes:
            context['review_inputs']['sources']['evidence/notes.json'] = hashlib.sha256(notes).hexdigest()
        manifest = {'schema_version': 8, 'layout_version': 2, 'state': state,
                    'scope': record['scope'], 'review_inputs': context['review_inputs'],
                    'profile_history': context['profile_history'],
                    'logical_scope': {'identity': context['review_inputs']['logical_scope_identity']},
                    'assignment_registry': context['execution_plan']}
        sources = {'evidence/context.json': json.dumps(context).encode(),
                   'evidence/reference-index.json': index_bytes,
                   'evidence/notes.json': b'changed' if changed_notes else notes}
        return manifest, context, record, sources

    def test_prepared_material_capture_fails_before_dispatch(self):
        manifest, context, record, sources = self._guided_preflight_inputs()
        before = copy.deepcopy((manifest, context, sources))
        result = preflight.validate_preflight(
            phase='register', manifest=manifest, logical_scope=manifest['logical_scope'],
            selection=None, context=context, record=None, sources=sources)
        self.assertFalse(result['ready'])
        self.assertIn('evidence/notes.json', {issue['reference'] for issue in result['issues']})
        self.assertEqual((manifest, context, sources), before)

    def test_retain_preflight_reports_index_source_errors(self):
        manifest, context, record, sources = self._guided_preflight_inputs(
            state='processing', captured_notes=True, changed_notes=True)
        record['schema_version'] = 8
        result = preflight.validate_preflight(
            phase='retain', manifest=manifest, logical_scope=manifest['logical_scope'],
            selection=None, context=context, record=record, sources=sources)
        self.assertFalse(result['ready'])
        self.assertIn('evidence/notes.json', {issue['reference'] for issue in result['issues']})

    def test_prepare_checks_syntax_without_future_results(self):
        selected = selection_input()
        args = dict(phase='prepare', manifest=None, logical_scope=None,
                    context=None, record=None, sources={})
        self.assertEqual(preflight.validate_preflight(selection=selected, **args),
                         {'phase': 'prepare', 'ready': True, 'issues': []})
        result = preflight.validate_preflight(selection=dict(selected,
            reference='https://example.test/pr/1'), **args)
        self.assertFalse(result['ready'])
        self.assertIn('invalid_reference', {i['code'] for i in result['issues']})


class PreflightIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.git('init')
        self.git('config', 'user.email', 'fixture@example.test')
        self.git('config', 'user.name', 'Fixture')
        (self.repo / 'source.txt').write_text('fixture', encoding='utf-8')
        self.git('add', 'source.txt')
        self.git('commit', '-m', 'fixture')
        self.scope = record10()['scope']
        self.scope_file = self.write('scope.json', self.scope)
        self.archive_root = self.root / 'archive'

    def git(self, *args):
        result = subprocess.run(['git', *args], cwd=self.repo,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def write(self, name, value):
        path = self.root / name
        path.write_text(json.dumps(value), encoding='utf-8')
        return path

    def prepare(self, **kwargs):
        return Path(review_artifacts.prepare(
            self.repo, self.scope_file, '2.13.0', 'codex',
            output_root=kwargs.pop('output_root', self.archive_root),
            profile_input=kwargs.pop('profile_input', selection_input()),
            current_inputs=kwargs.pop('current_inputs',
                current_inputs(self.scope, source_set_complete=True)), **kwargs))

    def snapshot(self, root):
        return {str(path.relative_to(root)): path.read_bytes()
                for path in root.rglob('*') if path.is_file()}

    def context_file(self, run, *, identity=None, plan=None):
        manifest = review_artifacts.read_json(run / 'cierre.json')
        context = context10(record10())
        context['profile_history'] = manifest['profile_history']
        context['profile'] = manifest['profile_history'][-1]['profile']
        context['profile_reference'] = manifest['profile_history'][-1]['reference']
        context['execution_plan'] = (manifest['assignment_registry']
                                     if plan is None else plan)
        context['review_inputs'] = dict(manifest['review_inputs'])
        if identity is not None:
            context['review_inputs']['logical_scope_identity'] = identity
        return self.write('context.json', context)

    def invoke_preflight(self, run, context_file, phase='register', evidence_inputs=()):
        command = [
            sys.executable, str(Path(__file__).resolve().parents[1] / 'scripts'),
            'artifacts', 'preflight',
            '--run-dir', str(run), '--context-input', str(context_file),
            '--phase', phase]
        for evidence in evidence_inputs:
            command.extend(['--evidence-input', str(evidence)])
        return subprocess.run(command, capture_output=True, text=True, encoding='utf-8')

    def test_prepare_rejects_invalid_profile_reference_before_archive_creation(self):
        with self.assertRaises(ValueError):
            self.prepare(profile_input=selection_input(
                reference='https://example.test/pr/1'))
        self.assertFalse(self.archive_root.exists())

    def test_record_event_rejects_completed_work_without_assignment_identity(self):
        run = self.prepare()
        event_file = self.write('event.json', {
            'kind': 'discovery', 'status': 'completed',
            'summary': 'Observed completion', 'evidence': []})
        before = self.snapshot(run)
        with self.assertRaisesRegex(ValueError, 'no assignment brief reference'):
            review_artifacts.record_event(run, event_file)
        self.assertEqual(self.snapshot(run), before)

    def test_preflight_cli_is_read_only_and_reports_ready(self):
        run = self.prepare()
        context = self.context_file(run)
        before = self.snapshot(self.root)
        completed = self.invoke_preflight(run, context)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertTrue(json.loads(completed.stdout)['ready'])
        discovery = self.invoke_preflight(run, context, phase='discovery')
        self.assertEqual(discovery.returncode, 1)
        self.assertIn('missing_assignment', {issue['code']
            for issue in json.loads(discovery.stdout)['issues']})
        self.assertEqual(self.snapshot(self.root), before)

    def test_prepared_material_capture_fails_before_dispatch_without_writes(self):
        notes = b'notes-v1'
        index = {'schema_version': 1, 'aliases': {}, 'inputs': [
            {'reference': 'evidence/notes.json', 'purpose': 'notes',
             'sha256': hashlib.sha256(notes).hexdigest()}]}
        index_bytes = json.dumps(index, sort_keys=True, separators=(',', ':')).encode()
        index_path = self.root / 'reference-index.json'
        notes_path = self.root / 'notes.json'
        index_path.write_bytes(index_bytes)
        notes_path.write_bytes(notes)
        run = self.prepare(current_inputs=current_inputs(self.scope, {
            'evidence/reference-index.json': hashlib.sha256(index_bytes).hexdigest()},
            source_set_complete=True))
        context_path = self.context_file(run)
        context = json.loads(context_path.read_text(encoding='utf-8'))
        context['reference_index'] = 'evidence/reference-index.json'
        context_path.write_text(json.dumps(context), encoding='utf-8')
        before = self.snapshot(run)

        result = self.invoke_preflight(run, context_path, evidence_inputs=[index_path, notes_path])
        self.assertEqual(result.returncode, 1)
        self.assertIn('evidence/notes.json', {
            issue['reference'] for issue in json.loads(result.stdout)['issues']})
        self.assertEqual(self.snapshot(run), before)

    def test_preflight_rejects_unsupported_layout_without_writes(self):
        historical = historical_prepare(review_artifacts, self.repo, self.scope,
                                        output_root=self.archive_root)
        context = self.write('context.json', context10(record10()))
        before = self.snapshot(self.root)
        completed = self.invoke_preflight(historical, context)
        self.assertEqual(completed.returncode, 2)
        self.assertIn('unsupported_layout', completed.stdout + completed.stderr)
        self.assertEqual(self.snapshot(self.root), before)

    def test_preflight_preserves_logical_scope_identity(self):
        run = self.prepare()
        manifest = review_artifacts.read_json(run / 'cierre.json')
        context = json.loads(self.context_file(run, identity='0' * 64).read_text(encoding='utf-8'))
        result = preflight.validate_preflight(
            phase='register', manifest=manifest, logical_scope=manifest['logical_scope'],
            selection=None, context=context, record=None,
            sources={'evidence/context.json': json.dumps(context).encode('utf-8')})
        self.assertFalse(result['ready'])
        self.assertIn('input_changed', {issue['code'] for issue in result['issues']})

    def test_preflight_discovery_accepts_a_registered_active_assignment(self):
        run = self.prepare()
        plan = context10(record10())['execution_plan']
        context = self.context_file(run, plan=plan)
        review_artifacts.register(run, [], context_input=context)
        before = self.snapshot(self.root)
        completed = self.invoke_preflight(run, context, phase='discovery')
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertTrue(json.loads(completed.stdout)['ready'])
        self.assertEqual(self.snapshot(self.root), before)

    def test_same_mr_with_another_head_shares_group_but_changes_inputs(self):
        from ccr.archive import layout as review_layout

        original = {'repository': 'https://git.example/acme/api', 'mode': 'mr',
                    'base': 'def9876543210', 'head': 'abc1234567890',
                    'snapshot': None, 'target': 'develop',
                    'reference': 'https://git.example/acme/api/merge_requests/1010'}
        other_head = dict(original, head='different-head')
        self.assertEqual(review_layout.logical_scope(original)['identity'],
                         review_layout.logical_scope(other_head)['identity'])
        current = current_inputs(other_head, source_set_complete=True)
        retained = current_inputs(original, source_set_complete=True)
        self.assertEqual(review_artifacts.review_inputs.compare_inputs(
            retained, current)['applicability'], 'changed')


if __name__ == '__main__':
    unittest.main()

