"""Preparation of proportional review records with pinned logical identities."""
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import sys

from ccr.archive import layout
from ccr.archive.reader import _repository_group
from ccr.contracts.scope import require_scope
from ccr.contracts.references import parse_reference, resolve_reference
from ccr.contracts.reference_index import canonical_reference
from ccr.contracts.execution import validate_execution_sources
from ccr.contracts.provenance import validate_check_sources
from ccr.contracts.review import validate as validate_review
from ccr.contracts.semantic_references import validate_semantic_references
from ccr.shared.encoding import archive_bytes, compact_bytes
from ccr.shared.json_io import atomic_write, read_bounded, read_json
from ccr.shared.paths import safe_path
from ccr.workflow.inputs import normalize_inputs

RECORD_BYTES_LIMIT = 16 * 1024 * 1024
CONTENT_BYTES_LIMIT = 80 * 1024 * 1024
METADATA_BYTES_LIMIT = 1024 * 1024
EVIDENCE_BYTES_LIMIT = 64 * 1024 * 1024


def _validate_content_sizes(sizes):
    """Apply the same serialized-output limits before publishing and reading."""
    if not {'review.json', 'informe.md'}.issubset(sizes) or len(sizes) > 66:
        raise ValueError('compact file inventory is invalid')
    if sizes['review.json'] > RECORD_BYTES_LIMIT:
        raise ValueError('compact record exceeds size limit')
    if sum(sizes.values()) > CONTENT_BYTES_LIMIT:
        raise ValueError('compact content exceeds aggregate size limit')
    if sum(size for name, size in sizes.items() if name.startswith('evidence/')) > EVIDENCE_BYTES_LIMIT:
        raise ValueError('compact evidence exceeds size limit')


def _digest(value):
    return hashlib.sha256(compact_bytes(value)).hexdigest()


def _decode_json(data):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate JSON key: ' + key)
            result[key] = value
        return result
    def invalid(value):
        raise ValueError('nonfinite JSON number: ' + value)
    return json.loads(data.decode('utf-8'), object_pairs_hook=unique, parse_constant=invalid)


