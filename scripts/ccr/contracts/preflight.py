"""Pure phase preflight and assignment-event validation."""
import hashlib
import json
from ccr.archive.layout import ARCHIVE_SCHEMA_VERSION, LAYOUT_VERSION
from ccr.contracts.reference_types import ReferenceIssue, _issue
from ccr.contracts import dispatch
from ccr.contracts.reference_index import validate_reference_selection, validate_selection_reference
from ccr.contracts.receipts import validate_record_receipts
from ccr.contracts.material_inputs import validate_captured_material_sources
from ccr.workflow.inputs import normalize_inputs


PHASES = {'prepare', 'register', 'discovery', 'retain'}

WORK_KINDS = {'agent', 'discovery', 'grouped-verification', dispatch.IDENTITY_ANNOTATION_KIND}

WORK_STATUSES = {'started', 'completed', 'passed', 'failed', 'blocked', 'skipped'}

MAX_ISSUES = 100

def _ordered(phase: str, issues: list[ReferenceIssue]) -> dict:
    ordered = sorted(issues, key=lambda item: (item['field'], item['code'], item['reference'] or ''))
    if len(ordered) > MAX_ISSUES:
        ordered = ordered[:MAX_ISSUES]
        ordered[-1] = dict(ordered[-1], message=ordered[-1]['message'][:450] +
                           ' (additional issues truncated)')
    return {'phase': phase, 'ready': not ordered, 'issues': ordered}

def validate_assignment_event(event: dict,
                              registry: list[dict]) -> list[ReferenceIssue]:
    """Admit a new work milestone, including its observed dispatch identity."""
    return _assignment_event_issues(event, registry, admit_dispatch=True)


def _assignment_event_issues(event: dict, registry: list[dict], *, admit_dispatch: bool
                             ) -> list[ReferenceIssue]:
    if (not isinstance(event, dict) or event.get('kind') not in WORK_KINDS
            or (event.get('status') not in WORK_STATUSES and not dispatch.is_identity_annotation(event))):
        return []
    evidence = event.get('evidence')
    if not isinstance(evidence, list) or not evidence:
        return [_issue('missing_assignment', 'assignment', None,
                       'work milestone has no assignment brief reference',
                       'an active required assignment brief')]
    evidence_refs = {item for item in evidence if isinstance(item, str)}
    if not evidence_refs:
        return [_issue('missing_assignment', 'assignment', None,
                       'work milestone has no assignment brief reference',
                       'an active required assignment brief')]

    assignments = registry if isinstance(registry, list) else []
    known = {row.get('reference') for row in assignments if isinstance(row, dict)
             and isinstance(row.get('reference'), str)}
    active = {row['reference'] for row in assignments if isinstance(row, dict)
              and row.get('required') is True and row.get('superseded_by') is None
              and isinstance(row.get('reference'), str)}
    matched = active.intersection(evidence_refs)
    if matched:
        if not admit_dispatch and event.get('kind') == 'agent' and event.get('status') == 'started':
            return []
        return dispatch.validate_dispatch_identity_event(event, assignments)
    code = 'unregistered_assignment' if known.intersection(evidence_refs) or evidence_refs else 'missing_assignment'
    reference = next(iter(sorted(evidence_refs)), None)
    return [_issue(code, 'assignment', reference,
                   'work milestone must identify an active required assignment brief captured in the execution plan',
                   'an active required assignment brief from the durable registry')]


def validate_assignment_history(events: list[dict], registry: list[dict]) -> list[ReferenceIssue]:
    """Validate observed bindings and recoveries without readmitting old starts.

    Annotation relations are checked against the original immutable trace first.
    Projected starts retain their sequence; absent historical identities remain
    unknown here and must satisfy completion/fallback gates during retention.
    """
    if not isinstance(events, list) or any(not isinstance(event, dict) for event in events):
        return [_issue('invalid_assignment_history', 'assignment.history', None,
                       'observed assignment history must be an array of event objects',
                       'the verified original trace events')]
    projected, issues = dispatch.project_dispatches(events, registry)
    if issues:
        return issues
    starts = iter(projected)
    for event in events:
        observed = next(starts) if event.get('kind') == 'agent' and event.get('status') == 'started' else event
        issues.extend(_assignment_event_issues(observed, registry, admit_dispatch=False))
    return issues

