'Prepare and verify exact public comment bytes; this helper never publishes.'

import argparse
import json
import sys
from ccr.execution.workspace_manifest import owned_session
from ccr.execution import workspaces as workspace_ops
from ccr.execution.candidates import write_new_json
from ccr.reporting.comment import (_read_body, _read_json, prepare_public_comment,
                                   verify_public_comment)

def main(argv=None, *, prog=None):
    parser = argparse.ArgumentParser(prog=prog, description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prepare = commands.add_parser('prepare', help='Render a new exact public comment draft')
    prepare.add_argument('--input', required=True)
    prepare.add_argument('--session', required=True)
    prepare.add_argument('--output', required=True)
    prepare.add_argument('--publication-context')
    prepare.add_argument('--check-publication-context')
    prepare.add_argument('--coverage-publication-context')
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
            coverage_context = (_read_json(args.coverage_publication_context, 'coverage publication context')
                                if args.coverage_publication_context else None)
            session_dir, _, workspace_manifest = owned_session(args.session)
        except (OSError, ValueError, TypeError, KeyError, workspace_ops.ReviewError) as exc:
            print(json.dumps({'status': 'error', 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
            return 2
        try:
            draft = prepare_public_comment(
                record, publication_context=publication_context,
                check_publication_context=check_context,
                coverage_publication_context=coverage_context)
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


if __name__ == '__main__':
    raise SystemExit(main())
