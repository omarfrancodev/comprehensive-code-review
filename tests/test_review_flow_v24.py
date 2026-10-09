"""Approved flow regressions: optional accounting and canonical presentation."""
import unittest

import test_review_artifacts as archive_tests
from test_review_presentation import current_record
from test_review_contract import contract, finding

artifacts = archive_tests.artifacts


def presented(kind='review'):
    value = current_record()
    value['schema_version'] = 4
    value['presentation'] = {'kind': kind, 'subject': 'Configuración documental'}
    return value


class PresentationFlowTests(unittest.TestCase):
    def test_explicit_kind_and_subject_are_shared_by_both_audiences(self):
        for kind, label in [('review', 'Code Review'), ('rereview', 'Re-review'),
                            ('complement', 'Complement Code Review')]:
            value = presented(kind)
            self.assertEqual(contract.validate(value), [])
            for audience in ('user', 'comment'):
                text = contract.render(value, audience)
                self.assertTrue(text.startswith('## ' + label + ' — Configuración documental\n\n'))
                self.assertIn('### Veredicto: **APROBABLE**', text)
                self.assertIn('Autores del cambio:', text)
                self.assertEqual('Matriz ABCDE' in text, audience == 'user')

    def test_findings_separate_priority_id_title_scenario_and_impact(self):
        value = presented()
        item = finding(blocking=True)
        value['findings'] = [item]
        value['verdict'] = 'not_approvable'
        for audience in ('user', 'comment'):
            text = contract.render(value, audience)
            self.assertIn('### ' + contract.PRIORITIES[item['priority']] + ' — ' + item['id'] + '\n\n#### 1. ', text)
            self.assertIn('- **Escenario:** ', text)
            self.assertIn('- **Impacto:** ', text)
            self.assertNotIn('Escenario e impacto', text)

    def test_presentation_identity_rejects_unknown_fields_kinds_or_multiline_subject(self):
        for presentation in ({'kind': 'other', 'subject': 'x'}, {'kind': 'review', 'subject': ''},
                             {'kind': 'review', 'subject': 'a\nb'}, {'kind': 'review', 'subject': 'x', 'extra': True}):
            value = presented()
            value['presentation'] = presentation
            self.assertTrue(any('presentation' in error for error in contract.validate(value)))


