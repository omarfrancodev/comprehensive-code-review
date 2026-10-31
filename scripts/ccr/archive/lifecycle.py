"""Ordinary archive preparation, profile, operation, and closure lifecycle."""
import base64
import copy
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import uuid

from ccr.archive import layout as review_layout
from ccr.archive import trace as review_trace

ARCHIVE_SCHEMA_VERSION = review_layout.ARCHIVE_SCHEMA_VERSION
from ccr.archive.coordination import _locked_run, _owned_run_locks, _restart_lock
from ccr.archive.evidence import _capture_review_inputs, _input_object
from ccr.archive.integrity import (
    CHECKPOINT_EVIDENCE_COUNT_LIMIT, CHECKPOINT_EVIDENCE_LIMIT,
    CHECKPOINT_METADATA_LIMIT, FILES, OPTIONAL_FILES, PENDING_CONTEXT_LIMIT,
    TRACE_ARCHIVE_SCHEMAS, TRACE_FILES, _evidence_name, _retained_name,
    verify_files as _verify_files,
)
from ccr.archive.intent_contracts import _validate_cleanup_metadata, normalize_transfer_history
from ccr.archive.reader import MARKER, load_run as _load_run, select_output_root, _validate_layout
from ccr.archive.restart_observations import resource_availability as _resource_availability
from ccr.archive.restart_state import (
    _active_restart_operation, _assert_not_restart_abandoned,
    _existing_restart_intent_path, _restart_source_identity,
)
from ccr.archive.retention import (
    _executors, _execution_gate, _present_resources, _retain_data,
    _temporary_manifests, _temporary_paths, _validate_model_usage_context,
)
from ccr.archive.transactions import (
    _append_trace, _append_trace_events, _archive_write, _milestone,
    recover_trace as _recover_trace, save_manifest as _save_manifest,
)
from ccr.contracts.scope import require_scope as _scope
from ccr.execution import harness as review_harness
from ccr.execution.locks import run_locks
from ccr.shared.encoding import archive_bytes as _json_bytes
from ccr.shared.git import git as _git, repository_identity
from ccr.shared.installation import resource_path, skill_root
from ccr.shared.json_io import atomic_write, read_bounded, read_json
from ccr.shared.paths import contains as _contains, safe_path
from ccr.workflow import inputs as review_inputs
from ccr.workflow import profiles as review_profiles
from ccr.workflow.builders import initial_selection as _initial_selection
from ccr.contracts import preflight as review_preflight
from ccr.contracts import dispatch as review_dispatch
from ccr.contracts import review as review_contract
from ccr.contracts.references import parse_reference as _parse_reference, resolve_reference
from ccr.contracts.reference_index import canonical_reference, validate_selection_reference
from ccr.contracts.reference_types import INITIAL_PROFILE_HISTORY_REFERENCE
from ccr.contracts import model_usage as review_model_usage
from ccr.maintenance import metrics as review_metrics
from ccr.reporting.render import render as render_review, render_handoff
from ccr.archive import restart_contract as review_restart
from ccr.execution import claims as resource_claims

CLEANUP_RECEIPT_LIMIT = 64
CHECKPOINT_HASH = re.compile(r'[0-9a-f]{64}')


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

def _starts_processing(event):
    return (event['kind'] in {'agent', 'discovery', 'check', 'grouped-verification'}
            and event['status'] in {'started', 'completed', 'passed', 'failed', 'blocked', 'skipped'})


def _profile_event(selection):
    return {'kind': 'profile', 'status': 'selected',
            'summary': 'Profile selected: ' + selection['profile'],
            'actor': selection['actor'], 'authority': selection['authority'],
            'provenance': {'kind': 'helper', 'source': 'review_artifacts:profile-selection'},
            'evidence': [selection['reference']]}

def _controller(value, fallback):
    if value is None:
        return {'identity': copy.deepcopy(fallback), 'source': 'profile-input'}
    item = _input_object(value, 'controller')
    identity = item.get('identity')
    source = item.get('source')
    if (set(item) != {'identity', 'source'} or not isinstance(identity, dict)
            or set(identity) != {'kind', 'name', 'provider_id'}
            or identity['kind'] not in {'helper', 'coordinator', 'agent', 'tool'}
            or not isinstance(identity['name'], str) or not identity['name'].strip() or len(identity['name']) > 160
            or any(ord(char) < 32 for char in identity['name'])
            or identity['provider_id'] is not None and (not isinstance(identity['provider_id'], str)
                or not identity['provider_id'].strip() or len(identity['provider_id']) > 160
                or any(ord(char) < 32 for char in identity['provider_id']))
            or not isinstance(source, str) or not source.strip() or len(source) > 500
            or any(ord(char) < 32 for char in source)):
        raise ValueError('controller requires a trace identity and nonempty source')
    return {'identity': copy.deepcopy(identity), 'source': source}

def _remove_unowned_prepare_directory(run, marker):
    """Remove only an empty run dir or its own marker when no closure exists."""
    try:
        closure = run / 'cierre.json'
        if closure.exists():
            return
        ownership = run / MARKER
        if ownership.exists():
            value = read_json(ownership)
            if (value.get('owner_id') != marker['owner_id'] or value.get('run_dir') != str(run)
                    or value.get('scope_sha256') != marker['scope_sha256']):
                return
            ownership.unlink()
        run.rmdir()
    except (OSError, ValueError, TypeError):
        return


def _retained_dispatch_identity(run, manifest, reference):
    """Resolve a closing annotation against its hash-verified retained source."""
    hashes = manifest.get('hashes', {})
    context_reference = 'evidence/context.json'
    if context_reference not in hashes:
        raise ValueError('closing review requires an already-retained execution context')
    context = read_json(safe_path(run / context_reference))
    if not isinstance(context, dict):
        raise ValueError('retained execution context must be an object')
    aliases = {}
    index_reference = context.get('reference_index')
    if index_reference is not None:
        if index_reference != 'evidence/reference-index.json' or index_reference not in hashes:
            raise ValueError('closing review requires an already-retained reference index')
        index = read_json(safe_path(run / index_reference))
        if not isinstance(index, dict):
            raise ValueError('retained reference index must be a JSON object')
        aliases = index.get('aliases', {})
    canonical = canonical_reference(reference, aliases)
    source_path, _ = _parse_reference(canonical, field='dispatch identity provenance')
    if source_path not in hashes:
        raise ValueError('closing review requires an already-retained dispatch identity source')
    raw = safe_path(run / source_path).read_bytes()
    alias_path, _ = _parse_reference(reference, field='dispatch identity provenance', allow_alias_key=True)
    if alias_path in aliases and _digest(raw) != aliases[alias_path]['sha256']:
        raise ValueError('retained dispatch identity source differs from the alias SHA-256 identity')
    return resolve_reference(canonical, {source_path: raw}, field='dispatch identity source')


