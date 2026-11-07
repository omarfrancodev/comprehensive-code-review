"""Reproduce a6eeb21 sidecars only under the existing resource-proof gate.

Current public views always sanitize retained rows with the current policy.
"""
import heapq
import itertools
import re
from urllib.parse import urlsplit, unquote_plus
from ccr.contracts.check_disclosure import (
    OMITTED, SENSITIVE_URL_KEY, _URL_SCHEME, _URL_ENTITY, _URL_QUOTES,
    _OMITTED_URL_QUERY, _private_http_url, _userinfo_spellings,
    _bounded_html_unescape, _displayed_http_url, _url_secrets,
    _sensitive_text_ranges, _secret_spellings, _legacy_safe_text,
    _command_sensitive_values,
)

def _url_quote_ranges(value, opener):
    """Pair one quote family without letting another family suppress it."""
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
                for gap in re.compile(r'\s+').finditer(value, content, match.start()):
                    if gap.end() < match.start() and _URL_SCHEME.match(value, gap.end()) is None:
                        destination = False
                        break
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
        if opener in value:
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
            if char == '\\' and (escaped in ('(', ')', '[', ']', '\\') or
                                  (closing_quote is not None and escaped == closing_quote)):
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
