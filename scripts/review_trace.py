"""Compact milestone trace schema, independent of review and archive schemas.

Sequence and timestamps describe recording order at the coordinator, not a total
order of execution across agents. This module has no durable writer: ownership,
transactions and recovery belong exclusively to review_artifacts.
"""
from datetime import datetime, timezone
import hashlib
import json
import re

SCHEMA_VERSION = 1
NAME = 'trazabilidad.jsonl'
EXTERNAL_KINDS = {'agent', 'profile', 'discovery', 'check', 'grouped-verification',
                  'freshness', 'authorized-publication', 'cleanup', 'interruption'}
HELPER_KINDS = {'prepare', 'register', 'retain', 'validation', 'handoff', 'close'}
FIELDS = {'kind', 'status', 'summary', 'actor', 'executor', 'provenance', 'evidence', 'relations', 'authority', 'occurred_at'}
STATUSES = {'started', 'completed', 'passed', 'failed', 'skipped', 'pending', 'blocked',
            'selected', 'retained', 'authorized', 'unchanged'}


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def _text(value, limit, label):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or any(ord(c) < 32 for c in value):
        raise ValueError('invalid or unbounded trace ' + label)


def _identity(value, *, actor=False):
    fields = {'name', 'provider_id'} | ({'kind'} if actor else set())
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError('invalid trace actor/executor identity')
    _text(value['name'], 160, 'identity')
    if value['provider_id'] is not None:
        _text(value['provider_id'], 160, 'provider ID')
    if actor and (not isinstance(value['kind'], str) or value['kind'] not in {'helper', 'coordinator', 'agent', 'tool'}):
        raise ValueError('invalid trace actor kind')


def event_input(raw, *, helper=False):
    if not isinstance(raw, dict) or set(raw) - FIELDS or not {'kind', 'status', 'summary'}.issubset(raw):
        raise ValueError('invalid structured trace event fields')
    allowed = EXTERNAL_KINDS | HELPER_KINDS if helper else EXTERNAL_KINDS
    if not isinstance(raw['kind'], str) or not isinstance(raw['status'], str) or raw['kind'] not in allowed or raw['status'] not in STATUSES:
        raise ValueError('unsupported trace milestone or status')
    _text(raw['summary'], 2000, 'summary')
    value = dict(raw)
    value.setdefault('actor', {'kind': 'helper' if helper else 'coordinator',
                               'name': 'review_artifacts' if helper else 'coordinator', 'provider_id': None})
    value.setdefault('executor', None)
    value.setdefault('provenance', {'kind': 'helper' if helper else 'agent', 'source': None})
    value.setdefault('evidence', [])
    value.setdefault('relations', [])
    value.setdefault('authority', None)
    value.setdefault('occurred_at', None)
    if value['occurred_at'] is not None:
        _utc_time(value['occurred_at'], 'execution')
    _identity(value['actor'], actor=True)
    if value['executor'] is not None:
        _identity(value['executor'])
    provenance = value['provenance']
    if (not isinstance(provenance, dict) or set(provenance) != {'kind', 'source'}
            or not isinstance(provenance['kind'], str)
            or provenance['kind'] not in {'helper', 'tool', 'agent', 'recovered'}):
        raise ValueError('invalid trace provenance')
    if provenance['source'] is not None:
        _text(provenance['source'], 500, 'provenance source')
    for field in ('evidence', 'relations'):
        if not isinstance(value[field], list) or len(value[field]) > 24:
            raise ValueError('invalid or unbounded trace ' + field)
    for ref in value['evidence']:
        _text(ref, 500, 'evidence reference')
    for relation in value['relations']:
        if not isinstance(relation, dict) or set(relation) != {'relation', 'target'}:
            raise ValueError('invalid trace relation')
        if not isinstance(relation['relation'], str) or relation['relation'] not in {'verifies', 'supports', 'depends_on', 'follows', 'reuses', 'supersedes', 'records', 'generated_from'}:
            raise ValueError('invalid trace relation type')
        _text(relation['target'], 500, 'relation target')
    if value['authority'] is not None:
        _text(value['authority'], 1000, 'authority')
    if value['kind'] == 'authorized-publication' and value['authority'] is None:
        raise ValueError('publication milestone requires explicit authorization provenance')
    if len(encoded(value)) > 8192:
        raise ValueError('trace event exceeds bounded milestone size')
    return value


