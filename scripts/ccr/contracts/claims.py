"""Value-level contracts for resource ownership claims and release receipts."""
import hashlib
import json
import re

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
