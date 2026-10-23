"""Build validated review preparation candidates inside an owned evidence session."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

from ccr.archive.integrity import verify_files
from ccr.archive.reader import load_run
from ccr.contracts import references as review_references, reference_index as review_reference_index
from ccr.execution import workspaces as workspace_ops
from ccr.execution.candidates import write_new_json
from ccr.execution.workspace_manifest import owned_session as _owned_session
from ccr.shared.encoding import compact_bytes as _json_bytes
from ccr.workflow.builders import (
    _issues_message, build_assignment_event, build_context, build_model_usage_update,
    build_profile_selection,
)

REFERENCE_INDEX = 'evidence/reference-index.json'
MAX_INPUT_BYTES = 131072
SHA256 = re.compile(r'[0-9a-f]{64}')
_write_new_json = write_new_json

def _read_input(path):
    path = Path(path)
    if path.stat().st_size > MAX_INPUT_BYTES:
        raise ValueError('setup input exceeds the bounded size')
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
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

def _validate_session_reference_index(session_dir, descriptor, captured_inputs):
    if (not isinstance(descriptor, dict) or set(descriptor) != {'reference', 'sha256'}
            or descriptor.get('reference') != REFERENCE_INDEX
            or not isinstance(descriptor.get('sha256'), str)
            or SHA256.fullmatch(descriptor['sha256']) is None):
        raise ValueError('reference_index must identify evidence/reference-index.json and its digest')
    index_path = _session_evidence_file(session_dir, REFERENCE_INDEX)
    index_bytes = index_path.read_bytes()
    if hashlib.sha256(index_bytes).hexdigest() != descriptor['sha256']:
        raise ValueError('session reference index bytes differ from their supplied digest')
    try:
        index = json.loads(index_bytes.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError('session reference index is not valid UTF-8 JSON') from exc
    sources = {REFERENCE_INDEX: index_bytes}
    if isinstance(index, dict):
        for row in index.get('aliases', {}).values() if isinstance(index.get('aliases'), dict) else []:
            if isinstance(row, dict) and isinstance(row.get('reference'), str):
                path = _session_evidence_file(session_dir, row['reference'])
                sources[row['reference']] = path.read_bytes()
        for row in index.get('inputs', []) if isinstance(index.get('inputs'), list) else []:
            if isinstance(row, dict) and isinstance(row.get('reference'), str):
                path = _session_evidence_file(session_dir, row['reference'])
                sources[row['reference']] = path.read_bytes()
    issues = review_reference_index.validate_reference_index(index, sources)
    if issues:
        raise ValueError('session reference index is invalid: ' + '; '.join(row['message'] for row in issues))
    if (not isinstance(captured_inputs, dict)
            or captured_inputs.get('sources', {}).get(REFERENCE_INDEX) != descriptor['sha256']):
        raise ValueError('session reference index digest is not in the captured review_inputs')
    return index

def run_command(command, input_path, output_path):
    payload = _read_input(input_path)
    session_dir, session_manifest_path, workspace_manifest = _owned_session(payload['session'])
    args = payload['arguments']
    if command == 'profile':
        result = build_profile_selection(args)
    elif command == 'event':
        if set(args) != {'event', 'assignment'}:
            raise ValueError('event arguments require exactly event and assignment')
        result = build_assignment_event(args['event'], args['assignment'])
    elif command == 'context':
        required = {'run_dir', 'execution_plan', 'executors', 'review_inputs', 'reference_index'}
        if set(args) != required:
            raise ValueError('context arguments require exactly run_dir, execution_plan, executors, review_inputs, reference_index')
        run, manifest, _ = load_run(args['run_dir'])
        verify_files(run, manifest)
        _validate_session_reference_index(session_dir, args['reference_index'], args['review_inputs'])
        result = build_context(
            manifest, execution_plan=args['execution_plan'], executors=args['executors'],
            review_inputs=args['review_inputs'], reference_index=args['reference_index'])
    else:
        raise ValueError('unsupported setup builder')
    path = write_new_json(session_dir, output_path, result)
    return {'status': 'written', 'output': str(path), 'session_id': workspace_manifest['session_id']}

_run_command = run_command
