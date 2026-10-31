"""Schema 12 is admitted across the same boundaries as schema 11."""
import copy
import json
import unittest

from script_test_support import enable_package_imports, archive_api
enable_package_imports()
from ccr.archive import lifecycle, retention
artifacts = archive_api()
from ccr.contracts import packets, receipts, review
from ccr.reporting import comment, delivery, render
from profile_topology_fixtures import record12
from recovery_fixtures import context10
from traceability_fixtures import publication_contexts, receipt2_bundle
import test_review_traceability_archive as archive_tests
import test_review_traceability_preflight as preflight_tests


def contexts12(record):
    contexts = publication_contexts(record)
    for row, check in zip(contexts['check_publication_context']['checks'], record['checks']):
        row['purpose'] = check['purpose']
    return contexts


class TopologyIntegrationTests(unittest.TestCase):
    def test_schema12_requires_valid_profile_binding(self):
        value = record12('focused', 'automatic', discovery=1)
        value['coverage']['execution']['plan'][0]['selection_id'] = 'unknown'
        self.assertTrue(any('unknown selection' in error for error in review.validate(value)))

    def archive(self):
        fixture = archive_tests.Archive11Tests()
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        return fixture

    def retain12(self, fixture, run, value, expected=12):
        manifest = fixture.read(run / 'cierre.json')
        value = copy.deepcopy(value)
        value['scope'] = manifest['scope']
        value['review_id'] = 'CR-' + manifest['run_id']
        execution = value['coverage']['execution']
        execution['selection_source'] = manifest['profile_history'][0]['selection_source']
        execution['profile_history'] = manifest['profile_history']
        context = context10(value)
        context['review_inputs'] = manifest['review_inputs']
        from ccr.workflow.builders import build_check_disclosure
        from ccr.contracts.check_disclosure import input_identity_for
        identity = input_identity_for(value)
        disclosure = build_check_disclosure(value, identity, {}, {})
        context.update(check_disclosure_reference='evidence/check-disclosure.json', check_disclosure_input_identity=identity)
        if expected == 12:
            artifacts.register(run, [], context_input=fixture.write('register12.json', context))
            for index, (assignment, result) in enumerate(zip(execution['plan'], execution['results']), 1):
                identity = {'name': result['reviewer_context'], 'provider_id': result['provider_id']}
                artifacts.record_event(run, fixture.write(f'start12-{index}.json', {
                    'kind': 'agent', 'status': 'started', 'summary': 'Synthetic reviewer started',
                    'executor': identity, 'evidence': [assignment['reference']]}))
                artifacts.record_event(run, fixture.write(f'result12-{index}.json', {
                    'kind': 'discovery' if assignment['role'] == 'discovery' else 'grouped-verification',
                    'status': 'completed', 'summary': 'Synthetic assignment completed',
                    'actor': {'kind': 'agent', **identity},
                    'evidence': [assignment['reference'], result['reference']]}))
        briefs = {row['id']: {'assignment_id': row['id'], 'scope': value['scope']} for row in execution['plan']}
        results = {row['assignment_id']: {'assignment_id': row['assignment_id'], 'status': 'completed'}
                   for row in execution['results']}
        return artifacts.retain(run, fixture.write('final12.json', value), expected_schema=expected,
            context_input=fixture.write('context12.json', context),
            evidence_inputs=[fixture.write('briefs.json', briefs), fixture.write('results.json', results),
                             fixture.write('check-disclosure.json', disclosure)],
            unavailable_reason='Provider exposes no counters')

    def test_schema12_archive_roundtrip(self):
        fixture = self.archive()
        run = fixture.prepare()
        value = record12('focused', 'automatic', discovery=1)
        self.retain12(fixture, run, value)
        self.assertTrue(lifecycle.validate(run, require_retained=True)['retained'])
        fixture.close(run)
        self.assertEqual(lifecycle.validate(run, require_complete=True)['state'], 'complete')
        saved = fixture.read(run / 'review.json')
        self.assertEqual(saved['checks'][0]['purpose'], value['checks'][0]['purpose'])
        self.assertEqual(sum(len(row['dimensions']) for row in saved['coverage']['areas']), 27)

    def test_schema12_checkpoint_promotes_exact_bytes(self):
        class Checkpoint12(archive_tests.TraceabilityCheckpointTests):
            def final_record(self, run, profile='focused', late_profile=False):
                value = super().final_record(run, profile, late_profile)
                value['schema_version'] = 12
                return value
        case = Checkpoint12('test_valid_final_checkpoint_can_be_promoted_without_external_files')
        self.addCleanup(case.doCleanups)
        case.setUp()
        run, _, _ = case.prepare_promotable_checkpoint()
        before = (run / 'pending' / 'review.json').read_bytes()
        retention.retain(run, expected_schema=12)
        self.assertEqual((run / 'review.json').read_bytes(), before)

    def test_schema11_expectation_rejects_schema12(self):
        fixture = self.archive()
        run = fixture.prepare()
        with self.assertRaisesRegex(ValueError, 'expected schema'):
            self.retain12(fixture, run, record12('focused', 'automatic', discovery=1), expected=11)
        self.assertFalse((run / 'review.json').exists())

    def test_schema12_preflight_rejects_missing_traceability(self):
        case = preflight_tests.Preflight11Tests()
        for mutation in ('purpose', 'dimension'):
            value = record12('focused', 'automatic', discovery=1)
            if mutation == 'purpose':
                del value['checks'][0]['purpose']
            else:
                value['coverage']['areas'][0]['dimensions'].pop()
            self.assertFalse(case.evaluate(value)['ready'])

    def test_schema12_receipt2_and_provenance(self):
        receipt, sources, check, executors = receipt2_bundle()
        reference = 'evidence/attempt-C001-receipt.json'
        check.update(reused=False, reference=reference)
        record = {'schema_version': 12, 'checks': [check]}
        sources[reference] = json.dumps(receipt).encode()
        self.assertEqual(receipts.validate_record_receipts(record, sources, executors), [])
        changed = copy.deepcopy(receipt)
        changed['purpose'] = 'Unrelated purpose'
        sources[reference] = json.dumps(changed).encode()
        self.assertTrue(receipts.validate_record_receipts(record, sources, executors))
        receipt['schema_version'] = 1
        del receipt['purpose']
        sources[reference] = json.dumps(receipt).encode()
        self.assertTrue(receipts.validate_record_receipts(record, sources, executors))

    def test_schema12_packet_merge_keeps_purpose(self):
        value = record12('focused', 'automatic', discovery=1)
        context = dict(context_id='ctx', scope=value['scope'], checks=value['checks'], check_schema_version=12)
        packet = dict(packet_version=1, stage='discovery', context_id='ctx', findings=[],
                      check_ids=['C001'], coverage=dict(flows=['Inspección'], limitations=[]))
        self.assertEqual(packets.merge(context, [packet])['checks'][0]['purpose'], value['checks'][0]['purpose'])
        context = copy.deepcopy(context)
        del context['checks'][0]['purpose']
        with self.assertRaises(ValueError):
            packets.merge(context, [packet])

    def test_schema12_render_and_delivery(self):
        fixture = self.archive()
        run = fixture.prepare()
        value = record12('focused', 'automatic', discovery=1)
        self.retain12(fixture, run, value)
        fixture.close(run)
        before = fixture.snapshot(run)
        self.assertIn('Dimensiones de cobertura', render.render(value))
        for mode in ('full', 'brief'):
            target = delivery.deliver(run, mode, fixture.repo, fixture.root / mode)
            text = (target / ('informe.md' if mode == 'full' else 'resumen.md')).read_text(encoding='utf-8')
            self.assertIn(value['checks'][0]['purpose'], text)
            self.assertIn('A01', text)
            if mode == 'full':
                self.assertEqual(fixture.read(target / 'review.json')['schema_version'], 12)
        self.assertEqual(fixture.snapshot(run), before)

    def test_schema12_public_draft3(self):
        value = record12('focused', 'automatic', discovery=1)
        from ccr.workflow.builders import build_check_disclosure
        from ccr.contracts.check_disclosure import input_identity_for
        disclosure = build_check_disclosure(value, input_identity_for(value), {}, {})
        kwargs = dict(check_disclosure_context=disclosure, check_disclosure_sources={})
        draft = comment.prepare_public_comment(value, **contexts12(value), **kwargs)
        self.assertEqual(draft['schema_version'], 3)
        self.assertIn(value['checks'][0]['purpose'], draft['body'])
        self.assertTrue(comment.verify_public_comment(value, draft, draft['body'], **kwargs)['verified'])
        bad = contexts12(value)
        bad['check_publication_context']['source_sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            comment.prepare_public_comment(value, **bad, **kwargs)
        bad = contexts12(value)
        del bad['check_publication_context']['checks'][0]['purpose']
        with self.assertRaises(ValueError):
            comment.prepare_public_comment(value, **bad, **kwargs)
