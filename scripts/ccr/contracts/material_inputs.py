"""Validation of guided material identities against selected retained bytes."""
import hashlib
import json
from ccr.contracts.reference_types import ISSUE_LIMIT, ReferenceIssue, _issue
from ccr.contracts.reference_index import (
    _is_sha256, _ordered_issues, canonical_reference, validate_reference_index,
)
from ccr.contracts.references import parse_reference


def _captured_material_matches(captured_sources: dict, reference: str,
                              expected: str, aliases: dict) -> bool:
    if not isinstance(reference, str) or not isinstance(expected, str):
        return False
    if captured_sources.get(reference) == expected:
        return True
    if not isinstance(aliases, dict):
        return False
    for captured_reference, digest in captured_sources.items():
        if not isinstance(captured_reference, str) or digest != expected:
            continue
        try:
            canonical = canonical_reference(captured_reference, aliases)
            alias_path, fragment = parse_reference(
                captured_reference, field='captured material', allow_alias_key=True)
        except (TypeError, ValueError):
            continue
        alias = aliases.get(alias_path)
        if (fragment is None and canonical == reference and isinstance(alias, dict)
                and alias.get('reference') == reference and alias.get('sha256') == expected):
            return True
    return False

def validate_captured_material_sources(captured_inputs: dict, index: dict,
                                       sources: dict[str, bytes]) -> list[ReferenceIssue]:
    """Require each indexed material input to be included in captured source hashes."""
    issues = validate_reference_index(index, sources)
    captured_sources = (captured_inputs.get('sources')
                        if isinstance(captured_inputs, dict) else None)
    if not isinstance(captured_sources, dict):
        issues.append(_issue('missing_input', 'review_inputs.sources', None,
                             'captured material source map is missing',
                             'the index and every material input digest'))
        captured_sources = {}
    aliases = index.get('aliases', {}) if isinstance(index, dict) else {}
    rows = index.get('inputs', []) if isinstance(index, dict) else []
    for number, row in enumerate(rows if isinstance(rows, list) else []):
        if not isinstance(row, dict):
            continue
        reference, expected = row.get('reference'), row.get('sha256')
        if (isinstance(reference, str) and _is_sha256(expected)
                and not _captured_material_matches(captured_sources, reference, expected, aliases)):
            issues.append(_issue('input_changed', f'review_inputs.sources[{reference}]', reference,
                                 'material source is not part of the initially captured review inputs',
                                 expected))
    try:
        from ccr.workflow.reuse import validate_reuse_evidence
        validate_reuse_evidence(captured_inputs.get('scope') if isinstance(captured_inputs,dict) else None,
                                index,sources)
    except (ValueError, TypeError, KeyError, UnicodeError) as exc:
        issues.append(_issue('input_changed','reuse_evidence',None,str(exc),'valid initial reuse evidence'))
    return _ordered_issues(issues)


def validate_material_inputs(record: dict, context: dict, index: dict,
                             sources: dict[str, bytes]) -> list[ReferenceIssue]:
    """Bind guided material identities to selected, hash-verified retained bytes."""
    issues = validate_reference_index(index, sources)
    if not isinstance(sources, dict):
        sources = {}

    def add(code, field, reference, message, expected):
        issues.append(_issue(code, field, reference, message, expected))

    if not isinstance(record, dict) or not isinstance(context, dict):
        add('missing_input', 'context', None,
            'material input validation requires record and execution context',
            'a final record and captured execution context')
        return _ordered_issues(issues)
    captured = context.get('review_inputs')
    captured_sources = captured.get('sources') if isinstance(captured, dict) else None
    if not isinstance(captured_sources, dict):
        captured_sources = {}
    aliases = index.get('aliases', {}) if isinstance(index, dict) else {}


    reference_index = context.get('reference_index')
    if reference_index != 'evidence/reference-index.json':
        add('missing_input', 'reference_index',
            reference_index if isinstance(reference_index, str) else None,
            'guided context must declare the selected reference index',
            'evidence/reference-index.json')
    else:
        index_bytes = sources.get(reference_index)
        if not isinstance(index_bytes, bytes):
            add('missing_input', 'reference_index', reference_index,
                'reference index bytes are not selected for retention',
                'selected evidence/reference-index.json')
        else:
            try:
                parsed = json.loads(index_bytes.decode('utf-8'))
            except (UnicodeDecodeError, json.JSONDecodeError):
                parsed = None
            if parsed != index:
                add('input_changed', 'reference_index', reference_index,
                    'selected reference index bytes differ from the validated index object',
                    'the exact selected reference-index.json bytes')
            selected_digest = hashlib.sha256(index_bytes).hexdigest()
            if captured_sources.get(reference_index) != selected_digest:
                add('input_changed', 'review_inputs.sources', reference_index,
                    'reference index is not bound to the initially captured source digest',
                    selected_digest)
    entries = index.get('inputs', []) if isinstance(index, dict) else []
    by_purpose = {}
    for entry in entries if isinstance(entries, list) else []:
        if isinstance(entry, dict) and isinstance(entry.get('purpose'), str):
            by_purpose.setdefault(entry['purpose'], []).append(entry)

    def identity_digest(value):
        if not isinstance(value, str):
            return None
        candidate = value[7:] if value.startswith('sha256:') else value
        return candidate if _is_sha256(candidate) else None

    description = record.get('description') if isinstance(record.get('description'), dict) else {}
    if description.get('status') in ('aligned', 'needs_update'):
        candidates = by_purpose.get('description', [])
        if not candidates:
            add('missing_input', 'description', None,
                'aligned description has no selected material source',
                'one purpose=description input in the reference index')
        elif len(candidates) != 1:
            add('input_changed', 'description', None,
                'aligned description must bind exactly one selected material source',
                'one purpose=description input')
        else:
            entry = candidates[0]
            reference = entry.get('reference')
            expected = entry.get('sha256')
            if not _captured_material_matches(captured_sources, reference, expected, aliases):
                add('input_changed', 'description', reference,
                    'description source is not part of the initially captured review inputs', expected)
            actual_identity = identity_digest(description.get('identity'))
            if actual_identity != expected:
                add('input_changed', 'description.identity', reference,
                    'description identity does not match the selected source hash', expected)

    requirements_identity = captured.get('requirements_identity') if isinstance(captured, dict) else None
    if requirements_identity is not None:
        requirements = by_purpose.get('requirements', [])
        if not requirements:
            add('missing_input', 'requirements', None,
                'captured requirements identity has no selected material input',
                'a purpose=requirements input or a disclosed limitation')
        elif len(requirements) == 1:
            ref = requirements[0].get('reference')
            if not _captured_material_matches(captured_sources, ref, requirements[0].get('sha256'), aliases):
                add('input_changed', 'requirements', ref,
                    'requirements source differs from the initially captured inputs',
                    str(requirements[0].get('sha256')))
            expected_identity = identity_digest(requirements_identity)
            if expected_identity is not None and expected_identity != requirements[0].get('sha256'):
                add('input_changed', 'requirements_identity', ref,
                    'requirements identity differs from selected source hash', expected_identity)
    try:
        from ccr.workflow.reuse import validate_reuse_evidence
        validate_reuse_evidence(record.get('scope'), index, sources, require_context=True)
    except (ValueError, TypeError, KeyError, UnicodeError) as exc:
        add('input_changed','reuse_evidence',None,str(exc),'verified reuse sidecars bound to the pinned scope')
    return _ordered_issues(issues)
