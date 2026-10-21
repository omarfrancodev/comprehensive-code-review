"""Read and validate an owned archive without importing mutating services."""
from datetime import datetime
import hashlib
from pathlib import Path
import re

from ccr.archive import layout as review_layout
from ccr.archive.integrity import CHECKPOINT_HASH
from ccr.archive.intent_contracts import _validate_cleanup_metadata, _validate_terminal_abandonment
from ccr.contracts.scope import require_scope as _scope
from ccr.execution import harness as review_harness
from ccr.shared.encoding import archive_bytes as _json_bytes
from ccr.shared.json_io import read_json
from ccr.shared.paths import contains as _contains, safe_path
from ccr.workflow import inputs as review_inputs
from ccr.workflow import profiles as review_profiles

MARKER = '.review-ownership.json'
ARCHIVE_SCHEMA_VERSION = review_layout.ARCHIVE_SCHEMA_VERSION


def _digest(data):
    return hashlib.sha256(data).hexdigest()

def _slug(value):
    label = re.sub(r'[^a-zA-Z0-9_-]+', '-', str(value)).strip('-_')[:36] or 'review'
    if re.fullmatch(r'(?i)(CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])', label):
        label = 'review-' + label
    return label

def _repository_group(identity):
    if (not isinstance(identity, str) or not identity.startswith(('origin:', 'common-dir:'))
            or not identity.split(':', 1)[1]):
        raise ValueError('invalid layout repository identity')
    identity_path = identity.split(':', 1)[1].replace('\\', '/')
    label = Path(identity_path).parent.name if identity_path.endswith('/.git') else identity_path.rsplit('/', 1)[-1]
    return _slug(label) + '-' + _digest(identity.encode('utf-8'))[:20]

def _scope_group(scope, logical_scope_input=None):
    return review_layout.scope_group(review_layout.logical_scope(scope, logical_scope_input))

def _validate_layout(run, manifest):
    """Bind location to durable identities; never need the original checkout."""
    review_layout.validate_layout(run, manifest)
    root = safe_path(manifest['archive_root'])
    parts = run.relative_to(root).parts
    key = manifest.get('repository_key')
    if len(parts) != 3 or not isinstance(key, str) or not re.fullmatch(r'[0-9a-f]{20}', key):
        raise ValueError('invalid archive layout: expected repository/scope/run below root')
    repository, scope, name = parts
    label, separator, suffix = repository.rpartition('-')
    # Historical _slug strips before truncating, so a generated label may end
    # in '-' or '_'. Validate its shape without applying a second normalization.
    if not separator or suffix != key or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,35}', label):
        raise ValueError('invalid archive layout: repository name must include its stable ID')
    if scope != _scope_group(manifest['scope'], manifest.get('logical_scope_input')):
        raise ValueError('invalid archive layout: scope directory differs from pinned scope')
    if manifest['schema_version'] >= 3:
        if repository != _repository_group(manifest.get('repository_identity')):
            raise ValueError('invalid archive layout: repository identity differs from directory')
        run_id = manifest.get('run_id')
        if not isinstance(run_id, str) or not re.fullmatch(r'[0-9a-f]{20}', run_id):
            raise ValueError('invalid archive layout: unique run ID is missing')
        try:
            created = datetime.fromisoformat(manifest['created_at'])
            if created.utcoffset() is None:
                raise ValueError('timestamp needs timezone')
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError('invalid archive layout: creation timestamp is missing or invalid') from exc
        expected = review_layout.run_name(manifest['scope'], manifest['created_at'], run_id,
                                          manifest.get('logical_scope_input'))
        if name != expected:
            raise ValueError('invalid archive layout: run directory differs from stored identity')

