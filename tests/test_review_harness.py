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

    def test_declared_ids_normalize_case_and_outer_whitespace_without_hiding_conflicts(self):
        source = {'kind': 'user', 'reference': 'Declared session identity'}
        for requested in ('Codex-CLI', ' codex-cli ', '\tCODEX-CLI\n'):
            with self.subTest(requested=requested):
                explicit = self.resolve('Codex', harness_id=requested, source=source)
                self.assertEqual(explicit['harness_id'], 'codex-cli')
                self.assertEqual(explicit['harness_source'], source)
                self.assertEqual(explicit['harness_diagnostics'], [])
                configured = self.resolve('Codex', environ={'CCR_HARNESS_ID': requested})
                self.assertEqual(configured['harness_id'], 'codex-cli')
                self.assertEqual(configured['harness_source']['kind'], 'environment')
                conflict = self.resolve('Codex Desktop', environ={'CCR_HARNESS_ID': requested})
                self.assertIsNone(conflict['harness_id'])
                self.assertEqual(conflict['harness_diagnostics'], ['identity_conflict'])
        self.assertEqual(self.resolve('Codex Desktop', harness_id=' CODEX-DESKTOP ')['harness_id'], 'codex-desktop')
        self.assertEqual(self.resolve('Codex', harness_id=' CODEX-CLI ',
                         environ={'CCR_HARNESS_ID': 'codex-desktop'})['harness_id'], 'codex-cli')
        unknown = self.resolve('Codex Desktop', harness_id=' NOT-IN-CATALOG ')
        self.assertIsNone(unknown['harness_id'])
        self.assertEqual(unknown['harness_diagnostics'], ['unknown_requested_id'])

    def test_blank_session_configuration_is_unset_but_explicit_blank_id_is_invalid(self):
        for configured in ('', ' ', '\t\n', '\r\n  '):
            with self.subTest(configured=configured):
                environment = {'CCR_HARNESS_ID': configured}
                value = self.resolve('Codex Desktop', environ=environment)
                self.assertEqual(value['harness_id'], 'codex-desktop')
                self.assertEqual(value['harness_source'], {'kind': 'alias', 'reference': 'Codex Desktop'})
                self.assertEqual(value['harness_diagnostics'], [])
                unknown = self.resolve('custom launcher', environ=environment)
                self.assertIsNone(unknown['harness_id'])
                self.assertEqual(unknown['harness_diagnostics'], ['unknown_harness'])
                explicit = self.resolve('Codex', harness_id='codex-cli', environ=environment)
                self.assertEqual(explicit['harness_id'], 'codex-cli')
                self.assertEqual(explicit['harness_source']['kind'], 'argument')
                with self.assertRaisesRegex(ValueError, 'nonempty explicit harness ID'):
                    self.resolve('Codex Desktop', harness_id=configured, environ=environment)

    def test_catalog_covers_additional_harnesses_without_guessing_generic_interfaces(self):
        expected = [('Cursor', 'cursor'), ('Cursor CLI', 'cursor-cli'), ('Cursor IDE', 'cursor-ide'),
                    ('Cursor Web', 'cursor-web'), ('Windsurf', 'windsurf'), ('Windsurf Editor', 'windsurf-editor'),
                    ('Windsurf VS Code', 'windsurf-vscode'), ('Gemini CLI', 'gemini-cli'),
                    ('OpenCode', 'opencode'), ('OpenCode Desktop', 'opencode-desktop'),
                    ('OpenCode TUI', 'opencode-tui'), ('OpenCode CLI', 'opencode-cli'),
                    ('OpenCode Web', 'opencode-web'), ('OpenCode IDE', 'opencode-ide'),
                    ('Cline', 'cline'), ('Cline CLI', 'cline-cli'), ('Cline VS Code', 'cline-vscode'),
                    ('Roo Code', 'roo-code'), ('Roo Code VS Code', 'roo-code-vscode'),
                    ('Continue', 'continue'), ('Continue CLI', 'continue-cli'),
                    ('Continue VS Code', 'continue-vscode'), ('Continue JetBrains', 'continue-jetbrains'),
                    ('Aider', 'aider'), ('Aider CLI', 'aider-cli'),
                    ('Google Antigravity', 'antigravity'), ('Antigravity IDE', 'antigravity-ide'),
                    ('GitHub Copilot', 'copilot'), ('Copilot VS Code', 'copilot-vscode'),
                    ('Copilot JetBrains', 'copilot-jetbrains'), ('Copilot Visual Studio', 'copilot-visual-studio'),
                    ('Augment Code', 'augment-code'), ('Auggie', 'augment-code-cli'),
                    ('Augment Code VS Code', 'augment-code-vscode'),
                    ('OpenHands', 'openhands'), ('OpenHands Web', 'openhands-web'),
                    ('Devin', 'devin'), ('Devin Desktop', 'devin-desktop')]
        for name, identifier in expected:
            with self.subTest(name=name):
                self.assertEqual(self.resolve(name)['harness_id'], identifier)
        for name, identifier in expected:
            if identifier in {'cursor', 'windsurf', 'opencode', 'cline', 'roo-code', 'continue', 'aider',
                              'antigravity', 'copilot', 'augment-code', 'openhands', 'devin'}:
                entry = next(item for item in harness.load_catalog()['entries'] if item['id'] == identifier)
                self.assertIsNone(entry['interface'])
        self.assertEqual(self.resolve('Cursor', harness_id='cursor-cli')['harness_id'], 'cursor-cli')
        self.assertEqual(self.resolve('Copilot VS Code', harness_id='copilot-jetbrains')['harness_diagnostics'], ['identity_conflict'])
        for ambiguous in ('VS Code', 'JetBrains', 'Claude', 'Gemini', 'GPT', 'Sonnet', 'Python'):
            self.assertIsNone(self.resolve(ambiguous)['harness_id'])

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
        from recovery_fixtures import legacy_prepare
        raw = ' Claude Code '
        with patch.dict(os.environ, {'CCR_HARNESS_ID': 'claude-code-cli'}):
            run = legacy_prepare(fixtures.artifacts, self.repo, self.scope, skill_version='2.10.0', harness=raw,
                        output_root=self.output, harness_id='claude-code-desktop',
                        harness_source={'kind': 'user', 'reference': 'session declaration'})
        initial = self.read(run / 'cierre.json')
        self.assertEqual(initial['schema_version'], 8)
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
            with self.assertRaisesRegex(ValueError, 'unsupported_layout'):
                fixtures.artifacts.validate(run)
            self.assertEqual(before, {p.name: p.read_bytes() for p in run.iterdir() if p.is_file()})
            self.assertFalse(set(keys) & set(self.read(run / 'cierre.json')))

    def test_cli_explicit_source_and_conflicts_are_archived(self):
        from recovery_fixtures import selection_input
        source = self.write('source.json', {'kind': 'user', 'reference': 'Desktop session declaration'})
        profile = self.write('profile.json', selection_input())
        args = [sys.executable, '-B', '-X', 'utf8', str(SCRIPTS / 'review_artifacts.py'), 'prepare',
                '--repo', str(self.repo), '--scope-file', str(self.scope), '--skill-version', '2.10.0',
                '--harness', 'Claude Code', '--output-root', str(self.output), '--profile-input', str(profile),
                '--harness-id', 'claude-code-desktop',
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

    def test_cli_unencodable_source_is_rejected_before_creating_archive_directories(self):
        from recovery_fixtures import selection_input
        profile = self.write('profile.json', selection_input())
        args = [sys.executable, '-B', '-X', 'utf8', str(SCRIPTS / 'review_artifacts.py'), 'prepare',
                '--repo', str(self.repo), '--scope-file', str(self.scope), '--skill-version', '2.10.0',
                '--harness', 'Codex', '--harness-id', 'codex-desktop', '--output-root', str(self.output),
                '--profile-input', str(profile)]
        for reference in ('\ud800', '\udfff'):
            with self.subTest(reference=ascii(reference)):
                source = self.write('source.json', {'kind': 'user', 'reference': reference})
                result = subprocess.run(args + ['--harness-source-file', str(source)], capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('invalid harness source', result.stderr)
                self.assertFalse(self.output.exists(), 'invalid source must not create archive directories')
        source = self.write('source.json', {'kind': 'user', 'reference': 'Sesión declarada — escritorio 🚀'})
        result = subprocess.run(args + ['--harness-source-file', str(source)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        value = self.read(Path(json.loads(result.stdout)['run_dir']) / 'cierre.json')
        self.assertEqual(value['harness_source']['reference'], 'Sesión declarada — escritorio 🚀')

    def test_cli_null_source_is_rejected_before_writing_with_or_without_explicit_id(self):
        from recovery_fixtures import selection_input
        source = self.write('null-source.json', None)
        profile = self.write('profile.json', selection_input())
        args = [sys.executable, '-B', '-X', 'utf8', str(SCRIPTS / 'review_artifacts.py'), 'prepare',
                '--repo', str(self.repo), '--scope-file', str(self.scope), '--skill-version', '2.10.0',
                '--harness', 'Codex', '--output-root', str(self.output), '--harness-source-file', str(source),
                '--profile-input', str(profile)]
        for extra in ([], ['--harness-id', 'codex-desktop']):
            result = subprocess.run(args + extra, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('harness source', result.stderr)
            self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main()
