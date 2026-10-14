"""Read-only inspection and bounded classification for durable review runs."""
import copy
import base64
import hashlib
import json
import re
from pathlib import Path


HASH = re.compile(r'[0-9a-f]{64}')
RUN_NAME = re.compile(r'[0-9]{8}T[0-9]{6}-[0-9a-f]{20}')
LOOKUP_REPORT_BYTES = 8 * 1024 * 1024
LOOKUP_CURSOR_BYTES = 2048


def _artifacts():
    import review_artifacts
    return review_artifacts


def validate_current_inputs(current_inputs, manifest, *, require_same_scope=True, compare_sources=True):
    """Validate caller-verified scope/source identities against pinned archive bytes."""
    artifacts = _artifacts()
    if (not isinstance(current_inputs, dict) or set(current_inputs) != {'scope', 'sources'}
            or not isinstance(current_inputs.get('sources'), dict)
            or len(current_inputs['sources']) > 64):
        raise ValueError('current inputs require exact scope and bounded source hash fields')
    artifacts._scope(current_inputs['scope'])
    if require_same_scope and current_inputs['scope'] != manifest.get('scope'):
        raise ValueError('current scope differs from the pinned review scope; restart is required')
    available = dict(manifest.get('hashes', {}))
    available.update(manifest.get('pending_hashes', {}))
    sources = {}
    for reference, digest in current_inputs['sources'].items():
        if (not isinstance(reference, str) or not reference.strip() or len(reference) > 500
                or any(ord(char) < 32 for char in reference)
                or not isinstance(digest, str) or not HASH.fullmatch(digest)):
            raise ValueError('current source identities must map bounded references to SHA-256 hashes')
        name = reference.split('#', 1)[0]
        if not artifacts._retained_name(name) and not artifacts._pending_file_name(name):
            raise ValueError('current source reference must identify retained or provisional review evidence')
        if compare_sources:
            expected = available.get(name)
            if expected is None:
                raise ValueError('current source has no preserved baseline identity: ' + reference)
            if expected != digest:
                raise ValueError('current source identity differs from preserved evidence: ' + reference)
        sources[reference] = digest
    return {'scope': copy.deepcopy(current_inputs['scope']), 'sources': sources}


def _action(name, reason):
    return {'action': name, 'reason': reason}


def _validated_sources(value, label):
    if not isinstance(value, dict) or len(value) > 64:
        raise ValueError(label + ' must be a bounded source-to-SHA-256 map')
    result = {}
    for reference, digest in value.items():
        if (not isinstance(reference, str) or not reference.strip() or len(reference) > 500
                or any(ord(char) < 32 for char in reference)
                or not isinstance(digest, str) or not HASH.fullmatch(digest)):
            raise ValueError(label + ' contains an invalid source identity')
        result[reference] = digest
    return result


