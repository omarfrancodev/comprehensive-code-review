"""Pure profile-history and schema-10 obligation validation."""
import copy
import re


ALIASES = {'economy': 'focused', 'balanced': 'standard'}
PROFILES = {'focused', 'standard', 'deep', 'extended'}
PROFILE_RANK = {'focused': 0, 'standard': 1, 'deep': 2, 'extended': 3}
PHASES = {'prepare', 'discovery', 'verification', 'report', 'retain', 'cleanup', 'close'}
SELECTION_FIELDS = {'id', 'profile', 'selection_source', 'reason', 'reference', 'phase',
                    'actor', 'authority', 'affected_assignments', 'changed_from', 'event_id'}
INPUT_FIELDS = SELECTION_FIELDS - {'id', 'changed_from', 'event_id'}
MAX_HISTORY = 32
ASSIGNMENT_FIELDS = {'id', 'role', 'independent', 'required', 'reference', 'selection_id', 'superseded_by'}
MAX_ASSIGNMENTS = 32
UNJUSTIFIED_DOWNGRADE = re.compile(
    r'\b(urgent|urgency|deadline|time|cost|costs|budget|quota|slot|slots|capacity|tokens?|credits?|'
    r'no findings?|no issues?|no defects?|clean review|urgencia|urgente|plazo|tiempo|coste|costos?|'
    r'presupuesto|cuota|cupo|sin hallazgos|sin defectos|sin incidencias|revision limpia|revisión limpia)\b',
    re.IGNORECASE)


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
    if not isinstance(value['selection_source'], str) or value['selection_source'] not in ('explicit', 'automatic'):
        raise ValueError('selection_source must be explicit or automatic')
    if not _text(value['reason']) or not _text(value['reference'], 500):
        raise ValueError('selection reason and reference must be nonempty bounded text')
    if not isinstance(value['phase'], str) or value['phase'] not in PHASES:
        raise ValueError('invalid selection phase')
    if not isinstance(value['actor'], dict) or set(value['actor']) != {'kind', 'name', 'provider_id'}:
        raise ValueError('selection actor must preserve the trace identity shape')
    actor = value['actor']
    if (not isinstance(actor['kind'], str) or actor['kind'] not in {'helper', 'coordinator', 'agent', 'tool'}
            or not _text(actor['name'], 160)):
        raise ValueError('invalid selection actor identity')
    if actor['provider_id'] is not None and not _text(actor['provider_id'], 160):
        raise ValueError('invalid selection actor provider ID')
    if value['authority'] is not None and not _text(value['authority'], 1000):
        raise ValueError('authority must be bounded text or null')
    if value['selection_source'] == 'explicit' and value['authority'] is None:
        raise ValueError('an explicit profile selection requires user authority')
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
        if (PROFILE_RANK[value['profile']] < PROFILE_RANK[old_profile]
                and value['selection_source'] == 'automatic'):
            if (value['reason'] == previous.get('reason')
                    or value['reference'] == previous.get('reference')
                    or UNJUSTIFIED_DOWNGRADE.search(value['reason'])):
                raise ValueError('automatic downgrade needs a new evidence-backed reason and source; urgency, cost, capacity or absence of findings is not a justification')
        if previous.get('selection_source') == 'explicit' and (
                value['selection_source'] != 'explicit' or value['authority'] is None):
            raise ValueError('an explicit profile transition requires a later explicit user source')
        if value['profile'] != old_profile:
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
        if not isinstance(row['id'], str) or not re.fullmatch(r'S[0-9]{3,}', row['id']):
            errors.append(prefix + ': invalid selection ID')
        elif row['id'] in seen_ids:
            errors.append('profile history contains duplicate selection identity')
        else:
            seen_ids.add(row['id'])
        if not isinstance(row['event_id'], str) or not re.fullmatch(r'E[0-9]{6,}', row['event_id']):
            errors.append(prefix + ': invalid profile event ID')
        elif row['event_id'] in seen_events:
            errors.append(prefix + ': duplicate profile event ID')
        else:
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


