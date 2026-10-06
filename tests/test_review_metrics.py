"""Real usage stays distinct from estimates; runner output capture must not imply truth."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
spec = importlib.util.spec_from_file_location('review_metrics', SCRIPTS / 'review_metrics.py') if (SCRIPTS / 'review_metrics.py').exists() else None
metrics = importlib.util.module_from_spec(spec) if spec else None
if spec:
    spec.loader.exec_module(metrics)


class UsageTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(metrics, 'per-phase measurement helper is missing')

    def test_cached_and_reasoning_are_subsets_not_additional_tokens(self):
        result = metrics.normalize_usage({'input_tokens': 5000, 'output_tokens': 900,
                                          'cached_input_tokens': 1500, 'reasoning_tokens': 200})
        self.assertEqual(result['total_tokens'], 5900)
        self.assertEqual(result['uncached_input_tokens'], 3500)
        self.assertIsNone(result['credits'])
        self.assertIsNone(result['cost'])

    def test_missing_usage_remains_unknown_while_measured_zero_is_zero(self):
        unknown = metrics.normalize_usage(None)
        self.assertIsNone(unknown['total_tokens'])
        self.assertIsNone(unknown['input_tokens'])
        self.assertEqual(metrics.normalize_usage({'input_tokens': 0, 'output_tokens': 0})['total_tokens'], 0)

    def test_invalid_negative_bool_nonfinite_and_impossible_subsets_are_rejected(self):
        for value in [{'input_tokens': -1}, {'input_tokens': True}, {'output_tokens': 1.5},
                      {'input_tokens': 5, 'cached_input_tokens': 6}, {'output_tokens': 2, 'reasoning_tokens': 3},
                      {'credits': float('nan')}, {'cost': 1}, {'unknown': 4}, []]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                metrics.normalize_usage(value)

    def test_partial_aggregation_exposes_unknowns_and_does_not_double_count(self):
        runs = [{'usage': metrics.normalize_usage({'input_tokens': 10, 'output_tokens': 2, 'credits': 0.5})},
                {'usage': metrics.normalize_usage(None)}]
        result = metrics.summarize(runs)
        self.assertIsNone(result['total_tokens']['total'])
        self.assertEqual(result['total_tokens']['known_subtotal'], 12)
        self.assertEqual(result['total_tokens']['unknown_runs'], 1)
        self.assertIsNone(result['credits']['total'])
        self.assertEqual(result['credits']['known_subtotal'], 0.5)

    def test_money_in_different_currencies_is_not_summed(self):
        runs = [{'usage': metrics.normalize_usage({'cost': 1, 'currency': 'USD'})},
                {'usage': metrics.normalize_usage({'cost': 2, 'currency': 'EUR'})}]
        self.assertEqual(metrics.summarize(runs)['cost_by_currency'], {'EUR': 2, 'USD': 1})


class RunnerCaptureTests(unittest.TestCase):
    def run_adapter(self, root, usage_text=None):
        adapter = root / 'adapter.py'
        adapter.write_text("import pathlib, sys\nprint('captured output')\n" +
                           ("pathlib.Path(sys.argv[1], 'usage.json').write_text(" + repr(usage_text) + ", encoding='utf-8')\n" if usage_text is not None else ''), encoding='utf-8')
        config = root / 'adapter.json'
        config.write_text(json.dumps({'fresh_context': True, 'argv': [sys.executable, str(adapter),
                                                                     '{output_dir}', '{prompt_file}', '{workspace}']}), encoding='utf-8')
        prompt = root / 'prompt.md'
        prompt.write_text('Bounded verification', encoding='utf-8')
        result = subprocess.run([sys.executable, '-B', str(SCRIPTS / 'review_runner.py'),
                                 '--config', str(config), '--prompt-file', str(prompt), '--workspace', str(root),
                                 '--output-dir', str(root / 'out'), '--role', 'verifier', '--phase', 'verification'],
                                capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads((root / 'out' / 'run.json').read_text(encoding='utf-8'))

    def test_runner_captures_normalized_adapter_usage_and_real_output_size(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            record = self.run_adapter(root, '{"input_tokens":100,"output_tokens":20,"credits":0.25}')
            self.assertEqual(record['usage']['total_tokens'], 120)
            self.assertEqual(record['usage']['credits'], 0.25)
            self.assertEqual(record['role'], 'verifier')
            self.assertEqual(record['phase'], 'verification')
            self.assertEqual(record['stdout_bytes'], (root / 'out' / 'stdout.txt').stat().st_size)
            self.assertFalse(record['review_validated'])

    def test_runner_counts_invocations_without_guessing_provider_session_count(self):
        with tempfile.TemporaryDirectory() as directory:
            record = self.run_adapter(Path(directory))
            self.assertIsNone(record['sessions'])
            self.assertEqual(record['executor_invocations'], 1)

    def test_oversized_credit_number_is_invalid_and_preserves_completed_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            record = self.run_adapter(Path(directory), '{"credits":1' + '0' * 400 + '}')
            self.assertEqual(record['status'], 'completed')
            self.assertEqual(record['usage_status'], 'invalid')
            self.assertIsNone(record['usage']['credits'])

    def test_runner_keeps_missing_usage_unknown_and_malformed_usage_visible(self):
        for usage in (None, '{"input_tokens":true}'):
            with self.subTest(usage=usage), tempfile.TemporaryDirectory() as directory:
                record = self.run_adapter(Path(directory), usage)
                self.assertIsNone(record['usage']['total_tokens'])
                self.assertEqual(record['usage_status'], 'unavailable' if usage is None else 'invalid')
                self.assertEqual(record['status'], 'completed')


if __name__ == '__main__':
    unittest.main()
