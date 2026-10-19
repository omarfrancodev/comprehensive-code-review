#!/usr/bin/env python3
"""Prepare, register, validate, retain and close durable review evidence (Python 3.10+).

Measurement inputs are an explicit caller assertion of disjoint executions. Duplicate
paths and execution_id values are refused; semantic overlap is not detectable here.
Temporary-path authority and ownership belong to the coordinator. This helper never
deletes registered resources and must not be used to infer disposal authority.
"""
import argparse
import copy
from contextlib import contextmanager, ExitStack
from datetime import datetime, timezone
from functools import wraps
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
from urllib.parse import urlsplit
import uuid

import review_contract
import review_metrics
import review_trace
import review_harness
import review_profiles
import review_inputs
import review_restart
import review_resource_claims
import review_layout
from review_run_lock import CoordinationError, LockConflictError, run_locks
from review_execution import validate_execution_sources
from review_check_provenance import validate_check_sources


FILES = ('review.json', 'informe.md')
OPTIONAL_FILES = ('measurements.json',)
TRACE_FILES = (review_trace.NAME, 'handoff.md')
MARKER = '.review-ownership.json'
ARCHIVE_SCHEMA_VERSION = review_layout.ARCHIVE_SCHEMA_VERSION
TRACE_ARCHIVE_SCHEMAS = frozenset({4, 5, 6, 7, 8})
PENDING_CONTEXT_LIMIT = 131072
CHECKPOINT_EVIDENCE_COUNT_LIMIT = 64
CHECKPOINT_METADATA_LIMIT = 16 * 1024 * 1024
CHECKPOINT_EVIDENCE_LIMIT = 64 * 1024 * 1024
CHECKPOINT_HASH = re.compile(r'[0-9a-f]{64}')
SCOPE_FIELDS = {'repository', 'mode', 'base', 'head', 'snapshot', 'target', 'reference'}
MEASUREMENT_FIELDS = set(review_metrics.COUNTERS) | {
    'usage', 'execution_id', 'run_id', 'input_ids', 'input_id', 'revision', 'snapshot',
    'phase', 'role', 'model', 'harness', 'started_at', 'finished_at', 'elapsed_seconds',
    'executor_invocations', 'status', 'usage_status', 'usage_error', 'unavailable_reason',
    'stdout_bytes', 'stderr_bytes', 'exit_code', 'timed_out', 'workspace', 'output_dir'}


def safe_path(value):
    """Reject traversal and every existing link/reparse component before resolving."""
    path = Path(value)
    if not path.is_absolute() or '..' in path.parts:
        raise ValueError('an absolute path without traversal is required: ' + str(path))
    for component in path.parts[1:]:
        if any(char in component for char in '<>:"|?*') or component.endswith((' ', '.')):
            raise ValueError('unsafe path component: ' + component)
    for current in (path, *path.parents):
        try:
            info = current.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('links/reparse points are not allowed: ' + str(current))
    return path.resolve()


def _contains(parent, child):
    return child == parent or parent in child.parents


def _json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n').encode('utf-8')


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _locked_run(function=None, *, when=None):
    """Serialize durable mutations; read-only validation stays lock-free."""
    def decorate(target):
        @wraps(target)
        def wrapped(run_dir, *args, **kwargs):
            if when is not None and not when(args, kwargs):
                return target(run_dir, *args, **kwargs)
            with _owned_run_locks([run_dir]):
                return target(run_dir, *args, **kwargs)
        return wrapped
    return decorate(function) if function is not None else decorate


@contextmanager
def _owned_run_locks(run_dirs, *, reservation=None):
    """Verify each run before creating lock files, then revalidate under lock."""
    paths = list(run_dirs)
    if not paths:
        raise ValueError('at least one owned review run is required')
    if reservation is not None:
        raise ValueError('restart reservations are not available for ordinary run mutations')
    for path in paths:
        _, manifest, _ = _load_run(path)
        _assert_not_restart_abandoned(manifest)
        if _active_restart_operation(path, manifest) is not None:
            raise ValueError('a durable restart is pending; retry that exact restart or recover it first')
    with run_locks(paths):
        loaded = [_load_run(path) for path in paths]
        for path, (_, manifest, _) in zip(paths, loaded):
            _assert_not_restart_abandoned(manifest)
            if _active_restart_operation(path, manifest) is not None:
                raise ValueError('a durable restart is pending; retry that exact restart or recover it first')
        yield loaded


def _restart_local_dir(source_run, manifest):
    source = safe_path(source_run)
    key = manifest.get('run_id') or 'legacy-' + _digest(
        _json_bytes({'run_dir': str(source), 'owner_id': manifest['owner_id']}))[:32]
    directory = source.parent / '.restart-intents' / key
    return safe_path(directory)


def _restart_intent_path(source_run, source_manifest, request):
    """Return a stable local path keyed by source identity and normalized request."""
    source = safe_path(source_run)
    digest = review_restart._sha(review_restart._request_identity(request))
    return _restart_local_dir(source, source_manifest) / (digest + '.json')


def _active_restart_paths(source_run, source_manifest):
    directory = _restart_local_dir(source_run, source_manifest)
    return directory / 'active.json', directory / 'active.owner.json'


def _restart_completion_path(intent_path):
    return Path(intent_path).with_suffix('.complete.json')


def _restart_abandonment_path(intent_path):
    return Path(intent_path).with_suffix('.abandoned.json')


def _validate_restart_abandonment(intent_path, intent):
    path = _restart_abandonment_path(intent_path)
    if not path.exists():
        return None
    receipt = read_json(path)
    return _validate_restart_abandonment_value(receipt, intent)


def _validate_restart_abandonment_value(receipt, intent):
    fields = {'schema_version', 'operation_id', 'source_run', 'source_owner_id', 'intent_sha256',
              'successor_run_dir', 'authority', 'controller', 'reason', 'recorded_at', 'receipt_sha256'}
    if not isinstance(receipt, dict) or set(receipt) != fields:
        raise ValueError('restart abandonment receipt has an invalid shape')
    unsigned = {key: value for key, value in receipt.items() if key != 'receipt_sha256'}
    if (receipt['schema_version'] != 1 or receipt['receipt_sha256'] != _digest(_json_bytes(unsigned))
            or receipt['operation_id'] != intent['operation_id']
            or receipt['source_run'] != intent['source']['run_dir']
            or receipt['source_owner_id'] != intent['source']['owner_id']
            or receipt['intent_sha256'] != intent['intent_sha256']
            or receipt['successor_run_dir'] != intent['successor']['run_dir']):
        raise ValueError('restart abandonment receipt differs from its exact intent')
    review_resource_claims._authority(receipt['authority'])
    _controller(receipt['controller'], intent['request']['controller']['identity'])
    review_restart._bounded_text(receipt['reason'], 'abandonment reason')
    return receipt


def _assert_not_restart_abandoned(manifest):
    receipt = manifest.get('restart_abandonment')
    if receipt is not None:
        raise ValueError('restart successor was explicitly abandoned; inspect its source: ' + receipt['source_run'])


def _validate_terminal_abandonment(run, manifest):
    receipt = manifest.get('restart_abandonment')
    if receipt is None:
        return
    operation = manifest.get('restart_operation')
    if not isinstance(operation, dict):
        raise ValueError('abandoned successor has no reserved restart identity')
    bound_intent = {'operation_id': operation['operation_id'], 'intent_sha256': operation['intent_sha256'],
        'source': {'run_dir': operation['source_run'], 'owner_id': operation['source_owner_id']},
        'successor': {'run_dir': str(run)}, 'request': {'controller': manifest['controller']}}
    _validate_restart_abandonment_value(receipt, bound_intent)
    if (manifest.get('state') != 'prepared' or manifest.get('retained') is not False
            or manifest['operation'] != {'disposition': 'blocked', 'reason': receipt['reason'],
                'source': 'abandon-restart', 'phase': 'prepare', 'successor': None}
            or len(manifest['profile_history']) != 1
            or set(manifest.get('hashes', {})) != {review_trace.NAME}
            or any(manifest.get(key) for key in ('resource_claims', 'resource_transfers', 'resource_transfer',
                'resource_cleanup', 'cleanup_receipts', 'executors', 'assignment_registry', 'checkpoint',
                'checkpoint_transaction', 'pending_hashes', 'planned_hashes'))):
        raise ValueError('abandoned successor contains work or resource ownership')


def _restart_source_identity(run, manifest):
    return {key: manifest.get(key) if key != 'run_dir' else str(run)
            for key in review_restart.SOURCE_FIELDS}


def _validate_restart_completion(path, intent):
    try:
        value = read_json(path)
    except FileNotFoundError:
        return None
    fields = {'schema_version', 'operation_id', 'source_run', 'source_owner_id',
              'intent_sha256', 'successor_run_dir', 'successor_owner_id', 'receipt_sha256'}
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError('restart completion receipt has an invalid shape')
    unsigned = {key: item for key, item in value.items() if key != 'receipt_sha256'}
    if (value['schema_version'] != 1 or value['receipt_sha256'] != _digest(_json_bytes(unsigned))
            or value['operation_id'] != intent['operation_id']
            or value['source_run'] != intent['source']['run_dir']
            or value['source_owner_id'] != intent['source']['owner_id']
            or value['intent_sha256'] != intent['intent_sha256']
            or value['successor_run_dir'] != intent['successor']['run_dir']
            or value['successor_owner_id'] != intent['successor']['owner_id']):
        raise ValueError('restart completion receipt differs from its reserved operation')
    return value


def _read_restart_intent(path, source_run, source_manifest):
    value = read_json(path)
    errors = review_restart.validate_restart_intent(value)
    if errors:
        raise ValueError('; '.join(errors))
    if value['source'] != _restart_source_identity(source_run, source_manifest):
        raise ValueError('restart intent belongs to a different source owner')
    if safe_path(path) != _restart_intent_path(source_run, source_manifest, value['request']):
        raise ValueError('restart intent path differs from its source/request identity')
    return value


def _active_restart_operation(source_run, source_manifest, *, include_abandoned=False):
    """Read the one source-bound active descriptor; never scan other reviews."""
    active_path, owner_path = _active_restart_paths(source_run, source_manifest)
    if not active_path.exists() and not owner_path.exists():
        return None
    if not owner_path.exists():
        raise ValueError('restart active descriptor has no ownership transition record')
    owner = read_json(owner_path)
    fields = {'schema_version', 'source_run', 'source_owner_id', 'active_sha256',
              'previous_active_sha256', 'active_descriptor', 'previous_descriptor'}
    if (not isinstance(owner, dict) or set(owner) != fields or owner['schema_version'] != 1
            or owner['source_run'] != str(safe_path(source_run))
            or owner['source_owner_id'] != source_manifest.get('owner_id')):
        raise ValueError('restart active descriptor ownership differs from its source')
    descriptor = owner['active_descriptor']
    previous = owner['previous_descriptor']
    if not isinstance(descriptor, dict):
        raise ValueError('restart active descriptor transition is invalid')
    if active_path.exists():
        raw = read_json(active_path)
        digest = _digest(_json_bytes(raw))
        if digest == owner['active_sha256']:
            descriptor = raw
        elif digest == owner.get('previous_active_sha256') and isinstance(previous, dict):
            descriptor = raw
        else:
            raise ValueError('restart active descriptor bytes are outside the authorized transition')
    if (descriptor.get('schema_version') != 1 or descriptor.get('source_run') != str(safe_path(source_run))
            or descriptor.get('source_owner_id') != source_manifest.get('owner_id')
            or descriptor.get('status') not in {'pending', 'complete'}):
        raise ValueError('restart active descriptor is invalid')
    intent = descriptor.get('intent')
    errors = review_restart.validate_restart_intent(intent)
    if errors:
        raise ValueError('; '.join(errors))
    if (descriptor.get('operation_id') != intent['operation_id']
            or descriptor.get('intent_path') != str(_restart_intent_path(source_run, source_manifest, intent['request']))
            or descriptor.get('intent_sha256') != intent['intent_sha256']
            or descriptor.get('successor_run_dir') != intent['successor']['run_dir']):
        raise ValueError('restart active descriptor differs from its intent')
    intent_path = Path(descriptor['intent_path'])
    if intent_path.exists():
        stored = _read_restart_intent(intent_path, source_run, source_manifest)
        if stored != intent:
            raise ValueError('restart active intent differs from its immutable request file')
    if descriptor['status'] == 'complete' or _validate_restart_completion(
            _restart_completion_path(intent_path), intent) is not None:
        return None
    if _validate_restart_abandonment(intent_path, intent) is not None:
        return descriptor if include_abandoned else None
    return descriptor


def _write_restart_intent(path, intent, source_run, source_manifest):
    errors = review_restart.validate_restart_intent(intent)
    if errors:
        raise ValueError('; '.join(errors))
    if path.exists():
        existing = _read_restart_intent(path, source_run, source_manifest)
        if existing != intent:
            raise ValueError('restart intent already exists with different reserved bytes')
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, _json_bytes(intent))


def _restart_recovery_source(run, manifest):
    """Identify the exact source lock that owns a successor's pending restart."""
    operation = manifest.get('restart_operation')
    if not isinstance(operation, dict) or manifest.get('state') == 'complete':
        return None
    try:
        source, source_manifest, _ = _load_run(operation['source_run'])
        _verify_files(source, source_manifest, allow_checkpoint_transaction=True,
                      allow_resource_transfer=True, allow_pending_trace=True)
        active = _active_restart_operation(source, source_manifest, include_abandoned=True)
    except (OSError, ValueError, TypeError, KeyError):
        # Historical availability does not establish this successor's integrity.
        # Its own pending transfers, trace and hashes remain subject to local gates.
        return None
    if active is None or active['operation_id'] != operation['operation_id']:
        return None
    if (active['successor_run_dir'] != str(run)
            or active['intent_sha256'] != operation['intent_sha256']):
        raise ValueError('successor restart identity differs from its active source operation')
    result = {'run_dir': str(source), 'operation_id': active['operation_id']}
    resource_exit = _restart_resource_exit(source, source_manifest, active)
    if resource_exit is not None:
        result['resource_exit'] = resource_exit
    return result


def _write_active_restart(source_run, source_manifest, intent_path, intent, *, status='pending'):
    active_path, owner_path = _active_restart_paths(source_run, source_manifest)
    descriptor = {'schema_version': 1, 'source_run': str(safe_path(source_run)),
                  'source_owner_id': source_manifest['owner_id'], 'operation_id': intent['operation_id'],
                  'intent_path': str(intent_path), 'intent_sha256': intent['intent_sha256'],
                  'successor_run_dir': intent['successor']['run_dir'], 'status': status,
                  'intent': copy.deepcopy(intent)}
    previous = None
    previous_digest = None
    if active_path.exists():
        previous = read_json(active_path)
        previous_digest = _digest(_json_bytes(previous))
    transition = {'schema_version': 1, 'source_run': str(safe_path(source_run)),
                  'source_owner_id': source_manifest['owner_id'],
                  'active_sha256': _digest(_json_bytes(descriptor)),
                  'previous_active_sha256': previous_digest,
                  'active_descriptor': descriptor, 'previous_descriptor': previous}
    owner_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(owner_path, _json_bytes(transition))
    atomic_write(active_path, _json_bytes(descriptor))
    final = dict(transition, previous_active_sha256=None, previous_descriptor=None)
    atomic_write(owner_path, _json_bytes(final))


def _retire_active_restart(intent_path, intent, source_run, source_manifest):
    active_path, owner_path = _active_restart_paths(source_run, source_manifest)
    _write_active_restart(source_run, source_manifest, intent_path, intent, status='complete')
    active_path.unlink(missing_ok=True)
    owner_path.unlink(missing_ok=True)


def _retire_completed_descriptor_if_present(intent_path, intent, source_run, source_manifest):
    active_path, owner_path = _active_restart_paths(source_run, source_manifest)
    if active_path.exists() or owner_path.exists():
        _retire_active_restart(intent_path, intent, source_run, source_manifest)


def _record_restart_completion(intent_path, intent):
    path = _restart_completion_path(intent_path)
    fields = {'schema_version': 1, 'operation_id': intent['operation_id'],
              'source_run': intent['source']['run_dir'], 'source_owner_id': intent['source']['owner_id'],
              'intent_sha256': intent['intent_sha256'], 'successor_run_dir': intent['successor']['run_dir'],
              'successor_owner_id': intent['successor']['owner_id']}
    value = dict(fields, receipt_sha256=_digest(_json_bytes(fields)))
    if path.exists():
        _validate_restart_completion(path, intent)
        return
    atomic_write(path, _json_bytes(value))


@contextmanager
def _restart_lock(source_path, *, timeout=30.0):
    """Retry only transient cross-process lock conflicts, then re-read the intent."""
    import time
    _, source_manifest, _ = _load_run(source_path)  # Ownership gate before lock-directory creation.
    _assert_not_restart_abandoned(source_manifest)
    deadline = time.monotonic() + timeout
    lock = None
    while True:
        lock = run_locks([source_path])
        try:
            lock.__enter__()
            break
        except LockConflictError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.05)
    try:
        _, source_manifest, _ = _load_run(source_path)
        _assert_not_restart_abandoned(source_manifest)
        yield
    finally:
        lock.__exit__(None, None, None)


def read_bounded(path, limit):
    """Read a regular file within a byte budget, including growth after stat."""
    if type(limit) is not int or limit < 0:
        raise ValueError('read limit must be a nonnegative integer')
    path = safe_path(path)
    try:
        with path.open('rb') as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode):
                raise ValueError('bounded input must be a regular file: ' + str(path))
            if info.st_size > limit:
                raise ValueError('input exceeds the ' + str(limit) + '-byte limit: ' + str(path))
            data = stream.read(limit + 1)
    except FileNotFoundError:
        raise
    if len(data) > limit:
        raise ValueError('input exceeds the ' + str(limit) + '-byte limit: ' + str(path))
    return data


def read_json(path, *, max_bytes=None):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate JSON key: ' + key)
            result[key] = value
        return result
    def invalid_constant(value):
        raise ValueError('nonfinite JSON number: ' + value)
    if max_bytes is None:
        data = safe_path(path).read_bytes()
    else:
        data = read_bounded(path, max_bytes)
    return json.loads(data.decode('utf-8'), object_pairs_hook=unique,
                      parse_constant=invalid_constant)


def atomic_write(path, data, *, staging_path=None):
    """Replace one validated path atomically, using an exclusive local staging file."""
    path = safe_path(path)
    staging = safe_path(staging_path) if staging_path is not None else path.parent / (
        '.' + path.name + '.' + uuid.uuid4().hex + '.tmp')
    if staging.parent != path.parent or staging == path:
        raise ValueError('atomic staging file must be a sibling of its destination')
    created = False
    failure = None
    try:
        with staging.open('xb') as stream:
            created = True
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        safe_path(path)
        os.replace(staging, path)
    except BaseException as exc:
        failure = exc
        raise
    finally:
        if created:
            try:
                staging.unlink(missing_ok=True)
            except OSError as cleanup_error:
                detail = 'atomic write staging remains at ' + str(staging) + ': ' + str(cleanup_error)
                if failure is None:
                    raise OSError(detail) from cleanup_error
                failure.args = (str(failure) + '; ' + detail,)


def _git(repo, *args, optional=False):
    structural = {'GIT_DIR', 'GIT_WORK_TREE', 'GIT_COMMON_DIR', 'GIT_INDEX_FILE',
                  'GIT_OBJECT_DIRECTORY', 'GIT_ALTERNATE_OBJECT_DIRECTORIES', 'GIT_NAMESPACE',
                  'GIT_IMPLICIT_WORK_TREE', 'GIT_PREFIX', 'GIT_GRAFT_FILE', 'GIT_SHALLOW_FILE',
                  'GIT_CONFIG', 'GIT_CONFIG_PARAMETERS', 'GIT_CONFIG_COUNT', 'GIT_REPLACE_REF_BASE'}
    environment = {key: value for key, value in os.environ.items() if key.upper() not in structural
                   and not key.upper().startswith(('GIT_CONFIG_KEY_', 'GIT_CONFIG_VALUE_'))}
    environment.update(GIT_OPTIONAL_LOCKS='0', GIT_TERMINAL_PROMPT='0', GIT_NO_REPLACE_OBJECTS='1')
    process = subprocess.run(['git', '-c', 'safe.directory=' + str(repo), *args], cwd=repo,
                             env=environment, capture_output=True, text=True,
                             encoding='utf-8', errors='replace', check=False)
    if process.returncode:
        if optional:
            return None
        raise ValueError('repository cannot be resolved by Git')
    return process.stdout.strip()


def repository_identity(repo):
    """Use normalized origin, or shared common directory for absent/relative origins."""
    repo = safe_path(repo)
    common = _git(repo, 'rev-parse', '--git-common-dir')
    common_path = Path(common)
    if not common_path.is_absolute():
        common_path = repo / common_path
    common_identity = 'common-dir:' + os.path.normcase(str(common_path.resolve()))
    remote = _git(repo, 'remote', 'get-url', 'origin', optional=True)
    if remote:
        if '://' in remote:
            parsed = urlsplit(remote)
            if parsed.hostname:
                host = parsed.hostname.lower()
                if parsed.port and parsed.port not in (22, 80, 443):
                    host += ':' + str(parsed.port)
                identity = host + '/' + parsed.path.strip('/')
            else:
                identity = str(Path(parsed.path).resolve())
        elif re.match(r'^(?:[^/@:]+@)?[^/:]+:', remote) and not re.match(r'^[A-Za-z]:[\\/]', remote):
            host, name = remote.split(':', 1)
            identity = host.rsplit('@', 1)[-1].lower() + '/' + name.strip('/')
        else:
            # Shared relative configuration is interpreted against different
            # checkout paths by Git; group this repository by its common directory.
            if not Path(remote).is_absolute():
                return common_identity
            identity = os.path.normcase(str(Path(remote).resolve()))
        identity = identity.rstrip('/')
        if identity.endswith('.git'):
            identity = identity[:-4]
        return 'origin:' + identity
    return common_identity


def select_output_root(repo, output_root=None):
    explicit = output_root is not None
    selected = output_root if explicit else os.environ.get('CCR_ARTIFACTS_DIR')
    if selected is None:
        selected = Path.home() / '.comprehensive-code-review' / 'reviews'
    if not selected:
        raise ValueError('CCR_ARTIFACTS_DIR is empty; specify a durable absolute root')
    root = safe_path(selected)
    if not explicit:
        checkouts = [safe_path(repo), Path(__file__).resolve().parents[1]]
        listing = _git(repo, 'worktree', 'list', '--porcelain')
        checkouts.extend(safe_path(line[9:]) for line in listing.splitlines() if line.startswith('worktree '))
        if any(_contains(parent, root) for parent in checkouts):
            raise ValueError('the default/global archive root must be outside repository worktrees and skill installation')
    return root


def _scope(scope):
    if not isinstance(scope, dict) or set(scope) != SCOPE_FIELDS:
        raise ValueError('scope must contain exactly the pinned scope fields')
    errors = review_contract.validate({'schema_version': 1, 'stage': 'discovery',
                                      'scope': scope, 'findings': [], 'checks': [],
                                      'coverage': {'flows': [], 'limitations': []}})
    if errors:
        raise ValueError('; '.join(errors))


def _slug(value):
    label = re.sub(r'[^a-zA-Z0-9_-]+', '-', str(value)).strip('-_')[:36] or 'review'
    if re.fullmatch(r'(?i)(CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])', label):
        label = 'review-' + label
    return label


def _repository_group(identity):
    if (not isinstance(identity, str) or not identity.startswith(('origin:', 'common-dir:'))
            or not identity.split(':', 1)[1]):
        raise ValueError('invalid layout repository identity')
    identity_path = identity.split(':', 1)[1].replace('\\', '/')
    label = Path(identity_path).parent.name if identity_path.endswith('/.git') else identity_path.rsplit('/', 1)[-1]
    return _slug(label) + '-' + _digest(identity.encode('utf-8'))[:20]


def _scope_group(scope, logical_scope_input=None):
    return review_layout.scope_group(review_layout.logical_scope(scope, logical_scope_input))


def _validate_layout(run, manifest):
    """Bind location to durable identities; never need the original checkout."""
    review_layout.validate_layout(run, manifest)
    root = safe_path(manifest['archive_root'])
    parts = run.relative_to(root).parts
    key = manifest.get('repository_key')
    if len(parts) != 3 or not isinstance(key, str) or not re.fullmatch(r'[0-9a-f]{20}', key):
        raise ValueError('invalid archive layout: expected repository/scope/run below root')
    repository, scope, name = parts
    label, separator, suffix = repository.rpartition('-')
    # Historical _slug strips before truncating, so a generated label may end
    # in '-' or '_'. Validate its shape without applying a second normalization.
    if not separator or suffix != key or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,35}', label):
        raise ValueError('invalid archive layout: repository name must include its stable ID')
    if scope != _scope_group(manifest['scope'], manifest.get('logical_scope_input')):
        raise ValueError('invalid archive layout: scope directory differs from pinned scope')
    if manifest['schema_version'] >= 3:
        if repository != _repository_group(manifest.get('repository_identity')):
            raise ValueError('invalid archive layout: repository identity differs from directory')
        run_id = manifest.get('run_id')
        if not isinstance(run_id, str) or not re.fullmatch(r'[0-9a-f]{20}', run_id):
            raise ValueError('invalid archive layout: unique run ID is missing')
        try:
            created = datetime.fromisoformat(manifest['created_at'])
            if created.utcoffset() is None:
                raise ValueError('timestamp needs timezone')
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError('invalid archive layout: creation timestamp is missing or invalid') from exc
        expected = review_layout.run_name(manifest['scope'], manifest['created_at'], run_id,
                                          manifest.get('logical_scope_input'))
        if name != expected:
            raise ValueError('invalid archive layout: run directory differs from stored identity')


def _temporary_paths(paths, manifest):
    registered = list(manifest.get('temporary_paths', []))
    repo, root = safe_path(manifest['repository_path']), safe_path(manifest['archive_root'])
    for raw in paths or []:
        path = safe_path(raw)
        if (path == repo or _contains(path, repo) or
                _contains(root, path) or _contains(path, root)):
            raise ValueError('user checkout and retained archive cannot be temporary resources')
        try:
            if not stat.S_ISDIR(path.stat().st_mode):
                raise ValueError('temporary resources must be session/workspace directories')
        except FileNotFoundError:
            pass
        if str(path) not in registered:
            registered.append(str(path))
    return registered


def _temporary_manifests(registered, manifest):
    """Preserve conventional original manifest locations, without reading contents."""
    locations = list(manifest.get('temporary_manifests', []))
    for raw in registered:
        path = safe_path(Path(raw) / 'manifest.json')
        try:
            info = path.stat()
        except FileNotFoundError:
            continue
        if not stat.S_ISREG(info.st_mode):
            raise ValueError('temporary manifest must be a regular file')
        if str(path) not in locations:
            locations.append(str(path))
    return locations


def _archive_write(run, manifest, name, data):
    reservation_id = manifest.get('restart_operation', {}).get('reservation_id')
    stage = (run / ('.' + name + '.' + reservation_id + '.tmp')
             if reservation_id and (run / '.review-restart-reservation.json').exists() else None)
    atomic_write(run / name, data, **({'staging_path': stage} if stage else {}))


def _save_manifest(run, manifest, marker):
    manifest['updated_at'] = datetime.now(timezone.utc).isoformat()
    data = _json_bytes(manifest)
    # Authorize only this specific old/new transition before the manifest replace.
    # Either digest remains verifiable if the process stops between atomic writes.
    current = safe_path(run / 'cierre.json')
    try:
        old_digest = _digest(current.read_bytes())
    except FileNotFoundError:
        old_digest = None
    transition = dict(marker, manifest_sha256=_digest(data), previous_manifest_sha256=old_digest)
    _archive_write(run, manifest, MARKER, _json_bytes(transition))
    _archive_write(run, manifest, 'cierre.json', data)
    marker = dict(marker, manifest_sha256=_digest(data))
    marker.pop('previous_manifest_sha256', None)
    _archive_write(run, manifest, MARKER, _json_bytes(marker))
    return marker


