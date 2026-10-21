"""Value-level contracts for resource ownership claims and release receipts."""
import hashlib
import json
import re

from ccr.shared.paths import safe_path

CLAIM_SCHEMA = 1
HASH = re.compile(r'[0-9a-f]{64}')

def _encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n').encode('utf-8')

def _digest(data):
    return hashlib.sha256(data).hexdigest()

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
    safe_path(sidecar['archive_path'])
    if sidecar['adopted'] and not sidecar['authority']:
        raise ValueError('adopted resource claim has no authority source')

def validate_release_observation(manifest, present_paths, released_claims):
    """Bind missing paths to an explicit, previously verified cleanup receipt."""
    present = {str(safe_path(path)) for path in present_paths}
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
        path = str(safe_path(row['session_dir']))
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
