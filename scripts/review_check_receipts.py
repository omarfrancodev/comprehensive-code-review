#!/usr/bin/env python3
"""Capture and validate explicit local check commands without shell parsing."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import ntpath
import os
from pathlib import Path
import posixpath
import re
import shlex
import subprocess
import sys
import uuid

import review_references
import review_workspace


RECEIPT_FIELDS = {'schema_version', 'check_id', 'argv', 'cwd', 'revision', 'executor',
                  'started_at', 'finished_at', 'exit_code', 'stdout', 'stderr'}
STREAM_FIELDS = {'reference', 'sha256', 'bytes'}
CHECK_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}')
SHA256 = re.compile(r'[0-9a-f]{64}')
MAX_REQUEST_BYTES = 131072
MAX_CONTEXT_BYTES = 131072


def _issue(field, reference, message, expected):
    return {'code': 'invalid_receipt', 'field': field, 'reference': reference,
            'message': message[:500], 'expected': expected[:500]}


def _text(value, maximum=4000):
    return isinstance(value, str) and bool(value.strip()) and len(value) <= maximum \
        and not any(ord(char) < 32 for char in value)


def _canonical_command_matches(value, argv):
    """Accept literal command controls only when the exact argv renders to them."""
    return isinstance(value, str) and len(value) <= 4000 and value == shlex.join(argv)


def _workspace_identity(value):
    if not isinstance(value, str) or not value.strip():
        return None
    drive, _ = ntpath.splitdrive(value)
    if drive and ntpath.isabs(value):
        return 'windows:' + ntpath.normcase(ntpath.normpath(value))
    if posixpath.isabs(value):
        return 'posix:' + posixpath.normpath(value)
    return None


def _timestamp(value):
    if not isinstance(value, str) or len(value) > 64:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def validate_receipt(receipt: dict, sources: dict[str, bytes], *,
                     check: dict, executors: list[dict]) -> list[review_references.ReferenceIssue]:
    """Validate a captured receipt against supplied bytes and registered identities only."""
    issues = []

    def fail(field, reference, message, expected):
        issues.append(_issue(field, reference, message, expected))

    if not isinstance(receipt, dict) or set(receipt) != RECEIPT_FIELDS:
        return [_issue('receipt', None, 'receipt has missing or unknown fields',
                       'exactly ' + ', '.join(sorted(RECEIPT_FIELDS)))]
    if type(receipt.get('schema_version')) is not int or receipt['schema_version'] != 1:
        fail('schema_version', None, 'unsupported receipt schema', 'schema_version 1')
    check_id = receipt.get('check_id')
    if not isinstance(check_id, str) or CHECK_ID.fullmatch(check_id) is None:
        fail('check_id', None, 'invalid check ID', 'bounded safe check identity')
    valid_argv = (isinstance(receipt.get('argv'), list) and bool(receipt['argv'])
            and len(receipt['argv']) <= 256
            and all(isinstance(item, str) and len(item) <= 8192 and '\0' not in item
                    for item in receipt['argv'])
            and bool(receipt['argv'][0].strip()))
    if not valid_argv:
        fail('argv', None, 'argv must be a bounded literal argument array',
             'nonempty executable and literal string arguments')
    if not _text(receipt.get('cwd')):
        fail('cwd', None, 'cwd must be a nonempty observed workspace path', 'bounded path text')
    if not _text(receipt.get('revision')):
        fail('revision', None, 'revision must be observed nonempty text', 'bounded revision identity')
    if not _text(receipt.get('executor')):
        fail('executor', None, 'executor must be a registered nonempty identity', 'bounded executor ID')

    started = _timestamp(receipt.get('started_at'))
    if started is None:
        fail('started_at', None, 'started_at must be a timezone-aware observation',
             'an ISO-8601 timestamp with offset')
    finished_value = receipt.get('finished_at')
    finished = _timestamp(finished_value) if finished_value is not None else None
    if finished_value is not None and finished is None:
        fail('finished_at', None, 'finished_at must be a timezone-aware observation or null',
             'an ISO-8601 timestamp with offset or null')
    exit_code = receipt.get('exit_code')
    if exit_code is not None and (type(exit_code) is not int or abs(exit_code) > 2147483647):
        fail('exit_code', None, 'exit_code must be an observed integer or null', 'integer or null')
    if started is not None and finished is not None and finished < started:
        fail('finished_at', None, 'finished_at precedes started_at', 'ordered observed timestamps')
    if (exit_code is None) != (finished is None):
        fail('exit_code', None, 'unfinished process requires null exit_code and finished_at',
             'both completion fields present or both null')

    for stream_name in ('stdout', 'stderr'):
        stream = receipt.get(stream_name)
        field = stream_name
        if not isinstance(stream, dict) or set(stream) != STREAM_FIELDS:
            fail(field, None, 'stream descriptor has missing or unknown fields',
                 'exact reference, sha256 and bytes fields')
            continue
        reference = stream.get('reference')
        try:
            path, fragment = review_references.parse_reference(reference, field=field)
            if fragment is not None or not path.startswith('evidence/'):
                raise ValueError('stream reference must be a flat local evidence file')
        except (TypeError, ValueError) as exc:
            fail(field + '.reference', reference if isinstance(reference, str) else None,
                 str(exc), 'a flat evidence file reference without a fragment')
            continue
        stream_digest = stream.get('sha256')
        if not isinstance(stream_digest, str) or not SHA256.fullmatch(stream_digest):
            fail(field + '.sha256', reference, 'stream digest must be lowercase SHA-256',
                 '64 lowercase hexadecimal characters')
        if type(stream.get('bytes')) is not int or stream['bytes'] < 0:
            fail(field + '.bytes', reference, 'stream byte count must be a nonnegative integer',
                 'nonnegative integer')
        data = sources.get(path) if isinstance(sources, dict) else None
        if not isinstance(data, bytes):
            fail(field + '.reference', reference, 'selected stream bytes are missing', path)
        else:
            if isinstance(stream_digest, str) and SHA256.fullmatch(stream_digest) \
                    and hashlib.sha256(data).hexdigest() != stream_digest:
                fail(field + '.sha256', reference, 'selected stream digest differs from receipt',
                     stream_digest)
            if type(stream.get('bytes')) is int and len(data) != stream['bytes']:
                fail(field + '.bytes', reference, 'selected stream byte count differs from receipt',
                     str(stream['bytes']))
    stdout_row, stderr_row = receipt.get('stdout'), receipt.get('stderr')
    if (isinstance(stdout_row, dict) and isinstance(stderr_row, dict)
            and isinstance(stdout_row.get('reference'), str)
            and stdout_row.get('reference') == stderr_row.get('reference')):
        fail('stderr.reference', stderr_row.get('reference'),
             'stdout and stderr must use distinct evidence files', 'a distinct flat stream reference')

    if not isinstance(check, dict):
        fail('check', None, 'check binding must be an object', 'the source check object')
    else:
        if check.get('id') != check_id:
            fail('check_id', None, 'receipt check ID differs from the source check', str(check.get('id')))
        if check.get('revision') != receipt.get('revision'):
            fail('revision', None, 'receipt revision differs from the source check', str(check.get('revision')))
        if (not valid_argv
                or not _canonical_command_matches(check.get('command'), receipt['argv'])):
            fail('command', None, 'source check command differs from the receipt argv',
                 'the source check command matching receipt argv')
        execution = check.get('execution')
        if (not isinstance(execution, dict) or execution.get('kind') != 'local'
                or execution.get('executor') != receipt.get('executor')):
            fail('executor', None, 'receipt must bind to the source local check executor',
                 'matching local check execution executor')
        status = check.get('status')
        if status not in ('passed', 'failed', 'blocked', 'not_run'):
            fail('check.status', None, 'source check has an unsupported status',
                 'passed, failed, blocked or not_run')
        elif exit_code is None:
            if status in ('passed', 'failed'):
                fail('exit_code', None, 'unfinished command cannot accredit passed or failed',
                     'observed exit code for a completed check')
        elif status == 'passed' and exit_code != 0:
            fail('exit_code', None, 'passed check has a nonzero exit code', 'exit code 0')
        elif status == 'failed' and exit_code == 0:
            fail('exit_code', None, 'failed check has a zero exit code', 'nonzero exit code')
        elif status in ('blocked', 'not_run'):
            fail('exit_code', None, 'blocked or not_run check cannot claim a completed command', 'null')

    if not isinstance(executors, list):
        fail('executor', None, 'executors must be an array', 'registered executor entries')
    else:
        matching = [row for row in executors if isinstance(row, dict)
                    and row.get('executor') == receipt.get('executor')]
        if len(matching) != 1:
            fail('executor', None, 'receipt executor is not uniquely registered', 'one matching executor')
        else:
            executor = matching[0]
            expected_revision = executor.get('snapshot') or executor.get('revision')
            if receipt.get('revision') != expected_revision:
                fail('revision', None, 'receipt revision differs from registered executor',
                     str(expected_revision))
            if (_workspace_identity(receipt.get('cwd')) is None
                    or _workspace_identity(receipt.get('cwd'))
                    != _workspace_identity(executor.get('workspace'))):
                fail('cwd', None, 'receipt cwd differs from the registered executor workspace',
                     'the registered executor workspace')

    return issues


def receipt_reference(check_id: str, output_dir: str | Path) -> str:
    """Return the flat archive reference used for this attempt's receipt."""
    if not isinstance(check_id, str) or CHECK_ID.fullmatch(check_id) is None:
        raise ValueError('check_id must be a bounded safe check identity')
    name = Path(output_dir).name
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}', name):
        raise ValueError('output directory name must be a bounded safe attempt identity')
    return f'evidence/{name}-{check_id}-receipt.json'


