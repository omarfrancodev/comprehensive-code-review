'Capture and validate explicit local check commands without shell parsing.'

import argparse
import json
from pathlib import Path
import subprocess
import sys
from ccr.contracts.receipts import receipt_reference
from ccr.execution import workspaces as workspace_ops
from ccr.execution.checks import _read_request, capture_check

def main(argv=None, *, prog=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(prog=prog, description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    run = commands.add_parser('run', help='Run one explicit local check and write a new receipt')
    run.add_argument('--request', required=True)
    run.add_argument('--output-dir', required=True)
    args = parser.parse_args(argv)
    try:
        request = _read_request(args.request)
        receipt = capture_check(**request, output_dir=args.output_dir)
        receipt_path = Path(args.output_dir).absolute() / Path(receipt_reference(
            receipt['check_id'], args.output_dir)).name
        print(json.dumps({'status': 'captured', 'receipt_path': str(receipt_path),
                          'receipt': receipt}, ensure_ascii=False, allow_nan=False))
        # A valid capture returns zero even when the check itself returned nonzero.
        return 0
    except (OSError, ValueError, TypeError, KeyError, workspace_ops.ReviewError,
            subprocess.SubprocessError) as exc:
        print(json.dumps({'status': 'error', 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
