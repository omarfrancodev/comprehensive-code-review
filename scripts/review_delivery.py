#!/usr/bin/env python3
"""Explicitly deliver a portable projection of a retained review; never review again."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

import review_artifacts as artifacts
import review_contract as contract


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def _json(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n').encode('utf-8')


def _public_url(value):
    try:
        parsed = urlsplit(value)
        # Accessing port also rejects malformed authority syntax.
        port = parsed.port
        return (parsed.scheme in {'http', 'https'} and bool(parsed.hostname)
                and not parsed.username and not parsed.password
                and not any(char.isspace() for char in value)
                and (port is None or 0 < port <= 65535))
    except ValueError:
        return False


class _Projection:
    def __init__(self, record, manifest, project, source_hash):
        self.source_hash = source_hash
        self.commands = sorted({check['command'] for check in record['checks']}, key=len, reverse=True)
        self.repo_roots = [str(project), manifest['repository_path']]
        self.private_roots = [manifest['archive_root']]
        self.changed = []

    def retained(self, value):
        # A provenance label, not a path/URL or a new human review identity.
        return 'retained:' + self.source_hash + '#ref-' + _hash(value.encode('utf-8'))[:16]

    def reference(self, value):
        if _public_url(value):
            return value
        projected = self.text(value)
        if re.match(r'^(?:[A-Za-z]:[\\/]|[\\/]|file:)', projected):
            return self.retained(value)
        return projected

    def text(self, value):
        for command in self.commands:
            value = value.replace(command, '[comprobación registrada; comando omitido]')
            value = value.replace(contract.markdown_text(command), '[comprobación registrada; comando omitido]')

        def segment(value):
            value = re.sub(r'(?i)file://[^\s;|<>\)\]]+', '[referencia privada]', value)
            value = re.sub(r'(?<![\w:])//[^\s;|<>\)\]]+', '[ruta privada]', value)
            for root in self.private_roots:
                normalized = root.replace('\\', '/')
                for spelling in dict.fromkeys((root, normalized)):
                    value = re.sub(re.escape(spelling) + r'(?:[/\\][^\s;|<>\)\]]*)?',
                                   lambda match: self.retained(match.group()), value, flags=re.IGNORECASE)
            for root in self.repo_roots:
                for spelling in dict.fromkeys((root, root.replace('\\', '/'))):
                    value = re.sub(re.escape(spelling.rstrip('/\\')) + r'[/\\]', '', value, flags=re.IGNORECASE)
                    value = re.sub(re.escape(spelling) + r'(?=$|[\s;|<>\)\]])', '[repositorio revisado]', value, flags=re.IGNORECASE)
            value = re.sub(r'(?i)(?<![a-z0-9])[a-z]:[\\/][^\s;|<>\)\]]+', '[ruta privada]', value)
            value = re.sub(r'\\\\[^\s;|<>\)\]]+', '[ruta privada]', value)
            # Preserve HTTP business paths expressed without a host.
            value = re.sub(r'(?<![\w:#/<])/(?!/)[^\s;|<>\)\]]+',
                           lambda match: match.group() if re.match(r'^/(?:api|v[0-9]+)(?:/|$)', match.group()) else '[ruta privada]', value)
            value = re.sub(r'(?<![\w/\\])(?:evidence|_?archive)[/\\][^\s;|<>\)\]]+',
                           lambda match: self.retained(match.group()), value)
            return value

        # Sanitize URL and non-URL spans separately; placeholders could collide
        # with caller content and accidentally restore a private path.
        spans = re.split(r'(https?://[^\s<>\)\]]+)', value, flags=re.IGNORECASE)
        value = ''.join(span if _public_url(span) else '[referencia privada]' if span.lower().startswith(('http://', 'https://'))
                        else segment(span) for span in spans)
        # Relative Markdown links cannot resolve from the delivery directory.
        value = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)',
                       lambda match: match.group() if _public_url(match[2]) else match[1] + ' · ' + match[2], value)
        return value

    def value(self, value, path='record'):
        if isinstance(value, dict):
            return {key: self.value(item, path + '.' + key) for key, item in value.items()}
        if isinstance(value, list):
            return [self.value(item, path + '[' + str(index) + ']') for index, item in enumerate(value)]
        if not isinstance(value, str):
            return value
        if path.endswith('.command'):
            projected = '[comprobación registrada; comando omitido]'
        elif path.endswith(('.url', '.previous_url')):
            projected = value if _public_url(value) else None
        elif path.endswith(('.reference', '.previous_reference')) and path != 'record.scope.reference' and not _public_url(value):
            projected = self.retained(value)
        elif path == 'record.scope.reference':
            projected = self.reference(value)
        else:
            projected = self.text(value)
            if path.endswith('.location.path'):
                projected = projected.replace('\\', '/')
                if projected.startswith('/'):
                    projected = '[ubicación privada retenida]'
        if projected != value:
            self.changed.append(path)
        return projected


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
        return contract.reference_text(projection.reference(value))
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
                lines.append('- ' + contract.markdown_text(text(item['title'])) + ' · ' + reference(item['reference'])
                             + ' · identidad: ' + contract.markdown_text(text(item['identity']))
                             + ' · secciones: ' + '; '.join(contract.markdown_text(section) for section in sections)
                             + ' · versión: ' + contract.markdown_text(version))
            else:
                if not isinstance(item['references'], list) or not item['references']:
                    raise ValueError('observations require collected evidence references')
                references = [reference(locator) for locator in item['references']]
                lines.append('- ' + contract.markdown_text(text(item['text'])) + ' · referencias: ' + '; '.join(references)
                             + ' · versión: ' + contract.markdown_text(version))
    return ('\n'.join(lines) + '\n').encode('utf-8') if entries_present else None


def _human(text):
    return re.sub(r'retained:[0-9a-f]{64}(?:\\)?#ref-[0-9a-f]{16}', 'referencia interna no incluida', text)


def _brief(record):
    scope = record['scope']
    lines = ['## Resumen de revisión', '', '### Veredicto: **' + contract.VERDICTS[record['verdict']] + '**', '',
             contract.markdown_text(record['verdict_reason']), '',
             '- **Alcance:** ' + contract.markdown_text(scope['repository']) + ' · ' + contract.MODE_LABELS[scope['mode']],
             '- **Versión:** ' + contract.markdown_text(scope['base'] or 'sin comparación') + ' → '
             + contract.markdown_text(scope['head'] or scope['snapshot']),
             '- **Verificación:** ' + contract.VERIFICATION[record['coverage']['verification']],
             '- **Cobertura obsoleta:** ' + ('sí' if record['coverage']['stale'] else 'no')]
    if scope['snapshot']:
        lines.append('- **Snapshot:** ' + contract.markdown_text(scope['snapshot']))
    if scope['target']:
        lines.append('- **Destino:** ' + contract.markdown_text(scope['target']))
    if scope['reference']:
        lines.append('- **Referencia:** ' + contract.reference_text(scope['reference']))
    if record.get('review_id'):
        lines.append('- **ID de revisión:** ' + record['review_id'])
    if record.get('previous_reviews'):
        lines.append('- **Revisiones previas:** ' + contract.previous_reviews_text(record, 'user'))
    lines.extend(['', '### Hallazgos', ''])
    confirmed = sorted((item for item in record['findings'] if item['status'] == 'confirmed'), key=lambda item: (item['priority'], item['id']))
    lines.extend(['**Confirmados:** ' + contract.confirmed_counts_text(record['findings']), ''])
    for item in confirmed:
        location = item['location']
        label = (str(location['path']) + ':' + str(location['line'])) if item['type'] == 'code' else location['section']
        lines.append('- ' + item['id'] + ' · ' + item['priority'] + ' · ' + contract.markdown_text(item['title'])
                     + ' · ' + (contract.reference_text(location['url']) + ' · ' if location['url'] else '')
                     + contract.markdown_text(label) + ' · bloqueante: ' + ('sí' if item['blocking'] else 'no'))
        for key, label in [('scenario', 'Escenario'), ('impact', 'Impacto'), ('correction', 'Corrección requerida')]:
            lines.append('  - **' + label + ':** ' + contract.markdown_text(item[key]))
    if not confirmed:
        lines.append('- Ningún hallazgo confirmado.')
    lines.extend(['', '### Comprobaciones', ''])
    for check in record['checks']:
        lines.append('- ' + check['id'] + ' · ' + contract.CHECK_STATUS[check['status']] + ' · versión: '
                     + contract.markdown_text(check['revision']) + ' · ' + contract.markdown_text(check['evidence'] or 'Sin ejecución'))
        if check.get('reference'):
            lines.append('  - Referencia: ' + contract.reference_text(check['reference']))
        if check['reused']:
            lines.append('  - Evidencia reutilizada: ' + contract.markdown_text(check['reuse_reason']))
        if check['failure_kind']:
            lines.append('  - Clasificación: ' + contract.FAILURE_KINDS[check['failure_kind']])
    if not record['checks']:
        lines.append('- Inspección estática; sin comprobaciones ejecutadas.')
    uncertainties = [item['id'] + ': ' + item['title'] + ' · ' + item['scenario'] for item in record['findings'] if item['status'] == 'unresolved']
    uncertainties.extend(item['detail'] for item in record['coverage']['limitations'])
    uncertainties.extend(row['details'] for row in record['coverage'].get('areas', []) if row['status'] in {'partial', 'not_evaluated'})
    uncertainties.extend(record['reservations'])
    if uncertainties:
        lines.extend(['', '### Incertidumbres y reservas', ''])
        lines.extend('- ' + contract.markdown_text(item) for item in dict.fromkeys(uncertainties))
    if record['rereview']:
        lines.extend(['', '### Re-review', ''])
        for item in record['rereview']:
            source = ' · anterior: ' + contract.markdown_text(item['previous_title']) if item.get('previous_title') else ''
            lines.append('- ' + item['id'] + ' · ' + contract.REREVIEW_STATUS[item['status']] + source + ' · ' + contract.markdown_text(item['details']))
    return '\n'.join(lines) + '\n'


def _write_file(path, data, owned_files):
    with artifacts.safe_path(path).open('xb') as stream:
        owned_files.append(path)
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def deliver(run_dir, delivery, project_root, output_root=None, context=None):
    """Return a new delivery directory, refusing every implicit or unsafe destination."""
    if delivery not in {'full', 'brief'}:
        raise ValueError('an explicit delivery full|brief is required')
    artifacts.validate(run_dir, require_retained=True)
    run = artifacts.safe_path(run_dir)
    manifest_bytes = (run / 'cierre.json').read_bytes()
    manifest = artifacts.read_json(run / 'cierre.json')
    project = artifacts.safe_path(project_root)
    selected = Path(output_root) if output_root is not None else project / 'docs' / 'ccr' / 'reviews'
    if not selected.is_absolute() and selected.drive:
        raise ValueError('drive-relative output roots are not allowed')
    root = artifacts.safe_path(selected if selected.is_absolute() else project / selected)
    temporary = [artifacts.safe_path(raw) for raw in manifest.get('temporary_paths', [])]
    if any(artifacts._contains(path, candidate) for path in temporary for candidate in (project, root)):
        raise ValueError('delivery requires a persistent checkout/output, outside registered temporary resources')
    if artifacts._contains(artifacts.safe_path(manifest['archive_root']), root):
        raise ValueError('delivery cannot write into its retained source archive')
    if not project.is_dir() or artifacts.safe_path(artifacts._git(project, 'rev-parse', '--show-toplevel')) != project:
        raise ValueError('--project-root must be the explicit Git repository root')
    identity = artifacts.repository_identity(project)
    expected = manifest.get('repository_identity')
    if (expected is not None and identity != expected) or (expected is None and _hash(identity.encode('utf-8'))[:20] != manifest['repository_key']):
        raise ValueError('project-root belongs to a different repository')
    source = (run / 'review.json').read_bytes()
    record = artifacts.read_json(run / 'review.json')
    source_hash = _hash(source)
    identifier = record.get('review_id') if record['schema_version'] in (6, 7) else manifest.get('run_id', run.name.rpartition('-')[2])
    if not isinstance(identifier, str) or not re.fullmatch(r'(?:CR-)?[0-9a-f]{20}', identifier):
        raise ValueError('known review/run identity required')
    destination = artifacts.safe_path(root / run.parent.name / identifier)
    if artifacts._contains(artifacts.safe_path(manifest['archive_root']), destination) or any(artifacts._contains(path, destination) for path in temporary):
        raise ValueError('delivery destination overlaps its retained archive or temporary resources')
    if destination.exists():
        raise ValueError('delivery destination already exists')
    projection = _Projection(record, manifest, project, source_hash)
    portable = projection.value(record)
    errors = contract.validate(portable)
    if errors:
        raise ValueError('portable record is invalid: ' + '; '.join(errors))
    source_label = identifier if record['schema_version'] in (6, 7) else 'identidad de archivo ' + identifier
    notice = ('\n> Proyección portable de la revisión retenida (' + source_label + '). No es una nueva revisión ni una nueva ejecución. '
              'Comandos y referencias privadas omitidos; la procedencia e integridad se registran en .ccr-delivery.json.\n')
    files = ({'review.json': _json(portable), 'informe.md': (_human(contract.render(portable)) + notice).encode('utf-8')}
             if delivery == 'full' else {'resumen.md': (_human(_brief(portable)) + notice).encode('utf-8')})
    contextual = _context_markdown(context, projection)
    if contextual is not None:
        files['contexto.md'] = _human(contextual.decode('utf-8')).encode('utf-8')
    files['.ccr-delivery.json'] = _json({'schema_version': 1, 'delivery': delivery, 'source_id': identifier,
        'source_id_kind': 'review_id' if record['schema_version'] in (6, 7) else 'run_id',
        'source_hash': source_hash, 'source_schema_version': record['schema_version'], 'projection': 'portable',
        'projected_fields': projection.changed, 'hashes': {name: _hash(data) for name, data in files.items()}})
    # Finish every read/validation/render before creating anything. Validate again
    # to catch archive changes during projection, without recording a checkpoint.
    artifacts.validate(run, require_retained=True)
    if (run / 'review.json').read_bytes() != source or (run / 'cierre.json').read_bytes() != manifest_bytes:
        raise ValueError('source changed during delivery preparation')
    created_dirs, owned_files = [], []
    try:
        missing = []
        current = destination.parent
        while not current.exists():
            missing.append(current)
            current = current.parent
        for directory in reversed(missing):
            artifacts.safe_path(directory).mkdir()
            created_dirs.append(directory)
        artifacts.safe_path(destination).mkdir()  # exclusive, even on a collision race
        created_dirs.append(destination)
        for name, data in files.items():
            path = artifacts.safe_path(destination / name)
            _write_file(path, data, owned_files)
        return destination
    except BaseException:
        for path in reversed(owned_files):
            try:
                artifacts.safe_path(path).unlink(missing_ok=True)
            except (OSError, ValueError):
                pass
        for directory in reversed(created_dirs):
            try:
                artifacts.safe_path(directory).rmdir()  # never recursively remove foreign content
            except (OSError, ValueError):
                pass
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', required=True)
    parser.add_argument('--delivery', choices=('full', 'brief'), required=True)
    parser.add_argument('--project-root', required=True)
    parser.add_argument('--output-root', help='Delivery root, relative to project-root or absolute; not the final scope/review directory')
    parser.add_argument('--context', help='Optional JSON containing only previously collected context')
    args = parser.parse_args()
    try:
        context = artifacts.read_json(args.context) if args.context else None
        destination = deliver(args.run_dir, args.delivery, args.project_root, args.output_root, context)
        print(json.dumps({'delivery_dir': str(destination)}, ensure_ascii=False))
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