def is_receipt_reference(reference, check_id) -> bool:
    """Recognize the explicit flat receipt filename convention for one check."""
    if not isinstance(reference, str) or not isinstance(check_id, str) \
            or CHECK_ID.fullmatch(check_id) is None:
        return False
    return reference.startswith('evidence/') and reference.endswith('-' + check_id + '-receipt.json')


def validate_record_receipts(record: dict, sources: dict[str, bytes],
                             executors: list[dict]) -> list[review_references.ReferenceIssue]:
    """Validate only checks that explicitly reference a named receipt artifact."""
    if not isinstance(record, dict) or record.get('schema_version') not in (9, 10):
        return []
    checks = record.get('checks')
    if not isinstance(checks, list):
        return []
    issues = []
    for number, check in enumerate(checks):
        if not isinstance(check, dict):
            continue
        reference = check.get('reference')
        if not is_receipt_reference(reference, check.get('id')):
            continue
        field = f'checks[{number}].reference'
        try:
            path, fragment = review_references.parse_reference(reference, field=field)
            if fragment is not None or not path.startswith('evidence/'):
                raise ValueError('receipt reference must identify a flat evidence file without a fragment')
        except (TypeError, ValueError) as exc:
            issues.append(_issue(field, reference, str(exc), 'a flat local check receipt reference'))
            continue
        data = sources.get(path) if isinstance(sources, dict) else None
        if not isinstance(data, bytes):
            issues.append(_issue(field, reference, 'selected check receipt bytes are missing', path))
            continue
        try:
            receipt = json.loads(data.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError):
            issues.append(_issue(field, reference, 'selected check receipt is not UTF-8 JSON',
                                 'a schema 1 check receipt'))
            continue
        issues.extend(validate_receipt(receipt, sources, check=check, executors=executors))
    return issues[:100]


