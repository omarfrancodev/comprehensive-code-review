"""Exercise comment preparation and verification against retained compact runs."""
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import unittest

import test_review_compact_archive as fixtures
from publication_fixtures import check_classification, coverage_classification
from ccr.archive import compact
from ccr.cli import comment
from ccr.reporting import render

SIDECAR = 'evidence/check-disclosure.json'
CONTEXT = 'evidence/context.json'


class CompactCommentTests(unittest.TestCase):
    setUp = fixtures.CompactPrepareTests.setUp
    prepare = fixtures.CompactPrepareTests.prepare
    record_and_sources = fixtures.CompactPrepareTests.record_and_sources

    def write_json(self, path, value):
        path.write_text(json.dumps(value), encoding='utf-8')
        return str(path)

    def publish(self, *, operation_id='comment', with_sidecar=False, no_checks=False,
                scope=None, additional_checks=()):
        from ccr.workflow.builders import build_check_disclosure

        if with_sidecar:
            from test_review_check_disclosure import fixture

            proof_record, identity, observations, proof_sources = fixture()
            scope = {**self.scope, 'head': identity['head']}
        if scope is not None:
            self.inputs = {**self.inputs, 'scope': scope}
        reserved = self.prepare(operation_id=operation_id, scope=scope)
        record, sources = self.record_and_sources(reserved)
        if scope is not None:
            record['scope'] = scope
            for check in record['checks']:
                check['revision'] = scope['head'] or scope['snapshot']
        if record['scope']['mode'] not in ('pr', 'mr'):
            record['description'] = dict(status='not_applicable', identity=None, details='')
        if no_checks:
            record['checks'] = []
        elif additional_checks:
            template = record['checks'][0]
            record['checks'].extend({**template, **check} for check in additional_checks)
        if with_sidecar:
            record['checks'][0]['command'] = proof_record['checks'][0]['command']
        record = compact.bind_compact_record(reserved, record)
        if with_sidecar:
            sidecar = build_check_disclosure(record, identity, observations, proof_sources)
            sources[SIDECAR] = json.dumps(sidecar, indent=2).encode()
            sources.update(proof_sources)
            context = json.loads(sources[CONTEXT])
            context.update(check_disclosure_reference=SIDECAR, check_disclosure_input_identity=identity)
            sources[CONTEXT] = json.dumps(context).encode()
        result = compact.create_compact(reserved, record, render.render(record), self.inputs, sources)
        return Path(result['run_dir']), record

    def cli(self, args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                status = comment.main([str(arg) for arg in args])
            except SystemExit as exc:
                status = exc.code
        return status, stdout.getvalue(), stderr.getvalue()

    def publication_args(self, run, record):
        from test_review_check_receipts import CaptureCheckTests

        _, workspace, _ = CaptureCheckTests().make_workspace(self.root)
        output = Path(workspace['session_dir']) / 'evidence' / 'draft.json'
        check_context = check_classification(record)
        for row, check in zip(check_context['checks'], record['checks']):
            row['purpose'] = 'Validar el flujo revisado.'
            row['reference'] = check['reference']
        args = ['prepare', '--run-dir', run, '--session', workspace['manifest'], '--output', output,
                '--check-publication-context', self.write_json(self.root / 'checks.json', check_context),
                '--coverage-publication-context', self.write_json(self.root / 'coverage.json', coverage_classification(record))]
        return args, output

    def verify_args(self, run, output):
        return ['verify', '--run-dir', run, '--draft', output, '--body', self.root / 'body.md']

    def inventory(self, run):
        return {path.relative_to(run): path.read_bytes() for path in run.rglob('*') if path.is_file()}

    def assert_succeeds(self, args):
        status, stdout, stderr = self.cli(args)
        self.assertEqual(status, 0, stderr)
        return json.loads(stdout)

    def assert_fails(self, args, expected):
        status, stdout, stderr = self.cli(args)
        self.assertNotEqual(status, 0)
        self.assertFalse(stdout)
        self.assertIn(expected, stderr)

    def test_closed_compact_without_disclosure_prepares_and_verifies(self):
        run, record = self.publish()
        original = self.inventory(run)
        args, output = self.publication_args(run, record)
        self.assert_succeeds(args)
        original_draft = output.read_bytes()
        draft = json.loads(original_draft)
        self.assertEqual(draft['schema_version'], 4)
        rows = draft['check_disclosure_context']['checks']
        self.assertEqual([row['mode'] for row in rows], ['explanation'] * len(record['checks']))
        self.assertIn('Validar el flujo revisado.', draft['body'])
        self.assertNotIn(record['checks'][0]['command'], draft['body'])
        body = self.root / 'body.md'
        body.write_bytes(draft['body'].encode())
        verify = self.verify_args(run, output)
        self.assertTrue(self.assert_succeeds(verify)['verified'])
        body.write_bytes(draft['body'].replace('\n', '\r\n').encode())
        self.assert_fails(verify, 'body_mismatch')
        self.assertTrue(self.assert_succeeds(verify + ['--remote'])['verified'])
        body.write_bytes(draft['body'][:-1].encode())
        self.assert_fails(verify + ['--remote'], 'body_mismatch')
        gitlab = ['--remote', '--remote-transport', 'gitlab']
        self.assertTrue(self.assert_succeeds(verify + gitlab)['verified'])
        self.assert_fails(verify + gitlab[1:], '--remote-transport requires --remote')
        body.write_bytes(draft['body'][:-2].encode())
        self.assert_fails(verify + gitlab, 'body_mismatch')
        body.write_bytes(draft['body'].encode())

        other_run, _ = self.publish(operation_id='other-comment')
        self.assert_fails(self.verify_args(other_run, output), 'source_mismatch')
        tampered = copy.deepcopy(draft)
        tampered['check_disclosure_context']['checks'][0]['explanation'] = 'Editado'
        altered = self.write_json(self.root / 'altered-draft.json', tampered)
        self.assert_fails(self.verify_args(run, altered), 'disclosure_mismatch')
        tampered = {**draft, 'body': 'Editado\n'}
        tampered['body_sha256'] = hashlib.sha256(tampered['body'].encode()).hexdigest()
        self.write_json(Path(altered), tampered)
        self.assert_fails(self.verify_args(run, altered), 'body_mismatch')
        self.assert_fails(args, 'exist')
        self.assertEqual(output.read_bytes(), original_draft)
        self.assertEqual(self.inventory(run), original)

    def test_retained_sidecar_is_used_and_missing_sidecar_blocks(self):
        run, record = self.publish(with_sidecar=True)
        args, output = self.publication_args(run, record)
        self.assert_succeeds(args)
        draft = json.loads(output.read_bytes())
        self.assertEqual(draft['check_disclosure_context']['check_disclosure_sha256'],
                         hashlib.sha256((run / SIDECAR).read_bytes()).hexdigest())
        self.assertEqual(draft['check_disclosure_context']['checks'][0]['command'],
                         'pytest tests/test_queue.py -k retry')
        self.assertIn('**Comando saneado:** pytest', draft['body'])
        self.assertNotIn('/private/home', draft['body'])
        (self.root / 'body.md').write_bytes(draft['body'].encode())
        verify = self.verify_args(run, output)
        self.assertTrue(self.assert_succeeds(verify)['verified'])

        sidecar = json.loads((run / SIDECAR).read_bytes())
        row = sidecar['checks'][0]
        names = (row['execution_reference'], row['evidence_reference'])
        catalog = {'input_identity': sidecar['input_identity'], 'sources': {
            name: {'path': str(run / name), 'sha256': hashlib.sha256((run / name).read_bytes()).hexdigest()}
            for name in names}}
        manual = ['verify', '--input', run / 'review.json', *verify[3:],
                  '--check-disclosure-context', run / SIDECAR,
                  '--check-disclosure-sources', self.write_json(self.root / 'catalog.json', catalog)]
        self.assertTrue(self.assert_succeeds(manual)['verified'])
        (run / SIDECAR).unlink()
        new_output = output.with_name('new.json')
        args[args.index(output)] = new_output
        self.assert_fails(args, 'compact')
        self.assert_fails(verify, 'compact')
        self.assertFalse(new_output.exists())

    def test_compact_without_checks_uses_empty_disclosure_view(self):
        run, record = self.publish(no_checks=True)
        args, output = self.publication_args(run, record)
        self.assert_succeeds(args)
        draft = json.loads(output.read_bytes())
        self.assertIsNone(draft['check_disclosure_context'])
        (self.root / 'body.md').write_bytes(draft['body'].encode())
        self.assertTrue(self.assert_succeeds(self.verify_args(run, output))['verified'])

    def rewrite_selected_bytes(self, run, edits):
        """Keep archive hashes coherent so malformed selected inputs reach semantic validation."""
        manifest = run / 'manifest.json'
        metadata = json.loads(manifest.read_bytes())
        for name, data in edits.items():
            (run / name).write_bytes(data)
            metadata['hashes'][name] = hashlib.sha256(data).hexdigest()
        manifest.write_bytes(json.dumps(metadata).encode())
        marker = run / '.review-ownership.json'
        owner = json.loads(marker.read_bytes())
        owner['manifest_sha256'] = hashlib.sha256(manifest.read_bytes()).hexdigest()
        marker.write_bytes(json.dumps(owner).encode())

    def test_unusable_declared_disclosure_never_degrades_to_fallback(self):
        run, record = self.publish(with_sidecar=True)
        args, output = self.publication_args(run, record)
        self.assert_succeeds(args)
        draft = json.loads(output.read_bytes())
        (self.root / 'body.md').write_bytes(draft['body'].encode())
        verify = self.verify_args(run, output)
        blocked = output.with_name('blocked.json')
        args[args.index(output)] = blocked
        context = json.loads((run / CONTEXT).read_bytes())
        sidecar = (run / SIDECAR).read_bytes()
        proof_path = json.loads(sidecar)['checks'][0]['execution_reference']
        proof = (run / proof_path).read_bytes()
        for name, change, diagnostic in (
            ('invalid reference', {CONTEXT: json.dumps({**context, 'check_disclosure_reference': []}).encode()},
             'compact check disclosure source is unavailable'),
            ('mismatched identity', {CONTEXT: json.dumps({**context, 'check_disclosure_input_identity': {}}).encode()},
             'disclosure input identity differs'),
            ('malformed sidecar', {SIDECAR: b'{'}, 'Expecting property name'),
            ('malformed row', {SIDECAR: json.dumps({**json.loads(sidecar), 'checks': [None]}).encode()},
             'invalid compact check disclosure evidence'),
            ('invalid proof', {proof_path: b'{}'}, 'snapshot disclosure requires'),
            ('orphan', {CONTEXT: json.dumps({**context, 'check_disclosure_reference': None}).encode()},
             'without a declared reference'),
        ):
            with self.subTest(name=name):
                edits = {CONTEXT: json.dumps(context).encode(), SIDECAR: sidecar, proof_path: proof, **change}
                self.rewrite_selected_bytes(run, edits)
                self.assert_fails(args, diagnostic)
                self.assert_fails(verify, diagnostic)
                self.assertFalse(blocked.exists())

        for path in ('manifest.json', 'review.json'):
            with self.subTest(path=path):
                before = (run / path).read_bytes()
                (run / path).write_bytes(before + b' ')
                self.assert_fails(args, 'hash differs')
                self.assert_fails(verify, 'hash differs')
                self.assertFalse(blocked.exists())
                (run / path).write_bytes(before)

    def test_source_options_and_old_drafts_keep_distinct_contracts(self):
        run, record = self.publish()
        args, output = self.publication_args(run, record)
        source = run / 'review.json'
        self.assert_fails(args + ['--input', source], 'not allowed with argument')
        for flag in ('--check-disclosure-context', '--check-disclosure-sources'):
            self.assert_fails(args + [flag, source], 'cannot be combined')
        standalone = list(args)
        index = standalone.index('--run-dir')
        standalone[index:index + 2] = ['--input', source]
        self.assert_fails(standalone, 'check disclosure context required')
        self.assert_fails(standalone + ['--check-disclosure-context', source], 'supplied together')
        invalid_session = list(args)
        invalid_session[invalid_session.index('--session') + 1] = self.root / 'missing.json'
        self.assert_fails(invalid_session, 'manifest')
        self.assertFalse(output.exists())
        self.assert_succeeds(args)
        draft = json.loads(output.read_bytes())
        (self.root / 'body.md').write_bytes(draft['body'].encode())
        for version in (2, 3):
            with self.subTest(version=version):
                legacy = self.write_json(self.root / 'legacy.json', {**draft, 'schema_version': version})
                self.assert_fails(self.verify_args(run, legacy), 'verify schema 2/3 drafts with --input')

    def test_corrupt_followup_source_blocks_both_commands(self):
        import test_review_legacy_alias_authority_pr37 as legacy

        historical = legacy.RetainedLegacyAliasAuthorityTests()
        historical.setUp()
        self.addCleanup(historical.doCleanups)
        prior, original = historical.publish_v1_alias()
        reserved = historical.prepare(operation_id='comment-followup')
        record, sources = legacy.v2_alias_copy(original)
        sources.update(historical.bind_followup(record, prior, reserved))
        saved = compact.create_compact(reserved, record, render.render(record), historical.inputs, sources)
        run = Path(saved['run_dir'])
        record = compact.read_compact(run)['record']
        args, output = self.publication_args(run, record)
        previous = record['assessment']['previous']['source']['reference']
        self.rewrite_selected_bytes(run, {previous: b'{}'})
        self.assert_fails(args, 'assessment source differs from selected SHA-256')
        self.assert_fails(self.verify_args(run, output), 'assessment source differs from selected SHA-256')
        self.assertFalse(output.exists())

    def test_range_with_snapshot_reuses_fallback(self):
        scope = {**self.scope, 'mode': 'range', 'reference': None, 'snapshot': 'b' * 64}
        run, record = self.publish(scope=scope, additional_checks=(
            dict(id='C002', status='failed', failure_kind='product', evidence='Validación externa fallida.',
                 reference='https://example.test/job/42', execution={'kind': 'external', 'executor': None}),
            dict(id='C003', status='not_run', evidence=None),
        ))
        args, output = self.publication_args(run, record)
        self.assert_succeeds(args)
        draft = json.loads(output.read_bytes())
        for entry in ('**C001**: aprobada', '**C002**: falló', '**C003**: no ejecutada',
                      'Validación externa fallida.', 'https://example.test/job/42'):
            self.assertIn(entry, draft['body'])
        self.assertTrue(all(row['mode'] == 'explanation' for row in draft['check_disclosure_context']['checks']))
        (self.root / 'body.md').write_bytes(draft['body'].encode())
        self.assertTrue(self.assert_succeeds(self.verify_args(run, output))['verified'])
