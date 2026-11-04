"""Explicitly deliver a portable projection of a retained review; never review again."""
import argparse
import hashlib
import heapq
import html
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

from ccr.archive.lifecycle import validate as validate_archive
from ccr.contracts import review as review_contract, validation
from ccr.reporting import markdown
from ccr.reporting.blocks import coverage_lines, evidence_groups, evidence_lines
from ccr.reporting.check_disclosure import disclosure_view, disclosure_lines
from ccr.contracts.check_disclosure import EXPLANATION_COMMAND, OMITTED, safe_text, private_values, sensitive_text_ranges
from ccr.reporting.render import confirmed_counts_text, previous_reviews_text, render_portable as render_record
from ccr.shared.git import git as _git, repository_identity
from ccr.shared.json_io import read_json
from ccr.shared.paths import contains, safe_path

from ccr.reporting.text_projection import (_Projection, _hash, _json, _public_url, _relative_to_root)


def _context_markdown(context, projection):
    """Render only supplied observations, all bound to references and versions."""
    if context is None or context == {}:
        return None
    labels = {'assumptions': 'Supuestos', 'decisions': 'Decisiones registradas',
              'sources': 'Fuentes y secciones analizadas', 'implementation_state': 'Estado observado de implementación',
              'pending': 'Pendientes registrados'}
    if not isinstance(context, dict) or set(context) - set(labels):
        raise ValueError('unknown delivery context fields')
    if len(_json(context)) > 32768 or sum(len(entries) for entries in context.values() if isinstance(entries, list)) > 24:
        raise ValueError('delivery context is limited to 32 KiB and 24 collected entries')
    lines = ['## Contexto recopilado', '',
             'Datos previos suministrados para esta entrega. No constituyen una nueva revisión ni autorización para actuar.']
    entries_present = False
    def text(value):
        if not isinstance(value, str) or not value.strip():
            raise ValueError('context entries require nonempty text, references and version')
        return projection.text(value)
    def reference(value):
        text(value)  # Validate its type before treating it as a locator.
        return markdown.reference_text(projection.reference(value))
    for key, label in labels.items():
        entries = context.get(key, [])
        if not isinstance(entries, list):
            raise ValueError('context sections must be arrays')
        if entries:
            entries_present = True
            lines.extend(['', '### ' + label, ''])
        for item in entries:
            fields = {'title', 'reference', 'identity', 'sections', 'version'} if key == 'sources' else {'text', 'references', 'version'}
            if not isinstance(item, dict) or set(item) != fields:
                raise ValueError('context source/observation fields are incomplete or unknown')
            version = text(item['version'])
            if key == 'sources':
                if not isinstance(item['sections'], list) or not item['sections']:
                    raise ValueError('sources require the sections actually analyzed')
                sections = [text(section) for section in item['sections']]
                lines.append('- ' + markdown.markdown_text(text(item['title'])) + ' · ' + reference(item['reference'])
                             + ' · identidad: ' + markdown.markdown_text(text(item['identity']))
                             + ' · secciones: ' + '; '.join(markdown.markdown_text(section) for section in sections)
                             + ' · versión: ' + markdown.markdown_text(version))
            else:
                if not isinstance(item['references'], list) or not item['references']:
                    raise ValueError('observations require collected evidence references')
                references = [reference(locator) for locator in item['references']]
                lines.append('- ' + markdown.markdown_text(text(item['text'])) + ' · referencias: ' + '; '.join(references)
                             + ' · versión: ' + markdown.markdown_text(version))
    return ('\n'.join(lines) + '\n').encode('utf-8') if entries_present else None

def _human(text):
    return re.sub(r'retained:[0-9a-f]{64}(?:\\)?#ref-[0-9a-f]{16}', 'referencia interna no incluida', text)

