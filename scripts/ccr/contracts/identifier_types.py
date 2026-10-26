"""Canonical identifier syntax used by review contracts."""
import re

def canonical_id(identifier, prefix):
    if not isinstance(identifier, str) or not re.fullmatch(prefix + r'[0-9]{3,}', identifier):
        return False
    digits = identifier[1:]
    significant = digits.lstrip('0')
    # Avoid integer conversion: hostile numeric strings can exceed Python's limit.
    return bool(significant) and digits == significant.zfill(3)

def review_id(identifier):
    return isinstance(identifier, str) and bool(re.fullmatch(r'CR-[0-9a-f]{20}', identifier))