@_locked_run
def record_event(run_dir, event_file, execution_metadata=None):
    """Coordinator-only durable writer for a bounded, structured worker milestone."""
    event = review_trace.event_input(read_json(event_file))
    if execution_metadata is not None:
        metadata_path = safe_path(execution_metadata)
        event = review_trace.event_from_execution(event, read_json(metadata_path), 'review_runner:' + str(metadata_path))
    run, manifest, marker = _load_run(run_dir)
    if manifest['schema_version'] not in TRACE_ARCHIVE_SCHEMAS:
        raise ValueError('legacy archives cannot acquire synthetic traces; prepare a new run')
    marker = _recover_trace(run, manifest, marker)
    _verify_files(run, manifest)
    if manifest['state'] == 'complete':
        raise ValueError('completed review history is immutable')
    if manifest['state'] == 'retaining':
        raise ValueError('retention is interrupted; finish retention before recording milestones')
    if manifest['schema_version'] in (5, 6, 7, 8) and event['occurred_at'] is not None and event['provenance']['source'] is None:
        raise ValueError('observed execution time requires an identifiable provenance source')
    trace_data = None
    if manifest['schema_version'] in (5, 6, 7, 8):
        trace_data = (run / review_trace.NAME).read_bytes()
        review_trace.validate_local_event_targets(event, trace_data)
    if manifest['schema_version'] == 8 and event['kind'] == 'profile':
        raise ValueError('use select-profile to record structured profile transitions')
    if manifest['schema_version'] == 8 and _starts_processing(event):
        if not manifest.get('profile_history'):
            raise ValueError('profile selection is required before review work starts')
        disposition = manifest.get('operation', {}).get('disposition')
        if disposition != 'open':
            raise ValueError('review operation is ' + str(disposition) + '; resume or recover before starting work')
        assignment_issues = review_preflight.validate_assignment_event(
            event, manifest.get('assignment_registry', []))
        if assignment_issues:
            raise ValueError('; '.join(issue['message'] for issue in assignment_issues))
        if (event['kind'] in {'agent', 'discovery', 'grouped-verification'}
                and event.get('evidence')):
            registry = manifest.get('assignment_registry')
            references = {row['reference'] for row in registry if isinstance(row, dict)
                          and row.get('required') is True and row.get('superseded_by') is None
                          and isinstance(row.get('reference'), str)} if isinstance(registry, list) else set()
            inactive = {row['reference'] for row in registry if isinstance(row, dict)
                        and (row.get('required') is not True or row.get('superseded_by') is not None)
                        and isinstance(row.get('reference'), str)} if isinstance(registry, list) else set()
            if inactive.intersection(event['evidence']):
                raise ValueError('assignment work cannot start a superseded or non-required brief')
            if event['status'] == 'started' and not references.intersection(event['evidence']):
                raise ValueError('assignment work must start from an active required brief captured in the execution plan')
    if manifest['schema_version'] == 8 and review_dispatch.is_identity_annotation(event):
        if manifest['state'] not in {'processing', 'closing'}:
            raise ValueError('dispatch identity annotation requires an already-open review trace')
        if manifest.get('operation', {}).get('disposition') != 'open':
            raise ValueError('review operation is not open; resume or recover before annotating dispatch identity')
        registry = manifest.get('assignment_registry', [])
        previous_events = [json.loads(line) for line in (trace_data or b'').splitlines()]
        next_sequence = manifest['trace']['events'] + 1
        candidate = dict(event, sequence=next_sequence,
                         event_id='E' + str(next_sequence).zfill(6))
        issues = review_preflight.validate_assignment_event(event, registry)
        issues.extend(review_dispatch.validate_dispatch_identity_event(
            candidate, registry, previous_events + [candidate]))
        if issues:
            raise ValueError('; '.join(issue['message'] for issue in issues))
        if manifest['state'] == 'closing':
            source = event.get('provenance', {}).get('source')
            observed = _retained_dispatch_identity(run, manifest, source)
            if not isinstance(observed, dict) or observed.get('executor') != event['executor']:
                raise ValueError('dispatch identity source does not match recorded executor')
        target = candidate['relations'][0]['target']
        existing = [row for row in previous_events if review_dispatch.is_identity_annotation(row)
                    and any(item.get('relation') == 'records' and item.get('target') == target
                            for item in row.get('relations', []) if isinstance(item, dict))]
        payload = {key: event[key] for key in review_trace.FIELDS}
        if existing:
            matching = [row for row in existing
                        if {key: row[key] for key in review_trace.FIELDS} == payload]
            if len(matching) == len(existing):
                first = matching[0]
                return {'run_id': manifest['run_id'], 'event_id': first['event_id'],
                        'sequence': first['sequence']}
            raise ValueError('divergent dispatch identity annotation conflicts with the existing target')
    if manifest['schema_version'] in (5, 6, 7, 8) and manifest['state'] == 'prepared' and _starts_processing(event):
        manifest['state'] = 'processing'
    _append_trace(run, manifest, marker, event, helper=False)
    return {'run_id': manifest['run_id'], 'event_id': 'E' + str(manifest['trace']['events']).zfill(6),
            'sequence': manifest['trace']['events']}

