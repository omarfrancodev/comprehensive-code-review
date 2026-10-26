"""Read immutable Git objects without modifying the checkout or invoking filters."""
import base64
import hashlib
import re

from ccr.archive.layout import logical_scope
from ccr.contracts.effective_changes import (
    ALGORITHM, MAX_ENTRIES, MAX_PATCH_BYTES, change_digest, decode_path,
    normalize_effective_changes,
)
from ccr.contracts.scope import require_scope
from ccr.shared.git import git, git_bytes, iter_git_bytes


def _b64(raw):
    return base64.b64encode(raw).decode('ascii')


def parse_raw(raw):
    parts = raw.split(b'\0')
    if parts[-1] != b'' or (len(parts)-1) % 2:
        raise ValueError('incomplete raw Git change list')
    rows = []
    for offset in range(0, len(parts)-1, 2):
        header = parts[offset].split()
        if len(header) != 5 or not header[0].startswith(b':') or header[4] not in (b'A', b'D', b'M', b'T'):
            raise ValueError('unsupported raw Git change')
        rows.append(dict(path=parts[offset+1], old_mode=header[0][1:].decode('ascii'),
            new_mode=header[1].decode('ascii'), old_blob=header[2].decode('ascii'),
            new_blob=header[3].decode('ascii')))
    return rows


def _blob_info(repo, oid, *, require_digest=True):
    digest, prefix = hashlib.sha256(), bytearray()
    stream = iter_git_bytes(repo, 'cat-file', 'blob', oid)
    try:
        for chunk in stream:
            if len(prefix) < 8000:
                prefix.extend(chunk[:8000-len(prefix)])
            if not require_digest and len(prefix) == 8000 and b'\0' not in prefix:
                # Text patches do not retain a blob digest. Never label this
                # prefix as a complete hash; binary transitions can request it later.
                return None, False
            digest.update(chunk)
    finally:
        stream.close()
    return digest.hexdigest(), b'\0' in prefix


def _patch(raw):
    output, inside = bytearray(), False
    for line in raw.split(b'\n')[:-1]:
        if line.startswith(b'@@ '):
            output.extend(b'@@\n')
            inside = True
        elif inside:
            if not line.startswith((b' ', b'+', b'-', b'\\')):
                raise ValueError('unexpected patch transport inside hunk')
            output.extend(line + b'\n')
    return bytes(output)


def _text_patch(repo, old_blob, new_blob, max_bytes):
    if old_blob is not None and new_blob is not None:
        return _patch(git_bytes(repo, 'diff', '--text', '--no-ext-diff', '--no-textconv',
            '--no-color', '--no-renames', '--full-index', '--no-indent-heuristic',
            '--diff-algorithm=myers', '--unified=3', '--inter-hunk-context=0',
            '--ignore-submodules=none', old_blob, new_blob, '--', max_output_bytes=max_bytes))
    # A whole-file addition/deletion has exactly one normalized hunk (or none
    # for an empty file). Avoid recursive pathspecs and writing an empty blob.
    content = git_bytes(repo, 'cat-file', 'blob', old_blob or new_blob,
                        max_output_bytes=max_bytes)
    if not content:
        return b''
    sign = b'-' if old_blob is not None else b'+'
    output = bytearray(b'@@\n')
    lines = content.split(b'\n')
    for number, line in enumerate(lines):
        if number == len(lines)-1 and not line:
            break
        output.extend(sign + line + b'\n')
        if number == len(lines)-1:
            output.extend(b'\\ No newline at end of file\n')
        if len(output) > max_bytes:
            raise ValueError('Git patch exceeds byte limit')
    return bytes(output)


