"""Synthetic schema-12 records and retained execution sources."""
import copy

from recovery_fixtures import context10, selection, source_events
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


def historical_fixture12(profile='deep', verification=1):
    count = 2 if profile == 'deep' else 3
    ids = ['V-previa'] + ([] if verification == 0 else
          ['V1'] if verification == 1 else ['V-candidatos', 'V-invariantes'])
    value = record12(profile, 'automatic', discovery=count, verification=len(ids), verification_ids=ids)
    execution = value['coverage']['execution']
    if profile == 'extended':
        first = selection('deep', 'automatic')
        second = selection('extended', 'explicit', id='S002', changed_from='deep',
                           reference='evidence/context.json#profile_history/1/profile',
                           event_id='E000002', phase='discovery', authority='Synthetic approval')
        execution['profile_history'] = [first, second]
        for row in execution['plan']:
            if row['id'] not in ('D1', 'D2', 'V-previa'):
                row['selection_id'] = 'S002'
    context, events, references = source_fixture12(value)
    original_events = events
    by_ref = {row['id']: row['reference'] for row in execution['plan']}
    def pair(identifier):
        return [event for event in original_events if by_ref[identifier] in event.get('evidence', [])]
    first_profile = [event for event in events if event.get('event_id') == 'E000001']
    second_profile = [event for event in events if event.get('event_id') == 'E000002'] if profile == 'extended' else []
    events = first_profile + pair('D1') + pair('V-previa') + pair('D2') + second_profile
    if profile == 'extended':
        events += pair('D3')
    for identifier in ids[1:]:
        events += pair(identifier)
    for index, event in enumerate(events, 1):
        event['sequence'] = index
        if event['kind'] != 'profile':
            event['event_id'] = f'E{index+100:06d}'
    return value, context, events, references
