"""Shared synthetic data for profile lifecycle and recovery tests."""
import copy

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
    return {
        'profile': record['profile'],
        'selection_source': execution['selection_source'],
        'profile_history': history,
        'profile_reference': history[-1]['reference'],
        'executors': [],
    }


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
    """Create a historical run using the current artifact test fixture/API."""
    from pathlib import Path
    version = kwargs.pop('skill_version', '2.11.0')
    harness = kwargs.pop('harness', 'codex')
    return Path(artifacts.prepare(repo, scope, version, harness, **kwargs))


__all__ = ['selection', 'selection_input', 'record10', 'context10', 'source_events', 'legacy_prepare']
