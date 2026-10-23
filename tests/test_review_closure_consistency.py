"""Retain, validate and close resolve one stable selection of guided sources."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ccr.archive import lifecycle, retention
from recovery_fixtures import context10, record10, selection_input


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


class ClosureConsistencyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='review-closure-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.git('init')
        self.git('config', 'user.name', 'Fixture Reviewer')
        self.git('config', 'user.email', 'fixture@example.test')
        (self.repo / 'product.py').write_text('answer = 42\n', encoding='utf-8')
        self.git('add', 'product.py')
        self.git('commit', '-m', 'fixture baseline')

    def git(self, *args):
        result = subprocess.run(['git', *args], cwd=self.repo, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def read(self, path):
        return json.loads(Path(path).read_text(encoding='utf-8'))

    def write(self, name, value):
        path = self.root / name
        path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
        return path

    def snapshot(self, run):
        return {str(path.relative_to(run)): path.read_bytes()
                for path in Path(run).rglob('*') if path.is_file()}

    def make_guided_run(self, *, complete_capture: bool) -> dict:
        description, notes = b'MR description captured for the fixture', b'External review notes'
        (self.root / 'description.md').write_bytes(description)
        (self.root / 'notes.json').write_bytes(notes)
        alias_output = b'worker summary output'
        index = {'schema_version': 1, 'aliases': {
            'evidence/worker/summary.json': {
                'reference': 'evidence/summary.json', 'sha256': digest(alias_output)}}, 'inputs': [
            {'reference': 'evidence/description.md', 'purpose': 'description',
             'sha256': digest(description)},
            {'reference': 'evidence/notes.json', 'purpose': 'notes',
             'sha256': digest(notes)}]}
        index_bytes = json.dumps(index, sort_keys=True, separators=(',', ':')).encode('utf-8')
        index_path = self.root / 'reference-index.json'
        index_path.write_bytes(index_bytes)
        (self.root / 'summary.json').write_bytes(alias_output)
        captured = {'evidence/reference-index.json': digest(index_bytes)}
        if complete_capture:
            captured.update({'evidence/description.md': digest(description),
                             'evidence/notes.json': digest(notes)})
        scope = record10()['scope']
        scope_path = self.write('scope.json', scope)
        output_root = self.root / 'archive'
        run = Path(lifecycle.prepare(
            self.repo, scope_path, '3.0.0', 'codex', output_root=output_root,
            profile_input=selection_input(),
            current_inputs={'scope': scope, 'sources': captured, 'source_set_complete': complete_capture}))
        manifest = self.read(run / 'cierre.json')
        final = record10()
        final['scope'] = manifest['scope']
        final['review_id'] = 'CR-' + manifest['run_id']
        final['description'] = {'status': 'unverified', 'identity': None,
                                'details': 'Description was not directly captured in this historical input map'}
        final['profile'] = manifest['profile_history'][-1]['profile']
        execution = final['coverage']['execution']
        execution['selection_source'] = manifest['profile_history'][0]['selection_source']
        execution['profile_history'] = copy.deepcopy(manifest['profile_history'])
        execution['plan'] = copy.deepcopy(record10()['coverage']['execution']['plan'])
        for row in execution['plan']:
            row['selection_id'] = manifest['profile_history'][-1]['id']
        briefs = {row['id']: {'assignment_id': row['id'], 'scope': scope}
                  for row in execution['plan']}
        results = {row['assignment_id']: {'assignment_id': row['assignment_id'], 'status': 'completed'}
                   for row in execution['results']}
        context = context10(final)
        context['review_inputs'] = copy.deepcopy(manifest['review_inputs'])
        context['reference_index'] = 'evidence/reference-index.json'
        context['profile'] = manifest['profile_history'][-1]['profile']
        context['selection_source'] = manifest['profile_history'][0]['selection_source']
        context['profile_history'] = copy.deepcopy(manifest['profile_history'])
        context['profile_reference'] = manifest['profile_history'][-1]['reference']
        context['execution_plan'] = copy.deepcopy(execution['plan'])
        context_path = self.write('context.json', context)
        lifecycle.register(run, [], context_input=context_path)
        manifest = self.read(run / 'cierre.json')
        for row, result in zip(execution['plan'], execution['results']):
            identity = {'name': result['reviewer_context'], 'provider_id': result['provider_id']}
            role = row['role']
            lifecycle.record_event(run, self.write('event-start.json', {
                'kind': 'agent', 'status': 'started', 'summary': 'Synthetic reviewer started',
                'executor': identity, 'evidence': [row['reference']]}))
            lifecycle.record_event(run, self.write('event-result.json', {
                'kind': 'discovery' if role == 'discovery' else 'grouped-verification',
                'status': 'completed', 'summary': 'Synthetic reviewer completed',
                'actor': {'kind': 'agent', **identity},
                'evidence': [row['reference'], result['reference']]}))
        context['execution_plan'] = copy.deepcopy(manifest['assignment_registry'])
        context_path = self.write('context-retain.json', context)
        final_path = self.write('final.json', final)
        evidence_inputs = [index_path, self.root / 'description.md', self.root / 'notes.json',
                           self.root / 'summary.json', self.write_bytes('briefs.json', briefs),
                           self.write_bytes('results.json', results)]
        return {'run': run, 'record': final_path, 'context': context_path,
                'evidence_inputs': evidence_inputs, 'index': index,
                'description': description, 'notes': notes, 'index_bytes': index_bytes}

    def write_bytes(self, name, value):
        path = self.root / name
        path.write_bytes(json.dumps(value, sort_keys=True, separators=(',', ':')).encode('utf-8'))
        return path

    def retain(self, case):
        return retention.retain(case['run'], case['record'],
                                context_input=case['context'],
                                evidence_inputs=case['evidence_inputs'],
                                unavailable_reason='Fixture has no provider counters',
                                expected_schema=10)

    def test_retain_then_validate_reloads_all_indexed_sources(self):
        case = self.make_guided_run(complete_capture=True)
        self.retain(case)
        before = self.snapshot(case['run'])
        result = lifecycle.validate(case['run'], require_retained=True)
        self.assertTrue(result['retained'])
        self.assertEqual(result['state'], 'closing')
        self.assertEqual(self.snapshot(case['run']), before)
        lifecycle.close(case['run'], cleanup='not_needed')
        self.assertEqual(lifecycle.validate(case['run'], require_complete=True)['state'], 'complete')

    def test_processing_unverified_snapshot_is_preserved(self):
        case = self.make_guided_run(complete_capture=False)
        self.retain(case)
        before = self.snapshot(case['run'])
        lifecycle.validate(case['run'], require_retained=True)
        after = self.read(case['run'] / 'review.json')
        self.assertEqual(after['description']['status'], 'unverified')
        self.assertEqual(after['description'], self.read(case['record'])['description'])
        self.assertEqual(self.snapshot(case['run']), before)

    def test_uninventoried_or_changed_source_blocks_without_cleanup(self):
        case = self.make_guided_run(complete_capture=True)
        self.retain(case)
        run, manifest = case['run'], self.read(case['run'] / 'cierre.json')
        before = self.snapshot(run)
        missing_inventory = copy.deepcopy(manifest)
        missing_inventory['hashes'].pop('evidence/notes.json')
        with self.assertRaisesRegex(ValueError, 'not selected for retention'):
            retention._execution_gate(run, missing_inventory, self.read(run / 'review.json'), {})
        self.assertEqual(self.snapshot(run), before)
        self.assertEqual(self.read(run / 'cierre.json')['cleanup'], 'pending')
        missing_alias_inventory = copy.deepcopy(manifest)
        missing_alias_inventory['hashes'].pop('evidence/summary.json')
        with self.assertRaisesRegex(ValueError, 'not selected for retention'):
            retention._execution_gate(run, missing_alias_inventory,
                                      self.read(run / 'review.json'), {})
        self.assertEqual(self.snapshot(run), before)

        notes = run / 'evidence' / 'notes.json'
        notes.write_bytes(b'changed after retention')
        changed_snapshot = self.snapshot(run)
        with self.assertRaises(ValueError):
            lifecycle.validate(run, require_retained=True)
        self.assertEqual(self.snapshot(run), changed_snapshot)
        self.assertEqual(self.read(run / 'cierre.json')['cleanup'], 'pending')

    def test_aligned_description_still_requires_initial_capture(self):
        case = self.make_guided_run(complete_capture=False)
        final = self.read(case['record'])
        final['description'] = {'status': 'aligned', 'identity': digest(case['description']),
                               'details': 'Fixture description'}
        case['record'].write_text(json.dumps(final), encoding='utf-8')
        before = self.snapshot(case['run'])
        with self.assertRaisesRegex(ValueError, 'initially captured'):
            self.retain(case)
        self.assertEqual(self.snapshot(case['run']), before)


if __name__ == '__main__':
    unittest.main()
