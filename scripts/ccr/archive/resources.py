"""Durable resource claims, transfer and cleanup coordination."""
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import uuid

from ccr.archive.coordination import _locked_run, owned_run_locks
from ccr.archive.integrity import verify_files as _verify_files
from ccr.archive.reader import load_run as _load_run
from ccr.archive.restart_state import _active_restart_operation, _assert_not_restart_abandoned
from ccr.archive.transactions import (
    _append_trace, _milestone, _recover_trace, save_manifest as _save_manifest,
)
from ccr.archive.intent_contracts import (
    CLEANUP_RECEIPT_LIMIT, TRANSFER_HISTORY_LIMIT,
    _validate_transfer_intent, normalize_transfer_history,
)
from ccr.archive.lifecycle import _controller
from ccr.archive.retention import _temporary_manifests
from ccr.execution import claims as resource_claims
from ccr.execution import workspaces as workspace_ops
from ccr.execution.locks import CoordinationError, LockConflictError, run_locks
from ccr.shared.encoding import archive_bytes as _json_bytes
from ccr.shared.json_io import atomic_write
from ccr.shared.paths import safe_path
from ccr.archive import trace as review_trace


def _digest(data):
    return hashlib.sha256(data).hexdigest()

def _store_transfer(manifest, intent):
    rows = normalize_transfer_history(manifest)
    matches = [index for index, row in enumerate(rows) if row['transfer_id'] == intent['transfer_id']]
    if len(matches) > 1:
        raise ValueError('duplicate transfer_id in resource transfer history')
    if matches:
        prior = rows[matches[0]]
        before, after = dict(prior), dict(intent)
        before.pop('status', None)
        before.pop('completed_at', None)
        after.pop('status', None)
        after.pop('completed_at', None)
        if before != after or prior['status'] == 'complete' and intent['status'] != 'complete':
            raise ValueError('resource transfer retry differs from its preserved intent')
        rows[matches[0]] = copy.deepcopy(intent)
    else:
        if len(rows) >= TRANSFER_HISTORY_LIMIT:
            raise ValueError('resource transfer history reached the 64-entry limit')
        if any(row['status'] == 'pending' for row in rows):
            raise ValueError('another resource transfer is already pending for this run')
        rows.append(copy.deepcopy(intent))
    manifest.pop('resource_transfer', None)
    manifest['resource_transfers'] = rows
    return rows

