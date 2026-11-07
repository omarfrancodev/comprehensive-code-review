# Frozen lexer for exact schema 1 proof reconstruction from f6b083e only.
"""Bounded lexical credential classification over original source text."""
import json
import re
from itertools import chain

_KEY = r'(?:token|password|secret|api[-_]?key|authorization|credential)'
_VALUE = re.compile(r'''(?:"(?P<double>(?:\\.|[^"\\])*)"|'(?P<single>(?:\\.|[^'\\])*)'|(?P<bare>[^\s,;}\]<>`]+))''')
_KEY_START = re.compile(r'''(?ix)(?<![\w-])(?P<quote>["']?)(?P<key>''' + _KEY + r''')(?P=quote)\s*(?P<sep>[=:])\s*(?:(?:Bearer|Basic)\s+)?''')
_FIELD_START = re.compile(r'(?m)^[ \t]*(?:(?:[-*+]|[0-9]{1,9}[.)])\s+)?$')
# Prefix atoms have disjoint leading characters, including nested lists.
_PREFIX = re.compile(r'(?:[ \t>]|[-*+](?=[ \t])|[0-9]{1,9}[.)](?=[ \t]))*')
_FENCE = re.compile(r'(?P<marker>`{3,}|~{3,})(?P<tail>[^\n]*)')
_TICKS = re.compile(r'`+')
_INLINE_VALUE_END = re.compile(r'`+|[\r\n]')
_INDENT = re.compile(r' *')
_LIST_MARKERS = re.compile(r'(?:[-*+]|[0-9]{1,9}[.)]) +')
_SOURCE_INDENT = re.compile(r'[ \t]*')
_LINES = re.compile(r'[^\n]*(?:\n|\Z)')


def _fence_layout(prefix):
    parts = prefix.split('>')
    for level, part in enumerate(parts):
        if level and part.startswith(' '):
            part = part[1:]
        expanded = part.expandtabs(4)
        yield (_INDENT.match(expanded).end(), len(expanded),
               [marker.end() for marker in _LIST_MARKERS.finditer(expanded)])


def _continues_fence(value, start, end, quote_indents, list_indent):
    cursor = start
    for required in quote_indents:
        indent = _SOURCE_INDENT.match(value, cursor, end)
        cursor = indent.end()
        if (cursor == end or value[cursor] != '>'
                or len(indent.group().expandtabs(4)) < required):
            return False
        cursor += 1
        if cursor < end and value[cursor] == ' ':
            cursor += 1
    indent = _SOURCE_INDENT.match(value, cursor, end)
    return (len(indent.group().expandtabs(4)) >= list_indent
            or not value[indent.end():end].strip())


def _fenced_code_ranges(value):
    opening = None
    active_lists = []
    for line in _LINES.finditer(value):
        first, end = line.span()
        if opening is not None and not _continues_fence(value, first, end, opening[3], opening[4]):
            yield opening[0], first
            opening = None
        prefix = _PREFIX.match(value, first, end)
        marker = _FENCE.match(value, prefix.end(), end)
        if opening is not None:
            if marker and not marker['tail'].strip():
                layout = list(_fence_layout(prefix.group()))
                _, indent, markers = layout[-1]
                if (marker['marker'][0] == opening[1] and len(marker['marker']) >= opening[2]
                        and not markers and len(layout) - 1 == len(opening[3])
                        and opening[4] <= indent <= opening[4] + 3):
                    yield opening[0], marker.end()
                    opening = None
            continue
        layout = list(_fence_layout(prefix.group()))
        del active_lists[len(layout):]
        quote_indents = []
        has_content = bool(value[prefix.end():end].strip())
        # Each quote level has its own list indentation stack. A dedent can
        # leave an inner item while the surrounding list still owns the fence.
        for level, (leading, indent, markers) in enumerate(layout):
            if level == len(active_lists):
                active_lists.append([])
            items = active_lists[level]
            if has_content or markers or level < len(layout) - 1:
                while items and items[-1] > leading:
                    items.pop()
                items.extend(markers)
            container_indent = items[-1] if items else 0
            if level < len(layout) - 1:
                quote_indents.append(container_indent)
        if marker:
            delimiter = marker['marker']
            if delimiter[0] == '`' and '`' in marker['tail']:
                continue  # A backtick fence's info string cannot contain ticks.
            # Preserve the conservative treatment of indented code with
            # fence markers, while still ending it at its indentation boundary.
            base_indent = indent if indent > container_indent + 3 else container_indent
            opening = first, delimiter[0], len(delimiter), quote_indents, base_indent
    if opening is not None:
        yield opening[0], len(value)


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
    keys = _KEY_START.finditer(value)
    first_key = next(keys, None)
    if first_key is None:
        return values
    # Visit line/code boundaries once rather than repeatedly slicing prefixes.
    newlines = iter(re.finditer('\n', value))
    newline = next(newlines, None)
    code_ranges = iter(_code_ranges(value))
    code_range = next(code_ranges, None)
    line_start, tested_line = 0, None
    consumed_until = 0
    for match in chain((first_key,), keys):
        if match.start() < consumed_until:
            continue
        while newline is not None and newline.start() < match.start():
            line_start = newline.end()
            newline = next(newlines, None)
        while code_range is not None and code_range[1] <= match.start():
            code_range = next(code_ranges, None)
        in_code = code_range is not None and code_range[0] <= match.start()
        field_start = (line_start != tested_line and
                       _FIELD_START.fullmatch(value, line_start, match.start()) is not None)
        tested_line = line_start

        value_start = match.end()
        ticks = _TICKS.match(value, value_start)
        code_end = None
        if ticks and code_range is not None:
            if ticks.end() == code_range[0]:
                code_end = code_range[1]
            elif in_code:
                # Backticks in a fence or larger span are literal delimiters
                # here. Match the next run on the same line within that code.
                closer = _INLINE_VALUE_END.search(value, ticks.end(), code_range[1])
                if closer and closer.group() == ticks.group():
                    code_end = closer.start()
        literal = None if code_end is not None else _VALUE.match(value, value_start)
        if code_end is None and literal is None:
            continue
        double = literal is not None and literal['double'] is not None
        single = literal is not None and literal['single'] is not None
        # A rejected prose colon never consumes its possible value. An
        # explicit assignment starting at that position is still visited.
        structured = (syntax == 'structured' or match['sep'] == '=' or match['quote']
                      or double or single or code_end is not None or match['key'].lower() == 'authorization'
                      or field_start or in_code)
        if not structured:
            continue
        if code_end is not None:
            candidate = value[ticks.end():code_end]
            consumed_until = code_end
            # Include the Markdown display spelling as well as source bytes.
            displayed = re.sub(r'\r\n?|\n', ' ', candidate)
            if displayed.startswith(' ') and displayed.endswith(' ') and displayed.strip(' '):
                displayed = displayed[1:-1]
            if displayed.strip() and displayed not in ('[omitido]', '[omitido'):
                values.add(displayed)
        else:
            candidate = next(part for part in literal.groups() if part is not None)
            if double or single:
                consumed_until = literal.end()
        if candidate and candidate not in ('[omitido]', '[omitido'):
            values.add(candidate)
            if double:
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