def prepare(repo, scope_file, skill_version, harness, output_root=None, previous_run=None, temporary_paths=None,
            *, profile_input=None, controller=None, harness_id=None, harness_source=None, current_inputs=None,
            logical_scope_input=None,
            _restart_reservation=None, _harness_identity=None):
    repo = safe_path(repo)
    repo = safe_path(_git(repo, 'rev-parse', '--show-toplevel'))
    scope = _input_object(scope_file, 'scope')
    _scope(scope)
    if _restart_reservation is not None:
        logical_scope_input = copy.deepcopy(_restart_reservation['request']['logical_scope_input'])
    logical = review_layout.logical_scope(scope, logical_scope_input)
    selection = _initial_selection(profile_input)
    selection_preflight = review_preflight.validate_preflight(
        phase='prepare', manifest=None, logical_scope=logical, selection=selection,
        context=None, record=None, sources={})
    if not selection_preflight['ready']:
        raise ValueError('; '.join(issue['message'] for issue in selection_preflight['issues']))
    captured_inputs = _capture_review_inputs(current_inputs, scope, selection['profile'], 'current review inputs',
                                             logical_scope_identity=logical['identity'])
    controller_value = _controller(controller, selection['actor'])
    if not isinstance(skill_version, str) or not skill_version.strip() or not isinstance(harness, str) or not harness.strip():
        raise ValueError('skill version and harness are required')
    if _harness_identity is None:
        harness_identity = review_harness.resolve(harness, harness_id, harness_source)
    else:
        review_harness.validate_identity(_harness_identity)
        harness_identity = copy.deepcopy(_harness_identity)
    identity = repository_identity(repo)
    repository_key = _digest(identity.encode('utf-8'))[:20]
    root = select_output_root(repo, output_root)
    previous = None
    if previous_run is not None:
        old, old_manifest, old_marker = _load_run(previous_run)
        active_restart = _active_restart_operation(old, old_manifest)
        if (active_restart is not None
                and (_restart_reservation is None
                     or active_restart['operation_id'] != _restart_reservation['operation_id'])):
            raise ValueError('a durable restart is pending; only its exact reserved prepare may continue')
        if _restart_reservation is not None:
            # Transfer can stop while recording its source milestone. Replay the
            # hash-bound append before checking the source's remaining files.
            _recover_trace(old, old_manifest, old_marker)
        _verify_files(old, old_manifest,
                      allow_checkpoint_transaction=_restart_reservation is not None,
                      allow_resource_transfer=_restart_reservation is not None)
        if old_manifest['repository_key'] != repository_key:
            raise ValueError('previous run belongs to a different repository')
        previous = str(old)
    manifest = {'schema_version': ARCHIVE_SCHEMA_VERSION, 'layout_version': review_layout.LAYOUT_VERSION,
                'logical_scope': logical, 'logical_scope_input': copy.deepcopy(logical_scope_input),
                'skill_version': skill_version, 'harness': harness,
                'scope': scope, 'archive_root': str(root), 'repository_path': str(repo),
                'repository_key': repository_key, 'repository_identity': identity, 'previous_run': previous,
                'owner_id': uuid.uuid4().hex, 'created_at': datetime.now(timezone.utc).isoformat(),
                'state': 'prepared', 'retained': False, 'cleanup': 'pending', 'residuals': [],
                'temporary_paths': [], 'temporary_manifests': [], 'executors': [], 'hashes': {},
                'profile_history': [selection],
                'operation': {'disposition': 'open', 'reason': None, 'source': None,
                              'phase': None, 'successor': None},
                'controller': controller_value,
                'checkpoint': None,
                'lineage': {'kind': 'restart' if previous else 'new', 'source_run': previous},
                'resource_claims': [], 'resource_transfers': [],
                'resource_cleanup': None, 'cleanup_receipts': [],
                'assignment_registry': [], 'review_inputs': captured_inputs}
    manifest.update(harness_identity)
    if _restart_reservation is not None:
        intent = _restart_reservation
        errors = review_restart.validate_restart_intent(intent)
        if errors:
            raise ValueError('; '.join(errors))
        reserved = intent['successor']
        logical_scope_input = copy.deepcopy(intent['request']['logical_scope_input'])
        logical = review_layout.logical_scope(scope, logical_scope_input)
        manifest.update(layout_version=review_layout.LAYOUT_VERSION, logical_scope=logical,
                        logical_scope_input=logical_scope_input)
        manifest.update(run_id=reserved['run_id'], owner_id=reserved['owner_id'],
                        created_at=reserved['created_at'], restart_operation={
                            'operation_id': intent['operation_id'],
                            'request_sha256': intent['request_sha256'],
                            'intent_sha256': intent['intent_sha256'],
                            'source_run': intent['source']['run_dir'],
                            'source_owner_id': intent['source']['owner_id'],
                            'reservation_id': reserved['reservation_id']})
    manifest['temporary_paths'] = _temporary_paths(temporary_paths, manifest)
    manifest['temporary_manifests'] = _temporary_manifests(manifest['temporary_paths'], manifest)
    scoped = root / _repository_group(identity) / review_layout.scope_group(logical)
    reservation_file = '.review-restart-reservation.json'
    if _restart_reservation is not None:
        reserved = _restart_reservation['successor']
        run = safe_path(reserved['run_dir'])
        created = datetime.fromisoformat(reserved['created_at'])
        expected_parent = safe_path(scoped)
        if run.parent != expected_parent:
            raise ValueError('reserved successor escaped its repository/scope group')
        _validate_layout(run, manifest)
        reservation = {'operation_id': _restart_reservation['operation_id'],
                       'intent_sha256': _restart_reservation['intent_sha256'],
                       'reservation_id': reserved['reservation_id'], 'run_dir': str(run),
                       'owner_id': reserved['owner_id']}
        reservation_path = run / reservation_file
        stage_names = {'.' + name + '.' + reserved['reservation_id'] + '.tmp'
                       for name in (reservation_file, MARKER, 'cierre.json', review_trace.NAME)}
        if run.exists():
            if reservation_path.exists() and read_json(reservation_path) != reservation:
                raise ValueError('reserved successor path is occupied by foreign or invalid data')
            try:
                existing, existing_manifest, existing_marker = _load_run(run)
            except (ValueError, OSError, TypeError, KeyError):
                existing_manifest = None
            if existing_manifest is not None:
                with run_locks([existing]):
                    existing, existing_manifest, existing_marker = _load_run(existing)
                    identity_fields = ('run_id', 'owner_id', 'created_at', 'archive_root',
                                       'repository_key', 'scope', 'previous_run', 'restart_operation')
                    if any(existing_manifest.get(key) != manifest.get(key) for key in identity_fields):
                        raise ValueError('reserved successor identity differs from its restart intent')
                    _assert_not_restart_abandoned(existing_manifest)
                    _recover_trace(existing, existing_manifest, existing_marker)
                    _verify_files(existing, existing_manifest, allow_resource_transfer=True)
                    if reservation_path.exists():
                        if read_json(reservation_path) != reservation:
                            raise ValueError('reserved successor reservation changed while acquiring its lock')
                        for name in stage_names:
                            safe_path(run / name).unlink(missing_ok=True)
                    reservation_path.unlink(missing_ok=True)
                    # Its sidecar may already name this successor while registration
                    # or transfer is not committed yet. The exact helper below owns
                    # that replay; a fresh unbound-resource preflight would reject it.
                    return str(existing)
            entries = {item.name for item in run.iterdir()}
            if entries - {reservation_file, MARKER} - stage_names:
                raise ValueError('partially prepared reserved successor contains unowned data')
            if (run / MARKER).exists():
                partial = read_json(run / MARKER)
                expected_marker = {'owner_id': manifest['owner_id'], 'run_dir': str(run),
                    'archive_root': str(root), 'repository_key': repository_key,
                    'scope_sha256': _digest(_json_bytes(scope)),
                    'logical_scope_sha256': _digest(_json_bytes(logical))}
                if (not isinstance(partial, dict) or any(partial.get(key) != value
                        for key, value in expected_marker.items())):
                    raise ValueError('partially prepared successor ownership differs from its reservation')
            resource_claims.plan_resource_registration(manifest['temporary_paths'], manifest)
            for name in stage_names:
                safe_path(run / name).unlink(missing_ok=True)
        else:
            resource_claims.plan_resource_registration(manifest['temporary_paths'], manifest)
            safe_path(scoped).mkdir(parents=True, exist_ok=True)
            run.mkdir()
        # The immutable source intent authorizes this exact allocation, including
        # an empty directory after mkdir. Keep the reservation until cierre exists.
        atomic_write(reservation_path, _json_bytes(reservation), staging_path=run / (
            '.' + reservation_file + '.' + reserved['reservation_id'] + '.tmp'))
    else:
        resource_claims.plan_resource_registration(manifest['temporary_paths'], manifest)
        safe_path(scoped).mkdir(parents=True, exist_ok=True)
        # Exclusive mkdir is the collision/ownership boundary; never adopt an existing run.
        for _ in range(8):
            created = datetime.now(timezone.utc)
            manifest.update(created_at=created.isoformat(), run_id=uuid.uuid4().hex[:20])
            run = scoped / review_layout.run_name(scope, manifest['created_at'], manifest['run_id'], logical_scope_input)
            _validate_layout(run, manifest)
            try:
                run.mkdir()
                break
            except FileExistsError:
                continue
        else:
            raise ValueError('cannot allocate a unique owned review run')
    marker = {'owner_id': manifest['owner_id'], 'run_dir': str(run), 'archive_root': str(root),
              'repository_key': repository_key, 'scope_sha256': _digest(_json_bytes(scope)),
              'logical_scope_sha256': _digest(_json_bytes(logical))}
    try:
        _append_trace_events(run, manifest, marker,
                             [_milestone('prepare', 'Owned archive prepared with pinned scope'),
                              _profile_event(selection)])
    except OSError:
        try:
            recovered_run, recovered, recovered_marker = _load_run(run)
            recovered_marker = _recover_trace(recovered_run, recovered, recovered_marker)
            _verify_files(recovered_run, recovered)
            if (recovered['profile_history'] == [selection]
                    and recovered['trace']['events'] >= 2):
                (recovered_run / reservation_file).unlink(missing_ok=True)
                return str(run)
        except (OSError, ValueError, TypeError, KeyError):
            _remove_unowned_prepare_directory(run, marker)
        raise
    (run / reservation_file).unlink(missing_ok=True)
    return str(run)

