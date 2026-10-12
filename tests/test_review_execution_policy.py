"""Observable schema, independence and retained-provenance gates."""
import copy
import json
import unittest

from test_review_profile_names import record7
from test_review_contract import contract, finding
from review_execution import validate_execution_sources
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

    def test_focused_requires_one_actual_context(self):
        value = record8()
        value['coverage']['execution']['results'][-1]['reviewer_context'] = 'another-context'
        self.assertInvalid(value, 'same context')


if __name__ == '__main__':
    unittest.main()


class ArchiveExecutionPolicyTests(unittest.TestCase):
    def setUp(self):
        self.fixture = delivery_tests.DeliveryTests()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()
        self.artifacts = delivery_tests.artifacts

    def prepared(self, profile='deep'):
        value = record8(profile)
        fixture = self.fixture
        run = self.artifacts.prepare(fixture.repo, fixture.write('scope.json', value['scope']),
                                     '2.11.0', 'codex', output_root=fixture.archive)
        from pathlib import Path
        run = Path(run)
        value['review_id'] = 'CR-' + self.artifacts.read_json(run / 'cierre.json')['run_id']
        context, events, _ = source_fixture(value)
        for event in events:
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
        self.assertEqual(projected['schema_version'], 8)
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
