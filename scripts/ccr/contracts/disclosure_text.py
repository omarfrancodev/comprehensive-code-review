"""Bounded lexical credential classification over original source text."""
import re
import json

_KEY = r'(?:token|password|secret|api[-_]?key|authorization|credential)'
_VALUE = r'''(?:"(?P<double>(?:\\.|[^"\\])*)"|'(?P<single>(?:\\.|[^'\\])*)'|(?P<bare>[^\s,;}\]<>`]+))'''
_PAIR = re.compile(r'''(?ix)(?<![\w-])(?P<quote>["']?)(?P<key>''' + _KEY + r''')(?P=quote)\s*(?P<sep>[=:])\s*(?:(?:Bearer|Basic)\s+)?''' + _VALUE)
_FIELD_START = re.compile(r'(?m)^[ \t]*(?:(?:[-*+]|[0-9]{1,9}[.)])\s+)?$')
# Container atoms have disjoint leading characters; prefix matching stays
# linear for nested lists/quotes and for lines that contain no fence.
_FENCE = re.compile(r'(?m)^(?P<prefix>(?:[ \t>]|[-*+](?=[ \t])|[0-9]{1,9}[.)](?=[ \t]))*)'
                    r'(?P<marker>`{3,}|~{3,})(?P<tail>[^\n]*)')
_TICKS = re.compile(r'`+')


def _fence_layout(prefix):
    quotes = prefix.count('>')
    tail = prefix.rsplit('>', 1)[-1]
    if quotes and tail.startswith(' '):
        tail = tail[1:]
    indent = len(tail.expandtabs(4))
    list_marker = any(char not in ' \t>' for char in prefix)
    return quotes, indent, list_marker


def _fenced_code_ranges(value):
    opening = None
    for match in _FENCE.finditer(value):
        marker = match['marker']
        if opening is None:
            if marker[0] == '`' and '`' in match['tail']:
                continue  # A backtick fence's info string cannot contain ticks.
            quotes, indent, list_marker = _fence_layout(match['prefix'])
            base_indent = indent if list_marker or indent > 3 else 0
            opening = (match.start(), marker[0], len(marker), quotes, base_indent)
        elif (marker[0] == opening[1] and len(marker) >= opening[2]
              and not match['tail'].strip()):
            quotes, indent, list_marker = _fence_layout(match['prefix'])
            if (not list_marker and quotes == opening[3]
                    and opening[4] <= indent <= opening[4] + 3):
                yield opening[0], match.end()
                opening = None
    if opening is not None:
        yield opening[0], len(value)  # Fenced blocks may continue to EOF.


def _inline_code_ranges(value, start, end):
    # Only retain the last position per delimiter length, rather than every
    # run. It proves a matching closer exists before accepting an opener.
    last_by_length = {}
    for match in _TICKS.finditer(value, start, end):
        last_by_length[match.end() - match.start()] = match.start()
    opening = None
    for match in _TICKS.finditer(value, start, end):
        length = match.end() - match.start()
        if opening is None:
            cursor = match.start()
            while cursor > start and value[cursor - 1] == '\\':
                cursor -= 1
            length -= (match.start() - cursor) % 2
            if length and last_by_length.get(length, -1) > match.start():
                opening = match.end(), length
        elif length == opening[1]:
            yield opening[0], match.start()
            opening = None  # Backslashes are literal inside code spans.


def _code_ranges(value):
    cursor = 0
    for first, last in _fenced_code_ranges(value):
        yield from _inline_code_ranges(value, cursor, first)
        yield first, last
        cursor = last
    yield from _inline_code_ranges(value, cursor, len(value))


def sensitive_values_from_text(value: str, *, syntax='prose') -> set[str]:
    """Only structured assignments teach values; narrative colons do not."""
    if syntax not in ('prose', 'structured'):
        raise ValueError('unknown privacy text syntax')
    if not isinstance(value, str):
        raise ValueError('privacy source must be text')
    values = set()
    # Visit line/code boundaries once rather than repeatedly slicing prefixes.
    newlines = iter(re.finditer('\n', value))
    newline = next(newlines, None)
    code_ranges = iter(_code_ranges(value))
    code_range = next(code_ranges, None)
    line_start, tested_line = 0, None
    for match in _PAIR.finditer(value):
        quoted_value = match['double'] is not None or match['single'] is not None
        while newline is not None and newline.start() < match.start():
            line_start = newline.end()
            newline = next(newlines, None)
        while code_range is not None and code_range[1] <= match.start():
            code_range = next(code_ranges, None)
        in_code = code_range is not None and code_range[0] <= match.start()
        field_start = (line_start != tested_line and
                       _FIELD_START.fullmatch(value, line_start, match.start()) is not None)
        tested_line = line_start
        # JSON quoted keys, explicit values/assignments and auth headers have
        # authority independently of sentence position. Other bare colon pairs
        # need a field boundary or an explicitly selected structured source.
        structured = (syntax == 'structured' or match['sep'] == '=' or match['quote']
                      or quoted_value or match['key'].lower() == 'authorization'
                      or field_start or in_code)
        if structured:
            candidate = next((match[name] for name in ('double', 'single', 'bare')
                              if match[name] is not None), '')
            if candidate and candidate not in ('[omitido]', '[omitido'):
                values.add(candidate)
                if match['double'] is not None:
                    # Preserve lexical and JSON spellings; no code evaluation.
                    try:
                        decoded = json.loads('"' + candidate + '"')
                        decoded.encode('utf-8')
                    except (ValueError, UnicodeError):
                        pass
                    else:
                        if decoded:
                            values.add(decoded)
    return values
