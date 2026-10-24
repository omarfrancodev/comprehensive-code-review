"""Pure validation and projection for observed reviewer dispatch identities."""
import copy
import json
import re

from ccr.contracts.reference_types import ReferenceIssue, _issue
from ccr.contracts.references import parse_reference


_EVENT_ID = re.compile(r'E[0-9]{6,}')
_SYSTEM_FIELDS = {'event_id', 'sequence', 'run_id', 'review_id', 'recorded_at',
                  'recorder', 'previous_sha256', 'sha256', 'schema_version'}


def _failure(message: str, reference: str | None = None) -> ReferenceIssue:
    return _issue('invalid_dispatch_identity', 'dispatch.identity', reference,
                  message, 'an observed independent dispatch or a valid records annotation')


def is_identity_annotation(event: object) -> bool:
    """Recognize recovery intent, including partial claims that must be rejected.

    Status alone never upgrades a historical observation into an identity claim.
    Either recovered provenance or a records link to the local event namespace
    expresses that intent; F/C and cross-review links remain ordinary milestones.
    """
    if not isinstance(event, dict) or event.get('kind') != 'agent' or event.get('status') != 'unchanged':
        return False
    provenance = event.get('provenance')
    if isinstance(provenance, dict) and provenance.get('kind') == 'recovered':
        return True
    relations = event.get('relations')
    return isinstance(relations, list) and any(
        isinstance(row, dict) and row.get('relation') == 'records'
        and isinstance(row.get('target'), str) and re.fullmatch(r'E[0-9]+', row['target']) is not None
        for row in relations)


def _identity(value: object) -> bool:
    return (isinstance(value, dict) and set(value) == {'name', 'provider_id'}
            and isinstance(value.get('name'), str) and bool(value['name'].strip())
            and len(value['name']) <= 160 and not any(ord(char) < 32 for char in value['name'])
            and (value.get('provider_id') is None
                 or isinstance(value.get('provider_id'), str)
                 and bool(value['provider_id'].strip()) and len(value['provider_id']) <= 160
                 and not any(ord(char) < 32 for char in value['provider_id'])))


def _active_assignments(registry: list[dict], evidence: object) -> list[dict]:
    if not isinstance(evidence, list):
        return []
    references = {item for item in evidence if isinstance(item, str)}
    return [row for row in registry if isinstance(row, dict)
            and row.get('reference') in references and row.get('required') is True
            and row.get('superseded_by') is None]


def _semantic_annotation(event: dict) -> str:
    value = {key: event.get(key) for key in
             ('kind', 'status', 'actor', 'executor', 'provenance', 'evidence',
              'relations', 'authority', 'occurred_at')}
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def _validate_annotation(event: dict, registry: list[dict],
                         trace_events: list[dict] | None = None) -> list[ReferenceIssue]:
    issues: list[ReferenceIssue] = []
    relation = event.get('relations')
    target = (relation[0].get('target') if isinstance(relation, list) and len(relation) == 1
              and isinstance(relation[0], dict) else None)
    if (event.get('kind') != 'agent' or event.get('status') != 'unchanged'
            or not isinstance(event.get('summary'), str) or not event['summary'].strip()
            or not isinstance(event.get('actor'), dict)
            or set(event['actor']) != {'kind', 'name', 'provider_id'}
            or event['actor'].get('kind') != 'coordinator'
            or not isinstance(event['actor'].get('name'), str)
            or not event['actor']['name'].strip()
            or len(event['actor']['name']) > 160
            or event['actor'].get('provider_id') is not None
            or not _identity(event.get('executor'))
            or event.get('authority') is not None or event.get('occurred_at') is not None):
        issues.append(_failure('identity annotation has invalid status, actor, executor or timestamp'))
    if (not isinstance(relation, list) or len(relation) != 1
            or not isinstance(relation[0], dict)
            or set(relation[0]) != {'relation', 'target'}
            or relation[0].get('relation') != 'records'
            or not isinstance(target, str) or not _EVENT_ID.fullmatch(target)):
        issues.append(_failure('identity annotation must record exactly one original event',
                               target if isinstance(target, str) else None))

    provenance = event.get('provenance')
    source = provenance.get('source') if isinstance(provenance, dict) else None
    if (not isinstance(provenance, dict) or set(provenance) != {'kind', 'source'}
            or provenance.get('kind') != 'recovered' or not isinstance(source, str)):
        issues.append(_failure('identity annotation requires recovered local dispatch evidence',
                               source if isinstance(source, str) else None))
    else:
        try:
            path, fragment = parse_reference(source, field='dispatch identity provenance',
                                             allow_alias_key=True)
            if not path.startswith('evidence/') or fragment is None:
                raise ValueError('dispatch identity provenance must select a local evidence object')
        except ValueError as exc:
            issues.append(_failure(str(exc), source))
        evidence = event.get('evidence')
        if (not isinstance(evidence, list) or len(evidence) > 24
                or any(not isinstance(item, str) for item in evidence) or source not in evidence):
            issues.append(_failure('dispatch identity source must be explicitly selected in evidence', source))

    evidence = event.get('evidence')
    assignments = _active_assignments(registry, evidence)
    if len(assignments) != 1 or assignments[0].get('independent') is not True:
        issues.append(_failure('identity annotation must cite one active independent assignment'))
    assignment = assignments[0] if len(assignments) == 1 else None

    if trace_events is None:
        return issues
    if not isinstance(trace_events, list):
        return issues + [_failure('trace events must be an array')]
    matches = [row for row in trace_events if isinstance(row, dict) and row.get('event_id') == target]
    if len(matches) != 1:
        issues.append(_failure('identity annotation target must exist exactly once in this run', target))
        original = None
    else:
        original = matches[0]
        sequence = event.get('sequence')
        original_sequence = original.get('sequence')
        original_assignments = _active_assignments(registry, original.get('evidence'))
        if (original.get('kind') != 'agent' or original.get('status') != 'started'
                or original.get('executor') is not None
                or type(sequence) is not int or type(original_sequence) is not int
                or sequence < 1 or original_sequence < 1
                or original_sequence >= sequence
                or assignment is None or original_assignments != [assignment]
                or not isinstance(event.get('event_id'), str)
                or event.get('event_id') == target):
            issues.append(_failure('target must be an earlier executor-less dispatch for the same active assignment', target))

    if isinstance(target, str):
        prior = [row for row in trace_events if isinstance(row, dict)
                 and row is not event and row.get('event_id') != event.get('event_id')
                 and is_identity_annotation(row)
                 and isinstance(row.get('relations'), list)
                 and any(isinstance(item, dict) and item.get('relation') == 'records'
                         and item.get('target') == target for item in row['relations'])]
        if any(_semantic_annotation(row) != _semantic_annotation(event) for row in prior):
            issues.append(_failure('divergent identity annotations target the same dispatch', target))
    return issues


