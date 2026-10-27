"""Run locks and source-bound restart coordination."""
from contextlib import contextmanager
from functools import wraps
import time

from ccr.archive.integrity import verify_files as _verify_files
from ccr.archive.reader import load_run as _load_run
from ccr.archive.restart_state import _active_restart_operation, _assert_not_restart_abandoned
from ccr.execution.locks import LockConflictError, run_locks

def _locked_run(function=None, *, when=None):
    """Serialize durable mutations; read-only validation stays lock-free."""
    def decorate(target):
        @wraps(target)
        def wrapped(run_dir, *args, **kwargs):
            if when is not None and not when(args, kwargs):
                return target(run_dir, *args, **kwargs)
            with _owned_run_locks([run_dir]):
                return target(run_dir, *args, **kwargs)
        return wrapped
    return decorate(function) if function is not None else decorate

@contextmanager
def owned_run_locks(run_dirs, *, reservation=None):
    """Verify each run before creating lock files, then revalidate under lock."""
    paths = list(run_dirs)
    if not paths:
        raise ValueError('at least one owned review run is required')
    if reservation is not None:
        raise ValueError('restart reservations are not available for ordinary run mutations')
    for path in paths:
        _, manifest, _ = _load_run(path)
        _assert_not_restart_abandoned(manifest)
        if _active_restart_operation(path, manifest) is not None:
            raise ValueError('a durable restart is pending; retry that exact restart or recover it first')
    with run_locks(paths):
        loaded = [_load_run(path) for path in paths]
        for path, (_, manifest, _) in zip(paths, loaded):
            _assert_not_restart_abandoned(manifest)
            if _active_restart_operation(path, manifest) is not None:
                raise ValueError('a durable restart is pending; retry that exact restart or recover it first')
        yield loaded

@contextmanager
def _restart_lock(source_path, *, timeout=30.0):
    """Retry only transient cross-process lock conflicts, then re-read the intent."""
    import time
    _, source_manifest, _ = _load_run(source_path)  # Ownership gate before lock-directory creation.
    _assert_not_restart_abandoned(source_manifest)
    deadline = time.monotonic() + timeout
    lock = None
    while True:
        lock = run_locks([source_path])
        try:
            lock.__enter__()
            break
        except LockConflictError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.05)
    try:
        _, source_manifest, _ = _load_run(source_path)
        _assert_not_restart_abandoned(source_manifest)
        yield
    finally:
        lock.__exit__(None, None, None)

_owned_run_locks = owned_run_locks
