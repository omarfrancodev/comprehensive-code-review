"""Passive, bounded model-observation ledger contracts."""
import copy
import json
import re
from datetime import datetime
from ccr.contracts.reference_types import ISSUE_LIMIT, ReferenceIssue

"""Record bounded private observations of configured and observed models."""

SCHEMA_VERSION = 1

MAX_ENTRIES = 256

MAX_LEDGER_BYTES = 256 * 1024

MAX_MODEL_LENGTH = 200

MAX_REFERENCE_LENGTH = 500

ACTIVITIES = {'coordination', 'discovery', 'verification', 'reporting',
              'publication', 'check', 'other'}

SOURCE_KINDS = {'platform', 'adapter_observed', 'dispatch', 'runner_argument',
                'user', 'unavailable', 'not_applicable'}

ENTRY_FIELDS = {'id', 'phase', 'activity', 'assignment_id', 'check_id', 'actor',
                'configured_model', 'observed_model', 'status', 'source', 'occurred_at'}

OBSERVATION_FIELDS = ENTRY_FIELDS - {'id', 'status'}

STATUSES = {'observed', 'configured_only', 'unknown', 'not_applicable', 'conflict'}

ADMIN_ID = re.compile(r'M[0-9]{4}')

REVIEW_ID = re.compile(r'CR-[0-9a-f]{20}')

HARNESS_ID = re.compile(r'[a-z][a-z0-9]*(?:-[a-z0-9]+)*')

def _json_bytes(value):
    try:
        return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                           indent=2, allow_nan=False) + '\n').encode('utf-8')
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise ValueError('model usage ledger must be bounded JSON data') from exc

def _text(value, field, limit, *, nullable=False):
    if value is None and nullable:
        return None
    if (not isinstance(value, str) or not value.strip() or len(value) > limit
            or any(ord(char) < 32 for char in value)):
        raise ValueError(field + ' must be bounded nonempty text' if not nullable
                         else field + ' must be bounded text or null')
    try:
        value.encode('utf-8')
    except UnicodeEncodeError as exc:
        raise ValueError(field + ' must be valid UTF-8 text') from exc
    return value

def _model(value, field):
    return _text(value, field, MAX_MODEL_LENGTH, nullable=True)

def _actor(value):
    if not isinstance(value, dict) or set(value) != {'kind', 'name', 'provider_id'}:
        raise ValueError('actor must contain exactly kind, name, and provider_id')
    return {
        'kind': _text(value['kind'], 'actor.kind', 64),
        'name': _text(value['name'], 'actor.name', 120),
        'provider_id': _text(value['provider_id'], 'actor.provider_id', 256, nullable=True),
    }

def _source(value):
    if not isinstance(value, dict) or set(value) != {'kind', 'reference'}:
        raise ValueError('source must contain exactly kind and reference')
    kind = value['kind']
    if not isinstance(kind, str) or kind not in SOURCE_KINDS:
        raise ValueError('unsupported model usage source kind')
    reference = _text(value['reference'], 'source.reference', MAX_REFERENCE_LENGTH, nullable=True)
    if kind in {'platform', 'adapter_observed'} and reference is None:
        raise ValueError('observed model source requires an available reference')
    return {'kind': kind, 'reference': reference}

def _occurred_at(value):
    if value is None:
        return None
    raw = _text(value, 'occurred_at', 64)
    try:
        parsed = datetime.fromisoformat(raw[:-1] + '+00:00' if raw.endswith('Z') else raw)
    except ValueError as exc:
        raise ValueError('occurred_at must preserve a supplied ISO 8601 timestamp') from exc
    if parsed.tzinfo is None or parsed.utcoffset().total_seconds() != 0:
        raise ValueError('occurred_at must identify a supplied UTC timestamp')
    return raw

