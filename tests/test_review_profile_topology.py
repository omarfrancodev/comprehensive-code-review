"""Schema-12 profile contract and compatibility checks."""
import copy
import unittest

from script_test_support import enable_package_imports
enable_package_imports()
from ccr.contracts import review, execution as execution_contract
from traceability_fixtures import record11
from profile_topology_fixtures import record12, source_fixture12, historical_fixture12
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

    def test_extended_two_final_batches_are_valid_and_three_are_rejected(self):
        value = record12('extended', 'explicit', discovery=3, verification=2)
        context, events, refs = source_fixture12(value)
        self.assertEqual(execution_contract.validate_execution_sources(value, context, events, refs), [])
        value = record12('extended', 'explicit', discovery=3, verification=3)
        context, events, refs = source_fixture12(value)
        errors = execution_contract.validate_execution_sources(value, context, events, refs)
        self.assertTrue(any('permits at most 2 final verification batches' in e for e in errors), errors)

    def test_previous_verification_is_history_not_a_final_batch(self):
        value = record12('deep', 'explicit', discovery=2, verification=2)
        context, events, refs = source_fixture12(value)
        # profile, D1 start/end, V1 start/end, D2 start/end, V2 start/end
        events = events[:3] + events[5:7] + events[3:5] + events[7:]
        for i, event in enumerate(events, 1):
            event['sequence'] = i
        self.assertEqual(execution_contract.validate_execution_sources(value, context, events, refs), [])

    def test_final_batch_must_start_after_last_discovery(self):
        value = record12('extended', 'explicit', discovery=3, verification=2)
        context, events, refs = source_fixture12(value)
        # Move only V1's original dispatch before D3 completes.
        start = events.pop(7)
        events.insert(6, start)
        for i, event in enumerate(events, 1):
            event['sequence'] = i
        errors = execution_contract.validate_execution_sources(value, context, events, refs)
        self.assertTrue(any('final verification batch must start and complete after' in e for e in errors), errors)

    def test_historical_batches_and_escalation_preserve_obligations(self):
        for profile, count in [('deep', 1), ('extended', 1), ('extended', 2)]:
            value, context, events, refs = historical_fixture12(profile, count)
            with self.subTest(profile=profile, finals=count):
                self.assertEqual(execution_contract.validate_execution_sources(value, context, events, refs), [])
        value, context, events, refs = historical_fixture12('deep', 0)
        errors = execution_contract.validate_execution_sources(value, context, events, refs)
        self.assertTrue(any('requires at least 1 final verification batches' in e for e in errors), errors)

    def test_final_limit_and_clean_standard_exception(self):
        for profile in ('focused', 'standard', 'deep'):
            value = record12(profile, 'explicit', discovery=2 if profile == 'deep' else 1, verification=2)
            if profile == 'focused':
                for row in value['coverage']['execution']['results']:
                    row['reviewer_context'] = 'coordinator'
            context, events, refs = source_fixture12(value)
            errors = execution_contract.validate_execution_sources(value, context, events, refs)
            self.assertTrue(any('permits at most 1 final verification batches' in e for e in errors), errors)
        clean = record12('standard', 'explicit', discovery=1, verification=0)
        self.assertEqual(execution_contract.validate_execution_sources(clean, *source_fixture12(clean)), [])

    def test_malformed_profile_history_is_rejected_without_crash(self):
        value = record12()
        context, events, refs = source_fixture12(value)
        value['coverage']['execution']['profile_history'] = [{}]
        context['profile_history'] = [{}]
        self.assertTrue(execution_contract.validate_execution_sources(value, context, events, refs))

    def test_degraded_missing_historical_result_is_not_hidden_by_final(self):
        value, _, events, refs = historical_fixture12('extended', 1)
        execution = value['coverage']['execution']
        execution['results'] = [r for r in execution['results'] if r['assignment_id'] != 'V-previa']
        execution['status'] = 'degraded'
        execution['fallbacks'] = [dict(assignments=['V-previa'], reason='dispatch_failed',
            detail='Synthetic failure', source='evidence/fallback.json#V-previa')]
        value['coverage']['verification'] = 'unavailable'
        events = [e for e in events if 'evidence/results.json#V-previa' not in e.get('evidence', [])]
        events.append(dict(sequence=max(e['sequence'] for e in events)+1, event_id='E000900',
                           kind='interruption', status='blocked', evidence=['evidence/fallback.json#V-previa']))
        refs.add('evidence/fallback.json#V-previa')
        from recovery_fixtures import context10
        context = context10(value)
        self.assertEqual(execution_contract.validate_execution_sources(value, context, events, refs), [])
        refs.remove('evidence/fallback.json#V-previa')
        self.assertTrue(any('fallback lacks retained' in e for e in
            execution_contract.validate_execution_sources(value, context, events, refs)))

    def test_degraded_missing_final_is_still_a_required_batch(self):
        value = record12('extended', 'explicit', discovery=3, verification=2)
        execution = value['coverage']['execution']
        execution['results'] = [r for r in execution['results'] if r['assignment_id'] != 'V2']
        execution['status'] = 'degraded'
        execution['fallbacks'] = [dict(assignments=['V2'], reason='dispatch_failed',
            detail='Synthetic failure', source='evidence/fallback.json#V2')]
        value['coverage']['verification'] = 'unavailable'
        context, events, refs = source_fixture12(value)
        self.assertEqual(execution_contract.validate_execution_sources(value, context, events, refs), [])
        refs.remove('evidence/fallback.json#V2')
        self.assertTrue(any('fallback lacks retained' in e for e in
            execution_contract.validate_execution_sources(value, context, events, refs)))

    def test_each_final_batch_requires_planned_independence(self):
        value = record12('extended', 'explicit', discovery=3, verification=2)
        next(row for row in value['coverage']['execution']['plan'] if row['id'] == 'V2')['independent'] = False
        value['coverage']['verification'] = 'same_session'
        context, events, refs = source_fixture12(value)
        errors = execution_contract.validate_execution_sources(value, context, events, refs)
        self.assertTrue(any('requires planned independence' in e for e in errors), errors)

    def test_later_dispatch_cannot_replace_original_early_start(self):
        value = record12('extended', 'explicit', discovery=3, verification=2)
        context, events, refs = source_fixture12(value)
        first = events.pop(7)
        events.insert(6, first)
        later = copy.deepcopy(first)
        later['event_id'] = 'E000900'
        events.insert(8, later)
        for i, event in enumerate(events, 1):
            event['sequence'] = i
        errors = execution_contract.validate_execution_sources(value, context, events, refs)
        self.assertTrue(any('final verification batch must start and complete after' in e for e in errors), errors)

        execution = value['coverage']['execution']
        execution['status'] = 'degraded'
        execution['fallbacks'] = [dict(assignments=['V2'], reason='dispatch_failed',
            detail='Synthetic interruption', source='evidence/fallback.json#V2')]
        value['coverage']['verification'] = 'same_session'
        refs.add('evidence/fallback.json#V2')
        events.append(dict(sequence=len(events)+1, event_id='E000901', kind='interruption',
                           status='blocked', evidence=['evidence/fallback.json#V2']))
        errors = execution_contract.validate_execution_sources(value, context, events, refs)
        self.assertTrue(any('final verification batch must start and complete after' in e for e in errors), errors)

    def test_coordinator_fallback_requires_own_stage_start(self):
        value = record12('extended', 'explicit', discovery=3, verification=2)
        execution = value['coverage']['execution']
        execution['status'] = 'degraded'
        execution['fallbacks'] = [dict(assignments=['V1'], reason='dispatch_failed',
            detail='Synthetic interruption', source='evidence/fallback.json#V1')]
        value['coverage']['verification'] = 'same_session'
        next(row for row in execution['results'] if row['assignment_id'] == 'V1')['reviewer_context'] = 'coordinator'
        context, events, refs = source_fixture12(value)
        for event in events:
            if 'evidence/briefs.json#V1' in event.get('evidence', []) and event['status'] == 'started':
                event['kind'] = 'grouped-verification'
                event['actor'] = event.pop('executor')
        self.assertEqual(execution_contract.validate_execution_sources(value, context, events, refs), [])
        non_coordinator = copy.deepcopy(value)
        next(row for row in non_coordinator['coverage']['execution']['results'] if row['assignment_id'] == 'V1')['reviewer_context'] = 'other-worker'
        changed_events = copy.deepcopy(events)
        for event in changed_events:
            if 'evidence/briefs.json#V1' in event.get('evidence', []) and isinstance(event.get('actor'), dict):
                event['actor']['name'] = 'other-worker'
        errors = execution_contract.validate_execution_sources(non_coordinator, context, changed_events, refs)
        self.assertTrue(any('final verification batch must start and complete after' in e for e in errors), errors)
        events = [event for event in events if not (event['kind'] == 'grouped-verification'
                  and event['status'] == 'started')]
        errors = execution_contract.validate_execution_sources(value, context, events, refs)
        self.assertTrue(any('final verification batch must start and complete after' in e for e in errors), errors)

    def test_legacy_schema_still_rejects_two_fresh_final_verifiers(self):
        for builder in (record10, record11):
            value = builder('extended', 'explicit')
            twelve = record12('extended', 'explicit', discovery=3, verification=2)
            value['coverage']['execution']['plan'] = twelve['coverage']['execution']['plan']
            value['coverage']['execution']['results'] = twelve['coverage']['execution']['results']
            context, events, refs = source_fixture12(value)
            errors = execution_contract.validate_execution_sources(value, context, events, refs)
            self.assertTrue(any('one fresh verifier' in e for e in errors), errors)

    def test_late_identity_annotation_keeps_original_dispatch_time(self):
        for early in (False, True):
            value = record12('extended', 'explicit', discovery=3, verification=2)
            context, events, refs = source_fixture12(value)
            start = events[7]
            if early:
                events.remove(start)
                events.insert(6, start)
            for index, event in enumerate(events, 1):
                event['sequence'] = index
                event['event_id'] = f'E{index:06d}'
            identity = start['executor']
            start['executor'] = None
            start['actor'] = {'kind': 'coordinator', 'name': 'coordinator', 'provider_id': None}
            source = 'evidence/dispatch.json#V1'
            refs.add(source)
            events.append(dict(kind='dispatch-identity', status='unchanged',
                summary='Observed original identity', actor={'kind': 'coordinator', 'name': 'coordinator', 'provider_id': None},
                executor=identity, provenance={'kind': 'recovered', 'source': source},
                evidence=['evidence/briefs.json#V1', source],
                relations=[{'relation': 'records', 'target': start['event_id']}], authority=None,
                occurred_at=None, sequence=len(events)+1, event_id='E000900'))
            errors = execution_contract.validate_execution_sources(value, context, events, refs)
            if early:
                self.assertTrue(any('final verification batch must start and complete after' in e for e in errors), errors)
            else:
                self.assertEqual(errors, [])

    def test_wrong_provider_does_not_replace_final_dispatch(self):
        value = record12('extended', 'explicit', discovery=3, verification=2)
        context, events, refs = source_fixture12(value)
        result = next(row for row in value['coverage']['execution']['results'] if row['assignment_id'] == 'V1')
        result['provider_id'] = 'actual-provider'
        completion = next(event for event in events if event['kind'] == 'grouped-verification'
                          and 'evidence/results.json#V1' in event['evidence'])
        completion['actor']['provider_id'] = 'actual-provider'
        start = next(event for event in events if event['kind'] == 'agent'
                     and 'evidence/briefs.json#V1' in event['evidence'])
        start['executor'] = copy.deepcopy(start['executor'])
        start['executor']['provider_id'] = 'wrong-provider'
        errors = execution_contract.validate_execution_sources(value, context, events, refs)
        self.assertTrue(any('independent result lacks observed dispatch' in e for e in errors), errors)
        start['executor']['provider_id'] = 'actual-provider'
        self.assertEqual(execution_contract.validate_execution_sources(value, context, events, refs), [])