def transfer_resources(source_run, successor_run, paths, *, authority, controller,
                       _restart_operation_id=None):
    """Transfer explicitly selected claimed workspaces under both run locks."""
    source_path, successor_path = safe_path(source_run), safe_path(successor_run)
    selected_raw_paths = [str(safe_path(path)) for path in paths]
    if not selected_raw_paths or len({os.path.normcase(path) for path in selected_raw_paths}) != len(paths):
        raise ValueError('resource transfer requires a nonempty unique explicit path list')
    selected_paths = sorted(selected_raw_paths, key=os.path.normcase)
    authority = resource_claims.normalize_authority(authority)
    _assert_not_restart_abandoned(_load_run(source_path)[1])
    _assert_not_restart_abandoned(_load_run(successor_path)[1])
    with run_locks([source_path, successor_path]), resource_claims.session_claim_locks(selected_paths):
        source, source_manifest, source_marker = _load_run(source_path)
        successor, next_manifest, next_marker = _load_run(successor_path)
        _assert_not_restart_abandoned(source_manifest)
        _assert_not_restart_abandoned(next_manifest)
        active_restart = _active_restart_operation(source, source_manifest)
        if (active_restart is not None
                and active_restart['operation_id'] != _restart_operation_id):
            raise ValueError('a durable restart is pending; recover source ' + str(source)
                             + ' for restart operation ' + active_restart['operation_id'])
        source_marker = _recover_trace(source, source_manifest, source_marker)
        next_marker = _recover_trace(successor, next_manifest, next_marker)
        restarting_checkpoint = active_restart is not None and _restart_operation_id == active_restart['operation_id']
        _verify_files(source, source_manifest, allow_resource_transfer=True,
                      allow_checkpoint_transaction=restarting_checkpoint)
        _verify_files(successor, next_manifest, allow_resource_transfer=True)
        if source == successor:
            raise ValueError('source and successor review runs must differ')
        if (source_manifest.get('schema_version') != 8 or next_manifest.get('schema_version') != 8
                or source_manifest.get('repository_key') != next_manifest.get('repository_key')
                or source_manifest.get('repository_path') != next_manifest.get('repository_path')
                or source_manifest.get('scope') != next_manifest.get('scope')):
            raise ValueError('resource transfer requires archive-8 runs for the same repository and scope')
        for label, value in (('source', source_manifest), ('successor', next_manifest)):
            if value.get('state') not in {'prepared', 'processing'}:
                raise ValueError(label + ' run must be prepared or processing; retaining/closing runs cannot transfer')
        normalized_controller = _controller(controller, next_manifest['controller']['identity'])
        source_history = normalize_transfer_history(source_manifest)
        next_history = normalize_transfer_history(next_manifest)
        pair = [row for row in source_history + next_history
                if row['source_run'] == str(source) and row['successor_run'] == str(successor)]
        by_id = {}
        for row in pair:
            prior = by_id.get(row['transfer_id'])
            if prior is not None:
                left, right = dict(prior), dict(row)
                left.pop('status', None); left.pop('completed_at', None)
                right.pop('status', None); right.pop('completed_at', None)
                if left != right:
                    raise ValueError('source and successor transfer histories conflict')
            else:
                by_id[row['transfer_id']] = row
        if len(by_id) > 1:
            raise ValueError('multiple transfers exist for the same source and successor runs')
        intent = next(iter(by_id.values()), None)
        current_transfer_id = intent['transfer_id'] if intent else None
        for history in (source_history, next_history):
            if any(row['status'] == 'pending' and row['transfer_id'] != current_transfer_id for row in history):
                raise ValueError('another resource transfer is already pending for this run')

        if intent is not None:
            _validate_transfer_intent(intent)
            expected = {'source_run': str(source), 'successor_run': str(successor),
                        'source_run_id': source_manifest['run_id'],
                        'successor_run_id': next_manifest['run_id'],
                        'source_owner_id': source_manifest['owner_id'],
                        'successor_owner_id': next_manifest['owner_id'],
                        'repository_key': source_manifest['repository_key'],
                        'authority': authority, 'controller': normalized_controller}
            if any(intent.get(key) != value for key, value in expected.items()) or \
                    {item['session_dir'] for item in intent['items']} != set(selected_paths):
                raise ValueError('completed or pending transfer request differs from its preserved inputs')
            source_matches = [row for row in source_history if row['transfer_id'] == intent['transfer_id']]
            next_matches = [row for row in next_history if row['transfer_id'] == intent['transfer_id']]
            if (source_matches and next_matches and source_matches[0]['status'] == 'complete'
                    and next_matches[0]['status'] == 'complete'):
                for item in intent['items']:
                    resource_claims.verify_claim(item['session_dir'], successor)
                return {'status': 'transferred', 'transfer_id': intent['transfer_id'],
                        'source_run': str(source), 'successor_run': str(successor),
                        'resources': [item['session_dir'] for item in intent['items']]}
            # A partially persisted completion is replayed using its original bytes.
        else:
            if source_manifest.get('state') in {'retaining', 'closing', 'complete'} or \
                    next_manifest.get('state') in {'retaining', 'closing', 'complete'}:
                raise ValueError('retaining, closing or complete review runs cannot transfer resources')
            if source_manifest.get('operation', {}).get('disposition') not in {'open', 'paused', 'blocked'}:
                raise ValueError('source review is already superseded or complete')
            if next_manifest.get('operation', {}).get('disposition') != 'open':
                raise ValueError('successor review must be open before claiming resources')
            previous = next_manifest.get('previous_run')
            lineage = next_manifest.get('lineage')
            if previous not in (None, str(source)):
                raise ValueError('successor previous_run conflicts with the requested transfer source')
            if not isinstance(lineage, dict) or lineage.get('source_run') not in (None, str(source)):
                raise ValueError('successor lineage conflicts with the requested transfer source')
            if previous == str(source) and (lineage.get('kind') != 'restart' or lineage.get('source_run') != str(source)):
                raise ValueError('successor previous_run and lineage identify different restart sources')

            source_rows = list(source_manifest.get('resource_claims', []))
            in_flight_rows = [row for row in source_rows if row.get('status') == 'releasing']
            if in_flight_rows:
                raise ValueError('resource cleanup is already in progress; recover it before transfer')
            active_rows = [row for row in source_rows if row.get('status') == 'owned']
            active_paths = {os.path.normcase(str(safe_path(row['session_dir']))) for row in active_rows}
            selected_path_keys = {os.path.normcase(str(safe_path(path))) for path in selected_paths}
            if selected_path_keys != active_paths:
                raise ValueError('transfer must include every active resource claim; partial transfer is refused '
                                 '(selected=' + str(len(selected_paths)) + ', active=' + str(len(active_paths)) + ')')
            if len(source_history) >= TRANSFER_HISTORY_LIMIT or len(next_history) >= TRANSFER_HISTORY_LIMIT:
                raise ValueError('resource transfer history reached the 64-entry limit')
            items = []
            registered_source_paths = {os.path.normcase(str(safe_path(path)))
                                       for path in source_manifest.get('temporary_paths', [])}
            for raw in selected_paths:
                if os.path.normcase(str(safe_path(raw))) not in registered_source_paths:
                    raise ValueError('every transferred session must be registered to the source run')
                if not safe_path(raw).is_dir():
                    raise ValueError('every active resource claim must be present before transfer')
                old_sidecar = resource_claims.verify_claim(raw, source,
                    allow_checkpoint_transaction=restarting_checkpoint)
                plan = resource_claims.plan_claim(
                    raw, successor, next_manifest, source_run=source,
                    authority=authority, allow_checkpoint_transaction=restarting_checkpoint)
                if plan['action'] != 'transfer' or old_sidecar['claim_id'] != plan['sidecar']['claim_id']:
                    raise ValueError('resource transfer plan does not match the verified source claim')
                source_rows = [row for row in source_manifest.get('resource_claims', [])
                               if row.get('claim_id') == old_sidecar['claim_id']]
                if len(source_rows) != 1 or source_rows[0].get('status') != 'owned':
                    raise ValueError('source archive does not have one active claim for the session')
                items.append({'session_dir': raw, 'claim_id': old_sidecar['claim_id'],
                              'old_claim_sha256': plan['expected_current_sha256'],
                              'new_claim': plan['sidecar'], 'new_claim_sha256': _digest(plan['bytes'])})
            intent = {'schema_version': 1, 'transfer_id': 'RT-' + uuid.uuid4().hex,
                      'status': 'pending', 'source_run': str(source), 'successor_run': str(successor),
                      'source_run_id': source_manifest['run_id'], 'successor_run_id': next_manifest['run_id'],
                      'source_owner_id': source_manifest['owner_id'],
                      'successor_owner_id': next_manifest['owner_id'],
                      'repository_key': source_manifest['repository_key'], 'authority': authority,
                      'controller': normalized_controller, 'items': items}

        if intent['status'] == 'pending':
            _store_transfer(source_manifest, intent)
            source_marker = _save_manifest(source, source_manifest, source_marker)
            _store_transfer(next_manifest, intent)
            next_marker = _save_manifest(successor, next_manifest, next_marker)

        _validate_transfer_intent(intent)
        for item in intent['items']:
            sidecar_path = safe_path(Path(item['session_dir']) / resource_claims.CLAIM_NAME)
            try:
                current_bytes = sidecar_path.read_bytes()
            except FileNotFoundError as exc:
                raise ValueError('claimed session disappeared during resource transfer') from exc
            current_hash = _digest(current_bytes)
            new_bytes = resource_claims.encode_claim(item['new_claim'])
            if current_hash == item['new_claim_sha256']:
                continue
            if current_hash != item['old_claim_sha256']:
                raise ValueError('resource claim changed after transfer intent; preserve the session')
            atomic_write(sidecar_path, new_bytes)

        transfer_id = intent['transfer_id']
        moved_paths = {item['session_dir'] for item in intent['items']}
        moved_keys = {os.path.normcase(path) for path in moved_paths}
        source_rows = list(source_manifest.get('resource_claims', []))
        next_rows = list(next_manifest.get('resource_claims', []))
        for item in intent['items']:
            old_rows = [row for row in source_rows if row.get('claim_id') == item['claim_id']]
            if len(old_rows) != 1 or old_rows[0].get('session_dir') != item['session_dir']:
                raise ValueError('source archive claim changed during transfer')
            if old_rows[0].get('status') == 'owned':
                old_rows[0].update(status='transferred', transfer_id=transfer_id,
                                   successor_run_id=next_manifest['run_id'])
            elif not (old_rows[0].get('status') == 'transferred'
                      and old_rows[0].get('transfer_id') == transfer_id):
                raise ValueError('source archive claim is not transferable')
            new_row = resource_claims.make_claim_row(
                item['new_claim'], claim_sha256=item['new_claim_sha256'],
                adopted=item['new_claim']['adopted'], authority=item['new_claim']['authority'],
                transferred_from=str(source), transfer_id=transfer_id)
            if not any(row.get('claim_id') == item['claim_id'] for row in next_rows):
                next_rows.append(new_row)
            elif not any(row == new_row for row in next_rows if row.get('claim_id') == item['claim_id']):
                raise ValueError('successor archive already has a different claim for this session')

        source_manifest['resource_claims'] = source_rows
        source_manifest['temporary_paths'] = [path for path in source_manifest.get('temporary_paths', [])
                                              if os.path.normcase(path) not in moved_keys]
        source_manifest['temporary_manifests'] = _temporary_manifests(
            source_manifest['temporary_paths'], source_manifest)
        source_manifest['operation'].update(disposition='superseded', reason=authority,
                                            source='transfer-resources', phase='restart',
                                            successor=str(successor))
        next_manifest['resource_claims'] = next_rows
        combined_paths = list(next_manifest.get('temporary_paths', [])) + sorted(moved_paths)
        unique_paths = {}
        for path in combined_paths:
            unique_paths.setdefault(os.path.normcase(path), path)
        next_manifest['temporary_paths'] = list(unique_paths.values())
        next_manifest['temporary_manifests'] = _temporary_manifests(
            next_manifest['temporary_paths'], next_manifest)
        next_manifest['previous_run'] = next_manifest.get('previous_run') or str(source)
        next_manifest['lineage'] = {'kind': 'restart', 'source_run': str(source)}
        source_marker = _save_manifest(source, source_manifest, source_marker)
        next_marker = _save_manifest(successor, next_manifest, next_marker)

        for run, manifest, marker, other in ((source, source_manifest, source_marker, successor),
                                             (successor, next_manifest, next_marker, source)):
            summary = 'Resource transfer ' + transfer_id + ' to ' + str(successor)
            if run == source:
                summary = 'Resource transfer ' + transfer_id + ' from ' + str(source)
            trace = [json.loads(line) for line in safe_path(run / review_trace.NAME).read_text(
                encoding='utf-8').splitlines()]
            if not any(event.get('kind') == 'handoff' and event.get('summary') == summary for event in trace):
                relation_target = str(other)
                event = {'kind': 'handoff', 'status': 'completed', 'summary': summary,
                         'authority': authority, 'provenance': {'kind': 'helper', 'source': 'review_artifacts:transfer-resources'},
                         'evidence': ['cierre.json'],
                         'relations': [{'relation': 'supersedes', 'target': relation_target}]}
                marker = _append_trace(run, manifest, marker, event)
            if run == source:
                source_marker = marker
            else:
                next_marker = marker

        completed = copy.deepcopy(intent)
        if completed['status'] != 'complete':
            completed['status'] = 'complete'
            completed['completed_at'] = datetime.now(timezone.utc).isoformat()
        _store_transfer(source_manifest, completed)
        _store_transfer(next_manifest, completed)
        _save_manifest(source, source_manifest, source_marker)
        _save_manifest(successor, next_manifest, next_marker)
        return {'status': 'transferred', 'transfer_id': transfer_id,
                'source_run': str(source), 'successor_run': str(successor),
                'resources': sorted(moved_paths)}

