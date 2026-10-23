"""Validation gates and report content for archive retention."""
from datetime import datetime, timezone
import copy
import hashlib
import json
import os
import stat
from pathlib import Path
from urllib.parse import urlsplit

from ccr.archive.coordination import _locked_run
from ccr.archive.evidence import _capture_review_inputs, _check_evidence_target, _evidence_contents, _input_object
from ccr.archive.integrity import (
    CHECKPOINT_METADATA_LIMIT, PENDING_CONTEXT_LIMIT, _evidence_name, _retained_name,
    verify_files as _verify_files,
)
from ccr.archive.reader import load_run as _load_run
from ccr.archive.transactions import _append_trace_events, _milestone, _recover_trace, save_manifest as _save_manifest
from ccr.shared.encoding import archive_bytes as _json_bytes
from ccr.shared.git import git as _git
from ccr.shared.json_io import atomic_write, read_bounded, read_json
from ccr.shared.paths import contains as _contains, safe_path
from ccr.workflow import inputs as review_inputs
from ccr.workflow import profiles as review_profiles
from ccr.maintenance import metrics as review_metrics
from ccr.contracts.review import validate as validate_review, validate_reference_semantics
from ccr.reporting.render import render as render_review, render_handoff
from ccr.contracts import preflight as review_preflight
from ccr.contracts import model_usage as review_model_usage
from ccr.archive import trace as review_trace
from ccr.archive import layout as review_layout
from ccr.reporting import projections as review_publication
from ccr.contracts.receipts import is_receipt_reference
from ccr.execution import claims as resource_claims
from ccr.contracts.execution import validate_execution_sources
from ccr.contracts.provenance import validate_check_sources
from ccr.contracts.references import parse_reference, resolve_reference
from ccr.contracts.reference_index import canonical_reference, reference_source_paths
from ccr.contracts.reference_types import INITIAL_PROFILE_HISTORY_REFERENCE, LEGACY_INITIAL_PROFILE_REFERENCE

def _temporary_paths(paths, manifest):
    registered = list(manifest.get('temporary_paths', []))
    repo, root = safe_path(manifest['repository_path']), safe_path(manifest['archive_root'])
    for raw in paths or []:
        path = safe_path(raw)
        if (path == repo or _contains(path, repo) or
                _contains(root, path) or _contains(path, root)):
            raise ValueError('user checkout and retained archive cannot be temporary resources')
        try:
            if not stat.S_ISDIR(path.stat().st_mode):
                raise ValueError('temporary resources must be session/workspace directories')
        except FileNotFoundError:
            pass
        if str(path) not in registered:
            registered.append(str(path))
    return registered

def _temporary_manifests(registered, manifest):
    """Preserve conventional original manifest locations, without reading contents."""
    locations = list(manifest.get('temporary_manifests', []))
    for raw in registered:
        path = safe_path(Path(raw) / 'manifest.json')
        try:
            info = path.stat()
        except FileNotFoundError:
            continue
        if not stat.S_ISREG(info.st_mode):
            raise ValueError('temporary manifest must be a regular file')
        if str(path) not in locations:
            locations.append(str(path))
    return locations

MEASUREMENT_FIELDS = set(review_metrics.COUNTERS) | {
    'usage', 'execution_id', 'run_id', 'input_ids', 'input_id', 'revision', 'snapshot',
    'phase', 'role', 'model', 'harness', 'started_at', 'finished_at', 'elapsed_seconds',
    'executor_invocations', 'status', 'usage_status', 'usage_error', 'unavailable_reason',
    'stdout_bytes', 'stderr_bytes', 'exit_code', 'timed_out', 'workspace', 'output_dir'}


def _digest(data):
    return hashlib.sha256(data).hexdigest()

