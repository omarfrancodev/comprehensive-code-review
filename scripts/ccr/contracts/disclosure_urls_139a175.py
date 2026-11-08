"""Frozen 139a175 sidecar reproduction under the existing resource-proof gate.

Only validation uses this historical writer. Current public projections always
sanitize the selected bytes again with the current policy.
"""
import heapq
import itertools
import re
from urllib.parse import urlsplit
from ccr.contracts.disclosure_primitives import (
    OMITTED, _URL_SCHEME, _OMITTED_URL_QUERY, _BFF_OMITTED_URL_QUERY,
    _private_http_url, _userinfo_spellings, _bounded_html_unescape,
    _displayed_http_url, _url_secrets, _sensitive_text_ranges, _secret_spellings,
    _legacy_safe_text, _command_sensitive_values,
)

# One shared boundary for classification and for excluding filename substrings
# from URL recognition. A lone terminal backslash still belongs to the member.
_HOME_ROOT = r'''~[^~\s/\\;|<>()\]`'"]*[\\/]'''
_QUOTED_PATH = r'''(?P<quote>[`'"])(?P<quoted_path>(?:/|[A-Za-z]:[\\/]|\\\\|(?i:file:)|\[(?:ruta privada|referencia privada)\]|''' + _HOME_ROOT + r''')(?:\\(?:[\s\S]|$)|(?!(?P=quote))[^\\])*)(?:(?P<closing>(?P=quote))|$)'''
_POSIX_PATH = r'''(?<![\w:#/<])/(?!/)[^\s;|<>\)\]`'"]+'''
_LOCAL_PATH = r'''(?:(?<!\w)(?:[A-Za-z]:[\\/]|\\\\|//|file:)|(?:(?<!\S)|(?<=(?<!\S)[([{]))(?P<home_binding>[-\w]+[=:])''' + _HOME_ROOT + r'''|(?:(?<!\S)|(?<=(?<!\S)[([{=,:;]))''' + _HOME_ROOT + r''')[^\s;|<>\)\]`'"]*'''
_SOURCE_TOKENS = re.compile(_QUOTED_PATH + r'|(?P<url>https?://[^\s<>\)\]]+)|(?P<local>'
                            + _LOCAL_PATH + ')|' + _POSIX_PATH, re.IGNORECASE)


def source_tokens(value, url_spans):
    urls = iter(url_spans)
    url = next(urls, None)
    for match in _SOURCE_TOKENS.finditer(value):
        while url is not None and url[1] <= match.start():
            url = next(urls, None)
        if url is not None and url[0] <= match.start() < url[1]:
            if match.start() == url[0] and match['url'] is not None:
                yield match, url[1]
        else:
            yield match, match.end()


def _local_start(match):
    return match.end('home_binding') if match['home_binding'] else match.start()


def private_detail_path_spans(value, url_spans):
    """Treat a quoted private locator, including a historical path marker, as a unit."""
    for match, last in source_tokens(value, url_spans):
        if match['local'] is not None or match['quoted_path'] is not None:
            yield _local_start(match), last


def projected_url_spans(value, *, _bff_compat=False):
    """Walk URL tokens once, distinguishing Markdown's closing delimiter."""
    position = 0
    while (scheme := _URL_SCHEME.search(value, position)) is not None:
        first = scheme.start()
        markdown_link = value[max(0, first - 2):first] == ']('
        outer = value[first - 1] if first and not _bff_compat else ''
        brackets = []
        cursor = scheme.end()
        trailing_close = None
        while cursor < len(value) and not value[cursor].isspace() and value[cursor] not in '<>':
            char = value[cursor]
            if outer in ('"', "'", '`') and char == outer:
                break
            if not _bff_compat and char == ',' and _URL_SCHEME.match(value, cursor + 1):
                break
            escaped = value[cursor + 1:cursor + 2]
            if char == '\\' and (escaped in ('(', ')', '[', ']', '\\') or (outer and escaped == outer)):
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
            if char not in ')]}.,;!':
                trailing_close = None
            cursor += 1
        yield first, trailing_close if trailing_close is not None else cursor
        position = cursor



def projected_url_secrets(value, *, _bff_compat=False):
    """Learn URL values from both wire and displayed spellings."""
    values = set()
    urls = (value[first:last] for first, last in projected_url_spans(value, _bff_compat=_bff_compat))
    # Old schema 1 writers could detach a query after an omission marker.
    omitted_query = _BFF_OMITTED_URL_QUERY if _bff_compat else _OMITTED_URL_QUERY
    tails = ('https://redacted.invalid/' + match[1] for match in omitted_query.finditer(value))
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
        paths = private_detail_path_spans(value, projected_url_spans(value))
    value = redact_projected_text(value, _secret_spellings(known), path_spans=paths, _bff_compat=_bff_compat)
    # Keep the existing filesystem filter outside full URL spans.
    chunks, cursor = [], 0
    for first, last in projected_url_spans(value, _bff_compat=_bff_compat):
        chunks.extend((_legacy_safe_text(value[cursor:first], _redact_assignments=False), value[first:last]))
        cursor = last
    chunks.append(_legacy_safe_text(value[cursor:], _redact_assignments=False))
    return ''.join(chunks)