def load_run(run_dir):
    run = safe_path(run_dir)
    try:
        marker = read_json(run / MARKER)
        manifest = read_json(run / 'cierre.json')
    except FileNotFoundError as exc:
        raise ValueError('foreign or incomplete archive: ownership manifest is missing') from exc
    if not isinstance(marker, dict) or not isinstance(manifest, dict):
        raise ValueError('invalid ownership manifest')
    if (marker.get('run_dir') != str(run) or marker.get('owner_id') != manifest.get('owner_id')
            or marker.get('scope_sha256') != _digest(_json_bytes(manifest.get('scope')))
            or marker.get('repository_key') != manifest.get('repository_key')
            or marker.get('archive_root') != manifest.get('archive_root')
            or _digest((run / 'cierre.json').read_bytes()) not in
            {marker.get('manifest_sha256'), marker.get('previous_manifest_sha256')}):
        raise ValueError('foreign run or modified ownership/scope manifest')
    root = safe_path(marker['archive_root'])
    if not _contains(root, run) or run == root:
        raise ValueError('run escaped its registered archive root')
    _scope(manifest.get('scope'))
    if manifest.get('schema_version') != ARCHIVE_SCHEMA_VERSION or manifest.get('layout_version') != review_layout.LAYOUT_VERSION:
        raise ValueError('unsupported_layout: this archive predates native archive schema 8/layout 2; preserve it or port a verified report for consultation')
    if marker.get('logical_scope_sha256') != _digest(_json_bytes(manifest.get('logical_scope'))):
        raise ValueError('foreign run or modified logical scope binding')
    if manifest['schema_version'] in (6, 7, 8):
        review_harness.validate_identity(manifest)
    if manifest['schema_version'] == 8:
        if not manifest.get('profile_history'):
            raise ValueError('profile selection is required before review work starts')
        errors = review_profiles.validate_history(manifest.get('profile_history'))
        if errors:
            raise ValueError('; '.join(errors))
        if 'assignment_registry' in manifest:
            try:
                review_profiles._assignment_rows(manifest['assignment_registry'],
                                                 manifest['profile_history'], 'assignment_registry')
            except (TypeError, ValueError) as exc:
                raise ValueError('invalid archive assignment registry: ' + str(exc)) from exc
        if 'review_inputs' in manifest and manifest['review_inputs'] is not None:
            try:
                inputs = review_inputs.normalize_inputs(manifest['review_inputs'], caller=False)
            except (TypeError, ValueError) as exc:
                raise ValueError('invalid archive review_inputs: ' + str(exc)) from exc
            if inputs.get('scope') != manifest.get('scope') or 'profile' in inputs:
                raise ValueError('archive review_inputs must bind the pinned scope and leave profile to profile_history')
        operation = manifest.get('operation')
        fields = {'disposition', 'reason', 'source', 'phase', 'successor'}
        if (not isinstance(operation, dict) or set(operation) != fields
                or operation['disposition'] not in {'open', 'paused', 'blocked', 'superseded', 'complete'}):
            raise ValueError('invalid archive operation disposition')
        restart_operation = manifest.get('restart_operation')
        if restart_operation is not None:
            restart_fields = {'operation_id', 'request_sha256', 'intent_sha256', 'source_run',
                              'source_owner_id', 'reservation_id'}
            if (not isinstance(restart_operation, dict) or set(restart_operation) != restart_fields
                    or not re.fullmatch(r'[0-9a-f]{32}', str(restart_operation['operation_id']))
                    or not CHECKPOINT_HASH.fullmatch(str(restart_operation['request_sha256']))
                    or not CHECKPOINT_HASH.fullmatch(str(restart_operation['intent_sha256']))
                    or not isinstance(restart_operation['source_run'], str)
                    or restart_operation['source_run'] != manifest.get('previous_run')
                    or not isinstance(restart_operation['source_owner_id'], str)
                    or not isinstance(restart_operation['reservation_id'], str)):
                raise ValueError('invalid reserved restart identity in archive')
        controller = manifest.get('controller')
        if (not isinstance(controller, dict) or set(controller) != {'identity', 'source'}
                or not isinstance(controller['identity'], dict) or not isinstance(controller['source'], str)):
            raise ValueError('invalid archive controller identity')
        _validate_cleanup_metadata(manifest)
        _validate_terminal_abandonment(run, manifest)
    states = {'prepared', 'retaining', 'closing', 'complete'}
    if manifest['schema_version'] in (5, 6, 7, 8):
        states.add('processing')
    if manifest.get('state') not in states:
        raise ValueError('invalid archive state')
    if manifest.get('cleanup') not in {'pending', 'complete', 'not_needed'}:
        raise ValueError('invalid closure state')
    _validate_layout(run, manifest)
    return run, manifest, marker
