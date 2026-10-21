"""Read-only validation for owned review-workspace manifests."""
import hashlib
import json
import os
from pathlib import Path
import re

from ccr.shared.git import git


class ReviewError(Exception):
    pass


def _repository(path):
    repo = no_links(Path(path).absolute())
    if not repo.is_dir():
        raise ReviewError("Repository directory does not exist")
    try:
        top = Path(git(repo, "rev-parse", "--show-toplevel")).resolve()
    except (OSError, ValueError) as exc:
        raise ReviewError("Git rev-parse failed: " + str(exc)) from exc
    if top != repo.resolve():
        raise ReviewError("--repo must be the actual repository/worktree root")
    return repo.resolve()


def is_link(path):
    # Windows junctions/reparse points also redirect paths; is_symlink alone is insufficient.
    return path.is_symlink() or bool(getattr(path.lstat(), "st_file_attributes", 0) & 0x400)

def no_links(path):
    path = Path(os.path.abspath(path))
    for part in (path, *path.parents):
        if part.exists() or part.is_symlink():
            if is_link(part):
                raise ReviewError(f"Path traverses a link/reparse point: {part}")
    return path

def load(path):
    path = no_links(Path(path).absolute())
    if path.name != "manifest.json" or not path.is_file():
        raise ReviewError("Expected an existing owned manifest.json")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    repo = _repository(manifest["repo"])
    sid = manifest["session_id"]
    if not re.fullmatch(r"[0-9a-f]{32}", sid):
        raise ReviewError("Invalid session ID")
    expected = no_links(repo / ".worktrees" / ("code-review-" + sid))
    if path.parent != expected or Path(manifest["session_dir"]).absolute() != expected or Path(manifest["manifest"]).absolute() != path:
        raise ReviewError("Manifest path/session does not match the owned directory")
    marker = expected / ".owner.json"
    no_links(marker)
    owner = json.loads(marker.read_text(encoding="utf-8"))
    if any(owner.get(k) != manifest.get(k) for k in ("session_id", "owner_token", "repo")):
        raise ReviewError("Ownership marker mismatch")
    claim_path = expected / ".review-run-owner.json"
    if claim_path.exists():
        no_links(claim_path)
        claim = json.loads(claim_path.read_text(encoding="utf-8"))
        if (not isinstance(claim, dict) or claim.get("schema_version") != 1
                or claim.get("session_id") != sid
                or claim.get("repo") != manifest.get("repo")
                or claim.get("owner_token_sha256") != hashlib.sha256(owner["owner_token"].encode("utf-8")).hexdigest()
                or claim.get("status") not in {"bootstrap", "owned"}):
            raise ReviewError("Review run resource claim does not match the owned session")
    entries = manifest["workspaces"]
    roles = [e["role"] for e in entries]
    if len(set(roles)) != len(roles) or not roles:
        raise ReviewError("Invalid workspace entries")
    for entry in entries:
        role = entry["role"]
        if not re.fullmatch(r"[a-z][a-z0-9-]{0,40}", role):
            raise ReviewError("Unsafe role path")
        if Path(entry["path"]).absolute() != expected / role:
            raise ReviewError("Workspace is not a direct owned child")
        no_links(expected / role)
    return manifest

def owned_session(raw_path):
    path = Path(raw_path).absolute()
    if path.is_dir():
        path = path / 'manifest.json'
    manifest = load(path)
    return Path(manifest['session_dir']).absolute(), path.absolute(), manifest