def _load_run(run_dir):
    run = safe_path(run_dir)
    try:
        marker = read_json(run / MARKER)
        manifest = read_json(run / 'cierre.json')
    except FileNotFoundError as exc:
        raise ValueError('foreign or incomplete archive: ownership manifest is missing') from exc
    if not isinstance(marker, dict) or not isinstance(manifest, dict):
        raise ValueError('invalid ownership manifest')
    if (marker.get('run_dir') != str(run) or marker.get('owner_id') != manifest.get('owner_id')
            or marker.get('scope_sha256') != _digest(_json_bytes(manifest.get('scope')))
            or marker.get('repository_key') != manifest.get('repository_key')
            or marker.get('archive_root') != manifest.get('archive_root')
            or _digest((run / 'cierre.json').read_bytes()) not in
            {marker.get('manifest_sha256'), marker.get('previous_manifest_sha256')}):
        raise ValueError('foreign run or modified ownership/scope manifest')
    root = safe_path(marker['archive_root'])
    if not _contains(root, run) or run == root:
        raise ValueError('run escaped its registered archive root')
    _scope(manifest.get('scope'))
    if manifest.get('schema_version') != ARCHIVE_SCHEMA_VERSION or manifest.get('layout_version') != review_layout.LAYOUT_VERSION:
        raise ValueError('unsupported_layout: this archive predates native archive schema 8/layout 2; preserve it or port a verified report for consultation')
    if marker.get('logical_scope_sha256') != _digest(_json_bytes(manifest.get('logical_scope'))):
        raise ValueError('foreign run or modified logical scope binding')
    if manifest['schema_version'] in (6, 7, 8):
        review_harness.validate_identity(manifest)
    if manifest['schema_version'] == 8:
        if not manifest.get('profile_history'):
            raise ValueError('profile selection is required before review work starts')
        errors = review_profiles.validate_history(manifest.get('profile_history'))
        if errors:
            raise ValueError('; '.join(errors))
        if 'assignment_registry' in manifest:
            try:
                review_profiles._assignment_rows(manifest['assignment_registry'],
                                                 manifest['profile_history'], 'assignment_registry')
            except (TypeError, ValueError) as exc:
                raise ValueError('invalid archive assignment registry: ' + str(exc)) from exc
        if 'review_inputs' in manifest and manifest['review_inputs'] is not None:
            try:
                inputs = review_inputs.normalize_inputs(manifest['review_inputs'], caller=False)
            except (TypeError, ValueError) as exc:
                raise ValueError('invalid archive review_inputs: ' + str(exc)) from exc
            if inputs.get('scope') != manifest.get('scope') or 'profile' in inputs:
                raise ValueError('archive review_inputs must bind the pinned scope and leave profile to profile_history')
        operation = manifest.get('operation')
        fields = {'disposition', 'reason', 'source', 'phase', 'successor'}
        if (not isinstance(operation, dict) or set(operation) != fields
                or operation['disposition'] not in {'open', 'paused', 'blocked', 'superseded', 'complete'}):
            raise ValueError('invalid archive operation disposition')
        restart_operation = manifest.get('restart_operation')
        if restart_operation is not None:
            restart_fields = {'operation_id', 'request_sha256', 'intent_sha256', 'source_run',
                              'source_owner_id', 'reservation_id'}
            if (not isinstance(restart_operation, dict) or set(restart_operation) != restart_fields
                    or not re.fullmatch(r'[0-9a-f]{32}', str(restart_operation['operation_id']))
                    or not CHECKPOINT_HASH.fullmatch(str(restart_operation['request_sha256']))
                    or not CHECKPOINT_HASH.fullmatch(str(restart_operation['intent_sha256']))
                    or not isinstance(restart_operation['source_run'], str)
                    or restart_operation['source_run'] != manifest.get('previous_run')
                    or not isinstance(restart_operation['source_owner_id'], str)
                    or not isinstance(restart_operation['reservation_id'], str)):
                raise ValueError('invalid reserved restart identity in archive')
        controller = manifest.get('controller')
        if (not isinstance(controller, dict) or set(controller) != {'identity', 'source'}
                or not isinstance(controller['identity'], dict) or not isinstance(controller['source'], str)):
            raise ValueError('invalid archive controller identity')
        _validate_cleanup_metadata(manifest)
        _validate_terminal_abandonment(run, manifest)
    states = {'prepared', 'retaining', 'closing', 'complete'}
    if manifest['schema_version'] in (5, 6, 7, 8):
        states.add('processing')
    if manifest.get('state') not in states:
        raise ValueError('invalid archive state')
    if manifest.get('cleanup') not in {'pending', 'complete', 'not_needed'}:
        raise ValueError('invalid closure state')
    _validate_layout(run, manifest)
    return run, manifest, marker


def _pending_file_name(name):
    if not isinstance(name, str):
        return False
    if name in {'pending/context.json', 'pending/review.json', 'pending/informe.md'}:
        return True
    return (isinstance(name, str) and name.startswith('pending/evidence/')
            and name.count('/') == 2 and name[17:] == _evidence_name(name[17:])
            and name[17:] not in {'.', '..'})


def _verify_pending(run, manifest, *, allow_transaction=False):
    if manifest.get('schema_version') != 8:
        if any(key in manifest for key in ('pending_hashes', 'checkpoint', 'checkpoint_transaction')):
            raise ValueError('legacy archive cannot contain provisional checkpoint metadata')
        return
    hashes = manifest.get('pending_hashes', {})
    if not isinstance(hashes, dict) or len(hashes) > CHECKPOINT_EVIDENCE_COUNT_LIMIT + 3 or any(not _pending_file_name(name)
                                           or not isinstance(value, str)
                                           or not CHECKPOINT_HASH.fullmatch(value)
                                           for name, value in hashes.items()):
        raise ValueError('invalid provisional checkpoint hash inventory')
    if len({name.casefold() for name in hashes}) != len(hashes):
        raise ValueError('provisional checkpoint contains case-insensitive destination collisions')
    checkpoint = manifest.get('checkpoint')
    transaction = manifest.get('checkpoint_transaction')
    accepted = {name: {digest} for name, digest in hashes.items()}
    may_be_missing = set()
    staging_paths = {}
    if transaction is not None:
        base_fields = {'input_signature', 'previous_hashes', 'planned_hashes', 'removed_hashes', 'checkpoint'}
        if not isinstance(transaction, dict) or set(transaction) not in (base_fields, base_fields | {'staging'}):
            raise ValueError('invalid checkpoint transaction intent')
        previous, planned, removed = (transaction['previous_hashes'], transaction['planned_hashes'],
                                       transaction['removed_hashes'])
        if previous != hashes or not isinstance(planned, dict) or any(
                not _pending_file_name(name) or not isinstance(value, str)
                or not CHECKPOINT_HASH.fullmatch(value) for name, value in planned.items()):
            raise ValueError('checkpoint transaction differs from its owned prior inventory')
        if len({name.casefold() for name in planned}) != len(planned):
            raise ValueError('checkpoint transaction contains case-insensitive destination collisions')
        if (not isinstance(removed, dict) or any(
                name not in {'pending/review.json', 'pending/informe.md'}
                or previous.get(name) != digest or name in planned
                or not isinstance(digest, str) or not CHECKPOINT_HASH.fullmatch(digest)
                for name, digest in removed.items())):
            raise ValueError('checkpoint transaction has an invalid owned removal intent')
        if not isinstance(transaction['input_signature'], str) or not CHECKPOINT_HASH.fullmatch(transaction['input_signature']):
            raise ValueError('invalid checkpoint input signature')
        if 'staging' in transaction:
            staging = transaction['staging']
            if not isinstance(staging, dict) or set(staging) - set(planned):
                raise ValueError('invalid checkpoint staging inventory')
            occupied = {name.casefold() for name in set(previous) | set(planned)}
            for destination, row in staging.items():
                if (not isinstance(row, dict) or set(row) != {'name', 'sha256'}
                        or not isinstance(row['name'], str) or not isinstance(row['sha256'], str)
                        or row['sha256'] != planned[destination]
                        or not CHECKPOINT_HASH.fullmatch(row['sha256'])):
                    raise ValueError('invalid checkpoint staging row')
                stage = PurePosixPath(row['name'])
                target = PurePosixPath(destination)
                if (str(stage) != row['name'] or stage.is_absolute() or '\\' in row['name']
                        or any(part in {'', '.', '..'} for part in stage.parts)
                        or stage.parent != target.parent or row['name'].casefold() in occupied):
                    raise ValueError('checkpoint staging path is not an owned sibling')
                if row['name'].casefold() in {item.casefold() for item in staging_paths.values()}:
                    raise ValueError('duplicate checkpoint staging path')
                staging_paths[destination] = row['name']
        accepted = {name: {digest} for name, digest in previous.items()}
        for name, digest in planned.items():
            accepted.setdefault(name, set()).add(digest)
            if name not in previous:
                may_be_missing.add(name)
        may_be_missing.update(removed)
        if not allow_transaction:
            if manifest.get('operation', {}).get('disposition') == 'superseded':
                raise ValueError('source review was superseded; inspect its recorded successor: '
                                 + str(manifest['operation']['successor']))
            raise ValueError('checkpoint transaction is pending; retry the checkpoint with its selected inputs')
        checkpoint = transaction['checkpoint']
    elif hashes and not isinstance(checkpoint, dict):
        raise ValueError('checkpoint hash inventory has no checkpoint record')

    if checkpoint is not None:
        if (not isinstance(checkpoint, dict) or set(checkpoint) != {
                'id', 'phase', 'recorded_at', 'input_signature', 'inventory', 'gate_errors'}
                or not isinstance(checkpoint['id'], str) or not re.fullmatch(r'K[0-9]{3,}', checkpoint['id'])
                or not isinstance(checkpoint['phase'], str)
                or checkpoint['phase'] not in review_profiles.PHASES - {'prepare'}
                or not isinstance(checkpoint['recorded_at'], str)
                or not isinstance(checkpoint['input_signature'], str)
                or not CHECKPOINT_HASH.fullmatch(checkpoint['input_signature'])
                or not isinstance(checkpoint['inventory'], list)
                or not isinstance(checkpoint['gate_errors'], list)):
            raise ValueError('invalid checkpoint metadata')
        try:
            recorded_at = datetime.fromisoformat(checkpoint['recorded_at'].replace('Z', '+00:00'))
            if recorded_at.utcoffset() is None:
                raise ValueError('timezone required')
        except (TypeError, ValueError) as exc:
            raise ValueError('invalid checkpoint recording time') from exc
        if len(checkpoint['inventory']) > CHECKPOINT_EVIDENCE_COUNT_LIMIT + 3:
            raise ValueError('checkpoint inventory exceeds its entry limit')
        inventory = {}
        for row in checkpoint['inventory']:
            if (not isinstance(row, dict) or set(row) != {'name', 'size', 'sha256'}
                    or not _pending_file_name(row['name']) or type(row['size']) is not int or row['size'] < 0
                    or not isinstance(row['sha256'], str) or not CHECKPOINT_HASH.fullmatch(row['sha256'])
                    or row['name'] in inventory or row['name'].casefold() in {key.casefold() for key in inventory}):
                raise ValueError('invalid checkpoint inventory row')
            inventory[row['name']] = row['sha256']
        inventory_hashes = transaction['planned_hashes'] if transaction is not None else hashes
        if inventory != inventory_hashes:
            raise ValueError('checkpoint inventory differs from provisional hashes')
        evidence_size = sum(row['size'] for row in checkpoint['inventory']
                            if row['name'].startswith('pending/evidence/'))
        metadata_size = sum(row['size'] for row in checkpoint['inventory']
                            if row['name'].lower().endswith(('.json', '.md')))
        context_row = next((row for row in checkpoint['inventory'] if row['name'] == 'pending/context.json'), None)
        if (evidence_size > CHECKPOINT_EVIDENCE_LIMIT or metadata_size > CHECKPOINT_METADATA_LIMIT
                or context_row is None or context_row['size'] > PENDING_CONTEXT_LIMIT):
            raise ValueError('checkpoint inventory exceeds its declared size bounds')
        if (len(checkpoint['gate_errors']) > 64 or any(not isinstance(item, str) or not item.strip()
                or len(item) > 2000 for item in checkpoint['gate_errors'])):
            raise ValueError('checkpoint gate diagnostics are invalid or unbounded')
    elif hashes or transaction is not None:
        raise ValueError('checkpoint metadata is incomplete')

    root = run / 'pending'
    if root.exists():
        if not root.is_dir() or root.is_symlink():
            raise ValueError('pending checkpoint root is not a regular directory')
        observed = set()
        for path in root.rglob('*'):
            safe_path(path)
            if path.is_dir():
                continue
            name = path.relative_to(run).as_posix()
            staging_owner = next((destination for destination, staged_name in staging_paths.items()
                                  if staged_name == name), None)
            if staging_owner is not None:
                info = path.lstat()
                if not stat.S_ISREG(info.st_mode) or info.st_size > (
                        CHECKPOINT_EVIDENCE_LIMIT if staging_owner.startswith('pending/evidence/')
                        else CHECKPOINT_METADATA_LIMIT):
                    raise ValueError('checkpoint staging is not a bounded regular file: ' + name)
                observed.add(name)
                continue
            if not _pending_file_name(name):
                raise ValueError('foreign file in pending checkpoint: ' + name)
            observed.add(name)
        if observed - set(accepted) - set(staging_paths.values()):
            raise ValueError('foreign pending checkpoint files are present')
    elif accepted and any(name not in may_be_missing for name in accepted):
        raise ValueError('pending checkpoint inventory is missing its directory')

    evidence_size_read = 0
    metadata_size_read = 0
    for name, allowed_digests in accepted.items():
        path = safe_path(run / name)
        try:
            if name.startswith('pending/evidence/'):
                limit = CHECKPOINT_EVIDENCE_LIMIT - evidence_size_read
            elif name == 'pending/context.json':
                limit = PENDING_CONTEXT_LIMIT
            else:
                limit = CHECKPOINT_METADATA_LIMIT - metadata_size_read
            data = read_bounded(path, limit)
        except FileNotFoundError:
            if name in may_be_missing:
                continue
            raise ValueError('pending checkpoint file is missing: ' + name)
        if _digest(data) not in allowed_digests:
            raise ValueError('modified pending checkpoint file: ' + name)
        if name.startswith('pending/evidence/'):
            evidence_size_read += len(data)
        else:
            metadata_size_read += len(data)
        if transaction is None:
            expected_size = next(row['size'] for row in checkpoint['inventory'] if row['name'] == name)
            if len(data) != expected_size:
                raise ValueError('pending checkpoint file size differs from its inventory: ' + name)
        elif name in transaction['planned_hashes'] and _digest(data) == transaction['planned_hashes'][name]:
            planned_size = next(row['size'] for row in checkpoint['inventory'] if row['name'] == name)
            if len(data) != planned_size:
                raise ValueError('pending checkpoint file size differs from its transaction: ' + name)


def _verify_files(run, manifest, required=False, *, allow_checkpoint_transaction=False,
                  allow_resource_transfer=False, allow_pending_trace=False):
    trace_plan = None
    if manifest.get('pending_trace') is not None:
        if not allow_pending_trace:
            raise ValueError('trace recording is pending; retry a helper mutation to recover the preserved event')
        trace_plan = _trace_recovery_plan(run, manifest)
    transfers = normalize_transfer_history(manifest)
    if any(row['status'] != 'complete' for row in transfers) and not allow_resource_transfer:
        pending = next(row for row in transfers if row['status'] != 'complete')
        operation = manifest.get('restart_operation')
        incoming_restart = (isinstance(operation, dict) and operation['source_run'] == pending['source_run']
                            and str(run) == pending['successor_run'])
        identity = ('restart operation ' + operation['operation_id']) if incoming_restart else ('transfer ' + pending['transfer_id'])
        detail = '; recover its source ' + pending['source_run'] + ' for ' + identity
        raise ValueError('resource transfer is pending' + detail)
    _verify_pending(run, manifest, allow_transaction=allow_checkpoint_transaction)
    hashes = manifest.get('hashes')
    if not isinstance(hashes, dict) or any(not _retained_name(name) for name in hashes):
        raise ValueError('invalid retained file manifest')
    planned = manifest.get('planned_hashes', {}) if manifest['state'] == 'retaining' else {}
    required_files = set(FILES) | (set(OPTIONAL_FILES) if manifest['schema_version'] == 1 else set())
    if manifest['schema_version'] in TRACE_ARCHIVE_SCHEMAS and review_trace.NAME not in hashes and trace_plan is None:
        raise ValueError('mandatory archive trace is missing from closure')
    if required and (not required_files.issubset(hashes) or manifest['state'] == 'retaining'):
        raise ValueError('retained evidence is absent or interrupted')
    if not isinstance(planned, dict) or any(not _retained_name(name) for name in planned):
        raise ValueError('invalid planned evidence paths')
    for name in set(FILES) | set(OPTIONAL_FILES) | (set(TRACE_FILES) if manifest['schema_version'] in TRACE_ARCHIVE_SCHEMAS else set()) | set(hashes) | set(planned):
        if name == review_trace.NAME and trace_plan is not None:
            continue  # Both possible byte states and the planned events were verified, without writing.
        path = safe_path(run / name)
        try:
            data = path.read_bytes()
        except FileNotFoundError:
            if (required and name in required_files | set(hashes)) or (name in hashes and manifest['state'] != 'retaining'):
                raise ValueError('retained evidence missing: ' + name)
            continue
        if _digest(data) not in {hashes.get(name), planned.get(name)}:
            raise ValueError('refusing to clobber modified archived file: ' + name)
    if manifest['schema_version'] in TRACE_ARCHIVE_SCHEMAS and trace_plan is None:
        review_trace.verify(safe_path(run / review_trace.NAME).read_bytes(), manifest.get('trace'), manifest['run_id'])


def _trace_recovery_plan(run, manifest):
    """Verify an owned pending append without changing any bytes."""
    pending = manifest.get('pending_trace')
    if manifest['schema_version'] not in TRACE_ARCHIVE_SCHEMAS or not isinstance(pending, dict):
        raise ValueError('invalid pending trace transition')
    path = safe_path(run / review_trace.NAME)
    try:
        current = path.read_bytes()
    except FileNotFoundError:
        if pending['previous_sha256'] is not None:
            raise ValueError('pending trace history is missing')
        current = b''
    if _digest(current) == pending['sha256']:
        planned = current
    elif (pending['previous_sha256'] is None and not current) or _digest(current) == pending['previous_sha256']:
        events = pending['events']
        if not isinstance(events, list) or not events or len(events) > 2:
            raise ValueError('invalid pending trace milestone group')
        planned = current + b''.join(review_trace.encoded(event) + b'\n' for event in events)
    else:
        raise ValueError('modified trace cannot be recovered')
    if _digest(planned) != pending['sha256']:
        raise ValueError('pending trace intent integrity mismatch')
    review_trace.verify(planned, pending['trace'], manifest['run_id'])
    return current, planned


def _recover_trace(run, manifest, marker):
    """Finish only an owned, hash-bound pending append; never adopt unknown bytes."""
    pending = manifest.get('pending_trace')
    if pending is None:
        return marker
    current, planned = _trace_recovery_plan(run, manifest)
    if current != planned:
        _archive_write(run, manifest, review_trace.NAME, planned)
    manifest['trace'] = pending['trace']
    manifest['hashes'][review_trace.NAME] = pending['sha256']
    manifest.pop('pending_trace')
    return _save_manifest(run, manifest, marker)


def _append_trace(run, manifest, marker, event, *, helper=True):
    return _append_trace_events(run, manifest, marker, [event], helper=helper)


def _append_trace_events(run, manifest, marker, events, *, helper=True):
    """Bind one mutation and its bounded milestones in one owned transition."""
    if manifest['schema_version'] not in TRACE_ARCHIVE_SCHEMAS:
        return _save_manifest(run, manifest, marker)
    path = safe_path(run / review_trace.NAME)
    old_digest = manifest['hashes'].get(review_trace.NAME)
    current = path.read_bytes() if old_digest is not None else b''
    if old_digest is not None and _digest(current) != old_digest:
        raise ValueError('modified trace cannot be appended')
    data = current
    values = []
    context = dict(manifest)
    for event in events:
        data, descriptor, value = review_trace.append(data, context, event, helper=helper)
        context['trace'] = descriptor
        values.append(value)
    manifest['pending_trace'] = {'previous_sha256': old_digest, 'sha256': _digest(data),
                                 'trace': descriptor, 'events': values}
    marker = _save_manifest(run, manifest, marker)
    return _recover_trace(run, manifest, marker)


def _milestone(kind, summary, *, status='completed', evidence=None):
    return {'kind': kind, 'status': status, 'summary': summary, 'evidence': evidence or [],
            'occurred_at': datetime.now(timezone.utc).isoformat(),
            'provenance': {'kind': 'helper', 'source': 'review_artifacts:' + kind}}


def _starts_processing(event):
    return (event['kind'] in {'agent', 'discovery', 'check', 'grouped-verification'}
            and event['status'] in {'started', 'completed', 'passed', 'failed', 'blocked', 'skipped'})


def _input_object(value, label, *, max_bytes=None):
    result = read_json(value, max_bytes=max_bytes) if isinstance(value, (str, os.PathLike)) else copy.deepcopy(value)
    if not isinstance(result, dict):
        raise ValueError(label + ' must be a JSON object')
    return result


def _initial_selection(profile_input):
    if profile_input is None:
        raise ValueError('profile selection is required before preparing a new archive')
    raw = _input_object(profile_input, 'profile selection')
    if set(raw) != review_profiles.INPUT_FIELDS:
        raise ValueError('initial profile selection must contain exactly the required decision fields')
    try:
        value = review_profiles.validate_selection(
            {key: raw[key] for key in review_profiles.INPUT_FIELDS})
    except KeyError as exc:
        raise ValueError('profile selection is missing required field: ' + str(exc.args[0])) from exc
    if value['phase'] != 'prepare' or value['affected_assignments']:
        raise ValueError('initial profile selection must use prepare phase and have no affected assignments')
    value.update(id='S001', changed_from=None, event_id='E000002')
    return value


def _capture_review_inputs(raw, scope, profile, label, *, logical_scope_identity=None):
    """Capture external inputs before work while keeping profile history authoritative."""
    if raw is None:
        return None
    value = review_inputs.normalize_inputs(_input_object(raw, label))
    if logical_scope_identity is not None:
        if ('logical_scope_identity' in value
                and value['logical_scope_identity'] != logical_scope_identity):
            raise ValueError(label + ' logical scope differs from the pinned selector')
        value.setdefault('logical_scope_identity', logical_scope_identity)
    if value['scope'] != scope:
        raise ValueError(label + ' scope differs from the pinned review scope')
    selected_profile = value.pop('profile', None)
    if selected_profile is not None and selected_profile != profile:
        raise ValueError(label + ' profile differs from the captured profile selection')
    for reference in value['sources']:
        if not reference.split('#', 1)[0].startswith('evidence/'):
            raise ValueError(label + ' source references must identify selected evidence/ files')
    return value


def _profile_event(selection):
    return {'kind': 'profile', 'status': 'selected',
            'summary': 'Profile selected: ' + selection['profile'],
            'actor': selection['actor'], 'authority': selection['authority'],
            'provenance': {'kind': 'helper', 'source': 'review_artifacts:profile-selection'},
            'evidence': [selection['reference']]}


def _controller(value, fallback):
    if value is None:
        return {'identity': copy.deepcopy(fallback), 'source': 'profile-input'}
    item = _input_object(value, 'controller')
    identity = item.get('identity')
    source = item.get('source')
    if (set(item) != {'identity', 'source'} or not isinstance(identity, dict)
            or set(identity) != {'kind', 'name', 'provider_id'}
            or identity['kind'] not in {'helper', 'coordinator', 'agent', 'tool'}
            or not isinstance(identity['name'], str) or not identity['name'].strip() or len(identity['name']) > 160
            or any(ord(char) < 32 for char in identity['name'])
            or identity['provider_id'] is not None and (not isinstance(identity['provider_id'], str)
                or not identity['provider_id'].strip() or len(identity['provider_id']) > 160
                or any(ord(char) < 32 for char in identity['provider_id']))
            or not isinstance(source, str) or not source.strip() or len(source) > 500
            or any(ord(char) < 32 for char in source)):
        raise ValueError('controller requires a trace identity and nonempty source')
    return {'identity': copy.deepcopy(identity), 'source': source}


def _remove_unowned_prepare_directory(run, marker):
    """Remove only an empty run dir or its own marker when no closure exists."""
    try:
        closure = run / 'cierre.json'
        if closure.exists():
            return
        ownership = run / MARKER
        if ownership.exists():
            value = read_json(ownership)
            if (value.get('owner_id') != marker['owner_id'] or value.get('run_dir') != str(run)
                    or value.get('scope_sha256') != marker['scope_sha256']):
                return
            ownership.unlink()
        run.rmdir()
    except (OSError, ValueError, TypeError):
        return


@_locked_run
def record_event(run_dir, event_file, execution_metadata=None):
    """Coordinator-only durable writer for a bounded, structured worker milestone."""
    event = review_trace.event_input(read_json(event_file))
    if execution_metadata is not None:
        metadata_path = safe_path(execution_metadata)
        event = review_trace.event_from_execution(event, read_json(metadata_path), 'review_runner:' + str(metadata_path))
    run, manifest, marker = _load_run(run_dir)
    if manifest['schema_version'] not in TRACE_ARCHIVE_SCHEMAS:
        raise ValueError('legacy archives cannot acquire synthetic traces; prepare a new run')
    marker = _recover_trace(run, manifest, marker)
    _verify_files(run, manifest)
    if manifest['state'] == 'complete':
        raise ValueError('completed review history is immutable')
    if manifest['state'] == 'retaining':
        raise ValueError('retention is interrupted; finish retention before recording milestones')
    if manifest['schema_version'] in (5, 6, 7, 8) and event['occurred_at'] is not None and event['provenance']['source'] is None:
        raise ValueError('observed execution time requires an identifiable provenance source')
    if manifest['schema_version'] in (5, 6, 7, 8):
        review_trace.validate_local_event_targets(event, (run / review_trace.NAME).read_bytes())
    if manifest['schema_version'] == 8 and event['kind'] == 'profile':
        raise ValueError('use select-profile to record structured profile transitions')
    if manifest['schema_version'] == 8 and _starts_processing(event):
        if not manifest.get('profile_history'):
            raise ValueError('profile selection is required before review work starts')
        disposition = manifest.get('operation', {}).get('disposition')
        if disposition != 'open':
            raise ValueError('review operation is ' + str(disposition) + '; resume or recover before starting work')
        if (event['kind'] in {'agent', 'discovery', 'grouped-verification'}
                and event.get('evidence')):
            registry = manifest.get('assignment_registry')
            references = {row['reference'] for row in registry if isinstance(row, dict)
                          and row.get('required') is True and row.get('superseded_by') is None
                          and isinstance(row.get('reference'), str)} if isinstance(registry, list) else set()
            inactive = {row['reference'] for row in registry if isinstance(row, dict)
                        and (row.get('required') is not True or row.get('superseded_by') is not None)
                        and isinstance(row.get('reference'), str)} if isinstance(registry, list) else set()
            if inactive.intersection(event['evidence']):
                raise ValueError('assignment work cannot start a superseded or non-required brief')
            if event['status'] == 'started' and not references.intersection(event['evidence']):
                raise ValueError('assignment work must start from an active required brief captured in the execution plan')
    if manifest['schema_version'] in (5, 6, 7, 8) and manifest['state'] == 'prepared' and _starts_processing(event):
        manifest['state'] = 'processing'
    _append_trace(run, manifest, marker, event, helper=False)
    return {'run_id': manifest['run_id'], 'event_id': 'E' + str(manifest['trace']['events']).zfill(6),
            'sequence': manifest['trace']['events']}


def _evidence_name(name):
    label = re.sub(r'[^a-zA-Z0-9._-]', '-', name).strip(' .')[:80] or 'evidence'
    if re.fullmatch(r'(?i)(CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])(?:\..*)?', label):
        label = 'evidence-' + label[:70]
    return label


