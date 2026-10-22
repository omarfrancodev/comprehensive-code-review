#!/usr/bin/env python3
"""Prepare and verify exact public comment bytes; this helper never publishes."""
import sys

from ccr.reporting.comment import (
    DRAFT_FIELDS, MAX_BODY_BYTES, MAX_JSON_BYTES, _digest_text, _read_body,
    _read_json, main, prepare_public_comment, verify_public_comment,
)

if __name__ == '__main__':
    sys.exit(main())
