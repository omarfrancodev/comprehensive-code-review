"""Prepare and verify exact public comment bytes; this helper never publishes."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

from ccr.execution.candidates import write_new_json
from ccr.execution import workspaces as workspace_ops
from ccr.execution.workspace_manifest import owned_session
from ccr.reporting.projections import publication_digest
from ccr.reporting.render import render as render_record

DRAFT_FIELDS = {'schema_version', 'source_sha256', 'publication_context',
                'check_publication_context', 'body', 'body_sha256'}
MAX_JSON_BYTES = 16 * 1024 * 1024
MAX_BODY_BYTES = 2 * 1024 * 1024

def _digest_text(value):
    try:
        return hashlib.sha256(value.encode('utf-8')).hexdigest()
    except (AttributeError, UnicodeEncodeError) as exc:
        raise ValueError('body_mismatch: body must be valid UTF-8 text') from exc

def prepare_public_comment(record: dict, *, publication_context: dict | None = None,
                           check_publication_context: dict | None = None) -> dict:
    """Render one deterministic draft with source and body hashes."""
    source_hash = publication_digest(record)
    body = render_record(
        record, audience='comment', publication_context=publication_context,
        check_publication_context=check_publication_context)
    return {
        'schema_version': 1,
        'source_sha256': source_hash,
        'publication_context': copy.deepcopy(publication_context),
        'check_publication_context': copy.deepcopy(check_publication_context),
        'body': body,
        'body_sha256': _digest_text(body),
    }

def verify_public_comment(record: dict, draft: dict, body: str, *, remote: bool = False) -> dict:
    """Verify an exact outbound body or an observed remote body against a fresh render."""
    source_hash = publication_digest(record)
    if not isinstance(draft, dict) or set(draft) != DRAFT_FIELDS \
            or type(draft.get('schema_version')) is not int or draft.get('schema_version') != 1:
        raise ValueError('invalid_draft: exact schema 1 fields required')
    if draft.get('source_sha256') != source_hash:
        raise ValueError('source_mismatch: draft is bound to another source record')
    if not isinstance(draft.get('body'), str):
        raise ValueError('body_mismatch: draft body is missing or exceeds the bound')
    try:
        encoded_draft = draft['body'].encode('utf-8')
    except UnicodeEncodeError as exc:
        raise ValueError('body_mismatch: draft body is not valid UTF-8') from exc
    if len(encoded_draft) > MAX_BODY_BYTES:
        raise ValueError('body_mismatch: draft body is missing or exceeds the bound')
    draft_hash = _digest_text(draft['body'])
    if draft.get('body_sha256') != draft_hash:
        raise ValueError('body_mismatch: draft body hash differs from its bytes')
    expected = render_record(
        record, audience='comment', publication_context=draft['publication_context'],
        check_publication_context=draft['check_publication_context'])
    if expected != draft['body']:
        raise ValueError('body_mismatch: draft differs from a fresh canonical render')
    if not isinstance(body, str):
        raise ValueError('body_mismatch: supplied body is missing or exceeds the bound')
    try:
        encoded_body = body.encode('utf-8')
    except UnicodeEncodeError as exc:
        raise ValueError('body_mismatch: supplied body is not valid UTF-8') from exc
    if len(encoded_body) > MAX_BODY_BYTES:
        raise ValueError('body_mismatch: supplied body is missing or exceeds the bound')
    comparable = body.replace('\r\n', '\n') if remote else body
    if comparable != draft['body']:
        raise ValueError('body_mismatch: supplied body differs from the canonical draft')
    return {'verified': True, 'source_sha256': source_hash, 'body_sha256': draft_hash}

def _read_json(path, label):
    source = Path(path)
    try:
        if source.stat().st_size > MAX_JSON_BYTES:
            raise ValueError(label + ' exceeds the bounded size')
        value = json.loads(source.read_text(encoding='utf-8'))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(label + ' is not readable UTF-8 JSON') from exc
    if not isinstance(value, dict):
        raise ValueError(label + ' must be a JSON object')
    return value

def _read_body(path):
    source = Path(path)
    try:
        if source.stat().st_size > MAX_BODY_BYTES:
            raise ValueError('body exceeds the bounded size')
        return source.read_bytes().decode('utf-8')
    except (OSError, UnicodeDecodeError) as exc:
        raise ValueError('body is not readable UTF-8 text') from exc

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prepare = commands.add_parser('prepare', help='Render a new exact public comment draft')
    prepare.add_argument('--input', required=True)
    prepare.add_argument('--session', required=True)
    prepare.add_argument('--output', required=True)
    prepare.add_argument('--publication-context')
    prepare.add_argument('--check-publication-context')
    verify = commands.add_parser('verify', help='Verify exact local or observed remote comment bytes')
    verify.add_argument('--input', required=True)
    verify.add_argument('--draft', required=True)
    verify.add_argument('--body', required=True)
    verify.add_argument('--remote', action='store_true')
    args = parser.parse_args(argv)
    if args.command == 'prepare':
        try:
            record = _read_json(args.input, 'record')
            publication_context = (_read_json(args.publication_context, 'publication context')
                                   if args.publication_context else None)
            check_context = (_read_json(args.check_publication_context, 'check publication context')
                             if args.check_publication_context else None)
            session_dir, _, workspace_manifest = owned_session(args.session)
        except (OSError, ValueError, TypeError, KeyError, workspace_ops.ReviewError) as exc:
            print(json.dumps({'status': 'error', 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
            return 2
        try:
            draft = prepare_public_comment(
                record, publication_context=publication_context,
                check_publication_context=check_context)
        except (ValueError, TypeError) as exc:
            print(json.dumps({'status': 'error', 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
            return 1
        try:
            output = write_new_json(session_dir, args.output, draft)
        except (OSError, ValueError, TypeError, workspace_ops.ReviewError) as exc:
            print(json.dumps({'status': 'error', 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
            return 2
        print(json.dumps({'status': 'prepared', 'output': str(output),
                          'session_id': workspace_manifest['session_id'],
                          'source_sha256': draft['source_sha256'],
                          'body_sha256': draft['body_sha256']}, ensure_ascii=False))
        return 0

    try:
        record = _read_json(args.input, 'record')
        draft = _read_json(args.draft, 'draft')
        body = _read_body(args.body)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({'status': 'error', 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    try:
        result = verify_public_comment(record, draft, body, remote=args.remote)
    except (ValueError, TypeError) as exc:
        print(json.dumps({'status': 'error', 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0
