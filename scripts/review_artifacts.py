#!/usr/bin/env python3
"""Prepare, register, validate, retain and close durable review evidence (Python 3.10+).

Measurement inputs are an explicit caller assertion of disjoint executions. Duplicate
paths and execution_id values are refused; semantic overlap is not detectable here.
Temporary-path authority and ownership belong to the coordinator. This helper never
deletes registered resources and must not be used to infer disposal authority.
"""
import argparse
import copy
from datetime import datetime, timezone
from functools import wraps
import hashlib
import json
import os
from pathlib import Path
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
import review_resource_claims
from review_run_lock import run_locks
from review_execution import validate_execution_sources
from review_check_provenance import validate_check_sources


FILES = ('review.json', 'informe.md')
OPTIONAL_FILES = ('measurements.json',)
TRACE_FILES = (review_trace.NAME, 'handoff.md')
MARKER = '.review-ownership.json'
ARCHIVE_SCHEMA_VERSION = 7
TRACE_ARCHIVE_SCHEMAS = frozenset({4, 5, 6, 7})
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
            with run_locks([run_dir]):
                return target(run_dir, *args, **kwargs)
        return wrapped
    return decorate(function) if function is not None else decorate


def read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate JSON key: ' + key)
            result[key] = value
        return result
    def invalid_constant(value):
        raise ValueError('nonfinite JSON number: ' + value)
    return json.loads(safe_path(path).read_text(encoding='utf-8'),
                      object_pairs_hook=unique, parse_constant=invalid_constant)