def _retained_name(name):
    if name in FILES + OPTIONAL_FILES + TRACE_FILES:
        return True
    return (isinstance(name, str) and name.startswith('evidence/')
            and name.count('/') == 1 and '\\' not in name
            and name[9:] == _evidence_name(name[9:]) and name[9:] not in {'.', '..'})


def _check_evidence_target(run, manifest, name):
    target = safe_path(run / name)
    if target.exists() and name not in manifest['hashes'] and name not in manifest.get('planned_hashes', {}):
        raise ValueError('refusing to clobber foreign evidence: ' + name)


def _evidence_contents(run, manifest, inputs, *, create_directory=True, reserve_context=False,
                       context_input=None):
    contents = {}
    seen = {'evidence/context.json'.casefold()} if reserve_context else set()
    for raw in inputs or []:
        source = safe_path(raw)
        if not stat.S_ISREG(source.stat().st_mode):
            raise ValueError('selected evidence must be a regular file')
        name = 'evidence/' + _evidence_name(source.name)
        if name.casefold() in seen:
            raise ValueError('duplicate selected evidence name: ' + name)
        seen.add(name.casefold())
        _check_evidence_target(run, manifest, name)
        contents[name] = source.read_bytes()
    # A retry must finish every previously selected artifact. Existing matching
    # planned bytes are reusable; missing sources require explicit resubmission.
    for name, expected in manifest.get('planned_hashes', {}).items():
        if name.startswith('evidence/') and name not in contents:
            if name == 'evidence/context.json' and context_input is not None:
                context = read_json(context_input, max_bytes=PENDING_CONTEXT_LIMIT)
                data = _json_bytes(context)
                if len(data) > 131072 or _digest(data) != expected:
                    raise ValueError('interrupted selected context differs from its reserved hash')
                contents[name] = data
                continue
            try:
                data = safe_path(run / name).read_bytes()
            except FileNotFoundError as exc:
                raise ValueError('interrupted selected evidence requires its input again: ' + name) from exc
            if _digest(data) != expected:
                raise ValueError('modified interrupted evidence: ' + name)
            contents[name] = data
    if contents and create_directory:
        safe_path(run / 'evidence').mkdir(exist_ok=True)
    return contents


def _checkpoint_diagnostics(values):
    if values is None:
        return []
    if not isinstance(values, list) or len(values) > 64:
        raise ValueError('checkpoint gate errors must be a bounded array')
    result = []
    for value in values:
        if not isinstance(value, str) or not value.strip() or len(value) > 2000:
            raise ValueError('checkpoint gate error must be bounded nonempty text')
        if value not in result:
            result.append(value)
    if sum(len(value.encode('utf-8')) for value in result) > 131072:
        raise ValueError('checkpoint gate errors exceed the metadata limit')
    return result


def _checkpoint_input_files(run, manifest, context_input, evidence_inputs, input_record,
                            phase, gate_errors, max_evidence_bytes):
    if phase not in review_profiles.PHASES - {'prepare'}:
        raise ValueError('checkpoint phase must identify review work after preparation')
    if (type(max_evidence_bytes) is not int or not 0 <= max_evidence_bytes <= CHECKPOINT_EVIDENCE_LIMIT):
        raise ValueError('checkpoint evidence limit must be between 0 and 64 MiB')
    context_path = safe_path(context_input)
    if not stat.S_ISREG(context_path.stat().st_mode):
        raise ValueError('checkpoint context must be a regular JSON file')
    try:
        context = read_json(context_path, max_bytes=PENDING_CONTEXT_LIMIT)
    except ValueError as exc:
        if 'input exceeds' in str(exc):
            raise ValueError('execution context exceeds the 131072-byte checkpoint limit') from exc
        raise
    if not isinstance(context, dict):
        raise ValueError('checkpoint context must be a JSON object')
    captured_inputs = manifest.get('review_inputs')
    supplied_inputs = context.get('review_inputs')
    if captured_inputs is not None:
        if supplied_inputs is None:
            raise ValueError('checkpoint context must preserve registered review_inputs')
        normalized_inputs = _capture_review_inputs(
            supplied_inputs, manifest['scope'], manifest['profile_history'][-1]['profile'],
            'checkpoint context review_inputs',
            logical_scope_identity=manifest.get('logical_scope', {}).get('identity'))
        if normalized_inputs != captured_inputs:
            raise ValueError('checkpoint context review_inputs differ from the initial captured identities')
    elif supplied_inputs is not None:
        raise ValueError('capture review_inputs during prepare or register before checkpoint work')
    context_bytes = _json_bytes(context)
    if len(context_bytes) > PENDING_CONTEXT_LIMIT:
        raise ValueError('execution context exceeds the 131072-byte checkpoint limit')
    payloads = {'pending/context.json': context_bytes}
    source_contents = {'evidence/context.json': context_bytes}
    evidence_total = 0
    evidence_count = 0
    seen = {'context.json'.casefold()}
    previous_names = {name.casefold(): name for name in manifest.get('pending_hashes', {})}
    for raw in evidence_inputs or []:
        source = safe_path(raw)
        if not stat.S_ISREG(source.stat().st_mode):
            raise ValueError('selected checkpoint evidence must be a regular file')
        name = _evidence_name(source.name)
        if name.casefold() in seen:
            raise ValueError('duplicate selected checkpoint evidence name: ' + name)
        seen.add(name.casefold())
        destination = 'pending/evidence/' + name
        if destination.casefold() in previous_names and previous_names[destination.casefold()] != destination:
            raise ValueError('case-insensitive checkpoint evidence capitalization differs from prior checkpoint: ' + name)
        evidence_count += 1
        if evidence_count > CHECKPOINT_EVIDENCE_COUNT_LIMIT:
            raise ValueError('checkpoint accepts at most 64 selected evidence files')
        data = read_bounded(source, max_evidence_bytes - evidence_total)
        evidence_total += len(data)
        if evidence_total > max_evidence_bytes:
            raise ValueError('selected checkpoint evidence exceeds the configured byte limit')
        payloads['pending/evidence/' + name] = data
        source_contents['evidence/' + name] = data

    for name, digest in manifest.get('pending_hashes', {}).items():
        if name.startswith('pending/evidence/') and name not in payloads:
            remaining = max_evidence_bytes - evidence_total
            prior = read_bounded(run / name, remaining)
            if _digest(prior) != digest:
                raise ValueError('modified prior checkpoint evidence: ' + name)
            source_contents['evidence/' + name.split('/', 2)[2]] = prior
            evidence_total += len(prior)

    diagnostics = _checkpoint_diagnostics(gate_errors)
    final = None
    if input_record is not None:
        try:
            final = _input_object(input_record, 'checkpoint final review', max_bytes=CHECKPOINT_METADATA_LIMIT)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            diagnostics.append('final review input could not be parsed: ' + str(exc)[:500])
        else:
            errors = review_contract.validate(final)
            if errors or final.get('stage') != 'final':
                diagnostics.extend('final structure: ' + error for error in errors[:48])
                if not errors:
                    diagnostics.append('final structure: stage must be final')
            else:
                if final.get('schema_version') != 10:
                    diagnostics.append('final structure: archive 8 checkpoints require review schema 10')
                else:
                    if final.get('review_id') != 'CR-' + manifest['run_id']:
                        diagnostics.append('archive identity gate: review ID differs from the run')
                    execution = final.get('coverage', {}).get('execution', {})
                    if execution.get('profile_history') != manifest.get('profile_history'):
                        diagnostics.append('archive profile history differs from the captured run selections')
                    try:
                        _execution_gate(run, manifest, final, source_contents)
                    except (OSError, ValueError, TypeError, KeyError) as exc:
                        diagnostics.append('final source gate: ' + str(exc)[:1500])
                    payloads['pending/review.json'] = _json_bytes(final)
                    payloads['pending/informe.md'] = review_contract.render(final).encode('utf-8')

    diagnostics = _checkpoint_diagnostics(diagnostics)
    selected_names = set(payloads)
    previous = {}
    pending_removals = manifest.get('checkpoint_transaction', {}).get('removed_hashes', {})
    for name, digest in manifest.get('pending_hashes', {}).items():
        if name not in payloads and name not in pending_removals:
            if name.startswith('pending/evidence/'):
                remaining = max_evidence_bytes - sum(
                    len(data) for selected, data in previous.items()
                    if selected.startswith('pending/evidence/'))
                previous[name] = read_bounded(run / name, remaining)
            elif name == 'pending/context.json':
                previous[name] = read_bounded(run / name, PENDING_CONTEXT_LIMIT)
            else:
                remaining = CHECKPOINT_METADATA_LIMIT - sum(
                    len(data) for selected, data in previous.items()
                    if not selected.startswith('pending/evidence/'))
                previous[name] = read_bounded(run / name, remaining)
            if _digest(previous[name]) != digest:
                raise ValueError('modified prior checkpoint bytes: ' + name)
    combined = dict(previous, **payloads)
    metadata_size = sum(len(data) for name, data in combined.items()
                        if name.lower().endswith(('.json', '.md')))
    if metadata_size > CHECKPOINT_METADATA_LIMIT:
        raise ValueError('checkpoint JSON/Markdown metadata exceeds 16 MiB')
    total_evidence = sum(len(data) for name, data in combined.items() if name.startswith('pending/evidence/'))
    if total_evidence > max_evidence_bytes:
        raise ValueError('cumulative checkpoint evidence exceeds the configured byte limit')
    if sum(name.startswith('pending/evidence/') for name in combined) > CHECKPOINT_EVIDENCE_COUNT_LIMIT:
        raise ValueError('checkpoint inventory exceeds 64 selected evidence files')
    signature = _digest(_json_bytes({'phase': phase,
                                     'input_hashes': {name: _digest(data) for name, data in sorted(payloads.items())},
                                     'gate_errors': diagnostics}))
    return combined, diagnostics, signature, selected_names


def _checkpoint_commit(run, manifest, marker, transaction, payloads):
    planned = transaction['planned_hashes']
    staging = transaction.get('staging', {})
    for name, expected in planned.items():
        data = payloads.get(name)
        read_limit = (CHECKPOINT_EVIDENCE_LIMIT if name.startswith('pending/evidence/')
                      else CHECKPOINT_METADATA_LIMIT)
        if data is None:
            path = safe_path(run / name)
            try:
                data = read_bounded(path, read_limit)
            except FileNotFoundError as exc:
                raise ValueError('retry checkpoint with missing selected input: ' + name) from exc
        if _digest(data) != expected:
            raise ValueError('checkpoint retry input differs from its preserved intent: ' + name)
        path = safe_path(run / name)
        try:
            current = read_bounded(path, read_limit)
        except FileNotFoundError:
            current = None
        if current is not None and _digest(current) == expected:
            staged = staging.get(name)
            if staged is not None:
                stage_path = safe_path(run / staged['name'])
                try:
                    stage_path.unlink()
                except FileNotFoundError:
                    pass
            continue
        allowed_old = transaction['previous_hashes'].get(name)
        if current is not None and _digest(current) != allowed_old:
            raise ValueError('foreign or modified pending checkpoint bytes: ' + name)
        if name.startswith('pending/evidence/'):
            safe_path(run / 'pending' / 'evidence').mkdir(parents=True, exist_ok=True)
        else:
            safe_path(run / 'pending').mkdir(exist_ok=True)
        staged = staging.get(name)
        if staged is not None:
            stage_path = safe_path(run / staged['name'])
            try:
                staged_data = read_bounded(stage_path, read_limit)
            except FileNotFoundError:
                staged_data = None
            if staged_data is not None:
                if _digest(staged_data) == expected:
                    os.replace(stage_path, path)
                    continue
                stage_path.unlink()
            atomic_write(path, data, staging_path=stage_path)
        else:
            atomic_write(path, data)
    for name, expected in transaction['removed_hashes'].items():
        path = safe_path(run / name)
        try:
            current = path.read_bytes()
        except FileNotFoundError:
            continue
        if _digest(current) != expected:
            raise ValueError('foreign or modified pending checkpoint bytes: ' + name)
        path.unlink()
    manifest['pending_hashes'] = planned
    manifest['checkpoint'] = transaction['checkpoint']
    manifest.pop('checkpoint_transaction', None)
    _save_manifest(run, manifest, marker)
    return manifest


@_locked_run
def checkpoint(run_dir, *, context_input, evidence_inputs=None, input_record=None, phase,
               gate_errors=None, max_evidence_bytes=CHECKPOINT_EVIDENCE_LIMIT):
    """Preserve explicitly selected provisional inputs/results without retaining a verdict."""
    run, manifest, marker = _load_run(run_dir)
    if manifest['schema_version'] != 8:
        raise ValueError('provisional checkpoints require archive 8')
    marker = _recover_trace(run, manifest, marker)
    _verify_files(run, manifest, allow_checkpoint_transaction=True)
    if manifest['state'] == 'complete' or manifest.get('operation', {}).get('disposition') in {'complete', 'superseded'}:
        raise ValueError('completed or superseded review cannot accept a checkpoint')
    payloads, diagnostics, signature, selected_names = _checkpoint_input_files(
        run, manifest, context_input, evidence_inputs, input_record, phase, gate_errors, max_evidence_bytes)
    transaction = manifest.get('checkpoint_transaction')
    if transaction is None:
        current = manifest.get('checkpoint')
        if isinstance(current, dict) and current.get('input_signature') == signature:
            return current
        prior_hashes = manifest.get('pending_hashes', {})
        removed_hashes = {}
        if 'pending/review.json' not in selected_names:
            removed_hashes = {name: prior_hashes[name]
                              for name in ('pending/review.json', 'pending/informe.md')
                              if name in prior_hashes}
        planned = {name: digest for name, digest in prior_hashes.items() if name not in removed_hashes}
        planned.update({name: _digest(payloads[name]) for name in selected_names})
        if len({name.casefold() for name in planned}) != len(planned):
            raise ValueError('case-insensitive collisions in planned checkpoint inventory')
        sequence = int(current['id'][1:]) + 1 if isinstance(current, dict) else 1
        inventory = []
        for name, digest in sorted(planned.items()):
            if name in payloads:
                data = payloads[name]
            elif name.startswith('pending/evidence/'):
                data = read_bounded(run / name, CHECKPOINT_EVIDENCE_LIMIT)
            elif name == 'pending/context.json':
                data = read_bounded(run / name, PENDING_CONTEXT_LIMIT)
            else:
                data = read_bounded(run / name, CHECKPOINT_METADATA_LIMIT)
            inventory.append({'name': name, 'size': len(data), 'sha256': digest})
        checkpoint_record = {'id': 'K' + str(sequence).zfill(3), 'phase': phase,
                             'recorded_at': datetime.now(timezone.utc).isoformat(),
                             'input_signature': signature,
                             'inventory': inventory,
                             'gate_errors': diagnostics}
        transaction = {'input_signature': signature, 'previous_hashes': prior_hashes,
                       'planned_hashes': planned, 'removed_hashes': removed_hashes,
                       'checkpoint': checkpoint_record}
        transaction['staging'] = {}
        for name in selected_names:
            target = PurePosixPath(name)
            staging_name = str(target.parent / ('.' + target.name + '.' + uuid.uuid4().hex + '.tmp'))
            transaction['staging'][name] = {'name': staging_name, 'sha256': planned[name]}
        manifest['checkpoint_transaction'] = transaction
        marker = _save_manifest(run, manifest, marker)
    elif transaction['input_signature'] != signature:
        raise ValueError('a different checkpoint is already pending; retry its selected inputs first')
    planned = transaction['planned_hashes']
    for name in planned:
        if name not in payloads:
            path = safe_path(run / name)
            try:
                payloads[name] = path.read_bytes()
            except FileNotFoundError:
                pass
    manifest = _checkpoint_commit(run, manifest, marker, transaction, payloads)
    return manifest['checkpoint']


def _measurements(inputs, unavailable_reason):
    if unavailable_reason is not None and (not isinstance(unavailable_reason, str) or not unavailable_reason.strip()):
        raise ValueError('unavailable reason must be nonempty text')
    runs, sources, seen_ids = [], [], set()
    for raw in inputs or []:
        path = safe_path(raw)
        if str(path) in sources:
            raise ValueError('duplicate measurement input path; only disjoint executions are accepted')
        value = read_json(path)
        if not isinstance(value, dict):
            raise ValueError('measurement input must be one execution object')
        if 'runs' in value or 'summary' in value:
            raise ValueError('inclusive summaries are not execution inputs')
        identifier = value.get('execution_id')
        if identifier is not None:
            if not isinstance(identifier, str) or not identifier.strip() or identifier in seen_ids:
                raise ValueError('duplicate or invalid execution_id')
            seen_ids.add(identifier)
        usage = value.get('usage')
        if usage is not None and not isinstance(usage, dict):
            raise ValueError('invalid usage object')
        reason = value.get('unavailable_reason') or value.get('usage_error') or unavailable_reason
        normalized = review_metrics.normalize_usage({field: usage.get(field) for field in review_metrics.USAGE_FIELDS}
                                                     if isinstance(usage, dict) else None)
        missing = (any(normalized[field] is None for field in review_metrics.TOKEN_FIELDS + ('credits', 'cost'))
                   or any(value.get(field) is None for field in review_metrics.COUNTERS))
        if missing and (not isinstance(reason, str) or not reason.strip()):
            raise ValueError('unknown usage/counters require an unavailable reason')
        runs.append({key: item for key, item in value.items() if key in MEASUREMENT_FIELDS})
        sources.append(str(path))
    if not runs:
        if not unavailable_reason:
            raise ValueError('unknown usage requires --unavailable-reason')
        runs = [{'usage': None, 'unavailable_reason': unavailable_reason}]
    summary = review_metrics.summarize(runs)
    quantitative = list(review_metrics.TOKEN_FIELDS) + ['credits', 'cost']
    known = missing = 0
    for value in runs:
        normalized = review_metrics.normalize_usage({field: value['usage'].get(field) for field in review_metrics.USAGE_FIELDS}
                                                     if isinstance(value.get('usage'), dict) else None)
        for item in [normalized[field] for field in quantitative] + [value.get(field) for field in review_metrics.COUNTERS]:
            known += item is not None
            missing += item is None
    return {'schema_version': 1, 'status': 'partial' if known and missing else 'reported' if known else 'unavailable',
            'runs': runs, 'sources': sources, 'summary': summary,
            'unavailable_reason': unavailable_reason,
            'disjoint_inputs_asserted': bool(inputs),
            'overlap_detection': 'Duplicate paths and explicit execution IDs only; semantic overlap is not detectable.'}


def prepare(repo, scope_file, skill_version, harness, output_root=None, previous_run=None, temporary_paths=None,
            *, profile_input=None, controller=None, harness_id=None, harness_source=None, current_inputs=None,
            logical_scope_input=None,
            _restart_reservation=None, _harness_identity=None):
    repo = safe_path(repo)
    repo = safe_path(_git(repo, 'rev-parse', '--show-toplevel'))
    scope = _input_object(scope_file, 'scope')
    _scope(scope)
    if _restart_reservation is not None:
        logical_scope_input = copy.deepcopy(_restart_reservation['request']['logical_scope_input'])
    logical = review_layout.logical_scope(scope, logical_scope_input)
    selection = _initial_selection(profile_input)
    captured_inputs = _capture_review_inputs(current_inputs, scope, selection['profile'], 'current review inputs',
                                             logical_scope_identity=logical['identity'])
    controller_value = _controller(controller, selection['actor'])
    if not isinstance(skill_version, str) or not skill_version.strip() or not isinstance(harness, str) or not harness.strip():
        raise ValueError('skill version and harness are required')
    if _harness_identity is None:
        harness_identity = review_harness.resolve(harness, harness_id, harness_source)
    else:
        review_harness.validate_identity(_harness_identity)
        harness_identity = copy.deepcopy(_harness_identity)
    identity = repository_identity(repo)
    repository_key = _digest(identity.encode('utf-8'))[:20]
    root = select_output_root(repo, output_root)
    previous = None
    if previous_run is not None:
        old, old_manifest, old_marker = _load_run(previous_run)
        active_restart = _active_restart_operation(old, old_manifest)
        if (active_restart is not None
                and (_restart_reservation is None
                     or active_restart['operation_id'] != _restart_reservation['operation_id'])):
            raise ValueError('a durable restart is pending; only its exact reserved prepare may continue')
        if _restart_reservation is not None:
            # Transfer can stop while recording its source milestone. Replay the
            # hash-bound append before checking the source's remaining files.
            _recover_trace(old, old_manifest, old_marker)
        _verify_files(old, old_manifest,
                      allow_checkpoint_transaction=_restart_reservation is not None,
                      allow_resource_transfer=_restart_reservation is not None)
        if old_manifest['repository_key'] != repository_key:
            raise ValueError('previous run belongs to a different repository')
        previous = str(old)
    manifest = {'schema_version': ARCHIVE_SCHEMA_VERSION, 'layout_version': review_layout.LAYOUT_VERSION,
                'logical_scope': logical, 'logical_scope_input': copy.deepcopy(logical_scope_input),
                'skill_version': skill_version, 'harness': harness,
                'scope': scope, 'archive_root': str(root), 'repository_path': str(repo),
                'repository_key': repository_key, 'repository_identity': identity, 'previous_run': previous,
                'owner_id': uuid.uuid4().hex, 'created_at': datetime.now(timezone.utc).isoformat(),
                'state': 'prepared', 'retained': False, 'cleanup': 'pending', 'residuals': [],
                'temporary_paths': [], 'temporary_manifests': [], 'executors': [], 'hashes': {},
                'profile_history': [selection],
                'operation': {'disposition': 'open', 'reason': None, 'source': None,
                              'phase': None, 'successor': None},
                'controller': controller_value,
                'checkpoint': None,
                'lineage': {'kind': 'restart' if previous else 'new', 'source_run': previous},
                'resource_claims': [], 'resource_transfers': [],
                'resource_cleanup': None, 'cleanup_receipts': [],
                'assignment_registry': [], 'review_inputs': captured_inputs}
    manifest.update(harness_identity)
    if _restart_reservation is not None:
        intent = _restart_reservation
        errors = review_restart.validate_restart_intent(intent)
        if errors:
            raise ValueError('; '.join(errors))
        reserved = intent['successor']
        logical_scope_input = copy.deepcopy(intent['request']['logical_scope_input'])
        logical = review_layout.logical_scope(scope, logical_scope_input)
        manifest.update(layout_version=review_layout.LAYOUT_VERSION, logical_scope=logical,
                        logical_scope_input=logical_scope_input)
        manifest.update(run_id=reserved['run_id'], owner_id=reserved['owner_id'],
                        created_at=reserved['created_at'], restart_operation={
                            'operation_id': intent['operation_id'],
                            'request_sha256': intent['request_sha256'],
                            'intent_sha256': intent['intent_sha256'],
                            'source_run': intent['source']['run_dir'],
                            'source_owner_id': intent['source']['owner_id'],
                            'reservation_id': reserved['reservation_id']})
    manifest['temporary_paths'] = _temporary_paths(temporary_paths, manifest)
    manifest['temporary_manifests'] = _temporary_manifests(manifest['temporary_paths'], manifest)
    scoped = root / _repository_group(identity) / review_layout.scope_group(logical)
    reservation_file = '.review-restart-reservation.json'
    if _restart_reservation is not None:
        reserved = _restart_reservation['successor']
        run = safe_path(reserved['run_dir'])
        created = datetime.fromisoformat(reserved['created_at'])
        expected_parent = safe_path(scoped)
        if run.parent != expected_parent:
            raise ValueError('reserved successor escaped its repository/scope group')
        _validate_layout(run, manifest)
        reservation = {'operation_id': _restart_reservation['operation_id'],
                       'intent_sha256': _restart_reservation['intent_sha256'],
                       'reservation_id': reserved['reservation_id'], 'run_dir': str(run),
                       'owner_id': reserved['owner_id']}
        reservation_path = run / reservation_file
        stage_names = {'.' + name + '.' + reserved['reservation_id'] + '.tmp'
                       for name in (reservation_file, MARKER, 'cierre.json', review_trace.NAME)}
        if run.exists():
            if reservation_path.exists() and read_json(reservation_path) != reservation:
                raise ValueError('reserved successor path is occupied by foreign or invalid data')
            try:
                existing, existing_manifest, existing_marker = _load_run(run)
            except (ValueError, OSError, TypeError, KeyError):
                existing_manifest = None
            if existing_manifest is not None:
                with run_locks([existing]):
                    existing, existing_manifest, existing_marker = _load_run(existing)
                    identity_fields = ('run_id', 'owner_id', 'created_at', 'archive_root',
                                       'repository_key', 'scope', 'previous_run', 'restart_operation')
                    if any(existing_manifest.get(key) != manifest.get(key) for key in identity_fields):
                        raise ValueError('reserved successor identity differs from its restart intent')
                    _assert_not_restart_abandoned(existing_manifest)
                    _recover_trace(existing, existing_manifest, existing_marker)
                    _verify_files(existing, existing_manifest, allow_resource_transfer=True)
                    if reservation_path.exists():
                        if read_json(reservation_path) != reservation:
                            raise ValueError('reserved successor reservation changed while acquiring its lock')
                        for name in stage_names:
                            safe_path(run / name).unlink(missing_ok=True)
                    reservation_path.unlink(missing_ok=True)
                    # Its sidecar may already name this successor while registration
                    # or transfer is not committed yet. The exact helper below owns
                    # that replay; a fresh unbound-resource preflight would reject it.
                    return str(existing)
            entries = {item.name for item in run.iterdir()}
            if entries - {reservation_file, MARKER} - stage_names:
                raise ValueError('partially prepared reserved successor contains unowned data')
            if (run / MARKER).exists():
                partial = read_json(run / MARKER)
                expected_marker = {'owner_id': manifest['owner_id'], 'run_dir': str(run),
                    'archive_root': str(root), 'repository_key': repository_key,
                    'scope_sha256': _digest(_json_bytes(scope)),
                    'logical_scope_sha256': _digest(_json_bytes(logical))}
                if (not isinstance(partial, dict) or any(partial.get(key) != value
                        for key, value in expected_marker.items())):
                    raise ValueError('partially prepared successor ownership differs from its reservation')
            review_resource_claims.plan_resource_registration(manifest['temporary_paths'], manifest)
            for name in stage_names:
                safe_path(run / name).unlink(missing_ok=True)
        else:
            review_resource_claims.plan_resource_registration(manifest['temporary_paths'], manifest)
            safe_path(scoped).mkdir(parents=True, exist_ok=True)
            run.mkdir()
        # The immutable source intent authorizes this exact allocation, including
        # an empty directory after mkdir. Keep the reservation until cierre exists.
        atomic_write(reservation_path, _json_bytes(reservation), staging_path=run / (
            '.' + reservation_file + '.' + reserved['reservation_id'] + '.tmp'))
    else:
        review_resource_claims.plan_resource_registration(manifest['temporary_paths'], manifest)
        safe_path(scoped).mkdir(parents=True, exist_ok=True)
        # Exclusive mkdir is the collision/ownership boundary; never adopt an existing run.
        for _ in range(8):
            created = datetime.now(timezone.utc)
            manifest.update(created_at=created.isoformat(), run_id=uuid.uuid4().hex[:20])
            run = scoped / review_layout.run_name(scope, manifest['created_at'], manifest['run_id'], logical_scope_input)
            _validate_layout(run, manifest)
            try:
                run.mkdir()
                break
            except FileExistsError:
                continue
        else:
            raise ValueError('cannot allocate a unique owned review run')
    marker = {'owner_id': manifest['owner_id'], 'run_dir': str(run), 'archive_root': str(root),
              'repository_key': repository_key, 'scope_sha256': _digest(_json_bytes(scope)),
              'logical_scope_sha256': _digest(_json_bytes(logical))}
    try:
        _append_trace_events(run, manifest, marker,
                             [_milestone('prepare', 'Owned archive prepared with pinned scope'),
                              _profile_event(selection)])
    except OSError:
        try:
            recovered_run, recovered, recovered_marker = _load_run(run)
            recovered_marker = _recover_trace(recovered_run, recovered, recovered_marker)
            _verify_files(recovered_run, recovered)
            if (recovered['profile_history'] == [selection]
                    and recovered['trace']['events'] >= 2):
                (recovered_run / reservation_file).unlink(missing_ok=True)
                return str(run)
        except (OSError, ValueError, TypeError, KeyError):
            _remove_unowned_prepare_directory(run, marker)
        raise
    (run / reservation_file).unlink(missing_ok=True)
    return str(run)