@_locked_run
def select_profile(run_dir, selection_input):
    """Capture a profile transition and its trace event as one idempotent mutation."""
    raw = _input_object(selection_input, 'profile selection')
    run, manifest, marker = _load_run(run_dir)
    if manifest['schema_version'] != 8:
        raise ValueError('profile transitions require an archive 8 run')
    marker = _recover_trace(run, manifest, marker)
    _verify_files(run, manifest)
    if manifest['state'] in {'retaining', 'closing', 'complete'}:
        raise ValueError('profile cannot change after retention or closure starts')
    if manifest.get('operation', {}).get('disposition') != 'open':
        raise ValueError('review operation is not open; resume or recover before selecting a profile')
    if set(raw) - review_profiles.INPUT_FIELDS - {'changed_from'}:
        raise ValueError('profile transition input cannot supply archive-assigned identity fields')
    history = manifest['profile_history']
    previous = history[-1]
    try:
        candidate = review_profiles.validate_selection(raw, previous=previous)
    except ValueError:
        raise
    if candidate == previous:
        return manifest
    if candidate['phase'] == 'prepare':
        raise ValueError('profile transitions cannot use prepare phase')
    if len(history) >= review_profiles.MAX_HISTORY:
        raise ValueError('profile history reached its selection limit')
    events = [json.loads(line) for line in (run / review_trace.NAME).read_bytes().splitlines()]
    affected = set(candidate['affected_assignments'])
    for row in manifest.get('assignment_registry', []):
        if row['id'] in affected and review_profiles._assignment_started(row, events):
            raise ValueError('started assignment cannot be affected by a profile transition: ' + row['id'])
    candidate.update(id='S' + str(len(history) + 1).zfill(3),
                     changed_from=previous['profile'],
                     event_id='E' + str(manifest['trace']['events'] + 1).zfill(6))
    manifest['profile_history'] = history + [candidate]
    _append_trace(run, manifest, marker, _profile_event(candidate))
    return manifest

@_locked_run
def register(run_dir, temporary_paths, *, context_input=None, authority=None):
    _, manifest, _ = _load_run(run_dir)
    temporary = _temporary_paths(temporary_paths, manifest)
    with resource_claims.session_claim_locks(temporary):
        return _register_locked(run_dir, temporary, context_input=context_input, authority=authority)

