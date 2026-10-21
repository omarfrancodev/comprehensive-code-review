"""Contract tests for result-validation and profile boundaries."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))


class ScriptContractBoundaryTests(unittest.TestCase):
    def test_invalid_record_accumulates_errors_without_mutation(self):
        from ccr.contracts.review import validate
        record = {'schema_version': 99}
        before = deepcopy(record)
        errors = validate(record)
        self.assertIsInstance(errors, list)
        self.assertTrue(any('unsupported version' in error for error in errors))
        self.assertEqual(record, before)

    def test_profile_aliases_keep_their_meaning(self):
        from ccr.workflow.profiles import canonical_profile
        self.assertEqual(canonical_profile('economy'), 'focused')
        self.assertEqual(canonical_profile('balanced'), 'standard')