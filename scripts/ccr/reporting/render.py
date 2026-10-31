"""Render user and public handoff reports from validated records."""
import html
import re
from urllib.parse import quote

from ccr.contracts.review import validate
from ccr.contracts.dimensions import DIMENSION_LABELS
from ccr.reporting.blocks import coverage_lines, evidence_groups, evidence_lines
from ccr.reporting.check_disclosure import disclosure_view, disclosure_lines
from ccr.contracts.validation import (
    AREAS, AREA_STATUS, CHECK_STATUS, DESCRIPTION, FAILURE_KINDS, MODE_LABELS,
    ORIGINS, PRIORITIES, PROFILE_PHASES, PROFILES,
    REREVIEW_STATUS, REVIEW_KINDS, VERDICTS, VERIFICATION,
)
from ccr.reporting.markdown import markdown_text, one_line, reference_text, table_cell
from ccr.reporting.models import model_summary, model_lines
from ccr.reporting.projections import (
    public_checks, public_coverage, public_limitations, public_projection, public_reservations, public_url,
)


def person_text(person):
    if person['verified'] is not True:
        return 'No identificado'
    # Validated account characters are safe and must remain intact for mentions.
    return '@' + person['username'] if person['username'] else markdown_text(person['name'])

def previous_reviews_text(record, audience):
    """Preserve parent identity without publishing private archive references."""
    references = []
    for prior in record.get('previous_reviews', []):
        parts = [prior['review_id']] if prior.get('review_id') else []
        reference = prior.get('reference')
        if reference and (audience == 'user' or (prior.get('verified') is True and public_url(reference))):
            parts.append(reference_text(reference))
        references.append(' · '.join(parts) or 'Fuente verificada conservada en el registro')
    return '; '.join(references)

def confirmed_counts_text(findings):
    """Format the shared priority/icon summary, counting confirmed findings only."""
    return ' · '.join(
        f"{label.split()[0]} {priority}: "
        f"{sum(item['status'] == 'confirmed' and item['priority'] == priority for item in findings)}"
        for priority, label in PRIORITIES.items())

def render(record, audience='user', publication_context=None, *, check_publication_context=None,
           coverage_publication_context=None, check_disclosure_context=None, check_disclosure_sources=None,
           model_usage_context=None):
    return _render(record, audience, publication_context,
                   check_publication_context=check_publication_context,
                   coverage_publication_context=coverage_publication_context,
                   check_disclosure_context=check_disclosure_context, check_disclosure_sources=check_disclosure_sources,
                   model_usage_context=model_usage_context)


def render_portable(record, evidence_by_finding):
    """Render a typed portable record with groups formed before prose projection."""
    return _render(record, evidence_by_finding=evidence_by_finding, include_models=False)


