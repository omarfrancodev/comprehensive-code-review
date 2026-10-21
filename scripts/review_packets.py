#!/usr/bin/env python3
"""Validate internal compact packets or merge decision deltas; never infer a verdict."""
import argparse
import json
from pathlib import Path
import sys

from ccr.contracts.packets import merge, validate


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('validate', 'merge'))
    parser.add_argument('--input', help='Compact packet JSON for validate')
    parser.add_argument('--context', help='Shared context JSON, including scope/context_id/check ledger')
    parser.add_argument('--discovery', nargs='+', help='Discovery packet JSON paths')
    parser.add_argument('--verification', help='Verification delta JSON path')
    args = parser.parse_args()
    def read(path):
        if not path:
            raise ValueError('required input path missing; consult --help')
        return json.loads(Path(path).read_text(encoding='utf-8'))
    try:
        if args.command == 'validate':
            errors = validate(read(args.input))
            print(json.dumps({'valid': not errors, 'errors': errors}, ensure_ascii=False))
            return 1 if errors else 0
        print(json.dumps(merge(read(args.context), [read(path) for path in args.discovery or []],
                               read(args.verification) if args.verification else None), ensure_ascii=False))
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
