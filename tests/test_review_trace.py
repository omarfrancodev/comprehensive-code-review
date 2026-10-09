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
    retain = fixtures.ArchiveTests.retain
    close = fixtures.ArchiveTests.close

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
        artifacts.register(run, [])
        self.retain(run)
        artifacts.validate(run, require_retained=True, record_checkpoint=True)
        self.close(run)
        events = self.events(run)
        self.assertEqual([event['kind'] for event in events], ['prepare', 'register', 'retain', 'validation', 'close'])
        self.assertEqual([event['sequence'] for event in events], list(range(1, 6)))
        self.assertTrue(all(datetime.fromisoformat(event['recorded_at']).utcoffset().total_seconds() == 0 for event in events))
        self.assertEqual(self.read(run / 'cierre.json')['schema_version'], 4)
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

    def test_tool_execution_time_is_preserved_separately_from_recording_time(self):
        run = self.prepare()
        event = self.event()
        event.update(occurred_at='2026-10-01T12:00:00+00:00', provenance={'kind': 'tool', 'source': 'provider-result:check-1'})
        artifacts.record_event(run, self.write('timed.json', event))
        recorded = self.events(run)[-1]
        self.assertEqual(recorded['occurred_at'], '2026-10-01T12:00:00+00:00')
        self.assertNotEqual(recorded['recorded_at'], recorded['occurred_at'])
        self.assertIsNone(self.events(run)[0]['occurred_at'])
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
        artifacts.register(run, [])
        self.assertEqual([e['kind'] for e in self.events(run)], ['prepare', 'check', 'register'])
        self.assertEqual(self.events(run)[1]['evidence'], ['C01'])

    def test_retention_cannot_pass_gate_if_milestone_planning_is_interrupted(self):
        run = self.prepare()
        with patch.object(artifacts.review_trace, 'append', side_effect=OSError('trace planning interrupted')):
            with self.assertRaises(OSError):
                self.retain(run)
        with self.assertRaisesRegex(ValueError, 'interrupted|pending'):
            artifacts.validate(run, require_retained=True)
        self.retain(run)
        self.assertEqual([e['kind'] for e in self.events(run)], ['prepare', 'retain'])

    def test_selected_evidence_inventory_does_not_overflow_compact_retention_event(self):
        run = self.prepare()
        sources = []
        for index in range(30):
            source = self.root / ('selected-' + str(index) + '.txt')
            source.write_text('Preserved evidence ' + str(index), encoding='utf-8')
            sources.append(source)
        artifacts.retain(run, self.final, evidence_inputs=sources)
        artifacts.validate(run, require_retained=True)
        self.assertEqual(len(list((run / 'evidence').iterdir())), 30)
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
        self.assertEqual([event['kind'] for event in self.events(run)], ['prepare', 'check'])

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
        artifacts.retain(run, self.final, handoff=True)
        self.assertIn('handoff.md', self.read(run / 'cierre.json')['hashes'])
        self.assertIn('handoff', [event['kind'] for event in self.events(run)])
        self.close(run)
        self.assertEqual((run / 'handoff.md').read_text(encoding='utf-8'),
                         artifacts.review_contract.render_handoff(self.read(run / 'review.json'),
                         {'source_record': 'review.json', 'source_report': 'informe.md'}))

    def test_legacy_archives_validate_and_close_without_trace_or_migration(self):
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
                self.assertEqual(artifacts.validate(run, require_retained=True)['schema_version'], schema)
                self.assertEqual((run / 'cierre.json').read_bytes(), before)
                self.close(run)
                self.assertFalse((run / 'trazabilidad.jsonl').exists())
                self.assertNotIn('trace', self.read(run / 'cierre.json'))

    def test_trace_chain_and_count_checked_even_if_whole_file_digest_matches(self):
        run = self.prepare()
        self.retain(run)
        _, manifest, marker = artifacts._load_run(run)
        events = self.events(run)
        events[-1]['sequence'] = 8
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
        artifacts.retain(run, self.final, handoff=True, handoff_context_input=path)
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
        context = self.write('context.json', {'requirements': ['evidence/spec.md']})
        with self.assertRaisesRegex(ValueError, 'retained evidence'):
            artifacts.retain(run, self.final, handoff=True, handoff_context_input=context)
        spec = self.root / 'spec.md'
        spec.write_text('Agreed behavior', encoding='utf-8')
        artifacts.retain(run, self.final, handoff=True, handoff_context_input=context, evidence_inputs=[spec])
        spec.unlink()
        self.close(run)
        self.assertIn('evidence/spec.md', (run / 'handoff.md').read_text(encoding='utf-8'))
        self.assertEqual((run / 'evidence/spec.md').read_text(encoding='utf-8'), 'Agreed behavior')


if __name__ == '__main__':
    unittest.main()
