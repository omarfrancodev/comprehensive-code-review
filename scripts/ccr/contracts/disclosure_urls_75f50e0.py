"""Frozen 75f50e0 sidecar reproduction for proof-validated historical rows.

Current consumers apply the current privacy policy after validation. This
module only preserves the exact previously emitted row under the same proof.
"""
import heapq
import itertools
import re
from urllib.parse import urlsplit
from ccr.contracts.disclosure_primitives import (
    OMITTED, _URL_SCHEME, _OMITTED_URL_QUERY, _private_http_url,
    _userinfo_spellings, _bounded_html_unescape, _displayed_http_url,
    _url_secrets, _sensitive_text_ranges, _secret_spellings,
    _legacy_safe_text, _command_sensitive_values,
)

def projected_url_spans(value, *, _bff_compat=False):
    """Walk URL tokens once, distinguishing Markdown's closing delimiter."""
    if _bff_compat:
        from ccr.contracts.disclosure_urls_139a175 import projected_url_spans as archived_spans
        yield from archived_spans(value, _bff_compat=True)
        return
    position = 0
    while (scheme := _URL_SCHEME.search(value, position)) is not None:
        first = scheme.start()
        markdown_link = value[max(0, first - 2):first] == ']('
        outer = value[first - 1] if first else ''
        closing_quote = {'"': '"', "'": "'", '`': '`', '“': '”', '‘': '’',
                         '«': '»', '‹': '›'}.get(outer)
        bounded = markdown_link or closing_quote is not None or outer in ('(', '<')
        brackets = []
        cursor = scheme.end()
        trailing_close = None
        while cursor < len(value) and not value[cursor].isspace() and value[cursor] not in '<>':
            char = value[cursor]
            if closing_quote is not None and char == closing_quote:
                break
            if not bounded and char in ',;(' and _URL_SCHEME.match(value, cursor + 1):
                break
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
            cursor += 1
        yield first, trailing_close if trailing_close is not None else cursor
        position = cursor



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