def _identity_differences(retained, current):
    differences = []
    if not isinstance(retained, dict) or not isinstance(current, dict):
        raise ValueError('retained and current review inputs must be objects')
    retained_scope = retained.get('scope')
    current_scope = current.get('scope')
    if retained_scope is None or current_scope is None:
        differences.append({'field': 'scope', 'status': 'unknown',
                            'reason': 'A pinned scope identity is missing.'})
    else:
        artifacts = _artifacts()
        artifacts._scope(retained_scope)
        artifacts._scope(current_scope)
        for field in sorted(artifacts.SCOPE_FIELDS):
            if retained_scope.get(field) != current_scope.get(field):
                differences.append({'field': 'scope.' + field, 'status': 'changed',
                                    'reason': 'The pinned review scope differs.'})

    old_sources = _validated_sources(retained.get('sources', {}), 'retained inputs')
    new_sources = _validated_sources(current.get('sources', {}), 'current inputs')
    complete = current.get('source_set_complete')
    if complete is not True:
        differences.append({'field': 'source_set_complete', 'status': 'unknown',
                            'reason': 'The coordinator did not confirm a complete current source set.'})
    else:
        old_by_path = {name.split('#', 1)[0]: digest for name, digest in old_sources.items()}
        new_by_path = {name.split('#', 1)[0]: digest for name, digest in new_sources.items()}
        for name in sorted(set(old_by_path) | set(new_by_path)):
            if name not in old_by_path or name not in new_by_path:
                differences.append({'field': 'sources.' + name, 'status': 'changed',
                                    'reason': 'The complete source set added or removed a source.'})
            elif old_by_path[name] != new_by_path[name]:
                differences.append({'field': 'sources.' + name, 'status': 'changed',
                                    'reason': 'The source content identity differs.'})

    identity_fields = ('description_identity', 'requirements_identity', 'plan_identity',
                       'configuration_identity', 'profile')
    for field in identity_fields:
        if field not in current:
            continue
        current_value = current[field]
        if field not in retained:
            differences.append({'field': field, 'status': 'unknown',
                                'reason': 'The archived run does not preserve this identity.'})
        elif retained[field] != current_value:
            differences.append({'field': field, 'status': 'changed',
                                'reason': 'The recorded review input differs.'})
    status = ('changed' if any(row['status'] == 'changed' for row in differences)
              else 'unknown' if differences else 'applicable')
    return {'applicability': status, 'differences': differences}


def classify_candidate(manifest, retained_inputs, current_inputs):
    """Compare a pinned candidate to caller-supplied current identities without IO."""
    if not isinstance(manifest, dict):
        raise ValueError('candidate manifest must be an object')
    if not isinstance(retained_inputs, dict) or not isinstance(current_inputs, dict):
        raise ValueError('retained and current review inputs must be objects')
    expected = copy.deepcopy(retained_inputs)
    if 'scope' not in expected:
        expected['scope'] = manifest.get('scope')
    if 'profile' not in expected:
        history = manifest.get('profile_history')
        if isinstance(history, list) and history and isinstance(history[-1], dict):
            expected['profile'] = history[-1].get('profile')
    return _identity_differences(expected, current_inputs)


def _scope_prefix(scope):
    artifacts = _artifacts()
    anchor = next((field for field in ('reference', 'target', 'snapshot') if scope.get(field)), None)
    hint = scope[anchor] if anchor else scope['head']
    if anchor == 'reference' and '://' in hint:
        from urllib.parse import urlsplit
        hint = urlsplit(hint).path.rstrip('/').rsplit('/', 1)[-1]
    return artifacts._slug(scope['mode']) + '-' + artifacts._slug(hint) + '-', anchor


