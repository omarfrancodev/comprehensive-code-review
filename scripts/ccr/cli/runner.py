'Run a configured fresh-context CLI adapter without shell expansion.'

import argparse
import json
import subprocess
import sys
from ccr.execution.runner import run

def main(argv=None, *, prog=None):
    parser = argparse.ArgumentParser(prog=prog, description=__doc__)
    for field in ("config", "prompt-file", "workspace", "output-dir"):
        parser.add_argument("--" + field, required=True)
    parser.add_argument("--timeout", type=float, default=900)
    parser.add_argument('--role', default='external_worker', help='Measurement label; does not configure the agent')
    parser.add_argument('--phase', default='unknown', help='Measurement phase label')
    parser.add_argument('--model', help='Actual model identifier, if known; does not select it')
    parser.add_argument('--harness', help='Actual execution environment, if known')
    args = parser.parse_args(argv)
    try:
        result = run(args)
        print(json.dumps(result))
        return 0 if result["status"] == "completed" else 1
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