def atomic_write(path, data):
    """Replace one validated path atomically, using an exclusive local staging file."""
    path = safe_path(path)
    staging = path.parent / ('.' + path.name + '.' + uuid.uuid4().hex + '.tmp')
    with staging.open('xb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    safe_path(path)
    os.replace(staging, path)


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


def _scope_group(scope):
    hint = scope['reference'] or scope['target'] or scope['snapshot'] or scope['head']
    if scope['reference'] and '://' in hint:
        hint = urlsplit(hint).path.rstrip('/').rsplit('/', 1)[-1]
    return _slug(scope['mode']) + '-' + _slug(hint) + '-' + _digest(_json_bytes(scope))[:16]


def _validate_layout(run, manifest):
    """Bind location to durable identities; never need the original checkout."""
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
    if scope != _scope_group(manifest['scope']):
        raise ValueError('invalid archive layout: scope directory differs from pinned scope')
    if not re.fullmatch(r'[0-9]{8}T[0-9]{6}-[0-9a-f]{20}', name):
        raise ValueError('invalid archive layout: timestamp and unique run ID are required')
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
        expected = created.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + run_id
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
    atomic_write(run / MARKER, _json_bytes(transition))
    atomic_write(run / 'cierre.json', data)
    marker = dict(marker, manifest_sha256=_digest(data))
    marker.pop('previous_manifest_sha256', None)
    atomic_write(run / MARKER, _json_bytes(marker))
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
    if manifest.get('schema_version') not in (1, 2, 3, 4, 5, 6, ARCHIVE_SCHEMA_VERSION):
        raise ValueError('unsupported archive schema')
    if manifest['schema_version'] in (6, 7):
        review_harness.validate_identity(manifest)
    if manifest['schema_version'] == 7:
        if not manifest.get('profile_history'):
            raise ValueError('profile selection is required before review work starts')
        errors = review_profiles.validate_history(manifest.get('profile_history'))
        if errors:
            raise ValueError('; '.join(errors))
        operation = manifest.get('operation')
        fields = {'disposition', 'reason', 'source', 'phase', 'successor'}
        if (not isinstance(operation, dict) or set(operation) != fields
                or operation['disposition'] not in {'open', 'paused', 'blocked', 'superseded', 'complete'}):
            raise ValueError('invalid archive operation disposition')
        controller = manifest.get('controller')
        if (not isinstance(controller, dict) or set(controller) != {'identity', 'source'}
                or not isinstance(controller['identity'], dict) or not isinstance(controller['source'], str)):
            raise ValueError('invalid archive controller identity')
    states = {'prepared', 'retaining', 'closing', 'complete'}
    if manifest['schema_version'] in (5, 6, 7):
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
    if manifest.get('schema_version') != 7:
        if any(key in manifest for key in ('pending_hashes', 'checkpoint', 'checkpoint_transaction')):
            raise ValueError('legacy archive cannot contain provisional checkpoint metadata')
        return
    hashes = manifest.get('pending_hashes', {})
    if not isinstance(hashes, dict) or len(hashes) > CHECKPOINT_EVIDENCE_COUNT_LIMIT + 3 or any(not _pending_file_name(name)
                                           or not isinstance(value, str)
                                           or not CHECKPOINT_HASH.fullmatch(value)
                                           for name, value in hashes.items()):
        raise ValueError('invalid provisional checkpoint hash inventory')
    checkpoint = manifest.get('checkpoint')
    transaction = manifest.get('checkpoint_transaction')
    accepted = {name: {digest} for name, digest in hashes.items()}
    may_be_missing = set()
    if transaction is not None:
        fields = {'input_signature', 'previous_hashes', 'planned_hashes', 'removed_hashes', 'checkpoint'}
        if not isinstance(transaction, dict) or set(transaction) != fields:
            raise ValueError('invalid checkpoint transaction intent')
        previous, planned, removed = (transaction['previous_hashes'], transaction['planned_hashes'],
                                       transaction['removed_hashes'])
        if previous != hashes or not isinstance(planned, dict) or any(
                not _pending_file_name(name) or not isinstance(value, str)
                or not CHECKPOINT_HASH.fullmatch(value) for name, value in planned.items()):
            raise ValueError('checkpoint transaction differs from its owned prior inventory')
        if (not isinstance(removed, dict) or any(
                name not in {'pending/review.json', 'pending/informe.md'}
                or previous.get(name) != digest or name in planned
                or not isinstance(digest, str) or not CHECKPOINT_HASH.fullmatch(digest)
                for name, digest in removed.items())):
            raise ValueError('checkpoint transaction has an invalid owned removal intent')
        if not isinstance(transaction['input_signature'], str) or not CHECKPOINT_HASH.fullmatch(transaction['input_signature']):
            raise ValueError('invalid checkpoint input signature')
        accepted = {name: {digest} for name, digest in previous.items()}
        for name, digest in planned.items():
            accepted.setdefault(name, set()).add(digest)
            if name not in previous:
                may_be_missing.add(name)
        may_be_missing.update(removed)
        if not allow_transaction:
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
                    or row['name'] in inventory):
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
            if not _pending_file_name(name):
                raise ValueError('foreign file in pending checkpoint: ' + name)
            observed.add(name)
        if observed - set(accepted):
            raise ValueError('foreign pending checkpoint files are present')
    elif accepted and any(name not in may_be_missing for name in accepted):
        raise ValueError('pending checkpoint inventory is missing its directory')

    for name, allowed_digests in accepted.items():
        path = safe_path(run / name)
        try:
            data = path.read_bytes()
        except FileNotFoundError:
            if name in may_be_missing:
                continue
            raise ValueError('pending checkpoint file is missing: ' + name)
        if _digest(data) not in allowed_digests:
            raise ValueError('modified pending checkpoint file: ' + name)
        if transaction is None:
            expected_size = next(row['size'] for row in checkpoint['inventory'] if row['name'] == name)
            if len(data) != expected_size:
                raise ValueError('pending checkpoint file size differs from its inventory: ' + name)
        elif name in transaction['planned_hashes'] and _digest(data) == transaction['planned_hashes'][name]:
            planned_size = next(row['size'] for row in checkpoint['inventory'] if row['name'] == name)
            if len(data) != planned_size:
                raise ValueError('pending checkpoint file size differs from its transaction: ' + name)