def _register_locked(run_dir, temporary_paths, *, context_input=None, authority=None):
    """Register coordinator-verified owned resources before discovery/execution."""
    run, manifest, marker = _load_run(run_dir)
    marker = _recover_trace(run, manifest, marker)
    _verify_files(run, manifest)
    if manifest['state'] not in {'prepared', 'processing'}:
        raise ValueError('register temporary resources before retention')
    if manifest['schema_version'] == 8 and manifest.get('operation', {}).get('disposition') != 'open':
        raise ValueError('review operation is not open; resume or recover before registering resources')
    if manifest['schema_version'] == 8 and context_input is None:
        raise ValueError('archive 8 registration requires captured context, including executors or an explicit empty list')
    temporary = _temporary_paths(temporary_paths, manifest)
    manifests = _temporary_manifests(temporary, manifest)
    executors = _executors(context_input, manifest, temporary)
    assignment_registry = list(manifest.get('assignment_registry', []))
    review_input_capture = manifest.get('review_inputs')
    disclosure_identity = manifest.get('check_disclosure_input_identity')
    claim_manifest = copy.deepcopy(manifest)
    claim_manifest.update(temporary_paths=temporary, temporary_manifests=manifests,
                          _claim_run_dir=str(run))
    if manifest['schema_version'] == 8 and context_input is not None:
        context = _input_object(context_input, 'execution context')
        phase_preflight = review_preflight.validate_preflight(
            phase='register', manifest=manifest, logical_scope=manifest.get('logical_scope'),
            selection=manifest['profile_history'][-1], context=context, record=None,
            sources={'evidence/context.json': _json_bytes(context)},
            check_material_sources=False)
        if not phase_preflight['ready']:
            raise ValueError('; '.join(issue['message'] for issue in phase_preflight['issues']))
        if (context.get('profile') != manifest['profile_history'][-1]['profile']
                or context.get('selection_source') != manifest['profile_history'][0]['selection_source']
                or context.get('profile_history') != manifest['profile_history']):
            raise ValueError('executor context must preserve the profile history captured by the archive')
        if not isinstance(context.get('execution_plan'), list):
            raise ValueError('archive 8 registration requires captured context.execution_plan')
        existing_trace = [json.loads(line) for line in (run / review_trace.NAME).read_bytes().splitlines()]
        supplied_disclosure_identity = context.get('check_disclosure_input_identity')
        if supplied_disclosure_identity is not None:
            from ccr.contracts.check_disclosure import input_identity_for
            scope_identity = {key: manifest['scope'].get(key) for key in ('head', 'snapshot')}
            if (not isinstance(supplied_disclosure_identity, dict)
                    or any(supplied_disclosure_identity.get(key) != value for key, value in scope_identity.items())):
                raise ValueError('disclosure identity differs from pinned scope')
            if disclosure_identity is not None and disclosure_identity != supplied_disclosure_identity:
                raise ValueError('disclosure identity cannot replace its initial capture')
            if disclosure_identity is None:
                if any(row.get('kind') in {'agent', 'discovery', 'grouped-verification', 'check'}
                       and row.get('status') in {'started', 'completed', 'passed', 'failed'} for row in existing_trace):
                    raise ValueError('disclosure inputs must be pinned before review work starts')
                baseline_hash = supplied_disclosure_identity.get('resource_manifest_sha256')
                if baseline_hash is not None:
                    from ccr.execution import workspaces as workspace_ops
                    baseline_hashes = set()
                    for executor in executors:
                        if executor.get('manifest'):
                            owned = workspace_ops.load(executor['manifest'])
                            baseline_hashes.update(row.get('resource_baseline_sha256') for row in owned['workspaces']
                                if row['path'] == executor['workspace'])
                    captured_hashes = set((review_input_capture or {}).get('sources', {}).values())
                    if baseline_hash not in baseline_hashes | captured_hashes:
                        raise ValueError('disclosure resource map is not part of the initially captured workspace/inputs')
                disclosure_identity = copy.deepcopy(supplied_disclosure_identity)
        if 'assignment_registry' not in manifest and any(
                row.get('kind') in {'agent', 'discovery', 'grouped-verification'}
                and row.get('status') in {'started', 'completed', 'passed', 'failed', 'blocked', 'skipped'}
                and row.get('evidence') for row in existing_trace if isinstance(row, dict)):
            raise ValueError('review work predates assignment capture; restart the review before registering execution')
        supplied_inputs = context.get('review_inputs')
        if supplied_inputs is not None:
            captured = _capture_review_inputs(supplied_inputs, manifest['scope'],
                                              manifest['profile_history'][-1]['profile'],
                                              'execution context review_inputs',
                                              logical_scope_identity=manifest.get('logical_scope', {}).get('identity'))
            if review_input_capture is None:
                if any(row.get('kind') in {'agent', 'discovery', 'grouped-verification'}
                       and row.get('status') in {'started', 'completed', 'passed', 'failed', 'blocked', 'skipped'}
                       and row.get('evidence') for row in existing_trace if isinstance(row, dict)):
                    raise ValueError('review inputs must be captured before assignment work starts; restart the review')
                review_input_capture = captured
            elif captured != review_input_capture:
                raise ValueError('execution context review_inputs cannot replace the original captured identities')
        assignment_registry = review_profiles.merge_assignment_registry(
            assignment_registry, context['execution_plan'], manifest['profile_history'], existing_trace)
        assignment_issues = review_preflight.validate_assignment_history(existing_trace, assignment_registry)
        if assignment_issues:
            raise ValueError('; '.join(issue['message'] for issue in assignment_issues))
        references = {row['reference'] for row in assignment_registry}
        for row in existing_trace:
            if (isinstance(row, dict) and row.get('kind') in {'agent', 'discovery', 'grouped-verification'}
                    and row.get('status') == 'started' and row.get('evidence')
                    and not references.intersection(row['evidence'])):
                raise ValueError('observed assignment start has no captured brief identity; preserve the run and restart')
        if context['execution_plan'] != assignment_registry:
            raise ValueError('context.execution_plan must preserve the complete durable assignment registry')
    rows = list(manifest.get('resource_claims', []))
    plans = resource_claims.plan_resource_registration(temporary, claim_manifest, authority=authority)
    pending_writes = []
    if manifest['schema_version'] == 8:
        for raw, plan in zip(temporary, plans):
            if plan['action'] == 'not_workspace':
                continue
            if plan['action'] == 'transfer':
                raise ValueError('resource belongs to another review; use transfer-resources with explicit authority')
            path = safe_path(Path(raw) / resource_claims.CLAIM_NAME)
            if plan['action'] in {'claim', 'adopt'}:
                try:
                    current_digest = _digest(path.read_bytes())
                except FileNotFoundError:
                    current_digest = None
                if current_digest != plan['expected_current_sha256']:
                    raise ValueError('resource claim changed after planning; preserve the session and retry')
                pending_writes.append((path, plan['bytes']))
            existing = [row for row in rows if row.get('session_dir') == str(safe_path(raw))]
            if existing and (len(existing) != 1 or existing[0] != plan['row']):
                raise ValueError('review archive already contains a different claim for this session')
            if not existing and plan['row'] is not None:
                rows.append(plan['row'])
        for path, data in pending_writes:
            atomic_write(path, data)
    manifest.update(temporary_paths=temporary, temporary_manifests=manifests, executors=executors)
    if manifest['schema_version'] == 8:
        manifest.update(resource_claims=rows, assignment_registry=assignment_registry,
                        review_inputs=review_input_capture)
        if disclosure_identity is not None:
            manifest['check_disclosure_input_identity'] = disclosure_identity
    _append_trace(run, manifest, marker, _milestone('register', 'Coordinator-owned temporary resources registered'))
    return manifest

@_locked_run
def pause(run_dir, *, authority, reason, phase):
    """Record an explicit user-directed pause without discarding the open run."""
    run, manifest, marker = _load_run(run_dir)
    marker = _recover_trace(run, manifest, marker)
    _verify_files(run, manifest)
    if manifest['schema_version'] != 8:
        raise ValueError('new pause transitions require archive 8; preserve legacy history and start a linked run')
    authority = resource_claims.normalize_authority(authority)
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000 or any(ord(c) < 32 for c in reason):
        raise ValueError('pause reason must be bounded nonempty text')
    if phase not in review_profiles.PHASES:
        raise ValueError('pause phase must identify a known review phase')
    operation = manifest['operation']
    if operation['disposition'] == 'paused' and operation['reason'] == reason and operation['phase'] == phase:
        return manifest
    if operation['disposition'] != 'open' or manifest['state'] in {'retaining', 'closing', 'complete'}:
        raise ValueError('only an open review can be paused')
    operation.update(disposition='paused', reason=reason.strip(), source='explicit-user-pause',
                     phase=phase, successor=None)
    _append_trace(run, manifest, marker, _recovery_event(
        manifest, 'Review paused by explicit request: ' + reason.strip(), status='blocked', authority=authority))
    return manifest

