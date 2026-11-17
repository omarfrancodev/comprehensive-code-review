"""Replay paired CCR archive phases against HEAD and the working tree."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from threading import Timer
import time
import zipfile


ROOT = Path(__file__).resolve().parents[2]
PYTHON = [sys.executable, "-B", "-X", "utf8"]


def read_json(path):
    return json.loads(path.read_bytes())


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def worker(scripts, metrics_path, watched, arguments):
    sys.path.insert(0, str(scripts))
    metrics = {"git_calls": 0, "selected_reads": 0, "renders": 0}
    original_open = Path.open
    original_popen = subprocess.Popen
    archive = Path(watched["archive"])
    inputs = set(map(Path, watched["inputs"]))

    def counted_open(path, mode="r", *args, **kwargs):
        if "r" in mode and (path in inputs or path.is_relative_to(archive)):
            metrics["selected_reads"] += 1
        return original_open(path, mode, *args, **kwargs)

    def counted_popen(command, *args, **kwargs):
        if isinstance(command, (list, tuple)) and Path(command[0]).stem.lower() == "git":
            metrics["git_calls"] += 1
        return original_popen(command, *args, **kwargs)

    from ccr.reporting import render

    original_render = render.render

    def counted_render(*args, **kwargs):
        metrics["renders"] += 1
        return original_render(*args, **kwargs)

    Path.open = counted_open
    subprocess.Popen = counted_popen
    render.render = counted_render
    from ccr.cli.main import main

    try:
        return main(arguments)
    finally:
        metrics_path.write_text(json.dumps(metrics), encoding="utf-8")


class Replay:
    def __init__(self, scripts, metrics_path, archive, inputs):
        self.scripts = scripts
        self.metrics_path = metrics_path
        self.watch = {"archive": str(archive), "inputs": list(map(str, inputs))}
        self.phases = []

    def call(self, phase, *args, area="artifacts", code=0):
        self.metrics_path.unlink(missing_ok=True)
        command = [*PYTHON, __file__, "--worker", str(self.scripts), str(self.metrics_path),
                   json.dumps(self.watch), area, *map(str, args)]
        start = time.perf_counter()
        result = subprocess.run(command, cwd=self.scripts.parent, capture_output=True, timeout=90)
        elapsed = (time.perf_counter() - start) * 1000
        if result.returncode != code:
            raise RuntimeError(f"{self.scripts.parent.name}/{phase}: "
                               f"{result.stdout.decode()} {result.stderr.decode()}")
        self.phases.append({"phase": phase, "calls": 1, **read_json(self.metrics_path),
                            "stdout_bytes": len(result.stdout),
                            "stdout_chars": len(result.stdout.decode("utf-8")),
                            "stderr_bytes": len(result.stderr), "elapsed_ms": round(elapsed, 1)})
        return result


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def complete(replay, run):
    response = replay.call("complete_validation", "validate", "--run-dir", run, "--require-complete")
    require(json.loads(response.stdout)["state"] == "complete", "Complete validation did not pass")


def result_of(run):
    record = read_json(run / "review.json")
    review_id = record.pop("review_id")
    if "compact_identity" in record:
        record["compact_identity"].pop("created_at")
    report = (run / "informe.md").read_text(encoding="utf-8").replace(review_id, "<review-id>")
    return record, report


def full_inputs(case):
    from test_review_coverage13 import areas
    from traceability_fixtures import PURPOSE

    data = case.make_guided_run(complete_capture=True, profile="deep")
    run, candidate, context = (data[key] for key in ("run", "record", "context"))
    record = read_json(candidate)
    record["schema_version"] = 13
    record["coverage"]["areas"] = areas()
    record["coverage"]["evidence"] = [{
        "id": "EV001", "kind": "static", "detail": "Synthetic fixture inspection",
        "check_id": None, "reference": None,
    }]
    for check in record["checks"]:
        check["purpose"] = PURPOSE
    candidate.write_text(json.dumps(record), encoding="utf-8")
    source_args = ["--run-dir", run, "--input", candidate, "--context-input", context]
    for source in data["evidence_inputs"]:
        source_args.extend(("--evidence-input", source))
    return data, source_args


def full(case, scripts, metrics, new, retry, *, replay_factory=Replay):
    data, source_args = full_inputs(case)
    run, candidate, context = (data[key] for key in ("run", "record", "context"))
    replay = replay_factory(scripts, metrics, run, [candidate, context, *data["evidence_inputs"]])
    preflight = ["preflight", "--phase", "retain", *source_args]
    retain = ["retain", "--expected-schema", "13", "--unavailable-reason",
              "Synthetic fixture has no provider counters", *source_args]
    if retry:
        before = case.snapshot(run)
        original = candidate.read_bytes()
        invalid = json.loads(original)
        invalid["verdict"] = "invalid"
        candidate.write_text(json.dumps(invalid), encoding="utf-8")
        replay.call("reject_candidate", *(retain if new else preflight), code=1)
        require(case.snapshot(run) == before, "Candidate rejection changed the archive")
        candidate.write_bytes(original)
    if not new:
        replay.call("preflight", *preflight)
    replay.call("retain", *retain)
    observed = replay.call("retained_validation", "validate", "--run-dir", run, "--require-retained")
    require(json.loads(observed.stdout)["retained"], "Retained validation did not pass")
    if new:
        closed = replay.call("finish", "finish", "--run-dir", run, "--cleanup", "not_needed")
        require(json.loads(closed.stdout)["status"] == "complete", "Finish did not verify the archive")
    else:
        replay.call("close", "close", "--run-dir", run, "--cleanup", "not_needed")
        complete(replay, run)
    record, report = result_of(run)
    require(record["profile"] == "deep" and record["resources"]["cleanup"] == "not_needed",
            "Full fixture changed profile or cleanup")
    evidence = {path.name: path.read_bytes() for path in data["evidence_inputs"]}
    for name, content in evidence.items():
        require((run / "evidence" / name).read_bytes() == content, f"Changed selected bytes: {name}")
    return replay.phases, (record, report, evidence)


def compact(scripts, metrics, new, disclosure, *, replay_factory=Replay):
    from test_review_compact_cli_output import CompactOutputTests

    case = CompactOutputTests()
    case.setUp()
    try:
        prepared, sources, args = case.inputs_for_bind()
        run = Path(prepared["run_dir"])
        candidate = Path(args[-1])
        replay = replay_factory(scripts, metrics, run, [args[2], candidate])
        if disclosure:
            session = case.session()
            from ccr.archive.resources import cleanup_workspace

            case.addCleanup(cleanup_workspace, argparse.Namespace(manifest=session["manifest"], run_dir=None))
            output = Path(session["session_dir"], "evidence", "bound.json")
            output.parent.mkdir(exist_ok=True)
            replay.watch["inputs"].append(str(output))
            if new:
                bound = replay.call("bind", *args, "--session", session["manifest"], "--output", output)
                require(json.loads(bound.stdout)["sha256"] == sha256(output.read_bytes()), "Wrong receipt hash")
            else:
                bound = replay.call("bind", *args)
                output.write_bytes(bound.stdout)
            candidate = output
            record = read_json(output)
            identity = {"head": record["scope"]["head"], "snapshot": record["scope"]["snapshot"],
                        "resource_manifest_sha256": None}
            request = {"session": session["manifest"], "arguments": {
                "input_identity": identity, "execution_observations": {}, "sources": {},
            }}
            if new:
                request["arguments"]["record_source"] = {
                    "reference": "evidence/bound.json", "sha256": sha256(output.read_bytes())}
            else:
                request["arguments"]["record"] = record
            request_path = case.write_json("disclosure-request.json", request)
            disclosure_path = output.with_name("disclosure.json")
            replay.watch["inputs"].append(str(request_path))
            replay.call("disclosure", "check-disclosure", "--input", request_path,
                        "--output", disclosure_path, area="setup")
            context = json.loads(sources["evidence/context.json"])
            context.update(check_disclosure_reference="evidence/check-disclosure.json",
                           check_disclosure_input_identity=identity)
            sources["evidence/context.json"] = json.dumps(context).encode()
            sources["evidence/check-disclosure.json"] = disclosure_path.read_bytes()
        catalog = {}
        for name, content in sources.items():
            path = case.root / Path(name).name
            if path == candidate:
                raise RuntimeError("Source would replace candidate")
            path.write_bytes(content)
            catalog[name] = str(path)
        current = case.write_json("current.json", case.inputs)
        catalog_path = case.write_json("catalog.json", catalog)
        replay.watch["inputs"].extend([str(current), str(catalog_path), *catalog.values()])
        replay.call("retain", "retain-compact", "--prepared-input", args[2], "--input", candidate,
                    "--current-inputs", current, "--sources-input", catalog_path,
                    *(["--summary"] if new else []))
        complete(replay, run)
        for name, content in sources.items():
            require((run / name).read_bytes() == content, f"Changed compact source: {name}")
        record, report = result_of(run)
        # Validate each disclosure's binding, then compare the remaining data.
        if disclosure:
            from ccr.contracts.check_disclosure import source_digest

            disclosure_value = json.loads(sources["evidence/check-disclosure.json"])
            retained = read_json(run / "review.json")
            require(disclosure_value.pop("review_id") == retained["review_id"] and
                    disclosure_value.pop("source_sha256") == source_digest(retained),
                    "Disclosure does not bind the retained compact record")
            sources["evidence/check-disclosure.json"] = disclosure_value
        return replay.phases, (record, report, sources)
    finally:
        case.doCleanups()


def interrupted(scripts, metrics, new):
    from ccr.contracts.check_disclosure import source_digest
    from test_review_disclosure_close_recovery import DisclosureCloseRecoveryTests

    helper = DisclosureCloseRecoveryTests()
    try:
        case, run, previous = helper.retained_cleaned_run()
        disclosure = case.read(run / "evidence/check-disclosure.json")
        helper.interrupt(case, run, "after")
        replay = Replay(scripts, metrics, run, [])
        if new:
            closed = replay.call("recover_finish", "finish", "--run-dir", run)
            require(json.loads(closed.stdout)["status"] == "complete", "Recovery did not verify the archive")
        else:
            replay.call("recover_close", "close", "--run-dir", run, "--cleanup", "complete")
            complete(replay, run)
        previous["resources"].update(cleanup="complete", residuals=[])
        require(case.read(run / "review.json") == previous, "Recovery changed the review")
        latest = case.read(run / "evidence/check-disclosure.json")
        require(latest["checks"] == disclosure["checks"] and latest["review_id"] == previous["review_id"] and
                latest["source_sha256"] == source_digest(previous) and
                latest["source_sha256"] != disclosure["source_sha256"], "Recovery changed check evidence")
        latest.pop("source_sha256")
        latest.pop("review_id")
        return replay.phases, (*result_of(run), latest)
    finally:
        helper.doCleanups()


def compare(left, right):
    for index, (old, new) in enumerate(zip(left, right, strict=True)):
        require(old == new, f"Pair differs in canonical output {index}: "
                f"{[key for key in old if old[key] != new.get(key)] if isinstance(old, dict) else type(old)}")


def native_run(case, scripts, run, name, guide, output, model, effort):
    prompt = (
        "Actúa como coordinador de CCR. Esta es una prueba sintética acotada a la fase de "
        "archivo. Los insumos de revisión ya se capturaron. Sigue las operaciones de la guía, "
        "examina cada salida y detente ante un fallo. No edites los insumos, no publiques y no "
        "uses otros servicios o agentes. Devuelve el estado y los gates ejecutados en tres líneas.\n\n"
        f"Guía:\n{guide}\n\n"
        f"Ejecuta cada comando por separado mediante PowerShell. Usa esta forma para invocar "
        f"el helper: & '{sys.executable}' -B -X utf8 '{scripts}' AREA COMANDO OPCIONES"
    )
    command = [
        "codex.exe", "-a", "never", "exec", "--ephemeral", "--json", "--skip-git-repo-check",
        "--sandbox", "workspace-write", "--model", model, "-c", f'model_reasoning_effort="{effort}"',
        "-",
    ]
    started = time.perf_counter()
    with (output / f"{name}.stderr").open("wb") as err:
        child = subprocess.Popen(command, cwd=case.root, stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, stderr=err, encoding="utf-8")
        assert child.stdin is not None and child.stdout is not None
        child.stdin.write(prompt)
        child.stdin.close()
        events = []
        timeout = Timer(180, child.kill)
        timeout.start()
        try:
            for line in child.stdout:
                if line.startswith("{"):
                    events.append({"at_ms": round((time.perf_counter() - started) * 1000, 1),
                                   "event": json.loads(line)})
            code = child.wait()
        finally:
            timeout.cancel()
    elapsed = round((time.perf_counter() - started) * 1000, 1)
    (output / f"{name}.json").write_text(json.dumps(events, indent=2) + "\n", encoding="utf-8")
    manifest_path = run / "cierre.json" if (run / "cierre.json").is_file() else run / "manifest.json"
    manifest = read_json(manifest_path) if manifest_path.is_file() else {}
    usage = [row["event"]["usage"] for row in events if row["event"]["type"] == "turn.completed"]
    calls = [row["event"]["item"] for row in events if row["event"]["type"] == "item.completed"
             and row["event"]["item"]["type"] == "command_execution"]
    turns = {row["event"]["type"]: row["at_ms"] for row in events if row["event"]["type"] in
             {"thread.started", "turn.started", "turn.completed", "turn.failed"}}
    from ccr.archive.lifecycle import validate

    try:
        verified = validate(run, require_complete=True)["state"] == "complete"
    except (OSError, ValueError):
        verified = False
    return {"case": name, "exit": code, "usage": usage, "commands": len(calls), "events_ms": turns,
            "elapsed_ms": elapsed, "successful_commands": sum(call.get("exit_code") == 0 for call in calls),
            "manifest_state": manifest.get("state"), "verified_complete": verified}


def shell_args(args):
    return " ".join("'" + str(item).replace("'", "''") + "'" for item in args)


def native_pilot(baseline, output, model, effort, base_commit):
    from test_review_closure_consistency import ClosureConsistencyTests
    from test_review_compact_cli_output import CompactOutputTests

    output.mkdir(parents=True, exist_ok=True)
    results = {"baseline": base_commit, "model": model, "effort": effort,
               "runs": [], "canonical_equivalence": {}}
    full_case = ClosureConsistencyTests()
    full_case.setUp()
    try:
        for mode in ("compact", "full"):
            completed = {}
            for new in (True, False) if mode == "compact" else (False, True):
                case = full_case
                scripts = (ROOT if new else baseline) / "scripts"
                label = mode + ("-new" if new else "-baseline")
                try:
                    if mode == "full":
                        data, args = full_inputs(case)
                        run = data["run"]
                        run_arg = shell_args(("--run-dir", run))
                        if new:
                            close = f"artifacts finish {run_arg} --cleanup not_needed"
                            preflight = ""
                        else:
                            close = (f"artifacts close {run_arg} --cleanup not_needed\n"
                                     f"artifacts validate {run_arg} --require-complete")
                            preflight = f"artifacts preflight --phase retain {shell_args(args)}\n"
                        guide = (f"{preflight}artifacts retain --expected-schema 13 {shell_args(args)}\n"
                                 f"artifacts validate {run_arg} --require-retained\n"
                                 "El fixture no tiene recursos temporales registrados. "
                                 "Confirma la salida retenida antes de cerrar.\n" + close)
                    else:
                        case = CompactOutputTests()
                        case.setUp()
                        prepared, sources, args = case.inputs_for_bind()
                        run = Path(prepared["run_dir"])
                        catalog = {}
                        for name, content in sources.items():
                            path = case.root / Path(name).name
                            path.write_bytes(content)
                            catalog[name] = str(path)
                        retain = ("--prepared-input", args[2], "--input", args[-1], "--current-inputs",
                                  case.write_json("current.json", case.inputs), "--sources-input",
                                  case.write_json("catalog.json", catalog))
                        guide = (f"artifacts retain-compact {shell_args(retain)}"
                                 f"{' --summary' if new else ''}\n"
                                 f"artifacts validate {shell_args(('--run-dir', run))} --require-complete")
                    result = native_run(case, scripts, run, label, guide, output, model, effort)
                    results["runs"].append(result)
                    if result["verified_complete"]:
                        completed[label] = result_of(run)
                    print(json.dumps(result), flush=True)
                finally:
                    if mode == "compact":
                        case.doCleanups()
                (output / "summary.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
            results["canonical_equivalence"][mode] = (len(completed) == 2 and
                completed[f"{mode}-baseline"] == completed[f"{mode}-new"])
            (output / "summary.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
        return all(results["canonical_equivalence"].values())
    finally:
        full_case.doCleanups()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="HEAD")
    parser.add_argument("--pairs", type=int, default=5)
    parser.add_argument("--route", action="append", choices=("full", "full_candidate_retry", "compact",
                        "compact_disclosure", "full_close_recovery"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--native", action="store_true", help="Run four metered Codex turns on synthetic fixtures")
    parser.add_argument("--model")
    parser.add_argument("--effort")
    args = parser.parse_args()
    if args.pairs < 1:
        parser.error("--pairs must be positive")
    if args.native and not (args.model and args.effort):
        parser.error("--native requires the same explicit --model and --effort for each variant")
    sys.path.insert(0, str(ROOT / "tests"))
    from test_review_closure_consistency import ClosureConsistencyTests

    args.output.parent.mkdir(parents=True, exist_ok=True)
    base = subprocess.check_output(["git", "rev-parse", args.base], cwd=ROOT, text=True).strip()
    results = {"baseline": base, "python": sys.version.split()[0], "runs": []}
    with tempfile.TemporaryDirectory(prefix="ccr-bench-") as directory:
        scratch = Path(directory)
        export = scratch / "baseline.zip"
        subprocess.run(["git", "archive", "--format=zip", "-o", export, base, "scripts"], cwd=ROOT, check=True)
        baseline = scratch / "baseline"
        with zipfile.ZipFile(export) as archive:
            archive.extractall(baseline)
        if args.native:
            return 0 if native_pilot(baseline, args.output, args.model, args.effort, base) else 1
        metrics = scratch / "phase.json"
        case = ClosureConsistencyTests()
        case.setUp()
        try:
            routes = {
                "full": lambda scripts, new: full(case, scripts, metrics, new, False),
                "full_candidate_retry": lambda scripts, new: full(case, scripts, metrics, new, True),
                "compact": lambda scripts, new: compact(scripts, metrics, new, False),
                "compact_disclosure": lambda scripts, new: compact(scripts, metrics, new, True),
                "full_close_recovery": lambda scripts, new: interrupted(scripts, metrics, new),
            }
            for name, route in routes.items():
                if args.route and name not in args.route:
                    continue
                for pair in range(1, args.pairs + 1):
                    outputs = {}
                    rows = []
                    for new in (False, True) if pair % 2 else (True, False):
                        variant = "new" if new else "baseline"
                        phases, outputs[variant] = route((ROOT if new else baseline) / "scripts", new)
                        rows.append({"route": name, "pair": pair, "variant": variant, "phases": phases})
                    compare(outputs["baseline"], outputs["new"])
                    results["runs"].extend(rows)
                    args.output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
                    print(f"{name} pair {pair}: equivalent", flush=True)
        finally:
            case.doCleanups()


if __name__ == "__main__":
    if sys.argv[1:2] == ["--worker"]:
        raise SystemExit(worker(Path(sys.argv[2]), Path(sys.argv[3]), json.loads(sys.argv[4]), sys.argv[5:]))
    raise SystemExit(main())
