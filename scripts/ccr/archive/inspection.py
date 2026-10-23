"""Verified, read-only inspection and continuation decisions for review archives."""
import copy
from datetime import datetime
import hashlib
import json
from pathlib import Path

from ccr.archive import trace as review_trace
from ccr.archive.integrity import verify_files as _verify_files
from ccr.archive.intent_contracts import normalize_transfer_history
from ccr.archive.reader import load_run as _load_run
from ccr.archive.restart_observations import (
    _diagnostic_recovery_route,
    _restart_recovery_source,
    resource_availability as _resource_availability,
)
from ccr.archive.restart_state import _active_restart_operation
from ccr.workflow import inputs as review_inputs
from ccr.workflow.inputs import candidate_inputs as _candidate_inputs, validate_current_inputs


def _action(name, reason):
    return {'action': name, 'reason': reason}

def _native_archive(manifest):
    return (isinstance(manifest, dict) and manifest.get('schema_version') == 8
            and manifest.get('layout_version') == 2)

def _decode_json_bytes(data):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate JSON key: ' + key)
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError('nonfinite JSON number: ' + value)

    return json.loads(data.decode('utf-8'), object_pairs_hook=unique,
                      parse_constant=invalid_constant)

def operational_summary(manifest: dict, events: list[dict], record: dict | None) -> dict:
    """Project verified closure facts without inferring links or publication from prose."""
    if not _native_archive(manifest):
        raise ValueError('operational summary requires native archive schema 8/layout 2')
    operation = manifest.get('operation')
    allowed_dispositions = {'open', 'paused', 'blocked', 'superseded', 'complete'}
    if (not isinstance(operation, dict)
            or not isinstance(operation.get('disposition'), str)
            or operation.get('disposition') not in allowed_dispositions):
        raise ValueError('operational summary requires a valid durable disposition')
    phase = operation.get('phase') or manifest.get('state')
    if not isinstance(phase, str) or not phase:
        raise ValueError('operational summary requires an observed phase')
    successor = operation.get('successor')
    if successor is not None and (not isinstance(successor, str) or not successor.strip()):
        raise ValueError('operational summary successor must be a durable path or null')
    cleanup = manifest.get('cleanup')
    if not isinstance(cleanup, str) or cleanup not in {'pending', 'complete', 'not_needed'}:
        raise ValueError('operational summary requires observed cleanup status')
    if not isinstance(events, list):
        raise ValueError('operational summary events must be a verified array')

    publication = None
    for event in events:
        if not isinstance(event, dict) or event.get('kind') != 'authorized-publication':
            continue
        if isinstance(event.get('status'), str) and event.get('status') in {'completed', 'passed', 'failed'}:
            publication = event
    if publication is not None:
        event_status = publication['status']
        publication_status = 'published' if event_status in {'completed', 'passed'} else 'failed'
        publication_summary = {
            'status': publication_status,
            'source': publication.get('event_id') if isinstance(publication.get('event_id'), str) else None,
            'occurred_at': publication.get('occurred_at'),
            'reason': publication.get('summary') if isinstance(publication.get('summary'), str) else None,
        }
    else:
        resources = record.get('resources') if isinstance(record, dict) else None
        snapshot_status = resources.get('publication') if isinstance(resources, dict) else None
        if isinstance(snapshot_status, str) and snapshot_status in {
                'not_requested', 'draft', 'published', 'failed'}:
            publication_summary = {'status': snapshot_status, 'source': 'review.json',
                                   'occurred_at': None, 'reason': None}
        else:
            publication_summary = {'status': 'unknown', 'source': None,
                                   'occurred_at': None, 'reason': None}
    return {
        'disposition': operation['disposition'],
        'phase': phase,
        'successor': successor,
        'cleanup': cleanup,
        'publication': publication_summary,
    }