def _cleanup_identity(intent):
    return {key: intent[key] for key in ('session_id', 'run_id', 'claim_id', 'claim_sha256')}

def _cleanup_rows(manifest, claim_id):
    return [row for row in manifest.get('resource_claims', [])
            if isinstance(row, dict) and row.get('claim_id') == claim_id]

def _cleanup_resources_remain(intent):
    repo = safe_path(intent['repository_path'])
    registered = {str(path.resolve()) for path in workspace_ops.registrations(repo)}
    for raw in intent['worktrees']:
        path = safe_path(raw)
        if str(path) in registered or path.exists():
            return True
    return safe_path(intent['session_dir']).exists()

def begin_resource_cleanup(run_dir, session_dir):
    """Persist a cleanup intent and mark the exact workspace claim as releasing."""
    run, manifest, marker = _load_run(run_dir)
    marker = _recover_trace(run, manifest, marker)
    _verify_files(run, manifest, allow_checkpoint_transaction=
                  manifest.get('operation', {}).get('disposition') == 'superseded')
    if manifest.get('schema_version') != 8:
        raise ValueError('durable resource cleanup requires archive schema 8')
    if manifest.get('state') in {'retaining', 'complete'}:
        raise ValueError('resource cleanup cannot begin during retention or after closure')
    if manifest.get('operation', {}).get('disposition') == 'complete':
        raise ValueError('completed review cannot begin resource cleanup')
    session = safe_path(session_dir)
    if not session.exists() or not session.is_dir():
        raise ValueError('cleanup requires the existing claimed session directory')
    sidecar = resource_claims.verify_claim(session, run)
    rows = _cleanup_rows(manifest, sidecar['claim_id'])
    if len(rows) != 1:
        raise ValueError('cleanup requires one exact durable resource claim')
    row = rows[0]
    if row.get('status') not in {'owned', 'releasing'}:
        raise ValueError('resource claim is not active for cleanup')
    intent = manifest.get('resource_cleanup')
    if isinstance(intent, dict) and intent.get('status') == 'pending':
        if (_cleanup_identity(intent) == {
                'session_id': sidecar['session_id'], 'run_id': manifest['run_id'],
                'claim_id': sidecar['claim_id'], 'claim_sha256': resource_claims.digest_claim(
                    resource_claims.encode_claim(sidecar))}
                and intent.get('session_dir') == str(session)):
            return copy.deepcopy(intent)
        raise ValueError('another resource cleanup is pending; recover it before starting cleanup')
    receipts = manifest.get('cleanup_receipts', [])
    if len(receipts) >= CLEANUP_RECEIPT_LIMIT:
        raise ValueError('resource cleanup receipt history reached the 64-entry limit')
    if any(receipt.get('claim_id') == sidecar['claim_id'] for receipt in receipts):
        raise ValueError('resource claim already has a durable cleanup receipt')
    if row.get('status') != 'owned':
        raise ValueError('releasing resource claim has no matching pending cleanup intent')

    workspace_data = resource_claims.inspect_workspace(session)
    if workspace_data is None:
        raise ValueError('cleanup requires a valid owned workspace session')
    workspace = workspace_data[1]
    registered = {str(path.resolve()) for path in workspace_ops.registrations(safe_path(workspace['repo']))}
    worktrees = []
    for entry in workspace['workspaces']:
        path = safe_path(entry['path'])
        if path.exists() and str(path) not in registered:
            raise ValueError('workspace is no longer registered; preserve and inspect it: ' + str(path))
        if str(path) in registered:
            worktrees.append(str(path))
    if len(worktrees) > 32:
        raise ValueError('cleanup worktree inventory exceeds the 32-entry limit')
    claim_hash = resource_claims.digest_claim(resource_claims.encode_claim(sidecar))
    intent = {'schema_version': 1, 'operation_id': 'CL-' + uuid.uuid4().hex,
              'status': 'pending', 'run_id': manifest['run_id'], 'session_id': sidecar['session_id'],
              'claim_id': sidecar['claim_id'], 'claim_sha256': claim_hash,
              'session_dir': str(session), 'repository_path': str(safe_path(workspace['repo'])),
              'worktrees': worktrees, 'started_at': datetime.now(timezone.utc).isoformat(),
              'completed_at': None, 'completion_source': None}
    row['status'] = 'releasing'
    manifest['resource_cleanup'] = intent
    _append_trace(run, manifest, marker, _milestone('cleanup',
                  'Cleanup started for a verified claimed review workspace', status='started',
                  evidence=['cierre.json#resource_cleanup']))
    return copy.deepcopy(intent)

