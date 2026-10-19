"""Pure validation and identity helpers for durable review restarts."""
import copy
import hashlib
import json
import os
from pathlib import Path

import review_harness
import review_inputs
import review_profiles
import review_layout


INTENT_VERSION = 2
INTENT_FIELDS = {'schema_version', 'operation_id', 'request_sha256', 'intent_sha256', 'source', 'request',
                 'successor', 'status'}
SOURCE_FIELDS = {'run_dir', 'run_id', 'owner_id', 'repository_key', 'repository_path', 'archive_root'}
SUCCESSOR_FIELDS = {'run_dir', 'run_id', 'owner_id', 'reservation_id', 'created_at'}
REQUEST_FIELDS = {'profile_input', 'controller', 'authority', 'current_inputs', 'transfer_paths', 'harness',
                  'logical_scope_input'}


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def _sha(value):
    return hashlib.sha256(_json(value)).hexdigest()


def _bounded_text(value, label, limit=1000):
    if (not isinstance(value, str) or not value.strip() or len(value) > limit
            or any(ord(char) < 32 for char in value)):
        raise ValueError(label + ' must be nonempty bounded text')
    return value.strip()


def _input_object(value, label):
    result = (json.loads(Path(value).read_text(encoding='utf-8'))
              if isinstance(value, (str, os.PathLike)) else copy.deepcopy(value))
    if not isinstance(result, dict):
        raise ValueError(label + ' must be a JSON object')
    return result


def _path(value, label):
    if not isinstance(value, str) or not value or not Path(value).is_absolute() or '..' in Path(value).parts:
        raise ValueError(label + ' must be an absolute path without traversal')
    return os.path.normpath(value)


def _normalize_controller(value):
    raw = _input_object(value, 'restart controller')
    if set(raw) != {'identity', 'source'} or not isinstance(raw['identity'], dict):
        raise ValueError('restart controller requires identity and source')
    identity = raw['identity']
    if set(identity) != {'kind', 'name', 'provider_id'}:
        raise ValueError('restart controller identity has an invalid shape')
    if identity['kind'] not in {'coordinator', 'agent', 'tool', 'helper'}:
        raise ValueError('restart controller identity kind is invalid')
    identity['name'] = _bounded_text(identity['name'], 'restart controller name', 160)
    if identity['provider_id'] is not None:
        identity['provider_id'] = _bounded_text(identity['provider_id'], 'restart controller provider ID', 160)
    raw['source'] = _bounded_text(raw['source'], 'restart controller source', 500)
    return raw


def _normalize_harness(value):
    raw = {'harness': 'unknown', 'harness_id': None, 'harness_source': None} if value is None else _input_object(value, 'current harness')
    input_fields = {'harness', 'harness_id', 'harness_source'}
    canonical_fields = input_fields | {'harness_catalog_version', 'harness_diagnostics'}
    fields = frozenset(raw)
    if fields not in {frozenset(input_fields), frozenset(canonical_fields)}:
        raise ValueError('current harness requires harness, harness_id and harness_source')
    name = raw['harness']
    if not isinstance(name, str) or not name.strip():
        raise ValueError('current harness text must be nonempty')
    if fields == frozenset(canonical_fields):
        review_harness.validate_identity({key: raw[key] for key in canonical_fields - {'harness'}})
        return copy.deepcopy(raw)
    identity = review_harness.resolve(name, raw['harness_id'], raw['harness_source'])
    return {'harness': name.strip(), **identity}


def normalize_restart_request(profile_input, controller, authority, current_inputs, transfer_paths, harness=None,
                              logical_scope_input=None):
    """Validate caller inputs before any restart reservation or destination creation."""
    selection = review_profiles.validate_selection(_input_object(profile_input, 'profile selection'))
    if selection['phase'] != 'prepare' or selection['affected_assignments']:
        raise ValueError('restart profile selection must be an initial prepare decision')
    normalized_controller = _normalize_controller(controller)
    normalized_inputs = review_inputs.normalize_inputs(_input_object(current_inputs, 'current review inputs'))
    # Profile selection is a separate immutable decision in this new run; the
    # current-input payload must not inherit the source run's previous profile.
    normalized_inputs.pop('profile', None)
    logical_scope = review_layout.logical_scope(normalized_inputs['scope'], logical_scope_input)
    if ('logical_scope_identity' in normalized_inputs
            and normalized_inputs['logical_scope_identity'] != logical_scope['identity']):
        raise ValueError('restart current review inputs logical scope differs from the pinned selector')
    normalized_inputs['logical_scope_identity'] = logical_scope['identity']
    if logical_scope_input is not None and not isinstance(logical_scope_input, dict):
        raise ValueError('logical scope input must be an object')
    if not isinstance(transfer_paths, list) or len(transfer_paths) > 64:
        raise ValueError('restart transfer paths must be a bounded array')
    normalized_paths = [_path(path, 'restart transfer path') for path in transfer_paths]
    if len(set(os.path.normcase(path) for path in normalized_paths)) != len(normalized_paths):
        raise ValueError('restart transfer paths must be unique')
    return {'profile_input': {key: selection[key] for key in review_profiles.INPUT_FIELDS},
            'controller': normalized_controller,
            'authority': _bounded_text(authority, 'restart authority'),
            'current_inputs': normalized_inputs,
            'transfer_paths': sorted(normalized_paths, key=os.path.normcase),
            'harness': _normalize_harness(harness),
            'logical_scope_input': copy.deepcopy(logical_scope_input)}


