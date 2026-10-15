"""Private, run-bound ownership records for disposable review workspaces."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat


CLAIM_NAME = '.review-run-owner.json'
CLAIM_SCHEMA = 1
HASH = re.compile(r'[0-9a-f]{64}')


def _encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n').encode('utf-8')


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _safe_path(value):
    path = Path(value)
    if not path.is_absolute() or '..' in path.parts:
        raise ValueError('resource claims require an absolute path without traversal')
    for component in path.parts[1:]:
        if any(char in component for char in '<> :"|?*'.replace(' ', '')) or component.endswith((' ', '.')):
            raise ValueError('unsafe resource claim path component: ' + component)
    for current in (path, *path.parents):
        try:
            info = current.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('resource claim path traverses a link/reparse point: ' + str(current))
    return path.resolve()


def _read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate JSON key in resource claim')
            result[key] = value
        return result
    return json.loads(_safe_path(path).read_text(encoding='utf-8'), object_pairs_hook=unique,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('invalid JSON constant')))


def _workspace(session_dir):
    session = _safe_path(session_dir)
    if not session.is_dir():
        raise ValueError('claimed review session is missing or not a directory')
    manifest_path = session / 'manifest.json'
    if not manifest_path.is_file():
        return None
    if not (session / '.owner.json').is_file():
        try:
            raw_manifest = _read_json(manifest_path)
        except (OSError, ValueError):
            return None
        markers = {'session_id', 'session_dir', 'owner_token'}
        if not isinstance(raw_manifest, dict) or not markers.intersection(raw_manifest):
            return None
    import review_workspace
    try:
        workspace = review_workspace.load(manifest_path)
    except review_workspace.ReviewError as exc:
        raise ValueError('claimed review workspace is invalid; preserve it for inspection: ' + str(exc)) from exc
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise ValueError('claimed review workspace manifest is invalid; preserve it for inspection') from exc
    try:
        owner = _read_json(session / '.owner.json')
    except (OSError, ValueError) as exc:
        raise ValueError('claimed review workspace owner marker is invalid; preserve it for inspection') from exc
    token = owner.get('owner_token')
    if (not isinstance(token, str) or not re.fullmatch(r'[0-9a-f]{32}', token)
            or owner.get('session_id') != workspace.get('session_id')
            or owner.get('repo') != workspace.get('repo')):
        raise ValueError('review session owner token or identity is invalid')
    return session, workspace, _digest(token.encode('utf-8'))


def _archive(run_dir):
    import review_artifacts
    run, manifest, marker = review_artifacts._load_run(run_dir)
    if manifest.get('schema_version') != 7:
        raise ValueError('resource claims require archive schema 7')
    return run, manifest, marker


def _authority(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 1000 or any(ord(char) < 32 for char in value):
        raise ValueError('resource adoption/transfer requires explicit bounded authority')
    return value.strip()


def _claim_row(sidecar, *, status='owned', claim_sha256=None, **extra):
    fields = ('claim_id', 'session_id', 'session_dir', 'owner_token_sha256', 'repo',
              'repository_key', 'run_id', 'owner_id', 'archive_path')
    result = {key: sidecar[key] for key in fields}
    result.update(status=status, claim_sha256=claim_sha256 or _digest(_encoded(sidecar)))
    result.update(adopted=sidecar['adopted'], authority=sidecar['authority'],
                  transferred_from=sidecar['transferred_from'])
    transfer_id = extra.pop('transfer_id', None)
    if transfer_id is not None:
        result['transfer_id'] = transfer_id
    result.update(extra)
    return result


def _preflight_unbound(session_dir, manifest, *, authority=None):
    """Check a resource before a new archive exists, without claiming it."""
    candidate = _safe_path(session_dir)
    if not candidate.exists() or not candidate.is_dir():
        return {'action': 'not_workspace', 'session_dir': str(candidate)}
    workspace_data = _workspace(candidate)
    if workspace_data is None:
        return {'action': 'not_workspace', 'session_dir': str(candidate)}
    session, workspace, token_digest = workspace_data
    import review_artifacts
    identity = review_artifacts.repository_identity(workspace['repo'])
    if (review_artifacts._digest(identity.encode('utf-8'))[:20] != manifest.get('repository_key')
            or manifest.get('repository_identity', identity) != identity):
        raise ValueError('review session belongs to a different repository')
    sidecar_path = session / CLAIM_NAME
    if not sidecar_path.exists():
        if authority is not None:
            _authority(authority)
        return {'action': 'adopt_pending', 'session_dir': str(session)}
    current = _read_json(sidecar_path)
    if (isinstance(current, dict) and current.get('schema_version') == CLAIM_SCHEMA
            and current.get('status') == 'bootstrap'):
        if (current.get('session_id') != workspace['session_id']
                or current.get('owner_token_sha256') != token_digest
                or current.get('repo') != workspace['repo']):
            raise ValueError('bootstrap resource claim does not match the owned workspace session')
        return {'action': 'claim_pending', 'session_dir': str(session)}
    _validate_sidecar(current, session, workspace, token_digest)
    restart_source = (manifest.get('restart_operation') or {}).get('source_run')
    verify_claim(session, current['archive_path'], allow_checkpoint_transaction=
                 restart_source == current['archive_path'] == manifest.get('previous_run'))
    if (manifest.get('restart_operation') is not None
            and current.get('run_id') == manifest.get('run_id')
            and current.get('owner_id') == manifest.get('owner_id')):
        return {'action': 'existing', 'session_dir': str(session)}
    if manifest.get('previous_run') == current['archive_path']:
        return {'action': 'transfer_pending', 'session_dir': str(session)}
    raise ValueError('review session is already claimed by another review run; use transfer-resources with explicit authority')


def plan_resource_registration(paths, manifest, *, authority=None):
    """Preflight a complete resource set before the caller mutates any sidecar."""
    if manifest.get('schema_version') != 7:
        return []
    selected = [_safe_path(path) for path in paths]
    if len({os.path.normcase(str(path)) for path in selected}) != len(selected):
        raise ValueError('resource registration paths must be unique')
    run_dir = manifest.get('_claim_run_dir')
    plans = []
    for path in selected:
        if run_dir is None:
            plans.append(_preflight_unbound(path, manifest, authority=authority))
        else:
            plans.append(plan_claim(path, run_dir, manifest, authority=authority))
    if run_dir is not None:
        active = {os.path.normcase(str(_safe_path(row['session_dir'])))
                  for row in manifest.get('resource_claims', [])
                  if isinstance(row, dict) and row.get('status') in {'owned', 'releasing'}
                  and isinstance(row.get('session_dir'), str)}
        for path, plan in zip(selected, plans):
            if plan['action'] == 'not_workspace' and os.path.normcase(str(path)) in active:
                raise ValueError('active review workspace claim is missing or no longer verifiable')
    return plans


def _sidecar_for(session, workspace, token_digest, run, manifest, *, prior=None,
                 adopted=False, authority=None, transferred_from=None):
    if prior is None:
        claim_id = 'RC-' + os.urandom(16).hex()
    else:
        claim_id = prior['claim_id']
    return {'schema_version': CLAIM_SCHEMA, 'status': 'owned', 'claim_id': claim_id,
            'session_id': workspace['session_id'], 'session_dir': str(session),
            'owner_token_sha256': token_digest, 'repo': workspace['repo'],
            'repository_key': manifest['repository_key'], 'run_id': manifest['run_id'],
            'owner_id': manifest['owner_id'], 'archive_path': str(run),
            'adopted': bool(adopted), 'authority': authority if adopted or transferred_from else None,
            'transferred_from': transferred_from}


def plan_claim(session_dir, run_dir, manifest, *, source_run=None, authority=None,
               allow_checkpoint_transaction=False):
    """Return an owned sidecar/manifest row plan without writing either one."""
    candidate = _safe_path(session_dir)
    if not candidate.exists():
        return {'action': 'not_workspace', 'sidecar': None, 'bytes': None, 'row': None,
                'expected_current_sha256': None}
    if not candidate.is_dir():
        raise ValueError('registered review resource is not a directory')
    workspace_data = _workspace(candidate)
    if workspace_data is None:
        return {'action': 'not_workspace', 'sidecar': None, 'bytes': None, 'row': None,
                'expected_current_sha256': None}
    session, workspace, token_digest = workspace_data
    run, actual, _ = _archive(run_dir)
    for field in ('run_id', 'owner_id', 'repository_key', 'repository_path'):
        if manifest.get(field) != actual.get(field):
            raise ValueError('claim plan manifest differs from the durable review run')
    if str(session) not in manifest.get('temporary_paths', []) and source_run is None:
        raise ValueError('review session must be registered as a temporary resource before claiming')
    import review_artifacts
    if review_artifacts.repository_identity(workspace['repo']) != actual.get('repository_identity'):
        raise ValueError('review session belongs to a different repository')

    sidecar_path = session / CLAIM_NAME
    current = None
    current_hash = None
    if sidecar_path.exists():
        current = _read_json(sidecar_path)
        current_hash = _digest(sidecar_path.read_bytes())
    if current is not None and current.get('schema_version') == CLAIM_SCHEMA and current.get('status') == 'bootstrap':
        if (current.get('session_id') != workspace['session_id']
                or current.get('owner_token_sha256') != token_digest
                or current.get('repo') != workspace['repo']):
            raise ValueError('bootstrap resource claim does not match the owned workspace session')
        sidecar = _sidecar_for(session, workspace, token_digest, run, actual)
        return {'action': 'claim', 'sidecar': sidecar, 'bytes': _encoded(sidecar),
                'row': _claim_row(sidecar), 'expected_current_sha256': current_hash}

    if current is None:
        if authority is None:
            raise ValueError('legacy session adoption requires explicit authority')
        reason = _authority(authority)
        sidecar = _sidecar_for(session, workspace, token_digest, run, actual,
                               adopted=True, authority=reason)
        return {'action': 'adopt', 'sidecar': sidecar, 'bytes': _encoded(sidecar),
                'row': _claim_row(sidecar, adopted=True, authority=reason),
                'expected_current_sha256': None}

    _validate_sidecar(current, session, workspace, token_digest)
    if current.get('run_id') == actual.get('run_id') and current.get('owner_id') == actual.get('owner_id'):
        rows = [row for row in actual.get('resource_claims', []) if row.get('claim_id') == current.get('claim_id')]
        if len(rows) > 1:
            raise ValueError('duplicate resource claim rows in review archive')
        if rows and rows[0].get('status') == 'releasing':
            raise ValueError('resource cleanup is pending; recover or retry cleanup before registration')
        if rows and rows[0].get('status') == 'released':
            raise ValueError('resource claim was released; it cannot be registered again')
        transfer_id = rows[0].get('transfer_id') if rows else None
        if transfer_id is not None and (not isinstance(transfer_id, str)
                                        or not re.fullmatch(r'RT-[0-9a-f]{32}', transfer_id)):
            raise ValueError('archive resource claim has an invalid transfer identity')
        expected_row = _claim_row(current, claim_sha256=current_hash,
                                  transfer_id=transfer_id,
                                  adopted=current.get('adopted', False),
                                  authority=current.get('authority'),
                                  transferred_from=current.get('transferred_from'))
        if rows and rows[0] != expected_row:
            raise ValueError('archive resource claim differs from its workspace sidecar')
        return {'action': 'existing' if rows else 'recover', 'sidecar': current,
                'bytes': _encoded(current), 'row': expected_row, 'expected_current_sha256': current_hash}

    if source_run is None:
        raise ValueError('review session is already claimed by a different review run')
    source_path = _safe_path(source_run)
    if str(source_path) != current.get('archive_path'):
        raise ValueError('source run does not match the current resource owner')
    _authority(authority)
    verify_claim(session, source_path, allow_checkpoint_transaction=allow_checkpoint_transaction)
    sidecar = _sidecar_for(session, workspace, token_digest, run, actual, prior=current,
                           adopted=False, authority=authority, transferred_from=str(source_path))
    return {'action': 'transfer', 'sidecar': sidecar, 'bytes': _encoded(sidecar),
            'row': _claim_row(sidecar, transferred_from=str(source_path)),
            'expected_current_sha256': current_hash}


def _validate_sidecar(sidecar, session, workspace, token_digest):
    fields = {'schema_version', 'status', 'claim_id', 'session_id', 'session_dir',
              'owner_token_sha256', 'repo', 'repository_key', 'run_id', 'owner_id',
              'archive_path', 'adopted', 'authority', 'transferred_from'}
    if (not isinstance(sidecar, dict) or set(sidecar) != fields
            or sidecar.get('schema_version') != CLAIM_SCHEMA or sidecar.get('status') != 'owned'
            or not isinstance(sidecar.get('claim_id'), str) or not re.fullmatch(r'RC-[0-9a-f]{32}', sidecar['claim_id'])
            or sidecar.get('session_id') != workspace.get('session_id')
            or sidecar.get('session_dir') != str(session)
            or sidecar.get('owner_token_sha256') != token_digest
            or sidecar.get('repo') != workspace.get('repo')
            or not isinstance(sidecar.get('repository_key'), str)
            or not re.fullmatch(r'[0-9a-f]{20}', sidecar['repository_key'])
            or not isinstance(sidecar.get('run_id'), str) or not re.fullmatch(r'[0-9a-f]{20}', sidecar['run_id'])
            or not isinstance(sidecar.get('owner_id'), str) or not re.fullmatch(r'[0-9a-f]{32}', sidecar['owner_id'])
            or not isinstance(sidecar.get('archive_path'), str)
            or type(sidecar.get('adopted')) is not bool
            or (sidecar.get('authority') is not None and not isinstance(sidecar.get('authority'), str))
            or (sidecar.get('transferred_from') is not None and not isinstance(sidecar.get('transferred_from'), str))):
        raise ValueError('invalid or foreign resource claim sidecar')
    _safe_path(sidecar['archive_path'])
    if sidecar['adopted'] and not sidecar['authority']:
        raise ValueError('adopted resource claim has no authority source')


def verify_claim(session_dir, run_dir, *, allow_checkpoint_transaction=False):
    return _verify_claim(session_dir, run_dir, verify_integrity=True,
                         allow_checkpoint_transaction=allow_checkpoint_transaction)


def inspect_claim_identity(session_dir, run_dir):
    """Read ownership only for abandoning an empty adoption; never authorize cleanup/work.

    The owning manifest, sidecar and claim row must match. Pending work evidence
    belongs to that other review and is neither recovered nor certified here.
    """
    return _verify_claim(session_dir, run_dir, verify_integrity=False)


def _verify_claim(session_dir, run_dir, *, verify_integrity, allow_checkpoint_transaction=False):
    workspace_data = _workspace(session_dir)
    if workspace_data is None:
        raise ValueError('resource claim requires a valid review workspace session')
    session, workspace, token_digest = workspace_data
    run, manifest, _ = _archive(run_dir)
    import review_artifacts
    if verify_integrity:
        review_artifacts._verify_files(run, manifest, allow_checkpoint_transaction=
            allow_checkpoint_transaction or manifest.get('operation', {}).get('disposition') == 'superseded')
    if review_artifacts.repository_identity(workspace['repo']) != manifest.get('repository_identity'):
        raise ValueError('claimed workspace belongs to a different repository')
    sidecar = _read_json(session / CLAIM_NAME)
    _validate_sidecar(sidecar, session, workspace, token_digest)
    if (sidecar.get('archive_path') != str(run) or sidecar.get('run_id') != manifest.get('run_id')
            or sidecar.get('owner_id') != manifest.get('owner_id')
            or sidecar.get('repository_key') != manifest.get('repository_key')):
        raise ValueError('resource claim is owned by another review run')
    sidecar_hash = _digest(_encoded(sidecar))
    rows = [row for row in manifest.get('resource_claims', []) if row.get('claim_id') == sidecar['claim_id']]
    if len(rows) == 1 and rows[0].get('status') not in {'owned', 'releasing'}:
        raise ValueError('resource claim is no longer active in this review archive')
    transfer_id = rows[0].get('transfer_id') if len(rows) == 1 else None
    if transfer_id is not None and (not isinstance(transfer_id, str)
                                    or not re.fullmatch(r'RT-[0-9a-f]{32}', transfer_id)):
        raise ValueError('archive resource claim has an invalid transfer identity')
    expected_row = _claim_row(sidecar, status=rows[0]['status'] if len(rows) == 1 else 'owned',
                              claim_sha256=sidecar_hash,
                              transfer_id=transfer_id,
                              adopted=sidecar['adopted'], authority=sidecar['authority'],
                              transferred_from=sidecar['transferred_from'])
    if (len(rows) != 1 or any(rows[0].get(key) != value for key, value in expected_row.items())
            or set(rows[0]) - (set(expected_row) | {'transfer_id'})):
        raise ValueError('archive resource claim does not match the verified workspace owner')
    return sidecar


def validate_release_observation(manifest, present_paths, released_claims):
    """Bind missing paths to an explicit, previously verified cleanup receipt."""
    present = {str(_safe_path(path)) for path in present_paths}
    if not isinstance(released_claims, list):
        raise ValueError('release receipts must be a list')
    by_id = {}
    for receipt in released_claims:
        if (not isinstance(receipt, dict) or set(receipt) != {'session_id', 'run_id', 'claim_id', 'claim_sha256'}
                or not all(isinstance(receipt.get(key), str) and receipt[key] for key in receipt)
                or not re.fullmatch(r'[0-9a-f]{32}', receipt['session_id'])
                or not re.fullmatch(r'[0-9a-f]{20}', receipt['run_id'])
                or not re.fullmatch(r'RC-[0-9a-f]{32}', receipt['claim_id'])
                or not HASH.fullmatch(receipt['claim_sha256']) or receipt['claim_id'] in by_id):
            raise ValueError('invalid or duplicate resource release receipt')
        by_id[receipt['claim_id']] = receipt
    rows = json.loads(json.dumps(manifest.get('resource_claims', [])))
    expected_ids = set()
    run_id = manifest.get('run_id')
    for row in rows:
        status = row.get('status')
        if status not in {'owned', 'releasing', 'released'}:
            continue
        expected_ids.add(row['claim_id'])
        path = str(_safe_path(row['session_dir']))
        receipt = by_id.get(row['claim_id'])
        if path in present:
            if status == 'released':
                raise ValueError('released resource path exists again; preserve and inspect it')
            if receipt is not None:
                raise ValueError('resource release receipt conflicts with a still-present claimed session')
            continue
        if (status == 'released' and receipt is None
                and 'cleanup_receipts' not in manifest and 'resource_cleanup' not in manifest
                and row.get('released_by') == 'review_workspace.cleanup'
                and row.get('release_claim_sha256') == row.get('claim_sha256')):
            # Archive-7 files written before durable cleanup receipts already
            # recorded the release in their hash-bound claim row.
            continue
        if (receipt is None or receipt['session_id'] != row['session_id'] or receipt['run_id'] != run_id
                or receipt['claim_sha256'] != row['claim_sha256']):
            raise ValueError('missing claimed resource does not prove its own cleanup; release evidence is required')
        if status == 'released':
            if row.get('release_claim_sha256') != receipt['claim_sha256']:
                raise ValueError('resource release receipt does not match the durable released claim')
        else:
            row['status'] = 'released'
            row['released_by'] = 'review_workspace.cleanup'
            row['release_claim_sha256'] = receipt['claim_sha256']
    if set(by_id) - expected_ids:
        raise ValueError('release receipt identifies a claim absent from this review archive')
    return rows


def validate_claims_for_close(run_dir, manifest):
    """Refuse close when claimed sessions are missing, transferred, or unverifiable."""
    rows = manifest.get('resource_claims', [])
    for row in rows:
        path = _safe_path(row['session_dir'])
        if row.get('status') in {'owned', 'releasing'}:
            if not path.exists():
                raise ValueError('claimed session is missing; its own cleanup was not recorded')
            verify_claim(path, run_dir)
        elif row.get('status') in {'released', 'transferred'} and path.exists():
            raise ValueError('released/transferred resource path exists again; preserve and inspect it')
        elif row.get('status') not in {'released', 'transferred'}:
            raise ValueError('unknown resource claim status blocks review closure')
