"""Bounded archive lookup and explicit latest-result selection."""
import base64
import copy
from datetime import datetime
import hashlib
import json
import re
from pathlib import Path

from ccr.archive import layout as review_layout
from ccr.archive import history as history_ops
from ccr.archive.inspection import (
    _abandoned_source_action, _action, _recover_source_action, _superseded_actions, classify_candidate,
)
from ccr.archive.reader import (
    _digest, _repository_group, _slug, load_run as _load_run, select_output_root,
)
from ccr.archive.restart_observations import (
    _diagnostic_recovery_route,
    _restart_recovery_source,
)
from ccr.archive.restart_state import _active_restart_operation
from ccr.contracts.review import validate as review_contract
from ccr.contracts.scope import require_scope as _scope
from ccr.shared.git import git as _git, repository_identity
from ccr.shared.json_io import read_json
from ccr.shared.paths import safe_path
from ccr.workflow import inputs as review_inputs
from ccr.workflow.inputs import candidate_inputs as _candidate_inputs

HASH = re.compile(r'[0-9a-f]{64}')
RUN_NAME = re.compile(r'[0-9]{8}T[0-9]{6}Z--[A-Za-z0-9_-]{1,36}--[0-9a-f]{20}')
OLD_RUN_NAME = re.compile(r'[0-9]{8}T[0-9]{6}-[0-9a-f]{20}')
LOOKUP_REPORT_BYTES = 8 * 1024 * 1024
LOOKUP_CURSOR_BYTES = 2048


def _cursor_encode(repository_group, scope_digest, group_name, run_name):
    raw = json.dumps({'v': 2, 'repository_group': repository_group, 'scope_sha256': scope_digest,
                      'group': group_name, 'run': run_name}, separators=(',', ':'), sort_keys=True).encode('utf-8')
    return base64.urlsafe_b64encode(raw).decode('ascii').rstrip('=')

def _cursor_decode(cursor, repository_group, scope_digest, prefix, *, exact=False):
    if cursor is None:
        return None
    if not isinstance(cursor, str) or not cursor or len(cursor) > LOOKUP_CURSOR_BYTES:
        raise ValueError('lookup cursor is invalid or too large')
    try:
        raw = base64.urlsafe_b64decode(cursor + '=' * (-len(cursor) % 4))
        value = json.loads(raw.decode('utf-8'))
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError('lookup cursor is malformed') from exc
    fields = {'v', 'repository_group', 'scope_sha256', 'group', 'run'}
    if not isinstance(value, dict) or set(value) != fields or value['v'] != 2:
        raise ValueError('lookup cursor has an unsupported shape')
    if value['repository_group'] != repository_group or value['scope_sha256'] != scope_digest:
        raise ValueError('lookup cursor belongs to a different repository or scope')
    allowed_groups = prefix if isinstance(prefix, tuple) else (prefix,)
    if (not isinstance(value['group'], str) or not any(
                value['group'] == item or value['group'].startswith(item) for item in allowed_groups)
            or (exact and value['group'] != prefix)
            or not isinstance(value['run'], str)
            or not (RUN_NAME.fullmatch(value['run']) or OLD_RUN_NAME.fullmatch(value['run']))):
        raise ValueError('lookup cursor is outside the requested scope group')
    return value['group'], value['run']

def _hash_file_bounded(path, expected):
    target = safe_path(path)
    info = target.stat()
    if not target.is_file() or info.st_size > LOOKUP_REPORT_BYTES:
        return False
    digest = hashlib.sha256()
    with target.open('rb') as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest() == expected

def _read_candidate_record(path, expected):
    target = safe_path(path)
    if not target.is_file() or target.stat().st_size > LOOKUP_REPORT_BYTES:
        return None
    data = target.read_bytes()
    if len(data) > LOOKUP_REPORT_BYTES or hashlib.sha256(data).hexdigest() != expected:
        return None

    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError('duplicate JSON key in retained report')
            value[key] = item
        return value

    try:
        record = json.loads(data.decode('utf-8'), object_pairs_hook=unique)
        if not isinstance(record, dict) or record.get('stage') != 'final' or review_contract(record):
            return None
        return record
    except (UnicodeDecodeError, ValueError, TypeError):
        return None

