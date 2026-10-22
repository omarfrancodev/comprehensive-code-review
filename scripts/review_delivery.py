#!/usr/bin/env python3
"""Compatibility CLI for portable delivery of retained reviews."""
import sys

from ccr.reporting.delivery import (
    _Projection, _brief, _context_markdown, _hash, _human, _json, _public_url,
    _write_file, deliver, main,
)

if __name__ == '__main__':
    sys.exit(main())
