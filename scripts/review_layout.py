"""Pure, versioned archive layout and logical-scope contract."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit


LAYOUT_VERSION = 2
ARCHIVE_SCHEMA_VERSION = 8
_HEX = re.compile(r'[0-9a-f]{40,64}', re.I)
_SAFE = re.compile(r'[^A-Za-z0-9_-]+')


def _canonical(value):
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
    if len(data) > 65536:
        raise ValueError('logical scope input exceeds 64 KiB')
    return data


def _slug(value, limit=36):
    text = _SAFE.sub('-', str(value)).strip('-_') or 'scope'
    text = text[:limit].rstrip('-_') or 'scope'
    if re.fullmatch(r'(?i)(CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])', text):
        text = ('x-' + text)[:limit]
    return text


def _text(value, label, *, nullable=False):
    if value is None and nullable:
        return None
    if not isinstance(value, str) or not value or len(value) > 500:
        raise ValueError(f'{label} must be nonempty text of at most 500 characters')
    if any(ord(char) < 32 or 0xD800 <= ord(char) <= 0xDFFF for char in value):
        raise ValueError(f'{label} contains invalid characters')
    return value


def _boundaries(value):
    if not isinstance(value, list) or len(value) > 64:
        raise ValueError('boundaries must be a list of at most 64 paths')
    normalized = []
    for raw in value:
        path = _text(raw, 'boundary')
        if '\\' in path or path.startswith('/') or re.match(r'^[A-Za-z]:', path):
            raise ValueError('boundary must be a relative POSIX path')
        parts = path.split('/')
        if any(part in ('', '.', '..') for part in parts):
            raise ValueError('boundary contains traversal or an empty path component')
        for part in parts:
            if any(c in part for c in '<>:"|?*') or part.endswith((' ', '.')) or re.fullmatch(r'(?i)(CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])(?:\..*)?', part):
                raise ValueError('boundary contains a Windows-reserved component')
        normalized.append('/'.join(parts))
    if len(set(normalized)) != len(normalized):
        raise ValueError('boundaries must not contain duplicates')
    return sorted(normalized)


def _selector(mode, scope, selector_input):
    supplied = selector_input
    if supplied is not None:
        if not isinstance(supplied, dict) or set(supplied) != {'mode', 'selector'} or supplied['mode'] != mode:
            raise ValueError('logical scope input must contain matching mode and selector')
        selector = supplied['selector']
        if not isinstance(selector, dict):
            raise ValueError('logical scope selector must be an object')
    else:
        selector = None
    if mode in ('mr', 'pr'):
        reference = _text(scope.get('reference'), 'scope reference')
        if selector is None:
            selector = {'reference': reference}
        if set(selector) != {'reference'} or _text(selector['reference'], 'selector reference') != reference:
            raise ValueError('logical reference must match the pinned scope')
        return {'reference': reference.strip().rstrip('/')}
    if mode == 'commit':
        if selector is None:
            selector = {'head': scope.get('head'), 'base': scope.get('base')}
        if set(selector) != {'head', 'base'} or selector['head'] != scope.get('head') or selector['base'] != scope.get('base'):
            raise ValueError('commit selector must match the pinned head and base')
        return {'head': _text(selector['head'], 'commit head'), 'base': _text(selector['base'], 'commit base', nullable=True)}
    if mode == 'range':
        if selector is None:
            if not scope.get('base') or not scope.get('head'):
                raise ValueError('range needs exact base and head or explicit refs')
            selector = {'kind': 'commits', 'base': scope['base'], 'head': scope['head']}
        if selector.get('kind') == 'commits' and set(selector) == {'kind', 'base', 'head'}:
            if selector['base'] != scope.get('base') or selector['head'] != scope.get('head'):
                raise ValueError('range commit selector must match pinned commits')
            return {'kind': 'commits', 'base': _text(selector['base'], 'range base'), 'head': _text(selector['head'], 'range head')}
        if selector.get('kind') == 'refs' and set(selector) == {'kind', 'base_ref', 'head_ref'}:
            resolved = supplied.get('resolved', {}) if supplied else {}
            if resolved != {'base': scope.get('base'), 'head': scope.get('head')}:
                raise ValueError('symbolic range refs require resolved base/head matching scope')
            return {'kind': 'refs', 'base_ref': _text(selector['base_ref'], 'base ref'), 'head_ref': _text(selector['head_ref'], 'head ref')}
        raise ValueError('range selector must be exact commits or explicit refs')
    if mode in ('module', 'feature'):
        if selector is None or set(selector) != {'reference', 'boundaries'}:
            raise ValueError(f'{mode} requires explicit reference and boundaries')
        reference = _text(selector['reference'], 'selector reference')
        if scope.get('reference') != reference:
            raise ValueError(f'{mode} reference must match pinned scope')
        bounds = _boundaries(selector['boundaries'])
        if not bounds:
            raise ValueError(f'{mode} requires at least one boundary')
        return {'reference': reference, 'boundaries': bounds}
    if mode in ('working', 'staged', 'unstaged'):
        if selector is None:
            selector = {'boundaries': []}
        if set(selector) != {'boundaries'}:
            raise ValueError(f'{mode} selector requires only boundaries')
        return {'boundaries': _boundaries(selector['boundaries'])}
    raise ValueError(f'unsupported scope mode: {mode}')


def logical_scope(scope: dict, selector_input: dict | None = None) -> dict:
    """Return the normalized selector identity, independent of changing revisions."""
    if not isinstance(scope, dict):
        raise ValueError('scope must be an object')
    mode = scope.get('mode')
    if mode not in ('mr', 'pr', 'commit', 'range', 'module', 'feature', 'working', 'staged', 'unstaged'):
        raise ValueError('unsupported scope mode')
    selector = _selector(mode, scope, selector_input)
    identity = hashlib.sha256(_canonical({'mode': mode, 'selector': selector})).hexdigest()
    if mode in ('mr', 'pr'):
        hint = _reference_hint(selector['reference'])
    elif mode == 'commit':
        hint = 'head-' + _slug(selector['head'], 12)
    elif mode == 'range':
        hint = ('base-' + _slug(selector['base'], 12) + '-head-' + _slug(selector['head'], 12)
                if selector['kind'] == 'commits' else 'range-' + _slug(selector['base_ref'], 12) + '-' + _slug(selector['head_ref'], 12))
    elif mode in ('module', 'feature'):
        hint = _slug(selector['reference'])
    else:
        hint = mode + ('-' + _slug(selector['boundaries'][0]) if selector['boundaries'] else '-all')
    hint = _slug(hint, 36)
    return {'mode': mode, 'selector': selector, 'hint': hint, 'identity': identity}


def _reference_hint(reference):
    parsed = urlsplit(reference)
    path = parsed.path.rstrip('/') if parsed.scheme else reference
    leaf = path.rsplit('/', 1)[-1]
    match = re.fullmatch(r'(?:!|#)?([0-9]{1,20})', leaf)
    if match:
        return 'mr-' + match.group(1)
    match = re.search(r'(?i)(?:merge_requests|pull|pulls|mr|pr)[/_-]?([0-9]{1,20})$', path)
    if match:
        return 'mr-' + match.group(1)
    return 'mr-' + _slug(leaf, 12) + '-' + hashlib.sha256(reference.encode('utf-8')).hexdigest()[:16]


def scope_group(logical: dict) -> str:
    if not isinstance(logical, dict) or set(logical) != {'mode', 'selector', 'hint', 'identity'}:
        raise ValueError('invalid logical scope descriptor')
    mode, hint, identity = logical['mode'], logical['hint'], logical['identity']
    if not isinstance(identity, str) or not re.fullmatch(r'[0-9a-f]{64}', identity):
        raise ValueError('invalid logical scope identity')
    if mode in ('mr', 'pr') and re.fullmatch(r'mr-[0-9]{1,20}', hint):
        return hint
    if mode == 'commit':
        return 'commit-' + _slug(logical['selector']['head'], 12) + '-' + identity[:16]
    if mode == 'range':
        return 'range-' + _slug(hint, 36) + '-' + identity[:16]
    return _slug(mode, 12) + '-' + _slug(hint, 36) + '-' + identity[:16]


def run_name(scope: dict, created_at: str, run_id: str, selector_input: dict | None = None) -> str:
    try:
        created = datetime.fromisoformat(created_at)
    except (TypeError, ValueError) as exc:
        raise ValueError('creation timestamp is invalid') from exc
    if created.utcoffset() is None:
        raise ValueError('creation timestamp needs timezone')
    if not isinstance(run_id, str) or not re.fullmatch(r'[0-9a-f]{20}', run_id):
        raise ValueError('run ID must be 20 lowercase hex characters')
    logical = logical_scope(scope, selector_input)
    hint = logical['hint']
    if logical['mode'] == 'commit':
        hint = 'head-' + _slug(logical['selector']['head'], 12)
    elif logical['mode'] == 'range' and logical['selector']['kind'] == 'commits':
        hint = 'base-' + _slug(logical['selector']['base'], 12) + '-head-' + _slug(logical['selector']['head'], 12)
    elif logical['mode'] not in ('mr', 'pr'):
        hint = ('snap-' + _slug(scope.get('snapshot'), 12) if scope.get('snapshot') else logical['mode'] + '-' + _slug(logical['hint'], 20))
    elif logical['mode'] in ('mr', 'pr'):
        hint = 'head-' + _slug(scope.get('head') or 'unknown', 12)
    value = datetime.now(timezone.utc) if False else created.astimezone(timezone.utc)
    name = value.strftime('%Y%m%dT%H%M%SZ') + '--' + _slug(hint, 36) + '--' + run_id
    if len(name) > 128:
        raise ValueError('run directory name exceeds 128 characters')
    return name


def validate_layout(run_dir: Path, manifest: dict) -> None:
    run = Path(run_dir)
    if manifest.get('schema_version') != ARCHIVE_SCHEMA_VERSION or manifest.get('layout_version') != LAYOUT_VERSION:
        raise ValueError('unsupported_layout: archive schema/layout version is not native layout 2')
    logical = manifest.get('logical_scope')
    expected_logical = logical_scope(manifest.get('scope'), manifest.get('logical_scope_input'))
    if logical != expected_logical:
        raise ValueError('invalid archive layout: logical scope descriptor differs from pinned selector')
    root = Path(manifest['archive_root']).resolve()
    try:
        parts = run.resolve().relative_to(root).parts
    except ValueError as exc:
        raise ValueError('invalid archive layout: run is outside archive root') from exc
    if len(parts) != 3 or parts[1] != scope_group(logical):
        raise ValueError('invalid archive layout: logical scope directory differs from descriptor')
    if parts[2] != run_name(manifest['scope'], manifest['created_at'], manifest['run_id'], manifest.get('logical_scope_input')):
        raise ValueError('invalid archive layout: run directory differs from stored timestamp, hint, and ID')
    if not re.fullmatch(r'[0-9a-f]{20}', str(manifest.get('repository_key', ''))):
        raise ValueError('invalid archive layout: repository key is missing')


def classify_header(manifest: dict) -> dict:
    if not isinstance(manifest, dict):
        return {'status': 'invalid', 'code': 'invalid_header', 'actions': ['preserve']}
    if manifest.get('schema_version') != ARCHIVE_SCHEMA_VERSION or manifest.get('layout_version') != LAYOUT_VERSION:
        return {'status': 'unsupported_layout', 'code': 'unsupported_layout', 'actions': ['port_history', 'new_review', 'preserve']}
    try:
        expected = logical_scope(manifest.get('scope'), manifest.get('logical_scope_input'))
        if manifest.get('logical_scope') != expected:
            raise ValueError('logical scope mismatch')
    except (TypeError, ValueError):
        return {'status': 'invalid', 'code': 'invalid_header', 'actions': ['preserve']}
    return {'status': 'native', 'code': None, 'actions': ['inspect', 'lookup']}