@_locked_run
def block(run_dir, *, source, reason, phase):
    """Record an observed failure; never infer a crash or harness failure."""
    run, manifest, marker = _load_run(run_dir)
    marker = _recover_trace(run, manifest, marker)
    _verify_files(run, manifest)
    if manifest['schema_version'] != 8:
        raise ValueError('new block transitions require archive 8; preserve legacy history and start a linked run')
    if not isinstance(source, str) or not source.strip() or len(source) > 500 or any(ord(c) < 32 for c in source):
        raise ValueError('block source must identify an observed failure source')
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000 or any(ord(c) < 32 for c in reason):
        raise ValueError('block reason must be bounded nonempty text')
    if phase not in review_profiles.PHASES:
        raise ValueError('block phase must identify a known review phase')
    operation = manifest['operation']
    if (operation['disposition'] == 'blocked' and operation['source'] == source
            and operation['reason'] == reason and operation['phase'] == phase):
        return manifest
    if operation['disposition'] not in {'open', 'paused', 'blocked'} or manifest['state'] in {'retaining', 'closing', 'complete'}:
        raise ValueError('only an open, paused or blocked review can record an observed blocker')
    operation.update(disposition='blocked', reason=reason.strip(), source=source.strip(),
                     phase=phase, successor=None)
    _append_trace(run, manifest, marker, _recovery_event(
        manifest, 'Observed review blocker: ' + reason.strip(), status='blocked', source=source.strip()))
    return manifest


def recovery_event(manifest, summary, *, status='completed', authority=None, source=None, relation=None):
    event = {'kind': 'interruption', 'status': status, 'summary': summary,
             'actor': copy.deepcopy(manifest.get('controller', {}).get('identity',
                 {'kind': 'coordinator', 'name': 'review coordinator', 'provider_id': None})),
             'provenance': {'kind': 'tool' if source else 'helper',
                            'source': source or 'review_artifacts:recovery'},
             'evidence': ['cierre.json'], 'authority': authority,
             'occurred_at': datetime.now(timezone.utc).isoformat()}
    if relation is not None:
        event['relations'] = [relation]
    return event

def takeover_controller(run, manifest, marker, controller, authority):
    """Persist an authorized controller change once, shared by resume and recovery."""
    normalized = _controller(controller, manifest.get('controller', {}).get('identity',
        {'kind': 'coordinator', 'name': 'review coordinator', 'provider_id': None}))
    previous = manifest.get('controller')
    if normalized == previous:
        return normalized, marker
    operation = manifest.get('operation', {})
    if manifest.get('state') == 'complete' or operation.get('disposition') in {'complete', 'superseded'}:
        return previous, marker
    if authority is None:
        raise ValueError('controller takeover requires explicit user authority')
    authority = resource_claims.normalize_authority(authority)
    prior = previous.get('identity', {}).get('name', 'unknown') if isinstance(previous, dict) else 'unknown'
    manifest['controller'] = normalized
    marker = _append_trace(run, manifest, marker, recovery_event(
        manifest, 'Controller takeover by ' + normalized['identity']['name']
        + '; prior controller recorded as ' + prior,
        authority=authority, relation={'relation': 'follows', 'target': 'E'
            + str(manifest.get('trace', {}).get('events', 0)).zfill(6)}))
    return normalized, marker

_recovery_event = recovery_event
_takeover_controller = takeover_controller

@_locked_run
def resume(run_dir, *, controller, authority, current_inputs):
    """Reopen an unchanged archive after explicit continuation/takeover authority."""
    run, manifest, marker = _load_run(run_dir)
    marker = _recover_trace(run, manifest, marker)
    _verify_files(run, manifest)
    if manifest['schema_version'] != 8:
        raise ValueError('unsupported_layout: preserve the legacy archive or port a verified report for consultation')
    if manifest['state'] in {'retaining', 'closing', 'complete'}:
        raise ValueError('retention/closure has started or completed; recover its transaction or create a new run')
    normalized_inputs = review_inputs.validate_current_inputs(
        current_inputs, manifest, require_applicable=True)
    operation = manifest['operation']
    if operation['disposition'] not in {'open', 'paused', 'blocked'}:
        raise ValueError('superseded or completed review cannot be resumed')
    resources = _resource_availability(run, manifest)
    if any(row['availability'] == 'missing_unknown' for row in resources):
        raise ValueError('claimed workspace is missing_unknown; use an authorized restart without transferring missing resources')
    normalized_controller = _controller(controller, manifest['controller']['identity'])
    changed_controller = normalized_controller != manifest['controller']
    if operation['disposition'] in {'paused', 'blocked'} and authority is None:
        raise ValueError('continuing a paused or blocked review requires explicit user authority')
    if authority is not None:
        authority = resource_claims.normalize_authority(authority)
    if operation['disposition'] == 'open' and not changed_controller:
        return manifest
    normalized_controller, marker = takeover_controller(
        run, manifest, marker, normalized_controller, authority)
    manifest['operation'].update(disposition='open', reason=None, source='resume', successor=None)
    manifest['operation']['phase'] = manifest['operation']['phase'] or 'discovery'
    summary = 'Review resumed by ' + normalized_controller['identity']['name']
    _append_trace(run, manifest, marker, _recovery_event(
        manifest, summary, authority=authority, relation={'relation': 'follows', 'target': 'E' +
            str(manifest['trace']['events']).zfill(6)}))
    return manifest