def _verify_files(run, manifest, required=False, *, allow_checkpoint_transaction=False,
                  allow_resource_transfer=False):
    if manifest.get('pending_trace') is not None:
        raise ValueError('trace recording is pending; retry a helper mutation to recover the preserved event')
    transfer = manifest.get('resource_transfer')
    if transfer is not None:
        _validate_transfer_intent(transfer)
        if transfer.get('status') != 'complete' and not allow_resource_transfer:
            raise ValueError('resource transfer is pending; retry its transfer helper before continuing')
    _verify_pending(run, manifest, allow_transaction=allow_checkpoint_transaction)
    hashes = manifest.get('hashes')
    if not isinstance(hashes, dict) or any(not _retained_name(name) for name in hashes):
        raise ValueError('invalid retained file manifest')
    planned = manifest.get('planned_hashes', {}) if manifest['state'] == 'retaining' else {}
    required_files = set(FILES) | (set(OPTIONAL_FILES) if manifest['schema_version'] == 1 else set())
    if manifest['schema_version'] in TRACE_ARCHIVE_SCHEMAS and review_trace.NAME not in hashes:
        raise ValueError('mandatory archive trace is missing from closure')
    if required and (not required_files.issubset(hashes) or manifest['state'] == 'retaining'):
        raise ValueError('retained evidence is absent or interrupted')
    if not isinstance(planned, dict) or any(not _retained_name(name) for name in planned):
        raise ValueError('invalid planned evidence paths')
    for name in set(FILES) | set(OPTIONAL_FILES) | (set(TRACE_FILES) if manifest['schema_version'] in TRACE_ARCHIVE_SCHEMAS else set()) | set(hashes) | set(planned):
        path = safe_path(run / name)
        try:
            data = path.read_bytes()
        except FileNotFoundError:
            if (required and name in required_files | set(hashes)) or (name in hashes and manifest['state'] != 'retaining'):
                raise ValueError('retained evidence missing: ' + name)
            continue
        if _digest(data) not in {hashes.get(name), planned.get(name)}:
            raise ValueError('refusing to clobber modified archived file: ' + name)
    if manifest['schema_version'] in TRACE_ARCHIVE_SCHEMAS:
        review_trace.verify(safe_path(run / review_trace.NAME).read_bytes(), manifest.get('trace'), manifest['run_id'])


def _recover_trace(run, manifest, marker):
    """Finish only an owned, hash-bound pending append; never adopt unknown bytes."""
    pending = manifest.get('pending_trace')
    if pending is None:
        return marker
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
    if current != planned:
        atomic_write(path, planned)
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


def _input_object(value, label):
    result = read_json(value) if isinstance(value, (str, os.PathLike)) else copy.deepcopy(value)
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
    if manifest['schema_version'] in (5, 6, 7) and event['occurred_at'] is not None and event['provenance']['source'] is None:
        raise ValueError('observed execution time requires an identifiable provenance source')
    if manifest['schema_version'] in (5, 6, 7):
        review_trace.validate_local_event_targets(event, (run / review_trace.NAME).read_bytes())
    if manifest['schema_version'] == 7 and event['kind'] == 'profile':
        raise ValueError('use select-profile to record structured profile transitions')
    if manifest['schema_version'] == 7 and _starts_processing(event):
        if not manifest.get('profile_history'):
            raise ValueError('profile selection is required before review work starts')
        disposition = manifest.get('operation', {}).get('disposition')
        if disposition != 'open':
            raise ValueError('review operation is ' + str(disposition) + '; resume or recover before starting work')
    if manifest['schema_version'] in (5, 6, 7) and manifest['state'] == 'prepared' and _starts_processing(event):
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


