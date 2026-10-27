"""Bounded checkpoint planning and recoverable staged commits."""
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path, PurePosixPath
import stat
import uuid

from ccr.archive.coordination import _locked_run
from ccr.archive.evidence import _capture_review_inputs, _input_object
from ccr.archive.integrity import (
    CHECKPOINT_EVIDENCE_COUNT_LIMIT, CHECKPOINT_EVIDENCE_LIMIT,
    CHECKPOINT_METADATA_LIMIT, PENDING_CONTEXT_LIMIT, verify_files as _verify_files,
)
from ccr.archive.reader import load_run as _load_run
from ccr.archive.retention import _execution_gate, _validate_model_usage_context
from ccr.archive.transactions import _archive_write, recover_trace as _recover_trace, save_manifest as _save_manifest
from ccr.contracts import review as review_contract
from ccr.reporting.render import render as render_review
from ccr.shared.encoding import archive_bytes as _json_bytes
from ccr.shared.json_io import atomic_write, read_bounded, read_json
from ccr.shared.paths import safe_path
from ccr.workflow import profiles as review_profiles
from ccr.archive import layout as review_layout
from ccr.archive import trace as review_trace
from ccr.archive.integrity import _evidence_name


def _digest(data):
    return hashlib.sha256(data).hexdigest()

def _checkpoint_diagnostics(values):
    if values is None:
        return []
    if not isinstance(values, list) or len(values) > 64:
        raise ValueError('checkpoint gate errors must be a bounded array')
    result = []
    for value in values:
        if not isinstance(value, str) or not value.strip() or len(value) > 2000:
            raise ValueError('checkpoint gate error must be bounded nonempty text')
        if value not in result:
            result.append(value)
    if sum(len(value.encode('utf-8')) for value in result) > 131072:
        raise ValueError('checkpoint gate errors exceed the metadata limit')
    return result

