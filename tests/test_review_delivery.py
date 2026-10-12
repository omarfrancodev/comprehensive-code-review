"""Explicit delivery projects retained reviews without changing the archive."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_review_artifacts import artifacts, record as legacy_record
from test_review_contract import finding
from test_review_traceability_contract import record6, check

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
spec = importlib.util.spec_from_file_location('review_delivery', SCRIPTS / 'review_delivery.py') if (SCRIPTS / 'review_delivery.py').exists() else None
delivery = importlib.util.module_from_spec(spec) if spec else None
if spec:
    spec.loader.exec_module(delivery)


class DeliveryTests(unittest.TestCase):
    def test_forward_slash_unc_snapshot_refuses_both_deliveries(self):
        for identity in ('//private-server/share/snapshot', 'snapshot //private-server/share/snapshot',
                         r'//private-server\share/snapshot'):
            with self.subTest(identity=identity):
                value = legacy_record()
                value['scope']['snapshot'] = identity
                self.assertEqual(artifacts.review_contract.validate(value), [])
                run = self.retained(value)
                before = self.snapshot(run)
                for mode in ('full', 'brief'):
                    output = self.root / mode
                    with self.assertRaises(ValueError) as caught:
                        delivery.deliver(run, mode, self.repo, output)
                    self.assertIn('scope.snapshot', str(caught.exception))
                    self.assertNotIn(identity, str(caught.exception))
                    self.assertFalse(output.exists())
                    self.assertEqual(before, self.snapshot(run))

    def test_structural_public_urls_and_relative_identities_remain_portable(self):
        for identity in ('https://example.test/reviews//snapshot', 'http://example.test/a//b',
                         'owner/repository', 'snapshots/review-123'):
            with self.subTest(identity=identity):
                value = legacy_record()
                value['scope']['snapshot'] = identity
                self.assertEqual(artifacts.review_contract.validate(value), [])
                projection = delivery._Projection(value, {'repository_path': str(self.repo),
                    'archive_root': str(self.archive)}, self.repo, 'a' * 64)
                portable = projection.value(value)
                self.assertEqual(artifacts.review_contract.validate(portable), [])
                self.assertEqual(portable['scope'], value['scope'])

    def test_embedded_private_identity_refuses_both_deliveries(self):
        for identity in ('snapshot /home/alice/private/state', r'snapshot C:\other\private\state',
                         r'snapshot \\other-server\private\state', 'snapshot file:///private/state'):
            with self.subTest(identity=identity):
                value = legacy_record()
                value['scope']['head'] = identity
                self.assertEqual(artifacts.review_contract.validate(value), [])
                run = self.retained(value)
                before = self.snapshot(run)
                for mode in ('full', 'brief'):
                    output = self.root / mode
                    with self.assertRaises(ValueError) as caught:
                        delivery.deliver(run, mode, self.repo, output)
                    self.assertIn('scope.head', str(caught.exception))
                    self.assertNotIn(identity, str(caught.exception))
                    self.assertFalse(output.exists())
                    self.assertEqual(before, self.snapshot(run))

    def test_description_identity_is_preserved_or_refused_as_structure(self):
        value = record6()
        identity = 'sha256:description-1'
        value['description']['identity'] = identity
        value['checks'] = [dict(check(), command=identity)]
        self.assertEqual(artifacts.review_contract.validate(value), [])
        projection = delivery._Projection(value, {'repository_path': str(self.repo),
            'archive_root': str(self.archive)}, self.repo, 'a' * 64)
        self.assertEqual(projection.value(value)['description']['identity'], identity)
        value['description']['identity'] = 'captured /private/description.md'
        with self.assertRaisesRegex(ValueError, 'description.identity'):
            projection.value(value)

    def test_projection_preserves_structure_when_commands_collide(self):
        for token in ('deep', 'passed', 'C001', 'head-456', 'F001'):
            with self.subTest(token=token):
                value = record6()
                value.update(profile='deep')
                value['checks'] = [dict(check(), command=token)]
                item = finding()
                item['id'] = 'F001'
                value['findings'] = [item]
                self.assertEqual(artifacts.review_contract.validate(value), [])
                projection = delivery._Projection(value, {'repository_path': str(self.repo),
                    'archive_root': str(self.archive)}, self.repo, 'a' * 64)
                portable = projection.value(value)
                self.assertEqual(artifacts.review_contract.validate(portable), [])
                for field in ('profile', 'scope'):
                    self.assertEqual(portable[field], value[field])
                for field in ('id', 'status', 'revision'):
                    self.assertEqual(portable['checks'][0][field], value['checks'][0][field])
                self.assertEqual(portable['findings'][0]['id'], 'F001')
                self.assertEqual(portable['checks'][0]['command'], '[comprobación registrada; comando omitido]')

    def test_private_structural_identity_refuses_delivery_without_writes(self):
        value = legacy_record()
        private = str(self.root / 'private' / 'snapshot')
        value['scope']['head'] = private
        self.assertEqual(artifacts.review_contract.validate(value), [])
        run = self.retained(value)
        before = self.snapshot(run)
        output = self.root / 'export'
        with self.assertRaises(ValueError) as caught:
            delivery.deliver(run, 'brief', self.repo, output)
        self.assertIn('scope.head', str(caught.exception))
        self.assertNotIn(private, str(caught.exception))
        self.assertFalse(output.exists())
        self.assertEqual(before, self.snapshot(run))

    def test_full_and_brief_share_typed_projection_and_lineage(self):
        value = record6()
        value['previous_reviews'] = [dict(review_id='CR-' + 'b' * 20,
            reference='archive/old/review.json', verified=True)]
        value['checks'] = [dict(check(), command='passed', reused=True,
            reuse_reason='Inputs unchanged', reference='archive/old/check.log')]
        value['rereview'] = [dict(id='F001', status='resolved', details='Fixed and verified',
            previous_review_id='CR-' + 'b' * 20, previous_reference='archive/old/review.json',
            previous_finding_id='F001', previous_title='Previous defect',
            previous_url='https://example.test/review#F001', check_ids=['C001'])]
        run = self.retained(value, closed=True)
        before = self.snapshot(run)
        for mode in ('full', 'brief'):
            target = Path(delivery.deliver(run, mode, self.repo, self.root / mode))
            self.assertIn('C001', (target / ('informe.md' if mode == 'full' else 'resumen.md')).read_text(encoding='utf-8'))
            self.assertEqual(artifacts.read_json(target / '.ccr-delivery.json')['source_schema_version'], 6)
            if mode == 'full':
                projected = artifacts.read_json(target / 'review.json')
                self.assertEqual(projected['rereview'][0]['previous_reference'], projected['previous_reviews'][0]['reference'])
                self.assertEqual(projected['rereview'][0]['previous_url'], value['rereview'][0]['previous_url'])
            self.assertEqual(before, self.snapshot(run))

    def test_brief_labels_bold_confirmed_checks_unresolved_and_historical_followup(self):
        value = record6()
        confirmed = finding()
        confirmed['id'] = 'F001'
        unresolved = copy.deepcopy(confirmed)
        unresolved.update(id='F002', status='unresolved', title='<script>unsafe</script> **claim**')
        value['findings'] = [confirmed, unresolved]
        value['checks'] = [check()]
        value['rereview'] = [dict(id='F-01', status='not_reevaluated', previous_title='Original', details='Outside scope')]
        text = delivery._brief(value)
        for label in ('- **F001** ·', '- **C001** ·', '- **F002**:', '- **F-01** ·'):
            self.assertIn(label, text)
        self.assertIn('&lt;script&gt;', text)
        self.assertNotIn('<script>', text)
        self.assertNotIn('**claim**', text)

    def setUp(self):
        self.assertIsNotNone(delivery, 'explicit delivery helper is missing')
        # TEMP/TMP are configured by the focused runner outside the installation.
        self.temp = tempfile.TemporaryDirectory(prefix='ccr-delivery-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        result = subprocess.run(['git', 'init', str(self.repo)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.archive = self.root / 'archive'

    def write(self, name, value):
        path = self.root / name
        path.write_text(json.dumps(value), encoding='utf-8')
        return path

    def retained(self, value=None, temporary=None, closed=False):
        value = copy.deepcopy(value or record6())
        scope = self.write('scope.json', value['scope'])
        run = Path(artifacts.prepare(self.repo, scope, '2.8.0', 'codex', output_root=self.archive,
                                    temporary_paths=temporary))
        if value['schema_version'] in (6, 7):
            value['review_id'] = 'CR-' + artifacts.read_json(run / 'cierre.json')['run_id']
        artifacts.retain(run, self.write('final.json', value))
        if closed:
            artifacts.close(run, self.write('cleanup.json', {'cleanup': 'not_needed', 'residuals': []}))
        return run

    def snapshot(self, directory):
        return {str(p.relative_to(directory)): p.read_bytes() for p in directory.rglob('*') if p.is_file()}

    def test_full_is_portable_canonical_and_source_is_immutable(self):
        value = record6()
        item = finding()
        item['id'] = 'F001'
        item['location'].update(path=str(self.repo / 'src' / 'api.py'), url='https://example.test/pr/12/files#L12')
        value['findings'] = [item]
        value['checks'] = [check()]
        value['checks'][0]['evidence'] += ' at /srv/private/result.log; evidence/result.log'
        value['checks'][0]['reference'] = 'evidence/result.log'
        run = self.retained(value, closed=True)
        before = self.snapshot(run)
        target = Path(delivery.deliver(run, 'full', self.repo))
        retained = artifacts.read_json(run / 'review.json')
        projected = artifacts.read_json(target / 'review.json')
        self.assertEqual(target, self.repo / 'docs' / 'ccr' / 'reviews' / run.parent.name / retained['review_id'])
        self.assertEqual(artifacts.review_contract.validate(projected), [])
        self.assertEqual(projected['findings'][0]['location']['path'], 'src/api.py')
        self.assertEqual(projected['findings'][0]['location']['url'], item['location']['url'])
        for field in ('id', 'scenario', 'impact', 'correction'):
            self.assertEqual(projected['findings'][0][field], item[field])
        self.assertEqual(projected['checks'][0]['status'], 'passed')
        content = '\n'.join(p.read_text(encoding='utf-8') for p in target.iterdir())
        self.assertIn('**Confirmados:** 🔴 P0: 0 · 🟠 P1: 0 · 🟡 P2: 1 · 🔵 P3: 0',
                      (target / 'informe.md').read_text(encoding='utf-8'))
        for private in ('SECRET', 'C:\\private', '/srv/private', 'evidence/result.log', str(run)):
            self.assertNotIn(private, content)
        self.assertIn('https://example.test/pr/12/files#L12', content)
        self.assertEqual(set(p.name for p in target.iterdir()), {'informe.md', 'review.json', '.ccr-delivery.json'})
        receipt = artifacts.read_json(target / '.ccr-delivery.json')
        self.assertEqual(receipt['source_hash'], hashlib.sha256(before['review.json']).hexdigest())
        for name, digest in receipt['hashes'].items():
            self.assertEqual(digest, hashlib.sha256((target / name).read_bytes()).hexdigest())
        self.assertEqual(before, self.snapshot(run))

    def test_brief_keeps_decisions_findings_checks_and_uncertainties(self):
        value = record6()
        item = finding()
        item['id'] = 'F001'
        value['findings'] = [item]
        value['checks'] = [check()]
        value['coverage']['limitations'] = [{'detail': 'Integración externa sin cubrir', 'material': False}]
        run = self.retained(value)
        target = Path(delivery.deliver(run, 'brief', self.repo))
        summary = (target / 'resumen.md').read_text(encoding='utf-8')
        for text in (item['id'], item['scenario'], item['impact'], item['correction'], 'C001', 'base-123', 'head-456',
                     'Integración externa sin cubrir', value['verdict_reason']):
            self.assertIn(text, summary)
        self.assertNotIn('SECRET', summary)
        self.assertEqual(set(p.name for p in target.iterdir()), {'resumen.md', '.ccr-delivery.json'})

    def test_no_delivery_and_missing_cli_flag_write_nothing(self):
        run = self.retained()
        before = self.snapshot(self.root)
        with self.assertRaises(ValueError):
            delivery.deliver(run, None, self.repo)
        result = subprocess.run([sys.executable, '-B', '-X', 'utf8', str(SCRIPTS / 'review_delivery.py'),
                                 '--run-dir', str(run), '--project-root', str(self.repo)], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('--delivery', result.stderr)
        self.assertEqual(before, self.snapshot(self.root))

    def test_existing_destination_and_tampered_or_unretained_source_refused(self):
        run = self.retained()
        target = Path(delivery.deliver(run, 'brief', self.repo))
        before = self.snapshot(target)
        with self.assertRaises(ValueError):
            delivery.deliver(run, 'full', self.repo)
        self.assertEqual(before, self.snapshot(target))
        (run / 'review.json').write_text('{}', encoding='utf-8')
        with self.assertRaises(ValueError):
            delivery.deliver(run, 'full', self.repo, self.root / 'other')
        self.assertFalse((self.root / 'other').exists())

    def test_prepared_archive_cannot_be_delivered(self):
        run = Path(artifacts.prepare(self.repo, self.write('scope.json', record6()['scope']),
                                    '2.8.0', 'codex', output_root=self.archive))
        before = self.snapshot(run)
        with self.assertRaises(ValueError):
            delivery.deliver(run, 'brief', self.repo)
        self.assertEqual(before, self.snapshot(run))
        self.assertFalse((self.repo / 'docs').exists())

    def test_business_paths_and_urls_survive_while_unc_and_absolute_paths_do_not(self):
        value = record6()
        value['verdict_reason'] = ('Ruta HTTP /api/orders y /v2/orders; repo src/api.py; '
                                  'https://example.test/api/orders?q=12#result; '
                                  r'local \\private\share\result.log; /srv/private/result.log; '
                                  '//private/share/result.log; file:///srv/private/result.log')
        run = self.retained(value)
        target = Path(delivery.deliver(run, 'full', self.repo))
        text = (target / 'informe.md').read_text(encoding='utf-8')
        for public in ('/api/orders', '/v2/orders', 'src/api.py', 'https://example.test/api/orders?q=12#result'):
            self.assertIn(public, text.replace('\\#', '#'))
            self.assertIn(public, artifacts.read_json(target / 'review.json')['verdict_reason'])
        for private in ('private\\share', '/srv/private', '//private/share', 'file:///'):
            self.assertNotIn(private, text)

    def test_reused_historical_check_preserves_execution_provenance(self):
        value = record6()
        value['previous_reviews'] = [dict(review_id='CR-' + 'b' * 20, reference='archive/old/review.json', verified=True)]
        value['grandfathered_ids']['checks'] = ['C-01']
        old = check('C-01')
        old.update(revision='previous-head', reused=True, reuse_reason='Mismo contrato sin cambios',
                   reference='archive/old/evidence/execution.log')
        value['checks'] = [old]
        run = self.retained(value)
        target = Path(delivery.deliver(run, 'full', self.repo))
        projected = artifacts.read_json(target / 'review.json')
        self.assertEqual(artifacts.review_contract.validate(projected), [])
        projected_check = projected['checks'][0]
        for field in ('id', 'revision', 'status', 'reused', 'reuse_reason'):
            self.assertEqual(projected_check[field], old[field])
        self.assertTrue(projected_check['reference'].startswith('retained:'))
        self.assertIn(artifacts.read_json(target / '.ccr-delivery.json')['source_hash'], projected_check['reference'])

    def test_explicit_cli_custom_root_uses_scope_and_review_subdirectories(self):
        run = self.retained()
        root = self.root / 'published'
        result = subprocess.run([sys.executable, '-B', '-X', 'utf8', str(SCRIPTS / 'review_delivery.py'),
                                 '--run-dir', str(run), '--delivery', 'brief', '--project-root', str(self.repo),
                                 '--output-root', str(root)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        target = Path(json.loads(result.stdout)['delivery_dir'])
        self.assertEqual(target.parent, root / run.parent.name)
        self.assertTrue((target / 'resumen.md').is_file())

    def test_relative_output_root_is_anchored_at_project_in_api_and_cli(self):
        first = self.retained()
        second = self.retained()
        absolute = Path(delivery.deliver(first, 'brief', self.repo, self.repo / 'docs' / 'team-review'))
        relative = Path(delivery.deliver(second, 'brief', self.repo, 'docs/team-review'))
        self.assertEqual(absolute.parent, relative.parent)
        third = self.retained()
        result = subprocess.run([sys.executable, '-B', '-X', 'utf8', str(SCRIPTS / 'review_delivery.py'),
                                 '--run-dir', str(third), '--delivery', 'brief', '--project-root', str(self.repo),
                                 '--output-root', 'docs/team-review'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(Path(json.loads(result.stdout)['delivery_dir']).parent, absolute.parent)
        with self.assertRaises(ValueError):
            delivery.deliver(third, 'full', self.repo, '../escape')

    def test_scope_reference_preserves_portable_branch_range_and_request_ids(self):
        for reference in ('feature/orders', 'HEAD~3..HEAD', '!1003'):
            value = record6()
            value['scope'].update(mode='range', reference=reference)
            value['description'].update(status='not_applicable', identity=None, details='')
            run = self.retained(value)
            target = Path(delivery.deliver(run, 'full', self.repo))
            self.assertEqual(artifacts.read_json(target / 'review.json')['scope']['reference'], reference)

    def test_brief_counts_only_confirmed_findings_and_discloses_empty_priorities(self):
        for populated in (False, True):
            value = record6()
            if populated:
                confirmed = finding()
                confirmed['id'] = 'F001'
                unresolved = finding(status='unresolved')
                unresolved.update(id='F002', priority='P1')
                value['findings'] = [confirmed, unresolved]
            run = self.retained(value)
            target = Path(delivery.deliver(run, 'brief', self.repo))
            text = (target / 'resumen.md').read_text(encoding='utf-8')
            expected = ('**Confirmados:** 🔴 P0: 0 · 🟠 P1: 0 · 🟡 P2: 1 · 🔵 P3: 0'
                        if populated else '**Confirmados:** 🔴 P0: 0 · 🟠 P1: 0 · 🟡 P2: 0 · 🔵 P3: 0')
            self.assertIn(expected, text)

    def test_output_under_source_or_registered_temporary_is_refused(self):
        temporary = self.root / 'temporary'
        temporary.mkdir()
        run = self.retained(temporary=[temporary])
        before = self.snapshot(run)
        for output in (run, run / 'nested', self.archive, temporary, temporary / 'child'):
            with self.subTest(output=output), self.assertRaises(ValueError):
                delivery.deliver(run, 'full', self.repo, output)
        self.assertEqual(before, self.snapshot(run))
        self.assertEqual(list(temporary.iterdir()), [])

    def test_project_must_be_same_git_root_and_never_registered_temporary(self):
        temporary = self.root / 'temporary'
        temporary.mkdir()
        run = self.retained(temporary=[temporary])
        for project in (temporary, temporary / 'child', self.repo / 'nested', self.root):
            with self.subTest(project=project), self.assertRaises(ValueError):
                delivery.deliver(run, 'full', project)
        other = self.root / 'other-repository'
        other.mkdir()
        subprocess.run(['git', 'init', str(other)], capture_output=True, check=True)
        with self.assertRaises(ValueError):
            delivery.deliver(run, 'full', other)
        self.assertFalse((self.repo / 'docs').exists())

    def test_context_requires_collected_references_and_versions(self):
        value = record6()
        item = finding()
        item['id'] = 'F001'
        value['findings'] = [item]
        run = self.retained(value)
        context = {'assumptions': [{'text': 'Validar consumidor externo después', 'references': ['F001'], 'version': 'head-456'}],
                   'sources': [{'title': 'Spec', 'reference': 'https://example.test/spec',
                                'identity': 'sha256:spec-1', 'sections': ['3.2 respuestas'], 'version': 'head-456'}],
                   'implementation_state': [{'text': 'Campo ausente observado', 'references': ['src/api.py:12'], 'version': 'head-456'}],
                   'pending': [{'text': 'Confirmar compatibilidad', 'references': ['https://example.test/spec#3.2'], 'version': 'head-456'}]}
        target = Path(delivery.deliver(run, 'brief', self.repo, context=context))
        text = (target / 'contexto.md').read_text(encoding='utf-8')
        for token in ('3.2 respuestas', 'sha256:spec-1', 'head-456', 'Campo ausente observado', 'Confirmar compatibilidad'):
            self.assertIn(token, text)
        self.assertIn('autorización', text)
        for bad in ({'spec': 'invented'}, {'pending': [{'text': 'Do it'}]}, {'sources': [{'title': 'Spec'}]}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                delivery.deliver(run, 'brief', self.repo, self.root / ('bad-' + str(len(str(bad)))), context=bad)

    def test_context_typed_references_hide_absolute_paths_and_are_bounded(self):
        value = record6()
        item = finding()
        item['id'] = 'F001'
        value['findings'] = [item]
        run = self.retained(value)
        context = {'pending': [{'text': 'Endpoint /api/orders requiere validación',
                               'references': ['/api/private/result.log', '_archive/old/report.md', 'F001'], 'version': 'head-456'}],
                   'sources': [{'title': 'Spec', 'reference': '/api/private/spec.md', 'identity': 'sha256:spec-1',
                                'sections': ['3.2'], 'version': 'head-456'}]}
        target = Path(delivery.deliver(run, 'brief', self.repo, context=context))
        text = (target / 'contexto.md').read_text(encoding='utf-8')
        self.assertIn('/api/orders', text)
        self.assertIn('F001', text)
        for private in ('/api/private', '_archive/old'):
            self.assertNotIn(private, text)
        for too_big in ({'pending': [{'text': 'x' * 33000, 'references': ['F001'], 'version': 'head-456'}]},
                        {'pending': [{'text': 'Pendiente', 'references': ['F001'], 'version': 'head-456'}] * 25}):
            with self.assertRaises(ValueError):
                delivery.deliver(run, 'brief', self.repo, self.root / 'oversized', context=too_big)
        self.assertFalse((self.root / 'oversized').exists())

    def test_versioned_records_preserve_schema_and_known_identity(self):
        for schema in range(1, 8):
            value = record6() if schema in (6, 7) else legacy_record()
            value['schema_version'] = schema
            if schema == 7:
                value['profile'] = 'standard'
            if schema >= 2:
                value['coverage']['areas'] = [dict(area=area, status='covered', details='Inspección', material=False, finding_ids=[]) for area in 'ABCDE']
            if schema >= 3:
                value['change_authors'] = []
            if schema >= 4:
                value['presentation'] = {'kind': 'review', 'subject': 'Contrato'}
            run = self.retained(value)
            before = self.snapshot(run)
            target = Path(delivery.deliver(run, 'full', self.repo))
            self.assertEqual(artifacts.read_json(target / 'review.json')['schema_version'], schema)
            self.assertEqual(target.name, artifacts.read_json(run / 'review.json').get('review_id', artifacts.read_json(run / 'cierre.json')['run_id']))
            self.assertEqual(before, self.snapshot(run))

    def test_private_rereview_provenance_remains_consistent_and_valid(self):
        value = record6()
        value['previous_reviews'] = [dict(review_id='CR-' + 'b' * 20, reference='archive/old/review.json', verified=True)]
        value['grandfathered_ids']['findings'] = ['F-01']
        value['rereview'] = [dict(id='F-01', status='not_reevaluated', details='Fuera del alcance',
            previous_review_id='CR-' + 'b' * 20, previous_reference='archive/old/review.json',
            previous_finding_id='F-01', previous_title='Contrato anterior', previous_url=None, check_ids=[])]
        run = self.retained(value)
        target = Path(delivery.deliver(run, 'full', self.repo))
        projected = artifacts.read_json(target / 'review.json')
        self.assertEqual(artifacts.review_contract.validate(projected), [])
        self.assertEqual(projected['previous_reviews'][0]['reference'], projected['rereview'][0]['previous_reference'])
        self.assertEqual(projected['rereview'][0]['id'], 'F-01')
        self.assertNotIn('archive/old', (target / 'informe.md').read_text(encoding='utf-8'))

    def test_traversal_link_and_reparse_destination_rejected(self):
        run = self.retained()
        with self.assertRaises(ValueError):
            delivery.deliver(run, 'full', self.repo, self.root / '..' / 'escape')
        linked = self.root / 'linked'
        try:
            linked.symlink_to(self.repo, target_is_directory=True)
        except OSError:
            pass
        else:
            with self.assertRaises(ValueError):
                delivery.deliver(run, 'full', self.repo, linked / 'delivery')
        original = Path.lstat
        def reparse(path):
            info = original(path)
            if path == self.repo:
                return type('Reparse', (), {'st_mode': info.st_mode, 'st_file_attributes': 0x400})()
            return info
        with patch.object(Path, 'lstat', reparse), self.assertRaises(ValueError):
            delivery.deliver(run, 'full', self.repo)

    def test_write_failure_rolls_back_only_own_preparation(self):
        run = self.retained()
        root = self.root / 'delivery'
        root.mkdir()
        keep = root / 'keep.txt'
        keep.write_text('user file', encoding='utf-8')
        original = delivery._write_file
        def partial_failure(path, data, owned_files):
            original(path, data[:5], owned_files)
            raise OSError('fixture disk failure after partial write')
        with patch.object(delivery, '_write_file', side_effect=partial_failure):
            with self.assertRaises(OSError):
                delivery.deliver(run, 'full', self.repo, root)
        self.assertEqual(list(root.iterdir()), [keep])
        self.assertEqual(keep.read_text(encoding='utf-8'), 'user file')


if __name__ == '__main__':
    unittest.main()
