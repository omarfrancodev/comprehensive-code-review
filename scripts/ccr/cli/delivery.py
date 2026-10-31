'Explicitly deliver a portable projection of a retained review; never review again.'

import argparse
import json
import sys
from ccr.reporting.delivery import deliver
from ccr.shared.json_io import read_json
from ccr.execution.disclosure import read_selected_disclosure

def main(argv=None, *, prog=None):
    parser = argparse.ArgumentParser(prog=prog, description=__doc__)
    parser.add_argument('--run-dir', required=True)
    parser.add_argument('--delivery', choices=('full', 'brief'), required=True)
    parser.add_argument('--project-root', required=True)
    parser.add_argument('--output-root', help='Delivery root, relative to project-root or absolute; not the final scope/review directory')
    parser.add_argument('--context', help='Optional JSON containing only previously collected context')
    parser.add_argument('--check-disclosure-context')
    parser.add_argument('--check-disclosure-sources')
    args = parser.parse_args(argv)
    try:
        context = read_json(args.context) if args.context else None
        if bool(args.check_disclosure_context) != bool(args.check_disclosure_sources):
            raise ValueError('check disclosure context and source catalog must be supplied together')
        disclosure, sources = (read_selected_disclosure(args.check_disclosure_context, args.check_disclosure_sources)
            if args.check_disclosure_context else (None, None))
        destination = deliver(args.run_dir, args.delivery, args.project_root, args.output_root, context,
            check_disclosure_context=disclosure, check_disclosure_sources=sources)
        print(json.dumps({'delivery_dir': str(destination)}, ensure_ascii=False))
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
