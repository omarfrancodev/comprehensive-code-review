"""CCR 3.6.0 projection, only for rerendering historical drafts 2/3."""
import re
from ccr.reporting.markdown import markdown_text, one_line

def legacy_public_projection(text, record, check_disclosure_context=None, check_disclosure_sources=None):
    """Exclude recorded raw commands and private absolute paths from publication."""
    if check_disclosure_context is not None or record.get('schema_version') == 13:
        from ccr.contracts.check_disclosure import _legacy_safe_text as safe_text, private_values
        typed_lines = {'  - **Comando saneado:** ' + markdown_text(row['command'])
                       for row in (check_disclosure_context or {}).get('checks', []) if row['command']}
        lines = []
        for line in text.splitlines(keepends=True):
            if line.rstrip('\r\n') not in typed_lines:
                for check in record.get('checks', []):
                    command = check.get('command', '')
                    if command:
                        line = line.replace(command, '[comprobación registrada]')
                        line = line.replace(markdown_text(command), '[comprobación registrada]')
            lines.append(line)
        text = ''.join(lines)
        return safe_text(text, private_values(record, check_disclosure_context, check_disclosure_sources or {}))
    for check in record.get('checks', []):
        command = one_line(check.get('command', ''))
        if command:
            text = text.replace(command, '[comprobación registrada]')
            text = text.replace(markdown_text(command), '[comprobación registrada]')
    urls = []

    def preserve_url(match):
        urls.append(match.group(0))
        return f'PUBLICURLPLACEHOLDER{len(urls) - 1}END'

    text = re.sub(r'https?://[^\s<>)\]]+', preserve_url, text)
    text = re.sub(r'(?i)(?<![a-z0-9])[a-z]:[\\/][^\s;|<>)]+', '[ruta privada]', text)
    text = re.sub(r'(?<![\w:#/<])/(?!/)[^\s;|<>)\]]+', '[ruta privada]', text)
    text = re.sub(r'\\\\[^\s;|<>)]+', '[ruta privada]', text)
    for index, url in enumerate(urls):
        text = text.replace(f'PUBLICURLPLACEHOLDER{index}END', url)
    return text
