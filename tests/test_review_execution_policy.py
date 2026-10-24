"""Observable schema, independence and retained-provenance gates."""
import copy
import json
import unittest

from test_review_profile_names import record7
from test_review_contract import contract, finding
from ccr.contracts.execution import validate_execution_sources
from ccr.archive import retention as archive_retention
import test_review_delivery as delivery_tests


def record8(profile='focused', selection='explicit'):
    value = record7(profile)
    value['schema_version'] = 8
    count = 2 if profile in ('deep', 'extended') else 1
    if profile == 'extended' and selection == 'automatic':
        count = 4
    independent = profile in ('deep', 'extended')
    plan = [dict(id=f'D{i}', role='discovery', independent=independent, required=True,
                 reference=f'evidence/briefs.json#D{i}') for i in range(1, count + 1)]
    plan.append(dict(id='V1', role='verification', independent=profile != 'focused',
                     required=True, reference='evidence/briefs.json#V1'))
    results = [dict(assignment_id=row['id'], reviewer_context=row['id'] if row['independent'] else 'coordinator',
                    provider_id=None, reference='evidence/results.json#' + row['id']) for row in plan]
    value['coverage'].update(verification='same_session' if profile == 'focused' else 'independent',
        execution=dict(selection_source=selection, status='fulfilled', plan=plan, results=results, fallbacks=[]))
    return value


def limit(kind='execution', material=False, summary=None, detail='Native dispatch unavailable'):
    return dict(kind=kind, detail=detail, material=material, public_summary=summary)


def source_fixture(value):
    context = dict(profile=value['profile'], selection_source=value['coverage']['execution']['selection_source'],
                   profile_reference='evidence/context.json#profile', executors=[])
    references = {context['profile_reference']}
    events = [dict(sequence=1, kind='profile', status='selected', evidence=[context['profile_reference']])]
    for row, result in zip(value['coverage']['execution']['plan'], value['coverage']['execution']['results']):
        references.update((row['reference'], result['reference']))
        identity = dict(name=result['reviewer_context'], provider_id=result['provider_id'])
        events.append(dict(sequence=len(events) + 1, kind='agent', status='started',
                           executor=identity, evidence=[row['reference']]))
        events.append(dict(sequence=len(events) + 1,
                           kind='discovery' if row['role'] == 'discovery' else 'grouped-verification',
                           status='completed', actor=identity, evidence=[result['reference']]))
    return context, events, references