def _assignment_rows(rows, history, label):
    if not isinstance(rows, list) or len(rows) > MAX_ASSIGNMENTS:
        raise ValueError(label + ' must be a bounded array of at most 32 assignments')
    selections = {row['id']: row for row in history}
    result, seen = [], set()
    for index, raw in enumerate(rows):
        if not isinstance(raw, dict) or set(raw) != ASSIGNMENT_FIELDS:
            raise ValueError(label + f'[{index}] requires the exact assignment fields')
        identifier = raw['id']
        if not _text(identifier, 160):
            raise ValueError(label + f'[{index}].id must be nonempty bounded text')
        if identifier in seen:
            raise ValueError(label + ' contains duplicate assignment IDs')
        seen.add(identifier)
        if not isinstance(raw['role'], str) or raw['role'] not in {'discovery', 'verification', 'project_gate'}:
            raise ValueError(label + f'[{index}].role is invalid')
        if type(raw['independent']) is not bool or type(raw['required']) is not bool:
            raise ValueError(label + f'[{index}] assignment flags must be booleans')
        if not _text(raw['reference'], 500):
            raise ValueError(label + f'[{index}].reference must be nonempty bounded text')
        selection_id = raw['selection_id']
        if not isinstance(selection_id, str) or selection_id not in selections:
            raise ValueError(label + f'[{index}].selection_id must identify a captured profile selection')
        superseded_by = raw['superseded_by']
        if superseded_by is not None and (not isinstance(superseded_by, str) or superseded_by not in selections):
            raise ValueError(label + f'[{index}].superseded_by must identify a captured profile selection')
        if (raw['role'] == 'project_gate' and superseded_by is not None
                or raw['required'] is False and superseded_by is None
                or raw['required'] is True and superseded_by is not None):
            raise ValueError(label + f'[{index}] has an invalid required/supersession state')
        if superseded_by is not None and identifier not in selections[superseded_by]['affected_assignments']:
            raise ValueError(label + f'[{index}] supersession must name the affected assignment')
        result.append(copy.deepcopy(raw))
    return result


def _assignment_started(row, trace_events):
    for event in trace_events:
        if (not isinstance(event, dict) or not isinstance(event.get('kind'), str) or event.get('kind') not in {
                'agent', 'discovery', 'grouped-verification'}):
            continue
        if (not isinstance(event.get('status'), str) or event.get('status') not in
                {'started', 'completed', 'passed', 'failed', 'blocked', 'skipped'}):
            continue
        evidence = event.get('evidence')
        if isinstance(evidence, list) and row['reference'] in evidence:
            return True
    return False


def _trace_rows(trace_events, errors, prefix):
    if not isinstance(trace_events, list):
        errors.append(prefix + 'trace events must be an array')
        return []
    result = []
    for index, raw in enumerate(trace_events):
        if not isinstance(raw, dict):
            errors.append(prefix + f'trace event {index} must be an object')
            continue
        row = raw
        if not isinstance(row.get('kind'), str) or not isinstance(row.get('status'), str):
            errors.append(prefix + f'trace event {index} kind/status must be text')
            continue
        evidence = row.get('evidence', [])
        if not isinstance(evidence, list) or any(not isinstance(item, str) for item in evidence):
            errors.append(prefix + f'trace event {index} evidence must be an array of text references')
            row = dict(row, evidence=[])
        sequence = row.get('sequence')
        if sequence is not None and type(sequence) is not int:
            errors.append(prefix + f'trace event {index} sequence must be an integer')
            row = dict(row, sequence=-1)
        result.append(row)
    return result


