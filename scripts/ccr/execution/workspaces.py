"""Physical operations for owned Git review workspaces."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import uuid

from ccr.execution import workspace_manifest as _workspace_manifest
from ccr.execution import claims as resource_claims

ReviewError = _workspace_manifest.ReviewError
is_link = _workspace_manifest.is_link
no_links = _workspace_manifest.no_links

def load(path):
    return _workspace_manifest.load(path)

def digest(data):
    return hashlib.sha256(data).hexdigest()

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

def tracked_fingerprint(repo, resource_files=None):
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
            if resource_files is not None:
                resource_files[name.replace('\\', '/')] = value[-1]
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

def view_hashes(workspace, resource_files=None):
    staged, unstaged = patches(workspace)
    return {"staged_sha256": digest(staged), "unstaged_sha256": digest(unstaged),
            "tracked_fingerprint": tracked_fingerprint(workspace, resource_files),
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
    (session / ".review-run-owner.json").write_text(json.dumps({
        "schema_version": 1, "status": "bootstrap", "session_id": session_id,
        "owner_token_sha256": hashlib.sha256(manifest["owner_token"].encode("utf-8")).hexdigest(),
        "repo": str(repo)}, sort_keys=True, indent=2) + "\n", encoding="utf-8")
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
            resource_files = {}
            entry["view_baseline"] = view_hashes(workspace, resource_files)
            entry["initial_untracked"] = {name: digest((workspace / name).read_bytes()) for name in untracked(workspace)}
            resource_files.update(entry['initial_untracked'])
            # Reuse the initial fingerprint scan, before CCR may create/alter fixtures.
            entry['resource_baseline'] = {'head': head, 'files': resource_files}
            from ccr.contracts.check_disclosure import canonical
            entry['resource_baseline_sha256'] = digest(canonical(entry['resource_baseline']))
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
def _cleanup_snapshot(manifest):
    repo, session = Path(manifest["repo"]), Path(manifest["session_dir"])
    expected_names = {".owner.json", ".review-run-owner.json", "manifest.json",
                      "staged.patch", "unstaged.patch", "evidence"} | {
                          entry["role"] for entry in manifest["workspaces"]}
    for child in session.iterdir():
        if is_link(child) or child.name not in expected_names:
            raise ReviewError(f"Unexpected session resource; preserve and inspect: {child}")
    evidence = session / "evidence"
    if evidence.exists():
        for item in evidence.rglob("*"):
            if is_link(item):
                raise ReviewError(f"Evidence contains a link: {item}")
    registered = registrations(repo)
    artifacts = {item["path"]: item["sha256"] for item in manifest.get("artifacts", [])}
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
    main_state = state(repo, session, manifest["included_files"])
    return main_state, registered


def plan_cleanup(args, manifest, *, claim=None):
    """Validate a complete cleanup request before the caller performs any durable effect."""
    repo, session = Path(manifest["repo"]), Path(manifest["session_dir"])
    claim_path = session / ".review-run-owner.json"
    current_claim = None
    if claim_path.exists():
        no_links(claim_path)
        current_claim = json.loads(claim_path.read_text(encoding="utf-8"))
    if current_claim is not None and current_claim.get("status") == "owned":
        if not getattr(args, "run_dir", None):
            raise ReviewError("Cleaning a claimed session requires its owning --run-dir")
        if claim is not None and claim != current_claim:
            raise ReviewError("The requested run does not own this session claim")
        try:
            verified = (resource_claims.inspect_claim_identity(session, args.run_dir) if claim is not None
                        else resource_claims.verify_claim(session, args.run_dir))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise ReviewError("Resource claim verification failed; preserve the session: " + str(exc)) from exc
        if verified["claim_id"] != current_claim.get("claim_id"):
            raise ReviewError("The requested run does not own this session claim")
    elif getattr(args, "run_dir", None):
        raise ReviewError("--run-dir is only valid for a session with an active review claim")
    main_state, registered = _cleanup_snapshot(manifest)
    return {"manifest_path": str(Path(args.manifest).absolute()), "manifest": manifest,
            "repo": str(repo), "session": str(session), "claim": current_claim,
            "run_dir": getattr(args, "run_dir", None), "main_state": main_state,
            "main_changed": main_state != manifest["main_baseline"],
            "registered": [str(path) for path in registered]}


def remove_workspaces(plan):
    """Revalidate the plan under its caller's locks, then remove only recorded worktrees."""
    manifest_path = Path(plan["manifest_path"])
    manifest = load(manifest_path)
    if manifest != plan["manifest"]:
        raise ReviewError("Workspace manifest changed after cleanup was planned; preserve the session")
    args = argparse.Namespace(manifest=str(manifest_path), run_dir=plan.get("run_dir"))
    current = plan_cleanup(args, manifest, claim=plan.get("claim"))
    if current["main_state"] != plan["main_state"]:
        raise ReviewError("Main checkout changed after cleanup was planned; preserve the session")
    repo, session = Path(current["repo"]), Path(current["session"])
    for entry in reversed(manifest["workspaces"]):
        workspace = Path(entry["path"])
        if workspace.resolve() in registrations(repo):
            git(repo, "worktree", "remove", "--force", str(workspace))
    remaining = registrations(repo)
    if any(Path(entry["path"]).resolve() in remaining for entry in manifest["workspaces"]):
        raise ReviewError("Owned worktree registration remains; keep manifest for recovery")
    shutil.rmtree(session)
    return {"status": "closed", "session_id": manifest["session_id"], "session_dir": str(session),
            "all_registered_removed": True, "main_changed": current["main_changed"],
            "remaining_worktrees": [str(path) for path in remaining]}
