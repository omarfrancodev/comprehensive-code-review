"""PR37 finish recovery and explicit-current-input guidance regressions."""
import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from script_test_support import enable_package_imports

enable_package_imports()
from ccr.archive import inspection, lifecycle, transactions
from ccr.cli import artifacts
import test_review_closure_consistency as guided
import test_review_disclosure_close_recovery as disclosure


class FinishRecoveryTests(unittest.TestCase):
    retained_cleaned_run = disclosure.DisclosureCloseRecoveryTests.retained_cleaned_run

    def test_finish_replays_final_close_trace_without_new_observation(self):
        # Excluding complete state from automatic replay strands the owned final append.
        for boundary in ('before', 'after'):
            with self.subTest(boundary=boundary):
                case, run, _ = self.retained_cleaned_run()
                original = transactions.atomic_write

                def interrupt(path, data, **kwargs):
                    if Path(path).name == 'trazabilidad.jsonl':
                        if boundary == 'after':
                            original(path, data, **kwargs)
                        raise OSError('final close trace interrupted')
                    return original(path, data, **kwargs)

                with patch.object(transactions, 'atomic_write', side_effect=interrupt):
                    with self.assertRaisesRegex(OSError, 'final close trace interrupted'):
                        lifecycle.close(run, cleanup='complete')
                manifest = case.read(run / 'cierre.json')
                self.assertEqual(manifest['state'], 'complete')
                self.assertIn('pending_trace', manifest)
                observation = copy.deepcopy(manifest['close_observation'])
                before = case.snapshot(run)
                self.assertEqual(inspection.inspect_run(run)['integrity']['status'], 'recoverable')
                with self.assertRaises(ValueError):
                    lifecycle.validate(run, require_complete=True)
                self.assertEqual(case.snapshot(run), before)

                completed, code = artifacts.finish_run(run)

                self.assertEqual((code, completed['status']), (0, 'complete'))
                self.assertEqual(lifecycle.validate(run, require_complete=True)['state'], 'complete')
                final = case.read(run / 'cierre.json')
                self.assertNotIn('pending_trace', final)
                self.assertEqual(final['close_observation'], observation)
                events = [json.loads(line) for line in
                          (run / 'trazabilidad.jsonl').read_bytes().splitlines()]
                self.assertEqual(len([event for event in events if event['kind'] == 'close']), 1)
                complete = case.snapshot(run)
                self.assertEqual(artifacts.finish_run(run)[1], 0)
                self.assertEqual(case.snapshot(run), complete)


class ExplicitCurrentSummaryTests(unittest.TestCase):
    def test_summary_requires_verification_of_explicit_unknown_current_inputs(self):
        # Falling through unknown freshness recommends retention despite incomplete current evidence.
        fixture = guided.ClosureConsistencyTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        case = fixture.make_guided_run(complete_capture=True, explicit_identities=True)
        run = case['run']
        current = fixture.read(run / 'cierre.json')['review_inputs']
        current['profile'] = fixture.read(case['record'])['profile']
        current['source_set_complete'] = False
        current['sources'] = {}
        candidate = dict(context_input=case['context'], input_file=case['record'],
                         evidence_inputs=case['evidence_inputs'])
        self.assertEqual(artifacts.preflight_run(run, phase='retain', **candidate)[1], 0)
        self.assertEqual(inspection.inspect_run(run, current_inputs=current)['freshness']['status'], 'unknown')
        before = fixture.snapshot(run)

        args = ['inspect', '--run-dir', run, '--summary', '--context-input', case['context'],
                '--input', case['record']]
        for evidence in case['evidence_inputs']:
            args.extend(['--evidence-input', evidence])
        code, status = fixture.archive_command(
            *args, '--current-inputs', fixture.write('current-incomplete.json', current))

        self.assertEqual(code, 0)
        self.assertEqual((status['status'], status['gate'], status['next_action']),
                         ('pending', 'current_inputs', 'verify_current_inputs'))
        self.assertTrue(status['reason'])
        self.assertEqual(fixture.snapshot(run), before)
        self.assertEqual(fixture.archive_command(*args)[1]['next_action'], 'retain')