def event_from_execution(raw: dict, metadata: dict, source: str) -> dict:
    """Use an existing wrapper boundary timestamp without inferring actor/status."""
    value = event_input(raw)
    if not isinstance(metadata, dict):
        raise ValueError('execution metadata must be an object')
    _text(source, 500, 'provenance source')
    if value['status'] == 'started':
        key = 'started_at'
    elif value['status'] in {'completed', 'passed', 'failed', 'blocked', 'skipped'}:
        key = 'finished_at'
    else:
        raise ValueError('event status has no execution timestamp mapping')
    observed = metadata.get(key)
    if observed is not None:
        _utc_time(observed, 'execution')
    supplied = value['occurred_at']
    if supplied is not None:
        if observed is None or (datetime.fromisoformat(supplied.replace('Z', '+00:00'))
                                != datetime.fromisoformat(observed.replace('Z', '+00:00'))):
            raise ValueError('execution timestamp conflicts with supplied occurred_at')
    value['occurred_at'] = supplied if supplied is not None else observed
    value['provenance'] = {'kind': 'tool', 'source': source}
    return event_input(value)


def append(data, manifest, raw, *, helper=False):
    value = event_input(raw, helper=helper)
    descriptor = manifest.get('trace', {'schema_version': SCHEMA_VERSION, 'events': 0, 'last_sha256': None})
    sequence = descriptor['events'] + 1
    value.update(schema_version=SCHEMA_VERSION, sequence=sequence, event_id='E' + str(sequence).zfill(6),
                 run_id=manifest['run_id'], review_id='CR-' + manifest['run_id'],
                 recorded_at=datetime.now(timezone.utc).isoformat(),
                 recorder={'kind': 'helper', 'name': 'review_artifacts', 'provider_id': None},
                 previous_sha256=descriptor['last_sha256'])
    value['sha256'] = digest(encoded(value))
    line = encoded(value) + b'\n'
    return data + line, {'schema_version': SCHEMA_VERSION, 'events': sequence, 'last_sha256': value['sha256']}, value


def _utc_time(value, label):
    if not isinstance(value, str) or len(value) > 50:
        raise ValueError('invalid trace UTC ' + label + ' time')
    try:
        timestamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if timestamp.utcoffset() is None or timestamp.utcoffset().total_seconds() != 0:
            raise ValueError('not UTC')
    except (TypeError, ValueError) as exc:
        raise ValueError('invalid trace UTC ' + label + ' time') from exc


def verify(data, descriptor, run_id):
    if (not isinstance(descriptor, dict) or set(descriptor) != {'schema_version', 'events', 'last_sha256'}
            or descriptor['schema_version'] != SCHEMA_VERSION or type(descriptor['events']) is not int
            or descriptor['events'] < 1 or not isinstance(descriptor['last_sha256'], str)):
        raise ValueError('invalid trace closure descriptor')
    if not data.endswith(b'\n'):
        raise ValueError('trace is truncated or missing')
    previous = None
    count = 0
    for count, line in enumerate(data.splitlines(), 1):
        try:
            value = json.loads(line)
        except (ValueError, UnicodeError) as exc:
            raise ValueError('invalid trace JSONL') from exc
        system_fields = {'schema_version', 'sequence', 'event_id', 'run_id', 'review_id',
                         'recorded_at', 'recorder', 'previous_sha256', 'sha256'}
        if not isinstance(value, dict) or set(value) != FIELDS | system_fields:
            raise ValueError('invalid trace event schema')
        event_input({key: value[key] for key in FIELDS}, helper=True)
        if (value['schema_version'] != SCHEMA_VERSION or type(value['sequence']) is not int
                or value['sequence'] != count or value['event_id'] != 'E' + str(count).zfill(6)
                or value['run_id'] != run_id or value['review_id'] != 'CR-' + run_id
                or value['previous_sha256'] != previous
                or value['recorder'] != {'kind': 'helper', 'name': 'review_artifacts', 'provider_id': None}):
            raise ValueError('trace sequence, ownership or chain differs from closure')
        _utc_time(value['recorded_at'], 'recording')
        claimed = value.pop('sha256')
        if not isinstance(claimed, str) or not re.fullmatch('[0-9a-f]{64}', claimed) or digest(encoded(value)) != claimed:
            raise ValueError('trace event integrity mismatch')
        previous = claimed
    if count != descriptor['events'] or previous != descriptor['last_sha256']:
        raise ValueError('trace length or tip differs from closure')
