#!/usr/bin/env python3
"""Owned Git review workspaces. Python 3.10+, Git, no third-party packages."""
import argparse
import json
import subprocess
import sys

from ccr.archive import resources as archive_resources
from ccr.execution import workspaces as workspace_ops

ReviewError = workspace_ops.ReviewError
is_link = workspace_ops.is_link
no_links = workspace_ops.no_links
load = workspace_ops.load
digest = workspace_ops.digest
git = workspace_ops.git
out = workspace_ops.out
repository = workspace_ops.repository
patches = workspace_ops.patches
tracked_fingerprint = workspace_ops.tracked_fingerprint
state = workspace_ops.state
selected_files = workspace_ops.selected_files
save = workspace_ops.save
registrations = workspace_ops.registrations
view_hashes = workspace_ops.view_hashes
untracked = workspace_ops.untracked
prepare = workspace_ops.prepare
plan_cleanup = workspace_ops.plan_cleanup
remove_workspaces = workspace_ops.remove_workspaces


def record_artifact(args):
    return archive_resources.record_artifact(args)


def cleanup(args):
    return archive_resources.cleanup_workspace(args)


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
        if command == "cleanup":
            p.add_argument("--run-dir", help="Owning review archive for a claimed session")
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
