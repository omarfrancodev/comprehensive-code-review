"""Synthetic schema-12 records and retained execution sources."""
import copy

from recovery_fixtures import context10, source_events
from traceability_fixtures import record11


def record12(profile='deep', source='explicit', discovery=2, verification=1,
             verification_ids=None):
    value = copy.deepcopy(record11(profile, source))
    execution = value['coverage']['execution']
    ids = verification_ids if verification_ids is not None else [
        f'V{i}' for i in range(1, verification + 1)]
    if len(ids) != verification:
        raise ValueError('verification_ids must match verification count')
    plan = []
    for role, identifiers in (('discovery', [f'D{i}' for i in range(1, discovery + 1)]),
                              ('verification', ids)):
        for identifier in identifiers:
            independent = profile in ('deep', 'extended') if role == 'discovery' else profile != 'focused'
            plan.append(dict(id=identifier, role=role, independent=independent,
                             required=True, reference=f'evidence/briefs.json#{identifier}',
                             selection_id='S001', superseded_by=None))
    execution['plan'] = plan
    execution['results'] = [
        dict(assignment_id=row['id'],
             reviewer_context=row['id'] if row['independent'] else 'coordinator',
             provider_id=None, reference=f"evidence/results.json#{row['id']}")
        for row in plan
    ]
    value['schema_version'] = 12
    value['coverage']['verification'] = (
        'skipped' if not verification else 'same_session' if profile == 'focused'
        else 'independent')
    return value


def source_fixture12(record):
    execution = record['coverage']['execution']
    context = context10(record)
    events = source_events(record)
    references = {row['reference'] for row in execution['profile_history']}
    references.update(row['reference'] for row in execution['plan'])
    references.update(row['reference'] for row in execution['results'])
    for fallback in execution['fallbacks']:
        references.add(fallback['source'])
        sequence = len(events) + 1
        events.append(dict(sequence=sequence, event_id=f'E{sequence:06d}',
                           kind='interruption', status='blocked',
                           evidence=[fallback['source']]))
    return context, events, references