def merge_assignment_registry(previous: list[dict], incoming: list[dict], history: list[dict],
                              trace_events: list[dict]) -> list[dict]:
    """Append assignments without erasing or rewriting work observed in trace."""
    if not isinstance(trace_events, list):
        raise ValueError('trace events must be an array')
    history_errors = validate_history(history)
    if history_errors:
        raise ValueError('invalid profile history for assignment registry: ' + '; '.join(history_errors))
    old_rows = _assignment_rows(previous, history, 'previous assignment registry')
    new_rows = _assignment_rows(incoming, history, 'incoming execution plan')
    events = trace_events
    incoming_by_id = {row['id']: row for row in new_rows}
    merged = []
    for old in old_rows:
        current = incoming_by_id.get(old['id'])
        started = _assignment_started(old, events)
        if current is None:
            if started:
                raise ValueError('started assignment cannot be omitted from execution plan: ' + old['id'])
            merged.append(old)
            continue
        if started and (old['required'] != current['required']
                        or old['superseded_by'] != current['superseded_by']):
            raise ValueError('started assignment cannot be superseded or rewritten: ' + old['id'])
        identity = ('id', 'role', 'independent', 'reference', 'selection_id')
        if started and any(old[key] != current[key] for key in identity):
            raise ValueError('started assignment identity cannot be changed; use a new ID: ' + old['id'])
        if any(old[key] != current[key] for key in identity):
            raise ValueError('assignment identity cannot be changed; use a new ID: ' + old['id'])
        if old['superseded_by'] is not None and current['superseded_by'] != old['superseded_by']:
            raise ValueError('assignment supersession is immutable: ' + old['id'])
        merged.append(current)
    old_ids = {row['id'] for row in old_rows}
    merged.extend(row for row in new_rows if row['id'] not in old_ids)
    return merged


