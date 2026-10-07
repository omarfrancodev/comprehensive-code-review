"""Archive path gates reject native layouts even with consistent ownership records."""
import json
from pathlib import Path
import subprocess
import sys
import unittest

import test_review_artifacts as archive_tests

artifacts = archive_tests.artifacts


class LayoutTests(unittest.TestCase):
    setUp = archive_tests.ArchiveTests.setUp
    git = archive_tests.ArchiveTests.git
    write = archive_tests.ArchiveTests.write
    prepare = archive_tests.ArchiveTests.prepare
    read = archive_tests.ArchiveTests.read
    retain = archive_tests.ArchiveTests.retain
    close = archive_tests.ArchiveTests.close

    def relocate(self, run, target):
        manifest = self.read(run / 'cierre.json')
        marker = self.read(run / artifacts.MARKER)
        target.parent.mkdir(parents=True, exist_ok=True)
        run.rename(target)
        marker['run_dir'] = str(target)
        artifacts._save_manifest(target, manifest, marker)
        return target

    def test_retain_rejects_missing_repository_id_before_writing_report(self):
        run = self.prepare()
        target = self.output / 'repo' / run.parent.name / run.name
        moved = self.relocate(run, target)
        before = (moved / 'cierre.json').read_bytes()
        with self.assertRaisesRegex(ValueError, 'layout'):
            self.retain(moved)
        self.assertEqual((moved / 'cierre.json').read_bytes(), before)
        self.assertFalse((moved / 'review.json').exists())

    def test_retain_rejects_renamed_scope_with_updated_marker(self):
        run = self.prepare()
        moved = self.relocate(run, run.parent.parent / 'mr-42' / run.name)
        with self.assertRaisesRegex(ValueError, 'layout'):
            self.retain(moved)

    def test_close_rejects_renamed_run_without_rewriting_retained_files(self):
        run = self.prepare()
        self.retain(run)
        moved = self.relocate(run, run.parent / '20261007-ccr-manual')
        before = {path.name: path.read_bytes() for path in moved.iterdir() if path.is_file()}
        with self.assertRaisesRegex(ValueError, 'layout'):
            self.close(moved)
        self.assertEqual(before, {path.name: path.read_bytes() for path in moved.iterdir() if path.is_file()})

    def test_repository_label_and_unique_run_id_are_bound_to_stored_identity(self):
        for component in ('repository', 'run_id'):
            with self.subTest(component=component):
                run = self.prepare()
                if component == 'repository':
                    target = self.output / ('other-' + run.parent.parent.name.rsplit('-', 1)[-1]) / run.parent.name / run.name
                else:
                    replacement = '0' * 20 if not run.name.endswith('0' * 20) else '1' * 20
                    target = run.parent / (run.name.split('-', 1)[0] + '-' + replacement)
                moved = self.relocate(run, target)
                with self.assertRaisesRegex(ValueError, 'layout'):
                    self.retain(moved)

    def test_layout_gate_rejects_extra_directory_below_explicit_root(self):
        run = self.prepare(output_root=self.repo / 'explicit-root')
        relative = run.relative_to(self.repo / 'explicit-root')
        moved = self.relocate(run, self.repo / 'explicit-root' / 'extra' / relative)
        with self.assertRaisesRegex(ValueError, 'layout'):
            self.retain(moved)

    def test_cli_validation_is_read_only_and_retention_is_an_explicit_gate(self):
        run = self.prepare()
        def invoke(*args):
            return subprocess.run([sys.executable, '-B', str(archive_tests.SCRIPTS / 'review_artifacts.py'),
                                   'validate', '--run-dir', str(run), *args],
                                  capture_output=True, text=True, encoding='utf-8')
        before = {path.name: path.read_bytes() for path in run.iterdir() if path.is_file()}
        result = invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['state'], 'prepared')
        self.assertEqual(before, {path.name: path.read_bytes() for path in run.iterdir() if path.is_file()})
        result = invoke('--require-retained')
        self.assertEqual(result.returncode, 1)
        self.assertIn('retained', json.loads(result.stderr)['error'])
        self.retain(run)
        result = invoke('--require-retained')
        self.assertEqual(result.returncode, 0, result.stderr)
        (run / 'informe.md').write_text('modified report', encoding='utf-8')
        result = invoke('--require-retained')
        self.assertEqual(result.returncode, 1)
        self.assertIn('modified', json.loads(result.stderr)['error'])

    def test_previous_run_with_invalid_layout_is_rejected(self):
        run = self.prepare()
        moved = self.relocate(run, self.output / 'repo' / run.parent.name / run.name)
        with self.assertRaisesRegex(ValueError, 'layout'):
            self.prepare(previous_run=moved)

    def test_validate_accepts_legacy_schemas_without_migration(self):
        for schema in (1, 2):
            with self.subTest(schema=schema):
                run = self.prepare()
                self.retain(run)
                _, manifest, marker = artifacts._load_run(run)
                manifest['schema_version'] = schema
                manifest.pop('repository_identity', None)
                manifest.pop('run_id', None)
                artifacts._save_manifest(run, manifest, marker)
                before = (run / 'cierre.json').read_bytes()
                result = artifacts.validate(run, require_retained=True)
                self.assertEqual(result['schema_version'], schema)
                self.assertEqual((run / 'cierre.json').read_bytes(), before)
                self.close(run)

    def test_validation_does_not_require_original_checkout_to_survive(self):
        run = self.prepare()
        self.retain(run)
        self.repo.rename(self.root / 'relocated-repo')
        result = artifacts.validate(run, require_retained=True)
        self.assertEqual(result['run_dir'], str(run))
        self.close(run)

    def test_schema3_rejects_repository_identity_with_wrong_key(self):
        run = self.prepare()
        _, manifest, marker = artifacts._load_run(run)
        manifest['repository_identity'] = 'origin:example.test/other/repo'
        artifacts._save_manifest(run, manifest, marker)
        with self.assertRaisesRegex(ValueError, 'layout'):
            self.retain(run)

    def test_register_adds_planned_resources_before_use_without_final_record(self):
        run = self.prepare()
        session = self.root / 'planned-session'
        self.assertFalse(session.exists())
        result = subprocess.run([sys.executable, '-B', str(archive_tests.SCRIPTS / 'review_artifacts.py'),
                                 'register', '--run-dir', str(run), '--temporary-path', str(session)],
                                capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['temporary_paths'], [str(session)])
        self.assertFalse(session.exists())
        self.assertFalse((run / 'review.json').exists())
        session.mkdir()
        artifacts.register(run, [session])
        self.retain(run)
        before = (run / 'cierre.json').read_bytes()
        with self.assertRaises(ValueError):
            artifacts.register(run, [self.root / 'late-session'])
        self.assertEqual((run / 'cierre.json').read_bytes(), before)

    def test_register_rejects_user_checkout_and_archive_without_changes(self):
        run = self.prepare()
        before = (run / 'cierre.json').read_bytes()
        for path in (self.repo, self.output, run):
            with self.subTest(path=path), self.assertRaises(ValueError):
                artifacts.register(run, [path])
        self.assertEqual((run / 'cierre.json').read_bytes(), before)

    def test_retention_gate_rejects_final_record_from_other_scope_even_with_matching_hash(self):
        run = self.prepare()
        self.retain(run)
        _, manifest, marker = artifacts._load_run(run)
        value = self.read(run / 'review.json')
        value['scope']['head'] = 'other-revision'
        data = artifacts._json_bytes(value)
        (run / 'review.json').write_bytes(data)
        manifest['hashes']['review.json'] = artifacts._digest(data)
        artifacts._save_manifest(run, manifest, marker)
        with self.assertRaisesRegex(ValueError, 'scope'):
            artifacts.validate(run, require_retained=True)

    def test_register_does_not_clobber_manifest_with_modified_selected_evidence(self):
        run = self.prepare()
        self.retain(run)
        (run / 'informe.md').write_text('user edit', encoding='utf-8')
        before = (run / 'cierre.json').read_bytes()
        with self.assertRaises(ValueError):
            artifacts.register(run, [self.root / 'resource'])
        self.assertEqual((run / 'cierre.json').read_bytes(), before)

    def test_generated_truncated_repository_labels_remain_valid_for_all_schemas(self):
        self.git('remote', 'add', 'origin', 'https://example.test/team/' + 'a' * 35 + '-service.git')
        for schema in (1, 2, 3):
            with self.subTest(schema=schema):
                run = self.prepare()
                self.retain(run)
                _, manifest, marker = artifacts._load_run(run)
                manifest['schema_version'] = schema
                if schema != 3:
                    manifest.pop('repository_identity')
                    manifest.pop('run_id')
                artifacts._save_manifest(run, manifest, marker)
                self.assertEqual(artifacts.validate(run, require_retained=True)['schema_version'], schema)
                self.close(run)

    def test_inline_close_observation_needs_no_file_after_session_removal(self):
        session = self.root / 'owned-session'
        session.mkdir()
        run = self.prepare(temporary_paths=[session])
        self.retain(run)
        session.rmdir()
        result = subprocess.run([sys.executable, '-B', str(archive_tests.SCRIPTS / 'review_artifacts.py'),
                                 'close', '--run-dir', str(run), '--cleanup', 'complete'],
                                capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['state'], 'complete')
        self.assertFalse((self.root / 'cleanup.json').exists())

    def test_inline_close_pending_keeps_exact_registered_residuals(self):
        session = self.root / 'owned-session'
        session.mkdir()
        run = self.prepare(temporary_paths=[session])
        self.retain(run)
        result = subprocess.run([sys.executable, '-B', str(archive_tests.SCRIPTS / 'review_artifacts.py'),
                                 'close', '--run-dir', str(run), '--cleanup', 'pending', '--residual', str(session)],
                                capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['residuals'], [str(session)])
        self.assertEqual(json.loads(result.stdout)['state'], 'closing')


if __name__ == '__main__':
    unittest.main()