@_locked_run(when=lambda args, kwargs: kwargs.get('record_checkpoint', args[1] if len(args) > 1 else False))
def validate(run_dir, require_retained=False, record_checkpoint=False, *, require_complete=False):
    """Read-only archive gate; selected evidence is verified, never copied here."""
    if require_complete and record_checkpoint:
        raise ValueError('complete gate is read-only; cannot record a checkpoint')
    require_retained = require_retained or require_complete
    run, manifest, marker = _load_run(run_dir)
    superseded = manifest.get('operation', {}).get('disposition') == 'superseded'
    if superseded and record_checkpoint:
        raise ValueError('superseded review history is immutable; validate without --record-checkpoint')
    if manifest['schema_version'] in TRACE_ARCHIVE_SCHEMAS and _digest((run / 'cierre.json').read_bytes()) != marker.get('manifest_sha256'):
        raise ValueError('ownership transition is pending; retry the interrupted helper mutation')
    _verify_files(run, manifest, required=require_retained,
                  allow_checkpoint_transaction=superseded and not require_retained)
    if require_retained and (manifest.get('retained') is not True or manifest['state'] not in {'closing', 'complete'}):
        raise ValueError('retained final review is required before cleanup')
    if require_retained:
        value = read_json(run / 'review.json')
        errors = review_contract.validate(value)
        if errors or not isinstance(value, dict) or value.get('stage') != 'final':
            raise ValueError('; '.join(errors) if errors else 'retained record must be a final review')
        if value['scope'] != manifest['scope']:
            raise ValueError('retained review scope differs from the pinned scope')
        if value.get('schema_version') in (6, 7, 8, 9, 10, 11, 12) and value.get('review_id') != 'CR-' + manifest.get('run_id', ''):
            raise ValueError('retained review ID differs from archive run ID')
        if manifest['schema_version'] == 8 and value.get('schema_version') not in (10, 11, 12):
            raise ValueError('archive 8 requires final review schema 10, 11 or 12')
        if value.get('schema_version') in (8, 9, 10, 11, 12):
            _execution_gate(run, manifest, value, {})
    if require_complete:
        if (manifest['state'] != 'complete' or manifest['cleanup'] not in {'complete', 'not_needed'}
                or manifest.get('residuals')):
            raise ValueError('complete durable review and observed cleanup are required')
        if (value['resources']['cleanup'] != manifest['cleanup']
                or value['resources']['residuals'] != manifest.get('residuals', [])):
            raise ValueError('retained review resources differ from completed closure')
    if record_checkpoint:
        if manifest['state'] == 'complete':
            raise ValueError('completed review history is immutable; validate without --record-checkpoint')
        if manifest['schema_version'] not in TRACE_ARCHIVE_SCHEMAS:
            raise ValueError('legacy archives cannot acquire synthetic trace checkpoints')
        _append_trace(run, manifest, marker, _milestone('validation',
                      'Retained evidence gate passed' if require_retained else 'Archive ownership and integrity gate passed', status='passed'))
    return {'run_dir': str(run), 'schema_version': manifest['schema_version'],
            'state': manifest['state'], 'retained': manifest.get('retained') is True,
            'cleanup': manifest['cleanup']}

def _close_recovery_contents(run, manifest):
    """Reconstruct only the exact owned old/planned cleanup transaction."""
    from ccr.archive.evidence import selected_source_bytes
    from ccr.archive.retention import rebind_disclosure_for_cleanup, retained_model_context
    from ccr.archive.intent_contracts import close_previous_disclosure_bytes

    context = json.loads(selected_source_bytes(run, manifest, {}, 'evidence/context.json'))
    reference = context.get('check_disclosure_reference')
    if reference is None:
        return None
    if reference != 'evidence/check-disclosure.json':
        raise ValueError('invalid close disclosure reference')
    current = read_json(run / 'review.json')
    # _verify_files has already checked every surviving file against old/planned
    # hashes. Reconstruct the old canonical record from its bounded cleanup facts,
    # accepting it only if its bytes match the original retained inventory.
    previous = None
    for cleanup in ('pending', 'complete', 'not_needed'):
        candidate = copy.deepcopy(current)
        candidate['resources'].update(cleanup=cleanup, residuals=manifest['residuals'])
        if _digest(_json_bytes(candidate)) == manifest['hashes'].get('review.json'):
            previous = candidate
            break
    if previous is None:
        raise ValueError('interrupted close cannot reconstruct the owned previous review')
    value = copy.deepcopy(previous)
    observation = manifest['close_observation']
    value['resources'].update(cleanup=observation['cleanup'], residuals=observation['residuals'])

    old_disclosure = close_previous_disclosure_bytes(manifest)
    if old_disclosure is None:
        # A still-surviving original needs no backup. Never infer its encoding
        # from the planned replacement: selected JSON bytes need not be canonical.
        old_disclosure = (run / reference).read_bytes()
        if _digest(old_disclosure) != manifest['hashes'].get(reference):
            raise ValueError('interrupted close has no owned previous disclosure bytes')
    old_sources = {reference: old_disclosure}
    contents = {'review.json': _json_bytes(value)}
    contents.update(rebind_disclosure_for_cleanup(previous, value, context,
        lambda name: selected_source_bytes(run, manifest, old_sources, name)))
    contents['informe.md'] = render_review(value, model_usage_context=retained_model_context(
        run, manifest, contents, record=value)).encode('utf-8')
    if 'handoff.md' in manifest['hashes']:
        contents['handoff.md'] = render_handoff(value, manifest.get('handoff_context')).encode('utf-8')
    if {name: _digest(raw) for name, raw in contents.items()} != manifest.get('planned_hashes'):
        raise ValueError('interrupted close differs from the exact planned inventory')
    return contents


