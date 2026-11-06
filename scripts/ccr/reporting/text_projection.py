"""Pure original-source text projection shared by delivery and publication."""
import hashlib
import heapq
import json
import re
from urllib.parse import urlsplit
from ccr.reporting import markdown
from ccr.reporting.check_disclosure import disclosure_view, sanitize_public_detail
from ccr.contracts import check_disclosure
from ccr.contracts.check_disclosure import EXPLANATION_COMMAND, OMITTED, sensitive_text_ranges
from ccr.contracts.disclosure_paths import _POSIX_PATH, _QUOTED_PATH, _SOURCE_TOKENS, _local_start, source_tokens
from ccr.contracts.disclosure_text import sensitive_values_from_text

_HTTP_CONTEXT = re.compile(
    r'''(?ix)(?<!\S)(?:GET|HEAD|POST|PUT|PATCH|DELETE|CONNECT|OPTIONS|TRACE|
    (?:endpoint|ruta|route|path)[ \t]+HTTP|HTTP[ \t]+(?:endpoint|route|path)|endpoint)[ \t]*:?[ \t]+[`'"]?$''')
_COMMAND_OMISSION = '[comprobación registrada; comando omitido]'


def _source_tokens(value):
    return source_tokens(value, check_disclosure.projected_url_spans(value))


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

    def __init__(self, record, manifest, project, source_hash, *, check_disclosure_context=None,
                 check_disclosure_sources=None, editorial_texts=()):
        self.source_hash = source_hash
        self.disclosure = disclosure_view(record, check_disclosure_context, check_disclosure_sources)
        editorial_texts = tuple(editorial_texts)
        self.new_policy = record.get('schema_version') == 13 or self.disclosure is not None or any(editorial_texts)
        self.disclosure_rows = {row['id']: row for row in self.disclosure['checks']} if self.disclosure else {}
        self.check_ids = [check['id'] for check in record['checks']]
        from ccr.reporting.projections import public_sensitive_values
        self.secrets = public_sensitive_values(record, self.disclosure, check_disclosure_sources or {},
                                               editorial_texts=(check_disclosure_context, *editorial_texts))
        # The proof view is a fresh projection. Apply the complete privacy set
        # before either portable commands or appended check details consume it.
        for row in (self.disclosure or {}).get('checks', []):
            row['command'] = sanitize_public_detail(row['command'], self.secrets, syntax='structured')
            row['resources'] = [sanitize_public_detail(path, self.secrets) for path in row['resources']]
            row['explanation'] = sanitize_public_detail(row['explanation'], self.secrets, explanation=True)
        commands = {check['command'] for check in record['checks']}
        commands.update(markdown.markdown_text(command) for command in tuple(commands))
        self.commands = sorted(commands, key=len, reverse=True)
        self.repo_roots = [str(project), manifest.get('repository_path', '')]
        self.private_roots = [manifest.get('archive_root', '')]
        self.changed = []

    def retained(self, value):
        # A provenance label, not a path/URL or a new human review identity.
        return 'retained:' + self.source_hash + '#ref-' + _hash(value.encode('utf-8'))[:16]

    def public_url(self, value, *, spellings=None):
        if not _public_url(value):
            return None
        # Syntax alone does not make a locator safe to share. Apply the same
        # secret policy as prose, including legacy deliveries without a sidecar.
        candidate = re.sub(r'^https?:', lambda match: match.group().lower(),
                           value, flags=re.IGNORECASE)
        if sensitive_values_from_text(candidate):
            return None
        if spellings is None:
            spellings = check_disclosure._secret_spellings(self.secrets)
        return None if check_disclosure.private_projected_url(candidate, spellings) else value

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
            r'(?i)(?:[a-z]:[\\/]|\\\\|//\S|file:|(?<![\w/\\])~[^/\\\s]*[/\\]|(?<![\w/\\.\-])/(?!/)\S)', span)
            for span in spans)
        if (private
                or (self.secrets and check_disclosure.redact_projected_text(
                    value, check_disclosure._secret_spellings(self.secrets)) != value)
                or any(_public_url(span) and self.public_url(span) is None for span in spans)
                or any(root.replace('\\', '/').lower() in value.replace('\\', '/').lower()
                       for root in roots if root)):
            raise ValueError('private structural value cannot be delivered: ' + path)
        return value

    def _http_members(self, value):
        """Classify HTTP-list members in original coordinates, before omission."""
        last_http_end = None
        context_start = 0
        for match, end in _source_tokens(value):
            if match.group('url') is not None:
                last_http_end = None
                context_start = end
                continue
            # Start/whitespace establishes an independent token; punctuation
            # inside a filename does not. Search the original string so the
            # bounded window cannot invent a start-of-text boundary.
            explicit = _HTTP_CONTEXT.search(value, max(context_start, match.start() - 128), match.start())
            continuation = (last_http_end is not None and re.fullmatch(
                r'''(?ix)[ \t`'"]*(?:(?:,|y|and|o|or)[ \t`'"]*)+''', value[last_http_end:match.start()]))
            quoted = match.group('quoted_path')
            local = match.group('local')
            if local is not None:
                # A method inside a filename cannot lend authority. An actual
                # method before this member still anchors its HTTP-list peers.
                last_http_end = match.start() + len(local.rstrip(',')) if explicit or continuation else None
                candidates = []
            elif quoted is not None:
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

    def _local_members(self, value):
        for match, end in _source_tokens(value):
            if match.group('local') is not None:
                yield _local_start(match), end

    def _local_text(self, value):
        core = value.rstrip(',')
        suffix = value[len(core):]
        if any(_relative_to_root(core, root) is not None for root in self.private_roots):
            return self.retained(core) + suffix
        for root in self.repo_roots:
            relative = _relative_to_root(core, root)
            if relative is not None:
                return (relative or '[repositorio revisado]') + suffix
        return ('[referencia privada]' if core.lower().startswith('file:') else '[ruta privada]') + suffix

    def _source_omissions(self, value, omit_commands, spellings):
        # Recognize copies globally in original coordinates. Expanding an
        # intersected quoted path protects its whole filename, even if a copy
        # consists only of a delimiter or extends across several members.
        streams = []
        if spellings:
            matches = check_disclosure._sensitive_text_ranges(value, spellings, markdown_escapes=True)
            streams.append(((*span, False) for span in matches))
        if omit_commands and self.commands:
            streams.append(((*span, True) for span in sensitive_text_ranges(value, self.commands)))
        urls = ()
        if self.new_policy:
            # An omission must never detach a URL's query from its authority.
            streams.append(((*span, False) for span in check_disclosure.private_url_spans(value)))
            urls = check_disclosure.projected_url_spans(value)
        if not streams:
            return
        members = heapq.merge((match.span() for match in re.finditer(_QUOTED_PATH, value)),
                              self._http_members(value), self._local_members(value), urls)
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
        spellings = (check_disclosure._secret_spellings(self.secrets | sensitive_values_from_text(value))
                     if self.new_policy else ())
        events = heapq.merge(
            ((*span[:2], 'omission', span[2]) for span in self._source_omissions(value, omit_commands, spellings)),
            ((*span, 'http', False) for span in self._http_members(value)),
            ((*span, 'local', False) for span in self._local_members(value)),
            key=lambda event: (event[0], event[2] != 'omission'))
        chunks, cursor = [], 0
        for first, last, kind, command in events:
            if first < cursor:
                continue
            chunks.append(self._text_fragment(value[cursor:first]))
            if kind == 'omission':
                chunks.append(_COMMAND_OMISSION if command else OMITTED)
            elif kind == 'local':
                chunks.append(self._local_text(value[first:last]))
            else:
                chunks.append(value[first:last])
            cursor = last
        chunks.append(self._text_fragment(value[cursor:]))
        value = ''.join(chunks)
        # Relative Markdown links cannot resolve from the delivery directory.
        url_spellings = () if self.new_policy else None
        # Source omissions may consume a delimiter that was also part of a
        # known spelling. Stop at the omission, not at a later link's close.
        value = re.sub(r'\[([^\]\r\n]+)\]\((\[(?:omitido|referencia privada)\])\)?',
                       lambda match: match[1] + ' · ' + match[2], value)
        value = re.sub(r'\[([^\]\r\n]+)\]\(([^\[)\r\n]+)\)',
                       lambda match: match.group() if self.public_url(match[2], spellings=url_spellings)
                       else match[1] + ' · ' + match[2], value)
        # Source copies were omitted before fragmenting. Recheck the
        # joined value once, including any text produced by the projection.
        return check_disclosure.redact_projected_text(value, spellings) if self.new_policy else value

    def _text_fragment(self, value):
        if not value:
            return value

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
                    if closing:
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

        # Recognize quoted members before URLs. Keep those members in their
        # surrounding ordinary text so HTTP-list context is not lost. No input
        # placeholders are restored into an already sanitized result.
        chunks, cursor = [], 0
        for match, end in _source_tokens(value):
            if match['url'] is None:
                continue
            url = self.public_url(value[match.start():end], spellings=() if self.new_policy else None)
            chunks.extend((segment(value[cursor:match.start()]), url or '[referencia privada]'))
            cursor = end
        return ''.join(chunks) + segment(value[cursor:])

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
