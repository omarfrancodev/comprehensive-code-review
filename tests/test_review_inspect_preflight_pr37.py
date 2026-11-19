"""Read-only finalization guidance must agree with real guided writes."""
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from script_test_support import enable_package_imports, run_cli

enable_package_imports()
from ccr.archive import compact, lifecycle, retention, transactions
from ccr.cli import artifacts
from ccr.contracts import preflight, review
from ccr.shared.encoding import archive_bytes
from test_review_coverage13 import record13
import test_review_closure_consistency as guided
import test_review_compact_archive as compact_fixtures


class InspectPreflightPR37Tests(unittest.TestCase):
    def guided_run(self):
        fixture = guided.ClosureConsistencyTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        case = fixture.make_guided_run(complete_capture=True, explicit_identities=True)
        return fixture, case

    def cli(self, fixture, *args):
        result = run_cli('artifacts', [str(arg) for arg in args], cwd=fixture.root)
        return result, json.loads(result.stdout or result.stderr)

    def candidate_args(self, case):
        args = ['--context-input', case['context'], '--input', case['record']]
        for source in case['evidence_inputs']:
            args.extend(['--evidence-input', source])
        return args

    def retain13(self, case):
        return retention.retain(case['run'], case['record'], context_input=case['context'],
            evidence_inputs=case['evidence_inputs'], expected_schema=13,
            unavailable_reason='Fixture has no provider counters')

    def interrupt_final_close(self, fixture, case, boundary):
        fixture.retain(case)
        original = transactions.atomic_write

        def interrupt(path, data, **kwargs):
            if Path(path).name == 'trazabilidad.jsonl':
                if boundary == 'after':
                    original(path, data, **kwargs)
                raise OSError('interrupted final close trace')
            return original(path, data, **kwargs)

        with patch.object(transactions, 'atomic_write', side_effect=interrupt):
            with self.assertRaisesRegex(OSError, 'interrupted final close trace'):
                lifecycle.close(case['run'], cleanup='not_needed')

    def test_summary_recommends_exact_close_retry_before_or_after_trace_replacement(self):
        # Checking complete before its final pending append incorrectly recommends preserve.
        for boundary in ('before', 'after'):
            with self.subTest(boundary=boundary):
                fixture, case = self.guided_run()
                run = case['run']
                self.interrupt_final_close(fixture, case, boundary)
                observation = fixture.read(run / 'cierre.json')['close_observation']
                before = fixture.snapshot(run)
                result, status = self.cli(fixture, 'inspect', '--run-dir', run, '--summary')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual((status['status'], status['gate'], status['next_action']),
                                 ('pending', 'close', 'retry_close'))
                self.assertEqual(fixture.snapshot(run), before)
                finished, status = self.cli(fixture, 'finish', '--run-dir', run)
                self.assertEqual((finished.returncode, status['status']), (0, 'complete'), finished.stderr)
                self.assertEqual(fixture.read(run / 'cierre.json')['close_observation'], observation)
                events = [json.loads(line) for line in (run / 'trazabilidad.jsonl').read_bytes().splitlines()]
                self.assertEqual(len([row for row in events if row['kind'] == 'close']), 1)

    def test_summary_preserves_a_malformed_final_close_transition(self):
        fixture, case = self.guided_run()
        run = case['run']
        self.interrupt_final_close(fixture, case, 'before')
        manifest = fixture.read(run / 'cierre.json')
        manifest['pending_trace']['sha256'] = '0' * 64
        marker = fixture.read(run / transactions.MARKER)
        transactions.save_manifest(run, manifest, marker)
        before = fixture.snapshot(run)
        _, status = self.cli(fixture, 'inspect', '--run-dir', run, '--summary')
        self.assertEqual(status['next_action'], 'preserve')
        self.assertEqual(fixture.snapshot(run), before)

    def test_summary_preserves_close_trace_without_its_durable_observation(self):
        fixture, case = self.guided_run()
        run = case['run']
        self.interrupt_final_close(fixture, case, 'before')
        manifest = fixture.read(run / 'cierre.json')
        manifest.pop('close_observation')
        marker = fixture.read(run / transactions.MARKER)
        transactions.save_manifest(run, manifest, marker)
        before = fixture.snapshot(run)
        _, status = self.cli(fixture, 'inspect', '--run-dir', run, '--summary')
        self.assertEqual(status['next_action'], 'preserve')
        self.assertEqual(fixture.snapshot(run), before)

    def test_summary_preserves_complete_manifest_without_retained_result(self):
        fixture, case = self.guided_run()
        run = case['run']
        self.interrupt_final_close(fixture, case, 'before')
        manifest = fixture.read(run / 'cierre.json')
        manifest['retained'] = False
        marker = fixture.read(run / transactions.MARKER)
        transactions.save_manifest(run, manifest, marker)
        before = fixture.snapshot(run)
        _, status = self.cli(fixture, 'inspect', '--run-dir', run, '--summary')
        self.assertEqual(status['next_action'], 'preserve')
        self.assertEqual(fixture.snapshot(run), before)

    def test_explicit_null_current_inputs_is_rejected_without_retention_guidance(self):
        # JSON null must not enter the legacy no-current-inputs branch.
        fixture, case = self.guided_run()
        current = fixture.write('explicit-null.json', None)
        before = fixture.snapshot(case['run'])
        for flags in ([], ['--summary', *self.candidate_args(case)]):
            with self.subTest(summary=bool(flags)):
                result, status = self.cli(fixture, 'inspect', '--run-dir', case['run'],
                                          '--current-inputs', current, *flags)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('object', status['error'])
        self.assertEqual(fixture.snapshot(case['run']), before)

    def test_current_inputs_valid_object_and_absent_option_preserve_their_behavior(self):
        fixture, case = self.guided_run()
        args = ['inspect', '--run-dir', case['run'], '--summary', *self.candidate_args(case)]
        current = fixture.read(case['run'] / 'cierre.json')['review_inputs']
        current['profile'] = fixture.read(case['record'])['profile']
        for flags in ([], ['--current-inputs', fixture.write('current.json', current)]):
            with self.subTest(explicit=bool(flags)):
                result, status = self.cli(fixture, *args, *flags)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(status['next_action'], 'retain')
        for invalid in (False, 42, [], 'invalid'):
            with self.subTest(invalid=invalid):
                result, status = self.cli(fixture, *args,
                    '--current-inputs', fixture.write('current-invalid.json', invalid))
                self.assertTrue(result.returncode != 0 or status['next_action'] != 'retain')

    def assessed_candidate(self, fixture, case, version):
        original = fixture.read(case['record'])
        record = record13()
        for field in ('scope', 'review_id', 'description', 'profile'):
            record[field] = original[field]
        record['coverage']['execution'] = original['coverage']['execution']
        record['checks'] = []
        record['coverage']['evidence'][0]['reference'] = 'evidence/notes.json'
        digest = hashlib.sha256(case['notes']).hexdigest()
        record['assessment'] = dict(schema_version=version,
            scope={**{key: record['scope'][key] for key in ('base', 'head', 'snapshot')},
                   'delta': [dict(detail='Inspected captured review notes', evidence_ids=['EV001'],
                       sources=[dict(reference='evidence/notes.json', sha256=digest)])]},
            previous=None, findings=[])
        if version == 2:
            record['assessment'].update(lineage=[], observed_hashes=[digest])
        self.assertEqual(review.validate(record), [])
        case['record'] = fixture.write('assessed-final.json', record)
        return record

    def test_retain_preflight_and_summary_refuse_historical_assessment_v1(self):
        fixture, case = self.guided_run()
        record = self.assessed_candidate(fixture, case, 1)
        before = fixture.snapshot(case['run'])
        result, diagnostic = self.cli(fixture, 'preflight', '--run-dir', case['run'],
                                      '--phase', 'retain', *self.candidate_args(case))
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertFalse(diagnostic['ready'])
        self.assertTrue(any(row['field'] == 'candidate.assessment' for row in diagnostic['issues']))
        _, status = self.cli(fixture, 'inspect', '--run-dir', case['run'], '--summary',
                             *self.candidate_args(case))
        self.assertEqual(status['gate'], 'retain_preflight')
        self.assertNotEqual(status['next_action'], 'retain')
        with self.assertRaisesRegex(ValueError, 'version 2'):
            self.retain13(case)
        self.assertEqual(fixture.snapshot(case['run']), before)
        self.assertEqual(review.validate(record), [])

    def test_pure_preflight_uses_the_same_guided_assessment_gate(self):
        fixture, case = self.guided_run()
        record = self.assessed_candidate(fixture, case, 1)
        manifest = fixture.read(case['run'] / 'cierre.json')
        context = fixture.read(case['context'])
        sources = {'evidence/' + path.name: path.read_bytes() for path in case['evidence_inputs']}
        sources['evidence/context.json'] = archive_bytes(context)
        diagnostic = preflight.validate_preflight(phase='retain', manifest=manifest,
            logical_scope=manifest['logical_scope'], selection=None,
            context=context, record=record, sources=sources)
        self.assertFalse(diagnostic['ready'])
        self.assertTrue(any(row['field'] == 'candidate.assessment' for row in diagnostic['issues']))

    def test_assessment_v2_passes_preflight_and_full_retention(self):
        fixture, case = self.guided_run()
        self.assessed_candidate(fixture, case, 2)
        result, diagnostic = self.cli(fixture, 'preflight', '--run-dir', case['run'],
                                      '--phase', 'retain', *self.candidate_args(case))
        self.assertEqual((result.returncode, diagnostic['ready']), (0, True), diagnostic)
        self.retain13(case)
        lifecycle.close(case['run'], cleanup='not_needed')
        self.assertEqual(lifecycle.validate(case['run'], require_complete=True)['state'], 'complete')

    def test_full_reader_accepts_historical_assessment_v1(self):
        fixture, case = self.guided_run()
        self.assessed_candidate(fixture, case, 1)
        # Only the new-write gate is bypassed to reconstruct a historical archive.
        with patch.object(retention, 'require_followup_assessment'), patch.object(
                preflight, 'require_followup_assessment'):
            self.retain13(case)
        lifecycle.close(case['run'], cleanup='not_needed')
        before = fixture.snapshot(case['run'])
        checked = lifecycle.validate(case['run'], require_complete=True)
        self.assertEqual(checked['state'], 'complete')
        _, status = self.cli(fixture, 'inspect', '--run-dir', case['run'], '--summary')
        self.assertEqual(status['status'], 'complete')
        self.assertEqual(fixture.snapshot(case['run']), before)

    def test_legacy_retain_accepts_v1_while_explicit_guided_schema13_refuses_it(self):
        # Retain's legacy admission must not inherit the new guided preflight default.
        fixture, case = self.guided_run()
        self.assessed_candidate(fixture, case, 1)
        before = fixture.snapshot(case['run'])
        with self.assertRaisesRegex(ValueError, 'version 2'):
            self.retain13(case)
        self.assertEqual(fixture.snapshot(case['run']), before)
        retention.retain(case['run'], case['record'], context_input=case['context'],
            evidence_inputs=case['evidence_inputs'], expected_schema=None,
            unavailable_reason='Fixture has no provider counters')
        lifecycle.close(case['run'], cleanup='not_needed')
        before = fixture.snapshot(case['run'])
        self.assertEqual(lifecycle.validate(case['run'], require_complete=True)['state'], 'complete')
        self.assertEqual(fixture.snapshot(case['run']), before)

    def test_ordinary_schema13_without_assessment_still_passes_preflight_and_retention(self):
        fixture, case = self.guided_run()
        record = self.assessed_candidate(fixture, case, 2)
        record.pop('assessment')
        case['record'] = fixture.write('ordinary-final.json', record)
        result, diagnostic = self.cli(fixture, 'preflight', '--run-dir', case['run'],
                                      '--phase', 'retain', *self.candidate_args(case))
        self.assertEqual((result.returncode, diagnostic['ready']), (0, True), diagnostic)
        self.retain13(case)
        lifecycle.close(case['run'], cleanup='not_needed')
        self.assertEqual(lifecycle.validate(case['run'], require_complete=True)['state'], 'complete')

    def test_compact_writer_refuses_v1_but_historical_reader_accepts_it(self):
        fixture = compact_fixtures.CompactPrepareTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        prepared = fixture.prepare()
        record, sources = fixture.record_and_sources(prepared)
        record['assessment'] = dict(schema_version=1,
            scope={**{key: record['scope'][key] for key in ('base', 'head', 'snapshot')},
                   'delta': [dict(detail='Inspected pinned flow', evidence_ids=['EV001'], sources=[])]},
            previous=None, findings=[])
        self.assertEqual(review.validate(record), [])
        with self.assertRaisesRegex(ValueError, 'version 2'):
            compact.create_compact(prepared, record, current_inputs=fixture.inputs, sources=sources)
        # Reconstruct a historical v1 artifact by bypassing only new-write admission.
        with patch.object(compact, 'require_followup_assessment'):
            saved = compact.create_compact(prepared, record, current_inputs=fixture.inputs, sources=sources)
        before = {path: path.read_bytes() for path in Path(saved['run_dir']).rglob('*') if path.is_file()}
        historical = compact.read_compact(saved['run_dir'])
        self.assertEqual(historical['record']['assessment']['schema_version'], 1)
        self.assertEqual({path: path.read_bytes() for path in before}, before)

    def test_compact_writer_and_reader_accept_assessment_v2(self):
        fixture = compact_fixtures.CompactPrepareTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        prepared = fixture.prepare()
        record, sources = fixture.record_and_sources(prepared)
        proof = b'Pinned producer and consumer flow inspected'
        digest = hashlib.sha256(proof).hexdigest()
        record['coverage']['evidence'][0]['reference'] = 'evidence/proof.txt'
        record['assessment'] = dict(schema_version=2,
            scope={**{key: record['scope'][key] for key in ('base', 'head', 'snapshot')},
                   'delta': [dict(detail='Inspected pinned flow', evidence_ids=['EV001'],
                       sources=[dict(reference='evidence/proof.txt', sha256=digest)])]},
            previous=None, findings=[], lineage=[], observed_hashes=[digest])
        sources['evidence/proof.txt'] = proof
        saved = compact.create_compact(prepared, record, current_inputs=fixture.inputs, sources=sources)
        self.assertEqual(compact.read_compact(saved['run_dir'])['record']['assessment']['schema_version'], 2)