def _measurements(inputs, unavailable_reason):
    if unavailable_reason is not None and (not isinstance(unavailable_reason, str) or not unavailable_reason.strip()):
        raise ValueError('unavailable reason must be nonempty text')
    runs, sources, seen_ids = [], [], set()
    for raw in inputs or []:
        path = safe_path(raw)
        if str(path) in sources:
            raise ValueError('duplicate measurement input path; only disjoint executions are accepted')
        value = read_json(path)
        if not isinstance(value, dict):
            raise ValueError('measurement input must be one execution object')
        if 'runs' in value or 'summary' in value:
            raise ValueError('inclusive summaries are not execution inputs')
        identifier = value.get('execution_id')
        if identifier is not None:
            if not isinstance(identifier, str) or not identifier.strip() or identifier in seen_ids:
                raise ValueError('duplicate or invalid execution_id')
            seen_ids.add(identifier)
        usage = value.get('usage')
        if usage is not None and not isinstance(usage, dict):
            raise ValueError('invalid usage object')
        reason = value.get('unavailable_reason') or value.get('usage_error') or unavailable_reason
        normalized = review_metrics.normalize_usage({field: usage.get(field) for field in review_metrics.USAGE_FIELDS}
                                                     if isinstance(usage, dict) else None)
        missing = (any(normalized[field] is None for field in review_metrics.TOKEN_FIELDS + ('credits', 'cost'))
                   or any(value.get(field) is None for field in review_metrics.COUNTERS))
        if missing and (not isinstance(reason, str) or not reason.strip()):
            raise ValueError('unknown usage/counters require an unavailable reason')
        runs.append({key: item for key, item in value.items() if key in MEASUREMENT_FIELDS})
        sources.append(str(path))
    if not runs:
        if not unavailable_reason:
            raise ValueError('unknown usage requires --unavailable-reason')
        runs = [{'usage': None, 'unavailable_reason': unavailable_reason}]
    summary = review_metrics.summarize(runs)
    quantitative = list(review_metrics.TOKEN_FIELDS) + ['credits', 'cost']
    known = missing = 0
    for value in runs:
        normalized = review_metrics.normalize_usage({field: value['usage'].get(field) for field in review_metrics.USAGE_FIELDS}
                                                     if isinstance(value.get('usage'), dict) else None)
        for item in [normalized[field] for field in quantitative] + [value.get(field) for field in review_metrics.COUNTERS]:
            known += item is not None
            missing += item is None
    return {'schema_version': 1, 'status': 'partial' if known and missing else 'reported' if known else 'unavailable',
            'runs': runs, 'sources': sources, 'summary': summary,
            'unavailable_reason': unavailable_reason,
            'disjoint_inputs_asserted': bool(inputs),
            'overlap_detection': 'Duplicate paths and explicit execution IDs only; semantic overlap is not detectable.'}

def _validate_model_usage_context(context, source, manifest):
    """Validate the optional private sidecar without mixing it into captured inputs."""
    reference = context.get('model_usage_reference') if isinstance(context, dict) else None
    if reference is None:
        return
    if reference != 'evidence/model-usage.json':
        raise ValueError('model usage reference must identify evidence/model-usage.json')
    try:
        payload = source(reference)
        if len(payload) > review_model_usage.MAX_LEDGER_BYTES:
            raise ValueError('model usage sidecar exceeds the 256 KiB bound')
        ledger = json.loads(payload.decode('utf-8'))
    except (AttributeError, UnicodeDecodeError, json.JSONDecodeError, OSError, ValueError) as exc:
        raise ValueError('selected model usage evidence is unreadable: ' + str(exc)) from exc
    expected_review_id = ('CR-' + manifest['run_id']) if isinstance(manifest.get('run_id'), str) else None
    issues = review_model_usage.validate_model_usage(
        ledger, review_id=expected_review_id, harness_id=manifest.get('harness_id'))
    if issues:
        raise ValueError('selected model usage evidence is invalid: ' + issues[0]['message'])

def _present_resources(registered):
    present = []
    for raw in registered:
        try:
            safe_path(raw).stat()
            present.append(raw)
        except FileNotFoundError:
            pass
        # PermissionError and other unverifiable states deliberately propagate.
    return present