class ArchiveFlowTests(unittest.TestCase):
    setUp = archive_tests.ArchiveTests.setUp
    git = archive_tests.ArchiveTests.git
    write = archive_tests.ArchiveTests.write
    prepare = archive_tests.ArchiveTests.prepare
    read = archive_tests.ArchiveTests.read
    close = archive_tests.ArchiveTests.close
    def test_default_flow_has_no_measurements_even_when_cleanup_rewrites_report(self):
        session = self.root / 'owned'
        session.mkdir()
        run = self.prepare(temporary_paths=[session])
        self.assertFalse((run / 'measurements.json').exists())
        artifacts.retain(run, self.final)
        session.rmdir()
        self.close(run, 'complete')
        manifest = self.read(run / 'cierre.json')
        self.assertEqual(manifest['schema_version'], 5)
        self.assertEqual(set(manifest['hashes']), {'review.json', 'informe.md', 'trazabilidad.jsonl'})
        self.assertFalse((run / 'measurements.json').exists())

    def test_explicit_unknown_measurement_is_optional_and_integrity_protected(self):
        run = self.prepare()
        artifacts.retain(run, self.final, unavailable_reason='Explicit cost evaluation; no counters')
        self.assertEqual(self.read(run / 'measurements.json')['status'], 'unavailable')
        (run / 'measurements.json').write_text('{}', encoding='utf-8')
        with self.assertRaises(ValueError):
            self.close(run)

    def test_legacy_schema1_archive_keeps_its_measurements_on_cleanup(self):
        session = self.root / 'legacy-owned'
        session.mkdir()
        run = self.prepare(temporary_paths=[session])
        artifacts.retain(run, self.final, unavailable_reason='Legacy unavailable usage')
        _, manifest, marker = artifacts._load_run(run)
        manifest['schema_version'] = 1
        artifacts._save_manifest(run, manifest, marker)
        before = (run / 'measurements.json').read_bytes()
        session.rmdir()
        self.close(run, 'complete')
        self.assertEqual((run / 'measurements.json').read_bytes(), before)
        self.assertEqual(self.read(run / 'cierre.json')['schema_version'], 1)

    def test_legacy_pending_retry_without_flags_preserves_optional_measurements(self):
        run = self.prepare()
        artifacts.retain(run, self.final, unavailable_reason='Legacy unavailable usage')
        _, manifest, marker = artifacts._load_run(run)
        manifest['schema_version'] = 1
        artifacts._save_manifest(run, manifest, marker)
        before = (run / 'measurements.json').read_bytes()
        artifacts.retain(run, self.final)
        self.assertEqual((run / 'measurements.json').read_bytes(), before)
        self.close(run)

    def test_presentation_survives_cleanup_and_renders_same_public_title(self):
        session = self.root / 'owned'
        session.mkdir()
        value = presented('complement')
        self.scope = self.write('scope.json', value['scope'])
        self.final = self.write('final.json', value)
        run = self.prepare(temporary_paths=[session])
        artifacts.retain(run, self.final)
        before = (run / 'informe.md').read_text(encoding='utf-8').splitlines()[0]
        session.rmdir()
        self.close(run, 'complete')
        saved = self.read(run / 'review.json')
        self.assertEqual(saved['presentation'], value['presentation'])
        self.assertEqual(contract.render(saved, 'comment').splitlines()[0], before)

    def test_context_executor_provenance_binds_real_worktree_and_head(self):
        session = self.repo / '.worktrees' / 'review-owned'
        workspace = session / 'validator'
        head = self.git('rev-parse', 'HEAD')
        value = archive_tests.record()
        value['scope']['head'] = head
        self.scope = self.write('scope.json', value['scope'])
        self.final = self.write('final.json', value)
        self.git('worktree', 'add', '--detach', str(workspace), head)
        self.addCleanup(lambda: self.git('worktree', 'remove', '--force', str(workspace)))
        run = self.prepare(temporary_paths=[session])
        executor = {'executor': 'validator', 'method': 'git-worktree', 'workspace': str(workspace),
                    'revision': head, 'snapshot': None, 'manifest': None,
                    'dependencies': 'shared', 'dependency_reason': 'Compatible read-only dependency tree'}
        context = self.write('context.json', {'executors': [executor], 'unrelated': 'omit'})
        artifacts.retain(run, self.final, context_input=context)
        self.assertEqual(self.read(run / 'cierre.json')['executors'], [executor])
        executor['revision'] = 'wrong-head'
        context = self.write('context.json', {'executors': [executor]})
        with self.assertRaises(ValueError):
            artifacts.retain(run, self.final, context_input=context)

    def test_local_review_can_record_an_unmodified_baseline_executor(self):
        base = self.git('rev-parse', 'HEAD')
        (self.repo / 'code.txt').write_text('new head', encoding='utf-8')
        self.git('add', 'code.txt')
        self.git('commit', '-m', 'next fixture')
        value = archive_tests.record()
        value['scope'].update(mode='working', head=self.git('rev-parse', 'HEAD'),
                              base=base, snapshot='selected-local-patch')
        self.scope = self.write('scope.json', value['scope'])
        self.final = self.write('final.json', value)
        session = self.repo / '.worktrees' / 'baseline-owned'
        workspace = session / 'baseline'
        self.git('worktree', 'add', '--detach', str(workspace), base)
        self.addCleanup(lambda: self.git('worktree', 'remove', '--force', str(workspace)))
        run = self.prepare(temporary_paths=[session])
        context = self.write('context.json', {'executors': [{'executor': 'baseline',
            'method': 'git-worktree', 'workspace': str(workspace), 'revision': base,
            'snapshot': None, 'manifest': None, 'dependencies': 'none',
            'dependency_reason': 'Static baseline fixture has no dependencies'}]})
        artifacts.retain(run, self.final, context_input=context)
        self.assertIsNone(self.read(run / 'cierre.json')['executors'][0]['snapshot'])


if __name__ == '__main__':
    unittest.main()
