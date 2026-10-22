"""Durable restart, replay, cancellation and recovery service."""
import copy
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import uuid

from ccr.archive import layout as review_layout, trace as review_trace
from ccr.archive.checkpoints import _checkpoint_commit, _checkpoint_input_files
from ccr.archive.coordination import _restart_lock
from ccr.archive.evidence import _capture_review_inputs, _input_object
from ccr.archive.integrity import _trace_recovery_plan, verify_files as _verify_files
from ccr.archive.intent_contracts import (
    _validate_restart_abandonment_value, normalize_transfer_history,
)
from ccr.archive.lifecycle import (
    _controller, _initial_selection, _recovery_event as recovery_event,
    _repository_group, _resource_availability, _takeover_controller as takeover_controller,
    prepare, register,
)
from ccr.archive.reader import MARKER, load_run as _load_run
from ccr.archive.resources import recover_resource_cleanup, transfer_resources
from ccr.archive.retention import _temporary_manifests, _temporary_paths
from ccr.archive import restart_contract as review_restart
from ccr.archive.restart_contract import _bounded_text, validate_restart_intent
from ccr.archive.restart_state import (
    _active_restart_operation, _active_restart_paths, _assert_not_restart_abandoned,
    _existing_restart_intent_path, _read_restart_intent, _restart_abandonment_path,
    _restart_completion_path, _restart_intent_path, _restart_local_dir,
    _restart_source_identity, _validate_restart_abandonment,
    _validate_restart_completion,
)
from ccr.archive.transactions import _append_trace, _milestone, _recover_trace, save_manifest
from ccr.contracts.scope import require_scope as _scope
from ccr.execution import claims as resource_claims
from ccr.execution import harness as review_harness
from ccr.execution.locks import CoordinationError, LockConflictError, run_locks
from ccr.shared.encoding import archive_bytes as _json_bytes
from ccr.shared.git import git as _git, repository_identity
from ccr.shared.installation import resource_path, skill_root
from ccr.shared.json_io import atomic_write, read_json
from ccr.shared.paths import safe_path
from ccr.workflow import inputs as review_inputs
from ccr.workflow import profiles as review_profiles

ARCHIVE_SCHEMA_VERSION = review_layout.ARCHIVE_SCHEMA_VERSION
PREFIX = 'Restart cancellation refusal: '

class _RestartCancellationUnavailable(ValueError):
    """Verified state which the conservative cancellation protocol cannot unwind."""

    def __init__(self, message, *, phase='successor_work'):
        super().__init__(message)
        self.phase = phase

    def diagnostic(self):
        return {'decision': 'refused', 'phase': self.phase, 'reason': str(self),
                'transaction_pending': True, 'resource_obligations_preserved': True}

def _digest(data):
    return hashlib.sha256(data).hexdigest()

def _write_restart_intent(path, intent, source_run, source_manifest):
    errors = review_restart.validate_restart_intent(intent)
    if errors:
        raise ValueError('; '.join(errors))
    if path.exists():
        existing = _read_restart_intent(path, source_run, source_manifest)
        if existing != intent:
            raise ValueError('restart intent already exists with different reserved bytes')
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, _json_bytes(intent))

def _restart_recovery_source(run, manifest):
    """Identify the exact source lock that owns a successor's pending restart."""
    operation = manifest.get('restart_operation')
    if not isinstance(operation, dict) or manifest.get('state') == 'complete':
        return None
    try:
        source, source_manifest, _ = _load_run(operation['source_run'])
        _verify_files(source, source_manifest, allow_checkpoint_transaction=True,
                      allow_resource_transfer=True, allow_pending_trace=True)
        active = _active_restart_operation(source, source_manifest, include_abandoned=True)
    except (OSError, ValueError, TypeError, KeyError):
        # Historical availability does not establish this successor's integrity.
        # Its own pending transfers, trace and hashes remain subject to local gates.
        return None
    if active is None or active['operation_id'] != operation['operation_id']:
        return None
    if (active['successor_run_dir'] != str(run)
            or active['intent_sha256'] != operation['intent_sha256']):
        raise ValueError('successor restart identity differs from its active source operation')
    result = {'run_dir': str(source), 'operation_id': active['operation_id']}
    resource_exit = _restart_resource_exit(source, source_manifest, active)
    if resource_exit is not None:
        result['resource_exit'] = resource_exit
    return result

def _write_active_restart(source_run, source_manifest, intent_path, intent, *, status='pending'):
    active_path, owner_path = _active_restart_paths(source_run, source_manifest)
    descriptor = {'schema_version': 1, 'source_run': str(safe_path(source_run)),
                  'source_owner_id': source_manifest['owner_id'], 'operation_id': intent['operation_id'],
                  'intent_path': str(intent_path), 'intent_sha256': intent['intent_sha256'],
                  'successor_run_dir': intent['successor']['run_dir'], 'status': status,
                  'intent': copy.deepcopy(intent)}
    previous = None
    previous_digest = None
    if active_path.exists():
        previous = read_json(active_path)
        previous_digest = _digest(_json_bytes(previous))
    transition = {'schema_version': 1, 'source_run': str(safe_path(source_run)),
                  'source_owner_id': source_manifest['owner_id'],
                  'active_sha256': _digest(_json_bytes(descriptor)),
                  'previous_active_sha256': previous_digest,
                  'active_descriptor': descriptor, 'previous_descriptor': previous}
    owner_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(owner_path, _json_bytes(transition))
    atomic_write(active_path, _json_bytes(descriptor))
    final = dict(transition, previous_active_sha256=None, previous_descriptor=None)
    atomic_write(owner_path, _json_bytes(final))

def _retire_active_restart(intent_path, intent, source_run, source_manifest):
    active_path, owner_path = _active_restart_paths(source_run, source_manifest)
    _write_active_restart(source_run, source_manifest, intent_path, intent, status='complete')
    active_path.unlink(missing_ok=True)
    owner_path.unlink(missing_ok=True)

def _retire_completed_descriptor_if_present(intent_path, intent, source_run, source_manifest):
    active_path, owner_path = _active_restart_paths(source_run, source_manifest)
    if active_path.exists() or owner_path.exists():
        _retire_active_restart(intent_path, intent, source_run, source_manifest)

def _record_restart_completion(intent_path, intent):
    path = _restart_completion_path(intent_path)
    fields = {'schema_version': 1, 'operation_id': intent['operation_id'],
              'source_run': intent['source']['run_dir'], 'source_owner_id': intent['source']['owner_id'],
              'intent_sha256': intent['intent_sha256'], 'successor_run_dir': intent['successor']['run_dir'],
              'successor_owner_id': intent['successor']['owner_id']}
    value = dict(fields, receipt_sha256=_digest(_json_bytes(fields)))
    if path.exists():
        _validate_restart_completion(path, intent)
        return
    atomic_write(path, _json_bytes(value))

