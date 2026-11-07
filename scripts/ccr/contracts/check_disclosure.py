"""Pure selected-byte proof and canonical selective disclosure contract.

The expected input identity is a trust anchor captured before review execution.
The resource manifest is hashed at workspace preparation, never after a check.
"""
import hashlib
import heapq
import itertools
import string
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


def _userinfo_spellings(text):
    # Read the original authority before HTML decoding can introduce URI
    # delimiters, or urlsplit can discard tabs/newlines in a password.
    # Numeric references are indivisible here: their '#' is part of the
    # original spelling, not an authority/fragment boundary for learning.
    authority = re.match(r'(?:&#(?:[xX][0-9a-fA-F]+|[0-9]+);?|[^/?#])*',
                         text.partition('://')[2]).group()
    userinfo, at, _ = authority.rpartition('@')
    _, colon, password = userinfo.partition(':')
    passwords = {password} if at and colon and password else set()
    # Delimiters can themselves be HTML references. Locate their interpreted
    # positions without discarding the source spelling between them. Keep the
    # literal delimiter frame too: decoding a username can move the first ':'.
    first_colon_end = last_at_start = None
    reference = r'&(?:#[xX][0-9a-fA-F]+|#[0-9]+|[a-zA-Z][a-zA-Z0-9]+);?'
    for match in re.finditer(reference + r'|[:@]', authority):
        separator = _bounded_html_unescape(match.group())
        if separator == ':' and first_colon_end is None:
            first_colon_end = match.end()
        elif separator == '@':
            last_at_start = match.start()
    if first_colon_end is not None and last_at_start is not None and first_colon_end < last_at_start:
        passwords.add(authority[first_colon_end:last_at_start])
    values = set()
    for password in passwords:
        decoded = unquote(password)  # Userinfo '+' is always literal.
        displayed = _bounded_html_unescape(password)
        values.update((password, decoded, displayed, unquote(displayed),
                       _bounded_html_unescape(decoded)))
    # urlsplit strips these controls. Retain that presentation independently
    # of any component changes introduced elsewhere in the interpreted URI.
    return (values | {re.sub(r'[\r\n\t]', '', value) for value in values}) - {''}


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
    # argv is exact input, not Markdown prose: ')' is legal in URI components
    # and ']' closes an IPv6 authority. Editorial delimiters must not cut it.
    for text in re.findall(r'https?://[^\s<>]+', argument, re.IGNORECASE):
        values.update(_userinfo_spellings(text))
        # Retain source and interpreted forms independently. A failure to parse
        # either representation must not discard values learned from the other.
        for candidate in (text, _bounded_html_unescape(text)):
            try:
                values.update(_url_secrets(urlsplit(candidate)))
            except ValueError:
                continue
    return values


def _argv_sensitive_values(argv):
    values = set()
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


def sensitive_values(sources):
    values = set()
    for raw in sources.values():
        try:
            item = json.loads(raw)
        except (ValueError, TypeError, UnicodeDecodeError):
            continue
        if not isinstance(item, dict):
            continue
        values.update(_argv_sensitive_values(item.get('argv', [])))
    return values


def _command_sensitive_values(command):
    """Learn redactions from retained text, never execution or resource proof."""
    values, seen, pending = set(), set(), [command]
    # Nested quoted scripts are text, not argv proof. Bound total lexical work
    # by input size and fail closed rather than silently skipping inner secrets.
    remaining = 16 * max(1, len(command))
    while pending:
        text = pending.pop()
        if text in seen:
            continue
        if len(text) > remaining:
            raise ValueError('retained command privacy analysis exceeds its work bound')
        remaining -= len(text)
        seen.add(text)
        values.update(_argument_secrets(text))
        for posix in (True, False):
            lexer = shlex.shlex(text, posix=posix, punctuation_chars=True)
            lexer.whitespace_split = True
            lexer.commenters = ''
            arguments = []
            try:
                arguments.extend(lexer)
            except ValueError:
                # Preserve both prior arguments and an unterminated quoted body.
                if lexer.token:
                    arguments.append(lexer.token)
            values.update(_argv_sensitive_values(arguments))
            # Outer spellings can hide sensitive keys through escapes/quoting.
            # Inspect candidate text before classifying its normalized tokens.
            pending.extend(argument for argument in arguments
                           if argument != text and any(char in argument for char in ' \t\r\n\\\'"'))
    return values | {re.sub(r'(?i)^(?:Bearer|Basic)\s+', '', value) for value in values}