def _evidence_contents(run, manifest, inputs, *, create_directory=True):
    contents = {}
    for raw in inputs or []:
        source = safe_path(raw)
        if not stat.S_ISREG(source.stat().st_mode):
            raise ValueError('selected evidence must be a regular file')
        name = 'evidence/' + _evidence_name(source.name)
        if name in contents:
            raise ValueError('duplicate selected evidence name: ' + name)
        _check_evidence_target(run, manifest, name)
        contents[name] = source.read_bytes()
    # A retry must finish every previously selected artifact. Existing matching
    # planned bytes are reusable; missing sources require explicit resubmission.
    for name, expected in manifest.get('planned_hashes', {}).items():
        if name.startswith('evidence/') and name not in contents:
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
    context = read_json(context_path)
    if not isinstance(context, dict):
        raise ValueError('checkpoint context must be a JSON object')
    context_bytes = _json_bytes(context)
    if len(context_bytes) > PENDING_CONTEXT_LIMIT:
        raise ValueError('execution context exceeds the 131072-byte checkpoint limit')
    payloads = {'pending/context.json': context_bytes}
    source_contents = {'evidence/context.json': context_bytes}
    evidence_total = 0
    evidence_count = 0
    seen = set()
    for raw in evidence_inputs or []:
        source = safe_path(raw)
        if not stat.S_ISREG(source.stat().st_mode):
            raise ValueError('selected checkpoint evidence must be a regular file')
        name = _evidence_name(source.name)
        if name in seen:
            raise ValueError('duplicate selected checkpoint evidence name: ' + name)
        seen.add(name)
        evidence_count += 1
        if evidence_count > CHECKPOINT_EVIDENCE_COUNT_LIMIT:
            raise ValueError('checkpoint accepts at most 64 selected evidence files')
        data = source.read_bytes()
        evidence_total += len(data)
        if evidence_total > max_evidence_bytes:
            raise ValueError('selected checkpoint evidence exceeds the configured byte limit')
        payloads['pending/evidence/' + name] = data
        source_contents['evidence/' + name] = data

    for name, digest in manifest.get('pending_hashes', {}).items():
        if name.startswith('pending/evidence/') and name not in payloads:
            prior = safe_path(run / name).read_bytes()
            if _digest(prior) != digest:
                raise ValueError('modified prior checkpoint evidence: ' + name)
            source_contents['evidence/' + name.split('/', 2)[2]] = prior

    diagnostics = _checkpoint_diagnostics(gate_errors)
    final = None
    if input_record is not None:
        try:
            final = _input_object(input_record, 'checkpoint final review')
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
                    diagnostics.append('final structure: archive 7 checkpoints require review schema 10')
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
            previous[name] = safe_path(run / name).read_bytes()
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
    for name, expected in planned.items():
        data = payloads.get(name)
        if data is None:
            path = safe_path(run / name)
            try:
                data = path.read_bytes()
            except FileNotFoundError as exc:
                raise ValueError('retry checkpoint with missing selected input: ' + name) from exc
        if _digest(data) != expected:
            raise ValueError('checkpoint retry input differs from its preserved intent: ' + name)
        path = safe_path(run / name)
        try:
            current = path.read_bytes()
        except FileNotFoundError:
            current = None
        if current is not None and _digest(current) == expected:
            continue
        allowed_old = transaction['previous_hashes'].get(name)
        if current is not None and _digest(current) != allowed_old:
            raise ValueError('foreign or modified pending checkpoint bytes: ' + name)
        if name.startswith('pending/evidence/'):
            safe_path(run / 'pending' / 'evidence').mkdir(parents=True, exist_ok=True)
        else:
            safe_path(run / 'pending').mkdir(exist_ok=True)
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
    if manifest['schema_version'] != 7:
        raise ValueError('provisional checkpoints require archive 7')
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
        sequence = int(current['id'][1:]) + 1 if isinstance(current, dict) else 1
        inventory = []
        for name, digest in sorted(planned.items()):
            data = payloads[name] if name in payloads else safe_path(run / name).read_bytes()
            inventory.append({'name': name, 'size': len(data), 'sha256': digest})
        checkpoint_record = {'id': 'K' + str(sequence).zfill(3), 'phase': phase,
                             'recorded_at': datetime.now(timezone.utc).isoformat(),
                             'input_signature': signature,
                             'inventory': inventory,
                             'gate_errors': diagnostics}
        transaction = {'input_signature': signature, 'previous_hashes': prior_hashes,
                       'planned_hashes': planned, 'removed_hashes': removed_hashes,
                       'checkpoint': checkpoint_record}
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
            *, profile_input=None, controller=None, harness_id=None, harness_source=None):
    repo = safe_path(repo)
    repo = safe_path(_git(repo, 'rev-parse', '--show-toplevel'))
    scope = read_json(scope_file)
    _scope(scope)
    selection = _initial_selection(profile_input)
    controller_value = _controller(controller, selection['actor'])
    if not isinstance(skill_version, str) or not skill_version.strip() or not isinstance(harness, str) or not harness.strip():
        raise ValueError('skill version and harness are required')
    harness_identity = review_harness.resolve(harness, harness_id, harness_source)
    identity = repository_identity(repo)
    repository_key = _digest(identity.encode('utf-8'))[:20]
    root = select_output_root(repo, output_root)
    previous = None
    if previous_run is not None:
        old, old_manifest, _ = _load_run(previous_run)
        _verify_files(old, old_manifest)
        if old_manifest['repository_key'] != repository_key:
            raise ValueError('previous run belongs to a different repository')
        previous = str(old)
    manifest = {'schema_version': ARCHIVE_SCHEMA_VERSION, 'skill_version': skill_version, 'harness': harness,
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
                'resource_claims': []}
    manifest.update(harness_identity)
    manifest['temporary_paths'] = _temporary_paths(temporary_paths, manifest)
    manifest['temporary_manifests'] = _temporary_manifests(manifest['temporary_paths'], manifest)
    scoped = root / _repository_group(identity) / _scope_group(scope)
    safe_path(scoped).mkdir(parents=True, exist_ok=True)
    # Exclusive mkdir is the collision/ownership boundary; never adopt an existing run.
    for _ in range(8):
        created = datetime.now(timezone.utc)
        manifest.update(created_at=created.isoformat(), run_id=uuid.uuid4().hex[:20])
        run = scoped / (created.strftime('%Y%m%dT%H%M%S') + '-' + manifest['run_id'])
        _validate_layout(run, manifest)
        try:
            run.mkdir()
            break
        except FileExistsError:
            continue
    else:
        raise ValueError('cannot allocate a unique owned review run')
    marker = {'owner_id': manifest['owner_id'], 'run_dir': str(run), 'archive_root': str(root),
              'repository_key': repository_key, 'scope_sha256': _digest(_json_bytes(scope))}
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
                return str(run)
        except (OSError, ValueError, TypeError, KeyError):
            _remove_unowned_prepare_directory(run, marker)
        raise
    return str(run)


