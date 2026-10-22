"""Compatibility command surface for archive inspection and lookup."""
from ccr.archive import layout as review_layout
from ccr.archive.inspection import (
    _action, _decode_json_bytes, _native_archive, _recover_source_action,
    _abandoned_source_action, _superseded_actions, classify_candidate,
    continuation_decision, inspect_run, operational_summary,
)
from ccr.archive.lookup import (
    HASH, LOOKUP_CURSOR_BYTES, LOOKUP_REPORT_BYTES, OLD_RUN_NAME, RUN_NAME,
    _candidate, _cursor_decode, _cursor_encode, _hash_file_bounded,
    _legacy_candidate, _legacy_scope_prefix, _read_candidate_record,
    find_candidates, select_latest,
)
from ccr.shared.json_io import read_json
from ccr.workflow import inputs as review_inputs
from ccr.workflow.inputs import candidate_inputs as _candidate_inputs, validate_current_inputs

def main():
    import argparse
    import json
    import sys
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', required=True)
    parser.add_argument('--current-inputs')
    args = parser.parse_args()
    try:
        value = read_json(args.current_inputs) if args.current_inputs else None
        print(json.dumps(inspect_run(args.run_dir, current_inputs=value), ensure_ascii=False, allow_nan=False))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