def normalize_model_observation(raw: dict) -> dict:
    """Validate one observation without inventing IDs, status, or model aliases."""
    if not isinstance(raw, dict) or set(raw) != OBSERVATION_FIELDS:
        raise ValueError('model observation requires the exact schema 1 entry fields except id/status')
    phase = _text(raw['phase'], 'phase', 64)
    activity = raw['activity']
    if not isinstance(activity, str) or activity not in ACTIVITIES:
        raise ValueError('unsupported model usage activity')
    assignment_id = _text(raw['assignment_id'], 'assignment_id', 120, nullable=True)
    check_id = _text(raw['check_id'], 'check_id', 120, nullable=True)
    actor = _actor(raw['actor'])
    configured = _model(raw['configured_model'], 'configured_model')
    observed = _model(raw['observed_model'], 'observed_model')
    source = _source(raw['source'])
    occurred_at = _occurred_at(raw['occurred_at'])

    if source['kind'] == 'not_applicable':
        if configured is not None or observed is not None:
            raise ValueError('not_applicable observations cannot identify a model')
        status = 'not_applicable'
    elif observed is not None:
        if source['kind'] not in {'platform', 'adapter_observed'} or source['reference'] is None:
            raise ValueError('observed_model requires a platform or adapter_observed reference')
        status = 'observed'
    else:
        status = 'configured_only' if configured is not None else 'unknown'
    return {
        'phase': phase, 'activity': activity, 'assignment_id': assignment_id,
        'check_id': check_id, 'actor': actor, 'configured_model': configured,
        'observed_model': observed, 'status': status, 'source': source,
        'occurred_at': occurred_at,
    }

def observation_from_metadata(metadata: dict, *, actor: dict, phase: str, activity: str,
                              assignment_id: str | None = None,
                              check_id: str | None = None) -> dict:
    """Map only supplied activity metadata; a runner's model is configuration."""
    if not isinstance(metadata, dict):
        raise ValueError('model metadata must be an object')
    if 'source' in metadata:
        source = metadata['source']
    elif 'model_source' in metadata:
        source = metadata['model_source']
    elif metadata.get('model') is not None or metadata.get('configured_model') is not None:
        source = {'kind': 'runner_argument', 'reference': None}
    else:
        source = {'kind': 'unavailable', 'reference': None}
    try:
        source = _source(source)
    except (TypeError, ValueError):
        # Untrusted observed fields never become observed without a valid source.
        if 'model_source' in metadata or 'source' in metadata:
            raise
        source = {'kind': 'unavailable', 'reference': None}

    configured = metadata.get('configured_model', metadata.get('model'))
    observed = metadata.get('observed_model')
    if source['kind'] == 'not_applicable':
        configured = observed = None
    elif source['kind'] not in {'platform', 'adapter_observed'}:
        observed = None
    raw = {
        'phase': phase, 'activity': activity, 'assignment_id': assignment_id,
        'check_id': check_id, 'actor': copy.deepcopy(actor),
        'configured_model': configured, 'observed_model': observed,
        'source': source, 'occurred_at': metadata.get('occurred_at'),
    }
    return normalize_model_observation(raw)

def _same_observation_context(left, right):
    return all(left.get(key) == right.get(key) for key in (
        'source', 'actor', 'phase', 'activity', 'assignment_id', 'check_id'))

def append_model_observation(ledger: dict | None, observation: dict, *,
                            review_id: str, harness_id: str | None) -> dict:
    """Return a new ledger with the observation appended, preserving prior bytes/facts."""
    if not isinstance(review_id, str) or REVIEW_ID.fullmatch(review_id) is None:
        raise ValueError('review_id must use CR- followed by 20 lowercase hexadecimal characters')
    if harness_id is not None and (not isinstance(harness_id, str)
                                   or HARNESS_ID.fullmatch(harness_id) is None):
        raise ValueError('harness_id must be a canonical ID or null')
    if not isinstance(observation, dict) or set(observation) != OBSERVATION_FIELDS | {'status'}:
        raise ValueError('append requires a normalized model observation without an id')
    normalized = normalize_model_observation({key: value for key, value in observation.items()
                                               if key != 'status'})
    if observation['status'] != normalized['status']:
        raise ValueError('normalized model observation status is inconsistent')
    if ledger is None:
        result = {'schema_version': SCHEMA_VERSION, 'review_id': review_id,
                  'harness_id': harness_id, 'entries': []}
    else:
        issues = validate_model_usage(ledger, review_id=review_id, harness_id=harness_id)
        if issues:
            raise ValueError('existing model usage ledger is invalid: ' + issues[0]['message'])
        result = copy.deepcopy(ledger)
    entries = result['entries']
    if len(entries) >= MAX_ENTRIES:
        raise ValueError('model usage entry limit reached; preserve the valid prefix')
    if any({key: value for key, value in previous.items() if key != 'id'} == normalized
           for previous in entries):
        return result
    row = copy.deepcopy(normalized)
    if row['status'] == 'observed':
        conflict = any(previous['status'] in {'observed', 'conflict'}
                       and previous['observed_model'] != row['observed_model']
                       and _same_observation_context(previous, row)
                       for previous in entries)
        if conflict:
            row['status'] = 'conflict'
    row['id'] = 'M' + str(len(entries) + 1).zfill(4)
    # Keep the published field order stable for review and inspection.
    row = {key: row[key] for key in ('id', 'phase', 'activity', 'assignment_id',
            'check_id', 'actor', 'configured_model', 'observed_model', 'status',
            'source', 'occurred_at')}
    result['entries'].append(row)
    if len(_json_bytes(result)) > MAX_LEDGER_BYTES:
        raise ValueError('model usage byte limit reached; preserve the valid prefix')
    return result

