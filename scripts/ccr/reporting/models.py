"""Private model summaries from supplied or retained facts; never query a provider."""
import copy
import hashlib
import json

from ccr.contracts.model_usage import MAX_LEDGER_BYTES, validate_model_usage
from ccr.contracts.dispatch import project_dispatches
from ccr.contracts.check_disclosure import safe_text
from ccr.reporting.markdown import table_cell


def model_summary(context, ledger):
    """Preserve every observation and expose missing capture for known participants."""
    context = context or {}
    diagnostics = list(context.get('model_usage_diagnostics', []))
    capture_visible = bool(context.get('_show_missing_model_participants') or diagnostics)
    if ledger is None and not capture_visible:
        return dict(recorded=False, harness_id=None, entries=[], diagnostics=diagnostics)
    if ledger is not None and not isinstance(ledger, dict):
        raise ValueError('selected model usage evidence must be an object')
    issues = (validate_model_usage(ledger, review_id=context.get('review_id', ledger.get('review_id')),
                                  harness_id=context.get('harness_id', ledger.get('harness_id')))
              if ledger is not None else [])
    if issues:
        raise ValueError('selected model usage evidence is invalid: ' + issues[0]['message'])
    entries = copy.deepcopy(ledger['entries']) if ledger is not None else []
    def identity_class(actor):
        # A coordinator can perform an agent assignment; process/tool rows
        # never capture the model of a same-named reviewer.
        kind = actor['kind']
        return 'model_user' if kind in ('coordinator', 'agent') else kind

    for participant in context.get('observed_participants', []):
        if any(all(row['actor'][key] == participant['actor'][key] for key in ('name', 'provider_id'))
               and identity_class(row['actor']) == identity_class(participant['actor'])
               and row['assignment_id'] == participant['assignment_id']
               for row in entries):
            continue
        entries.append(dict(participant, configured_model=None, observed_model=None, status='unknown',
                            source={'kind': 'unavailable', 'reference': None}))
    return dict(recorded=ledger is not None,
                harness_id=ledger['harness_id'] if ledger is not None else context.get('harness_id'), entries=entries,
                diagnostics=diagnostics)


