'Record supplied per-phase counters and summarize disjoint runs without token estimates.'

import argparse
import json
from pathlib import Path
import sys
from ccr.maintenance.metrics import COUNTERS, normalize_usage, summarize

def main(argv=None, *, prog=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(prog=prog, description=__doc__)
    parser.add_argument('command', choices=('record', 'summarize'))
    parser.add_argument('--input', nargs='+', help='Disjoint run.json files for summarize')
    parser.add_argument('--usage-file', help='Adapter-normalized actual usage JSON; omitted means unknown')
    for name in ('phase', 'role', 'model', 'harness'):
        parser.add_argument('--' + name)
    for name in COUNTERS:
        parser.add_argument('--' + name.replace('_', '-'), type=int)
    args = parser.parse_args(argv)
    try:
        if args.command == 'summarize':
            if not args.input:
                raise ValueError('--input requires disjoint run files')
            result = summarize([json.loads(Path(path).read_text(encoding='utf-8')) for path in args.input])
        else:
            if not args.phase or not args.role:
                raise ValueError('record requires --phase and --role')
            usage = json.loads(Path(args.usage_file).read_text(encoding='utf-8')) if args.usage_file else None
            result = {name: getattr(args, name) for name in ('phase', 'role', 'model', 'harness') + COUNTERS}
            result['usage'] = normalize_usage(usage)
            summarize([result])  # validate counters before emitting anything
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
