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


def canonical_profile(value):
    """Resolve supported request aliases to a current profile name."""
    return _canonical(value)