@_locked_run
def select_profile(run_dir, selection_input):
    """Capture a profile transition and its trace event as one idempotent mutation."""
    raw = _input_object(selection_input, 'profile selection')
    run, manifest, marker = _load_run(run_dir)
    if manifest['schema_version'] != 8:
        raise ValueError('profile transitions require an archive 8 run')
    marker = _recover_trace(run, manifest, marker)
    _verify_files(run, manifest)
    if manifest['state'] in {'retaining', 'closing', 'complete'}:
        raise ValueError('profile cannot change after retention or closure starts')
    if manifest.get('operation', {}).get('disposition') != 'open':
        raise ValueError('review operation is not open; resume or recover before selecting a profile')
    if set(raw) - review_profiles.INPUT_FIELDS - {'changed_from'}:
        raise ValueError('profile transition input cannot supply archive-assigned identity fields')
    history = manifest['profile_history']
    previous = history[-1]
    try:
        candidate = review_profiles.validate_selection(raw, previous=previous)
    except ValueError:
        raise
    if candidate == previous:
        return manifest
    if candidate['phase'] == 'prepare':
        raise ValueError('profile transitions cannot use prepare phase')
    if len(history) >= review_profiles.MAX_HISTORY:
        raise ValueError('profile history reached its selection limit')
    events = [json.loads(line) for line in (run / review_trace.NAME).read_bytes().splitlines()]
    affected = set(candidate['affected_assignments'])
    for row in manifest.get('assignment_registry', []):
        if row['id'] in affected and review_profiles._assignment_started(row, events):
            raise ValueError('started assignment cannot be affected by a profile transition: ' + row['id'])
    candidate.update(id='S' + str(len(history) + 1).zfill(3),
                     changed_from=previous['profile'],
                     event_id='E' + str(manifest['trace']['events'] + 1).zfill(6))
    manifest['profile_history'] = history + [candidate]
    _append_trace(run, manifest, marker, _profile_event(candidate))
    return manifest


@_locked_run
def register(run_dir, temporary_paths, *, context_input=None, authority=None):
    _, manifest, _ = _load_run(run_dir)
    temporary = _temporary_paths(temporary_paths, manifest)
    with review_resource_claims.session_claim_locks(temporary):
        return _register_locked(run_dir, temporary, context_input=context_input, authority=authority)


def _register_locked(run_dir, temporary_paths, *, context_input=None, authority=None):
    """Register coordinator-verified owned resources before discovery/execution."""
    run, manifest, marker = _load_run(run_dir)
    marker = _recover_trace(run, manifest, marker)
    _verify_files(run, manifest)
    if manifest['state'] not in {'prepared', 'processing'}:
        raise ValueError('register temporary resources before retention')
    if manifest['schema_version'] == 8 and manifest.get('operation', {}).get('disposition') != 'open':
        raise ValueError('review operation is not open; resume or recover before registering resources')
    if manifest['schema_version'] == 8 and context_input is None:
        raise ValueError('archive 8 registration requires captured context, including executors or an explicit empty list')
    temporary = _temporary_paths(temporary_paths, manifest)
    manifests = _temporary_manifests(temporary, manifest)
    executors = _executors(context_input, manifest, temporary)
    assignment_registry = list(manifest.get('assignment_registry', []))
    review_input_capture = manifest.get('review_inputs')
    claim_manifest = copy.deepcopy(manifest)
    claim_manifest.update(temporary_paths=temporary, temporary_manifests=manifests,
                          _claim_run_dir=str(run))
    if manifest['schema_version'] == 8 and context_input is not None:
        context = _input_object(context_input, 'execution context')
        if (context.get('profile') != manifest['profile_history'][-1]['profile']
                or context.get('selection_source') != manifest['profile_history'][0]['selection_source']
                or context.get('profile_history') != manifest['profile_history']):
            raise ValueError('executor context must preserve the profile history captured by the archive')
        if not isinstance(context.get('execution_plan'), list):
            raise ValueError('archive 8 registration requires captured context.execution_plan')
        existing_trace = [json.loads(line) for line in (run / review_trace.NAME).read_bytes().splitlines()]
        if 'assignment_registry' not in manifest and any(
                row.get('kind') in {'agent', 'discovery', 'grouped-verification'}
                and row.get('status') in {'started', 'completed', 'passed', 'failed', 'blocked', 'skipped'}
                and row.get('evidence') for row in existing_trace if isinstance(row, dict)):
            raise ValueError('review work predates assignment capture; restart the review before registering execution')
        supplied_inputs = context.get('review_inputs')
        if supplied_inputs is not None:
            captured = _capture_review_inputs(supplied_inputs, manifest['scope'],
                                              manifest['profile_history'][-1]['profile'],
                                              'execution context review_inputs',
                                              logical_scope_identity=manifest.get('logical_scope', {}).get('identity'))
            if review_input_capture is None:
                if any(row.get('kind') in {'agent', 'discovery', 'grouped-verification'}
                       and row.get('status') in {'started', 'completed', 'passed', 'failed', 'blocked', 'skipped'}
                       and row.get('evidence') for row in existing_trace if isinstance(row, dict)):
                    raise ValueError('review inputs must be captured before assignment work starts; restart the review')
                review_input_capture = captured
            elif captured != review_input_capture:
                raise ValueError('execution context review_inputs cannot replace the original captured identities')
        assignment_registry = review_profiles.merge_assignment_registry(
            assignment_registry, context['execution_plan'], manifest['profile_history'], existing_trace)
        references = {row['reference'] for row in assignment_registry}
        for row in existing_trace:
            if (isinstance(row, dict) and row.get('kind') in {'agent', 'discovery', 'grouped-verification'}
                    and row.get('status') == 'started' and row.get('evidence')
                    and not references.intersection(row['evidence'])):
                raise ValueError('observed assignment start has no captured brief identity; preserve the run and restart')
        if context['execution_plan'] != assignment_registry:
            raise ValueError('context.execution_plan must preserve the complete durable assignment registry')
    rows = list(manifest.get('resource_claims', []))
    plans = review_resource_claims.plan_resource_registration(temporary, claim_manifest, authority=authority)
    pending_writes = []
    if manifest['schema_version'] == 8:
        for raw, plan in zip(temporary, plans):
            if plan['action'] == 'not_workspace':
                continue
            if plan['action'] == 'transfer':
                raise ValueError('resource belongs to another review; use transfer-resources with explicit authority')
            path = safe_path(Path(raw) / review_resource_claims.CLAIM_NAME)
            if plan['action'] in {'claim', 'adopt'}:
                try:
                    current_digest = _digest(path.read_bytes())
                except FileNotFoundError:
                    current_digest = None
                if current_digest != plan['expected_current_sha256']:
                    raise ValueError('resource claim changed after planning; preserve the session and retry')
                pending_writes.append((path, plan['bytes']))
            existing = [row for row in rows if row.get('session_dir') == str(safe_path(raw))]
            if existing and (len(existing) != 1 or existing[0] != plan['row']):
                raise ValueError('review archive already contains a different claim for this session')
            if not existing and plan['row'] is not None:
                rows.append(plan['row'])
        for path, data in pending_writes:
            atomic_write(path, data)
    manifest.update(temporary_paths=temporary, temporary_manifests=manifests, executors=executors)
    if manifest['schema_version'] == 8:
        manifest.update(resource_claims=rows, assignment_registry=assignment_registry,
                        review_inputs=review_input_capture)
    _append_trace(run, manifest, marker, _milestone('register', 'Coordinator-owned temporary resources registered'))
    return manifest


TRANSFER_HISTORY_LIMIT = 64
CLEANUP_RECEIPT_LIMIT = 64


def _validate_cleanup_metadata(manifest):
    """Validate archive-7 cleanup intent and its bounded receipt inventory."""
    if ('cleanup_receipts' in manifest) != ('resource_cleanup' in manifest):
        raise ValueError('resource cleanup metadata fields must be introduced together')
    receipts = manifest.get('cleanup_receipts', [])
    if not isinstance(receipts, list) or len(receipts) > CLEANUP_RECEIPT_LIMIT:
        raise ValueError('invalid or oversized resource cleanup receipt history')
    by_id = {}
    for receipt in receipts:
        if (not isinstance(receipt, dict)
                or set(receipt) != {'session_id', 'run_id', 'claim_id', 'claim_sha256'}
                or not all(isinstance(receipt.get(key), str) and receipt[key] for key in receipt)
                or receipt['run_id'] != manifest.get('run_id')
                or not re.fullmatch(r'RC-[0-9a-f]{32}', receipt['claim_id'])
                or not CHECKPOINT_HASH.fullmatch(receipt['claim_sha256'])
                or receipt['claim_id'] in by_id):
            raise ValueError('invalid or duplicate resource cleanup receipt')
        by_id[receipt['claim_id']] = receipt
    claim_rows = [row for row in manifest.get('resource_claims', [])
                  if isinstance(row, dict) and isinstance(row.get('claim_id'), str)]
    claims = {row['claim_id']: row for row in claim_rows}
    if len(claims) != len(claim_rows):
        raise ValueError('duplicate resource claim IDs block cleanup verification')
    for claim_id, receipt in by_id.items():
        row = claims.get(claim_id)
        if (row is None or row.get('status') != 'released'
                or any(row.get(key) != receipt[key]
                       for key in ('session_id', 'claim_sha256'))
                or row.get('release_claim_sha256') != receipt['claim_sha256']):
            raise ValueError('resource cleanup receipt does not match a released claim')
    if 'cleanup_receipts' in manifest:
        for claim_id, row in claims.items():
            if row.get('status') == 'released' and claim_id not in by_id:
                raise ValueError('released resource claim has no durable cleanup receipt')

    intent = manifest.get('resource_cleanup')
    if intent is None:
        if any(row.get('status') == 'releasing' for row in manifest.get('resource_claims', [])
               if isinstance(row, dict)):
            raise ValueError('resource claim is releasing without a durable cleanup intent')
        return
    fields = {'schema_version', 'operation_id', 'status', 'run_id', 'session_id', 'claim_id',
              'claim_sha256', 'session_dir', 'repository_path', 'worktrees', 'started_at',
              'completed_at', 'completion_source'}
    if (not isinstance(intent, dict) or set(intent) != fields or intent.get('schema_version') != 1
            or intent.get('status') not in {'pending', 'complete'}
            or not isinstance(intent.get('operation_id'), str)
            or not re.fullmatch(r'CL-[0-9a-f]{32}', intent['operation_id'])
            or intent.get('run_id') != manifest.get('run_id')
            or intent.get('repository_path') != manifest.get('repository_path')
            or not isinstance(intent.get('session_id'), str) or not intent['session_id']
            or not isinstance(intent.get('claim_id'), str)
            or not re.fullmatch(r'RC-[0-9a-f]{32}', intent['claim_id'])
            or not isinstance(intent.get('claim_sha256'), str)
            or not CHECKPOINT_HASH.fullmatch(intent['claim_sha256'])
            or not isinstance(intent.get('session_dir'), str)
            or not isinstance(intent.get('repository_path'), str)
            or not isinstance(intent.get('worktrees'), list) or len(intent['worktrees']) > 32
            or any(not isinstance(path, str) for path in intent['worktrees'])
            or len(set(intent['worktrees'])) != len(intent['worktrees'])):
        raise ValueError('invalid durable resource cleanup intent')
    safe_path(intent['session_dir'])
    safe_path(intent['repository_path'])
    for path in intent['worktrees']:
        safe_path(path)
    for key in ('started_at', 'completed_at'):
        value = intent.get(key)
        if value is not None:
            try:
                parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
                if parsed.utcoffset() is None:
                    raise ValueError('timezone required')
            except (AttributeError, TypeError, ValueError) as exc:
                raise ValueError('invalid resource cleanup timestamp') from exc
    row = claims.get(intent['claim_id'])
    if (row is None or any(row.get(key) != intent[key]
                           for key in ('session_id', 'session_dir', 'claim_sha256'))):
        raise ValueError('resource cleanup intent does not match its claimed session')
    if intent['status'] == 'pending':
        if (row.get('status') != 'releasing' or intent.get('completed_at') is not None
                or intent.get('completion_source') is not None
                or intent['claim_id'] in by_id):
            raise ValueError('pending resource cleanup intent conflicts with claim state')
    elif (row.get('status') != 'released' or intent.get('completed_at') is None
          or intent.get('completion_source') not in {'review_workspace.cleanup', 'review_artifacts.recovery'}
          or row.get('released_by') != intent.get('completion_source')
          or row.get('release_claim_sha256') != intent.get('claim_sha256')
          or by_id.get(intent['claim_id']) != {key: intent[key] for key in
              ('session_id', 'run_id', 'claim_id', 'claim_sha256')}):
        raise ValueError('completed resource cleanup intent has no exact release receipt')

    close_observation = manifest.get('close_observation')
    if close_observation is not None:
        observed_receipts = close_observation.get('released_claims') if isinstance(close_observation, dict) else None
        receipts_match = (observed_receipts == receipts if isinstance(close_observation, dict)
                          and close_observation.get('cleanup') != 'pending'
                          else isinstance(observed_receipts, list)
                          and receipts[:len(observed_receipts)] == observed_receipts)
        if ('cleanup_receipts' not in manifest or 'resource_cleanup' not in manifest
                or not isinstance(close_observation, dict)
                or set(close_observation) != {'cleanup', 'residuals', 'released_claims'}
                or close_observation.get('cleanup') not in {'complete', 'not_needed', 'pending'}
                or not isinstance(close_observation.get('residuals'), list)
                or not isinstance(close_observation.get('released_claims'), list)
                or not receipts_match):
            raise ValueError('invalid or detached durable close observation')
        residuals = [safe_path(raw) for raw in close_observation['residuals']
                     if isinstance(raw, str)]
        registered_paths = {safe_path(raw) for raw in manifest.get('temporary_paths', [])}
        if (len(residuals) != len(close_observation['residuals'])
                or len(set(residuals)) != len(residuals)
                or set(residuals) - registered_paths
                or close_observation['cleanup'] in {'complete', 'not_needed'} and residuals
                or close_observation['cleanup'] == 'not_needed' and manifest.get('temporary_paths')):
            raise ValueError('durable close observation has invalid residual resources')
        if manifest.get('state') == 'complete' and (
                close_observation['cleanup'] != manifest.get('cleanup')
                or [str(path) for path in residuals] != manifest.get('residuals', [])):
            raise ValueError('completed archive differs from its durable close observation')


def normalize_transfer_history(manifest):
    """Read both the current transfer list and the prior singular archive-7 slot."""
    history = manifest.get('resource_transfers')
    legacy = manifest.get('resource_transfer')
    if history is None:
        rows = [] if legacy is None else [copy.deepcopy(legacy)]
    elif isinstance(history, list):
        rows = copy.deepcopy(history)
        if legacy is not None:
            _validate_transfer_intent(legacy)
            matches = [row for row in rows if isinstance(row, dict)
                       and row.get('transfer_id') == legacy.get('transfer_id')]
            if matches and matches[0] != legacy:
                raise ValueError('legacy and current resource transfer records conflict')
            if not matches:
                rows.append(copy.deepcopy(legacy))
    else:
        raise ValueError('resource transfer history must be a list')
    if len(rows) > TRANSFER_HISTORY_LIMIT:
        raise ValueError('resource transfer history exceeds the 64-entry limit')
    identifiers = set()
    pending = 0
    for row in rows:
        _validate_transfer_intent(row)
        identifier = row['transfer_id']
        if identifier in identifiers:
            raise ValueError('duplicate transfer_id in resource transfer history')
        identifiers.add(identifier)
        pending += row['status'] == 'pending'
    if pending > 1:
        raise ValueError('resource transfer history contains more than one pending transfer')
    return rows


def _store_transfer(manifest, intent):
    rows = normalize_transfer_history(manifest)
    matches = [index for index, row in enumerate(rows) if row['transfer_id'] == intent['transfer_id']]
    if len(matches) > 1:
        raise ValueError('duplicate transfer_id in resource transfer history')
    if matches:
        prior = rows[matches[0]]
        before, after = dict(prior), dict(intent)
        before.pop('status', None)
        before.pop('completed_at', None)
        after.pop('status', None)
        after.pop('completed_at', None)
        if before != after or prior['status'] == 'complete' and intent['status'] != 'complete':
            raise ValueError('resource transfer retry differs from its preserved intent')
        rows[matches[0]] = copy.deepcopy(intent)
    else:
        if len(rows) >= TRANSFER_HISTORY_LIMIT:
            raise ValueError('resource transfer history reached the 64-entry limit')
        if any(row['status'] == 'pending' for row in rows):
            raise ValueError('another resource transfer is already pending for this run')
        rows.append(copy.deepcopy(intent))
    manifest.pop('resource_transfer', None)
    manifest['resource_transfers'] = rows
    return rows


def transfer_resources(source_run, successor_run, paths, *, authority, controller,
                       _restart_operation_id=None):
    """Transfer explicitly selected claimed workspaces under both run locks."""
    source_path, successor_path = safe_path(source_run), safe_path(successor_run)
    selected_raw_paths = [str(safe_path(path)) for path in paths]
    if not selected_raw_paths or len({os.path.normcase(path) for path in selected_raw_paths}) != len(paths):
        raise ValueError('resource transfer requires a nonempty unique explicit path list')
    selected_paths = sorted(selected_raw_paths, key=os.path.normcase)
    authority = review_resource_claims._authority(authority)
    _assert_not_restart_abandoned(_load_run(source_path)[1])
    _assert_not_restart_abandoned(_load_run(successor_path)[1])
    with run_locks([source_path, successor_path]), review_resource_claims.session_claim_locks(selected_paths):
        source, source_manifest, source_marker = _load_run(source_path)
        successor, next_manifest, next_marker = _load_run(successor_path)
        _assert_not_restart_abandoned(source_manifest)
        _assert_not_restart_abandoned(next_manifest)
        active_restart = _active_restart_operation(source, source_manifest)
        if (active_restart is not None
                and active_restart['operation_id'] != _restart_operation_id):
            raise ValueError('a durable restart is pending; recover source ' + str(source)
                             + ' for restart operation ' + active_restart['operation_id'])
        source_marker = _recover_trace(source, source_manifest, source_marker)
        next_marker = _recover_trace(successor, next_manifest, next_marker)
        restarting_checkpoint = active_restart is not None and _restart_operation_id == active_restart['operation_id']
        _verify_files(source, source_manifest, allow_resource_transfer=True,
                      allow_checkpoint_transaction=restarting_checkpoint)
        _verify_files(successor, next_manifest, allow_resource_transfer=True)
        if source == successor:
            raise ValueError('source and successor review runs must differ')
        if (source_manifest.get('schema_version') != 8 or next_manifest.get('schema_version') != 8
                or source_manifest.get('repository_key') != next_manifest.get('repository_key')
                or source_manifest.get('repository_path') != next_manifest.get('repository_path')
                or source_manifest.get('scope') != next_manifest.get('scope')):
            raise ValueError('resource transfer requires archive-7 runs for the same repository and scope')
        for label, value in (('source', source_manifest), ('successor', next_manifest)):
            if value.get('state') not in {'prepared', 'processing'}:
                raise ValueError(label + ' run must be prepared or processing; retaining/closing runs cannot transfer')
        normalized_controller = _controller(controller, next_manifest['controller']['identity'])
        source_history = normalize_transfer_history(source_manifest)
        next_history = normalize_transfer_history(next_manifest)
        pair = [row for row in source_history + next_history
                if row['source_run'] == str(source) and row['successor_run'] == str(successor)]
        by_id = {}
        for row in pair:
            prior = by_id.get(row['transfer_id'])
            if prior is not None:
                left, right = dict(prior), dict(row)
                left.pop('status', None); left.pop('completed_at', None)
                right.pop('status', None); right.pop('completed_at', None)
                if left != right:
                    raise ValueError('source and successor transfer histories conflict')
            else:
                by_id[row['transfer_id']] = row
        if len(by_id) > 1:
            raise ValueError('multiple transfers exist for the same source and successor runs')
        intent = next(iter(by_id.values()), None)
        current_transfer_id = intent['transfer_id'] if intent else None
        for history in (source_history, next_history):
            if any(row['status'] == 'pending' and row['transfer_id'] != current_transfer_id for row in history):
                raise ValueError('another resource transfer is already pending for this run')

        if intent is not None:
            _validate_transfer_intent(intent)
            expected = {'source_run': str(source), 'successor_run': str(successor),
                        'source_run_id': source_manifest['run_id'],
                        'successor_run_id': next_manifest['run_id'],
                        'source_owner_id': source_manifest['owner_id'],
                        'successor_owner_id': next_manifest['owner_id'],
                        'repository_key': source_manifest['repository_key'],
                        'authority': authority, 'controller': normalized_controller}
            if any(intent.get(key) != value for key, value in expected.items()) or \
                    {item['session_dir'] for item in intent['items']} != set(selected_paths):
                raise ValueError('completed or pending transfer request differs from its preserved inputs')
            source_matches = [row for row in source_history if row['transfer_id'] == intent['transfer_id']]
            next_matches = [row for row in next_history if row['transfer_id'] == intent['transfer_id']]
            if (source_matches and next_matches and source_matches[0]['status'] == 'complete'
                    and next_matches[0]['status'] == 'complete'):
                for item in intent['items']:
                    review_resource_claims.verify_claim(item['session_dir'], successor)
                return {'status': 'transferred', 'transfer_id': intent['transfer_id'],
                        'source_run': str(source), 'successor_run': str(successor),
                        'resources': [item['session_dir'] for item in intent['items']]}
            # A partially persisted completion is replayed using its original bytes.
        else:
            if source_manifest.get('state') in {'retaining', 'closing', 'complete'} or \
                    next_manifest.get('state') in {'retaining', 'closing', 'complete'}:
                raise ValueError('retaining, closing or complete review runs cannot transfer resources')
            if source_manifest.get('operation', {}).get('disposition') not in {'open', 'paused', 'blocked'}:
                raise ValueError('source review is already superseded or complete')
            if next_manifest.get('operation', {}).get('disposition') != 'open':
                raise ValueError('successor review must be open before claiming resources')
            previous = next_manifest.get('previous_run')
            lineage = next_manifest.get('lineage')
            if previous not in (None, str(source)):
                raise ValueError('successor previous_run conflicts with the requested transfer source')
            if not isinstance(lineage, dict) or lineage.get('source_run') not in (None, str(source)):
                raise ValueError('successor lineage conflicts with the requested transfer source')
            if previous == str(source) and (lineage.get('kind') != 'restart' or lineage.get('source_run') != str(source)):
                raise ValueError('successor previous_run and lineage identify different restart sources')

            source_rows = list(source_manifest.get('resource_claims', []))
            in_flight_rows = [row for row in source_rows if row.get('status') == 'releasing']
            if in_flight_rows:
                raise ValueError('resource cleanup is already in progress; recover it before transfer')
            active_rows = [row for row in source_rows if row.get('status') == 'owned']
            active_paths = {os.path.normcase(str(safe_path(row['session_dir']))) for row in active_rows}
            selected_path_keys = {os.path.normcase(str(safe_path(path))) for path in selected_paths}
            if selected_path_keys != active_paths:
                raise ValueError('transfer must include every active resource claim; partial transfer is refused '
                                 '(selected=' + str(len(selected_paths)) + ', active=' + str(len(active_paths)) + ')')
            if len(source_history) >= TRANSFER_HISTORY_LIMIT or len(next_history) >= TRANSFER_HISTORY_LIMIT:
                raise ValueError('resource transfer history reached the 64-entry limit')
            items = []
            registered_source_paths = {os.path.normcase(str(safe_path(path)))
                                       for path in source_manifest.get('temporary_paths', [])}
            for raw in selected_paths:
                if os.path.normcase(str(safe_path(raw))) not in registered_source_paths:
                    raise ValueError('every transferred session must be registered to the source run')
                if not safe_path(raw).is_dir():
                    raise ValueError('every active resource claim must be present before transfer')
                old_sidecar = review_resource_claims.verify_claim(raw, source,
                    allow_checkpoint_transaction=restarting_checkpoint)
                plan = review_resource_claims.plan_claim(
                    raw, successor, next_manifest, source_run=source,
                    authority=authority, allow_checkpoint_transaction=restarting_checkpoint)
                if plan['action'] != 'transfer' or old_sidecar['claim_id'] != plan['sidecar']['claim_id']:
                    raise ValueError('resource transfer plan does not match the verified source claim')
                source_rows = [row for row in source_manifest.get('resource_claims', [])
                               if row.get('claim_id') == old_sidecar['claim_id']]
                if len(source_rows) != 1 or source_rows[0].get('status') != 'owned':
                    raise ValueError('source archive does not have one active claim for the session')
                items.append({'session_dir': raw, 'claim_id': old_sidecar['claim_id'],
                              'old_claim_sha256': plan['expected_current_sha256'],
                              'new_claim': plan['sidecar'], 'new_claim_sha256': _digest(plan['bytes'])})
            intent = {'schema_version': 1, 'transfer_id': 'RT-' + uuid.uuid4().hex,
                      'status': 'pending', 'source_run': str(source), 'successor_run': str(successor),
                      'source_run_id': source_manifest['run_id'], 'successor_run_id': next_manifest['run_id'],
                      'source_owner_id': source_manifest['owner_id'],
                      'successor_owner_id': next_manifest['owner_id'],
                      'repository_key': source_manifest['repository_key'], 'authority': authority,
                      'controller': normalized_controller, 'items': items}

        if intent['status'] == 'pending':
            _store_transfer(source_manifest, intent)
            source_marker = _save_manifest(source, source_manifest, source_marker)
            _store_transfer(next_manifest, intent)
            next_marker = _save_manifest(successor, next_manifest, next_marker)

        _validate_transfer_intent(intent)
        for item in intent['items']:
            sidecar_path = safe_path(Path(item['session_dir']) / review_resource_claims.CLAIM_NAME)
            try:
                current_bytes = sidecar_path.read_bytes()
            except FileNotFoundError as exc:
                raise ValueError('claimed session disappeared during resource transfer') from exc
            current_hash = _digest(current_bytes)
            new_bytes = review_resource_claims._encoded(item['new_claim'])
            if current_hash == item['new_claim_sha256']:
                continue
            if current_hash != item['old_claim_sha256']:
                raise ValueError('resource claim changed after transfer intent; preserve the session')
            atomic_write(sidecar_path, new_bytes)

        transfer_id = intent['transfer_id']
        moved_paths = {item['session_dir'] for item in intent['items']}
        moved_keys = {os.path.normcase(path) for path in moved_paths}
        source_rows = list(source_manifest.get('resource_claims', []))
        next_rows = list(next_manifest.get('resource_claims', []))
        for item in intent['items']:
            old_rows = [row for row in source_rows if row.get('claim_id') == item['claim_id']]
            if len(old_rows) != 1 or old_rows[0].get('session_dir') != item['session_dir']:
                raise ValueError('source archive claim changed during transfer')
            if old_rows[0].get('status') == 'owned':
                old_rows[0].update(status='transferred', transfer_id=transfer_id,
                                   successor_run_id=next_manifest['run_id'])
            elif not (old_rows[0].get('status') == 'transferred'
                      and old_rows[0].get('transfer_id') == transfer_id):
                raise ValueError('source archive claim is not transferable')
            new_row = review_resource_claims._claim_row(
                item['new_claim'], claim_sha256=item['new_claim_sha256'],
                adopted=item['new_claim']['adopted'], authority=item['new_claim']['authority'],
                transferred_from=str(source), transfer_id=transfer_id)
            if not any(row.get('claim_id') == item['claim_id'] for row in next_rows):
                next_rows.append(new_row)
            elif not any(row == new_row for row in next_rows if row.get('claim_id') == item['claim_id']):
                raise ValueError('successor archive already has a different claim for this session')

        source_manifest['resource_claims'] = source_rows
        source_manifest['temporary_paths'] = [path for path in source_manifest.get('temporary_paths', [])
                                              if os.path.normcase(path) not in moved_keys]
        source_manifest['temporary_manifests'] = _temporary_manifests(
            source_manifest['temporary_paths'], source_manifest)
        source_manifest['operation'].update(disposition='superseded', reason=authority,
                                            source='transfer-resources', phase='restart',
                                            successor=str(successor))
        next_manifest['resource_claims'] = next_rows
        combined_paths = list(next_manifest.get('temporary_paths', [])) + sorted(moved_paths)
        unique_paths = {}
        for path in combined_paths:
            unique_paths.setdefault(os.path.normcase(path), path)
        next_manifest['temporary_paths'] = list(unique_paths.values())
        next_manifest['temporary_manifests'] = _temporary_manifests(
            next_manifest['temporary_paths'], next_manifest)
        next_manifest['previous_run'] = next_manifest.get('previous_run') or str(source)
        next_manifest['lineage'] = {'kind': 'restart', 'source_run': str(source)}
        source_marker = _save_manifest(source, source_manifest, source_marker)
        next_marker = _save_manifest(successor, next_manifest, next_marker)

        for run, manifest, marker, other in ((source, source_manifest, source_marker, successor),
                                             (successor, next_manifest, next_marker, source)):
            summary = 'Resource transfer ' + transfer_id + ' to ' + str(successor)
            if run == source:
                summary = 'Resource transfer ' + transfer_id + ' from ' + str(source)
            trace = [json.loads(line) for line in safe_path(run / review_trace.NAME).read_text(
                encoding='utf-8').splitlines()]
            if not any(event.get('kind') == 'handoff' and event.get('summary') == summary for event in trace):
                relation_target = str(other)
                event = {'kind': 'handoff', 'status': 'completed', 'summary': summary,
                         'authority': authority, 'provenance': {'kind': 'helper', 'source': 'review_artifacts:transfer-resources'},
                         'evidence': ['cierre.json'],
                         'relations': [{'relation': 'supersedes', 'target': relation_target}]}
                marker = _append_trace(run, manifest, marker, event)
            if run == source:
                source_marker = marker
            else:
                next_marker = marker

        completed = copy.deepcopy(intent)
        if completed['status'] != 'complete':
            completed['status'] = 'complete'
            completed['completed_at'] = datetime.now(timezone.utc).isoformat()
        _store_transfer(source_manifest, completed)
        _store_transfer(next_manifest, completed)
        _save_manifest(source, source_manifest, source_marker)
        _save_manifest(successor, next_manifest, next_marker)
        return {'status': 'transferred', 'transfer_id': transfer_id,
                'source_run': str(source), 'successor_run': str(successor),
                'resources': sorted(moved_paths)}