def _checkpoint_input_files(run, manifest, context_input, evidence_inputs, input_record,
                            phase, gate_errors, max_evidence_bytes):
    if phase not in review_profiles.PHASES - {'prepare'}:
        raise ValueError('checkpoint phase must identify review work after preparation')
    if (type(max_evidence_bytes) is not int or not 0 <= max_evidence_bytes <= CHECKPOINT_EVIDENCE_LIMIT):
        raise ValueError('checkpoint evidence limit must be between 0 and 64 MiB')
    context_path = safe_path(context_input)
    if not stat.S_ISREG(context_path.stat().st_mode):
        raise ValueError('checkpoint context must be a regular JSON file')
    try:
        context = read_json(context_path, max_bytes=PENDING_CONTEXT_LIMIT)
    except ValueError as exc:
        if 'input exceeds' in str(exc):
            raise ValueError('execution context exceeds the 131072-byte checkpoint limit') from exc
        raise
    if not isinstance(context, dict):
        raise ValueError('checkpoint context must be a JSON object')
    captured_inputs = manifest.get('review_inputs')
    supplied_inputs = context.get('review_inputs')
    if captured_inputs is not None:
        if supplied_inputs is None:
            raise ValueError('checkpoint context must preserve registered review_inputs')
        normalized_inputs = _capture_review_inputs(
            supplied_inputs, manifest['scope'], manifest['profile_history'][-1]['profile'],
            'checkpoint context review_inputs',
            logical_scope_identity=manifest.get('logical_scope', {}).get('identity'))
        if normalized_inputs != captured_inputs:
            raise ValueError('checkpoint context review_inputs differ from the initial captured identities')
    elif supplied_inputs is not None:
        raise ValueError('capture review_inputs during prepare or register before checkpoint work')
    context_bytes = _json_bytes(context)
    if len(context_bytes) > PENDING_CONTEXT_LIMIT:
        raise ValueError('execution context exceeds the 131072-byte checkpoint limit')
    payloads = {'pending/context.json': context_bytes}
    source_contents = {'evidence/context.json': context_bytes}
    evidence_total = 0
    evidence_count = 0
    seen = {'context.json'.casefold()}
    previous_names = {name.casefold(): name for name in manifest.get('pending_hashes', {})}
    for raw in evidence_inputs or []:
        source = safe_path(raw)
        if not stat.S_ISREG(source.stat().st_mode):
            raise ValueError('selected checkpoint evidence must be a regular file')
        name = _evidence_name(source.name)
        if name.casefold() in seen:
            raise ValueError('duplicate selected checkpoint evidence name: ' + name)
        seen.add(name.casefold())
        destination = 'pending/evidence/' + name
        if destination.casefold() in previous_names and previous_names[destination.casefold()] != destination:
            raise ValueError('case-insensitive checkpoint evidence capitalization differs from prior checkpoint: ' + name)
        evidence_count += 1
        if evidence_count > CHECKPOINT_EVIDENCE_COUNT_LIMIT:
            raise ValueError('checkpoint accepts at most 64 selected evidence files')
        data = read_bounded(source, max_evidence_bytes - evidence_total)
        evidence_total += len(data)
        if evidence_total > max_evidence_bytes:
            raise ValueError('selected checkpoint evidence exceeds the configured byte limit')
        payloads['pending/evidence/' + name] = data
        source_contents['evidence/' + name] = data

    for name, digest in manifest.get('pending_hashes', {}).items():
        if name.startswith('pending/evidence/') and name not in payloads:
            remaining = max_evidence_bytes - evidence_total
            prior = read_bounded(run / name, remaining)
            if _digest(prior) != digest:
                raise ValueError('modified prior checkpoint evidence: ' + name)
            source_contents['evidence/' + name.split('/', 2)[2]] = prior
            evidence_total += len(prior)

    _validate_model_usage_context(context, lambda name: source_contents.get(name), manifest)

    diagnostics = _checkpoint_diagnostics(gate_errors)
    final = None
    if input_record is not None:
        try:
            final = _input_object(input_record, 'checkpoint final review', max_bytes=CHECKPOINT_METADATA_LIMIT)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            diagnostics.append('final review input could not be parsed: ' + str(exc)[:500])
        else:
            errors = review_contract.validate(final)
            if errors or final.get('stage') != 'final':
                diagnostics.extend('final structure: ' + error for error in errors[:48])
                if not errors:
                    diagnostics.append('final structure: stage must be final')
            else:
                if final.get('schema_version') not in (10, 11):
                    diagnostics.append('final structure: archive 8 checkpoints require review schema 10 or 11')
                else:
                    if final.get('review_id') != 'CR-' + manifest['run_id']:
                        diagnostics.append('archive identity gate: review ID differs from the run')
                    execution = final.get('coverage', {}).get('execution', {})
                    if execution.get('profile_history') != manifest.get('profile_history'):
                        diagnostics.append('archive profile history differs from the captured run selections')
                    try:
                        _execution_gate(run, manifest, final, source_contents)
                    except (OSError, ValueError, TypeError, KeyError) as exc:
                        diagnostics.append('final source gate: ' + str(exc)[:1500])
                    payloads['pending/review.json'] = _json_bytes(final)
                    payloads['pending/informe.md'] = render_review(final).encode('utf-8')

    diagnostics = _checkpoint_diagnostics(diagnostics)
    selected_names = set(payloads)
    previous = {}
    pending_removals = manifest.get('checkpoint_transaction', {}).get('removed_hashes', {})
    for name, digest in manifest.get('pending_hashes', {}).items():
        if name not in payloads and name not in pending_removals:
            if name.startswith('pending/evidence/'):
                remaining = max_evidence_bytes - sum(
                    len(data) for selected, data in previous.items()
                    if selected.startswith('pending/evidence/'))
                previous[name] = read_bounded(run / name, remaining)
            elif name == 'pending/context.json':
                previous[name] = read_bounded(run / name, PENDING_CONTEXT_LIMIT)
            else:
                remaining = CHECKPOINT_METADATA_LIMIT - sum(
                    len(data) for selected, data in previous.items()
                    if not selected.startswith('pending/evidence/'))
                previous[name] = read_bounded(run / name, remaining)
            if _digest(previous[name]) != digest:
                raise ValueError('modified prior checkpoint bytes: ' + name)
    combined = dict(previous, **payloads)
    metadata_size = sum(len(data) for name, data in combined.items()
                        if name.lower().endswith(('.json', '.md')))
    if metadata_size > CHECKPOINT_METADATA_LIMIT:
        raise ValueError('checkpoint JSON/Markdown metadata exceeds 16 MiB')
    total_evidence = sum(len(data) for name, data in combined.items() if name.startswith('pending/evidence/'))
    if total_evidence > max_evidence_bytes:
        raise ValueError('cumulative checkpoint evidence exceeds the configured byte limit')
    if sum(name.startswith('pending/evidence/') for name in combined) > CHECKPOINT_EVIDENCE_COUNT_LIMIT:
        raise ValueError('checkpoint inventory exceeds 64 selected evidence files')
    signature = _digest(_json_bytes({'phase': phase,
                                     'input_hashes': {name: _digest(data) for name, data in sorted(payloads.items())},
                                     'gate_errors': diagnostics}))
    return combined, diagnostics, signature, selected_names

