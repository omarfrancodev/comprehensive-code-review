"""Pure profile-history and schema-10 obligation validation."""
import copy
import re


ALIASES = {'economy': 'focused', 'balanced': 'standard'}
PROFILES = {'focused', 'standard', 'deep', 'extended'}
PHASES = {'prepare', 'discovery', 'verification', 'report', 'retain', 'cleanup', 'close'}
SELECTION_FIELDS = {'id', 'profile', 'selection_source', 'reason', 'reference', 'phase',
                    'actor', 'authority', 'affected_assignments', 'changed_from', 'event_id'}
INPUT_FIELDS = SELECTION_FIELDS - {'id', 'changed_from', 'event_id'}
MAX_HISTORY = 32


def _text(value, limit=4000):
    return isinstance(value, str) and bool(value.strip()) and len(value) <= limit and not any(ord(char) < 32 for char in value)


def _canonical(profile):
    if not isinstance(profile, str):
        raise ValueError('profile must be supported text')
    value = ALIASES.get(profile, profile)
    if value not in PROFILES:
        raise ValueError('profile must be focused, standard, deep or extended')
    return value


def _same_decision(raw, previous):
    return all(raw.get(field) == previous.get(field) for field in INPUT_FIELDS)


def validate_selection(raw: dict, previous: dict | None = None) -> dict:
    """Normalize a selection without mutating input or replacing an identical first capture."""
    if not isinstance(raw, dict) or set(raw) - SELECTION_FIELDS or not INPUT_FIELDS.issubset(raw):
        raise ValueError('selection requires the exact profile, source, reason, reference, phase, actor, authority and affected assignments fields')
    value = copy.deepcopy(raw)
    value['profile'] = _canonical(value['profile'])
    if value['selection_source'] not in ('explicit', 'automatic'):
        raise ValueError('selection_source must be explicit or automatic')
    if not _text(value['reason']) or not _text(value['reference'], 500):
        raise ValueError('selection reason and reference must be nonempty bounded text')
    if value['phase'] not in PHASES:
        raise ValueError('invalid selection phase')
    if not isinstance(value['actor'], dict) or set(value['actor']) != {'kind', 'name', 'provider_id'}:
        raise ValueError('selection actor must preserve the trace identity shape')
    actor = value['actor']
    if actor['kind'] not in {'helper', 'coordinator', 'agent', 'tool'} or not _text(actor['name'], 160):
        raise ValueError('invalid selection actor identity')
    if actor['provider_id'] is not None and not _text(actor['provider_id'], 160):
        raise ValueError('invalid selection actor provider ID')
    if value['authority'] is not None and not _text(value['authority'], 1000):
        raise ValueError('authority must be bounded text or null')
    affected = value['affected_assignments']
    if not isinstance(affected, list) or len(affected) > 64 or any(not _text(item, 160) for item in affected):
        raise ValueError('affected_assignments must be a bounded list of assignment IDs')
    if len(set(affected)) != len(affected):
        raise ValueError('affected_assignments contains duplicate IDs')

    if previous is not None:
        if not isinstance(previous, dict) or set(previous) != SELECTION_FIELDS:
            raise ValueError('previous selection has an invalid shape')
        if _same_decision(value, previous):
            return copy.deepcopy(previous)
        old_profile = _canonical(previous.get('profile'))
        if value['profile'] != old_profile:
            if previous.get('selection_source') == 'explicit' and (
                    value['selection_source'] != 'explicit' or value['authority'] is None):
                raise ValueError('an explicit profile transition requires a later explicit user source')
            if value['selection_source'] == 'explicit' and value['authority'] is None:
                raise ValueError('an explicit profile transition requires user authority')
    return value


def validate_history(history: list[dict]) -> list[str]:
    """Validate immutable selection IDs, links, first-selection identity, and bounds."""
    errors = []
    if not isinstance(history, list) or not history:
        return ['profile history must be a nonempty array']
    if len(history) > MAX_HISTORY:
        errors.append(f'profile history exceeds maximum {MAX_HISTORY} selections')
    seen_ids, seen_events = set(), set()
    previous = None
    for index, row in enumerate(history):
        prefix = f'profile_history[{index}]'
        if not isinstance(row, dict) or set(row) != SELECTION_FIELDS:
            errors.append(prefix + ': exact selection fields required')
            continue
        try:
            normalized = validate_selection({key: row[key] for key in INPUT_FIELDS})
        except (ValueError, KeyError) as exc:
            errors.append(prefix + ': ' + str(exc))
            continue
        expected_id = f'S{index + 1:03d}'
        if row['id'] != expected_id:
            errors.append(prefix + f': expected selection ID {expected_id}')
        if row['profile'] != normalized['profile']:
            errors.append(prefix + ': retained profile names must be canonical')
        if row['id'] in seen_ids:
            errors.append('profile history contains duplicate selection identity')
        seen_ids.add(row['id'])
        if not isinstance(row['event_id'], str) or not re.fullmatch(r'E[0-9]{6,}', row['event_id']):
            errors.append(prefix + ': invalid profile event ID')
        if row['event_id'] in seen_events:
            errors.append(prefix + ': duplicate profile event ID')
        seen_events.add(row['event_id'])
        if index == 0:
            if row['changed_from'] is not None or row['phase'] != 'prepare':
                errors.append('initial profile selection must be S001, have no predecessor and use prepare phase')
            if row['affected_assignments']:
                errors.append('initial profile selection cannot affect assignments before they exist')
        else:
            if previous is not None and row['changed_from'] != previous['profile']:
                errors.append(prefix + ': changed_from must preserve the prior profile')
            if row['phase'] == 'prepare':
                errors.append(prefix + ': later profile transitions cannot use prepare phase')
            if previous is not None:
                try:
                    validate_selection({key: row[key] for key in INPUT_FIELDS}, previous=previous)
                except ValueError as exc:
                    errors.append(prefix + ': ' + str(exc))
        previous = normalized | {key: row.get(key) for key in ('id', 'changed_from', 'event_id')}
    return errors