def validate_preflight(*, phase: str, manifest: dict | None,
                       logical_scope: dict | None, selection: dict | None,
                       context: dict | None, record: dict | None,
                       sources: dict[str, bytes],
                       check_material_sources: bool = True) -> dict:
    """Check only the supplied phase inputs; never reads or writes files."""
    if phase not in PHASES:
        raise ValueError('phase must be prepare, register, discovery or retain')
    issues: list[ReferenceIssue] = []
    if phase == 'prepare':
        if selection is None:
            issues.append(_issue('missing_input', 'selection', None,
                                 'prepare requires a profile selection',
                                 'a selection using evidence/context.json#profile'))
        else:
            issues.extend(validate_selection_reference(selection, None))
        return _ordered(phase, issues)

    if not isinstance(manifest, dict):
        issues.append(_issue('missing_input', 'manifest', None,
                             'phase preflight requires a native archive manifest',
                             'archive schema 8 and layout 2'))
        return _ordered(phase, issues)
    if (manifest.get('schema_version') != ARCHIVE_SCHEMA_VERSION
            or manifest.get('layout_version') != LAYOUT_VERSION):
        issues.append(_issue('input_changed', 'manifest.layout', None,
                             'unsupported_layout: preflight requires native archive schema 8/layout 2',
                             'archive schema 8 and layout 2'))

    pinned_scope = manifest.get('logical_scope')
    if logical_scope is not None:
        if (not isinstance(logical_scope, dict) or not isinstance(pinned_scope, dict)
                or logical_scope.get('identity') != pinned_scope.get('identity')
                or logical_scope.get('identity') != manifest.get('logical_scope', {}).get('identity')):
            issues.append(_issue('input_changed', 'logical_scope_identity', None,
                                 'preflight logical scope differs from the captured archive identity',
                                 str((pinned_scope or {}).get('identity'))))

    if selection is None:
        history = manifest.get('profile_history')
        selection = (history[-1] if isinstance(history, list) and history
                     and isinstance(history[-1], dict) else None)
    if selection is None:
        issues.append(_issue('missing_input', 'selection', None,
                             'archive has no captured profile selection',
                             'a captured selection using evidence/context.json#profile'))
    else:
        issues.extend(validate_selection_reference(selection, sources))

    if not isinstance(context, dict):
        issues.append(_issue('missing_input', 'context', None,
                             'phase preflight requires the existing execution context',
                             'the context captured for this archive'))
    else:
        history = manifest.get('profile_history')
        last_selection = (history[-1] if isinstance(history, list) and history
                          and isinstance(history[-1], dict) else {})
        if (context.get('profile_history') != history or not last_selection
                or context.get('profile') != last_selection.get('profile')
                or context.get('profile_reference') != last_selection.get('reference')):
            issues.append(_issue('input_changed', 'context.profile_history', None,
                                 'execution context does not preserve the captured profile history',
                                 'the exact archive profile history'))
        captured = manifest.get('review_inputs')
        supplied = context.get('review_inputs')
        if captured is not None:
            try:
                normalized = normalize_inputs(supplied) if supplied is not None else None
            except (TypeError, ValueError) as exc:
                normalized = None
                issues.append(_issue('input_changed', 'review_inputs', None,
                                     'execution context review inputs are invalid: ' + str(exc),
                                     'the exact captured review_inputs'))
            if normalized is None:
                if not any(row['field'] == 'review_inputs' for row in issues):
                    issues.append(_issue('missing_input', 'review_inputs', None,
                                         'execution context omitted captured review inputs',
                                         'the exact captured review_inputs'))
            elif normalized != captured:
                issues.append(_issue('input_changed', 'review_inputs', None,
                                     'execution context differs from the immutable captured inputs',
                                     'the exact captured review_inputs'))
            expected_identity = (pinned_scope or {}).get('identity') if isinstance(pinned_scope, dict) else None
            if isinstance(normalized, dict) and normalized.get('logical_scope_identity') != expected_identity:
                issues.append(_issue('input_changed', 'logical_scope_identity', None,
                                     'execution context logical scope differs from the archive',
                                     str(expected_identity)))
        if (check_material_sources and phase in {'register', 'discovery', 'retain'}
                and context.get('reference_index') == 'evidence/reference-index.json'):
            index_reference = context['reference_index']
            index_bytes = sources.get(index_reference)
            if not isinstance(index_bytes, bytes):
                issues.append(_issue('missing_input', 'reference_index', index_reference,
                                     'prepared review reference index is not selected for preflight',
                                     'selected evidence/reference-index.json bytes'))
            else:
                try:
                    index = json.loads(index_bytes.decode('utf-8'))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    index = None
                    issues.append(_issue('invalid_reference', 'reference_index', index_reference,
                                         'prepared review reference index is not valid UTF-8 JSON',
                                         'the captured reference index'))
                else:
                    issues.extend(validate_reference_selection(index, sources))
                captured_sources = (context.get('review_inputs', {}).get('sources')
                                    if isinstance(context.get('review_inputs'), dict) else None)
                index_digest = hashlib.sha256(index_bytes).hexdigest()
                if not isinstance(captured_sources, dict) or captured_sources.get(index_reference) != index_digest:
                    issues.append(_issue('input_changed', 'review_inputs.sources', index_reference,
                                         'reference index is not bound to the initially captured source digest',
                                         index_digest))
                if isinstance(index, dict):
                    if (phase in {'register', 'discovery'}
                            and manifest.get('state') == 'prepared'):
                        issues.extend(validate_captured_material_sources(
                            context.get('review_inputs'), index, sources))

        plan = context.get('execution_plan')
        if not isinstance(plan, list):
            issues.append(_issue('missing_input', 'execution_plan', None,
                                 'execution context requires an explicit execution_plan assignment list',
                                 'a list of registered assignments, possibly empty during register'))
        elif phase in {'discovery', 'retain'} and plan != manifest.get('assignment_registry'):
            issues.append(_issue('input_changed', 'execution_plan', None,
                                 'execution plan differs from the durable assignment registry',
                                 'the exact durable assignment registry'))
        if phase == 'discovery':
            registry = manifest.get('assignment_registry')
            active = [row for row in registry if isinstance(row, dict)
                      and row.get('required') is True and row.get('superseded_by') is None] \
                if isinstance(registry, list) else []
            if not active:
                issues.append(_issue('missing_assignment', 'assignment_registry', None,
                                     'discovery requires at least one active required assignment',
                                     'an active required assignment in the durable registry'))

    if phase == 'retain' and not isinstance(record, dict):
        issues.append(_issue('missing_input', 'record', None,
                             'retain preflight is incomplete without a final candidate',
                             'the structurally final review candidate'))
    elif phase == 'retain' and record.get('schema_version') in (9, 10, 11):
        issues.extend(validate_record_receipts(
            record, sources, context.get('executors', []) if isinstance(context, dict) else []))
    return _ordered(phase, issues)