def _validate_owned_workspace(*, check_id, argv, command, cwd, executor_workspace,
                              revision, executor, output_dir):
    if not isinstance(check_id, str) or CHECK_ID.fullmatch(check_id) is None:
        raise ValueError('check_id must be a bounded safe check identity')
    if not isinstance(argv, list) or not argv or len(argv) > 256 or any(
            not isinstance(item, str) or len(item) > 8192 or '\0' in item for item in argv):
        raise ValueError('argv must be a bounded literal argument array')
    if not argv[0].strip():
        raise ValueError('argv[0] must name the explicit executable')
    if not _canonical_command_matches(command, argv):
        raise ValueError('command must be the canonical display of the exact argv')
    if (_workspace_identity(cwd) is None
            or _workspace_identity(cwd) != _workspace_identity(executor_workspace)):
        raise ValueError('cwd must match the registered executor workspace')
    if not _text(revision) or not _text(executor):
        raise ValueError('revision and executor must be observed nonempty text')

    worktree = review_workspace.no_links(Path(cwd).absolute())
    target = review_workspace.no_links(Path(output_dir).absolute())
    evidence_dir = target.parent
    if evidence_dir.name != 'evidence':
        raise ValueError('output_dir must be a new direct child of the owned session evidence directory')
    if not evidence_dir.is_dir():
        raise ValueError('owned session evidence directory is missing')
    if target.exists() or target.is_symlink():
        raise FileExistsError('output_dir already exists; preserve this attempt and choose a new directory')
    if target.name in {'', '.', '..'} or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}', target.name):
        raise ValueError('output_dir name must be a bounded safe attempt identity')
    session_dir = evidence_dir.parent
    manifest_path = review_workspace.no_links(session_dir / 'manifest.json')
    manifest = review_workspace.load(manifest_path)
    if manifest.get('status') != 'active':
        raise ValueError('check capture requires an active owned workspace session')
    workspace_entries = manifest.get('workspaces')
    if not isinstance(workspace_entries, list) or str(worktree) not in {
            str(Path(row['path']).absolute()) for row in workspace_entries
            if isinstance(row, dict) and isinstance(row.get('path'), str)}:
        raise ValueError('cwd is not a workspace owned by the output session')
    context_path = review_workspace.no_links(session_dir / 'evidence' / 'context.json')
    if not context_path.is_file():
        raise ValueError('registered executor context is missing from the owned session')
    try:
        with context_path.open('rb') as handle:
            context_bytes = handle.read(MAX_CONTEXT_BYTES + 1)
        if len(context_bytes) > MAX_CONTEXT_BYTES:
            raise ValueError('registered executor context exceeds the bounded size')
        context = json.loads(context_bytes.decode('utf-8'))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError('registered executor context is invalid UTF-8 JSON') from exc
    executors = context.get('executors') if isinstance(context, dict) else None
    if not isinstance(executors, list):
        raise ValueError('registered executor context must contain an executors array')
    matching = [row for row in executors if isinstance(row, dict)
                and row.get('executor') == executor]
    if len(matching) != 1:
        raise ValueError('executor must be uniquely registered in the owned session context')
    registered_workspace = matching[0].get('workspace')
    if (_workspace_identity(registered_workspace) is None
            or _workspace_identity(registered_workspace) != _workspace_identity(cwd)
            or _workspace_identity(registered_workspace) != _workspace_identity(executor_workspace)):
        raise ValueError('executor ' + executor + ' is registered to another workspace')
    actual_root = review_workspace.out(worktree, 'rev-parse', '--show-toplevel').decode().strip()
    if (not worktree.is_dir() or os.path.normcase(str(Path(actual_root).resolve()))
            != os.path.normcase(str(worktree.resolve()))):
        raise ValueError('cwd must be the root of the owned Git worktree')
    actual_head = review_workspace.out(worktree, 'rev-parse', 'HEAD').decode().strip()
    if manifest.get('mode') == 'commit' and revision != actual_head:
        raise ValueError('revision differs from the owned commit workspace HEAD')
    if not Path(manifest['repo']).is_dir():
        raise ValueError('owned workspace repository is unavailable')
    return worktree, target


