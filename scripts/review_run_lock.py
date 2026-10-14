"""Cross-process exclusive mutation locks for review archive runs."""
from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import stat
import threading


_guard = threading.RLock()
_held = {}


def _lock_identity(run_dir):
    run = Path(run_dir)
    if not run.is_absolute():
        raise ValueError('run lock requires an absolute run directory')
    if not run.exists() or not run.is_dir():
        raise ValueError('run lock requires an existing run directory')
    if run.is_symlink():
        raise ValueError('run lock refuses a linked run directory')
    run = Path(os.path.abspath(str(run)))
    for component in (run, *run.parents):
        try:
            info = component.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('run lock refuses linked path components')
    # realpath asks the OS for the final path of an existing directory. On
    # Windows this also expands 8.3 aliases, so long and short spellings share
    # one process lock and one lock file.
    canonical = os.path.realpath(str(run))
    if os.name == 'nt':
        # Python's realpath resolves junctions but does not expand every 8.3
        # spelling. Ask Windows for the long name of the existing directory.
        try:
            import ctypes
            get_long_path = ctypes.windll.kernel32.GetLongPathNameW
            get_long_path.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint)
            get_long_path.restype = ctypes.c_uint
            buffer = ctypes.create_unicode_buffer(32768)
            length = get_long_path(canonical, buffer, len(buffer))
            if 0 < length < len(buffer):
                canonical = buffer.value
        except (AttributeError, OSError):
            pass
        if canonical.startswith('\\\\?\\UNC\\'):
            canonical = '\\\\' + canonical[8:]
        elif canonical.startswith('\\\\?\\'):
            canonical = canonical[4:]
    canonical = os.path.normcase(os.path.normpath(canonical))
    run = Path(canonical)
    identity = canonical
    lock_root = run.parent / '.review-locks'
    if lock_root.exists() and (lock_root.is_symlink() or not lock_root.is_dir()
                               or getattr(lock_root.lstat(), 'st_file_attributes', 0) & 0x400):
        raise ValueError('review lock directory is not a regular directory')
    lock_root.mkdir(exist_ok=True)
    digest = hashlib.sha256(identity.encode('utf-8')).hexdigest()
    return identity, lock_root / (digest + '.lock')


def _acquire(identity, lock_path, owner):
    current = _held.get(identity)
    if current is not None:
        if current['owner'] != owner:
            raise ValueError('review run mutation lock conflict: ' + identity)
        current['depth'] += 1
        return

    stream = lock_path.open('a+b')
    try:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b'0')
            stream.flush()
        stream.seek(0)
        if os.name == 'nt':
            import msvcrt
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise ValueError('review run mutation lock conflict: ' + identity) from exc
        else:
            import fcntl
            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise ValueError('review run mutation lock conflict: ' + identity) from exc
        _held[identity] = {'owner': owner, 'depth': 1, 'stream': stream}
    except BaseException:
        stream.close()
        raise


def _release(identity, owner):
    current = _held.get(identity)
    if current is None or current['owner'] != owner:
        raise RuntimeError('review run mutation lock ownership was lost')
    current['depth'] -= 1
    if current['depth']:
        return
    stream = current['stream']
    try:
        if os.name == 'nt':
            import msvcrt
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
    finally:
        stream.close()
        del _held[identity]


@contextmanager
def run_locks(run_dirs):
    """Lock unique run directories in a stable order; nested same-thread calls reenter."""
    owner = threading.get_ident()
    identities = {}
    for run_dir in run_dirs:
        identity, lock_path = _lock_identity(run_dir)
        identities[identity] = lock_path
    ordered = sorted(identities.items())
    acquired = []
    try:
        for identity, lock_path in ordered:
            with _guard:
                _acquire(identity, lock_path, owner)
            acquired.append(identity)
        yield
    finally:
        for identity in reversed(acquired):
            with _guard:
                _release(identity, owner)
