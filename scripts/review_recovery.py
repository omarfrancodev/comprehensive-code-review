"""Read-only inspection and bounded classification for durable review runs."""
import copy
import base64
from datetime import datetime
import hashlib
import json
import re
from pathlib import Path
import review_inputs
import review_layout


HASH = re.compile(r'[0-9a-f]{64}')
RUN_NAME = re.compile(r'[0-9]{8}T[0-9]{6}Z--[A-Za-z0-9_-]{1,36}--[0-9a-f]{20}')
OLD_RUN_NAME = re.compile(r'[0-9]{8}T[0-9]{6}-[0-9a-f]{20}')
LOOKUP_REPORT_BYTES = 8 * 1024 * 1024
LOOKUP_CURSOR_BYTES = 2048


def _artifacts():
    import review_artifacts
    return review_artifacts


def validate_current_inputs(current_inputs, manifest, *, require_same_scope=True, compare_sources=True,
                            require_applicable=False):
    """Validate common caller inputs and optionally require unchanged captured identities."""
    normalized = review_inputs.normalize_inputs(current_inputs)
    if require_same_scope and normalized['scope'] != manifest.get('scope'):
        raise ValueError('current scope differs from the pinned review scope; restart is required')
    # Callers that resume the exact pinned scope may omit this newer field. The
    # archive's normalized selector is authoritative in that case; changed
    # scopes still need an explicit selector identity and remain unknown.
    if (normalized['scope'] == manifest.get('scope')
            and 'logical_scope_identity' not in normalized):
        logical = manifest.get('logical_scope')
        if isinstance(logical, dict) and isinstance(logical.get('identity'), str):
            normalized['logical_scope_identity'] = logical['identity']
    retained = _candidate_inputs(manifest)
    if not compare_sources and retained is not None:
        retained = copy.deepcopy(retained)
        retained['sources'] = copy.deepcopy(normalized['sources'])
        retained['source_set_complete'] = normalized.get('source_set_complete')
    appraisal = review_inputs.compare_inputs(retained, normalized)
    if require_applicable and appraisal['applicability'] != 'applicable':
        raise ValueError('current review inputs are ' + appraisal['applicability']
                         + '; resume requires applicable inputs, use restart when they changed or are unknown')
    return normalized


def _action(name, reason):
    return {'action': name, 'reason': reason}


def classify_candidate(manifest, retained_inputs, current_inputs):
    """Compare a pinned candidate to caller-supplied current identities without IO."""
    if not isinstance(manifest, dict):
        raise ValueError('candidate manifest must be an object')
    return review_inputs.compare_inputs(retained_inputs, current_inputs)


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
    artifacts = _artifacts()
    target = artifacts.safe_path(path)
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
    artifacts = _artifacts()
    target = artifacts.safe_path(path)
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
        import review_contract
        if not isinstance(record, dict) or record.get('stage') != 'final' or review_contract.validate(record):
            return None
        return record
    except (UnicodeDecodeError, ValueError, TypeError):
        return None


def _candidate_inputs(manifest, record=None):
    captured = manifest.get('review_inputs')
    retained = (copy.deepcopy(captured) if isinstance(captured, dict) else
                {'scope': copy.deepcopy(manifest.get('scope')), 'sources': {},
                 'source_set_complete': False})
    retained.setdefault('scope', manifest.get('scope'))
    history = manifest.get('profile_history')
    if isinstance(history, list) and history and isinstance(history[-1], dict):
        retained['profile'] = history[-1].get('profile')
    elif isinstance(record, dict) and isinstance(record.get('profile'), str):
        retained['profile'] = record['profile']
    return retained


