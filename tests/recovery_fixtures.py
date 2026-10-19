"""Shared synthetic data for profile lifecycle and recovery tests."""
import copy
import json

from test_review_execution_policy import record8, source_fixture


def selection(profile='focused', source='automatic', **updates):
    value = {
        'id': 'S001',
        'profile': profile,
        'selection_source': source,
        'reason': 'Bounded synthetic review selection',
        'reference': 'evidence/context.json#profile',
        'phase': 'prepare',
        'actor': {'kind': 'coordinator', 'name': 'coordinator', 'provider_id': None},
        'authority': 'User requested profile' if source == 'explicit' else None,
        'affected_assignments': [],
        'changed_from': None,
        'event_id': 'E000001',
    }
    value.update(updates)
    return value


def selection_input(profile='focused', source='automatic', **updates):
    value = selection(profile, source, **updates)
    for field in ('id', 'changed_from', 'event_id'):
        value.pop(field)
    return value


def record10(profile='focused', source='automatic'):
    value = copy.deepcopy(record8(profile, source))
    value['schema_version'] = 10
    initial = selection(profile, source)
    value['coverage']['execution']['profile_history'] = [initial]
    for row in value['coverage']['execution']['plan']:
        row['selection_id'] = initial['id']
        row['superseded_by'] = None
    return value


def context10(record):
    execution = record['coverage']['execution']
    history = copy.deepcopy(execution['profile_history'])
    try:
        import review_layout
        logical_identity = review_layout.logical_scope(record['scope'])['identity']
    except (ImportError, TypeError, ValueError):
        logical_identity = None
    inputs = {'scope': copy.deepcopy(record['scope']), 'sources': {}, 'source_set_complete': True,
              'description_identity': record.get('description', {}).get('identity'),
              'requirements_identity': None, 'plan_identity': None,
              'configuration_identity': None, 'logical_scope_identity': logical_identity}
    return {
        'profile': record['profile'],
        'selection_source': execution['selection_source'],
        'profile_history': history,
        'profile_reference': history[-1]['reference'],
        'execution_plan': copy.deepcopy(execution['plan']),
        'review_inputs': inputs,
        'executors': [],
    }


def current_inputs(scope, sources=None, *, source_set_complete=False, **identities):
    """Build a bounded caller-verified scope/source identity fixture."""
    value = {'scope': copy.deepcopy(scope), 'sources': copy.deepcopy(sources or {})}
    if source_set_complete is not None:
        value['source_set_complete'] = source_set_complete
    value.update(copy.deepcopy(identities))
    return value


def source_events(record):
    execution = record['coverage']['execution']
    events = []
    for index, row in enumerate(execution['profile_history'], 1):
        events.append({
            'sequence': index,
            'event_id': row['event_id'],
            'kind': 'profile',
            'status': 'selected',
            'evidence': [row['reference']],
        })
    for row in execution['plan']:
        result = next((item for item in execution['results'] if item['assignment_id'] == row['id']), None)
        if result is None:
            continue
        identity = {'name': result['reviewer_context'], 'provider_id': result['provider_id']}
        events.append({
            'sequence': len(events) + 1,
            'event_id': f'E{len(events) + 1:06d}',
            'kind': 'agent',
            'status': 'started',
            'executor': identity,
            'evidence': [row['reference']],
        })
        events.append({
            'sequence': len(events) + 1,
            'event_id': f'E{len(events) + 1:06d}',
            'kind': 'discovery' if row['role'] == 'discovery' else 'grouped-verification',
            'status': 'completed',
            'actor': identity,
            'evidence': [result['reference']],
        })
    return events


def legacy_prepare(artifacts, repo, scope, **kwargs):
    """Create the native archive format for tests that exercise current operations."""
    from pathlib import Path
    version = kwargs.pop('skill_version', '2.13.0')
    harness = kwargs.pop('harness', 'codex')
    kwargs.setdefault('profile_input', selection_input())
    pinned_scope = artifacts.read_json(scope) if isinstance(scope, (str, Path)) else scope
    kwargs.setdefault('current_inputs', current_inputs(pinned_scope, source_set_complete=True))
    return Path(artifacts.prepare(repo, scope, version, harness, **kwargs))


def historical_prepare(artifacts, repo, scope, **kwargs):
    """Create an archive-6 fixture for read-only deprecation tests."""
    from pathlib import Path
    from review_trace import FIELDS, append
    version = kwargs.pop('skill_version', '2.11.0')
    harness = kwargs.pop('harness', 'codex')
    run = Path(artifacts.prepare(repo, scope, version, harness,
                                profile_input=selection_input(), **kwargs))
    manifest = artifacts.read_json(run / 'cierre.json')
    marker = artifacts.read_json(run / artifacts.MARKER)
    event = json.loads((run / 'trazabilidad.jsonl').read_text(encoding='utf-8').splitlines()[0])
    trace_data, descriptor, _ = append(b'', {'run_id': manifest['run_id']},
                                       {key: event[key] for key in FIELDS}, helper=True)
    artifacts.atomic_write(run / 'trazabilidad.jsonl', trace_data)
    manifest['schema_version'] = 6
    manifest['trace'] = descriptor
    manifest['hashes']['trazabilidad.jsonl'] = artifacts._digest(trace_data)
    for field in ('profile_history', 'operation', 'controller', 'checkpoint', 'lineage',
                  'resource_claims', 'resource_transfers', 'assignment_registry', 'review_inputs'):
        manifest.pop(field, None)
    for field in ('layout_version', 'logical_scope', 'logical_scope_input'):
        manifest.pop(field, None)
    marker.pop('logical_scope_sha256', None)
    pinned_scope = manifest['scope']
    hint = pinned_scope['reference'] or pinned_scope['target'] or pinned_scope['snapshot'] or pinned_scope['head']
    if pinned_scope['reference'] and '://' in hint:
        from urllib.parse import urlsplit
        hint = urlsplit(hint).path.rstrip('/').rsplit('/', 1)[-1]
    old_group = artifacts._slug(pinned_scope['mode']) + '-' + artifacts._slug(hint) + '-' + artifacts._digest(
        artifacts._json_bytes(pinned_scope))[:16]
    created = manifest['created_at']
    from datetime import datetime, timezone
    legacy_name = datetime.fromisoformat(created).astimezone(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + manifest['run_id']
    old_run = Path(manifest['archive_root']) / artifacts._repository_group(manifest['repository_identity']) / old_group / legacy_name
    old_run.parent.mkdir(parents=True, exist_ok=True)
    run.rename(old_run)
    marker['run_dir'] = str(old_run)
    artifacts._save_manifest(old_run, manifest, marker)
    return old_run


__all__ = ['selection', 'selection_input', 'record10', 'context10', 'current_inputs',
           'source_events', 'legacy_prepare', 'historical_prepare']
