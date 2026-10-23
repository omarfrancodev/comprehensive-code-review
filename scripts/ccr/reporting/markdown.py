"""Shared safe formatting primitives for report renderers."""
import html
import re
from urllib.parse import quote, urlsplit

def one_line(value):
    return ' '.join(str(value).splitlines()).strip()

def table_cell(value):
    return one_line(value).replace('|', '\\|')

def markdown_text(value):
    """Keep untrusted metadata inside one literal Markdown block."""
    return re.sub(r'([\\`*{}\[\]()#+!_|>~])', r'\\\1', html.escape(one_line(value), quote=False))

def reference_text(value):
    raw = one_line(value)
    try:
        parsed = urlsplit(raw)
        if parsed.scheme in ('http', 'https') and parsed.netloc and not parsed.username:
            return '[Ver referencia](' + quote(raw, safe='/:#?&=%-._~') + ')'
    except ValueError:
        pass
    return markdown_text(raw)