def private_values(record, view, sources):
    values = sensitive_values(sources)
    for check in record.get('checks', []):
        values.update(_command_sensitive_values(check['command']))
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


_LEGACY_MARKDOWN_ESCAPE = re.compile(r'\\([\\`*{}\[\]()#+!_|>~])')
_MARKDOWN_ESCAPE = re.compile(r'\\([' + re.escape(string.punctuation) + r'])')


def _encoded_value_ranges(text, spellings, *, overlaps=False, markdown_escapes=False, _bff_compat=False):
    """Locate encoded copies in original source coordinates."""
    if not spellings:
        return []
    entity = r'&(?:\#[xX][0-9a-fA-F]+|\#[0-9]+|[a-zA-Z][a-zA-Z0-9]+);?'
    markdown_escape = _MARKDOWN_ESCAPE if markdown_escapes and not _bff_compat else _LEGACY_MARKDOWN_ESCAPE
    markers = {match.start() for match in re.finditer(r'(?:%[0-9a-fA-F]{2})+', text)}
    markers.update(match.start() for match in re.finditer(entity, text))
    if markdown_escapes:
        markers.update(match.start() for match in re.finditer(markdown_escape, text))
    encoded_starts = sorted(markers)
    if not encoded_starts:
        return []
    shown = text
    starts = array('I', range(len(text)))
    ends = array('I', range(1, len(text) + 1))
    # At a given source offset only the farthest end can affect the
    # union. Store one endpoint per input character, regardless of the
    # number of spellings, overlaps or decoding passes.
    farthest = array('I', [0]) * len(text)

    def collect():
        for secret in spellings:
            position = shown.find(secret)
            while position != -1:
                first, last = starts[position], ends[position + len(secret) - 1]
                encoded_index = bisect_left(encoded_starts, first)
                if encoded_index < len(encoded_starts) and encoded_starts[encoded_index] < last:
                    # Literal-only matches are handled by replace below. Do not
                    # retain one range per plain-text occurrence or per view.
                    covered_end = farthest[first]
                    if overlaps and covered_end >= last:
                        # All windows ending inside this known range are
                        # already covered, even if they start on another entity.
                        boundary = bisect_right(ends, covered_end)
                        following = max(position + 1, boundary - len(secret) + 1)
                    else:
                        farthest[first] = max(covered_end, last)
                        following = position + (1 if overlaps else len(secret))
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
    merged = []
    for first, last in enumerate(farthest):
        if not last:
            continue
        if merged and first <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(last, merged[-1][1]))
        else:
            merged.append((first, last))
    return merged


def _redact_encoded_values(text, spellings):
    """Redact known encoded copies using source offsets, never decoded output."""
    result, cursor = [], 0
    for first, last in _encoded_value_ranges(text, spellings):
        result.extend((text[cursor:first], OMITTED))
        cursor = last
    result.append(text[cursor:])
    return ''.join(result)


def _secret_spellings(secrets):
    secrets = tuple(secret for secret in secrets if secret)
    spellings = set()
    for secret in secrets:
        plain = ' '.join(secret.splitlines()).strip()
        escaped = html.escape(plain, quote=False)
        spellings.update((secret, plain, escaped,
            re.sub(r'([\\`*{}\[\]()#+!_|>~])', r'\\\1', escaped)))
    return tuple(sorted((text for text in spellings if text), key=len, reverse=True))


def sensitive_text_ranges(text, secrets):
    """Yield merged sensitive intervals before callers transform source text."""
    return _sensitive_text_ranges(text, _secret_spellings(secrets))


def _sensitive_text_ranges(text, spellings, *, markdown_escapes=False, _bff_compat=False):
    """Match with an already prepared set of spellings.

    Literal matches stream, including overlaps, rather than allocating one
    tuple for every character of a repetitive value. Encoded matches share the
    existing source-offset decoder; no decoded text is returned to a renderer.
    """
    def literal(secret):
        position = text.find(secret)
        while position != -1:
            yield position, position + len(secret)
            position = text.find(secret, position + 1)
    streams = [literal(secret) for secret in spellings]
    streams.append(iter(_encoded_value_ranges(text, spellings, overlaps=True,
                                             markdown_escapes=markdown_escapes, _bff_compat=_bff_compat)))
    pending = None
    for first, last in heapq.merge(*streams):
        if pending is not None and first <= pending[1]:
            pending = pending[0], max(last, pending[1])
        else:
            if pending is not None:
                yield pending
            pending = first, last
    if pending is not None:
        yield pending