def _execution_gate(run, manifest, value, contents):
    """Read only selected source bytes and observed same-run trace; no archive scan."""
    def source(name):
        if not _retained_name(name):
            raise ValueError('execution reference must identify retained local evidence')
        if name in contents:
            return contents[name]
        if name in manifest['hashes']:
            return safe_path(run / name).read_bytes()
        raise ValueError('execution source is not selected for retention: ' + name)

    context = json.loads(source('evidence/context.json'))
    if not isinstance(context, dict):
        raise ValueError('execution context must be an object')
    _validate_model_usage_context(context, source, manifest)
    events = [json.loads(line) for line in source(review_trace.NAME).splitlines()]
    execution = value['coverage']['execution']
    requested = {row['reference'] for key in ('plan', 'results') for row in execution[key]}
    requested.update(row['source'] for row in execution['fallbacks'])
    for event in events:
        if isinstance(event, dict) and event.get('kind') == 'agent' and event.get('status') == 'unchanged':
            provenance = event.get('provenance')
            source_reference = provenance.get('source') if isinstance(provenance, dict) else None
            if isinstance(source_reference, str):
                requested.add(source_reference)
    index_reference = context.get('reference_index')
    checks = value.get('checks', []) if isinstance(value.get('checks'), list) else []
    for check in checks:
        if not isinstance(check, dict):
            continue
        receipt_ref = check.get('reference')
        if is_receipt_reference(receipt_ref, check.get('id')):
            requested.add(receipt_ref)
            try:
                receipt = json.loads(source(receipt_ref).decode('utf-8'))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            if isinstance(receipt, dict):
                for stream_name in ('stdout', 'stderr'):
                    stream = receipt.get(stream_name)
                    if isinstance(stream, dict) and isinstance(stream.get('reference'), str):
                        requested.add(stream['reference'])
    if index_reference is not None:
        if index_reference != 'evidence/reference-index.json':
            raise ValueError('guided reference_index must use evidence/reference-index.json')
        requested.add(index_reference)
        requested.update(row['reference'] for row in value.get('checks', [])
                         if isinstance(row, dict) and isinstance(row.get('reference'), str))
    captured_inputs = manifest.get('review_inputs')
    if captured_inputs is not None:
        supplied_inputs = context.get('review_inputs')
        if supplied_inputs is None:
            raise ValueError('retained execution context must preserve captured review_inputs')
        normalized_inputs = _capture_review_inputs(
            supplied_inputs, manifest['scope'], manifest['profile_history'][-1]['profile'],
            'retained context review_inputs',
            logical_scope_identity=manifest.get('logical_scope', {}).get('identity'))
        if normalized_inputs != captured_inputs:
            raise ValueError('retained context review_inputs differ from the initial captured identities')
        requested.update(captured_inputs['sources'])
    if manifest.get('schema_version') == 8:
        registry = manifest.get('assignment_registry')
        if not isinstance(registry, list):
            raise ValueError('archive assignment registry is missing; register the execution plan before retention')
        if context.get('execution_plan') != registry:
            raise ValueError('retained context execution_plan differs from the durable assignment registry')
        requested.update(row['reference'] for row in registry)
    history = context.get('profile_history', [dict(profile=context.get('profile'), reference=context.get('profile_reference'))])
    if not isinstance(history, list) or any(not isinstance(row, dict) or not isinstance(row.get('reference'), str) for row in history):
        raise ValueError('execution context needs observed profile source/history')
    requested.update(INITIAL_PROFILE_HISTORY_REFERENCE
                     if row.get('id') == 'S001'
                     and row.get('reference') == LEGACY_INITIAL_PROFILE_REFERENCE
                     else row['reference'] for row in history)
    references = set()
    resolved = {}
    selected_sources = {name: raw for name, raw in contents.items()
                        if isinstance(name, str) and name.startswith('evidence/')
                        and isinstance(raw, bytes)}
    reference_index = None
    aliases = {}
    index_bytes = None
    if index_reference is not None:
        try:
            index_bytes = source(index_reference)
            reference_index = json.loads(index_bytes.decode('utf-8'))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise ValueError('selected reference index is unreadable: ' + str(exc)) from exc
        if not isinstance(reference_index, dict):
            raise ValueError('selected reference index must be a JSON object')
        aliases = reference_index.get('aliases', {})
        if not isinstance(aliases, dict):
            raise ValueError('selected reference index aliases must be an object')
        try:
            requested.update(reference_source_paths(reference_index))
        except (TypeError, ValueError) as exc:
            raise ValueError('selected reference index source selection is invalid: ' + str(exc)) from exc
        selected_sources[index_reference] = index_bytes
    for event in events:
        if not isinstance(event, dict) or event.get('kind') != 'agent' or event.get('status') != 'unchanged':
            continue
        provenance = event.get('provenance')
        source_reference = provenance.get('source') if isinstance(provenance, dict) else None
        try:
            canonical_source = canonical_reference(source_reference, aliases)
            source_path, _ = parse_reference(canonical_source, field='dispatch identity source')
        except (TypeError, ValueError) as exc:
            raise ValueError('dispatch identity source is invalid: ' + str(exc)) from exc
        if source_path not in contents and source_path not in manifest['hashes']:
            raise ValueError('dispatch identity source is not selected for retention: ' + source_path)
    for reference in requested:
        try:
            canonical = canonical_reference(reference, aliases)
        except ValueError as exc:
            raise ValueError('execution source alias is invalid: ' + str(exc)) from exc
        path, _ = parse_reference(canonical, field='execution source')
        raw = source(path)
        selected_sources[path] = raw
        resolved[reference] = resolve_reference(
            canonical, {path: raw}, field='execution source')
        references.add(reference)
    if captured_inputs is not None:
        for reference, expected in captured_inputs['sources'].items():
            canonical = canonical_reference(reference, aliases)
            name, _ = parse_reference(canonical, field='captured review input')
            if _digest(source(name)) != expected:
                raise ValueError('selected external review input differs from its captured SHA-256 identity: '
                                 + reference)
        description = value.get('description') if isinstance(value.get('description'), dict) else {}
        if ('description_identity' in captured_inputs
                and description.get('identity') != captured_inputs['description_identity']):
            raise ValueError('final review description identity differs from the initial captured input')
    for row in history:
        source_reference = (INITIAL_PROFILE_HISTORY_REFERENCE
                            if row.get('id') == 'S001'
                            and row.get('reference') == LEGACY_INITIAL_PROFILE_REFERENCE
                            else row['reference'])
        if resolved.get(source_reference) != row.get('profile'):
            raise ValueError('profile source fragment differs from declared transition')
        if source_reference != row['reference']:
            resolved[row['reference']] = resolved[source_reference]
            references.add(row['reference'])
    errors = validate_execution_sources(value, context, events, references,
                                       assignment_registry=manifest.get('assignment_registry'))
    for event in events:
        if not isinstance(event, dict) or event.get('kind') != 'agent' or event.get('status') != 'unchanged':
            continue
        provenance = event.get('provenance')
        source_reference = provenance.get('source') if isinstance(provenance, dict) else None
        observed = resolved.get(source_reference) if isinstance(source_reference, str) else None
        if not isinstance(observed, dict) or observed.get('executor') != event.get('executor'):
            errors.append('coverage.execution.sources: dispatch identity source does not match recorded executor')
    if index_reference is not None:
        packets = []
        for group_name in ('plan', 'results'):
            for row in execution.get(group_name, []):
                if not isinstance(row, dict) or not isinstance(row.get('reference'), str):
                    continue
                try:
                    canonical = canonical_reference(
                        row['reference'], aliases)
                    path, _ = parse_reference(canonical, field='selected execution packet')
                    raw = selected_sources.get(path)
                    if raw is not None and path.endswith('.json'):
                        packet_value = json.loads(raw.decode('utf-8'))
                        if isinstance(packet_value, dict) and any(
                                key in packet_value for key in ('check_ids', 'findings', 'decisions')):
                            packets.append(packet_value)
                except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
                    # The reference and its source already receive a bounded diagnostic below.
                    continue
        errors.extend(validate_reference_semantics(
            value, context, reference_index, selected_sources, packets))
    if value.get('schema_version') in (9, 10):
        errors.extend(validate_check_sources(value, context.get('executors'),
                                             receipt_sources=selected_sources))
        errors.extend(validate_check_sources(value, manifest.get('executors', []),
                                             receipt_sources=selected_sources))
        # Both retained sources must bind each used identity to the same inputs.
        declared = context.get('executors', [])
        projected = manifest.get('executors', [])
        if isinstance(declared, list) and all(isinstance(row, dict) for row in declared + projected):
            for check in value['checks']:
                identity = check['execution']['executor']
                if identity is None:
                    continue
                source_row = next((row for row in declared if row.get('executor') == identity), {})
                closure_row = next((row for row in projected if row.get('executor') == identity), {})
                if any(source_row.get(key) != closure_row.get(key) for key in ('revision', 'snapshot')):
                    errors.append('checks.execution.sources: retained context and closure binding differ')
    if errors:
        raise ValueError('; '.join(errors))