def recover(run_dir, *, controller, authority, current_inputs):
    """Recover only exact helper-owned transactions; return a plan for external work."""
    run_path = safe_path(run_dir)
    run, manifest, _ = _load_run(run_path)
    normalized_inputs = review_inputs.validate_current_inputs(
        current_inputs, manifest, require_same_scope=False)
    input_appraisal = review_inputs.compare_inputs(review_inputs.candidate_inputs(manifest), normalized_inputs)
    authority = resource_claims.normalize_authority(authority) if authority is not None else None
    fallback = manifest.get('controller', {}).get('identity',
        {'kind': 'coordinator', 'name': 'legacy review coordinator', 'provider_id': None})
    normalized_controller = _controller(controller, fallback)
    active_restart = _active_restart_operation(run_path, manifest, include_abandoned=True)
    if active_restart is not None:
        with _restart_lock(run_path):
            run, manifest, _ = _load_run(run_path)
            active_restart = _active_restart_operation(run_path, manifest, include_abandoned=True)
            if active_restart is None:
                return {'status': 'restart_no_longer_pending', 'run_dir': str(run_path),
                        'run_id': manifest.get('run_id'),
                        'actions': [{'action': 'inspect', 'reason': 'The pending restart changed while acquiring its source lock.'}]}
            return _recover_pending_restart(run_path, manifest, active_restart, authority, current_inputs)
    recovery_source = _restart_recovery_source(run, manifest)
    resource_exit = _diagnostic_recovery_route(run, manifest, recovery_source=recovery_source)
    if resource_exit is not None:
        return {'status': 'plan', 'run_dir': str(run), 'run_id': manifest.get('run_id'),
                'input_appraisal': input_appraisal, **resource_exit}
    if recovery_source is not None:
        return {'status': 'restart_pending', 'run_dir': str(run), 'run_id': manifest.get('run_id'),
                'input_appraisal': input_appraisal,
                'actions': [_recover_source_action(recovery_source)]}
    return _recover_run_transactions(run_path, normalized_controller, authority, current_inputs, input_appraisal)

def _restart_transfer_denial(intent, manifests):
    pair = [row for manifest in manifests for row in normalize_transfer_history(manifest)
            if row['source_run'] == intent['source']['run_dir']
            and row['successor_run'] == intent['successor']['run_dir']]
    if not pair:
        return None
    phase = 'transfer_durable' if any(row['status'] != 'complete' for row in pair) else 'transfer_committed'
    return _RestartCancellationUnavailable(
        'A durable resource transfer prevents cancellation; preserve its ownership obligations even if the successor is absent.',
        phase=phase)

def _restart_resource_manifests(run, manifest, intent):
    """Read the same verified source/successor pair for every refusal route.

    Mutators hold both run locks while observing a present successor. A missing
    successor never discards durable transfer proof already held by the source.
    """
    _verify_files(run, manifest, allow_checkpoint_transaction=True,
                  allow_resource_transfer=True, allow_pending_trace=True)
    manifests = [manifest]
    successor = safe_path(intent['successor']['run_dir'])
    if (successor / 'cierre.json').exists():
        _, next_manifest, _ = _load_run(successor)
        _verify_restart_successor_identity(successor, next_manifest, intent)
        _verify_files(successor, next_manifest, allow_checkpoint_transaction=True,
                      allow_resource_transfer=True, allow_pending_trace=True)
        manifests.append(next_manifest)
    return manifests

def _independent_review_action(run, reason, operation_id=None):
    result = {'action': 'new_independent_review', 'run_dir': str(run), 'previous_run': None,
              'use_fresh_resources': True, 'requires_explicit_authority': True,
              'reason': reason + ' Preserve the pending transaction; an explicitly authorized prepare without '
                        'previous-run can use fresh resources independently. It does not cancel the original '
                        'operation or clean another review session.'}
    if operation_id is not None:
        result['operation_id'] = operation_id
    return result

def _unavailable_transfer_source_exit(run, manifest):
    for transfer in normalize_transfer_history(manifest):
        if transfer['status'] == 'complete' or transfer['successor_run'] != str(run):
            continue
        if (transfer['successor_run_id'] != manifest['run_id']
                or transfer['successor_owner_id'] != manifest['owner_id']
                or transfer['repository_key'] != manifest['repository_key']):
            raise ValueError('incoming transfer successor identity differs from its local archive')
        operation = manifest.get('restart_operation')
        reservation_path = run / '.review-restart-reservation.json'
        if operation is not None and reservation_path.exists():
            expected = {key: operation[key] for key in ('operation_id', 'intent_sha256', 'reservation_id')}
            expected.update(run_dir=str(run), owner_id=manifest['owner_id'])
            if read_json(reservation_path) != expected:
                raise ValueError('prepared successor reservation differs from its local restart identity')
        try:
            source, source_manifest, _ = _load_run(transfer['source_run'])
            _verify_files(source, source_manifest, allow_checkpoint_transaction=True,
                          allow_resource_transfer=True, allow_pending_trace=True)
        except (OSError, ValueError, TypeError, KeyError):
            _verify_files(run, manifest, allow_checkpoint_transaction=True,
                          allow_resource_transfer=True, allow_pending_trace=True)
            return {'recovery': {'status': 'source_unavailable', 'can_complete': False,
                'transaction_pending': True, 'cancellation_supported': False,
                'source_run': transfer['source_run'], 'blocked_by': ['source_unavailable']},
                'actions': [{'action': 'preserve', 'run_dir': str(run), 'source_run': transfer['source_run'],
                             'reason': 'The exact incoming transfer source cannot be verified; preserve the transaction and resources.'},
                            _independent_review_action(run, 'The incoming transfer cannot finish without its verified source.')]}
        if (source_manifest.get('run_id') != transfer['source_run_id']
                or source_manifest.get('owner_id') != transfer['source_owner_id']
                or source_manifest.get('repository_key') != transfer['repository_key']):
            raise ValueError('incoming transfer source identity differs from its recorded intent')
    return None

def _diagnostic_recovery_route(run, manifest, *, active_restart=None, recovery_source=None):
    if active_restart is not None:
        return _restart_resource_exit(run, manifest, active_restart)
    if recovery_source is not None and recovery_source.get('resource_exit') is not None:
        return recovery_source['resource_exit']
    return _unavailable_transfer_source_exit(run, manifest)

