"""Validation and one-hop canonicalization for retained-reference indexes."""
import hashlib
import json
import re
from ccr.contracts.reference_types import (
    INITIAL_PROFILE_HISTORY_REFERENCE, INPUT_PURPOSES, ISSUE_LIMIT,
    LEGACY_INITIAL_PROFILE_REFERENCE, SHA256, ReferenceIssue, _issue,
)
from ccr.contracts.references import parse_reference, resolve_reference
from ccr.workflow.profiles import canonical_profile


def validate_selection_reference(selection: dict,
                                 sources: dict[str, bytes] | None) -> list[ReferenceIssue]:
    """Validate profile selection syntax and, when supplied, its exact value."""
    field = 'profile reference'
    reference = selection.get('reference') if isinstance(selection, dict) else None
    issues: list[ReferenceIssue] = []
    try:
        path, fragment = parse_reference(reference, field=field)
    except ValueError as exc:
        return [_issue('invalid_reference', field, reference if isinstance(reference, str) else None,
                       str(exc), 'evidence/context.json#profile')]

    if fragment is None:
        return [_issue('missing_fragment', field, reference,
                       'profile selection requires a JSON profile fragment',
                       'evidence/context.json#profile')]
    selection_id = selection.get('id') if isinstance(selection, dict) else None
    expected_fragment = None
    legacy_initial = selection_id == 'S001' and reference == LEGACY_INITIAL_PROFILE_REFERENCE
    if selection_id is None:
        expected_fragment = 'profile'
    elif selection_id == 'S001':
        expected_fragment = 'profile_history/0/profile'
    else:
        match = re.fullmatch(r'S(\d{3})', selection_id) if isinstance(selection_id, str) else None
        if match is not None and int(match.group(1)) >= 2:
            expected_fragment = f'profile_history/{int(match.group(1)) - 1}/profile'
    allowed_fragments = {expected_fragment} if expected_fragment else set()
    if selection_id == 'S001':
        allowed_fragments.add('profile')
    if path != 'evidence/context.json' or fragment not in allowed_fragments:
        expected_reference = (INITIAL_PROFILE_HISTORY_REFERENCE if selection_id == 'S001'
                              else 'evidence/context.json#' + expected_fragment
                              if expected_fragment else None)
        return [_issue('invalid_reference', field, reference,
                       'profile selection must identify its canonical observed history row',
                       expected_reference or 'a valid S001 profile or S002+ history reference')]
    if sources is None:
        return []
    if not isinstance(sources, dict) or path not in sources:
        return [_issue('missing_source', field, reference,
                       'profile source is not available in the selected bytes', path)]
    try:
        source_reference = reference
        if legacy_initial:
            try:
                captured_context = json.loads(sources[path].decode('utf-8'))
            except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
                captured_context = None
            history = captured_context.get('profile_history') if isinstance(captured_context, dict) else None
            if isinstance(history, list) and history:
                source_reference = INITIAL_PROFILE_HISTORY_REFERENCE
        observed = resolve_reference(source_reference, sources, field=field)
        from ccr.workflow.profiles import canonical_profile
        expected = canonical_profile(selection.get('profile'))
    except (ValueError, TypeError) as exc:
        return [_issue('invalid_reference', field, reference, str(exc),
                       'valid UTF-8 JSON with the selected profile')]
    if observed != expected:
        issues.append(_issue('profile_mismatch', field, reference,
                             'profile source differs from the captured selection', expected))
    return issues[:ISSUE_LIMIT]

def _ordered_issues(issues: list[ReferenceIssue]) -> list[ReferenceIssue]:
    return sorted(issues, key=lambda item: (item['field'], item['code'],
                                             item['reference'] or ''))[:ISSUE_LIMIT]

def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and SHA256.fullmatch(value) is not None

def _selected_bytes(reference: str, sources: dict[str, bytes], field: str) -> bytes:
    path, fragment = parse_reference(reference, field=field)
    if fragment is not None:
        raise ValueError(field + ' must identify a file without a fragment')
    raw = sources.get(path)
    if not isinstance(raw, bytes):
        raise ValueError(field + ' source is not selected as retained bytes: ' + path)
    return raw

