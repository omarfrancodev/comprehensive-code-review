"""Build validated review preparation candidates inside an owned evidence session."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
import sys

from ccr.archive.integrity import verify_files
from ccr.archive.reader import load_run
from ccr.contracts import references as review_references, reference_index as review_reference_index
from ccr.contracts.model_usage import MAX_LEDGER_BYTES
from ccr.execution import workspaces as workspace_ops
from ccr.execution.candidates import write_new_json
from ccr.execution.workspace_manifest import owned_session as _owned_session
from ccr.shared.encoding import compact_bytes as _json_bytes
from ccr.shared.json_io import read_json
from ccr.workflow.builders import (
    _issues_message, build_assignment_event, build_context, build_model_usage_update, build_check_disclosure,
    build_profile_selection, build_review_inputs,
)

REFERENCE_INDEX = 'evidence/reference-index.json'
MAX_INPUT_BYTES = 131072
# The request embeds the entire ledger. ASCII-escaped JSON can use up to
# three times its validated UTF-8 size; retain the ordinary envelope allowance.
MAX_MODEL_USAGE_INPUT_BYTES = MAX_INPUT_BYTES + 3 * MAX_LEDGER_BYTES
MAX_SELECTED_SOURCE_COUNT = 64
MAX_SELECTED_SOURCE_BYTES = 64 * 1024 * 1024
SHA256 = re.compile(r'[0-9a-f]{64}')
_write_new_json = write_new_json

def _read_input(path, *, max_bytes=MAX_INPUT_BYTES):
    path = Path(path)
    if path.stat().st_size > max_bytes:
        raise ValueError('setup input exceeds the bounded size')
    try:
        value = read_json(path, max_bytes=max_bytes)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError('setup input is not readable UTF-8 JSON') from exc
    if not isinstance(value, dict) or set(value) != {'session', 'arguments'}:
        raise ValueError('setup input requires exactly {session, arguments}')
    if not isinstance(value['session'], str) or not value['session'].strip() or not isinstance(value['arguments'], dict):
        raise ValueError('setup input session and arguments have invalid types')
    return value

def _session_evidence_file(session_dir: Path, reference: str) -> Path:
    path, fragment = review_references.parse_reference(reference, field='session evidence')
    if fragment is not None or not path.startswith('evidence/'):
        raise ValueError('session evidence reference must be a local evidence file without a fragment')
    result = workspace_ops.no_links(session_dir / Path(*path.split('/')))
    if not result.is_file():
        raise ValueError('selected session evidence is missing: ' + path)
    return result

def _read_selected_session_sources(session_dir, index, index_bytes):
    paths = review_reference_index.reference_source_paths(index)
    if len(paths) + 1 > MAX_SELECTED_SOURCE_COUNT:
        raise ValueError('selected reference sources exceed the 64-file input limit')
    sources = {REFERENCE_INDEX: index_bytes}
    total = len(index_bytes)
    for reference in paths:
        path = _session_evidence_file(session_dir, reference)
        size = path.stat().st_size
        if size > MAX_SELECTED_SOURCE_BYTES - total:
            raise ValueError('selected reference sources exceed the 64 MiB input limit')
        data = path.read_bytes()
        if len(data) > MAX_SELECTED_SOURCE_BYTES - total:
            raise ValueError('selected reference sources exceed the 64 MiB input limit')
        sources[reference] = data
        total += len(data)
    return sources

def _validate_session_reference_index(session_dir, descriptor, captured_inputs, *,
                                       require_material=False):
    if (not isinstance(descriptor, dict) or set(descriptor) != {'reference', 'sha256'}
            or descriptor.get('reference') != REFERENCE_INDEX
            or not isinstance(descriptor.get('sha256'), str)
            or SHA256.fullmatch(descriptor['sha256']) is None):
        raise ValueError('reference_index must identify evidence/reference-index.json and its digest')
    index_path = _session_evidence_file(session_dir, REFERENCE_INDEX)
    if index_path.stat().st_size > MAX_INPUT_BYTES:
        raise ValueError('session reference index exceeds the bounded size')
    index_bytes = index_path.read_bytes()
    if hashlib.sha256(index_bytes).hexdigest() != descriptor['sha256']:
        raise ValueError('session reference index bytes differ from their supplied digest')
    try:
        index = json.loads(index_bytes.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError('session reference index is not valid UTF-8 JSON') from exc
    try:
        sources = _read_selected_session_sources(session_dir, index, index_bytes)
    except (TypeError, ValueError) as exc:
        raise ValueError('session reference index is invalid: ' + str(exc)) from exc
    issues = review_reference_index.validate_reference_index(index, sources)
    if issues:
        raise ValueError('session reference index is invalid: ' + '; '.join(row['message'] for row in issues))
    if (not isinstance(captured_inputs, dict)
            or not isinstance(captured_inputs.get('sources'), dict)
            or captured_inputs['sources'].get(REFERENCE_INDEX) != descriptor['sha256']):
        raise ValueError('session reference index digest is not in the captured review_inputs')
    if require_material:
        from ccr.contracts.material_inputs import validate_captured_material_sources
        issues = validate_captured_material_sources(captured_inputs, index, sources)
        if issues:
            raise ValueError('session material inputs are not fully captured: ' +
                             '; '.join(row['message'] for row in issues))
    return index

def run_command(command, input_path, output_path):
    input_limit = (MAX_SELECTED_SOURCE_BYTES if command in ('materials', 'reuse-context')
                   else MAX_MODEL_USAGE_INPUT_BYTES if command == 'model-usage'
                   else MAX_INPUT_BYTES)
    payload = _read_input(input_path, max_bytes=input_limit)
    session_dir, session_manifest_path, workspace_manifest = _owned_session(payload['session'])
    args = payload['arguments']
    if command == 'changes':
        from ccr.execution.change_scope import collect_effective_changes
        if set(args) != {'repo','scope','target_head'} or Path(args['repo']).resolve() != Path(workspace_manifest['repo']).resolve():
            raise ValueError('changes requires the owned repository, scope and target_head')
        result = collect_effective_changes(args['repo'],args['scope'],target_head=args['target_head'])
    elif command == 'materials':
        from ccr.workflow.reuse import build_material_map, validate_material_map
        if set(args) != {'materials','complete','diagnostics','reference_index'}:
            raise ValueError('invalid materials arguments')
        descriptor = args['reference_index']
        index = _validate_session_reference_index(session_dir,descriptor,
            {'sources':{REFERENCE_INDEX:descriptor.get('sha256') if isinstance(descriptor,dict) else None}})
        sources = _read_selected_session_sources(session_dir,index,
            _session_evidence_file(session_dir,REFERENCE_INDEX).read_bytes())
        result = build_material_map(args['materials'],complete=args['complete'],diagnostics=args['diagnostics'])
        validate_material_map(result,index,sources)
    elif command == 'reuse-context':
        from ccr.execution.claims import CLAIM_NAME, verify_claim
        from ccr.execution.change_scope import collect_context_files
        from ccr.workflow.reuse import build_review_context, MATERIALS, CHANGES, validate_reuse_evidence
        required = {'scope','logical_scope_identity','files','materials','complete','diagnostics'}
        if set(args) != required:
            raise ValueError('invalid reuse-context arguments')
        claim = read_json(workspace_ops.no_links(session_dir/CLAIM_NAME),max_bytes=MAX_INPUT_BYTES)
        if claim.get('status') != 'owned':
            raise ValueError('final reuse context requires a registered run')
        verify_claim(session_dir,claim['archive_path'])
        _,manifest,_ = load_run(claim['archive_path'])
        if manifest['scope'] != args['scope']:
            raise ValueError('reuse context scope differs from registered inputs')
        captured = manifest['review_inputs']
        sources = load_current_sources(payload['session'],captured)
        index = json.loads(sources[REFERENCE_INDEX])
        validate_reuse_evidence(args['scope'],index,sources)
        if sorted(args['materials'],key=lambda r:r['key']) != json.loads(sources[MATERIALS])['entries']:
            raise ValueError('reuse context cannot introduce new material inputs')
        files = collect_context_files(workspace_manifest['repo'],json.loads(sources[CHANGES])['comparison'],args['files'])
        if files != sorted(args['files'],key=lambda r:(r['side'],base64.b64decode(r['path_b64']))):
            raise ValueError('context hashes do not match pinned Git objects')
        if args['complete'] and not json.loads(sources[MATERIALS])['complete']:
            raise ValueError('incomplete material map cannot certify context')
        result = build_review_context(**args)
    elif command == 'check-disclosure':
        required = {'record', 'input_identity', 'execution_observations', 'sources'}
        if set(args) != required or not isinstance(args['sources'], dict) or len(args['sources']) > 64:
            raise ValueError('check-disclosure arguments require record, input_identity, execution_observations and selected sources')
        selected = {}
        for reference, row in args['sources'].items():
            if not isinstance(row, dict) or set(row) != {'reference', 'sha256'}:
                raise ValueError('check-disclosure source requires owned-session reference and SHA-256')
            raw = _session_evidence_file(session_dir, row['reference']).read_bytes()
            if len(raw) > 1024 * 1024 or hashlib.sha256(raw).hexdigest() != row['sha256']:
                raise ValueError('check-disclosure selected source differs from its SHA-256')
            selected[reference] = raw
        result = build_check_disclosure(args['record'], args['input_identity'], args['execution_observations'], selected)
    elif command == 'model-usage':
        required = {'context', 'ledger', 'metadata', 'actor', 'phase', 'activity',
                    'review_id', 'harness_id', 'assignment_id', 'check_id'}
        if set(args) != required:
            raise ValueError('model-usage arguments require exactly ' + ', '.join(sorted(required)))
        context, ledger = build_model_usage_update(**args)
        result = {'context': context, 'ledger': ledger}
    elif command == 'profile':
        result = build_profile_selection(args)
    elif command == 'event':
        if set(args) != {'event', 'assignment'}:
            raise ValueError('event arguments require exactly event and assignment')
        result = build_assignment_event(args['event'], args['assignment'])
    elif command == 'inputs':
        required = {'scope', 'reference_index', 'source_set_complete', 'identities'}
        if set(args) != required:
            raise ValueError('inputs arguments require exactly scope, reference_index, source_set_complete, identities')
        descriptor = args['reference_index']
        index = _validate_session_reference_index(
            session_dir, descriptor,
            {'sources': {REFERENCE_INDEX: descriptor.get('sha256')
                         if isinstance(descriptor, dict) else None}})
        selected_sources = _read_selected_session_sources(
            session_dir, index, _session_evidence_file(session_dir, REFERENCE_INDEX).read_bytes())
        if hashlib.sha256(selected_sources[REFERENCE_INDEX]).hexdigest() != descriptor['sha256']:
            raise ValueError('session reference index changed while inputs were being captured')
        result = build_review_inputs(
            args['scope'], selected_sources[REFERENCE_INDEX], selected_sources,
            source_set_complete=args['source_set_complete'], identities=args['identities'])
        from ccr.workflow.reuse import validate_reuse_evidence
        validate_reuse_evidence(args['scope'],index,selected_sources)
    elif command == 'context':
        required = {'run_dir', 'execution_plan', 'executors', 'review_inputs', 'reference_index'}
        if set(args) != required:
            raise ValueError('context arguments require exactly run_dir, execution_plan, executors, review_inputs, reference_index')
        run, manifest, _ = load_run(args['run_dir'])
        verify_files(run, manifest)
        _validate_session_reference_index(
            session_dir, args['reference_index'], args['review_inputs'],
            require_material=manifest.get('state') == 'prepared')
        result = build_context(
            manifest, execution_plan=args['execution_plan'], executors=args['executors'],
            review_inputs=args['review_inputs'], reference_index=args['reference_index'])
        from ccr.contracts.check_disclosure import input_identity_for
        identity = input_identity_for({'scope': manifest['scope']})
        baselines = {row.get('resource_baseline_sha256') for row in workspace_manifest['workspaces']
                     if row['path'] in {entry['workspace'] for entry in args['executors']}}
        baselines.discard(None)
        if len(baselines) == 1:
            identity['resource_manifest_sha256'] = next(iter(baselines))
        prior_identity = manifest.get('check_disclosure_input_identity')
        if prior_identity is not None and identity != prior_identity:
            raise ValueError('context cannot replace the initially pinned disclosure identity')
        result['check_disclosure_input_identity'] = identity
    else:
        raise ValueError('unsupported setup builder')
    path = write_new_json(session_dir, output_path, result)
    return {'status': 'written', 'output': str(path), 'session_id': workspace_manifest['session_id']}


def load_current_sources(session, current_inputs):
    """Read the captured final index only inside the verified caller session."""
    session_dir, _, _ = _owned_session(session)
    from ccr.workflow.inputs import normalize_inputs
    current_inputs = normalize_inputs(current_inputs)
    descriptor = dict(reference=REFERENCE_INDEX,sha256=current_inputs['sources'].get(REFERENCE_INDEX))
    index = _validate_session_reference_index(session_dir,descriptor,current_inputs,require_material=True)
    sources = _read_selected_session_sources(session_dir,index,
        _session_evidence_file(session_dir,REFERENCE_INDEX).read_bytes())
    if hashlib.sha256(sources[REFERENCE_INDEX]).hexdigest() != descriptor['sha256']:
        raise ValueError('current reference index changed during capture')
    return sources

_run_command = run_command