def _restart_resource_exit(run, manifest, active_restart):
    """Read-only guidance; the mutator must recheck eligibility under its locks."""
    intent = active_restart['intent']
    if _find_restart_abandonment(active_restart['intent_path'], intent) is not None:
        return None  # An already authorized cancellation must finish through ordinary recovery.
    successor = safe_path(intent['successor']['run_dir'])
    own_archives = {os.path.normcase(str(run)), os.path.normcase(str(successor))}
    missing, foreign, own_sidecars = [], [], []
    for raw in intent['request']['transfer_paths']:
        session = safe_path(raw)
        if not session.exists():
            missing.append(raw)
            continue
        sidecar_path = safe_path(session / resource_claims.CLAIM_NAME)
        if not sidecar_path.exists():
            continue
        sidecar = read_json(sidecar_path)
        if isinstance(sidecar, dict) and sidecar.get('status') == 'owned':
            owner = safe_path(sidecar.get('archive_path', ''))
            if os.path.normcase(str(owner)) not in own_archives:
                resource_claims.inspect_claim_identity(session, owner)
                foreign.append(raw)
            else:
                own_sidecars.append((session, owner))
    if not missing and not foreign:
        return None
    # Never turn local corruption into an alternative-work suggestion.
    manifests = _restart_resource_manifests(run, manifest, intent)
    prepared = len(manifests) == 2
    next_manifest = manifests[1] if prepared else None
    transfers = [row for current in manifests for row in normalize_transfer_history(current)]
    claimed = {os.path.normcase(str(safe_path(row['session_dir']))) for current in manifests
               for row in current.get('resource_claims', []) if row.get('status') in {'owned', 'releasing'}}
    claimed.update(os.path.normcase(str(safe_path(item['session_dir']))) for row in transfers
                   if row['source_run'] == str(run) and row['successor_run'] == str(successor)
                   for item in row['items'])
    missing = [raw for raw in missing if os.path.normcase(str(safe_path(raw))) in claimed]
    if not missing and not foreign:
        return None  # missing_unclaimed does not prevent the existing exact replay.
    # A transfer may have replaced its sidecar before persisting its claim row.
    # Only its exact hash-bound bytes may bypass ordinary ownership-row checks.
    for session, owner in own_sidecars:
        permitted = {item[key] for row in transfers if row['status'] == 'pending'
            and row['source_run'] == str(run) and row['successor_run'] == str(successor)
            for item in row['items'] if os.path.normcase(item['session_dir']) == os.path.normcase(str(session))
            for key in ('old_claim_sha256', 'new_claim_sha256')}
        if _digest((session / resource_claims.CLAIM_NAME).read_bytes()) in permitted:
            continue
        if (prepared and owner == successor
                and not any(row['source_run'] == str(run) and row['successor_run'] == str(successor)
                            for row in transfers)
                and not any(os.path.normcase(row['session_dir']) == os.path.normcase(str(session))
                            for row in next_manifest.get('resource_claims', []))):
            # register can stop after claiming an adopted session but before its
            # row is saved. Reuse its pure preflight, without performing replay.
            plan = resource_claims.plan_claim(session, owner, next_manifest)
            if plan['action'] != 'recover':
                raise ValueError('pending adoption does not match its reserved successor')
        else:
            resource_claims.inspect_claim_identity(session, owner)
    blocked_by = []
    denial = _restart_transfer_denial(intent, manifests)
    if denial is not None or any(row['status'] != 'complete' for row in transfers):
        blocked_by.append('transfer_in_progress')
        denial = denial or _RestartCancellationUnavailable(
            'A durable transfer has committed its intent; cancellation cannot infer rollback or release of missing workspaces.',
            phase='transfer_durable')
    if any(row.get('status') == 'releasing' or
           (row.get('status') == 'owned' and safe_path(row['session_dir']).exists())
           for row in manifest.get('resource_claims', [])):
        blocked_by.append('source_claims_present')
        if denial is None:
            denial = _RestartCancellationUnavailable(
                'Present or releasing source claims require their owning resource protocol.', phase='source_claims_present')
    supported = not blocked_by
    if supported and prepared:
        try:
            _empty_adoption_successor(intent, manifest)
        except _RestartCancellationUnavailable as exc:
            supported = False
            blocked_by.append('successor_claims_or_work')
            denial = exc
    if supported:
        action = {'action': 'abandon_restart', 'run_dir': str(run),
            'operation_id': intent['operation_id'], 'intent_path': active_restart['intent_path'],
            'requires_explicit_authority': True,
            'reason': 'A selected resource is missing or held by another review; abandon-restart can cancel this exact request with explicit authority. '
                      'This diagnostic does not execute cancellation or release claims.'}
    else:
        reasons = {'transfer_in_progress': 'A durable resource transfer prevents abandonment.',
                   'source_claims_present': 'Present or releasing source claims prevent abandonment.',
                   'successor_claims_or_work': 'Claims or work already owned by the successor prevent abandonment.'}
        action = _independent_review_action(run, ' '.join(reasons[code] for code in blocked_by), intent['operation_id'])
    actions = [action]
    if denial is not None and manifest.get('schema_version') == 8 and manifest.get('state') != 'complete':
        actions.append({'action': 'record_restart_refusal', 'run_dir': str(run),
            'operation_id': intent['operation_id'], 'intent_path': active_restart['intent_path'],
            'requires_explicit_authority': True, 'phase': denial.phase,
            'reason': 'Record this refusal in the source trace with authority and observed evidence; the restart and all resource obligations remain pending.'})
    return {'missing_resources': missing, 'foreign_resources': foreign, 'cancellation_supported': supported,
            'recovery': {'status': 'cancellation_available' if supported else 'independent_review_required',
                'can_complete': False, 'transaction_pending': True, 'cancellation_supported': supported,
                'source_run': str(run), 'operation_id': intent['operation_id'], 'blocked_by': blocked_by,
                **({'cancellation_denial': denial.diagnostic()} if denial is not None else {})},
            'actions': actions}

def _recover_pending_restart(run_path, manifest, active_restart, authority, current_inputs):
    """Caller holds the source restart lock and reread the active descriptor."""
    intent = active_restart['intent']
    if authority is None:
        raise ValueError('recovering a pending restart requires explicit authority')
    cancellation = _find_restart_abandonment(active_restart['intent_path'], intent)
    if cancellation is not None:
        _finish_restart_abandonment(Path(active_restart['intent_path']), intent, run_path, cancellation)
        return {'status': 'restart_abandoned', 'run_dir': str(run_path), 'run_id': manifest.get('run_id'),
                'actions': [{'action': 'new_review', 'run_dir': str(run_path),
                             'reason': 'The recorded cancellation completed; a fresh request needs a new selection decision.'}]}
    requested_inputs = review_inputs.normalize_inputs(current_inputs)
    requested_inputs.pop('profile', None)
    restart_profile = intent['request']['profile_input']['profile']
    expected_inputs = copy.deepcopy(intent['request']['current_inputs'])
    expected_inputs.setdefault('logical_scope_identity', review_layout.logical_scope(
        expected_inputs['scope'], intent['request']['logical_scope_input'])['identity'])
    if (requested_inputs['scope'] == expected_inputs['scope']
            and 'logical_scope_identity' not in requested_inputs):
        requested_inputs['logical_scope_identity'] = review_layout.logical_scope(
            requested_inputs['scope'], intent['request']['logical_scope_input'])['identity']
    expected_inputs['profile'] = restart_profile
    requested_inputs['profile'] = restart_profile
    restart_appraisal = review_inputs.compare_inputs(expected_inputs, requested_inputs)
    if requested_inputs != expected_inputs:
        return {'status': 'restart_pending', 'run_dir': str(run_path), 'run_id': manifest.get('run_id'),
                'successor_run_dir': active_restart['successor_run_dir'],
                'input_appraisal': restart_appraisal,
                'replay_inputs_match': False,
                'actions': [{'action': 'retry_restart',
                             'reason': 'The pending reservation can continue only with the exact current inputs captured by its intent.'}]}
    resource_exit = _restart_resource_exit(run_path, manifest, active_restart)
    if resource_exit is not None:
        return {'status': 'restart_pending', 'run_dir': str(run_path), 'run_id': manifest.get('run_id'),
                'successor_run_dir': active_restart['successor_run_dir'],
                'input_appraisal': restart_appraisal, 'replay_inputs_match': True,
                **resource_exit}
    intent_path = Path(active_restart['intent_path'])
    if not intent_path.exists():
        _write_restart_intent(intent_path, intent, run_path, manifest)
    successor = _complete_restart_intent(intent_path, run_path, manifest)
    return {'status': 'restarted', 'run_dir': str(run_path), 'run_id': manifest.get('run_id'),
            'successor_run_dir': successor, 'input_appraisal': restart_appraisal, 'replay_inputs_match': True,
            'actions': [{'action': 'inspect_successor', 'reason': 'The exact reserved restart completed; no review work was dispatched.'}]}

