import unittest
from unittest.mock import patch
from script_test_support import enable_package_imports

enable_package_imports()
from ccr.contracts.checks import purpose_errors
from ccr.execution import checks as capture
from ccr.contracts import receipts
import test_review_check_receipts as old
from traceability_fixtures import receipt2_bundle, PURPOSE


class PurposeTests(unittest.TestCase):
    def test_unencodable_purpose_never_creates_attempt_or_runs_process(self):
        import tempfile
        from pathlib import Path
        for value in ('Verify \ud800', 'Verify \udfff'):
            with self.subTest(value=ascii(value)), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                target = root / 'attempt'
                with patch.object(capture, '_validate_owned_workspace', return_value=(root, target)) as owned:
                    with patch.object(capture.subprocess, 'run') as process:
                        process.return_value.returncode = 0
                        observed_error = None
                        try:
                            capture.capture_check(check_id='C001', purpose=value, argv=['python', '-V'],
                                command='python -V', cwd=str(root), executor_workspace=str(root),
                                revision='head', executor='X1', output_dir=str(target))
                        except ValueError as error:
                            observed_error = error
                        process.assert_not_called()
                        owned.assert_not_called()
                        self.assertFalse(target.exists())
                        self.assertIsInstance(observed_error, ValueError)
                        self.assertIn('purpose', str(observed_error))
        self.assertEqual(purpose_errors('Verify Unicode \U0001f600', 'purpose'), [])

    def test_purpose_validation_precedes_any_process_or_attempt(self):
        for value in (None, '', ' ', 'x' * 4001, 'objetivo\nresultado', 'a\tb'):
            self.assertTrue(purpose_errors(value, 'purpose'))
            with patch.object(capture, '_validate_owned_workspace') as owned:
                with patch.object(capture.subprocess, 'run') as process:
                    with self.assertRaises(ValueError):
                        capture.capture_check(check_id='C001', purpose=value, argv=['python', '-V'],
                            command='python -V', cwd='unused', executor_workspace='unused',
                            revision='head', executor='X1', output_dir='unused')
                    owned.assert_not_called()
                    process.assert_not_called()

    def test_receipt2_binds_purpose_and_keeps_legacy_receipt1(self):
        receipt, sources, check, executors = receipt2_bundle()
        self.assertEqual(receipts.validate_receipt(receipt, sources, check=check, executors=executors), [])
        receipt['purpose'] = 'Otro objetivo'
        self.assertTrue(receipts.validate_receipt(receipt, sources, check=check, executors=executors))
        old_check, old_executors = old.valid_binding()
        old_receipt = old.valid_receipt()
        old_sources = {old_receipt['stdout']['reference']: b'', old_receipt['stderr']['reference']: b''}
        self.assertEqual(receipts.validate_receipt(old_receipt, old_sources,
                         check=old_check, executors=old_executors), [])

    def test_missing_request_purpose_is_rejected(self):
        import json
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'request.json'
            path.write_text(json.dumps(dict(check_id='C001', argv=['python', '-V'], command='python -V',
                cwd='unused', executor_workspace='unused', revision='head', executor='X1')), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'purpose'):
                capture._read_request(path)