def _validate_transfer_intent(value):
    if not isinstance(value, dict):
        raise ValueError('invalid resource transfer intent')
    fields = {'schema_version', 'transfer_id', 'status', 'source_run', 'successor_run',
              'source_run_id', 'successor_run_id', 'source_owner_id', 'successor_owner_id',
              'repository_key', 'authority', 'controller', 'items'}
    if set(value) == fields | {'completed_at'}:
        fields = fields | {'completed_at'}
    if (not isinstance(value, dict) or set(value) != fields
            or value.get('schema_version') != 1
            or not isinstance(value.get('transfer_id'), str) or not re.fullmatch(r'RT-[0-9a-f]{32}', value['transfer_id'])
            or value.get('status') not in {'pending', 'complete'}
            or not all(isinstance(value.get(key), str) and value[key] for key in
                       ('source_run', 'successor_run', 'source_run_id', 'successor_run_id',
                        'source_owner_id', 'successor_owner_id', 'repository_key', 'authority'))
            or not isinstance(value.get('controller'), dict)
            or not isinstance(value.get('items'), list) or not value['items']):
        raise ValueError('invalid resource transfer intent')
    if (not re.fullmatch(r'[0-9a-f]{20}', value['source_run_id'])
            or not re.fullmatch(r'[0-9a-f]{20}', value['successor_run_id'])
            or not re.fullmatch(r'[0-9a-f]{32}', value['source_owner_id'])
            or not re.fullmatch(r'[0-9a-f]{32}', value['successor_owner_id'])
            or not re.fullmatch(r'[0-9a-f]{20}', value['repository_key'])):
        raise ValueError('resource transfer identities are invalid')
    safe_path(value['source_run'])
    safe_path(value['successor_run'])
    if value['status'] == 'complete':
        completed = value.get('completed_at')
        try:
            if not isinstance(completed, str) or datetime.fromisoformat(completed.replace('Z', '+00:00')).utcoffset() is None:
                raise ValueError
        except ValueError as exc:
            raise ValueError('completed resource transfer needs an observed timestamp') from exc
    seen_paths = set()
    for item in value['items']:
        if (not isinstance(item, dict) or set(item) != {
                'session_dir', 'claim_id', 'old_claim_sha256', 'new_claim', 'new_claim_sha256'}
                or not isinstance(item['session_dir'], str)
                or not isinstance(item['claim_id'], str)
                or not re.fullmatch(r'RC-[0-9a-f]{32}', item['claim_id'])
                or not isinstance(item['old_claim_sha256'], str)
                or not CHECKPOINT_HASH.fullmatch(item['old_claim_sha256'])
                or not isinstance(item['new_claim_sha256'], str)
                or not CHECKPOINT_HASH.fullmatch(item['new_claim_sha256'])
                or not isinstance(item['new_claim'], dict)
                or _digest(review_resource_claims._encoded(item['new_claim'])) != item['new_claim_sha256']):
            raise ValueError('invalid resource transfer claim plan')
        safe_path(item['session_dir'])
        if item['session_dir'] in seen_paths or item['new_claim'].get('claim_id') != item['claim_id']:
            raise ValueError('resource transfer paths and claims must be unique and bound')
        seen_paths.add(item['session_dir'])


def _recovery_event(manifest, summary, *, status='completed', authority=None, source=None, relation=None):
    event = {'kind': 'interruption', 'status': status, 'summary': summary,
             'actor': copy.deepcopy(manifest.get('controller', {}).get('identity',
                 {'kind': 'coordinator', 'name': 'review coordinator', 'provider_id': None})),
             'provenance': {'kind': 'tool' if source else 'helper',
                            'source': source or 'review_artifacts:recovery'},
             'evidence': ['cierre.json'], 'authority': authority,
             'occurred_at': datetime.now(timezone.utc).isoformat()}
    if relation is not None:
        event['relations'] = [relation]
    return event


def _takeover_controller(run, manifest, marker, controller, authority):
    """Persist an authorized controller change once, shared by resume and recover."""
    normalized = _controller(controller, manifest.get('controller', {}).get('identity',
        {'kind': 'coordinator', 'name': 'review coordinator', 'provider_id': None}))
    previous = manifest.get('controller')
    if normalized == previous:
        return normalized, marker
    operation = manifest.get('operation', {})
    if manifest.get('state') == 'complete' or operation.get('disposition') in {'complete', 'superseded'}:
        return previous, marker
    if authority is None:
        raise ValueError('controller takeover requires explicit user authority')
    authority = review_resource_claims._authority(authority)
    prior = previous.get('identity', {}).get('name', 'unknown') if isinstance(previous, dict) else 'unknown'
    manifest['controller'] = normalized
    marker = _append_trace(run, manifest, marker, _recovery_event(
        manifest, 'Controller takeover by ' + normalized['identity']['name']
        + '; prior controller recorded as ' + prior,
        authority=authority, relation={'relation': 'follows', 'target': 'E'
            + str(manifest.get('trace', {}).get('events', 0)).zfill(6)}))
    return normalized, marker


def _cleanup_identity(intent):
    return {key: intent[key] for key in ('session_id', 'run_id', 'claim_id', 'claim_sha256')}


def _cleanup_rows(manifest, claim_id):
    return [row for row in manifest.get('resource_claims', [])
            if isinstance(row, dict) and row.get('claim_id') == claim_id]


def _cleanup_resources_remain(intent):
    import review_workspace
    repo = safe_path(intent['repository_path'])
    registered = {str(path.resolve()) for path in review_workspace.registrations(repo)}
    for raw in intent['worktrees']:
        path = safe_path(raw)
        if str(path) in registered or path.exists():
            return True
    return safe_path(intent['session_dir']).exists()


@_locked_run
def begin_resource_cleanup(run_dir, session_dir):
    """Persist a cleanup intent and mark the exact workspace claim as releasing."""
    run, manifest, marker = _load_run(run_dir)
    marker = _recover_trace(run, manifest, marker)
    _verify_files(run, manifest, allow_checkpoint_transaction=
                  manifest.get('operation', {}).get('disposition') == 'superseded')
    if manifest.get('schema_version') != 8:
        raise ValueError('durable resource cleanup requires archive schema 7')
    if manifest.get('state') in {'retaining', 'complete'}:
        raise ValueError('resource cleanup cannot begin during retention or after closure')
    if manifest.get('operation', {}).get('disposition') == 'complete':
        raise ValueError('completed review cannot begin resource cleanup')
    session = safe_path(session_dir)
    if not session.exists() or not session.is_dir():
        raise ValueError('cleanup requires the existing claimed session directory')
    sidecar = review_resource_claims.verify_claim(session, run)
    rows = _cleanup_rows(manifest, sidecar['claim_id'])
    if len(rows) != 1:
        raise ValueError('cleanup requires one exact durable resource claim')
    row = rows[0]
    if row.get('status') not in {'owned', 'releasing'}:
        raise ValueError('resource claim is not active for cleanup')
    intent = manifest.get('resource_cleanup')
    if isinstance(intent, dict) and intent.get('status') == 'pending':
        if (_cleanup_identity(intent) == {
                'session_id': sidecar['session_id'], 'run_id': manifest['run_id'],
                'claim_id': sidecar['claim_id'], 'claim_sha256': review_resource_claims._digest(
                    review_resource_claims._encoded(sidecar))}
                and intent.get('session_dir') == str(session)):
            return copy.deepcopy(intent)
        raise ValueError('another resource cleanup is pending; recover it before starting cleanup')
    receipts = manifest.get('cleanup_receipts', [])
    if len(receipts) >= CLEANUP_RECEIPT_LIMIT:
        raise ValueError('resource cleanup receipt history reached the 64-entry limit')
    if any(receipt.get('claim_id') == sidecar['claim_id'] for receipt in receipts):
        raise ValueError('resource claim already has a durable cleanup receipt')
    if row.get('status') != 'owned':
        raise ValueError('releasing resource claim has no matching pending cleanup intent')

    workspace_data = review_resource_claims._workspace(session)
    if workspace_data is None:
        raise ValueError('cleanup requires a valid owned workspace session')
    workspace = workspace_data[1]
    import review_workspace
    registered = {str(path.resolve()) for path in review_workspace.registrations(safe_path(workspace['repo']))}
    worktrees = []
    for entry in workspace['workspaces']:
        path = safe_path(entry['path'])
        if path.exists() and str(path) not in registered:
            raise ValueError('workspace is no longer registered; preserve and inspect it: ' + str(path))
        if str(path) in registered:
            worktrees.append(str(path))
    if len(worktrees) > 32:
        raise ValueError('cleanup worktree inventory exceeds the 32-entry limit')
    claim_hash = review_resource_claims._digest(review_resource_claims._encoded(sidecar))
    intent = {'schema_version': 1, 'operation_id': 'CL-' + uuid.uuid4().hex,
              'status': 'pending', 'run_id': manifest['run_id'], 'session_id': sidecar['session_id'],
              'claim_id': sidecar['claim_id'], 'claim_sha256': claim_hash,
              'session_dir': str(session), 'repository_path': str(safe_path(workspace['repo'])),
              'worktrees': worktrees, 'started_at': datetime.now(timezone.utc).isoformat(),
              'completed_at': None, 'completion_source': None}
    row['status'] = 'releasing'
    manifest['resource_cleanup'] = intent
    _append_trace(run, manifest, marker, _milestone('cleanup',
                  'Cleanup started for a verified claimed review workspace', status='started',
                  evidence=['cierre.json#resource_cleanup']))
    return copy.deepcopy(intent)


def _finish_resource_cleanup_locked(run, manifest, marker, observation, *, completion_source):
    intent = manifest.get('resource_cleanup')
    if not isinstance(intent, dict):
        raise ValueError('no durable resource cleanup intent exists')
    fields = {'operation_id', 'run_id', 'session_id', 'claim_id', 'claim_sha256'}
    if not isinstance(observation, dict) or set(observation) != fields:
        raise ValueError('cleanup completion must identify its exact durable operation and claim')
    expected = {'operation_id': intent['operation_id'], **_cleanup_identity(intent)}
    if observation != expected:
        raise ValueError('cleanup completion differs from the durable cleanup intent')
    if intent['status'] == 'complete':
        receipt = {key: intent[key] for key in ('session_id', 'run_id', 'claim_id', 'claim_sha256')}
        if receipt not in manifest.get('cleanup_receipts', []):
            raise ValueError('completed cleanup has no durable matching receipt')
        return {'status': 'released', 'receipt': receipt, 'operation_id': intent['operation_id']}
    if intent['status'] != 'pending':
        raise ValueError('unknown resource cleanup state')
    if _cleanup_resources_remain(intent):
        raise ValueError('cleanup cannot be completed while its session or registered worktrees remain')
    rows = _cleanup_rows(manifest, intent['claim_id'])
    if len(rows) != 1 or rows[0].get('status') != 'releasing':
        raise ValueError('cleanup intent no longer matches one releasing resource claim')
    receipt = {key: intent[key] for key in ('session_id', 'run_id', 'claim_id', 'claim_sha256')}
    receipts = manifest.setdefault('cleanup_receipts', [])
    existing = [row for row in receipts if row.get('claim_id') == intent['claim_id']]
    if existing and existing != [receipt]:
        raise ValueError('resource cleanup retry conflicts with a different durable receipt')
    if not existing:
        if len(receipts) >= CLEANUP_RECEIPT_LIMIT:
            raise ValueError('resource cleanup receipt history reached the 64-entry limit')
        receipts.append(receipt)
    rows[0].update(status='released', released_by=completion_source,
                   release_claim_sha256=intent['claim_sha256'])
    intent.update(status='complete', completed_at=datetime.now(timezone.utc).isoformat(),
                   completion_source=completion_source)
    _append_trace(run, manifest, marker, _milestone('cleanup',
                  'Verified workspace cleanup and recorded its release receipt', status='completed',
                  evidence=['cierre.json#cleanup_receipts']))
    return {'status': 'released', 'receipt': receipt, 'operation_id': intent['operation_id']}


@_locked_run
def finish_resource_cleanup(run_dir, observation):
    """Record a receipt only after the exact session and its worktrees are absent."""
    run, manifest, marker = _load_run(run_dir)
    marker = _recover_trace(run, manifest, marker)
    _verify_files(run, manifest, allow_checkpoint_transaction=
                  manifest.get('operation', {}).get('disposition') == 'superseded')
    if manifest.get('schema_version') != 8:
        raise ValueError('durable resource cleanup requires archive schema 7')
    return _finish_resource_cleanup_locked(run, manifest, marker, observation,
                                           completion_source='review_workspace.cleanup')


@_locked_run
def recover_resource_cleanup(run_dir):
    """Finish a pending cleanup record only when its exact resources are already absent."""
    run, manifest, marker = _load_run(run_dir)
    marker = _recover_trace(run, manifest, marker)
    _verify_files(run, manifest, allow_checkpoint_transaction=
                  manifest.get('operation', {}).get('disposition') == 'superseded')
    if manifest.get('schema_version') != 8:
        raise ValueError('durable resource cleanup requires archive schema 7')
    intent = manifest.get('resource_cleanup')
    if intent is None:
        return {'status': 'none', 'run_id': manifest['run_id']}
    if intent['status'] == 'complete':
        receipt = {key: intent[key] for key in ('session_id', 'run_id', 'claim_id', 'claim_sha256')}
        return {'status': 'released', 'receipt': receipt, 'operation_id': intent['operation_id']}
    if intent['status'] != 'pending':
        raise ValueError('unknown durable resource cleanup status')
    session = safe_path(intent['session_dir'])
    if session.exists():
        sidecar = review_resource_claims.verify_claim(session, run)
        if (sidecar.get('session_id') != intent['session_id']
                or sidecar.get('claim_id') != intent['claim_id']
                or review_resource_claims._digest(review_resource_claims._encoded(sidecar))
                != intent['claim_sha256']):
            raise ValueError('pending cleanup session differs from the exact verified cleanup intent')
    if _cleanup_resources_remain(intent):
        return {'status': 'pending', 'operation_id': intent['operation_id'],
                'reason': 'The recorded session or one of its worktrees still exists; retry workspace cleanup.'}
    observation = {'operation_id': intent['operation_id'], **_cleanup_identity(intent)}
    return _finish_resource_cleanup_locked(run, manifest, marker, observation,
                                           completion_source='review_artifacts.recovery')


@_locked_run
def pause(run_dir, *, authority, reason, phase):
    """Record an explicit user-directed pause without discarding the open run."""
    run, manifest, marker = _load_run(run_dir)
    marker = _recover_trace(run, manifest, marker)
    _verify_files(run, manifest)
    if manifest['schema_version'] != 8:
        raise ValueError('new pause transitions require archive 8; preserve legacy history and start a linked run')
    authority = review_resource_claims._authority(authority)
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000 or any(ord(c) < 32 for c in reason):
        raise ValueError('pause reason must be bounded nonempty text')
    if phase not in review_profiles.PHASES:
        raise ValueError('pause phase must identify a known review phase')
    operation = manifest['operation']
    if operation['disposition'] == 'paused' and operation['reason'] == reason and operation['phase'] == phase:
        return manifest
    if operation['disposition'] != 'open' or manifest['state'] in {'retaining', 'closing', 'complete'}:
        raise ValueError('only an open review can be paused')
    operation.update(disposition='paused', reason=reason.strip(), source='explicit-user-pause',
                     phase=phase, successor=None)
    _append_trace(run, manifest, marker, _recovery_event(
        manifest, 'Review paused by explicit request: ' + reason.strip(), status='blocked', authority=authority))
    return manifest


@_locked_run
def block(run_dir, *, source, reason, phase):
    """Record an observed failure; never infer a crash or harness failure."""
    run, manifest, marker = _load_run(run_dir)
    marker = _recover_trace(run, manifest, marker)
    _verify_files(run, manifest)
    if manifest['schema_version'] != 8:
        raise ValueError('new block transitions require archive 8; preserve legacy history and start a linked run')
    if not isinstance(source, str) or not source.strip() or len(source) > 500 or any(ord(c) < 32 for c in source):
        raise ValueError('block source must identify an observed failure source')
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000 or any(ord(c) < 32 for c in reason):
        raise ValueError('block reason must be bounded nonempty text')
    if phase not in review_profiles.PHASES:
        raise ValueError('block phase must identify a known review phase')
    operation = manifest['operation']
    if (operation['disposition'] == 'blocked' and operation['source'] == source
            and operation['reason'] == reason and operation['phase'] == phase):
        return manifest
    if operation['disposition'] not in {'open', 'paused', 'blocked'} or manifest['state'] in {'retaining', 'closing', 'complete'}:
        raise ValueError('only an open, paused or blocked review can record an observed blocker')
    operation.update(disposition='blocked', reason=reason.strip(), source=source.strip(),
                     phase=phase, successor=None)
    _append_trace(run, manifest, marker, _recovery_event(
        manifest, 'Observed review blocker: ' + reason.strip(), status='blocked', source=source.strip()))
    return manifest


def _resource_availability(run, manifest, *, verify_owned=True):
    """One classifier for inspection and mutation gates; absence is not release."""
    claims = {row['session_dir']: row for row in manifest.get('resource_claims', [])}
    receipts = {row['claim_id'] for row in manifest.get('cleanup_receipts', [])}
    resources = []
    for raw in manifest.get('temporary_paths', []):
        path = safe_path(raw)
        row = claims.get(raw, {})
        present, status = path.exists(), row.get('status')
        if status in {'owned', 'releasing'} and present and verify_owned:
            review_resource_claims.verify_claim(path, run)
        if status == 'transferred':
            availability = 'transferred'
        elif status == 'released':
            availability = 'unexpected_present' if present else 'released'
        elif status in {'owned', 'releasing'}:
            availability = ('cleanup_pending' if status == 'releasing' else 'available') if present else (
                'released' if row.get('claim_id') in receipts else 'missing_unknown')
        else:
            availability = 'available' if present else 'missing_unclaimed'
        resources.append({'path': raw, 'present': present, 'claim_status': status, 'availability': availability})
    return resources


@_locked_run
def resume(run_dir, *, controller, authority, current_inputs):
    """Reopen an unchanged archive after explicit continuation/takeover authority."""
    import review_recovery
    run, manifest, marker = _load_run(run_dir)
    marker = _recover_trace(run, manifest, marker)
    _verify_files(run, manifest)
    if manifest['schema_version'] != 8:
        raise ValueError('legacy runs cannot be resumed in place; create a linked archive-7 restart')
    if manifest['state'] in {'retaining', 'closing', 'complete'}:
        raise ValueError('retention/closure has started or completed; recover its transaction or create a new run')
    normalized_inputs = review_recovery.validate_current_inputs(
        current_inputs, manifest, require_applicable=True)
    operation = manifest['operation']
    if operation['disposition'] not in {'open', 'paused', 'blocked'}:
        raise ValueError('superseded or completed review cannot be resumed')
    resources = _resource_availability(run, manifest)
    if any(row['availability'] == 'missing_unknown' for row in resources):
        raise ValueError('claimed workspace is missing_unknown; use an authorized restart without transferring missing resources')
    normalized_controller = _controller(controller, manifest['controller']['identity'])
    changed_controller = normalized_controller != manifest['controller']
    if operation['disposition'] in {'paused', 'blocked'} and authority is None:
        raise ValueError('continuing a paused or blocked review requires explicit user authority')
    if authority is not None:
        authority = review_resource_claims._authority(authority)
    if operation['disposition'] == 'open' and not changed_controller:
        return manifest
    normalized_controller, marker = _takeover_controller(
        run, manifest, marker, normalized_controller, authority)
    manifest['operation'].update(disposition='open', reason=None, source='resume', successor=None)
    manifest['operation']['phase'] = manifest['operation']['phase'] or 'discovery'
    summary = 'Review resumed by ' + normalized_controller['identity']['name']
    _append_trace(run, manifest, marker, _recovery_event(
        manifest, summary, authority=authority, relation={'relation': 'follows', 'target': 'E' +
            str(manifest['trace']['events']).zfill(6)}))
    return manifest


def recover(run_dir, *, controller, authority, current_inputs):
    """Recover only exact helper-owned transactions; return a plan for external work."""
    import review_recovery
    run_path = safe_path(run_dir)
    run, manifest, _ = _load_run(run_path)
    normalized_inputs = review_recovery.validate_current_inputs(
        current_inputs, manifest, require_same_scope=False)
    input_appraisal = review_inputs.compare_inputs(review_recovery._candidate_inputs(manifest), normalized_inputs)
    authority = review_resource_claims._authority(authority) if authority is not None else None
    fallback = manifest.get('controller', {}).get('identity',
        {'kind': 'coordinator', 'name': 'legacy review coordinator', 'provider_id': None})
    normalized_controller = _controller(controller, fallback)
    active_restart = _active_restart_operation(run_path, manifest, include_abandoned=True)
    if active_restart is not None:
        with _restart_lock(run_path):
            run, manifest, _ = _load_run(run_path)
            active_restart = _active_restart_operation(run_path, manifest, include_abandoned=True)
            if active_restart is None:
                return {'status': 'restart_no_longer_pending', 'run_dir': str(run_path),
                        'run_id': manifest.get('run_id'),
                        'actions': [{'action': 'inspect', 'reason': 'The pending restart changed while acquiring its source lock.'}]}
            return _recover_pending_restart(run_path, manifest, active_restart, authority, current_inputs)
    recovery_source = _restart_recovery_source(run, manifest)
    resource_exit = _diagnostic_recovery_route(run, manifest, recovery_source=recovery_source)
    if resource_exit is not None:
        return {'status': 'plan', 'run_dir': str(run), 'run_id': manifest.get('run_id'),
                'input_appraisal': input_appraisal, **resource_exit}
    if recovery_source is not None:
        return {'status': 'restart_pending', 'run_dir': str(run), 'run_id': manifest.get('run_id'),
                'input_appraisal': input_appraisal,
                'actions': [review_recovery._recover_source_action(recovery_source)]}
    return _recover_run_transactions(run_path, normalized_controller, authority, current_inputs, input_appraisal)


class _RestartCancellationUnavailable(ValueError):
    """Verified state which the conservative cancellation protocol cannot unwind."""

    def __init__(self, message, *, phase='successor_work'):
        super().__init__(message)
        self.phase = phase

    def diagnostic(self):
        return {'decision': 'refused', 'phase': self.phase, 'reason': str(self),
                'transaction_pending': True, 'resource_obligations_preserved': True}


def _restart_transfer_denial(intent, manifests):
    pair = [row for manifest in manifests for row in normalize_transfer_history(manifest)
            if row['source_run'] == intent['source']['run_dir']
            and row['successor_run'] == intent['successor']['run_dir']]
    if not pair:
        return None
    phase = 'transfer_durable' if any(row['status'] != 'complete' for row in pair) else 'transfer_committed'
    return _RestartCancellationUnavailable(
        'A durable resource transfer prevents cancellation; preserve its ownership obligations even if the successor is absent.',
        phase=phase)


def _restart_resource_manifests(run, manifest, intent):
    """Read the same verified source/successor pair for every refusal route.

    Mutators hold both run locks while observing a present successor. A missing
    successor never discards durable transfer proof already held by the source.
    """
    _verify_files(run, manifest, allow_checkpoint_transaction=True,
                  allow_resource_transfer=True, allow_pending_trace=True)
    manifests = [manifest]
    successor = safe_path(intent['successor']['run_dir'])
    if (successor / 'cierre.json').exists():
        _, next_manifest, _ = _load_run(successor)
        _verify_restart_successor_identity(successor, next_manifest, intent)
        _verify_files(successor, next_manifest, allow_checkpoint_transaction=True,
                      allow_resource_transfer=True, allow_pending_trace=True)
        manifests.append(next_manifest)
    return manifests


def _independent_review_action(run, reason, operation_id=None):
    result = {'action': 'new_independent_review', 'run_dir': str(run), 'previous_run': None,
              'use_fresh_resources': True, 'requires_explicit_authority': True,
              'reason': reason + ' Preserve the pending transaction; an explicitly authorized prepare without '
                        'previous-run can use fresh resources independently. It does not cancel the original '
                        'operation or clean another review session.'}
    if operation_id is not None:
        result['operation_id'] = operation_id
    return result


def _unavailable_transfer_source_exit(run, manifest):
    for transfer in normalize_transfer_history(manifest):
        if transfer['status'] == 'complete' or transfer['successor_run'] != str(run):
            continue
        if (transfer['successor_run_id'] != manifest['run_id']
                or transfer['successor_owner_id'] != manifest['owner_id']
                or transfer['repository_key'] != manifest['repository_key']):
            raise ValueError('incoming transfer successor identity differs from its local archive')
        operation = manifest.get('restart_operation')
        reservation_path = run / '.review-restart-reservation.json'
        if operation is not None and reservation_path.exists():
            expected = {key: operation[key] for key in ('operation_id', 'intent_sha256', 'reservation_id')}
            expected.update(run_dir=str(run), owner_id=manifest['owner_id'])
            if read_json(reservation_path) != expected:
                raise ValueError('prepared successor reservation differs from its local restart identity')
        try:
            source, source_manifest, _ = _load_run(transfer['source_run'])
            _verify_files(source, source_manifest, allow_checkpoint_transaction=True,
                          allow_resource_transfer=True, allow_pending_trace=True)
        except (OSError, ValueError, TypeError, KeyError):
            _verify_files(run, manifest, allow_checkpoint_transaction=True,
                          allow_resource_transfer=True, allow_pending_trace=True)
            return {'recovery': {'status': 'source_unavailable', 'can_complete': False,
                'transaction_pending': True, 'cancellation_supported': False,
                'source_run': transfer['source_run'], 'blocked_by': ['source_unavailable']},
                'actions': [{'action': 'preserve', 'run_dir': str(run), 'source_run': transfer['source_run'],
                             'reason': 'The exact incoming transfer source cannot be verified; preserve the transaction and resources.'},
                            _independent_review_action(run, 'The incoming transfer cannot finish without its verified source.')]}
        if (source_manifest.get('run_id') != transfer['source_run_id']
                or source_manifest.get('owner_id') != transfer['source_owner_id']
                or source_manifest.get('repository_key') != transfer['repository_key']):
            raise ValueError('incoming transfer source identity differs from its recorded intent')
    return None