@_locked_run
def close(run_dir, cleanup_file=None, *, cleanup=None, residuals=None, released_claims=None):
    """Observe exact registered resources and persist closure; never remove resources."""
    run, manifest, marker = _load_run(run_dir)
    marker = _recover_trace(run, manifest, marker)
    if 'previous_manifest_sha256' in marker:
        # _load_run already bound these exact bytes to an owned old/new intent.
        # A stop before manifest replacement leaves no pending_trace to replay;
        # pin the authorized surviving manifest, then retry this mutation normally.
        marker = dict(marker, manifest_sha256=_digest((run / 'cierre.json').read_bytes()))
        marker.pop('previous_manifest_sha256')
        atomic_write(run / MARKER, _json_bytes(marker))
    pending_close = (manifest['state'] == 'retaining'
                     and isinstance(manifest.get('close_observation'), dict))
    recovery_contents = None
    if pending_close:
        _verify_files(run, manifest)
        if manifest['schema_version'] == 8:
            recovery_contents = _close_recovery_contents(run, manifest)
        candidate = (json.loads(recovery_contents['review.json']) if recovery_contents is not None
                     else read_json(run / 'review.json'))
        errors = review_contract.validate(candidate) if isinstance(candidate, dict) else ['retained review is not an object']
        if errors or candidate.get('stage') != 'final' or candidate.get('scope') != manifest['scope']:
            raise ValueError('; '.join(errors) if errors else 'interrupted close has no valid retained final review')
        if manifest['schema_version'] == 8:
            _execution_gate(run, manifest, candidate, recovery_contents or {})
    else:
        validate(run, require_retained=True, require_complete=manifest['state'] == 'complete')
    if (cleanup_file is None) == (cleanup is None):
        raise ValueError('supply either cleanup_file or an inline cleanup observation')
    if cleanup_file is not None:
        if residuals is not None or released_claims is not None:
            raise ValueError('residuals and release receipts belong to the cleanup file or inline observation, not both')
        observed = read_json(cleanup_file)
    else:
        observed = {'cleanup': cleanup, 'residuals': residuals if residuals is not None else []}
        if released_claims is not None:
            observed['released_claims'] = released_claims
    if (not isinstance(observed, dict) or set(observed) not in ({'cleanup', 'residuals'},
                                                                  {'cleanup', 'residuals', 'released_claims'})
            or observed['cleanup'] not in {'complete', 'not_needed', 'pending'}
            or not isinstance(observed['residuals'], list)):
        raise ValueError('cleanup must be an explicit cleanup/residuals object')
    residuals = [str(safe_path(raw)) for raw in observed['residuals']]
    registered = [str(safe_path(raw)) for raw in manifest['temporary_paths']]
    if len(set(residuals)) != len(residuals) or set(residuals) - set(registered):
        raise ValueError('residuals must be exact registered temporary paths')
    present = _present_resources(registered)
    if set(residuals) != set(present):
        raise ValueError('observed cleanup does not disclose every existing registered resource')
    if manifest['schema_version'] == 8:
        has_durable_cleanup = 'cleanup_receipts' in manifest and 'resource_cleanup' in manifest
        durable_receipts = manifest.get('cleanup_receipts', []) if has_durable_cleanup else []
        supplied_receipts = observed.get('released_claims')
        if has_durable_cleanup and supplied_receipts is not None and supplied_receipts != durable_receipts:
            raise ValueError('supplied release receipts differ from the durable cleanup receipt history')
        if isinstance(manifest.get('resource_cleanup'), dict) and manifest['resource_cleanup'].get('status') == 'pending':
            raise ValueError('resource cleanup intent is pending; recover or retry cleanup before closing the review')
        manifest['resource_claims'] = resource_claims.validate_release_observation(
            manifest, present, durable_receipts if has_durable_cleanup else (supplied_receipts or []))
        resource_claims.validate_claims_for_close(run, manifest)
    cleanup = observed['cleanup']
    if (cleanup in {'complete', 'not_needed'} and residuals) or (cleanup == 'not_needed' and registered):
        raise ValueError('cleanup conflicts with registered resources or residuals')
    durable_close = None
    if manifest['schema_version'] == 8 and has_durable_cleanup:
        durable_close = {'cleanup': cleanup, 'residuals': residuals,
                         'released_claims': copy.deepcopy(durable_receipts)}
        prior_close = manifest.get('close_observation')
        if prior_close is not None and prior_close != durable_close:
            prior_receipts = prior_close.get('released_claims', [])
            may_advance_pending = (manifest['state'] == 'closing'
                                   and prior_close.get('cleanup') == 'pending'
                                   and cleanup in {'pending', 'complete'}
                                   and set(residuals).issubset(set(prior_close.get('residuals', [])))
                                   and durable_close['released_claims'][:len(prior_receipts)] == prior_receipts)
            if not may_advance_pending:
                raise ValueError('close retry differs from the exact durable cleanup observation')
    if manifest['state'] == 'complete':
        if cleanup != manifest['cleanup'] or residuals != manifest['residuals']:
            raise ValueError('completed review history cannot be reopened')
        return manifest
    if recovery_contents is not None:
        # Observation/claim checks above must succeed before any recovery writes.
        # Every byte and selected source was gated against the owned intent.
        _retain_data(run, manifest, marker, recovery_contents, record_retention=False)
        run, manifest, marker = _load_run(run)
        pending_close = False
    value = read_json(run / 'review.json')
    if value.get('scope') != manifest['scope']:
        raise ValueError('retained review scope differs from manifest')
    value = copy.deepcopy(value)
    value['resources'].update(cleanup=cleanup, residuals=residuals)
    errors = review_contract.validate(value)
    if errors:
        raise ValueError('; '.join(errors))
    from ccr.archive.retention import retained_model_context
    report = render_review(value, model_usage_context=retained_model_context(run, manifest, record=value)).encode('utf-8')
    contents = None
    previous_disclosure = None
    if value != read_json(run / 'review.json') or pending_close:
        contents = {'review.json': _json_bytes(value), 'informe.md': report}
        from ccr.archive.retention import rebind_disclosure_for_cleanup
        from ccr.archive.evidence import selected_source_bytes
        retained_context = (json.loads(selected_source_bytes(run, manifest, {}, 'evidence/context.json'))
                            if 'evidence/context.json' in manifest['hashes'] else {})
        contents.update(rebind_disclosure_for_cleanup(read_json(run / 'review.json'), value, retained_context,
            lambda name: selected_source_bytes(run, manifest, {}, name)))
        if 'handoff.md' in manifest['hashes']:
            contents['handoff.md'] = render_handoff(value, manifest.get('handoff_context')).encode('utf-8')
        reference = retained_context.get('check_disclosure_reference')
        if durable_close is not None and reference in contents:
            from ccr.contracts.check_disclosure import MAX_BYTES
            original = selected_source_bytes(run, manifest, {}, reference)
            # The selected JSON contract bounds canonical size; its whitespace
            # may be larger. Reject an unbounded recovery copy before any intent
            # write, preserving the already valid retained archive unchanged.
            if len(original) > MAX_BYTES:
                raise ValueError('previous disclosure bytes exceed the ' + str(MAX_BYTES) + '-byte recovery limit')
            previous_disclosure = {
                'reference': reference, 'base64': base64.b64encode(original).decode('ascii')}
    if durable_close is not None and manifest.get('close_observation') != durable_close:
        manifest['close_observation'] = durable_close
        marker = _save_manifest(run, manifest, marker)
    if contents is not None:
        # Persist exact selected bytes inside the owned old/planned intent
        # before any sidecar replacement makes the original unavailable.
        if previous_disclosure is not None:
            manifest['close_previous_disclosure'] = previous_disclosure
        manifest = _retain_data(run, manifest, marker, contents, record_retention=False)
        run, manifest, marker = _load_run(run)
    manifest.update(cleanup=cleanup, residuals=residuals,
                    state='complete' if cleanup != 'pending' else 'closing')
    if manifest['state'] == 'complete':
        manifest['closed_at'] = datetime.now(timezone.utc).isoformat()
        if manifest['schema_version'] == 8:
            manifest['operation']['disposition'] = 'complete'
            manifest['operation']['phase'] = 'close'
    _append_trace(run, manifest, marker, _milestone('close', 'Observed resource closure: ' + cleanup,
                  status='pending' if cleanup == 'pending' else 'completed', evidence=['review.json', 'informe.md']))
    return manifest
