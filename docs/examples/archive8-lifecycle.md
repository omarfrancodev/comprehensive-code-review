# Archive 8/layout 2: coordinator lifecycle

These commands use a coordinator-owned native evidence session without writing executors. Replace the absolute paths and skill version with observed values. Input JSON follows [artifacts.md](../../references/archive/artifacts.md); `scope.json` and the initial selection exist before preparation. Reading/creating the remaining evidence follows registration. No findings, identities or events may be fabricated from these examples.

```sh
# ccr-example: prepare
python /absolute/skill/scripts/review_artifacts.py prepare \
  --repo /absolute/project \
  --scope-file /absolute/owned/session/evidence/scope.json \
  --profile-input /absolute/owned/session/evidence/profile-selection.json \
  --skill-version 2.12.1 --harness unknown \
  --temporary-path /absolute/owned/session --output-root /absolute/archive
```

Use the returned run directory for every subsequent command. Build `context.json` with the exact returned history, the exact `review_inputs` object captured in `cierre.json`, planned assignments and `executors: []`. Preserve those captured input identities unchanged; adding or omitting an identity changes the record.

```sh
# ccr-example: register
python /absolute/skill/scripts/review_artifacts.py register \
  --run-dir /absolute/returned/run \
  --temporary-path /absolute/owned/session \
  --context-input /absolute/owned/session/evidence/context.json
```

Only when another decision is observed, record it before affected work; `selection-change.json` uses the documented selection fields. After selecting, refresh the exact history, effective profile and profile_reference, and preserve every started assignment. Context/final `selection_source` still preserves the initial decision's source; each later source remains in its history row.

```sh
# ccr-example: select-profile
python /absolute/skill/scripts/review_artifacts.py select-profile \
  --run-dir /absolute/returned/run \
  --selection-input /absolute/owned/session/evidence/selection-change.json
```

```sh
# ccr-example: register-updated
python /absolute/skill/scripts/review_artifacts.py register \
  --run-dir /absolute/returned/run \
  --temporary-path /absolute/owned/session \
  --context-input /absolute/owned/session/evidence/context.json
```

For each meaningful observed dispatch/result, provide its real actor/provider, brief/result reference and provenance in `event.json`; repeat this command for each observed event. Profile events come from prepare/select-profile.

```sh
# ccr-example: record-event
python /absolute/skill/scripts/review_artifacts.py record-event \
  --run-dir /absolute/returned/run \
  --event-file /absolute/owned/session/evidence/event.json
```

Checkpoint the selected context/packets and structurally final record when available. A checkpoint is provisional even with no structural errors; source gates still apply at retention.

```sh
# ccr-example: checkpoint
python /absolute/skill/scripts/review_artifacts.py checkpoint \
  --run-dir /absolute/returned/run --phase report \
  --context-input /absolute/owned/session/evidence/context.json \
  --evidence-input /absolute/owned/session/evidence/briefs.json \
  --evidence-input /absolute/owned/session/evidence/results.json \
  --input /absolute/owned/session/evidence/final-review.json
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

After that gate, verify ownership and dispose of this exact native session through its native owner. Workspace sessions instead use `review_workspace.py cleanup --manifest <session>/manifest.json --run-dir <run>`; do not apply native deletion to a workspace session. Only after observing successful disposal:

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

If any step fails, preserve this exact run/session and inspect its reported transaction. A different request is not a retry. Recovery and explicitly abandoned unprepared restarts are documented in [recovery.md](../../references/archive/recovery.md).