def _private_http_url(text, spellings=(), *, modern=False):
    try:
        # Inspect the displayed URL as well as raw prose; Markdown escapes
        # and HTML entities must not disguise a sensitive query key.
        displayed = _displayed_http_url(text, bounded=modern, modern=modern)
        parsed = urlsplit(displayed)
        # Markdown reference encoding must not reintroduce a known secret.
        # Decode URL escapes for comparison only; '+' stays literal and
        # benign references retain their original spelling.
        decoded = unquote(displayed)
        # Normalization can also change a literal credential containing
        # escapes. Check original and displayed forms before discarding them.
        if any(secret in candidate for candidate in (text, displayed, decoded)
               for secret in spellings):
            return True
        if (parsed.username or parsed.password or not parsed.hostname
                or parsed.hostname.lower() in {'localhost', '127.0.0.1', '::1'}
                or parsed.hostname.lower().endswith(('.local', '.internal'))
                or _url_secrets(parsed)):
            return True
        return False
    except ValueError:
        return True


_URL_SCHEME = re.compile(r'https?://', re.IGNORECASE)
_URL_ENTITY = re.compile(r'&(?:\#[xX][0-9a-fA-F]+|\#[0-9]+|[a-zA-Z][a-zA-Z0-9]+);?')
_URL_QUOTES = {'"': '"', "'": "'", '`': '`', '“': '”', '‘': '’', '«': '»', '‹': '›'}
_URL_QUOTE_TOKENS = re.compile(r'''\\[\s\S]|["'`“”‘’«»‹›]''')
_BFF_OMITTED_URL_QUERY = re.compile(r'\[(?:omitido|ruta privada|URL omitida)\]\]*([?#][^\s<>]+)')
_OMITTED_URL_QUERY = re.compile(r'\[(?:omitido|ruta privada|URL omitida)\][\])]*([?#][^\s<>]+)')


def _quoted_url_destination(value, first, last):
    while first < last and value[first] in '([{ \t\r\n':
        first += 1
    if _URL_SCHEME.match(value, first, last) is None:
        return False
    for gap in re.compile(r'\s+').finditer(value, first, last):
        if gap.end() < last and _URL_SCHEME.match(value, gap.end(), last) is None:
            return False
    return True


def _url_quote_ranges(value, opener):
    """Pair one quote family without letting another family suppress it."""
    if opener == '`':
        from ccr.contracts.disclosure_text import _code_ranges, _LINES, _FENCE
        for first, last in _code_ranges(value, _LINES, _FENCE):
            yield first - 1, last, '`', _quoted_url_destination(value, first, last)
        return
    closing = _URL_QUOTES[opener]
    tokens = re.compile(r'\\[\s\S]|[' + re.escape(opener + closing) + ']')
    first = None
    destination = False
    for match in tokens.finditer(value):
        char = match.group()
        if len(char) != 1:
            continue
        if char == "'":
            before = match.start() > 0 and value[match.start() - 1].isalnum()
            after = match.end() < len(value) and value[match.end()].isalnum()
            if before and (first is None or after):
                continue  # Apostrophes in words and possessives do not open quotes.
        if first is None and char == opener:
            first = match.start()
            content = match.end()
            while content < len(value) and value[content] in '([{ \t':
                content += 1
            destination = _URL_SCHEME.match(value, content) is not None
        elif first is not None and char == closing:
            # A stranded prose opener must not consume a later immediate URL
            # opener of the same kind. A word-adjacent closing quote stays closed.
            if (opener == closing and not destination
                    and _URL_SCHEME.match(value, match.end()) is not None
                    and match.start() > 0 and value[match.start() - 1].isspace()):
                first = match.start()
                content = match.end()
                destination = True
                continue
            if destination:
                # A quote beginning with a URL can continue with ordinary
                # prose. Its sentence punctuation does not belong to the URL.
                destination = _quoted_url_destination(value, content, match.start())
            yield first, match.start(), closing, destination
            first = None