def _candidate(run_dir, group_name, repo_identity, archive_root, scope, current_inputs, logical):
    artifacts = _artifacts()
    run, manifest, _ = artifacts._load_run(run_dir)
    if (manifest.get('archive_root') != str(archive_root)
            or manifest.get('repository_key') != artifacts._digest(repo_identity.encode('utf-8'))[:20]
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
    active_restart = artifacts._active_restart_operation(run, manifest, include_abandoned=True)
    recovery_source = artifacts._restart_recovery_source(run, manifest)
    restart_exit = artifacts._diagnostic_recovery_route(run, manifest,
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
    artifacts = _artifacts()
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise ValueError('lookup limit must be an integer from 1 through 100')
    artifacts._scope(scope)
    repo = artifacts.safe_path(repo)
    repo = artifacts.safe_path(artifacts._git(repo, 'rev-parse', '--show-toplevel'))
    identity = artifacts.repository_identity(repo)
    root = artifacts.select_output_root(repo, archive_root)
    repo_group = artifacts._repository_group(identity)
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
        repository_path = artifacts.safe_path(repository_path)
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
            group_path = artifacts.safe_path(group_path)
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
                run_path = artifacts.safe_path(run_path)
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
                from review_history import verify_history
                history_dirs = sorted(history_root.iterdir(), key=lambda path: path.name)
                for history_dir in history_dirs:
                    if not history_dir.is_dir():
                        continue
                    try:
                        verified = verify_history(history_dir)
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
    """Select only an explicitly requested, fully scanned, verified native result."""
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
    artifacts = _artifacts()
    verified_inputs = review_inputs.normalize_inputs(current_inputs)
    verified_inputs.setdefault('logical_scope_identity', logical['identity'])
    try:
        _, manifest, _ = artifacts._load_run(selected['run_dir'])
        checked = _candidate(Path(selected['run_dir']), review_layout.scope_group(manifest['logical_scope']),
                             artifacts.repository_identity(repo), artifacts.select_output_root(repo, archive_root),
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
    artifacts = _artifacts()
    anchor = next((field for field in ('reference', 'target', 'snapshot') if scope.get(field)), None)
    hint = scope[anchor] if anchor else scope.get('head')
    if not hint:
        return None
    if anchor == 'reference' and '://' in hint:
        from urllib.parse import urlsplit
        hint = urlsplit(hint).path.rstrip('/').rsplit('/', 1)[-1]
    return artifacts._slug(scope['mode']) + '-' + artifacts._slug(hint) + '-'


def _legacy_candidate(run_dir, scope):
    """Read only the bounded legacy header; never inspect resources or transactions."""
    artifacts = _artifacts()
    path = artifacts.safe_path(run_dir)
    header_path = path / 'cierre.json'
    if not header_path.is_file() or header_path.stat().st_size > 1024 * 1024:
        return {'kind': 'historical_source', 'run_dir': str(path), 'status': 'invalid',
                'actions': [_action('preserve', 'Historical header is missing or oversized.')], 'scope': None}
    try:
        manifest = artifacts.read_json(header_path, max_bytes=1024 * 1024)
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


def _recover_source_action(source):
    return dict(_action('recover_source', 'Recover the exact restart through its owning source run.'),
                run_dir=source['run_dir'], operation_id=source['operation_id'])


def _abandoned_source_action(manifest):
    return dict(_action('inspect_source', 'This explicitly abandoned successor is terminal history; inspect its source.'),
                run_dir=manifest['restart_abandonment']['source_run'])


def _superseded_actions(resources=()):
    actions = [_action('inspect_successor', 'The source run records a successor; inspect that exact run.')]
    if any(row['claim_status'] == 'owned' and row['present'] for row in resources):
        actions.append(_action('cleanup', 'Clean the remaining source-owned sessions using this source --run-dir.'))
    return actions


def inspect_run(run_dir, *, current_inputs=None):
    """Inspect one explicitly selected run without repairing or changing any file."""
    artifacts = _artifacts()
    run_path = Path(run_dir).absolute()
    base = {'schema_version': 1, 'run_dir': str(run_path), 'run_id': None, 'review_id': None,
            'integrity': {'status': 'invalid', 'errors': []}, 'phase': None,
            'operation': {'disposition': 'unknown'}, 'known_sources': [], 'missing_sources': [],
            'resources': [], 'pending_transaction': [], 'freshness': {'status': 'unknown', 'reasons': []},
            'actions': [_action('preserve', 'Run identity has not been verified.')], 'activity': 'unknown'}
    try:
        run, manifest, marker = artifacts._load_run(run_path)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        base['integrity']['errors'] = [str(exc)[:1000]]
        if 'unsupported_layout' in str(exc):
            base['integrity']['status'] = 'unsupported_layout'
            base['actions'] = [_action('port_history', 'Old archives are read-only here; port a verified report for consultation.'),
                               _action('new_review', 'Start a new review using the current archive layout.'),
                               _action('preserve', 'Keep the original archive unchanged.')]
        return base

    operation = copy.deepcopy(manifest.get('operation') or {
        'disposition': 'complete' if manifest.get('state') == 'complete' else 'open',
        'phase': None, 'reason': None, 'source': None, 'successor': None})
    pending = []
    errors = []
    recovery_source = None
    restart_exit = None
    try:
        active_restart = artifacts._active_restart_operation(run, manifest, include_abandoned=True)
        recovery_source = artifacts._restart_recovery_source(run, manifest)
        if recovery_source is not None:
            pending.append({'kind': 'restart_source', 'status': 'pending',
                            'run_dir': recovery_source['run_dir'], 'operation_id': recovery_source['operation_id']})
        if active_restart:
            pending.append({'kind': 'restart', 'status': 'pending',
                            'operation_id': active_restart['operation_id'],
                            'successor_run_dir': active_restart['successor_run_dir'],
                            'intent_path': active_restart['intent_path']})
        restart_exit = artifacts._diagnostic_recovery_route(run, manifest,
            active_restart=active_restart, recovery_source=recovery_source)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        errors.append(str(exc)[:1000])
    if manifest.get('pending_trace') is not None:
        pending.append({'kind': 'trace_append', 'status': 'pending'})
    if manifest.get('checkpoint_transaction') is not None:
        pending.append({'kind': 'checkpoint', 'status':
                        'superseded' if operation.get('disposition') == 'superseded' else 'pending'})
    try:
        transfers = artifacts.normalize_transfer_history(manifest)
        for transfer in transfers:
            if transfer.get('status') != 'complete':
                pending.append({'kind': 'resource_transfer', 'status': 'pending',
                                'transfer_id': transfer.get('transfer_id')})
    except (ValueError, TypeError, KeyError) as exc:
        errors.append(str(exc)[:1000])
    cleanup = manifest.get('resource_cleanup')
    if isinstance(cleanup, dict) and cleanup.get('status') == 'pending':
        pending.append({'kind': 'resource_cleanup', 'status': 'pending',
                        'operation_id': cleanup.get('operation_id')})
    if manifest.get('state') == 'retaining':
        pending.append({'kind': 'retention', 'status': 'pending'})
    if manifest.get('state') == 'closing':
        pending.append({'kind': 'closure', 'status': 'pending'})

    try:
        if not manifest.get('pending_trace'):
            artifacts._verify_files(run, manifest, allow_checkpoint_transaction=True,
                                    allow_resource_transfer=True)
        resources = artifacts._resource_availability(run, manifest,
            verify_owned=not manifest.get('pending_trace')
                         and not any(row['status'] == 'pending' for row in pending))
    except (OSError, ValueError, TypeError, KeyError) as exc:
        errors.append(str(exc)[:1000])
        resources = []

    known = sorted(set(manifest.get('hashes', {})) | set(manifest.get('pending_hashes', {})))
    missing = [name for name in known if not (run / name).is_file()]
    freshness = {'status': 'unknown', 'reasons': [], 'differences': []}
    if current_inputs is not None:
        try:
            normalized = validate_current_inputs(current_inputs, manifest, require_same_scope=False)
            appraisal = classify_candidate(manifest, _candidate_inputs(manifest), normalized)
            status = {'applicable': 'verified', 'changed': 'changed', 'unknown': 'unknown'}[
                appraisal['applicability']]
            freshness = {'status': status,
                         'reasons': [row['reason'] for row in appraisal['differences']],
                         'differences': appraisal['differences']}
        except (OSError, ValueError, TypeError, KeyError) as exc:
            reason = str(exc)[:1000]
            freshness = {'status': 'unknown', 'reasons': [reason],
                         'differences': [{'field': 'current_inputs', 'status': 'unknown', 'reason': reason}]}

    disposition = operation.get('disposition')
    actions = []
    if errors:
        integrity_status = 'invalid'
        actions = [_action('preserve', 'Integrity/source verification failed; do not adopt or rewrite this run.')]
    elif restart_exit is not None:
        integrity_status = 'recoverable'
        actions = restart_exit['actions']
    elif recovery_source is not None:
        integrity_status = 'recoverable'
        actions = [_recover_source_action(recovery_source)]
    elif any(row['status'] == 'pending' for row in pending):
        integrity_status = 'recoverable'
        actions = (restart_exit['actions'] if restart_exit is not None else
                   [_action('recover', 'A helper-owned transaction is pending; recover its exact recorded inputs first.')])
    else:
        integrity_status = 'verified'
        if manifest.get('restart_abandonment') is not None:
            actions = [_abandoned_source_action(manifest)]
        elif disposition == 'paused':
            actions = [_action('resume', 'Continuing a user-paused run requires explicit continuation authority.'),
                       _action('restart', 'A fresh linked run is available if inputs or scope changed.')]
        elif disposition == 'blocked':
            actions = [_action('recover', 'Inspect the recorded blocker and recover only verified helper-owned state.'),
                       _action('restart', 'Start a new linked run if the original sources cannot be verified.')]
        elif disposition == 'superseded':
            actions = _superseded_actions(resources)
        elif disposition == 'complete' or manifest.get('state') == 'complete':
            actions = [_action('show', 'The completed report is immutable and may be shown as recorded.'),
                       _action('restart', 'A repeat creates a new linked review ID.')]
        else:
            actions = [_action('continue', 'The run is open; verify current inputs and operation phase before work.'),
                       _action('recover', 'Check for helper-owned state that can be completed from preserved bytes.'),
                       _action('restart', 'A fresh linked run is available if the scope changed.')]
        if any(row['availability'] == 'missing_unknown' for row in resources) and disposition not in {'superseded', 'complete'}:
            actions = [_action('restart', 'A claimed session is missing_unknown; preserve its claim and restart without transferring it.')]

    activity = ('completed' if integrity_status == 'verified'
                and (disposition == 'complete' or manifest.get('state') == 'complete') else 'unknown')
    run_id = manifest.get('run_id')
    return {'schema_version': 1, 'run_dir': str(run), 'run_id': run_id,
            'review_id': 'CR-' + run_id if isinstance(run_id, str) else None,
            'integrity': {'status': integrity_status, 'errors': errors},
            'phase': operation.get('phase') or manifest.get('state'), 'operation': operation,
            'known_sources': known, 'missing_sources': missing, 'resources': resources,
            'pending_transaction': pending, 'freshness': freshness, 'actions': actions,
            'activity': activity,
            **({'recovery': restart_exit['recovery']} if restart_exit is not None and not errors else {})}


def main():
    import argparse
    import json
    import sys
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', required=True)
    parser.add_argument('--current-inputs')
    args = parser.parse_args()
    try:
        value = _artifacts().read_json(args.current_inputs) if args.current_inputs else None
        print(json.dumps(inspect_run(args.run_dir, current_inputs=value), ensure_ascii=False, allow_nan=False))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
