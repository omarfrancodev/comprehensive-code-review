import copy
import hashlib
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from script_test_support import enable_package_imports
enable_package_imports()
import test_review_compact_archive as fixtures
from ccr.archive import compact, transactions
from ccr.reporting import render, delivery
from ccr.workflow.builders import build_check_disclosure
from ccr.shared.git import repository_identity
from ccr.contracts.model_usage import observation_from_metadata, append_model_observation
from test_review_coverage13 import record13

class ReviewFixTests(unittest.TestCase):
    setUp = fixtures.CompactPrepareTests.setUp
    prepare = fixtures.CompactPrepareTests.prepare
    record_and_sources = fixtures.CompactPrepareTests.record_and_sources

    def test_handoff_accepts_grouped_pending_dimensions(self):
        record = record13()
        group = record['coverage']['areas'][0]['groups'][0]
        group.update(status='partial', reason='Fallback pendiente')
        text = render.render_handoff(record)
        self.assertIn('Fallback pendiente', text)
        self.assertIn('A01', text)

    def test_promoted_writes_use_reserved_staging(self):
        run = self.root / 'full'
        run.mkdir()
        (run / '.review-restart-reservation.json').write_text('{}')
        with patch.object(transactions, 'atomic_write') as write:
            transactions._archive_write(run, {'compact_promotion': {'reservation_id': 'reserved'}}, 'cierre.json', b'{}')
        self.assertEqual(write.call_args.kwargs['staging_path'], run / '.cierre.json.reserved.tmp')

    def test_compact_alias_is_retained_and_read(self):
        proof = b'# inspection\nVerified flow'
        digest = hashlib.sha256(proof).hexdigest()
        index = {'schema_version': 1, 'aliases': {'evidence/original/nested.md': {
            'reference': 'evidence/proof.md', 'sha256': digest}}, 'inputs': []}
        raw = json.dumps(index).encode()
        inputs = dict(self.inputs, sources={'evidence/reference-index.json': hashlib.sha256(raw).hexdigest()})
        prepared = self.prepare(inputs=inputs)
        record, sources = self.record_and_sources(prepared)
        record['description'] = {'status': 'unverified', 'identity': None, 'details': 'No captured description'}
        context = json.loads(sources['evidence/context.json'])
        context['reference_index'] = 'evidence/reference-index.json'
        sources.update({'evidence/context.json': json.dumps(context).encode(),
            'evidence/reference-index.json': raw, 'evidence/proof.md': proof})
        record['coverage']['evidence'][0]['reference'] = 'evidence/original/nested.md#inspection'
        result = compact.create_compact(prepared, record, render.render(record), inputs, sources)
        self.assertEqual(compact.read_compact(result['run_dir'])['record']['review_id'], prepared['review_id'])

    def with_models(self, prepared, record, sources):
        observation = observation_from_metadata({'observed_model': 'observed-review-model',
            'model_source': {'kind': 'platform', 'reference': 'call-1'}},
            actor={'kind': 'coordinator', 'name': 'coordinator', 'provider_id': None},
            phase='coordination', activity='coordination')
        ledger = append_model_observation(None, observation, review_id=record['review_id'],
            harness_id=prepared['request']['producer']['harness_id'])
        context = json.loads(sources['evidence/context.json'])
        context['model_usage_reference'] = 'evidence/model-usage.json'
        sources['evidence/context.json'] = json.dumps(context).encode()
        sources['evidence/model-usage.json'] = json.dumps(ledger).encode()

    def test_compact_report_shows_retained_model(self):
        prepared = self.prepare()
        record, sources = self.record_and_sources(prepared)
        self.with_models(prepared, record, sources)
        result = compact.create_compact(prepared, record, render.render(record), self.inputs, sources)
        self.assertIn('observed-review-model', (Path(result['run_dir']) / 'informe.md').read_text(encoding='utf-8'))
        compact.read_compact(result['run_dir'])

    def test_oversized_raw_model_ledger_is_rejected_before_publish(self):
        prepared = self.prepare()
        record, sources = self.record_and_sources(prepared)
        self.with_models(prepared, record, sources)
        sources['evidence/model-usage.json'] += b' ' * 262145
        with self.assertRaises(ValueError):
            compact.create_compact(prepared, record, render.render(record), self.inputs, sources)
        self.assertFalse(Path(prepared['run_dir']).exists())

    def test_both_deliveries_use_retained_disclosure(self):
        repo = self.root / 'repo'
        repo.mkdir()
        subprocess.run(['git', 'init', '-q', str(repo)], check=True, capture_output=True)
        prepared = self.prepare(repo_identity=repository_identity(repo), archive_root=self.root / 'archive')
        record, sources = self.record_and_sources(prepared)
        record['compact_identity'] = compact._compact_identity(prepared['request'], prepared['logical_scope'], prepared['created_at'])
        identity = {'head': record['scope']['head'], 'snapshot': record['scope']['snapshot'], 'resource_manifest_sha256': None}
        sidecar = build_check_disclosure(record, identity, {}, sources)
        context = json.loads(sources['evidence/context.json'])
        context.update(check_disclosure_reference='evidence/check-disclosure.json', check_disclosure_input_identity=identity)
        sources.update({'evidence/context.json': json.dumps(context).encode(), 'evidence/check-disclosure.json': json.dumps(sidecar).encode()})
        result = compact.create_compact(prepared, record, render.render(record), self.inputs, sources)
        for mode in ('brief', 'full'):
            path = delivery.deliver(result['run_dir'], mode, repo, repo / mode)
            self.assertTrue((path / '.ccr-delivery.json').is_file())
