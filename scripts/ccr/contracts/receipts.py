"""Pure validation and naming rules for captured check receipts."""
from datetime import datetime
import hashlib
import json
import ntpath
from pathlib import Path
import posixpath
import re
import shlex
from ccr.contracts.reference_types import ReferenceIssue
from ccr.contracts.references import parse_reference
from ccr.contracts.checks import purpose_errors

RECEIPT_FIELDS = {'schema_version', 'check_id', 'argv', 'cwd', 'revision', 'executor',
                  'started_at', 'finished_at', 'exit_code', 'stdout', 'stderr'}
STREAM_FIELDS = {'reference', 'sha256', 'bytes'}
CHECK_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}')
SHA256 = re.compile(r'[0-9a-f]{64}')
MAX_REQUEST_BYTES = 131072
MAX_CONTEXT_BYTES = 131072

def _issue(field, reference, message, expected):
    return {'code': 'invalid_receipt', 'field': field, 'reference': reference,
            'message': message[:500], 'expected': expected[:500]}

def _text(value, maximum=4000):
    return isinstance(value, str) and bool(value.strip()) and len(value) <= maximum \
        and not any(ord(char) < 32 for char in value)

def _canonical_command_matches(value, argv):
    """Accept literal command controls only when the exact argv renders to them."""
    return isinstance(value, str) and len(value) <= 4000 and value == shlex.join(argv)

def _workspace_identity(value):
    if not isinstance(value, str) or not value.strip():
        return None
    drive, _ = ntpath.splitdrive(value)
    if drive and ntpath.isabs(value):
        return 'windows:' + ntpath.normcase(ntpath.normpath(value))
    if posixpath.isabs(value):
        return 'posix:' + posixpath.normpath(value)
    return None

def _timestamp(value):
    if not isinstance(value, str) or len(value) > 64:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed

