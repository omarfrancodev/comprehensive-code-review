"""Pure dispatch identity and late-annotation projection contracts."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from ccr.contracts import dispatch


class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.brief = 'evidence/briefs.json#D1'
        self.assignment = {
            'id': 'D1', 'role': 'discovery', 'independent': True, 'required': True,
            'reference': self.brief, 'selection_id': 'S001', 'superseded_by': None,
        }
        self.registry = [self.assignment]

    def start(self, *, executor=None, event_id='E000004', sequence=4,
              evidence=None, kind='agent'):
        return {
            'kind': kind, 'status': 'started', 'summary': 'Observed dispatch',
            'actor': {'kind': 'coordinator', 'name': 'coordinator', 'provider_id': None},
            'executor': copy.deepcopy(executor),
            'provenance': {'kind': 'tool', 'source': 'dispatch adapter'},
            'evidence': [self.brief] if evidence is None else list(evidence),
            'relations': [], 'authority': None, 'occurred_at': None,
            'event_id': event_id, 'sequence': sequence,
        }

    def annotation(self, *, target='E000004', executor=None, source='evidence/dispatch.json#D1',
                   evidence=None, sequence=8, event_id='E000008', occurred_at=None):
        return {
            'kind': 'dispatch-identity', 'status': 'unchanged',
            'summary': 'Observed identity for original dispatch; no new execution',
            'actor': {'kind': 'coordinator', 'name': 'coordinator', 'provider_id': None},
            'executor': {'name': 'worker-a', 'provider_id': None} if executor is None else executor,
            'provenance': {'kind': 'recovered', 'source': source},
            'evidence': [self.brief, source] if evidence is None else list(evidence),
            'relations': [{'relation': 'records', 'target': target}],
            'authority': None, 'occurred_at': occurred_at,
            'event_id': event_id, 'sequence': sequence,
        }

    def test_independent_start_requires_executor(self):
        event = self.start()
        self.assertTrue(dispatch.validate_dispatch_identity_event(event, self.registry))
        event['executor'] = {'name': 'worker-a', 'provider_id': None}
        self.assertEqual(dispatch.validate_dispatch_identity_event(event, self.registry), [])

    def test_generic_unchanged_milestones_do_not_project_dispatch_identity(self):
        for source in (None, 'observed harness notice'):
            for relations in ([], [{'relation': 'records', 'target': 'C001'}],
                              [{'relation': 'records', 'target': 'External worker observation'}]):
                with self.subTest(source=source, relations=relations):
                    event = self.annotation()
                    event.update(kind='agent', summary='Worker already active; no new dispatch', executor=None,
                                 provenance={'kind': 'agent', 'source': source},
                                 evidence=[], relations=relations)
                    events = [self.start(), event]
                    before = copy.deepcopy(events)

                    self.assertEqual(dispatch.validate_dispatch_identity_event(event, self.registry), [])
                    projected, issues = dispatch.project_dispatches(events, self.registry)

                    self.assertEqual(issues, [])
                    self.assertIsNone(projected[0]['executor'])
                    self.assertEqual(events, before)

    def test_partial_identity_intent_is_still_rejected(self):
        for changes in (
            {'relations': []},
            {'provenance': {'kind': 'agent', 'source': None}},
            {'provenance': {'kind': 'recovered', 'source': None}},
            {'executor': None},
        ):
            with self.subTest(changes=changes):
                event = self.annotation()
                event.update(changes)
                events = [self.start(), event]
                before = copy.deepcopy(events)

                self.assertTrue(dispatch.validate_dispatch_identity_event(event, self.registry, events))
                projected, issues = dispatch.project_dispatches(events, self.registry)

                self.assertTrue(issues)
                self.assertIsNone(projected[0]['executor'])
                self.assertEqual(events, before)

    def test_historical_recovered_and_local_records_do_not_claim_identity(self):
        for provenance, relations in (
            ({'kind': 'recovered', 'source': 'Observed worker notice'}, []),
            ({'kind': 'tool', 'source': None}, [{'relation': 'records', 'target': 'E000004'}]),
            ({'kind': 'recovered', 'source': 'Observed worker notice'},
             [{'relation': 'records', 'target': 'E000004'}]),
        ):
            with self.subTest(provenance=provenance, relations=relations):
                event = self.annotation()
                event.update(kind='agent', executor=None, evidence=[],
                             provenance=provenance, relations=relations)
                events = [self.start(), event]
                before = copy.deepcopy(events)

                self.assertEqual(dispatch.validate_dispatch_identity_event(event, self.registry), [])
                projected, issues = dispatch.project_dispatches(events, self.registry)

                self.assertEqual(issues, [])
                self.assertIsNone(projected[0]['executor'])
                self.assertEqual(events, before)

    def test_explicit_identity_kind_projects_the_original_dispatch(self):
        event = dict(self.annotation(), kind='dispatch-identity')
        projected, issues = dispatch.project_dispatches([self.start(), event], self.registry)
        self.assertEqual(issues, [])
        self.assertEqual(projected[0]['executor'], event['executor'])
        self.assertEqual(projected[0]['sequence'], 4)

    def test_annotation_shaped_historical_event_does_not_supply_identity(self):
        event = dict(self.annotation(), kind='agent')
        projected, issues = dispatch.project_dispatches([self.start(), event], self.registry)
        self.assertEqual(issues, [])
        self.assertFalse(dispatch.is_identity_annotation(event))
        self.assertIsNone(projected[0]['executor'])

    def test_explicit_identity_kind_keeps_partial_events_under_validation(self):
        for changes in ({'relations': []}, {'executor': None}, {'status': 'completed'},
                        {'provenance': {'kind': 'agent', 'source': None}},
                        {'evidence': []}):
            with self.subTest(changes=changes):
                event = dict(self.annotation(), kind='dispatch-identity', **changes)
                self.assertTrue(dispatch.validate_dispatch_identity_event(event, self.registry))
                _, issues = dispatch.project_dispatches([self.start(), event], self.registry)
                self.assertTrue(issues)

    def test_late_annotation_keeps_original_order_and_result(self):
        original = self.start()
        result = {
            'kind': 'discovery', 'status': 'completed', 'summary': 'Observed result',
            'evidence': [self.brief], 'event_id': 'E000007', 'sequence': 7,
        }
        events = [original, result, self.annotation()]
        before = copy.deepcopy(events)

        projected, issues = dispatch.project_dispatches(events, self.registry)

        self.assertEqual(issues, [])
        self.assertEqual(events, before)
        self.assertEqual(len(projected), 1)
        self.assertEqual(projected[0]['sequence'], 4)
        self.assertEqual(projected[0]['event_id'], 'E000004')
        self.assertEqual(projected[0]['executor'], {'name': 'worker-a', 'provider_id': None})
        self.assertIsNone(projected[0]['occurred_at'])
        self.assertIn(result, events)

    def test_annotation_target_and_conflicts_are_rejected(self):
        valid_start = self.start()
        bad_cases = [
            ([valid_start], self.annotation(target='E000999')),
            ([valid_start, self.start(event_id='E000009', sequence=9)],
             self.annotation(target='E000009', sequence=8)),
            ([self.start(evidence=['evidence/briefs.json#D2'])], self.annotation()),
            ([self.start(executor={'name': 'already-known', 'provider_id': None})], self.annotation()),
            ([valid_start], self.annotation(source='https://example.invalid/dispatch.json#D1')),
            ([valid_start], self.annotation(source='evidence/dispatch.json')),
            ([valid_start], self.annotation(source=None, evidence=[self.brief])),
            ([valid_start], self.annotation(occurred_at='2026-10-23T00:00:00Z')),
            ([valid_start], self.annotation(evidence=[self.brief])),
        ]
        for events, annotation in bad_cases:
            with self.subTest(annotation=annotation):
                projected, issues = dispatch.project_dispatches(events + [annotation], self.registry)
                self.assertTrue(issues)
                self.assertFalse(any(row.get('executor') == annotation.get('executor') for row in projected))

        non_independent = [dict(self.assignment, independent=False)]
        issues = dispatch.validate_dispatch_identity_event(
            self.annotation(), non_independent, [valid_start, self.annotation()])
        self.assertTrue(issues)

        conflict = self.annotation(executor={'name': 'worker-b', 'provider_id': None}, event_id='E000009')
        projected, issues = dispatch.project_dispatches(
            [valid_start, self.annotation(), conflict], self.registry)
        self.assertTrue(issues)
        self.assertTrue(all(row.get('executor') is None for row in projected))

    def test_static_start_and_unknown_provider_remain_valid(self):
        static = self.start(kind='discovery')
        self.assertEqual(dispatch.validate_dispatch_identity_event(static, self.registry), [])

        observed = self.start(executor={'name': 'worker-a', 'provider_id': None})
        self.assertEqual(dispatch.validate_dispatch_identity_event(observed, self.registry), [])

    def test_nested_dispatch_alias_grammar_preserves_projection_and_rejects_unsafe_paths(self):
        event = self.annotation(source='evidence/harness/dispatch.json#D1')
        projected, issues = dispatch.project_dispatches([self.start(), event], self.registry)
        self.assertEqual(issues, [])
        self.assertEqual(projected[0]['event_id'], 'E000004')
        self.assertEqual(projected[0]['executor'], {'name': 'worker-a', 'provider_id': None})
        for source in ('evidence/../dispatch.json#D1', '/evidence/harness/dispatch.json#D1',
                       'evidence/harness%2fdispatch.json#D1', 'evidence/harness/dispatch.json?x#D1'):
            with self.subTest(source=source):
                self.assertTrue(dispatch.validate_dispatch_identity_event(
                    self.annotation(source=source), self.registry))


if __name__ == '__main__':
    unittest.main()