@_locked_run
def select_profile(run_dir, selection_input):
    """Capture a profile transition and its trace event as one idempotent mutation."""
    raw = _input_object(selection_input, 'profile selection')
    run, manifest, marker = _load_run(run_dir)
    if manifest['schema_version'] != 7:
        raise ValueError('profile transitions require an archive 7 run')
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
    candidate.update(id='S' + str(len(history) + 1).zfill(3),
                     changed_from=previous['profile'],
                     event_id='E' + str(manifest['trace']['events'] + 1).zfill(6))
    manifest['profile_history'] = history + [candidate]
    _append_trace(run, manifest, marker, _profile_event(candidate))
    return manifest


@_locked_run
def register(run_dir, temporary_paths, *, context_input=None, authority=None):
    """Register coordinator-verified owned resources before discovery/execution."""
    run, manifest, marker = _load_run(run_dir)
    marker = _recover_trace(run, manifest, marker)
    _verify_files(run, manifest)
    if manifest['state'] not in {'prepared', 'processing'}:
        raise ValueError('register temporary resources before retention')
    if manifest['schema_version'] == 7 and manifest.get('operation', {}).get('disposition') != 'open':
        raise ValueError('review operation is not open; resume or recover before registering resources')
    if manifest['schema_version'] == 7 and context_input is None:
        raise ValueError('archive 7 registration requires captured context, including executors or an explicit empty list')
    temporary = _temporary_paths(temporary_paths, manifest)
    manifests = _temporary_manifests(temporary, manifest)
    executors = _executors(context_input, manifest, temporary)
    if manifest['schema_version'] == 7 and context_input is not None:
        context = read_json(context_input)
        if (context.get('profile') != manifest['profile_history'][-1]['profile']
                or context.get('selection_source') != manifest['profile_history'][0]['selection_source']
                or context.get('profile_history') != manifest['profile_history']):
            raise ValueError('executor context must preserve the profile history captured by the archive')
    rows = list(manifest.get('resource_claims', []))
    for raw in temporary:
        plan = review_resource_claims.plan_claim(raw, run, manifest, authority=authority)
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
            atomic_write(path, plan['bytes'])
        existing = [row for row in rows if row.get('session_dir') == str(safe_path(raw))]
        if existing and (len(existing) != 1 or existing[0] != plan['row']):
            raise ValueError('review archive already contains a different claim for this session')
        if not existing:
            rows.append(plan['row'])
    manifest.update(temporary_paths=temporary, temporary_manifests=manifests,
                    executors=executors, resource_claims=rows)
    _append_trace(run, manifest, marker, _milestone('register', 'Coordinator-owned temporary resources registered'))
    return manifest