def _recover_run_transactions(run_path, normalized_controller, authority, current_inputs, input_appraisal):
    run, manifest, _ = _load_run(run_path)
    cleanup_intent = manifest.get('resource_cleanup')
    if isinstance(cleanup_intent, dict) and cleanup_intent.get('status') == 'pending':
        cleanup_result = recover_resource_cleanup(run_path)
        if cleanup_result.get('status') == 'pending':
            return _recovery_outcome({'status': 'plan', 'run_dir': str(run_path),
                    'run_id': manifest.get('run_id'),
                    'actions': [{'action': 'retry_cleanup',
                                 'reason': cleanup_result.get('reason', 'The recorded workspace cleanup is incomplete.')}]
                    }, input_appraisal)
        run, manifest, _ = _load_run(run_path)
    pending_transfers = [row for row in normalize_transfer_history(manifest) if row['status'] == 'pending']
    if pending_transfers:
        transfer = pending_transfers[0]
        if authority != transfer['authority']:
            raise ValueError('resource transfer recovery authority differs from its preserved intent')
        transfer_resources(transfer['source_run'], transfer['successor_run'],
                           [item['session_dir'] for item in transfer['items']],
                           authority=transfer['authority'], controller=transfer['controller'])

    with run_locks([run_path]):
        run, manifest, marker = _load_run(run_path)
        active_restart = _active_restart_operation(run, manifest, include_abandoned=True)
        if active_restart is not None:
            return _recover_pending_restart(run, manifest, active_restart, authority, current_inputs)
        normalized_inputs = review_inputs.validate_current_inputs(
            current_inputs, manifest, require_same_scope=False)
        input_appraisal = review_inputs.compare_inputs(review_inputs.candidate_inputs(manifest), normalized_inputs)
        if manifest.get('pending_trace') is not None:
            marker = _recover_trace(run, manifest, marker)
            run, manifest, marker = _load_run(run)
        if manifest.get('restart_abandonment') is not None:
            _verify_files(run, manifest)
            return {'status': 'abandoned', 'run_dir': str(run), 'run_id': manifest.get('run_id'),
                    'input_appraisal': input_appraisal,
                    'actions': [_abandoned_source_action(manifest)]}
        if manifest.get('operation', {}).get('disposition') == 'superseded':
            # A checkpoint interrupted before restart is historical provisional
            # state. Do not require its original inputs or commit it on a run
            # whose review work is already owned by its successor.
            _verify_files(run, manifest, allow_checkpoint_transaction=True)
            resources = _resource_availability(run, manifest)
            return {'status': 'superseded', 'run_dir': str(run), 'run_id': manifest.get('run_id'),
                    'successor_run_dir': manifest['operation']['successor'],
                    'input_appraisal': input_appraisal, 'resources': resources,
                    'actions': _superseded_actions(resources)}
        checkpoint_transaction = manifest.get('checkpoint_transaction')
        if checkpoint_transaction is not None:
            if manifest['schema_version'] != 8 or manifest['state'] == 'complete':
                raise ValueError('checkpoint transaction is invalid for this review state')
            _verify_files(run, manifest, allow_checkpoint_transaction=True,
                          allow_resource_transfer=True)
            payloads = {}
            missing = []
            for name, expected in checkpoint_transaction['planned_hashes'].items():
                path = safe_path(run / name)
                try:
                    data = path.read_bytes()
                except FileNotFoundError:
                    missing.append(name)
                    continue
                current_hash = _digest(data)
                previous_hash = checkpoint_transaction['previous_hashes'].get(name)
                if current_hash == expected:
                    payloads[name] = data
                elif current_hash == previous_hash:
                    missing.append(name)
                else:
                    raise ValueError('foreign or modified checkpoint bytes block recovery: ' + name)
            if missing:
                return _recovery_outcome({'status': 'plan', 'run_dir': str(run), 'run_id': manifest.get('run_id'),
                        'actions': [{'action': 'retry_checkpoint',
                                     'reason': 'Resupply the original selected inputs: ' + ', '.join(sorted(missing))}]},
                                        input_appraisal)
            _checkpoint_commit(run, manifest, marker, checkpoint_transaction, payloads)
            run, manifest, marker = _load_run(run)

        if manifest.get('schema_version') == 8:
            normalized_controller, marker = takeover_controller(
                run, manifest, marker, normalized_controller, authority)

        if manifest['state'] in {'retaining', 'closing'}:
            return _recovery_outcome({'status': 'plan', 'run_dir': str(run), 'run_id': manifest.get('run_id'),
                    'actions': [{'action': 'retry_retention' if manifest['state'] == 'retaining' else 'retry_close',
                                 'reason': 'The original final input or cleanup observation must be supplied; no external work was run.'}]},
                                    input_appraisal)
        if any(row['status'] == 'pending' for row in normalize_transfer_history(manifest)):
            raise ValueError('resource transfer remains pending; retry recovery from its recorded source run')
        _verify_files(run, manifest)
        resources = _resource_availability(run, manifest)
        if any(row['availability'] == 'missing_unknown' for row in resources):
            return _recovery_outcome({'status': 'plan', 'run_dir': str(run), 'run_id': manifest.get('run_id'),
                'resources': resources, 'actions': [{'action': 'restart',
                    'reason': 'A claimed session is missing_unknown; preserve its claim and restart without transferring it.'}]},
                input_appraisal)
        disposition = manifest.get('operation', {}).get('disposition', 'complete' if manifest['state'] == 'complete' else 'open')
        if disposition in {'paused', 'blocked'}:
            return _recovery_outcome({'status': disposition, 'run_dir': str(run), 'run_id': manifest.get('run_id'),
                    'actions': [{'action': 'resume', 'reason': 'Explicit continuation authority is required before more work.'},
                                {'action': 'restart', 'reason': 'Create a linked new run when the original scope or sources cannot be continued.'}]},
                                    input_appraisal)
        if disposition == 'complete' or manifest['state'] == 'complete':
            return _recovery_outcome({'status': disposition, 'run_dir': str(run), 'run_id': manifest.get('run_id'),
                    'actions': [{'action': 'show', 'reason': 'Preserve and show the existing immutable result.'},
                                {'action': 'restart', 'reason': 'A repeat must use a new review ID.'}]},
                                    input_appraisal)
        checkpoint = manifest.get('checkpoint')
        if isinstance(checkpoint, dict) and checkpoint.get('gate_errors'):
            return _recovery_outcome({'status': 'provisional', 'run_dir': str(run), 'run_id': manifest.get('run_id'),
                    'checkpoint_id': checkpoint['id'], 'gate_errors': checkpoint['gate_errors'],
                    'actions': [{'action': 'continue', 'reason': 'The checkpoint remains provisional; its gates still apply.'},
                                {'action': 'restart', 'reason': 'A new run is available if history or scope cannot be repaired.'}]},
                                    input_appraisal)
        return _recovery_outcome({'status': 'recovered' if checkpoint_transaction is not None or manifest.get('checkpoint') else 'ready',
                'run_dir': str(run), 'run_id': manifest.get('run_id'),
                'checkpoint_id': checkpoint.get('id') if isinstance(checkpoint, dict) else None,
                'actions': [{'action': 'continue', 'reason': 'Recovery did not dispatch agents, run checks or alter prior worker identity.'}]},
                                  input_appraisal)

def _recovery_outcome(result, appraisal):
    result['input_appraisal'] = appraisal
    if appraisal['applicability'] != 'applicable':
        result['actions'] = [row for row in result.get('actions', [])
                             if row.get('action') not in {'continue', 'resume', 'retry_checkpoint',
                                                          'retry_retention', 'retry_close'}]
        result['actions'].append({'action': 'restart',
            'reason': 'Recovery may restore exact helper-owned bytes, but current inputs are '
                      + appraisal['applicability'] + '; do not continue this review.'})
    return result

def _link_restart(source_run, successor_run, *, authority, controller, moved_paths=(), preserve_claims=False):
    source_path, successor_path = safe_path(source_run), safe_path(successor_run)
    authority = resource_claims.normalize_authority(authority)
    _load_run(source_path)
    _load_run(successor_path)
    with run_locks([source_path, successor_path]):
        source, old, old_marker = _load_run(source_path)
        successor, new, _ = _load_run(successor_path)
        _assert_not_restart_abandoned(old)
        _assert_not_restart_abandoned(new)
        _verify_files(source, old, allow_checkpoint_transaction=True, allow_resource_transfer=True)
        _verify_files(successor, new)
        if old['schema_version'] != 8 or old['state'] == 'complete':
            return
        if old['operation']['disposition'] == 'superseded':
            if old['operation']['successor'] == str(successor) and new.get('previous_run') == str(source):
                return
            raise ValueError('source review already has a different successor')
        if old['operation']['disposition'] not in {'open', 'paused', 'blocked'}:
            raise ValueError('source review cannot be superseded from its current disposition')
        if not preserve_claims and any(row.get('status') == 'owned' for row in old.get('resource_claims', [])):
            raise ValueError('owned resources require explicit transfer before restart')
        normalized_controller = _controller(controller, new['controller']['identity'])
        old['operation'].update(disposition='superseded', reason=authority,
                                source='restart', phase='restart', successor=str(successor))
        old['temporary_paths'] = [path for path in old.get('temporary_paths', []) if path not in set(moved_paths)]
        old['temporary_manifests'] = _temporary_manifests(old['temporary_paths'], old)
        _append_trace(source, old, old_marker, {'kind': 'handoff', 'status': 'completed',
            'summary': 'Review superseded by linked successor ' + new['run_id'],
            'actor': normalized_controller['identity'],
            'authority': authority, 'evidence': ['cierre.json'],
            'relations': [{'relation': 'supersedes', 'target': str(successor)}]})

