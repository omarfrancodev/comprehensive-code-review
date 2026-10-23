"""Filesystem path checks shared by archive and workspace operations."""
from pathlib import Path
import stat


def safe_path(value):
    """Reject traversal and every existing link/reparse component before resolving."""
    path = Path(value)
    if not path.is_absolute() or '..' in path.parts:
        raise ValueError('an absolute path without traversal is required: ' + str(path))
    for component in path.parts[1:]:
        if any(char in component for char in '<>:"|?*') or component.endswith((' ', '.')):
            raise ValueError('unsafe path component: ' + component)
    for current in (path, *path.parents):
        try:
            info = current.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('links/reparse points are not allowed: ' + str(current))
    return path.resolve()


def contains(parent, child):
    return child == parent or parent in child.parents
