"""Schema-12 profile contract and compatibility checks."""
import copy
import unittest

from script_test_support import enable_package_imports
enable_package_imports()
from ccr.contracts import review
from traceability_fixtures import record11
from profile_topology_fixtures import record12
from recovery_fixtures import record10


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

    def test_schema12_discovery_boundaries_for_both_selection_sources(self):
        for source in ('automatic', 'explicit'):
            for profile, count, valid in [('deep', 1, False), ('deep', 2, True),
                                           ('deep', 3, False), ('extended', 2, False),
                                           ('extended', 3, True), ('extended', 5, True),
                                           ('extended', 6, False)]:
                with self.subTest(source=source, profile=profile, count=count):
                    errors = review.validate(record12(profile, source, discovery=count))
                    cardinality = any('discovery cardinality does not match' in e for e in errors)
                    self.assertEqual(cardinality, not valid, errors)
                    if valid:
                        self.assertEqual(errors, [])

    def test_schema10_and_11_keep_previous_discovery_boundaries(self):
        for builder in (record10, record11):
            for source, profile in [('explicit', 'deep'), ('explicit', 'extended'),
                                    ('automatic', 'extended')]:
                value = builder(profile, source)
                if profile == 'deep':
                    execution = value['coverage']['execution']
                    assignment = dict(execution['plan'][0], id='D3', reference='evidence/briefs.json#D3')
                    result = dict(execution['results'][0], assignment_id='D3', reviewer_context='D3',
                                  reference='evidence/results.json#D3')
                    execution['plan'].insert(-1, assignment)
                    execution['results'].insert(-1, result)
                with self.subTest(schema=value['schema_version'], source=source, profile=profile):
                    self.assertEqual(review.validate(value), [])

    def test_all_active_verifications_contribute_to_aggregate(self):
        for state in ('independent', 'coordinator', 'missing_one', 'missing_both', 'coordinator_and_missing'):
            value = record12('extended', 'explicit', discovery=3, verification=2)
            execution = value['coverage']['execution']
            if state != 'independent':
                execution['status'] = 'degraded'
                missing_ids = {'missing_one': ['V1'], 'missing_both': ['V1', 'V2'],
                               'coordinator_and_missing': ['V2'], 'coordinator': []}[state]
                coordinator_ids = ['V1'] if state in ('coordinator', 'coordinator_and_missing') else []
                execution['results'] = [row for row in execution['results']
                                        if row['assignment_id'] not in missing_ids]
                for result in execution['results']:
                    if result['assignment_id'] in coordinator_ids:
                        result['reviewer_context'] = 'coordinator'
                execution['fallbacks'] = [dict(assignments=[identifier], reason='dispatch_failed',
                    detail='Synthetic interruption', source=f'evidence/fallback.json#{identifier}')
                    for identifier in missing_ids + coordinator_ids]
                value['coverage']['verification'] = 'unavailable' if missing_ids else 'same_session'
            with self.subTest(state=state):
                self.assertEqual(review.validate(value), [])
                wrong = copy.deepcopy(value)
                wrong['coverage']['verification'] = ('independent' if state != 'independent' else 'same_session')
                self.assertTrue(any('coverage.verification contradicts' in e for e in review.validate(wrong)))
