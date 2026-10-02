#!/usr/bin/env python3
"""Owned Git review workspaces. Python 3.10+, Git, no third-party packages."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid


class ReviewError(Exception):
    pass


def digest(data):
    return hashlib.sha256(data).hexdigest()


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


def git(repo, *args, data=None, check=True):
    structural = {"GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE",
                  "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_NAMESPACE",
                  "GIT_IMPLICIT_WORK_TREE", "GIT_PREFIX", "GIT_GRAFT_FILE", "GIT_SHALLOW_FILE",
                  "GIT_CONFIG", "GIT_CONFIG_PARAMETERS", "GIT_CONFIG_COUNT", "GIT_REPLACE_REF_BASE"}
    env = {k: v for k, v in os.environ.items() if k.upper() not in structural
           and not k.upper().startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_"))}
    env.update(GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0", GIT_NO_REPLACE_OBJECTS="1")
    # Explicit path is trusted by the caller, without persistent global config changes.
    argv = ["git", "-c", f"safe.directory={repo}", "-c", f"core.hooksPath={os.devnull}", *args]
    result = subprocess.run(argv, cwd=repo, input=data, capture_output=True, env=env)
    if check and result.returncode:
        raise ReviewError(f"Git {args[0]} failed ({result.returncode}): "
                          + result.stderr.decode("utf-8", errors="replace").strip())
    return result


def out(repo, *args):
    return git(repo, *args).stdout


def repository(path):
    repo = no_links(Path(path).absolute())
    if not repo.is_dir():
        raise ReviewError("Repository directory does not exist")
    top = Path(out(repo, "rev-parse", "--show-toplevel").decode().strip()).resolve()
    if top != repo.resolve():
        raise ReviewError("--repo must be the actual repository/worktree root")
    return repo.resolve()


def patches(repo):
    return (out(repo, "diff", "--cached", "--binary", "--full-index", "HEAD", "--"),
            out(repo, "diff", "--binary", "--full-index", "--"))


def tracked_fingerprint(repo):
    """Read actual bytes/types; Git diffs can hide changes through index flags."""
    entries = []
    for encoded in out(repo, "ls-files", "-z").split(b"\0"):
        if not encoded:
            continue
        name = os.fsdecode(encoded)
        path = repo / name
        no_links(path.parent)
        if path.is_symlink():
            value = [name, "link", os.readlink(path)]
        elif not path.exists():
            value = [name, "missing"]
        elif is_link(path):
            raise ReviewError(f"Tracked path is an unsupported reparse point: {path}")
        elif path.is_file():
            value = [name, "file", path.stat().st_mode, digest(path.read_bytes())]
        elif path.is_dir():
            # Submodule contents are out of this helper's automatic capture coverage.
            value = [name, "directory"]
        else:
            raise ReviewError(f"Unsupported tracked file type: {path}")
        entries.append(value)
    return digest(json.dumps(entries, ensure_ascii=True).encode())


def state(repo, excluded_session=None, includes=()):
    staged, unstaged = patches(repo)
    status = out(repo, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    if excluded_session:
        prefix = str(Path(excluded_session).relative_to(repo)).replace("\\", "/") + "/"
        status = b"\0".join(piece for piece in status.split(b"\0")
                             if not piece.startswith(("?? " + prefix).encode()))
    files = {}
    for name in includes:
        path = repo / name
        files[name] = digest(path.read_bytes()) if path.is_file() and not is_link(path) else None
    return {"head": out(repo, "rev-parse", "HEAD").decode().strip(),
            "staged_sha256": digest(staged), "unstaged_sha256": digest(unstaged),
            "status_sha256": digest(status), "included_files": files,
            "tracked_fingerprint": tracked_fingerprint(repo)}


def selected_files(repo, names):
    selected = {}
    for name in names:
        rel = Path(name)
        if rel.is_absolute() or ".." in rel.parts or not rel.parts:
            raise ReviewError(f"Unsafe untracked path: {name}")
        if rel.parts[0] in {".git", ".worktrees"}:
            raise ReviewError(f"Not a review source file: {name}")
        path = no_links(repo / rel)
        if not path.is_file() or not path.resolve().is_relative_to(repo):
            raise ReviewError(f"Included file is missing/not ordinary: {name}")
        if git(repo, "check-ignore", "-q", "--", str(rel), check=False).returncode == 0:
            raise ReviewError(f"Ignored files cannot be included: {name}")
        if git(repo, "ls-files", "--error-unmatch", "--", str(rel), check=False).returncode == 0:
            raise ReviewError(f"Included file must be untracked: {name}")
        key = rel.as_posix()
        if key in selected:
            raise ReviewError(f"Duplicate included file: {name}")
        selected[key] = path.read_bytes()
    return selected


def save(manifest):
    path = Path(manifest["manifest"])
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temp.replace(path)


def registrations(repo):
    items = []
    for entry in out(repo, "worktree", "list", "--porcelain", "-z").split(b"\0"):
        if entry.startswith(b"worktree "):
            items.append(Path(os.fsdecode(entry[9:])).resolve())
    return items


def view_hashes(workspace):
    staged, unstaged = patches(workspace)
    return {"staged_sha256": digest(staged), "unstaged_sha256": digest(unstaged),
            "tracked_fingerprint": tracked_fingerprint(workspace),
            "index_flags_sha256": digest(out(workspace, "ls-files", "-v", "-z"))}


def untracked(workspace):
    return [os.fsdecode(p) for p in out(workspace, "ls-files", "--others", "--exclude-standard", "-z").split(b"\0") if p]


def prepare(args):
    repo = repository(args.repo)
    roles = args.role or ["review"]
    if len(set(roles)) != len(roles) or any(not re.fullmatch(r"[a-z][a-z0-9-]{0,40}", r) for r in roles):
        raise ReviewError("Roles must be unique lowercase slugs")
    if args.include_untracked and args.mode not in {"working", "unstaged"}:
        raise ReviewError("New files can only be included in working/unstaged mode")
    current_head = out(repo, "rev-parse", "HEAD").decode().strip()
    head = out(repo, "rev-parse", "--verify", f"{args.ref}^{{commit}}").decode().strip()
    if args.mode != "commit" and head != current_head:
        raise ReviewError("Local snapshots must use the current HEAD")
    selected = selected_files(repo, args.include_untracked)
    staged, unstaged = patches(repo)
    if args.mode != "commit":
        flags = out(repo, "ls-files", "-v", "-z").split(b"\0")
        if any(flag and (flag[:1].islower() or flag[:1] == b"S") for flag in flags):
            raise ReviewError("Local capture does not support assume-unchanged/skip-worktree index flags")
        if out(repo, "ls-files", "--unmerged", "-z"):
            raise ReviewError("Local capture requires a resolved index without merge conflicts")
        raw = out(repo, "diff", "--cached", "--raw", "HEAD", "--") + out(repo, "diff", "--raw", "--")
        if re.search(rb"\b(?:120000|160000)\b", raw):
            raise ReviewError("Local changes to symlinks or submodules require a separate reviewed capture")
        if re.search(rb"(?m)^:000000 ", out(repo, "diff", "--raw", "--")):
            raise ReviewError("Local capture does not support intent-to-add entries; choose an explicit supported view")
    baseline = state(repo, includes=selected)
    if baseline["staged_sha256"] != digest(staged) or baseline["unstaged_sha256"] != digest(unstaged):
        raise ReviewError("Local state changed while capturing; retry")
    if baseline["head"] != current_head or any(baseline["included_files"][k] != digest(v) for k, v in selected.items()):
        raise ReviewError("Local files/HEAD changed while capturing; retry")
    session_id = uuid.uuid4().hex
    parent = no_links(repo / ".worktrees")
    if parent.exists() and not parent.is_dir():
        raise ReviewError(".worktrees is not a directory")
    parent.mkdir(exist_ok=True)
    session = parent / ("code-review-" + session_id)
    session.mkdir()
    manifest = {"schema_version": 1, "session_id": session_id, "owner_token": uuid.uuid4().hex,
                "repo": str(repo), "session_dir": str(session), "manifest": str(session / "manifest.json"),
                "head": head, "mode": args.mode, "status": "preparing", "main_baseline": baseline,
                "included_files": list(selected), "workspaces": [], "artifacts": []}
    (session / ".owner.json").write_text(json.dumps({k: manifest[k] for k in ("session_id", "owner_token", "repo")}), encoding="utf-8")
    save(manifest)
    try:
        (session / "staged.patch").write_bytes(staged)
        (session / "unstaged.patch").write_bytes(unstaged)
        for role in roles:
            workspace = session / role
            entry = {"role": role, "path": str(workspace)}
            manifest["workspaces"].append(entry)
            save(manifest)
            git(repo, "worktree", "add", "--detach", str(workspace), head)
            if args.mode != "commit" and staged:
                git(workspace, "apply", "--binary", "--index", "-", data=staged)
            if args.mode in {"working", "unstaged"} and unstaged:
                git(workspace, "apply", "--binary", "-", data=unstaged)
            if args.mode in {"working", "unstaged"}:
                for name, data in selected.items():
                    dest = no_links(workspace / name)
                    if dest.exists():
                        raise ReviewError(f"Included file collides in snapshot: {name}")
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(data)
            entry["view_baseline"] = view_hashes(workspace)
            entry["initial_untracked"] = {name: digest((workspace / name).read_bytes()) for name in untracked(workspace)}
            save(manifest)
        if state(repo, session, selected) != baseline:
            raise ReviewError("Main checkout changed during capture; retry with a fresh snapshot")
        manifest["status"] = "active"
        save(manifest)
        return manifest
    except Exception as exc:
        # Only this run's freshly created paths; never clean unrelated worktrees.
        failures = []
        for entry in reversed(manifest["workspaces"]):
            workspace = Path(entry["path"])
            if workspace.resolve() in registrations(repo):
                result = git(repo, "worktree", "remove", "--force", str(workspace), check=False)
                if result.returncode:
                    failures.append(str(workspace))
        if failures:
            raise ReviewError(f"Prepare failed: {exc}. Rollback incomplete; inspect {manifest['manifest']}: {failures}") from exc
        shutil.rmtree(session)
        raise


def load(path):
    path = no_links(Path(path).absolute())
    if path.name != "manifest.json" or not path.is_file():
        raise ReviewError("Expected an existing owned manifest.json")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    repo = repository(manifest["repo"])
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


def record_artifact(args):
    manifest = load(args.manifest)
    path = no_links(Path(args.path).absolute())
    if not path.is_file() or not any(path.is_relative_to(Path(w["path"])) for w in manifest["workspaces"]):
        raise ReviewError("Only an existing ordinary file inside an owned worktree can be recorded")
    workspace = next(Path(w["path"]) for w in manifest["workspaces"] if path.is_relative_to(Path(w["path"])))
    rel = path.relative_to(workspace).as_posix()
    if git(workspace, "ls-files", "--error-unmatch", "--", rel, check=False).returncode == 0:
        raise ReviewError("Tracked product files cannot be declared disposable fixtures")
    artifact = {"path": str(path), "sha256": digest(path.read_bytes())}
    manifest["artifacts"] = [a for a in manifest["artifacts"] if a["path"] != str(path)] + [artifact]
    save(manifest)
    return {"status": "recorded", "artifact": artifact, "manifest": manifest["manifest"]}


def cleanup(args):
    manifest = load(args.manifest)
    repo, session = Path(manifest["repo"]), Path(manifest["session_dir"])
    expected_names = {".owner.json", "manifest.json", "staged.patch", "unstaged.patch", "evidence"} | {w["role"] for w in manifest["workspaces"]}
    for child in session.iterdir():
        if is_link(child) or child.name not in expected_names:
            raise ReviewError(f"Unexpected session resource; preserve and inspect: {child}")
    evidence = session / "evidence"
    if evidence.exists():
        for item in evidence.rglob("*"):
            if is_link(item):
                raise ReviewError(f"Evidence contains a link: {item}")
    registered = registrations(repo)
    artifacts = {a["path"]: a["sha256"] for a in manifest.get("artifacts", [])}
    # Validate the entire session BEFORE deleting the first worktree.
    for entry in manifest["workspaces"]:
        workspace = Path(entry["path"])
        if workspace.resolve() not in registered:
            if workspace.exists():
                raise ReviewError(f"Workspace is no longer registered; cannot safely remove: {workspace}")
            continue
        if out(workspace, "rev-parse", "HEAD").decode().strip() != manifest["head"]:
            raise ReviewError(f"Workspace HEAD changed; preserve: {workspace}")
        if manifest["status"] != "active" or view_hashes(workspace) != entry.get("view_baseline"):
            raise ReviewError(f"Tracked snapshot changed; preserve: {workspace}")
        for name in untracked(workspace):
            path = no_links(workspace / name)
            expected_hash = entry.get("initial_untracked", {}).get(name, artifacts.get(str(path)))
            if not path.is_file() or expected_hash is None or digest(path.read_bytes()) != expected_hash:
                raise ReviewError(f"Unrecorded/changed file; preserve or record an owned fixture: {path}")
    main_changed = state(repo, session, manifest["included_files"]) != manifest["main_baseline"]
    for entry in reversed(manifest["workspaces"]):
        workspace = Path(entry["path"])
        if workspace.resolve() in registrations(repo):
            git(repo, "worktree", "remove", "--force", str(workspace))
    remaining = registrations(repo)
    if any(Path(w["path"]).resolve() in remaining for w in manifest["workspaces"]):
        raise ReviewError("Owned worktree registration remains; keep manifest for recovery")
    shutil.rmtree(session)
    return {"status": "closed", "session_id": manifest["session_id"], "session_dir": str(session),
            "all_registered_removed": True, "main_changed": main_changed,
            "remaining_worktrees": [str(p) for p in remaining]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare", help="Capture state into new detached role worktrees")
    p.add_argument("--repo", required=True)
    p.add_argument("--ref", default="HEAD")
    p.add_argument("--mode", choices=("commit", "staged", "unstaged", "working"), default="commit")
    p.add_argument("--role", action="append", default=[])
    p.add_argument("--include-untracked", action="append", default=[])
    for command in ("inspect", "cleanup", "record-artifact"):
        p = sub.add_parser(command)
        p.add_argument("--manifest", required=True)
        if command == "record-artifact":
            p.add_argument("--path", required=True)
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            result = prepare(args)
        elif args.command == "cleanup":
            result = cleanup(args)
        elif args.command == "record-artifact":
            result = record_artifact(args)
        else:
            result = load(args.manifest)
            result["registered_worktrees"] = [str(p) for p in registrations(Path(result["repo"]))]
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (ReviewError, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