def _request_identity(request):
    return {key: copy.deepcopy(value) for key, value in request.items() if key != 'authority'}


def _source_key(source):
    """Legacy local operation key is not a fabricated review/run identity."""
    return source['run_id'] or 'legacy-' + _sha({'run_dir': str(Path(source['run_dir']).resolve()),
                                               'owner_id': source['owner_id']})


def build_restart_intent(source, request, successor):
    """Bind one normalized request to an exact source and reserved successor."""
    if not isinstance(source, dict) or not SOURCE_FIELDS.issubset(source):
        raise ValueError('restart source identity is incomplete')
    if not isinstance(request, dict) or set(request) != REQUEST_FIELDS:
        raise ValueError('normalized restart request has an invalid shape')
    if not isinstance(successor, dict) or set(successor) != SUCCESSOR_FIELDS:
        raise ValueError('restart successor reservation has an invalid shape')
    source_value = {key: copy.deepcopy(source[key]) for key in SOURCE_FIELDS}
    source_value['run_dir'] = _path(source_value['run_dir'], 'restart source run directory')
    source_value['repository_path'] = _path(source_value['repository_path'], 'restart source repository')
    source_value['archive_root'] = _path(source_value['archive_root'], 'restart archive root')
    if source_value['run_id'] is not None:
        source_value['run_id'] = _bounded_text(source_value['run_id'], 'restart source run_id', 128)
    for field in ('owner_id', 'repository_key'):
        source_value[field] = _bounded_text(source_value[field], 'restart source ' + field, 128)
    successor_value = {key: copy.deepcopy(successor[key]) for key in SUCCESSOR_FIELDS}
    successor_value['run_dir'] = _path(successor_value['run_dir'], 'reserved successor path')
    for field in ('run_id', 'owner_id', 'reservation_id', 'created_at'):
        successor_value[field] = _bounded_text(successor_value[field], 'successor ' + field, 128)
    request_value = copy.deepcopy(request)
    request_digest = _sha(_request_identity(request_value))
    operation_id = hashlib.sha256((_source_key(source_value) + '\n' + source_value['owner_id']
                                   + '\n' + request_digest).encode('utf-8')).hexdigest()[:32]
    intent = {'schema_version': INTENT_VERSION, 'operation_id': operation_id,
              'request_sha256': request_digest, 'source': source_value,
              'request': request_value, 'successor': successor_value, 'status': 'pending'}
    intent['intent_sha256'] = _sha(intent)
    errors = validate_restart_intent(intent)
    if errors:
        raise ValueError('; '.join(errors))
    return intent


def validate_restart_intent(intent):
    """Return bounded validation errors for a durable restart intent."""
    errors = []
    if not isinstance(intent, dict) or set(intent) != INTENT_FIELDS:
        return ['restart intent has an invalid shape']
    if intent.get('schema_version') != INTENT_VERSION or intent.get('status') not in {'pending', 'complete'}:
        errors.append('restart intent version or status is invalid')
    source, request, successor = intent.get('source'), intent.get('request'), intent.get('successor')
    if not isinstance(source, dict) or set(source) != SOURCE_FIELDS:
        errors.append('restart intent source identity is invalid')
    if not isinstance(request, dict) or set(request) != REQUEST_FIELDS:
        errors.append('restart intent request shape is invalid')
    if not isinstance(successor, dict) or set(successor) != SUCCESSOR_FIELDS:
        errors.append('restart intent successor reservation is invalid')
    if errors:
        return errors[:16]
    try:
        unsigned = {key: value for key, value in intent.items() if key != 'intent_sha256'}
        if intent.get('intent_sha256') != _sha(unsigned):
            errors.append('restart intent digest differs')
        expected = _sha(_request_identity(request))
        if intent.get('request_sha256') != expected:
            errors.append('restart intent request digest differs')
        operation = hashlib.sha256((_source_key(source) + '\n' + source['owner_id'] + '\n' + expected).encode('utf-8')).hexdigest()[:32]
        if intent.get('operation_id') != operation:
            errors.append('restart intent operation identity differs')
        for field in ('run_dir', 'repository_path', 'archive_root'):
            _path(source[field], 'restart source ' + field)
        if source['run_id'] is not None:
            _bounded_text(source['run_id'], 'restart source run_id', 128)
        for field in ('owner_id', 'repository_key'):
            _bounded_text(source[field], 'restart source ' + field, 128)
        _path(successor['run_dir'], 'reserved successor path')
        for field in ('run_id', 'owner_id', 'reservation_id', 'created_at'):
            _bounded_text(successor[field], 'successor ' + field, 128)
        normalized = normalize_restart_request(request['profile_input'], request['controller'],
            request['authority'], request['current_inputs'], request['transfer_paths'], request['harness'],
            request['logical_scope_input'])
        if normalized != request:
            errors.append('restart intent request is not normalized')
    except (KeyError, TypeError, ValueError, OSError) as exc:
        errors.append('restart intent validation failed: ' + str(exc)[:500])
    return errors[:16]
