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

# One shared boundary for classification and for excluding filename substrings
# from URL recognition. A lone terminal backslash still belongs to the member.
_QUOTED_PATH = r'''(?P<quote>[`'"])(?P<quoted_path>(?:/|[A-Za-z]:[\\/]|\\\\|(?i:file:))(?:\\(?:[\s\S]|$)|(?!(?P=quote))[^\\])*)(?:(?P<closing>(?P=quote))|$)'''
_POSIX_PATH = r'''(?<![\w:#/<])/(?!/)[^\s;|<>\)\]`'"]+'''
_COMMAND_OMISSION = '[comprobación registrada; comando omitido]'


def _relative_to_root(value, root):
    if not root:
        return None
    root = root.rstrip('/\\')
    normalized, prefix = value.replace('\\', '/').lower(), root.replace('\\', '/').lower()
    if normalized == prefix:
        return ''
    return value[len(root) + 1:] if normalized.startswith(prefix + '/') else None


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
    # Contract fields are deliberately classified. New strings require an
    # explicit portability policy rather than silently rewriting identities.
    STRUCTURAL = set('''stage profile verdict review_id
        scope.repository scope.mode scope.base scope.head scope.snapshot scope.target
        findings[].id findings[].type findings[].status findings[].priority findings[].origin
        findings[].evidence[].kind findings[].evidence[].check_id
        checks[].id checks[].revision checks[].status checks[].failure_kind
        checks[].execution.kind checks[].execution.executor
        coverage.verification coverage.areas[].area coverage.areas[].status
        coverage.areas[].finding_ids[] coverage.limitations[].kind
        coverage.areas[].dimensions[].id coverage.areas[].dimensions[].status
        coverage.areas[].dimensions[].finding_ids[]
        coverage.areas[].applicability coverage.areas[].groups[].ids[]
        coverage.areas[].groups[].status coverage.areas[].groups[].evidence_ids[]
        coverage.areas[].groups[].finding_ids[] coverage.evidence[].id
        coverage.evidence[].kind coverage.evidence[].check_id
        coverage.execution.selection_source coverage.execution.status
        coverage.execution.plan[].id coverage.execution.plan[].role
        coverage.execution.plan[].selection_id coverage.execution.plan[].superseded_by
        coverage.execution.profile_history[].id coverage.execution.profile_history[].profile
        coverage.execution.profile_history[].selection_source coverage.execution.profile_history[].phase
        coverage.execution.profile_history[].actor.kind coverage.execution.profile_history[].actor.name
        coverage.execution.profile_history[].actor.provider_id
        coverage.execution.profile_history[].affected_assignments[]
        coverage.execution.profile_history[].changed_from coverage.execution.profile_history[].event_id
        coverage.execution.results[].assignment_id coverage.execution.results[].reviewer_context
        coverage.execution.results[].provider_id coverage.execution.fallbacks[].assignments[]
        coverage.execution.fallbacks[].reason responsible.name responsible.username
        change_authors[].name change_authors[].username change_authors[].commits[]
        presentation.kind description.identity previous_reviews[].review_id
        compact_identity.inputs_sha256 compact_identity.logical_scope_identity compact_identity.created_at
        grandfathered_ids.findings[] grandfathered_ids.checks[]
        rereview[].id rereview[].status rereview[].previous_review_id
        rereview[].previous_finding_id rereview[].check_ids[] resources.cleanup resources.publication'''.split())
    PROSE = set('''profile_reason verdict_reason reservations[]
        findings[].title findings[].scenario findings[].impact findings[].correction
        findings[].blocking_reason findings[].evidence[].details findings[].location.section
        checks[].purpose checks[].evidence checks[].reuse_reason checks[].rerun_reason
        coverage.flows[] coverage.limitations[].detail coverage.limitations[].public_summary
        coverage.areas[].details coverage.areas[].dimensions[].details coverage.execution.fallbacks[].detail
        coverage.areas[].applicability_reason coverage.areas[].groups[].reason coverage.evidence[].detail
        coverage.execution.profile_history[].reason coverage.execution.profile_history[].authority
        responsible.source change_authors[].source description.details
        presentation.subject rereview[].details rereview[].previous_title resources.residuals[]'''.split())

    def __init__(self, record, manifest, project, source_hash, *, check_disclosure_context=None, check_disclosure_sources=None):
        self.source_hash = source_hash
        self.disclosure = disclosure_view(record, check_disclosure_context, check_disclosure_sources)
        self.new_policy = record.get('schema_version') == 13 or self.disclosure is not None
        self.disclosure_rows = {row['id']: row for row in self.disclosure['checks']} if self.disclosure else {}
        self.check_ids = [check['id'] for check in record['checks']]
        self.secrets = private_values(record, self.disclosure, check_disclosure_sources or {})
        commands = {check['command'] for check in record['checks']}
        commands.update(markdown.markdown_text(command) for command in tuple(commands))
        self.commands = sorted(commands, key=len, reverse=True)
        self.repo_roots = [str(project), manifest.get('repository_path', '')]
        self.private_roots = [manifest.get('archive_root', '')]
        self.changed = []

    def retained(self, value):
        # A provenance label, not a path/URL or a new human review identity.
        return 'retained:' + self.source_hash + '#ref-' + _hash(value.encode('utf-8'))[:16]

    def public_url(self, value):
        if not _public_url(value):
            return None
        # Syntax alone does not make a locator safe to share. Apply the same
        # secret policy as prose, including legacy deliveries without a sidecar.
        candidate = re.sub(r'^https?:', lambda match: match.group().lower(),
                           value, flags=re.IGNORECASE)
        return value if safe_text(candidate, self.secrets) == candidate else None

    def reference(self, value):
        if self.public_url(value):
            return value
        if _public_url(value):
            return self.retained(value)
        projected = self.text(value, omit_commands=False)
        if re.match(r'^(?:[A-Za-z]:[\\/]|[\\/]|file:)', projected):
            return self.retained(value)
        return projected

    def structural(self, value, path):
        roots = self.repo_roots + self.private_roots
        spans = re.split(r'(https?://[^\s<>\)\]]+)', value, flags=re.IGNORECASE)
        private = any(not _public_url(span) and re.search(
            r'(?i)(?:[a-z]:[\\/]|\\\\|//\S|file:|(?<![\w/\\.\-])/(?!/)\S)', span)
            for span in spans)
        if (private
                or (self.secrets and safe_text(value, self.secrets, redact_paths=False) != value)
                or any(_public_url(span) and self.public_url(span) is None for span in spans)
                or any(root.replace('\\', '/').lower() in value.replace('\\', '/').lower()
                       for root in roots if root)):
            raise ValueError('private structural value cannot be delivered: ' + path)
        return value

    def _http_members(self, value):
        """Classify HTTP-list members in original coordinates, before omission."""
        last_http_end = None
        context_start = 0
        for match in re.finditer(_QUOTED_PATH + r'|(?P<url>https?://[^\s<>\)\]]+)|' + _POSIX_PATH,
                                 value, flags=re.IGNORECASE):
            if match.group('url') is not None:
                last_http_end = None
                context_start = match.end()
                continue
            prefix = value[max(context_start, match.start() - 128):match.start()]
            explicit = re.search(
                r'''(?ix)(?<![\w-])(?:GET|HEAD|POST|PUT|PATCH|DELETE|CONNECT|OPTIONS|TRACE|
                (?:endpoint|ruta|route|path)[ \t]+HTTP|HTTP[ \t]+(?:endpoint|route|path)|endpoint)[ \t]*:?[ \t]+[`'"]?$''',
                prefix)
            continuation = (last_http_end is not None and re.fullmatch(
                r'''(?ix)[ \t`'"]*(?:(?:,|y|and|o|or)[ \t`'"]*)+''', value[last_http_end:match.start()]))
            quoted = match.group('quoted_path')
            if quoted is not None:
                active = match.group('closing') and (explicit or continuation)
                last_http_end = match.end() if active else None
                candidates = [(match.start(), match.end(), quoted)] if active and not any(
                    char.isspace() for char in quoted) else []
            elif explicit or continuation:
                candidates, offset = [], match.start()
                for part in re.split(r'''(,)(?=[`'"]*/)''', match.group()):
                    if part != ',':
                        core = part.rstrip(",`'\"")
                        candidates.append((offset, offset + len(core), core))
                        last_http_end = offset + len(core)
                    offset += len(part)
            else:
                last_http_end = None
                context_start = match.end()
                continue
            context_start = match.end()
            for first, last, path in candidates:
                if (re.match(r'^/(?:api|v[0-9]+)(?:/|$)', path)
                        and not any(_relative_to_root(path, root) is not None
                                    for root in self.private_roots + self.repo_roots)):
                    yield first, last

    def _source_omissions(self, value, omit_commands):
        # Recognize copies globally in original coordinates. Expanding an
        # intersected quoted path protects its whole filename, even if a copy
        # consists only of a delimiter or extends across several members.
        streams = []
        if self.new_policy and self.secrets:
            streams.append(((*span, False) for span in sensitive_text_ranges(value, self.secrets)))
        if omit_commands and self.commands:
            streams.append(((*span, True) for span in sensitive_text_ranges(value, self.commands)))
        if not streams:
            return
        members = heapq.merge((match.span() for match in re.finditer(_QUOTED_PATH, value)),
                              self._http_members(value))
        member = next(members, None)
        pending = None
        for first, last, command in heapq.merge(*streams):
            while member is not None and member[1] <= first:
                member = next(members, None)
            while member is not None and member[0] < last:
                first, last = min(first, member[0]), max(last, member[1])
                member = next(members, None)
            if pending is not None and first <= pending[1]:
                pending = pending[0], max(last, pending[1]), command or pending[2]
            else:
                if pending is not None:
                    yield pending
                pending = first, last, command
        if pending is not None:
            yield pending

    def text(self, value, omit_commands=True):
        # Public HTTP members and omissions retain their original source spans.
        # Omissions take precedence; public neighbors do not need an anchor to
        # survive in the redacted spelling, nor can input markers create one.
        events = heapq.merge(
            ((*span[:2], 'omission', span[2]) for span in self._source_omissions(value, omit_commands)),
            ((*span, 'http', False) for span in self._http_members(value)),
            key=lambda event: (event[0], event[2] != 'omission'))
        chunks, cursor = [], 0
        for first, last, kind, command in events:
            if first < cursor:
                continue
            chunks.append(self._text_fragment(value[cursor:first]))
            if kind == 'omission':
                chunks.append(_COMMAND_OMISSION if command else OMITTED)
            else:
                route = value[first:last]
                chunks.append(safe_text(route, self.secrets, redact_paths=False) if self.new_policy else route)
            cursor = last
        chunks.append(self._text_fragment(value[cursor:]))
        value = ''.join(chunks)
        # Relative Markdown links cannot resolve from the delivery directory.
        value = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)',
                       lambda match: match.group() if self.public_url(match[2]) else match[1] + ' · ' + match[2], value)
        return safe_text(value, self.secrets, redact_paths=False) if self.new_policy else value

    def _text_fragment(self, value):
        def redact(text):
            # Apply only after original quotation boundaries have been read,
            # but before a root rewrite could erase part of a sensitive value.
            if self.new_policy:
                text = safe_text(text, self.secrets, redact_paths=False)
            return text

        def segment(value):
            def normalize_roots(text):
                for root in self.private_roots:
                    if not root:
                        continue
                    for spelling in dict.fromkeys((root, root.replace('\\', '/'))):
                        text = re.sub(re.escape(spelling) + r'(?:[/\\][^\s;|<>\)\]]*)?',
                                      lambda match: self.retained(match.group()), text, flags=re.IGNORECASE)
                for root in self.repo_roots:
                    if not root:
                        continue
                    for spelling in dict.fromkeys((root, root.replace('\\', '/'))):
                        text = re.sub(re.escape(spelling.rstrip('/\\')) + r'[/\\]', '', text, flags=re.IGNORECASE)
                        text = re.sub(re.escape(spelling) + r'(?=$|[\s;|<>\)\]])', '[repositorio revisado]', text, flags=re.IGNORECASE)
                return text
            # Root rewriting must not truncate a quoted filename before its
            # privacy decision. Normalize ordinary text and whole members apart.
            chunks, cursor = [], 0
            for member in re.finditer(_QUOTED_PATH, value):
                chunks.extend((normalize_roots(value[cursor:member.start()]), member.group()))
                cursor = member.end()
            value = ''.join(chunks) + normalize_roots(value[cursor:])
            # Public HTTP members were classified before segmentation. Every
            # remaining absolute path needs the private/known-root policy.
            def posix_path(match):
                quoted = match.group('quoted_path')
                if quoted is not None:
                    closing = match.group('closing') or ''
                    shown = '[ruta privada]'
                    if redact(match.group()) != match.group():
                        # A sensitive copy can include the quotes themselves.
                        # Keep the original member opaque; never reparse its
                        # redacted spelling or relativize its remaining suffix.
                        shown = '[ruta privada]'
                    elif closing:
                        if any(_relative_to_root(quoted, root) is not None for root in self.private_roots):
                            shown = self.retained(quoted)
                        else:
                            for root in self.repo_roots:
                                relative = _relative_to_root(quoted, root)
                                if relative is not None:
                                    shown = relative or '[repositorio revisado]'
                                    break
                    return match.group('quote') + shown + closing
                return '[ruta privada]' + match.group()[len(match.group().rstrip(',')):]
            # Quoted paths are indivisible, even with spaces or internal commas.
            # Unterminated quoted paths fail closed through the end of the span.
            value = re.sub(_QUOTED_PATH + '|' + _POSIX_PATH, posix_path, value)
            value = re.sub(r'(?i)file://[^\s;|<>\)\]]+', '[referencia privada]', value)
            value = re.sub(r'(?<![\w:])//[^\s;|<>\)\]]+', '[ruta privada]', value)
            value = re.sub(r'(?i)(?<![a-z0-9])[a-z]:[\\/][^\s;|<>\)\]]+', '[ruta privada]', value)
            value = re.sub(r'\\\\[^\s;|<>\)\]]+', '[ruta privada]', value)
            value = re.sub(r'(?<![\w/\\])(?:evidence|_?archive)[/\\][^\s;|<>\)\]]+',
                           lambda match: self.retained(match.group()), value)
            return value

        # Read original quotation boundaries before redaction can change them.
        # Redact ordinary text before URL splitting too: a single learned
        # credential can span a repository root and a URL-shaped substring.
        chunks, cursor = [], 0
        for member in re.finditer(_QUOTED_PATH, value):
            chunks.extend((redact(value[cursor:member.start()]), member.group()))
            cursor = member.end()
        value = ''.join(chunks) + redact(value[cursor:])

        # Recognize quoted members before URLs. Keep those members in their
        # surrounding ordinary text so HTTP-list context is not lost. No input
        # placeholders are restored into an already sanitized result.
        chunks, cursor = [], 0
        for span in re.finditer(_QUOTED_PATH + r'|(?P<url>https?://[^\s<>\)\]]+)', value, flags=re.IGNORECASE):
            if span.group('url') is None:
                continue
            chunks.extend((segment(value[cursor:span.start()]),
                           span.group() if self.public_url(span.group()) else '[referencia privada]'))
            cursor = span.end()
        value = ''.join(chunks) + segment(value[cursor:])
        return redact(value)

    def value(self, value, path='record'):
        if isinstance(value, dict):
            if path == 'record.aliases':
                return {self.structural(key, path + ' key'): self.structural(item, path + ' value')
                        for key, item in value.items()}
            return {key: self.value(item, path + '.' + key) for key, item in value.items()}
        if isinstance(value, list):
            return [self.value(item, path + '[' + str(index) + ']') for index, item in enumerate(value)]
        if not isinstance(value, str):
            return value
        field = re.sub(r'\[\d+\]', '[]', path.removeprefix('record.'))
        if field in self.STRUCTURAL:
            projected = self.structural(value, path)
        elif field == 'description.status':
            projected = self.structural(value, path)
        elif field == 'checks[].command':
            index = int(re.search(r'checks\[(\d+)\]', path)[1])
            row = self.disclosure_rows.get(self.check_ids[index])
            projected = (row['command'] or EXPLANATION_COMMAND) if row else '[comprobación registrada; comando omitido]'
        elif path.endswith(('.url', '.previous_url')):
            projected = self.public_url(value)
        elif (path.endswith(('.reference', '.previous_reference')) or field == 'coverage.execution.fallbacks[].source') and field != 'scope.reference':
            projected = self.public_url(value) or self.retained(value)
        elif path == 'record.scope.reference':
            projected = self.reference(value)
        elif field == 'findings[].location.path':
            projected = self.text(value, omit_commands=False).replace('\\', '/')
            if projected.startswith('/'):
                projected = '[ubicación privada retenida]'
        elif field in self.PROSE:
            projected = self.text(value)
        else:
            raise ValueError('unclassified portable field: ' + path)
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
