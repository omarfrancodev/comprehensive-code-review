#!/usr/bin/env python3
"""Compatibility CLI for review preparation setup."""
import sys

from ccr.execution.candidates import write_new_json as _write_new_json
from ccr.workflow.builders import (
    _issues_message, _json_bytes, build_assignment_event, build_context,
    build_model_usage_update, build_profile_selection,
)
from ccr.workflow.setup import (
    MAX_INPUT_BYTES, REFERENCE_INDEX, SHA256, _read_input,
    _session_evidence_file, _validate_session_reference_index, main, run_command,
)

_run_command = run_command

if __name__ == '__main__':
    sys.exit(main())