def _restart_operation_row(intent):
    return {'operation_id': intent['operation_id'], 'request_sha256': intent['request_sha256'],
            'intent_sha256': intent['intent_sha256'], 'source_run': intent['source']['run_dir'],
            'source_owner_id': intent['source']['owner_id'],
            'reservation_id': intent['successor']['reservation_id']}

def _restart_adoption_context(request):
    selection = _initial_selection(request['profile_input'])
    context = {'profile': selection['profile'], 'selection_source': selection['selection_source'],
               'profile_reference': selection['reference'], 'profile_history': [selection],
               'execution_plan': [], 'executors': [], 'review_inputs': copy.deepcopy(request['current_inputs'])}
    errors = review_profiles.validate_history(context['profile_history'])
    if errors or not isinstance(context['execution_plan'], list) or not isinstance(context['executors'], list):
        raise ValueError('restart adoption context is invalid: ' + '; '.join(errors))
    return _input_object(context, 'restart adoption context')

def _prepare_from_restart_intent(intent_path):
    """Create or resume only the exact destination reserved by the intent."""
    intent_file = safe_path(intent_path)
    intent = read_json(intent_file)
    errors = review_restart.validate_restart_intent(intent)
    if errors:
        raise ValueError('; '.join(errors))
    source_path = safe_path(intent['source']['run_dir'])
    source, source_manifest, _ = _load_run(source_path)
    intent = _read_restart_intent(intent_file, source, source_manifest) if intent_file.exists() else intent
    request = intent['request']
    source_claims = [row for row in source_manifest.get('resource_claims', []) if row.get('status') == 'owned']
    selected = request['transfer_paths']
    active_present = [row for row in source_claims if Path(row['session_dir']).exists()]
    transfer_records = normalize_transfer_history(source_manifest)
    is_transferring = bool(source_claims) or any(
        row.get('source_run') == str(source_path)
        and row.get('successor_run') == intent['successor']['run_dir']
        and {item.get('session_dir') for item in row.get('items', [])} == set(selected)
        for row in transfer_records)
    has_adoption = bool(selected) and not is_transferring
    adoption_context = _restart_adoption_context(request) if has_adoption else None
    current_scope = request['current_inputs']['scope']
    version_path = resource_path('SKILL.md')
    try:
        skill_text = version_path.read_text(encoding='utf-8')
        version_match = re.search(r'(?m)^\s+version:\s*["\']?([0-9]+\.[0-9]+\.[0-9]+)', skill_text)
        skill_version = version_match.group(1) if version_match else source_manifest['skill_version']
    except OSError:
        skill_version = source_manifest['skill_version']
    harness = request['harness']
    successor = prepare(source_manifest['repository_path'], current_scope, skill_version, harness['harness'],
        source_manifest['archive_root'], source_path, selected,
        profile_input=request['profile_input'], controller=request['controller'],
        current_inputs=request['current_inputs'], logical_scope_input=request['logical_scope_input'],
        _restart_reservation=intent,
        _harness_identity={key: harness[key] for key in ('harness_id', 'harness_catalog_version',
                                                          'harness_source', 'harness_diagnostics')})
    if selected:
        if is_transferring:
            transfer_resources(source_path, successor, selected, authority=request['authority'],
                               controller=request['controller'],
                               _restart_operation_id=intent['operation_id'])
        elif has_adoption:
            register(successor, selected, context_input=adoption_context, authority=request['authority'])
    if source_manifest.get('schema_version') == 8 and source_manifest.get('state') != 'complete':
        moved = set(selected) if is_transferring else set()
        preserve_claims = any(row.get('status') == 'owned' and row['session_dir'] not in moved
                              for row in source_manifest.get('resource_claims', []))
        _link_restart(source_path, successor, authority=request['authority'],
                      controller=request['controller'], moved_paths=moved,
                      preserve_claims=preserve_claims)
    return str(successor)

def _complete_restart_intent(intent_path, source_path, source_manifest):
    intent = _read_restart_intent(intent_path, source_path, source_manifest)
    cancellation = _find_restart_abandonment(intent_path, intent)
    if cancellation is not None:
        _finish_restart_abandonment(intent_path, intent, source_path, cancellation)
        raise ValueError('this restart request was explicitly abandoned; use a new selection decision for a new request')
    active = _active_restart_operation(source_path, source_manifest)
    if active is not None and active['operation_id'] != intent['operation_id']:
        raise ValueError('another restart operation is active for this source')
    _write_restart_intent(intent_path, intent, source_path, source_manifest)
    if active is None:
        completion = _validate_restart_completion(_restart_completion_path(intent_path), intent)
        if completion is not None:
            successor, successor_manifest, _ = _load_run(completion['successor_run_dir'])
            _verify_files(successor, successor_manifest)
            if successor_manifest.get('restart_operation') != _restart_operation_row(intent):
                raise ValueError('completed restart successor differs from its durable receipt')
            _retire_completed_descriptor_if_present(intent_path, intent, source_path, source_manifest)
            return str(successor)
        _write_active_restart(source_path, source_manifest, intent_path, intent)
    try:
        successor_path = _prepare_from_restart_intent(intent_path)
    except ValueError as exc:
        error_type = type(exc) if isinstance(exc, CoordinationError) else ValueError
        raise error_type(str(exc) + '; inspect/recover source ' + str(source_path)
                         + ' for the recorded recovery plan') from exc
    successor, successor_manifest, _ = _load_run(successor_path)
    _verify_files(successor, successor_manifest, allow_resource_transfer=True)
    if successor_manifest.get('restart_operation') != _restart_operation_row(intent):
        raise ValueError('prepared successor does not match the reserved restart operation')
    _record_restart_completion(intent_path, intent)
    _retire_active_restart(intent_path, intent, source_path, source_manifest)
    return str(successor)

