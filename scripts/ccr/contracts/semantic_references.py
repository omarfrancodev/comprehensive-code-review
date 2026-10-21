"""Semantic validation of local references and internal review claims."""
import json
import re
from ccr.contracts.reference_types import (
    CHECK_TOKEN, FIXED_FILES, ISSUE_LIMIT, ReferenceIssue, _issue,
)
from ccr.contracts.reference_index import (
    _ordered_issues, canonical_reference, validate_reference_index,
)
from ccr.contracts.references import parse_reference, resolve_reference


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
