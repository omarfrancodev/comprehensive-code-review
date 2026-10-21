#!/usr/bin/env python3
"""Build validated review preparation candidates inside an owned evidence session."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import uuid

import review_artifacts
import review_layout
import review_model_usage
import review_preflight
import review_profiles
import review_references
import review_trace
import review_workspace

from ccr.execution.workspace_manifest import owned_session as _owned_session

REFERENCE_INDEX = 'evidence/reference-index.json'
MAX_INPUT_BYTES = 131072
SHA256 = re.compile(r'[0-9a-f]{64}')

def _json_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')

def _issues_message(result):
    return '; '.join(issue['message'] for issue in result.get('issues', []))

def build_profile_selection(raw: dict) -> dict:
    """Return a canonical selection only when its source and authority are valid."""
    value = review_profiles.validate_selection(raw)
    issues = review_references.validate_selection_reference(value, None)
    if issues:
        raise ValueError('; '.join(issue['message'] for issue in issues))
    return value

def build_context(manifest: dict, *, execution_plan: list[dict],
                  executors: list[dict], review_inputs: dict,
                  reference_index: dict) -> dict:
    """Build registration context from exact native closure identities."""
    if (not isinstance(manifest, dict)
            or manifest.get('schema_version') != review_layout.ARCHIVE_SCHEMA_VERSION
            or manifest.get('layout_version') != review_layout.LAYOUT_VERSION):
        raise ValueError('context builder requires a native archive schema 8/layout 2 manifest')
    history = manifest.get('profile_history')
    history_errors = review_profiles.validate_history(history)
    if history_errors:
        raise ValueError('manifest profile history is invalid: ' + '; '.join(history_errors))
    captured = manifest.get('review_inputs')
    if not isinstance(captured, dict) or not isinstance(review_inputs, dict):
        raise ValueError('context requires captured review_inputs from the native manifest')
    try:
        supplied = review_artifacts._capture_review_inputs(
            review_inputs, manifest.get('scope'), history[-1]['profile'],
            'context review_inputs',
            logical_scope_identity=(manifest.get('logical_scope') or {}).get('identity'))
        retained = review_artifacts._capture_review_inputs(
            captured, manifest.get('scope'), history[-1]['profile'],
            'manifest review_inputs',
            logical_scope_identity=(manifest.get('logical_scope') or {}).get('identity'))
    except (TypeError, ValueError, KeyError) as exc:
        raise ValueError('captured review_inputs are invalid: ' + str(exc)) from exc
    if supplied != retained or supplied != captured:
        raise ValueError('context review_inputs must preserve the exact captured identities')
    logical = manifest.get('logical_scope')
    identity = logical.get('identity') if isinstance(logical, dict) else None
    if not isinstance(identity, str) or captured.get('logical_scope_identity') != identity:
        raise ValueError('captured review_inputs must preserve logical_scope_identity')
    if not isinstance(execution_plan, list):
        raise ValueError('execution_plan must be an explicit assignment list')
    if not isinstance(executors, list):
        raise ValueError('executors must be an explicit array')
    registry = manifest.get('assignment_registry')
    if not isinstance(registry, list):
        raise ValueError('native manifest assignment_registry must be an array')
    try:
        merged_plan = review_profiles.merge_assignment_registry(
            registry, execution_plan, history,
            manifest.get('trace_events', []))
    except (TypeError, ValueError, KeyError) as exc:
        raise ValueError('execution plan differs from the captured assignment contract: ' + str(exc)) from exc
    if (not isinstance(reference_index, dict)
            or set(reference_index) != {'reference', 'sha256'}
            or reference_index.get('reference') != REFERENCE_INDEX
            or not isinstance(reference_index.get('sha256'), str)
            or SHA256.fullmatch(reference_index['sha256']) is None):
        raise ValueError('reference_index must identify the captured evidence/reference-index.json digest')
    if captured.get('sources', {}).get(REFERENCE_INDEX) != reference_index['sha256']:
        raise ValueError('reference_index digest differs from the initially captured inputs')

    result = {
        'profile': history[-1]['profile'],
        'selection_source': history[0]['selection_source'],
        'profile_history': copy.deepcopy(history),
        'profile_reference': history[-1]['reference'],
        'execution_plan': merged_plan,
        'executors': copy.deepcopy(executors),
        'review_inputs': copy.deepcopy(captured),
        'reference_index': REFERENCE_INDEX,
    }
    preflight = review_preflight.validate_preflight(
        phase='register', manifest=manifest, logical_scope=logical,
        selection=history[-1], context=result, record=None,
        sources={'evidence/context.json': _json_bytes(result)})
    if not preflight['ready']:
        raise ValueError('context does not satisfy registration preflight: ' + _issues_message(preflight))
    return result

def build_model_usage_update(context: dict, ledger: dict | None, metadata: dict, *,
                             actor: dict, phase: str, activity: str,
                             review_id: str, harness_id: str | None,
                             assignment_id: str | None = None,
                             check_id: str | None = None) -> tuple[dict, dict | None]:
    """Add already-observed model metadata without making its absence a review gate."""
    if not isinstance(context, dict):
        raise ValueError('model usage update requires an execution context object')
    updated_context = copy.deepcopy(context)
    expected_reference = 'evidence/model-usage.json'
    if context.get('model_usage_reference') not in (None, expected_reference):
        error = 'execution context has an unsupported model usage reference'
        observation = None
    elif context.get('model_usage_reference') == expected_reference and ledger is None:
        error = 'existing model usage reference requires its current ledger'
        observation = None
    else:
        try:
            observation = review_model_usage.observation_from_metadata(
                metadata, actor=actor, phase=phase, activity=activity,
                assignment_id=assignment_id, check_id=check_id)
            updated_ledger = review_model_usage.append_model_observation(
                ledger, observation, review_id=review_id, harness_id=harness_id)
        except (TypeError, ValueError) as exc:
            error = str(exc)
        else:
            updated_context['model_usage_reference'] = expected_reference
            return updated_context, updated_ledger

    diagnostics = context.get('model_usage_diagnostics', [])
    if not isinstance(diagnostics, list):
        diagnostics = []
    diagnostics = [item[:500] for item in diagnostics
                   if isinstance(item, str) and item.strip()][:32]
    message = ('model usage capture incomplete: ' + error).replace('\r', ' ').replace('\n', ' ')[:500]
    if len(diagnostics) < 32:
        if message not in diagnostics:
            diagnostics.append(message)
    elif 'additional model usage capture failures were omitted' not in diagnostics[-1].lower():
        diagnostics[-1] = 'Additional model usage capture failures were omitted due to the diagnostic limit.'
    if diagnostics:
        updated_context['model_usage_diagnostics'] = diagnostics
    return updated_context, copy.deepcopy(ledger)

def build_assignment_event(raw: dict, assignment: dict) -> dict:
    """Validate an observed work milestone without inventing actor or timing facts."""
    if not isinstance(raw, dict) or 'actor' not in raw:
        raise ValueError('assignment event requires the observed actor')
    if (not isinstance(assignment, dict)
            or set(assignment) != review_profiles.ASSIGNMENT_FIELDS
            or assignment.get('required') is not True
            or assignment.get('superseded_by') is not None):
        raise ValueError('assignment event requires one active required registered assignment')
    event = review_trace.event_input(raw)
    if event['kind'] not in {'agent', 'discovery', 'grouped-verification'}:
        raise ValueError('assignment event kind must identify assigned work')
    if event['status'] not in {'started', 'completed', 'passed', 'failed', 'blocked', 'skipped'}:
        raise ValueError('assignment event status must identify an observed work milestone')
    issues = review_preflight.validate_assignment_event(event, [assignment])
    if issues:
        raise ValueError('; '.join(issue['message'] for issue in issues))
    return event

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
    result = review_workspace.no_links(session_dir / Path(*path.split('/')))
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
    issues = review_references.validate_reference_index(index, sources)
    if issues:
        raise ValueError('session reference index is invalid: ' + '; '.join(row['message'] for row in issues))
    if (not isinstance(captured_inputs, dict)
            or captured_inputs.get('sources', {}).get(REFERENCE_INDEX) != descriptor['sha256']):
        raise ValueError('session reference index digest is not in the captured review_inputs')
    return index

def _write_new_json(session_dir: Path, output: str, value: dict) -> Path:
    evidence_dir = review_workspace.no_links(session_dir / 'evidence')
    target = review_workspace.no_links(Path(output).absolute())
    if not target.is_relative_to(evidence_dir) or target.parent != evidence_dir:
        raise ValueError('setup output must be a direct child of the owned session evidence directory')
    if not target.name.endswith('.json'):
        raise ValueError('setup output must use a .json filename')
    if not evidence_dir.exists():
        evidence_dir.mkdir()
    if target.exists() or target.is_symlink():
        raise FileExistsError('setup output already exists; choose a new evidence filename')
    payload = _json_bytes(value) + b'\n'
    temporary = evidence_dir / ('.review-setup-' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('xb') as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        review_workspace.no_links(evidence_dir)
        review_workspace.no_links(target)
        if target.exists() or target.is_symlink():
            raise FileExistsError('setup output already exists; choose a new evidence filename')
        os.rename(temporary, target)
        if target.read_bytes() != payload:
            target.unlink(missing_ok=True)
            raise OSError('setup output verification failed')
        return target
    finally:
        temporary.unlink(missing_ok=True)

def _run_command(command, input_path, output_path):
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
        run, manifest, _ = review_artifacts._load_run(args['run_dir'])
        review_artifacts._verify_files(run, manifest)
        _validate_session_reference_index(session_dir, args['reference_index'], args['review_inputs'])
        result = build_context(
            manifest, execution_plan=args['execution_plan'], executors=args['executors'],
            review_inputs=args['review_inputs'], reference_index=args['reference_index'])
    else:
        raise ValueError('unsupported setup builder')
    path = _write_new_json(session_dir, output_path, result)
    return {'status': 'written', 'output': str(path), 'session_id': workspace_manifest['session_id']}

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('profile', 'context', 'event'):
        item = sub.add_parser(command)
        item.add_argument('--input', required=True)
        item.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    try:
        result = _run_command(args.command, args.input, args.output)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 0
    except (OSError, ValueError, TypeError, KeyError, review_workspace.ReviewError) as exc:
        print(json.dumps({'status': 'error', 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1

if __name__ == '__main__':
    sys.exit(main())
