"""Reproduce 4ed296c sidecars only under the existing resource-proof gate.

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

def projected_url_spans(value, *, _bff_compat=False):
    """Walk URL tokens once, distinguishing Markdown's closing delimiter."""
    if _bff_compat:
        from ccr.contracts.disclosure_urls_139a175 import projected_url_spans as archived_spans
        yield from archived_spans(value, _bff_compat=True)
        return
    position = 0
    quote_end = None
    closing_quote = None
    while (scheme := _URL_SCHEME.search(value, position)) is not None:
        first = scheme.start()
        markdown_link = value[max(0, first - 2):first] == ']('
        outer = value[first - 1] if first else ''
        if quote_end is not None and first >= quote_end:
            # A URL can end at whitespace before its surrounding quote. That
            # quote is still a closing delimiter when the next URL is found.
            position = max(position, quote_end + 1)
            quote_end = None
            closing_quote = None
        quote_start = first - 1
        while quote_start >= position and value[quote_start] in '([{ \t':
            quote_start -= 1
        quote_open = value[quote_start] if quote_start >= position else ''
        if quote_end is None and quote_open in _URL_QUOTES:
            closing_quote = _URL_QUOTES[quote_open]
            # A quote bounds the whole prose list, including its later URLs.
            # Find its end once so each member keeps the same closing boundary.
            quotes = re.compile(r'\\[\s\S]|' + re.escape(closing_quote))
            quote_end = next((match.start() for match in quotes.finditer(value, scheme.end())
                              if match.group() == closing_quote), len(value))
        single_destination = markdown_link or outer == '<'
        bounded = single_destination or quote_end is not None or outer == '('
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
            if (not single_destination and not sensitive_value and char in (',', ';', '(')
                    and _URL_SCHEME.match(value, next_cursor)):
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