def _render(record, audience='user', publication_context=None, *, check_publication_context=None,
            coverage_publication_context=None, evidence_by_finding=None,
            check_disclosure_context=None, check_disclosure_sources=None, model_usage_context=None,
            include_models=True):
    errors = validate(record)
    if errors or record.get('stage') != 'final':
        raise ValueError('; '.join(errors) if errors else 'only final records can be rendered')
    if audience not in {'user', 'comment'}:
        raise ValueError('audience must be user or comment')
    disclosure = (disclosure_view(record, check_disclosure_context, check_disclosure_sources)
                  if audience == 'comment' or check_disclosure_context is not None else None)
    disclosure_rows = {row['id']: row for row in disclosure['checks']} if disclosure else {}
    if publication_context is not None and audience != 'comment':
        raise ValueError('publication context is only applicable to public rendering')
    if check_publication_context is not None and audience != 'comment':
        raise ValueError('check publication context is only applicable to public rendering')
    if coverage_publication_context is not None and audience != 'comment':
        raise ValueError('coverage publication context is only applicable to public rendering')
    flows = (public_coverage(record, coverage_publication_context) if audience == 'comment'
             else record['coverage']['flows'])
    public_check_rows = (public_checks(record, check_publication_context)
                         if audience == 'comment' else None)
    scope = record['scope']
    responsible = record['responsible']
    version = scope['snapshot'] or scope['head']
    remote = scope['mode'] in {'mr', 'pr'}
    responsibility = 'Responsable del MR/PR' if remote else 'Responsable'
    presentation = record.get('presentation')
    title = (REVIEW_KINDS[presentation['kind']] + ' — ' + markdown_text(presentation['subject'])
             if presentation else 'Code Review')
    lines = ['## ' + title, '', f"### Veredicto: **{VERDICTS[record['verdict']]}**", '',
             markdown_text(record['verdict_reason']), '',
             f"- **Alcance:** {markdown_text(scope['repository'])} · {MODE_LABELS[scope['mode']]}",
             f"- **Versión:** {markdown_text(scope['base'] or 'sin comparación')} → {markdown_text(version)}"]
    if record.get('review_id'):
        lines.append('- **ID de revisión:** ' + record['review_id'])
    if record.get('previous_reviews'):
        lines.append('- **Revisiones previas:** ' + previous_reviews_text(record, audience))
    if scope['target']:
        lines.append(f"- **Destino:** {markdown_text(scope['target'])}")
    lines.append(f'- **{responsibility}:** {person_text(responsible)}')
    if record['schema_version'] in (3, 4, 5, 6, 7, 8, 9, 10, 11, 12):
        authors = '; '.join(person_text(author) for author in record['change_authors']) or 'No identificados'
        lines.append('- **Autores del cambio:** ' + authors)
    if scope['reference']:
        reference_label = 'MR/PR' if scope['mode'] in {'mr', 'pr'} else 'Referencia'
        lines.append(f"- **{reference_label}:** {reference_text(scope['reference'])}")
    if audience == 'user':
        if record['schema_version'] in (10, 11, 12):
            history = record['coverage']['execution']['profile_history']
            initial = history[0]
            lines.extend([f"- **Perfil inicial:** {PROFILES[initial['profile']]} — {markdown_text(initial['reason'])}.",
                          f"- **Perfil efectivo:** {PROFILES[record['profile']]} — {markdown_text(record['profile_reason'])}."])
            if len(history) > 1:
                transitions = '; '.join(
                    f"{PROFILES[item['changed_from']]} → {PROFILES[item['profile']]} "
                    f"(durante {PROFILE_PHASES[item['phase']]}) — {markdown_text(item['reason'])}"
                    for item in history[1:])
                lines.append('- **Transiciones de perfil:** ' + transitions + '.')
        else:
            lines.append(f"- **Perfil:** {PROFILES[record['profile']]} — {markdown_text(record['profile_reason'])}.")
        lines.append(f"- **Verificación:** {VERIFICATION[record['coverage']['verification']]}.")
        if record['schema_version'] in (8, 9, 10, 11, 12):
            status = {'fulfilled': 'cumplida', 'degraded': 'degradada'}[record['coverage']['execution']['status']]
            lines.append('- **Ejecución del perfil:** ' + status + '.')
    description = record['description']
    if description['status'] != 'not_applicable':
        lines.append(f"- **Descripción:** {DESCRIPTION[description['status']]} — {markdown_text(description['details'])}")
    else:
        lines.append('- **Descripción:** No aplica; revisión local.')
    confirmed = sorted((f for f in record['findings'] if f['status'] == 'confirmed'),
                       key=lambda f: (f['priority'], f['id']))
    counts = confirmed_counts_text(record['findings'])
    lines.extend(['', '### Hallazgos', '', '**Confirmados:** ' + counts])
    if confirmed:
        for ordinal, item in enumerate(confirmed, 1):
            location = item['location']
            label = f"{location['path']}:{location['line']}" if item['type'] == 'code' else location['section']
            if location['url']:
                label = f"[{one_line(label)}]({location['url']})"
            ledger = {check['id']: check for check in record['checks']}
            groups = (evidence_by_finding[item['id']] if evidence_by_finding is not None
                      else evidence_groups(item['evidence'], ledger))
            evidence = evidence_lines(groups)
            lines.extend(['', '<a id="' + html.escape(item['id'], quote=True) + '"></a>', '',
                          f"### {PRIORITIES[item['priority']]} — {one_line(item['id'])}", '',
                          f"#### {ordinal}. {one_line(item['title'])}", '',
                          f"- **Ubicación:** {label} · **Origen:** {ORIGINS[item['origin']]}",
                          f"- **Escenario:** {one_line(item['scenario'])}",
                          f"- **Impacto:** {one_line(item['impact'])}",
                          '- **Evidencia:**', *evidence, f"- **Corrección requerida:** {one_line(item['correction'])}",
                          '- **Bloqueante:** ' + ('sí — ' + one_line(item['blocking_reason']) if item['blocking'] else 'no')])
    else:
        lines.extend(['', 'No se confirmaron defectos bloqueantes dentro del alcance revisado.'])
    unresolved = [f for f in record['findings'] if f['status'] == 'unresolved']
    limitations = (public_limitations(record, publication_context) if audience == 'comment' else
                   [dict(item) for item in record['coverage']['limitations']])
    lines.extend(['', '### Validación', ''])
    if record['checks']:
        public_rows = ({row['id']: row for row in public_check_rows}
                       if public_check_rows is not None else {})
        for check in record['checks']:
            display = public_rows.get(check['id'], check) if audience == 'comment' else check
            lines.extend(['', '<a id="' + html.escape(check['id'], quote=True) + '"></a>', ''])
            reuse = ' · evidencia reutilizada: ' + one_line(display['reuse_reason']) if display['reused'] else ''
            repeat = f" · repetición: {one_line(display['rerun_reason'])}" if display['rerun_reason'] else ''
            classification = f" · fallo de {FAILURE_KINDS[check['failure_kind']]}" if check['failure_kind'] else ''
            command = f" `{one_line(check['command'])}` —" if audience == 'user' and not disclosure else ''
            lines.append(f"- **{check['id']}**:{command} {CHECK_STATUS[check['status']]} · versión {one_line(check['revision'])}{classification}{reuse}{repeat}")
            lines.append('  - **Propósito:** ' + markdown_text(display.get('purpose') or 'Propósito no registrado (resultado anterior)'))
            if check['id'] in disclosure_rows:
                lines.extend(disclosure_lines(disclosure_rows[check['id']]))
            if display.get('evidence'):
                lines.append('  - **Resultado:** ' + markdown_text(display['evidence']))
            if display.get('reference'):
                lines.append('  - **Referencia de ejecución:** ' + reference_text(display['reference']))
    else:
        lines.append('- Inspección estática; no se ejecutaron comprobaciones.')
    lines.extend(['', *coverage_lines(flows)])
    areas = record['coverage'].get('areas', [])
    if audience == 'user' and areas:
        lines.extend(['', '### Matriz ABCDE', '',
                      '| Área | Estado | Evidencia o motivo | Hallazgos |',
                      '|---|---|---|---|'])
        for row in sorted(areas, key=lambda item: item['area']):
            references = ', '.join(table_cell(identifier) for identifier in row['finding_ids']) or '—'
            lines.append(f"| {row['area']} — {AREAS[row['area']]} | {AREA_STATUS[row['status']]} | {table_cell(row['details'])} | {references} |")
        if record['schema_version'] in (11, 12):
            lines.extend(['', '### Dimensiones de cobertura', '',
                          '| ID | Dimensión | Estado | Evidencia o motivo | Hallazgos |',
                          '|---|---|---|---|---|'])
            for area in sorted(areas, key=lambda item: item['area']):
                for row in sorted(area['dimensions'], key=lambda item: item['id']):
                    references = ', '.join(markdown_text(identifier) for identifier in row['finding_ids']) or '—'
                    lines.append(f"| {row['id']} | {DIMENSION_LABELS[row['id']]} | {AREA_STATUS[row['status']]} | {markdown_text(row['details'])} | {references} |")
    known_limits = {one_line(item['detail']): i for i, item in enumerate(limitations)}
    for row in areas if audience == 'user' else []:
        detail = one_line(row['details'])
        if row['material']:
            if detail in known_limits:
                limitations[known_limits[detail]]['material'] = True
            else:
                known_limits[detail] = len(limitations)
                limitations.append({'detail': detail, 'material': True})
    if unresolved or limitations:
        lines.extend(['', '### Incertidumbres', ''])
        lines.extend(f"- **{f['id']}**: {markdown_text(f['title'])} — {markdown_text(f['scenario'])}" for f in unresolved)
        lines.extend(f"- {one_line(item['detail'])}" + (' [material]' if item['material'] else '') for item in limitations)
    conditions = [f"{f['id']}: {one_line(f['correction'])}" for f in confirmed if f['blocking']]
    reservations = public_reservations(record, limitations) if audience == 'comment' else record['reservations']
    conditions.extend(one_line(r) for r in reservations)
    if conditions:
        lines.extend(['', '### Condiciones y reservas', ''])
        lines.extend('- [ ] ' + condition for condition in conditions)
    if record['rereview']:
        lines.extend(['', '### Re-review', ''])
        for item in record['rereview']:
            source = ''
            if item.get('previous_finding_id'):
                source = f" · anterior {markdown_text(item['previous_finding_id'])}: {markdown_text(item['previous_title'])}"
                reference = item.get('previous_url') or item.get('previous_reference')
                if reference and (audience == 'user' or public_url(reference)):
                    source += ' · ' + reference_text(reference)
                if item.get('previous_review_id'):
                    source += ' · ' + item['previous_review_id']
            checks = ' · comprobaciones: ' + ', '.join(item['check_ids']) if item.get('check_ids') else ''
            lines.append(f"- **{item['id']}**: {REREVIEW_STATUS[item['status']]}{source} — {one_line(item['details'])}{checks}")
    if audience == 'user' and (record['resources']['residuals'] or record['resources']['publication'] in {'published', 'failed'}):
        lines.extend(['', '### Recursos y publicación', ''])
        lines.extend('- Recurso pendiente: ' + one_line(p) for p in record['resources']['residuals'])
        if record['resources']['publication'] in {'published', 'failed'}:
            lines.append('- Publicación: ' + record['resources']['publication'])
    if audience == 'user' and include_models:
        if model_usage_context is not None and model_usage_context.get('ledger') is not None:
            if model_usage_context['ledger'].get('review_id') != record.get('review_id'):
                raise ValueError('model usage evidence belongs to another review')
        lines.extend(model_lines(model_usage_context))
    output = '\n'.join(lines) + '\n'
    return public_projection(output, record, disclosure, check_disclosure_sources) if audience == 'comment' else output