def validate_dispatch_identity_event(event: dict, registry: list[dict],
                                     trace_events: list[dict] | None = None) -> list[ReferenceIssue]:
    """Validate a new independent start or a bounded annotation of its identity."""
    if not isinstance(event, dict) or not isinstance(registry, list):
        return [_failure('dispatch event and assignment registry must be objects/arrays')]
    if event.get('kind') == 'agent' and event.get('status') == 'started':
        assignments = _active_assignments(registry, event.get('evidence'))
        if any(row.get('independent') is True for row in assignments):
            if len(assignments) != 1:
                return [_failure('independent dispatch must identify exactly one active assignment')]
            if not _identity(event.get('executor')):
                return [_failure('independent dispatch must record the observed executor')]
        return []
    if is_identity_annotation(event):
        return _validate_annotation(event, registry, trace_events)
    return []


def project_dispatches(trace_events: list[dict], registry: list[dict]
                       ) -> tuple[list[dict], list[ReferenceIssue]]:
    """Project late annotations onto original starts without rewriting the trace."""
    if not isinstance(trace_events, list) or not isinstance(registry, list):
        return [], [_failure('trace events and assignment registry must be arrays')]
    starts = [event for event in trace_events if isinstance(event, dict)
              and event.get('kind') == 'agent' and event.get('status') == 'started']
    projected = [copy.deepcopy(event) for event in starts]
    by_id = {event.get('event_id'): index for index, event in enumerate(starts)
             if isinstance(event.get('event_id'), str)}
    issues: list[ReferenceIssue] = []
    annotations = [event for event in trace_events if is_identity_annotation(event)]
    for event in annotations:
        current = validate_dispatch_identity_event(event, registry, trace_events)
        issues.extend(current)
        relation = event.get('relations')
        target = (relation[0].get('target') if isinstance(relation, list) and len(relation) == 1
                  and isinstance(relation[0], dict) else None)
        if current or target not in by_id:
            continue
        index = by_id[target]
        if projected[index].get('executor') is None:
            projected[index]['executor'] = copy.deepcopy(event.get('executor'))
        elif projected[index].get('executor') != event.get('executor'):
            issues.append(_failure('identity annotation conflicts with original dispatch identity', target))
    unique = {}
    for issue in issues:
        key = (issue['code'], issue['field'], issue['reference'], issue['message'])
        unique[key] = issue
    return projected, [unique[key] for key in sorted(unique, key=lambda item: (item[1], item[0], item[2] or '', item[3]))]