def transfer_resources(source_run, successor_run, paths, *, authority, controller):
    """Transfer explicitly selected claimed workspaces under both run locks."""
    source_path, successor_path = safe_path(source_run), safe_path(successor_run)
    selected_paths = sorted({str(safe_path(path)) for path in paths})
    if not selected_paths or len(selected_paths) != len(paths):
        raise ValueError('resource transfer requires a nonempty unique explicit path list')
    authority = review_resource_claims._authority(authority)
    with run_locks([source_path, successor_path]):
        source, source_manifest, source_marker = _load_run(source_path)
        successor, next_manifest, next_marker = _load_run(successor_path)
        source_marker = _recover_trace(source, source_manifest, source_marker)
        next_marker = _recover_trace(successor, next_manifest, next_marker)
        _verify_files(source, source_manifest, allow_resource_transfer=True)
        _verify_files(successor, next_manifest, allow_resource_transfer=True)
        if source == successor:
            raise ValueError('source and successor review runs must differ')
        if (source_manifest.get('schema_version') != 7 or next_manifest.get('schema_version') != 7
                or source_manifest.get('repository_key') != next_manifest.get('repository_key')
                or source_manifest.get('repository_path') != next_manifest.get('repository_path')
                or source_manifest.get('scope') != next_manifest.get('scope')):
            raise ValueError('resource transfer requires archive-7 runs for the same repository and scope')
        if source_manifest.get('state') == 'complete' or next_manifest.get('state') == 'complete':
            raise ValueError('completed review history cannot participate in a resource transfer')
        normalized_controller = _controller(controller, next_manifest['controller']['identity'])
        source_intent = source_manifest.get('resource_transfer')
        next_intent = next_manifest.get('resource_transfer')
        intent = source_intent or next_intent

        if (isinstance(source_intent, dict) and source_intent.get('status') == 'complete'
                and isinstance(next_intent, dict) and next_intent.get('status') == 'complete'):
            if source_intent != next_intent:
                raise ValueError('completed source and successor transfer records differ')
            for item in source_intent['items']:
                review_resource_claims.verify_claim(item['session_dir'], successor)
            return {'status': 'transferred', 'transfer_id': source_intent['transfer_id'],
                    'source_run': str(source), 'successor_run': str(successor),
                    'resources': [item['session_dir'] for item in source_intent['items']]}

        if intent is None:
            if source_manifest.get('operation', {}).get('disposition') not in {'open', 'paused', 'blocked'}:
                raise ValueError('source review is already superseded or complete')
            if next_manifest.get('operation', {}).get('disposition') != 'open':
                raise ValueError('successor review must be open before claiming resources')
            items = []
            for raw in selected_paths:
                if raw not in source_manifest.get('temporary_paths', []):
                    raise ValueError('every transferred session must be registered to the source run')
                old_sidecar = review_resource_claims.verify_claim(raw, source)
                plan = review_resource_claims.plan_claim(
                    raw, successor, next_manifest, source_run=source,
                    authority=authority)
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
        else:
            _validate_transfer_intent(intent)
            comparable = dict(intent)
            comparable.pop('status', None)
            comparable.pop('completed_at', None)
            expected = {'schema_version': 1, 'transfer_id': intent['transfer_id'],
                        'source_run': str(source), 'successor_run': str(successor),
                        'source_run_id': source_manifest['run_id'],
                        'successor_run_id': next_manifest['run_id'],
                        'source_owner_id': source_manifest['owner_id'],
                        'successor_owner_id': next_manifest['owner_id'],
                        'repository_key': source_manifest['repository_key'],
                        'authority': authority, 'controller': normalized_controller,
                        'items': intent['items']}
            if comparable != expected or {item['session_dir'] for item in intent['items']} != set(selected_paths):
                raise ValueError('retry transfer inputs differ from the preserved two-run intent')
            for candidate in (source_intent, next_intent):
                if candidate is not None:
                    other = dict(candidate)
                    other.pop('status', None)
                    other.pop('completed_at', None)
                    if other != comparable:
                        raise ValueError('source and successor contain conflicting transfer intents')

        if source_intent is None:
            source_manifest['resource_transfer'] = copy.deepcopy(intent)
            source_marker = _save_manifest(source, source_manifest, source_marker)
        if next_intent is None:
            next_manifest['resource_transfer'] = copy.deepcopy(intent)
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
                                              if path not in moved_paths]
        source_manifest['temporary_manifests'] = _temporary_manifests(
            source_manifest['temporary_paths'], source_manifest)
        source_manifest['operation'].update(disposition='superseded', reason=authority,
                                            source='transfer-resources', phase='restart',
                                            successor=str(successor))
        next_manifest['resource_claims'] = next_rows
        next_manifest['temporary_paths'] = list(dict.fromkeys(
            list(next_manifest.get('temporary_paths', [])) + sorted(moved_paths)))
        next_manifest['temporary_manifests'] = _temporary_manifests(
            next_manifest['temporary_paths'], next_manifest)
        next_manifest['previous_run'] = next_manifest.get('previous_run') or str(source)
        next_manifest['lineage'] = {'kind': 'restart', 'source_run': str(source)}
        source_marker = _save_manifest(source, source_manifest, source_marker)
        next_marker = _save_manifest(successor, next_manifest, next_marker)

        for run, manifest, marker, other in ((source, source_manifest, source_marker, successor),
                                             (successor, next_manifest, next_marker, source)):
            summary = 'Resource transfer ' + transfer_id + ' to ' + manifest['resource_transfer']['successor_run']
            if manifest['resource_transfer']['source_run'] == str(run):
                summary = 'Resource transfer ' + transfer_id + ' from ' + str(run)
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
        completed['status'] = 'complete'
        completed['completed_at'] = datetime.now(timezone.utc).isoformat()
        source_manifest['resource_transfer'] = copy.deepcopy(completed)
        next_manifest['resource_transfer'] = copy.deepcopy(completed)
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