def validate_receipt(receipt: dict, sources: dict[str, bytes], *,
                     check: dict, executors: list[dict]) -> list[ReferenceIssue]:
    """Validate a captured receipt against supplied bytes and registered identities only."""
    issues = []

    def fail(field, reference, message, expected):
        issues.append(_issue(field, reference, message, expected))

    expected_fields = RECEIPT_FIELDS | ({'purpose'} if isinstance(receipt, dict) and receipt.get('schema_version') == 2 else set())
    if not isinstance(receipt, dict) or set(receipt) != expected_fields:
        return [_issue('receipt', None, 'receipt has missing or unknown fields',
                       'exactly ' + ', '.join(sorted(expected_fields)))]
    if type(receipt.get('schema_version')) is not int or receipt['schema_version'] not in (1, 2):
        fail('schema_version', None, 'unsupported receipt schema', 'schema_version 1 or 2')
    if receipt.get('schema_version') == 2:
        for message in purpose_errors(receipt.get('purpose'), 'purpose'):
            fail('purpose', None, message, 'declared purpose before execution')
        if isinstance(check, dict) and check.get('purpose') != receipt.get('purpose'):
            fail('purpose', None, 'receipt purpose differs from the source check', 'identical purpose')
    check_id = receipt.get('check_id')
    if not isinstance(check_id, str) or CHECK_ID.fullmatch(check_id) is None:
        fail('check_id', None, 'invalid check ID', 'bounded safe check identity')
    valid_argv = (isinstance(receipt.get('argv'), list) and bool(receipt['argv'])
            and len(receipt['argv']) <= 256
            and all(isinstance(item, str) and len(item) <= 8192 and '\0' not in item
                    for item in receipt['argv'])
            and bool(receipt['argv'][0].strip()))
    if not valid_argv:
        fail('argv', None, 'argv must be a bounded literal argument array',
             'nonempty executable and literal string arguments')
    if not _text(receipt.get('cwd')):
        fail('cwd', None, 'cwd must be a nonempty observed workspace path', 'bounded path text')
    if not _text(receipt.get('revision')):
        fail('revision', None, 'revision must be observed nonempty text', 'bounded revision identity')
    if not _text(receipt.get('executor')):
        fail('executor', None, 'executor must be a registered nonempty identity', 'bounded executor ID')

    started = _timestamp(receipt.get('started_at'))
    if started is None:
        fail('started_at', None, 'started_at must be a timezone-aware observation',
             'an ISO-8601 timestamp with offset')
    finished_value = receipt.get('finished_at')
    finished = _timestamp(finished_value) if finished_value is not None else None
    if finished_value is not None and finished is None:
        fail('finished_at', None, 'finished_at must be a timezone-aware observation or null',
             'an ISO-8601 timestamp with offset or null')
    exit_code = receipt.get('exit_code')
    if exit_code is not None and (type(exit_code) is not int or abs(exit_code) > 2147483647):
        fail('exit_code', None, 'exit_code must be an observed integer or null', 'integer or null')
    if started is not None and finished is not None and finished < started:
        fail('finished_at', None, 'finished_at precedes started_at', 'ordered observed timestamps')
    if (exit_code is None) != (finished is None):
        fail('exit_code', None, 'unfinished process requires null exit_code and finished_at',
             'both completion fields present or both null')

    for stream_name in ('stdout', 'stderr'):
        stream = receipt.get(stream_name)
        field = stream_name
        if not isinstance(stream, dict) or set(stream) != STREAM_FIELDS:
            fail(field, None, 'stream descriptor has missing or unknown fields',
                 'exact reference, sha256 and bytes fields')
            continue
        reference = stream.get('reference')
        try:
            path, fragment = parse_reference(reference, field=field)
            if fragment is not None or not path.startswith('evidence/'):
                raise ValueError('stream reference must be a flat local evidence file')
        except (TypeError, ValueError) as exc:
            fail(field + '.reference', reference if isinstance(reference, str) else None,
                 str(exc), 'a flat evidence file reference without a fragment')
            continue
        stream_digest = stream.get('sha256')
        if not isinstance(stream_digest, str) or not SHA256.fullmatch(stream_digest):
            fail(field + '.sha256', reference, 'stream digest must be lowercase SHA-256',
                 '64 lowercase hexadecimal characters')
        if type(stream.get('bytes')) is not int or stream['bytes'] < 0:
            fail(field + '.bytes', reference, 'stream byte count must be a nonnegative integer',
                 'nonnegative integer')
        data = sources.get(path) if isinstance(sources, dict) else None
        if not isinstance(data, bytes):
            fail(field + '.reference', reference, 'selected stream bytes are missing', path)
        else:
            if isinstance(stream_digest, str) and SHA256.fullmatch(stream_digest) \
                    and hashlib.sha256(data).hexdigest() != stream_digest:
                fail(field + '.sha256', reference, 'selected stream digest differs from receipt',
                     stream_digest)
            if type(stream.get('bytes')) is int and len(data) != stream['bytes']:
                fail(field + '.bytes', reference, 'selected stream byte count differs from receipt',
                     str(stream['bytes']))
    stdout_row, stderr_row = receipt.get('stdout'), receipt.get('stderr')
    if (isinstance(stdout_row, dict) and isinstance(stderr_row, dict)
            and isinstance(stdout_row.get('reference'), str)
            and stdout_row.get('reference') == stderr_row.get('reference')):
        fail('stderr.reference', stderr_row.get('reference'),
             'stdout and stderr must use distinct evidence files', 'a distinct flat stream reference')

    if not isinstance(check, dict):
        fail('check', None, 'check binding must be an object', 'the source check object')
    else:
        if check.get('id') != check_id:
            fail('check_id', None, 'receipt check ID differs from the source check', str(check.get('id')))
        if check.get('revision') != receipt.get('revision'):
            fail('revision', None, 'receipt revision differs from the source check', str(check.get('revision')))
        if (not valid_argv
                or not _canonical_command_matches(check.get('command'), receipt['argv'])):
            fail('command', None, 'source check command differs from the receipt argv',
                 'the source check command matching receipt argv')
        execution = check.get('execution')
        if (not isinstance(execution, dict) or execution.get('kind') != 'local'
                or execution.get('executor') != receipt.get('executor')):
            fail('executor', None, 'receipt must bind to the source local check executor',
                 'matching local check execution executor')
        status = check.get('status')
        if status not in ('passed', 'failed', 'blocked', 'not_run'):
            fail('check.status', None, 'source check has an unsupported status',
                 'passed, failed, blocked or not_run')
        elif exit_code is None:
            if status in ('passed', 'failed'):
                fail('exit_code', None, 'unfinished command cannot accredit passed or failed',
                     'observed exit code for a completed check')
        elif status == 'passed' and exit_code != 0:
            fail('exit_code', None, 'passed check has a nonzero exit code', 'exit code 0')
        elif status == 'failed' and exit_code == 0:
            fail('exit_code', None, 'failed check has a zero exit code', 'nonzero exit code')
        elif status in ('blocked', 'not_run'):
            fail('exit_code', None, 'blocked or not_run check cannot claim a completed command', 'null')

    if not isinstance(executors, list):
        fail('executor', None, 'executors must be an array', 'registered executor entries')
    else:
        matching = [row for row in executors if isinstance(row, dict)
                    and row.get('executor') == receipt.get('executor')]
        if len(matching) != 1:
            fail('executor', None, 'receipt executor is not uniquely registered', 'one matching executor')
        else:
            executor = matching[0]
            expected_revision = executor.get('snapshot') or executor.get('revision')
            if receipt.get('revision') != expected_revision:
                fail('revision', None, 'receipt revision differs from registered executor',
                     str(expected_revision))
            if (_workspace_identity(receipt.get('cwd')) is None
                    or _workspace_identity(receipt.get('cwd'))
                    != _workspace_identity(executor.get('workspace'))):
                fail('cwd', None, 'receipt cwd differs from the registered executor workspace',
                     'the registered executor workspace')

    return issues