def _now():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')


def _json_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf-8') + b'\n'


def _file_identity(path):
    digest = hashlib.sha256()
    size = 0
    with Path(path).open('rb') as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def capture_check(*, check_id: str, argv: list[str], command: str, cwd: str,
                  executor_workspace: str, revision: str, executor: str,
                  output_dir: str) -> dict:
    """Run one explicit argv in an owned workspace and retain a new attempt receipt."""
    worktree, target = _validate_owned_workspace(
        check_id=check_id, argv=argv, command=command, cwd=cwd,
        executor_workspace=executor_workspace, revision=revision,
        executor=executor, output_dir=output_dir)
    prefix = target.name + '-' + check_id
    stdout_name, stderr_name = prefix + '-out.log', prefix + '-err.log'
    receipt_name = prefix + '-receipt.json'
    output_reference = 'evidence/' + stdout_name
    error_reference = 'evidence/' + stderr_name
    started_at = _now()
    target.mkdir()
    exit_code = None
    finished_at = None
    try:
        with (target / stdout_name).open('xb') as stdout, (target / stderr_name).open('xb') as stderr:
            try:
                completed = subprocess.run(argv, cwd=str(worktree), stdout=stdout, stderr=stderr,
                                           shell=False, check=False)
                exit_code = completed.returncode
                finished_at = _now()
            except OSError:
                # No process result was observed; preserve the attempt as incomplete evidence.
                pass
        stdout_digest, stdout_size = _file_identity(target / stdout_name)
        stderr_digest, stderr_size = _file_identity(target / stderr_name)
        receipt = {
            'schema_version': 1,
            'check_id': check_id,
            'argv': list(argv),
            'cwd': str(worktree),
            'revision': revision,
            'executor': executor,
            'started_at': started_at,
            'finished_at': finished_at,
            'exit_code': exit_code,
            'stdout': {'reference': output_reference,
                       'sha256': stdout_digest, 'bytes': stdout_size},
            'stderr': {'reference': error_reference,
                       'sha256': stderr_digest, 'bytes': stderr_size},
        }
        receipt_path = target / receipt_name
        temporary = target / ('.receipt-' + uuid.uuid4().hex + '.tmp')
        try:
            with temporary.open('xb') as handle:
                handle.write(_json_bytes(receipt))
                handle.flush()
                os.fsync(handle.fileno())
            review_workspace.no_links(target)
            os.rename(temporary, receipt_path)
        finally:
            temporary.unlink(missing_ok=True)
        return receipt
    except Exception:
        # The unique attempt directory and any partial bytes stay available for inspection.
        raise


