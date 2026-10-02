# Canonical review record — schema version 1

One source, rendered only for the requested audience. Workers return just schema_version, stage, scope, findings, checks and coverage; final consolidation adds final-only fields. No complete user/public report or repeated shared context from workers. Coordinator IDs are stable; remap role collisions once.

All listed fields are required in applicable objects. Use explicit null/empty arrays for unknown/not applicable values. Unknown fields/enums are errors in this schema version. Evidence is specific, not numeric confidence. Use actual supplied revision/snapshot identities; local edits require a snapshot identifying the selected state.

## Worker fields

- schema_version: integer 1; stage: discovery/verification/final.
- scope: repository; mode pr/mr/commit/range/staged/unstaged/working/module/feature; base/head/snapshot/target/reference (text/null). head or snapshot is required.
- findings/checks: arrays under the contracts below; include only owned/referenced check entries.
- coverage: flows (text array), limitations (detail text, material boolean). Final adds adequate/stale booleans and verification independent/same_session/skipped/unavailable.

## Findings

Fields: id (stable text), type code/description, status candidate/confirmed/rejected/unresolved, priority P0/P1/P2/P3, blocking (boolean), blocking_reason (text/null), origin introduced/preexisting/unknown, title, location, scenario, impact, evidence, correction.

Discovery emits candidates, not confirmation. Suspected blockers remain blocking=false until confirmed; capture their potential consequence in impact. Final has no candidate state. Blocking requires confirmation and a reason; severity does not determine it automatically.

location: path/line/url/section (text/null except positive integer/null line). Code requires actual path/line; description requires section without invented code lines. Use exact-version links when available.

evidence: nonempty array with kind static/executed, details text, check_id (null for static; included ID for executed). Confirmation requires decisive static flow or actual supporting execution; fixture/environment failures alone cannot prove a product defect. Structural relationships do not establish truth.

## Checks

Fields: id, command, revision (actual execution head/base/snapshot, or prior revision for justified reuse), status passed/failed/blocked/not_run, failure_kind (product/fixture/environment if failed; otherwise null), evidence (text; nullable only if not_run), reused (boolean), reuse_reason (nonempty text if reused, otherwise null), rerun_reason (text/null).

The shared ledger additionally keeps executor and fixture/configuration identities; worker packets use this compact projection. Reuse identifies unchanged relevant inputs/configuration and keeps the original revision; it never relabels old execution as current. Reruns record reason. Baseline evidence refers to actual base, not new-head execution. Static-only review legitimately has no checks.

## Final-only fields

- profile economy/balanced/deep; profile_reason text.
- responsible: name/username/source (text/null), verified boolean. Username has no @ prefix. Mentions require an actual verified account; verified display name is sufficient without an account. Unknown renders No identificado.
- description: status aligned/needs_update/unverified for MR/PR, otherwise not_applicable; identity (captured text/hash identity or null when unavailable); details text.
- verdict approvable/approvable_with_reservations/not_approvable/insufficient_evidence; verdict_reason text; reservations (concrete nonblocking text array). Use profiles.md precedence; reservations cannot waive material uncertainty.
- rereview: id/status/details array; status resolved/still_valid/withdrawn/new. Resolved/withdrawn IDs need not remain in current findings.
- aliases: object mapping duplicate IDs directly to surviving finding/re-review IDs; empty when none. Preserve it in the final record for incremental reviews, never chains or self-aliases. Workers do not supply this coordinator registry.
- resources: cleanup complete/not_needed/pending; residuals (exact path array); publication not_requested/draft/published/failed. Residuals require pending cleanup. Published needs actual remote evidence retained outside disposable resources.

## Mechanical tools

Run python /absolute/skill/scripts/review_contract.py validate --input /absolute/record.json. render-user/render-comment produce Spanish Markdown; read errors and repair the record, not product code. Without Python/filesystem, enforce the same contract through supported structured tools or an in-chat record; honor no-create instructions.

Optional deduplicate consumes a findings array plus --groups containing explicitly selected same-cause ID arrays. It preserves all scenarios. Coordinator/verifier decides equivalence; matching titles do not.