def _retain_data(run, manifest, marker, contents, *, record_retention=True):
    # Persist pending intent before replacing files. Old and planned digests allow a
    # safe retry after interruption, without accepting arbitrary user modifications.
    manifest.update(state='retaining', cleanup='pending', retained=False,
                    planned_hashes={name: _digest(data) for name, data in contents.items()})
    marker = _save_manifest(run, manifest, marker)
    for name, data in contents.items():
        if name.startswith('evidence/'):
            safe_path(run / 'evidence').mkdir(exist_ok=True)
        atomic_write(run / name, data)
    hashes = dict(manifest['hashes'])
    hashes.update(manifest.pop('planned_hashes'))
    manifest.update(state='closing', retained=True, hashes=hashes)
    events = []
    if record_retention:
        selected = sum(name.startswith('evidence/') for name in contents)
        events.append(_milestone('retain', 'Canonical final record retained with ' + str(selected) + ' selected evidence files',
                                 status='retained', evidence=['review.json', 'informe.md', 'cierre.json#hashes']))
    if 'handoff.md' in contents:
        events.append(_milestone('handoff', 'Requested handoff generated from canonical review',
                                evidence=['review.json', 'handoff.md']))
    if events:
        _append_trace_events(run, manifest, marker, events)
    else:
        _save_manifest(run, manifest, marker)
    return manifest

