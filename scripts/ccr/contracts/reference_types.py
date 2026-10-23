"""Shared issue type and bounded local-reference grammar constants."""
import re
from typing import TypedDict
from ccr.archive.trace import NAME as TRACE_NAME

REFERENCE_LIMIT = 500
ISSUE_LIMIT = 100
SHA256 = re.compile(r'[0-9a-f]{64}')
CHECK_TOKEN = re.compile(r'(?<![A-Za-z0-9_])C[0-9]{3,}(?![A-Za-z0-9_])')
INPUT_PURPOSES = {'description', 'requirements', 'notes', 'plan', 'configuration', 'other'}
CANONICAL_NAME = re.compile(r'[A-Za-z0-9._-]+')
WINDOWS_DEVICE = re.compile(r'(?i)(CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])(?:\..*)?')
FIXED_FILES = {'review.json', 'informe.md', 'measurements.json',
               TRACE_NAME, 'handoff.md'}
INITIAL_PROFILE_HISTORY_REFERENCE = 'evidence/context.json#profile_history/0/profile'
LEGACY_INITIAL_PROFILE_REFERENCE = 'evidence/context.json#profile'

class ReferenceIssue(TypedDict):
    code: str
    field: str
    reference: str | None
    message: str
    expected: str

def _issue(code: str, field: str, reference: str | None,
           message: str, expected: str) -> ReferenceIssue:
    return {'code': code, 'field': field, 'reference': reference,
            'message': message[:500], 'expected': expected[:500]}
