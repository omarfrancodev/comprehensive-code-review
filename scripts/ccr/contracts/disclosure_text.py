"""Bounded lexical credential classification over original source text."""
import re
import json

_KEY = r'(?:token|password|secret|api[-_]?key|authorization|credential)'
_VALUE = r'''(?:"(?P<double>(?:\\.|[^"\\])*)"|'(?P<single>(?:\\.|[^'\\])*)'|(?P<bare>[^\s,;}\]<>`]+))'''
_PAIR = re.compile(r'''(?ix)(?<![\w-])(?P<quote>["']?)(?P<key>''' + _KEY + r''')(?P=quote)\s*(?P<sep>[=:])\s*(?:(?:Bearer|Basic)\s+)?''' + _VALUE)
_FIELD_START = re.compile(r'(?m)^[ \t]*(?:[-*+]\s+)?$')


def sensitive_values_from_text(value: str, *, syntax='prose') -> set[str]:
    """Only structured assignments teach values; narrative colons do not."""
    if syntax not in ('prose', 'structured'):
        raise ValueError('unknown privacy text syntax')
    if not isinstance(value, str):
        raise ValueError('privacy source must be text')
    values = set()
    # Visit line/quote boundaries once rather than repeatedly slicing prefixes.
    newlines = iter(re.finditer('\n', value))
    newline = next(newlines, None)
    ticks = iter(re.finditer(r'(?<!\\)`', value))
    tick = next(ticks, None)
    line_start, tested_line, tick_count = 0, None, 0
    for match in _PAIR.finditer(value):
        quoted_value = match['double'] is not None or match['single'] is not None
        while newline is not None and newline.start() < match.start():
            line_start = newline.end()
            newline = next(newlines, None)
        while tick is not None and tick.start() < match.start():
            tick_count += 1
            tick = next(ticks, None)
        field_start = (line_start != tested_line and
                       _FIELD_START.fullmatch(value, line_start, match.start()) is not None)
        tested_line = line_start
        # JSON quoted keys, explicit values/assignments and auth headers have
        # authority independently of sentence position. Other bare colon pairs
        # need a field boundary or an explicitly selected structured source.
        structured = (syntax == 'structured' or match['sep'] == '=' or match['quote']
                      or quoted_value or match['key'].lower() == 'authorization'
                      or field_start or tick_count % 2)
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
