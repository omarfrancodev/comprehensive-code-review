'Prepare and verify exact public comment bytes; this helper never publishes.'

import argparse
import json
import sys
from ccr.archive.compact import read_compact
from ccr.execution.workspace_manifest import owned_session
from ccr.execution import workspaces as workspace_ops
from ccr.execution.candidates import write_new_json
from ccr.reporting.comment import (_read_body, _read_json, prepare_public_comment,
                                   verify_public_comment)
from ccr.execution.disclosure import read_selected_disclosure
from ccr.reporting.finding_publication import read_finding_publication_context
from ccr.reporting.check_disclosure import build_explanation_only_disclosure

_DISCLOSURE_PATH = 'evidence/check-disclosure.json'


def _read_comment_source(args):
    if args.run_dir is None:
        if bool(args.check_disclosure_context) != bool(args.check_disclosure_sources):
            raise ValueError('check disclosure context and source catalog must be supplied together')
        disclosure, sources = (
            read_selected_disclosure(args.check_disclosure_context, args.check_disclosure_sources)
            if args.check_disclosure_context else (None, None))
        return _read_json(args.input, 'record'), disclosure, sources

    if args.check_disclosure_context is not None or args.check_disclosure_sources is not None:
        raise ValueError('--run-dir cannot be combined with explicit check disclosure flags')
    retained = read_compact(args.run_dir)
    record, sources = retained['record'], retained['sources']
    context = json.loads(sources['evidence/context.json'])
    reference = context.get('check_disclosure_reference')
    if reference is None:
        if _DISCLOSURE_PATH in sources:
            raise ValueError('compact check disclosure sidecar exists without a declared reference')
        return record, build_explanation_only_disclosure(record) if record['checks'] else None, None

    # Auxiliary retained evidence can affect redaction when reconstructing the sidecar.
    return record, json.loads(sources[reference]), sources


def main(argv=None, *, prog=None):
    parser = argparse.ArgumentParser(prog=prog, description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prepare = commands.add_parser('prepare', help='Render a new exact public comment draft')
    prepare.add_argument('--session', required=True)
    prepare.add_argument('--output', required=True)
    prepare.add_argument('--publication-context')
    prepare.add_argument('--check-publication-context')
    prepare.add_argument('--coverage-publication-context')
    prepare.add_argument('--finding-publication-context')
    verify = commands.add_parser('verify', help='Verify exact local or observed remote comment bytes')
    verify.add_argument('--draft', required=True)
    verify.add_argument('--body', required=True)
    verify.add_argument('--remote', action='store_true')
    verify.add_argument('--remote-transport', choices=('gitlab',),
                        help='Enable the GitLab note comparison for an observed remote body')
    for item in (prepare, verify):
        source = item.add_mutually_exclusive_group(required=True)
        source.add_argument('--input', help='Read a standalone review record')
        source.add_argument('--run-dir', help='Read a verified, complete compact archive')
        item.add_argument('--check-disclosure-context')
        item.add_argument('--check-disclosure-sources')
    args = parser.parse_args(argv)
    if args.command == 'verify' and args.remote_transport and not args.remote:
        parser.error('--remote-transport requires --remote')
    try:
        record, disclosure, disclosure_sources = _read_comment_source(args)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({'status': 'error', 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    if args.command == 'prepare':
        try:
            publication_context = (_read_json(args.publication_context, 'publication context')
                                   if args.publication_context else None)
            check_context = (_read_json(args.check_publication_context, 'check publication context')
                             if args.check_publication_context else None)
            coverage_context = (_read_json(args.coverage_publication_context, 'coverage publication context')
                                if args.coverage_publication_context else None)
            finding_context = (read_finding_publication_context(args.finding_publication_context)
                               if args.finding_publication_context else None)
            session_dir, _, workspace_manifest = owned_session(args.session)
        except (OSError, ValueError, TypeError, KeyError, workspace_ops.ReviewError) as exc:
            print(json.dumps({'status': 'error', 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
            return 2
        try:
            draft = prepare_public_comment(
                record, publication_context=publication_context,
                check_publication_context=check_context,
                coverage_publication_context=coverage_context, finding_publication_context=finding_context,
                check_disclosure_context=disclosure, check_disclosure_sources=disclosure_sources)
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
        draft = _read_json(args.draft, 'draft')
        body = _read_body(args.body)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({'status': 'error', 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    try:
        if args.run_dir is not None and isinstance(draft, dict) and draft.get('schema_version') in (2, 3):
            raise ValueError('verify schema 2/3 drafts with --input and their original disclosure selection')
        result = verify_public_comment(record, draft, body, remote=args.remote,
            remote_transport=args.remote_transport,
            check_disclosure_context=disclosure, check_disclosure_sources=disclosure_sources)
    except (ValueError, TypeError) as exc:
        print(json.dumps({'status': 'error', 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
