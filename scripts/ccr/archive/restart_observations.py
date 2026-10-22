"""Read-only observations for restart recovery and resource ownership."""
import hashlib
import json
import os
from pathlib import Path

from ccr.archive import trace as review_trace
from ccr.archive.integrity import _trace_recovery_plan, verify_files as _verify_files
from ccr.archive.intent_contracts import (
    _validate_restart_abandonment_value, normalize_transfer_history,
)
from ccr.archive.reader import MARKER, load_run as _load_run
from ccr.archive.restart_state import (
    _active_restart_operation, _restart_abandonment_path, _validate_restart_abandonment,
)
from ccr.execution import claims as resource_claims
from ccr.shared.json_io import read_json
from ccr.shared.paths import safe_path
from ccr.workflow.profiles import initial_selection as _initial_selection


def _digest(data):
    return hashlib.sha256(data).hexdigest()


class _RestartCancellationUnavailable(ValueError):
    """Verified state which the conservative cancellation protocol cannot unwind."""

    def __init__(self, message, *, phase='successor_work'):
        super().__init__(message)
        self.phase = phase

    def diagnostic(self):
        return {'decision': 'refused', 'phase': self.phase, 'reason': str(self),
                'transaction_pending': True, 'resource_obligations_preserved': True}

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

def _restart_operation_row(intent):
    return {'operation_id': intent['operation_id'], 'request_sha256': intent['request_sha256'],
            'intent_sha256': intent['intent_sha256'], 'source_run': intent['source']['run_dir'],
            'source_owner_id': intent['source']['owner_id'],
            'reservation_id': intent['successor']['reservation_id']}

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

def resource_availability(run, manifest, *, verify_owned=True):
    """One classifier for inspection and mutation gates; absence is not release."""
    claims = {row['session_dir']: row for row in manifest.get('resource_claims', [])}
    receipts = {row['claim_id'] for row in manifest.get('cleanup_receipts', [])}
    resources = []
    for raw in manifest.get('temporary_paths', []):
        path = safe_path(raw)
        row = claims.get(raw, {})
        present, status = path.exists(), row.get('status')
        if status in {'owned', 'releasing'} and present and verify_owned:
            resource_claims.verify_claim(path, run)
        if status == 'transferred':
            availability = 'transferred'
        elif status == 'released':
            availability = 'unexpected_present' if present else 'released'
        elif status in {'owned', 'releasing'}:
            availability = ('cleanup_pending' if status == 'releasing' else 'available') if present else (
                'released' if row.get('claim_id') in receipts else 'missing_unknown')
        else:
            availability = 'available' if present else 'missing_unclaimed'
        resources.append({'path': raw, 'present': present, 'claim_status': status, 'availability': availability})
    return resources