def _issue(field, reference, message, expected):
    return ReferenceIssue(code='invalid_model_usage', field=field,
        reference=reference, message=message, expected=expected)

def validate_model_usage(ledger: dict, *, review_id: str,
                         harness_id: str | None) -> list[ReferenceIssue]:
    """Validate private sidecar structure, identity binding and fixed retention bounds."""
    issues: list[ReferenceIssue] = []
    if not isinstance(ledger, dict) or set(ledger) != {'schema_version', 'review_id', 'harness_id', 'entries'}:
        return [_issue('model_usage', None, 'model usage ledger has an invalid exact schema',
                       '{schema_version, review_id, harness_id, entries}')]
    if type(ledger['schema_version']) is not int or ledger['schema_version'] != SCHEMA_VERSION:
        issues.append(_issue('model_usage.schema_version', None,
                             'unsupported model usage schema', str(SCHEMA_VERSION)))
    if ledger['review_id'] != review_id:
        issues.append(_issue('model_usage.review_id', None,
                             'model usage ledger belongs to another review', str(review_id)))
    if ledger['harness_id'] != harness_id:
        issues.append(_issue('model_usage.harness_id', None,
                             'model usage ledger belongs to another harness', str(harness_id)))
    entries = ledger['entries']
    if not isinstance(entries, list):
        issues.append(_issue('model_usage.entries', None,
                             'model usage entries must be an array', 'an array of schema 1 observations'))
        return issues
    if len(entries) > MAX_ENTRIES:
        issues.append(_issue('model_usage.entries', None,
                             'model usage entry limit is 256', 'at most 256 entries'))
    try:
        size = len(_json_bytes(ledger))
    except ValueError:
        size = MAX_LEDGER_BYTES + 1
    if size > MAX_LEDGER_BYTES:
        issues.append(_issue('model_usage', None,
                             'model usage byte limit is 256 KiB', 'at most 262144 UTF-8 JSON bytes'))

    prior = []
    for index, row in enumerate(entries[:MAX_ENTRIES]):
        reference = 'evidence/model-usage.json#' + str(index)
        if not isinstance(row, dict) or set(row) != ENTRY_FIELDS:
            issues.append(_issue('model_usage.entries[' + str(index) + ']', reference,
                                 'model usage entry has invalid exact fields',
                                 ', '.join(sorted(ENTRY_FIELDS))))
            continue
        expected_id = 'M' + str(index + 1).zfill(4)
        if row.get('id') != expected_id or not isinstance(row.get('id'), str) or not ADMIN_ID.fullmatch(row['id']):
            issues.append(_issue('model_usage.entries[' + str(index) + '].id', reference,
                                 'model usage ID is not the next administrative ID', expected_id))
        try:
            normalized = normalize_model_observation({key: row[key] for key in OBSERVATION_FIELDS})
        except (TypeError, ValueError, KeyError) as exc:
            issues.append(_issue('model_usage.entries[' + str(index) + ']', reference,
                                 'invalid model usage observation: ' + str(exc),
                                 'one exact valid model observation'))
            continue
        status = row.get('status')
        if status == 'conflict':
            conflict = normalized['status'] == 'observed' and any(
                old.get('status') in {'observed', 'conflict'}
                and old.get('observed_model') != row.get('observed_model')
                and _same_observation_context(old, row) for old in prior)
            if not conflict:
                issues.append(_issue('model_usage.entries[' + str(index) + '].status', reference,
                                     'conflict requires incompatible observed models in the same context',
                                     'observed or conflict with a matching prior observation'))
        elif status != normalized['status']:
            issues.append(_issue('model_usage.entries[' + str(index) + '].status', reference,
                                 'model usage status disagrees with supplied provenance',
                                 normalized['status']))
        prior.append(row)
    return issues[:ISSUE_LIMIT]
