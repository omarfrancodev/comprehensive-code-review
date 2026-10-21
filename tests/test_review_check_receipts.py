"""Check receipts preserve the exact command, outputs and execution binding."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
OWNED_WORKSPACE = str(Path(__file__).resolve().parents[1] / '.owned-executor')
sys.path.insert(0, str(SCRIPTS))
import review_check_receipts as receipts
import review_preflight
import review_workspace
from recovery_fixtures import context10, record10
from test_review_traceability_contract import check as base_check


def valid_receipt():
    stdout = b''
    stderr = b''
    return {
        'schema_version': 1,
        'check_id': 'C001',
        'argv': ['python', '-V'],
        'cwd': OWNED_WORKSPACE,
        'revision': 'head-456',
        'executor': 'X1',
        'started_at': '2026-10-19T18:00:00+00:00',
        'finished_at': '2026-10-19T18:00:01+00:00',
        'exit_code': 0,
        'stdout': {'reference': 'evidence/C001-out.log',
                   'sha256': hashlib.sha256(stdout).hexdigest(), 'bytes': len(stdout)},
        'stderr': {'reference': 'evidence/C001-err.log',
                   'sha256': hashlib.sha256(stderr).hexdigest(), 'bytes': len(stderr)},
    }


def valid_binding():
    check = {'id': 'C001', 'command': 'python -V', 'revision': 'head-456', 'status': 'passed',
             'execution': {'kind': 'local', 'executor': 'X1'}}
    executor = {'executor': 'X1', 'revision': 'head-456', 'snapshot': None,
                'workspace': OWNED_WORKSPACE}
    return check, [executor]


class CheckReceiptTests(unittest.TestCase):
    def test_retain_preflight_rejects_missing_selected_receipt(self):
        record = record10()
        check = dict(base_check(), revision=record['scope']['head'],
                     reference='evidence/attempt-1-C001-receipt.json',
                     execution={'kind': 'local', 'executor': 'X1'})
        record['checks'] = [check]
        context = context10(record)
        executor = {'executor': 'X1', 'revision': check['revision'], 'snapshot': None}
        context['executors'] = [executor]
        manifest = {'schema_version': 8, 'layout_version': 2, 'scope': record['scope'],
                    'profile_history': context['profile_history'],
                    'logical_scope': {'identity': context['review_inputs']['logical_scope_identity']},
                    'review_inputs': context['review_inputs'],
                    'assignment_registry': context['execution_plan']}
        result = review_preflight.validate_preflight(
            phase='retain', manifest=manifest, logical_scope=manifest['logical_scope'],
            selection=context['profile_history'][-1], context=context, record=record,
            sources={'evidence/context.json': json.dumps(context).encode('utf-8')})
        self.assertFalse(result['ready'])
        self.assertIn('invalid_receipt', {issue['code'] for issue in result['issues']})

    def test_record_receipt_reference_requires_selected_receipt_and_streams(self):
        receipt = valid_receipt()
        receipt['stdout']['reference'] = 'evidence/attempt-1-C001-out.log'
        receipt['stderr']['reference'] = 'evidence/attempt-1-C001-err.log'
        receipt_reference = 'evidence/attempt-1-C001-receipt.json'
        check, executors = valid_binding()
        check['reference'] = receipt_reference
        record = {'schema_version': 10, 'checks': [check]}
        receipt_bytes = json.dumps(receipt, sort_keys=True, separators=(',', ':')).encode('utf-8')
        sources = {receipt_reference: receipt_bytes,
                   receipt['stdout']['reference']: b'', receipt['stderr']['reference']: b''}
        self.assertEqual(receipts.validate_record_receipts(record, sources, executors), [])
        del sources[receipt['stderr']['reference']]
        self.assertIn('invalid_receipt', {issue['code'] for issue in
                                          receipts.validate_record_receipts(record, sources, executors)})

    def test_empty_streams_need_observed_exit(self):
        receipt = valid_receipt()
        check, executors = valid_binding()
        sources = {'evidence/C001-out.log': b'', 'evidence/C001-err.log': b''}
        self.assertEqual(receipts.validate_receipt(
            receipt, sources, check=check, executors=executors), [])

        incomplete = dict(receipt, exit_code=None, finished_at=None)
        issues = receipts.validate_receipt(
            incomplete, sources, check=check, executors=executors)
        self.assertIn('invalid_receipt', {issue['code'] for issue in issues})

    def test_receipt_command_must_match_the_argv_declared_by_the_check(self):
        receipt = valid_receipt()
        check, executors = valid_binding()
        sources = {'evidence/C001-out.log': b'', 'evidence/C001-err.log': b''}
        check['command'] = 'pytest -q'

        issues = receipts.validate_receipt(receipt, sources, check=check, executors=executors)

        self.assertTrue(any(issue['field'] == 'command' for issue in issues))

    def test_receipt_accepts_canonical_command_with_literal_newline_and_tab(self):
        receipt = valid_receipt()
        argv = ['python', '-c', 'print(1)\nprint(2)', '\tvalue']
        receipt['argv'] = argv
        check, executors = valid_binding()
        check['command'] = shlex.join(argv)
        sources = {'evidence/C001-out.log': b'', 'evidence/C001-err.log': b''}

        self.assertEqual(receipts.validate_receipt(
            receipt, sources, check=check, executors=executors), [])

    def test_receipt_cwd_must_match_registered_executor_workspace(self):
        receipt = valid_receipt()
        check, executors = valid_binding()
        executors[0]['workspace'] = str(Path(OWNED_WORKSPACE).with_name('different-executor'))
        sources = {'evidence/C001-out.log': b'', 'evidence/C001-err.log': b''}

        issues = receipts.validate_receipt(receipt, sources, check=check, executors=executors)

        self.assertTrue(any(issue['field'] == 'cwd' for issue in issues))

    def test_tampered_bytes_and_mismatched_executor_or_revision_fail(self):
        receipt = valid_receipt()
        check, executors = valid_binding()
        sources = {'evidence/C001-out.log': b'', 'evidence/C001-err.log': b''}
        altered = dict(sources, **{'evidence/C001-out.log': b'changed'})
        self.assertIn('invalid_receipt', {issue['code'] for issue in receipts.validate_receipt(
            receipt, altered, check=check, executors=executors)})
        self.assertTrue(receipts.validate_receipt(
            receipt, sources, check=dict(check, revision='other-head'), executors=executors))
        self.assertTrue(receipts.validate_receipt(
            receipt, sources, check=check,
            executors=[dict(executors[0], executor='X2')]))

    def test_validation_never_starts_a_process(self):
        with patch('review_check_receipts.subprocess.run') as run:
            receipts.validate_receipt(valid_receipt(), {
                'evidence/C001-out.log': b'', 'evidence/C001-err.log': b''},
                check=valid_binding()[0], executors=valid_binding()[1])
            run.assert_not_called()


@unittest.skipUnless(shutil.which('git'), 'Git is required for owned-workspace capture')
class CaptureCheckTests(unittest.TestCase):
    def make_workspace(self, root):
        repo = root / 'repo'
        repo.mkdir()
        env = os.environ.copy()
        for key in list(env):
            if key.upper().startswith('GIT_'):
                del env[key]
        env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull,
                   GIT_CONFIG_NOSYSTEM='1')

        def git(*args):
            result = subprocess.run(['git', *args], cwd=repo, env=env,
                                    capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(result.returncode, 0, result.stderr)
            return result.stdout.strip()

        git('init', '-q')
        git('config', 'user.name', 'Fixture Reviewer')
        git('config', 'user.email', 'fixture@example.invalid')
        (repo / 'product.py').write_text('answer = 42\n', encoding='utf-8')
        git('add', 'product.py')
        git('commit', '-qm', 'fixture baseline')
        manifest = review_workspace.prepare(argparse.Namespace(
            repo=str(repo), mode='commit', ref='HEAD', role=['executor'],
            include_untracked=[]))
        return repo, manifest, Path(manifest['workspaces'][0]['path'])

    def test_receipt_preserves_literal_argv_and_previous_attempt(self):
        with tempfile.TemporaryDirectory(prefix='review-check-receipt-') as directory:
            root = Path(directory).resolve()
            repo, manifest, cwd = self.make_workspace(root)
            session = Path(manifest['session_dir'])
            evidence = session / 'evidence'
            evidence.mkdir()
            (evidence / 'context.json').write_text(json.dumps({
                'executors': [{'executor': 'X1', 'workspace': str(cwd)}]
            }), encoding='utf-8')
            revision = review_workspace.out(cwd, 'rev-parse', 'HEAD').decode().strip()
            argv = [sys.executable, '-c',
                    'import json,sys; print(json.dumps(sys.argv[1:]))',
                    'a b', '$value', '`tick`']
            output_dir = evidence / 'attempt-1'
            request = {'check_id': 'C001', 'argv': argv, 'cwd': str(cwd),
                       'command': shlex.join(argv), 'revision': revision, 'executor': 'X1',
                       'executor_workspace': str(cwd),
                       'output_dir': str(output_dir)}
            before = {str(path.relative_to(session)): path.read_bytes()
                      for path in session.rglob('*') if path.is_file()}
            receipt = receipts.capture_check(**request)
            stdout_path = output_dir / Path(receipt['stdout']['reference']).name
            self.assertEqual(receipt['argv'], argv)
            self.assertEqual(receipt['exit_code'], 0)
            self.assertEqual(json.loads(stdout_path.read_text(encoding='utf-8')),
                             ['a b', '$value', '`tick`'])
            self.assertEqual(receipt['stdout']['sha256'],
                             hashlib.sha256(stdout_path.read_bytes()).hexdigest())
            with self.assertRaises((ValueError, OSError)):
                receipts.capture_check(**request)
            after = {str(path.relative_to(session)): path.read_bytes()
                     for path in session.rglob('*') if path.is_file()}
            self.assertEqual(after, before | {
                str(path.relative_to(session)): path.read_bytes()
                for path in output_dir.rglob('*') if path.is_file()})

            failed_dir = evidence / 'attempt-2'
            failed_argv = [sys.executable, '-c', 'raise SystemExit(7)']
            failed = receipts.capture_check(
                check_id='C001', argv=failed_argv, command=shlex.join(failed_argv),
                cwd=str(cwd), executor_workspace=str(cwd), revision=revision,
                executor='X1', output_dir=str(failed_dir))
            self.assertEqual(failed['exit_code'], 7)

            request_path = root / 'request.json'
            cli_argv = [sys.executable, '-c', 'raise SystemExit(9)']
            request_path.write_text(json.dumps({
                'check_id': 'C001',
                'argv': cli_argv, 'command': shlex.join(cli_argv),
                'cwd': str(cwd), 'executor_workspace': str(cwd),
                'revision': revision, 'executor': 'X1',
            }), encoding='utf-8')
            cli_dir = evidence / 'attempt-3'
            completed = subprocess.run([
                sys.executable, str(SCRIPTS / 'review_check_receipts.py'), 'run',
                '--request', str(request_path), '--output-dir', str(cli_dir)],
                cwd=root, capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(json.loads(completed.stdout)['receipt']['exit_code'], 9)

            review_workspace.cleanup(argparse.Namespace(manifest=manifest['manifest'], run_dir=None))

    def test_capture_accepts_canonical_command_with_literal_newline_and_tab(self):
        with tempfile.TemporaryDirectory(prefix='review-check-literal-', dir=str(Path.cwd())) as directory:
            root = Path(directory).resolve()
            _, manifest, cwd = self.make_workspace(root)
            session = Path(manifest['session_dir'])
            evidence = session / 'evidence'
            evidence.mkdir()
            (evidence / 'context.json').write_text(json.dumps({
                'executors': [{'executor': 'X1', 'workspace': str(cwd)}]
            }), encoding='utf-8')
            revision = review_workspace.out(cwd, 'rev-parse', 'HEAD').decode().strip()
            argv = [sys.executable, '-c', 'print("first")\nprint("second")', '\tvalue']
            output_dir = evidence / 'attempt-1'

            try:
                receipt = receipts.capture_check(
                    check_id='C001', argv=argv, command=shlex.join(argv), cwd=str(cwd),
                    executor_workspace=str(cwd), revision=revision, executor='X1',
                    output_dir=str(output_dir))
            except ValueError as exc:
                self.fail('capture rejected the canonical literal argv: ' + str(exc))

            self.assertEqual(receipt['argv'], argv)
            self.assertEqual(receipt['exit_code'], 0)
            stdout_path = output_dir / Path(receipt['stdout']['reference']).name
            self.assertEqual(stdout_path.read_text(encoding='utf-8'), 'first\nsecond\n')
            review_workspace.cleanup(argparse.Namespace(manifest=manifest['manifest'], run_dir=None))

    def test_capture_rejects_unowned_workspace_before_process(self):
        with tempfile.TemporaryDirectory(prefix='review-check-unowned-') as directory:
            root = Path(directory).resolve()
            cwd = root / 'cwd'
            output_dir = root / 'evidence' / 'attempt-1'
            cwd.mkdir()
            with patch('review_check_receipts.subprocess.run') as run:
                with self.assertRaises((ValueError, OSError)):
                    receipts.capture_check(check_id='C001', argv=[sys.executable, '-V'],
                                           command=shlex.join([sys.executable, '-V']),
                                           cwd=str(cwd), executor_workspace=str(cwd),
                                           revision='head', executor='X1',
                                           output_dir=str(output_dir))
                run.assert_not_called()

    def test_capture_rejects_command_and_workspace_mismatches_before_execution(self):
        with tempfile.TemporaryDirectory(prefix='review-check-binding-') as directory:
            root = Path(directory).resolve()
            cwd = root / 'registered-workspace'
            other_workspace = root / 'other-workspace'
            marker = root / 'command-ran.txt'
            argv = [sys.executable, '-c',
                    'from pathlib import Path; Path(__import__("sys").argv[1]).write_text("ran")',
                    str(marker)]
            common = {'check_id': 'C001', 'argv': argv, 'cwd': str(cwd),
                      'revision': 'head', 'executor': 'X1',
                      'output_dir': str(root / 'session' / 'evidence' / 'attempt-1')}

            with self.assertRaisesRegex(ValueError, 'canonical display'):
                receipts.capture_check(**common, command='python -V',
                                       executor_workspace=str(cwd))
            self.assertFalse(marker.exists())

            with self.assertRaisesRegex(ValueError, 'registered executor workspace'):
                receipts.capture_check(**common, command=shlex.join(argv),
                                       executor_workspace=str(other_workspace))
            self.assertFalse(marker.exists())

    def test_capture_rejects_executor_bound_to_another_owned_workspace_before_process(self):
        with tempfile.TemporaryDirectory(dir=str(Path.cwd())) as directory:
            root = Path(directory).resolve()
            session = root / 'session'
            evidence = session / 'evidence'
            workspace_a = session / 'executor-a'
            workspace_b = session / 'executor-b'
            repo = root / 'repo'
            for path in (evidence, workspace_a, workspace_b, repo):
                path.mkdir(parents=True, exist_ok=True)
            (evidence / 'context.json').write_text(json.dumps({
                'executors': [{'executor': 'X1', 'workspace': str(workspace_a)}]
            }), encoding='utf-8')
            manifest = {
                'status': 'active', 'mode': 'commit', 'repo': str(repo),
                'workspaces': [{'role': 'executor-a', 'path': str(workspace_a)},
                               {'role': 'executor-b', 'path': str(workspace_b)}],
            }

            def fake_git_out(worktree, *args):
                if args == ('rev-parse', '--show-toplevel'):
                    return (str(worktree) + '\n').encode('utf-8')
                if args == ('rev-parse', 'HEAD'):
                    return b'same-head\n'
                raise AssertionError('unexpected Git query: ' + repr(args))

            with patch('review_workspace.load', return_value=manifest), \
                    patch('review_workspace.out', side_effect=fake_git_out) as git_out, \
                    patch('review_check_receipts.subprocess.run') as run:
                run.return_value = subprocess.CompletedProcess(['python', '-V'], 0)
                with self.assertRaisesRegex(ValueError, 'executor X1 is registered to another workspace'):
                    receipts.capture_check(
                        check_id='C001', argv=[sys.executable, '-V'],
                        command=shlex.join([sys.executable, '-V']),
                        cwd=str(workspace_b), executor_workspace=str(workspace_b),
                        revision='same-head', executor='X1',
                        output_dir=str(evidence / 'attempt-1'))
                git_out.assert_not_called()
                run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
