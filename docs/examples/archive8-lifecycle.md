# Archive 8/layout 2: coordinator lifecycle

Use an exclusive owned evidence session. Before a second run, perform bounded `lookup` and inspect its candidates; choose an exact run explicitly if continuing or restarting. This example starts a new review. Replace absolute paths and the skill version with observed values. `scope.json`, the selected `reference-index.json`, and the inputs needed to hash it exist in the session before prepare.

```sh
# ccr-example: lookup, then inspect/select explicitly; lookup never chooses for you
python /absolute/skill/scripts/review_artifacts.py lookup \
  --repo /absolute/project \
  --scope-file /absolute/owned/session/evidence/scope.json
```

Create the profile candidate in the owned session. The input file is exactly `{session, arguments}`; `session` identifies the verified `review_workspace.py` manifest. Explicit selection keeps the authority supplied by the user.

```json
{
  "session": "/absolute/owned/session/manifest.json",
  "arguments": {
    "profile": "focused",
    "selection_source": "explicit",
    "reason": "One bounded discovery and a skeptical pass cover this scope",
    "reference": "evidence/context.json#profile",
    "phase": "prepare",
    "actor": {"kind": "coordinator", "name": "coordinator", "provider_id": null},
    "authority": "User requested focused review",
    "affected_assignments": []
  }
}
```

```sh
python /absolute/skill/scripts/review_setup.py profile \
  --input /absolute/owned/session/evidence/profile-input.json \
  --output /absolute/owned/session/evidence/profile-selection.json
```

The selected index digest is part of `current-inputs.json` before prepare. The run captures the exact source identity and returns the profile history, logical-scope identity and `run_dir` used below.

```sh
# ccr-example: prepare
python /absolute/skill/scripts/review_artifacts.py prepare \
  --repo /absolute/project \
  --scope-file /absolute/owned/session/evidence/scope.json \
  --current-inputs /absolute/owned/session/evidence/current-inputs.json \
  --profile-input /absolute/owned/session/evidence/profile-selection.json \
  --skill-version 2.13.0 --harness unknown \
  --temporary-path /absolute/owned/session --output-root /absolute/archive
```

Read the exact returned `cierre.json`; do not reconstruct profile IDs, event IDs or captured inputs. Build `context-input.json` with the planned assignment rows, `executors: []` when no writing executors exist, and the captured index descriptor. The session helper verifies the sidecar and its selected files before it writes the new context candidate.

```json
{
  "session": "/absolute/owned/session/manifest.json",
  "arguments": {
    "run_dir": "/absolute/returned/run",
    "execution_plan": [
      {"id": "D1", "role": "discovery", "independent": false, "required": true,
       "reference": "evidence/briefs.json#D1", "selection_id": "S001", "superseded_by": null},
      {"id": "V1", "role": "verification", "independent": false, "required": true,
       "reference": "evidence/briefs.json#V1", "selection_id": "S001", "superseded_by": null}
    ],
    "executors": [],
    "review_inputs": {
      "scope": {"repository": "example/service", "mode": "mr", "base": "base-sha",
                "head": "head-sha", "snapshot": null, "target": "main",
                "reference": "https://git.example/service/-/merge_requests/1"},
      "sources": {"evidence/reference-index.json": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},
      "source_set_complete": true, "description_identity": null,
      "requirements_identity": null, "plan_identity": null, "configuration_identity": null,
      "logical_scope_identity": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    },
    "reference_index": {"reference": "evidence/reference-index.json", "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
  }
}
```

```sh
python /absolute/skill/scripts/review_setup.py context \
  --input /absolute/owned/session/evidence/context-input.json \
  --output /absolute/owned/session/evidence/context.json
```

Run registration preflight, then register the context and owned resources. Before dispatch, ensure the registered plan has an active required assignment and pass discovery preflight.

```sh
# ccr-example: preflight-register
python /absolute/skill/scripts/review_artifacts.py preflight \
  --run-dir /absolute/returned/run \
  --context-input /absolute/owned/session/evidence/context.json --phase register
```

```sh
# ccr-example: register
python /absolute/skill/scripts/review_artifacts.py register \
  --run-dir /absolute/returned/run \
  --temporary-path /absolute/owned/session \
  --context-input /absolute/owned/session/evidence/context.json
```

```sh
# ccr-example: preflight-discovery
python /absolute/skill/scripts/review_artifacts.py preflight \
  --run-dir /absolute/returned/run \
  --context-input /absolute/owned/session/evidence/context.json --phase discovery
```

Only after the discovery gate passes, dispatch the assignment. Create an event from the actual observed actor, status, brief and time/provider data. The event builder will not add a missing brief or invent an occurrence time.

```json
{
  "session": "/absolute/owned/session/manifest.json",
  "arguments": {
    "event": {
      "kind": "agent",
      "status": "started",
      "summary": "Observed reviewer dispatch",
      "actor": {"kind": "coordinator", "name": "coordinator", "provider_id": null},
      "occurred_at": null,
      "evidence": ["evidence/briefs.json#D1"]
    },
    "assignment": {"id": "D1", "role": "discovery", "independent": false,
                    "required": true, "reference": "evidence/briefs.json#D1",
                    "selection_id": "S001", "superseded_by": null}
  }
}
```

```sh
# ccr-example: record-event
python /absolute/skill/scripts/review_artifacts.py record-event \
  --run-dir /absolute/returned/run \
  --event-file /absolute/owned/session/evidence/dispatch-event.json
```

Record each later observed result with both its active brief and result references. Checkpoint selected context/packets and the structurally final record when available. A checkpoint stays provisional; source gates still apply at retention.

```sh
# ccr-example: checkpoint
python /absolute/skill/scripts/review_artifacts.py checkpoint \
  --run-dir /absolute/returned/run --phase report \
  --context-input /absolute/owned/session/evidence/context.json \
  --evidence-input /absolute/owned/session/evidence/briefs.json \
  --evidence-input /absolute/owned/session/evidence/results.json \
  --evidence-input /absolute/owned/session/evidence/reference-index.json \
  --input /absolute/owned/session/evidence/final-review.json
```

```sh
# ccr-example: preflight-retain
python /absolute/skill/scripts/review_artifacts.py preflight \
  --run-dir /absolute/returned/run \
  --context-input /absolute/owned/session/evidence/context.json \
  --phase retain --input /absolute/owned/session/evidence/final-review.json
```

```sh
# ccr-example: retain
python /absolute/skill/scripts/review_artifacts.py retain \
  --run-dir /absolute/returned/run --expected-schema 10
```

```sh
# ccr-example: validate-retained
python /absolute/skill/scripts/review_artifacts.py validate \
  --run-dir /absolute/returned/run --require-retained
```

After the retention gate, verify ownership and dispose of this exact native session through its native owner. Workspace sessions instead use `review_workspace.py cleanup --manifest <session>/manifest.json --run-dir <run>`; do not apply native deletion to a workspace session. Only after observing successful disposal:

```sh
# ccr-example: close
python /absolute/skill/scripts/review_artifacts.py close \
  --run-dir /absolute/returned/run --cleanup complete
```

```sh
# ccr-example: validate-complete
python /absolute/skill/scripts/review_artifacts.py validate \
  --run-dir /absolute/returned/run --require-complete
```

If any step fails, preserve this exact run/session and inspect its reported transaction. A different request is not a retry. Recovery and explicitly abandoned unprepared restarts are documented in [recovery.md](../../references/archive/recovery.md). `archive7-lifecycle.md` remains historical guidance only.
