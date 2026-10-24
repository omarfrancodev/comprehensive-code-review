"""Retain, validate and close resolve one stable selection of guided sources."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ccr.archive import lifecycle, retention
from ccr.archive import resources
from ccr.contracts import preflight
from ccr.execution import workspaces
from ccr.workflow import builders
from ccr.cli.artifacts import preflight_run
from recovery_fixtures import context10, record10, selection_input


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


class ClosureConsistencyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='review-closure-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.owned_sessions = []
        self.addCleanup(self.cleanup_owned_sessions)
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

    def cleanup_owned_sessions(self):
        for entry in reversed(self.owned_sessions):
            session = entry['session']
            if not session.exists():
                continue
            claim = session / '.review-run-owner.json'
            owned = claim.exists() and self.read(claim).get('status') == 'owned'
            run = entry.get('run')
            resources.cleanup_workspace(argparse.Namespace(
                manifest=str(session / 'manifest.json'),
                run_dir=str(run) if owned and run is not None else None))

    def make_guided_run(self, *, complete_capture: bool, owned_session: bool = False,
                        late_dispatch: bool = False, capture_dispatch: bool = False,
                        material_alias: bool = False, dispatch_alias: bool = False,
                        annotate_dispatch: bool = True,
                        dispatch_source: str | None = None, late_assignment: str = 'D1',
                        profile: str = 'focused', early_verifier: bool = False) -> dict:
        dispatch_source = dispatch_source or 'evidence/dispatch.json#' + late_assignment
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
        if material_alias:
            (self.root / 'description-copy.md').write_bytes(description)
            index['aliases']['evidence/description.md'] = {
                'reference': 'evidence/description-copy.md', 'sha256': digest(description)}
        if dispatch_alias:
            result = next(row for row in record10(profile)['coverage']['execution']['results']
                          if row['assignment_id'] == late_assignment)
            dispatch_bytes = json.dumps({late_assignment: {'executor': {
                'name': result['reviewer_context'], 'provider_id': result['provider_id']}}},
                sort_keys=True, separators=(',', ':')).encode('utf-8')
            index['aliases'][dispatch_source.partition('#')[0]] = {
                'reference': 'evidence/dispatch-retained.json', 'sha256': digest(dispatch_bytes)}
        index_bytes = json.dumps(index, sort_keys=True, separators=(',', ':')).encode('utf-8')
        index_path = self.root / 'reference-index.json'
        index_path.write_bytes(index_bytes)
        (self.root / 'summary.json').write_bytes(alias_output)
        captured = {'evidence/reference-index.json': digest(index_bytes)}
        if complete_capture:
            captured.update({'evidence/description.md': digest(description),
                             'evidence/notes.json': digest(notes)})
        scope = record10(profile)['scope']
        scope_path = self.write('scope.json', scope)
        output_root = self.root / 'archive'
        session = None
        owned_entry = None
        if owned_session:
            session_manifest = workspaces.prepare(argparse.Namespace(
                repo=str(self.repo), ref='HEAD', mode='commit', role=['review'], include_untracked=[]))
            session = Path(session_manifest['session_dir'])
            owned_entry = {'session': session, 'run': None}
            self.owned_sessions.append(owned_entry)
        run = Path(lifecycle.prepare(
            self.repo, scope_path, '3.0.0', 'codex', output_root=output_root,
            temporary_paths=[str(session)] if session is not None else None,
            profile_input=selection_input(profile),
            current_inputs={'scope': scope, 'sources': captured, 'source_set_complete': complete_capture}))
        if owned_entry is not None:
            owned_entry['run'] = run
        manifest = self.read(run / 'cierre.json')
        final = record10(profile)
        final['scope'] = manifest['scope']
        final['review_id'] = 'CR-' + manifest['run_id']
        final['description'] = {'status': 'unverified', 'identity': None,
                                'details': 'Description was not directly captured in this historical input map'}
        final['profile'] = manifest['profile_history'][-1]['profile']
        execution = final['coverage']['execution']
        execution['selection_source'] = manifest['profile_history'][0]['selection_source']
        execution['profile_history'] = copy.deepcopy(manifest['profile_history'])
        execution['plan'] = copy.deepcopy(record10(profile)['coverage']['execution']['plan'])
        if late_dispatch and not annotate_dispatch:
            execution['status'] = 'degraded'
            execution['fallbacks'] = [{'assignments': [late_assignment], 'reason': 'dispatch_failed',
                'detail': 'Historical dispatch omitted executor identity',
                'source': 'evidence/context.json#dispatch_fallback'}]
            final['coverage']['limitations'] = [{'kind': 'execution', 'material': False,
                'detail': 'Historical dispatch omitted executor identity', 'public_summary': None}]
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
        if late_dispatch and not annotate_dispatch:
            context['dispatch_fallback'] = 'Observed missing dispatch identity'
        context_path = self.write('context.json', context)
        lifecycle.register(run, [str(session)] if session is not None else [], context_input=context_path)
        manifest = self.read(run / 'cierre.json')
        dispatch_identity = None
        dispatch_start = None

        def record_start(row, result):
            nonlocal dispatch_start, dispatch_identity
            identity = {'name': result['reviewer_context'], 'provider_id': result['provider_id']}
            start_payload = {
                'kind': 'agent', 'status': 'started', 'summary': 'Synthetic reviewer started',
                'executor': None if late_dispatch and row['id'] == late_assignment else identity,
                'evidence': [row['reference']]}
            if late_dispatch and row['id'] == late_assignment:
                start_payload['actor'] = {'kind': 'coordinator', 'name': 'coordinator', 'provider_id': None}
                with patch.object(preflight.dispatch, 'validate_dispatch_identity_event', return_value=[]):
                    start_result = lifecycle.record_event(run, self.write('event-start.json', start_payload))
                dispatch_start = start_result['event_id']
                dispatch_identity = identity
            else:
                lifecycle.record_event(run, self.write('event-start.json', start_payload))

        if early_verifier:
            verifier = next(row for row in execution['plan'] if row['id'] == 'V1')
            result = next(row for row in execution['results'] if row['assignment_id'] == 'V1')
            record_start(verifier, result)
        for row, result in zip(execution['plan'], execution['results']):
            identity = {'name': result['reviewer_context'], 'provider_id': result['provider_id']}
            role = row['role']
            if not early_verifier or row['id'] != 'V1':
                record_start(row, result)
            else:
                lifecycle.record_event(run, self.write('event-stage-start.json', {
                    'kind': 'grouped-verification', 'status': 'started',
                    'summary': 'Same reviewer starts final verification stage',
                    'actor': {'kind': 'agent', **identity}, 'evidence': [row['reference']]}))
            lifecycle.record_event(run, self.write('event-result.json', {
                'kind': 'discovery' if role == 'discovery' else 'grouped-verification',
                'status': 'completed', 'summary': 'Synthetic reviewer completed',
                'actor': {'kind': 'agent', **identity},
                'evidence': [row['reference'], result['reference']]}))
        dispatch_path = None
        if late_dispatch:
            dispatch_path = self.write_bytes(
                'dispatch-retained.json' if dispatch_alias else 'dispatch.json',
                {late_assignment: {'executor': dispatch_identity}})
            annotation = {'kind': 'agent', 'status': 'unchanged',
                'summary': 'Observed identity for original dispatch; no new execution',
                'actor': {'kind': 'coordinator', 'name': 'coordinator', 'provider_id': None},
                'executor': dispatch_identity,
                'provenance': {'kind': 'recovered', 'source': dispatch_source},
                'evidence': ['evidence/briefs.json#' + late_assignment, dispatch_source],
                'relations': [{'relation': 'records', 'target': dispatch_start}],
                'authority': None, 'occurred_at': None}
            annotation_path = self.write('dispatch-annotation.json', annotation)
            if annotate_dispatch:
                lifecycle.record_event(run, annotation_path)
            else:
                lifecycle.record_event(run, self.write('dispatch-fallback.json', {
                    'kind': 'interruption', 'status': 'blocked',
                    'summary': 'Observed historical dispatch without executor identity',
                    'evidence': ['evidence/context.json#dispatch_fallback']}))
        else:
            annotation_path = None
        context['execution_plan'] = copy.deepcopy(manifest['assignment_registry'])
        context_path = self.write('context-retain.json', context)
        final_path = self.write('final.json', final)
        evidence_inputs = [index_path, self.root / 'description.md', self.root / 'notes.json',
                           self.root / 'summary.json', self.write_bytes('briefs.json', briefs),
                           self.write_bytes('results.json', results)]
        if capture_dispatch and dispatch_path is not None:
            evidence_inputs.append(dispatch_path)
        if material_alias:
            evidence_inputs.append(self.root / 'description-copy.md')
        return {'run': run, 'record': final_path, 'context': context_path,
                'evidence_inputs': evidence_inputs, 'index': index,
                'description': description, 'notes': notes, 'index_bytes': index_bytes,
                'session': session, 'dispatch_path': dispatch_path,
                'annotation': annotation_path}

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

    def generic_agent_event(self):
        return {
            'kind': 'agent', 'status': 'unchanged',
            'summary': 'Worker already active; no new dispatch',
            'actor': {'kind': 'agent', 'name': 'worker-notice', 'provider_id': None},
            'executor': None, 'provenance': {'kind': 'agent', 'source': None},
            'evidence': [], 'relations': [],
        }

    def test_generic_agent_event_is_recorded_in_processing_and_closing(self):
        case = self.make_guided_run(complete_capture=True)
        event = self.write('generic-event.json', self.generic_agent_event())
        lifecycle.record_event(case['run'], event)
        self.retain(case)
        self.write('generic-event.json', dict(self.generic_agent_event(),
                   provenance={'kind': 'agent', 'source': 'observed harness notice'}))
        lifecycle.record_event(case['run'], event)

        self.assertTrue(lifecycle.validate(case['run'], require_retained=True)['retained'])
        lifecycle.close(case['run'], cleanup='not_needed')
        self.assertEqual(lifecycle.validate(case['run'], require_complete=True)['state'], 'complete')

    def test_historical_generic_event_survives_retention_close_and_immutable_validation(self):
        case = self.make_guided_run(complete_capture=True)
        run, manifest, marker = lifecycle._load_run(case['run'])
        # Use the durable trace writer to represent a pre-annotation historical event.
        # No execution gate is mocked and the historical trace is never rewritten.
        event = lifecycle.review_trace.event_input(self.generic_agent_event())
        lifecycle._append_trace(run, manifest, marker, event, helper=False)
        trace_path = run / 'trazabilidad.jsonl'
        historical_trace = trace_path.read_bytes()

        self.retain(case)

        self.assertTrue(lifecycle.validate(run, require_retained=True)['retained'])
        lifecycle.close(run, cleanup='not_needed')
        self.assertTrue(trace_path.read_bytes().startswith(historical_trace))
        before = self.snapshot(run)
        self.assertEqual(lifecycle.validate(run, require_complete=True)['state'], 'complete')
        self.assertTrue(lifecycle.validate(run, require_retained=True)['retained'])
        self.assertEqual(self.snapshot(run), before)

    def test_partial_identity_annotation_is_rejected_without_trace_writes(self):
        case = self.make_guided_run(complete_capture=True, late_dispatch=True,
                                    annotate_dispatch=False, capture_dispatch=True, profile='deep')
        annotation = self.read(case['annotation'])
        before = self.snapshot(case['run'])
        for changes in ({'relations': []},
                        {'provenance': {'kind': 'agent', 'source': None}},
                        {'provenance': {'kind': 'recovered', 'source': None}},
                        {'executor': None}):
            with self.subTest(changes=changes):
                invalid = self.write('partial-annotation.json', dict(annotation, **changes))
                with self.assertRaises(ValueError):
                    lifecycle.record_event(case['run'], invalid)
                self.assertEqual(self.snapshot(case['run']), before)

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

    def test_late_final_verifier_identity_retains_and_closes_without_new_execution(self):
        case = self.make_guided_run(complete_capture=True, late_dispatch=True,
            late_assignment='V1', capture_dispatch=True, dispatch_alias=True,
            dispatch_source='evidence/harness/dispatch.json#V1', profile='deep')
        trace_path = case['run'] / 'trazabilidad.jsonl'
        before = trace_path.read_bytes()
        events = [json.loads(line) for line in before.splitlines()]
        original = next(row for row in events if row['kind'] == 'agent' and row['status'] == 'started'
                        and 'evidence/briefs.json#V1' in row['evidence'])
        self.assertIsNone(original['executor'])
        self.assertEqual(original['actor']['kind'], 'coordinator')

        self.retain(case)

        self.assertTrue(lifecycle.validate(case['run'], require_retained=True)['retained'])
        lifecycle.close(case['run'], cleanup='not_needed')
        self.assertEqual(lifecycle.validate(case['run'], require_complete=True)['state'], 'complete')
        self.assertTrue(trace_path.read_bytes().startswith(before))
        after = [json.loads(line) for line in trace_path.read_bytes().splitlines()]
        starts = [row for row in after if row['kind'] == 'agent' and row['status'] == 'started'
                  and 'evidence/briefs.json#V1' in row['evidence']]
        results = [row for row in after if row['kind'] == 'grouped-verification'
                   and row['status'] == 'completed' and 'evidence/results.json#V1' in row['evidence']]
        self.assertEqual(starts, [original])
        self.assertEqual(len(results), 1)

    def test_retention_rejects_early_verifier_with_later_stage_start_without_writes(self):
        for recovered in (False, True):
            with self.subTest(recovered=recovered):
                case = self.make_guided_run(complete_capture=True, early_verifier=True,
                    late_dispatch=recovered, late_assignment='V1', capture_dispatch=recovered,
                    profile='deep')
                before = self.snapshot(case['run'])

                with self.assertRaisesRegex(ValueError, 'one fresh verifier after the final discovery batch'):
                    self.retain(case)

                self.assertEqual(self.snapshot(case['run']), before)

    def test_reretain_reuses_inventoried_index_material_and_alias_sources(self):
        case = self.make_guided_run(complete_capture=True, material_alias=True,
                                    late_dispatch=True, dispatch_alias=True,
                                    capture_dispatch=True, profile='deep')
        self.retain(case)
        selected_before = {name: raw for name, raw in self.snapshot(case['run']).items()
                           if name.startswith('evidence/')}
        case['evidence_inputs'] = []
        before = self.snapshot(case['run'])
        result, code = preflight_run(case['run'], case['context'], phase='retain',
                                    input_file=case['record'])
        self.assertEqual(code, 0, result)
        self.assertTrue(result['ready'])
        self.assertEqual(self.snapshot(case['run']), before)

        self.retain(case)

        self.assertTrue(lifecycle.validate(case['run'], require_retained=True)['retained'])
        self.assertEqual({name: raw for name, raw in self.snapshot(case['run']).items()
                          if name.startswith('evidence/')}, selected_before)
        lifecycle.close(case['run'], cleanup='not_needed')
        self.assertEqual(lifecycle.validate(case['run'], require_complete=True)['state'], 'complete')

    def test_reretain_explicit_changed_source_is_not_replaced_by_archived_bytes(self):
        case = self.make_guided_run(complete_capture=True)
        self.retain(case)
        (self.root / 'notes.json').write_bytes(b'changed explicit candidate')
        case['evidence_inputs'] = [self.root / 'notes.json']
        before = self.snapshot(case['run'])
        with self.assertRaisesRegex(ValueError, 'selected material input differs'):
            self.retain(case)
        self.assertEqual(self.snapshot(case['run']), before)

    def test_present_but_uninventoried_material_is_not_reused_by_preflight(self):
        case = self.make_guided_run(complete_capture=True)
        (case['run'] / 'evidence').mkdir(exist_ok=True)
        (case['run'] / 'evidence' / 'notes.json').write_bytes(case['notes'])
        case['evidence_inputs'] = [path for path in case['evidence_inputs'] if path.name != 'notes.json']
        before = self.snapshot(case['run'])
        with self.assertRaisesRegex(ValueError, 'not selected'):
            self.retain(case)
        self.assertEqual(self.snapshot(case['run']), before)

    def test_nested_dispatch_alias_passes_builder_closing_mutator_and_replay(self):
        case = self.make_guided_run(complete_capture=True, late_dispatch=True,
            dispatch_alias=True, capture_dispatch=True, annotate_dispatch=False,
            dispatch_source='evidence/harness/dispatch.json#D1', profile='deep')
        self.retain(case)
        annotation = self.read(case['annotation'])
        assignment = self.read(case['run'] / 'cierre.json')['assignment_registry'][0]
        built = builders.build_assignment_event(annotation, assignment)
        self.assertEqual(built['provenance']['source'], 'evidence/harness/dispatch.json#D1')
        for source in ('evidence/unknown/dispatch.json#D1', 'evidence/harness/dispatch.json#D999'):
            invalid = copy.deepcopy(annotation)
            invalid['provenance']['source'] = source
            invalid['evidence'][-1] = source
            before = self.snapshot(case['run'])
            with self.subTest(source=source), self.assertRaises(ValueError):
                lifecycle.record_event(case['run'], self.write('invalid-nested-annotation.json', invalid))
            self.assertEqual(self.snapshot(case['run']), before)
        first = lifecycle.record_event(case['run'], case['annotation'])
        before = self.snapshot(case['run'])
        self.assertEqual(lifecycle.record_event(case['run'], case['annotation']), first)
        self.assertEqual(self.snapshot(case['run']), before)
        self.assertTrue(lifecycle.validate(case['run'], require_retained=True)['retained'])
        lifecycle.close(case['run'], cleanup='not_needed')
        self.assertEqual(lifecycle.validate(case['run'], require_complete=True)['state'], 'complete')

    def test_material_input_alias_survives_revalidation_and_close(self):
        case = self.make_guided_run(complete_capture=True, material_alias=True)
        self.retain(case)
        before = self.snapshot(case['run'])

        self.assertTrue(lifecycle.validate(case['run'], require_retained=True)['retained'])

        self.assertEqual(self.snapshot(case['run']), before)
        lifecycle.close(case['run'], cleanup='not_needed')
        self.assertEqual(lifecycle.validate(case['run'], require_complete=True)['state'], 'complete')

    def test_closing_annotation_alias_replay_returns_original_event_without_writes(self):
        case = self.make_guided_run(complete_capture=True, late_dispatch=True,
                                    capture_dispatch=True, dispatch_alias=True, profile='deep')
        self.retain(case)
        self.assertTrue(lifecycle.validate(case['run'], require_retained=True)['retained'])
        before = self.snapshot(case['run'])
        events = [json.loads(line) for line in (case['run'] / 'trazabilidad.jsonl').read_bytes().splitlines()]
        original = next(row for row in events if row['kind'] == 'agent' and row['status'] == 'unchanged')

        replay = lifecycle.record_event(case['run'], case['annotation'])

        self.assertEqual(replay['event_id'], original['event_id'])
        self.assertEqual(replay['sequence'], original['sequence'])
        self.assertEqual(self.snapshot(case['run']), before)

    def test_closing_annotation_rejects_invalid_fragment_and_executor_without_writes(self):
        for alias in (False, True):
            for defect, message in (('fragment', 'fragment does not resolve'),
                                    ('executor', 'does not match recorded executor')):
                with self.subTest(alias=alias, defect=defect):
                    case = self.make_guided_run(complete_capture=True, late_dispatch=True,
                        capture_dispatch=True, annotate_dispatch=False, dispatch_alias=alias, profile='deep')
                    self.retain(case)
                    self.assertTrue(lifecycle.validate(case['run'], require_retained=True)['retained'])
                    invalid = self.read(case['annotation'])
                    if defect == 'fragment':
                        invalid['provenance']['source'] = 'evidence/dispatch.json#D999'
                        invalid['evidence'][-1] = 'evidence/dispatch.json#D999'
                    else:
                        invalid['executor']['name'] = 'different-worker'
                    before = self.snapshot(case['run'])

                    with self.assertRaisesRegex(ValueError, message):
                        lifecycle.record_event(case['run'], self.write('invalid-annotation.json', invalid))

                    self.assertEqual(self.snapshot(case['run']), before)
                    self.assertTrue(lifecycle.validate(case['run'], require_retained=True)['retained'])
                    lifecycle.record_event(case['run'], case['annotation'])
                    lifecycle.close(case['run'], cleanup='not_needed')
                    self.assertEqual(lifecycle.validate(case['run'], require_complete=True)['state'], 'complete')

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

    def test_annotation_and_sources_survive_real_owned_cleanup(self):
        case = self.make_guided_run(complete_capture=True, owned_session=True,
                                    late_dispatch=True, capture_dispatch=True, profile='deep')
        self.retain(case)
        self.assertTrue(lifecycle.validate(case['run'], require_retained=True)['retained'])
        before_replay = self.snapshot(case['run'])
        lifecycle.record_event(case['run'], case['annotation'])
        self.assertEqual(self.snapshot(case['run']), before_replay)
        self.assertEqual(lifecycle.validate(case['run'], require_retained=True)['state'], 'closing')
        trace = [json.loads(line) for line in (case['run'] / 'trazabilidad.jsonl').read_bytes().splitlines()]
        d1_starts = [row for row in trace if row.get('kind') == 'agent' and row.get('status') == 'started'
                     and 'evidence/briefs.json#D1' in row.get('evidence', [])]
        d1_results = [row for row in trace if row.get('kind') == 'discovery' and row.get('status') == 'completed'
                      and 'evidence/results.json#D1' in row.get('evidence', [])]
        annotations = [row for row in trace if row.get('kind') == 'agent' and row.get('status') == 'unchanged']
        self.assertEqual(len(d1_starts), 1)
        self.assertIsNone(d1_starts[0]['executor'])
        self.assertEqual(len(d1_results), 1)
        self.assertEqual(len(annotations), 1)
        self.assertEqual(annotations[0]['relations'][0]['target'], d1_starts[0]['event_id'])

        cleanup = resources.cleanup_workspace(argparse.Namespace(
            manifest=str(case['session'] / 'manifest.json'), run_dir=str(case['run'])))
        self.assertFalse(case['session'].exists())
        self.assertEqual(lifecycle.validate(case['run'], require_retained=True)['state'], 'closing')
        lifecycle.close(case['run'], cleanup='complete', residuals=[],
                        released_claims=cleanup['released_claims'])
        self.assertEqual(lifecycle.validate(case['run'], require_complete=True)['state'], 'complete')
        self.assertIn('evidence/dispatch.json', self.read(case['run'] / 'cierre.json')['hashes'])

    def test_unselected_dispatch_identity_source_blocks_before_cleanup(self):
        case = self.make_guided_run(complete_capture=True, owned_session=True,
                                    late_dispatch=True, capture_dispatch=False, profile='deep')
        try:
            with self.assertRaisesRegex(ValueError, 'dispatch identity source'):
                self.retain(case)
            manifest = self.read(case['run'] / 'cierre.json')
            self.assertEqual(manifest['resource_cleanup'], None)
            self.assertTrue(case['session'].exists())
        finally:
            self.cleanup_owned_sessions()

    def test_mismatched_dispatch_identity_source_blocks_before_cleanup(self):
        case = self.make_guided_run(complete_capture=True, owned_session=True,
                                    late_dispatch=True, capture_dispatch=True, profile='deep')
        try:
            dispatch = self.read(case['dispatch_path'])
            dispatch['D1']['executor']['name'] = 'worker-b'
            case['dispatch_path'].write_bytes(
                json.dumps(dispatch, sort_keys=True, separators=(',', ':')).encode('utf-8'))
            before = self.snapshot(case['run'])

            with self.assertRaisesRegex(ValueError, 'dispatch identity source does not match recorded executor'):
                self.retain(case)

            self.assertEqual(self.snapshot(case['run']), before)
            self.assertIsNone(self.read(case['run'] / 'cierre.json')['resource_cleanup'])
            self.assertTrue(case['session'].exists())
        finally:
            self.cleanup_owned_sessions()


if __name__ == '__main__':
    unittest.main()
