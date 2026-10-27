"""Reproduce the two request-capture differences of the 9e5bf72 v2 producer.

Keep the real archive writer, signing, reservation and descriptor code. Only
restore omission of the derived identity and the ignored restart capture return.
Never use this context for the reader/retry/recovery assertions under test.
"""
from contextlib import contextmanager
from unittest.mock import patch

from ccr.archive import evidence as archive_evidence
from ccr.archive import restart as restart_ops
from ccr.archive import restart_contract as review_restart


@contextmanager
def previous_v2_producer(artifacts):
    normalize = review_restart.normalize_restart_request
    capture = archive_evidence._capture_review_inputs

    def previous_normalize(*args, **kwargs):
        value = normalize(*args, **kwargs)
        raw = args[3] if len(args) > 3 else kwargs['current_inputs']
        if 'logical_scope_identity' not in raw:
            value['current_inputs'].pop('logical_scope_identity', None)
        return value

    def previous_capture(raw, scope, profile, label, **kwargs):
        value = capture(raw, scope, profile, label, **kwargs)
        if label == 'restart current review inputs' and 'logical_scope_identity' not in raw:
            value.pop('logical_scope_identity', None)
        return value

    with patch.object(review_restart, 'normalize_restart_request', previous_normalize), \
            patch.object(restart_ops, '_capture_review_inputs', previous_capture):
        yield
