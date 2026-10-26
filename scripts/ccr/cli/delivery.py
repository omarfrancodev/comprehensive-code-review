'Explicitly deliver a portable projection of a retained review; never review again.'

import argparse
import json
import sys
from ccr.reporting.delivery import deliver
from ccr.shared.json_io import read_json

def main(argv=None, *, prog=None):
    parser = argparse.ArgumentParser(prog=prog, description=__doc__)
    parser.add_argument('--run-dir', required=True)
    parser.add_argument('--delivery', choices=('full', 'brief'), required=True)
    parser.add_argument('--project-root', required=True)
    parser.add_argument('--output-root', help='Delivery root, relative to project-root or absolute; not the final scope/review directory')
    parser.add_argument('--context', help='Optional JSON containing only previously collected context')
    args = parser.parse_args(argv)
    try:
        context = read_json(args.context) if args.context else None
        destination = deliver(args.run_dir, args.delivery, args.project_root, args.output_root, context)
        print(json.dumps({'delivery_dir': str(destination)}, ensure_ascii=False))
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
