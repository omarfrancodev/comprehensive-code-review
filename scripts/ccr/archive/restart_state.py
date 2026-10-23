"""Read-only restart descriptor and receipt inspection."""
import copy
import hashlib
from pathlib import Path

from ccr.archive.intent_contracts import _validate_restart_abandonment_value
from ccr.archive.restart_contract import (
    SOURCE_FIELDS, _request_identity, _sha, validate_restart_intent,
)
from ccr.shared.encoding import archive_bytes as _json_bytes
from ccr.shared.json_io import read_json
from ccr.shared.paths import safe_path


def _digest(data):
    return hashlib.sha256(data).hexdigest()

def _restart_local_dir(source_run, manifest):
    source = safe_path(source_run)
    key = manifest.get('run_id') or 'legacy-' + _digest(
        _json_bytes({'run_dir': str(source), 'owner_id': manifest['owner_id']}))[:32]
    directory = source.parent / '.restart-intents' / key
    return safe_path(directory)

def _restart_intent_path(source_run, source_manifest, request):
    """Return a stable local path keyed by source identity and normalized request."""
    source = safe_path(source_run)
    digest = _sha(_request_identity(request))
    return _restart_local_dir(source, source_manifest) / (digest + '.json')

def _existing_restart_intent_path(source_run, source_manifest, request):
    """Look up only the two exact v2 encodings, without scanning other intents."""
    canonical = _restart_intent_path(source_run, source_manifest, request)
    previous = copy.deepcopy(request)
    previous['current_inputs'].pop('logical_scope_identity', None)
    previous_path = _restart_intent_path(source_run, source_manifest, previous)
    if previous_path != canonical and previous_path.exists():
        if canonical.exists():
            raise ValueError('multiple restart intents match this request; preserve both reservations')
        return previous_path
    return canonical

def _active_restart_paths(source_run, source_manifest):
    directory = _restart_local_dir(source_run, source_manifest)
    return directory / 'active.json', directory / 'active.owner.json'

def _restart_completion_path(intent_path):
    return Path(intent_path).with_suffix('.complete.json')

def _restart_abandonment_path(intent_path):
    return Path(intent_path).with_suffix('.abandoned.json')

def _validate_restart_abandonment(intent_path, intent):
    path = _restart_abandonment_path(intent_path)
    if not path.exists():
        return None
    receipt = read_json(path)
    return _validate_restart_abandonment_value(receipt, intent)

def _assert_not_restart_abandoned(manifest):
    receipt = manifest.get('restart_abandonment')
    if receipt is not None:
        raise ValueError('restart successor was explicitly abandoned; inspect its source: ' + receipt['source_run'])

def _restart_source_identity(run, manifest):
    return {key: manifest.get(key) if key != 'run_dir' else str(run)
            for key in SOURCE_FIELDS}

def _validate_restart_completion(path, intent):
    try:
        value = read_json(path)
    except FileNotFoundError:
        return None
    fields = {'schema_version', 'operation_id', 'source_run', 'source_owner_id',
              'intent_sha256', 'successor_run_dir', 'successor_owner_id', 'receipt_sha256'}
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError('restart completion receipt has an invalid shape')
    unsigned = {key: item for key, item in value.items() if key != 'receipt_sha256'}
    if (value['schema_version'] != 1 or value['receipt_sha256'] != _digest(_json_bytes(unsigned))
            or value['operation_id'] != intent['operation_id']
            or value['source_run'] != intent['source']['run_dir']
            or value['source_owner_id'] != intent['source']['owner_id']
            or value['intent_sha256'] != intent['intent_sha256']
            or value['successor_run_dir'] != intent['successor']['run_dir']
            or value['successor_owner_id'] != intent['successor']['owner_id']):
        raise ValueError('restart completion receipt differs from its reserved operation')
    return value

def _read_restart_intent(path, source_run, source_manifest):
    value = read_json(path)
    errors = validate_restart_intent(value)
    if errors:
        raise ValueError('; '.join(errors))
    if value['source'] != _restart_source_identity(source_run, source_manifest):
        raise ValueError('restart intent belongs to a different source owner')
    if safe_path(path) != _restart_intent_path(source_run, source_manifest, value['request']):
        raise ValueError('restart intent path differs from its source/request identity')
    return value

def _active_restart_operation(source_run, source_manifest, *, include_abandoned=False):
    """Read the one source-bound active descriptor; never scan other reviews."""
    active_path, owner_path = _active_restart_paths(source_run, source_manifest)
    if not active_path.exists() and not owner_path.exists():
        return None
    if not owner_path.exists():
        raise ValueError('restart active descriptor has no ownership transition record')
    owner = read_json(owner_path)
    fields = {'schema_version', 'source_run', 'source_owner_id', 'active_sha256',
              'previous_active_sha256', 'active_descriptor', 'previous_descriptor'}
    if (not isinstance(owner, dict) or set(owner) != fields or owner['schema_version'] != 1
            or owner['source_run'] != str(safe_path(source_run))
            or owner['source_owner_id'] != source_manifest.get('owner_id')):
        raise ValueError('restart active descriptor ownership differs from its source')
    descriptor = owner['active_descriptor']
    previous = owner['previous_descriptor']
    if not isinstance(descriptor, dict):
        raise ValueError('restart active descriptor transition is invalid')
    if active_path.exists():
        raw = read_json(active_path)
        digest = _digest(_json_bytes(raw))
        if digest == owner['active_sha256']:
            descriptor = raw
        elif digest == owner.get('previous_active_sha256') and isinstance(previous, dict):
            descriptor = raw
        else:
            raise ValueError('restart active descriptor bytes are outside the authorized transition')
    if (descriptor.get('schema_version') != 1 or descriptor.get('source_run') != str(safe_path(source_run))
            or descriptor.get('source_owner_id') != source_manifest.get('owner_id')
            or descriptor.get('status') not in {'pending', 'complete'}):
        raise ValueError('restart active descriptor is invalid')
    intent = descriptor.get('intent')
    errors = validate_restart_intent(intent)
    if errors:
        raise ValueError('; '.join(errors))
    if (descriptor.get('operation_id') != intent['operation_id']
            or descriptor.get('intent_path') != str(_restart_intent_path(source_run, source_manifest, intent['request']))
            or descriptor.get('intent_sha256') != intent['intent_sha256']
            or descriptor.get('successor_run_dir') != intent['successor']['run_dir']):
        raise ValueError('restart active descriptor differs from its intent')
    intent_path = Path(descriptor['intent_path'])
    if intent_path.exists():
        stored = _read_restart_intent(intent_path, source_run, source_manifest)
        if stored != intent:
            raise ValueError('restart active intent differs from its immutable request file')
    if descriptor['status'] == 'complete' or _validate_restart_completion(
            _restart_completion_path(intent_path), intent) is not None:
        return None
    if _validate_restart_abandonment(intent_path, intent) is not None:
        return descriptor if include_abandoned else None
    return descriptor