def continuation_decision(manifest: dict, *, input_appraisal: dict,
                          pending_operation: dict | None,
                          candidate_issues: list[dict]) -> dict:
    """Classify the safest next path; this function never performs that action."""
    if not _native_archive(manifest):
        raise ValueError('continuation decision requires native archive schema 8/layout 2')
    operation = manifest.get('operation')
    if (not isinstance(operation, dict) or not isinstance(operation.get('disposition'), str)
            or operation.get('disposition') not in {
            'open', 'paused', 'blocked', 'superseded', 'complete'}):
        raise ValueError('continuation decision requires a valid durable disposition')
    if (not isinstance(input_appraisal, dict)
            or not isinstance(input_appraisal.get('applicability'), str)
            or input_appraisal.get('applicability') not in {'applicable', 'changed', 'unknown'}):
        raise ValueError('continuation decision requires a bounded input appraisal')
    if candidate_issues is None or not isinstance(candidate_issues, list) \
            or any(not isinstance(issue, dict) for issue in candidate_issues):
        raise ValueError('candidate_issues must be an array of diagnostics')
    if pending_operation is not None and (
            not isinstance(pending_operation, dict)
            or not isinstance(pending_operation.get('kind'), str)
            or type(pending_operation.get('can_complete')) is not bool):
        raise ValueError('pending_operation requires a kind and explicit can_complete boolean')

    def decision(action, reason, requires_authority=False, new_work=False):
        return {'action': action, 'reason': reason,
                'requires_authority': requires_authority, 'new_work': new_work}

    disposition = operation['disposition']
    if disposition in {'complete', 'superseded'} or manifest.get('state') == 'complete':
        return decision('show_history', 'This run is immutable history; inspect it or start a linked review.')
    if pending_operation is not None:
        if pending_operation['can_complete']:
            return decision('recover', 'Complete only the exact pending helper-owned operation.',
                            new_work=False)
        return decision('preserve', 'The pending operation cannot be verified or completed; preserve both records.')
    if manifest.get('restart_abandonment') is not None:
        return decision('show_history', 'This recorded restart refusal is terminal; preserve its source and receipt.')
    if manifest.get('state') in {'retaining', 'closing'}:
        return decision('preserve', 'Retention or closure needs its exact original input or cleanup observation.')
    if input_appraisal['applicability'] != 'applicable':
        return decision('restart', 'Current inputs changed or remain unknown; preserve the source and plan a linked run.',
                        requires_authority=True, new_work=True)

    if candidate_issues:
        candidate_only = all(isinstance(issue.get('field'), str)
                             and issue['field'].startswith('candidate.')
                             for issue in candidate_issues)
        if (candidate_only and manifest.get('retained') is not True
                and disposition == 'open' and manifest.get('state') in {'prepared', 'processing'}):
            return decision('rebuild_candidate',
                'Regenerate the unretained candidate from the same captured inputs, then rerun preflight.',
                new_work=False)
        if not candidate_only:
            return decision('restart', 'A captured identity or non-candidate gate needs a linked review plan.',
                            requires_authority=True, new_work=True)
        return decision('preserve', 'The candidate is retained or its lifecycle state cannot be rewritten.')

    if disposition in {'paused', 'blocked'}:
        return decision('resume', 'Resume only after the existing authority and input gates pass.',
                        requires_authority=True, new_work=True)
    if disposition == 'open' and manifest.get('state') in {'prepared', 'processing'}:
        return decision('resume', 'Continue only the existing incomplete gates after preflight.',
                        requires_authority=False, new_work=True)
    return decision('preserve', 'The observed state does not authorize a continuation path.')

def classify_candidate(manifest, retained_inputs, current_inputs):
    """Compare a pinned candidate to caller-supplied current identities without IO."""
    if not isinstance(manifest, dict):
        raise ValueError('candidate manifest must be an object')
    return review_inputs.compare_inputs(retained_inputs, current_inputs)

def _recover_source_action(source):
    return dict(_action('recover_source', 'Recover the exact restart through its owning source run.'),
                run_dir=source['run_dir'], operation_id=source['operation_id'])

def _abandoned_source_action(manifest):
    return dict(_action('inspect_source', 'This explicitly abandoned successor is terminal history; inspect its source.'),
                run_dir=manifest['restart_abandonment']['source_run'])

def _superseded_actions(resources=()):
    actions = [_action('inspect_successor', 'The source run records a successor; inspect that exact run.')]
    if any(row['claim_status'] == 'owned' and row['present'] for row in resources):
        actions.append(_action('cleanup', 'Clean the remaining source-owned sessions using this source --run-dir.'))
    return actions