def projected_url_spans(value, *, _bff_compat=False):
    """Walk URL tokens once, distinguishing Markdown's closing delimiter."""
    if _bff_compat:
        from ccr.contracts.disclosure_urls_139a175 import projected_url_spans as archived_spans
        yield from archived_spans(value, _bff_compat=True)
        return
    position = 0
    quotes = []
    for opener in _URL_QUOTES:
        if opener in value or (opener == '`' and '~~~' in value):
            ranges = iter(_url_quote_ranges(value, opener))
            quotes.append({'ranges': ranges, 'current': next(ranges, None)})
    while (scheme := _URL_SCHEME.search(value, position)) is not None:
        first = scheme.start()
        markdown_link = value[max(0, first - 2):first] == ']('
        outer = value[first - 1] if first else ''
        nearest_quote_start = -1
        quoted_destination = False
        quote_end = None
        closing_quote = None
        for state in quotes:
            quote = state['current']
            while quote is not None and quote[1] <= first:
                quote = next(state['ranges'], None)
            state['current'] = quote
            if quote is not None and quote[0] < first:
                opening, end, closing, destination = quote
                # The nearest quote owns punctuation. Any enclosing quote can
                # still end the token, even when an outer prefix is malformed.
                if opening > nearest_quote_start:
                    nearest_quote_start = opening
                    quoted_destination = destination
                if quote_end is None or end < quote_end:
                    quote_end, closing_quote = end, closing
        single_destination = markdown_link or outer == '<'
        bounded = single_destination or quoted_destination or outer == '('
        brackets = []
        cursor = scheme.end()
        trailing_close = None
        parameter_start = None
        in_value = False
        sensitive_value = False
        in_fragment = False
        while cursor < len(value) and not value[cursor].isspace() and value[cursor] not in '<>':
            char = value[cursor]
            if cursor == quote_end:
                break
            next_cursor = cursor + 1
            parameter_char = char
            entity = _URL_ENTITY.match(value, cursor) if char == '&' else None
            if entity is not None:
                displayed = _bounded_html_unescape(entity.group())
                if displayed != entity.group():
                    # Entities affect parameter interpretation. Only literal
                    # source characters can group or close a Markdown target.
                    parameter_char = displayed if len(displayed) == 1 else ''
                    next_cursor = entity.end()
            if not single_destination and parameter_char in (',', ';', '('):
                neighbor = next_cursor
                while neighbor < len(value) and value[neighbor].isspace():
                    neighbor += 1
                if (_URL_SCHEME.match(value, neighbor) is not None
                        and (not sensitive_value or neighbor > next_cursor)):
                    break
            # Only the first '=' binds a parameter. An embedded scheme and its
            # punctuation belong to that value until a real '&' or '#' ends it.
            if ((parameter_char == '?' and parameter_start is None)
                    or (parameter_char == '#' and not in_fragment)):
                parameter_start = next_cursor
                in_fragment = parameter_char == '#'
                in_value = False
                sensitive_value = False
            elif parameter_char == '&' and parameter_start is not None:
                parameter_start = next_cursor
                in_value = False
                sensitive_value = False
            elif parameter_char == '=' and parameter_start is not None and not in_value:
                key = _displayed_http_url(value[parameter_start:cursor], bounded=True, modern=True)
                sensitive_value = bool(SENSITIVE_URL_KEY.search(unquote_plus(key)))
                in_value = True
            escaped = value[cursor + 1:cursor + 2]
            if (char == '\\' and (escaped in ('(', ')', '[', ']', '\\') or
                                   (closing_quote is not None and escaped == closing_quote))
                    and (quote_end is None or cursor + 1 < quote_end)):
                trailing_close = None
                cursor += 2
                continue
            if char in '([':
                brackets.append(')' if char == '(' else ']')
            elif char in ')]':
                if brackets and brackets[-1] == char:
                    brackets.pop()
                elif (markdown_link or outer == '(') and char == ')':
                    break
                elif trailing_close is None:
                    trailing_close = cursor
            if not bounded and char in '.,;!' and trailing_close is None:
                trailing_close = cursor
            if char not in ')]}.,;!':
                trailing_close = None
            cursor = next_cursor
        yield first, trailing_close if trailing_close is not None else cursor
        position = cursor
        if cursor == quote_end:
            position += 1


