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


FILES = ('review.json', 'informe.md')
OPTIONAL_FILES = ('measurements.json',)
TRACE_FILES = (review_trace.NAME, 'handoff.md')
MARKER = '.review-ownership.json'
ARCHIVE_SCHEMA_VERSION = 5
TRACE_ARCHIVE_SCHEMAS = frozenset({4, 5})
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
    if manifest.get('schema_version') not in (1, 2, 3, 4, ARCHIVE_SCHEMA_VERSION):
        raise ValueError('unsupported archive schema')
    states = {'prepared', 'retaining', 'closing', 'complete'}
    if manifest['schema_version'] == 5:
        states.add('processing')
    if manifest.get('state') not in states:
        raise ValueError('invalid archive state')
    if manifest.get('cleanup') not in {'pending', 'complete', 'not_needed'}:
        raise ValueError('invalid closure state')
    _validate_layout(run, manifest)
    return run, manifest, marker


def _verify_files(run, manifest, required=False):
    if manifest.get('pending_trace') is not None:
        raise ValueError('trace recording is pending; retry a helper mutation to recover the preserved event')
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
    if manifest['schema_version'] == 5 and event['occurred_at'] is not None and event['provenance']['source'] is None:
        raise ValueError('observed execution time requires an identifiable provenance source')
    if manifest['schema_version'] == 5:
        review_trace.validate_local_event_targets(event, (run / review_trace.NAME).read_bytes())
    if manifest['schema_version'] == 5 and manifest['state'] == 'prepared' and _starts_processing(event):
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


def _evidence_contents(run, manifest, inputs):
    contents = {}
    for raw in inputs or []:
        source = safe_path(raw)
        if not stat.S_ISREG(source.stat().st_mode):
            raise ValueError('selected evidence must be a regular file')
        name = 'evidence/' + _evidence_name(source.name)
        if name in contents:
            raise ValueError('duplicate selected evidence name: ' + name)
        target = safe_path(run / name)
        if target.exists() and name not in manifest['hashes'] and name not in manifest.get('planned_hashes', {}):
            raise ValueError('refusing to clobber foreign evidence: ' + name)
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
    if contents:
        safe_path(run / 'evidence').mkdir(exist_ok=True)
    return contents


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


def prepare(repo, scope_file, skill_version, harness, output_root=None, previous_run=None, temporary_paths=None):
    repo = safe_path(repo)
    repo = safe_path(_git(repo, 'rev-parse', '--show-toplevel'))
    scope = read_json(scope_file)
    _scope(scope)
    if not isinstance(skill_version, str) or not skill_version.strip() or not isinstance(harness, str) or not harness.strip():
        raise ValueError('skill version and harness are required')
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
                'temporary_paths': [], 'temporary_manifests': [], 'executors': [], 'hashes': {}}
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
    _append_trace(run, manifest, marker, _milestone('prepare', 'Owned archive prepared with pinned scope'))
    return str(run)


def register(run_dir, temporary_paths):
    """Register coordinator-verified owned resources before discovery/execution."""
    run, manifest, marker = _load_run(run_dir)
    marker = _recover_trace(run, manifest, marker)
    _verify_files(run, manifest)
    if manifest['state'] not in {'prepared', 'processing'}:
        raise ValueError('register temporary resources before retention')
    temporary = _temporary_paths(temporary_paths, manifest)
    manifests = _temporary_manifests(temporary, manifest)
    manifest.update(temporary_paths=temporary, temporary_manifests=manifests)
    _append_trace(run, manifest, marker, _milestone('register', 'Coordinator-owned temporary resources registered'))
    return manifest


def validate(run_dir, require_retained=False, record_checkpoint=False):
    """Read-only archive gate; selected evidence is verified, never copied here."""
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
        if value.get('schema_version') in (6, 7) and value.get('review_id') != 'CR-' + manifest.get('run_id', ''):
            raise ValueError('retained review ID differs from archive run ID')
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


def retain(run_dir, input_file, measurement_inputs=None, unavailable_reason=None, temporary_paths=None, evidence_inputs=None, context_input=None, handoff=False, handoff_context_input=None):
    run, manifest, marker = _load_run(run_dir)
    marker = _recover_trace(run, manifest, marker)
    if manifest['state'] == 'complete':
        raise ValueError('completed review history is immutable; prepare a new run with --previous-run')
    _verify_files(run, manifest)
    if handoff_context_input is not None and not handoff:
        raise ValueError('--handoff-context-input requires an explicit --handoff request')
    value = read_json(input_file)
    errors = review_contract.validate(value)
    if errors or not isinstance(value, dict) or value.get('stage') != 'final':
        raise ValueError('; '.join(errors) if errors else 'only final review records can be retained')
    if value['scope'] != manifest['scope']:
        raise ValueError('final review scope differs from the pinned scope')
    if value.get('schema_version') in (6, 7) and value.get('review_id') != 'CR-' + manifest.get('run_id', ''):
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
    contents.update(_evidence_contents(run, manifest, evidence_inputs))
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


def close(run_dir, cleanup_file=None, *, cleanup=None, residuals=None):
    """Observe exact registered resources and persist closure; never remove resources."""
    run, manifest, marker = _load_run(run_dir)
    marker = _recover_trace(run, manifest, marker)
    _verify_files(run, manifest, required=True)
    if (cleanup_file is None) == (cleanup is None):
        raise ValueError('supply either cleanup_file or an inline cleanup observation')
    if cleanup_file is not None:
        if residuals is not None:
            raise ValueError('residuals belong to the cleanup file or inline observation, not both')
        observed = read_json(cleanup_file)
    else:
        observed = {'cleanup': cleanup, 'residuals': residuals if residuals is not None else []}
    if (not isinstance(observed, dict) or set(observed) != {'cleanup', 'residuals'}
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
    resources = commands.add_parser('register', help='Register verified owned temporary paths before use')
    resources.add_argument('--run-dir', required=True)
    resources.add_argument('--temporary-path', action='append', required=True)
    gate = commands.add_parser('validate', help='Read-only ownership, layout and retained hash checks')
    gate.add_argument('--run-dir', required=True)
    gate.add_argument('--require-retained', action='store_true', help='Require complete retained evidence before cleanup')
    gate.add_argument('--record-checkpoint', action='store_true', help='Record a passed milestone in an open schema4/5 archive')
    trace = commands.add_parser('record-event', help='Coordinator records one bounded structured milestone')
    trace.add_argument('--run-dir', required=True)
    trace.add_argument('--event-file', required=True)
    trace.add_argument('--execution-metadata', help='Optional existing review_runner run.json; no timing or identity inference')
    keep = commands.add_parser('retain')
    keep.add_argument('--run-dir', required=True)
    keep.add_argument('--input', required=True)
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
            result = {'run_dir': prepare(args.repo, args.scope_file, args.skill_version, args.harness,
                                         args.output_root, args.previous_run, args.temporary_path)}
        elif args.command == 'retain':
            result = retain(args.run_dir, args.input, args.measurement_input,
                            args.unavailable_reason, args.temporary_path, args.evidence_input, args.context_input, args.handoff, args.handoff_context_input)
        elif args.command == 'register':
            result = register(args.run_dir, args.temporary_path)
        elif args.command == 'validate':
            result = validate(args.run_dir, args.require_retained, args.record_checkpoint)
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
