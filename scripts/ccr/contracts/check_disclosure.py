"""Pure selected-byte proof and canonical selective disclosure contract.

The expected input identity is a trust anchor captured before review execution.
The resource manifest is hashed at workspace preparation, never after a check.
"""
import hashlib
from array import array
from bisect import bisect_left, bisect_right
import html
import json
import ntpath
import re
import shlex
from urllib.parse import urlsplit, unquote, unquote_plus

FIELDS = {'schema_version', 'review_id', 'source_sha256', 'input_identity', 'checks'}
ROW_FIELDS = {'id', 'command_sha256', 'execution_reference', 'mode', 'command', 'resources', 'explanation', 'evidence_reference'}
RESOURCE_FIELDS = {'path', 'revision', 'project_sha256', 'executed_sha256'}
OMITTED = '[omitido]'
EXPLANATION_COMMAND = '[comprobación explicada; comando no acreditado]'
MAX_BYTES = 1024 * 1024
RESOURCE_OPERAND = re.compile(r'(?i)\.(?:json|ya?ml|toml|ini|cfg|conf|config|xml|csv|tsv|txt|dat|bin|py|js|mjs|cjs|sh|ps1|dll|exe|csproj|sln|mk)$')
RESOURCE_FLAGS = {'--fixture', '--input', '--data', '--config', '--settings', '--file', '--output', '-o'}
SENSITIVE_URL_KEY = re.compile(r'(?i)(?:token|password|secret|api.?key|auth|credential)')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def source_digest(record):
    return digest(canonical(record))


def input_identity_for(record):
    return {key: record['scope'].get(key) for key in ('head', 'snapshot')}


def _relative(value):
    if not isinstance(value, str) or not value or '\x00' in value:
        return None
    value = value.replace('\\', '/')
    if value.startswith('/') or ntpath.splitdrive(value)[0] or any(part in ('', '.', '..') for part in value.split('/')):
        return None
    return value


def _read(sources, reference):
    if not isinstance(reference, str) or not reference.startswith('evidence/') or _relative(reference) is None:
        raise ValueError('disclosure requires a selected safe evidence reference')
    raw = sources.get(reference)
    if not isinstance(raw, bytes) or len(raw) > MAX_BYTES:
        raise ValueError('disclosure selected evidence is missing or exceeds its bound')
    return raw, json.loads(raw.decode('utf-8'))


def _secret_argument(argument):
    key = argument.split('=', 1)[0]
    return (key.startswith('-') or '=' in argument) and bool(re.search(
        r'(?i)(?:token|password|secret|api[-_]?key|authorization|credential)', key))


def _url_secrets(parsed):
    """Share URL classification and wire/decoded credential learning."""
    values = set()
    for component in (parsed.query, parsed.fragment):
        for pair in component.split('&'):
            key, separator, value = pair.partition('=')
            # A fragment can carry OAuth parameters directly or an SPA route
            # followed by '?'. Matching the decoded key also covers that prefix.
            if separator and SENSITIVE_URL_KEY.search(unquote_plus(key)):
                values.update((value, unquote_plus(value)))
    if parsed.password:
        # Userinfo preserves literal '+', unlike form query/fragment values.
        values.update((parsed.password, unquote(parsed.password)))
    return values


def _bounded_html_unescape(text):
    """Apply HTML semantics without arbitrary-sized numeric conversions."""
    def bounded_number(match):
        number = match.group()[2:].rstrip(';')
        prefix = number[0] if number[0] in 'xX' else ''
        digits = number[len(prefix):].lstrip('0') or '0'
        # Canonicalize the comparison input, never the selected source bytes.
        # Every larger significant value lies outside Unicode. Let HTML handle
        # the bounded replacement and all named/control-character semantics.
        if len(digits) > (6 if prefix else 7):
            return '&#1114112;'
        return '&#' + prefix + digits + ';'
    return html.unescape(re.sub(r'&#(?:[xX][0-9a-fA-F]+|[0-9]+);?', bounded_number, text))


