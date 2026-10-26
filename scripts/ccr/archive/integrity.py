"""Read-only archive file, checkpoint, transfer, and trace integrity checks."""
from datetime import datetime
import hashlib
from pathlib import Path, PurePosixPath
import re
import stat

from ccr.archive import trace as review_trace
from ccr.archive.intent_contracts import CHECKPOINT_HASH, normalize_transfer_history
from ccr.shared.json_io import read_bounded
from ccr.shared.paths import safe_path
from ccr.contracts import references as review_references
from ccr.workflow import profiles as review_profiles

FILES = ('review.json', 'informe.md')
OPTIONAL_FILES = ('measurements.json',)
TRACE_FILES = (review_trace.NAME, 'handoff.md')
TRACE_ARCHIVE_SCHEMAS = frozenset({4, 5, 6, 7, 8})
PENDING_CONTEXT_LIMIT = 131072
CHECKPOINT_EVIDENCE_COUNT_LIMIT = 64
CHECKPOINT_METADATA_LIMIT = 16 * 1024 * 1024
CHECKPOINT_EVIDENCE_LIMIT = 64 * 1024 * 1024


def _digest(data):
    return hashlib.sha256(data).hexdigest()

def _pending_file_name(name):
    if not isinstance(name, str):
        return False
    if name in {'pending/context.json', 'pending/review.json', 'pending/informe.md'}:
        return True
    return (isinstance(name, str) and name.startswith('pending/evidence/')
            and name.count('/') == 2 and name[17:] == _evidence_name(name[17:])
            and name[17:] not in {'.', '..'})

