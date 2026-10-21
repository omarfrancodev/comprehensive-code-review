#!/usr/bin/env python3
"""Validate review records, render Spanish reports, or group explicit duplicate candidates.

Python 3.10+, standard library only. Structural checks never establish finding truth.
"""
import argparse
import json
from pathlib import Path
import sys

from ccr.contracts.identifier_types import *
from ccr.contracts.identifiers import *
from ccr.contracts.review import *
from ccr.contracts.scope import *
from ccr.contracts.validation import *
from ccr.reporting.markdown import *
from ccr.reporting.projections import *
from ccr.reporting.render import *
from ccr.workflow.profiles import canonical_profile


def normalize_profile(value):
    """Resolve request aliases only; never rewrite a retained historical record."""
    if not isinstance(value, str):
        raise ValueError('expected a supported profile name')
    normalized = PROFILE_ALIASES.get(value, value)
    if normalized not in CURRENT_PROFILES:
        raise ValueError('expected focused, standard, deep or extended (economy/balanced aliases accepted)')
    return normalized

def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('validate', 'render-user', 'render-comment', 'render-handoff', 'canonicalize-ids', 'deduplicate'))
    parser.add_argument('--input', required=True, help='Record JSON; for deduplicate: findings array JSON')
    parser.add_argument('--groups', help='Explicit same-cause ID groups JSON; required for deduplicate')
    parser.add_argument('--context', help='Optional explicitly collected handoff provenance JSON')
    parser.add_argument('--publication-context', help='Ephemeral source-bound historical limitation classification for render-comment')
    parser.add_argument('--check-publication-context', help='Ephemeral source-bound public check summaries for render-comment')
    parser.add_argument('--reserved-ids', help='Known review-chain finding/check ID arrays for monotonic allocation')
    args = parser.parse_args()
    try:
        if args.publication_context and args.command != 'render-comment':
            raise ValueError('--publication-context is only applicable to render-comment')
        if args.check_publication_context and args.command != 'render-comment':
            raise ValueError('--check-publication-context is only applicable to render-comment')
        publication_context = json.loads(Path(args.publication_context).read_text(encoding='utf-8')) if args.publication_context else None
        check_publication_context = (json.loads(Path(args.check_publication_context).read_text(encoding='utf-8'))
                                     if args.check_publication_context else None)
        value = json.loads(Path(args.input).read_text(encoding='utf-8'))
        if args.command == 'validate':
            errors = validate(value)
            print(json.dumps({'valid': not errors, 'errors': errors}, ensure_ascii=False))
            return 1 if errors else 0
        if args.command == 'deduplicate':
            if not args.groups:
                raise ValueError('--groups is required')
            groups = json.loads(Path(args.groups).read_text(encoding='utf-8'))
            print(json.dumps(deduplicate(value, groups), ensure_ascii=False))
        elif args.command == 'canonicalize-ids':
            reserved = json.loads(Path(args.reserved_ids).read_text(encoding='utf-8')) if args.reserved_ids else None
            record, mapping = canonicalize_ids(value, reserved_ids=reserved)
            print(json.dumps({'record': record, 'source_mapping': mapping}, ensure_ascii=False))
        elif args.command == 'render-handoff':
            context = json.loads(Path(args.context).read_text(encoding='utf-8')) if args.context else None
            print(render_handoff(value, context=context), end='')
        elif args.command == 'render-comment':
            print(render(value, 'comment', publication_context,
                         check_publication_context=check_publication_context), end='')
        else:
            print(render(value, 'user', publication_context), end='')
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
