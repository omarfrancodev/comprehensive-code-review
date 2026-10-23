'Build validated review preparation candidates inside an owned evidence session.'

import argparse
import json
import sys
from ccr.execution import workspaces as workspace_ops
from ccr.workflow.setup import run_command

def main(argv=None, *, prog=None):
    parser = argparse.ArgumentParser(prog=prog, description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('profile', 'context', 'event'):
        item = sub.add_parser(command)
        item.add_argument('--input', required=True)
        item.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    try:
        result = run_command(args.command, args.input, args.output)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 0
    except (OSError, ValueError, TypeError, KeyError, workspace_ops.ReviewError) as exc:
        print(json.dumps({'status': 'error', 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