def _candidate(run_dir, group_name, repo_identity, archive_root, scope, current_inputs, logical):
    run, manifest, _ = _load_run(run_dir)
    if (manifest.get('archive_root') != str(archive_root)
            or manifest.get('repository_key') != _digest(repo_identity.encode('utf-8'))[:20]
            or manifest.get('repository_identity', repo_identity) != repo_identity
            or review_layout.scope_group(manifest['logical_scope']) != group_name):
        raise ValueError('candidate ownership, repository, or scope group differs from the lookup')
    if manifest.get('logical_scope', {}).get('identity') != logical['identity']:
        return None
    stable_field = next((field for field in ('reference', 'target', 'snapshot') if scope.get(field)), None)
    if stable_field and manifest['scope'].get(stable_field) != scope.get(stable_field):
        return None

    disposition = (manifest.get('operation') or {}).get('disposition')
    complete = manifest.get('state') == 'complete' and (disposition in (None, 'complete'))
    integrity = 'manifest_verified'
    record = None
    if complete:
        hashes = manifest.get('hashes', {})
        record_hash = hashes.get('review.json')
        report_hash = hashes.get('informe.md')
        record = (_read_candidate_record(run / 'review.json', record_hash)
                  if isinstance(record_hash, str) and HASH.fullmatch(record_hash) else None)
        valid = (record is not None and isinstance(report_hash, str) and HASH.fullmatch(report_hash)
                 and _hash_file_bounded(run / 'informe.md', report_hash))
        integrity = 'report_verified' if valid else 'invalid'

    retained = _candidate_inputs(manifest, record)
    applicability = ({'applicability': 'unknown', 'differences': [
                        {'field': 'current_inputs', 'status': 'unknown',
                         'reason': 'Current source identities were not supplied.'}]}
                     if current_inputs is None
                     else classify_candidate(manifest, retained, current_inputs))
    operation = copy.deepcopy(manifest.get('operation') or {
        'disposition': 'complete' if complete else 'open', 'phase': manifest.get('state')})
    active_restart = _active_restart_operation(run, manifest, include_abandoned=True)
    recovery_source = _restart_recovery_source(run, manifest)
    restart_exit = _diagnostic_recovery_route(run, manifest,
        active_restart=active_restart, recovery_source=recovery_source)
    pending = ([{'kind': 'restart', 'status': 'pending', 'operation_id': active_restart['operation_id'],
                 'successor_run_dir': active_restart['successor_run_dir'],
                 'intent_path': active_restart['intent_path']}] if active_restart else [])
    if integrity == 'invalid':
        actions = [_action('preserve', 'The retained report is missing, oversized, or does not match its archive hash.')]
    elif restart_exit is not None:
        actions = restart_exit['actions']
    elif recovery_source is not None:
        actions = [_recover_source_action(recovery_source)]
    elif manifest.get('restart_abandonment') is not None:
        actions = [_abandoned_source_action(manifest)]
    elif pending:
        actions = (restart_exit['actions'] if restart_exit is not None else
                   [_action('recover', 'Recover the exact pending restart under its source lock.'),
                    _action('retry_restart', 'Retry the immutable request and reserved successor.')])
    elif disposition == 'superseded':
        actions = _superseded_actions()
    elif complete:
        if applicability['applicability'] == 'applicable':
            actions = [_action('show_report', 'The completed report hash matches; inspect this exact run before use.'),
                       _action('new_review', 'Create a linked review if a fresh evaluation is requested.')]
        else:
            actions = [_action('show_historical_report', 'The report is verified as recorded, but freshness is not established.'),
                       _action('new_review', 'Create a linked review to evaluate current inputs.')]
    else:
        actions = [_action('inspect_recover', 'Inspect this exact run and its inputs before any continuation.'),
                   _action('restart', 'Create a linked run if continuation is unavailable or inputs changed.')]
    latest = manifest.get('profile_history')
    return {'run_dir': str(run), 'run_id': manifest.get('run_id'),
            'review_id': 'CR-' + manifest['run_id'] if isinstance(manifest.get('run_id'), str) else None,
            'kind': 'native', 'scope': copy.deepcopy(manifest['scope']),
            'logical_scope': copy.deepcopy(manifest['logical_scope']), 'state': manifest.get('state'),
            'created_at': manifest.get('created_at'),
            'phase': operation.get('phase') or manifest.get('state'), 'operation': operation,
            'profile': latest[-1].get('profile') if isinstance(latest, list) and latest else None,
            'integrity': integrity, 'applicability': applicability['applicability'],
            'differences': applicability['differences'], 'actions': actions, 'pending_transaction': pending,
            **({'recovery': restart_exit['recovery']} if restart_exit is not None and integrity != 'invalid' else {})}