def _validate_prepared(prepared):
    fields = {'schema_version', 'request', 'logical_scope', 'created_at', 'run_id', 'review_id', 'run_dir', 'staging_dir'}
    if not isinstance(prepared, dict) or set(prepared) != fields or prepared['schema_version'] != 1:
        raise ValueError('invalid compact preparation fields')
    request = prepared['request']
    required = {'repository_identity', 'scope', 'logical_scope_input', 'review_inputs',
                'selection', 'operation_id', 'archive_root', 'profile_input', 'profile_selection', 'producer'}
    if not isinstance(request, dict) or set(request) != required:
        raise ValueError('invalid compact preparation request')
    scope = request['scope']
    require_scope(scope)
    logical = layout.logical_scope(scope, request['logical_scope_input'])
    inputs = normalize_inputs(request['review_inputs'])
    selection = request['selection']
    from ccr.workflow.builders import initial_selection
    from ccr.execution.harness import validate_identity
    if initial_selection(request['profile_input']) != request['profile_selection']:
        raise ValueError('compact initial profile selection changed')
    producer = request['producer']
    if (not isinstance(producer, dict) or not isinstance(producer.get('skill_version'), str)
            or not producer['skill_version'].strip() or not isinstance(producer.get('harness'), str)
            or not producer['harness'].strip()):
        raise ValueError('compact producer identity is required')
    validate_identity(producer)
    operation_id = request['operation_id']
    if (inputs['scope'] != scope or inputs.get('logical_scope_identity') != logical['identity']
            or not isinstance(selection, dict) or set(selection) != {'mode', 'reason'}
            or selection.get('mode') != 'compact' or not isinstance(selection.get('reason'), str)
            or not selection['reason'].strip() or not isinstance(operation_id, str)
            or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', operation_id)):
        raise ValueError('compact preparation has inconsistent inputs or selection')
    root = safe_path(request['archive_root'])
    group = safe_path(root / _repository_group(request['repository_identity']) / layout.scope_group(logical))
    operation_hash = _digest({'operation_id': operation_id, 'logical_scope': logical['identity'],
                              'repository_identity': request['repository_identity']})
    stage = safe_path(group / ('.compact-' + operation_hash[:32]))
    run = safe_path(group / layout.run_name(scope, prepared['created_at'], prepared['run_id'],
                                            request['logical_scope_input']))
    if (logical != prepared['logical_scope'] or prepared['review_id'] != 'CR-' + prepared['run_id']
            or stage != safe_path(prepared['staging_dir']) or run != safe_path(prepared['run_dir'])):
        raise ValueError('compact preparation escaped or changed its pinned identity')
    return stage, run


def _read_prepared(stage):
    raw = read_bounded(stage / 'prepared.json', 1024 * 1024)
    marker = read_json(stage / '.reservation.json', max_bytes=1024 * 1024)
    if (not isinstance(marker, dict) or set(marker) != {'schema_version', 'prepared_sha256'}
            or marker['schema_version'] != 1
            or marker['prepared_sha256'] != hashlib.sha256(raw).hexdigest()):
        raise ValueError('compact reservation identity changed or is incomplete')
    return _decode_json(raw)


def prepare_compact(root, repository_identity, scope, logical_scope_input, review_inputs, selection, operation_id,
                    *, profile_input, skill_version, harness, harness_id=None, harness_source=None):
    """Reserve a compact run before discovery, replaying only an identical request."""
    root = safe_path(root)
    require_scope(scope)
    logical = layout.logical_scope(scope, logical_scope_input)
    inputs = normalize_inputs(review_inputs)
    if inputs['scope'] != scope:
        raise ValueError('review inputs differ from the pinned scope')
    if 'logical_scope_identity' in inputs and inputs['logical_scope_identity'] != logical['identity']:
        raise ValueError('review inputs differ from the logical scope identity')
    inputs['logical_scope_identity'] = logical['identity']
    if (not isinstance(selection, dict) or set(selection) != {'mode', 'reason'}
            or selection['mode'] != 'compact' or not isinstance(selection['reason'], str)
            or not selection['reason'].strip()):
        raise ValueError('compact selection requires mode and observed reason')
    if not isinstance(operation_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', operation_id):
        raise ValueError('operation ID must be a bounded literal identifier')
    repository_group = _repository_group(repository_identity)
    from ccr.workflow.builders import initial_selection
    from ccr.execution.harness import resolve
    if not isinstance(profile_input, dict):
        raise ValueError('compact initial profile must be a captured JSON object')
    profile = initial_selection(profile_input)
    if inputs.get('profile') is not None and inputs['profile'] != profile['profile']:
        raise ValueError('compact inputs differ from the initial profile')
    if not isinstance(skill_version, str) or not skill_version.strip():
        raise ValueError('compact skill version is required')
    producer = {'skill_version': skill_version, 'harness': harness,
                **resolve(harness, harness_id, harness_source)}
    group = safe_path(root / repository_group / layout.scope_group(logical))
    request = {'repository_identity': repository_identity, 'scope': copy.deepcopy(scope),
               'logical_scope_input': copy.deepcopy(logical_scope_input), 'review_inputs': inputs,
               'selection': copy.deepcopy(selection), 'operation_id': operation_id,
               'archive_root': str(root), 'profile_input': copy.deepcopy(profile_input),
               'profile_selection': profile, 'producer': producer}
    operation_hash = _digest({'operation_id': operation_id, 'logical_scope': logical['identity'],
                              'repository_identity': repository_identity})
    stage = safe_path(group / ('.compact-' + operation_hash[:32]))
    group.mkdir(parents=True, exist_ok=True)
    def existing_reservation():
        path = safe_path(stage / 'prepared.json')
        if not path.is_file():
            raise ValueError('compact reservation is incomplete; preserve it for inspection')
        try:
            prepared = _read_prepared(stage)
        except (OSError, UnicodeError, ValueError) as exc:
            raise ValueError('compact reservation is invalid; preserve it for inspection') from exc
        if not isinstance(prepared, dict) or prepared.get('request') != request:
            raise ValueError('compact operation already exists with different pinned inputs')
        _validate_prepared(prepared)
        return prepared
    if stage.exists():
        return existing_reservation()
    created_at = datetime.now(timezone.utc).isoformat()
    run_id = secrets.token_hex(10)
    run = safe_path(group / layout.run_name(scope, created_at, run_id, logical_scope_input))
    prepared = {'schema_version': 1, 'request': request, 'logical_scope': logical,
                'created_at': created_at, 'run_id': run_id, 'review_id': 'CR-' + run_id,
                'run_dir': str(run), 'staging_dir': str(stage)}
    temporary = safe_path(group / ('.compact-build-' + operation_hash[:16] + '-' + secrets.token_hex(8)))
    temporary.mkdir()
    target = safe_path(temporary / 'prepared.json')
    prepared_bytes = archive_bytes(prepared)
    with target.open('xb') as stream:
        stream.write(prepared_bytes)
        stream.flush()
        os.fsync(stream.fileno())
    reservation = {'schema_version': 1, 'prepared_sha256': hashlib.sha256(prepared_bytes).hexdigest()}
    _write_exact(temporary / '.reservation.json', archive_bytes(reservation))
    try:
        _publish_no_replace(temporary, stage)
    except OSError:
        if stage.exists():
            winner = existing_reservation()
            if temporary.exists():
                _validate_payload_inventory(temporary, {'prepared.json', '.reservation.json'})
                if (_read_prepared(temporary) != prepared
                        or read_bounded(temporary / 'prepared.json', 1024 * 1024) != prepared_bytes
                        or read_bounded(temporary / '.reservation.json', 1024 * 1024) != archive_bytes(reservation)):
                    raise ValueError('losing compact build changed; preserve it for inspection')
                (temporary / 'prepared.json').unlink()
                (temporary / '.reservation.json').unlink()
                temporary.rmdir()
            return winner
        raise
    return prepared


def _source_bytes(sources):
    if not isinstance(sources, dict) or len(sources) > 64:
        raise ValueError('compact sources must be a bounded selected byte map')
    result = {}
    total = 0
    for name, data in sources.items():
        path, fragment = parse_reference(name, field='compact source')
        if fragment is not None or not path.startswith('evidence/') or not isinstance(data, bytes):
            raise ValueError('compact source must be selected evidence bytes without fragments')
        total += len(data)
        if total > EVIDENCE_BYTES_LIMIT:
            raise ValueError('compact evidence exceeds 64 MiB')
        result[path] = data
    return result


def _validate_compact_record(record):
    if not isinstance(record, dict) or record.get('schema_version') != 13 or record.get('stage') != 'final':
        raise ValueError('compact result requires final schema 13')
    errors = validate_review(record)
    if errors:
        raise ValueError('invalid compact review: ' + '; '.join(errors))
    plan = record['coverage']['execution']['plan']
    active = [row for row in plan if row.get('superseded_by') is None]
    if (len([row for row in active if row['role'] == 'discovery']) != 1
            or any(row['independent'] for row in active)):
        raise ValueError('compact review requires one discovery and no independent assignment')
    if record['resources']['residuals'] or record['resources']['cleanup'] not in ('complete', 'not_needed'):
        raise ValueError('compact review has unobserved cleanup or residual resources')


def _compact_identity(request, logical_scope, created_at):
    return {'inputs_sha256': _digest(request['review_inputs']),
            'logical_scope_identity': logical_scope['identity'], 'created_at': created_at}


def bind_compact_record(prepared, record):
    """Return the reservation-bound final before hashing any dependent sidecar."""
    stage, _ = _validate_prepared(prepared)
    if _read_prepared(stage) != prepared:
        raise ValueError('compact preparation differs from the pinned reservation')
    record = copy.deepcopy(record)
    identity = _compact_identity(prepared['request'], prepared['logical_scope'], prepared['created_at'])
    if 'compact_identity' in record and record['compact_identity'] != identity:
        raise ValueError('compact result identity differs from its preparation')
    record['compact_identity'] = identity
    _validate_compact_record(record)
    if record.get('scope') != prepared['request']['scope'] or record.get('review_id') != prepared['review_id']:
        raise ValueError('compact result differs from its pinned scope or identity')
    return record


def _validate_compact_sources(record, request, selected):
    """Verify selected observed milestones; never synthesize execution history."""
    try:
        context = _decode_json(selected['evidence/context.json'])
        events = _decode_json(selected['evidence/compact-execution.json'])
    except (KeyError, UnicodeError, ValueError) as exc:
        raise ValueError('compact review requires selected observed execution sources') from exc
    if not isinstance(context, dict) or normalize_inputs(context.get('review_inputs')) != request['review_inputs']:
        raise ValueError('compact context differs from initially pinned inputs')
    inputs = request['review_inputs']
    if ('description_identity' in inputs
            and record['description'].get('identity') != inputs['description_identity']):
        raise ValueError('compact description differs from its initially pinned identity')
    index = None
    index_ref = context.get('reference_index')
    if index_ref is not None:
        from ccr.contracts.material_inputs import validate_captured_material_sources, validate_material_inputs
        if index_ref != 'evidence/reference-index.json' or index_ref not in selected:
            raise ValueError('compact material reference index is unavailable')
        index = _decode_json(selected[index_ref])
        issues = (validate_captured_material_sources(inputs, index, selected)
                  + validate_material_inputs(record, context, index, selected))
        if issues:
            raise ValueError('compact material sources cannot be verified: ' + str(issues[0]))
    from ccr.workflow.builders import initial_selection
    from ccr.execution.harness import validate_identity
    producer = request['producer']
    validate_identity(producer)
    if initial_selection(request['profile_input']) != request['profile_selection']:
        raise ValueError('compact initial profile selection changed')
    if context.get('harness_id', producer['harness_id']) != producer['harness_id']:
        raise ValueError('compact context differs from the initial harness identity')
    if context.get('executors') != [] or any(
            row.get('execution', {}).get('kind') == 'local' for row in record.get('checks', [])):
        raise ValueError('writing or local executors require a full owned-resource archive')
    model_ref = context.get('model_usage_reference')
    if model_ref is not None:
        from ccr.contracts.model_usage import validate_model_usage, MAX_LEDGER_BYTES
        if model_ref != 'evidence/model-usage.json' or model_ref not in selected:
            raise ValueError('compact model observations require their selected ledger')
        if len(selected[model_ref]) > MAX_LEDGER_BYTES:
            raise ValueError('compact model usage exceeds 256 KiB')
        ledger = _decode_json(selected[model_ref])
        if validate_model_usage(ledger, review_id=record['review_id'], harness_id=producer['harness_id']):
            raise ValueError('compact model observations differ from review or harness identity')
    execution = record['coverage']['execution']
    if not execution['profile_history'] or execution['profile_history'][0] != request['profile_selection']:
        raise ValueError('compact initial profile differs from its pre-discovery selection')
    references = {row['reference'] for key in ('plan', 'results', 'profile_history') for row in execution[key]}
    references.update(row['source'] for row in execution['fallbacks'])
    for reference in references:
        try:
            resolved = resolve_reference(canonical_reference(reference, index.get('aliases', {}) if index else {}), selected, field='compact execution source')
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError('compact execution source is unavailable: ' + str(reference)) from exc
        for row in execution['profile_history']:
            if row['reference'] == reference and resolved != row['profile']:
                raise ValueError('compact profile source differs from the observed selection')
    errors = validate_execution_sources(record, context, events, references,
                                        assignment_registry=context.get('execution_plan'))
    errors.extend(validate_check_sources(record, context.get('executors'), receipt_sources=selected))
    if errors:
        raise ValueError('compact execution cannot be verified: ' + '; '.join(errors))
    if context.get('check_disclosure_reference') is not None:
        from ccr.reporting.check_disclosure import disclosure_view
        reference = context['check_disclosure_reference']
        if reference != 'evidence/check-disclosure.json' or reference not in selected:
            raise ValueError('compact check disclosure source is unavailable')
        disclosure = _decode_json(selected[reference])
        if disclosure['input_identity'] != context.get('check_disclosure_input_identity'):
            raise ValueError('compact disclosure input identity differs from context')
        disclosure_view(record, disclosure, selected)
    return index


def _write_exact(path, data):
    path = safe_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open('xb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError:
        import stat
        before = path.lstat()
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or getattr(before, 'st_file_attributes', 0) & 0x400:
            raise ValueError('compact staging file is not singly owned')
        with path.open('r+b') as stream:
            opened = os.fstat(stream.fileno())
            if not os.path.samestat(before, opened) or opened.st_nlink != 1:
                raise ValueError('compact staging file changed while opening')
            current = stream.read(len(data) + 1)
            if not data.startswith(current):
                raise ValueError('compact staging contains different bytes')
            if len(current) < len(data):
                stream.write(data[len(current):])
                stream.flush()
                os.fsync(stream.fileno())


def _publish_no_replace(source, target):
    """Atomically publish a directory without replacing a concurrent destination."""
    if os.name == 'nt':
        os.rename(source, target)
        return
    if sys.platform.startswith('linux'):
        import ctypes
        libc = ctypes.CDLL(None, use_errno=True)
        renameat2 = getattr(libc, 'renameat2', None)
        if renameat2 is None:
            raise ValueError('atomic no-replace directory publication unavailable')
        renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        renameat2.restype = ctypes.c_int
        if renameat2(-100, os.fsencode(source), -100, os.fsencode(target), 1) != 0:
            number = ctypes.get_errno()
            raise OSError(number, os.strerror(number))
        return
    raise ValueError('atomic no-replace directory publication unavailable on this host')


def _validate_payload_inventory(payload, names):
    import stat
    allowed_files = {Path(name).as_posix() for name in names}
    allowed_dirs = {parent.as_posix() for name in allowed_files
                    for parent in Path(name).parents if parent != Path('.')}
    pending = [payload]
    while pending:
        directory = pending.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                # DirEntry.stat reports st_nlink=0 on Windows; os.stat opens
                # the entry and obtains the actual link count.
                info = os.stat(entry.path, follow_symlinks=False)
                relative = Path(entry.path).relative_to(payload).as_posix()
                if getattr(info, 'st_file_attributes', 0) & 0x400 or stat.S_ISLNK(info.st_mode):
                    raise ValueError('compact payload contains a linked path')
                if stat.S_ISDIR(info.st_mode) and relative in allowed_dirs:
                    pending.append(Path(entry.path))
                elif not (stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and relative in allowed_files):
                    raise ValueError('compact payload contains unselected or unowned data')


def create_compact(prepared, record, report, current_inputs, sources):
    """Publish only an unchanged pinned result and explicitly selected evidence."""
    from ccr.execution.locks import run_locks
    stage, target = _validate_prepared(prepared)
    with run_locks([stage]):
        if (stage / 'promotion.json').exists():
            intent = read_json(stage / 'promotion.json')
            unsigned = dict(intent) if isinstance(intent, dict) else {}
            digest = unsigned.pop('intent_sha256', None)
            if (digest != _digest(unsigned) or unsigned.get('source_reservation') != str(stage)
                    or unsigned.get('source_review_id') != prepared['review_id']
                    or unsigned.get('source_sha256') != _digest(prepared)
                    or not target.exists() or not isinstance(unsigned.get('request'), dict)
                    or unsigned['request'].get('source_manifest_sha256') != _digest(read_compact(target)['manifest'])):
                raise ValueError('compact attempt was promoted; preserve its reservation')
        return _create_compact_locked(prepared, record, report, current_inputs, sources)


def _create_compact_locked(prepared, record, report, current_inputs, sources):
    stage, target = _validate_prepared(prepared)
    record = bind_compact_record(prepared, record)
    request = prepared['request']
    current = normalize_inputs(current_inputs)
    current.setdefault('logical_scope_identity', prepared['logical_scope']['identity'])
    if current != request['review_inputs']:
        raise ValueError('compact current inputs differ from the pinned inputs')
    selected = _source_bytes(sources)
    index = _validate_compact_sources(record, request, selected)
    for reference, expected in request['review_inputs']['sources'].items():
        path, _ = parse_reference(canonical_reference(reference, index.get('aliases', {}) if index else {}), field='pinned source')
        if path not in selected or hashlib.sha256(selected[path]).hexdigest() != expected:
            raise ValueError('pinned compact source is missing or differs')
    issues = validate_semantic_references(record, [], index, selected)
    if issues:
        raise ValueError('compact selected evidence is incomplete: ' + str(issues[0]))
    from ccr.reporting.render import render
    canonical_report = _render_compact(record, request, selected)
    if not isinstance(report, str) or report not in (render(record), canonical_report):
        raise ValueError('compact report does not match the canonical result')
    files = {'review.json': archive_bytes(record), 'informe.md': canonical_report.encode('utf-8'), **selected}
    _validate_content_sizes({name: len(data) for name, data in files.items()})
    hashes = {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
    manifest = {'schema_version': 1, 'mode': 'compact', 'state': 'complete',
                'request': request, 'logical_scope': prepared['logical_scope'],
                'created_at': prepared['created_at'], 'run_id': prepared['run_id'],
                'review_id': prepared['review_id'], 'hashes': hashes}
    manifest_data = archive_bytes(manifest)
    marker = {'schema_version': 1, 'mode': 'compact', 'run_id': prepared['run_id'],
              'run_dir': prepared['run_dir'], 'manifest_sha256': hashlib.sha256(manifest_data).hexdigest()}
    files['manifest.json'] = manifest_data
    files['.review-ownership.json'] = archive_bytes(marker)
    if any(len(files[name]) > METADATA_BYTES_LIMIT for name in ('manifest.json', '.review-ownership.json')):
        raise ValueError('compact metadata exceeds size limit')
    if target.exists():
        retained = read_compact(target)
        if retained['manifest'] != manifest:
            raise ValueError('compact destination already contains different bytes')
        return {'review_id': prepared['review_id'], 'run_dir': str(target), 'hashes': hashes, 'mode': 'compact'}
    payload = safe_path(stage / 'payload')
    intent_path = safe_path(stage / 'payload-intent.json')
    intent = {'schema_version': 1, 'prepared_sha256': _digest(prepared), 'run_dir': str(target),
              'hashes': {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}}
    if intent_path.exists():
        if read_json(intent_path, max_bytes=1024 * 1024) != intent:
            raise ValueError('compact payload differs from its durable intent')
    else:
        if payload.exists():
            raise ValueError('preexisting compact payload has no durable ownership intent')
        atomic_write(intent_path, archive_bytes(intent))
    payload.mkdir(exist_ok=True)
    for name, data in files.items():
        _write_exact(payload / name, data)
    _validate_payload_inventory(payload, files)
    try:
        _publish_no_replace(payload, target)
    except OSError as exc:
        if target.exists() and read_compact(target)['manifest'] == manifest:
            pass
        else:
            raise ValueError('compact publication could not safely commit') from exc
    retained = read_compact(target)
    if retained['manifest'] != manifest:
        raise ValueError('published compact artifact differs from its reservation')
    return {'review_id': prepared['review_id'], 'run_dir': str(target), 'hashes': hashes, 'mode': 'compact'}


def read_compact(run_dir):
    """Validate a compact artifact without repairing or changing it."""
    run = safe_path(run_dir)
    marker = read_json(run / '.review-ownership.json', max_bytes=METADATA_BYTES_LIMIT)
    manifest_data = read_bounded(run / 'manifest.json', METADATA_BYTES_LIMIT)
    if (not isinstance(marker, dict)
            or set(marker) != {'schema_version', 'mode', 'run_id', 'run_dir', 'manifest_sha256'}
            or type(marker.get('schema_version')) is not int or marker['schema_version'] != 1
            or marker.get('mode') != 'compact'
            or marker.get('run_dir') != str(run)
            or marker.get('manifest_sha256') != hashlib.sha256(manifest_data).hexdigest()):
        raise ValueError('compact ownership or manifest hash differs')
    manifest = _decode_json(manifest_data)
    if (not isinstance(manifest, dict)
            or set(manifest) != {'schema_version', 'mode', 'state', 'request', 'logical_scope',
                                 'created_at', 'run_id', 'review_id', 'hashes'}
            or type(manifest.get('schema_version')) is not int or manifest['schema_version'] != 1
            or manifest.get('mode') != 'compact' or manifest.get('state') != 'complete'
            or marker.get('run_id') != manifest.get('run_id')):
        raise ValueError('compact manifest is incomplete or unsupported')
    request = manifest['request']
    logical = layout.logical_scope(request['scope'], request['logical_scope_input'])
    root = safe_path(request['archive_root'])
    expected = safe_path(root / _repository_group(request['repository_identity']) / layout.scope_group(logical)
                         / layout.run_name(request['scope'], manifest['created_at'], manifest['run_id'],
                                           request['logical_scope_input']))
    if run != expected or logical != manifest.get('logical_scope'):
        raise ValueError('compact layout or logical scope differs')
    hashes = manifest.get('hashes')
    if not isinstance(hashes, dict) or not {'review.json', 'informe.md'}.issubset(hashes) or len(hashes) > 66:
        raise ValueError('compact file inventory is invalid')
    for name in hashes:
        if name not in ('review.json', 'informe.md'):
            _source_bytes({name: b''})
    _validate_payload_inventory(run, set(hashes) | {'manifest.json', '.review-ownership.json'})
    _validate_content_sizes({name: safe_path(run / name).stat().st_size for name in hashes})
    content = {}
    total = 0
    for name, digest in hashes.items():
        path = safe_path(run / name)
        size = path.stat().st_size
        total += size
        if total > CONTENT_BYTES_LIMIT or not path.is_file() or not isinstance(digest, str):
            raise ValueError('compact file exceeds bounds or is not regular')
        data = read_bounded(path, CONTENT_BYTES_LIMIT - total + size)
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError('compact file hash differs')
        content[name] = data
    if len(content['review.json']) > RECORD_BYTES_LIMIT:
        raise ValueError('compact record exceeds size limit')
    record = _decode_json(content['review.json'])
    _validate_compact_record(record)
    if (record.get('scope') != request['scope'] or record.get('review_id') != manifest.get('review_id')
            or manifest['review_id'] != 'CR-' + manifest['run_id']
            or record.get('compact_identity') != _compact_identity(request, logical, manifest['created_at'])):
        raise ValueError('compact record identity or contract differs')
    normalized = normalize_inputs(request['review_inputs'])
    if normalized.get('scope') != request['scope'] or normalized.get('logical_scope_identity') != logical['identity']:
        raise ValueError('compact initial input identity differs from the pinned scope')
    selected = {name: data for name, data in content.items() if name.startswith('evidence/')}
    index = _validate_compact_sources(record, request, selected)
    if content['informe.md'] != _render_compact(record, request, selected).encode('utf-8'):
        raise ValueError('compact report does not match the canonical record')
    for reference, digest in request['review_inputs']['sources'].items():
        path, _ = parse_reference(canonical_reference(reference, index.get('aliases', {}) if index else {}), field='pinned source')
        if path not in selected or hashlib.sha256(selected[path]).hexdigest() != digest:
            raise ValueError('compact pinned source differs')
    if validate_semantic_references(record, [], index, selected):
        raise ValueError('compact references do not resolve to retained evidence')
    return {'manifest': manifest, 'record': record, 'sources': selected}


def _render_compact(record, request, selected):
    """Render the private report from verified retained observations."""
    from ccr.reporting.models import model_usage_context
    from ccr.reporting.render import render
    context = _decode_json(selected['evidence/context.json'])
    events = _decode_json(selected['evidence/compact-execution.json'])
    manifest = {'run_id': record['review_id'][3:], 'harness_id': request['producer']['harness_id']}
    models = model_usage_context(context, lambda name: selected[name], manifest, record=record, events=events)
    return render(record, model_usage_context=models)
