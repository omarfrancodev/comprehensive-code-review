# Persistent review archive

The coordinator keeps three locations distinct: the user checkout, run-owned execution scratch/workspaces, and the persistent archive. A user development worktree remains user-owned. Native scratch is not the durable destination. Honor no-create requests and existing write permissions; an inaccessible root produces an explicit persistence limitation and an in-conversation record, not a silent switch to project docs or provider scratch.

## Root and run identity

Choose the root once: explicit user output location, otherwise CCR_ARTIFACTS_DIR, otherwise the user's home/.comprehensive-code-review/reviews. A requested project-docs destination is an explicit override; a normal review request does not select it. Keep the default outside the project, temporary sessions and skill installation. Reject links/reparse-point paths; report blocked access instead of modifying permissions or configuration.

Mandatory layout: <root>/<repository-slug>-<stable-id>/<scope-slug>/<timestamp>-<run-id>/. An output override selects the root, not a different layout. Use exactly the `run_dir` returned by `prepare`; never rebuild, shorten or rename its components. Historical folders are not precedent for new runs. Multiple MR/PRs get separate runs; re-review creates another run referencing the earlier one, never overwrites it. History persists until explicitly deleted; do not add automated retention or load past context as a cache.

The repository ID is the first 20 hex characters of SHA-256 of the normalized remote identity, or resolved Git common-directory identity for absent/relative local remotes. Scope folders contain mode, reference hint and the first 16 hex characters of SHA-256 of canonical pinned scope JSON. Runs use UTC YYYYMMDDTHHMMSS and a unique 20-hex execution ID. `review_artifacts.py` defines canonical JSON bytes and Windows-safe slug derivation. Schema 3 binds the directory to stored `repository_identity`, `repository_key`, `scope`, `created_at` and `run_id`, so validation does not require the original checkout or an unchanged remote. Schemas 1/2 keep compatible structural checks without migration. Preserve nonconforming historical archives; a failed gate is a reported compatibility limitation, not permission to rename/rewrite history.

## Bootstrap and temporary evidence

Load this reference before creating any artifact. First pin inputs with read-only inspection. Before durable `prepare`, put its required `scope.json` in `evidence/` of an exclusive owned session, with an ownership manifest recording that bootstrap. A writing executor's session uses workspaces.md; a static-only review may use a native owned evidence session without creating a Git worktree. This bounded preparation is the only pre-run artifact phase: pass that session via `prepare --temporary-path`, validate the returned run, and finish registration before discovery, worker dispatch or validation commands.

Once prepared, create descriptions, captures, identity hashes, discussions, context/checks and role packets within that registered session's `evidence/`. Additional owned sessions/executors need `register --temporary-path` before use; planned directories can be registered before creation, and registration repeated after their ownership manifest exists. Do not create a parallel scratch directory beside `reviews/` or elsewhere outside the registered session. Original user inputs can be read where they exist; this rule governs review-created temporaries. Workers write assigned evidence; the coordinator owns durable metadata.

## Mandatory compact records

| File | Purpose |
|---|---|
| informe.md | User report from the canonical final record |
| review.json | Complete version-bound final record |
| cierre.json | Run/skill version, scope, repository/root, harness, previous run, executor isolation/inputs/dependencies, registered temporary paths, hashes and observed closure |

Initialize cierre.json after pinning scope, before execution; register temporary resources before using them. A run without a final verdict keeps that closure, distinguishing interruption from completion. The default completed archive has informe.md, review.json and cierre.json plus its ownership marker and selected evidence. Measurement files are absent by default. Only an explicitly requested cost evaluation uses measurements.md and retains optional measurements.json; unknown requested counters remain null with a reason. Preserve old archives and their measurement hashes; no migration or deletion.

Execution facts/packets remain under owned evidence/context.json, checks.json, discovery-<role>.json and verification.json. Persist selected reproductions, fixtures/configuration identity and decisive logs under archive evidence/ only when needed to reproduce/audit results. Record hashes and use retained paths in final references. A retained fixture is a copy of review evidence, not a product patch. Do not copy all scratch/history, credentials, unnecessary private metadata or dependency/build trees. Do not require workers to reload archived reports.

## Lifecycle and helper

When the interpreter/script is executable within permissions, use the helper for durable preparation, registration, retention and closure, plus its validation gates. Native preparation is not an alternative because it seems simpler or older runs used it. If the helper cannot execute, record that limitation and use native operations only when they implement and verify the same layout, ownership/closure records, exact scope, atomic writes, hashes and lifecycle. Read the contract in `scripts/review_artifacts.py`; disclose native validation rather than claiming helper execution. If guarantees cannot be verified, preserve evidence and report persistence incomplete. A helper validation failure is not unavailability and must not be bypassed with native writes.

