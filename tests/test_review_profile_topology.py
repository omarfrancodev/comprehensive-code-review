"""Schema-12 profile contract and compatibility checks."""
import copy
import unittest

from script_test_support import enable_package_imports
enable_package_imports()
from ccr.contracts import review
from traceability_fixtures import record11
from profile_topology_fixtures import record12


class ProfileTopologyTests(unittest.TestCase):
    def test_schema12_retains_schema11_fields_and_rejects_unknown_version(self):
        record = record12()
        self.assertEqual(review.validate(record), [])
        self.assertEqual(sum(len(area['dimensions']) for area in record['coverage']['areas']), 27)
        self.assertTrue(all(check['purpose'] for check in record['checks']))
        unsupported = copy.deepcopy(record)
        unsupported['schema_version'] = 13
        self.assertTrue(any('unsupported version' in error for error in review.validate(unsupported)))

    def test_schema12_rejects_missing_purpose_and_dimension(self):
        record = record12()
        missing_purpose = copy.deepcopy(record)
        del missing_purpose['checks'][0]['purpose']
        self.assertTrue(any('purpose' in error for error in review.validate(missing_purpose)))
        missing_dimension = copy.deepcopy(record)
        missing_dimension['coverage']['areas'][0]['dimensions'].pop()
        self.assertTrue(any('dimension' in error for error in review.validate(missing_dimension)))

    def test_schema11_fixture_remains_valid(self):
        self.assertEqual(review.validate(record11()), [])