def _verify_pending(run, manifest, *, allow_transaction=False):
    if manifest.get('schema_version') != 8:
        if any(key in manifest for key in ('pending_hashes', 'checkpoint', 'checkpoint_transaction')):
            raise ValueError('legacy archive cannot contain provisional checkpoint metadata')
        return
    hashes = manifest.get('pending_hashes', {})
    if not isinstance(hashes, dict) or len(hashes) > CHECKPOINT_EVIDENCE_COUNT_LIMIT + 3 or any(not _pending_file_name(name)
                                           or not isinstance(value, str)
                                           or not CHECKPOINT_HASH.fullmatch(value)
                                           for name, value in hashes.items()):
        raise ValueError('invalid provisional checkpoint hash inventory')
    if len({name.casefold() for name in hashes}) != len(hashes):
        raise ValueError('provisional checkpoint contains case-insensitive destination collisions')
    checkpoint = manifest.get('checkpoint')
    transaction = manifest.get('checkpoint_transaction')
    accepted = {name: {digest} for name, digest in hashes.items()}
    may_be_missing = set()
    staging_paths = {}
    if transaction is not None:
        base_fields = {'input_signature', 'previous_hashes', 'planned_hashes', 'removed_hashes', 'checkpoint'}
        if not isinstance(transaction, dict) or set(transaction) not in (base_fields, base_fields | {'staging'}):
            raise ValueError('invalid checkpoint transaction intent')
        previous, planned, removed = (transaction['previous_hashes'], transaction['planned_hashes'],
                                       transaction['removed_hashes'])
        if previous != hashes or not isinstance(planned, dict) or any(
                not _pending_file_name(name) or not isinstance(value, str)
                or not CHECKPOINT_HASH.fullmatch(value) for name, value in planned.items()):
            raise ValueError('checkpoint transaction differs from its owned prior inventory')
        if len({name.casefold() for name in planned}) != len(planned):
            raise ValueError('checkpoint transaction contains case-insensitive destination collisions')
        if (not isinstance(removed, dict) or any(
                name not in {'pending/review.json', 'pending/informe.md'}
                or previous.get(name) != digest or name in planned
                or not isinstance(digest, str) or not CHECKPOINT_HASH.fullmatch(digest)
                for name, digest in removed.items())):
            raise ValueError('checkpoint transaction has an invalid owned removal intent')
        if not isinstance(transaction['input_signature'], str) or not CHECKPOINT_HASH.fullmatch(transaction['input_signature']):
            raise ValueError('invalid checkpoint input signature')
        if 'staging' in transaction:
            staging = transaction['staging']
            if not isinstance(staging, dict) or set(staging) - set(planned):
                raise ValueError('invalid checkpoint staging inventory')
            occupied = {name.casefold() for name in set(previous) | set(planned)}
            for destination, row in staging.items():
                if (not isinstance(row, dict) or set(row) != {'name', 'sha256'}
                        or not isinstance(row['name'], str) or not isinstance(row['sha256'], str)
                        or row['sha256'] != planned[destination]
                        or not CHECKPOINT_HASH.fullmatch(row['sha256'])):
                    raise ValueError('invalid checkpoint staging row')
                stage = PurePosixPath(row['name'])
                target = PurePosixPath(destination)
                if (str(stage) != row['name'] or stage.is_absolute() or '\\' in row['name']
                        or any(part in {'', '.', '..'} for part in stage.parts)
                        or stage.parent != target.parent or row['name'].casefold() in occupied):
                    raise ValueError('checkpoint staging path is not an owned sibling')
                if row['name'].casefold() in {item.casefold() for item in staging_paths.values()}:
                    raise ValueError('duplicate checkpoint staging path')
                staging_paths[destination] = row['name']
        accepted = {name: {digest} for name, digest in previous.items()}
        for name, digest in planned.items():
            accepted.setdefault(name, set()).add(digest)
            if name not in previous:
                may_be_missing.add(name)
        may_be_missing.update(removed)
        if not allow_transaction:
            if manifest.get('operation', {}).get('disposition') == 'superseded':
                raise ValueError('source review was superseded; inspect its recorded successor: '
                                 + str(manifest['operation']['successor']))
            raise ValueError('checkpoint transaction is pending; retry the checkpoint with its selected inputs')
        checkpoint = transaction['checkpoint']
    elif hashes and not isinstance(checkpoint, dict):
        raise ValueError('checkpoint hash inventory has no checkpoint record')

    if checkpoint is not None:
        if (not isinstance(checkpoint, dict) or set(checkpoint) != {
                'id', 'phase', 'recorded_at', 'input_signature', 'inventory', 'gate_errors'}
                or not isinstance(checkpoint['id'], str) or not re.fullmatch(r'K[0-9]{3,}', checkpoint['id'])
                or not isinstance(checkpoint['phase'], str)
                or checkpoint['phase'] not in review_profiles.PHASES - {'prepare'}
                or not isinstance(checkpoint['recorded_at'], str)
                or not isinstance(checkpoint['input_signature'], str)
                or not CHECKPOINT_HASH.fullmatch(checkpoint['input_signature'])
                or not isinstance(checkpoint['inventory'], list)
                or not isinstance(checkpoint['gate_errors'], list)):
            raise ValueError('invalid checkpoint metadata')
        try:
            recorded_at = datetime.fromisoformat(checkpoint['recorded_at'].replace('Z', '+00:00'))
            if recorded_at.utcoffset() is None:
                raise ValueError('timezone required')
        except (TypeError, ValueError) as exc:
            raise ValueError('invalid checkpoint recording time') from exc
        if len(checkpoint['inventory']) > CHECKPOINT_EVIDENCE_COUNT_LIMIT + 3:
            raise ValueError('checkpoint inventory exceeds its entry limit')
        inventory = {}
        for row in checkpoint['inventory']:
            if (not isinstance(row, dict) or set(row) != {'name', 'size', 'sha256'}
                    or not _pending_file_name(row['name']) or type(row['size']) is not int or row['size'] < 0
                    or not isinstance(row['sha256'], str) or not CHECKPOINT_HASH.fullmatch(row['sha256'])
                    or row['name'] in inventory or row['name'].casefold() in {key.casefold() for key in inventory}):
                raise ValueError('invalid checkpoint inventory row')
            inventory[row['name']] = row['sha256']
        inventory_hashes = transaction['planned_hashes'] if transaction is not None else hashes
        if inventory != inventory_hashes:
            raise ValueError('checkpoint inventory differs from provisional hashes')
        evidence_size = sum(row['size'] for row in checkpoint['inventory']
                            if row['name'].startswith('pending/evidence/'))
        metadata_size = sum(row['size'] for row in checkpoint['inventory']
                            if row['name'].lower().endswith(('.json', '.md')))
        context_row = next((row for row in checkpoint['inventory'] if row['name'] == 'pending/context.json'), None)
        if (evidence_size > CHECKPOINT_EVIDENCE_LIMIT or metadata_size > CHECKPOINT_METADATA_LIMIT
                or context_row is None or context_row['size'] > PENDING_CONTEXT_LIMIT):
            raise ValueError('checkpoint inventory exceeds its declared size bounds')
        if (len(checkpoint['gate_errors']) > 64 or any(not isinstance(item, str) or not item.strip()
                or len(item) > 2000 for item in checkpoint['gate_errors'])):
            raise ValueError('checkpoint gate diagnostics are invalid or unbounded')
    elif hashes or transaction is not None:
        raise ValueError('checkpoint metadata is incomplete')

    root = run / 'pending'
    if root.exists():
        if not root.is_dir() or root.is_symlink():
            raise ValueError('pending checkpoint root is not a regular directory')
        observed = set()
        for path in root.rglob('*'):
            safe_path(path)
            if path.is_dir():
                continue
            name = path.relative_to(run).as_posix()
            staging_owner = next((destination for destination, staged_name in staging_paths.items()
                                  if staged_name == name), None)
            if staging_owner is not None:
                info = path.lstat()
                if not stat.S_ISREG(info.st_mode) or info.st_size > (
                        CHECKPOINT_EVIDENCE_LIMIT if staging_owner.startswith('pending/evidence/')
                        else CHECKPOINT_METADATA_LIMIT):
                    raise ValueError('checkpoint staging is not a bounded regular file: ' + name)
                observed.add(name)
                continue
            if not _pending_file_name(name):
                raise ValueError('foreign file in pending checkpoint: ' + name)
            observed.add(name)
        if observed - set(accepted) - set(staging_paths.values()):
            raise ValueError('foreign pending checkpoint files are present')
    elif accepted and any(name not in may_be_missing for name in accepted):
        raise ValueError('pending checkpoint inventory is missing its directory')

    evidence_size_read = 0
    metadata_size_read = 0
    for name, allowed_digests in accepted.items():
        path = safe_path(run / name)
        try:
            if name.startswith('pending/evidence/'):
                limit = CHECKPOINT_EVIDENCE_LIMIT - evidence_size_read
            elif name == 'pending/context.json':
                limit = PENDING_CONTEXT_LIMIT
            else:
                limit = CHECKPOINT_METADATA_LIMIT - metadata_size_read
            data = read_bounded(path, limit)
        except FileNotFoundError:
            if name in may_be_missing:
                continue
            raise ValueError('pending checkpoint file is missing: ' + name)
        if _digest(data) not in allowed_digests:
            raise ValueError('modified pending checkpoint file: ' + name)
        if name.startswith('pending/evidence/'):
            evidence_size_read += len(data)
        else:
            metadata_size_read += len(data)
        if transaction is None:
            expected_size = next(row['size'] for row in checkpoint['inventory'] if row['name'] == name)
            if len(data) != expected_size:
                raise ValueError('pending checkpoint file size differs from its inventory: ' + name)
        elif name in transaction['planned_hashes'] and _digest(data) == transaction['planned_hashes'][name]:
            planned_size = next(row['size'] for row in checkpoint['inventory'] if row['name'] == name)
            if len(data) != planned_size:
                raise ValueError('pending checkpoint file size differs from its transaction: ' + name)