def collect_effective_changes(repo, scope, *, target_head):
    require_scope(scope)
    if scope['mode'] not in ('mr', 'pr'):
        raise ValueError('effective change capture currently requires MR/PR scope')
    for commit in (scope['base'], scope['head'], target_head):
        if not isinstance(commit, str) or re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', commit) is None:
            raise ValueError('capture requires full pinned commits')
    fmt = 'sha1' if len(scope['head']) == 40 else 'sha256'
    value = dict(schema_version=1, algorithm=ALGORITHM,
        logical_scope_identity=logical_scope(scope)['identity'], complete=False, entries=[], diagnostics=[],
        comparison=dict(kind='merge-base-to-head', base=scope['base'], head=scope['head'],
            target_head=target_head, diff_base=scope['base'], object_format=fmt))
    scope_ready=False
    try:
        for commit in (scope['base'], scope['head'], target_head):
            git(repo, 'cat-file', '-e', commit+'^{commit}')
        bases = git(repo, 'merge-base', '--all', target_head, scope['head']).splitlines()
        if bases != [scope['base']]:
            raise ValueError('effective diff base is ambiguous or differs from the pinned scope')
        scope_ready=True
        rows = parse_raw(git_bytes(repo, 'diff', '--raw', '-z', '--no-abbrev', '--no-renames',
            '--no-ext-diff', '--no-textconv', '--ignore-submodules=none', scope['base'], scope['head'], '--',
            max_output_bytes=4*1024*1024))
        if len(rows) > MAX_ENTRIES:
            raise ValueError('effective changes exceed entry limit')
        patch_size, blobs = 0, {}
        def blob_info(oid, require_digest=False):
            if oid not in blobs or (require_digest and blobs[oid][0] is None):
                blobs[oid] = _blob_info(repo, oid, require_digest=require_digest)
            return blobs[oid]
        for row in rows:
            paths, hashes, binary = {}, {}, False
            modes = {row['old_mode'], row['new_mode']}
            for side in ('old', 'new'):
                exists = row[side+'_mode'] != '000000'
                paths[side+'_path_b64'] = _b64(row['path']) if exists else None
                paths[side+'_mode'] = row[side+'_mode'] if exists else None
                paths[side+'_blob'] = row[side+'_blob'] if exists else None
                if exists and '160000' not in modes:
                    digest, is_binary = blob_info(row[side+'_blob'], require_digest='120000' in modes)
                    hashes[side+'_sha256'] = digest
                    binary |= is_binary
                else:
                    hashes[side+'_sha256'] = None
            modes = {paths['old_mode'], paths['new_mode']}
            if '160000' in modes:
                kind = 'gitlink'
                payload = {side+'_commit': paths[side+'_blob'] for side in ('old','new')}
            elif '120000' in modes or binary:
                for side in ('old', 'new'):
                    if paths[side+'_blob'] is not None:
                        hashes[side+'_sha256'] = blob_info(paths[side+'_blob'], require_digest=True)[0]
                kind, payload = ('symlink' if '120000' in modes else 'binary'), hashes
            else:
                kind = 'text'
                patch = _text_patch(repo, paths['old_blob'], paths['new_blob'], MAX_PATCH_BYTES-patch_size)
                patch_size += len(patch)
                payload = {'patch_b64': _b64(patch)}
            value['entries'].append(dict(**paths, kind=kind, payload=payload))
        value['entries'].sort(key=lambda r: (decode_path(r['old_path_b64']) if r['old_path_b64'] else b'',
                                             decode_path(r['new_path_b64']) if r['new_path_b64'] else b''))
        value['complete'] = True
    except (OSError, ValueError, UnicodeError) as exc:
        value.update(complete=False, entries=[], diagnostics=[dict(
            code='capture_incomplete' if scope_ready else 'current_scope_unknown', detail=str(exc)[:2000])])
    value['changes_sha256'] = change_digest(value)
    try:
        return normalize_effective_changes(value)
    except ValueError:
        value.update(complete=False, entries=[], diagnostics=[dict(code='capture_incomplete', detail='Descriptor limit or shape was invalid.')])
        value['changes_sha256'] = change_digest(value)
        return normalize_effective_changes(value)


def collect_context_files(repo, comparison, files):
    if len(files) > MAX_ENTRIES:
        raise ValueError('context inventory exceeds entry limit')
    trees, digests, result = {}, {}, []
    for row in files:
        side, path = row['side'], decode_path(row['path_b64'])
        if side not in ('base', 'head'):
            raise ValueError('invalid context side')
        if side not in trees:
            raw = git_bytes(repo, 'ls-tree', '-r', '-z', comparison['diff_base' if side == 'base' else 'head'],
                            max_output_bytes=32*1024*1024)
            entries = {}
            for line in raw.split(b'\0'):
                if line:
                    metadata, name = line.split(b'\t', 1)
                    mode, kind, oid = metadata.split(b' ')
                    entries[name] = (mode.decode('ascii'), oid.decode('ascii'))
            trees[side] = entries
        if path not in trees[side]:
            raise ValueError('inspected context path is absent from the pinned tree')
        mode, oid = trees[side][path]
        if mode == '160000':
            digest = hashlib.sha256(oid.encode()).hexdigest()
        else:
            if oid not in digests:
                digests[oid] = _blob_info(repo, oid)[0]
            digest = digests[oid]
        result.append(dict(side=side, path_b64=row['path_b64'], mode=mode, content_sha256=digest))
    return sorted(result, key=lambda row: (row['side'], decode_path(row['path_b64'])))