def _argument_secrets(argument):
    """Extract credential values, including encoded URL queries/fragments."""
    values = set()
    header = re.fullmatch(r'(?:--header=|-H)?([\w-]+)\s*:\s*(.+)', argument)
    if header and SENSITIVE_URL_KEY.search(header.group(1)):
        credential = header.group(2).strip()
        values.add(credential)
        # Authentication schemes are public; the credential can be repeated on
        # its own in results, paths, or prose and must be redacted there too.
        values.add(re.sub(r'(?i)^(?:Bearer|Basic)\s+', '', credential))
    for text in re.findall(r'https?://[^\s<>\]\)]+', argument, re.IGNORECASE):
        try:
            parsed = urlsplit(_bounded_html_unescape(text))
            values.update(_url_secrets(parsed))
        except ValueError:
            continue
    return values


def sensitive_values(sources):
    values = set()
    for raw in sources.values():
        try:
            item = json.loads(raw)
        except (ValueError, TypeError, UnicodeDecodeError):
            continue
        if not isinstance(item, dict):
            continue
        argv = item.get('argv', [])
        secret_next = False
        for argument in argv if isinstance(argv, list) else []:
            if not isinstance(argument, str):
                continue
            values.update(_argument_secrets(argument))
            if secret_next:
                values.add(argument); secret_next = False
            if _secret_argument(argument):
                if '=' in argument: values.add(argument.split('=', 1)[1])
                else: secret_next = True
    return {value for value in values if value}


def private_values(record, view, sources):
    values = sensitive_values(sources)
    rows = {row['id']: row for row in view['checks']} if view else {}
    for raw in sources.values():
        try:
            execution = json.loads(raw)
        except (ValueError, TypeError, UnicodeDecodeError):
            continue
        if not isinstance(execution, dict) or execution.get('check_id') not in rows:
            continue
        row = rows[execution['check_id']]
        allowed = row['resources']
        for arg in execution.get('argv', []):
            if not isinstance(arg, str) or arg.startswith('-'):
                continue
            name = ntpath.basename(arg)
            if ('/' in arg or '\\' in arg or RESOURCE_OPERAND.search(name)):
                if not any(arg.replace('\\', '/').endswith(path) for path in allowed):
                    values.add(arg)
                    if len(name) > 3:
                        values.add(name)
    return values


def _redact_encoded_values(text, spellings):
    """Redact known encoded copies using source offsets, never decoded output."""
    if not spellings:
        return text
    entity = r'&(?:\#[xX][0-9a-fA-F]+|\#[0-9]+|[a-zA-Z][a-zA-Z0-9]+);?'
    encoded_starts = sorted({match.start() for match in re.finditer(r'(?:%[0-9a-fA-F]{2})+', text)}
                           | {match.start() for match in re.finditer(entity, text)})
    if not encoded_starts:
        return text
    shown = text
    starts = array('I', range(len(text)))
    ends = array('I', range(1, len(text) + 1))
    ranges = set()

    def collect():
        for secret in spellings:
            position = shown.find(secret)
            while position != -1:
                first, last = starts[position], ends[position + len(secret) - 1]
                encoded_index = bisect_left(encoded_starts, first)
                if encoded_index < len(encoded_starts) and encoded_starts[encoded_index] < last:
                    # Literal-only matches are handled by replace below. Do not
                    # retain one range per plain-text occurrence or per view.
                    ranges.add((first, last))
                    # Only withheld matches make their overlaps safe to skip.
                    following = position + len(secret)
                elif encoded_index < len(encoded_starts):
                    # Skip literal-only windows, but retain overlaps that can
                    # reach the next source encoding marker after normalization.
                    boundary = bisect_right(ends, encoded_starts[encoded_index])
                    following = max(position + 1, boundary - len(secret) + 1)
                else:
                    break
                position = shown.find(secret, following)

    def transform(pattern, convert):
        nonlocal shown, starts, ends
        parts, next_starts, next_ends = [], array('I'), array('I')
        cursor = 0
        for match in re.finditer(pattern, shown):
            first, last = match.span()
            parts.append(shown[cursor:first])
            next_starts.extend(starts[cursor:first])
            next_ends.extend(ends[cursor:first])
            replacement = convert(match)
            parts.append(replacement)
            # A UTF-8 escape run or displayed entity can produce several
            # characters. If it contains a secret, withhold that source run.
            next_starts.extend([starts[first]] * len(replacement))
            next_ends.extend([ends[last - 1]] * len(replacement))
            cursor = last
        parts.append(shown[cursor:])
        next_starts.extend(starts[cursor:])
        next_ends.extend(ends[cursor:])
        shown, starts, ends = ''.join(parts), next_starts, next_ends
        collect()

    markdown_escape = r'\\([\\`*{}\[\]()#+!_|>~])'
    # First preserve a credential's literal HTML/Markdown escape spelling.
    transform(r'(?:%[0-9a-fA-F]{2})+', lambda match: unquote(match.group()))
    shown = text
    starts = array('I', range(len(text)))
    ends = array('I', range(1, len(text) + 1))
    # Display escapes can surround URL escapes, or be URL-escaped themselves.
    # This independent view also decodes percent escapes only once.
    transform(entity, lambda match: _bounded_html_unescape(match.group()))
    transform(markdown_escape, lambda match: match.group(1))
    # A renderer can escape the entity spelling already present in source prose.
    transform(entity, lambda match: _bounded_html_unescape(match.group()))
    transform(markdown_escape, lambda match: match.group(1))
    transform(r'(?:%[0-9a-fA-F]{2})+', lambda match: unquote(match.group()))
    transform(entity, lambda match: _bounded_html_unescape(match.group()))
    transform(markdown_escape, lambda match: match.group(1))
    if not ranges:
        return text
    merged = []
    for first, last in sorted(ranges):
        if merged and first <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(last, merged[-1][1]))
        else:
            merged.append((first, last))
    result, cursor = [], 0
    for first, last in merged:
        result.extend((text[cursor:first], OMITTED))
        cursor = last
    result.append(text[cursor:])
    return ''.join(result)