def _executors(context_input, manifest, temporary):
    """Project existing neutral context facts; verify Git roots/HEAD, not check truth."""
    previous = manifest.get('executors', [])
    if context_input is None:
        return previous
    context = _input_object(context_input, 'execution context')
    if not isinstance(context, dict) or not isinstance(context.get('executors'), list):
        raise ValueError('context.executors must be an array')
    entries = {item['executor']: item for item in previous}
    seen = set()
    for raw in context['executors']:
        required = {'executor', 'method', 'workspace', 'revision', 'snapshot', 'manifest',
                    'dependencies', 'dependency_reason'}
        if not isinstance(raw, dict) or set(raw) - required - {'authorization'} or not required.issubset(raw):
            raise ValueError('invalid executor provenance fields')
        entry = dict(raw)
        for key in ('executor', 'revision', 'dependency_reason'):
            if not isinstance(entry[key], str) or not entry[key].strip():
                raise ValueError('executor ' + key + ' must be nonempty text')
        if entry['executor'] in seen:
            raise ValueError('duplicate executor identity')
        seen.add(entry['executor'])
        if entry['method'] not in {'git-worktree', 'native-worktree', 'authorized-copy'}:
            raise ValueError('unsupported executor isolation method')
        if entry['dependencies'] not in {'shared', 'local', 'none'}:
            raise ValueError('invalid dependency strategy')
        workspace = safe_path(entry['workspace'])
        if not workspace.is_dir() or not any(_contains(Path(path), workspace) for path in temporary):
            raise ValueError('executor workspace must be an existing registered temporary resource')
        entry['workspace'] = str(workspace)
        baseline = entry['revision'] == manifest['scope']['base'] and entry['snapshot'] is None
        if entry['snapshot'] != manifest['scope']['snapshot'] and not baseline:
            raise ValueError('executor snapshot differs from pinned scope')
        if entry['revision'] not in {manifest['scope']['head'], manifest['scope']['base']}:
            raise ValueError('executor revision differs from pinned scope')
        if entry['method'] == 'authorized-copy':
            if not isinstance(entry.get('authorization'), str) or not entry['authorization'].strip():
                raise ValueError('copy execution requires explicit user authorization provenance')
        else:
            repo = Path(manifest['repository_path'])
            if safe_path(_git(workspace, 'rev-parse', '--show-toplevel')) != workspace:
                raise ValueError('executor must be an actual worktree root')
            def common(path):
                value = Path(_git(path, 'rev-parse', '--git-common-dir'))
                return (path / value).resolve() if not value.is_absolute() else value.resolve()
            if common(workspace) != common(repo) or _git(workspace, 'rev-parse', 'HEAD') != entry['revision']:
                raise ValueError('executor worktree repository or HEAD differs from provenance')
        if entry['manifest'] is not None:
            path = safe_path(entry['manifest'])
            if not path.is_file() or not any(_contains(Path(raw_path), path) for raw_path in temporary):
                raise ValueError('executor manifest must exist inside registered temporary resources')
            entry['manifest'] = str(path)
        if entry['executor'] in entries and entries[entry['executor']] != entry:
            raise ValueError('retained executor identity cannot be rewritten; use a new executor ID')
        entries[entry['executor']] = entry
    return list(entries.values())

