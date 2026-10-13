"""Read-only inspection and bounded classification for durable review runs."""
import copy
import re
from pathlib import Path


HASH = re.compile(r'[0-9a-f]{64}')


def _artifacts():
    import review_artifacts
    return review_artifacts


def validate_current_inputs(current_inputs, manifest, *, require_same_scope=True, compare_sources=True):
    """Validate caller-verified scope/source identities against pinned archive bytes."""
    artifacts = _artifacts()
    if (not isinstance(current_inputs, dict) or set(current_inputs) != {'scope', 'sources'}
            or not isinstance(current_inputs.get('sources'), dict)
            or len(current_inputs['sources']) > 64):
        raise ValueError('current inputs require exact scope and bounded source hash fields')
    artifacts._scope(current_inputs['scope'])
    if require_same_scope and current_inputs['scope'] != manifest.get('scope'):
        raise ValueError('current scope differs from the pinned review scope; restart is required')
    available = dict(manifest.get('hashes', {}))
    available.update(manifest.get('pending_hashes', {}))
    sources = {}
    for reference, digest in current_inputs['sources'].items():
        if (not isinstance(reference, str) or not reference.strip() or len(reference) > 500
                or any(ord(char) < 32 for char in reference)
                or not isinstance(digest, str) or not HASH.fullmatch(digest)):
            raise ValueError('current source identities must map bounded references to SHA-256 hashes')
        name = reference.split('#', 1)[0]
        if not artifacts._retained_name(name) and not artifacts._pending_file_name(name):
            raise ValueError('current source reference must identify retained or provisional review evidence')
        if compare_sources:
            expected = available.get(name)
            if expected is None:
                raise ValueError('current source has no preserved baseline identity: ' + reference)
            if expected != digest:
                raise ValueError('current source identity differs from preserved evidence: ' + reference)
        sources[reference] = digest
    return {'scope': copy.deepcopy(current_inputs['scope']), 'sources': sources}


def _action(name, reason):
    return {'action': name, 'reason': reason}


def inspect_run(run_dir, *, current_inputs=None):
    """Inspect one explicitly selected run without repairing or changing any file."""
    artifacts = _artifacts()
    run_path = Path(run_dir).absolute()
    base = {'schema_version': 1, 'run_dir': str(run_path), 'run_id': None, 'review_id': None,
            'integrity': {'status': 'invalid', 'errors': []}, 'phase': None,
            'operation': {'disposition': 'unknown'}, 'known_sources': [], 'missing_sources': [],
            'resources': [], 'pending_transaction': [], 'freshness': {'status': 'unknown', 'reasons': []},
            'actions': [_action('preserve', 'Run identity has not been verified.')], 'activity': 'unknown'}
    try:
        run, manifest, marker = artifacts._load_run(run_path)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        base['integrity']['errors'] = [str(exc)[:1000]]
        return base

    operation = copy.deepcopy(manifest.get('operation') or {
        'disposition': 'complete' if manifest.get('state') == 'complete' else 'open',
        'phase': None, 'reason': None, 'source': None, 'successor': None})
    pending = []
    if manifest.get('pending_trace') is not None:
        pending.append({'kind': 'trace_append', 'status': 'pending'})
    if manifest.get('checkpoint_transaction') is not None:
        pending.append({'kind': 'checkpoint', 'status': 'pending'})
    transfer = manifest.get('resource_transfer')
    if isinstance(transfer, dict) and transfer.get('status') != 'complete':
        pending.append({'kind': 'resource_transfer', 'status': 'pending',
                        'transfer_id': transfer.get('transfer_id')})
    if manifest.get('state') == 'retaining':
        pending.append({'kind': 'retention', 'status': 'pending'})
    if manifest.get('state') == 'closing':
        pending.append({'kind': 'closure', 'status': 'pending'})

    errors = []
    try:
        if not manifest.get('pending_trace'):
            artifacts._verify_files(run, manifest, allow_checkpoint_transaction=True,
                                    allow_resource_transfer=True)
        if not manifest.get('pending_trace') and not pending:
            import review_resource_claims
            for claim in manifest.get('resource_claims', []):
                if claim.get('status') == 'owned' and Path(claim['session_dir']).exists():
                    review_resource_claims.verify_claim(claim['session_dir'], run)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        errors.append(str(exc)[:1000])

    known = sorted(set(manifest.get('hashes', {})) | set(manifest.get('pending_hashes', {})))
    missing = [name for name in known if not (run / name).is_file()]
    resources = []
    claim_by_path = {row.get('session_dir'): row for row in manifest.get('resource_claims', [])
                     if isinstance(row, dict)}
    for raw in manifest.get('temporary_paths', []):
        path = Path(raw)
        row = claim_by_path.get(raw, {})
        resources.append({'path': raw, 'present': path.exists(), 'claim_status': row.get('status')})

    freshness = {'status': 'unknown', 'reasons': []}
    if current_inputs is not None:
        try:
            validate_current_inputs(current_inputs, manifest)
            freshness = {'status': 'verified', 'reasons': []}
        except (OSError, ValueError, TypeError, KeyError) as exc:
            reason = str(exc)[:1000]
            freshness = {'status': 'changed' if 'differs' in reason or 'restart is required' in reason else 'unknown',
                         'reasons': [reason]}

    disposition = operation.get('disposition')
    actions = []
    if errors:
        integrity_status = 'invalid'
        actions = [_action('preserve', 'Integrity/source verification failed; do not adopt or rewrite this run.')]
    elif pending:
        integrity_status = 'recoverable'
        actions = [_action('recover', 'A helper-owned transaction is pending; recover its exact recorded inputs first.')]
    else:
        integrity_status = 'verified'
        if disposition == 'paused':
            actions = [_action('resume', 'Continuing a user-paused run requires explicit continuation authority.'),
                       _action('restart', 'A fresh linked run is available if inputs or scope changed.')]
        elif disposition == 'blocked':
            actions = [_action('recover', 'Inspect the recorded blocker and recover only verified helper-owned state.'),
                       _action('restart', 'Start a new linked run if the original sources cannot be verified.')]
        elif disposition == 'superseded':
            actions = [_action('inspect_successor', 'The source run records a successor; inspect that exact run.')]
        elif disposition == 'complete' or manifest.get('state') == 'complete':
            actions = [_action('show', 'The completed report is immutable and may be shown as recorded.'),
                       _action('restart', 'A repeat creates a new linked review ID.')]
        else:
            actions = [_action('continue', 'The run is open; verify current inputs and operation phase before work.'),
                       _action('recover', 'Check for helper-owned state that can be completed from preserved bytes.'),
                       _action('restart', 'A fresh linked run is available if the scope changed.')]

    activity = ('completed' if integrity_status == 'verified'
                and (disposition == 'complete' or manifest.get('state') == 'complete') else 'unknown')
    return {'schema_version': 1, 'run_dir': str(run), 'run_id': manifest.get('run_id'),
            'review_id': 'CR-' + manifest['run_id'],
            'integrity': {'status': integrity_status, 'errors': errors},
            'phase': operation.get('phase') or manifest.get('state'), 'operation': operation,
            'known_sources': known, 'missing_sources': missing, 'resources': resources,
            'pending_transaction': pending, 'freshness': freshness, 'actions': actions,
            'activity': activity}


def main():
    import argparse
    import json
    import sys
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', required=True)
    parser.add_argument('--current-inputs')
    args = parser.parse_args()
    try:
        value = _artifacts().read_json(args.current_inputs) if args.current_inputs else None
        print(json.dumps(inspect_run(args.run_dir, current_inputs=value), ensure_ascii=False, allow_nan=False))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