def safe_text(value, secrets=()):
    """Bounded privacy filter used across every new-policy prose field."""
    if not isinstance(value, str):
        return value
    secrets = tuple(secret for secret in secrets if secret)
    spellings = set()
    for secret in secrets:
        plain = ' '.join(secret.splitlines()).strip()
        escaped = html.escape(plain, quote=False)
        spellings.update((secret, plain, escaped,
            re.sub(r'([\\`*{}\[\]()#+!_|>~])', r'\\\1', escaped)))
    spellings = tuple(sorted((text for text in spellings if text), key=len, reverse=True))
    def redact(text):
        # Copies may be outside a recognized URL, including after an original
        # delimiter. Match their source spelling and preserve everything else.
        text = _redact_encoded_values(text, spellings)
        for secret in spellings:
            text = text.replace(secret, OMITTED)
        return text
    def url(text):
        try:
            # Inspect the displayed URL as well as raw prose; Markdown escapes
            # and HTML entities must not disguise a sensitive query key.
            displayed = re.sub(r'\\([\\`*{}\[\]()#+!_|>~])', r'\1', html.unescape(text))
            parsed = urlsplit(displayed)
            # Markdown reference encoding must not reintroduce a known secret.
            # Decode URL escapes for comparison only; '+' stays literal and
            # benign references retain their original spelling.
            decoded = unquote(displayed)
            # Normalization can also change a literal credential containing
            # escapes. Check original and displayed forms before discarding them.
            if any(secret in candidate for candidate in (text, displayed, decoded)
                   for secret in spellings):
                return '[URL omitida]'
            if (parsed.username or parsed.password or not parsed.hostname
                    or parsed.hostname.lower() in {'localhost', '127.0.0.1', '::1'}
                    or parsed.hostname.lower().endswith(('.local', '.internal'))
                    or _url_secrets(parsed)):
                return '[URL omitida]'
            return text
        except ValueError:
            return '[URL omitida]'
    # Split original text before inserting any markers: their ']' must never
    # truncate a URL and hide a later encoded occurrence from its policy check.
    spans = re.split(r'(https?://[^\s<>\]\)]+)', value, flags=re.IGNORECASE)
    for index in range(0, len(spans), 2):
        spans[index] = redact(spans[index])
        spans[index] = re.sub(r'(?i)(?:[a-z]:[\\/]|\\\\)[^\s<>\]\)]+', '[ruta privada]', spans[index])
        spans[index] = re.sub(r'(?<![\w:/<])/(?!/)[^\s<>\]\)]+', '[ruta privada]', spans[index])
    for index in range(1, len(spans), 2):
        spans[index] = url(spans[index])
    # A literal credential can cross an original delimiter boundary. Redact it
    # after URL decisions; these markers can no longer affect URL recognition.
    value = redact(''.join(spans))
    value = re.sub(r'(?i)\b(token|password|secret|api[-_]?key|authorization)\s*[=:]\s*(?:(?:Bearer|Basic)\s+)?[^\s,;]+', r'\1=[omitido]', value)
    value = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', ' ', value)
    return value