def validate_reference_index(index: dict, sources: dict[str, bytes]) -> list[ReferenceIssue]:
    """Validate the optional one-hop alias and material-input sidecar."""
    issues: list[ReferenceIssue] = []

    if not isinstance(sources, dict):
        issues.append(_issue('missing_input', 'sources', None,
                             'selected retained sources must be a byte map',
                             'a map from selected local paths to bytes'))
        sources = {}

    def issue(code, field, reference, message, expected):
        issues.append(_issue(code, field, reference, message, expected))

    if not isinstance(index, dict):
        return [_issue('missing_input', 'reference_index', None,
                       'reference index must be an object',
                       '{schema_version, aliases, inputs}')]
    if set(index) != {'schema_version', 'aliases', 'inputs'}:
        issue('invalid_reference', 'reference_index', None,
              'reference index has missing or unknown fields',
              'exactly schema_version, aliases and inputs')
    if type(index.get('schema_version')) is not int or index.get('schema_version') != 1:
        issue('invalid_reference', 'reference_index.schema_version', None,
              'unsupported reference index schema', 'schema_version 1')

    aliases = index.get('aliases')
    if not isinstance(aliases, dict):
        issue('invalid_reference', 'reference_index.aliases', None,
              'reference index aliases must be an object', 'a map of local source references')
        aliases = {}
    alias_paths: dict[str, str] = {}
    for source_reference, value in aliases.items():
        field = 'reference_index.aliases'
        try:
            source_path, source_fragment = parse_reference(
                source_reference, field=field, allow_alias_key=True)
            if source_fragment is not None:
                raise ValueError('alias keys must identify files without fragments')
            if not source_path.startswith('evidence/'):
                raise ValueError('alias keys must identify local evidence files')
        except (TypeError, ValueError) as exc:
            issue('invalid_reference', field, source_reference if isinstance(source_reference, str) else None,
                  str(exc), 'a safe local source path, optionally nested, without a fragment')
            continue
        if not isinstance(value, dict) or set(value) != {'reference', 'sha256'}:
            issue('invalid_reference', field, source_reference,
                  'alias must contain exactly reference and sha256',
                  '{reference: flat selected evidence path, sha256: lowercase digest}')
            continue
        target = value.get('reference')
        try:
            target_path, target_fragment = parse_reference(target, field=field)
            if target_fragment is not None or not target_path.startswith('evidence/'):
                raise ValueError('alias destination must be a flat evidence file without a fragment')
        except (TypeError, ValueError) as exc:
            issue('invalid_reference', field, source_reference, str(exc),
                  'a flat selected evidence destination')
            continue
        if target_path == source_path:
            issue('invalid_reference', field, source_reference,
                  'self-aliases are not allowed', 'a distinct canonical evidence path')
        if not _is_sha256(value.get('sha256')):
            issue('input_changed', field, source_reference,
                  'alias sha256 must be a lowercase SHA-256 digest', '64 lowercase hexadecimal characters')
        alias_paths[source_path] = target_path
        try:
            target_bytes = _selected_bytes(target_path, sources, field)
            if _is_sha256(value.get('sha256')) and hashlib.sha256(target_bytes).hexdigest() != value['sha256']:
                issue('input_changed', field, source_reference,
                      'canonical alias bytes differ from the recorded original digest', value['sha256'])
        except (TypeError, ValueError) as exc:
            issue('missing_source', field, source_reference, str(exc), target_path)
        original_bytes = sources.get(source_path)
        if isinstance(original_bytes, bytes) and _is_sha256(value.get('sha256')):
            if hashlib.sha256(original_bytes).hexdigest() != value['sha256']:
                issue('input_changed', field, source_reference,
                      'selected original alias bytes differ from the recorded digest', value['sha256'])

    for source_path, target_path in alias_paths.items():
        if target_path in alias_paths:
            code = 'invalid_reference'
            issue(code, 'reference_index.aliases', source_path,
                  'alias chains and cycles are not allowed',
                  'a one-hop alias to a selected canonical evidence file')

    raw_inputs = index.get('inputs')
    if not isinstance(raw_inputs, list):
        issue('invalid_reference', 'reference_index.inputs', None,
              'reference index inputs must be an array', 'selected input entries')
        raw_inputs = []
    seen_inputs = set()
    for number, value in enumerate(raw_inputs):
        field = f'reference_index.inputs[{number}]'
        if not isinstance(value, dict) or set(value) != {'reference', 'purpose', 'sha256'}:
            issue('invalid_reference', field, None,
                  'input must contain exactly reference, purpose and sha256',
                  '{reference, purpose, sha256}')
            continue
        reference = value.get('reference')
        try:
            path, fragment = parse_reference(reference, field=field)
            if fragment is not None or not path.startswith('evidence/'):
                raise ValueError('input must be a flat retained evidence file without a fragment')
        except (TypeError, ValueError) as exc:
            issue('invalid_reference', field, reference if isinstance(reference, str) else None,
                  str(exc), 'a flat selected evidence path')
            continue
        if path == 'evidence/reference-index.json':
            issue('invalid_reference', field, reference,
                  'reference index cannot include itself in inputs',
                  'a material input other than evidence/reference-index.json')
        if path in seen_inputs:
            issue('invalid_reference', field, reference,
                  'duplicate material input path', 'one entry per selected input path')
        seen_inputs.add(path)
        if not isinstance(value.get('purpose'), str) or value.get('purpose') not in INPUT_PURPOSES:
            issue('invalid_reference', field + '.purpose', reference,
                  'unknown material input purpose', ', '.join(sorted(INPUT_PURPOSES)))
        if not _is_sha256(value.get('sha256')):
            issue('input_changed', field + '.sha256', reference,
                  'input sha256 must be a lowercase SHA-256 digest', '64 lowercase hexadecimal characters')
            continue
        try:
            data = _selected_bytes(path, sources, field)
        except (TypeError, ValueError) as exc:
            issue('missing_input', field, reference, str(exc), path)
            continue
        if hashlib.sha256(data).hexdigest() != value['sha256']:
            issue('input_changed', field, reference,
                  'selected material input differs from the reference index digest', value['sha256'])
    return _ordered_issues(issues)