def restart(source_run, *, profile_input, controller, authority, current_inputs, transfer_paths=None,
            harness=None, logical_scope_input=None):
    """Create or replay one durable, source-bound archive-8 restart operation."""
    source_path = safe_path(source_run)
    with _restart_lock(source_path):
        source, manifest, marker = _load_run(source_path)
        is_immutable = manifest.get('state') == 'complete' or manifest.get('schema_version') != 8
        if not is_immutable:
            marker = _recover_trace(source, manifest, marker)
        _verify_files(source, manifest, allow_checkpoint_transaction=True,
                      allow_resource_transfer=True)
        # A restart pins its destination selector, even when the snapshot is
        # unchanged. Do not fill omitted identities from the source selector.
        normalized_inputs = review_inputs.normalize_inputs(current_inputs)
        if normalized_inputs['scope']['repository'] != manifest['scope']['repository']:
            raise ValueError('restart cannot change the source repository identity')
        if logical_scope_input is None:
            logical_scope_input = manifest.get('logical_scope_input')
        logical = review_layout.logical_scope(normalized_inputs['scope'], logical_scope_input)
        raw_harness = harness
        if raw_harness is None:
            raw_harness = {'harness': 'unknown', 'harness_id': None, 'harness_source': None}
        request = review_restart.normalize_restart_request(profile_input, controller, authority,
            normalized_inputs, list(transfer_paths or []), raw_harness, logical_scope_input)
        _scope(request['current_inputs']['scope'])
        request['current_inputs'] = _capture_review_inputs(request['current_inputs'], request['current_inputs']['scope'],
                               request['profile_input']['profile'], 'restart current review inputs',
                               logical_scope_identity=logical['identity'])
        repository = safe_path(_git(safe_path(manifest['repository_path']), 'rev-parse', '--show-toplevel'))
        identity = repository_identity(repository)
        if _digest(identity.encode('utf-8'))[:20] != manifest['repository_key']:
            raise ValueError('restart source repository identity no longer matches its pinned archive')
        future = dict(manifest, temporary_paths=[], temporary_manifests=[], repository_identity=identity)
        selected_temporaries = _temporary_paths(request['transfer_paths'], future)
        _temporary_manifests(selected_temporaries, future)
        disposition = manifest.get('operation', {}).get('disposition',
            'complete' if manifest.get('state') == 'complete' else 'open')
        if manifest.get('state') in {'retaining', 'closing'}:
            raise ValueError('recover the pending retain/close transaction before restarting')
        if isinstance(manifest.get('resource_cleanup'), dict) and manifest['resource_cleanup'].get('status') == 'pending':
            raise ValueError('recover pending resource cleanup before restarting')
        if disposition not in {'open', 'paused', 'blocked', 'superseded', 'complete'}:
            raise ValueError('source review cannot be restarted from its current operation state')
        active = _active_restart_operation(source, manifest)
        intent_path = (Path(active['intent_path']) if active is not None
                       else _existing_restart_intent_path(source, manifest, request))
        if active is not None:
            active_intent = active['intent']
            if not review_restart.same_restart_request(active_intent['request'], request):
                raise ValueError('a different restart request is already active for this source')
            if not intent_path.exists():
                _write_restart_intent(intent_path, active_intent, source, manifest)
        elif intent_path.exists():
            existing_intent = _read_restart_intent(intent_path, source, manifest)
            if not review_restart.same_restart_request(existing_intent['request'], request):
                raise ValueError('restart intent identity collision; preserve the reserved operation')
            cancellation = _validate_restart_abandonment(intent_path, existing_intent)
            if cancellation is not None:
                _finish_restart_abandonment(intent_path, existing_intent, source, cancellation)
                raise ValueError('this restart request was explicitly abandoned; use a new selection decision for a new request')
            completion = _validate_restart_completion(_restart_completion_path(intent_path), existing_intent)
            if completion is not None:
                successor, successor_manifest, _ = _load_run(completion['successor_run_dir'])
                _verify_files(successor, successor_manifest)
                if successor_manifest.get('restart_operation') != _restart_operation_row(existing_intent):
                    raise ValueError('completed restart successor differs from its durable receipt')
                _retire_completed_descriptor_if_present(intent_path, existing_intent, source, manifest)
                return str(successor)
            request = existing_intent['request']
            intent = existing_intent
            _write_active_restart(source, manifest, intent_path, intent)
        else:
            if disposition == 'superseded':
                raise ValueError('source review was superseded; inspect its recorded successor')
            source_claims = [row for row in manifest.get('resource_claims', []) if row.get('status') == 'owned']
            selected = request['transfer_paths']
            active_present, active_missing = [], []
            for row in source_claims:
                session = Path(row['session_dir'])
                if session.exists():
                    resource_claims.verify_claim(session, source, allow_checkpoint_transaction=True)
                    active_present.append(row['session_dir'])
                else:
                    active_missing.append(row['session_dir'])
            if selected:
                selected_paths = [str(safe_path(path)) for path in selected]
                selected_keys = {os.path.normcase(path) for path in selected_paths}
                active_keys = {os.path.normcase(path) for path in active_present}
                if source_claims and (active_missing or selected_keys != active_keys):
                    raise ValueError('restart transfer must include every present owned claim; missing claims cannot be transferred')
                if source_claims and normalized_inputs['scope'] != manifest['scope']:
                    raise ValueError('owned sessions stay with the source when the review scope changes; do not transfer them')
                registered = {os.path.normcase(path) for path in manifest.get('temporary_paths', [])}
                if source_claims and not selected_keys.issubset(registered):
                    raise ValueError('restart transfer paths must already be registered to the source run')
                if not source_claims:
                    _restart_adoption_context(request)
                    from_claims = {'schema_version': ARCHIVE_SCHEMA_VERSION, 'repository_path': manifest['repository_path'],
                                   'repository_identity': identity,
                                   'repository_key': manifest['repository_key'], 'archive_root': manifest['archive_root'],
                                   'temporary_paths': []}
                    plans = resource_claims.plan_resource_registration(
                        selected_paths, from_claims, authority=request['authority'])
                    if any(plan.get('action') not in {'adopt_pending', 'claim_pending'} for plan in plans):
                        raise ValueError('only verified review workspace sessions can be adopted during restart')
            elif active_present and normalized_inputs['scope'] == manifest['scope']:
                raise ValueError('explicit transfer paths are required to preserve present owned sessions across a same-scope restart')
            candidate_successor = datetime.now(timezone.utc)
            run_id = uuid.uuid4().hex[:20]
            scoped = Path(manifest['archive_root']) / _repository_group(identity) / review_layout.scope_group(logical)
            successor_info = {'run_dir': str(scoped / review_layout.run_name(
                                  normalized_inputs['scope'], candidate_successor.isoformat(), run_id, logical_scope_input)),
                              'run_id': run_id, 'owner_id': uuid.uuid4().hex,
                              'reservation_id': uuid.uuid4().hex,
                              'created_at': candidate_successor.isoformat()}
            intent = review_restart.build_restart_intent(
                _restart_source_identity(source, manifest), request, successor_info)
            intent_path = _restart_intent_path(source, manifest, request)
            _write_active_restart(source, manifest, intent_path, intent)
            _write_restart_intent(intent_path, intent, source, manifest)
        return _complete_restart_intent(intent_path, source, manifest)

def _find_restart_abandonment(intent_path, intent):
    receipt = _validate_restart_abandonment(intent_path, intent)
    successor_path = safe_path(intent['successor']['run_dir'])
    if (successor_path / 'cierre.json').exists():
        _, successor, _ = _load_run(successor_path)
        embedded = successor.get('restart_abandonment')
        if embedded is not None:
            _validate_restart_abandonment_value(embedded, intent)
            if receipt is not None and receipt != embedded:
                raise ValueError('source and successor abandonment receipts differ')
            receipt = embedded
    return receipt

def _verify_restart_successor_identity(run, manifest, intent):
    """Check the reserved identity even when work/transfer makes cancellation unavailable."""
    reserved = intent['successor']
    expected = {'run_id': reserved['run_id'], 'owner_id': reserved['owner_id'],
                'created_at': reserved['created_at'], 'previous_run': intent['source']['run_dir'],
                'repository_key': intent['source']['repository_key'],
                'scope': intent['request']['current_inputs']['scope'],
                'restart_operation': _restart_operation_row(intent)}
    if any(manifest.get(key) != value for key, value in expected.items()):
        raise ValueError('prepared successor identity differs from the exact adoption intent')
    reservation_path = run / '.review-restart-reservation.json'
    if reservation_path.exists():
        expected_reservation = {'operation_id': intent['operation_id'], 'intent_sha256': intent['intent_sha256'],
            'reservation_id': reserved['reservation_id'], 'run_dir': str(run), 'owner_id': reserved['owner_id']}
        if read_json(reservation_path) != expected_reservation:
            raise ValueError('prepared successor reservation differs from its intent')

