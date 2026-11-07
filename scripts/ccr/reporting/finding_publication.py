"""Source-bound sparse editorial views. Never mutate a retained result."""
import copy
import json
from pathlib import Path
from ccr.reporting.projections import publication_digest

MAX_CONTEXT_BYTES = 256 * 1024
MAX_TEXT_BYTES = 16 * 1024
_TEXT_FIELDS = {'title', 'scenario', 'impact', 'correction', 'blocking_reason'}


def _invalid(message):
    raise ValueError('invalid_finding_context: ' + message)


def _encoded(value):
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(',', ':'), allow_nan=False).encode('utf-8')
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        _invalid('valid bounded UTF-8 JSON required')


def _text(value):
    if not isinstance(value, str) or not value.strip():
        _invalid('nonempty editorial text required')
    try:
        if len(value.encode('utf-8')) > MAX_TEXT_BYTES:
            _invalid('editorial text exceeds 16 KiB')
    except UnicodeError:
        _invalid('editorial text is not valid UTF-8')


def normalize_finding_publication_context(record: dict, context: dict | None) -> dict | None:
    if context is None:
        return None
    if len(_encoded(context)) > MAX_CONTEXT_BYTES:
        _invalid('context exceeds 256 KiB')
    if (not isinstance(context, dict) or set(context) != {'schema_version', 'source_sha256', 'findings'}
            or type(context['schema_version']) is not int or context['schema_version'] != 1
            or not isinstance(context['findings'], list)):
        _invalid('exact schema 1 context fields required')
    if context['source_sha256'] != publication_digest(record):
        raise ValueError('finding_context_mismatch: context identifies another original record')
    original = {row['id']: row for row in record['findings'] if row['status'] in ('confirmed', 'unresolved')}
    edited = {}
    for row in context['findings']:
        if not isinstance(row, dict) or not isinstance(row.get('id'), str):
            _invalid('finding row requires an ID')
        identifier = row['id']
        if identifier not in original or identifier in edited or len(row) < 2 or set(row) - (_TEXT_FIELDS | {'id', 'evidence'}):
            _invalid('unique visible source finding and editable fields required')
        result = {'id': identifier}
        for key in _TEXT_FIELDS & row.keys():
            _text(row[key])
            if key == 'blocking_reason' and original[identifier].get(key) is None:
                _invalid('cannot add a blocking reason')
            result[key] = row[key]
        if 'evidence' in row:
            if not isinstance(row['evidence'], list) or not row['evidence']:
                _invalid('nonempty indexed evidence edits required')
            evidence = {}
            for item in row['evidence']:
                if (not isinstance(item, dict) or set(item) != {'index', 'summary'}
                        or type(item['index']) is not int or item['index'] in evidence
                        or not 0 <= item['index'] < len(original[identifier]['evidence'])):
                    _invalid('unique original evidence indices required')
                _text(item['summary'])
                evidence[item['index']] = dict(item)
            result['evidence'] = [evidence[index] for index in sorted(evidence)]
        edited[identifier] = result
    normalized = dict(schema_version=1, source_sha256=context['source_sha256'],
                      findings=[edited[row['id']] for row in record['findings'] if row['id'] in edited])
    if len(_encoded(normalized)) > MAX_CONTEXT_BYTES:
        _invalid('normalized context exceeds 256 KiB')
    return normalized


def finding_publication_digest(context: dict | None) -> str | None:
    return publication_digest(context) if context is not None else None


def project_public_findings(record: dict, context: dict | None = None) -> list[dict]:
    context = normalize_finding_publication_context(record, context)
    view = copy.deepcopy(record['findings'])
    rows = {row['id']: row for row in context['findings']} if context else {}
    for finding in view:
        row = rows.get(finding['id'], {})
        for key in _TEXT_FIELDS & row.keys():
            finding[key] = row[key]
        for item in row.get('evidence', []):
            finding['evidence'][item['index']]['details'] = item['summary']
    return view


def read_finding_publication_context(path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                _invalid('duplicate JSON key')
            result[key] = value
        return result
    with Path(path).open('rb') as stream:
        raw = stream.read(MAX_CONTEXT_BYTES + 1)
    if len(raw) > MAX_CONTEXT_BYTES:
        _invalid('context exceeds 256 KiB')
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                           parse_constant=lambda value: _invalid('nonfinite JSON number'))
        if not isinstance(value, dict):
            _invalid('context JSON must be an object')
        return value
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        _invalid('readable UTF-8 JSON required')