def find_candidates(repo, scope, *, archive_root=None, limit=20, cursor=None, current_inputs=None,
                    logical_scope_input=None, include_history=False):
    """Find bounded candidates only below this repository's stable scope group."""
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise ValueError('lookup limit must be an integer from 1 through 100')
    _scope(scope)
    repo = safe_path(repo)
    repo = safe_path(_git(repo, 'rev-parse', '--show-toplevel'))
    identity = repository_identity(repo)
    root = select_output_root(repo, archive_root)
    repo_group = _repository_group(identity)
    logical = review_layout.logical_scope(scope, logical_scope_input)
    exact_group = review_layout.scope_group(logical)
    scope_digest = hashlib.sha256(json.dumps({'scope': scope, 'logical_scope': logical},
        ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()
    if current_inputs is not None:
        current_inputs = review_inputs.normalize_inputs(current_inputs)
        if current_inputs.get('scope') != scope:
            raise ValueError('current inputs must refer to the exact requested lookup scope')
        current_inputs.setdefault('logical_scope_identity', logical['identity'])
    legacy_prefix = _legacy_scope_prefix(scope)
    after = _cursor_decode(cursor, repo_group, scope_digest,
                           tuple(item for item in (exact_group, legacy_prefix) if item))
    repository_path = root / repo_group
    try:
        repository_path = safe_path(repository_path)
        groups = sorted(repository_path.iterdir(), key=lambda path: path.name) if repository_path.is_dir() else []
    except (OSError, ValueError):
        return {'schema_version': 1, 'candidates': [], 'next_cursor': None,
                'truncated': False, 'search_complete': False}

    # Listing names is confined to the selected logical group inside this repository.
    candidates = []
    has_more = False
    search_complete = True
    last_key = None
    for group_path in groups:
        group_name = group_path.name
        if group_name != exact_group and not (legacy_prefix and group_name.startswith(legacy_prefix)):
            continue
        try:
            group_path = safe_path(group_path)
            if not group_path.is_dir():
                if group_name == exact_group:
                    search_complete = False
                continue
            runs = sorted(group_path.iterdir(), key=lambda path: path.name)
        except (OSError, ValueError):
            if group_name == exact_group:
                search_complete = False
            continue
        for run_path in runs:
            run_name = run_path.name
            if RUN_NAME.fullmatch(run_name):
                is_native_name = group_name == exact_group
            else:
                # Old run names are reported as incompatible only under this bounded group.
                old_run = OLD_RUN_NAME.fullmatch(run_name)
                if not old_run or group_name == exact_group:
                    continue
                is_native_name = False
            key = (group_name, run_name)
            if after is not None and key <= after:
                continue
            try:
                run_path = safe_path(run_path)
                if not run_path.is_dir():
                    continue
                if not is_native_name:
                    candidate = _legacy_candidate(run_path, scope)
                else:
                    candidate = _candidate(run_path, group_name, identity, root, scope, current_inputs, logical)
                if candidate is None:
                    continue
            except (OSError, ValueError, TypeError, KeyError) as exc:
                candidate = {'kind': 'native' if is_native_name else 'historical_source',
                             'run_dir': str(run_path), 'run_id': None, 'review_id': None,
                             'scope': None, 'state': 'unknown', 'phase': None,
                             'operation': {'disposition': 'unknown'}, 'profile': None,
                             'integrity': 'invalid', 'applicability': 'unknown',
                             'differences': [],
                             'actions': [_action('preserve', 'Candidate ownership or integrity could not be verified: '
                                                 + str(exc)[:300])]}
            if len(candidates) == limit:
                has_more = True
                break
            candidates.append(candidate)
            last_key = key
        if has_more:
            break
    next_cursor = (_cursor_encode(repo_group, scope_digest, last_key[0], last_key[1])
                   if has_more and last_key else None)
    history_truncated = False
    if include_history and cursor is None:
        history_root = root / '.historical' / repo_group
        if history_root.is_dir():
            try:

                history_dirs = sorted(history_root.iterdir(), key=lambda path: path.name)
                for history_dir in history_dirs:
                    if not history_dir.is_dir():
                        continue
                    try:
                        verified = history_ops.verify_history(history_dir)
                        consultation = verified['consultation']
                        prior_scope = consultation.get('scope')
                        prior_logical = review_layout.logical_scope(prior_scope)
                        if prior_logical['identity'] != logical['identity']:
                            continue
                        row = {'kind': 'historical_port', 'history_dir': str(history_dir),
                               'port_id': verified['port_id'], 'scope': prior_scope,
                               'integrity': 'verified_package', 'applicability': 'unknown',
                               'actions': [_action('show_history', 'Show as historical consultation; freshness is unknown.')]}
                        if len(candidates) >= limit:
                            history_truncated = True
                            break
                        candidates.append(row)
                    except (OSError, ValueError, TypeError, KeyError):
                        # Invalid packages are not surfaced as usable historical results.
                        continue
            except OSError:
                history_truncated = True
    return {'schema_version': 1, 'candidates': candidates, 'next_cursor': next_cursor,
            'truncated': has_more or history_truncated, 'search_complete': search_complete}

def select_latest(repo, scope, *, current_inputs, logical_scope_input=None, archive_root=None, max_scan=10000):
    """Explicit historical consultation; selection does not establish applicability."""
    return latest_verified_candidate(repo,scope,current_inputs=current_inputs,
        logical_scope_input=logical_scope_input,archive_root=archive_root,max_scan=max_scan)


def latest_verified_candidate(repo, scope, *, current_inputs, logical_scope_input=None, archive_root=None, max_scan=10000):
    """Shared read-only selection for historical consultation and reuse assessment."""
    if isinstance(max_scan, bool) or not isinstance(max_scan, int) or not 1 <= max_scan <= 10000:
        raise ValueError('max_scan must be an integer from 1 through 10000')
    logical = review_layout.logical_scope(scope, logical_scope_input)
    found = []
    cursor = None
    scanned = 0
    while True:
        page_size = min(100, max_scan - scanned)
        page = find_candidates(repo, scope, archive_root=archive_root, limit=page_size, cursor=cursor,
                               current_inputs=current_inputs, logical_scope_input=logical_scope_input)
        rows = page['candidates']
        scanned += len(rows)
        if not page.get('search_complete', True):
            return {'status': 'incomplete_search', 'selected': None, 'scanned': scanned,
                    'reason': 'The native logical scope could not be read completely.'}
        for row in rows:
            if row.get('kind') != 'native':
                continue
            if row.get('integrity') == 'invalid' or row.get('scope') is None:
                return {'status': 'incomplete_search', 'selected': None, 'scanned': scanned,
                        'reason': 'A candidate in the exact logical group could not be verified.'}
            if (row.get('logical_scope', {}).get('identity') == logical['identity']
                    and row.get('state') == 'complete'
                    and row.get('operation', {}).get('disposition') in (None, 'complete')
                    and row.get('integrity') == 'report_verified'):
                found.append(row)
        if not page['truncated']:
            break
        if scanned >= max_scan or not page['next_cursor']:
            return {'status': 'incomplete_search', 'selected': None, 'scanned': scanned,
                    'reason': 'The bounded scan reached its maximum before the scope was exhausted.'}
        cursor = page['next_cursor']
    if not found:
        return {'status': 'no_match', 'selected': None, 'scanned': scanned}
    parsed = []
    for row in found:
        try:
            value = datetime.fromisoformat(row['created_at'].replace('Z', '+00:00'))
            if value.tzinfo is None:
                raise ValueError()
            parsed.append((value, row))
        except (AttributeError, TypeError, ValueError):
            return {'status': 'incomplete_search', 'selected': None, 'scanned': scanned,
                    'reason': 'A verified result lacks an unambiguous timestamp.'}
    newest = max(value for value, _ in parsed)
    ties = [row for value, row in parsed if value == newest]
    if len(ties) != 1:
        return {'status': 'ambiguous', 'selected': None, 'scanned': scanned,
                'candidates': [{'run_dir': row['run_dir'], 'review_id': row['review_id']} for row in ties]}
    selected = ties[0]
    verified_inputs = review_inputs.normalize_inputs(current_inputs)
    verified_inputs.setdefault('logical_scope_identity', logical['identity'])
    try:
        _, manifest, _ = _load_run(selected['run_dir'])
        checked = _candidate(Path(selected['run_dir']), review_layout.scope_group(manifest['logical_scope']),
                             repository_identity(repo), select_output_root(repo, archive_root),
                             scope, verified_inputs, logical)
    except (OSError, ValueError, TypeError, KeyError):
        checked = None
    if (checked is None or checked.get('integrity') != 'report_verified'
            or checked.get('state') != 'complete'
            or checked.get('operation', {}).get('disposition') not in (None, 'complete')
            or checked.get('logical_scope', {}).get('identity') != logical['identity']
            or checked.get('created_at') != selected.get('created_at')
            or checked.get('run_id') != selected.get('run_id')):
        return {'status': 'incomplete_search', 'selected': None, 'scanned': scanned,
                'reason': 'The selected result changed during final verification.'}
    return {'status': 'selected', 'selected': checked, 'scanned': scanned}

def _legacy_scope_prefix(scope):
    anchor = next((field for field in ('reference', 'target', 'snapshot') if scope.get(field)), None)
    hint = scope[anchor] if anchor else scope.get('head')
    if not hint:
        return None
    if anchor == 'reference' and '://' in hint:
        from urllib.parse import urlsplit
        hint = urlsplit(hint).path.rstrip('/').rsplit('/', 1)[-1]
    return _slug(scope['mode']) + '-' + _slug(hint) + '-'

def _legacy_candidate(run_dir, scope):
    """Read only the bounded legacy header; never inspect resources or transactions."""
    path = safe_path(run_dir)
    header_path = path / 'cierre.json'
    if not header_path.is_file() or header_path.stat().st_size > 1024 * 1024:
        return {'kind': 'historical_source', 'run_dir': str(path), 'status': 'invalid',
                'actions': [_action('preserve', 'Historical header is missing or oversized.')], 'scope': None}
    try:
        manifest = read_json(header_path, max_bytes=1024 * 1024)
    except (ValueError, OSError, TypeError):
        return {'kind': 'historical_source', 'run_dir': str(path), 'status': 'invalid',
                'actions': [_action('preserve', 'Historical header cannot be read safely.')], 'scope': None}
    historical_scope = manifest.get('scope') if isinstance(manifest, dict) else None
    same_scope = historical_scope == scope
    if isinstance(historical_scope, dict) and scope.get('mode') in ('mr', 'pr'):
        same_scope = all(historical_scope.get(field) == scope.get(field)
                         for field in ('mode', 'repository', 'reference'))
    if not isinstance(manifest, dict) or not same_scope:
        return None
    classification = review_layout.classify_header(manifest)
    return {'kind': 'historical_source', 'run_dir': str(path), 'status': classification['status'],
            'run_id': manifest.get('run_id'), 'review_id': None, 'scope': copy.deepcopy(manifest.get('scope')),
            'actions': [_action(action, 'The old layout is incompatible; preserve it and port a verified report or start a new review.')
                        for action in classification.get('actions', ['preserve'])]}
