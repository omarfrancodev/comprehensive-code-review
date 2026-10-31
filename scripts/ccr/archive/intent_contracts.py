"""Archive ownership intent and receipt contracts."""
import base64
import binascii
import copy
from datetime import datetime
import hashlib
import json
import re

from ccr.archive import trace as review_trace
from ccr.archive.restart_contract import _bounded_text
from ccr.contracts.claims import _authority, _encoded
from ccr.shared.encoding import archive_bytes as _json_bytes
from ccr.shared.paths import safe_path

CHECKPOINT_HASH = re.compile(r'[0-9a-f]{64}')
CLEANUP_RECEIPT_LIMIT = 64
TRANSFER_HISTORY_LIMIT = 64


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _validate_controller(value):
    if (not isinstance(value, dict) or set(value) != {'identity', 'source'}
            or not isinstance(value.get('identity'), dict)
            or set(value['identity']) != {'kind', 'name', 'provider_id'}
            or value['identity'].get('kind') not in {'helper', 'coordinator', 'agent', 'tool'}
            or not isinstance(value['identity'].get('name'), str)
            or not value['identity']['name'].strip() or len(value['identity']['name']) > 160
            or any(ord(char) < 32 for char in value['identity']['name'])
            or (value['identity'].get('provider_id') is not None
                and (not isinstance(value['identity'].get('provider_id'), str)
                     or not value['identity'].get('provider_id').strip()
                     or len(value['identity'].get('provider_id')) > 160
                     or any(ord(char) < 32 for char in value['identity'].get('provider_id'))))
            or not isinstance(value.get('source'), str) or not value['source'].strip()
            or len(value['source']) > 500 or any(ord(char) < 32 for char in value['source'])):
        raise ValueError('controller requires a trace identity and nonempty source')

def close_previous_disclosure_bytes(manifest):
    """Decode only bounded prior bytes bound to an owned close replacement."""
    if 'close_previous_disclosure' not in manifest:
        return None
    from ccr.contracts.check_disclosure import MAX_BYTES
    evidence = manifest['close_previous_disclosure']
    reference = 'evidence/check-disclosure.json'
    if (manifest.get('schema_version') != 8 or manifest.get('state') != 'retaining'
            or not isinstance(manifest.get('close_observation'), dict)
            or 'cleanup_receipts' not in manifest or 'resource_cleanup' not in manifest
            or not isinstance(evidence, dict) or set(evidence) != {'reference', 'base64'}
            or evidence.get('reference') != reference
            or reference not in manifest.get('hashes', {})
            or reference not in manifest.get('planned_hashes', {})
            or not isinstance(evidence.get('base64'), str)
            or len(evidence['base64']) > 4 * ((MAX_BYTES + 2) // 3)):
        raise ValueError('invalid owned previous disclosure byte evidence')
    try:
        raw = base64.b64decode(evidence['base64'], validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError('invalid previous disclosure base64 bytes') from exc
    if len(raw) > MAX_BYTES or _digest(raw) != manifest['hashes'][reference]:
        raise ValueError('previous disclosure bytes differ from the owned original hash')
    return raw


def _validate_cleanup_metadata(manifest):
    """Validate native cleanup intent and its bounded receipt inventory."""
    close_previous_disclosure_bytes(manifest)
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
                or _digest(_encoded(item['new_claim'])) != item['new_claim_sha256']):
            raise ValueError('invalid resource transfer claim plan')
        safe_path(item['session_dir'])
        if item['session_dir'] in seen_paths or item['new_claim'].get('claim_id') != item['claim_id']:
            raise ValueError('resource transfer paths and claims must be unique and bound')
        seen_paths.add(item['session_dir'])

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
    _authority(receipt['authority'])
    _validate_controller(receipt['controller'])
    _bounded_text(receipt['reason'], 'abandonment reason')
    return receipt

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
