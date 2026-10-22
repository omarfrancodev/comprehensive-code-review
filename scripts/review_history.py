"""Read and port a verifiable old review as a three-file consultation package."""
import argparse
import json
import sys

from ccr.archive import reader as artifacts
from ccr.archive.history import (
    CONTENT_LIMIT, HEX, HISTORY_FILES, METADATA_LIMIT, HistoryError,
    _created_hint, _decode_json, _hash, _history_payload, _json_bytes,
    _read, _scope_hint, _source_snapshot, copy_field, inspect_source,
    port_review, show_history, verify_history,
)

def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    inspect = commands.add_parser('inspect')
    inspect.add_argument('--source-run', required=True)
    port = commands.add_parser('port')
    port.add_argument('--source-run', required=True)
    port.add_argument('--output-root')
    show = commands.add_parser('show')
    show.add_argument('--history-dir', required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'inspect':
            print(json.dumps(inspect_source(args.source_run), ensure_ascii=False))
        elif args.command == 'port':
            print(json.dumps(port_review(args.source_run, args.output_root), ensure_ascii=False))
        else:
            print(show_history(args.history_dir), end='')
        return 0
    except (OSError, TypeError, KeyError, ValueError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