def _finish_resource_cleanup_locked(run, manifest, marker, observation, *, completion_source):
    intent = manifest.get('resource_cleanup')
    if not isinstance(intent, dict):
        raise ValueError('no durable resource cleanup intent exists')
    fields = {'operation_id', 'run_id', 'session_id', 'claim_id', 'claim_sha256'}
    if not isinstance(observation, dict) or set(observation) != fields:
        raise ValueError('cleanup completion must identify its exact durable operation and claim')
    expected = {'operation_id': intent['operation_id'], **_cleanup_identity(intent)}
    if observation != expected:
        raise ValueError('cleanup completion differs from the durable cleanup intent')
    if intent['status'] == 'complete':
        receipt = {key: intent[key] for key in ('session_id', 'run_id', 'claim_id', 'claim_sha256')}
        if receipt not in manifest.get('cleanup_receipts', []):
            raise ValueError('completed cleanup has no durable matching receipt')
        return {'status': 'released', 'receipt': receipt, 'operation_id': intent['operation_id']}
    if intent['status'] != 'pending':
        raise ValueError('unknown resource cleanup state')
    if _cleanup_resources_remain(intent):
        raise ValueError('cleanup cannot be completed while its session or registered worktrees remain')
    rows = _cleanup_rows(manifest, intent['claim_id'])
    if len(rows) != 1 or rows[0].get('status') != 'releasing':
        raise ValueError('cleanup intent no longer matches one releasing resource claim')
    receipt = {key: intent[key] for key in ('session_id', 'run_id', 'claim_id', 'claim_sha256')}
    receipts = manifest.setdefault('cleanup_receipts', [])
    existing = [row for row in receipts if row.get('claim_id') == intent['claim_id']]
    if existing and existing != [receipt]:
        raise ValueError('resource cleanup retry conflicts with a different durable receipt')
    if not existing:
        if len(receipts) >= CLEANUP_RECEIPT_LIMIT:
            raise ValueError('resource cleanup receipt history reached the 64-entry limit')
        receipts.append(receipt)
    rows[0].update(status='released', released_by=completion_source,
                   release_claim_sha256=intent['claim_sha256'])
    intent.update(status='complete', completed_at=datetime.now(timezone.utc).isoformat(),
                   completion_source=completion_source)
    _append_trace(run, manifest, marker, _milestone('cleanup',
                  'Verified workspace cleanup and recorded its release receipt', status='completed',
                  evidence=['cierre.json#cleanup_receipts']))
    return {'status': 'released', 'receipt': receipt, 'operation_id': intent['operation_id']}