def _trace_recovery_plan(run, manifest):
    """Verify an owned pending append without changing any bytes."""
    pending = manifest.get('pending_trace')
    if manifest['schema_version'] not in TRACE_ARCHIVE_SCHEMAS or not isinstance(pending, dict):
        raise ValueError('invalid pending trace transition')
    path = safe_path(run / review_trace.NAME)
    try:
        current = path.read_bytes()
    except FileNotFoundError:
        if pending['previous_sha256'] is not None:
            raise ValueError('pending trace history is missing')
        current = b''
    if _digest(current) == pending['sha256']:
        planned = current
    elif (pending['previous_sha256'] is None and not current) or _digest(current) == pending['previous_sha256']:
        events = pending['events']
        if not isinstance(events, list) or not events or len(events) > 2:
            raise ValueError('invalid pending trace milestone group')
        planned = current + b''.join(review_trace.encoded(event) + b'\n' for event in events)
    else:
        raise ValueError('modified trace cannot be recovered')
    if _digest(planned) != pending['sha256']:
        raise ValueError('pending trace intent integrity mismatch')
    review_trace.verify(planned, pending['trace'], manifest['run_id'])
    return current, planned

def verify_files(run, manifest, required=False, *, allow_checkpoint_transaction=False,
                  allow_resource_transfer=False, allow_pending_trace=False):
    trace_plan = None
    if manifest.get('pending_trace') is not None:
        if not allow_pending_trace:
            raise ValueError('trace recording is pending; retry a helper mutation to recover the preserved event')
        trace_plan = _trace_recovery_plan(run, manifest)
    transfers = normalize_transfer_history(manifest)
    if any(row['status'] != 'complete' for row in transfers) and not allow_resource_transfer:
        pending = next(row for row in transfers if row['status'] != 'complete')
        operation = manifest.get('restart_operation')
        incoming_restart = (isinstance(operation, dict) and operation['source_run'] == pending['source_run']
                            and str(run) == pending['successor_run'])
        identity = ('restart operation ' + operation['operation_id']) if incoming_restart else ('transfer ' + pending['transfer_id'])
        detail = '; recover its source ' + pending['source_run'] + ' for ' + identity
        raise ValueError('resource transfer is pending' + detail)
    _verify_pending(run, manifest, allow_transaction=allow_checkpoint_transaction)
    hashes = manifest.get('hashes')
    if not isinstance(hashes, dict) or any(not _retained_name(name) for name in hashes):
        raise ValueError('invalid retained file manifest')
    planned = manifest.get('planned_hashes', {}) if manifest['state'] == 'retaining' else {}
    required_files = set(FILES) | (set(OPTIONAL_FILES) if manifest['schema_version'] == 1 else set())
    if manifest['schema_version'] in TRACE_ARCHIVE_SCHEMAS and review_trace.NAME not in hashes and trace_plan is None:
        raise ValueError('mandatory archive trace is missing from closure')
    if required and (not required_files.issubset(hashes) or manifest['state'] == 'retaining'):
        raise ValueError('retained evidence is absent or interrupted')
    if not isinstance(planned, dict) or any(not _retained_name(name) for name in planned):
        raise ValueError('invalid planned evidence paths')
    for name in set(FILES) | set(OPTIONAL_FILES) | (set(TRACE_FILES) if manifest['schema_version'] in TRACE_ARCHIVE_SCHEMAS else set()) | set(hashes) | set(planned):
        if name == review_trace.NAME and trace_plan is not None:
            continue  # Both possible byte states and the planned events were verified, without writing.
        path = safe_path(run / name)
        try:
            data = path.read_bytes()
        except FileNotFoundError:
            if (required and name in required_files | set(hashes)) or (name in hashes and manifest['state'] != 'retaining'):
                raise ValueError('retained evidence missing: ' + name)
            continue
        if _digest(data) not in {hashes.get(name), planned.get(name)}:
            raise ValueError('refusing to clobber modified archived file: ' + name)
    if manifest['schema_version'] in TRACE_ARCHIVE_SCHEMAS and trace_plan is None:
        review_trace.verify(safe_path(run / review_trace.NAME).read_bytes(), manifest.get('trace'), manifest['run_id'])

def _evidence_name(name):
    label = re.sub(r'[^a-zA-Z0-9._-]', '-', name).strip(' .')[:80] or 'evidence'
    if re.fullmatch(r'(?i)(CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])(?:\..*)?', label):
        label = 'evidence-' + label[:70]
    return label

def _retained_name(name):
    try:
        path, fragment = review_references.parse_reference(name, field='retained name')
    except ValueError:
        return False
    if fragment is not None:
        return False
    if path in FILES + OPTIONAL_FILES + TRACE_FILES:
        return True
    return (path.startswith('evidence/') and path.count('/') == 1
            and path[9:] == _evidence_name(path[9:]) and path[9:] not in {'.', '..'})
