"""Synthetic public-comment fixtures model the MR 1021 renderer mismatch."""
from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
from ccr.reporting import projections as review_publication
from recovery_fixtures import record10


def publication_record() -> dict:
    record = record10('focused', 'explicit')
    head, base = record['scope']['head'], record['scope']['base']
    record['checks'] = [
        {
            'id': 'C001', 'command': 'dotnet test --filter Scheduling', 'revision': head,
            'status': 'passed', 'failure_kind': None,
            'evidence': 'La respuesta contiene los datos esperados para la agenda.',
            'reused': False, 'reuse_reason': None, 'rerun_reason': None,
            'reference': 'evidence/test-scheduling.log',
            'execution': {'kind': 'local', 'executor': 'X1'},
        },
        {
            'id': 'C002', 'command': 'dotnet test --filter Reproduction', 'revision': head,
            'status': 'failed', 'failure_kind': 'product',
            'evidence': 'La reproducción confirma que la respuesta actual omite el id requerido.',
            'reused': False, 'reuse_reason': None, 'rerun_reason': None,
            'reference': 'evidence/repro-head.log',
            'execution': {'kind': 'local', 'executor': 'X1'},
        },
        {
            'id': 'C003', 'command': 'dotnet test -m:1', 'revision': base,
            'status': 'passed', 'failure_kind': None,
            'evidence': 'La revisión base conserva el id en la respuesta.',
            'reused': False, 'reuse_reason': None,
            'rerun_reason': 'CS2012; log evidence/attempt1.log; reintento -m:1',
            'reference': 'evidence/repro-base.log',
            'execution': {'kind': 'local', 'executor': 'X2'},
        },
    ]
    return record


def check_classification(record: dict) -> dict:
    checks = []
    for check in record['checks']:
        checks.append({
            'id': check['id'],
            'evidence': check['evidence'],
            'reuse_reason': check['reuse_reason'],
            # This fixture's C003 repeat was caused by compiler resource mechanics.
            'rerun_reason': None,
            # Local references remain private; this classification adds no links.
            'reference': None,
        })
    return {'source_sha256': review_publication.publication_digest(record),
            'checks': checks}