def finish_resource_cleanup(run_dir, observation):
    """Record a receipt only after the exact session and its worktrees are absent."""
    run, manifest, marker = _load_run(run_dir)
    marker = _recover_trace(run, manifest, marker)
    _verify_files(run, manifest, allow_checkpoint_transaction=
                  manifest.get('operation', {}).get('disposition') == 'superseded')
    if manifest.get('schema_version') != 8:
        raise ValueError('durable resource cleanup requires archive schema 8')
    return _finish_resource_cleanup_locked(run, manifest, marker, observation,
                                           completion_source='workspace_ops.cleanup')

def recover_resource_cleanup(run_dir):
    """Finish a pending cleanup record only when its exact resources are already absent."""
    run, manifest, marker = _load_run(run_dir)
    marker = _recover_trace(run, manifest, marker)
    _verify_files(run, manifest, allow_checkpoint_transaction=
                  manifest.get('operation', {}).get('disposition') == 'superseded')
    if manifest.get('schema_version') != 8:
        raise ValueError('durable resource cleanup requires archive schema 8')
    intent = manifest.get('resource_cleanup')
    if intent is None:
        return {'status': 'none', 'run_id': manifest['run_id']}
    if intent['status'] == 'complete':
        receipt = {key: intent[key] for key in ('session_id', 'run_id', 'claim_id', 'claim_sha256')}
        return {'status': 'released', 'receipt': receipt, 'operation_id': intent['operation_id']}
    if intent['status'] != 'pending':
        raise ValueError('unknown durable resource cleanup status')
    session = safe_path(intent['session_dir'])
    if session.exists():
        sidecar = resource_claims.verify_claim(session, run)
        if (sidecar.get('session_id') != intent['session_id']
                or sidecar.get('claim_id') != intent['claim_id']
                or resource_claims.digest_claim(resource_claims.encode_claim(sidecar))
                != intent['claim_sha256']):
            raise ValueError('pending cleanup session differs from the exact verified cleanup intent')
    if _cleanup_resources_remain(intent):
        return {'status': 'pending', 'operation_id': intent['operation_id'],
                'reason': 'The recorded session or one of its worktrees still exists; retry workspace cleanup.'}
    observation = {'operation_id': intent['operation_id'], **_cleanup_identity(intent)}
    return _finish_resource_cleanup_locked(run, manifest, marker, observation,
                                           completion_source='review_artifacts.recovery')