def _empty_adoption_successor(intent, source_manifest):
    """Read-only preflight under both locks: empty successor and an unavailable resource."""
    run, manifest, marker = _load_run(intent['successor']['run_dir'])
    _verify_restart_successor_identity(run, manifest, intent)
    transfer_denial = _restart_transfer_denial(intent, (source_manifest, manifest))
    if transfer_denial is not None:
        raise transfer_denial
    if any(row.get('status') == 'releasing' or
           (row.get('status') == 'owned' and safe_path(row['session_dir']).exists())
           for row in source_manifest.get('resource_claims', [])):
        raise _RestartCancellationUnavailable('present or releasing source claims prevent abandonment',
                                            phase='source_claims_present')
    if manifest.get('resource_claims'):
        raise _RestartCancellationUnavailable(
            'successor already owns committed adoption claims; cancellation cannot discard their ownership',
            phase='adoption_committed')
    if not intent['request']['transfer_paths']:
        raise _RestartCancellationUnavailable('prepared successor has no selected resources for abandonment; recover its exact restart',
                                            phase='resource_selection_empty')
    if source_manifest.get('operation', {}).get('disposition') == 'superseded':
        raise _RestartCancellationUnavailable('source is already superseded; its committed successor must be preserved',
                                            phase='source_superseded')
    if (manifest['state'] != 'prepared' or manifest['operation']['disposition'] != 'open'
            or manifest['profile_history'] != [_initial_selection(intent['request']['profile_input'])]
            or set(manifest['hashes']) - {review_trace.NAME}
            or any(manifest.get(key) for key in ('resource_transfers', 'resource_transfer',
                'resource_cleanup', 'cleanup_receipts', 'executors', 'assignment_registry', 'checkpoint',
                'checkpoint_transaction', 'pending_hashes', 'planned_hashes'))):
        raise _RestartCancellationUnavailable('a prepared successor with work or claims must be recovered; abandonment cannot orphan it')
    allowed = {MARKER, 'cierre.json', review_trace.NAME, '.review-restart-reservation.json'}
    if {path.name for path in run.iterdir()} - allowed:
        raise _RestartCancellationUnavailable('prepared successor contains evidence or unknown files; preserve it for recovery')
    unavailable_resource = False
    for raw in intent['request']['transfer_paths']:
        if not safe_path(raw).exists():
            unavailable_resource = True
            continue  # Preserve the source claim as missing_unknown; never synthesize release evidence.
        workspace = resource_claims.inspect_workspace(raw)
        if workspace is None:
            raise ValueError('adoption session is not a verifiable review workspace')
        session, workspace_manifest, token = workspace
        sidecar_path = session / resource_claims.CLAIM_NAME
        if not sidecar_path.exists():
            continue
        sidecar = read_json(sidecar_path)
        if sidecar.get('status') == 'bootstrap':
            continue  # load() already bound this bootstrap to its session/token.
        resource_claims.validate_sidecar(sidecar, session, workspace_manifest, token)
        if (sidecar['archive_path'] == str(run) or sidecar['run_id'] == manifest['run_id']
                or sidecar['owner_id'] == manifest['owner_id']):
            raise _RestartCancellationUnavailable('prepared successor already owns an adoption sidecar; recover it',
                                                phase='adoption_committed')
        if sidecar['archive_path'] == intent['source']['run_dir']:
            raise _RestartCancellationUnavailable('adoption session belongs to the restart source; recover its claim',
                                                phase='source_claims_present')
        resource_claims.inspect_claim_identity(session, sidecar['archive_path'])
        unavailable_resource = True
    if not unavailable_resource:
        raise _RestartCancellationUnavailable('a prepared successor must be recovered unless a resource is absent or foreign-claimed',
                                            phase='resources_available')
    pending = manifest.get('pending_trace')
    if pending is not None and [row.get('kind') for row in pending.get('events', [])] != ['prepare', 'profile']:
        raise _RestartCancellationUnavailable('prepared successor has a non-preparation trace transaction; recover it')
    _verify_files(run, manifest, allow_pending_trace=True)
    trace_bytes = (_trace_recovery_plan(run, manifest)[1] if pending is not None
                   else (run / review_trace.NAME).read_bytes())
    events = [json.loads(line) for line in trace_bytes.splitlines()]
    if [row['kind'] for row in events] != ['prepare', 'profile']:
        raise _RestartCancellationUnavailable('prepared successor has observations beyond initial preparation; recover it')
    return run, manifest, marker

def _finish_restart_abandonment(intent_path, intent, source_path, receipt):
    """Caller owns the source lock; finish only an already authorized durable decision."""
    _validate_restart_abandonment_value(receipt, intent)
    intent_path = Path(intent_path)
    source, source_manifest, marker = _load_run(source_path)
    prepared = (safe_path(intent['successor']['run_dir']) / 'cierre.json').exists()
    if prepared:
        with run_locks([intent['successor']['run_dir']]):
            successor, manifest, successor_marker = _load_run(intent['successor']['run_dir'])
            if manifest.get('restart_abandonment') != receipt:
                raise ValueError('prepared successor has no matching durable abandonment decision')
            _recover_trace(successor, manifest, successor_marker)
            _verify_files(successor, manifest)
    _write_restart_intent(intent_path, intent, source, source_manifest)
    stored = _validate_restart_abandonment(intent_path, intent)
    if stored is None:
        atomic_write(_restart_abandonment_path(intent_path), _json_bytes(receipt))
    elif stored != receipt:
        raise ValueError('abandonment receipt changed during replay')
    if source_manifest.get('schema_version') == 8 and source_manifest.get('state') != 'complete':
        marker = _recover_trace(source, source_manifest, marker)
        summary = ('Restart abandoned after blocked adoption: ' if prepared else
                   'Restart abandoned before successor preparation: ') + intent['operation_id']
        events = [json.loads(line) for line in (source / review_trace.NAME).read_bytes().splitlines()]
        if not any(row.get('summary') == summary for row in events):
            _append_trace(source, source_manifest, marker, {'kind': 'interruption', 'status': 'completed',
                'summary': summary, 'actor': receipt['controller']['identity'], 'authority': receipt['authority'],
                'evidence': ['cierre.json'], 'provenance': {'kind': 'helper', 'source': 'review_artifacts:abandon-restart'}})
    _, owner_path = _active_restart_paths(source, source_manifest)
    if owner_path.exists() and read_json(owner_path)['active_descriptor'].get('operation_id') == intent['operation_id']:
        _retire_active_restart(intent_path, intent, source, source_manifest)
    return receipt

