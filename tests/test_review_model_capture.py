"""The setup operation records supplied metadata without selecting a model."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from script_test_support import enable_package_imports
enable_package_imports()
from ccr.workflow import setup
from ccr.workflow.builders import build_model_usage_update

REVIEW_ID = 'CR-' + 'a' * 20
HARNESS = 'synthetic-harness'


def capture(context=None, ledger=None, metadata=None, **kwargs):
    return build_model_usage_update(context or {}, ledger, metadata or {},
        actor=kwargs.pop('actor', {'kind': 'coordinator', 'name': 'coordinator', 'provider_id': None}),
        phase=kwargs.pop('phase', 'coordination'), activity=kwargs.pop('activity', 'coordination'),
        review_id=REVIEW_ID, harness_id=HARNESS, **kwargs)


class ModelCaptureTests(unittest.TestCase):
    def test_schema12_failed_capture_keeps_actual_participants_unknown_without_ledger(self):
        from ccr.reporting.models import model_usage_context, model_summary, model_lines
        coordinator = dict(kind='coordinator', name='actual-coordinator', provider_id=None)
        reviewer = dict(kind='agent', name='actual-reviewer', provider_id='ctx-D1')
        context = dict(profile_history=[dict(actor=coordinator)],
            execution_plan=[dict(id='D1', role='discovery', reference='evidence/briefs.json#D1'),
                            dict(id='D2', role='discovery', reference='evidence/briefs.json#D2')],
            model_usage_diagnostics=['model usage capture incomplete: metadata exceeds bound'])
        events = [dict(kind='agent', status='started', executor=dict(name=reviewer['name'], provider_id=reviewer['provider_id']),
                       evidence=['evidence/briefs.json#D1']),
                  dict(kind='discovery', status='completed', actor=reviewer, evidence=['evidence/briefs.json#D1'])]
        before = json.dumps(context, sort_keys=True)
        with patch('subprocess.run', side_effect=AssertionError('no probes')):
            envelope = model_usage_context(context, lambda name: self.fail('no selected ledger to read'),
                dict(run_id='a'*20, harness_id=HARNESS), record={'schema_version':12}, events=events)
        self.assertIsNone(envelope['ledger'])
        self.assertIsNone(envelope['sha256'])
        summary = model_summary(envelope['context'], envelope['ledger'])
        self.assertFalse(summary['recorded'])
        self.assertEqual([row['assignment_id'] for row in summary['entries']], [None, 'D1'])
        self.assertEqual([row['status'] for row in summary['entries']], ['unknown', 'unknown'])
        text = '\n'.join(model_lines(envelope))
        self.assertIn('actual-coordinator', text)
        self.assertIn('actual-reviewer / D1', text)
        self.assertIn('metadata exceeds bound', text)
        self.assertNotIn('D2', text)
        self.assertEqual(json.dumps(context, sort_keys=True), before)
        # A new run with no attempted capture still contrasts real participants.
        context.pop('model_usage_diagnostics')
        current = model_usage_context(context, lambda name: self.fail('no ledger'),
            dict(run_id='a'*20, harness_id=HARNESS), record={'schema_version':12}, events=events)
        self.assertEqual(len(model_summary(current['context'], None)['entries']), 2)
        # Historical absent-sidecar runs acquire no participant rows or ledger.
        historical = model_usage_context(context, lambda name: self.fail('no ledger'),
            dict(run_id='a'*20, harness_id=HARNESS), record={'schema_version':11}, events=events)
        self.assertEqual(model_summary(historical['context'], None)['entries'], [])
        self.assertNotIn('actual-reviewer', '\n'.join(model_lines(historical)))

    def test_schema12_private_report_and_deliveries_show_known_participants_without_ledger(self):
        from test_review_topology_integration import TopologyIntegrationTests
        from profile_topology_fixtures import record12
        from ccr.reporting import delivery
        topology = TopologyIntegrationTests()
        self.addCleanup(topology.doCleanups)
        fixture = topology.archive()
        run = fixture.prepare()
        value = record12('focused', 'automatic', discovery=1)
        topology.retain12(fixture, run, value)
        fixture.close(run)
        before = fixture.snapshot(run)
        expected = {row['reviewer_context'] for row in value['coverage']['execution']['results']}
        private = (run/'informe.md').read_text(encoding='utf-8')
        self.assertIn('unknown', private)
        for name in expected:
            self.assertIn(name, private)
        self.assertFalse((run/'evidence'/'model-usage.json').exists())
        for mode in ('full', 'brief'):
            target = delivery.deliver(run, mode, fixture.repo, fixture.root/('missing-'+mode))
            text = (target/('informe.md' if mode == 'full' else 'resumen.md')).read_text(encoding='utf-8')
            for name in expected:
                self.assertIn(name, text)
            self.assertIn('unknown', text)
            self.assertIsNone(fixture.read(target/'.ccr-delivery.json')['model_usage_sha256'])
        self.assertEqual(before, fixture.snapshot(run))

    def test_missing_metadata_has_bounded_diagnostic_without_probes(self):
        with patch('subprocess.run', side_effect=AssertionError('no model probes')):
            context, ledger = capture()
        self.assertEqual(ledger['entries'][0]['status'], 'unknown')
        self.assertIn('not exposed', context['model_usage_diagnostics'][0])

    def test_dispatch_process_is_not_a_model_actor(self):
        _, ledger = capture(metadata={'model': 'synthetic-configured'},
            actor={'kind': 'process', 'name': 'dispatcher', 'provider_id': None})
        self.assertEqual(ledger['entries'][0]['status'], 'not_applicable')
        self.assertIsNone(ledger['entries'][0]['configured_model'])

    def test_summary_preserves_observations_and_reports_uncaptured_real_reviewers(self):
        from ccr.reporting.models import model_summary
        context, ledger = capture(metadata={'model': 'synthetic-configured'})
        context['observed_participants'] = [
            dict(actor={'kind': 'agent', 'name': 'actual-reviewer', 'provider_id': 'ctx-1'},
                 assignment_id='D1', phase='discovery', activity='discovery')]
        summary = model_summary(context, ledger)
        self.assertEqual(summary['harness_id'], HARNESS)
        self.assertEqual([row['status'] for row in summary['entries']], ['configured_only', 'unknown'])
        self.assertEqual(summary['entries'][1]['assignment_id'], 'D1')
        self.assertIsNone(summary['entries'][1]['observed_model'])
        self.assertEqual(model_summary({}, None)['entries'], [])
        self.assertFalse(model_summary({}, None)['recorded'])

    def test_selected_ledger_digest_and_review_are_verified(self):
        from ccr.reporting.models import model_usage_context
        import hashlib
        context, ledger = capture()
        raw = json.dumps(ledger).encode()
        manifest = dict(run_id='a'*20, harness_id=HARNESS)
        loaded = model_usage_context(context, lambda name: raw, manifest)
        self.assertEqual(loaded['sha256'], hashlib.sha256(raw).hexdigest())
        with self.assertRaisesRegex(ValueError, 'another review'):
            model_usage_context(context, lambda name: raw, dict(manifest, run_id='b'*20))
        for corrupt in (b'[]', b'null', b'{bad', b' '*262145):
            with self.subTest(corrupt=corrupt[:10]), self.assertRaises(ValueError):
                model_usage_context(context, lambda name: corrupt, manifest)

    def test_summary_tracks_real_dispatches_and_skips_unexecuted_assignments(self):
        from ccr.reporting.models import model_usage_context, model_summary
        context, ledger = capture()
        context['execution_plan'] = [dict(id='D1', role='discovery', reference='evidence/briefs.json#D1'),
                                     dict(id='D2', role='discovery', reference='evidence/briefs.json#D2')]
        events = [dict(kind='agent', status='started', executor={'name':'worker', 'provider_id':'ctx-1'},
                       evidence=['evidence/briefs.json#D1'])]
        envelope = model_usage_context(context, lambda name: json.dumps(ledger).encode(),
            dict(run_id='a'*20, harness_id=HARNESS), events=events)
        summary = model_summary(envelope['context'], envelope['ledger'])
        self.assertEqual([row['assignment_id'] for row in summary['entries']], [None, 'D1'])
        self.assertEqual(summary['entries'][1]['status'], 'unknown')
        events = [dict(kind='discovery', status='completed',
            actor={'kind':'agent', 'name':'worker','provider_id':'ctx-1'},
            evidence=['evidence/briefs.json#D1'])]
        envelope = model_usage_context(context, lambda name: json.dumps(ledger).encode(),
            dict(run_id='a'*20, harness_id=HARNESS), events=events)
        self.assertEqual([row['assignment_id'] for row in model_summary(envelope['context'], envelope['ledger'])['entries']], [None, 'D1'])

    def test_configured_default_and_model_changes_preserve_facts(self):
        context, ledger = capture(metadata={'harness': HARNESS, 'provider_id':'opaque', 'default':'inherited'})
        self.assertEqual(ledger['entries'][0]['status'], 'unknown')
        self.assertIsNone(ledger['entries'][0]['configured_model'])
        context, ledger = capture(context, ledger, {'observed_model':'synthetic-a',
            'source':{'kind':'platform', 'reference':'call-1'}})
        context, ledger = capture(context, ledger, {'observed_model':'synthetic-b',
            'source':{'kind':'platform', 'reference':'call-1'}})
        self.assertEqual([row['status'] for row in ledger['entries']], ['unknown','observed','conflict'])

    def test_coordinator_review_keeps_its_identity_and_assignment(self):
        from ccr.reporting.models import model_summary
        context, ledger = capture(metadata={'model':'synthetic-a'}, assignment_id='D1',
                                   phase='discovery', activity='discovery')
        context['observed_participants'] = [dict(
            actor={'kind':'agent', 'name':'coordinator', 'provider_id':None},
            assignment_id='D1', phase='discovery', activity='discovery')]
        self.assertEqual(len(model_summary(context, ledger)['entries']), 1)

    def test_captured_reviewer_does_not_hide_uncaptured_known_coordinator(self):
        from ccr.reporting.models import model_usage_context, model_summary
        context, ledger = capture(actor={'kind':'agent','name':'reviewer','provider_id':'ctx-1'},
                                   assignment_id='D1', phase='discovery', activity='discovery')
        context['profile_history'] = [dict(actor={'kind':'coordinator','name':'coordinator','provider_id':None})]
        envelope = model_usage_context(context, lambda name: json.dumps(ledger).encode(),
            dict(run_id='a'*20, harness_id=HARNESS))
        rows = model_summary(envelope['context'], envelope['ledger'])['entries']
        self.assertEqual([row['actor']['name'] for row in rows], ['reviewer', 'coordinator'])

    def test_model_presentation_sanitizes_source_and_diagnostic_values(self):
        from ccr.reporting.models import model_lines
        context, ledger = capture(metadata={'observed_model':'synthetic-model',
            'source':{'kind':'platform','reference':'https://private-host/source?token=fixture-secret'}})
        context['model_usage_diagnostics'] = ['password=fixture-password C:/private/source.txt']
        text = '\n'.join(model_lines(dict(context=context, ledger=ledger, sha256='a'*64)))
        self.assertIn('synthetic-model', text)
        for secret in ('fixture-secret', 'private-host', 'fixture-password', 'C:/private'):
            self.assertNotIn(secret, text)
        missing = '\n'.join(model_lines(dict(context={'model_usage_diagnostics':['capture limit reached']}, ledger=None, sha256=None)))
        self.assertIn('capture limit reached', missing)

    def test_models_survive_retention_cleanup_and_local_deliveries(self):
        import hashlib
        from test_review_traceability_archive import Archive11Tests
        from traceability_fixtures import record11
        from ccr.reporting import delivery, render
        case = Archive11Tests()
        self.addCleanup(case.doCleanups)
        case.setUp()
        run = case.prepare()
        manifest = case.read(run/'cierre.json')
        context, ledger = build_model_usage_update({}, None,
            {'model': 'synthetic-configured', 'observed_model': 'synthetic-observed',
             'source': {'kind': 'platform', 'reference': 'C:/private/model-source.json'}},
            actor={'kind': 'coordinator', 'name': 'coordinator', 'provider_id': None},
            phase='coordination', activity='coordination', review_id='CR-'+manifest['run_id'],
            harness_id=manifest['harness_id'])
        case.final = case.write('final11.json', record11())
        ledger_path = case.write('model-usage.json', ledger)
        ledger_bytes = ledger_path.read_bytes()
        context_path = case.write('model-context.json', context)
        case.retain(run, expected_schema=11, context_input=context_path, evidence_inputs=[ledger_path])
        self.assertIn('synthetic-observed', (run/'informe.md').read_text(encoding='utf-8'))
        case.close(run)
        ledger_path.unlink()
        context_path.unlink()
        self.assertIn('synthetic-observed', (run/'informe.md').read_text(encoding='utf-8'))
        before = case.snapshot(run)
        from ccr.archive.retention import retained_model_context
        forged = retained_model_context(run, case.read(run/'cierre.json'))
        forged['sha256'] = '0'*64
        with self.assertRaisesRegex(ValueError, 'model usage'):
            delivery.deliver(run, 'full', case.repo, case.root/'forged', model_usage_context=forged)
        self.assertFalse((case.root/'forged').exists())
        for mode in ('full', 'brief'):
            target = delivery.deliver(run, mode, case.repo, case.root/mode)
            text = (target/('informe.md' if mode == 'full' else 'resumen.md')).read_text(encoding='utf-8')
            self.assertIn('synthetic-observed', text)
            self.assertIn('synthetic-configured', text)
            self.assertIn('unknown', text)
            self.assertNotIn('C:/private', text)
            receipt = case.read(target/'.ccr-delivery.json')
            self.assertEqual(receipt['schema_version'], 2)
            self.assertEqual(receipt['model_usage_sha256'], hashlib.sha256(ledger_bytes).hexdigest())
            if mode == 'full':
                self.assertNotIn('synthetic-observed', (target/'review.json').read_text(encoding='utf-8'))
        self.assertEqual(before, case.snapshot(run))
        value = case.read(run/'review.json')
        from traceability_fixtures import publication_contexts
        comment = render.render(value, audience='comment', **publication_contexts(value))
        self.assertNotIn('synthetic-observed', comment)
        self.assertNotIn('synthetic-observed', render.render_handoff(value))
    def test_setup_model_usage_writes_candidate_and_preserves_source(self):
        with tempfile.TemporaryDirectory() as folder:
            session = Path(folder)
            (session / 'evidence').mkdir()
            args = dict(context={}, ledger=None, metadata={'model': 'synthetic-model'},
                        actor={'kind': 'agent', 'name': 'reviewer', 'provider_id': None},
                        phase='discovery', activity='discovery', review_id='CR-'+'a'*20,
                        harness_id='synthetic-harness', assignment_id='D1', check_id=None)
            request = session / 'input.json'
            request.write_text(json.dumps(dict(session=str(session), arguments=args)), encoding='utf-8')
            output = session / 'evidence' / 'candidate.json'
            with patch.object(setup, '_owned_session', return_value=(session, session/'manifest.json', {'session_id': 'synthetic'})):
                setup.run_command('model-usage', request, output)
            value = json.loads(output.read_text(encoding='utf-8'))
            entry = value['ledger']['entries'][0]
            self.assertEqual(entry['configured_model'], 'synthetic-model')
            self.assertIsNone(entry['observed_model'])
            self.assertEqual(entry['assignment_id'], 'D1')
            self.assertEqual(value['context']['model_usage_reference'], 'evidence/model-usage.json')
            self.assertFalse((session/'evidence'/'model-usage.json').exists())
            self.assertEqual(json.loads(request.read_text(encoding='utf-8'))['arguments']['context'], {})
            args['context'] = value['context']
            args['ledger'] = value['ledger']
            args['metadata'] = {}
            args['actor'] = {'kind': 'coordinator', 'name': 'coordinator', 'provider_id': None}
            args['assignment_id'] = None
            args['phase'] = 'report'
            args['activity'] = 'reporting'
            request.write_text(json.dumps(dict(session=str(session), arguments=args)), encoding='utf-8')
            second_output = session / 'evidence' / 'candidate-2.json'
            with patch.object(setup, '_owned_session', return_value=(session, session/'manifest.json', {'session_id': 'synthetic'})):
                setup.run_command('model-usage', request, second_output)
            second = json.loads(second_output.read_text(encoding='utf-8'))
            self.assertEqual(len(second['ledger']['entries']), 2)
            self.assertEqual(second['ledger']['entries'][0], entry)
            self.assertEqual(second['ledger']['entries'][1]['status'], 'unknown')
            self.assertIsNone(second['ledger']['entries'][1]['configured_model'])
            self.assertIsNone(second['ledger']['entries'][1]['observed_model'])

    def test_setup_model_usage_records_supplied_coordinator_and_assignments(self):
        with tempfile.TemporaryDirectory() as folder:
            session = Path(folder)
            (session/'evidence').mkdir()
            context, ledger = {}, None
            for index, assignment in enumerate((None, 'D1', 'D2', 'V1')):
                activity = 'coordination' if assignment is None else ('discovery' if assignment.startswith('D') else 'verification')
                actor = dict(kind='coordinator' if assignment is None else 'agent',
                             name=assignment or 'coordinator', provider_id=None if assignment is None else 'ctx-'+assignment)
                metadata = {} if assignment == 'D2' else {'model':'synthetic-'+str(index)}
                args = dict(context=context, ledger=ledger, metadata=metadata, actor=actor,
                    phase=activity, activity=activity, review_id=REVIEW_ID, harness_id=HARNESS,
                    assignment_id=assignment, check_id=None)
                request = session/('request-'+str(index)+'.json')
                request.write_text(json.dumps(dict(session=str(session), arguments=args)), encoding='utf-8')
                output = session/'evidence'/('candidate-'+str(index)+'.json')
                with patch.object(setup, '_owned_session', return_value=(session, session/'manifest.json', {'session_id':'synthetic'})), \
                     patch('subprocess.run', side_effect=AssertionError('no dispatch or provider probe')):
                    setup.run_command('model-usage', request, output)
                candidate = json.loads(output.read_text(encoding='utf-8'))
                context, ledger = candidate['context'], candidate['ledger']
            self.assertEqual([row['assignment_id'] for row in ledger['entries']], [None,'D1','D2','V1'])
            self.assertEqual([row['status'] for row in ledger['entries']], ['configured_only','configured_only','unknown','configured_only'])
            self.assertEqual(context['model_usage_reference'], 'evidence/model-usage.json')
            self.assertNotIn('review_inputs', context)

    def test_result_only_completions_preserve_assignment_models_and_identity(self):
        import copy
        from profile_topology_fixtures import record12, source_fixture12
        from ccr.contracts.execution import validate_execution_sources
        from ccr.reporting.models import model_usage_context, model_summary
        record = record12('focused', 'automatic', discovery=1)
        context, events, references = source_fixture12(record)
        result_refs = {r['reference'] for r in record['coverage']['execution']['results']}
        for event in events:
            if event.get('kind') == 'agent':
                event['kind'] = 'discovery' if 'D1' in str(event['evidence']) else 'grouped-verification'
                event.pop('executor', None)
                event['actor'] = dict(kind='coordinator', name='coordinator', provider_id=None)
            if event.get('kind') in ('discovery', 'grouped-verification') and event.get('status') in ('completed', 'passed'):
                event['evidence'] = [ref for ref in event['evidence'] if ref in result_refs]
        self.assertEqual(validate_execution_sources(record, context, events, references), [])
        def entries(candidate):
            envelope = model_usage_context(context, lambda _: self.fail('no ledger'),
                dict(run_id=record['review_id'][3:], harness_id=HARNESS), record=record, events=candidate)
            self.assertIsNone(envelope['ledger'])
            return model_summary(envelope['context'], None)['entries']
        rows = entries(events)
        self.assertEqual([(r['actor']['name'], r['assignment_id'], r['phase']) for r in rows],
            [('coordinator', None, 'coordination'), ('coordinator', 'D1', 'discovery'), ('coordinator', 'V1', 'verification')])
        for mismatch in ('name', 'provider_id', 'role'):
            bad = copy.deepcopy(events)
            event = next(e for e in bad if e.get('status') == 'completed' and 'evidence/results.json#D1' in e.get('evidence', []))
            if mismatch == 'role': event['kind'] = 'grouped-verification'
            else: event['actor'][mismatch] = 'unrelated'
            self.assertNotIn('D1', [r['assignment_id'] for r in entries(bad)])
