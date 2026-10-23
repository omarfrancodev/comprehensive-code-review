"""Pure review setup builders."""
import copy
import hashlib
import json
import os
import re

from ccr.archive import layout as review_layout, trace as review_trace
from ccr.contracts import model_usage as review_model_usage, preflight as review_preflight
from ccr.contracts.reference_index import (
    reference_source_paths, validate_reference_index, validate_selection_reference,
)
from ccr.contracts.reference_types import INITIAL_PROFILE_HISTORY_REFERENCE
from ccr.shared.encoding import compact_bytes as _json_bytes
from ccr.shared.json_io import read_json
from ccr.workflow import inputs as input_ops
from ccr.workflow import profiles as review_profiles

REFERENCE_INDEX = 'evidence/reference-index.json'
SHA256 = re.compile(r'[0-9a-f]{64}')

def _issues_message(result):
    return '; '.join(issue['message'] for issue in result.get('issues', []))

def capture_input_sources(index_bytes: bytes,
                         sources: dict[str, bytes]) -> dict[str, str]:
    """Hash a validated reference index and its material inputs, excluding outputs."""
    if not isinstance(index_bytes, bytes):
        raise ValueError('reference index bytes must be supplied explicitly')
    try:
        index = json.loads(index_bytes.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError('reference index is not valid UTF-8 JSON') from exc
    if not isinstance(sources, dict):
        raise ValueError('selected source bytes must be an explicit map')
    selected = dict(sources)
    selected[REFERENCE_INDEX] = index_bytes
    issues = validate_reference_index(index, selected)
    if issues:
        raise ValueError('; '.join(issue['message'] + ': ' +
                                 (issue['reference'] or issue['field']) for issue in issues))
    try:
        paths = reference_source_paths(index)
    except (TypeError, ValueError) as exc:
        raise ValueError('reference index source selection is invalid: ' + str(exc)) from exc
    result = {REFERENCE_INDEX: hashlib.sha256(index_bytes).hexdigest()}
    for row in index['inputs']:
        reference = row['reference']
        path = reference.split('#', 1)[0]
        result[path] = hashlib.sha256(selected[path]).hexdigest()
    # Validate that alias targets belong to the selected, bounded byte map.
    missing = [path for path in paths if path not in selected]
    if missing:
        raise ValueError('selected reference source is missing: ' + ', '.join(missing))
    return result

def build_profile_selection(raw: dict) -> dict:
    """Return a canonical selection only when its source and authority are valid."""
    value = review_profiles.validate_selection(raw)
    issues = validate_selection_reference(value, None)
    if issues:
        raise ValueError('; '.join(issue['message'] for issue in issues))
    return value


def initial_selection(profile_input):
    """Normalize the exact initial profile decision for a newly prepared archive."""
    if profile_input is None:
        raise ValueError('profile selection is required before preparing a new archive')
    raw = read_json(profile_input) if isinstance(profile_input, (str, os.PathLike)) else copy.deepcopy(profile_input)
    if not isinstance(raw, dict):
        raise ValueError('profile selection must be a JSON object')
    if set(raw) != review_profiles.INPUT_FIELDS:
        raise ValueError('initial profile selection must contain exactly the required decision fields')
    try:
        value = review_profiles.validate_selection(
            {key: raw[key] for key in review_profiles.INPUT_FIELDS})
    except KeyError as exc:
        raise ValueError('profile selection is missing required field: ' + str(exc.args[0])) from exc
    if value['phase'] != 'prepare' or value['affected_assignments']:
        raise ValueError('initial profile selection must use prepare phase and have no affected assignments')
    reference_issues = validate_selection_reference(value, None)
    if reference_issues:
        raise ValueError('; '.join(issue['message'] for issue in reference_issues))
    value.update(id='S001', changed_from=None, event_id='E000002')
    value['reference'] = INITIAL_PROFILE_HISTORY_REFERENCE
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
        supplied = input_ops.capture_review_inputs(
            review_inputs, manifest.get('scope'), history[-1]['profile'],
            'context review_inputs',
            logical_scope_identity=(manifest.get('logical_scope') or {}).get('identity'))
        retained = input_ops.capture_review_inputs(
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
