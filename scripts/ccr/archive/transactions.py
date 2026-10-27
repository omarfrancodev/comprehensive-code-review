"""Atomic archive manifest transitions and pending trace recovery."""
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import stat

from ccr.archive import trace as review_trace
from ccr.archive.integrity import _trace_recovery_plan, TRACE_ARCHIVE_SCHEMAS
from ccr.shared.encoding import archive_bytes as _json_bytes
from ccr.shared.json_io import atomic_write
from ccr.shared.paths import safe_path

MARKER = '.review-ownership.json'


def _digest(data):
    return hashlib.sha256(data).hexdigest()

def _archive_write(run, manifest, name, data):
    reservation_id = manifest.get('restart_operation', {}).get('reservation_id')
    stage = (run / ('.' + name + '.' + reservation_id + '.tmp')
             if reservation_id and (run / '.review-restart-reservation.json').exists() else None)
    atomic_write(run / name, data, **({'staging_path': stage} if stage else {}))

def save_manifest(run, manifest, marker):
    manifest['updated_at'] = datetime.now(timezone.utc).isoformat()
    data = _json_bytes(manifest)
    # Authorize only this specific old/new transition before the manifest replace.
    # Either digest remains verifiable if the process stops between atomic writes.
    current = safe_path(run / 'cierre.json')
    try:
        old_digest = _digest(current.read_bytes())
    except FileNotFoundError:
        old_digest = None
    transition = dict(marker, manifest_sha256=_digest(data), previous_manifest_sha256=old_digest)
    _archive_write(run, manifest, MARKER, _json_bytes(transition))
    _archive_write(run, manifest, 'cierre.json', data)
    marker = dict(marker, manifest_sha256=_digest(data))
    marker.pop('previous_manifest_sha256', None)
    _archive_write(run, manifest, MARKER, _json_bytes(marker))
    return marker

def recover_trace(run, manifest, marker):
    """Finish only an owned, hash-bound pending append; never adopt unknown bytes."""
    pending = manifest.get('pending_trace')
    if pending is None:
        return marker
    current, planned = _trace_recovery_plan(run, manifest)
    if current != planned:
        _archive_write(run, manifest, review_trace.NAME, planned)
    manifest['trace'] = pending['trace']
    manifest['hashes'][review_trace.NAME] = pending['sha256']
    manifest.pop('pending_trace')
    return save_manifest(run, manifest, marker)

def _append_trace(run, manifest, marker, event, *, helper=True):
    return _append_trace_events(run, manifest, marker, [event], helper=helper)

def _append_trace_events(run, manifest, marker, events, *, helper=True):
    """Bind one mutation and its bounded milestones in one owned transition."""
    if manifest['schema_version'] not in TRACE_ARCHIVE_SCHEMAS:
        return save_manifest(run, manifest, marker)
    path = safe_path(run / review_trace.NAME)
    old_digest = manifest['hashes'].get(review_trace.NAME)
    current = path.read_bytes() if old_digest is not None else b''
    if old_digest is not None and _digest(current) != old_digest:
        raise ValueError('modified trace cannot be appended')
    data = current
    values = []
    context = dict(manifest)
    for event in events:
        data, descriptor, value = review_trace.append(data, context, event, helper=helper)
        context['trace'] = descriptor
        values.append(value)
    manifest['pending_trace'] = {'previous_sha256': old_digest, 'sha256': _digest(data),
                                 'trace': descriptor, 'events': values}
    marker = save_manifest(run, manifest, marker)
    return recover_trace(run, manifest, marker)

def _milestone(kind, summary, *, status='completed', evidence=None):
    return {'kind': kind, 'status': status, 'summary': summary, 'evidence': evidence or [],
            'occurred_at': datetime.now(timezone.utc).isoformat(),
            'provenance': {'kind': 'helper', 'source': 'review_artifacts:' + kind}}

# Compatibility names used by the legacy archive facade.
_recover_trace = recover_trace
_save_manifest = save_manifest