def _checkpoint_commit(run, manifest, marker, transaction, payloads):
    planned = transaction['planned_hashes']
    staging = transaction.get('staging', {})
    for name, expected in planned.items():
        data = payloads.get(name)
        read_limit = (CHECKPOINT_EVIDENCE_LIMIT if name.startswith('pending/evidence/')
                      else CHECKPOINT_METADATA_LIMIT)
        if data is None:
            path = safe_path(run / name)
            try:
                data = read_bounded(path, read_limit)
            except FileNotFoundError as exc:
                raise ValueError('retry checkpoint with missing selected input: ' + name) from exc
        if _digest(data) != expected:
            raise ValueError('checkpoint retry input differs from its preserved intent: ' + name)
        path = safe_path(run / name)
        try:
            current = read_bounded(path, read_limit)
        except FileNotFoundError:
            current = None
        if current is not None and _digest(current) == expected:
            staged = staging.get(name)
            if staged is not None:
                stage_path = safe_path(run / staged['name'])
                try:
                    stage_path.unlink()
                except FileNotFoundError:
                    pass
            continue
        allowed_old = transaction['previous_hashes'].get(name)
        if current is not None and _digest(current) != allowed_old:
            raise ValueError('foreign or modified pending checkpoint bytes: ' + name)
        if name.startswith('pending/evidence/'):
            safe_path(run / 'pending' / 'evidence').mkdir(parents=True, exist_ok=True)
        else:
            safe_path(run / 'pending').mkdir(exist_ok=True)
        staged = staging.get(name)
        if staged is not None:
            stage_path = safe_path(run / staged['name'])
            try:
                staged_data = read_bounded(stage_path, read_limit)
            except FileNotFoundError:
                staged_data = None
            if staged_data is not None:
                if _digest(staged_data) == expected:
                    os.replace(stage_path, path)
                    continue
                stage_path.unlink()
            atomic_write(path, data, staging_path=stage_path)
        else:
            atomic_write(path, data)
    for name, expected in transaction['removed_hashes'].items():
        path = safe_path(run / name)
        try:
            current = path.read_bytes()
        except FileNotFoundError:
            continue
        if _digest(current) != expected:
            raise ValueError('foreign or modified pending checkpoint bytes: ' + name)
        path.unlink()
    manifest['pending_hashes'] = planned
    manifest['checkpoint'] = transaction['checkpoint']
    manifest.pop('checkpoint_transaction', None)
    _save_manifest(run, manifest, marker)
    return manifest

@_locked_run
def checkpoint(run_dir, *, context_input, evidence_inputs=None, input_record=None, phase,
               gate_errors=None, max_evidence_bytes=CHECKPOINT_EVIDENCE_LIMIT):
    """Preserve explicitly selected provisional inputs/results without retaining a verdict."""
    run, manifest, marker = _load_run(run_dir)
    if manifest['schema_version'] != 8:
        raise ValueError('provisional checkpoints require archive 8')
    marker = _recover_trace(run, manifest, marker)
    _verify_files(run, manifest, allow_checkpoint_transaction=True)
    if manifest['state'] == 'complete' or manifest.get('operation', {}).get('disposition') in {'complete', 'superseded'}:
        raise ValueError('completed or superseded review cannot accept a checkpoint')
    payloads, diagnostics, signature, selected_names = _checkpoint_input_files(
        run, manifest, context_input, evidence_inputs, input_record, phase, gate_errors, max_evidence_bytes)
    transaction = manifest.get('checkpoint_transaction')
    if transaction is None:
        current = manifest.get('checkpoint')
        if isinstance(current, dict) and current.get('input_signature') == signature:
            return current
        prior_hashes = manifest.get('pending_hashes', {})
        removed_hashes = {}
        if 'pending/review.json' not in selected_names:
            removed_hashes = {name: prior_hashes[name]
                              for name in ('pending/review.json', 'pending/informe.md')
                              if name in prior_hashes}
        planned = {name: digest for name, digest in prior_hashes.items() if name not in removed_hashes}
        planned.update({name: _digest(payloads[name]) for name in selected_names})
        if len({name.casefold() for name in planned}) != len(planned):
            raise ValueError('case-insensitive collisions in planned checkpoint inventory')
        sequence = int(current['id'][1:]) + 1 if isinstance(current, dict) else 1
        inventory = []
        for name, digest in sorted(planned.items()):
            if name in payloads:
                data = payloads[name]
            elif name.startswith('pending/evidence/'):
                data = read_bounded(run / name, CHECKPOINT_EVIDENCE_LIMIT)
            elif name == 'pending/context.json':
                data = read_bounded(run / name, PENDING_CONTEXT_LIMIT)
            else:
                data = read_bounded(run / name, CHECKPOINT_METADATA_LIMIT)
            inventory.append({'name': name, 'size': len(data), 'sha256': digest})
        checkpoint_record = {'id': 'K' + str(sequence).zfill(3), 'phase': phase,
                             'recorded_at': datetime.now(timezone.utc).isoformat(),
                             'input_signature': signature,
                             'inventory': inventory,
                             'gate_errors': diagnostics}
        transaction = {'input_signature': signature, 'previous_hashes': prior_hashes,
                       'planned_hashes': planned, 'removed_hashes': removed_hashes,
                       'checkpoint': checkpoint_record}
        transaction['staging'] = {}
        for name in selected_names:
            target = PurePosixPath(name)
            staging_name = str(target.parent / ('.' + target.name + '.' + uuid.uuid4().hex + '.tmp'))
            transaction['staging'][name] = {'name': staging_name, 'sha256': planned[name]}
        manifest['checkpoint_transaction'] = transaction
        marker = _save_manifest(run, manifest, marker)
    elif transaction['input_signature'] != signature:
        raise ValueError('a different checkpoint is already pending; retry its selected inputs first')
    planned = transaction['planned_hashes']
    for name in planned:
        if name not in payloads:
            path = safe_path(run / name)
            try:
                payloads[name] = path.read_bytes()
            except FileNotFoundError:
                pass
    manifest = _checkpoint_commit(run, manifest, marker, transaction, payloads)
    return manifest['checkpoint']