def _diagnostic_recovery_route(run, manifest, *, active_restart=None, recovery_source=None):
    if active_restart is not None:
        return _restart_resource_exit(run, manifest, active_restart)
    if recovery_source is not None and recovery_source.get('resource_exit') is not None:
        return recovery_source['resource_exit']
    return _unavailable_transfer_source_exit(run, manifest)


def _restart_resource_exit(run, manifest, active_restart):
    """Read-only guidance; the mutator must recheck eligibility under its locks."""
    intent = active_restart['intent']
    if _find_restart_abandonment(active_restart['intent_path'], intent) is not None:
        return None  # An already authorized cancellation must finish through ordinary recovery.
    successor = safe_path(intent['successor']['run_dir'])
    own_archives = {os.path.normcase(str(run)), os.path.normcase(str(successor))}
    missing, foreign, own_sidecars = [], [], []
    for raw in intent['request']['transfer_paths']:
        session = safe_path(raw)
        if not session.exists():
            missing.append(raw)
            continue
        sidecar_path = safe_path(session / review_resource_claims.CLAIM_NAME)
        if not sidecar_path.exists():
            continue
        sidecar = read_json(sidecar_path)
        if isinstance(sidecar, dict) and sidecar.get('status') == 'owned':
            owner = safe_path(sidecar.get('archive_path', ''))
            if os.path.normcase(str(owner)) not in own_archives:
                review_resource_claims.inspect_claim_identity(session, owner)
                foreign.append(raw)
            else:
                own_sidecars.append((session, owner))
    if not missing and not foreign:
        return None
    # Never turn local corruption into an alternative-work suggestion.
    manifests = _restart_resource_manifests(run, manifest, intent)
    prepared = len(manifests) == 2
    next_manifest = manifests[1] if prepared else None
    transfers = [row for current in manifests for row in normalize_transfer_history(current)]
    claimed = {os.path.normcase(str(safe_path(row['session_dir']))) for current in manifests
               for row in current.get('resource_claims', []) if row.get('status') in {'owned', 'releasing'}}
    claimed.update(os.path.normcase(str(safe_path(item['session_dir']))) for row in transfers
                   if row['source_run'] == str(run) and row['successor_run'] == str(successor)
                   for item in row['items'])
    missing = [raw for raw in missing if os.path.normcase(str(safe_path(raw))) in claimed]
    if not missing and not foreign:
        return None  # missing_unclaimed does not prevent the existing exact replay.
    # A transfer may have replaced its sidecar before persisting its claim row.
    # Only its exact hash-bound bytes may bypass ordinary ownership-row checks.
    for session, owner in own_sidecars:
        permitted = {item[key] for row in transfers if row['status'] == 'pending'
            and row['source_run'] == str(run) and row['successor_run'] == str(successor)
            for item in row['items'] if os.path.normcase(item['session_dir']) == os.path.normcase(str(session))
            for key in ('old_claim_sha256', 'new_claim_sha256')}
        if _digest((session / review_resource_claims.CLAIM_NAME).read_bytes()) in permitted:
            continue
        if (prepared and owner == successor
                and not any(row['source_run'] == str(run) and row['successor_run'] == str(successor)
                            for row in transfers)
                and not any(os.path.normcase(row['session_dir']) == os.path.normcase(str(session))
                            for row in next_manifest.get('resource_claims', []))):
            # register can stop after claiming an adopted session but before its
            # row is saved. Reuse its pure preflight, without performing replay.
            plan = review_resource_claims.plan_claim(session, owner, next_manifest)
            if plan['action'] != 'recover':
                raise ValueError('pending adoption does not match its reserved successor')
        else:
            review_resource_claims.inspect_claim_identity(session, owner)
    blocked_by = []
    denial = _restart_transfer_denial(intent, manifests)
    if denial is not None or any(row['status'] != 'complete' for row in transfers):
        blocked_by.append('transfer_in_progress')
        denial = denial or _RestartCancellationUnavailable(
            'A durable transfer has committed its intent; cancellation cannot infer rollback or release of missing workspaces.',
            phase='transfer_durable')
    if any(row.get('status') == 'releasing' or
           (row.get('status') == 'owned' and safe_path(row['session_dir']).exists())
           for row in manifest.get('resource_claims', [])):
        blocked_by.append('source_claims_present')
        if denial is None:
            denial = _RestartCancellationUnavailable(
                'Present or releasing source claims require their owning resource protocol.', phase='source_claims_present')
    supported = not blocked_by
    if supported and prepared:
        try:
            _empty_adoption_successor(intent, manifest)
        except _RestartCancellationUnavailable as exc:
            supported = False
            blocked_by.append('successor_claims_or_work')
            denial = exc
    if supported:
        action = {'action': 'abandon_restart', 'run_dir': str(run),
            'operation_id': intent['operation_id'], 'intent_path': active_restart['intent_path'],
            'requires_explicit_authority': True,
            'reason': 'A selected resource is missing or held by another review; abandon-restart can cancel this exact request with explicit authority. '
                      'This diagnostic does not execute cancellation or release claims.'}
    else:
        reasons = {'transfer_in_progress': 'A durable resource transfer prevents abandonment.',
                   'source_claims_present': 'Present or releasing source claims prevent abandonment.',
                   'successor_claims_or_work': 'Claims or work already owned by the successor prevent abandonment.'}
        action = _independent_review_action(run, ' '.join(reasons[code] for code in blocked_by), intent['operation_id'])
    actions = [action]
    if denial is not None and manifest.get('schema_version') == 8 and manifest.get('state') != 'complete':
        actions.append({'action': 'record_restart_refusal', 'run_dir': str(run),
            'operation_id': intent['operation_id'], 'intent_path': active_restart['intent_path'],
            'requires_explicit_authority': True, 'phase': denial.phase,
            'reason': 'Record this refusal in the source trace with authority and observed evidence; the restart and all resource obligations remain pending.'})
    return {'missing_resources': missing, 'foreign_resources': foreign, 'cancellation_supported': supported,
            'recovery': {'status': 'cancellation_available' if supported else 'independent_review_required',
                'can_complete': False, 'transaction_pending': True, 'cancellation_supported': supported,
                'source_run': str(run), 'operation_id': intent['operation_id'], 'blocked_by': blocked_by,
                **({'cancellation_denial': denial.diagnostic()} if denial is not None else {})},
            'actions': actions}


def _recover_pending_restart(run_path, manifest, active_restart, authority, current_inputs):
    """Caller holds the source restart lock and reread the active descriptor."""
    intent = active_restart['intent']
    if authority is None:
        raise ValueError('recovering a pending restart requires explicit authority')
    cancellation = _find_restart_abandonment(active_restart['intent_path'], intent)
    if cancellation is not None:
        _finish_restart_abandonment(Path(active_restart['intent_path']), intent, run_path, cancellation)
        return {'status': 'restart_abandoned', 'run_dir': str(run_path), 'run_id': manifest.get('run_id'),
                'actions': [{'action': 'new_review', 'run_dir': str(run_path),
                             'reason': 'The recorded cancellation completed; a fresh request needs a new selection decision.'}]}
    requested_inputs = review_inputs.normalize_inputs(current_inputs)
    requested_inputs.pop('profile', None)
    restart_profile = intent['request']['profile_input']['profile']
    expected_inputs = copy.deepcopy(intent['request']['current_inputs'])
    if (requested_inputs['scope'] == expected_inputs['scope']
            and 'logical_scope_identity' not in requested_inputs):
        requested_inputs['logical_scope_identity'] = review_layout.logical_scope(
            requested_inputs['scope'], intent['request']['logical_scope_input'])['identity']
    expected_inputs['profile'] = restart_profile
    requested_inputs['profile'] = restart_profile
    restart_appraisal = review_inputs.compare_inputs(expected_inputs, requested_inputs)
    if requested_inputs != expected_inputs:
        return {'status': 'restart_pending', 'run_dir': str(run_path), 'run_id': manifest.get('run_id'),
                'successor_run_dir': active_restart['successor_run_dir'],
                'input_appraisal': restart_appraisal,
                'replay_inputs_match': False,
                'actions': [{'action': 'retry_restart',
                             'reason': 'The pending reservation can continue only with the exact current inputs captured by its intent.'}]}
    resource_exit = _restart_resource_exit(run_path, manifest, active_restart)
    if resource_exit is not None:
        return {'status': 'restart_pending', 'run_dir': str(run_path), 'run_id': manifest.get('run_id'),
                'successor_run_dir': active_restart['successor_run_dir'],
                'input_appraisal': restart_appraisal, 'replay_inputs_match': True,
                **resource_exit}
    intent_path = Path(active_restart['intent_path'])
    if not intent_path.exists():
        _write_restart_intent(intent_path, intent, run_path, manifest)
    successor = _complete_restart_intent(intent_path, run_path, manifest)
    return {'status': 'restarted', 'run_dir': str(run_path), 'run_id': manifest.get('run_id'),
            'successor_run_dir': successor, 'input_appraisal': restart_appraisal, 'replay_inputs_match': True,
            'actions': [{'action': 'inspect_successor', 'reason': 'The exact reserved restart completed; no review work was dispatched.'}]}


def _recover_run_transactions(run_path, normalized_controller, authority, current_inputs, input_appraisal):
    import review_recovery
    run, manifest, _ = _load_run(run_path)
    cleanup_intent = manifest.get('resource_cleanup')
    if isinstance(cleanup_intent, dict) and cleanup_intent.get('status') == 'pending':
        cleanup_result = recover_resource_cleanup(run_path)
        if cleanup_result.get('status') == 'pending':
            return _recovery_outcome({'status': 'plan', 'run_dir': str(run_path),
                    'run_id': manifest.get('run_id'),
                    'actions': [{'action': 'retry_cleanup',
                                 'reason': cleanup_result.get('reason', 'The recorded workspace cleanup is incomplete.')}]
                    }, input_appraisal)
        run, manifest, _ = _load_run(run_path)
    pending_transfers = [row for row in normalize_transfer_history(manifest) if row['status'] == 'pending']
    if pending_transfers:
        transfer = pending_transfers[0]
        if authority != transfer['authority']:
            raise ValueError('resource transfer recovery authority differs from its preserved intent')
        transfer_resources(transfer['source_run'], transfer['successor_run'],
                           [item['session_dir'] for item in transfer['items']],
                           authority=transfer['authority'], controller=transfer['controller'])

    with run_locks([run_path]):
        run, manifest, marker = _load_run(run_path)
        active_restart = _active_restart_operation(run, manifest, include_abandoned=True)
        if active_restart is not None:
            return _recover_pending_restart(run, manifest, active_restart, authority, current_inputs)
        normalized_inputs = review_recovery.validate_current_inputs(
            current_inputs, manifest, require_same_scope=False)
        input_appraisal = review_inputs.compare_inputs(review_recovery._candidate_inputs(manifest), normalized_inputs)
        if manifest.get('pending_trace') is not None:
            marker = _recover_trace(run, manifest, marker)
            run, manifest, marker = _load_run(run)
        if manifest.get('restart_abandonment') is not None:
            _verify_files(run, manifest)
            return {'status': 'abandoned', 'run_dir': str(run), 'run_id': manifest.get('run_id'),
                    'input_appraisal': input_appraisal,
                    'actions': [review_recovery._abandoned_source_action(manifest)]}
        if manifest.get('operation', {}).get('disposition') == 'superseded':
            # A checkpoint interrupted before restart is historical provisional
            # state. Do not require its original inputs or commit it on a run
            # whose review work is already owned by its successor.
            _verify_files(run, manifest, allow_checkpoint_transaction=True)
            resources = _resource_availability(run, manifest)
            return {'status': 'superseded', 'run_dir': str(run), 'run_id': manifest.get('run_id'),
                    'successor_run_dir': manifest['operation']['successor'],
                    'input_appraisal': input_appraisal, 'resources': resources,
                    'actions': review_recovery._superseded_actions(resources)}
        checkpoint_transaction = manifest.get('checkpoint_transaction')
        if checkpoint_transaction is not None:
            if manifest['schema_version'] != 8 or manifest['state'] == 'complete':
                raise ValueError('checkpoint transaction is invalid for this review state')
            _verify_files(run, manifest, allow_checkpoint_transaction=True,
                          allow_resource_transfer=True)
            payloads = {}
            missing = []
            for name, expected in checkpoint_transaction['planned_hashes'].items():
                path = safe_path(run / name)
                try:
                    data = path.read_bytes()
                except FileNotFoundError:
                    missing.append(name)
                    continue
                current_hash = _digest(data)
                previous_hash = checkpoint_transaction['previous_hashes'].get(name)
                if current_hash == expected:
                    payloads[name] = data
                elif current_hash == previous_hash:
                    missing.append(name)
                else:
                    raise ValueError('foreign or modified checkpoint bytes block recovery: ' + name)
            if missing:
                return _recovery_outcome({'status': 'plan', 'run_dir': str(run), 'run_id': manifest.get('run_id'),
                        'actions': [{'action': 'retry_checkpoint',
                                     'reason': 'Resupply the original selected inputs: ' + ', '.join(sorted(missing))}]},
                                        input_appraisal)
            _checkpoint_commit(run, manifest, marker, checkpoint_transaction, payloads)
            run, manifest, marker = _load_run(run)

        if manifest.get('schema_version') == 8:
            normalized_controller, marker = _takeover_controller(
                run, manifest, marker, normalized_controller, authority)

        if manifest['state'] in {'retaining', 'closing'}:
            return _recovery_outcome({'status': 'plan', 'run_dir': str(run), 'run_id': manifest.get('run_id'),
                    'actions': [{'action': 'retry_retention' if manifest['state'] == 'retaining' else 'retry_close',
                                 'reason': 'The original final input or cleanup observation must be supplied; no external work was run.'}]},
                                    input_appraisal)
        if any(row['status'] == 'pending' for row in normalize_transfer_history(manifest)):
            raise ValueError('resource transfer remains pending; retry recovery from its recorded source run')
        _verify_files(run, manifest)
        resources = _resource_availability(run, manifest)
        if any(row['availability'] == 'missing_unknown' for row in resources):
            return _recovery_outcome({'status': 'plan', 'run_dir': str(run), 'run_id': manifest.get('run_id'),
                'resources': resources, 'actions': [{'action': 'restart',
                    'reason': 'A claimed session is missing_unknown; preserve its claim and restart without transferring it.'}]},
                input_appraisal)
        disposition = manifest.get('operation', {}).get('disposition', 'complete' if manifest['state'] == 'complete' else 'open')
        if disposition in {'paused', 'blocked'}:
            return _recovery_outcome({'status': disposition, 'run_dir': str(run), 'run_id': manifest.get('run_id'),
                    'actions': [{'action': 'resume', 'reason': 'Explicit continuation authority is required before more work.'},
                                {'action': 'restart', 'reason': 'Create a linked new run when the original scope or sources cannot be continued.'}]},
                                    input_appraisal)
        if disposition == 'complete' or manifest['state'] == 'complete':
            return _recovery_outcome({'status': disposition, 'run_dir': str(run), 'run_id': manifest.get('run_id'),
                    'actions': [{'action': 'show', 'reason': 'Preserve and show the existing immutable result.'},
                                {'action': 'restart', 'reason': 'A repeat must use a new review ID.'}]},
                                    input_appraisal)
        checkpoint = manifest.get('checkpoint')
        if isinstance(checkpoint, dict) and checkpoint.get('gate_errors'):
            return _recovery_outcome({'status': 'provisional', 'run_dir': str(run), 'run_id': manifest.get('run_id'),
                    'checkpoint_id': checkpoint['id'], 'gate_errors': checkpoint['gate_errors'],
                    'actions': [{'action': 'continue', 'reason': 'The checkpoint remains provisional; its gates still apply.'},
                                {'action': 'restart', 'reason': 'A new run is available if history or scope cannot be repaired.'}]},
                                    input_appraisal)
        return _recovery_outcome({'status': 'recovered' if checkpoint_transaction is not None or manifest.get('checkpoint') else 'ready',
                'run_dir': str(run), 'run_id': manifest.get('run_id'),
                'checkpoint_id': checkpoint.get('id') if isinstance(checkpoint, dict) else None,
                'actions': [{'action': 'continue', 'reason': 'Recovery did not dispatch agents, run checks or alter prior worker identity.'}]},
                                  input_appraisal)


def _recovery_outcome(result, appraisal):
    result['input_appraisal'] = appraisal
    if appraisal['applicability'] != 'applicable':
        result['actions'] = [row for row in result.get('actions', [])
                             if row.get('action') not in {'continue', 'resume', 'retry_checkpoint',
                                                          'retry_retention', 'retry_close'}]
        result['actions'].append({'action': 'restart',
            'reason': 'Recovery may restore exact helper-owned bytes, but current inputs are '
                      + appraisal['applicability'] + '; do not continue this review.'})
    return result


def _link_restart(source_run, successor_run, *, authority, controller, moved_paths=(), preserve_claims=False):
    source_path, successor_path = safe_path(source_run), safe_path(successor_run)
    authority = review_resource_claims._authority(authority)
    _load_run(source_path)
    _load_run(successor_path)
    with run_locks([source_path, successor_path]):
        source, old, old_marker = _load_run(source_path)
        successor, new, _ = _load_run(successor_path)
        _assert_not_restart_abandoned(old)
        _assert_not_restart_abandoned(new)
        _verify_files(source, old, allow_checkpoint_transaction=True, allow_resource_transfer=True)
        _verify_files(successor, new)
        if old['schema_version'] != 8 or old['state'] == 'complete':
            return
        if old['operation']['disposition'] == 'superseded':
            if old['operation']['successor'] == str(successor) and new.get('previous_run') == str(source):
                return
            raise ValueError('source review already has a different successor')
        if old['operation']['disposition'] not in {'open', 'paused', 'blocked'}:
            raise ValueError('source review cannot be superseded from its current disposition')
        if not preserve_claims and any(row.get('status') == 'owned' for row in old.get('resource_claims', [])):
            raise ValueError('owned resources require explicit transfer before restart')
        normalized_controller = _controller(controller, new['controller']['identity'])
        old['operation'].update(disposition='superseded', reason=authority,
                                source='restart', phase='restart', successor=str(successor))
        old['temporary_paths'] = [path for path in old.get('temporary_paths', []) if path not in set(moved_paths)]
        old['temporary_manifests'] = _temporary_manifests(old['temporary_paths'], old)
        _append_trace(source, old, old_marker, {'kind': 'handoff', 'status': 'completed',
            'summary': 'Review superseded by linked successor ' + new['run_id'],
            'actor': normalized_controller['identity'],
            'authority': authority, 'evidence': ['cierre.json'],
            'relations': [{'relation': 'supersedes', 'target': str(successor)}]})


def _restart_operation_row(intent):
    return {'operation_id': intent['operation_id'], 'request_sha256': intent['request_sha256'],
            'intent_sha256': intent['intent_sha256'], 'source_run': intent['source']['run_dir'],
            'source_owner_id': intent['source']['owner_id'],
            'reservation_id': intent['successor']['reservation_id']}


def _restart_adoption_context(request):
    selection = _initial_selection(request['profile_input'])
    context = {'profile': selection['profile'], 'selection_source': selection['selection_source'],
               'profile_reference': selection['reference'], 'profile_history': [selection],
               'execution_plan': [], 'executors': [], 'review_inputs': copy.deepcopy(request['current_inputs'])}
    errors = review_profiles.validate_history(context['profile_history'])
    if errors or not isinstance(context['execution_plan'], list) or not isinstance(context['executors'], list):
        raise ValueError('restart adoption context is invalid: ' + '; '.join(errors))
    return _input_object(context, 'restart adoption context')


def _prepare_from_restart_intent(intent_path):
    """Create or resume only the exact destination reserved by the intent."""
    intent_file = safe_path(intent_path)
    intent = read_json(intent_file)
    errors = review_restart.validate_restart_intent(intent)
    if errors:
        raise ValueError('; '.join(errors))
    source_path = safe_path(intent['source']['run_dir'])
    source, source_manifest, _ = _load_run(source_path)
    intent = _read_restart_intent(intent_file, source, source_manifest) if intent_file.exists() else intent
    request = intent['request']
    source_claims = [row for row in source_manifest.get('resource_claims', []) if row.get('status') == 'owned']
    selected = request['transfer_paths']
    active_present = [row for row in source_claims if Path(row['session_dir']).exists()]
    transfer_records = normalize_transfer_history(source_manifest)
    is_transferring = bool(source_claims) or any(
        row.get('source_run') == str(source_path)
        and row.get('successor_run') == intent['successor']['run_dir']
        and {item.get('session_dir') for item in row.get('items', [])} == set(selected)
        for row in transfer_records)
    has_adoption = bool(selected) and not is_transferring
    adoption_context = _restart_adoption_context(request) if has_adoption else None
    current_scope = request['current_inputs']['scope']
    version_path = Path(__file__).resolve().parents[1] / 'SKILL.md'
    try:
        skill_text = version_path.read_text(encoding='utf-8')
        version_match = re.search(r'(?m)^\s+version:\s*["\']?([0-9]+\.[0-9]+\.[0-9]+)', skill_text)
        skill_version = version_match.group(1) if version_match else source_manifest['skill_version']
    except OSError:
        skill_version = source_manifest['skill_version']
    harness = request['harness']
    successor = prepare(source_manifest['repository_path'], current_scope, skill_version, harness['harness'],
        source_manifest['archive_root'], source_path, selected,
        profile_input=request['profile_input'], controller=request['controller'],
        current_inputs=request['current_inputs'], logical_scope_input=request['logical_scope_input'],
        _restart_reservation=intent,
        _harness_identity={key: harness[key] for key in ('harness_id', 'harness_catalog_version',
                                                          'harness_source', 'harness_diagnostics')})
    if selected:
        if is_transferring:
            transfer_resources(source_path, successor, selected, authority=request['authority'],
                               controller=request['controller'],
                               _restart_operation_id=intent['operation_id'])
        elif has_adoption:
            register(successor, selected, context_input=adoption_context, authority=request['authority'])
    if source_manifest.get('schema_version') == 8 and source_manifest.get('state') != 'complete':
        moved = set(selected) if is_transferring else set()
        preserve_claims = any(row.get('status') == 'owned' and row['session_dir'] not in moved
                              for row in source_manifest.get('resource_claims', []))
        _link_restart(source_path, successor, authority=request['authority'],
                      controller=request['controller'], moved_paths=moved,
                      preserve_claims=preserve_claims)
    return str(successor)


def _complete_restart_intent(intent_path, source_path, source_manifest):
    intent = _read_restart_intent(intent_path, source_path, source_manifest)
    cancellation = _find_restart_abandonment(intent_path, intent)
    if cancellation is not None:
        _finish_restart_abandonment(intent_path, intent, source_path, cancellation)
        raise ValueError('this restart request was explicitly abandoned; use a new selection decision for a new request')
    active = _active_restart_operation(source_path, source_manifest)
    if active is not None and active['operation_id'] != intent['operation_id']:
        raise ValueError('another restart operation is active for this source')
    _write_restart_intent(intent_path, intent, source_path, source_manifest)
    if active is None:
        completion = _validate_restart_completion(_restart_completion_path(intent_path), intent)
        if completion is not None:
            successor, successor_manifest, _ = _load_run(completion['successor_run_dir'])
            _verify_files(successor, successor_manifest)
            if successor_manifest.get('restart_operation') != _restart_operation_row(intent):
                raise ValueError('completed restart successor differs from its durable receipt')
            _retire_completed_descriptor_if_present(intent_path, intent, source_path, source_manifest)
            return str(successor)
        _write_active_restart(source_path, source_manifest, intent_path, intent)
    try:
        successor_path = _prepare_from_restart_intent(intent_path)
    except ValueError as exc:
        error_type = type(exc) if isinstance(exc, CoordinationError) else ValueError
        raise error_type(str(exc) + '; inspect/recover source ' + str(source_path)
                         + ' for the recorded recovery plan') from exc
    successor, successor_manifest, _ = _load_run(successor_path)
    _verify_files(successor, successor_manifest, allow_resource_transfer=True)
    if successor_manifest.get('restart_operation') != _restart_operation_row(intent):
        raise ValueError('prepared successor does not match the reserved restart operation')
    _record_restart_completion(intent_path, intent)
    _retire_active_restart(intent_path, intent, source_path, source_manifest)
    return str(successor)