class ExecutionPolicyTests(unittest.TestCase):
    def assertValid(self, value):
        self.assertEqual(contract.validate(value), [])

    def assertInvalid(self, value, fragment):
        self.assertTrue(any(fragment in error for error in contract.validate(value)), contract.validate(value))

    def test_schema8_requires_typed_limitations(self):
        value = record8()
        value['coverage']['limitations'] = [limit()]
        self.assertValid(value)
        for mutation in [dict(kind='unknown'), dict(material=True), dict(public_summary='private mechanics')]:
            bad = copy.deepcopy(value)
            bad['coverage']['limitations'][0].update(mutation)
            self.assertInvalid(bad, 'limitations')
        for field in ('kind', 'public_summary'):
            bad = copy.deepcopy(value)
            del bad['coverage']['limitations'][0][field]
            self.assertInvalid(bad, 'limitations')
        value['coverage']['limitations'] = [limit(material=True, summary='Required validation remains incomplete')]
        value['verdict'] = 'insufficient_evidence'
        self.assertValid(value)

    def test_schema8_keeps_ids_authors_and_verdict_precedence(self):
        value = record8()
        for field in ('review_id', 'change_authors', 'previous_reviews', 'grandfathered_ids'):
            bad = copy.deepcopy(value)
            del bad[field]
            self.assertInvalid(bad, field)
        bad = copy.deepcopy(value)
        bad['findings'] = [dict(finding(), id='F1')]
        self.assertInvalid(bad, 'canonical')
        value['coverage']['limitations'] = [limit(material=True, summary='Validation incomplete')]
        value['findings'] = [dict(finding(), id='F001', blocking=True, blocking_reason='Contract acceptance is broken')]
        value['verdict'] = 'not_approvable'
        self.assertValid(value)
        allocated, mapping = contract.canonicalize_ids(record8())
        self.assertValid(allocated)
        self.assertEqual(mapping, {'findings': {}, 'checks': {}})

    def test_legacy_validation_does_not_mutate_source(self):
        for profile in ('focused', 'standard', 'deep', 'extended'):
            value = record7(profile)
            before = json.dumps(value, sort_keys=True)
            self.assertValid(value)
            self.assertEqual(json.dumps(value, sort_keys=True), before)

    def test_deep_requires_two_fresh_discoveries_and_grouped_verifier(self):
        value = record8('deep')
        self.assertValid(value)
        for change in ('one', 'four', 'no_verifier', 'not_independent'):
            bad = copy.deepcopy(value)
            execution = bad['coverage']['execution']
            if change == 'one':
                execution['plan'].pop(1)
                execution['results'].pop(1)
            elif change == 'four':
                execution['plan'] += [dict(execution['plan'][0], id='D3'), dict(execution['plan'][0], id='D4')]
            elif change == 'no_verifier':
                execution['plan'].pop()
                execution['results'].pop()
            else:
                execution['plan'][0]['independent'] = False
            self.assertInvalid(bad, 'execution')

    def test_extended_counts_follow_selection_source(self):
        self.assertValid(record8('extended'))
        self.assertValid(record8('extended', 'automatic'))
        bad = record8('extended')
        bad['coverage']['execution']['selection_source'] = 'automatic'
        self.assertInvalid(bad, 'discovery')

    def test_same_input_context_is_not_reviewer_identity(self):
        value = record8('deep')
        # All workers may consume the same neutral brief source; contexts stay distinct.
        for row in value['coverage']['execution']['plan']:
            row['reference'] = 'evidence/context.json#shared-input'
        self.assertValid(value)

    def test_reused_reviewer_context_cannot_claim_independence(self):
        for field in ('reviewer_context', 'provider_id'):
            bad = record8('deep')
            for row in bad['coverage']['execution']['results']:
                row[field] = 'same-observed-context'
            self.assertInvalid(bad, 'independence')

    def test_fallback_requires_observed_source(self):
        value = record8('deep')
        execution = value['coverage']['execution']
        execution.update(status='degraded', results=[], fallbacks=[dict(assignments=['D1', 'D2', 'V1'],
            reason='tool_unavailable', detail='No native dispatch tool', source='evidence/context.json#capability')])
        value['coverage'].update(verification='unavailable', adequate=False)
        value['coverage']['limitations'] = [limit(material=True, summary='Verification remains incomplete')]
        value['verdict'] = 'insufficient_evidence'
        self.assertValid(value)
        for mutation in [dict(source=''), dict(reason='user_did_not_request_subagents'), dict(reason='few_slots'),
                         dict(assignments=['D1'])]:
            bad = copy.deepcopy(value)
            bad['coverage']['execution']['fallbacks'][0].update(mutation)
            self.assertInvalid(bad, 'execution')

    def test_restriction_does_not_invent_product_defect(self):
        value = record8('deep')
        execution = value['coverage']['execution']
        execution['status'] = 'degraded'
        execution['results'] = [dict(assignment_id='V1', reviewer_context='coordinator', provider_id=None,
                                     reference='evidence/results.json#V1')]
        execution['fallbacks'] = [dict(assignments=['D1', 'D2', 'V1'], reason='explicit_restriction',
            detail='User forbids delegation', source='evidence/context.json#restriction')]
        value['coverage']['verification'] = 'same_session'
        value['coverage']['limitations'] = [limit()]
        self.assertValid(value)
        self.assertEqual(value['verdict'], 'approvable')

    def test_focused_and_clean_standard_do_not_overdelegate(self):
        self.assertValid(record8())
        value = record8('standard')
        value['coverage']['verification'] = 'skipped'
        value['coverage']['execution']['plan'].pop()
        value['coverage']['execution']['results'].pop()
        self.assertValid(value)

    def test_standard_p3_requires_fresh_verification(self):
        value = record8('standard')
        value['findings'] = [dict(finding(), id='F001', priority='P3')]
        self.assertValid(value)
        value['coverage']['execution']['plan'][-1]['independent'] = False
        value['coverage']['execution']['results'][-1]['reviewer_context'] = 'coordinator'
        value['coverage']['verification'] = 'same_session'
        self.assertInvalid(value, 'verification')

    def test_standard_unresolved_code_candidate_requires_fresh_verification(self):
        value = record8('standard')
        value['findings'] = [dict(finding(), id='F001', priority='P3', status='unresolved')]
        value['coverage']['execution']['plan'][-1]['independent'] = False
        value['coverage']['execution']['results'][-1]['reviewer_context'] = 'coordinator'
        value['coverage']['verification'] = 'same_session'
        self.assertInvalid(value, 'verification')

    def test_malformed_execution_returns_errors_without_crashing(self):
        for raw in (None, [], {}, {'plan': [None]}, {'selection_source': []}):
            value = record8()
            value['coverage']['execution'] = raw
            self.assertInvalid(value, 'execution')

    def test_profile_transition_needs_observed_source(self):
        value = record8('deep')
        context, events, references = source_fixture(value)
        self.assertEqual(validate_execution_sources(value, context, events, references), [])
        context['profile_history'] = [dict(profile='standard', reference='evidence/initial.json#profile'),
                                      dict(profile='deep', reference=context['profile_reference'])]
        references.add('evidence/initial.json#profile')
        self.assertTrue(validate_execution_sources(value, context, events, references))

    def test_selection_source_cannot_bypass_automatic_extended_counts(self):
        value = record8('extended')
        context, events, references = source_fixture(value)
        context['selection_source'] = 'automatic'
        self.assertTrue(validate_execution_sources(value, context, events, references))

    def test_failed_dispatch_is_not_a_completed_reviewer(self):
        value = record8('deep')
        context, events, references = source_fixture(value)
        for event in events:
            if event['kind'] == 'discovery':
                event['status'] = 'failed'
        self.assertTrue(validate_execution_sources(value, context, events, references))

    def test_execution_sources_must_exist_before_retention(self):
        value = record8('deep')
        context, events, references = source_fixture(value)
        for reference in sorted(references):
            self.assertTrue(validate_execution_sources(value, context, events, references - {reference}))
        events[1]['executor'] = None
        self.assertTrue(validate_execution_sources(value, context, events, references))

    def recovered_dispatch(self, identifier, *, early_verifier=False):
        from recovery_fixtures import context10, record10, source_events

        value = record10('deep')
        context = context10(value)
        events = source_events(value)
        assignment = next(row for row in value['coverage']['execution']['plan'] if row['id'] == identifier)
        result = next(row for row in value['coverage']['execution']['results']
                      if row['assignment_id'] == identifier)
        start = next(event for event in events if event.get('kind') == 'agent'
                     and event.get('status') == 'started' and assignment['reference'] in event['evidence'])
        if early_verifier:
            events.remove(start)
            events.insert(2, start)
            for sequence, event in enumerate(events, 1):
                event.update(sequence=sequence, event_id=f'E{sequence:06d}')
        start['executor'] = None
        start['actor'] = {'kind': 'coordinator', 'name': 'coordinator', 'provider_id': None}
        references = {context['profile_reference']}
        references.update(row['reference'] for row in value['coverage']['execution']['plan'])
        references.update(row['reference'] for row in value['coverage']['execution']['results'])
        source = 'evidence/dispatch.json#' + identifier
        annotation = {
            'kind': 'agent', 'status': 'unchanged',
            'summary': 'Observed identity for original dispatch; no new execution',
            'actor': {'kind': 'coordinator', 'name': 'coordinator', 'provider_id': None},
            'executor': {'name': result['reviewer_context'], 'provider_id': result['provider_id']},
            'provenance': {'kind': 'recovered', 'source': source},
            'evidence': [assignment['reference'], source],
            'relations': [{'relation': 'records', 'target': start['event_id']}],
            'authority': None, 'occurred_at': None,
            'event_id': 'E000008', 'sequence': 8,
        }
        events.append(annotation)
        references.add(source)
        return value, context, events, references, start

    def test_late_dispatch_identity_projects_the_original_independent_start(self):
        for identifier in ('D1', 'V1'):
            with self.subTest(assignment=identifier):
                value, context, events, references, start = self.recovered_dispatch(identifier)
                self.assertTrue(validate_execution_sources(value, context, events[:-1], references))
                before = copy.deepcopy(events)

                self.assertEqual(validate_execution_sources(value, context, events, references), [])

                self.assertEqual(events, before)
                self.assertIsNone(start['executor'])

    def test_late_verifier_identity_does_not_move_early_dispatch_after_discovery(self):
        value, context, events, references, start = self.recovered_dispatch('V1', early_verifier=True)
        before = copy.deepcopy(events)

        errors = validate_execution_sources(value, context, events, references)

        self.assertTrue(any('one fresh verifier after the final discovery batch' in error for error in errors))
        self.assertEqual(start['sequence'], 3)
        self.assertEqual(events[-1]['sequence'], 8)
        self.assertEqual(events, before)

    def test_later_start_cannot_replace_early_independent_dispatch(self):
        for recovered in (False, True):
            for later_start in ('stage', 'wrong_provider', 'actor_only', 'repeated_dispatch'):
                with self.subTest(recovered=recovered, later_start=later_start):
                    value, context, events, references, start = self.recovered_dispatch(
                        'V1', early_verifier=True)
                    identity = copy.deepcopy(events[-1]['executor'])
                    if not recovered:
                        events.pop()
                        start['executor'] = identity
                    completion = next(event for event in events
                                      if event['kind'] == 'grouped-verification')
                    events.remove(completion)
                    executor = copy.deepcopy(identity)
                    if later_start == 'wrong_provider':
                        executor['provider_id'] = 'another-provider-context'
                    elif later_start == 'actor_only':
                        executor['name'] = 'another-reviewer'
                    events.append(dict(
                        kind='grouped-verification' if later_start == 'stage' else 'agent',
                        status='started', actor={'kind': 'agent', **identity},
                        executor=None if later_start == 'stage' else executor,
                        evidence=['evidence/briefs.json#V1']))
                    events.append(completion)
                    for sequence, event in enumerate(events, 1):
                        event.update(sequence=sequence, event_id=f'E{sequence:06d}')
                    before = copy.deepcopy(events)

                    errors = validate_execution_sources(value, context, events, references)

                    self.assertTrue(any('one fresh verifier after the final discovery batch' in error
                                        for error in errors), errors)
                    self.assertEqual(start['sequence'], 3)
                    self.assertEqual(events, before)

    def test_same_session_final_verifier_accepts_grouped_stage_start(self):
        from recovery_fixtures import context10, record10, source_events

        value = record10('focused')
        context = context10(value)
        events = source_events(value)
        start = next(event for event in events if event.get('status') == 'started'
                     and 'evidence/briefs.json#V1' in event['evidence'])
        start.update(kind='grouped-verification', executor=None,
                     actor={'kind': 'coordinator', 'name': 'coordinator', 'provider_id': None})
        references = {context['profile_reference']}
        references.update(row['reference'] for row in value['coverage']['execution']['plan'])
        references.update(row['reference'] for row in value['coverage']['execution']['results'])

        self.assertEqual(validate_execution_sources(value, context, events, references), [])

    def test_fresh_recovered_verifier_ignores_other_provider_dispatch(self):
        value, context, events, references, start = self.recovered_dispatch('V1')
        result = next(row for row in value['coverage']['execution']['results']
                      if row['assignment_id'] == 'V1')
        result['provider_id'] = 'observed-v1-provider'
        completion = next(event for event in events if event['kind'] == 'grouped-verification')
        completion['actor']['provider_id'] = result['provider_id']
        annotation = events[-1]
        annotation['executor']['provider_id'] = result['provider_id']
        earlier = copy.deepcopy(start)
        earlier['executor'] = {'name': result['reviewer_context'], 'provider_id': None}
        events.insert(2, earlier)
        for sequence, event in enumerate(events, 1):
            event.update(sequence=sequence, event_id=f'E{sequence:06d}')
        annotation['relations'][0]['target'] = start['event_id']
        before = copy.deepcopy(events)

        self.assertEqual(validate_execution_sources(value, context, events, references), [])

        self.assertEqual(events, before)

    def test_generic_unchanged_milestone_preserves_schema8_and_schema10_sources(self):
        from ccr.archive import trace
        from recovery_fixtures import context10, record10, source_events

        for schema in (8, 10):
            with self.subTest(schema=schema):
                value = record8() if schema == 8 else record10()
                if schema == 8:
                    context, events, references = source_fixture(value)
                else:
                    context, events = context10(value), source_events(value)
                    references = {context['profile_reference']}
                    references.update(row['reference'] for row in value['coverage']['execution']['plan'])
                    references.update(row['reference'] for row in value['coverage']['execution']['results'])
                self.assertEqual(validate_execution_sources(value, context, events, references), [])
                generic = trace.event_input({
                    'kind': 'agent', 'status': 'unchanged',
                    'summary': 'Worker already active; no new dispatch',
                    'actor': {'kind': 'agent', 'name': 'worker-notice', 'provider_id': None},
                    'executor': None, 'provenance': {'kind': 'agent', 'source': None},
                    'evidence': [], 'relations': []})
                generic.update(sequence=len(events) + 1, event_id=f'E{len(events) + 1:06d}')
                events.append(generic)
                before = copy.deepcopy(events)

                self.assertEqual(validate_execution_sources(value, context, events, references), [])

                self.assertEqual(events, before)

    def test_focused_requires_one_actual_context(self):
        value = record8()
        value['coverage']['execution']['results'][-1]['reviewer_context'] = 'another-context'
        self.assertInvalid(value, 'same context')

    def test_schema8_brief_discloses_fulfillment_with_independent_verification(self):
        for status, label in [('fulfilled', 'cumplida'), ('degraded', 'degradada')]:
            with self.subTest(status=status):
                value = record8('deep')
                execution = value['coverage']['execution']
                if status == 'degraded':
                    execution['status'] = 'degraded'
                    execution['results'].pop(1)
                    execution['fallbacks'] = [dict(assignments=['D2'], reason='quota_exhausted',
                        detail='Observed discovery quota exhausted', source='evidence/context.json#restriction')]
                self.assertValid(value)
                output = delivery_tests.delivery._brief(value)
                self.assertIn('**Ejecución del perfil:** ' + label, output)
                self.assertIn('**Verificación:** independiente', output)
        self.assertNotIn('Ejecución del perfil', delivery_tests.delivery._brief(record7('deep')))

    def test_focused_allows_separate_required_project_gate(self):
        value = record8()
        execution = value['coverage']['execution']
        execution['plan'].append(dict(id='G1', role='project_gate', independent=True, required=True,
                                     reference='evidence/policy.json#G1'))
        execution['results'].append(dict(assignment_id='G1', reviewer_context='fresh-gate', provider_id=None,
                                        reference='evidence/results.json#G1'))
        self.assertValid(value)
        self.assertEqual(validate_execution_sources(value, *source_fixture(value)), [])
        execution['results'][-1]['reviewer_context'] = 'coordinator'
        self.assertInvalid(value, 'independence')

    def test_observed_profiles_cannot_downgrade_or_change_explicit_selection(self):
        for initial, final, selection, valid in [('focused', 'deep', 'automatic', True),
                ('deep', 'focused', 'automatic', False), ('focused', 'deep', 'explicit', False)]:
            with self.subTest(initial=initial, final=final, selection=selection):
                value = record8(final, selection)
                context, events, references = source_fixture(value)
                initial_ref = 'evidence/initial.json#profile'
                context['profile_history'] = [dict(profile=initial, reference=initial_ref),
                                              dict(profile=final, reference=context['profile_reference'])]
                references.add(initial_ref)
                for event in events:
                    event['sequence'] += 1
                events.insert(0, dict(sequence=1, kind='profile', status='selected', evidence=[initial_ref]))
                self.assertEqual(not validate_execution_sources(value, context, events, references), valid)

    def test_profile_selection_must_precede_observed_work(self):
        value = record8('deep', 'automatic')
        context, events, references = source_fixture(value)
        selection = events.pop(0)
        selection['sequence'] = len(events) + 2
        events.append(selection)
        self.assertTrue(validate_execution_sources(value, context, events, references))

    def test_automatic_escalation_can_reuse_prior_discovery_but_precedes_new_dispatch(self):
        value = record8('deep', 'automatic')
        context, events, references = source_fixture(value)
        initial_ref = 'evidence/initial.json#profile'
        context['profile_history'] = [dict(profile='focused', reference=initial_ref),
                                      dict(profile='deep', reference=context['profile_reference'])]
        references.add(initial_ref)
        final_selection = events.pop(0)
        events.insert(0, dict(kind='profile', status='selected', evidence=[initial_ref]))
        events.insert(3, final_selection)
        for sequence, event in enumerate(events, 1):
            event['sequence'] = sequence
        self.assertEqual(validate_execution_sources(value, context, events, references), [])
        events.remove(final_selection)
        events.append(final_selection)
        for sequence, event in enumerate(events, 1):
            event['sequence'] = sequence
        self.assertTrue(validate_execution_sources(value, context, events, references))