def _resource_proof(check, observation, sources, identity):
    raw, pinned = _read(sources, observation['evidence_reference'])
    if digest(raw) != identity.get('resource_manifest_sha256'):
        raise ValueError('resource manifest differs from the pinned input identity')
    if any(pinned.get(key) != identity.get(key) for key in ('head', 'snapshot') if key in pinned):
        raise ValueError('resource manifest identifies another input')
    _, execution = _read(sources, observation['execution_reference'])
    argv = execution.get('argv')
    if (execution.get('check_id') != check['id'] or execution.get('revision') != check['revision']
            or not isinstance(argv, list) or not argv or len(argv) > 256
            or any(not isinstance(arg, str) or len(arg) > 8192 for arg in argv)
            or shlex.join(argv) != check['command']):
        raise ValueError('selected execution does not match the exact check argv/revision')
    resources, contents, seen = [], {}, set()
    for resource in execution.get('resources', []):
        if (not isinstance(resource, dict) or set(resource) - {'path', 'executed_sha256', 'content', 'git_objects'}
                or not {'path', 'executed_sha256', 'content'}.issubset(resource)):
            raise ValueError('invalid execution resource fields')
        path = _relative(resource.get('path'))
        if path is None:
            raise ValueError('invalid execution resource path')
        if path in seen:
            raise ValueError('duplicate execution resource path is ambiguous')
        seen.add(path)
        expected = pinned.get('files', {}).get(path)
        try:
            content = bytes.fromhex(resource.get('content', ''))
        except (ValueError, TypeError) as exc:
            raise ValueError('invalid execution resource content') from exc
        actual = digest(content)
        if actual != resource.get('executed_sha256'):
            raise ValueError('execution resource content differs from its recorded SHA-256')
        if expected == actual == resource.get('executed_sha256'):
            if 'git_objects' in resource and not _git_membership(identity.get('head'), path, content, resource['git_objects']):
                raise ValueError('resource Git object chain differs from pinned revision')
            resources.append(dict(path=path, revision=check['revision'], project_sha256=expected, executed_sha256=actual))
            contents[path] = content
    return execution, resources, contents


def _git_membership(head, path, content, objects):
    """Verify commit -> ordinary trees -> blob using retained raw Git object bytes."""
    try:
        algorithm = hashlib.sha1 if len(head) == 40 else hashlib.sha256 if len(head) == 64 else None
        if algorithm is None or not isinstance(objects, dict) or len(objects) > 128:
            return False
        def object_bytes(oid, kind):
            row = objects[oid]
            raw = bytes.fromhex(row['data'])
            if row['kind'] != kind or algorithm(kind.encode() + b' ' + str(len(raw)).encode() + b'\0' + raw).hexdigest() != oid:
                raise ValueError('invalid Git object')
            return raw
        commit = object_bytes(head, 'commit')
        root = commit.split(b'\n', 1)[0]
        if not root.startswith(b'tree '):
            return False
        oid = root[5:].decode('ascii')
        width = len(head) // 2
        components = path.split('/')
        for index, component in enumerate(components):
            raw = object_bytes(oid, 'tree'); offset = 0; found = None
            while offset < len(raw):
                end = raw.index(b'\0', offset)
                mode, name = raw[offset:end].split(b' ', 1)
                child = raw[end + 1:end + 1 + width].hex()
                offset = end + 1 + width
                if name == component.encode('utf-8'):
                    found = mode, child
            if found is None:
                return False
            mode, oid = found
            if index == len(components) - 1:
                return mode in (b'100644', b'100755') and object_bytes(oid, 'blob') == content
            if mode not in (b'40000', b'040000'):
                return False
        return False
    except (ValueError, TypeError, KeyError, AttributeError, UnicodeError):
        return False