def restart(source_run, *, profile_input, controller, authority, current_inputs, transfer_paths=None,
            harness=None, logical_scope_input=None):
    """Create or replay one durable, source-bound archive-7 restart operation."""
    import review_recovery
    source_path = safe_path(source_run)
    with _restart_lock(source_path):
        source, manifest, marker = _load_run(source_path)
        is_immutable = manifest.get('state') == 'complete' or manifest.get('schema_version') != 8
        if not is_immutable:
            marker = _recover_trace(source, manifest, marker)
        _verify_files(source, manifest, allow_checkpoint_transaction=True,
                      allow_resource_transfer=True)
        normalized_inputs = review_recovery.validate_current_inputs(
            current_inputs, manifest, require_same_scope=False, compare_sources=False)
        if normalized_inputs['scope']['repository'] != manifest['scope']['repository']:
            raise ValueError('restart cannot change the source repository identity')
        if logical_scope_input is None:
            logical_scope_input = manifest.get('logical_scope_input')
        logical = review_layout.logical_scope(normalized_inputs['scope'], logical_scope_input)
        raw_harness = harness
        if raw_harness is None:
            raw_harness = {'harness': 'unknown', 'harness_id': None, 'harness_source': None}
        request = review_restart.normalize_restart_request(profile_input, controller, authority,
            normalized_inputs, list(transfer_paths or []), raw_harness, logical_scope_input)
        _scope(request['current_inputs']['scope'])
        _capture_review_inputs(request['current_inputs'], request['current_inputs']['scope'],
                               request['profile_input']['profile'], 'restart current review inputs',
                               logical_scope_identity=logical['identity'])
        repository = safe_path(_git(safe_path(manifest['repository_path']), 'rev-parse', '--show-toplevel'))
        identity = repository_identity(repository)
        if _digest(identity.encode('utf-8'))[:20] != manifest['repository_key']:
            raise ValueError('restart source repository identity no longer matches its pinned archive')
        future = dict(manifest, temporary_paths=[], temporary_manifests=[], repository_identity=identity)
        selected_temporaries = _temporary_paths(request['transfer_paths'], future)
        _temporary_manifests(selected_temporaries, future)
        disposition = manifest.get('operation', {}).get('disposition',
            'complete' if manifest.get('state') == 'complete' else 'open')
        if manifest.get('state') in {'retaining', 'closing'}:
            raise ValueError('recover the pending retain/close transaction before restarting')
        if isinstance(manifest.get('resource_cleanup'), dict) and manifest['resource_cleanup'].get('status') == 'pending':
            raise ValueError('recover pending resource cleanup before restarting')
        if disposition not in {'open', 'paused', 'blocked', 'superseded', 'complete'}:
            raise ValueError('source review cannot be restarted from its current operation state')
        active = _active_restart_operation(source, manifest)
        intent_path = _restart_intent_path(source, manifest, request)
        if active is not None:
            active_intent = active['intent']
            if (active_intent['request_sha256'] != review_restart._sha(review_restart._request_identity(request))
                    or active_intent['request'] != dict(request, authority=active_intent['request']['authority'])):
                raise ValueError('a different restart request is already active for this source')
            intent_path = Path(active['intent_path'])
            if not intent_path.exists():
                _write_restart_intent(intent_path, active_intent, source, manifest)
        elif intent_path.exists():
            existing_intent = _read_restart_intent(intent_path, source, manifest)
            cancellation = _validate_restart_abandonment(intent_path, existing_intent)
            if cancellation is not None:
                _finish_restart_abandonment(intent_path, existing_intent, source, cancellation)
                raise ValueError('this restart request was explicitly abandoned; use a new selection decision for a new request')
            completion = _validate_restart_completion(_restart_completion_path(intent_path), existing_intent)
            if completion is not None:
                successor, successor_manifest, _ = _load_run(completion['successor_run_dir'])
                _verify_files(successor, successor_manifest)
                if successor_manifest.get('restart_operation') != _restart_operation_row(existing_intent):
                    raise ValueError('completed restart successor differs from its durable receipt')
                _retire_completed_descriptor_if_present(intent_path, existing_intent, source, manifest)
                return str(successor)
            if existing_intent['request_sha256'] != review_restart._sha(review_restart._request_identity(request)):
                raise ValueError('restart intent identity collision; preserve the reserved operation')
            request = existing_intent['request']
            intent = existing_intent
            _write_active_restart(source, manifest, intent_path, intent)
        else:
            if disposition == 'superseded':
                raise ValueError('source review was superseded; inspect its recorded successor')
            source_claims = [row for row in manifest.get('resource_claims', []) if row.get('status') == 'owned']
            selected = request['transfer_paths']
            active_present, active_missing = [], []
            for row in source_claims:
                session = Path(row['session_dir'])
                if session.exists():
                    review_resource_claims.verify_claim(session, source, allow_checkpoint_transaction=True)
                    active_present.append(row['session_dir'])
                else:
                    active_missing.append(row['session_dir'])
            if selected:
                selected_paths = [str(safe_path(path)) for path in selected]
                selected_keys = {os.path.normcase(path) for path in selected_paths}
                active_keys = {os.path.normcase(path) for path in active_present}
                if source_claims and (active_missing or selected_keys != active_keys):
                    raise ValueError('restart transfer must include every present owned claim; missing claims cannot be transferred')
                if source_claims and normalized_inputs['scope'] != manifest['scope']:
                    raise ValueError('owned sessions stay with the source when the review scope changes; do not transfer them')
                registered = {os.path.normcase(path) for path in manifest.get('temporary_paths', [])}
                if source_claims and not selected_keys.issubset(registered):
                    raise ValueError('restart transfer paths must already be registered to the source run')
                if not source_claims:
                    _restart_adoption_context(request)
                    from_claims = {'schema_version': 7, 'repository_path': manifest['repository_path'],
                                   'repository_identity': identity,
                                   'repository_key': manifest['repository_key'], 'archive_root': manifest['archive_root'],
                                   'temporary_paths': []}
                    plans = review_resource_claims.plan_resource_registration(
                        selected_paths, from_claims, authority=request['authority'])
                    if any(plan.get('action') not in {'adopt_pending', 'claim_pending'} for plan in plans):
                        raise ValueError('only verified review workspace sessions can be adopted during restart')
            elif active_present and normalized_inputs['scope'] == manifest['scope']:
                raise ValueError('explicit transfer paths are required to preserve present owned sessions across a same-scope restart')
            candidate_successor = datetime.now(timezone.utc)
            run_id = uuid.uuid4().hex[:20]
            scoped = Path(manifest['archive_root']) / _repository_group(identity) / review_layout.scope_group(logical)
            successor_info = {'run_dir': str(scoped / review_layout.run_name(
                                  normalized_inputs['scope'], candidate_successor.isoformat(), run_id, logical_scope_input)),
                              'run_id': run_id, 'owner_id': uuid.uuid4().hex,
                              'reservation_id': uuid.uuid4().hex,
                              'created_at': candidate_successor.isoformat()}
            intent = review_restart.build_restart_intent(
                _restart_source_identity(source, manifest), request, successor_info)
            intent_path = _restart_intent_path(source, manifest, request)
            _write_active_restart(source, manifest, intent_path, intent)
            _write_restart_intent(intent_path, intent, source, manifest)
        return _complete_restart_intent(intent_path, source, manifest)


def _find_restart_abandonment(intent_path, intent):
    receipt = _validate_restart_abandonment(intent_path, intent)
    successor_path = safe_path(intent['successor']['run_dir'])
    if (successor_path / 'cierre.json').exists():
        _, successor, _ = _load_run(successor_path)
        embedded = successor.get('restart_abandonment')
        if embedded is not None:
            _validate_restart_abandonment_value(embedded, intent)
            if receipt is not None and receipt != embedded:
                raise ValueError('source and successor abandonment receipts differ')
            receipt = embedded
    return receipt


def _verify_restart_successor_identity(run, manifest, intent):
    """Check the reserved identity even when work/transfer makes cancellation unavailable."""
    reserved = intent['successor']
    expected = {'run_id': reserved['run_id'], 'owner_id': reserved['owner_id'],
                'created_at': reserved['created_at'], 'previous_run': intent['source']['run_dir'],
                'repository_key': intent['source']['repository_key'],
                'scope': intent['request']['current_inputs']['scope'],
                'restart_operation': _restart_operation_row(intent)}
    if any(manifest.get(key) != value for key, value in expected.items()):
        raise ValueError('prepared successor identity differs from the exact adoption intent')
    reservation_path = run / '.review-restart-reservation.json'
    if reservation_path.exists():
        expected_reservation = {'operation_id': intent['operation_id'], 'intent_sha256': intent['intent_sha256'],
            'reservation_id': reserved['reservation_id'], 'run_dir': str(run), 'owner_id': reserved['owner_id']}
        if read_json(reservation_path) != expected_reservation:
            raise ValueError('prepared successor reservation differs from its intent')


def _empty_adoption_successor(intent, source_manifest):
    """Read-only preflight under both locks: empty successor and an unavailable resource."""
    run, manifest, marker = _load_run(intent['successor']['run_dir'])
    _verify_restart_successor_identity(run, manifest, intent)
    transfer_denial = _restart_transfer_denial(intent, (source_manifest, manifest))
    if transfer_denial is not None:
        raise transfer_denial
    if any(row.get('status') == 'releasing' or
           (row.get('status') == 'owned' and safe_path(row['session_dir']).exists())
           for row in source_manifest.get('resource_claims', [])):
        raise _RestartCancellationUnavailable('present or releasing source claims prevent abandonment',
                                            phase='source_claims_present')
    if manifest.get('resource_claims'):
        raise _RestartCancellationUnavailable(
            'successor already owns committed adoption claims; cancellation cannot discard their ownership',
            phase='adoption_committed')
    if not intent['request']['transfer_paths']:
        raise _RestartCancellationUnavailable('prepared successor has no selected resources for abandonment; recover its exact restart',
                                            phase='resource_selection_empty')
    if source_manifest.get('operation', {}).get('disposition') == 'superseded':
        raise _RestartCancellationUnavailable('source is already superseded; its committed successor must be preserved',
                                            phase='source_superseded')
    if (manifest['state'] != 'prepared' or manifest['operation']['disposition'] != 'open'
            or manifest['profile_history'] != [_initial_selection(intent['request']['profile_input'])]
            or set(manifest['hashes']) - {review_trace.NAME}
            or any(manifest.get(key) for key in ('resource_transfers', 'resource_transfer',
                'resource_cleanup', 'cleanup_receipts', 'executors', 'assignment_registry', 'checkpoint',
                'checkpoint_transaction', 'pending_hashes', 'planned_hashes'))):
        raise _RestartCancellationUnavailable('a prepared successor with work or claims must be recovered; abandonment cannot orphan it')
    allowed = {MARKER, 'cierre.json', review_trace.NAME, '.review-restart-reservation.json'}
    if {path.name for path in run.iterdir()} - allowed:
        raise _RestartCancellationUnavailable('prepared successor contains evidence or unknown files; preserve it for recovery')
    unavailable_resource = False
    for raw in intent['request']['transfer_paths']:
        if not safe_path(raw).exists():
            unavailable_resource = True
            continue  # Preserve the source claim as missing_unknown; never synthesize release evidence.
        workspace = review_resource_claims._workspace(raw)
        if workspace is None:
            raise ValueError('adoption session is not a verifiable review workspace')
        session, workspace_manifest, token = workspace
        sidecar_path = session / review_resource_claims.CLAIM_NAME
        if not sidecar_path.exists():
            continue
        sidecar = read_json(sidecar_path)
        if sidecar.get('status') == 'bootstrap':
            continue  # load() already bound this bootstrap to its session/token.
        review_resource_claims._validate_sidecar(sidecar, session, workspace_manifest, token)
        if (sidecar['archive_path'] == str(run) or sidecar['run_id'] == manifest['run_id']
                or sidecar['owner_id'] == manifest['owner_id']):
            raise _RestartCancellationUnavailable('prepared successor already owns an adoption sidecar; recover it',
                                                phase='adoption_committed')
        if sidecar['archive_path'] == intent['source']['run_dir']:
            raise _RestartCancellationUnavailable('adoption session belongs to the restart source; recover its claim',
                                                phase='source_claims_present')
        review_resource_claims.inspect_claim_identity(session, sidecar['archive_path'])
        unavailable_resource = True
    if not unavailable_resource:
        raise _RestartCancellationUnavailable('a prepared successor must be recovered unless a resource is absent or foreign-claimed',
                                            phase='resources_available')
    pending = manifest.get('pending_trace')
    if pending is not None and [row.get('kind') for row in pending.get('events', [])] != ['prepare', 'profile']:
        raise _RestartCancellationUnavailable('prepared successor has a non-preparation trace transaction; recover it')
    _verify_files(run, manifest, allow_pending_trace=True)
    trace_bytes = (_trace_recovery_plan(run, manifest)[1] if pending is not None
                   else (run / review_trace.NAME).read_bytes())
    events = [json.loads(line) for line in trace_bytes.splitlines()]
    if [row['kind'] for row in events] != ['prepare', 'profile']:
        raise _RestartCancellationUnavailable('prepared successor has observations beyond initial preparation; recover it')
    return run, manifest, marker


def record_restart_refusal(run_dir, *, intent_path, controller, authority, reason):
    """Record an authorized refusal, without cancelling or changing resource owners."""
    import review_restart_refusal
    return review_restart_refusal.record(run_dir, intent_path=intent_path,
        controller=controller, authority=authority, reason=reason)


def _finish_restart_abandonment(intent_path, intent, source_path, receipt):
    """Caller owns the source lock; finish only an already authorized durable decision."""
    _validate_restart_abandonment_value(receipt, intent)
    intent_path = Path(intent_path)
    source, source_manifest, marker = _load_run(source_path)
    prepared = (safe_path(intent['successor']['run_dir']) / 'cierre.json').exists()
    if prepared:
        with run_locks([intent['successor']['run_dir']]):
            successor, manifest, successor_marker = _load_run(intent['successor']['run_dir'])
            if manifest.get('restart_abandonment') != receipt:
                raise ValueError('prepared successor has no matching durable abandonment decision')
            _recover_trace(successor, manifest, successor_marker)
            _verify_files(successor, manifest)
    _write_restart_intent(intent_path, intent, source, source_manifest)
    stored = _validate_restart_abandonment(intent_path, intent)
    if stored is None:
        atomic_write(_restart_abandonment_path(intent_path), _json_bytes(receipt))
    elif stored != receipt:
        raise ValueError('abandonment receipt changed during replay')
    if source_manifest.get('schema_version') == 8 and source_manifest.get('state') != 'complete':
        marker = _recover_trace(source, source_manifest, marker)
        summary = ('Restart abandoned after blocked adoption: ' if prepared else
                   'Restart abandoned before successor preparation: ') + intent['operation_id']
        events = [json.loads(line) for line in (source / review_trace.NAME).read_bytes().splitlines()]
        if not any(row.get('summary') == summary for row in events):
            _append_trace(source, source_manifest, marker, {'kind': 'interruption', 'status': 'completed',
                'summary': summary, 'actor': receipt['controller']['identity'], 'authority': receipt['authority'],
                'evidence': ['cierre.json'], 'provenance': {'kind': 'helper', 'source': 'review_artifacts:abandon-restart'}})
    _, owner_path = _active_restart_paths(source, source_manifest)
    if owner_path.exists() and read_json(owner_path)['active_descriptor'].get('operation_id') == intent['operation_id']:
        _retire_active_restart(intent_path, intent, source, source_manifest)
    return receipt


def abandon_restart(run_dir, *, intent_path, controller, authority, reason):
    """Cancel an unprepared restart or its exact empty, resource-blocked successor.

    Never delete an archive, modify a foreign session, or discard review work.
    """
    authority = review_resource_claims._authority(authority)
    reason = review_restart._bounded_text(reason, 'abandonment reason')
    with _restart_lock(run_dir):
        run, manifest, marker = _load_run(run_dir)
        intent_path = safe_path(intent_path)
        if not intent_path.exists():
            active = _active_restart_operation(run, manifest)
            if active is None or str(intent_path) != active['intent_path']:
                raise ValueError('only the exact active intent path can be reconstructed for abandonment')
            intent = active['intent']
        else:
            intent = _read_restart_intent(intent_path, run, manifest)
        actor = _controller(controller, intent['request']['controller']['identity'])
        receipt = _find_restart_abandonment(intent_path, intent)
        if receipt is not None:
            if any(receipt[key] != value for key, value in
                   {'authority': authority, 'controller': actor, 'reason': reason}.items()):
                raise ValueError('abandonment replay differs from its durable observation')
        else:
            active = _active_restart_operation(run, manifest)
            if active is None or active['operation_id'] != intent['operation_id']:
                raise ValueError('only the exact active pending restart may be abandoned')
            with ExitStack() as stack:
                if (safe_path(intent['successor']['run_dir']) / 'cierre.json').exists():
                    stack.enter_context(run_locks([intent['successor']['run_dir']]))
                manifests = _restart_resource_manifests(run, manifest, intent)
                transfer_denial = _restart_transfer_denial(intent, manifests)
                if transfer_denial is not None:
                    raise transfer_denial
                # Preserve the original guard for an unrelated pending transfer too.
                _verify_files(run, manifest, allow_checkpoint_transaction=True, allow_pending_trace=True)
                receipt = {'schema_version': 1, 'operation_id': intent['operation_id'],
                    'source_run': str(run), 'source_owner_id': manifest['owner_id'],
                    'intent_sha256': intent['intent_sha256'], 'successor_run_dir': intent['successor']['run_dir'],
                    'authority': authority, 'controller': actor, 'reason': reason,
                    'recorded_at': datetime.now(timezone.utc).isoformat()}
                receipt['receipt_sha256'] = _digest(_json_bytes(receipt))
                if len(manifests) == 2:
                    successor, empty, successor_marker = _empty_adoption_successor(intent, manifest)
                    successor_marker = _recover_trace(successor, empty, successor_marker)
                    empty['restart_abandonment'] = receipt
                    empty['operation'] = {'disposition': 'blocked', 'reason': reason,
                        'source': 'abandon-restart', 'phase': 'prepare', 'successor': None}
                    _append_trace(successor, empty, successor_marker, {'kind': 'interruption', 'status': 'completed',
                        'summary': 'Empty adoption successor explicitly abandoned: ' + intent['operation_id'],
                        'actor': actor['identity'], 'authority': authority, 'evidence': ['cierre.json'],
                        'provenance': {'kind': 'helper', 'source': 'review_artifacts:abandon-restart'}})
        return _finish_restart_abandonment(intent_path, intent, run, receipt)


@_locked_run(when=lambda args, kwargs: kwargs.get('record_checkpoint', args[1] if len(args) > 1 else False))
def validate(run_dir, require_retained=False, record_checkpoint=False, *, require_complete=False):
    """Read-only archive gate; selected evidence is verified, never copied here."""
    if require_complete and record_checkpoint:
        raise ValueError('complete gate is read-only; cannot record a checkpoint')
    require_retained = require_retained or require_complete
    run, manifest, marker = _load_run(run_dir)
    superseded = manifest.get('operation', {}).get('disposition') == 'superseded'
    if superseded and record_checkpoint:
        raise ValueError('superseded review history is immutable; validate without --record-checkpoint')
    if manifest['schema_version'] in TRACE_ARCHIVE_SCHEMAS and _digest((run / 'cierre.json').read_bytes()) != marker.get('manifest_sha256'):
        raise ValueError('ownership transition is pending; retry the interrupted helper mutation')
    _verify_files(run, manifest, required=require_retained,
                  allow_checkpoint_transaction=superseded and not require_retained)
    if require_retained and (manifest.get('retained') is not True or manifest['state'] not in {'closing', 'complete'}):
        raise ValueError('retained final review is required before cleanup')
    if require_retained:
        value = read_json(run / 'review.json')
        errors = review_contract.validate(value)
        if errors or not isinstance(value, dict) or value.get('stage') != 'final':
            raise ValueError('; '.join(errors) if errors else 'retained record must be a final review')
        if value['scope'] != manifest['scope']:
            raise ValueError('retained review scope differs from the pinned scope')
        if value.get('schema_version') in (6, 7, 8, 9, 10) and value.get('review_id') != 'CR-' + manifest.get('run_id', ''):
            raise ValueError('retained review ID differs from archive run ID')
        if manifest['schema_version'] == 8 and value.get('schema_version') != 10:
            raise ValueError('archive 8 requires final review schema 10')
        if value.get('schema_version') in (8, 9, 10):
            _execution_gate(run, manifest, value, {})
    if require_complete:
        if (manifest['state'] != 'complete' or manifest['cleanup'] not in {'complete', 'not_needed'}
                or manifest.get('residuals')):
            raise ValueError('complete durable review and observed cleanup are required')
        if (value['resources']['cleanup'] != manifest['cleanup']
                or value['resources']['residuals'] != manifest.get('residuals', [])):
            raise ValueError('retained review resources differ from completed closure')
    if record_checkpoint:
        if manifest['state'] == 'complete':
            raise ValueError('completed review history is immutable; validate without --record-checkpoint')
        if manifest['schema_version'] not in TRACE_ARCHIVE_SCHEMAS:
            raise ValueError('legacy archives cannot acquire synthetic trace checkpoints')
        _append_trace(run, manifest, marker, _milestone('validation',
                      'Retained evidence gate passed' if require_retained else 'Archive ownership and integrity gate passed', status='passed'))
    return {'run_dir': str(run), 'schema_version': manifest['schema_version'],
            'state': manifest['state'], 'retained': manifest.get('retained') is True,
            'cleanup': manifest['cleanup']}


def _retain_data(run, manifest, marker, contents, *, record_retention=True):
    # Persist pending intent before replacing files. Old and planned digests allow a
    # safe retry after interruption, without accepting arbitrary user modifications.
    manifest.update(state='retaining', cleanup='pending', retained=False,
                    planned_hashes={name: _digest(data) for name, data in contents.items()})
    marker = _save_manifest(run, manifest, marker)
    for name, data in contents.items():
        if name.startswith('evidence/'):
            safe_path(run / 'evidence').mkdir(exist_ok=True)
        atomic_write(run / name, data)
    hashes = dict(manifest['hashes'])
    hashes.update(manifest.pop('planned_hashes'))
    manifest.update(state='closing', retained=True, hashes=hashes)
    events = []
    if record_retention:
        selected = sum(name.startswith('evidence/') for name in contents)
        events.append(_milestone('retain', 'Canonical final record retained with ' + str(selected) + ' selected evidence files',
                                 status='retained', evidence=['review.json', 'informe.md', 'cierre.json#hashes']))
    if 'handoff.md' in contents:
        events.append(_milestone('handoff', 'Requested handoff generated from canonical review',
                                evidence=['review.json', 'handoff.md']))
    if events:
        _append_trace_events(run, manifest, marker, events)
    else:
        _save_manifest(run, manifest, marker)
    return manifest


def _executors(context_input, manifest, temporary):
    """Project existing neutral context facts; verify Git roots/HEAD, not check truth."""
    previous = manifest.get('executors', [])
    if context_input is None:
        return previous
    context = _input_object(context_input, 'execution context')
    if not isinstance(context, dict) or not isinstance(context.get('executors'), list):
        raise ValueError('context.executors must be an array')
    entries = {item['executor']: item for item in previous}
    seen = set()
    for raw in context['executors']:
        required = {'executor', 'method', 'workspace', 'revision', 'snapshot', 'manifest',
                    'dependencies', 'dependency_reason'}
        if not isinstance(raw, dict) or set(raw) - required - {'authorization'} or not required.issubset(raw):
            raise ValueError('invalid executor provenance fields')
        entry = dict(raw)
        for key in ('executor', 'revision', 'dependency_reason'):
            if not isinstance(entry[key], str) or not entry[key].strip():
                raise ValueError('executor ' + key + ' must be nonempty text')
        if entry['executor'] in seen:
            raise ValueError('duplicate executor identity')
        seen.add(entry['executor'])
        if entry['method'] not in {'git-worktree', 'native-worktree', 'authorized-copy'}:
            raise ValueError('unsupported executor isolation method')
        if entry['dependencies'] not in {'shared', 'local', 'none'}:
            raise ValueError('invalid dependency strategy')
        workspace = safe_path(entry['workspace'])
        if not workspace.is_dir() or not any(_contains(Path(path), workspace) for path in temporary):
            raise ValueError('executor workspace must be an existing registered temporary resource')
        entry['workspace'] = str(workspace)
        baseline = entry['revision'] == manifest['scope']['base'] and entry['snapshot'] is None
        if entry['snapshot'] != manifest['scope']['snapshot'] and not baseline:
            raise ValueError('executor snapshot differs from pinned scope')
        if entry['revision'] not in {manifest['scope']['head'], manifest['scope']['base']}:
            raise ValueError('executor revision differs from pinned scope')
        if entry['method'] == 'authorized-copy':
            if not isinstance(entry.get('authorization'), str) or not entry['authorization'].strip():
                raise ValueError('copy execution requires explicit user authorization provenance')
        else:
            repo = Path(manifest['repository_path'])
            if safe_path(_git(workspace, 'rev-parse', '--show-toplevel')) != workspace:
                raise ValueError('executor must be an actual worktree root')
            def common(path):
                value = Path(_git(path, 'rev-parse', '--git-common-dir'))
                return (path / value).resolve() if not value.is_absolute() else value.resolve()
            if common(workspace) != common(repo) or _git(workspace, 'rev-parse', 'HEAD') != entry['revision']:
                raise ValueError('executor worktree repository or HEAD differs from provenance')
        if entry['manifest'] is not None:
            path = safe_path(entry['manifest'])
            if not path.is_file() or not any(_contains(Path(raw_path), path) for raw_path in temporary):
                raise ValueError('executor manifest must exist inside registered temporary resources')
            entry['manifest'] = str(path)
        if entry['executor'] in entries and entries[entry['executor']] != entry:
            raise ValueError('retained executor identity cannot be rewritten; use a new executor ID')
        entries[entry['executor']] = entry
    return list(entries.values())


def _handoff_context(input_file, value, contents, manifest):
    """Retain only requested, bounded context with references that survive cleanup."""
    context = read_json(input_file)
    allowed = {'source_record', 'source_report', 'requirements', 'plan', 'decisions_pending'}
    if not isinstance(context, dict) or set(context) - allowed or len(_json_bytes(context)) > 32768:
        raise ValueError('handoff context must contain only bounded handoff fields')
    context = copy.deepcopy(context)
    for field, source in [('source_record', 'review.json'), ('source_report', 'informe.md')]:
        if field in context and context[field] != source:
            raise ValueError('handoff source references must identify the retained canonical record and report')
        context[field] = source
    for field in ('requirements', 'plan', 'decisions_pending'):
        entries = context.get(field, [])
        if not isinstance(entries, list) or len(entries) > 24:
            raise ValueError('handoff context arrays must contain at most 24 entries')
        for item in entries:
            if isinstance(item, str):
                if len(item) > 2000:
                    raise ValueError('unbounded handoff context text')
                reference = item
            elif isinstance(item, dict) and field != 'decisions_pending':
                reference = item.get('reference')
            else:
                raise ValueError('invalid handoff context entry')
            if field == 'decisions_pending':
                continue
            if not isinstance(reference, str):
                raise ValueError('handoff provenance must identify an evidence reference')
            parsed = urlsplit(reference)
            if parsed.scheme in {'http', 'https'} and parsed.netloc and not parsed.username:
                continue
            if (not reference.startswith('evidence/') or not _retained_name(reference)
                    or reference not in contents and reference not in manifest['hashes']):
                raise ValueError('local handoff provenance must reference selected retained evidence')
    # The canonical renderer validates exact entry shapes and captured identities.
    review_contract.render_handoff(value, context)
    return context


@_locked_run
def retain(run_dir, input_file=None, measurement_inputs=None, unavailable_reason=None, temporary_paths=None, evidence_inputs=None, context_input=None, handoff=False, handoff_context_input=None, *, expected_schema=None):
    run, manifest, marker = _load_run(run_dir)
    marker = _recover_trace(run, manifest, marker)
    if manifest['state'] == 'complete':
        raise ValueError('completed review history is immutable; prepare a new run with --previous-run')
    _verify_files(run, manifest)
    temporary = _temporary_paths(temporary_paths, manifest)
    if manifest['schema_version'] == 8:
        claim_manifest = copy.deepcopy(manifest)
        claim_manifest.update(_claim_run_dir=str(run), temporary_paths=temporary)
        resource_plans = review_resource_claims.plan_resource_registration(temporary, claim_manifest)
        if any(plan['action'] not in {'not_workspace', 'existing'} for plan in resource_plans):
            raise ValueError('register and verify every review workspace before retention')
    if input_file is None:
        if manifest['schema_version'] != 8 or not isinstance(manifest.get('checkpoint'), dict):
            raise ValueError('retention requires an explicit final review input or a provisional final checkpoint')
        candidate = run / 'pending' / 'review.json'
        if not candidate.is_file():
            raise ValueError('provisional checkpoint has no structurally valid final review to promote')
        input_file = candidate
    if manifest['schema_version'] == 8 and isinstance(manifest.get('checkpoint'), dict):
        if context_input is None and (run / 'pending' / 'context.json').is_file():
            context_input = run / 'pending' / 'context.json'
        if evidence_inputs is None:
            evidence_inputs = [run / name for name in manifest.get('pending_hashes', {})
                               if name.startswith('pending/evidence/')]
    value = read_json(input_file, max_bytes=CHECKPOINT_METADATA_LIMIT)
    if not isinstance(value, dict):
        raise ValueError('final review input must be a JSON object')
    if expected_schema is not None:
        if type(expected_schema) is not int or expected_schema not in range(1, 11):
            raise ValueError('expected schema must be a supported integer 1–10')
        if not isinstance(value, dict) or value.get('schema_version') != expected_schema:
            raise ValueError('expected schema ' + str(expected_schema) + ' differs from final review schema')
    if manifest['schema_version'] == 8:
        if value.get('schema_version') != 10:
            raise ValueError('archive 8 requires final review schema 10')
        coverage = value.get('coverage')
        execution = coverage.get('execution') if isinstance(coverage, dict) else None
        if not isinstance(execution, dict):
            raise ValueError('final coverage and coverage.execution must be JSON objects')
        if execution.get('profile_history') != manifest.get('profile_history'):
            raise ValueError('final profile history differs from the archive selections')
        if manifest.get('operation', {}).get('disposition') != 'open':
            raise ValueError('review operation is not open; recover or restart before retaining')
    if handoff_context_input is not None and not handoff:
        raise ValueError('--handoff-context-input requires an explicit --handoff request')
    errors = review_contract.validate(value)
    if errors or not isinstance(value, dict) or value.get('stage') != 'final':
        raise ValueError('; '.join(errors) if errors else 'only final review records can be retained')
    if value['scope'] != manifest['scope']:
        raise ValueError('final review scope differs from the pinned scope')
    if value.get('schema_version') in (6, 7, 8, 9, 10) and value.get('review_id') != 'CR-' + manifest.get('run_id', ''):
        raise ValueError('final review_id must bind to archive run identity: CR-' + manifest.get('run_id', ''))
    declared_residuals = [str(safe_path(raw)) for raw in value['resources']['residuals']]
    if set(declared_residuals) - set(temporary):
        raise ValueError('register declared temporary residuals before retaining cleanup evidence')
    present = _present_resources(temporary)
    if temporary:
        value = copy.deepcopy(value)
        value['resources'].update(cleanup='pending', residuals=present)
    executors = _executors(context_input, manifest, temporary)
    contents = {'review.json': _json_bytes(value), 'informe.md': review_contract.render(value).encode('utf-8')}
    if measurement_inputs or unavailable_reason is not None:
        measurements = _measurements(measurement_inputs, unavailable_reason)
        contents['measurements.json'] = _json_bytes(measurements)
    elif manifest['schema_version'] == 1:
        contents['measurements.json'] = safe_path(run / 'measurements.json').read_bytes()
    contents.update(_evidence_contents(run, manifest, evidence_inputs,
        create_directory=value.get('schema_version') not in (8, 9, 10), reserve_context=context_input is not None,
        context_input=context_input))
    if value.get('schema_version') in (8, 9, 10):
        if context_input is not None:
            _check_evidence_target(run, manifest, 'evidence/context.json')
            context_bytes = _json_bytes(read_json(context_input, max_bytes=PENDING_CONTEXT_LIMIT))
            if len(context_bytes) > 131072:
                raise ValueError('execution context exceeds bounded retained context size')
            if ('evidence/context.json' in contents
                    and read_json(context_input) != json.loads(contents['evidence/context.json'])):
                raise ValueError('selected execution context conflicts with context_input')
            contents['evidence/context.json'] = context_bytes
        _execution_gate(run, dict(manifest, executors=executors), value, contents)
    if handoff_context_input is not None:
        manifest['handoff_context'] = _handoff_context(handoff_context_input, value, contents, manifest)
    if handoff or 'handoff.md' in manifest['hashes'] or 'handoff.md' in manifest.get('planned_hashes', {}):
        manifest.setdefault('handoff_context', {'source_record': 'review.json', 'source_report': 'informe.md'})
        contents['handoff.md'] = review_contract.render_handoff(value, manifest.get('handoff_context')).encode('utf-8')
    manifest['temporary_paths'] = temporary
    manifest['temporary_manifests'] = _temporary_manifests(temporary, manifest)
    manifest['residuals'] = present
    manifest['executors'] = executors
    return _retain_data(run, manifest, marker, contents)


