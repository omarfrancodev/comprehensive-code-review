"""Shared, filesystem-free grammar and resolver for retained review evidence."""
import json
import re
from typing import TypedDict

import review_trace


REFERENCE_LIMIT = 500
ISSUE_LIMIT = 100
CANONICAL_NAME = re.compile(r'[A-Za-z0-9._-]+')
WINDOWS_DEVICE = re.compile(r'(?i)(CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])(?:\..*)?')
FIXED_FILES = {'review.json', 'informe.md', 'measurements.json',
               review_trace.NAME, 'handoff.md'}
class ReferenceIssue(TypedDict):
    code: str
    field: str
    reference: str | None
    message: str
    expected: str


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

    if path == review_trace.NAME:
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


def _issue(code: str, field: str, reference: str | None,
           message: str, expected: str) -> ReferenceIssue:
    return {'code': code, 'field': field, 'reference': reference,
            'message': message[:500], 'expected': expected[:500]}


def validate_selection_reference(selection: dict,
                                 sources: dict[str, bytes] | None) -> list[ReferenceIssue]:
    """Validate profile selection syntax and, when supplied, its exact value."""
    field = 'profile reference'
    reference = selection.get('reference') if isinstance(selection, dict) else None
    issues: list[ReferenceIssue] = []
    try:
        path, fragment = parse_reference(reference, field=field)
    except ValueError as exc:
        return [_issue('invalid_reference', field, reference if isinstance(reference, str) else None,
                       str(exc), 'evidence/context.json#profile')]

    if fragment is None:
        return [_issue('missing_fragment', field, reference,
                       'profile selection requires a JSON profile fragment',
                       'evidence/context.json#profile')]
    if path != 'evidence/context.json' or fragment != 'profile':
        return [_issue('invalid_reference', field, reference,
                       'profile selection must use the canonical profile source',
                       'evidence/context.json#profile')]
    if sources is None:
        return []
    if not isinstance(sources, dict) or path not in sources:
        return [_issue('missing_source', field, reference,
                       'profile source is not available in the selected bytes', path)]
    try:
        observed = resolve_reference(reference, sources, field=field)
        import review_profiles
        expected = review_profiles._canonical(selection.get('profile'))
    except (ValueError, TypeError) as exc:
        return [_issue('invalid_reference', field, reference, str(exc),
                       'valid UTF-8 JSON with the selected profile')]
    if observed != expected:
        issues.append(_issue('profile_mismatch', field, reference,
                             'profile source differs from the captured selection', expected))
    return issues[:ISSUE_LIMIT]
