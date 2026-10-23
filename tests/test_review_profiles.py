"""Immutable profile history and schema-10 execution obligations."""
import copy
import importlib
import inspect
import unittest

from recovery_fixtures import record10, selection, selection_input
from test_review_contract import contract
from test_review_traceability_contract import check
from ccr.contracts.provenance import validate_check_sources
from recovery_fixtures import context10, source_events
from ccr.contracts.execution import validate_execution_sources
from ccr.contracts import execution as execution_contract
from ccr.reporting.projections import public_limitations


profiles = importlib.import_module('ccr.workflow.profiles')


class ReviewProfileTests(unittest.TestCase):
    def test_schema10_user_report_shows_initial_effective_and_transition(self):
        value = record10('deep')
        later = selection('standard', 'explicit', id='S002', changed_from='deep',
                          reference='evidence/context.json#profile_history/1/profile',
                          phase='verification', event_id='E000002',
                          reason='User explicitly narrowed the requested profile',
                          authority='User requested standard after discovery')
        value['coverage']['execution']['profile_history'].append(later)
        value['profile'] = 'standard'
        value['profile_reason'] = 'User explicitly narrowed the requested profile'

        report = contract.render(value, audience='user')
        comment = contract.render(value, audience='comment')

        self.assertIn('**Perfil inicial:** profundo', report)
        self.assertIn('**Perfil efectivo:** standard (estándar)', report)
        self.assertIn('profundo → standard (estándar)', report)
        self.assertIn('User explicitly narrowed the requested profile', report)
        self.assertNotIn('Perfil inicial', comment)
        self.assertNotIn('Ejecución del perfil', comment)

    def test_schema10_uses_embedded_publication_classification(self):
        value = record10('standard')
        value['coverage']['limitations'] = [dict(kind='execution', detail='Private worker mechanics',
                                                material=False, public_summary=None)]

        self.assertEqual(public_limitations(value), [])

    def test_selection_aliases_and_first_identity(self):
        raw = selection_input('balanced')
        normalized = profiles.validate_selection(raw)
        self.assertEqual(normalized['profile'], 'standard')
        self.assertEqual(raw['profile'], 'balanced')
        self.assertEqual(profiles.validate_history([selection('standard')]), [])
        bad = selection('standard', id='S002', changed_from='S001')
        self.assertTrue(profiles.validate_history([bad]))

    def test_explicit_transition_requires_user_source(self):
        previous = selection('focused', 'explicit')
        changed = selection_input('deep', 'automatic', phase='discovery')
        with self.assertRaisesRegex(ValueError, 'explicit'):
            profiles.validate_selection(changed, previous=previous)
        changed = selection_input('deep', 'explicit', phase='discovery', authority='User requested deep')
        self.assertEqual(profiles.validate_selection(changed, previous=previous)['profile'], 'deep')
        invalid_history = [selection('focused', 'automatic'),
                           selection('deep', 'explicit', id='S002', changed_from='focused',
                                     phase='discovery', authority=None, event_id='E000002')]
        self.assertTrue(any('user authority' in error for error in profiles.validate_history(invalid_history)))

    def test_automatic_upgrade_and_supported_downgrade(self):
        history = [
            selection('standard', 'automatic'),
            selection('deep', 'automatic', id='S002', changed_from='standard',
                      phase='discovery', event_id='E000004', reference='evidence/trigger.json#deep'),
            selection('focused', 'automatic', id='S003', changed_from='deep',
                      phase='verification', event_id='E000009', reference='evidence/trigger.json#focused',
                      reason='Observed evidence disproved the broad security trigger'),
        ]
        self.assertEqual(profiles.validate_history(history), [])
        unjustified = selection('deep', 'automatic')
        narrowed = selection_input('focused', 'automatic', phase='verification',
                                   reference='evidence/trigger.json#focused',
                                   reason='No findings, save tokens')
        with self.assertRaisesRegex(ValueError, 'not a justification'):
            profiles.validate_selection(narrowed, previous=unjustified)

    def test_same_selection_replay_preserves_first(self):
        first = selection('standard', 'automatic')
        replay = profiles.validate_selection(selection_input('standard'), previous=first)
        self.assertEqual(replay, first)
        alias_replay = profiles.validate_selection(selection_input('balanced'), previous=first)
        self.assertEqual(alias_replay, first)
        self.assertTrue(any('duplicate selection identity' in error
                            for error in profiles.validate_history([first, replay])))

    def test_history_limit_is_visible(self):
        rows = [selection('standard', id=f'S{i:03d}', changed_from=None if i == 1 else 'standard',
                          event_id=f'E{i:06d}', phase='prepare' if i == 1 else 'discovery',
                          reference=f'evidence/selection-{i}.json#profile') for i in range(1, 34)]
        errors = profiles.validate_history(rows)
        self.assertTrue(any('maximum 32' in error for error in errors), errors)

    def test_downgrade_preserves_started_obligations(self):
        value = record10('deep', 'automatic')
        value['profile'] = 'focused'
        execution = value['coverage']['execution']
        initial = selection('deep', 'automatic')
        later = selection('focused', 'automatic', id='S002', changed_from='deep',
                          phase='verification', event_id='E000009', reference='evidence/context.json#focused',
                          reason='The initial deep trigger was disproved by the retained call graph')
        execution['profile_history'] = [initial, later]
        for row in execution['plan']:
            row['selection_id'] = initial['id']
        self.assertEqual(contract.validate(value), [])
        self.assertEqual(execution_contract.validate_profile_execution(value), [])
        execution['plan'] = [row for row in execution['plan'] if row['role'] != 'verification']
        execution['results'] = [row for row in execution['results'] if row['assignment_id'] != 'V1']
        errors = execution_contract.validate_profile_execution(value)
        self.assertTrue(any('verification obligation' in error for error in errors), errors)

    def test_upgrade_reuses_prior_independent_discovery(self):
        value = record10('deep', 'automatic')
        execution = value['coverage']['execution']
        value['profile'] = 'extended'
        execution['profile_history'].append(selection(
            'extended', 'automatic', id='S002', changed_from='deep', phase='discovery',
            event_id='E000006', reference='evidence/context.json#extended',
            affected_assignments=['D3', 'D4', 'V1']))
        execution['plan'][-1]['selection_id'] = 'S002'
        for identifier in ('D3', 'D4'):
            row = copy.deepcopy(execution['plan'][0])
            row.update(id=identifier, selection_id='S002', reference=f'evidence/briefs.json#{identifier}')
            execution['plan'].insert(-1, row)
            execution['results'].append(dict(assignment_id=identifier, reviewer_context=identifier,
                provider_id=None, reference=f'evidence/results.json#{identifier}'))
        self.assertEqual(contract.validate(value), [])
        self.assertEqual(execution_contract.validate_profile_execution(value), [])

    def test_supersession_cannot_cancel_project_gate(self):
        value = record10('deep', 'automatic')
        execution = value['coverage']['execution']
        later = selection('focused', 'automatic', id='S002', changed_from='deep',
                          phase='discovery', event_id='E000009',
                          reference='evidence/context.json#focused-trigger-disproved',
                          reason='Retained call graph evidence disproved the deep trigger')
        execution['profile_history'].append(later)
        gate = copy.deepcopy(execution['plan'][0])
        gate.update(id='G1', role='project_gate', selection_id='S001', superseded_by='S002', required=False)
        execution['plan'].append(gate)
        errors = execution_contract.validate_profile_execution(value)
        self.assertTrue(any('project_gate' in error and 'supersed' in error for error in errors), errors)

    def test_prior_coordinator_pass_is_not_new_independent_discovery(self):
        value = record10('deep')
        execution = value['coverage']['execution']
        execution['plan'][0]['independent'] = False
        execution['results'][0]['reviewer_context'] = 'coordinator'
        errors = execution_contract.validate_profile_execution(value)
        self.assertTrue(any('independent discovery' in error for error in errors), errors)

    def test_schema10_does_not_relax_local_check_bindings(self):
        value = record10('focused')
        local_check = dict(check(), revision=value['scope']['head'],
                           execution={'kind': 'local', 'executor': None})
        value['checks'] = [local_check]
        self.assertTrue(any('executor' in error for error in contract.validate(value)))
        local_check['execution']['executor'] = 'X1'
        self.assertTrue(any('unknown executor' in error for error in validate_check_sources(value, [])))

    def test_schema10_sources_bind_profile_ids_and_work_order(self):
        value = record10('deep')
        context = context10(value)
        events = source_events(value)
        references = {context['profile_reference']}
        for row in value['coverage']['execution']['plan']:
            references.add(row['reference'])
        for row in value['coverage']['execution']['results']:
            references.add(row['reference'])
        self.assertEqual(validate_execution_sources(value, context, events, references), [])
        events[0]['sequence'] = 99
        self.assertTrue(any('initial profile selection' in error
                            for error in validate_execution_sources(value, context, events, references)))

    def test_explicit_same_profile_requires_authority(self):
        previous = selection('deep', 'automatic')
        explicit = selection_input('deep', 'explicit', phase='discovery',
                                   reference='evidence/context.json#profile_history/1/profile',
                                   authority=None)
        with self.assertRaisesRegex(ValueError, 'authority'):
            profiles.validate_selection(explicit, previous=previous)

    def test_initial_explicit_profile_requires_authority(self):
        explicit = selection_input('deep', 'explicit', authority=None)
        with self.assertRaisesRegex(ValueError, 'authority'):
            profiles.validate_selection(explicit)

    def test_started_assignment_identity_cannot_change(self):
        merge = getattr(profiles, 'merge_assignment_registry', None)
        self.assertTrue(callable(merge), 'assignment registry merge must be implemented')
        plan = copy.deepcopy(record10('deep')['coverage']['execution']['plan'])
        incoming = copy.deepcopy(plan)
        incoming[0]['reference'] = 'evidence/briefs.json#replaced'
        events = [{'kind': 'agent', 'status': 'started', 'evidence': [plan[0]['reference']]}]
        with self.assertRaisesRegex(ValueError, 'started assignment'):
            merge(plan, incoming, [selection('deep')], events)

    def test_completed_result_and_brief_are_retained_after_transition(self):
        merge = getattr(profiles, 'merge_assignment_registry', None)
        self.assertTrue(callable(merge), 'assignment registry merge must be implemented')
        original = copy.deepcopy(record10('deep')['coverage']['execution']['plan'])
        replacement = copy.deepcopy(original)
        extra = copy.deepcopy(original[0])
        extra.update(id='D3', selection_id='S002', reference='evidence/briefs.json#D3')
        replacement.append(extra)
        history = [selection('deep'), selection('focused', 'automatic', id='S002',
            changed_from='deep', phase='discovery', event_id='E000002',
            reference='evidence/context.json#profile_history/1/profile',
            reason='Observed evidence disproved the initial deep trigger')]
        events = [{'kind': 'discovery', 'status': 'started', 'evidence': [original[0]['reference']]},
                  {'kind': 'discovery', 'status': 'completed', 'evidence': [original[0]['reference']]}]
        merged = merge(original, replacement, history, events)
        by_id = {row['id']: row for row in merged}
        self.assertEqual(by_id['D1']['reference'], original[0]['reference'])
        self.assertIn('D3', by_id)
        with self.assertRaisesRegex(ValueError, 'started assignment cannot be omitted'):
            merge(original, [row for row in replacement if row['id'] != 'D1'], history, events)

    def test_downgrade_omits_started_assignments_from_final_and_context(self):
        self.assertIn('assignment_registry', inspect.signature(
            execution_contract.validate_profile_execution).parameters,
            'profile validation must compare the durable assignment registry')
        value = record10('focused')
        initial = selection('deep')
        later = selection('focused', 'automatic', id='S002', changed_from='deep',
                          phase='verification', event_id='E000002',
                          reference='evidence/context.json#profile_history/1/profile',
                          reason='Retained evidence showed the deep trigger did not apply')
        value['profile'] = 'focused'
        execution = value['coverage']['execution']
        execution['profile_history'] = [initial, later]
        execution['selection_source'] = 'automatic'
        execution['plan'][0].update(id='D3', selection_id='S002', reference='evidence/briefs.json#D3')
        execution['plan'][1]['selection_id'] = 'S002'
        execution['results'][0].update(assignment_id='D3', reference='evidence/results.json#D3')
        registry = copy.deepcopy(record10('deep')['coverage']['execution']['plan'])
        started = [{'sequence': 3, 'kind': 'discovery', 'status': 'started',
                    'evidence': [registry[0]['reference']]}]
        errors = execution_contract.validate_profile_execution(value, started, assignment_registry=registry)
        self.assertTrue(any('started/completed assignment' in error and 'D1' in error for error in errors), errors)

    def test_focused_to_deep_preserves_coordinator_without_counting_it_as_fresh(self):
        value = record10('deep')
        execution = value['coverage']['execution']
        initial = selection('focused')
        later = selection('deep', 'automatic', id='S002', changed_from='focused',
                          phase='discovery', event_id='E000002',
                          reference='evidence/context.json#profile_history/1/profile')
        execution['profile_history'] = [initial, later]
        execution['plan'][0].update(independent=False, selection_id='S001')
        execution['plan'][1]['selection_id'] = 'S002'
        execution['plan'][2]['selection_id'] = 'S002'
        execution['results'][0]['reviewer_context'] = 'coordinator'
        extra = copy.deepcopy(execution['plan'][1])
        extra.update(id='D3', reference='evidence/briefs.json#D3')
        execution['plan'].insert(2, extra)
        execution['results'].append(dict(assignment_id='D3', reviewer_context='D3', provider_id=None,
                                         reference='evidence/results.json#D3'))
        self.assertEqual(contract.validate(value), [])

    def test_prior_verification_is_preserved_but_final_batch_needs_new_verifier(self):
        value = record10('deep')
        context = context10(value)
        events = source_events(value)
        verifier = [event for event in events if event.get('kind') in ('agent', 'grouped-verification')
                    and 'V1' in str(event.get('evidence', []))]
        self.assertEqual(len(verifier), 2)
        events = [event for event in events if event not in verifier]
        second_discovery = next(i for i, event in enumerate(events)
                                if event.get('kind') == 'discovery' and 'D2' in str(event.get('evidence', [])))
        events[second_discovery:second_discovery] = verifier
        for sequence, event in enumerate(events, 1):
            event['sequence'] = sequence
        references = {context['profile_reference']}
        for row in value['coverage']['execution']['plan']:
            references.add(row['reference'])
        for row in value['coverage']['execution']['results']:
            references.add(row['reference'])
        errors = validate_execution_sources(value, context, events, references)
        self.assertTrue(any('after the final discovery batch' in error for error in errors), errors)

    def test_prior_verifier_and_new_final_batch_verifier_are_both_retained(self):
        value = record10('deep')
        execution = value['coverage']['execution']
        old_verifier = copy.deepcopy(execution['plan'][-1])
        old_verifier.update(id='V2', reference='evidence/briefs.json#V2')
        execution['plan'].append(old_verifier)
        old_result = copy.deepcopy(execution['results'][-1])
        old_result.update(assignment_id='V2', reference='evidence/results.json#V2')
        old_result.update(reviewer_context='final-verifier')
        execution['results'].append(old_result)
        context = context10(value)
        events = source_events(value)
        prior_verifier = [event for event in events if event.get('kind') in ('agent', 'grouped-verification')
                          and 'V1' in str(event.get('evidence', []))]
        events = [event for event in events if event not in prior_verifier]
        final_discovery = next(i for i, event in enumerate(events)
                               if event.get('kind') == 'discovery'
                               and 'D2' in str(event.get('evidence', [])))
        events[final_discovery:final_discovery] = prior_verifier
        for sequence, event in enumerate(events, 1):
            event['sequence'] = sequence
        references = {context['profile_reference']}
        for row in execution['plan']:
            references.add(row['reference'])
        for row in execution['results']:
            references.add(row['reference'])
        self.assertEqual(validate_execution_sources(value, context, events, references), [])

    def test_malformed_trace_fields_return_validation_errors(self):
        value = record10('deep')
        errors = execution_contract.validate_profile_execution(
            value, [{'kind': [], 'status': [], 'evidence': None, 'sequence': []}])
        self.assertTrue(errors)
        context = context10(value)
        errors = validate_execution_sources(value, context,
            [{'kind': [], 'status': [], 'evidence': None, 'sequence': []}], set())
        self.assertTrue(errors)

    def test_acquired_automatic_extended_minimum_survives_explicit_selection(self):
        self.assertIn('assignment_registry', inspect.signature(
            execution_contract.validate_profile_execution).parameters,
            'profile validation must calculate obligations from acquired selections')
        value = record10('extended', 'automatic')
        execution = value['coverage']['execution']
        execution['plan'] = [row for row in execution['plan'] if row['id'] in {'D1', 'D2', 'V1'}]
        execution['results'] = [row for row in execution['results']
                                if row['assignment_id'] in {'D1', 'D2', 'V1'}]
        execution['profile_history'].append(selection('extended', 'explicit', id='S002',
            changed_from='extended', phase='verification', event_id='E000002',
            reference='evidence/context.json#profile_history/1/profile',
            authority='User explicitly retained extended'))
        registry = copy.deepcopy(execution['plan'])
        trace = [
            {'sequence': 1, 'event_id': 'E000001', 'kind': 'profile', 'status': 'selected',
             'evidence': [execution['profile_history'][0]['reference']]},
            {'sequence': 2, 'kind': 'discovery', 'status': 'started', 'evidence': [registry[0]['reference']]},
            {'sequence': 3, 'kind': 'discovery', 'status': 'started', 'evidence': [registry[1]['reference']]},
            {'sequence': 4, 'event_id': 'E000002', 'kind': 'profile', 'status': 'selected',
             'evidence': [execution['profile_history'][1]['reference']]},
        ]
        errors = execution_contract.validate_profile_execution(value, trace, assignment_registry=registry)
        self.assertTrue(any('at least 4 active discovery assignments' in error for error in errors), errors)

    def test_generic_start_is_not_fabricated_as_assignment(self):
        merge = getattr(profiles, 'merge_assignment_registry', None)
        self.assertTrue(callable(merge), 'assignment registry merge must be implemented')
        generic = {'kind': 'discovery', 'status': 'started', 'evidence': []}
        self.assertEqual(merge([], [], [selection('focused')], [generic]), [])

    def test_nonhashable_selection_fields_return_errors(self):
        malformed = [selection('focused', id=[]), selection('focused', event_id=[]),
                     selection('focused', phase=[]), selection('focused', actor={'kind': [],
                         'name': 'coordinator', 'provider_id': None})]
        for row in malformed:
            with self.subTest(row=row):
                self.assertTrue(profiles.validate_history([row]))


if __name__ == '__main__':
    unittest.main()
