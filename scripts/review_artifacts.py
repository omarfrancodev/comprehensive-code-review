#!/usr/bin/env python3
"""Prepare, retain and close durable review evidence (Python 3.10+, stdlib only).

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


FILES = ('review.json', 'informe.md')
OPTIONAL_FILES = ('measurements.json',)
MARKER = '.review-ownership.json'
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
    if manifest.get('state') not in {'prepared', 'retaining', 'closing', 'complete'}:
        raise ValueError('invalid archive state')
    if manifest.get('cleanup') not in {'pending', 'complete', 'not_needed'}:
        raise ValueError('invalid closure state')
    if manifest.get('schema_version') not in (1, 2):
        raise ValueError('unsupported archive schema')
    return run, manifest, marker


def _verify_files(run, manifest, required=False):
    hashes = manifest.get('hashes')
    if not isinstance(hashes, dict) or any(not _retained_name(name) for name in hashes):
        raise ValueError('invalid retained file manifest')
    planned = manifest.get('planned_hashes', {}) if manifest['state'] == 'retaining' else {}
    required_files = set(FILES) | (set(OPTIONAL_FILES) if manifest['schema_version'] == 1 else set())
    if required and (not required_files.issubset(hashes) or manifest['state'] == 'retaining'):
        raise ValueError('retained evidence is absent or interrupted')
    if not isinstance(planned, dict) or any(not _retained_name(name) for name in planned):
        raise ValueError('invalid planned evidence paths')
    for name in set(FILES) | set(OPTIONAL_FILES) | set(hashes) | set(planned):
        path = safe_path(run / name)
        try:
            data = path.read_bytes()
        except FileNotFoundError:
            if (required and name in required_files | set(hashes)) or (name in hashes and manifest['state'] != 'retaining'):
                raise ValueError('retained evidence missing: ' + name)
            continue
        if _digest(data) not in {hashes.get(name), planned.get(name)}:
            raise ValueError('refusing to clobber modified archived file: ' + name)


def _evidence_name(name):
    label = re.sub(r'[^a-zA-Z0-9._-]', '-', name).strip(' .')[:80] or 'evidence'
    if re.fullmatch(r'(?i)(CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])(?:\..*)?', label):
        label = 'evidence-' + label[:70]
    return label


def _retained_name(name):
    if name in FILES + OPTIONAL_FILES:
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
    manifest = {'schema_version': 2, 'skill_version': skill_version, 'harness': harness,
                'scope': scope, 'archive_root': str(root), 'repository_path': str(repo),
                'repository_key': repository_key, 'previous_run': previous,
                'owner_id': uuid.uuid4().hex, 'created_at': datetime.now(timezone.utc).isoformat(),
                'state': 'prepared', 'retained': False, 'cleanup': 'pending', 'residuals': [],
                'temporary_paths': [], 'temporary_manifests': [], 'executors': [], 'hashes': {}}
    manifest['temporary_paths'] = _temporary_paths(temporary_paths, manifest)
    manifest['temporary_manifests'] = _temporary_manifests(manifest['temporary_paths'], manifest)
    identity_path = identity.split(':', 1)[1].replace('\\', '/')
    label = Path(identity_path).parent.name if identity_path.endswith('/.git') else identity_path.rsplit('/', 1)[-1]
    group = root / (_slug(label) + '-' + repository_key)
    scope_key = _digest(_json_bytes(scope))[:16]
    hint = scope['reference'] or scope['target'] or scope['snapshot'] or scope['head']
    if scope['reference'] and '://' in hint:
        hint = urlsplit(hint).path.rstrip('/').rsplit('/', 1)[-1]
    scoped = group / (_slug(scope['mode']) + '-' + _slug(hint) + '-' + scope_key)
    safe_path(scoped).mkdir(parents=True, exist_ok=True)
    # Exclusive mkdir is the collision/ownership boundary; never adopt an existing run.
    for _ in range(8):
        run = scoped / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid.uuid4().hex[:20])
        try:
            run.mkdir()
            break
        except FileExistsError:
            continue
    else:
        raise ValueError('cannot allocate a unique owned review run')
    marker = {'owner_id': manifest['owner_id'], 'run_dir': str(run), 'archive_root': str(root),
              'repository_key': repository_key, 'scope_sha256': _digest(_json_bytes(scope))}
    _save_manifest(run, manifest, marker)
    return str(run)


def _retain_data(run, manifest, marker, contents):
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


def retain(run_dir, input_file, measurement_inputs=None, unavailable_reason=None, temporary_paths=None, evidence_inputs=None, context_input=None):
    run, manifest, marker = _load_run(run_dir)
    if manifest['state'] == 'complete':
        raise ValueError('completed review history is immutable; prepare a new run with --previous-run')
    _verify_files(run, manifest)
    value = read_json(input_file)
    errors = review_contract.validate(value)
    if errors or not isinstance(value, dict) or value.get('stage') != 'final':
        raise ValueError('; '.join(errors) if errors else 'only final review records can be retained')
    if value['scope'] != manifest['scope']:
        raise ValueError('final review scope differs from the pinned scope')
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


def close(run_dir, cleanup_file):
    """Observe exact registered resources and persist closure; never remove resources."""
    run, manifest, marker = _load_run(run_dir)
    _verify_files(run, manifest, required=True)
    observed = read_json(cleanup_file)
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
        manifest = _retain_data(run, manifest, marker,
                                {'review.json': _json_bytes(value), 'informe.md': report})
        run, manifest, marker = _load_run(run)
    manifest.update(cleanup=cleanup, residuals=residuals,
                    state='complete' if cleanup != 'pending' else 'closing')
    if manifest['state'] == 'complete':
        manifest['closed_at'] = datetime.now(timezone.utc).isoformat()
    _save_manifest(run, manifest, marker)
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
    keep = commands.add_parser('retain')
    keep.add_argument('--run-dir', required=True)
    keep.add_argument('--input', required=True)
    keep.add_argument('--measurement-input', action='append')
    keep.add_argument('--unavailable-reason')
    keep.add_argument('--temporary-path', action='append')
    keep.add_argument('--evidence-input', action='append')
    keep.add_argument('--context-input', help='Existing neutral context JSON with executor provenance')
    finish = commands.add_parser('close')
    finish.add_argument('--run-dir', required=True)
    finish.add_argument('--cleanup-file', required=True)
    args = parser.parse_args()
    try:
        if args.command == 'prepare':
            result = {'run_dir': prepare(args.repo, args.scope_file, args.skill_version, args.harness,
                                         args.output_root, args.previous_run, args.temporary_path)}
        elif args.command == 'retain':
            result = retain(args.run_dir, args.input, args.measurement_input,
                            args.unavailable_reason, args.temporary_path, args.evidence_input, args.context_input)
        else:
            result = close(args.run_dir, args.cleanup_file)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
