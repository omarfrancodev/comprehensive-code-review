"""Durable, explicitly authorized refusals of unsafe restart cancellation.

The receipt is the hash-bound source trace event, committed with the existing
trace transaction. No second journal, ownership transfer or cleanup is implied.
"""
from contextlib import ExitStack
import copy
from datetime import datetime, timezone
import json
import os

from ccr.execution import claims as resource_claims

PREFIX = 'Restart cancellation refusal: '


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


def _sessions(artifacts, paths, manifests):
    """A durable claim cannot be downgraded to unclaimed by a missing sidecar."""
    claims = resource_claims
    key = lambda path: os.path.normcase(str(artifacts.safe_path(path)))
    committed = {key(row['session_dir']) for manifest in manifests
                 for row in manifest.get('resource_claims', [])
                 if row.get('status') in {'owned', 'releasing', 'transferred'}}
    committed.update(key(item['session_dir']) for manifest in manifests
                     for transfer in artifacts.normalize_transfer_history(manifest)
                     for item in transfer['items'])
    result = []
    for raw in paths:
        session = artifacts.safe_path(raw)
        present = session.exists()
        sidecar = artifacts.safe_path(session / claims.CLAIM_NAME)
        if present:
            workspace = claims.inspect_workspace(session)
            if workspace is None:
                raise ValueError('selected session ownership is unverifiable; preserve it before recording a refusal')
            current = artifacts.read_json(sidecar) if sidecar.exists() else None
            if current is None or current.get('status') == 'bootstrap':
                if key(session) in committed:
                    raise ValueError('committed session ownership sidecar is missing or downgraded; preserve it before recording a refusal')
                if current is not None:
                    claims.preflight_unbound(session, manifests[0])  # Validate the actual bootstrap identity.
            else:
                claims.validate_sidecar(current, *workspace)
        result.append({'session_dir': str(session), 'present': present,
                       'claim_sha256': artifacts._digest(sidecar.read_bytes()) if sidecar.exists() else None})
    return result


def record(run_dir, *, intent_path, controller, authority, reason):
    import review_artifacts as artifacts
    claims = resource_claims
    authority = claims.normalize_authority(authority)
    reason = artifacts.review_restart._bounded_text(reason, 'refusal reason')
    with artifacts._restart_lock(run_dir):
        run, manifest, marker = artifacts._load_run(run_dir)
        if manifest.get('schema_version') != artifacts.ARCHIVE_SCHEMA_VERSION or manifest['state'] in {'complete', 'retaining', 'closing'}:
            raise ValueError('recording a refusal requires a non-final native archive source')
        active = artifacts._active_restart_operation(run, manifest)
        path = artifacts.safe_path(intent_path)
        if active is None or str(path) != active['intent_path']:
            raise ValueError('refusal requires the exact active restart intent; no archive scan or reconstruction is allowed')
        intent = artifacts._read_restart_intent(path, run, manifest)
        actor = artifacts._controller(controller, intent['request']['controller']['identity'])
        successor = artifacts.safe_path(intent['successor']['run_dir'])
        with ExitStack() as stack:
            if (successor / 'cierre.json').exists():
                stack.enter_context(artifacts.run_locks([successor]))
            stack.enter_context(claims.session_claim_locks(intent['request']['transfer_paths']))
            manifests = artifacts._restart_resource_manifests(run, manifest, intent)
            sessions = _sessions(artifacts, intent['request']['transfer_paths'], manifests)
            route = artifacts._restart_resource_exit(run, manifest, active)
            denial = (route or {}).get('recovery', {}).get('cancellation_denial')
            if denial is None or route['cancellation_supported']:
                raise ValueError('this restart has no verified resource cancellation refusal to record')
            # The source, reserved successor and every present owner were verified
            # read-only by the route above while holding their coordination locks.
            # Record only identities/hashes, never recover another review's work.
            states = {'source': _observation(manifest), 'successor':
                      _observation(manifests[1]) if len(manifests) > 1 else None, 'sessions': sessions}
            observation = artifacts._digest(artifacts._json_bytes(states))
            decision = {'decision': 'refused', 'phase': denial['phase'], 'reason': reason,
                'cancellation_reason': denial['reason'],
                'operation_id': intent['operation_id'], 'intent_sha256': intent['intent_sha256'],
                'observation_sha256': observation}
            identity = dict(decision, authority=authority, controller=actor)
            decision['refusal_id'] = 'RF-' + artifacts._digest(artifacts._json_bytes(identity))[:32]
            summary = PREFIX + json.dumps(decision, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
            evidence = ['cierre.json', str(path),
                'resource-observation-sha256:' + observation,
                'source-resource-state-sha256:' + artifacts._digest(artifacts._json_bytes(states['source'])),
                'successor-resource-state-sha256:' + artifacts._digest(artifacts._json_bytes(states['successor'])),
                'session-ownership-state-sha256:' + artifacts._digest(artifacts._json_bytes(states['sessions']))]
            event = {'kind': 'interruption', 'status': 'blocked', 'summary': summary,
                'actor': actor['identity'], 'authority': authority, 'evidence': evidence,
                'occurred_at': datetime.now(timezone.utc).isoformat(),
                'provenance': {'kind': 'helper', 'source': 'review_artifacts:record-restart-refusal'}}
            artifacts.review_trace.event_input(event, helper=True)  # Bound every input before any write.
            marker = artifacts._recover_trace(run, manifest, marker)
            events = [json.loads(line) for line in (run / artifacts.review_trace.NAME).read_bytes().splitlines()]
            matches = [row for row in events if row['summary'] == summary
                       and row['provenance'] == event['provenance']]
            if matches:
                if len(matches) != 1 or matches[0]['actor'] != actor['identity'] or matches[0]['authority'] != authority:
                    raise ValueError('recorded refusal identity or authority differs from this exact observation')
                return _receipt(matches[0], run)
            artifacts._append_trace(run, manifest, marker, event)
            events = [json.loads(line) for line in (run / artifacts.review_trace.NAME).read_bytes().splitlines()]
            return _receipt(events[-1], run)