def validate_profile_execution(record: dict, trace_events: list[dict] | None = None, *,
                               assignment_registry: list[dict] | None = None) -> list[str]:
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
    results_by_id = {row.get('assignment_id'): row for row in results if isinstance(row, dict)
                     and isinstance(row.get('assignment_id'), str)}
    trace = _trace_rows(trace_events, errors, prefix) if trace_events is not None else []
    starts = [event for event in trace if event.get('status') == 'started'
              and isinstance(event.get('kind'), str)
              and event.get('kind') in {'agent', 'discovery', 'grouped-verification'}]
    for row in plan:
        if not isinstance(row, dict):
            errors.append(prefix + 'assignment must be an object')
            continue
        identifier = row.get('id')
        if not _text(identifier, 160):
            errors.append(prefix + 'assignment ID must be nonempty bounded text')
            continue
        if not isinstance(row.get('role'), str) or row.get('role') not in {
                'discovery', 'verification', 'project_gate'}:
            errors.append(prefix + 'assignment role is invalid: ' + identifier)
            continue
        if type(row.get('independent')) is not bool or type(row.get('required')) is not bool:
            errors.append(prefix + 'assignment flags must be booleans: ' + identifier)
            continue
        if not _text(row.get('reference'), 500):
            errors.append(prefix + 'assignment reference must be nonempty bounded text: ' + identifier)
            continue
        selection_id = row.get('selection_id')
        if not isinstance(selection_id, str):
            errors.append(prefix + 'assignment selection_id must be text: ' + str(identifier))
            continue
        selected = by_selection.get(selection_id)
        if selected is None:
            errors.append(prefix + 'assignment references unknown selection: ' + str(identifier))
            continue
        superseded_by = row.get('superseded_by')
        if superseded_by is not None and not isinstance(superseded_by, str):
            errors.append(prefix + 'assignment superseded_by must be text or null: ' + str(identifier))
            continue
        successor = by_selection.get(superseded_by) if superseded_by is not None else None
        if superseded_by is not None:
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

    registry_by_id = None
    registry = plan
    if assignment_registry is not None:
        try:
            registry = _assignment_rows(assignment_registry, history, 'assignment registry')
        except ValueError as exc:
            errors.append(prefix + str(exc))
            registry = []
        registry_by_id = {row['id']: row for row in registry}
        plan_by_id = {row.get('id'): row for row in plan if isinstance(row, dict)
                      and isinstance(row.get('id'), str)}
        for row in registry:
            started = _assignment_started(row, trace)
            current = plan_by_id.get(row['id'])
            completed = row['id'] in results_by_id
            if current is None:
                state = 'started/completed' if started or completed else 'captured'
                errors.append(prefix + state + ' assignment is missing from final plan: ' + row['id'])
            elif current != row:
                errors.append(prefix + 'final plan differs from captured assignment registry: ' + row['id'])
        for row in plan:
            if isinstance(row, dict) and isinstance(row.get('id'), str) and row['id'] not in registry_by_id:
                errors.append(prefix + 'assignment was not captured before execution: ' + row['id'])

    if trace_events is not None:
        last_sequence = -1
        for index, row in enumerate(history):
            matches = [event for event in trace if isinstance(event.get('event_id'), str)
                       and event.get('event_id') == row['event_id']
                       and event.get('kind') == 'profile' and event.get('status') in {'selected', 'completed'}
                       and isinstance(event.get('evidence'), list)
                       and row['reference'] in event.get('evidence', [])]
            if not matches:
                errors.append(prefix + 'selection lacks matching observed profile event: ' + row['id'])
                continue
            sequence = matches[0].get('sequence', -1)
            if type(sequence) is not int or sequence <= last_sequence:
                errors.append(prefix + 'profile event order is invalid: ' + row['id'])
            last_sequence = sequence
            if index == 0 and any(type(event.get('sequence')) is int and event['sequence'] <= sequence for event in starts):
                errors.append(prefix + 'initial profile selection must precede observed review work')
    active = [row for row in plan if isinstance(row, dict) and row.get('superseded_by') is None]
    rank = {'focused': 0, 'standard': 1, 'deep': 2, 'extended': 3}
    required_profiles = [by_selection[row['selection_id']]['profile'] for row in active
                         if isinstance(row.get('selection_id'), str) and row['selection_id'] in by_selection]
    required_profiles.append(history[-1]['profile'])
    strongest = max(required_profiles, key=rank.get)
    discovery = [row for row in active if row.get('role') == 'discovery']
    verification = [row for row in active if row.get('role') == 'verification']
    source = next((row['selection_source'] for row in reversed(history) if row['profile'] == strongest), history[0]['selection_source'])
    observed_assignment_ids = set(results_by_id)
    if trace_events is None:
        observed_assignment_ids.update(row['id'] for row in active if isinstance(row, dict)
                                       and isinstance(row.get('id'), str))
    else:
        observed_assignment_ids.update(row['id'] for row in registry if isinstance(row, dict)
                                       and isinstance(row.get('id'), str)
                                       and _assignment_started(row, trace))
    acquired_extended_auto = False
    if strongest == 'extended':
        observed_rows = [row for row in registry if isinstance(row, dict)
                         and isinstance(row.get('id'), str) and row['id'] in observed_assignment_ids]
        used_selection_ids = {row.get('selection_id') for row in observed_rows
                              if isinstance(row.get('selection_id'), str)}
        acquired_extended_auto = any(row['id'] in used_selection_ids and row['profile'] == 'extended'
                                     and row['selection_source'] == 'automatic' for row in history)
    minimum = {'focused': 1, 'standard': 1, 'deep': 2,
               'extended': 4 if acquired_extended_auto or source == 'automatic' else 2}[strongest]
    qualifying_discovery = discovery
    if strongest in {'deep', 'extended'}:
        qualifying_discovery = [row for row in discovery if row.get('independent') is True]
    if len(qualifying_discovery) < minimum:
        qualifier = ' (independent discovery assignments required)' if strongest in {'deep', 'extended'} else ''
        errors.append(prefix + f'{strongest} profile obligations require at least {minimum} active discovery assignments{qualifier}')
    if strongest in {'deep', 'extended'}:
        if not any(row.get('independent') is True for row in verification):
            errors.append(prefix + 'deep/extended profile requires an independent grouped verification obligation')
    return errors
