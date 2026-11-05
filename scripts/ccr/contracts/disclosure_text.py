"""Bounded lexical credential classification over original source text."""
import json
import re
from bisect import bisect_left
from itertools import chain

_KEY = r'(?:token|password|secret|api[-_]?key|authorization|credential)'
_VALUE = re.compile(r'''(?:"(?P<double>(?:\\.|[^"\\])*)"|'(?P<single>(?:\\.|[^'\\])*)'|(?P<bare>[^\s,;}\]<>`]+))''')
_KEY_START = re.compile(r'''(?ix)(?<![\w-])(?P<quote>["']?)(?P<key>''' + _KEY + r''')(?P=quote)\s*(?P<sep>[=:])\s*(?:(?:Bearer|Basic)\s+)?''')
_FIELD_START = re.compile(r'[ \t]*(?:(?:[-*+]|[0-9]{1,9}[.)])\s+)?')
# Prefix atoms have disjoint leading characters, including nested lists.
_PREFIX = re.compile(r'(?:[ \t>]|[-*+](?=[ \t])|[0-9]{1,9}[.)](?=[ \t]))*')
_FENCE = re.compile(r'(?P<marker>`{3,}|~{3,})(?P<tail>[^\r\n]*)')
_TICKS = re.compile(r'`+')
_INDENT = re.compile(r' *')
_LINE_END = re.compile(r'\r\n|[\r\n]')
_LIST_MARKERS = re.compile(r'(?:[-*+]|[0-9]{1,9}[.)]) +')
_LINES = re.compile(r'[^\r\n]*(?:\r\n|[\r\n]|\Z)')


def _fence_layout(prefix):
    parts = prefix.split('>')
    for level, part in enumerate(parts):
        if level and part.startswith(' '):
            part = part[1:]
        yield (_INDENT.match(part).end(), len(part),
               [marker.end() for marker in _LIST_MARKERS.finditer(part)])


def _continues_fence(prefix, has_content, quote_indents, list_indent):
    cursor = 0
    for required in quote_indents:
        quote = _INDENT.match(prefix, cursor).end()
        if quote - cursor < required or prefix[quote:quote + 1] != '>':
            return False
        cursor = quote + 1
        if prefix[cursor:cursor + 1] == ' ':
            cursor += 1
    content = _INDENT.match(prefix, cursor).end()
    return (content - cursor >= list_indent
            or (content == len(prefix) and not has_content))


def _fenced_code_ranges(value):
    opening = None
    active_lists = []
    for line in _LINES.finditer(value):
        first, end = line.span()
        prefix = _PREFIX.match(value, first, end)
        # Expand once from column zero. Removing quote markers first would
        # give the tab after a marker the wrong width.
        expanded = prefix.group().expandtabs(4)
        has_content = bool(value[prefix.end():end].strip())
        if opening is not None and not _continues_fence(expanded, has_content, opening[3], opening[4]):
            yield opening[0], opening[5], first, first
            opening = None
        marker = _FENCE.match(value, prefix.end(), end)
        if opening is not None:
            if marker and not marker['tail'].strip():
                layout = list(_fence_layout(expanded))
                _, indent, markers = layout[-1]
                if (marker['marker'][0] == opening[1] and len(marker['marker']) >= opening[2]
                        and not markers and len(layout) - 1 == len(opening[3])
                        and opening[4] <= indent <= opening[4] + 3):
                    yield opening[0], opening[5], first, marker.end()
                    opening = None
            continue
        layout = list(_fence_layout(expanded))
        del active_lists[len(layout):]
        quote_indents = []
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
            opening = first, delimiter[0], len(delimiter), quote_indents, base_indent, end
    if opening is not None:
        yield opening[0], opening[5], len(value), len(value)


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
    for first, content_start, content_end, last in _fenced_code_ranges(value):
        yield from _inline_code_ranges(value, cursor, first)
        if content_start < content_end:
            yield content_start, content_end
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
    newlines = iter(_LINE_END.finditer(value))
    newline = next(newlines, None)
    code_ranges = iter(_code_ranges(value))
    code_range = next(code_ranges, None)
    ticks_by_length = None
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
            ticks_by_length = None
        in_code = code_range is not None and code_range[0] <= match.start()
        field_start = (line_start != tested_line and
                       _FIELD_START.fullmatch(value, line_start, match.start()) is not None)
        tested_line = line_start

        value_start = match.end()
        if in_code and value_start >= code_range[1]:
            continue  # Whitespace after a key cannot borrow a value from prose.
        ticks = _TICKS.match(value, value_start)
        code_end = None
        if ticks and code_range is not None:
            if ticks.end() == code_range[0]:
                code_end = code_range[1]
            elif in_code:
                # Inside code these are literal delimiters. Index the
                # remaining line once and never consume a subsequent field
                # when the current line has no matching closing run.
                if ticks_by_length is None or ticks.start() >= tick_line_end:
                    newline_after_ticks = _LINE_END.search(value, ticks.end(), code_range[1])
                    tick_line_end = newline_after_ticks.start() if newline_after_ticks else code_range[1]
                    ticks_by_length = {}
                    for run in _TICKS.finditer(value, ticks.start(), tick_line_end):
                        ticks_by_length.setdefault(run.end() - run.start(), []).append(run.start())
                positions = ticks_by_length.get(ticks.end() - ticks.start(), ())
                next_run = bisect_left(positions, ticks.end())
                if next_run < len(positions):
                    code_end = positions[next_run]
        literal = None if code_end is not None else _VALUE.match(value, value_start)
        if code_end is None and (literal is None or (in_code and literal.end() > code_range[1])):
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
