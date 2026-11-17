from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import sys
import unittest

import test_review_compact_archive as fixtures
from ccr.execution import workspaces


SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'


class CompactOutputTests(unittest.TestCase):
    setUp = fixtures.CompactPrepareTests.setUp
    prepare = fixtures.CompactPrepareTests.prepare
    record_and_sources = fixtures.CompactPrepareTests.record_and_sources

    def invoke(self, *args, area='artifacts'):
        return subprocess.run([sys.executable, '-B', '-X', 'utf8', str(SCRIPTS), area,
                               *map(str, args)], capture_output=True, encoding='utf-8')

    def write_json(self, name, value):
        path = self.root / name
        path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
        return path

    def session(self):
        repo = self.root / 'repo'
        repo.mkdir()
        workspaces.git(repo, 'init', '-q')
        workspaces.git(repo, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                       '-c', 'commit.gpgsign=false', 'commit', '--allow-empty', '-qm', 'Fixture')
        return workspaces.prepare(argparse.Namespace(
            repo=str(repo), mode='commit', ref='HEAD', role=['review'], include_untracked=[]))

    def inputs_for_bind(self):
        prepared = self.prepare()
        record, sources = self.record_and_sources(prepared)
        args = ('bind-compact', '--prepared-input', self.write_json('prepared.json', prepared),
                '--input', self.write_json('record.json', record))
        return prepared, sources, args

    def test_file_binding_and_summary_keep_the_archive_and_disclosure_gates(self):
        prepared, sources, args = self.inputs_for_bind()
        session = self.session()
        output = Path(session['session_dir'], 'evidence', 'bound.json')
        legacy = self.invoke(*args)
        self.assertEqual(legacy.returncode, 0, legacy.stderr)
        brief = self.invoke(*args, '--session', session['manifest'], '--output', output)
        self.assertEqual(brief.returncode, 0, brief.stderr)
        raw = output.read_bytes()
        record = json.loads(raw)
        self.assertEqual(record, json.loads(legacy.stdout))
        self.assertEqual(json.loads(brief.stdout), {
            'status': 'bound', 'review_id': prepared['review_id'],
            'output': str(output), 'sha256': hashlib.sha256(raw).hexdigest(),
        })
        self.assertLess(len(brief.stdout), len(legacy.stdout))
        self.assertNotIn('compact_identity', json.loads(Path(args[-1]).read_text(encoding='utf-8')))
        self.assertFalse(Path(prepared['run_dir']).exists())

        identity = {'head': record['scope']['head'], 'snapshot': record['scope']['snapshot'],
                    'resource_manifest_sha256': None}
        evidence = output.parent
        disclosure_request = {'session': session['manifest'], 'arguments': {
            'input_identity': identity, 'execution_observations': {}, 'sources': {},
        }}
        selected_record = {'reference': 'evidence/bound.json', 'sha256': hashlib.sha256(raw).hexdigest()}
        disclosure = evidence / 'disclosure.json'
        oversized = b' ' * (128 * 1024) + raw
        (evidence / 'oversized.json').write_bytes(oversized)
        for invalid in ({**selected_record, 'sha256': '0' * 64},
                        {**selected_record, 'reference': 'evidence/../../bound.json'},
                        {'reference': 'evidence/oversized.json', 'sha256': hashlib.sha256(oversized).hexdigest()}):
            with self.subTest(invalid=invalid):
                disclosure_request['arguments']['record_source'] = invalid
                request = self.write_json('disclosure-request.json', disclosure_request)
                rejected = self.invoke('check-disclosure', '--input', request, '--output', disclosure, area='setup')
                self.assertEqual(rejected.returncode, 1, rejected.stderr)
                self.assertIn('record source', rejected.stderr)
                self.assertFalse(disclosure.exists())
        disclosure_request['arguments']['record_source'] = selected_record
        request = self.write_json('disclosure-request.json', disclosure_request)
        built = self.invoke('check-disclosure', '--input', request, '--output', disclosure, area='setup')
        self.assertEqual(built.returncode, 0, built.stderr)
        del disclosure_request['arguments']['record_source']
        disclosure_request['arguments']['record'] = record
        embedded = evidence / 'embedded-disclosure.json'
        request = self.write_json('disclosure-request.json', disclosure_request)
        baseline = self.invoke('check-disclosure', '--input', request, '--output', embedded, area='setup')
        self.assertEqual(baseline.returncode, 0, baseline.stderr)
        self.assertEqual(disclosure.read_bytes(), embedded.read_bytes())
        context = json.loads(sources['evidence/context.json'])
        context.update(check_disclosure_reference='evidence/check-disclosure.json',
                       check_disclosure_input_identity=identity)
        sources['evidence/context.json'] = json.dumps(context).encode()
        sources['evidence/check-disclosure.json'] = disclosure.read_bytes()

        catalog = {}
        for name, data in sources.items():
            path = self.root / Path(name).name
            path.write_bytes(data)
            catalog[name] = str(path)
        catalog_path = self.write_json('catalog.json', catalog)
        retain_args = ('retain-compact', '--prepared-input', args[2], '--input', output,
                       '--current-inputs', self.write_json('current.json', self.inputs),
                       '--sources-input', catalog_path)

        # Removing observed execution must fail on either output path.
        missing = dict(catalog)
        del missing['evidence/compact-execution.json']
        self.write_json('catalog.json', missing)
        for flags in ((), ('--summary',)):
            with self.subTest(flags=flags):
                failed = self.invoke(*retain_args, *flags)
                self.assertEqual(failed.returncode, 1, failed.stderr)
                self.assertIn('execution', failed.stderr)
                self.assertFalse(Path(prepared['run_dir']).exists())

        self.write_json('catalog.json', catalog)
        saved = self.invoke(*retain_args, '--summary')
        self.assertEqual(saved.returncode, 0, saved.stderr)
        receipt = json.loads(saved.stdout)
        self.assertEqual(receipt, {
            'review_id': prepared['review_id'], 'run_dir': prepared['run_dir'], 'mode': 'compact',
        })
        full = self.invoke(*retain_args)
        self.assertEqual(full.returncode, 0, full.stderr)
        self.assertIn('evidence/check-disclosure.json', json.loads(full.stdout)['hashes'])
        checked = self.invoke('validate', '--run-dir', receipt['run_dir'], '--require-complete')
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertEqual(json.loads(checked.stdout)['state'], 'complete')
        run = Path(receipt['run_dir'])
        self.assertFalse((run / 'evidence/model-usage.json').exists())
        self.assertEqual(json.loads((run / 'review.json').read_bytes()), record)

    def test_binding_rejects_output_escape_collision_and_identity_conflict(self):
        prepared, _, args = self.inputs_for_bind()
        session = self.session()
        owned = Path(session['session_dir'], 'evidence')
        owned.mkdir()
        target = owned / 'bound.json'
        target.write_bytes(b'preserve existing bytes')
        escaped = self.root / 'outside.json'
        for path in (target, escaped):
            with self.subTest(path=path):
                result = self.invoke(*args, '--session', session['manifest'], '--output', path)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn('output', result.stderr)
                self.assertEqual(result.stdout, '')
        self.assertEqual(target.read_bytes(), b'preserve existing bytes')
        self.assertFalse(escaped.exists())

        record = json.loads(Path(args[-1]).read_text(encoding='utf-8'))
        record['review_id'] = 'CR-' + 'f' * 20
        self.write_json('record.json', record)
        conflicted = self.invoke(*args, '--session', session['manifest'], '--output', owned / 'wrong.json')
        self.assertEqual(conflicted.returncode, 1, conflicted.stderr)
        self.assertIn('pinned scope or identity', conflicted.stderr)
        self.assertFalse((owned / 'wrong.json').exists())
        self.assertFalse(Path(prepared['run_dir']).exists())

