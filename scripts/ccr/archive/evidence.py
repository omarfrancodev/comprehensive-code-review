"""Bounded capture and preparation of archive evidence bytes."""
import copy
import hashlib
import json
import os
from pathlib import Path
import stat

from ccr.archive.integrity import _evidence_name, PENDING_CONTEXT_LIMIT
from ccr.contracts.references import parse_reference
from ccr.shared.encoding import archive_bytes as _json_bytes
from ccr.shared.json_io import read_json
from ccr.shared.paths import safe_path
from ccr.workflow import inputs as review_inputs


def _digest(data):
    return hashlib.sha256(data).hexdigest()

def _input_object(value, label, *, max_bytes=None):
    result = read_json(value, max_bytes=max_bytes) if isinstance(value, (str, os.PathLike)) else copy.deepcopy(value)
    if not isinstance(result, dict):
        raise ValueError(label + ' must be a JSON object')
    return result

def _capture_review_inputs(raw, scope, profile, label, *, logical_scope_identity=None):
    """Capture external inputs before work while keeping profile history authoritative."""
    if raw is None:
        return None
    value = review_inputs.normalize_inputs(_input_object(raw, label))
    if logical_scope_identity is not None:
        if ('logical_scope_identity' in value
                and value['logical_scope_identity'] != logical_scope_identity):
            raise ValueError(label + ' logical scope differs from the pinned selector')
        value.setdefault('logical_scope_identity', logical_scope_identity)
    if value['scope'] != scope:
        raise ValueError(label + ' scope differs from the pinned review scope')
    selected_profile = value.pop('profile', None)
    if selected_profile is not None and selected_profile != profile:
        raise ValueError(label + ' profile differs from the captured profile selection')
    for reference in value['sources']:
        path, _ = parse_reference(
            reference, field=label + ' source', allow_alias_key=True)
        if not path.startswith('evidence/'):
            raise ValueError(label + ' source references must identify selected evidence/ files')
    return value

def _check_evidence_target(run, manifest, name):
    target = safe_path(run / name)
    if target.exists() and name not in manifest['hashes'] and name not in manifest.get('planned_hashes', {}):
        raise ValueError('refusing to clobber foreign evidence: ' + name)

def _evidence_contents(run, manifest, inputs, *, create_directory=True, reserve_context=False,
                       context_input=None):
    contents = {}
    seen = {'evidence/context.json'.casefold()} if reserve_context else set()
    for raw in inputs or []:
        source = safe_path(raw)
        if not stat.S_ISREG(source.stat().st_mode):
            raise ValueError('selected evidence must be a regular file')
        name = 'evidence/' + _evidence_name(source.name)
        if name.casefold() in seen:
            raise ValueError('duplicate selected evidence name: ' + name)
        seen.add(name.casefold())
        _check_evidence_target(run, manifest, name)
        contents[name] = source.read_bytes()
    # A retry must finish every previously selected artifact. Existing matching
    # planned bytes are reusable; missing sources require explicit resubmission.
    for name, expected in manifest.get('planned_hashes', {}).items():
        if name.startswith('evidence/') and name not in contents:
            if name == 'evidence/context.json' and context_input is not None:
                context = read_json(context_input, max_bytes=PENDING_CONTEXT_LIMIT)
                data = _json_bytes(context)
                if len(data) > 131072 or _digest(data) != expected:
                    raise ValueError('interrupted selected context differs from its reserved hash')
                contents[name] = data
                continue
            try:
                data = safe_path(run / name).read_bytes()
            except FileNotFoundError as exc:
                raise ValueError('interrupted selected evidence requires its input again: ' + name) from exc
            if _digest(data) != expected:
                raise ValueError('modified interrupted evidence: ' + name)
            contents[name] = data
    if contents and create_directory:
        safe_path(run / 'evidence').mkdir(exist_ok=True)
    return contents
