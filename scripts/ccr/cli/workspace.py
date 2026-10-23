'Owned Git review workspaces. Python 3.10+, Git, no third-party packages.'

import argparse
import json
import subprocess
import sys
from pathlib import Path
from ccr.archive.resources import cleanup_workspace as cleanup, record_artifact
from ccr.execution.workspaces import ReviewError, load, prepare, registrations

def main(argv=None, *, prog=None):
    parser = argparse.ArgumentParser(prog=prog, description=__doc__)
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
    args = parser.parse_args(argv)
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


if __name__ == '__main__':
    raise SystemExit(main())
