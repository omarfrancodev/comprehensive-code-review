"""Create-once JSON evidence candidates inside an owned session."""
import json
import os
from pathlib import Path
import uuid

from ccr.execution import workspaces as workspace_ops
from ccr.shared.encoding import compact_bytes as _json_bytes

def write_new_json(session_dir: Path, output: str, value: dict) -> Path:
    evidence_dir = workspace_ops.no_links(session_dir / 'evidence')
    target = workspace_ops.no_links(Path(output).absolute())
    if not target.is_relative_to(evidence_dir) or target.parent != evidence_dir:
        raise ValueError('setup output must be a direct child of the owned session evidence directory')
    if not target.name.endswith('.json'):
        raise ValueError('setup output must use a .json filename')
    if not evidence_dir.exists():
        evidence_dir.mkdir()
    if target.exists() or target.is_symlink():
        raise FileExistsError('setup output already exists; choose a new evidence filename')
    payload = _json_bytes(value) + b'\n'
    temporary = evidence_dir / ('.review-setup-' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('xb') as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        workspace_ops.no_links(evidence_dir)
        workspace_ops.no_links(target)
        if target.exists() or target.is_symlink():
            raise FileExistsError('setup output already exists; choose a new evidence filename')
        os.rename(temporary, target)
        if target.read_bytes() != payload:
            target.unlink(missing_ok=True)
            raise OSError('setup output verification failed')
        return target
    finally:
        temporary.unlink(missing_ok=True)
