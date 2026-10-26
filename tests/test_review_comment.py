"""Public comment drafts bind source, classifications and exact Markdown bytes."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from publication_fixtures import coverage_classification

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ccr.reporting import comment as comments
from script_test_support import contract_api
contract = contract_api()
from script_test_support import workspace_api
review_workspace = workspace_api()
from publication_fixtures import publication_record, check_classification


class PublicCommentTests(unittest.TestCase):
    def test_draft_matches_render_and_rejects_manual_edit(self):
        record = publication_record()
        original = copy.deepcopy(record)
        context = check_classification(record)
        draft = comments.prepare_public_comment(record, check_publication_context=context, coverage_publication_context=coverage_classification(record))
        self.assertEqual(draft, comments.prepare_public_comment(
            record, check_publication_context=context, coverage_publication_context=coverage_classification(record)))
        self.assertEqual(draft['body'], contract.render(
            record, audience='comment', check_publication_context=context, coverage_publication_context=coverage_classification(record)))
        self.assertEqual(draft['body_sha256'], hashlib.sha256(
            draft['body'].encode('utf-8')).hexdigest())
        self.assertTrue(comments.verify_public_comment(
            record, draft, draft['body'])['verified'])
        with self.assertRaisesRegex(ValueError, 'body_mismatch'):
            comments.verify_public_comment(record, draft, draft['body'] + '\nRetoque manual')
        self.assertEqual(record, original)

    def test_crlf_is_only_allowed_for_remote_transport(self):
        record = publication_record()
        draft = comments.prepare_public_comment(
            record, check_publication_context=check_classification(record), coverage_publication_context=coverage_classification(record))
        remote_body = draft['body'].replace('\n', '\r\n')
        with self.assertRaisesRegex(ValueError, 'body_mismatch'):
            comments.verify_public_comment(record, draft, remote_body)
        self.assertTrue(comments.verify_public_comment(
            record, draft, remote_body, remote=True)['verified'])

    def test_source_context_status_and_body_hash_tampering_fail_without_mutation(self):
        record = publication_record()
        context = check_classification(record)
        draft = comments.prepare_public_comment(record, check_publication_context=context, coverage_publication_context=coverage_classification(record))
        original_record, original_draft = copy.deepcopy(record), copy.deepcopy(draft)

        bad = copy.deepcopy(draft)
        bad['source_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'source_mismatch'):
            comments.verify_public_comment(record, bad, draft['body'])

        bad = copy.deepcopy(draft)
        bad['check_publication_context']['checks'][1]['evidence'] = 'Different public evidence'
        with self.assertRaisesRegex(ValueError, 'body_mismatch'):
            comments.verify_public_comment(record, bad, draft['body'])

        bad = copy.deepcopy(draft)
        bad['check_publication_context']['checks'][1]['status'] = 'passed'
        with self.assertRaises(ValueError):
            comments.verify_public_comment(record, bad, draft['body'])

        bad = copy.deepcopy(draft)
        bad['body_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'body_mismatch'):
            comments.verify_public_comment(record, bad, draft['body'])
        self.assertEqual(record, original_record)
        self.assertEqual(draft, original_draft)


@unittest.skipUnless(shutil.which('git'), 'Git is required for owned-session comment CLI')
class PublicCommentCliTests(unittest.TestCase):
    def test_prepare_uses_owned_session_and_verify_is_read_only(self):
        with tempfile.TemporaryDirectory(prefix='review-comment-') as directory:
            root = Path(directory).resolve()
            repo = root / 'repo'
            repo.mkdir()
            env = os.environ.copy()
            for key in list(env):
                if key.upper().startswith('GIT_'):
                    del env[key]
            env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull,
                       GIT_CONFIG_NOSYSTEM='1', PYTHONUTF8='1')

            def run(command, cwd=root):
                return subprocess.run(command, cwd=cwd, env=env, capture_output=True,
                                      text=True, encoding='utf-8')

            for command in (['git', 'init', '-q'],
                            ['git', 'config', 'user.name', 'Fixture Reviewer'],
                            ['git', 'config', 'user.email', 'fixture@example.invalid']):
                self.assertEqual(run(command, cwd=repo).returncode, 0)
            (repo / 'code.py').write_text('answer = 42\n', encoding='utf-8')
            for command in (['git', 'add', 'code.py'], ['git', 'commit', '-qm', 'baseline']):
                self.assertEqual(run(command, cwd=repo).returncode, 0)
            manifest = review_workspace.prepare(argparse.Namespace(
                repo=str(repo), mode='commit', ref='HEAD', role=['review'], include_untracked=[]))
            session = Path(manifest['session_dir'])
            evidence = session / 'evidence'
            evidence.mkdir()
            record = publication_record()
            record_path = root / 'review.json'
            record_bytes = json.dumps(record, ensure_ascii=False).encode('utf-8')
            record_path.write_bytes(record_bytes)
            context = check_classification(record)
            context_path = root / 'check-publication.json'
            context_path.write_text(json.dumps(context, ensure_ascii=False), encoding='utf-8')
            draft_path = evidence / 'public-comment.json'
            coverage_path = root / 'coverage-publication.json'
            coverage_path.write_text(json.dumps(coverage_classification(record)), encoding='utf-8')
            helper = SCRIPTS
            prepare = run([sys.executable, str(helper), 'comment', 'prepare', '--input', str(record_path),
                           '--session', str(manifest['manifest']), '--output', str(draft_path),
                           '--check-publication-context', str(context_path),
                           '--coverage-publication-context', str(coverage_path)])
            self.assertEqual(prepare.returncode, 0, prepare.stderr)
            draft = json.loads(draft_path.read_text(encoding='utf-8'))
            rendered = run([sys.executable, str(helper), 'contract', 'render-comment', '--input', str(record_path),
                            '--check-publication-context', str(context_path),
                            '--coverage-publication-context', str(coverage_path)])
            self.assertEqual(rendered.returncode, 0, rendered.stderr)
            self.assertEqual(rendered.stdout, draft['body'])
            coverage_path.write_text(json.dumps(dict(coverage_classification(record), flows=[])), encoding='utf-8')
            invalid = run([sys.executable, str(helper), 'comment', 'prepare', '--input', str(record_path),
                           '--session', str(manifest['manifest']), '--output', str(evidence / 'invalid.json'),
                           '--check-publication-context', str(context_path),
                           '--coverage-publication-context', str(coverage_path)])
            self.assertEqual(invalid.returncode, 1)
            self.assertFalse((evidence / 'invalid.json').exists())
            body_path = root / 'body.md'
            body_path.write_text(draft['body'], encoding='utf-8', newline='')
            before = {str(path.relative_to(session)): path.read_bytes()
                      for path in session.rglob('*') if path.is_file()}
            verify = run([sys.executable, str(helper), 'comment', 'verify', '--input', str(record_path),
                          '--draft', str(draft_path), '--body', str(body_path)])
            self.assertEqual(verify.returncode, 0, verify.stderr)
            self.assertTrue(json.loads(verify.stdout)['verified'])
            self.assertEqual({str(path.relative_to(session)): path.read_bytes()
                              for path in session.rglob('*') if path.is_file()}, before)
            self.assertEqual(record_path.read_bytes(), record_bytes)

            body_path.write_text(draft['body'] + '\nEdited', encoding='utf-8')
            mismatch = run([sys.executable, str(helper), 'comment', 'verify', '--input', str(record_path),
                            '--draft', str(draft_path), '--body', str(body_path)])
            self.assertEqual(mismatch.returncode, 1)
            self.assertIn('body_mismatch', mismatch.stderr)
            self.assertEqual(record_path.read_bytes(), record_bytes)

            cleanup = review_workspace.cleanup(argparse.Namespace(
                manifest=manifest['manifest'], run_dir=None))
            self.assertEqual(cleanup['status'], 'closed')


if __name__ == '__main__':
    unittest.main()