def _read_request(path):
    source = Path(path)
    if source.stat().st_size > MAX_REQUEST_BYTES:
        raise ValueError('check request exceeds the bounded size')
    try:
        request = json.loads(source.read_text(encoding='utf-8'))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError('check request is not readable UTF-8 JSON') from exc
    fields = {'check_id', 'argv', 'command', 'cwd', 'executor_workspace',
              'revision', 'executor'}
    if not isinstance(request, dict) or set(request) != fields:
        raise ValueError('check request requires exactly check_id, argv, command, cwd, '
                         'executor_workspace, revision and executor')
    return request


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    run = commands.add_parser('run', help='Run one explicit local check and write a new receipt')
    run.add_argument('--request', required=True)
    run.add_argument('--output-dir', required=True)
    args = parser.parse_args(argv)
    try:
        request = _read_request(args.request)
        receipt = capture_check(**request, output_dir=args.output_dir)
        receipt_path = Path(args.output_dir).absolute() / Path(receipt_reference(
            receipt['check_id'], args.output_dir)).name
        print(json.dumps({'status': 'captured', 'receipt_path': str(receipt_path),
                          'receipt': receipt}, ensure_ascii=False, allow_nan=False))
        # A valid capture returns zero even when the check itself returned nonzero.
        return 0
    except (OSError, ValueError, TypeError, KeyError, review_workspace.ReviewError,
            subprocess.SubprocessError) as exc:
        print(json.dumps({'status': 'error', 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