def _brief(record, *, evidence_by_finding=None):
    scope = record['scope']
    lines = ['## Resumen de revisión', '', '### Veredicto: **' + validation.VERDICTS[record['verdict']] + '**', '',
             markdown.markdown_text(record['verdict_reason']), '',
             '- **Alcance:** ' + markdown.markdown_text(scope['repository']) + ' · ' + validation.MODE_LABELS[scope['mode']],
             '- **Versión:** ' + markdown.markdown_text(scope['base'] or 'sin comparación') + ' → '
             + markdown.markdown_text(scope['head'] or scope['snapshot']),
             '- **Verificación:** ' + validation.VERIFICATION[record['coverage']['verification']],
             '- **Cobertura obsoleta:** ' + ('sí' if record['coverage']['stale'] else 'no')]
    if record['schema_version'] in (8, 9, 10, 11, 12, 13):
        status = {'fulfilled': 'cumplida', 'degraded': 'degradada'}[record['coverage']['execution']['status']]
        lines.append('- **Ejecución del perfil:** ' + status)
    if scope['snapshot']:
        lines.append('- **Snapshot:** ' + markdown.markdown_text(scope['snapshot']))
    if scope['target']:
        lines.append('- **Destino:** ' + markdown.markdown_text(scope['target']))
    if scope['reference']:
        lines.append('- **Referencia:** ' + markdown.reference_text(scope['reference']))
    if record.get('review_id'):
        lines.append('- **ID de revisión:** ' + record['review_id'])
    if record.get('previous_reviews'):
        lines.append('- **Revisiones previas:** ' + previous_reviews_text(record, 'user'))
    lines.extend(['', '### Hallazgos', ''])
    confirmed = sorted((item for item in record['findings'] if item['status'] == 'confirmed'), key=lambda item: (item['priority'], item['id']))
    lines.extend(['**Confirmados:** ' + confirmed_counts_text(record['findings']), ''])
    for item in confirmed:
        location = item['location']
        label = (str(location['path']) + ':' + str(location['line'])) if item['type'] == 'code' else location['section']
        lines.append('- **' + item['id'] + '** · ' + item['priority'] + ' · ' + markdown.markdown_text(item['title'])
                     + ' · ' + (markdown.reference_text(location['url']) + ' · ' if location['url'] else '')
                     + markdown.markdown_text(label) + ' · bloqueante: ' + ('sí' if item['blocking'] else 'no'))
        for key, label in [('scenario', 'Escenario'), ('impact', 'Impacto'), ('correction', 'Corrección requerida')]:
            lines.append('  - **' + label + ':** ' + markdown.markdown_text(item[key]))
        lines.append('  - **Evidencia:**')
        groups = (evidence_by_finding[item['id']] if evidence_by_finding is not None else
                  evidence_groups(item['evidence'], {c['id']: c for c in record['checks']}))
        lines.extend('  ' + line for line in evidence_lines(groups))
    if not confirmed:
        lines.append('- Ningún hallazgo confirmado.')
    lines.extend(['', '### Validación', ''])
    for check in record['checks']:
        lines.extend(['', '<a id="' + html.escape(check['id'], quote=True) + '"></a>', ''])
        lines.append('- **' + check['id'] + '** · ' + validation.CHECK_STATUS[check['status']] + ' · versión: '
                     + markdown.markdown_text(check['revision']))
        lines.append('  - **Propósito:** ' + markdown.markdown_text(check.get('purpose') or 'Propósito no registrado (resultado anterior)'))
        if record['schema_version'] in (12, 13):
            lines.append('  - **Comando saneado:** ' + markdown.markdown_text(check['command']))
        lines.append('  - **Resultado:** ' + markdown.markdown_text(check['evidence'] or 'Sin ejecución'))
        if check.get('reference'):
            lines.append('  - Referencia: ' + markdown.reference_text(check['reference']))
        if check['reused']:
            lines.append('  - Evidencia reutilizada: ' + markdown.markdown_text(check['reuse_reason']))
        if check['failure_kind']:
            lines.append('  - Clasificación: ' + validation.FAILURE_KINDS[check['failure_kind']])
    if not record['checks']:
        lines.append('- Inspección estática; sin comprobaciones ejecutadas.')
    lines.extend(['', *coverage_lines(record['coverage']['flows'])])
    if record['schema_version'] in (11, 12):
        lines.extend(['', '### Dimensiones de cobertura', ''])
        for area in record['coverage']['areas']:
            for row in area['dimensions']:
                detail = ' — ' + markdown.markdown_text(row['details']) if row['status'] != 'covered' else ''
                lines.append('- **' + row['id'] + '** · ' + validation.AREA_STATUS[row['status']] + detail)
    uncertainties = ['**' + item['id'] + '**: ' + markdown.markdown_text(item['title'] + ' · ' + item['scenario'])
                     for item in record['findings'] if item['status'] == 'unresolved']
    uncertainties.extend(markdown.markdown_text(item['detail']) for item in record['coverage']['limitations'])
    coverage_areas = record['coverage'].get('areas', [])
    if record['schema_version'] == 13:
        from ccr.contracts.dimensions import display_areas13
        coverage_areas = display_areas13(coverage_areas)
    uncertainties.extend(markdown.markdown_text(row['details']) for row in coverage_areas if row['status'] in {'partial', 'not_evaluated'})
    uncertainties.extend(markdown.markdown_text(item) for item in record['reservations'])
    if uncertainties:
        lines.extend(['', '### Incertidumbres y reservas', ''])
        lines.extend('- ' + item for item in dict.fromkeys(uncertainties))
    if record['rereview']:
        lines.extend(['', '### Re-review', ''])
        for item in record['rereview']:
            source = ' · anterior: ' + markdown.markdown_text(item['previous_title']) if item.get('previous_title') else ''
            lines.append('- **' + item['id'] + '** · ' + validation.REREVIEW_STATUS[item['status']] + source + ' · ' + markdown.markdown_text(item['details']))
    return '\n'.join(lines) + '\n'