def receipt_reference(check_id: str, output_dir: str | Path) -> str:
    """Return the flat archive reference used for this attempt's receipt."""
    if not isinstance(check_id, str) or CHECK_ID.fullmatch(check_id) is None:
        raise ValueError('check_id must be a bounded safe check identity')
    name = Path(output_dir).name
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}', name):
        raise ValueError('output directory name must be a bounded safe attempt identity')
    return f'evidence/{name}-{check_id}-receipt.json'

def is_receipt_reference(reference, check_id) -> bool:
    """Recognize the explicit flat receipt filename convention for one check."""
    if not isinstance(reference, str) or not isinstance(check_id, str) \
            or CHECK_ID.fullmatch(check_id) is None:
        return False
    return reference.startswith('evidence/') and reference.endswith('-' + check_id + '-receipt.json')

def validate_record_receipts(record: dict, sources: dict[str, bytes],
                             executors: list[dict]) -> list[ReferenceIssue]:
    """Validate only checks that explicitly reference a named receipt artifact."""
    if not isinstance(record, dict) or record.get('schema_version') not in (9, 10, 11):
        return []
    checks = record.get('checks')
    if not isinstance(checks, list):
        return []
    issues = []
    for number, check in enumerate(checks):
        if not isinstance(check, dict):
            continue
        reference = check.get('reference')
        if not is_receipt_reference(reference, check.get('id')):
            continue
        field = f'checks[{number}].reference'
        try:
            path, fragment = parse_reference(reference, field=field)
            if fragment is not None or not path.startswith('evidence/'):
                raise ValueError('receipt reference must identify a flat evidence file without a fragment')
        except (TypeError, ValueError) as exc:
            issues.append(_issue(field, reference, str(exc), 'a flat local check receipt reference'))
            continue
        data = sources.get(path) if isinstance(sources, dict) else None
        if not isinstance(data, bytes):
            issues.append(_issue(field, reference, 'selected check receipt bytes are missing', path))
            continue
        try:
            receipt = json.loads(data.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError):
            issues.append(_issue(field, reference, 'selected check receipt is not UTF-8 JSON',
                                 'a schema 1 check receipt'))
            continue
        if (record.get('schema_version') == 11 and check.get('reused') is False
                and isinstance(check.get('execution'), dict) and check['execution'].get('kind') == 'local'
                and (not isinstance(receipt, dict) or receipt.get('schema_version') != 2)):
            issues.append(_issue(field, reference, 'new local check requires a purpose-bound schema 2 receipt',
                                 'schema 2 receipt with the original purpose'))
        issues.extend(validate_receipt(receipt, sources, check=check, executors=executors))
    return issues[:100]