def _project_command(execution, resources, contents):
    argv = execution['argv']; eligible = {row['path'] for row in resources}
    cwd = execution.get('cwd', '').replace('\\', '/').rstrip('/')
    tool = ntpath.basename(argv[0]).lower().removesuffix('.exe')
    allowed = {'python', 'python3', 'pytest', 'dotnet', 'npm', 'make', 'node', 'ruby', 'go', 'cargo'}
    # A path's basename does not establish a runner's origin. Until an adapter
    # proves that executable, retain independently proved resources and explain
    # the check instead of laundering a wrapper into a trusted bare command.
    if (argv[0] != ntpath.basename(argv[0]) or ntpath.splitdrive(argv[0])[0]
            or tool not in allowed or any(arg in ('-c', '-e', '--eval', '--command') or any(c in arg for c in ('\n', '\r', '\x00')) for arg in argv)):
        return None, 'explanation'
    def project_path(arg):
        path = arg.replace('\\', '/')
        compare = str.lower if ntpath.splitdrive(cwd)[0] else lambda value: value
        if cwd and compare(path).startswith(compare(cwd) + '/'):
            path = path[len(cwd) + 1:]
        return path if _relative(path) in eligible else None
    def supported_task(definition):
        # A bounded literal adapter, not a shell or dependency evaluator. The
        # documented bare runner is manifest-bound; script operands must also
        # have original/executed byte proof. Nested tasks remain unsupported.
        if not isinstance(definition, str) or re.search(r'[|;&`$<>\n\r]|\b(?:sh|bash|cmd|powershell)\b', definition):
            return False
        try:
            nested = shlex.split(definition)
        except ValueError:
            return False
        if nested == ['jest']:
            return True
        if not nested or nested[0] not in {'python', 'python3', 'node', 'ruby', 'pytest', 'dotnet'}:
            return False
        _, mode = _project_command(dict(execution, argv=nested), resources, contents)
        return mode == 'project_command'
    entry = next((arg for arg in argv[1:] if not arg.startswith('-')), None)
    if tool == 'npm':
        # These invocations can select another package or task runtime. No adapter
        # currently binds that alternate manifest, so do not attribute cwd's task.
        redirected = {'--prefix', '--workspace', '--workspaces', '-w', '--global', '-g', '--userconfig', '--globalconfig', '--script-shell'}
        if any(arg.split('=', 1)[0] in redirected or arg.startswith(('-w', '--prefix=', '--workspace=')) for arg in argv[1:]):
            return None, 'explanation'
        if len(argv) < 2 or argv[1].startswith('-'):
            return None, 'explanation'
        try:
            scripts = json.loads(contents.get('package.json', b'{}')).get('scripts', {})
        except (ValueError, AttributeError):
            return None, 'explanation'
        task = argv[2] if len(argv) > 2 and argv[1] == 'run' else entry
        definition = scripts.get(task)
        if not supported_task(definition) or any(name in scripts for name in ('pre' + str(task), 'post' + str(task))):
            return None, 'explanation'
    elif tool == 'make':
        if any(arg.split('=', 1)[0] in {'-f', '--file', '--makefile', '-C', '--directory'}
               or arg.startswith(('-f', '-C')) or '=' in arg for arg in argv[1:]):
            return None, 'explanation'
        content = contents.get('Makefile', b'').decode('utf-8', errors='replace')
        # Only one explicit target with one literal recipe is currently bound;
        # prerequisites, includes, variables and multiple recipes need an adapter.
        match = re.fullmatch(re.escape(entry or '') + r'[ \t]*:[ \t]*\n\t([^\n]+)\n?', content)
        if not entry or len(argv) != 2 or not match or not supported_task(match.group(1)):
            return None, 'explanation'
    elif tool == 'dotnet' and (entry != 'test' or len(argv) < 3 or argv[1] != 'test'
            or not any(project_path(arg) and arg.lower().endswith(('.csproj', '.sln')) for arg in argv[2:])):
        return None, 'explanation'
    elif entry is None:
        return None, 'explanation'
    elif tool not in {'dotnet', 'go', 'cargo'} and project_path(entry) is None:
        return None, 'explanation'
    elif tool in {'go', 'cargo'}:
        return None, 'explanation'  # No adapter proves these task definitions yet.
    projected = [tool]; mixed = False; secret_next = False; resource_next = False
    for arg in argv[1:]:
        if secret_next:
            projected.append(OMITTED); mixed = True; secret_next = False; continue
        if _secret_argument(arg):
            if '=' in arg: projected.append(arg.split('=', 1)[0] + '=' + OMITTED)
            else: projected.append(arg); secret_next = True
            mixed = True; continue
        if _argument_secrets(arg):
            projected.append(OMITTED); mixed = True; continue
        original = project_path(arg)
        if original:
            projected.append(safe_text(original)); resource_next = False; continue
        if resource_next:
            projected.append(OMITTED); mixed = True; resource_next = False; continue
        if arg in RESOURCE_FLAGS:
            projected.append(arg); resource_next = True; continue
        if ('/' in arg or '\\' in arg or re.search(r'(?i)(?:https?:|file:)', arg)
                or RESOURCE_OPERAND.search(arg)
                or arg in ('..', '.') or any(c in arg for c in ('`', '$', ';', '|', '&', '<', '>'))):
            projected.append(OMITTED); mixed = True
        else:
            projected.append(arg)
    return shlex.join(projected), 'mixed' if mixed else 'project_command'


