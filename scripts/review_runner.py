#!/usr/bin/env python3
"""Run a configured fresh-context CLI adapter without shell expansion."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time


def stop(process):
    if os.name == "nt":
        # PID refers exclusively to the process spawned here, including its tree.
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True)
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        time.sleep(0.1)
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if process.poll() is None:
        process.kill()
    process.wait(timeout=10)


def run(args):
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    argv = config.get("argv")
    if config.get("fresh_context") is not True or not isinstance(argv, list) or not argv or any(not isinstance(v, str) or not v for v in argv):
        raise ValueError("Adapter requires argv list and established fresh_context: true contract")
    placeholders = {match for arg in argv for match in re.findall(r"\{([^{}]+)\}", arg)}
    if not {"prompt_file", "workspace"}.issubset(placeholders) or placeholders - {"prompt_file", "workspace", "output_dir"}:
        raise ValueError("Require prompt_file/workspace placeholders; only output_dir is additionally supported")
    prompt, workspace, output = (Path(p).absolute() for p in (args.prompt_file, args.workspace, args.output_dir))
    if not prompt.is_file() or not workspace.is_dir() or args.timeout <= 0:
        raise ValueError("Require existing prompt/workspace and a positive timeout")
    # Batch files invoke cmd.exe and can reintroduce shell expansion; use an executable adapter.
    if Path(argv[0]).suffix.lower() in {".cmd", ".bat", ".ps1"}:
        raise ValueError("Use an executable adapter or an explicit interpreter argv, not a shell/batch entrypoint")
    if output.exists() or output.is_symlink():
        raise ValueError("Output directory already exists; refusing to overwrite")
    values = {"prompt_file": str(prompt), "workspace": str(workspace), "output_dir": str(output)}
    command = []
    for arg in argv:
        expanded = re.sub(r"\{([^{}]+)\}", lambda m: values[m.group(1)], arg)
        if "{" in expanded or "}" in expanded:
            raise ValueError("Unresolved braces in adapter argv")
        command.append(expanded)
    output.mkdir(parents=True)
    metadata = {"started_at": datetime.now(timezone.utc).isoformat(), "workspace": str(workspace),
                "output_dir": str(output), "exit_code": None, "timed_out": False,
                "status": "failed", "review_validated": False,
                "descendant_lifecycle": "adapter_responsibility; runner timeout termination is best effort",
                "workspace_cleanup_ready": False}
    process = None
    try:
        with (output / "stdout.txt").open("wb") as stdout, (output / "stderr.txt").open("wb") as stderr:
            kwargs = {"start_new_session": True} if os.name != "nt" else {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
            process = subprocess.Popen(command, cwd=workspace, stdout=stdout, stderr=stderr, shell=False, **kwargs)
            try:
                metadata["exit_code"] = process.wait(timeout=args.timeout)
                metadata["status"] = "completed" if process.returncode == 0 else "failed"
            except subprocess.TimeoutExpired:
                metadata["timed_out"] = True
                metadata["status"] = "timed_out"
                stop(process)
                metadata["exit_code"] = process.returncode
            except KeyboardInterrupt:
                stop(process)
                metadata["exit_code"] = process.returncode
                metadata["status"] = "cancelled"
    except OSError as exc:
        metadata["error"] = str(exc)
    finally:
        if process is not None and process.poll() is None:
            stop(process)
        metadata["finished_at"] = datetime.now(timezone.utc).isoformat()
        (output / "run.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("config", "prompt-file", "workspace", "output-dir"):
        parser.add_argument("--" + field, required=True)
    parser.add_argument("--timeout", type=float, default=900)
    args = parser.parse_args()
    try:
        result = run(args)
        print(json.dumps(result))
        return 0 if result["status"] == "completed" else 1
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
