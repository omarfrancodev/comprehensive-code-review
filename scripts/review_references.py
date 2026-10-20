"""Shared, filesystem-free grammar and resolver for retained review evidence."""
import json
import hashlib
import re
from typing import TypedDict

import review_trace


REFERENCE_LIMIT = 500
ISSUE_LIMIT = 100
SHA256 = re.compile(r'[0-9a-f]{64}')
CHECK_TOKEN = re.compile(r'(?<![A-Za-z0-9_])C[0-9]{3,}(?![A-Za-z0-9_])')
INPUT_PURPOSES = {'description', 'requirements', 'notes', 'plan', 'configuration', 'other'}
CANONICAL_NAME = re.compile(r'[A-Za-z0-9._-]+')
WINDOWS_DEVICE = re.compile(r'(?i)(CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])(?:\..*)?')
FIXED_FILES = {'review.json', 'informe.md', 'measurements.json',
               review_trace.NAME, 'handoff.md'}
class ReferenceIssue(TypedDict):
    code: str
    field: str
    reference: str | None
    message: str
    expected: str


def _safe_component(value: str) -> bool:
    return (bool(value) and value not in {'.', '..'} and ':' not in value
            and not value.endswith((' ', '.'))
            and not WINDOWS_DEVICE.fullmatch(value))


def parse_reference(reference: str, *, field: str,
                    allow_alias_key: bool = False) -> tuple[str, str | None]:
    """Parse a local retained reference without touching the filesystem."""
    if (not isinstance(reference, str) or not reference or len(reference) > REFERENCE_LIMIT
            or any(ord(char) < 32 for char in reference)):
        raise ValueError(field + ' must be bounded nonempty text without control characters')
    path, marker, fragment = reference.partition('#')
    if '\\' in path or '?' in path:
        raise ValueError(field + ' must use a local POSIX reference without query or backslashes')
    if marker and (not fragment or '#' in fragment):
        raise ValueError(field + ' has an invalid fragment')
    if not path or path.startswith('/') or re.match(r'^[A-Za-z]:', path):
        raise ValueError(field + ' must be relative to the retained review')
    if re.search(r'%(?:2f|5c)', path, re.IGNORECASE):
        raise ValueError(field + ' cannot encode path separators')
    if '%' in path:
        raise ValueError(field + ' cannot contain encoded path characters')
    if re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:', path):
        raise ValueError(field + ' cannot be a URL')

    parts = path.split('/')
    if any(not _safe_component(part) for part in parts):
        raise ValueError(field + ' contains an unsafe path component')
    if parts[0] == 'evidence':
        if len(parts) < 2 or (len(parts) != 2 and not allow_alias_key):
            raise ValueError(field + ' must identify a flat retained evidence file')
        if any(not CANONICAL_NAME.fullmatch(part) for part in parts[1:]):
            if not allow_alias_key:
                raise ValueError(field + ' contains a noncanonical retained evidence name')
    elif path not in FIXED_FILES or allow_alias_key:
        raise ValueError(field + ' must identify retained local evidence')
    return path, fragment if marker else None