def build_disclosure_row(check, observation, sources, identity):
    row = dict(id=check['id'], command_sha256=digest(check['command'].encode('utf-8')),
               execution_reference=None, mode='explanation', command=None, resources=[],
               explanation='No se dispone de argv y procedencia verificables para este check; propósito y resultado se conservan.', evidence_reference=None)
    if not observation:
        return row
    row.update(execution_reference=observation.get('execution_reference'), evidence_reference=observation.get('evidence_reference'))
    execution, resources, contents = _resource_proof(check, observation, sources, identity)
    row['resources'] = resources
    row['command'], row['mode'] = _project_command(execution, resources, contents)
    secrets = sensitive_values(sources)
    if row['command'] is not None:
        row['command'] = safe_text(row['command'], secrets)
    row['explanation'] = safe_text(observation.get('explanation') or row['explanation'], secrets)
    return row


def validate_check_disclosure(record, disclosure, sources, input_identity):
    try:
        if not isinstance(disclosure, dict) or set(disclosure) != FIELDS or type(disclosure.get('schema_version')) is not int or disclosure.get('schema_version') != 1:
            return ['check disclosure requires exact schema 1 fields']
        if len(canonical(disclosure)) > MAX_BYTES:
            return ['check disclosure exceeds bounded size']
        if not isinstance(input_identity, dict) or set(input_identity) - {'head', 'snapshot', 'resource_manifest_sha256'}:
            return ['check disclosure input identity has unknown fields']
        if (disclosure['review_id'] != record.get('review_id') or disclosure['source_sha256'] != source_digest(record)
                or disclosure['input_identity'] != input_identity
                or any(input_identity.get(key) != value for key, value in input_identity_for(record).items())):
            return ['check disclosure source/input binding differs']
        rows = disclosure['checks']
        if not isinstance(rows, list) or len(rows) != len(record['checks']):
            return ['check disclosure must cover every check exactly once']
        indexed = {row['id']: row for row in rows}
        if len(indexed) != len(rows) or set(indexed) != {check['id'] for check in record['checks']}:
            return ['check disclosure requires unique real check IDs']
        for check in record['checks']:
            row = indexed[check['id']]
            if set(row) != ROW_FIELDS or not isinstance(row['explanation'], str) or not row['explanation'].strip():
                return ['check disclosure requires exact row fields and concrete explanation']
            observation = row if row['execution_reference'] or row['evidence_reference'] else None
            expected = build_disclosure_row(check, observation, sources, input_identity)
            if row != expected:
                return ['check disclosure differs from selected execution/input proof']
        return []
    except (KeyError, TypeError, ValueError, AttributeError, UnicodeDecodeError) as exc:
        return ['invalid check disclosure evidence: ' + str(exc)]
