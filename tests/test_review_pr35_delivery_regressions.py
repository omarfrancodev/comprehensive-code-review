"""PR35 disclosure composition and portable schema13 delivery regressions."""
import json
from pathlib import Path
import subprocess
import sys
import unittest
import copy

from script_test_support import enable_package_imports
enable_package_imports()
import test_review_compact_archive as fixtures
from ccr.archive import compact
from ccr.contracts.check_disclosure import source_digest
from ccr.reporting import delivery, render
from ccr.shared.git import repository_identity
from ccr.workflow.builders import build_check_disclosure
import test_review_check_receipts as receipts
from test_review_contract import finding

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'


class CompactDisclosureCliTests(unittest.TestCase):
    setUp = fixtures.CompactPrepareTests.setUp
    prepare = fixtures.CompactPrepareTests.prepare
    record_and_sources = fixtures.CompactPrepareTests.record_and_sources

    def write(self, name, value):
        path = self.root / name
        path.write_text(json.dumps(value), encoding='utf-8')
        return path

    def cli(self, *args):
        result = subprocess.run([sys.executable, '-B', '-X', 'utf8', str(SCRIPTS), *map(str, args)],
                                capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_cli_binds_raw_final_before_public_disclosure_builder_and_retains_same_record(self):
        repo, workspace, _ = receipts.CaptureCheckTests().make_workspace(self.root)
        prepared = self.prepare(repo_identity=repository_identity(repo), archive_root=self.root / 'archive')
        raw, sources = self.record_and_sources(prepared)
        self.assertNotIn('compact_identity', raw)
        prepared_path = self.write('prepared.json', prepared)
        raw_path = self.write('raw.json', raw)
        bound = self.cli('artifacts', 'bind-compact', '--prepared-input', prepared_path, '--input', raw_path)
        final_path = self.write('bound.json', bound)
        self.assertEqual(json.loads(raw_path.read_bytes()), raw)
        self.assertIn('compact_identity', bound)
        self.assertEqual(self.cli('artifacts', 'bind-compact', '--prepared-input', prepared_path,
                                 '--input', final_path), bound)
        identity = {'head': bound['scope']['head'], 'snapshot': bound['scope']['snapshot'],
                    'resource_manifest_sha256': None}
        evidence = Path(workspace['session_dir']) / 'evidence'
        evidence.mkdir()
        disclosure_path = evidence / 'check-disclosure.json'
        request = self.write('disclosure-request.json', {'session': workspace['manifest'], 'arguments': {
            'record': bound, 'input_identity': identity, 'execution_observations': {}, 'sources': {}}})
        self.cli('setup', 'check-disclosure', '--input', request, '--output', disclosure_path)
        sidecar_bytes = disclosure_path.read_bytes()
        self.assertEqual(json.loads(sidecar_bytes)['source_sha256'], source_digest(bound))
        self.assertNotEqual(source_digest(raw), source_digest(bound))
        context = json.loads(sources['evidence/context.json'])
        context.update(check_disclosure_reference='evidence/check-disclosure.json',
                       check_disclosure_input_identity=identity)
        sources['evidence/context.json'] = json.dumps(context).encode()
        sources['evidence/check-disclosure.json'] = sidecar_bytes
        catalog = {}
        for index, (name, data) in enumerate(sources.items()):
            path = self.root / ('source-' + str(index) + '.json')
            path.write_bytes(data)
            catalog[name] = str(path)
        result = self.cli('artifacts', 'retain-compact', '--prepared-input', prepared_path,
            '--input', final_path, '--current-inputs', self.write('inputs.json', self.inputs),
            '--sources-input', self.write('catalog.json', catalog))
        retained = compact.read_compact(result['run_dir'])
        self.assertEqual(retained['record'], bound)
        self.assertEqual((Path(result['run_dir']) / 'evidence/check-disclosure.json').read_bytes(), sidecar_bytes)
        for mode in ('full', 'brief'):
            target = delivery.deliver(result['run_dir'], mode, repo, repo / mode)
            self.assertTrue((target / '.ccr-delivery.json').is_file())

    def test_binding_preserves_exact_record_and_independent_disclosure_anchors(self):
        prepared = self.prepare()
        raw, sources = self.record_and_sources(prepared)
        original = copy.deepcopy(raw)
        bound = compact.bind_compact_record(prepared, raw)
        self.assertEqual(raw, original)
        wrong = copy.deepcopy(bound)
        wrong['compact_identity']['inputs_sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            compact.bind_compact_record(prepared, wrong)
        identity = {'head': bound['scope']['head'], 'snapshot': bound['scope']['snapshot'],
                    'resource_manifest_sha256': None}
        sidecar = build_check_disclosure(bound, identity, {}, sources)
        context = json.loads(sources['evidence/context.json'])
        context.update(check_disclosure_reference='evidence/check-disclosure.json',
                       check_disclosure_input_identity=identity)
        sources['evidence/context.json'] = json.dumps(context).encode()
        for mutation in ('record', 'input_anchor'):
            record = copy.deepcopy(bound)
            disclosure = copy.deepcopy(sidecar)
            if mutation == 'record':
                record['verdict_reason'] += ' Changed after disclosure'
            else:
                disclosure['input_identity']['head'] = 'forged-head'
            sources['evidence/check-disclosure.json'] = json.dumps(disclosure).encode()
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                compact.create_compact(prepared, record, render.render(record), self.inputs, sources)
        self.assertFalse(Path(prepared['run_dir']).exists())
        self.assertFalse((Path(prepared['staging_dir']) / 'payload-intent.json').exists())

    def test_schema13_deliveries_keep_business_paths_and_relative_repository_location(self):
        repo = self.root / 'repo'
        repo.mkdir()
        subprocess.run(['git', 'init', '-q', str(repo)], check=True, capture_output=True)
        prepared = self.prepare(repo_identity=repository_identity(repo), archive_root=self.root / 'archive')
        record, sources = self.record_and_sources(prepared)
        record['checks'] = []
        item = finding()
        item.update(id='F001', scenario='GET /api/orders y GET /v2/orders devuelven 500')
        item['location']['path'] = str(repo / 'src' / 'api.py')
        record['findings'] = [item]
        record['coverage']['areas'][0]['groups'][0]['finding_ids'] = ['F001']
        record['verdict_reason'] = ('Ruta HTTP /api/orders y /v2/orders; '
            'https://example.test/api/orders?q=12; /srv/private/result.log; '
            r'\\private\share\result.log; file:///private/state; '
            'https://example.test/private?token=synthetic-secret; password=synthetic-secret')
        result = compact.create_compact(prepared, record, render.render(record), self.inputs, sources)
        run = Path(result['run_dir'])
        before = {p.relative_to(run): p.read_bytes() for p in run.rglob('*') if p.is_file()}
        for mode in ('full', 'brief'):
            target = delivery.deliver(run, mode, repo, repo / mode)
            text = (target / ('informe.md' if mode == 'full' else 'resumen.md')).read_text(encoding='utf-8')
            for expected in ('/api/orders', '/v2/orders', 'src/api.py'):
                self.assertIn(expected, text)
            for private in ('synthetic-secret', '/srv/private', 'private\\share', 'file:///', str(repo)):
                self.assertNotIn(private, text)
            if mode == 'full':
                portable = json.loads((target / 'review.json').read_bytes())
                self.assertEqual(portable['findings'][0]['location']['path'], 'src/api.py')
                self.assertEqual(portable['findings'][0]['scenario'], item['scenario'])
                self.assertIn('https://example.test/api/orders?q=12', portable['verdict_reason'])
            self.assertEqual(before, {p.relative_to(run): p.read_bytes() for p in run.rglob('*') if p.is_file()})