def _displayed_http_url(text, *, bounded=False, modern=False):
    displayed = _bounded_html_unescape(text) if bounded else html.unescape(text)
    escapes = _MARKDOWN_ESCAPE if modern else _LEGACY_MARKDOWN_ESCAPE
    return escapes.sub(r'\1', displayed)


def projected_url_secrets(value, *, _bff_compat=False):
    """Learn URL values from both wire and displayed spellings."""
    if _bff_compat:
        from ccr.contracts.disclosure_urls_139a175 import projected_url_secrets as archived_secrets
        return archived_secrets(value, _bff_compat=True)
    values = set()
    urls = (value[first:last] for first, last in projected_url_spans(value))
    # Old schema 1 writers could detach a query after an omission marker.
    def detached_queries():
        for match in _OMITTED_URL_QUERY.finditer(value):
            # A historical omission can leave the original opening quote.
            # Apply the same URL boundaries to its query and to complete URLs.
            outer = value[match.start() - 1:match.start()] if match.start() else ''
            candidate = outer + 'https://redacted.invalid/' + match[1]
            for first, last in projected_url_spans(candidate):
                yield candidate[first:last]
    tails = detached_queries()
    for url in itertools.chain(urls, tails):
        values.update(_userinfo_spellings(url))
        for spelling in (url, _bounded_html_unescape(url),
                         _displayed_http_url(url, bounded=True, modern=not _bff_compat)):
            try:
                values.update(_url_secrets(urlsplit(spelling)))
            except ValueError:
                continue
    return {value for value in values if value}


def private_projected_url(value, spellings=()):
    """Apply URL policy to the entire typed locator and its visible spellings."""
    return (_private_http_url(value, modern=True) or
            next(_sensitive_text_ranges(value, spellings, markdown_escapes=True), None) is not None)


def private_url_spans(value, *, _bff_compat=False):
    for first, last in projected_url_spans(value, _bff_compat=_bff_compat):
        if _private_http_url(value[first:last], modern=not _bff_compat):
            yield first, last


def redact_projected_text(value, spellings, *, path_spans=(), _bff_compat=False):
    """Redact copies across the composed value, using original URL boundaries."""
    urls = iter(projected_url_spans(value, _bff_compat=_bff_compat))
    url = next(urls, None)
    chunks, cursor, pending = [], 0, None
    known = _sensitive_text_ranges(value, spellings, markdown_escapes=True, _bff_compat=_bff_compat)
    private_urls = private_url_spans(value, _bff_compat=_bff_compat)
    for first, last in heapq.merge(known, private_urls, path_spans):
        while url is not None and url[1] <= first:
            url = next(urls, None)
        while url is not None and url[0] < last:
            first, last = min(first, url[0]), max(last, url[1])
            url = next(urls, None)
        if pending is not None and first <= pending[1]:
            pending = pending[0], max(last, pending[1])
        else:
            if pending is not None:
                chunks.extend((value[cursor:pending[0]], OMITTED))
                cursor = pending[1]
            pending = first, last
    if pending is not None:
        chunks.extend((value[cursor:pending[0]], OMITTED))
        cursor = pending[1]
    chunks.append(value[cursor:])
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', ' ', ''.join(chunks))


def _legacy_safe_text(value, secrets=(), *, redact_paths=True, _redact_assignments=True):
    """Filter private prose; typed projections may apply their own path policy."""
    if not isinstance(value, str):
        return value
    return _sanitize_spellings(value, _secret_spellings(secrets), redact_paths=redact_paths,
                               redact_assignments=_redact_assignments)