def _write_file(path, data, owned_files):
    with safe_path(path).open('xb') as stream:
        owned_files.append(path)
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())

def deliver(run_dir, delivery, project_root, output_root=None, context=None, *,
            check_disclosure_context=None, check_disclosure_sources=None, model_usage_context=None):
    """Return a new delivery directory, refusing every implicit or unsafe destination."""
    if delivery not in {'full', 'brief'}:
        raise ValueError('an explicit delivery full|brief is required')
    validate_archive(run_dir, require_retained=True)
    run = safe_path(run_dir)
    compact_mode = (run / 'manifest.json').is_file()
    manifest_path = run / ('manifest.json' if compact_mode else 'cierre.json')
    manifest_bytes = manifest_path.read_bytes()
    compact_sources = None
    if compact_mode:
        from ccr.archive.compact import read_compact
        compact = read_compact(run)
        compact_manifest = compact['manifest']
        request = compact_manifest['request']
        compact_sources = compact['sources']
        manifest = {'repository_identity': request['repository_identity'],
                    'archive_root': request['archive_root'], 'run_id': compact_manifest['run_id'],
                    'hashes': compact_manifest['hashes'], 'temporary_paths': []}
    else:
        manifest = read_json(manifest_path)
    project = safe_path(project_root)
    selected = Path(output_root) if output_root is not None else project / 'docs' / 'ccr' / 'reviews'
    if not selected.is_absolute() and selected.drive:
        raise ValueError('drive-relative output roots are not allowed')
    root = safe_path(selected if selected.is_absolute() else project / selected)
    temporary = [safe_path(raw) for raw in manifest.get('temporary_paths', [])]
    if any(contains(path, candidate) for path in temporary for candidate in (project, root)):
        raise ValueError('delivery requires a persistent checkout/output, outside registered temporary resources')
    if contains(safe_path(manifest['archive_root']), root):
        raise ValueError('delivery cannot write into its retained source archive')
    if not project.is_dir() or safe_path(_git(project, 'rev-parse', '--show-toplevel')) != project:
        raise ValueError('--project-root must be the explicit Git repository root')
    identity = repository_identity(project)
    expected = manifest.get('repository_identity')
    if (expected is not None and identity != expected) or (expected is None and _hash(identity.encode('utf-8'))[:20] != manifest['repository_key']):
        raise ValueError('project-root belongs to a different repository')
    source = (run / 'review.json').read_bytes()
    record = read_json(run / 'review.json')
    source_hash = _hash(source)
    identifier = record.get('review_id') if record['schema_version'] in (6, 7, 8, 9, 10, 11, 12, 13) else manifest.get('run_id', run.name.rpartition('-')[2])
    if not isinstance(identifier, str) or not re.fullmatch(r'(?:CR-)?[0-9a-f]{20}', identifier):
        raise ValueError('known review/run identity required')
    destination = safe_path(root / run.parent.name / identifier)
    if contains(safe_path(manifest['archive_root']), destination) or any(contains(path, destination) for path in temporary):
        raise ValueError('delivery destination overlaps its retained archive or temporary resources')
    if destination.exists():
        raise ValueError('delivery destination already exists')
    from ccr.archive.evidence import selected_source_bytes as archive_source_bytes
    def selected_source_bytes(source_run, source_manifest, overlay, name):
        if compact_sources is not None:
            if name not in compact_sources:
                raise ValueError('compact retained source is unavailable: ' + name)
            return compact_sources[name]
        return archive_source_bytes(source_run, source_manifest, overlay, name)
    from ccr.archive.trace import NAME as TRACE_NAME
    from ccr.reporting import models
    retained_context = json.loads(selected_source_bytes(run, manifest, {}, 'evidence/context.json')) if 'evidence/context.json' in manifest['hashes'] else {}
    if compact_mode:
        manifest['harness_id'] = request['producer']['harness_id']
    from ccr.execution.disclosure import SelectedDisclosureSources
    selected = SelectedDisclosureSources(check_disclosure_sources or {})
    if compact_sources is not None:
        selected.update(compact_sources)
    reference = retained_context.get('check_disclosure_reference')
    if reference is not None:
        if reference != 'evidence/check-disclosure.json':
            raise ValueError('invalid check disclosure reference')
        selected[reference] = selected_source_bytes(run, manifest, {}, reference)
        retained_disclosure = json.loads(selected[reference])
        if check_disclosure_context is not None and check_disclosure_context != retained_disclosure:
            raise ValueError('disclosure differs from the retained selection')
        check_disclosure_context = retained_disclosure
        for row in retained_disclosure['checks']:
            for field in ('execution_reference', 'evidence_reference'):
                if row[field] is not None:
                    selected[row[field]] = selected_source_bytes(run, manifest, {}, row[field])
        if retained_disclosure['input_identity'] != retained_context.get('check_disclosure_input_identity'):
            raise ValueError('disclosure input identity differs from retained context')
        if retained_disclosure['input_identity'].get('resource_manifest_sha256') is not None and not compact_mode:
            if retained_disclosure['input_identity'] != manifest.get('check_disclosure_input_identity'):
                raise ValueError('disclosure input map was not registered before review work')
            selected.input_identity = manifest['check_disclosure_input_identity']
    elif (compact_mode or record.get('schema_version') == 13) and record.get('checks'):
        # No project-resource proof was pinned; disclose an explanation only.
        from ccr.workflow.builders import build_check_disclosure
        identity = {'head': record['scope']['head'], 'snapshot': record['scope']['snapshot']}
        check_disclosure_context = build_check_disclosure(record, identity, {}, selected)
    events = ([json.loads(line) for line in selected_source_bytes(run, manifest, {}, TRACE_NAME).splitlines()]
              if TRACE_NAME in manifest['hashes'] else
              json.loads(compact_sources['evidence/compact-execution.json']) if compact_mode else None)
    retained_models = models.model_usage_context(retained_context,
        lambda name: selected_source_bytes(run, manifest, {}, name), manifest, record=record, events=events)
    if model_usage_context is not None and model_usage_context != retained_models:
        raise ValueError('supplied model usage differs from retained selection')
    model_usage_context = retained_models
    projection = _Projection(record, manifest, project, source_hash,
        check_disclosure_context=check_disclosure_context, check_disclosure_sources=selected)
    # Exact-source equality and origin grouping must precede lossy prose
    # sanitization: distinct private paths can project to the same text.
    ledger = {check['id']: check for check in record['checks']}
    evidence_by_finding = {}
    for finding in record['findings']:
        groups = evidence_groups(finding['evidence'], ledger)
        for group in groups:
            group['details'] = [projection.text(detail) for detail in group['details']]
        evidence_by_finding[finding['id']] = groups
    portable = projection.value(record)
    errors = review_contract.validate(portable)
    if errors:
        raise ValueError('portable record is invalid: ' + '; '.join(errors))
    source_label = identifier if record['schema_version'] in (6, 7, 8, 9, 10, 11, 12, 13) else 'identidad de archivo ' + identifier
    notice = ('\n> Proyección portable de la revisión retenida (' + source_label + '). No es una nueva revisión ni una nueva ejecución. '
              'Comandos y referencias privadas omitidos; la procedencia e integridad se registran en .ccr-delivery.json.\n')
    files = ({'review.json': _json(portable), 'informe.md': (_human(render_record(portable, evidence_by_finding)) + notice).encode('utf-8')}
             if delivery == 'full' else {'resumen.md': (_human(_brief(portable, evidence_by_finding=evidence_by_finding)) + notice).encode('utf-8')})
    additional = []
    if projection.disclosure:
        additional.extend(['', '### Detalle acreditado de checks', ''])
        for row in projection.disclosure['checks']:
            additional.append('- **' + row['id'] + '**')
            additional.extend(disclosure_lines(row))
    additional.extend(models.model_lines(model_usage_context, sanitize=lambda value: projection.text(safe_text(value))))
    report_name = 'informe.md' if delivery == 'full' else 'resumen.md'
    if additional:
        files[report_name] += ('\n'.join(additional) + '\n').encode('utf-8')
    contextual = _context_markdown(context, projection)
    if contextual is not None:
        files['contexto.md'] = _human(contextual.decode('utf-8')).encode('utf-8')
    new_policy = record['schema_version'] in (12, 13) or projection.disclosure is not None or model_usage_context.get('sha256') is not None
    receipt = {'schema_version': 3 if compact_mode else 2 if new_policy else 1, 'delivery': delivery, 'source_id': identifier,
        'source_id_kind': 'review_id' if record['schema_version'] in (6, 7, 8, 9, 10, 11, 12, 13) else 'run_id',
        'source_hash': source_hash, 'source_schema_version': record['schema_version'], 'projection': 'portable',
        'projected_fields': projection.changed, 'hashes': {name: _hash(data) for name, data in files.items()}}
    if new_policy:
        receipt.update(projection_policy='project-resources-v1',
            check_disclosure_sha256=projection.disclosure['check_disclosure_sha256'] if projection.disclosure else None,
            model_usage_sha256=model_usage_context.get('sha256'))
    if compact_mode:
        receipt['artifact_mode'] = 'compact'
    files['.ccr-delivery.json'] = _json(receipt)
    # Finish every read/validation/render before creating anything. Validate again
    # to catch archive changes during projection, without recording a checkpoint.
    validate_archive(run, require_retained=True)
    if (run / 'review.json').read_bytes() != source or manifest_path.read_bytes() != manifest_bytes:
        raise ValueError('source changed during delivery preparation')
    created_dirs, owned_files = [], []
    try:
        missing = []
        current = destination.parent
        while not current.exists():
            missing.append(current)
            current = current.parent
        for directory in reversed(missing):
            safe_path(directory).mkdir()
            created_dirs.append(directory)
        safe_path(destination).mkdir()  # exclusive, even on a collision race
        created_dirs.append(destination)
        for name, data in files.items():
            path = safe_path(destination / name)
            _write_file(path, data, owned_files)
        return destination
    except BaseException:
        for path in reversed(owned_files):
            try:
                safe_path(path).unlink(missing_ok=True)
            except (OSError, ValueError):
                pass
        for directory in reversed(created_dirs):
            try:
                safe_path(directory).rmdir()  # never recursively remove foreign content
            except (OSError, ValueError):
                pass
        raise
