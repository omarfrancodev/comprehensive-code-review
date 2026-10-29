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

from ccr.contracts.receipts import (
    CHECK_ID, MAX_CONTEXT_BYTES, MAX_REQUEST_BYTES, RECEIPT_FIELDS, SHA256,
    STREAM_FIELDS, _canonical_command_matches, _issue, _text, _timestamp,
    _workspace_identity, is_receipt_reference, receipt_reference,
    validate_receipt, validate_record_receipts,
)
from ccr.execution import workspaces as workspace_ops
from ccr.contracts.checks import purpose_errors

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

    worktree = workspace_ops.no_links(Path(cwd).absolute())
    target = workspace_ops.no_links(Path(output_dir).absolute())
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
    manifest_path = workspace_ops.no_links(session_dir / 'manifest.json')
    manifest = workspace_ops.load(manifest_path)
    if manifest.get('status') != 'active':
        raise ValueError('check capture requires an active owned workspace session')
    workspace_entries = manifest.get('workspaces')
    if not isinstance(workspace_entries, list) or str(worktree) not in {
            str(Path(row['path']).absolute()) for row in workspace_entries
            if isinstance(row, dict) and isinstance(row.get('path'), str)}:
        raise ValueError('cwd is not a workspace owned by the output session')
    context_path = workspace_ops.no_links(session_dir / 'evidence' / 'context.json')
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
    actual_root = workspace_ops.out(worktree, 'rev-parse', '--show-toplevel').decode().strip()
    if (not worktree.is_dir() or os.path.normcase(str(Path(actual_root).resolve()))
            != os.path.normcase(str(worktree.resolve()))):
        raise ValueError('cwd must be the root of the owned Git worktree')
    actual_head = workspace_ops.out(worktree, 'rev-parse', 'HEAD').decode().strip()
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


def _capture_disclosure_inputs(worktree, argv, check_id, revision):
    """Read only literal referenced resources against the preparation-time map."""
    manifest = workspace_ops.load(worktree.parent / 'manifest.json')
    entry = next(row for row in manifest['workspaces'] if Path(row['path']).absolute() == worktree)
    pinned = entry.get('resource_baseline')
    if pinned is None:
        return None, None  # Old owned sessions have no pre-CCR origin proof.
    from ccr.contracts.check_disclosure import canonical, digest, MAX_BYTES
    if digest(canonical(pinned)) != entry.get('resource_baseline_sha256'):
        raise ValueError('pinned resource baseline was changed')
    if len(canonical(pinned)) > MAX_BYTES:
        return None, None
    # The executable can itself be an original project resource. Its byte proof
    # is independent of whether a disclosure adapter can explain its behavior.
    candidates = list(argv)
    tool = ntpath.basename(argv[0]).lower().removesuffix('.exe')
    if tool == 'npm': candidates.append('package.json')
    if tool == 'make': candidates.append('Makefile')
    resources = []; seen = set(); total = 0
    for argument in candidates:
        if argument.startswith('-'):
            continue
        try:
            path = Path(argument)
            path = path if path.is_absolute() else worktree / path
            path = workspace_ops.no_links(path.absolute())
            relative = path.relative_to(worktree).as_posix()
            if relative not in pinned['files'] or relative in seen or not path.is_file():
                continue
            if path.stat().st_size > MAX_BYTES // 4:
                continue
            content = path.read_bytes(); total += len(content)
            if total > MAX_BYTES // 3:
                break
            resource = dict(path=relative, executed_sha256=digest(content), content=content.hex())
            if manifest.get('mode') == 'commit':
                objects = {}
                commit = workspace_ops.out(worktree, 'cat-file', 'commit', manifest['head'])
                objects[manifest['head']] = dict(kind='commit', data=commit.hex())
                oid = commit.split(b'\n', 1)[0].split(b' ', 1)[1].decode()
                for depth, component in enumerate(relative.split('/')):
                    raw = workspace_ops.out(worktree, 'cat-file', 'tree', oid)
                    objects[oid] = dict(kind='tree', data=raw.hex())
                    target_path = '/'.join(relative.split('/')[:depth + 1])
                    oid = workspace_ops.out(worktree, 'rev-parse', manifest['head'] + ':' + target_path).decode().strip()
                blob = workspace_ops.out(worktree, 'cat-file', 'blob', oid)
                objects[oid] = dict(kind='blob', data=blob.hex())
                resource['git_objects'] = objects
            resources.append(resource)
            seen.add(relative)
        except (ValueError, OSError, workspace_ops.ReviewError):
            continue
    observation = dict(check_id=check_id, revision=revision, argv=list(argv), cwd=str(worktree), resources=resources)
    if len(canonical(observation)) > MAX_BYTES:
        observation['resources'] = []
    return pinned, observation

def capture_check(*, check_id: str, purpose: str, argv: list[str], command: str, cwd: str,
                  executor_workspace: str, revision: str, executor: str,
                  output_dir: str) -> dict:
    """Run one explicit argv in an owned workspace and retain a new attempt receipt."""
    errors = purpose_errors(purpose, 'purpose')
    if errors:
        raise ValueError('; '.join(errors))
    worktree, target = _validate_owned_workspace(
        check_id=check_id, argv=argv, command=command, cwd=cwd,
        executor_workspace=executor_workspace, revision=revision,
        executor=executor, output_dir=output_dir)
    prefix = target.name + '-' + check_id
    pinned, disclosure_observation = _capture_disclosure_inputs(worktree, argv, check_id, revision)
    stdout_name, stderr_name = prefix + '-out.log', prefix + '-err.log'
    receipt_name = prefix + '-receipt.json'
    output_reference = 'evidence/' + stdout_name
    error_reference = 'evidence/' + stderr_name
    started_at = _now()
    target.mkdir()
    if pinned is not None:
        from ccr.contracts.check_disclosure import canonical
        (target / (prefix + '-inputs.json')).write_bytes(canonical(pinned))
        (target / (prefix + '-disclosure.json')).write_bytes(canonical(disclosure_observation))
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
            'schema_version': 2,
            'purpose': purpose,
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
            workspace_ops.no_links(target)
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
              'revision', 'executor', 'purpose'}
    if not isinstance(request, dict) or set(request) != fields:
        raise ValueError('check request requires exactly check_id, argv, command, cwd, '
                         'executor_workspace, revision, executor and purpose')
    errors = purpose_errors(request['purpose'], 'purpose')
    if errors:
        raise ValueError('; '.join(errors))
    return request
