"""Versioned, byte-preserving identity of effective Git changes (not recovery)."""
import base64
import binascii
import copy
import hashlib
import json
import re

ALGORITHM = 'ccr-effective-diff-v1'
MAX_ENTRIES = 10000
MAX_PATCH_BYTES = 32 * 1024 * 1024
MAX_DESCRIPTOR_BYTES = 64 * 1024 * 1024
HASH = re.compile(r'[0-9a-f]{64}')
MODES = {'100644', '100755', '120000', '160000'}


def canonical_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode('utf-8')


def decode_path(value):
    raw = decode64(value)
    if (not raw or b'\0' in raw or raw.startswith((b'/', b'\\'))
            or any(part in (b'', b'.', b'..') for part in raw.split(b'/'))
            or re.match(rb'^[A-Za-z]:', raw)):
        raise ValueError('invalid Git path bytes')
    return raw


def decode64(value):
    try:
        raw = base64.b64decode(value, validate=True)
        if base64.b64encode(raw).decode('ascii') != value:
            raise ValueError('noncanonical base64')
        return raw
    except (ValueError, TypeError, binascii.Error) as exc:
        raise ValueError('invalid base64 bytes') from exc


def diagnostics(value):
    if not isinstance(value, list) or len(value) > 100:
        raise ValueError('diagnostics must contain at most 100 rows')
    for row in value:
        if (not isinstance(row, dict) or set(row) != {'code', 'detail'}
                or any(not isinstance(row[k], str) or not row[k] or len(row[k]) > 2000
                       for k in ('code', 'detail'))):
            raise ValueError('invalid diagnostic')


def effective_projection(descriptor):
    rows = [{k: copy.deepcopy(v) for k, v in row.items() if k not in ('old_blob', 'new_blob')}
            for row in descriptor['entries']]
    return sorted(rows, key=lambda r: (decode_path(r['old_path_b64']) if r['old_path_b64'] else b'',
                                      decode_path(r['new_path_b64']) if r['new_path_b64'] else b''))


def change_digest(descriptor):
    return hashlib.sha256(canonical_bytes(effective_projection(descriptor))).hexdigest()