def validate_profile_execution(record: dict, trace_events: list[dict] | None = None) -> list[str]:
    """Validate schema-10 history linkage and obligations that cannot be downgraded away."""
    if not isinstance(record, dict) or record.get('schema_version') != 10:
        return []
    coverage = record.get('coverage')
    execution = coverage.get('execution') if isinstance(coverage, dict) else None
    if not isinstance(execution, dict):
        return ['coverage.execution.profile_history: execution object required']
    history = execution.get('profile_history')
    errors = validate_history(history)
    if errors:
        return ['coverage.execution.' + item for item in errors]
    prefix = 'coverage.execution.profile_history: '
    if history[-1]['profile'] != record.get('profile'):
        errors.append(prefix + 'last selection must match final profile')
    if history[0]['selection_source'] != execution.get('selection_source'):
        errors.append(prefix + 'selection_source must preserve the initial selection')
    by_selection = {row['id']: row for row in history}
    plan = execution.get('plan') if isinstance(execution.get('plan'), list) else []
    results = execution.get('results') if isinstance(execution.get('results'), list) else []
    results_by_id = {row.get('assignment_id'): row for row in results if isinstance(row, dict)}
    trace = trace_events if isinstance(trace_events, list) else []
    starts = [event for event in trace if isinstance(event, dict) and event.get('status') == 'started'
              and event.get('kind') in {'agent', 'discovery', 'grouped-verification'}]
    for row in plan:
        if not isinstance(row, dict):
            continue
        identifier = row.get('id')
        selected = by_selection.get(row.get('selection_id'))
        if selected is None:
            errors.append(prefix + 'assignment references unknown selection: ' + str(identifier))
            continue
        successor = by_selection.get(row.get('superseded_by')) if row.get('superseded_by') is not None else None
        if row.get('superseded_by') is not None:
            if successor is None or row['superseded_by'] == row.get('selection_id'):
                errors.append(prefix + 'assignment has invalid superseding selection: ' + str(identifier))
            elif identifier not in successor.get('affected_assignments', []):
                errors.append(prefix + 'superseding selection must name affected assignment: ' + str(identifier))
            if row.get('role') == 'project_gate':
                errors.append(prefix + 'project_gate cannot be superseded: ' + str(identifier))
            if identifier in results_by_id or any(row.get('reference') in event.get('evidence', []) for event in starts):
                errors.append(prefix + 'started assignment cannot be superseded: ' + str(identifier))
            if row.get('required') is not False:
                errors.append(prefix + 'superseded assignment must be marked not required: ' + str(identifier))
        elif row.get('required') is not True:
            errors.append(prefix + 'nonrequired assignment needs a valid supersession: ' + str(identifier))

    if trace_events is not None:
        last_sequence = -1
        for index, row in enumerate(history):
            matches = [event for event in trace if event.get('event_id') == row['event_id']
                       and event.get('kind') == 'profile' and event.get('status') in {'selected', 'completed'}
                       and row['reference'] in event.get('evidence', [])]
            if not matches:
                errors.append(prefix + 'selection lacks matching observed profile event: ' + row['id'])
                continue
            sequence = matches[0].get('sequence', -1)
            if not isinstance(sequence, int) or sequence <= last_sequence:
                errors.append(prefix + 'profile event order is invalid: ' + row['id'])
            last_sequence = sequence
            if index == 0 and any(event.get('sequence', 0) <= sequence for event in starts):
                errors.append(prefix + 'initial profile selection must precede observed review work')
    active = [row for row in plan if isinstance(row, dict) and row.get('superseded_by') is None]
    rank = {'focused': 0, 'standard': 1, 'deep': 2, 'extended': 3}
    required_profiles = [by_selection[row.get('selection_id')]['profile'] for row in active
                         if row.get('selection_id') in by_selection]
    required_profiles.append(history[-1]['profile'])
    strongest = max(required_profiles, key=rank.get)
    discovery = [row for row in active if row.get('role') == 'discovery']
    verification = [row for row in active if row.get('role') == 'verification']
    source = next((row['selection_source'] for row in reversed(history) if row['profile'] == strongest), history[0]['selection_source'])
    minimum = {'focused': 1, 'standard': 1, 'deep': 2, 'extended': 4 if source == 'automatic' else 2}[strongest]
    if len(discovery) < minimum:
        errors.append(prefix + f'{strongest} profile obligations require at least {minimum} active discovery assignments')
    if strongest in {'deep', 'extended'}:
        if len(verification) != 1 or verification[0].get('independent') is not True:
            errors.append(prefix + 'deep/extended profile requires one fresh grouped verification obligation')
        if any(row.get('independent') is not True for row in discovery):
            errors.append(prefix + 'deep/extended profile requires independent discovery assignments')
    return errors
