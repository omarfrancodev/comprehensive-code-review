"""Pure validation of check execution provenance."""
from ccr.contracts.receipts import validate_record_receipts

"""Pure schema-9 check provenance validation; no execution or filesystem probes."""

def _text(value):
    return isinstance(value, str) and bool(value.strip()) and len(value) <= 4000

def validate_check_execution(record):
    if record.get('schema_version') not in (9, 10, 11, 12):
        return []
    errors = []
    checks = record.get('checks')
    if not isinstance(checks, list):
        return ['checks: expected array']
    for index, check in enumerate(checks):
        prefix = f'checks[{index}].execution: '
        execution = check.get('execution') if isinstance(check, dict) else None
        if not isinstance(execution, dict) or set(execution) != {'kind', 'executor'}:
            errors.append(prefix + 'exact kind/executor fields required')
            continue
        kind, executor = execution['kind'], execution['executor']
        if kind not in ('local', 'static', 'external', 'reused'):
            errors.append(prefix + 'invalid kind')
        if executor is not None and not _text(executor):
            errors.append(prefix + 'executor must be nonempty identity or null')
        if kind == 'local' and check.get('status') in ('passed', 'failed') and not _text(executor):
            errors.append(prefix + 'completed local check requires executor')
        if kind != 'local' and executor is not None:
            errors.append(prefix + 'nonlocal check cannot declare executor')
        if (kind == 'reused') != (check.get('reused') is True):
            errors.append(prefix + 'reused kind must match reused flag')
        if kind == 'external' and check.get('status') in ('passed', 'failed') and not _text(check.get('reference')):
            errors.append(prefix + 'completed external check requires source reference')
    return errors

def validate_check_sources(record, executors, *, receipt_sources=None):
    errors = validate_check_execution(record)
    if errors or record.get('schema_version') not in (9, 10, 11, 12):
        return errors
    if not isinstance(executors, list):
        return ['checks.execution.sources: executors must be an array']
    by_id = {}
    for row in executors:
        if not isinstance(row, dict) or not _text(row.get('executor')) or row['executor'] in by_id:
            return ['checks.execution.sources: invalid or duplicate executor identity']
        by_id[row['executor']] = row
    scope = record['scope']
    for index, check in enumerate(record['checks']):
        identity = check['execution']['executor']
        if identity is None:
            continue
        prefix = f'checks[{index}].execution.sources: '
        executor = by_id.get(identity)
        if executor is None:
            errors.append(prefix + 'unknown executor identity')
            continue
        revision, snapshot = executor.get('revision'), executor.get('snapshot')
        baseline = revision == scope['base'] and snapshot is None
        pinned = baseline or revision == scope['head'] and snapshot == scope['snapshot']
        matches = check['revision'] == (snapshot if snapshot is not None else revision)
        if not pinned or not matches:
            errors.append(prefix + 'executor revision/snapshot differs from check and pinned scope')
    if receipt_sources is not None:
        receipt_issues = validate_record_receipts(
            record, receipt_sources, executors)
        errors.extend(issue['field'] + ': ' + issue['message'] for issue in receipt_issues)
    return errors