def render_handoff(record, context=None, audience='user', publication_context=None, *,
                   check_publication_context=None, coverage_publication_context=None,
                   check_disclosure_context=None, check_disclosure_sources=None):
    """Render an explicitly requested contextual index, never an authorization."""
    errors = validate(record)
    if errors or record.get('stage') != 'final':
        raise ValueError('; '.join(errors) if errors else 'only final records can be rendered')
    if audience not in {'user', 'comment'}:
        raise ValueError('audience must be user or comment')
    disclosure = (disclosure_view(record, check_disclosure_context, check_disclosure_sources)
                  if audience == 'comment' or check_disclosure_context is not None else None)
    disclosure_rows = {row['id']: row for row in disclosure['checks']} if disclosure else {}
    if publication_context is not None and audience != 'comment':
        raise ValueError('publication context is only applicable to public rendering')
    if audience != 'comment' and (check_publication_context is not None or coverage_publication_context is not None):
        raise ValueError('check/coverage publication context is only applicable to public rendering')
    checks = (public_checks(record, check_publication_context) if audience == 'comment' else record['checks'])
    flows = public_coverage(record, coverage_publication_context) if audience == 'comment' else record['coverage']['flows']
    limitations = (public_limitations(record, publication_context) if audience == 'comment' else
                   record['coverage']['limitations'])
    context = context or {}
    allowed = {'source_record', 'source_report', 'requirements', 'plan', 'decisions_pending'}
    if not isinstance(context, dict) or set(context) - allowed:
        raise ValueError('unknown handoff context fields')
    scope = record['scope']
    lines = ['## Transferencia contextual de revisión', '',
             '- **ID de revisión:** ' + record.get('review_id', 'ID histórico no disponible'),
             '- **Alcance:** ' + markdown_text(scope['repository']) + ' · ' + MODE_LABELS[scope['mode']]]
    if record.get('previous_reviews'):
        lines.append('- **Revisiones previas:** ' + previous_reviews_text(record, audience))
    for key, label in [('base', 'Base'), ('head', 'Head'), ('snapshot', 'Snapshot'), ('target', 'Destino')]:
        if scope.get(key):
            lines.append(f'- **{label}:** ' + markdown_text(scope[key]))
    if scope.get('reference'):
        lines.append('- **Referencia del alcance:** ' + reference_text(scope['reference']))
    for key, label in [('source_record', 'Registro fuente'), ('source_report', 'Informe fuente')]:
        if context.get(key):
            if not isinstance(context[key], str):
                raise ValueError(key + ' must be a reference string')
            lines.append(f'- **{label}:** ' + reference_text(context[key]))
    lines.extend(['', '### Índice de hallazgos confirmados', ''])
    confirmed = [item for item in record['findings'] if item['status'] == 'confirmed']
    for item in sorted(confirmed, key=lambda item: (item['priority'], item['id'])):
        correction_reference = ''
        if context.get('source_report'):
            target = context['source_report'].split('#')[0] + '#' + item['id']
            correction_reference = ' · [Corrección ' + markdown_text(item['id']) + '](' + quote(target, safe='/:#?&=%-._~') + ')'
        lines.append(f"- {item['id']} · {item['priority']} · bloqueante: {'sí' if item['blocking'] else 'no'} · "
                     + markdown_text(item['title']) + ' · corrección requerida: ' + markdown_text(item['correction']) + correction_reference)
        lines.append('  - **Evidencia:**')
        lines.extend('  ' + line for line in evidence_lines(evidence_groups(item['evidence'], {c['id']: c for c in record['checks']})))
    if not confirmed:
        lines.append('- Ningún hallazgo confirmado.')
    uncertainties = [item['id'] + ': ' + item['title'] for item in record['findings'] if item['status'] == 'unresolved']
    uncertainties += [item['detail'] for item in limitations]
    if audience == 'user':
        uncertainties += [row['details'] for row in record['coverage'].get('areas', [])
                          if row['status'] in {'partial', 'not_evaluated'}]
    pending = context.get('decisions_pending', [])
    if not isinstance(pending, list) or any(not isinstance(item, str) for item in pending):
        raise ValueError('decisions_pending must be a text array')
    reservations = public_reservations(record, limitations) if audience == 'comment' else record['reservations']
    lines.extend(['', '### Incertidumbres y decisiones pendientes', ''])
    lines.extend('- ' + markdown_text(item) for item in dict.fromkeys(uncertainties + pending + reservations))
    if not uncertainties and not pending and not reservations:
        lines.append('- Ninguna registrada.')
    lines.extend(['', '### Validación', ''])
    for check in checks:
        lines.extend(['', '<a id="' + html.escape(check['id'], quote=True) + '"></a>', ''])
        evidence_ref = (' · referencia: ' + reference_text(check['reference']) if check.get('reference') else
                        ' · [Evidencia ' + check['id'] + '](' + quote(context['source_report'].split('#')[0] + '#' + check['id'], safe='/:#?&=%-._~') + ')' if context.get('source_report') else
                        ' · evidencia: véase Validación del informe fuente')
        lines.append(f"- {check['id']} · {CHECK_STATUS[check['status']]} · versión {markdown_text(check['revision'])}" +
                     evidence_ref)
        lines.append('  - **Propósito:** ' + markdown_text(check.get('purpose') or 'Propósito no registrado (resultado anterior)'))
        if check['id'] in disclosure_rows:
            lines.extend(disclosure_lines(disclosure_rows[check['id']]))
        lines.append('  - **Resultado:** ' + markdown_text(check['evidence'] or 'Sin ejecución'))
    if not record['checks']:
        lines.append('- Inspección estática; sin comprobaciones ejecutadas.')
    lines.extend(['', *coverage_lines(flows)])
    for key, label in [('requirements', 'Requisitos y especificaciones'), ('plan', 'Plan')]:
        entries = context.get(key, [])
        if not isinstance(entries, list):
            raise ValueError(key + ' must be an array of collected provenance')
        if entries:
            lines.extend(['', '### ' + label, ''])
        for item in entries:
            if isinstance(item, str):
                lines.append('- ' + reference_text(item))
            elif isinstance(item, dict) and set(item) == {'title', 'reference', 'identity'} and all(isinstance(item[key], str) and item[key].strip() for key in item):
                lines.append('- ' + markdown_text(item['title']) + ' · ' + reference_text(item['reference']) + ' · identidad: ' + markdown_text(item['identity']))
            else:
                raise ValueError('provenance needs title, reference and captured identity')
    lines.extend(['', 'Antes de continuar, comprobar que base, head y snapshot coincidan con la versión actual y repetir las comprobaciones afectadas o pendientes con un nuevo ID de ejecución.',
                  'La transferencia conserva el contexto; cualquier corrección, commit o publicación requiere la autorización correspondiente.'])
    output = '\n'.join(lines) + '\n'
    return public_projection(output, record, disclosure, check_disclosure_sources) if audience == 'comment' else output
