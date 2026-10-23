"""Filesystem-free grammar and resolver for retained evidence references."""
import json
import re
from ccr.archive.trace import NAME as TRACE_NAME
from ccr.contracts.reference_types import (
    CANONICAL_NAME, FIXED_FILES, REFERENCE_LIMIT, WINDOWS_DEVICE,
)

def _safe_component(value: str) -> bool:
    return (bool(value) and value not in {'.', '..'} and ':' not in value
            and not value.endswith((' ', '.'))
            and not WINDOWS_DEVICE.fullmatch(value))

def parse_reference(reference: str, *, field: str,
                    allow_alias_key: bool = False) -> tuple[str, str | None]:
    """Parse a local retained reference without touching the filesystem."""
    if (not isinstance(reference, str) or not reference or len(reference) > REFERENCE_LIMIT
            or any(ord(char) < 32 for char in reference)):
        raise ValueError(field + ' must be bounded nonempty text without control characters')
    path, marker, fragment = reference.partition('#')
    if '\\' in path or '?' in path:
        raise ValueError(field + ' must use a local POSIX reference without query or backslashes')
    if marker and (not fragment or '#' in fragment):
        raise ValueError(field + ' has an invalid fragment')
    if not path or path.startswith('/') or re.match(r'^[A-Za-z]:', path):
        raise ValueError(field + ' must be relative to the retained review')
    if re.search(r'%(?:2f|5c)', path, re.IGNORECASE):
        raise ValueError(field + ' cannot encode path separators')
    if '%' in path:
        raise ValueError(field + ' cannot contain encoded path characters')
    if re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:', path):
        raise ValueError(field + ' cannot be a URL')

    parts = path.split('/')
    if any(not _safe_component(part) for part in parts):
        raise ValueError(field + ' contains an unsafe path component')
    if parts[0] == 'evidence':
        if len(parts) < 2 or (len(parts) != 2 and not allow_alias_key):
            raise ValueError(field + ' must identify a flat retained evidence file')
        if any(not CANONICAL_NAME.fullmatch(part) for part in parts[1:]):
            if not allow_alias_key:
                raise ValueError(field + ' contains a noncanonical retained evidence name')
    elif path not in FIXED_FILES or allow_alias_key:
        raise ValueError(field + ' must identify retained local evidence')
    return path, fragment if marker else None

def resolve_reference(reference: str, sources: dict[str, bytes], *, field: str) -> object:
    """Resolve one reference against caller-supplied retained bytes only."""
    path, fragment = parse_reference(reference, field=field)
    if not isinstance(sources, dict):
        raise ValueError(field + ' sources must be a map of retained bytes')
    if path not in sources:
        raise ValueError(field + ' source is not selected for retention: ' + path)
    raw = sources[path]
    if not isinstance(raw, bytes):
        raise ValueError(field + ' source must contain bytes')
    if fragment is None:
        return raw

    if path.endswith('.json'):
        try:
            value = json.loads(raw.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(field + ' JSON source is invalid UTF-8 JSON') from exc
        # Preserve the existing profile resolver's key/index and ~0/~1 behavior.
        for token in fragment.lstrip('/').split('/'):
            key = token.replace('~1', '/').replace('~0', '~')
            try:
                value = value[int(key)] if isinstance(value, list) else value[key]
            except (KeyError, IndexError, ValueError, TypeError) as exc:
                raise ValueError(field + ' fragment does not resolve: ' + reference) from exc
        return value

    if path == TRACE_NAME:
        try:
            events = [json.loads(line) for line in raw.decode('utf-8').splitlines()]
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(field + ' trace source is invalid UTF-8 JSONL') from exc
        matches = [event for event in events
                   if isinstance(event, dict) and event.get('event_id') == fragment]
        if not matches:
            raise ValueError(field + ' trace event does not resolve: ' + reference)
        return matches[0]

    if path.endswith('.md'):
        try:
            text = raw.decode('utf-8')
        except UnicodeDecodeError as exc:
            raise ValueError(field + ' Markdown source is not UTF-8') from exc
        anchor = (r'(?:<a\s+id=["\x27]' + re.escape(fragment)
                  + r'["\x27]|^#{1,6}\s+' + re.escape(fragment) + r'(?:\s|$))')
        if re.search(anchor, text, re.MULTILINE):
            return raw
    raise ValueError(field + ' fragment does not resolve: ' + reference)
