"""Pure privacy primitives shared by current and frozen disclosure readers.

This leaf never imports the proof contract or its archived reader entry points.
"""
import heapq
import html
import ntpath
import re
import shlex
import string
from array import array
from bisect import bisect_left, bisect_right
from urllib.parse import urlsplit, unquote, unquote_plus


OMITTED = '[omitido]'


SENSITIVE_URL_KEY = re.compile(r'(?i)(?:token|password|secret|api.?key|auth|credential)')


def _secret_argument(argument):
    key = argument.split('=', 1)[0]
    return (key.startswith('-') or '=' in argument) and bool(re.search(
        r'(?i)(?:token|password|secret|api[-_]?key|authorization|credential)', key))


def _sensitive_url_parameters(parsed):
    for name, component in (('query', parsed.query), ('fragment', parsed.fragment)):
        for pair in component.split('&'):
            key, separator, value = pair.partition('=')
            # A fragment can carry OAuth parameters directly or an SPA route
            # followed by '?'. Matching the decoded key also covers that prefix.
            if separator and SENSITIVE_URL_KEY.search(unquote_plus(key)):
                yield name, key, value


def _url_secrets(parsed):
    """Share URL classification and wire/decoded credential learning."""
    values = set()
    for _, _, value in _sensitive_url_parameters(parsed):
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


def _displayed_http_url(text, *, bounded=False, modern=False):
    displayed = _bounded_html_unescape(text) if bounded else html.unescape(text)
    escapes = _MARKDOWN_ESCAPE if modern else _LEGACY_MARKDOWN_ESCAPE
    return escapes.sub(r'\1', displayed)


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