def model_usage_context(context, source, manifest, *, record=None, events=None):
    """Bind selected original bytes to their retained review and harness identity."""
    context = copy.deepcopy(context or {})
    reference = context.get('model_usage_reference')
    capture_visible = bool(record and record.get('schema_version') == 12
                           or context.get('model_usage_diagnostics'))
    if reference is None and not capture_visible:
        return dict(context=context, ledger=None, sha256=None)
    if reference is not None and reference != 'evidence/model-usage.json':
        raise ValueError('model usage reference must identify evidence/model-usage.json')
    raw = ledger = None
    if reference is not None:
        try:
            raw = source(reference)
            if len(raw) > MAX_LEDGER_BYTES:
                raise ValueError('selected model usage exceeds 256 KiB')
            ledger = json.loads(raw.decode('utf-8'))
            if not isinstance(ledger, dict):
                raise ValueError('selected model usage evidence must be an object')
        except (OSError, UnicodeDecodeError, ValueError, TypeError) as exc:
            raise ValueError('selected model usage evidence is unreadable: ' + str(exc)) from exc
    if capture_visible:
        # Presentation policy only; this does not assert that capture succeeded
        # or add a field to selected context/ledger bytes.
        context['_show_missing_model_participants'] = True
    context.update(review_id='CR-' + manifest['run_id'], harness_id=manifest.get('harness_id'))
    participants = []
    for selection in context.get('profile_history', []):
        actor = selection.get('actor')
        if isinstance(actor, dict) and actor.get('kind') == 'coordinator':
            participants.append(dict(actor=copy.deepcopy(actor), assignment_id=None,
                                     phase='coordination', activity='coordination'))
    plan = context.get('execution_plan', [])
    if events:
        projected, issues = project_dispatches(events, plan)
        if issues:
            raise ValueError('invalid model participant dispatch: ' + issues[0]['message'])
        for event in projected:
            identity = event.get('executor')
            if event.get('kind') != 'agent' or event.get('status') != 'started' or not identity:
                continue
            for assignment in plan:
                if assignment.get('reference') in event.get('evidence', []):
                    role = assignment['role']
                    activity = 'discovery' if role == 'discovery' else 'verification'
                    participants.append(dict(actor=dict(kind='agent', **identity),
                        assignment_id=assignment['id'], phase=activity, activity=activity))
        for event in events:
            actor = event.get('actor')
            if (event.get('kind') not in {'discovery', 'grouped-verification'}
                    or event.get('status') not in {'completed', 'passed', 'failed', 'blocked'}
                    or not isinstance(actor, dict) or actor.get('kind') not in {None, 'agent', 'coordinator'}):
                continue
            if actor.get('kind') is None:
                # Completion actors use the execution identity shape (name/provider).
                # Reuse an observed coordinator identity, otherwise this is the
                # actual result reviewer, not evidence of an independent dispatch.
                kind = 'coordinator' if any(
                    row['actor'].get('kind') == 'coordinator'
                    and all(row['actor'].get(key) == actor.get(key) for key in ('name', 'provider_id'))
                    for row in participants) else 'agent'
                actor = dict(actor, kind=kind)
            results = (record or {}).get('coverage', {}).get('execution', {}).get('results', [])
            for assignment in plan:
                activity = 'discovery' if assignment['role'] == 'discovery' else 'verification'
                expected_kind = 'discovery' if activity == 'discovery' else 'grouped-verification'
                if event['kind'] != expected_kind:
                    continue
                evidence = event.get('evidence', [])
                result_bound = any(result.get('assignment_id') == assignment['id']
                    and result.get('reference') in evidence
                    and result.get('reviewer_context') == actor.get('name')
                    and result.get('provider_id') == actor.get('provider_id') for result in results)
                if assignment.get('reference') in evidence or result_bound:
                    participants.append(dict(actor=copy.deepcopy(actor), assignment_id=assignment['id'],
                                             phase=activity, activity=activity))
    context['observed_participants'] = participants
    model_summary(context, ledger)
    return dict(context=context, ledger=ledger, sha256=hashlib.sha256(raw).hexdigest() if raw is not None else None)


def model_lines(model_context, *, sanitize=None):
    """Render a bounded table; local deliveries can sanitize all cells uniformly."""
    if model_context is None:
        summary = model_summary({}, None)
    else:
        summary = model_summary(model_context['context'], model_context['ledger'])
    lines = ['', '### Modelos por participante', '']
    def cell(value):
        value = str(value) if value is not None else 'no disponible'
        value = safe_text(value)
        return table_cell(sanitize(value) if sanitize else value)
    if not summary['recorded'] and not summary['entries']:
        return lines + ['Modelo no registrado.'] + ['- ' + cell(item) for item in summary['diagnostics'][:32]]
    if not summary['recorded']:
        lines.append('Modelo no registrado; participantes observados sin captura de modelo.')
    lines += ['Harness: ' + cell(summary['harness_id']), '',
              '| Participante / asignación | Fase | Configurado | Observado | Estado | Procedencia / ausencia |',
              '| --- | --- | --- | --- | --- | --- |']
    for row in summary['entries']:
        actor = row['actor']
        participant = actor['name'] + (' / ' + row['assignment_id'] if row['assignment_id'] else '')
        source = row['source']['kind'] + (': ' + row['source']['reference'] if row['source']['reference'] else '')
        if row['status'] == 'unknown':
            source = 'Modelo no expuesto; captura no disponible'
        lines.append('| ' + ' | '.join(cell(item) for item in (participant, row['phase'],
            row['configured_model'], row['observed_model'], row['status'], source)) + ' |')
    for diagnostic in summary['diagnostics'][:32]:
        lines.append('- ' + cell(diagnostic))
    return lines
