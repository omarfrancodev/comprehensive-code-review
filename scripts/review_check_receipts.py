#!/usr/bin/env python3
"""Compatibility CLI for explicit local check capture and receipt validation."""
import sys

from ccr.execution.checks import (
    CHECK_ID, MAX_CONTEXT_BYTES, MAX_REQUEST_BYTES, RECEIPT_FIELDS, SHA256,
    STREAM_FIELDS, _canonical_command_matches, _file_identity, _issue,
    _json_bytes, _now, _read_request, _text, _timestamp,
    _validate_owned_workspace, _workspace_identity, capture_check, main,
    is_receipt_reference, receipt_reference, validate_receipt,
    validate_record_receipts,
)

if __name__ == '__main__':
    sys.exit(main())
