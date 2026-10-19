"""Archive traces preserve milestones and integrity without logging every probe."""
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import test_review_artifacts as fixtures

artifacts = fixtures.artifacts


class TraceTests(unittest.TestCase):
    setUp = fixtures.ArchiveTests.setUp
    git = fixtures.ArchiveTests.git
    write = fixtures.ArchiveTests.write
    prepare = fixtures.ArchiveTests.prepare
    read = fixtures.ArchiveTests.read
    close = fixtures.ArchiveTests.close

    def retain(self, run, **kwargs):
        kwargs.setdefault('unavailable_reason', None)
        return fixtures.ArchiveTests.retain(self, run, **kwargs)

    def register_empty(self, run):
        manifest = self.read(run / 'cierre.json')
        history = manifest['profile_history']
        return artifacts.register(run, [], context_input=self.write('empty-context.json', {
            'profile': history[-1]['profile'], 'selection_source': history[0]['selection_source'],
            'profile_reference': history[-1]['reference'], 'profile_history': history,
            'execution_plan': [], 'executors': [], 'review_inputs': manifest['review_inputs']}))

    def events(self, run):
        return [json.loads(line) for line in (run / 'trazabilidad.jsonl').read_text(encoding='utf-8').splitlines()]

    def event(self):
        return {'kind': 'check', 'status': 'passed', 'summary': 'Relevant regression passed',
                'actor': {'kind': 'agent', 'name': 'verifier', 'provider_id': None},
                'executor': {'name': 'isolated-verifier', 'provider_id': None},
                'provenance': {'kind': 'agent', 'source': None},
                'evidence': ['C01'], 'relations': [{'relation': 'verifies', 'target': 'F01'}]}

    def test_new_archive_records_owned_lifecycle_and_complete_is_immutable(self):
        run = self.prepare()
        self.register_empty(run)
        self.retain(run)
        artifacts.validate(run, require_retained=True, record_checkpoint=True)
        self.close(run)
        events = self.events(run)
        kinds = [event['kind'] for event in events]
        milestones = ['prepare', 'profile', 'register', 'retain', 'validation', 'close']
        self.assertEqual(sorted(milestones, key=kinds.index), milestones)
        self.assertEqual([event['sequence'] for event in events], list(range(1, len(events) + 1)))
        self.assertTrue(all(datetime.fromisoformat(event['recorded_at']).utcoffset().total_seconds() == 0 for event in events))
        self.assertEqual(self.read(run / 'cierre.json')['schema_version'], 8)
        before = {p.name: p.read_bytes() for p in run.iterdir() if p.is_file()}
        artifacts.validate(run, require_retained=True)
        self.close(run)
        self.assertEqual(before, {p.name: p.read_bytes() for p in run.iterdir() if p.is_file()})
        with self.assertRaisesRegex(ValueError, 'immutable'):
            artifacts.record_event(run, self.write('event.json', self.event()))

    def test_structured_event_cli_keeps_actor_separate_from_recorder(self):
        run = self.prepare()
        event_file = self.write('event.json', self.event())
        process = subprocess.run([sys.executable, str(Path(artifacts.__file__)), 'record-event',
                                  '--run-dir', str(run), '--event-file', str(event_file)], capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stderr)
        event = self.events(run)[-1]
        self.assertEqual(event['actor']['name'], 'verifier')
        self.assertEqual(event['recorder']['name'], 'review_artifacts')
        self.assertIsNone(event['actor']['provider_id'])
        self.assertEqual(event['evidence'], ['C01'])
        self.assertEqual(event['relations'], [{'relation': 'verifies', 'target': 'F01'}])
        self.assertEqual(event['review_id'], 'CR-' + self.read(run / 'cierre.json')['run_id'])

    def legacy_run(self, version):
        """Build a historical fixture, including matching ownership/inventory."""
        run = self.prepare()
        manifest = self.read(run / 'cierre.json')
        marker = self.read(run / artifacts.MARKER)
        manifest['schema_version'] = version
        if version < 4:
            manifest.pop('trace')
            manifest['hashes'].pop('trazabilidad.jsonl')
            (run / 'trazabilidad.jsonl').unlink()
        artifacts._save_manifest(run, manifest, marker)
        return run

    def test_processing_starts_on_observed_work_only(self):
        run = self.prepare()
        self.assertEqual(self.read(run / 'cierre.json')['schema_version'], 8)
        self.assertEqual(artifacts.validate(run)['state'], 'prepared')
        for kind, status in [('agent', 'pending')]:
            artifacts.record_event(run, self.write('planned.json', dict(kind=kind, status=status, summary='Planning only')))
            self.assertEqual(artifacts.validate(run)['state'], 'prepared')
        artifacts.validate(run, record_checkpoint=True)
        self.assertEqual(artifacts.validate(run)['state'], 'prepared')
        artifacts.record_event(run, self.write('start.json', dict(kind='discovery', status='started', summary='Discovery began')))
        self.assertEqual(artifacts.validate(run)['state'], 'processing')
        self.register_empty(run)
        self.retain(run)
        artifacts.validate(run, require_retained=True, record_checkpoint=True)
        self.assertEqual(artifacts.validate(run)['state'], 'closing')
        artifacts.record_event(run, self.write('late.json', self.event()))
        self.assertEqual(artifacts.validate(run)['state'], 'closing')
        self.close(run)
        self.assertEqual(artifacts.validate(run, require_retained=True)['state'], 'complete')

    def test_work_start_predicate_uses_observed_kinds_and_statuses(self):
        for kind in ('agent', 'discovery', 'check', 'grouped-verification'):
            for status in ('started', 'completed', 'passed', 'failed', 'blocked', 'skipped'):
                self.assertTrue(artifacts._starts_processing({'kind': kind, 'status': status}))
            for status in ('pending', 'selected', 'authorized', 'unchanged', 'retained'):
                self.assertFalse(artifacts._starts_processing({'kind': kind, 'status': status}))
        self.assertFalse(artifacts._starts_processing({'kind': 'validation', 'status': 'passed'}))

    def test_legacy_states_and_complete_bytes_are_preserved(self):
        for version in range(1, 8):
            run = self.legacy_run(version)
            before = {p.name: p.read_bytes() for p in run.iterdir() if p.is_file()}
            for operation in (lambda: artifacts.validate(run),
                              lambda: artifacts.record_event(run, self.write('legacy.json', self.event()))):
                with self.subTest(version=version), self.assertRaisesRegex(ValueError, 'unsupported_layout'):
                    operation()
            self.assertEqual(before, {p.name: p.read_bytes() for p in run.iterdir() if p.is_file()})

    def test_processing_recovery_preserves_pending_event(self):
        for failed_file in ('trazabilidad.jsonl', artifacts.MARKER):
            run = self.prepare()
            original = artifacts.atomic_write
            writes = 0
            def interrupt(path, data):
                nonlocal writes
                if Path(path).name == failed_file:
                    writes += 1
                    if failed_file == 'trazabilidad.jsonl' or writes == 2:
                        raise OSError('interrupted processing transition')
                original(path, data)
            with patch.object(artifacts, 'atomic_write', side_effect=interrupt), self.assertRaises(OSError):
                artifacts.record_event(run, self.write('start.json', dict(kind='discovery', status='started', summary='Observed start')))
            pending = self.read(run / 'cierre.json')['pending_trace']['events'][0]
            with self.assertRaisesRegex(ValueError, 'pending'):
                artifacts.validate(run)
            self.register_empty(run)
            self.assertEqual(artifacts.validate(run)['state'], 'processing')
            self.assertEqual(self.events(run)[2], pending)

    def test_manifest_replace_interruption_leaves_preparation_recoverable(self):
        run = self.prepare()
        original = artifacts.atomic_write
        def interrupt(path, data):
            if Path(path).name == 'cierre.json':
                raise OSError('manifest replace interrupted')
            original(path, data)
        with patch.object(artifacts, 'atomic_write', side_effect=interrupt), self.assertRaises(OSError):
            artifacts.record_event(run, self.write('start.json', dict(kind='discovery', status='started', summary='Observed start')))
        with self.assertRaisesRegex(ValueError, 'pending'):
            artifacts.validate(run)
        self.register_empty(run)
        self.assertEqual(artifacts.validate(run)['state'], 'prepared')
        self.assertEqual([e['kind'] for e in self.events(run)], ['prepare', 'profile', 'register'])

    def test_tool_execution_time_is_preserved_separately_from_recording_time(self):
        run = self.prepare()
        event = self.event()
        event.update(occurred_at='2026-10-01T12:00:00+00:00', provenance={'kind': 'tool', 'source': 'provider-result:check-1'})
        artifacts.record_event(run, self.write('timed.json', event))
        recorded = self.events(run)[-1]
        self.assertEqual(recorded['occurred_at'], '2026-10-01T12:00:00+00:00')
        self.assertNotEqual(recorded['recorded_at'], recorded['occurred_at'])
        self.assertIsNotNone(self.events(run)[0]['occurred_at'])
        for invalid in ('unknown', '2026-10-01T12:00:00', '2026-10-01T12:00:00-05:00'):
            event['occurred_at'] = invalid
            with self.assertRaises(ValueError):
                artifacts.record_event(run, self.write('invalid-time.json', event))

    def test_trace_tampering_deletion_and_reordering_block_archive_gate(self):
        run = self.prepare()
        self.retain(run)
        self.close(run)
        path = run / 'trazabilidad.jsonl'
        original = path.read_bytes()
        lines = original.splitlines(keepends=True)
        for tampered in (b'', b''.join(reversed(lines)), original.replace(b'prepare', b'changed')):
            path.write_bytes(tampered)
            with self.assertRaises(ValueError):
                artifacts.validate(run, require_retained=True)
        path.write_bytes(original)
        path.unlink()
        with self.assertRaises(ValueError):
            artifacts.validate(run, require_retained=True)

    def test_helper_milestones_capture_observed_utc_time(self):
        run = self.prepare()
        self.register_empty(run)
        artifacts.validate(run, record_checkpoint=True)
        artifacts.record_event(run, self.write('unknown-clock.json', self.event()))
        self.retain(run)
        self.close(run)
        for event in self.events(run):
            if event['actor']['kind'] == 'helper':
                self.assertEqual(datetime.fromisoformat(event['occurred_at']).utcoffset().total_seconds(), 0)
                self.assertEqual(event['provenance'], {'kind': 'helper', 'source': 'review_artifacts:' + event['kind']})
                self.assertLessEqual(datetime.fromisoformat(event['occurred_at']), datetime.fromisoformat(event['recorded_at']))
            else:
                self.assertIsNone(event['occurred_at'])
        self.assertFalse((run / 'measurements.json').exists())

    def test_execution_metadata_rejects_conflicts_and_keeps_unknown_times(self):
        raw = self.event()
        metadata = {'started_at': '2026-10-09T12:00:00+00:00', 'finished_at': '2026-10-09T12:01:00+00:00'}
        adapter = artifacts.review_trace.event_from_execution
        for status in ('started', 'completed', 'passed', 'failed', 'blocked', 'skipped'):
            event = dict(raw, status=status)
            key = 'started_at' if status == 'started' else 'finished_at'
            value = adapter(event, metadata, 'review_runner:run.json')
            self.assertEqual(value['occurred_at'], metadata[key])
            self.assertEqual(value['actor'], raw['actor'])
            self.assertEqual(value['executor'], raw['executor'])
            self.assertEqual(value['status'], status)
            self.assertEqual(adapter(dict(event, occurred_at=metadata[key]), metadata, 'runner')['occurred_at'], metadata[key])
            self.assertIsNone(adapter(event, {}, 'runner')['occurred_at'])
            self.assertIsNone(adapter(event, {key: None}, 'runner')['occurred_at'])
        for invalid in ('unknown', '2026-10-09T12:00:00', '2026-10-09T12:00:00-05:00', 7):
            with self.assertRaises(ValueError):
                adapter(raw, dict(metadata, finished_at=invalid), 'runner')
        with self.assertRaisesRegex(ValueError, 'conflict'):
            adapter(dict(raw, occurred_at=metadata['started_at']), metadata, 'runner')
        with self.assertRaisesRegex(ValueError, 'conflict'):
            adapter(dict(raw, occurred_at=metadata['finished_at']), {}, 'runner')
        with self.assertRaises(ValueError):
            adapter(dict(raw, status='pending'), metadata, 'runner')
        with self.assertRaises(ValueError):
            adapter(raw, [], 'runner')
        # Equivalent UTC spellings denote the same observed instant.
        equivalent = dict(raw, occurred_at='2026-10-09T12:01:00Z')
        self.assertEqual(adapter(equivalent, metadata, 'runner')['occurred_at'], equivalent['occurred_at'])

    def test_execution_metadata_cli_preserves_identity_without_metrics(self):
        run = self.prepare()
        event_path = self.write('timed-event.json', self.event())
        metadata = self.write('runner.json', {'finished_at': '2026-10-09T12:01:00+00:00'})
        result = subprocess.run([sys.executable, artifacts.__file__, 'record-event', '--run-dir', str(run),
                                 '--event-file', str(event_path), '--execution-metadata', str(metadata)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        observed = self.events(run)[-1]
        self.assertEqual(observed['occurred_at'], '2026-10-09T12:01:00+00:00')
        self.assertEqual(observed['actor'], self.event()['actor'])
        self.assertEqual(observed['provenance'], {'kind': 'tool', 'source': 'review_runner:' + str(metadata)})
        self.assertFalse((run / 'measurements.json').exists())

    def test_historical_time_validation_is_unchanged(self):
        event = dict(self.event(), occurred_at='2026-10-01T12:00:00+00:00')
        legacy = self.legacy_run(4)
        manifest = self.read(legacy / 'cierre.json')
        data, descriptor, observed = artifacts.review_trace.append(
            (legacy / 'trazabilidad.jsonl').read_bytes(), manifest, event)
        artifacts.review_trace.verify(data, descriptor, manifest['run_id'])
        self.assertEqual(observed['occurred_at'], event['occurred_at'])
        before = {p.name: p.read_bytes() for p in legacy.iterdir() if p.is_file()}
        with self.assertRaisesRegex(ValueError, 'unsupported_layout'):
            artifacts.record_event(legacy, self.write('old-time.json', event))
        self.assertEqual(before, {p.name: p.read_bytes() for p in legacy.iterdir() if p.is_file()})
        run = self.prepare()
        with self.assertRaisesRegex(ValueError, 'source'):
            artifacts.record_event(run, self.write('new-time.json', event))
        self.assertEqual(artifacts.validate(run)['state'], 'prepared')

    def test_new_local_event_targets_and_legacy_references(self):
        run = self.prepare()
        for target in ('E000000', 'E000003', 'E999999'):
            event = dict(self.event(), relations=[{'relation': 'follows', 'target': target}])
            before = (run / 'cierre.json').read_bytes()
            with self.assertRaisesRegex(ValueError, 'target'):
                artifacts.record_event(run, self.write('future.json', event))
            self.assertEqual((run / 'cierre.json').read_bytes(), before)
        for target in ('E000001', 'F001', 'C001', 'F-01', 'CR-' + 'b' * 20 + '#E999999', 'https://example.test/old#F-1'):
            event = dict(self.event(), relations=[{'relation': 'supports', 'target': target}])
            data = (run / 'trazabilidad.jsonl').read_bytes()
            with patch.object(Path, 'read_bytes', side_effect=AssertionError('relation resolution must not read files')):
                artifacts.review_trace.validate_local_event_targets(event, data)
            artifacts.record_event(run, self.write('observed.json', event))
            self.assertEqual(self.events(run)[-1]['relations'], event['relations'])
        legacy = self.legacy_run(4)
        manifest = self.read(legacy / 'cierre.json')
        data, descriptor, _ = artifacts.review_trace.append(
            (legacy / 'trazabilidad.jsonl').read_bytes(), manifest,
            dict(self.event(), relations=[{'relation': 'follows', 'target': 'E999999'}]))
        artifacts.review_trace.verify(data, descriptor, manifest['run_id'])
        before = {p.name: p.read_bytes() for p in legacy.iterdir() if p.is_file()}
        with self.assertRaisesRegex(ValueError, 'unsupported_layout'):
            artifacts.validate(legacy)
        self.assertEqual(before, {p.name: p.read_bytes() for p in legacy.iterdir() if p.is_file()})

    def test_actor_executor_and_recorder_remain_distinct(self):
        run = self.prepare()
        event = dict(self.event(), relations=[])
        event['actor'] = {'kind': 'agent', 'name': 'verifier', 'provider_id': 'worker-17'}
        event['executor'] = {'name': 'isolated-verifier', 'provider_id': 'executor-17'}
        artifacts.record_event(run, self.write('identity.json', event))
        artifacts.record_event(run, self.write('unknown-identity.json', dict(self.event(), relations=[])))
        first, second = self.events(run)[-2:]
        self.assertEqual(first['actor'], event['actor'])
        self.assertEqual(first['executor'], event['executor'])
        self.assertEqual(first['recorder'], {'kind': 'helper', 'name': 'review_artifacts', 'provider_id': None})
        self.assertIsNone(second['actor']['provider_id'])
        self.assertIsNone(second['executor']['provider_id'])
        self.assertEqual(first['relations'], [])
        self.assertEqual(second['relations'], [])
        for invalid in (dict(event, relations=[{'relation': 'supports', 'target': 'F001'}] * 25),
                        dict(event, evidence=['x' * 400] * 24)):
            with self.assertRaises(ValueError):
                artifacts.record_event(run, self.write('unbounded.json', invalid))

    def test_trace_interruption_is_pending_and_next_mutation_recovers_evidence(self):
        run = self.prepare()
        event_file = self.write('event.json', self.event())
        original = artifacts.atomic_write
        def interrupt(path, data):
            if Path(path).name == 'trazabilidad.jsonl':
                raise OSError('interrupted trace write')
            original(path, data)
        with patch.object(artifacts, 'atomic_write', side_effect=interrupt), self.assertRaises(OSError):
            artifacts.record_event(run, event_file)
        with self.assertRaisesRegex(ValueError, 'pending'):
            artifacts.validate(run)
        self.register_empty(run)
        self.assertEqual([e['kind'] for e in self.events(run)], ['prepare', 'profile', 'check', 'register'])
        self.assertEqual(self.events(run)[2]['evidence'], ['C01'])

    def test_retention_cannot_pass_gate_if_milestone_planning_is_interrupted(self):
        run = self.prepare()
        with patch.object(artifacts.review_trace, 'append', side_effect=OSError('trace planning interrupted')):
            with self.assertRaises(OSError):
                self.retain(run)
        with self.assertRaisesRegex(ValueError, 'interrupted|pending'):
            artifacts.validate(run, require_retained=True)
        self.retain(run)
        kinds = [e['kind'] for e in self.events(run)]
        self.assertEqual(kinds[:2], ['prepare', 'profile'])
        self.assertEqual(kinds[-1], 'retain')
        self.assertEqual(kinds.count('retain'), 1)

    def test_selected_evidence_inventory_does_not_overflow_compact_retention_event(self):
        run = self.prepare()
        sources = []
        for index in range(30):
            source = self.root / ('selected-' + str(index) + '.txt')
            source.write_text('Preserved evidence ' + str(index), encoding='utf-8')
            sources.append(source)
        self.retain(run, evidence_inputs=sources)
        artifacts.validate(run, require_retained=True)
        self.assertEqual({p.name for p in (run / 'evidence').iterdir()},
                         {p.name for p in sources} | {'context.json', 'briefs.json', 'results.json'})
        self.assertLessEqual(len(self.events(run)[-1]['evidence']), 4)
        self.assertIn('cierre.json#hashes', self.events(run)[-1]['evidence'])

    def test_malformed_identity_and_relation_shapes_raise_value_error_before_mutation(self):
        run = self.prepare()
        before = (run / 'cierre.json').read_bytes()
        for path in [('kind',), ('status',), ('actor', 'kind'), ('provenance', 'kind')]:
            raw = self.event()
            target = raw
            for part in path[:-1]:
                target = target[part]
            target[path[-1]] = []
            with self.subTest(path=path), self.assertRaises(ValueError):
                artifacts.record_event(run, self.write('bad-shape.json', raw))
        raw = self.event()
        raw['relations'][0]['relation'] = []
        with self.assertRaises(ValueError):
            artifacts.record_event(run, self.write('bad-shape.json', raw))
        self.assertEqual(before, (run / 'cierre.json').read_bytes())

    def test_interrupted_ownership_intent_before_manifest_replace_reports_pending(self):
        run = self.prepare()
        event_file = self.write('event.json', self.event())
        original = artifacts.atomic_write
        def interrupt(path, data):
            if Path(path).name == 'cierre.json':
                raise OSError('interrupted pending manifest write')
            original(path, data)
        with patch.object(artifacts, 'atomic_write', side_effect=interrupt), self.assertRaises(OSError):
            artifacts.record_event(run, event_file)
        with self.assertRaisesRegex(ValueError, 'pending'):
            artifacts.validate(run)
        artifacts.record_event(run, event_file)
        self.assertEqual([event['kind'] for event in self.events(run)], ['prepare', 'profile', 'check'])

    def test_events_reject_unbounded_probes_metrics_and_fabricated_recorder_fields(self):
        run = self.prepare()
        invalid = [{'kind': 'search', 'status': 'passed', 'summary': 'one probe'},
                   dict(self.event(), metrics={'tokens': 100}),
                   dict(self.event(), sequence=50),
                   dict(self.event(), summary='x' * 2001)]
        before = (run / 'cierre.json').read_bytes()
        for event in invalid:
            with self.assertRaises(ValueError):
                artifacts.record_event(run, self.write('bad.json', event))
        self.assertEqual(before, (run / 'cierre.json').read_bytes())

    def test_optional_handoff_is_generated_hashed_and_kept_canonical_on_close(self):
        run = self.prepare()
        self.retain(run)
        self.assertFalse((run / 'handoff.md').exists())
        self.assertTrue(callable(getattr(artifacts.review_contract, 'render_handoff', None)))
        self.retain(run, handoff=True)
        self.assertIn('handoff.md', self.read(run / 'cierre.json')['hashes'])
        self.assertIn('handoff', [event['kind'] for event in self.events(run)])
        self.close(run)
        self.assertEqual((run / 'handoff.md').read_text(encoding='utf-8'),
                         artifacts.review_contract.render_handoff(self.read(run / 'review.json'),
                         {'source_record': 'review.json', 'source_report': 'informe.md'}))

    def test_legacy_archives_without_trace_refuse_operation_without_migration(self):
        for schema in (1, 2, 3):
            with self.subTest(schema=schema):
                run = self.prepare()
                self.retain(run)
                _, manifest, marker = artifacts._load_run(run)
                manifest['schema_version'] = schema
                manifest['hashes'].pop('trazabilidad.jsonl')
                manifest.pop('trace')
                (run / 'trazabilidad.jsonl').unlink()
                artifacts._save_manifest(run, manifest, marker)
                before = (run / 'cierre.json').read_bytes()
                with self.assertRaisesRegex(ValueError, 'unsupported_layout'):
                    artifacts.validate(run, require_retained=True)
                with self.assertRaisesRegex(ValueError, 'unsupported_layout'):
                    self.close(run)
                self.assertEqual((run / 'cierre.json').read_bytes(), before)
                self.assertFalse((run / 'trazabilidad.jsonl').exists())
                self.assertNotIn('trace', self.read(run / 'cierre.json'))

    def test_trace_chain_and_count_checked_even_if_whole_file_digest_matches(self):
        run = self.prepare()
        self.retain(run)
        _, manifest, marker = artifacts._load_run(run)
        events = self.events(run)
        events[-1]['sequence'] = len(events) + 1
        data = b''.join(json.dumps(event).encode('utf-8') + b'\n' for event in events)
        (run / 'trazabilidad.jsonl').write_bytes(data)
        manifest['hashes']['trazabilidad.jsonl'] = artifacts._digest(data)
        artifacts._save_manifest(run, manifest, marker)
        with self.assertRaisesRegex(ValueError, 'sequence'):
            artifacts.validate(run, require_retained=True)

    def test_handoff_context_survives_source_cleanup_and_close(self):
        session = self.root / 'handoff-inputs'
        session.mkdir()
        context = {'source_record': 'review.json', 'source_report': 'informe.md',
                   'requirements': [{'title': 'Accepted scope', 'reference': 'https://example.test/spec', 'identity': 'revision 2'}],
                   'plan': ['https://example.test/plan'], 'decisions_pending': ['Confirm the deployment window']}
        path = session / 'handoff-context.json'
        path.write_text(json.dumps(context), encoding='utf-8')
        run = self.prepare(temporary_paths=[session])
        self.retain(run, handoff=True, handoff_context_input=path)
        path.unlink()
        session.rmdir()
        artifacts.close(run, cleanup='complete')
        retained = self.read(run / 'cierre.json')
        self.assertEqual(retained['handoff_context'], context)
        handoff = (run / 'handoff.md').read_text(encoding='utf-8')
        self.assertIn('revision 2', handoff)
        self.assertIn('Confirm the deployment window', handoff)
        self.assertEqual(handoff, artifacts.review_contract.render_handoff(self.read(run / 'review.json'), context))

    def test_handoff_context_requires_explicit_request_and_rejects_unrelated_data(self):
        run = self.prepare()
        context = self.write('context.json', {'executors': [], 'private': 'do not archive'})
        with self.assertRaises(ValueError):
            artifacts.retain(run, self.final, handoff_context_input=context)
        with self.assertRaises(ValueError):
            artifacts.retain(run, self.final, handoff=True, handoff_context_input=context)
        self.assertFalse((run / 'handoff.md').exists())
        self.assertNotIn('handoff_context', self.read(run / 'cierre.json'))

    def test_handoff_local_provenance_requires_selected_durable_evidence(self):
        run = self.prepare()
        context = self.write('handoff-context.json', {'requirements': ['evidence/spec.md']})
        with self.assertRaisesRegex(ValueError, 'retained evidence'):
            self.retain(run, handoff=True, handoff_context_input=context)
        spec = self.root / 'spec.md'
        spec.write_text('Agreed behavior', encoding='utf-8')
        self.retain(run, handoff=True, handoff_context_input=context, evidence_inputs=[spec])
        spec.unlink()
        self.close(run)
        self.assertIn('evidence/spec.md', (run / 'handoff.md').read_text(encoding='utf-8'))
        self.assertEqual((run / 'evidence/spec.md').read_text(encoding='utf-8'), 'Agreed behavior')


if __name__ == '__main__':
    unittest.main()
