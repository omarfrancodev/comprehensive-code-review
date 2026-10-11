"""Canonical harness identity is declared once, never inferred from model/provider."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import test_review_artifacts as fixtures

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
spec = importlib.util.spec_from_file_location('review_harness', SCRIPTS / 'review_harness.py') if (SCRIPTS / 'review_harness.py').exists() else None
harness = importlib.util.module_from_spec(spec) if spec else None
if spec:
    spec.loader.exec_module(harness)


class HarnessTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(harness, 'canonical harness resolver is missing')

    def resolve(self, name, **kwargs):
        return harness.resolve(name, environ=kwargs.pop('environ', {}), **kwargs)

    def test_exact_names_and_aliases_keep_interfaces_distinct(self):
        for name, identifier in [('Claude Code Desktop', 'claude-code-desktop'),
                                 (' CLAUDE-CODE-DESKTOP ', 'claude-code-desktop'),
                                 ('Claude Code', 'claude-code'), ('claude-code-cli', 'claude-code-cli'),
                                 ('Codex desktop/native agents + PowerShell', 'codex-desktop'),
                                 ('codex', 'codex'), ('Kiro IDE', 'kiro-ide'),
                                 ('copilot-cli', 'copilot-cli'), ('kirocrew-dashboard', 'kirocrew-dashboard')]:
            with self.subTest(name=name):
                value = self.resolve(name)
                self.assertEqual(value['harness_id'], identifier)
                self.assertEqual(value['harness_catalog_version'], 1)
                self.assertEqual(value['harness_diagnostics'], [])
                self.assertEqual(value['harness_source'], {'kind': 'alias', 'reference': name})

    def test_explicit_identity_and_session_configuration_precise_generic_names(self):
        source = {'kind': 'user', 'reference': 'User declared this local session is Desktop'}
        value = self.resolve('claude-code', harness_id='claude-code-desktop', source=source)
        self.assertEqual(value['harness_id'], 'claude-code-desktop')
        self.assertEqual(value['harness_source'], source)
        value = self.resolve('Claude Code', environ={'CCR_HARNESS_ID': 'claude-code-desktop'})
        self.assertEqual(value['harness_id'], 'claude-code-desktop')
        self.assertEqual(value['harness_source'], {'kind': 'environment', 'reference': 'CCR_HARNESS_ID'})
        value = self.resolve('Claude Code', harness_id='claude-code-cli', environ={'CCR_HARNESS_ID': 'claude-code-desktop'})
        self.assertEqual(value['harness_id'], 'claude-code-cli')
        self.assertEqual(value['harness_source']['kind'], 'argument')
        self.assertEqual(self.resolve('Claude Code Desktop', harness_id='claude-code')['harness_id'], 'claude-code-desktop')

    def test_unknowns_and_conflicts_do_not_invent_an_interface(self):
        for name, kwargs, code in [('custom environment', {}, 'unknown_harness'),
                                   ('Claude Code', {'harness_id': 'not-in-catalog'}, 'unknown_requested_id'),
                                   ('Claude Code Desktop', {'harness_id': 'claude-code-cli'}, 'identity_conflict'),
                                   ('Codex', {'harness_id': 'claude-code'}, 'identity_conflict')]:
            with self.subTest(name=name, kwargs=kwargs):
                value = self.resolve(name, **kwargs)
                self.assertIsNone(value['harness_id'])
                self.assertEqual(value['harness_diagnostics'], [code])
        self.assertEqual(self.resolve('private launcher', harness_id='claude-code-desktop')['harness_id'], 'claude-code-desktop')

    def test_malformed_sources_and_ambiguous_catalog_fail_before_resolution(self):
        for source in ({}, {'kind': 'user', 'reference': ''}, {'kind': 'guess', 'reference': 'model'},
                       {'kind': 'user', 'reference': 'session', 'extra': True}, {'kind': 'platform', 'reference': []}):
            with self.subTest(source=source), self.assertRaises(ValueError):
                self.resolve('claude-code', harness_id='claude-code-desktop', source=source)
        with self.assertRaises(ValueError):
            self.resolve('claude-code', source={'kind': 'user', 'reference': 'session'})
        catalog = harness.load_catalog()
        catalog['entries'][1]['aliases'].append(catalog['entries'][0]['name'])
        with self.assertRaisesRegex(ValueError, 'duplicate|ambiguous'):
            harness.validate_catalog(catalog)
        for field, bad in [('id', 'UPPER'), ('family', []), ('interface', {}), ('aliases', 'not-list')]:
            altered = copy.deepcopy(harness.load_catalog())
            altered['entries'][0][field] = bad
            with self.subTest(field=field), self.assertRaises(ValueError):
                harness.validate_catalog(altered)

    def test_stored_identity_is_structural_and_does_not_reopen_catalog(self):
        value = self.resolve('Claude Code Desktop')
        value.update(harness_id='future-harness', harness_catalog_version=99)
        with patch.object(harness, 'load_catalog', side_effect=AssertionError('must not re-resolve')):
            harness.validate_identity(value)
        for key, bad in [('harness_id', []), ('harness_catalog_version', True),
                         ('harness_source', {}), ('harness_diagnostics', 'not-array')]:
            altered = dict(value, **{key: bad})
            with self.subTest(key=key), self.assertRaises(ValueError):
                harness.validate_identity(altered)


class ArchiveHarnessTests(unittest.TestCase):
    setUp = fixtures.ArchiveTests.setUp
    git = fixtures.ArchiveTests.git
    write = fixtures.ArchiveTests.write
    prepare = fixtures.ArchiveTests.prepare
    read = fixtures.ArchiveTests.read
    retain = fixtures.ArchiveTests.retain
    close = fixtures.ArchiveTests.close

    def test_identity_persists_through_processing_retention_and_close(self):
        raw = ' Claude Code '
        with patch.dict(os.environ, {'CCR_HARNESS_ID': 'claude-code-cli'}):
            run = Path(fixtures.artifacts.prepare(self.repo, self.scope, '2.10.0', raw, output_root=self.output,
                        harness_id='claude-code-desktop', harness_source={'kind': 'user', 'reference': 'session declaration'}))
        initial = self.read(run / 'cierre.json')
        self.assertEqual(initial['schema_version'], 6)
        self.assertEqual(initial['harness'], raw)
        self.assertEqual(initial['harness_id'], 'claude-code-desktop')
        with patch.dict(os.environ, {'CCR_HARNESS_ID': 'codex-cli'}):
            fixtures.artifacts.record_event(run, self.write('event.json', dict(kind='discovery', status='started', summary='Inspected flow')))
            self.assertEqual(fixtures.artifacts.validate(run)['state'], 'processing')
            self.retain(run)
            self.close(run)
        final = self.read(run / 'cierre.json')
        for key in ('harness', 'harness_id', 'harness_catalog_version', 'harness_source', 'harness_diagnostics'):
            self.assertEqual(initial[key], final[key])
        self.assertEqual(fixtures.artifacts.validate(run, require_retained=True)['state'], 'complete')
        manifest = dict(final, harness_id='codex-cli')
        (run / 'cierre.json').write_text(json.dumps(manifest), encoding='utf-8')
        with self.assertRaises(ValueError):
            fixtures.artifacts.validate(run)

    def test_legacy_archive_has_no_synthetic_identity_and_stays_byte_identical(self):
        keys = ('harness_id', 'harness_catalog_version', 'harness_source', 'harness_diagnostics')
        for version in (1, 2, 3, 4, 5):
            run = self.prepare()
            manifest = self.read(run / 'cierre.json')
            marker = self.read(run / fixtures.artifacts.MARKER)
            manifest['schema_version'] = version
            for key in keys:
                manifest.pop(key, None)
            if version < 4:
                manifest.pop('trace')
                manifest['hashes'].pop('trazabilidad.jsonl')
                (run / 'trazabilidad.jsonl').unlink()
            fixtures.artifacts._save_manifest(run, manifest, marker)
            before = {p.name: p.read_bytes() for p in run.iterdir() if p.is_file()}
            self.assertEqual(fixtures.artifacts.validate(run)['schema_version'], version)
            self.assertEqual(before, {p.name: p.read_bytes() for p in run.iterdir() if p.is_file()})
            self.assertFalse(set(keys) & set(self.read(run / 'cierre.json')))

    def test_cli_explicit_source_and_conflicts_are_archived(self):
        source = self.write('source.json', {'kind': 'user', 'reference': 'Desktop session declaration'})
        args = [sys.executable, '-B', '-X', 'utf8', str(SCRIPTS / 'review_artifacts.py'), 'prepare',
                '--repo', str(self.repo), '--scope-file', str(self.scope), '--skill-version', '2.10.0',
                '--harness', 'Claude Code', '--output-root', str(self.output), '--harness-id', 'claude-code-desktop',
                '--harness-source-file', str(source)]
        result = subprocess.run(args, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        run = Path(json.loads(result.stdout)['run_dir'])
        self.assertEqual(self.read(run / 'cierre.json')['harness_id'], 'claude-code-desktop')
        args[args.index('--harness') + 1] = 'Codex Desktop'
        result = subprocess.run(args, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        value = self.read(Path(json.loads(result.stdout)['run_dir']) / 'cierre.json')
        self.assertIsNone(value['harness_id'])
        self.assertEqual(value['harness_diagnostics'], ['identity_conflict'])
        before = sorted(str(p) for p in self.output.rglob('*'))
        source.write_text('{}', encoding='utf-8')
        result = subprocess.run(args, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(before, sorted(str(p) for p in self.output.rglob('*')))


if __name__ == '__main__':
    unittest.main()