def inspect_run(run_dir, *, current_inputs=None):
    """Inspect one explicitly selected run without repairing or changing any file."""
    run_path = Path(run_dir).absolute()
    base = {'schema_version': 1, 'run_dir': str(run_path), 'run_id': None, 'review_id': None,
            'integrity': {'status': 'invalid', 'errors': []}, 'phase': None,
            'operation': {'disposition': 'unknown'}, 'known_sources': [], 'missing_sources': [],
            'resources': [], 'pending_transaction': [], 'freshness': {'status': 'unknown', 'reasons': []},
            'actions': [_action('preserve', 'Run identity has not been verified.')], 'activity': 'unknown'}
    try:
        run, manifest, marker = _load_run(run_path)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        base['integrity']['errors'] = [str(exc)[:1000]]
        if 'unsupported_layout' in str(exc):
            base['integrity']['status'] = 'unsupported_layout'
            base['actions'] = [_action('port_history', 'Old archives are read-only here; port a verified report for consultation.'),
                               _action('new_review', 'Start a new review using the current archive layout.'),
                               _action('preserve', 'Keep the original archive unchanged.')]
        return base

    operation = copy.deepcopy(manifest.get('operation') or {
        'disposition': 'complete' if manifest.get('state') == 'complete' else 'open',
        'phase': None, 'reason': None, 'source': None, 'successor': None})
    pending = []
    errors = []
    recovery_source = None
    restart_exit = None
    try:
        active_restart = _active_restart_operation(run, manifest, include_abandoned=True)
        recovery_source = _restart_recovery_source(run, manifest)
        if recovery_source is not None:
            pending.append({'kind': 'restart_source', 'status': 'pending',
                            'run_dir': recovery_source['run_dir'], 'operation_id': recovery_source['operation_id']})
        if active_restart:
            pending.append({'kind': 'restart', 'status': 'pending',
                            'operation_id': active_restart['operation_id'],
                            'successor_run_dir': active_restart['successor_run_dir'],
                            'intent_path': active_restart['intent_path']})
        restart_exit = _diagnostic_recovery_route(run, manifest,
            active_restart=active_restart, recovery_source=recovery_source)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        errors.append(str(exc)[:1000])
    if manifest.get('pending_trace') is not None:
        pending.append({'kind': 'trace_append', 'status': 'pending'})
    if manifest.get('checkpoint_transaction') is not None:
        pending.append({'kind': 'checkpoint', 'status':
                        'superseded' if operation.get('disposition') == 'superseded' else 'pending'})
    try:
        transfers = normalize_transfer_history(manifest)
        for transfer in transfers:
            if transfer.get('status') != 'complete':
                pending.append({'kind': 'resource_transfer', 'status': 'pending',
                                'transfer_id': transfer.get('transfer_id')})
    except (ValueError, TypeError, KeyError) as exc:
        errors.append(str(exc)[:1000])
    cleanup = manifest.get('resource_cleanup')
    if isinstance(cleanup, dict) and cleanup.get('status') == 'pending':
        pending.append({'kind': 'resource_cleanup', 'status': 'pending',
                        'operation_id': cleanup.get('operation_id')})
    if manifest.get('state') == 'retaining':
        pending.append({'kind': 'retention', 'status': 'pending'})
    if manifest.get('state') == 'closing':
        pending.append({'kind': 'closure', 'status': 'pending'})

    try:
        if not manifest.get('pending_trace'):
            _verify_files(run, manifest, allow_checkpoint_transaction=True,
                                    allow_resource_transfer=True)
        resources = _resource_availability(run, manifest,
            verify_owned=not manifest.get('pending_trace')
                         and not any(row['status'] == 'pending' for row in pending))
    except (OSError, ValueError, TypeError, KeyError) as exc:
        errors.append(str(exc)[:1000])
        resources = []

    known = sorted(set(manifest.get('hashes', {})) | set(manifest.get('pending_hashes', {})))
    missing = [name for name in known if not (run / name).is_file()]
    freshness = {'status': 'unknown', 'reasons': [], 'differences': []}
    if current_inputs is not None:
        try:
            normalized = validate_current_inputs(current_inputs, manifest, require_same_scope=False)
            appraisal = classify_candidate(manifest, _candidate_inputs(manifest), normalized)
            status = {'applicable': 'verified', 'changed': 'changed', 'unknown': 'unknown'}[
                appraisal['applicability']]
            freshness = {'status': status,
                         'reasons': [row['reason'] for row in appraisal['differences']],
                         'differences': appraisal['differences']}
        except (OSError, ValueError, TypeError, KeyError) as exc:
            reason = str(exc)[:1000]
            freshness = {'status': 'unknown', 'reasons': [reason],
                         'differences': [{'field': 'current_inputs', 'status': 'unknown', 'reason': reason}]}

    disposition = operation.get('disposition')
    actions = []
    if errors:
        integrity_status = 'invalid'
        actions = [_action('preserve', 'Integrity/source verification failed; do not adopt or rewrite this run.')]
    elif restart_exit is not None:
        integrity_status = 'recoverable'
        actions = restart_exit['actions']
    elif recovery_source is not None:
        integrity_status = 'recoverable'
        actions = [_recover_source_action(recovery_source)]
    elif any(row['status'] == 'pending' for row in pending):
        integrity_status = 'recoverable'
        actions = (restart_exit['actions'] if restart_exit is not None else
                   [_action('recover', 'A helper-owned transaction is pending; recover its exact recorded inputs first.')])
    else:
        integrity_status = 'verified'
        if manifest.get('restart_abandonment') is not None:
            actions = [_abandoned_source_action(manifest)]
        elif disposition == 'paused':
            actions = [_action('resume', 'Continuing a user-paused run requires explicit continuation authority.'),
                       _action('restart', 'A fresh linked run is available if inputs or scope changed.')]
        elif disposition == 'blocked':
            actions = [_action('recover', 'Inspect the recorded blocker and recover only verified helper-owned state.'),
                       _action('restart', 'Start a new linked run if the original sources cannot be verified.')]
        elif disposition == 'superseded':
            actions = _superseded_actions(resources)
        elif disposition == 'complete' or manifest.get('state') == 'complete':
            actions = [_action('show', 'The completed report is immutable and may be shown as recorded.'),
                       _action('restart', 'A repeat creates a new linked review ID.')]
        else:
            actions = [_action('continue', 'The run is open; verify current inputs and operation phase before work.'),
                       _action('recover', 'Check for helper-owned state that can be completed from preserved bytes.'),
                       _action('restart', 'A fresh linked run is available if the scope changed.')]
        if any(row['availability'] == 'missing_unknown' for row in resources) and disposition not in {'superseded', 'complete'}:
            actions = [_action('restart', 'A claimed session is missing_unknown; preserve its claim and restart without transferring it.')]

    activity = ('completed' if integrity_status == 'verified'
                and (disposition == 'complete' or manifest.get('state') == 'complete') else 'unknown')
    run_id = manifest.get('run_id')
    result = {'schema_version': 1, 'run_dir': str(run), 'run_id': run_id,
              'review_id': 'CR-' + run_id if isinstance(run_id, str) else None,
              'integrity': {'status': integrity_status, 'errors': errors},
              'phase': operation.get('phase') or manifest.get('state'), 'operation': operation,
              'known_sources': known, 'missing_sources': missing, 'resources': resources,
              'pending_transaction': pending, 'freshness': freshness, 'actions': actions,
              'activity': activity,
              **({'recovery': restart_exit['recovery']} if restart_exit is not None and not errors else {})}
    if integrity_status == 'verified' and _native_archive(manifest) and not pending:
        try:
            hashes = manifest.get('hashes', {})
            trace_name = review_trace.NAME
            trace_data = (run / trace_name).read_bytes()
            if hashlib.sha256(trace_data).hexdigest() != hashes.get(trace_name):
                raise ValueError('trace bytes changed after integrity verification')
            review_trace.verify(trace_data, manifest.get('trace'), manifest['run_id'])
            verified_events = [json.loads(line) for line in trace_data.splitlines()]
            retained_record = None
            if 'review.json' in hashes:
                record_data = (run / 'review.json').read_bytes()
                if hashlib.sha256(record_data).hexdigest() != hashes['review.json']:
                    raise ValueError('retained record bytes changed after integrity verification')
                retained_record = _decode_json_bytes(record_data)
            result['operational_summary'] = operational_summary(
                manifest, verified_events, retained_record)
        except (OSError, ValueError, TypeError, KeyError, UnicodeDecodeError,
                json.JSONDecodeError) as exc:
            errors.append('operational summary unavailable: ' + str(exc)[:500])
            result['integrity'] = {'status': 'invalid', 'errors': errors}
            result['activity'] = 'unknown'
            result['actions'] = [_action('preserve',
                'Operational source verification failed; do not continue or rewrite this run.')]
    return result
