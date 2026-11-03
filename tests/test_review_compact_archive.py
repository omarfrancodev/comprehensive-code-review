import copy
import contextlib
import io
import json
import subprocess
import os
import threading
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor

from script_test_support import enable_package_imports
enable_package_imports()
from ccr.archive import compact
from ccr.archive import lifecycle
from ccr.cli import artifacts as artifacts_cli
from ccr.archive.inspection import inspect_run
from ccr.archive.lookup import find_candidates, select_latest
from ccr.shared.git import repository_identity
from ccr.reporting import delivery, render
from recovery_fixtures import context10, selection_input
from profile_topology_fixtures import source_fixture12
from test_review_coverage13 import record13


class CompactPrepareTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='compact-review-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.scope = record13()['scope']
        self.inputs = {'scope': copy.deepcopy(self.scope), 'sources': {}, 'source_set_complete': True}
        self.selection = {'mode': 'compact', 'reason': 'Alcance identificado'}
        self.profile_input = selection_input('focused', 'explicit')

    def prepare(self, scope=None, selector=None, inputs=None, operation_id='operation-1', repo_identity=None,
                archive_root=None):
        scope = scope or self.scope
        return compact.prepare_compact(archive_root or self.root, repo_identity or 'origin:https://example.test/team/repo', scope,
                                       selector, inputs or self.inputs, self.selection, operation_id,
                                       profile_input=self.profile_input, skill_version='3.5.0', harness='codex')

    def test_exact_retry_keeps_identity_and_rejects_changed_inputs(self):
        prepared = self.prepare()
        self.assertEqual(prepared, self.prepare())
        inputs = copy.deepcopy(self.inputs)
        inputs['requirements_identity'] = 'different'
        with self.assertRaises(ValueError):
            self.prepare(inputs=inputs)

    def test_interrupted_preparation_retries_without_adopting_partial_directory(self):
        def interrupt(source, target):
            raise OSError('injected preparation interruption')
        with patch.object(compact, '_publish_no_replace', side_effect=interrupt):
            with self.assertRaises(OSError):
                self.prepare()
        prepared = self.prepare()
        self.assertEqual(prepared, self.prepare())
        self.assertTrue(Path(prepared['staging_dir'], '.reservation.json').is_file())

    def test_concurrent_preparations_remove_only_their_verified_losing_build(self):
        barrier = threading.Barrier(2)
        original = compact._publish_no_replace
        def publish(source, target):
            barrier.wait(timeout=15)
            return original(source, target)
        with patch.object(compact, '_publish_no_replace', side_effect=publish):
            with ThreadPoolExecutor(max_workers=2) as pool:
                prepared = list(pool.map(lambda _: self.prepare(), range(2)))
        self.assertEqual(prepared[0], prepared[1])
        self.assertEqual(list(Path(prepared[0]['staging_dir']).parent.glob('.compact-build-*')), [])

    def test_explicit_harness_identity_is_pinned(self):
        prepared = compact.prepare_compact(self.root, 'origin:https://example.test/team/repo', self.scope,
            None, self.inputs, self.selection, 'explicit-harness', profile_input=self.profile_input,
            skill_version='3.5.0', harness='Codex', harness_id='codex-desktop',
            harness_source={'kind': 'user', 'reference': 'declaración de prueba'})
        producer = prepared['request']['producer']
        self.assertEqual(producer['harness_id'], 'codex-desktop')
        self.assertEqual(producer['harness_source']['kind'], 'user')

    def test_module_boundaries_are_explicit_and_distinct(self):
        scope = dict(self.scope, mode='module', reference='refactor')
        inputs = dict(self.inputs, scope=scope)
        first = {'mode': 'module', 'selector': {'reference': 'refactor', 'boundaries': ['src/a']}}
        second = {'mode': 'module', 'selector': {'reference': 'refactor', 'boundaries': ['src/b']}}
        with self.assertRaises(ValueError):
            self.prepare(scope=scope, inputs=inputs)
        one = self.prepare(scope, first, inputs, 'operation-1')
        two = self.prepare(scope, second, inputs, 'operation-2')
        self.assertNotEqual(one['logical_scope']['identity'], two['logical_scope']['identity'])
        self.assertNotEqual(one['run_dir'], two['run_dir'])

    def test_scope_and_input_mismatch_is_refused(self):
        scope = dict(self.scope, head='different')
        with self.assertRaises(ValueError):
            self.prepare(scope=scope)

    def record_and_sources(self, prepared):
        record = record13()
        record['review_id'] = prepared['review_id']
        record['coverage']['execution']['profile_history'][0] = copy.deepcopy(prepared['request']['profile_selection'])
        plan = record['coverage']['execution']['plan']
        results = record['coverage']['execution']['results']
        context, events, _ = source_fixture12(record)
        context['review_inputs'] = copy.deepcopy(prepared['request']['review_inputs'])
        sources = {
            'evidence/context.json': json.dumps(context).encode(),
            'evidence/compact-execution.json': json.dumps(events).encode(),
            'evidence/briefs.json': json.dumps({row['id']: {'question': 'Revisar'} for row in plan}).encode(),
            'evidence/results.json': json.dumps({row['assignment_id']: {'result': 'Revisado'} for row in results}).encode(),
        }
        return record, sources

    def test_missing_or_unobserved_execution_cannot_publish(self):
        prepared = self.prepare()
        record, sources = self.record_and_sources(prepared)
        without_events = dict(sources)
        del without_events['evidence/compact-execution.json']
        with self.assertRaises(ValueError):
            compact.create_compact(prepared, record, render.render(record), self.inputs, without_events)
        sources['evidence/compact-execution.json'] = b'[]'
        with self.assertRaises(ValueError):
            compact.create_compact(prepared, record, render.render(record), self.inputs, sources)
        self.assertFalse(Path(prepared['run_dir']).exists())

    def test_record_must_match_initial_description_and_profile(self):
        inputs = dict(self.inputs, description_identity='different')
        prepared = self.prepare(inputs=inputs)
        record, sources = self.record_and_sources(prepared)
        with self.assertRaisesRegex(ValueError, 'description'):
            compact.create_compact(prepared, record, render.render(record), inputs, sources)
        record['description']['identity'] = 'different'
        record['coverage']['execution']['profile_history'][0]['reason'] = 'Changed afterwards'
        with self.assertRaises(ValueError):
            compact.create_compact(prepared, record, render.render(record), inputs, sources)

    def test_publish_verify_retry_and_detect_manifest_tampering(self):
        prepared = self.prepare()
        record, sources = self.record_and_sources(prepared)
        report = render.render(record)
        result = compact.create_compact(prepared, record, report, self.inputs, sources)
        self.assertEqual(result, compact.create_compact(prepared, record, report, self.inputs, sources))
        read = compact.read_compact(result['run_dir'])
        self.assertEqual(read['record']['review_id'], prepared['review_id'])
        manifest = Path(result['run_dir']) / 'manifest.json'
        content = json.loads(manifest.read_text(encoding='utf-8'))
        content['created_at'] = '2020-01-01T00:00:00+00:00'
        manifest.write_text(json.dumps(content), encoding='utf-8')
        with self.assertRaises(ValueError):
            compact.read_compact(result['run_dir'])

    def test_interrupted_staging_replays_exact_bytes(self):
        prepared = self.prepare()
        record, sources = self.record_and_sources(prepared)
        original = compact._write_exact
        calls = 0
        def interrupt_after_write(path, data):
            nonlocal calls
            original(path, data)
            calls += 1
            if calls == 2:
                raise OSError('injected interruption')
        with patch.object(compact, '_write_exact', side_effect=interrupt_after_write):
            with self.assertRaises(OSError):
                compact.create_compact(prepared, record, render.render(record), self.inputs, sources)
        self.assertFalse(Path(prepared['run_dir']).exists())
        result = compact.create_compact(prepared, record, render.render(record), self.inputs, sources)
        self.assertEqual(compact.read_compact(result['run_dir'])['record']['review_id'], prepared['review_id'])

    def test_interrupted_partial_file_can_only_resume_matching_bytes(self):
        prepared = self.prepare()
        record, sources = self.record_and_sources(prepared)
        original = compact._write_exact
        def interrupt(path, data):
            if path.name == 'review.json':
                path.write_bytes(data[:25])
                raise OSError('interrupted during write')
            original(path, data)
        with patch.object(compact, '_write_exact', side_effect=interrupt):
            with self.assertRaises(OSError):
                compact.create_compact(prepared, record, render.render(record), self.inputs, sources)
        result = compact.create_compact(prepared, record, render.render(record), self.inputs, sources)
        self.assertEqual(compact.read_compact(result['run_dir'])['record']['review_id'], prepared['review_id'])

    def test_preexisting_payload_without_intent_is_never_modified(self):
        prepared = self.prepare()
        record, sources = self.record_and_sources(prepared)
        payload = Path(prepared['staging_dir']) / 'payload'
        payload.mkdir()
        foreign = payload / 'review.json'
        foreign.write_bytes(b'{')
        with self.assertRaises(ValueError):
            compact.create_compact(prepared, record, render.render(record), self.inputs, sources)
        self.assertEqual(foreign.read_bytes(), b'{')

    def test_unselected_staging_file_never_enters_published_artifact(self):
        prepared = self.prepare()
        record, sources = self.record_and_sources(prepared)
        payload = Path(prepared['staging_dir']) / 'payload'
        payload.mkdir()
        foreign = payload / 'unselected-secret.txt'
        foreign.write_text('private', encoding='utf-8')
        with self.assertRaises(ValueError):
            compact.create_compact(prepared, record, render.render(record), self.inputs, sources)
        self.assertTrue(foreign.is_file())
        self.assertFalse(Path(prepared['run_dir']).exists())

    def test_partial_hardlink_never_modifies_external_file(self):
        prepared = self.prepare()
        record, sources = self.record_and_sources(prepared)
        payload = Path(prepared['staging_dir']) / 'payload'
        with patch.object(compact, '_write_exact', side_effect=OSError('interrupted')):
            with self.assertRaises(OSError):
                compact.create_compact(prepared, record, render.render(record), self.inputs, sources)
        external = self.root / 'external.txt'
        external.write_bytes(b'{')
        try:
            os.link(external, payload / 'review.json')
        except OSError as exc:
            self.skipTest('host does not permit hardlinks: ' + str(exc))
        with self.assertRaises(ValueError):
            compact.create_compact(prepared, record, render.render(record), self.inputs, sources)
        self.assertEqual(external.read_bytes(), b'{')

    def test_lost_publication_response_is_idempotent(self):
        prepared = self.prepare()
        record, sources = self.record_and_sources(prepared)
        original = compact._publish_no_replace
        def lost_response(source, target):
            original(source, target)
            raise OSError('lost response after commit')
        with patch.object(compact, '_publish_no_replace', side_effect=lost_response):
            result = compact.create_compact(prepared, record, render.render(record), self.inputs, sources)
        self.assertEqual(result, compact.create_compact(prepared, record, render.render(record), self.inputs, sources))

    def test_unsupported_ownership_marker_is_never_accepted(self):
        prepared = self.prepare()
        record, sources = self.record_and_sources(prepared)
        result = compact.create_compact(prepared, record, render.render(record), self.inputs, sources)
        marker_path = Path(result['run_dir']) / '.review-ownership.json'
        marker = json.loads(marker_path.read_text(encoding='utf-8'))
        marker['schema_version'] = 99
        marker_path.write_text(json.dumps(marker), encoding='utf-8')
        with self.assertRaises(ValueError):
            compact.read_compact(result['run_dir'])

    def test_concurrent_identical_publications_do_not_replace_or_duplicate(self):
        prepared = self.prepare()
        record, sources = self.record_and_sources(prepared)
        def publish():
            try:
                return compact.create_compact(prepared, record, render.render(record), self.inputs, sources)
            except ValueError:
                return None  # A competing lock may be refused; exact retry follows.
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: publish(), range(2)))
        self.assertTrue(any(result is not None for result in results))
        retried = compact.create_compact(prepared, record, render.render(record), self.inputs, sources)
        self.assertEqual(compact.read_compact(retried['run_dir'])['record']['review_id'], prepared['review_id'])

    def test_missing_sources_or_changed_inputs_never_publish(self):
        prepared = self.prepare()
        record, sources = self.record_and_sources(prepared)
        with self.assertRaises(ValueError):
            compact.create_compact(prepared, record, render.render(record), self.inputs, {})
        changed = dict(self.inputs, requirements_identity='changed')
        with self.assertRaises(ValueError):
            compact.create_compact(prepared, record, render.render(record), changed, sources)
        self.assertFalse(Path(prepared['run_dir']).exists())

    def test_lookup_and_latest_recognize_completed_compact(self):
        repo = self.root / 'repo'
        repo.mkdir()
        subprocess.run(['git', 'init', '-q', str(repo)], check=True, capture_output=True)
        identity = repository_identity(repo)
        prepared = self.prepare(repo_identity=identity)
        record, sources = self.record_and_sources(prepared)
        result = compact.create_compact(prepared, record, render.render(record), self.inputs, sources)
        page = find_candidates(repo, self.scope, archive_root=self.root, current_inputs=self.inputs)
        row = next(item for item in page['candidates'] if item['run_dir'] == result['run_dir'])
        self.assertEqual(row['integrity'], 'report_verified')
        self.assertEqual(row['artifact_mode'], 'compact')
        latest = select_latest(repo, self.scope, current_inputs=self.inputs, archive_root=self.root)
        self.assertEqual(latest['status'], 'selected')
        self.assertEqual(latest['selected']['review_id'], prepared['review_id'])
        inspected = inspect_run(result['run_dir'], current_inputs=self.inputs)
        self.assertEqual(inspected['integrity']['status'], 'verified')
        self.assertEqual(inspected['artifact_mode'], 'compact')
        self.assertTrue(lifecycle.validate(result['run_dir'], require_complete=True)['retained'])

    def test_unfinished_cleanup_never_publishes(self):
        prepared = self.prepare()
        record, sources = self.record_and_sources(prepared)
        record['resources']['cleanup'] = 'pending'
        with self.assertRaises(ValueError):
            compact.create_compact(prepared, record, render.render(record), self.inputs, sources)
        self.assertFalse(Path(prepared['run_dir']).exists())

    def test_local_executor_requires_full_resource_ownership(self):
        prepared = self.prepare()
        record, sources = self.record_and_sources(prepared)
        record['checks'][0]['execution'] = {'kind': 'local', 'executor': 'worker'}
        with self.assertRaisesRegex(ValueError, 'full owned-resource archive'):
            compact.create_compact(prepared, record, render.render(record), self.inputs, sources)
        self.assertFalse(Path(prepared['run_dir']).exists())

    def test_tampered_preparation_cannot_redirect_publication(self):
        prepared = self.prepare()
        forged = copy.deepcopy(prepared)
        forged['run_dir'] = str(self.root / 'foreign')
        (Path(prepared['staging_dir']) / 'prepared.json').write_text(json.dumps(forged), encoding='utf-8')
        record, sources = self.record_and_sources(forged)
        with self.assertRaises(ValueError):
            compact.create_compact(forged, record, render.render(record), self.inputs, sources)
        self.assertFalse((self.root / 'foreign').exists())

    def test_tampered_initial_material_identity_cannot_become_the_new_baseline(self):
        prepared = self.prepare()
        forged = copy.deepcopy(prepared)
        forged['request']['review_inputs']['requirements_identity'] = 'replacement'
        (Path(prepared['staging_dir']) / 'prepared.json').write_text(json.dumps(forged), encoding='utf-8')
        changed = dict(self.inputs, requirements_identity='replacement')
        record, sources = self.record_and_sources(forged)
        with self.assertRaises(ValueError):
            compact.create_compact(forged, record, render.render(record), changed, sources)
        self.assertFalse(Path(prepared['run_dir']).exists())

    def test_compact_brief_and_full_deliver_with_safe_command_fallback(self):
        repo = self.root / 'repo'
        repo.mkdir()
        subprocess.run(['git', 'init', '-q', str(repo)], check=True, capture_output=True)
        prepared = self.prepare(repo_identity=repository_identity(repo), archive_root=self.root / 'archive')
        record, sources = self.record_and_sources(prepared)
        record['coverage']['evidence'][0]['detail'] = 'password=hunter2'
        result = compact.create_compact(prepared, record, render.render(record), self.inputs, sources)
        for mode in ('brief', 'full'):
            with self.subTest(mode=mode):
                delivered = delivery.deliver(result['run_dir'], mode, repo, repo / ('out-' + mode))
                folder = Path(delivered)
                receipt = json.loads((folder / '.ccr-delivery.json').read_text(encoding='utf-8'))
                self.assertEqual(receipt['artifact_mode'], 'compact')
                report = (folder / ('resumen.md' if mode == 'brief' else 'informe.md')).read_text(encoding='utf-8')
                self.assertNotIn('hunter2', report)
                self.assertNotIn('python -V', report)

    def test_cli_prepares_compact_from_explicit_pinned_inputs(self):
        repo = self.root / 'repo'
        repo.mkdir()
        subprocess.run(['git', 'init', '-q', str(repo)], check=True, capture_output=True)
        for name, value in (('scope.json', self.scope), ('inputs.json', self.inputs), ('selection.json', self.selection),
                            ('profile.json', self.profile_input)):
            (self.root / name).write_text(json.dumps(value), encoding='utf-8')
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = artifacts_cli.main(['prepare-compact', '--repo', str(repo),
                '--scope-file', str(self.root / 'scope.json'), '--current-inputs', str(self.root / 'inputs.json'),
                '--selection-input', str(self.root / 'selection.json'), '--operation-id', 'case-1',
                '--profile-input', str(self.root / 'profile.json'), '--skill-version', '3.5.0', '--harness', 'codex',
                '--output-root', str(self.root / 'archive')])
        self.assertEqual(result, 0)
        prepared = json.loads(output.getvalue())
        self.assertEqual(prepared['request']['selection']['mode'], 'compact')
        record, sources = self.record_and_sources(prepared)
        record_path = self.root / 'record.json'
        record_path.write_text(json.dumps(record), encoding='utf-8')
        source_paths = {}
        for name, data in sources.items():
            path = self.root / name.replace('/', '-')
            path.write_bytes(data)
            source_paths[name] = str(path)
        catalog = self.root / 'sources.json'
        catalog.write_text(json.dumps(source_paths), encoding='utf-8')
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = artifacts_cli.main(['retain-compact',
                '--prepared-input', str(Path(prepared['staging_dir']) / 'prepared.json'),
                '--input', str(record_path), '--current-inputs', str(self.root / 'inputs.json'),
                '--sources-input', str(catalog)])
        self.assertEqual(result, 0)
        stored = compact.read_compact(json.loads(output.getvalue())['run_dir'])['record']
        self.assertEqual(stored.pop('compact_identity'), compact._compact_identity(
            prepared['request'], prepared['logical_scope'], prepared['created_at']))
        self.assertEqual(stored, record)