def record_artifact(args):
    """Serialize artifact registration with any concurrent claim or cleanup."""
    manifest = workspace_ops.load(args.manifest)
    try:
        with resource_claims.session_claim_locks([manifest['session_dir']]):
            return workspace_ops.record_artifact(args)
    except LockConflictError as exc:
        raise workspace_ops.ReviewError(
            'Artifact registration lock conflict; preserve the session and retry: ' + str(exc)) from exc
    except CoordinationError as exc:
        raise workspace_ops.ReviewError(
            'Artifact registration failed; preserve the session: ' + str(exc)) from exc


def cleanup_workspace(args):
    """Coordinate validation, durable intent, physical removal, and receipt completion."""
    manifest = workspace_ops.load(args.manifest)
    session = Path(manifest['session_dir'])
    try:
        with resource_claims.session_claim_locks([session]):
            claim_path = session / resource_claims.CLAIM_NAME
            claim = None
            if claim_path.exists():
                workspace_ops.no_links(claim_path)
                claim = resource_claims.read_claim(claim_path)
            if isinstance(claim, dict) and claim.get('status') == 'owned':
                run_dir = getattr(args, 'run_dir', None)
                if not run_dir:
                    raise workspace_ops.ReviewError(
                        'Cleaning a claimed session requires its owning --run-dir')
                run_path = safe_path(run_dir)
                try:
                    with owned_run_locks([run_path]):
                        try:
                            verified = resource_claims.verify_claim(session, run_path)
                        except (OSError, ValueError, KeyError, TypeError) as exc:
                            raise workspace_ops.ReviewError(
                                'Could not verify workspace claim ownership; preserve the session: '
                                + str(exc)) from exc
                        if verified.get('claim_id') != claim.get('claim_id'):
                            raise workspace_ops.ReviewError(
                                'The requested run does not own this session claim')
                        plan = workspace_ops.plan_cleanup(args, manifest, claim=claim)
                        try:
                            intent = begin_resource_cleanup(run_path, session)
                        except (OSError, ValueError, KeyError, TypeError) as exc:
                            raise workspace_ops.ReviewError(
                                'Could not record durable cleanup intent; preserve the session: '
                                + str(exc)) from exc
                        result = workspace_ops.remove_workspaces(plan)
                        observation = {key: intent[key] for key in (
                            'operation_id', 'run_id', 'session_id', 'claim_id', 'claim_sha256')}
                        try:
                            released = finish_resource_cleanup(run_path, observation)
                        except (OSError, ValueError, KeyError, TypeError) as exc:
                            raise workspace_ops.ReviewError(
                                'Workspace was removed but durable cleanup completion is pending recovery: '
                                + str(exc)) from exc
                        result['released_claims'] = [released['receipt']]
                        return result
                except LockConflictError as exc:
                    raise workspace_ops.ReviewError(
                        'Review archive cleanup lock conflict; preserve the session and retry: '
                        + str(exc)) from exc
                except CoordinationError as exc:
                    raise workspace_ops.ReviewError(
                        'Review archive cleanup failed; preserve the session: ' + str(exc)) from exc
            if getattr(args, 'run_dir', None):
                raise workspace_ops.ReviewError(
                    '--run-dir is only valid for a session with an active review claim')
            plan = workspace_ops.plan_cleanup(args, manifest)
            return workspace_ops.remove_workspaces(plan)
    except LockConflictError as exc:
        raise workspace_ops.ReviewError(
            'Workspace cleanup lock conflict; preserve the session and retry: ' + str(exc)) from exc
    except CoordinationError as exc:
        raise workspace_ops.ReviewError(
            'Workspace cleanup failed; preserve the session: ' + str(exc)) from exc
