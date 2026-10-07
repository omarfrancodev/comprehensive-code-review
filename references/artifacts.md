# Persistent review archive

The coordinator keeps three locations distinct: the user checkout, run-owned execution scratch/workspaces, and the persistent archive. A user development worktree remains user-owned. Native scratch is not the durable destination. Honor no-create requests and existing write permissions; an inaccessible root produces an explicit persistence limitation and an in-conversation record, not a silent switch to project docs or provider scratch.

## Root and run identity

Choose the root once: explicit user output location, otherwise CCR_ARTIFACTS_DIR, otherwise the user's home/.comprehensive-code-review/reviews. A requested project-docs destination is an explicit override; a normal review request does not select it. Keep the default outside the project, temporary sessions and skill installation. Reject links/reparse-point paths; report blocked access instead of modifying permissions or configuration.

Layout: <root>/<repository-slug>-<stable-id>/<scope-slug>/<timestamp>-<run-id>/. The repository ID uses normalized remote identity, or resolved Git common directory when the remote is absent or a relative local path, rather than the source worktree path. Use short Windows-safe names and a unique execution ID. Multiple MR/PRs get separate runs. Re-review creates another run referencing the earlier one, never overwrites it. History persists until explicitly deleted; do not add automated retention or load past context as a cache.

## Mandatory compact records

| File | Purpose |
|---|---|
| informe.md | User report from the canonical final record |
| review.json | Complete version-bound final record |
| cierre.json | Run/skill version, scope, repository/root, harness, previous run, executor isolation/inputs/dependencies, registered temporary paths, hashes and observed closure |

Initialize cierre.json after pinning scope, before execution; register temporary resources before using them. A run without a final verdict keeps that closure, distinguishing interruption from completion. The default completed archive has informe.md, review.json and cierre.json plus its ownership marker and selected evidence. Measurement files are absent by default. Only an explicitly requested cost evaluation uses measurements.md and retains optional measurements.json; unknown requested counters remain null with a reason. Preserve old archives and their measurement hashes; no migration or deletion.

Execution facts/packets remain under owned evidence/context.json, checks.json, discovery-<role>.json and verification.json. Persist selected reproductions, fixtures/configuration identity and decisive logs under archive evidence/ only when needed to reproduce/audit results. Record hashes and use retained paths in final references. A retained fixture is a copy of review evidence, not a product patch. Do not copy all scratch/history, credentials, unnecessary private metadata or dependency/build trees. Do not require workers to reload archived reports.

## Lifecycle and helper

The helper is optional; its records and lifecycle also apply with native tools. The coordinator is the sole writer of a durable run; workers return assigned evidence. Run prepare/retain/close sequentially for that run, not concurrently. Invoke through an absolute interpreter/script path and consult --help:

```text
python /absolute/skill/scripts/review_artifacts.py prepare --repo /absolute/project --scope-file /absolute/pinned-scope.json --skill-version 2.5.0 --harness actual-harness --temporary-path /absolute/project/.worktrees/code-review-SESSION
python /absolute/skill/scripts/review_artifacts.py retain --run-dir /absolute/durable/run --input /absolute/final-review.json --context-input /absolute/owned/session/evidence/context.json --evidence-input /absolute/owned/worktree/tests/reproduction.cs
python /absolute/skill/scripts/review_artifacts.py close --run-dir /absolute/durable/run --cleanup-file /absolute/observed-cleanup.json
```

prepare accepts optional --output-root and --previous-run; retain also accepts --temporary-path for executors registered later. Supply scope as the canonical scope object. Register only exact review-owned temporary directories after checking ownership; never register the user checkout, another task's workspace or the persistent archive. The helper observes these paths and never removes them or proves their ownership.

retain verifies scope/record, writes report/final record atomically and records hashes. --context-input projects only executors from existing context.json into closure: it checks registered paths, actual Git root/common repository/HEAD and pinned scope, not check outcomes or copy content. Capture it before cleanup; omitted input is valid for static-only reviews. Writing executors must supply equivalent provenance through the helper or native closure. With registered resources it retains pending cleanup and observed residual paths in both report and closure; successful cleanup requires close. Register any declared residual before retention; the helper supports filesystem directories, so other native resource types need explicit coordinator evidence. Optional repeatable --evidence-input copies selected regular files into evidence/ and hashes them; duplicate basenames or links are refused. New closure schema 2 requires report/final record; optional measurements remain integrity-checked when present. Legacy schema 1 keeps its required measurement evidence. Only explicit --measurement-input or --unavailable-reason opts into measurement creation on a new run. For requested evaluations, supply disjoint inputs excluding inclusive parent totals; duplicate paths/known execution IDs are rejected, semantic overlap remains a coordinator check. Retrying without measurement arguments preserves already retained optional measurements.

Stop workers and preserve/verify all required evidence first. If retention fails, retain temporary evidence and report the failure. Then run the owned workspace cleanup operation, inspect its results and remaining resources, and supply close an observed object: {cleanup: complete|not_needed|pending, residuals: [exact absolute paths]}. Complete requires registered temporary resources absent; not_needed requires none registered; pending identifies remaining registered resources. Inaccessible resources or modified archived files cannot be treated as successfully closed. The helper updates review.resources/report hashes with observed cleanup. Keep closure pending until that succeeds.

An interrupted run preserves initial closure and temporary manifest locations for recovery. close is metadata finalization, not deletion. Safe recovery reads the exact run record, verifies ownership/current state and updates only that run. A successful close keeps the archive; cleanup never deletes it. Surface its actual location in the user handoff, outside the public MR/PR comment. With no files, retain the relevant in-conversation data and state that the durable directory was unavailable.

Completed runs are immutable; close is idempotent for their already observed result. Corrections or another review create a new linked run. Initial, update and successful-close timestamps identify the actual lifecycle.
