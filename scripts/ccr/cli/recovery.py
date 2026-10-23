'Read-only inspection and bounded classification for durable review runs.'

import argparse
import json
import sys
from ccr.archive.inspection import inspect_run
from ccr.shared.json_io import read_json

def main(argv=None, *, prog=None):
    import argparse
    import json
    import sys
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(prog=prog, description=__doc__)
    parser.add_argument('--run-dir', required=True)
    parser.add_argument('--current-inputs')
    args = parser.parse_args(argv)
    try:
        value = read_json(args.current_inputs) if args.current_inputs else None
        print(json.dumps(inspect_run(args.run_dir, current_inputs=value), ensure_ascii=False, allow_nan=False))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