@_locked_run(when=lambda args, kwargs: kwargs.get('record_checkpoint', args[1] if len(args) > 1 else False))
def validate(run_dir, require_retained=False, record_checkpoint=False, *, require_complete=False):
    """Read-only archive gate; selected evidence is verified, never copied here."""
    if require_complete and record_checkpoint:
        raise ValueError('complete gate is read-only; cannot record a checkpoint')
    require_retained = require_retained or require_complete
    run, manifest, marker = _load_run(run_dir)
    if manifest['schema_version'] in TRACE_ARCHIVE_SCHEMAS and _digest((run / 'cierre.json').read_bytes()) != marker.get('manifest_sha256'):
        raise ValueError('ownership transition is pending; retry the interrupted helper mutation')
    _verify_files(run, manifest, required=require_retained)
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
        if manifest['schema_version'] == 7 and value.get('schema_version') != 10:
            raise ValueError('archive 7 requires final review schema 10')
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
    context = read_json(context_input)
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
    if input_file is None:
        if manifest['schema_version'] != 7 or not isinstance(manifest.get('checkpoint'), dict):
            raise ValueError('retention requires an explicit final review input or a provisional final checkpoint')
        candidate = run / 'pending' / 'review.json'
        if not candidate.is_file():
            raise ValueError('provisional checkpoint has no structurally valid final review to promote')
        input_file = candidate
    if manifest['schema_version'] == 7 and isinstance(manifest.get('checkpoint'), dict):
        if context_input is None and (run / 'pending' / 'context.json').is_file():
            context_input = run / 'pending' / 'context.json'
        if evidence_inputs is None:
            evidence_inputs = [run / name for name in manifest.get('pending_hashes', {})
                               if name.startswith('pending/evidence/')]
    value = read_json(input_file)
    if expected_schema is not None:
        if type(expected_schema) is not int or expected_schema not in range(1, 11):
            raise ValueError('expected schema must be a supported integer 1–10')
        if not isinstance(value, dict) or value.get('schema_version') != expected_schema:
            raise ValueError('expected schema ' + str(expected_schema) + ' differs from final review schema')
    if manifest['schema_version'] == 7:
        if value.get('schema_version') != 10:
            raise ValueError('archive 7 requires final review schema 10')
        if value.get('coverage', {}).get('execution', {}).get('profile_history') != manifest.get('profile_history'):
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
    temporary = _temporary_paths(temporary_paths, manifest)
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
    contents.update(_evidence_contents(run, manifest, evidence_inputs, create_directory=value.get('schema_version') not in (8, 9, 10)))
    if value.get('schema_version') in (8, 9, 10):
        if context_input is not None:
            _check_evidence_target(run, manifest, 'evidence/context.json')
            context_bytes = _json_bytes(read_json(context_input))
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
    for row in history:
        if resolved.get(row['reference']) != row.get('profile'):
            raise ValueError('profile source fragment differs from declared transition')
    errors = validate_execution_sources(value, context, events, references)
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
def close(run_dir, cleanup_file=None, *, cleanup=None, residuals=None):
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
    validate(run, require_retained=True, require_complete=manifest['state'] == 'complete')
    if (cleanup_file is None) == (cleanup is None):
        raise ValueError('supply either cleanup_file or an inline cleanup observation')
    if cleanup_file is not None:
        if residuals is not None:
            raise ValueError('residuals belong to the cleanup file or inline observation, not both')
        observed = read_json(cleanup_file)
    else:
        observed = {'cleanup': cleanup, 'residuals': residuals if residuals is not None else []}
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
    if manifest['schema_version'] == 7:
        manifest['resource_claims'] = review_resource_claims.validate_release_observation(
            manifest, present, observed.get('released_claims', []))
        review_resource_claims.validate_claims_for_close(run, manifest)
    cleanup = observed['cleanup']
    if (cleanup in {'complete', 'not_needed'} and residuals) or (cleanup == 'not_needed' and registered):
        raise ValueError('cleanup conflicts with registered resources or residuals')
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
    if value != read_json(run / 'review.json'):
        contents = {'review.json': _json_bytes(value), 'informe.md': report}
        if 'handoff.md' in manifest['hashes']:
            contents['handoff.md'] = review_contract.render_handoff(value, manifest.get('handoff_context')).encode('utf-8')
        manifest = _retain_data(run, manifest, marker, contents, record_retention=False)
        run, manifest, marker = _load_run(run)
    manifest.update(cleanup=cleanup, residuals=residuals,
                    state='complete' if cleanup != 'pending' else 'closing')
    if manifest['state'] == 'complete':
        manifest['closed_at'] = datetime.now(timezone.utc).isoformat()
        if manifest['schema_version'] == 7:
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
    create.add_argument('--profile-input', required=True,
                        help='Existing JSON selection captured before the new run is created')
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
    args = parser.parse_args()
    try:
        if args.command == 'prepare':
            source = read_json(args.harness_source_file) if args.harness_source_file else None
            if args.harness_source_file and (not isinstance(source, dict) or args.harness_id is None):
                raise ValueError('harness source file requires an object and an explicit --harness-id')
            result = {'run_dir': prepare(args.repo, args.scope_file, args.skill_version, args.harness,
                                         args.output_root, args.previous_run, args.temporary_path,
                                         profile_input=args.profile_input,
                                         controller=read_json(args.controller_input) if args.controller_input else None,
                                         harness_id=args.harness_id, harness_source=source)}
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
        elif args.command == 'select-profile':
            result = select_profile(args.run_dir, args.selection_input)
        elif args.command == 'validate':
            result = validate(args.run_dir, args.require_retained, args.record_checkpoint, require_complete=args.require_complete)
        elif args.command == 'record-event':
            result = record_event(args.run_dir, args.event_file, args.execution_metadata)
        else:
            result = close(args.run_dir, args.cleanup_file, cleanup=args.cleanup, residuals=args.residual)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