if __name__ == '__main__':
    unittest.main()


class ArchiveExecutionPolicyTests(unittest.TestCase):
    def setUp(self):
        self.fixture = delivery_tests.DeliveryTests()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()
        self.artifacts = delivery_tests.artifacts

    def prepared(self, profile='deep'):
        from recovery_fixtures import context10, legacy_prepare, record10, selection_input, source_events
        value = record10(profile)
        fixture = self.fixture
        run = legacy_prepare(self.artifacts, fixture.repo, fixture.write('scope.json', value['scope']),
                             skill_version='2.12.1', harness='codex', output_root=fixture.archive,
                             profile_input=selection_input(profile),
                             current_inputs=context10(value)['review_inputs'])
        from pathlib import Path
        run = Path(run)
        manifest = self.artifacts.read_json(run / 'cierre.json')
        value['review_id'] = 'CR-' + manifest['run_id']
        value['coverage']['execution']['profile_history'] = manifest['profile_history']
        context = context10(value)
        self.artifacts.register(run, [], context_input=fixture.write('context.json', context))
        events = source_events(value)
        for event in events:
            if event['kind'] == 'profile':
                continue
            identity = event.get('actor', dict(name='coordinator', provider_id=None))
            observed = dict(kind=event['kind'], status=event['status'], summary='Observed synthetic review step',
                            actor=dict(identity, kind='agent'), executor=event.get('executor'),
                            provenance=dict(kind='tool', source='synthetic native result'), evidence=event['evidence'],
                            relations=[], authority=None, occurred_at=None)
            self.artifacts.record_event(run, fixture.write('event.json', observed))
        plan = value['coverage']['execution']['plan']
        inputs = [fixture.write('briefs.json', {row['id']: dict(questions=['Check invariant']) for row in plan}),
                  fixture.write('results.json', {row['id']: dict(result='completed') for row in plan})]
        return run, value, fixture.write('context.json', context), inputs

    def test_schema8_archive_requires_matching_run_identity(self):
        run, value, context, inputs = self.prepared()
        value['review_id'] = 'CR-' + 'f' * 20
        before = self.fixture.snapshot(run)
        with self.assertRaises(ValueError):
            self.artifacts.retain(run, self.fixture.write('final.json', value), context_input=context, evidence_inputs=inputs)
        self.assertEqual(before, self.fixture.snapshot(run))

    def test_automatic_context_cannot_overwrite_uninventoried_evidence(self):
        run, value, context, inputs = self.prepared()
        (run / 'evidence').mkdir()
        foreign = run / 'evidence' / 'context.json'
        foreign.write_bytes(b'foreign evidence: preserve these exact bytes')
        before = self.fixture.snapshot(run)
        with self.assertRaisesRegex(ValueError, 'foreign evidence'):
            self.artifacts.retain(run, self.fixture.write('final.json', value),
                                  context_input=context, evidence_inputs=inputs)
        self.assertEqual(before, self.fixture.snapshot(run))

    def test_automatic_context_retries_owned_interrupted_and_inventoried_evidence(self):
        from unittest.mock import patch
        run, value, context, inputs = self.prepared()
        final = self.fixture.write('final.json', value)
        original = archive_retention.atomic_write
        def interrupt(path, data):
            original(path, data)
            if path == run / 'evidence' / 'context.json':
                raise OSError('interrupted after owned context write')
        with patch.object(archive_retention, 'atomic_write', side_effect=interrupt), self.assertRaises(OSError):
            self.artifacts.retain(run, final, context_input=context, evidence_inputs=inputs)
        self.assertIn('evidence/context.json', self.artifacts.read_json(run / 'cierre.json')['planned_hashes'])
        self.artifacts.retain(run, final, context_input=context)
        self.artifacts.retain(run, final, context_input=context, evidence_inputs=inputs)
        self.assertEqual(self.artifacts.read_json(run / 'evidence' / 'context.json')['profile'], 'deep')
        self.assertTrue(self.artifacts.validate(run, require_retained=True)['retained'])

    def test_execution_sources_must_exist_before_retention(self):
        run, value, context, inputs = self.prepared()
        before = self.fixture.snapshot(run)
        with self.assertRaises(ValueError):
            self.artifacts.retain(run, self.fixture.write('final.json', value), context_input=context, evidence_inputs=inputs[:1])
        self.assertEqual(before, self.fixture.snapshot(run))

    def test_context_trace_profile_mismatch_blocks_retention(self):
        run, value, context, inputs = self.prepared()
        raw = self.artifacts.read_json(context)
        raw['profile'] = 'standard'
        context = self.fixture.write('context.json', raw)
        before = self.fixture.snapshot(run)
        with self.assertRaises(ValueError):
            self.artifacts.retain(run, self.fixture.write('final.json', value), context_input=context, evidence_inputs=inputs)
        self.assertEqual(before, self.fixture.snapshot(run))

    def test_schema8_delivery_preserves_source_and_execution_provenance(self):
        run, value, context, inputs = self.prepared()
        self.artifacts.retain(run, self.fixture.write('final.json', value), context_input=context, evidence_inputs=inputs)
        self.artifacts.validate(run, require_retained=True)
        self.artifacts.close(run, cleanup='not_needed', residuals=[])
        before = self.fixture.snapshot(run)
        from pathlib import Path
        target = Path(delivery_tests.delivery.deliver(run, 'full', self.fixture.repo))
        projected = self.artifacts.read_json(target / 'review.json')
        receipt = self.artifacts.read_json(target / '.ccr-delivery.json')
        self.assertEqual(projected['schema_version'], 10)
        self.assertEqual(projected['review_id'], value['review_id'])
        self.assertEqual(receipt['source_id_kind'], 'review_id')
        self.assertEqual(projected['coverage']['execution']['status'], 'fulfilled')
        self.assertEqual(contract.validate(projected), [])
        self.assertEqual(before, self.fixture.snapshot(run))
        # Brief projects the same source without requiring portable references to resolve.
        brief_root = self.fixture.root / 'brief-delivery'
        target = Path(delivery_tests.delivery.deliver(run, 'brief', self.fixture.repo, output_root=brief_root))
        self.assertTrue((target / 'resumen.md').is_file())
        self.assertEqual(before, self.fixture.snapshot(run))