def normalize_effective_changes(raw):
    fields = {'schema_version', 'algorithm', 'logical_scope_identity', 'comparison',
              'complete', 'entries', 'changes_sha256', 'diagnostics'}
    if not isinstance(raw, dict) or set(raw) != fields:
        raise ValueError('invalid effective changes fields')
    if type(raw['schema_version']) is not int or raw['schema_version'] != 1 or raw['algorithm'] != ALGORITHM:
        raise ValueError('unsupported effective changes algorithm/schema')
    if not isinstance(raw['logical_scope_identity'], str) or not HASH.fullmatch(raw['logical_scope_identity']):
        raise ValueError('invalid logical scope identity')
    if type(raw['complete']) is not bool:
        raise ValueError('complete must be boolean')
    diagnostics(raw['diagnostics'])
    comparison = raw['comparison']
    if (not isinstance(comparison, dict) or set(comparison) !=
            {'kind', 'base', 'head', 'target_head', 'diff_base', 'object_format'}
            or comparison['kind'] != 'merge-base-to-head'
            or comparison['object_format'] not in ('sha1', 'sha256')):
        raise ValueError('invalid comparison provenance')
    length = 40 if comparison['object_format'] == 'sha1' else 64

    def oid(value):
        return isinstance(value, str) and re.fullmatch('[0-9a-f]{' + str(length) + '}', value)

    for name in ('base', 'head', 'target_head', 'diff_base'):
        if not oid(comparison[name]):
            raise ValueError('comparison requires full commit identities')
    rows = raw['entries']
    if not isinstance(rows, list) or len(rows) > MAX_ENTRIES:
        raise ValueError('effective changes exceed entry limit')
    seen, patch_size = set(), 0
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'old_path_b64', 'new_path_b64', 'old_mode',
                'new_mode', 'kind', 'old_blob', 'new_blob', 'payload'}:
            raise ValueError('invalid effective change entry')
        paths = []
        for side in ('old', 'new'):
            path, mode, blob = (row[side + suffix] for suffix in ('_path_b64', '_mode', '_blob'))
            if path is None:
                if mode is not None or blob is not None:
                    raise ValueError('absent path must have absent mode/blob')
                paths.append(None)
            else:
                paths.append(decode_path(path))
                if mode not in MODES or not oid(blob):
                    raise ValueError('invalid file mode/blob')
        key = tuple(paths)
        if key == (None, None) or key in seen:
            raise ValueError('duplicate or absent effective change path')
        seen.add(key)
        kind, payload = row['kind'], row['payload']
        if not isinstance(payload, dict):
            raise ValueError('invalid payload')
        modes = {row['old_mode'], row['new_mode']} - {None}
        if kind == 'text':
            if set(payload) != {'patch_b64'} or not modes.issubset({'100644', '100755'}):
                raise ValueError('invalid text payload/mode')
            patch_size += len(decode64(payload['patch_b64']))
        elif kind in ('binary', 'symlink', 'gitlink'):
            suffix = 'commit' if kind == 'gitlink' else 'sha256'
            if set(payload) != {'old_' + suffix, 'new_' + suffix}:
                raise ValueError('invalid content payload')
            if kind == 'symlink' and '120000' not in modes or kind == 'gitlink' and '160000' not in modes:
                raise ValueError('invalid content kind/mode')
            for side in ('old', 'new'):
                value = payload[side + '_' + suffix]
                if row[side + '_path_b64'] is None:
                    if value is not None:
                        raise ValueError('absent side has content')
                elif not (oid(value) if kind == 'gitlink' else isinstance(value, str) and HASH.fullmatch(value)):
                    raise ValueError('invalid content identity')
        else:
            raise ValueError('unknown effective change kind')
    if patch_size > MAX_PATCH_BYTES or len(canonical_bytes(raw)) > MAX_DESCRIPTOR_BYTES:
        raise ValueError('effective changes exceed byte limit')
    if raw['changes_sha256'] != change_digest(raw):
        raise ValueError('effective changes digest differs from payload')
    if raw['entries'] != sorted(raw['entries'], key=lambda r: (
            decode_path(r['old_path_b64']) if r['old_path_b64'] else b'',
            decode_path(r['new_path_b64']) if r['new_path_b64'] else b'')):
        raise ValueError('effective changes must be ordered')
    return copy.deepcopy(raw)


def compare_effective_changes(retained, current):
    current = normalize_effective_changes(current)
    result = dict(code_equivalence='unknown', changed_paths=[], metadata_only=False, reasons=[])
    try:
        old = normalize_effective_changes(retained)
    except (ValueError, TypeError):
        result['reasons'] = [dict(code='previous_changes_unknown', detail='No verified previous change descriptor.')]
        return result
    if not old['complete'] or not current['complete']:
        result['reasons'] = [dict(code='incomplete_changes', detail='Change capture is incomplete.')]
        return result
    equal = (old['logical_scope_identity'] == current['logical_scope_identity']
             and effective_projection(old) == effective_projection(current))
    result.update(code_equivalence='equivalent' if equal else 'different',
                  metadata_only=equal and old != current)
    if not equal:
        old_rows = {(r['old_path_b64'], r['new_path_b64']): r for r in effective_projection(old)}
        new_rows = {(r['old_path_b64'], r['new_path_b64']): r for r in effective_projection(current)}
        result['changed_paths'] = [dict(old_path_b64=k[0], new_path_b64=k[1])
            for k in sorted(set(old_rows) | set(new_rows), key=repr) if old_rows.get(k) != new_rows.get(k)]
        result['reasons'] = [dict(code='effective_changes_differ', detail='Reviewed paths, modes or content differ.')]
    return result