def _execution_gate(run, manifest, value, contents):
    """Read only selected source bytes and observed same-run trace; no archive scan."""
    def source(name):
        if not _retained_name(name):
            raise ValueError('execution reference must identify retained local evidence')
        if name in contents:
            return contents[name]
        if name in manifest['hashes']:
            return safe_path(run / name).read_bytes()
        raise ValueError('execution source is not selected for retention: ' + name)

    context = json.loads(source('evidence/context.json'))
    if not isinstance(context, dict):
        raise ValueError('execution context must be an object')
    events = [json.loads(line) for line in source(review_trace.NAME).splitlines()]
    execution = value['coverage']['execution']
    requested = {row['reference'] for key in ('plan', 'results') for row in execution[key]}
    requested.update(row['source'] for row in execution['fallbacks'])
    captured_inputs = manifest.get('review_inputs')
    if captured_inputs is not None:
        supplied_inputs = context.get('review_inputs')
        if supplied_inputs is None:
            raise ValueError('retained execution context must preserve captured review_inputs')
        normalized_inputs = _capture_review_inputs(
            supplied_inputs, manifest['scope'], manifest['profile_history'][-1]['profile'],
            'retained context review_inputs',
            logical_scope_identity=manifest.get('logical_scope', {}).get('identity'))
        if normalized_inputs != captured_inputs:
            raise ValueError('retained context review_inputs differ from the initial captured identities')
        requested.update(captured_inputs['sources'])
    if manifest.get('schema_version') == 8:
        registry = manifest.get('assignment_registry')
        if not isinstance(registry, list):
            raise ValueError('archive assignment registry is missing; register the execution plan before retention')
        if context.get('execution_plan') != registry:
            raise ValueError('retained context execution_plan differs from the durable assignment registry')
        requested.update(row['reference'] for row in registry)
    history = context.get('profile_history', [dict(profile=context.get('profile'), reference=context.get('profile_reference'))])
    if not isinstance(history, list) or any(not isinstance(row, dict) or not isinstance(row.get('reference'), str) for row in history):
        raise ValueError('execution context needs observed profile source/history')
    requested.update(row['reference'] for row in history)
    references = set()
    resolved = {}
    for reference in requested:
        parsed = urlsplit(reference)
        if parsed.scheme or parsed.netloc or parsed.query:
            raise ValueError('execution source must resolve inside the retained run')
        raw = source(parsed.path)
        if not parsed.fragment:
            resolved[reference] = raw
        elif parsed.path.endswith('.json'):
            document = json.loads(raw)
            keys = parsed.fragment.lstrip('/').split('/')
            for key in keys:
                key = key.replace('~1', '/').replace('~0', '~')
                try:
                    document = document[int(key)] if isinstance(document, list) else document[key]
                except (KeyError, IndexError, ValueError, TypeError) as exc:
                    raise ValueError('missing execution source fragment: ' + reference) from exc
            resolved[reference] = document
        elif parsed.path == review_trace.NAME:
            matching = [row for row in events if row['event_id'] == parsed.fragment]
            if not matching:
                raise ValueError('missing observed trace event source: ' + reference)
            resolved[reference] = matching[0]
        elif parsed.path.endswith('.md') and re.search(
                r'(?:<a\s+id=["\x27]' + re.escape(parsed.fragment) + r'["\x27]|^#{1,6}\s+'
                + re.escape(parsed.fragment) + r'(?:\s|$))', raw.decode('utf-8'), re.MULTILINE):
            resolved[reference] = raw
        else:
            raise ValueError('unresolved execution source fragment: ' + reference)
        references.add(reference)
    if captured_inputs is not None:
        for reference, expected in captured_inputs['sources'].items():
            name = urlsplit(reference).path
            if _digest(source(name)) != expected:
                raise ValueError('selected external review input differs from its captured SHA-256 identity: '
                                 + reference)
        description = value.get('description') if isinstance(value.get('description'), dict) else {}
        if ('description_identity' in captured_inputs
                and description.get('identity') != captured_inputs['description_identity']):
            raise ValueError('final review description identity differs from the initial captured input')
    for row in history:
        if resolved.get(row['reference']) != row.get('profile'):
            raise ValueError('profile source fragment differs from declared transition')
    errors = validate_execution_sources(value, context, events, references,
                                       assignment_registry=manifest.get('assignment_registry'))
    if value.get('schema_version') in (9, 10):
        errors.extend(validate_check_sources(value, context.get('executors')))
        errors.extend(validate_check_sources(value, manifest.get('executors', [])))
        # Both retained sources must bind each used identity to the same inputs.
        declared = context.get('executors', [])
        projected = manifest.get('executors', [])
        if isinstance(declared, list) and all(isinstance(row, dict) for row in declared + projected):
            for check in value['checks']:
                identity = check['execution']['executor']
                if identity is None:
                    continue
                source_row = next((row for row in declared if row.get('executor') == identity), {})
                closure_row = next((row for row in projected if row.get('executor') == identity), {})
                if any(source_row.get(key) != closure_row.get(key) for key in ('revision', 'snapshot')):
                    errors.append('checks.execution.sources: retained context and closure binding differ')
    if errors:
        raise ValueError('; '.join(errors))


def _present_resources(registered):
    present = []
    for raw in registered:
        try:
            safe_path(raw).stat()
            present.append(raw)
        except FileNotFoundError:
            pass
        # PermissionError and other unverifiable states deliberately propagate.
    return present


@_locked_run
def close(run_dir, cleanup_file=None, *, cleanup=None, residuals=None, released_claims=None):
    """Observe exact registered resources and persist closure; never remove resources."""
    run, manifest, marker = _load_run(run_dir)
    marker = _recover_trace(run, manifest, marker)
    if 'previous_manifest_sha256' in marker:
        # _load_run already bound these exact bytes to an owned old/new intent.
        # A stop before manifest replacement leaves no pending_trace to replay;
        # pin the authorized surviving manifest, then retry this mutation normally.
        marker = dict(marker, manifest_sha256=_digest((run / 'cierre.json').read_bytes()))
        marker.pop('previous_manifest_sha256')
        atomic_write(run / MARKER, _json_bytes(marker))
    pending_close = (manifest['state'] == 'retaining'
                     and isinstance(manifest.get('close_observation'), dict))
    if pending_close:
        _verify_files(run, manifest)
        candidate = read_json(run / 'review.json')
        errors = review_contract.validate(candidate) if isinstance(candidate, dict) else ['retained review is not an object']
        if errors or candidate.get('stage') != 'final' or candidate.get('scope') != manifest['scope']:
            raise ValueError('; '.join(errors) if errors else 'interrupted close has no valid retained final review')
        if manifest['schema_version'] == 8:
            _execution_gate(run, manifest, candidate, {})
    else:
        validate(run, require_retained=True, require_complete=manifest['state'] == 'complete')
    if (cleanup_file is None) == (cleanup is None):
        raise ValueError('supply either cleanup_file or an inline cleanup observation')
    if cleanup_file is not None:
        if residuals is not None or released_claims is not None:
            raise ValueError('residuals and release receipts belong to the cleanup file or inline observation, not both')
        observed = read_json(cleanup_file)
    else:
        observed = {'cleanup': cleanup, 'residuals': residuals if residuals is not None else []}
        if released_claims is not None:
            observed['released_claims'] = released_claims
    if (not isinstance(observed, dict) or set(observed) not in ({'cleanup', 'residuals'},
                                                                  {'cleanup', 'residuals', 'released_claims'})
            or observed['cleanup'] not in {'complete', 'not_needed', 'pending'}
            or not isinstance(observed['residuals'], list)):
        raise ValueError('cleanup must be an explicit cleanup/residuals object')
    residuals = [str(safe_path(raw)) for raw in observed['residuals']]
    registered = [str(safe_path(raw)) for raw in manifest['temporary_paths']]
    if len(set(residuals)) != len(residuals) or set(residuals) - set(registered):
        raise ValueError('residuals must be exact registered temporary paths')
    present = _present_resources(registered)
    if set(residuals) != set(present):
        raise ValueError('observed cleanup does not disclose every existing registered resource')
    if manifest['schema_version'] == 8:
        has_durable_cleanup = 'cleanup_receipts' in manifest and 'resource_cleanup' in manifest
        durable_receipts = manifest.get('cleanup_receipts', []) if has_durable_cleanup else []
        supplied_receipts = observed.get('released_claims')
        if has_durable_cleanup and supplied_receipts is not None and supplied_receipts != durable_receipts:
            raise ValueError('supplied release receipts differ from the durable cleanup receipt history')
        if isinstance(manifest.get('resource_cleanup'), dict) and manifest['resource_cleanup'].get('status') == 'pending':
            raise ValueError('resource cleanup intent is pending; recover or retry cleanup before closing the review')
        manifest['resource_claims'] = review_resource_claims.validate_release_observation(
            manifest, present, durable_receipts if has_durable_cleanup else (supplied_receipts or []))
        review_resource_claims.validate_claims_for_close(run, manifest)
    cleanup = observed['cleanup']
    if (cleanup in {'complete', 'not_needed'} and residuals) or (cleanup == 'not_needed' and registered):
        raise ValueError('cleanup conflicts with registered resources or residuals')
    durable_close = None
    if manifest['schema_version'] == 8 and has_durable_cleanup:
        durable_close = {'cleanup': cleanup, 'residuals': residuals,
                         'released_claims': copy.deepcopy(durable_receipts)}
        prior_close = manifest.get('close_observation')
        if prior_close is not None and prior_close != durable_close:
            prior_receipts = prior_close.get('released_claims', [])
            may_advance_pending = (manifest['state'] == 'closing'
                                   and prior_close.get('cleanup') == 'pending'
                                   and cleanup in {'pending', 'complete'}
                                   and set(residuals).issubset(set(prior_close.get('residuals', [])))
                                   and durable_close['released_claims'][:len(prior_receipts)] == prior_receipts)
            if not may_advance_pending:
                raise ValueError('close retry differs from the exact durable cleanup observation')
    if manifest['state'] == 'complete':
        if cleanup != manifest['cleanup'] or residuals != manifest['residuals']:
            raise ValueError('completed review history cannot be reopened')
        return manifest
    value = read_json(run / 'review.json')
    if value.get('scope') != manifest['scope']:
        raise ValueError('retained review scope differs from manifest')
    value = copy.deepcopy(value)
    value['resources'].update(cleanup=cleanup, residuals=residuals)
    errors = review_contract.validate(value)
    if errors:
        raise ValueError('; '.join(errors))
    report = review_contract.render(value).encode('utf-8')
    if durable_close is not None and manifest.get('close_observation') != durable_close:
        manifest['close_observation'] = durable_close
        marker = _save_manifest(run, manifest, marker)
    if value != read_json(run / 'review.json') or pending_close:
        contents = {'review.json': _json_bytes(value), 'informe.md': report}
        if 'handoff.md' in manifest['hashes']:
            contents['handoff.md'] = review_contract.render_handoff(value, manifest.get('handoff_context')).encode('utf-8')
        manifest = _retain_data(run, manifest, marker, contents, record_retention=False)
        run, manifest, marker = _load_run(run)
    manifest.update(cleanup=cleanup, residuals=residuals,
                    state='complete' if cleanup != 'pending' else 'closing')
    if manifest['state'] == 'complete':
        manifest['closed_at'] = datetime.now(timezone.utc).isoformat()
        if manifest['schema_version'] == 8:
            manifest['operation']['disposition'] = 'complete'
            manifest['operation']['phase'] = 'close'
    _append_trace(run, manifest, marker, _milestone('close', 'Observed resource closure: ' + cleanup,
                  status='pending' if cleanup == 'pending' else 'completed', evidence=['review.json', 'informe.md']))
    return manifest


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    create = commands.add_parser('prepare')
    for name in ('repo', 'scope-file', 'skill-version', 'harness'):
        create.add_argument('--' + name, required=True)
    create.add_argument('--output-root')
    create.add_argument('--previous-run')
    create.add_argument('--temporary-path', action='append')
    create.add_argument('--logical-scope-input', help='Existing JSON {mode, selector} for module/feature or partial local scopes')
    create.add_argument('--profile-input', required=True,
                        help='Existing JSON selection captured before the new run is created')
    create.add_argument('--current-inputs', help='Existing JSON with scope, external source hashes and observed identities')
    create.add_argument('--controller-input',
                        help='Existing JSON {identity, source} for the coordinating context')
    create.add_argument('--harness-id', help='Declared canonical catalog ID; overrides session CCR_HARNESS_ID')
    create.add_argument('--harness-source-file', help='Existing JSON {kind: user|platform, reference: text}; requires --harness-id')
    resources = commands.add_parser('register', help='Register verified owned temporary paths before use')
    resources.add_argument('--run-dir', required=True)
    resources.add_argument('--temporary-path', action='append', required=True)
    resources.add_argument('--context-input', help='Existing neutral context JSON with executor provenance')
    resources.add_argument('--authority', help='Explicit user authority for adopting an existing legacy session')
    transfer = commands.add_parser('transfer-resources', help='Transfer explicitly selected claimed workspaces to a successor run')
    transfer.add_argument('--source-run', required=True)
    transfer.add_argument('--successor-run', required=True)
    transfer.add_argument('--resource-path', action='append', required=True)
    transfer.add_argument('--authority', required=True)
    transfer.add_argument('--controller-input', required=True)
    inspect = commands.add_parser('inspect', help='Read-only status/integrity inspection of one explicit review run')
    inspect.add_argument('--run-dir', required=True)
    inspect.add_argument('--current-inputs', help='Existing JSON {scope, sources} verified by the coordinator')
    lookup = commands.add_parser('lookup', help='Find bounded prior-run candidates for one repository and scope')
    lookup.add_argument('--repo', required=True)
    lookup.add_argument('--scope-file', required=True)
    lookup.add_argument('--archive-root', help='Explicit archive root; defaults to ~/.comprehensive-code-review/reviews')
    lookup.add_argument('--current-inputs', help='Existing JSON with scope, source hashes and optional input identities')
    lookup.add_argument('--limit', type=int, default=20)
    lookup.add_argument('--cursor', help='Opaque continuation cursor returned by a previous lookup page')
    lookup.add_argument('--logical-scope-input', help='Existing JSON selector required for module/feature or partial local lookup')
    lookup.add_argument('--include-history', action='store_true', help='Include explicitly ported historical consultation packages')
    lookup.add_argument('--select', choices=('latest',), help='Explicitly select latest verified result; never shown automatically')
    pause_command = commands.add_parser('pause', help='Record an explicit user-directed review pause')
    pause_command.add_argument('--run-dir', required=True)
    pause_command.add_argument('--authority-input', required=True,
                               help='JSON string or {"authority": text} with explicit user direction')
    pause_command.add_argument('--reason', required=True)
    pause_command.add_argument('--phase', required=True, choices=sorted(review_profiles.PHASES))
    block_command = commands.add_parser('block', help='Record an observed review failure without inferring a crash')
    block_command.add_argument('--run-dir', required=True)
    block_command.add_argument('--source', required=True)
    block_command.add_argument('--reason', required=True)
    block_command.add_argument('--phase', required=True, choices=sorted(review_profiles.PHASES))
    resume_command = commands.add_parser('resume', help='Resume a verified unchanged archive after explicit authority')
    resume_command.add_argument('--run-dir', required=True)
    resume_command.add_argument('--controller-input', required=True)
    resume_command.add_argument('--authority-input', required=True)
    resume_command.add_argument('--current-inputs', required=True)
    recover_command = commands.add_parser('recover', help='Complete exact helper-owned transactions or return a plan')
    recover_command.add_argument('--run-dir', required=True)
    recover_command.add_argument('--controller-input', required=True)
    recover_command.add_argument('--authority-input', required=True)
    recover_command.add_argument('--current-inputs', required=True)
    restart_command = commands.add_parser('restart', help='Create a fresh linked archive-8 review run')
    restart_command.add_argument('--run-dir', required=True, help='Verified source review run')
    restart_command.add_argument('--profile-input', required=True)
    restart_command.add_argument('--controller-input', required=True)
    restart_command.add_argument('--authority-input', required=True)
    restart_command.add_argument('--current-inputs', required=True)
    restart_command.add_argument('--logical-scope-input', help='Existing JSON {mode, selector} when logical boundaries change')
    restart_command.add_argument('--harness', default='unknown', help='Harness observed for this restart invocation')
    restart_command.add_argument('--harness-id', help='Canonical current harness ID from the CCR catalog')
    restart_command.add_argument('--harness-source-input', help='JSON provenance for an explicit harness ID')
    restart_command.add_argument('--transfer-path', action='append',
                                 help='Explicit owned session path to transfer; repeat for every active claim')
    abandon = commands.add_parser('abandon-restart', help='Cancel an unprepared restart or an exact empty resource-blocked successor')
    abandon.add_argument('--run-dir', required=True)
    abandon.add_argument('--intent-input', required=True, help='Exact intent path returned by inspect; no archive scan')
    abandon.add_argument('--controller-input', required=True)
    abandon.add_argument('--authority-input', required=True)
    abandon.add_argument('--reason', required=True)
    refusal = commands.add_parser('record-restart-refusal', help='Record a phase-specific cancellation refusal; leave the exact restart pending')
    refusal.add_argument('--run-dir', required=True)
    refusal.add_argument('--intent-input', required=True)
    refusal.add_argument('--controller-input', required=True)
    refusal.add_argument('--authority-input', required=True)
    refusal.add_argument('--reason', required=True)
    select = commands.add_parser('select-profile', help='Atomically capture a profile transition before using it')
    select.add_argument('--run-dir', required=True)
    select.add_argument('--selection-input', required=True)
    gate = commands.add_parser('validate', help='Read-only ownership, layout and retained hash checks')
    gate.add_argument('--run-dir', required=True)
    gate.add_argument('--require-retained', action='store_true', help='Require complete retained evidence before cleanup')
    gate.add_argument('--require-complete', action='store_true', help='Read-only gate for retained result and completed observed cleanup')
    gate.add_argument('--record-checkpoint', action='store_true', help='Record a passed milestone in an open trace archive')
    trace = commands.add_parser('record-event', help='Coordinator records one bounded structured milestone')
    trace.add_argument('--run-dir', required=True)
    trace.add_argument('--event-file', required=True)
    trace.add_argument('--execution-metadata', help='Optional existing review_runner run.json; no timing or identity inference')
    pending = commands.add_parser('checkpoint', help='Preserve selected inputs/results provisionally without retaining a verdict')
    pending.add_argument('--run-dir', required=True)
    pending.add_argument('--context-input', required=True)
    pending.add_argument('--evidence-input', action='append')
    pending.add_argument('--input', help='Optional structurally final review JSON; source gates remain mandatory for promotion')
    pending.add_argument('--phase', required=True, choices=sorted(review_profiles.PHASES - {'prepare'}))
    pending.add_argument('--diagnostic-input', help='Optional JSON array or {gate_errors: [...]} of bounded observed gate errors')
    pending.add_argument('--max-evidence-bytes', type=int, default=CHECKPOINT_EVIDENCE_LIMIT,
                         help='Selected checkpoint evidence byte limit, from 0 to 67108864')
    keep = commands.add_parser('retain')
    keep.add_argument('--run-dir', required=True)
    keep.add_argument('--input', help='Final review JSON; omit only when promoting the archive-owned final checkpoint')
    keep.add_argument('--expected-schema', type=int, choices=range(1, 11), help='Require the caller-selected final contract before retention')
    keep.add_argument('--measurement-input', action='append')
    keep.add_argument('--unavailable-reason')
    keep.add_argument('--temporary-path', action='append')
    keep.add_argument('--evidence-input', action='append')
    keep.add_argument('--context-input', help='Existing neutral context JSON with executor provenance')
    keep.add_argument('--handoff', action='store_true', help='Retain a handoff generated from the canonical record')
    keep.add_argument('--handoff-context-input', help='Explicit handoff spec/plan references and pending decisions; requires --handoff')
    finish = commands.add_parser('close')
    finish.add_argument('--run-dir', required=True)
    observed = finish.add_mutually_exclusive_group(required=True)
    observed.add_argument('--cleanup-file')
    observed.add_argument('--cleanup', choices=('complete', 'not_needed', 'pending'),
                          help='Observed state without creating a post-cleanup temporary file')
    finish.add_argument('--residual', action='append', help='Exact registered remaining path; repeat with --cleanup pending')
    finish.add_argument('--released-claims-input',
                        help='Existing JSON list of exact durable cleanup receipts for inline close')
    args = parser.parse_args()
    try:
        authority_input = None
        if getattr(args, 'authority_input', None):
            authority_input = read_json(args.authority_input)
            if isinstance(authority_input, dict) and set(authority_input) == {'authority'}:
                authority_input = authority_input['authority']
            if not isinstance(authority_input, str):
                raise ValueError('authority input must be a JSON string or an object with exactly the authority field')
        if args.command == 'prepare':
            source = read_json(args.harness_source_file) if args.harness_source_file else None
            if args.harness_source_file and (not isinstance(source, dict) or args.harness_id is None):
                raise ValueError('harness source file requires an object and an explicit --harness-id')
            result = {'run_dir': prepare(args.repo, args.scope_file, args.skill_version, args.harness,
                                         args.output_root, args.previous_run, args.temporary_path,
                                         profile_input=args.profile_input,
                                         controller=read_json(args.controller_input) if args.controller_input else None,
                                         harness_id=args.harness_id, harness_source=source,
                                         current_inputs=read_json(args.current_inputs) if args.current_inputs else None,
                                         logical_scope_input=read_json(args.logical_scope_input) if args.logical_scope_input else None)}
        elif args.command == 'checkpoint':
            diagnostic = read_json(args.diagnostic_input) if args.diagnostic_input else None
            if isinstance(diagnostic, dict) and set(diagnostic) == {'gate_errors'}:
                diagnostic = diagnostic['gate_errors']
            result = checkpoint(args.run_dir, context_input=args.context_input,
                                evidence_inputs=args.evidence_input, input_record=args.input,
                                phase=args.phase, gate_errors=diagnostic,
                                max_evidence_bytes=args.max_evidence_bytes)
        elif args.command == 'retain':
            result = retain(args.run_dir, args.input, args.measurement_input,
                            args.unavailable_reason, args.temporary_path, args.evidence_input, args.context_input, args.handoff, args.handoff_context_input,
                            expected_schema=args.expected_schema)
        elif args.command == 'register':
            result = register(args.run_dir, args.temporary_path, context_input=args.context_input,
                              authority=args.authority)
        elif args.command == 'transfer-resources':
            result = transfer_resources(args.source_run, args.successor_run, args.resource_path,
                                        authority=args.authority, controller=read_json(args.controller_input))
        elif args.command == 'inspect':
            import review_recovery
            current = read_json(args.current_inputs) if args.current_inputs else None
            result = review_recovery.inspect_run(args.run_dir, current_inputs=current)
        elif args.command == 'lookup':
            import review_recovery
            current = read_json(args.current_inputs) if args.current_inputs else None
            requested_scope = read_json(args.scope_file)
            logical_input = read_json(args.logical_scope_input) if args.logical_scope_input else None
            if args.select == 'latest':
                if current is None:
                    raise ValueError('--select latest requires --current-inputs')
                result = review_recovery.select_latest(args.repo, requested_scope, archive_root=args.archive_root,
                    current_inputs=current, logical_scope_input=logical_input)
            else:
                result = review_recovery.find_candidates(args.repo, requested_scope,
                    archive_root=args.archive_root, limit=args.limit, cursor=args.cursor,
                    current_inputs=current, logical_scope_input=logical_input,
                    include_history=args.include_history)
        elif args.command == 'pause':
            result = pause(args.run_dir, authority=authority_input, reason=args.reason, phase=args.phase)
        elif args.command == 'block':
            result = block(args.run_dir, source=args.source, reason=args.reason, phase=args.phase)
        elif args.command == 'resume':
            result = resume(args.run_dir, controller=read_json(args.controller_input), authority=authority_input,
                            current_inputs=read_json(args.current_inputs))
        elif args.command == 'recover':
            result = recover(args.run_dir, controller=read_json(args.controller_input), authority=authority_input,
                             current_inputs=read_json(args.current_inputs))
        elif args.command == 'restart':
            harness_source = read_json(args.harness_source_input) if args.harness_source_input else None
            result = {'run_dir': restart(args.run_dir, profile_input=args.profile_input,
                         controller=read_json(args.controller_input), authority=authority_input,
                         current_inputs=read_json(args.current_inputs), transfer_paths=args.transfer_path,
                           logical_scope_input=read_json(args.logical_scope_input) if args.logical_scope_input else None,
                         harness={'harness': args.harness, 'harness_id': args.harness_id,
                                  'harness_source': harness_source})}
        elif args.command == 'abandon-restart':
            result = abandon_restart(args.run_dir, intent_path=args.intent_input,
                controller=read_json(args.controller_input), authority=authority_input, reason=args.reason)
        elif args.command == 'record-restart-refusal':
            result = record_restart_refusal(args.run_dir, intent_path=args.intent_input,
                controller=read_json(args.controller_input), authority=authority_input, reason=args.reason)
        elif args.command == 'select-profile':
            result = select_profile(args.run_dir, args.selection_input)
        elif args.command == 'validate':
            result = validate(args.run_dir, args.require_retained, args.record_checkpoint, require_complete=args.require_complete)
        elif args.command == 'record-event':
            result = record_event(args.run_dir, args.event_file, args.execution_metadata)
        else:
            receipts = read_json(args.released_claims_input) if args.released_claims_input else None
            if receipts is not None and not isinstance(receipts, list):
                raise ValueError('released claims input must be a JSON list')
            result = close(args.run_dir, args.cleanup_file, cleanup=args.cleanup,
                           residuals=args.residual, released_claims=receipts)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        detail = {'error': str(exc)}
        if isinstance(exc, _RestartCancellationUnavailable):
            detail['cancellation_denial'] = exc.diagnostic()
        print(json.dumps(detail, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