def abandon_restart(run_dir, *, intent_path, controller, authority, reason):
    """Cancel an unprepared restart or its exact empty, resource-blocked successor.

    Never delete an archive, modify a foreign session, or discard review work.
    """
    authority = resource_claims.normalize_authority(authority)
    reason = review_restart._bounded_text(reason, 'abandonment reason')
    with _restart_lock(run_dir):
        run, manifest, marker = _load_run(run_dir)
        intent_path = safe_path(intent_path)
        if not intent_path.exists():
            active = _active_restart_operation(run, manifest)
            if active is None or str(intent_path) != active['intent_path']:
                raise ValueError('only the exact active intent path can be reconstructed for abandonment')
            intent = active['intent']
        else:
            intent = _read_restart_intent(intent_path, run, manifest)
        actor = _controller(controller, intent['request']['controller']['identity'])
        receipt = _find_restart_abandonment(intent_path, intent)
        if receipt is not None:
            if any(receipt[key] != value for key, value in
                   {'authority': authority, 'controller': actor, 'reason': reason}.items()):
                raise ValueError('abandonment replay differs from its durable observation')
        else:
            active = _active_restart_operation(run, manifest)
            if active is None or active['operation_id'] != intent['operation_id']:
                raise ValueError('only the exact active pending restart may be abandoned')
            with ExitStack() as stack:
                if (safe_path(intent['successor']['run_dir']) / 'cierre.json').exists():
                    stack.enter_context(run_locks([intent['successor']['run_dir']]))
                manifests = _restart_resource_manifests(run, manifest, intent)
                transfer_denial = _restart_transfer_denial(intent, manifests)
                if transfer_denial is not None:
                    raise transfer_denial
                # Preserve the original guard for an unrelated pending transfer too.
                _verify_files(run, manifest, allow_checkpoint_transaction=True, allow_pending_trace=True)
                receipt = {'schema_version': 1, 'operation_id': intent['operation_id'],
                    'source_run': str(run), 'source_owner_id': manifest['owner_id'],
                    'intent_sha256': intent['intent_sha256'], 'successor_run_dir': intent['successor']['run_dir'],
                    'authority': authority, 'controller': actor, 'reason': reason,
                    'recorded_at': datetime.now(timezone.utc).isoformat()}
                receipt['receipt_sha256'] = _digest(_json_bytes(receipt))
                if len(manifests) == 2:
                    successor, empty, successor_marker = _empty_adoption_successor(intent, manifest)
                    successor_marker = _recover_trace(successor, empty, successor_marker)
                    empty['restart_abandonment'] = receipt
                    empty['operation'] = {'disposition': 'blocked', 'reason': reason,
                        'source': 'abandon-restart', 'phase': 'prepare', 'successor': None}
                    _append_trace(successor, empty, successor_marker, {'kind': 'interruption', 'status': 'completed',
                        'summary': 'Empty adoption successor explicitly abandoned: ' + intent['operation_id'],
                        'actor': actor['identity'], 'authority': authority, 'evidence': ['cierre.json'],
                        'provenance': {'kind': 'helper', 'source': 'review_artifacts:abandon-restart'}})
        return _finish_restart_abandonment(intent_path, intent, run, receipt)



def _action(name, reason):
    return {'action': name, 'reason': reason}

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

def _observation(manifest):
    """Exclude mutable trace metadata so an exact replay retains its identity."""
    return {key: copy.deepcopy(manifest.get(key)) for key in (
        'run_id', 'owner_id', 'repository_key', 'state', 'operation', 'profile_history',
        'resource_claims', 'resource_transfers', 'resource_transfer', 'resource_cleanup',
        'cleanup_receipts', 'temporary_paths', 'assignment_registry', 'executors',
        'checkpoint', 'checkpoint_transaction', 'pending_hashes', 'planned_hashes')}

def _receipt(event, run):
    decision = json.loads(event['summary'][len(PREFIX):])
    return dict(decision, status='recorded', transaction_pending=True, run_dir=str(run),
                event_id=event['event_id'], recorded_at=event['recorded_at'],
                authority=event['authority'], controller=event['actor'],
                receipt_sha256=event['sha256'])

def _sessions(paths, manifests):
    """A durable claim cannot be downgraded to unclaimed by a missing sidecar."""
    key = lambda path: os.path.normcase(str(safe_path(path)))
    committed = {key(row['session_dir']) for manifest in manifests
                 for row in manifest.get('resource_claims', [])
                 if row.get('status') in {'owned', 'releasing', 'transferred'}}
    committed.update(key(item['session_dir']) for manifest in manifests
                     for transfer in normalize_transfer_history(manifest)
                     for item in transfer['items'])
    result = []
    for raw in paths:
        session = safe_path(raw)
        present = session.exists()
        sidecar = safe_path(session / resource_claims.CLAIM_NAME)
        if present:
            workspace = resource_claims.inspect_workspace(session)
            if workspace is None:
                raise ValueError('selected session ownership is unverifiable; preserve it before recording a refusal')
            current = read_json(sidecar) if sidecar.exists() else None
            if current is None or current.get('status') == 'bootstrap':
                if key(session) in committed:
                    raise ValueError('committed session ownership sidecar is missing or downgraded; preserve it before recording a refusal')
                if current is not None:
                    resource_claims.preflight_unbound(session, manifests[0])
            else:
                resource_claims.validate_sidecar(current, *workspace)
        result.append({'session_dir': str(session), 'present': present,
                       'claim_sha256': _digest(sidecar.read_bytes()) if sidecar.exists() else None})
    return result


def record_restart_refusal(run_dir, *, intent_path, controller, authority, reason):
    authority = resource_claims.normalize_authority(authority)
    reason = _bounded_text(reason, 'refusal reason')
    with _restart_lock(run_dir):
        run, manifest, marker = _load_run(run_dir)
        if manifest.get('schema_version') != ARCHIVE_SCHEMA_VERSION or manifest['state'] in {'complete', 'retaining', 'closing'}:
            raise ValueError('recording a refusal requires a non-final native archive source')
        active = _active_restart_operation(run, manifest)
        path = safe_path(intent_path)
        if active is None or str(path) != active['intent_path']:
            raise ValueError('refusal requires the exact active restart intent; no archive scan or reconstruction is allowed')
        intent = _read_restart_intent(path, run, manifest)
        actor = _controller(controller, intent['request']['controller']['identity'])
        successor = safe_path(intent['successor']['run_dir'])
        with ExitStack() as stack:
            if (successor / 'cierre.json').exists():
                stack.enter_context(run_locks([successor]))
            stack.enter_context(resource_claims.session_claim_locks(intent['request']['transfer_paths']))
            manifests = _restart_resource_manifests(run, manifest, intent)
            sessions = _sessions( intent['request']['transfer_paths'], manifests)
            route = _restart_resource_exit(run, manifest, active)
            denial = (route or {}).get('recovery', {}).get('cancellation_denial')
            if denial is None or route['cancellation_supported']:
                raise ValueError('this restart has no verified resource cancellation refusal to record')
            # The source, reserved successor and every present owner were verified
            # read-only by the route above while holding their coordination locks.
            # Record only identities/hashes, never recover another review's work.
            states = {'source': _observation(manifest), 'successor':
                      _observation(manifests[1]) if len(manifests) > 1 else None, 'sessions': sessions}
            observation = _digest(_json_bytes(states))
            decision = {'decision': 'refused', 'phase': denial['phase'], 'reason': reason,
                'cancellation_reason': denial['reason'],
                'operation_id': intent['operation_id'], 'intent_sha256': intent['intent_sha256'],
                'observation_sha256': observation}
            identity = dict(decision, authority=authority, controller=actor)
            decision['refusal_id'] = 'RF-' + _digest(_json_bytes(identity))[:32]
            summary = PREFIX + json.dumps(decision, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
            evidence = ['cierre.json', str(path),
                'resource-observation-sha256:' + observation,
                'source-resource-state-sha256:' + _digest(_json_bytes(states['source'])),
                'successor-resource-state-sha256:' + _digest(_json_bytes(states['successor'])),
                'session-ownership-state-sha256:' + _digest(_json_bytes(states['sessions']))]
            event = {'kind': 'interruption', 'status': 'blocked', 'summary': summary,
                'actor': actor['identity'], 'authority': authority, 'evidence': evidence,
                'occurred_at': datetime.now(timezone.utc).isoformat(),
                'provenance': {'kind': 'helper', 'source': 'review_artifacts:record-restart-refusal'}}
            review_trace.event_input(event, helper=True)  # Bound every input before any write.
            marker = _recover_trace(run, manifest, marker)
            events = [json.loads(line) for line in (run / review_trace.NAME).read_bytes().splitlines()]
            matches = [row for row in events if row['summary'] == summary
                       and row['provenance'] == event['provenance']]
            if matches:
                if len(matches) != 1 or matches[0]['actor'] != actor['identity'] or matches[0]['authority'] != authority:
                    raise ValueError('recorded refusal identity or authority differs from this exact observation')
                return _receipt(matches[0], run)
            _append_trace(run, manifest, marker, event)
            events = [json.loads(line) for line in (run / review_trace.NAME).read_bytes().splitlines()]
            return _receipt(events[-1], run)
