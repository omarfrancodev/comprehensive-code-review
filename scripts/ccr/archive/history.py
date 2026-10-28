"""Verify and port historical reviews as three-file consultation packages."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re

from ccr.archive import layout as review_layout
from ccr.archive import reader as archive_reader
from ccr.contracts import review as review_contract
from ccr.shared.json_io import read_bounded
from ccr.shared.paths import safe_path

METADATA_LIMIT = 1024 * 1024
CONTENT_LIMIT = 8 * 1024 * 1024
HISTORY_FILES = {'informe.md', 'consulta.json', '.ccr-history.json'}
HEX = re.compile(r'[0-9a-f]{64}')


class HistoryError(ValueError):
    pass

def _hash(data):
    return hashlib.sha256(data).hexdigest()

def _json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n').encode('utf-8')

def _decode_json(data, label):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise HistoryError(f'{label} contains a duplicate JSON key')
            value[key] = item
        return value
    try:
        return json.loads(data.decode('utf-8'), object_pairs_hook=unique)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HistoryError(f'{label} is not valid UTF-8 JSON') from exc

def _read(path, limit, label):
    target = safe_path(path)
    try:
        info = target.stat()
        if not target.is_file() or info.st_size > limit:
            raise HistoryError(f'{label} is missing, not a regular file, or exceeds its size limit')
        data = read_bounded(target, limit)
    except (OSError, ValueError) as exc:
        raise HistoryError(f'{label} cannot be read safely: {exc}') from exc
    if len(data) > limit:
        raise HistoryError(f'{label} exceeds its size limit')
    return data

def _source_snapshot(run):
    run = safe_path(run)
    manifest_bytes = _read(run / 'cierre.json', METADATA_LIMIT, 'source manifest')
    marker_bytes = _read(run / archive_reader.MARKER, METADATA_LIMIT, 'ownership marker')
    review_bytes = _read(run / 'review.json', CONTENT_LIMIT, 'retained review')
    report_bytes = _read(run / 'informe.md', CONTENT_LIMIT, 'retained report')
    manifest = _decode_json(manifest_bytes, 'source manifest')
    marker = _decode_json(marker_bytes, 'ownership marker')
    record = _decode_json(review_bytes, 'retained review')
    if not isinstance(manifest, dict) or not isinstance(marker, dict) or not isinstance(record, dict):
        raise HistoryError('source metadata and retained review must be JSON objects')
    if manifest.get('schema_version') not in range(1, 8):
        raise HistoryError('source archive schema is unsupported for historical consultation')
    if manifest.get('retained') is not True or manifest.get('state') not in {'closing', 'complete'}:
        raise HistoryError('source has no stable retained final result')
    if not isinstance(manifest.get('scope'), dict) or record.get('scope') != manifest['scope']:
        raise HistoryError('retained review scope differs from its source manifest')
    errors = review_contract.validate(record)
    if errors or record.get('stage') != 'final':
        raise HistoryError('retained review contract is invalid: ' + '; '.join(errors[:8]))
    run_id = manifest.get('run_id')
    if run_id is not None and (not isinstance(run_id, str) or not re.fullmatch(r'[0-9a-f]{20}', run_id)):
        raise HistoryError('source run identity is malformed')
    if run_id and record.get('schema_version') in (6, 7, 8, 9, 10, 11, 12) and record.get('review_id') != 'CR-' + run_id:
        raise HistoryError('retained review ID differs from source run identity')
    hashes = manifest.get('hashes')
    if (not isinstance(hashes, dict) or hashes.get('review.json') != _hash(review_bytes)
            or hashes.get('informe.md') != _hash(report_bytes)):
        raise HistoryError('retained review or report hash differs from the source manifest')
    required_marker = {'run_dir': str(run), 'owner_id': manifest.get('owner_id'),
                       'archive_root': manifest.get('archive_root'),
                       'repository_key': manifest.get('repository_key'),
                       'scope_sha256': _hash(_json_bytes(manifest['scope']))}
    if any(marker.get(key) != value for key, value in required_marker.items()):
        raise HistoryError('ownership marker does not bind the source path and scope')
    if _hash(manifest_bytes) not in {marker.get('manifest_sha256'), marker.get('previous_manifest_sha256')}:
        raise HistoryError('ownership marker does not bind the source manifest bytes')
    root = safe_path(manifest['archive_root'])
    if root not in run.parents:
        raise HistoryError('source run escapes its declared archive root')
    repository_key = manifest.get('repository_key')
    identity = manifest.get('repository_identity')
    if (not isinstance(identity, str) or not isinstance(repository_key, str)
            or _hash(identity.encode('utf-8'))[:20] != repository_key):
        raise HistoryError('source repository identity is incomplete or contradictory')
    repo_group = archive_reader._repository_group(identity)
    if len(run.relative_to(root).parts) != 3 or run.relative_to(root).parts[0] != repo_group:
        raise HistoryError('source repository folder differs from its stable repository identity')
    pending = ('pending_trace', 'checkpoint_transaction', 'resource_transfer', 'resource_cleanup_intent',
               'active_restart', 'pending_restart', 'pending_hashes', 'planned_hashes')
    restart_operation = manifest.get('restart_operation')
    restart_pending = isinstance(restart_operation, dict) and restart_operation.get('status') == 'pending'
    cleanup_intent = manifest.get('resource_cleanup')
    cleanup_pending = isinstance(cleanup_intent, dict) and cleanup_intent.get('status') == 'pending'
    transfers = manifest.get('resource_transfers', [])
    transfer_pending = (not isinstance(transfers, list) or any(
        not isinstance(row, dict) or row.get('status') != 'complete' for row in transfers))
    if (any(manifest.get(field) for field in pending) or restart_pending or transfer_pending or cleanup_pending
            or 'previous_manifest_sha256' in marker):
        raise HistoryError('source has a pending transaction and cannot be ported')
    cleanup = manifest.get('cleanup')
    if cleanup not in {'complete', 'not_needed', 'pending'}:
        cleanup = None
    return {'run': run, 'manifest_bytes': manifest_bytes, 'marker_bytes': marker_bytes,
            'review_bytes': review_bytes, 'report_bytes': report_bytes, 'manifest': manifest,
            'record': record, 'cleanup': cleanup}

def inspect_source(source_run: Path) -> dict:
    try:
        source = _source_snapshot(source_run)
    except (OSError, TypeError, KeyError, ValueError) as exc:
        return {'status': 'invalid', 'source_run': str(source_run), 'reason': str(exc)[:1000],
                'actions': ['preserve']}
    manifest, record = source['manifest'], source['record']
    return {'status': 'portable', 'source_run': str(source['run']),
            'archive_schema': manifest['schema_version'], 'review_schema': record['schema_version'],
            'review_id': record.get('review_id'), 'scope': manifest['scope'],
            'verdict': record.get('verdict'), 'source_created_at': manifest.get('created_at'),
            'cleanup': source['cleanup'], 'actions': ['port_history', 'new_review', 'preserve']}

def _scope_hint(scope):
    try:
        logical = review_layout.logical_scope(scope)
        group = review_layout.scope_group(logical)
    except (ValueError, TypeError):
        hint = scope.get('reference') or scope.get('target') or scope.get('snapshot') or scope.get('head') or 'scope'
        group = archive_reader._slug(scope.get('mode', 'scope')) + '-' + archive_reader._slug(hint)
    safe = re.sub(r'[^A-Za-z0-9_-]+', '-', str(group)).strip('-_')[:64].rstrip('-_')
    if not safe or re.fullmatch(r'(?i)(CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])', safe):
        safe = 'scope-' + (safe or 'unknown')[:58]
    return safe

def _created_hint(value):
    try:
        moment = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if moment.tzinfo is None:
            return None
        return moment.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    except (AttributeError, TypeError, ValueError):
        return None

def _history_payload(source):
    manifest, record = source['manifest'], source['record']
    identity = manifest['repository_identity']
    source_id = hashlib.sha256((str(source['run']) + '\n' + _hash(source['manifest_bytes']) + '\n'
                                + _hash(source['review_bytes']) + '\n' + _hash(source['report_bytes'])).encode('utf-8')).hexdigest()
    port_id = 'HP-' + source_id[:20]
    hint = _scope_hint(manifest['scope']) + '--' + (_created_hint(manifest.get('created_at')) or 'undated') + '--' + port_id
    history_root = Path(manifest['archive_root']) / '.historical'
    destination = history_root / archive_reader._repository_group(identity) / hint
    consultation = {'historical_schema': 1, 'port_id': port_id,
        'original_review_id': record.get('review_id'), 'scope': manifest['scope'],
        'presentation': copy_field(record.get('presentation')),
        'verdict': record.get('verdict'), 'verdict_reason': record.get('verdict_reason'),
        'source': {'run_dir': str(source['run']), 'archive_schema': manifest['schema_version'],
                   'review_schema': record['schema_version'], 'skill_version': manifest.get('skill_version'),
                   'repository_key': manifest['repository_key'], 'manifest_sha256': _hash(source['manifest_bytes']),
                   'review_sha256': _hash(source['review_bytes']), 'report_sha256': _hash(source['report_bytes']),
                   'created_at': manifest.get('created_at'), 'state': manifest.get('state'),
                   'disposition': (manifest.get('operation') or {}).get('disposition'),
                   'retained': manifest.get('retained'), 'cleanup': source['cleanup']},
        'limitations': ['Consulta histórica; no revalidada.',
                        'La evidencia y los enlaces originales pueden no estar disponibles.']}
    metadata = {'kind': 'historical_review', 'schema_version': 1, 'port_id': port_id,
        'source_sha256': {'manifest': _hash(source['manifest_bytes']), 'review': _hash(source['review_bytes']),
                          'report': _hash(source['report_bytes'])},
        'files': {'informe.md': _hash(source['report_bytes']), 'consulta.json': _hash(_json_bytes(consultation))},
        'inventory': sorted(HISTORY_FILES)}
    return port_id, destination, consultation, metadata

def copy_field(value):
    # JSON round-trip avoids retaining references to caller-owned nested values.
    return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False)) if value is not None else None

def verify_history(history_dir: Path) -> dict:
    directory = safe_path(history_dir)
    if not directory.is_dir():
        raise HistoryError('historical consultation package is not a directory')
    files = {path.name for path in directory.iterdir() if path.is_file()}
    if files != HISTORY_FILES or any(path.is_dir() for path in directory.iterdir()):
        raise HistoryError('historical consultation package inventory must contain exactly three files')
    metadata_bytes = _read(directory / '.ccr-history.json', METADATA_LIMIT, 'historical package metadata')
    consultation_bytes = _read(directory / 'consulta.json', METADATA_LIMIT, 'historical consultation record')
    report_bytes = _read(directory / 'informe.md', CONTENT_LIMIT, 'historical report')
    metadata = _decode_json(metadata_bytes, 'historical package metadata')
    consultation = _decode_json(consultation_bytes, 'historical consultation record')
    if (not isinstance(metadata, dict) or metadata.get('kind') != 'historical_review'
            or metadata.get('schema_version') != 1 or metadata.get('inventory') != sorted(HISTORY_FILES)):
        raise HistoryError('historical package metadata is invalid')
    if (not isinstance(consultation, dict) or consultation.get('historical_schema') != 1
            or consultation.get('port_id') != metadata.get('port_id')):
        raise HistoryError('historical consultation record is invalid')
    hashes = metadata.get('files')
    if (not isinstance(hashes, dict) or hashes != {'informe.md': _hash(report_bytes),
                                                   'consulta.json': _hash(consultation_bytes)}):
        raise HistoryError('historical package content was modified')
    for key in ('manifest', 'review', 'report'):
        if not HEX.fullmatch(str(metadata.get('source_sha256', {}).get(key, ''))):
            raise HistoryError('historical source provenance is malformed')
    return {'status': 'verified_package', 'history_dir': str(directory), 'port_id': metadata['port_id'],
            'consultation': consultation, 'report_sha256': _hash(report_bytes)}

def port_review(source_run: Path, output_root: Path | None = None) -> dict:
    source = _source_snapshot(source_run)
    # Check all selected bytes again before publishing; a legacy writer may not cooperate with our locks.
    after = _source_snapshot(source['run'])
    for key in ('manifest_bytes', 'marker_bytes', 'review_bytes', 'report_bytes'):
        if source[key] != after[key]:
            raise HistoryError('source changed while it was being read; no historical package was published')
    port_id, default_destination, consultation, metadata = _history_payload(source)
    destination = default_destination
    if output_root is not None:
        root = safe_path(output_root)
        root.mkdir(parents=True, exist_ok=True)
        destination = root / '.historical' / default_destination.parent.name / default_destination.name
    destination = Path(destination)
    if destination.exists():
        verified = verify_history(destination)
        if verified['port_id'] != port_id:
            raise HistoryError('historical destination belongs to a different port operation')
        return {'status': 'existing', 'history_dir': str(destination), 'port_id': port_id}
    parent = safe_path(destination.parent)
    parent.mkdir(parents=True, exist_ok=True)
    stage = safe_path(parent / ('.staging-' + port_id))
    stage.mkdir(exist_ok=True)
    payloads = {'informe.md': source['report_bytes'], 'consulta.json': _json_bytes(consultation),
                '.ccr-history.json': _json_bytes(metadata)}
    for name, data in payloads.items():
        path = safe_path(stage / name)
        if path.exists():
            if _read(path, CONTENT_LIMIT, 'historical staging file') != data:
                raise HistoryError('historical staging directory contains changed bytes')
        else:
            with path.open('xb') as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
    verify_history(stage)
    try:
        os.rename(stage, destination)
        status = 'created'
    except FileExistsError:
        verified = verify_history(destination)
        if verified['port_id'] != port_id:
            raise HistoryError('historical destination collision; existing bytes were preserved')
        status = 'existing'
    verify_history(destination)
    return {'status': status, 'history_dir': str(destination), 'port_id': port_id}

def show_history(history_dir: Path) -> str:
    value = verify_history(history_dir)
    report_bytes = _read(Path(value['history_dir']) / 'informe.md', CONTENT_LIMIT, 'historical report')
    if _hash(report_bytes) != value['report_sha256']:
        raise HistoryError('historical report changed after package verification')
    report = report_bytes.decode('utf-8')
    return ('AVISO: consulta histórica; no revalidada. La evidencia y los enlaces originales pueden no estar disponibles.\n\n'
            + report)
