"""Durable, replayable compact-to-full promotion without invented milestones."""
import copy
from datetime import datetime, timezone
import secrets

from ccr.archive import layout
from ccr.archive.compact import _digest, _read_prepared, _validate_prepared, read_compact
from ccr.archive.reader import _repository_group
from ccr.execution.locks import run_locks
from ccr.shared.encoding import archive_bytes
from ccr.shared.git import git, repository_identity
from ccr.shared.json_io import atomic_write, read_json
from ccr.shared.paths import safe_path
from ccr.workflow.inputs import normalize_inputs


def validate_intent(intent):
    fields = {'schema_version', 'operation_id', 'source_review_id', 'source_reservation',
              'source_sha256', 'request', 'successor', 'intent_sha256'}
    if not isinstance(intent, dict) or set(intent) != fields or intent['schema_version'] != 1:
        raise ValueError('invalid compact promotion intent')
    value = copy.deepcopy(intent)
    digest = value.pop('intent_sha256')
    if digest != _digest(value):
        raise ValueError('compact promotion intent hash differs')
    stage = safe_path(intent['source_reservation'])
    prepared = _read_prepared(stage)
    checked, _ = _validate_prepared(prepared)
    if checked != stage or _digest(prepared) != intent['source_sha256'] or prepared['review_id'] != intent['source_review_id']:
        raise ValueError('compact promotion source differs from its reservation')
    request = intent['request']
    original = prepared['request']
    if (request['scope'] != original['scope'] or request['inputs'] != original['review_inputs']
            or request['logical_scope_input'] != original['logical_scope_input']
            or request['repository_identity'] != original['repository_identity']
            or request['archive_root'] != original['archive_root']
            or request['profile_input'] != original['profile_input']
            or request['skill_version'] != original['producer']['skill_version']
            or request['harness'] != original['producer']['harness']):
        raise ValueError('compact promotion cannot change pinned inputs')
    source_path = safe_path(prepared['run_dir'])
    published_hash = request.get('source_manifest_sha256')
    if published_hash is not None:
        if _digest(read_compact(source_path)['manifest']) != published_hash:
            raise ValueError('published compact source changed during promotion')
    elif source_path.exists():
        raise ValueError('unpublished compact source appeared after promotion')
    successor = intent['successor']
    expected = safe_path(safe_path(request['archive_root']) / _repository_group(request['repository_identity'])
        / layout.scope_group(prepared['logical_scope']) / layout.run_name(request['scope'],
            successor['created_at'], successor['run_id'], request['logical_scope_input']))
    if safe_path(successor['run_dir']) != expected:
        raise ValueError('compact promotion destination differs from its reservation')
    return intent


def promote_compact(*, repo, prepared, current_inputs, operation_id, reason, profile_input,
                    skill_version, harness, prepare_full, controller=None):
    stage, target = _validate_prepared(prepared)
    if _read_prepared(stage) != prepared:
        raise ValueError('compact source reservation changed')
    if not isinstance(operation_id, str) or not operation_id or len(operation_id) > 128:
        raise ValueError('promotion operation ID is required')
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000:
        raise ValueError('promotion requires an observed reason')
    repo = safe_path(git(repo, 'rev-parse', '--show-toplevel'))
    original = prepared['request']
    if repository_identity(repo) != original['repository_identity']:
        raise ValueError('promotion repository differs from pinned source')
    if (profile_input != original['profile_input'] or skill_version != original['producer']['skill_version']
            or harness != original['producer']['harness']):
        raise ValueError('promotion profile or producer differs from the compact preparation')
    inputs = normalize_inputs(current_inputs)
    inputs.setdefault('logical_scope_identity', prepared['logical_scope']['identity'])
    if inputs != original['review_inputs']:
        raise ValueError('promotion inputs differ from pinned source')
    with run_locks([stage]):
        if _read_prepared(stage) != prepared:
            raise ValueError('compact source changed while obtaining the promotion lock')
        published_hash = _digest(read_compact(target)['manifest']) if target.exists() else None
        request = {'scope': original['scope'], 'inputs': inputs,
            'logical_scope_input': original['logical_scope_input'],
            'repository_identity': original['repository_identity'], 'archive_root': original['archive_root'],
            'repo': str(repo), 'reason': reason, 'profile_input': profile_input,
            'skill_version': skill_version, 'harness': harness, 'controller': controller,
            'source_manifest_sha256': published_hash}
        intent_path = safe_path(stage / 'promotion.json')
        if intent_path.exists():
            intent = validate_intent(read_json(intent_path))
            if intent['operation_id'] != operation_id or intent['request'] != request:
                raise ValueError('compact source already has a different promotion intent')
        else:
            created = datetime.now(timezone.utc).isoformat()
            run_id = secrets.token_hex(10)
            run = target.parent / layout.run_name(original['scope'], created, run_id, original['logical_scope_input'])
            intent = {'schema_version': 1, 'operation_id': operation_id,
                'source_review_id': prepared['review_id'], 'source_reservation': str(stage),
                'source_sha256': _digest(prepared), 'request': request,
                'successor': {'created_at': created, 'run_id': run_id, 'owner_id': secrets.token_hex(16),
                              'reservation_id': secrets.token_hex(16), 'run_dir': str(run)}}
            intent['intent_sha256'] = _digest(intent)
            validate_intent(intent)
            atomic_write(intent_path, archive_bytes(intent))
        run = prepare_full(repo, original['scope'], skill_version, harness, original['archive_root'],
            profile_input=profile_input, controller=controller, current_inputs=inputs,
            logical_scope_input=original['logical_scope_input'], _compact_reservation=intent,
            _harness_identity={key: original['producer'][key] for key in
                               ('harness_id', 'harness_catalog_version', 'harness_source', 'harness_diagnostics')})
        return {'mode': 'full', 'run_dir': str(run), 'source_review_id': prepared['review_id'],
                'operation_id': operation_id, 'intent_path': str(intent_path)}
