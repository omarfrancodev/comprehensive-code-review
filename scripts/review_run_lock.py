"""Cross-process exclusive mutation locks for review archive runs."""
from contextlib import contextmanager
import errno
import hashlib
import os
from pathlib import Path
import stat
import threading


_guard = threading.RLock()
_held = {}


class CoordinationError(ValueError):
    """A coordination precondition failed; this does not imply lock contention."""


class LockConflictError(CoordinationError):
    """Another cooperative owner currently holds the requested lock."""


def _lock_identity(run_dir, *, coordination_root=None):
    run = Path(run_dir)
    if not run.is_absolute():
        raise CoordinationError('run lock requires an absolute run directory')
    if not run.exists() or not run.is_dir():
        raise CoordinationError('run lock requires an existing run directory')
    if run.is_symlink():
        raise CoordinationError('run lock refuses a linked run directory')
    run = Path(os.path.abspath(str(run)))
    for component in (run, *run.parents):
        try:
            info = component.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise CoordinationError('run lock refuses linked path components')
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
    lock_root = run.parent / '.review-locks' if coordination_root is None else Path(coordination_root)
    if not lock_root.is_absolute() or '..' in lock_root.parts:
        raise CoordinationError('review lock directory must be absolute without traversal')
    for component in (lock_root, *lock_root.parents):
        try:
            info = component.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise CoordinationError('review lock directory traverses a link/reparse point')
    if lock_root.exists() and (lock_root.is_symlink() or not lock_root.is_dir()
                               or getattr(lock_root.lstat(), 'st_file_attributes', 0) & 0x400):
        raise CoordinationError('review lock directory is not a regular directory')
    try:
        lock_root.mkdir(exist_ok=True)
    except OSError as exc:
        raise CoordinationError('review lock directory could not be created: ' + str(lock_root) + ': ' + str(exc)) from exc
    digest = hashlib.sha256(identity.encode('utf-8')).hexdigest()
    return identity, lock_root / (digest + '.lock')


def _regular_lock(info):
    return (stat.S_ISREG(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400
            and info.st_nlink == 1)


def _windows_lock_fd(lock_path):
    """Open the final component itself, without granting rename/delete sharing."""
    import ctypes
    from ctypes import wintypes
    import msvcrt

    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                       wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE)
    create.restype = wintypes.HANDLE
    close = kernel.CloseHandle
    close.argtypes = (wintypes.HANDLE,)
    close.restype = wintypes.BOOL
    info = kernel.GetFileInformationByHandleEx
    info.argtypes = (wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD)
    info.restype = wintypes.BOOL

    class AttributeTag(ctypes.Structure):
        _fields_ = [('attributes', wintypes.DWORD), ('tag', wintypes.DWORD)]

    # GENERIC_READ|WRITE, SHARE_READ|WRITE, OPEN_ALWAYS, OPEN_REPARSE_POINT.
    handle = create(str(lock_path), 0xC0000000, 0x3, None, 4, 0x00200000, None)
    if handle == wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        attributes = AttributeTag()
        if not info(handle, 9, ctypes.byref(attributes), ctypes.sizeof(attributes)):
            raise ctypes.WinError(ctypes.get_last_error())
        if attributes.attributes & (0x400 | 0x10):
            raise CoordinationError('review lock file must not be linked or a directory')
        fd = msvcrt.open_osfhandle(handle, os.O_RDWR | os.O_BINARY)
    except BaseException:
        close(handle)
        raise
    return fd  # The CRT descriptor now owns the handle.


def _open_lock_file(lock_path):
    """Do not write until both the opened object and final path are verified."""
    try:
        before = lock_path.lstat()
    except FileNotFoundError:
        before = None
    if before is not None and not _regular_lock(before):
        raise CoordinationError('review lock file must be regular, unlinked and singly owned')
    fd = None
    try:
        if os.name == 'nt':
            fd = _windows_lock_fd(lock_path)
        else:
            if not hasattr(os, 'O_NOFOLLOW'):
                raise CoordinationError('this platform cannot open coordination files without following links')
            fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW
                         | getattr(os, 'O_NONBLOCK', 0) | getattr(os, 'O_CLOEXEC', 0), 0o600)
        opened = os.fstat(fd)
        current = lock_path.lstat()
        if (not _regular_lock(opened) or not _regular_lock(current)
                or not os.path.samestat(opened, current)
                or before is not None and not os.path.samestat(before, opened)):
            raise CoordinationError('review lock file identity changed or is not a regular unlinked file')
        stream = os.fdopen(fd, 'r+b')
        fd = None
        return stream
    except OSError as exc:
        raise CoordinationError('review lock file could not be opened safely: ' + str(lock_path) + ': ' + str(exc)) from exc
    finally:
        if fd is not None:
            os.close(fd)


def _acquire(identity, lock_path, owner):
    current = _held.get(identity)
    if current is not None:
        if current['owner'] != owner:
            raise LockConflictError('review run mutation lock conflict: ' + identity)
        current['depth'] += 1
        return

    stream = _open_lock_file(lock_path)
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
                if exc.errno not in {errno.EACCES, errno.EAGAIN}:
                    raise
                raise LockConflictError('review run mutation lock conflict: ' + identity) from exc
        else:
            import fcntl
            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                if exc.errno not in {errno.EACCES, errno.EAGAIN}:
                    raise
                raise LockConflictError('review run mutation lock conflict: ' + identity) from exc
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
def run_locks(run_dirs, *, coordination_root=None):
    """Lock unique run directories in a stable order; nested same-thread calls reenter."""
    owner = threading.get_ident()
    identities = {}
    for run_dir in run_dirs:
        identity, lock_path = (_lock_identity(run_dir) if coordination_root is None else
                               _lock_identity(run_dir, coordination_root=coordination_root))
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
