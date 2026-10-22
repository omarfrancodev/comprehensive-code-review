#!/usr/bin/env python3
"""Compatibility CLI for configured review runners."""
import sys

from ccr.execution.runner import main, normalize_usage, run, stop

if __name__ == '__main__':
    sys.exit(main())