def resolve_reference(reference: str, sources: dict[str, bytes], *, field: str) -> object:
    """Resolve one reference against caller-supplied retained bytes only."""
    path, fragment = parse_reference(reference, field=field)
    if not isinstance(sources, dict):
        raise ValueError(field + ' sources must be a map of retained bytes')
    if path not in sources:
        raise ValueError(field + ' source is not selected for retention: ' + path)
    raw = sources[path]
    if not isinstance(raw, bytes):
        raise ValueError(field + ' source must contain bytes')
    if fragment is None:
        return raw

    if path.endswith('.json'):
        try:
            value = json.loads(raw.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(field + ' JSON source is invalid UTF-8 JSON') from exc
        # Preserve the existing profile resolver's key/index and ~0/~1 behavior.
        for token in fragment.lstrip('/').split('/'):
            key = token.replace('~1', '/').replace('~0', '~')
            try:
                value = value[int(key)] if isinstance(value, list) else value[key]
            except (KeyError, IndexError, ValueError, TypeError) as exc:
                raise ValueError(field + ' fragment does not resolve: ' + reference) from exc
        return value

    if path == review_trace.NAME:
        try:
            events = [json.loads(line) for line in raw.decode('utf-8').splitlines()]
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(field + ' trace source is invalid UTF-8 JSONL') from exc
        matches = [event for event in events
                   if isinstance(event, dict) and event.get('event_id') == fragment]
        if not matches:
            raise ValueError(field + ' trace event does not resolve: ' + reference)
        return matches[0]

    if path.endswith('.md'):
        try:
            text = raw.decode('utf-8')
        except UnicodeDecodeError as exc:
            raise ValueError(field + ' Markdown source is not UTF-8') from exc
        anchor = (r'(?:<a\s+id=["\x27]' + re.escape(fragment)
                  + r'["\x27]|^#{1,6}\s+' + re.escape(fragment) + r'(?:\s|$))')
        if re.search(anchor, text, re.MULTILINE):
            return raw
    raise ValueError(field + ' fragment does not resolve: ' + reference)


def _issue(code: str, field: str, reference: str | None,
           message: str, expected: str) -> ReferenceIssue:
    return {'code': code, 'field': field, 'reference': reference,
            'message': message[:500], 'expected': expected[:500]}


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
    if selection_id in (None, 'S001'):
        expected_fragment = 'profile'
    else:
        match = re.fullmatch(r'S(\d{3})', selection_id) if isinstance(selection_id, str) else None
        if match is not None and int(match.group(1)) >= 2:
            expected_fragment = f'profile_history/{int(match.group(1)) - 1}/profile'
    expected_reference = 'evidence/context.json#' + expected_fragment if expected_fragment else None
    if path != 'evidence/context.json' or fragment != expected_fragment:
        return [_issue('invalid_reference', field, reference,
                       'profile selection must identify its canonical observed history row',
                       expected_reference or 'a valid S001 profile or S002+ history reference')]
    if sources is None:
        return []
    if not isinstance(sources, dict) or path not in sources:
        return [_issue('missing_source', field, reference,
                       'profile source is not available in the selected bytes', path)]
    try:
        observed = resolve_reference(reference, sources, field=field)
        import review_profiles
        expected = review_profiles._canonical(selection.get('profile'))
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


def validate_semantic_references(record: dict, packets: list[dict],
                                 index: dict | None,
                                 sources: dict[str, bytes]) -> list[ReferenceIssue]:
    """Check typed check IDs, local links, and internal C### claims on selected data."""
    issues: list[ReferenceIssue] = []
    if not isinstance(record, dict):
        return [_issue('missing_input', 'record', None, 'record must be an object',
                       'a final review record')]
    if not isinstance(sources, dict):
        issues.append(_issue('missing_input', 'sources', None,
                             'selected retained sources must be a byte map',
                             'a map from selected local paths to bytes'))
        sources = {}
    aliases = index.get('aliases', {}) if isinstance(index, dict) else {}
    if index is not None:
        issues.extend(validate_reference_index(index, sources))
    checks = record.get('checks', [])
    current_ids = {row.get('id') for row in checks if isinstance(row, dict)
                   and isinstance(row.get('id'), str)} if isinstance(checks, list) else set()
    historical_ids = set()
    grandfathered = record.get('grandfathered_ids')
    previous = record.get('previous_reviews')
    if isinstance(grandfathered, dict) and isinstance(grandfathered.get('checks'), list) \
            and isinstance(previous, list) and any(isinstance(row, dict) and row.get('verified') is True
                                                   for row in previous):
        historical_ids = {item for item in grandfathered['checks'] if isinstance(item, str)}

    def add(code, field, reference, message, expected):
        issues.append(_issue(code, field, reference, message, expected))

    def check_id(identifier, field):
        if not isinstance(identifier, str):
            return
        if identifier not in current_ids:
            add('unknown_check', field, identifier,
                'typed check reference does not identify a current retained check',
                'an ID from record.checks')

    def scan_text(value, field, allowed_historical=()):
        if not isinstance(value, str):
            return
        for identifier in CHECK_TOKEN.findall(value):
            if identifier not in current_ids and identifier not in allowed_historical:
                check_id(identifier, field)

    def local_reference(raw, field):
        if not isinstance(raw, str) or not raw.startswith(('evidence/', 'review.json', 'informe.md',
                                                            'measurements.json', 'trazabilidad.jsonl', 'handoff.md')):
            return
        try:
            canonical = canonical_reference(raw, aliases)
            resolve_reference(canonical, sources, field=field)
        except (TypeError, ValueError) as exc:
            add('missing_source' if 'not selected' in str(exc) else 'invalid_reference',
                field, raw, str(exc), 'a selected, resolvable retained reference')

    coverage = record.get('coverage')
    if isinstance(coverage, dict):
        for number, area in enumerate(coverage.get('areas', []) if isinstance(coverage.get('areas'), list) else []):
            if isinstance(area, dict):
                scan_text(area.get('details'), f'coverage.areas[{number}].details')
        execution = coverage.get('execution')
        if isinstance(execution, dict):
            plans = execution.get('plan', [])
            results = execution.get('results', [])
            plan_ids = {row.get('id') for row in plans if isinstance(row, dict)
                        and isinstance(row.get('id'), str)} if isinstance(plans, list) else set()
            for group_name, rows in (('plan', plans), ('results', results)):
                if isinstance(rows, list):
                    for number, row in enumerate(rows):
                        if isinstance(row, dict):
                            local_reference(row.get('reference'),
                                            f'coverage.execution.{group_name}[{number}].reference')
            if isinstance(results, list):
                for number, row in enumerate(results):
                    if (isinstance(row, dict) and
                            (not isinstance(row.get('assignment_id'), str)
                             or row.get('assignment_id') not in plan_ids)):
                        add('unregistered_assignment', f'coverage.execution.results[{number}].assignment_id',
                            row.get('assignment_id') if isinstance(row.get('assignment_id'), str) else None,
                            'execution result does not identify a registered assignment',
                            'an assignment ID from coverage.execution.plan')
            fallbacks = execution.get('fallbacks', [])
            if isinstance(fallbacks, list):
                for number, row in enumerate(fallbacks):
                    if isinstance(row, dict):
                        local_reference(row.get('source'),
                                        f'coverage.execution.fallbacks[{number}].source')

    for number, check in enumerate(checks if isinstance(checks, list) else []):
        if isinstance(check, dict):
            local_reference(check.get('reference'), f'checks[{number}].reference')
            scan_text(check.get('evidence'), f'checks[{number}].evidence')
    for number, finding in enumerate(record.get('findings', []) if isinstance(record.get('findings'), list) else []):
        if isinstance(finding, dict):
            for evidence_number, evidence in enumerate(finding.get('evidence', []) if isinstance(finding.get('evidence'), list) else []):
                if isinstance(evidence, dict):
                    check_id(evidence.get('check_id'), f'findings[{number}].evidence[{evidence_number}].check_id')
                    scan_text(evidence.get('details'), f'findings[{number}].evidence[{evidence_number}].details')
                    for link in re.findall(r'\[[^\]]*\]\(([^)]+)\)', evidence.get('details', '') if isinstance(evidence.get('details'), str) else ''):
                        local_reference(link, f'findings[{number}].evidence[{evidence_number}].details')
    for number, row in enumerate(record.get('rereview', []) if isinstance(record.get('rereview'), list) else []):
        if not isinstance(row, dict):
            continue
        allowed = set()
        linked = previous if isinstance(previous, list) else []
        if any(isinstance(prior, dict) and prior.get('verified') is True
               and prior.get('reference') == row.get('previous_reference')
               and (row.get('previous_review_id') is None or prior.get('review_id') == row.get('previous_review_id'))
               for prior in linked):
            allowed = historical_ids
        scan_text(row.get('details'), f'rereview[{number}].details', allowed)
        for check_number, identifier in enumerate(row.get('check_ids', []) if isinstance(row.get('check_ids'), list) else []):
            check_id(identifier, f'rereview[{number}].check_ids[{check_number}]')
    for packet_number, packet in enumerate(packets if isinstance(packets, list) else []):
        if not isinstance(packet, dict):
            continue
        for check_number, identifier in enumerate(packet.get('check_ids', []) if isinstance(packet.get('check_ids'), list) else []):
            check_id(identifier, f'packets[{packet_number}].check_ids[{check_number}]')
        for collection in ('findings', 'decisions'):
            rows = packet.get(collection, [])
            for row_number, row in enumerate(rows if isinstance(rows, list) else []):
                if not isinstance(row, dict):
                    continue
                for evidence_number, evidence in enumerate(row.get('evidence', []) if isinstance(row.get('evidence'), list) else []):
                    if not isinstance(evidence, dict):
                        continue
                    check_id(evidence.get('check_id'),
                             f'packets[{packet_number}].{collection}[{row_number}].evidence[{evidence_number}].check_id')
                    scan_text(evidence.get('details'),
                              f'packets[{packet_number}].{collection}[{row_number}].evidence[{evidence_number}].details')

    # Scan explicit references and Markdown links only inside selected briefs/results.
    selected_paths = set()
    execution = coverage.get('execution') if isinstance(coverage, dict) else None
    if isinstance(execution, dict):
        for group_name in ('plan', 'results'):
            rows = execution.get(group_name, [])
            if isinstance(rows, list):
                for row in rows:
                    raw = row.get('reference') if isinstance(row, dict) else None
                    if isinstance(raw, str):
                        try:
                            selected_paths.add(canonical_reference(raw, aliases).split('#', 1)[0])
                        except ValueError:
                            pass
    link_pattern = re.compile(r'\[[^\]]*\]\(([^)]+)\)')

    def markdown_target(target: str, source_path: str, field: str) -> None:
        target = target.strip()
        if re.match(r'(?i)^(?:https?://|mailto:|data:)', target):
            return
        if target.startswith('#'):
            target = source_path + target
        elif not target.startswith('evidence/') and target not in FIXED_FILES:
            target = 'evidence/' + target
        local_reference(target, field)

    for path in sorted(selected_paths):
        raw = sources.get(path)
        if not isinstance(raw, bytes):
            continue
        try:
            content = raw.decode('utf-8')
        except UnicodeDecodeError:
            add('invalid_reference', 'selected_brief', path,
                'selected brief/result is not valid UTF-8', 'UTF-8 selected brief/result content')
            continue
        for link in link_pattern.findall(content):
            markdown_target(link, path, 'selected_brief.link')
        if path.endswith('.json'):
            try:
                value = json.loads(raw.decode('utf-8'))
            except json.JSONDecodeError:
                continue

            def scan_json(item, field):
                if isinstance(item, dict):
                    for key, child in item.items():
                        child_field = field + '.' + str(key)
                        if key in {'reference', 'source'}:
                            local_reference(child, child_field)
                        elif key == 'check_id':
                            check_id(child, child_field)
                        elif key == 'check_ids':
                            for number, identifier in enumerate(child if isinstance(child, list) else []):
                                check_id(identifier, child_field + f'[{number}]')
                        elif isinstance(child, (dict, list)):
                            scan_json(child, child_field)
                        elif isinstance(child, str):
                            scan_text(child, child_field)
                            for target in link_pattern.findall(child):
                                markdown_target(target, path, child_field)
                elif isinstance(item, list):
                    for number, child in enumerate(item):
                        scan_json(child, field + f'[{number}]')

            scan_json(value, path)
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
            if not isinstance(reference, str) or captured_sources.get(reference) != expected:
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
            if not isinstance(ref, str) or captured_sources.get(ref) != requirements[0].get('sha256'):
                add('input_changed', 'requirements', ref,
                    'requirements source differs from the initially captured inputs',
                    str(requirements[0].get('sha256')))
            expected_identity = identity_digest(requirements_identity)
            if expected_identity is not None and expected_identity != requirements[0].get('sha256'):
                add('input_changed', 'requirements_identity', ref,
                    'requirements identity differs from selected source hash', expected_identity)
    return _ordered_issues(issues)
