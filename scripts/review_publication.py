"""Select limitations by audience; historical classification is source-bound."""
import hashlib
import json
import re
from urllib.parse import urlsplit


CHECK_PUBLICATION_FIELDS = {'id', 'evidence', 'reuse_reason', 'rerun_reason', 'reference'}
PUBLIC_CHECK_FIELDS = {'id', 'revision', 'status', 'failure_kind', 'evidence', 'reused',
                       'reuse_reason', 'rerun_reason', 'reference'}


def publication_digest(record):
    return hashlib.sha256(json.dumps(record, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def public_url(value):
    if not isinstance(value, str):
        return False
    try:
        parsed = urlsplit(value)
        return parsed.scheme in {'http', 'https'} and bool(parsed.netloc) \
            and not parsed.username and not parsed.password
    except ValueError:
        return False


def _needs_check_classification(check):
    if check.get('reuse_reason') is not None or check.get('rerun_reason') is not None:
        return True
    evidence = check.get('evidence')
    if not isinstance(evidence, str):
        return False
    command = check.get('command')
    reference = check.get('reference')
    return ('evidence/' in evidence
            or isinstance(command, str) and bool(command) and command in evidence
            or isinstance(reference, str) and bool(reference) and reference in evidence
            or bool(re.search(r'(?i)(?:[A-Z]:[\\/]|\\\\[^\\\s]+\\[^\\\s]+|(?<![\w:])/(?:[^\s/]+/)+[^\s]+)', evidence)))


def public_checks(record: dict, classification: dict | None = None) -> list[dict]:
    """Project check facts for comments, with source-bound editorial summaries."""
    checks = record.get('checks') if isinstance(record, dict) else None
    if not isinstance(checks, list):
        raise ValueError('checks must be an array for public projection')
    if classification is None:
        if any(_needs_check_classification(check) for check in checks if isinstance(check, dict)):
            raise ValueError('check publication context required for free-text reasons or internal evidence')
        rows = None
    else:
        if (not isinstance(classification, dict)
                or set(classification) != {'source_sha256', 'checks'}
                or classification.get('source_sha256') != publication_digest(record)
                or not isinstance(classification.get('checks'), list)
                or len(classification['checks']) != len(checks)):
            raise ValueError('check publication context does not match the source record')
        rows = {}
        for row in classification['checks']:
            if (not isinstance(row, dict) or set(row) != CHECK_PUBLICATION_FIELDS
                    or not isinstance(row.get('id'), str) or row['id'] in rows):
                raise ValueError('check publication context requires exact unique check rows')
            rows[row['id']] = row
        if set(rows) != {check.get('id') for check in checks if isinstance(check, dict)}:
            raise ValueError('check publication context must cover every source check exactly once')

    selected = []
    for check in checks:
        if not isinstance(check, dict):
            raise ValueError('source check must be an object')
        row = rows.get(check['id']) if rows is not None else None
        if row is None:
            evidence = check.get('evidence')
            reuse_reason = check.get('reuse_reason')
            rerun_reason = check.get('rerun_reason')
            reference = check.get('reference') if public_url(check.get('reference')) else None
        else:
            evidence = row.get('evidence')
            reuse_reason = row.get('reuse_reason')
            rerun_reason = row.get('rerun_reason')
            reference = row.get('reference')
            original_evidence = check.get('evidence')
            if original_evidence is None:
                if evidence is not None:
                    raise ValueError('check publication context cannot invent evidence')
            elif not isinstance(evidence, str) or not evidence.strip():
                raise ValueError('check publication context must retain or summarize existing evidence')
            if check.get('reused') is True:
                if not isinstance(reuse_reason, str) or not reuse_reason.strip():
                    raise ValueError('reused check needs a public reuse summary')
            elif reuse_reason is not None:
                raise ValueError('check publication context cannot add a reuse reason')
            if check.get('rerun_reason') is None and rerun_reason is not None:
                raise ValueError('check publication context cannot add a rerun reason')
            original_reference = check.get('reference')
            expected_reference = original_reference if public_url(original_reference) else None
            if reference != expected_reference:
                raise ValueError('check publication context cannot add or change a public URL')
            for name, value in (('reuse_reason', reuse_reason), ('rerun_reason', rerun_reason)):
                if value is not None and (not isinstance(value, str) or not value.strip()):
                    raise ValueError(name + ' must be nonempty public text or null')

        if evidence is not None and (not isinstance(evidence, str) or not evidence.strip()):
            raise ValueError('public check evidence must be nonempty text or null')
        selected.append({
            'id': check['id'],
            'revision': check['revision'],
            'status': check['status'],
            'failure_kind': check.get('failure_kind'),
            'evidence': evidence,
            'reused': check['reused'],
            'reuse_reason': reuse_reason,
            'rerun_reason': rerun_reason,
            'reference': reference,
        })
    return selected


def public_limitations(record, classification=None):
    original = record['coverage']['limitations']
    if record['schema_version'] in (8, 9, 10):
        if classification is not None:
            raise ValueError('schemas 8–10 already contain limitation classification')
        rows = original
    elif classification is None:
        if original:
            raise ValueError('historical public limitations require bound publication context')
        rows = []
    else:
        if (not isinstance(classification, dict) or set(classification) != {'source_sha256', 'limitations'}
                or classification['source_sha256'] != publication_digest(record)
                or not isinstance(classification['limitations'], list)
                or len(classification['limitations']) != len(original)):
            raise ValueError('publication context does not match the source record')
        indexed = {}
        for row in classification['limitations']:
            if (not isinstance(row, dict) or set(row) != {'index', 'kind', 'public_summary'}
                    or type(row['index']) is not int or not 0 <= row['index'] < len(original)
                    or row['index'] in indexed):
                raise ValueError('publication context requires each original index exactly once')
            indexed[row['index']] = row
        rows = [dict(item, kind=indexed[i]['kind'], public_summary=indexed[i]['public_summary'])
                for i, item in enumerate(original)]
    # Merge evidenced material gaps by original detail before selecting audience text.
    # No semantic classification of unmatched prose; area-only gaps remain publishable.
    rows = [dict(row) for row in rows]
    key = lambda detail: ' '.join(detail.split())
    for area in record['coverage'].get('areas', []):
        if not area['material']:
            continue
        matching = [row for row in rows if key(row['detail']) == key(area['details'])]
        if matching:
            for row in matching:
                row['material'] = True
        else:
            rows.append(dict(kind='validation', detail=area['details'], material=True, public_summary=None))
    selected = []
    indexed = {}
    for row in rows:
        if row['kind'] not in ('behavior', 'validation', 'execution'):
            raise ValueError('invalid public limitation kind')
        summary = row['public_summary']
        if summary is not None and (not isinstance(summary, str) or not summary.strip()):
            raise ValueError('public_summary must be nonempty text or null')
        if row['kind'] == 'execution':
            if row['material']:
                if summary is None:
                    raise ValueError('material execution requires a public impact summary')
            else:
                if summary is not None:
                    raise ValueError('nonmaterial execution must not have a public summary')
                continue
        detail = summary if summary is not None else row['detail']
        if key(detail) in indexed:
            selected[indexed[key(detail)]]['material'] |= row['material']
        else:
            indexed[key(detail)] = len(selected)
            selected.append(dict(detail=detail, material=row['material']))
    return selected


def public_reservations(record, limitations):
    """Exclude exact source/projected duplicates, retaining unrelated conditions."""
    key = lambda detail: ' '.join(detail.split())
    seen = {key(row['detail']) for row in record['coverage']['limitations'] + limitations}
    selected = []
    for reservation in record['reservations']:
        if key(reservation) not in seen:
            selected.append(reservation)
            seen.add(key(reservation))
    return selected