def _cursor_encode(repository_group, scope_digest, group_name, run_name):
    raw = json.dumps({'v': 1, 'repository_group': repository_group, 'scope_sha256': scope_digest,
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
    if not isinstance(value, dict) or set(value) != fields or value['v'] != 1:
        raise ValueError('lookup cursor has an unsupported shape')
    if value['repository_group'] != repository_group or value['scope_sha256'] != scope_digest:
        raise ValueError('lookup cursor belongs to a different repository or scope')
    if (not isinstance(value['group'], str) or not value['group'].startswith(prefix)
            or (exact and value['group'] != prefix)
            or not isinstance(value['run'], str) or not RUN_NAME.fullmatch(value['run'])):
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
    hashes = manifest.get('hashes', {})
    sources = {name: digest for name, digest in hashes.items() if name.startswith('evidence/')}
    retained = {'scope': manifest.get('scope'), 'sources': sources}
    history = manifest.get('profile_history')
    if isinstance(history, list) and history and isinstance(history[-1], dict):
        retained['profile'] = history[-1].get('profile')
    elif isinstance(record, dict) and isinstance(record.get('profile'), str):
        retained['profile'] = record['profile']
    description = record.get('description') if isinstance(record, dict) else None
    if isinstance(description, dict) and 'identity' in description:
        retained['description_identity'] = description['identity']
    return retained


def _candidate(run_dir, group_name, repo_identity, archive_root, scope, current_inputs):
    artifacts = _artifacts()
    run, manifest, _ = artifacts._load_run(run_dir)
    if (manifest.get('archive_root') != str(archive_root)
            or manifest.get('repository_key') != artifacts._digest(repo_identity.encode('utf-8'))[:20]
            or manifest.get('repository_identity', repo_identity) != repo_identity
            or artifacts._scope_group(manifest['scope']) != group_name):
        raise ValueError('candidate ownership, repository, or scope group differs from the lookup')
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
    if integrity == 'invalid':
        actions = [_action('preserve', 'The retained report is missing, oversized, or does not match its archive hash.')]
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
            'scope': copy.deepcopy(manifest['scope']), 'state': manifest.get('state'),
            'phase': operation.get('phase') or manifest.get('state'), 'operation': operation,
            'profile': latest[-1].get('profile') if isinstance(latest, list) and latest else None,
            'integrity': integrity, 'applicability': applicability['applicability'],
            'differences': applicability['differences'], 'actions': actions}


def find_candidates(repo, scope, *, archive_root=None, limit=20, cursor=None, current_inputs=None):
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
    prefix, anchor = _scope_prefix(scope)
    exact_group = artifacts._scope_group(scope)
    scope_digest = artifacts._digest(artifacts._json_bytes(scope))
    if current_inputs is not None:
        if not isinstance(current_inputs, dict) or current_inputs.get('scope') != scope:
            raise ValueError('current inputs must refer to the exact requested lookup scope')
        _validated_sources(current_inputs.get('sources', {}), 'current inputs')
    after = _cursor_decode(cursor, repo_group, scope_digest, prefix if anchor else exact_group,
                           exact=not bool(anchor))
    repository_path = root / repo_group
    try:
        repository_path = artifacts.safe_path(repository_path)
    except (OSError, ValueError):
        return {'schema_version': 1, 'candidates': [], 'next_cursor': None, 'truncated': False}
    if not repository_path.is_dir():
        return {'schema_version': 1, 'candidates': [], 'next_cursor': None, 'truncated': False}

    # Listing names is confined to this repository folder. Only the requested
    # MR/reference (or exact scope when no stable anchor exists) is opened.
    groups = sorted(repository_path.iterdir(), key=lambda path: path.name)
    candidates = []
    has_more = False
    last_key = None
    for group_path in groups:
        group_name = group_path.name
        if not (group_name.startswith(prefix) if anchor else group_name == exact_group):
            continue
        try:
            group_path = artifacts.safe_path(group_path)
        except (OSError, ValueError):
            continue
        if not group_path.is_dir():
            continue
        for run_path in sorted(group_path.iterdir(), key=lambda path: path.name):
            run_name = run_path.name
            if not RUN_NAME.fullmatch(run_name):
                continue
            key = (group_name, run_name)
            if after is not None and key <= after:
                continue
            try:
                run_path = artifacts.safe_path(run_path)
                if not run_path.is_dir():
                    continue
                candidate = _candidate(run_path, group_name, identity, root, scope, current_inputs)
                if candidate is None:
                    continue
            except (OSError, ValueError, TypeError, KeyError) as exc:
                candidate = {'run_dir': str(run_path), 'run_id': None, 'review_id': None,
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
    return {'schema_version': 1, 'candidates': candidates, 'next_cursor': next_cursor,
            'truncated': has_more}


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
        return base

    operation = copy.deepcopy(manifest.get('operation') or {
        'disposition': 'complete' if manifest.get('state') == 'complete' else 'open',
        'phase': None, 'reason': None, 'source': None, 'successor': None})
    pending = []
    if manifest.get('pending_trace') is not None:
        pending.append({'kind': 'trace_append', 'status': 'pending'})
    if manifest.get('checkpoint_transaction') is not None:
        pending.append({'kind': 'checkpoint', 'status': 'pending'})
    transfer = manifest.get('resource_transfer')
    if isinstance(transfer, dict) and transfer.get('status') != 'complete':
        pending.append({'kind': 'resource_transfer', 'status': 'pending',
                        'transfer_id': transfer.get('transfer_id')})
    if manifest.get('state') == 'retaining':
        pending.append({'kind': 'retention', 'status': 'pending'})
    if manifest.get('state') == 'closing':
        pending.append({'kind': 'closure', 'status': 'pending'})

    errors = []
    try:
        if not manifest.get('pending_trace'):
            artifacts._verify_files(run, manifest, allow_checkpoint_transaction=True,
                                    allow_resource_transfer=True)
        if not manifest.get('pending_trace') and not pending:
            import review_resource_claims
            for claim in manifest.get('resource_claims', []):
                if claim.get('status') == 'owned' and Path(claim['session_dir']).exists():
                    review_resource_claims.verify_claim(claim['session_dir'], run)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        errors.append(str(exc)[:1000])

    known = sorted(set(manifest.get('hashes', {})) | set(manifest.get('pending_hashes', {})))
    missing = [name for name in known if not (run / name).is_file()]
    resources = []
    claim_by_path = {row.get('session_dir'): row for row in manifest.get('resource_claims', [])
                     if isinstance(row, dict)}
    for raw in manifest.get('temporary_paths', []):
        path = Path(raw)
        row = claim_by_path.get(raw, {})
        resources.append({'path': raw, 'present': path.exists(), 'claim_status': row.get('status')})

    freshness = {'status': 'unknown', 'reasons': []}
    if current_inputs is not None:
        try:
            validate_current_inputs(current_inputs, manifest)
            freshness = {'status': 'verified', 'reasons': []}
        except (OSError, ValueError, TypeError, KeyError) as exc:
            reason = str(exc)[:1000]
            freshness = {'status': 'changed' if 'differs' in reason or 'restart is required' in reason else 'unknown',
                         'reasons': [reason]}

    disposition = operation.get('disposition')
    actions = []
    if errors:
        integrity_status = 'invalid'
        actions = [_action('preserve', 'Integrity/source verification failed; do not adopt or rewrite this run.')]
    elif pending:
        integrity_status = 'recoverable'
        actions = [_action('recover', 'A helper-owned transaction is pending; recover its exact recorded inputs first.')]
    else:
        integrity_status = 'verified'
        if disposition == 'paused':
            actions = [_action('resume', 'Continuing a user-paused run requires explicit continuation authority.'),
                       _action('restart', 'A fresh linked run is available if inputs or scope changed.')]
        elif disposition == 'blocked':
            actions = [_action('recover', 'Inspect the recorded blocker and recover only verified helper-owned state.'),
                       _action('restart', 'Start a new linked run if the original sources cannot be verified.')]
        elif disposition == 'superseded':
            actions = [_action('inspect_successor', 'The source run records a successor; inspect that exact run.')]
        elif disposition == 'complete' or manifest.get('state') == 'complete':
            actions = [_action('show', 'The completed report is immutable and may be shown as recorded.'),
                       _action('restart', 'A repeat creates a new linked review ID.')]
        else:
            actions = [_action('continue', 'The run is open; verify current inputs and operation phase before work.'),
                       _action('recover', 'Check for helper-owned state that can be completed from preserved bytes.'),
                       _action('restart', 'A fresh linked run is available if the scope changed.')]

    activity = ('completed' if integrity_status == 'verified'
                and (disposition == 'complete' or manifest.get('state') == 'complete') else 'unknown')
    return {'schema_version': 1, 'run_dir': str(run), 'run_id': manifest.get('run_id'),
            'review_id': 'CR-' + manifest['run_id'],
            'integrity': {'status': integrity_status, 'errors': errors},
            'phase': operation.get('phase') or manifest.get('state'), 'operation': operation,
            'known_sources': known, 'missing_sources': missing, 'resources': resources,
            'pending_transaction': pending, 'freshness': freshness, 'actions': actions,
            'activity': activity}


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