The coordinator is the sole durable writer. Run mutations sequentially for that run. Invoke through an absolute interpreter/script path and consult --help:

```text
python /absolute/skill/scripts/review_artifacts.py prepare --repo /absolute/project --scope-file /absolute/owned/session/evidence/scope.json --skill-version 2.6.0 --harness actual-harness --temporary-path /absolute/owned/session
python /absolute/skill/scripts/review_artifacts.py validate --run-dir /absolute/returned/run
python /absolute/skill/scripts/review_artifacts.py register --run-dir /absolute/returned/run --temporary-path /absolute/project/.worktrees/code-review-EXECUTOR
python /absolute/skill/scripts/review_artifacts.py retain --run-dir /absolute/returned/run --input /absolute/owned/session/evidence/final-review.json --context-input /absolute/owned/session/evidence/context.json --evidence-input /absolute/owned/worktree/tests/reproduction.cs
python /absolute/skill/scripts/review_artifacts.py validate --run-dir /absolute/returned/run --require-retained
python /absolute/skill/scripts/review_artifacts.py close --run-dir /absolute/returned/run --cleanup complete
```

prepare accepts optional --output-root and --previous-run. Supply canonical scope. `register` adds resources while state is prepared; `retain --temporary-path` remains compatible but does not replace registration before use. Register only exact review-owned temporary directories after checking ownership; never the user checkout, another task's workspace or the persistent archive. Registration observes paths/manifests but does not create resources, delete them or prove ownership.

`validate` is read-only: ownership/manifest integrity, repository/scope/run layout and existing selected-file hashes. `--require-retained` additionally requires the retained final record, report, exact scope and required legacy measurements before cleanup. `retain`, `register`, `close` and previous-run loading also reject invalid layout automatically. Gates check registered records and selected files, not arbitrary files elsewhere or finding truth. On failure, preserve the exact run/session and report the error; do not claim successful retention, cleanup readiness or closure.

retain verifies scope/record, writes report/final record atomically and records hashes. --context-input projects executors from existing context.json into closure, verifying registered paths, Git root/common repository/HEAD and pinned scope, not check outcomes or copying content. Capture it before cleanup; omitted input is valid for static-only reviews. Writing executors supply equivalent provenance through helper/native closure. Registered resources keep cleanup pending until observed close. Register declared residuals before retention; other native resource types need coordinator evidence. Repeatable --evidence-input copies selected regular files into evidence/ and hashes them; duplicate basenames or links are refused. Schemas 2/3 require report/final record; schema 1 keeps required measurements. Optional measurements remain integrity-checked; only explicit --measurement-input or --unavailable-reason opts into new measurement creation. Requested evaluations supply disjoint inputs excluding inclusive parent totals; duplicate paths/known execution IDs are rejected, semantic overlap remains a coordinator check. Retry without measurement arguments preserves already retained measurements.

Select every evidence file needed to reproduce/audit the verdict or referenced by the final report, passing each via repeatable `--evidence-input`. It copies files; it neither moves them nor automatically retains context/checks/description/discussions. `--context-input` only projects executors. Verify retained inventory/hashes and use durable final references. Do not ask the user whether required evidence should survive disposal; retention is part of the review contract. New closure schema 3 adds layout identities; schemas 1/2 keep their existing file requirements.

Stop workers, retain required evidence and pass `validate --require-retained` before removing any temporary resource; with unavailable helper, record equivalent native checks. If retention/validation fails, preserve temporary evidence and report the failure. Then run the owned workspace cleanup, inspect its results and remaining resources, and supply close an observed object: {cleanup: complete|not_needed|pending, residuals: [exact absolute paths]}. Complete requires registered resources absent; not_needed requires none registered; pending identifies remaining registered resources. Inaccessible resources or modified archived files cannot be treated as successfully closed. The helper updates review.resources/report hashes with observed cleanup. Keep closure pending until that succeeds.

After disposal, pass the observation directly with `close --cleanup complete` (or `not_needed` for no registered resources); `--cleanup pending --residual /absolute/remaining/path` lists exact remaining resources, repeating --residual as needed. This creates no post-cleanup temporary file. `--cleanup-file` remains available for an existing permitted observation file, mutually exclusive with inline flags. Native closure writes the observed object directly to durable metadata.

An interrupted run preserves initial closure and temporary manifest locations for recovery. close is metadata finalization, not deletion. Safe recovery reads the exact run record, verifies ownership/current state and updates only that run. A successful close keeps the archive; cleanup never deletes it. Surface its actual location in the user handoff, outside the public MR/PR comment. With no files, retain the relevant in-conversation data and state that the durable directory was unavailable.

Completed runs are immutable; close is idempotent for their already observed result. Corrections or another review create a new linked run. Initial, update and successful-close timestamps identify the actual lifecycle.