def _sanitize_spellings(value, spellings, *, redact_paths, redact_assignments):
    def redact(text):
        if not text:
            return text
        # Copies may be outside a recognized URL, including after an original
        # delimiter. Match their source spelling and preserve everything else.
        text = _redact_encoded_values(text, spellings)
        for secret in spellings:
            text = text.replace(secret, OMITTED)
        return text
    # Split original text before inserting any markers: their ']' must never
    # truncate a URL and hide a later encoded occurrence from its policy check.
    spans = re.split(r'(https?://[^\s<>\]\)]+)', value, flags=re.IGNORECASE)
    for index in range(0, len(spans), 2):
        spans[index] = redact(spans[index])
        if redact_paths:
            spans[index] = re.sub(r'(?i)(?:[a-z]:[\\/]|\\\\)[^\s<>\]\)]+', '[ruta privada]', spans[index])
            spans[index] = re.sub(r'(?<![\w:/<])/(?!/)[^\s<>\]\)]+', '[ruta privada]', spans[index])
    for index in range(1, len(spans), 2):
        if _private_http_url(spans[index], spellings):
            spans[index] = '[URL omitida]'
    # A literal credential can cross an original delimiter boundary. Redact it
    # after URL decisions; these markers can no longer affect URL recognition.
    value = redact(''.join(spans))
    if redact_assignments:
        value = re.sub(r'(?i)\b(token|password|secret|api[-_]?key|authorization)\s*[=:]\s*(?:(?:Bearer|Basic)\s+)?[^\s,;]+', r'\1=[omitido]', value)
    value = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', ' ', value)
    return value


def safe_text(value, secrets=(), *, redact_paths=True, syntax='prose'):
    """Sanitize original source text; presentation escapes carry no authority."""
    return _sanitize_source_text(value, secrets, redact_paths, syntax)


def sanitize_projected_detail(value, secrets, *, syntax='prose', explanation=False, _bff_compat=False):
    from ccr.contracts.disclosure_text import sensitive_values_from_text
    if not isinstance(value, str):
        return value
    known = (set(secrets) | sensitive_values_from_text(value, syntax=syntax) |
             projected_url_secrets(value, _bff_compat=_bff_compat))
    if syntax == 'structured':
        known.update(_command_sensitive_values(value))
    paths = ()
    if explanation and not _bff_compat:
        from ccr.contracts.disclosure_paths import private_detail_path_spans
        paths = private_detail_path_spans(value, projected_url_spans(value))
    value = redact_projected_text(value, _secret_spellings(known), path_spans=paths, _bff_compat=_bff_compat)
    # Keep the existing filesystem filter outside full URL spans.
    chunks, cursor = [], 0
    for first, last in projected_url_spans(value, _bff_compat=_bff_compat):
        chunks.extend((_legacy_safe_text(value[cursor:first], _redact_assignments=False), value[first:last]))
        cursor = last
    chunks.append(_legacy_safe_text(value[cursor:], _redact_assignments=False))
    return ''.join(chunks)


def _safe_text_lf(value, secrets=(), *, redact_paths=True, syntax='prose'):
    """Reproduce the archived editorial-v1 row, never generate a new view."""
    return _sanitize_source_text(value, secrets, redact_paths, syntax, lf_compat=True)


def _safe_text_f6b(value, secrets=(), *, redact_paths=True, syntax='prose'):
    from ccr.contracts.disclosure_text_f6b083e import sensitive_values_from_text
    return _sanitize_source_text(value, secrets, redact_paths, syntax, archived_lexer=sensitive_values_from_text)


def _sanitize_source_text(value, secrets, redact_paths, syntax, *, lf_compat=False, archived_lexer=None):
    from ccr.contracts.disclosure_text import sensitive_values_from_text
    if not isinstance(value, str):
        return value
    learned = (archived_lexer(value, syntax=syntax) if archived_lexer else
               sensitive_values_from_text(value, syntax=syntax, _lf_compat=lf_compat))
    if syntax == 'structured':
        learned.update(_command_sensitive_values(value))
    return _legacy_safe_text(value, set(secrets) | learned, redact_paths=redact_paths,
                             _redact_assignments=False)


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


def _project_command(execution, resources, contents, *, sanitize=safe_text):
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
            projected.append(sanitize(original)); resource_next = False; continue
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