def _handoff_context(input_file, value, contents, manifest):
    """Retain only requested, bounded context with references that survive cleanup."""
    context = read_json(input_file)
    allowed = {'source_record', 'source_report', 'requirements', 'plan', 'decisions_pending'}
    if not isinstance(context, dict) or set(context) - allowed or len(_json_bytes(context)) > 32768:
        raise ValueError('handoff context must contain only bounded handoff fields')
    context = copy.deepcopy(context)
    for field, source in [('source_record', 'review.json'), ('source_report', 'informe.md')]:
        if field in context and context[field] != source:
            raise ValueError('handoff source references must identify the retained canonical record and report')
        context[field] = source
    for field in ('requirements', 'plan', 'decisions_pending'):
        entries = context.get(field, [])
        if not isinstance(entries, list) or len(entries) > 24:
            raise ValueError('handoff context arrays must contain at most 24 entries')
        for item in entries:
            if isinstance(item, str):
                if len(item) > 2000:
                    raise ValueError('unbounded handoff context text')
                reference = item
            elif isinstance(item, dict) and field != 'decisions_pending':
                reference = item.get('reference')
            else:
                raise ValueError('invalid handoff context entry')
            if field == 'decisions_pending':
                continue
            if not isinstance(reference, str):
                raise ValueError('handoff provenance must identify an evidence reference')
            parsed = urlsplit(reference)
            if parsed.scheme in {'http', 'https'} and parsed.netloc and not parsed.username:
                continue
            if (not reference.startswith('evidence/') or not _retained_name(reference)
                    or reference not in contents and reference not in manifest['hashes']):
                raise ValueError('local handoff provenance must reference selected retained evidence')
    # The canonical renderer validates exact entry shapes and captured identities.
    render_handoff(value, context)
    return context