def reference_source_paths(index: dict) -> list[str]:
    """List only canonical material and alias-target files selected by an index."""
    if not isinstance(index, dict) or set(index) != {'schema_version', 'aliases', 'inputs'}:
        raise ValueError('reference index must contain exactly schema_version, aliases and inputs')
    if index.get('schema_version') != 1:
        raise ValueError('reference index schema_version must be 1')
    aliases = index.get('aliases')
    inputs = index.get('inputs')
    if not isinstance(aliases, dict) or not isinstance(inputs, list):
        raise ValueError('reference index aliases and inputs have invalid types')

    selected = set()
    for alias, row in aliases.items():
        try:
            alias_path, fragment = parse_reference(
                alias, field='reference_index.aliases', allow_alias_key=True)
            if fragment is not None or alias_path != alias:
                raise ValueError('alias key must be a local evidence file without a fragment')
            target = canonical_reference(alias, aliases)
            target_path, target_fragment = parse_reference(
                target, field='reference_index.aliases target')
            if target_fragment is not None or not target_path.startswith('evidence/'):
                raise ValueError('alias destination must be a flat evidence file without a fragment')
        except (TypeError, ValueError) as exc:
            raise ValueError('invalid reference index alias ' + str(alias) + ': ' + str(exc)) from exc
        if not isinstance(row, dict) or set(row) != {'reference', 'sha256'}:
            raise ValueError('alias must contain exactly reference and sha256: ' + str(alias))
        selected.add(target_path)

    for number, row in enumerate(inputs):
        if not isinstance(row, dict) or set(row) != {'reference', 'purpose', 'sha256'}:
            raise ValueError(f'reference index input {number} has an invalid shape')
        try:
            path, fragment = parse_reference(row.get('reference'),
                                             field=f'reference_index.inputs[{number}]')
        except (TypeError, ValueError) as exc:
            raise ValueError(f'invalid reference index input {number}: {exc}') from exc
        if fragment is not None or not path.startswith('evidence/'):
            raise ValueError(f'reference index input {number} must be a flat evidence file')
        if path == 'evidence/reference-index.json':
            raise ValueError('reference index cannot include itself in inputs')
        selected.add(path)
    return sorted(selected)

def canonical_reference(reference: str, aliases: dict[str, dict[str, str]]) -> str:
    """Canonicalize a retained reference through at most one validated alias."""
    field = 'reference'
    try:
        path, fragment = parse_reference(reference, field=field, allow_alias_key=True)
    except ValueError:
        raise
    if not isinstance(aliases, dict):
        raise ValueError('reference aliases must be an object')
    if path not in aliases:
        # An unaliased reference must still be selectable by the ordinary grammar.
        path, fragment = parse_reference(reference, field=field)
        return path + ('#' + fragment if fragment is not None else '')
    row = aliases[path]
    if not isinstance(row, dict) or set(row) != {'reference', 'sha256'}:
        raise ValueError('alias must contain exactly reference and sha256')
    target, target_fragment = parse_reference(row.get('reference'), field=field)
    if (target_fragment is not None or not target.startswith('evidence/')
            or target in aliases or target == path):
        raise ValueError('alias must be a one-hop path to distinct flat evidence')
    if not _is_sha256(row.get('sha256')):
        raise ValueError('alias sha256 must be a lowercase SHA-256 digest')
    return target + ('#' + fragment if fragment is not None else '')
