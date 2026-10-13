"""Immutable profile history and schema-10 execution obligations."""
import copy
import importlib
import unittest

from recovery_fixtures import record10, selection, selection_input
from test_review_contract import contract
from test_review_traceability_contract import check
from review_check_provenance import validate_check_sources
from recovery_fixtures import context10, source_events
from review_execution import validate_execution_sources


profiles = importlib.import_module('review_profiles')


class ReviewProfileTests(unittest.TestCase):
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
                      phase='verification', event_id='E000009', reference='evidence/trigger.json#focused'),
        ]
        self.assertEqual(profiles.validate_history(history), [])

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
                          phase='verification', event_id='E000009', reference='evidence/context.json#focused')
        execution['profile_history'] = [initial, later]
        for row in execution['plan']:
            row['selection_id'] = initial['id']
        self.assertEqual(contract.validate(value), [])
        self.assertEqual(profiles.validate_profile_execution(value), [])
        execution['plan'] = [row for row in execution['plan'] if row['role'] != 'verification']
        execution['results'] = [row for row in execution['results'] if row['assignment_id'] != 'V1']
        errors = profiles.validate_profile_execution(value)
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
        self.assertEqual(profiles.validate_profile_execution(value), [])

    def test_supersession_cannot_cancel_project_gate(self):
        value = record10('deep', 'automatic')
        execution = value['coverage']['execution']
        later = selection('focused', 'automatic', id='S002', changed_from='deep',
                          phase='discovery', event_id='E000009', reference='evidence/context.json#focused')
        execution['profile_history'].append(later)
        gate = copy.deepcopy(execution['plan'][0])
        gate.update(id='G1', role='project_gate', selection_id='S001', superseded_by='S002', required=False)
        execution['plan'].append(gate)
        errors = profiles.validate_profile_execution(value)
        self.assertTrue(any('project_gate' in error and 'supersed' in error for error in errors), errors)

    def test_prior_coordinator_pass_is_not_new_independent_discovery(self):
        value = record10('deep')
        execution = value['coverage']['execution']
        execution['plan'][0]['independent'] = False
        execution['results'][0]['reviewer_context'] = 'coordinator'
        errors = profiles.validate_profile_execution(value)
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


if __name__ == '__main__':
    unittest.main()