@_locked_run
def retain(run_dir, input_file=None, measurement_inputs=None, unavailable_reason=None, temporary_paths=None, evidence_inputs=None, context_input=None, handoff=False, handoff_context_input=None, *, expected_schema=None):
    run, manifest, marker = _load_run(run_dir)
    marker = _recover_trace(run, manifest, marker)
    if manifest['state'] == 'complete':
        raise ValueError('completed review history is immutable; prepare a new run with --previous-run')
    _verify_files(run, manifest)
    temporary = _temporary_paths(temporary_paths, manifest)
    if manifest['schema_version'] == 8:
        claim_manifest = copy.deepcopy(manifest)
        claim_manifest.update(_claim_run_dir=str(run), temporary_paths=temporary)
        resource_plans = resource_claims.plan_resource_registration(temporary, claim_manifest)
        if any(plan['action'] not in {'not_workspace', 'existing'} for plan in resource_plans):
            raise ValueError('register and verify every review workspace before retention')
    if input_file is None:
        if manifest['schema_version'] != 8 or not isinstance(manifest.get('checkpoint'), dict):
            raise ValueError('retention requires an explicit final review input or a provisional final checkpoint')
        candidate = run / 'pending' / 'review.json'
        if not candidate.is_file():
            raise ValueError('provisional checkpoint has no structurally valid final review to promote')
        input_file = candidate
    if manifest['schema_version'] == 8 and isinstance(manifest.get('checkpoint'), dict):
        if context_input is None and (run / 'pending' / 'context.json').is_file():
            context_input = run / 'pending' / 'context.json'
        if evidence_inputs is None:
            evidence_inputs = [run / name for name in manifest.get('pending_hashes', {})
                               if name.startswith('pending/evidence/')]
    value = read_json(input_file, max_bytes=CHECKPOINT_METADATA_LIMIT)
    if not isinstance(value, dict):
        raise ValueError('final review input must be a JSON object')
    if expected_schema is not None:
        if type(expected_schema) is not int or expected_schema not in range(1, 11):
            raise ValueError('expected schema must be a supported integer 1–10')
        if not isinstance(value, dict) or value.get('schema_version') != expected_schema:
            raise ValueError('expected schema ' + str(expected_schema) + ' differs from final review schema')
    if manifest['schema_version'] == 8:
        if value.get('schema_version') != 10:
            raise ValueError('archive 8 requires final review schema 10')
        coverage = value.get('coverage')
        execution = coverage.get('execution') if isinstance(coverage, dict) else None
        if not isinstance(execution, dict):
            raise ValueError('final coverage and coverage.execution must be JSON objects')
        if execution.get('profile_history') != manifest.get('profile_history'):
            raise ValueError('final profile history differs from the archive selections')
        if manifest.get('operation', {}).get('disposition') != 'open':
            raise ValueError('review operation is not open; recover or restart before retaining')
    if handoff_context_input is not None and not handoff:
        raise ValueError('--handoff-context-input requires an explicit --handoff request')
    errors = validate_review(value)
    if errors or not isinstance(value, dict) or value.get('stage') != 'final':
        raise ValueError('; '.join(errors) if errors else 'only final review records can be retained')
    if value['scope'] != manifest['scope']:
        raise ValueError('final review scope differs from the pinned scope')
    if value.get('schema_version') in (6, 7, 8, 9, 10) and value.get('review_id') != 'CR-' + manifest.get('run_id', ''):
        raise ValueError('final review_id must bind to archive run identity: CR-' + manifest.get('run_id', ''))
    if manifest['schema_version'] == 8:
        context = _input_object(context_input, 'execution context') if context_input is not None else None
        preflight_sources = ({'evidence/context.json': _json_bytes(context)} if context is not None else {})
        for raw in evidence_inputs or []:
            path = safe_path(raw)
            if not stat.S_ISREG(path.stat().st_mode):
                raise ValueError('selected preflight evidence must be a regular file')
            name = 'evidence/' + _evidence_name(path.name)
            if name in preflight_sources:
                raise ValueError('duplicate selected preflight evidence name: ' + name)
            preflight_sources[name] = path.read_bytes()
        phase_preflight = review_preflight.validate_preflight(
            phase='retain', manifest=manifest, logical_scope=manifest.get('logical_scope'),
            selection=manifest['profile_history'][-1], context=context, record=value,
            sources=preflight_sources)
        if not phase_preflight['ready']:
            raise ValueError('; '.join(issue['message'] for issue in phase_preflight['issues']))
    declared_residuals = [str(safe_path(raw)) for raw in value['resources']['residuals']]
    if set(declared_residuals) - set(temporary):
        raise ValueError('register declared temporary residuals before retaining cleanup evidence')
    present = _present_resources(temporary)
    if temporary:
        value = copy.deepcopy(value)
        value['resources'].update(cleanup='pending', residuals=present)
    executors = _executors(context_input, manifest, temporary)
    contents = {'review.json': _json_bytes(value), 'informe.md': render_review(value).encode('utf-8')}
    if measurement_inputs or unavailable_reason is not None:
        measurements = _measurements(measurement_inputs, unavailable_reason)
        contents['measurements.json'] = _json_bytes(measurements)
    elif manifest['schema_version'] == 1:
        contents['measurements.json'] = safe_path(run / 'measurements.json').read_bytes()
    contents.update(_evidence_contents(run, manifest, evidence_inputs,
        create_directory=value.get('schema_version') not in (8, 9, 10), reserve_context=context_input is not None,
        context_input=context_input))
    if value.get('schema_version') in (8, 9, 10):
        if context_input is not None:
            _check_evidence_target(run, manifest, 'evidence/context.json')
            context_bytes = _json_bytes(read_json(context_input, max_bytes=PENDING_CONTEXT_LIMIT))
            if len(context_bytes) > 131072:
                raise ValueError('execution context exceeds bounded retained context size')
            if ('evidence/context.json' in contents
                    and read_json(context_input) != json.loads(contents['evidence/context.json'])):
                raise ValueError('selected execution context conflicts with context_input')
            contents['evidence/context.json'] = context_bytes
        _execution_gate(run, dict(manifest, executors=executors), value, contents)
    if handoff_context_input is not None:
        manifest['handoff_context'] = _handoff_context(handoff_context_input, value, contents, manifest)
    if handoff or 'handoff.md' in manifest['hashes'] or 'handoff.md' in manifest.get('planned_hashes', {}):
        manifest.setdefault('handoff_context', {'source_record': 'review.json', 'source_report': 'informe.md'})
        contents['handoff.md'] = render_handoff(value, manifest.get('handoff_context')).encode('utf-8')
    manifest['temporary_paths'] = temporary
    manifest['temporary_manifests'] = _temporary_manifests(temporary, manifest)
    manifest['residuals'] = present
    manifest['executors'] = executors
    return _retain_data(run, manifest, marker, contents)