def build_disclosure_row(check, observation, sources, identity, *, _legacy=False, _lf_compat=False,
                         _f6b_compat=False, _pre_atomic=False, _bff_compat=False, _139a_compat=False,
                         _75f_compat=False, _780_compat=False, _4ed_compat=False, _251_compat=False,
                         _a6e_compat=False):
    sanitize = (_legacy_safe_text if _legacy else _safe_text_f6b if _f6b_compat else
                _safe_text_lf if _lf_compat else safe_text)
    row = dict(id=check['id'], command_sha256=digest(check['command'].encode('utf-8')),
               execution_reference=None, mode='explanation', command=None, resources=[],
               explanation='No se dispone de argv y procedencia verificables para este check; propósito y resultado se conservan.', evidence_reference=None)
    if not observation:
        return row
    row.update(execution_reference=observation.get('execution_reference'), evidence_reference=observation.get('evidence_reference'))
    execution, resources, contents = _resource_proof(check, observation, sources, identity)
    row['resources'] = resources
    row['command'], row['mode'] = _project_command(execution, resources, contents, sanitize=sanitize)
    secrets = sensitive_values(sources)
    if row['command'] is not None:
        row['command'] = (_legacy_safe_text(row['command'], secrets) if _legacy else
                          sanitize(row['command'], secrets, syntax='structured'))
    explanation = observation.get('explanation') or row['explanation']
    if _legacy or _lf_compat or _f6b_compat or _pre_atomic:
        row['explanation'] = sanitize(explanation, secrets)
    elif _139a_compat:
        from ccr.contracts.disclosure_urls_139a175 import sanitize_projected_detail as archived_detail
        row['explanation'] = archived_detail(explanation, secrets, explanation=True)
    elif _75f_compat:
        from ccr.contracts.disclosure_urls_75f50e0 import sanitize_projected_detail as archived_detail
        row['explanation'] = archived_detail(explanation, secrets, explanation=True)
    elif _780_compat:
        from ccr.contracts.disclosure_urls_7806fd9 import sanitize_projected_detail as archived_detail
        row['explanation'] = archived_detail(explanation, secrets, explanation=True)
    elif _4ed_compat:
        from ccr.contracts.disclosure_urls_4ed296c import sanitize_projected_detail as archived_detail
        row['explanation'] = archived_detail(explanation, secrets, explanation=True)
    elif _251_compat:
        from ccr.contracts.disclosure_urls_25108bc import sanitize_projected_detail as archived_detail
        row['explanation'] = archived_detail(explanation, secrets, explanation=True)
    elif _a6e_compat:
        from ccr.contracts.disclosure_urls_a6eeb21 import sanitize_projected_detail as archived_detail
        row['explanation'] = archived_detail(explanation, secrets, explanation=True)
    else:
        row['explanation'] = sanitize_projected_detail(explanation, secrets, explanation=True, _bff_compat=_bff_compat)
    return row


def validate_check_disclosure(record, disclosure, sources, input_identity, *, _legacy_only=False):
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
            expected = build_disclosure_row(check, observation, sources, input_identity, _legacy=_legacy_only)
            if row != expected and not _legacy_only:
                expected = build_disclosure_row(check, observation, sources, input_identity, _a6e_compat=True)
            if row != expected and not _legacy_only:
                expected = build_disclosure_row(check, observation, sources, input_identity, _251_compat=True)
            if row != expected and not _legacy_only:
                expected = build_disclosure_row(check, observation, sources, input_identity, _4ed_compat=True)
            if row != expected and not _legacy_only:
                expected = build_disclosure_row(check, observation, sources, input_identity, _780_compat=True)
            if row != expected and not _legacy_only:
                expected = build_disclosure_row(check, observation, sources, input_identity, _75f_compat=True)
            if row != expected and not _legacy_only:
                expected = build_disclosure_row(check, observation, sources, input_identity, _139a_compat=True)
            if row != expected and not _legacy_only:
                expected = build_disclosure_row(check, observation, sources, input_identity, _bff_compat=True)
            if row != expected and not _legacy_only:
                expected = build_disclosure_row(check, observation, sources, input_identity, _pre_atomic=True)
            if row != expected and not _legacy_only:
                # Reproduce the previous editorial row under the same proof.
                expected = build_disclosure_row(check, observation, sources, input_identity, _lf_compat=True)
            if row != expected and not _legacy_only:
                expected = build_disclosure_row(check, observation, sources, input_identity, _f6b_compat=True)
            if row != expected and not _legacy_only:
                # Schema 1 predates editorial-v1. Its existing selected bytes
                # remain valid under their original full resource-proof gate.
                expected = build_disclosure_row(check, observation, sources, input_identity, _legacy=True)
            if row != expected:
                return ['check disclosure differs from selected execution/input proof']
        return []
    except (KeyError, TypeError, ValueError, AttributeError, UnicodeDecodeError) as exc:
        return ['invalid check disclosure evidence: ' + str(exc)]
