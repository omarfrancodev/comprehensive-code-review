"""Bounded JSON reads and atomic writes for trusted archive paths."""
import os
import stat
import uuid

from ccr.shared.paths import safe_path
from ccr.shared.encoding import decode_json


def read_bounded(path, limit):
    """Read a regular file within a byte budget, including growth after stat."""
    if type(limit) is not int or limit < 0:
        raise ValueError('read limit must be a nonnegative integer')
    path = safe_path(path)
    try:
        with path.open('rb') as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode):
                raise ValueError('bounded input must be a regular file: ' + str(path))
            if info.st_size > limit:
                raise ValueError('input exceeds the ' + str(limit) + '-byte limit: ' + str(path))
            data = stream.read(limit + 1)
    except FileNotFoundError:
        raise
    if len(data) > limit:
        raise ValueError('input exceeds the ' + str(limit) + '-byte limit: ' + str(path))
    return data


def read_json(path, *, max_bytes=None):
    data = safe_path(path).read_bytes() if max_bytes is None else read_bounded(path, max_bytes)
    return decode_json(data)


def atomic_write(path, data, *, staging_path=None):
    """Replace one validated path atomically, using an exclusive local staging file."""
    path = safe_path(path)
    staging = safe_path(staging_path) if staging_path is not None else path.parent / (
        '.' + path.name + '.' + uuid.uuid4().hex + '.tmp')
    if staging.parent != path.parent or staging == path:
        raise ValueError('atomic staging file must be a sibling of its destination')
    created = False
    failure = None
    try:
        with staging.open('xb') as stream:
            created = True
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        safe_path(path)
        os.replace(staging, path)
    except BaseException as exc:
        failure = exc
        raise
    finally:
        if created:
            try:
                staging.unlink(missing_ok=True)
            except OSError as cleanup_error:
                detail = 'atomic write staging remains at ' + str(staging) + ': ' + str(cleanup_error)
                if failure is None:
                    raise OSError(detail) from cleanup_error
                failure.args = (str(failure) + '; ' + detail,)
