# Canonical review record — schema version 8

One final source, rendered for the requested audience. Workers use worker-packets.md; packet_version is independent. The coordinator merges deltas, maps provisional IDs under identifiers.md, supplies judgments and validates the complete record. Legacy full workers retain their schema. Workers return no complete user/public report or delivery. Explicit portable delivery under delivery.md is a projection identified by its separate receipt; preserve the original canonical record for archive retention/closure.

All listed fields are required in applicable objects. Use explicit null/empty arrays for unknown/not applicable values. Unknown fields/enums are errors in this schema version. Evidence is specific, not numeric confidence. Use actual supplied revision/snapshot identities; local edits require a snapshot identifying the selected state.

## Canonical envelope / legacy full worker fields

- schema_version: integer 8 for new final reviews; stage: final. Helpers accept legacy versions 1–7 unchanged. Schema 7 adopts focused/standard names without changing strategy; schema 6 added durable review/source identities and canonical IDs; schema 5 introduced extended. No guessed missing legacy fields. Compact worker packet_version stays independent; existing full worker/merge outputs may use schema 1/2 until the coordinator completes the final record.
- review_id (schemas6/7/8): `CR-` followed by the actual 20 lowercase hex run ID; durable retention binds it to the prepared run.
- previous_reviews (schemas6/7/8): array of {review_id: actual CR ID or null for legacy unknown, reference: actual durable archive reference or verified URL, verified: true}. Empty for a new unlinked review; prior evidence must support linkage.
- grandfathered_ids (schemas6/7/8): {findings: [], checks: []} declares only genuine legacy IDs evidenced by linked prior records. New IDs follow identifiers.md; preserve history exactly.
- presentation (final schemas4–8): {kind: review/rereview/complement, subject: nonempty single-line functional title}. Choose once from scope; use the same values for user/public rendering and closure. Kind is explicit. Schemas1–3 render the legacy Code Review title without guessed presentation.
- scope: repository; mode pr/mr/commit/range/staged/unstaged/working/module/feature; base/head/snapshot/target/reference (text/null). head or snapshot is required.
- findings/checks: arrays under the contracts below; include only owned/referenced check entries.
- coverage: flows (text array), limitations (kind behavior/validation/execution, detail text, material boolean, public_summary text/null). Final adds adequate/stale booleans, verification independent/same_session/skipped/unavailable, and areas under the contract below. Deep/extended never skip assigned invariant verification; unavailable independence uses a disclosed fallback and existing material-gap verdict rules. Worker packets keep their existing minimal shape without a full matrix.

## Final coverage areas

Versions 2–8 final coverage.areas requires exactly one row for each A/B/C/D/E, as defined in review-areas.md. Each row has area (letter), status covered/partial/not_evaluated/not_applicable, details (nonempty concise evidence or applicability/pending reason), material (boolean; true only for partial/not_evaluated required coverage gaps), finding_ids (distinct retained non-rejected canonical IDs; empty when none).

Covered rows can reference findings. Not-applicable rows require a reason, material=false and no findings. Multiple rows may reference one cause without duplicating finding objects. Material gaps affect verdict/verification even if omitted from coverage.limitations; public uncertainty must still disclose them without the matrix. Version 1 retains its earlier coverage fields and behavior.

## Findings

Fields: id (stable text), type code/description, status candidate/confirmed/rejected/unresolved, priority P0/P1/P2/P3, blocking (boolean), blocking_reason (text/null), origin introduced/preexisting/unknown, title, location, scenario, impact, evidence, correction.

Discovery emits candidates, not confirmation. Suspected blockers remain blocking=false until confirmed; capture their potential consequence in impact. Final has no candidate state. Blocking requires confirmation and a reason; severity does not determine it automatically.

location: path/line/url/section (text/null except positive integer/null line). Code requires actual path/line; description requires section without invented code lines. Use exact-version links when available.

evidence: nonempty array with kind static/executed, details text, check_id (null for static; included ID for executed). Confirmation requires decisive static flow or actual supporting execution; fixture/environment failures alone cannot prove a product defect. Structural relationships do not establish truth.

## Checks

Fields: id, command, revision (actual execution head/base/snapshot, or prior revision for justified reuse), status passed/failed/blocked/not_run, failure_kind (product/fixture/environment if failed; otherwise null), evidence (text; nullable only if not_run), reused (boolean), reuse_reason (nonempty text if reused, otherwise null), rerun_reason (text/null).

Schemas6/7 also require reference (text/null): retained source of the actual execution. Reused checks require a durable reference and retain the original revision. Keep meaningful output, test result, skipped/blockage reason and selected log references in evidence; render those in Validación rather than repeating finding scenario/impact. Public projection redacts private commands/paths while preserving check ID, revision and useful result.

The shared ledger additionally keeps executor and fixture/configuration identities; worker packets use this compact projection. Reuse identifies unchanged relevant inputs/configuration and keeps the original revision; it never relabels old execution as current. Reruns record reason. Baseline evidence refers to actual base, not new-head execution. Static-only review legitimately has no checks.

## Final-only fields

- profile focused/standard/deep/extended in schemas7/8 (effective whole-review strategy). Normalize economy → focused and balanced → standard only when interpreting new requests; store canonical names in new schema8 records. Historical schemas5/6 retain economy/balanced/deep/extended and schemas1–4 retain economy/balanced/deep; never normalize or migrate their records; profile_reason text identifying explicit/automatic selection, concrete basis and any escalation. ABCDE/flow assignments and reviewer justifications stay in context/briefs; no auto/mixed enum or risk score.
- responsible: name/username/source (text/null), verified boolean. Username has no @ prefix. Mentions require an actual verified account; verified display name is sufficient without an account. Unknown renders No identificado.
- change_authors (schemas3–8): identity array, empty for unknown. Each entry has name/username/source (text/null), verified boolean, commits (nonempty distinct reviewed commit identities; an explicitly attributed local snapshot may use its snapshot identity). Verified entries need an identity/source; usernames use the responsible-account rules. Commit membership and account mapping are coordinator evidence checks, not established by structural validation. Exact duplicate entries are invalid. Separate this attribution from MR/PR assignment, creator and committer. Unknown identities never become mentions.
- description: status aligned/needs_update/unverified for MR/PR, otherwise not_applicable; identity (captured text/hash identity or null when unavailable); details text.
- verdict approvable/approvable_with_reservations/not_approvable/insufficient_evidence; verdict_reason text; reservations (concrete nonblocking text array). Use profiles.md precedence; reservations cannot waive material uncertainty.
- rereview: id/status/details array; schema6 added not_reevaluated to resolved/still_valid/withdrawn/new. Each row in schemas6/7/8 also requires previous_review_id, previous_reference, previous_finding_id, previous_title, previous_url (text/null), and check_ids (array). Prior rows reference verified previous_reviews lineage and retain the actual source ID/title; previous_reference exactly matches its source reference. Legacy unknown review IDs stay null. Only verified public source URLs populate previous_url. New rows have all previous_* null. Resolved/withdrawn/not_reevaluated IDs need not remain in current findings. Untouched prior claims are explicitly not_reevaluated, never silently resolved.
- aliases: object mapping duplicate IDs directly to surviving finding/re-review IDs; empty when none. Preserve it in the final record for incremental reviews, including historical aliases explicitly declared in grandfathered_ids.findings and linked directly to a survivor with verified prior finding provenance, never chains or self-aliases. Workers do not supply this coordinator registry.
- resources: cleanup complete/not_needed/pending; residuals (exact path array); publication not_requested/draft/published/failed. Residuals require pending cleanup. Published needs actual remote evidence retained outside disposable resources.

The durable run/skill version, file inventory and closure belong in cierre.json under artifacts.md; optional evaluation measurements remain in measurements.json, outside this final schema. A retained report/fixture is not a pending temporary residual. Complete cleanup does not mean deleting the archive. Retain final records before disposal; update resources only from observed cleanup evidence.

## Mechanical tools

Run python /absolute/skill/scripts/review_contract.py validate --input /absolute/record.json. render-user/render-comment produce Spanish Markdown; read errors and repair the record, not product code. Without Python/filesystem, enforce the same contract through supported structured tools or an in-chat record; honor no-create instructions.

Optional deduplicate consumes a findings array plus --groups containing explicitly selected same-cause ID arrays. It preserves all scenarios. Coordinator/verifier decides equivalence; matching titles do not.

## Schema 8 limitations and execution

Limitations have exactly {kind, detail, material, public_summary}. Kind is behavior/validation/execution; full detail stays internal. Behavior/validation publishes its summary when present, otherwise its publishable detail. Nonmaterial execution requires null summary and is omitted publicly. Material execution requires a summary of the pending product check/gate, preserving verdict impact. Verdict reasons, reservations, findings, checks, re-review and area details describe product evidence/acceptance conditions; internal mechanics belong here or in execution/trace. The renderer selects data structurally, not by semantic text classification.

Final coverage.execution has exactly:

- selection_source: explicit/automatic; status: fulfilled/degraded.
- plan: {id, role, independent, required, reference}. Unique nonempty ID; role discovery/verification/project_gate; boolean flags; reference to existing brief/verified gate policy. Include only necessary required assignments. Additional discovery needs a distinct justified brief.
- results: {assignment_id, reviewer_context, provider_id, reference}. Completed observed passes only. Reviewer context is the actual reviewer identity, not packet context_id. Provider ID is actual text or null; reference points to retained result. Reusing context/provider cannot count as independent passes.
- fallbacks: {assignments, reason, detail, source}. Assignment IDs identify affected requirements. Reason tool_unavailable/explicit_restriction/dispatch_failed/quota_exhausted; internal detail and source of observed impediment. Failed attempts are trace observations, not completed results. Omission of a subagent request and few slots are not fallback reasons.

Focused: one discovery and one same-context skeptical pass. Standard: one discovery and a fresh grouped verifier for substantive code candidates/material questions; clean closure or purely mechanical description may use the existing exception. Deep: two/three justified fresh discoveries and one fresh verifier even without findings. Extended automatic: four/five justified fresh discoveries; explicit: two to five, plus one fresh grouped verifier. Project gates are separate required assignments with verified policy source, outside discovery limits.

Fulfilled satisfies the plan and independence. Degraded documents fallback for every unmet requirement; a coordinator fallback can record a skeptical pass without claiming independence. Focused's shared-context requirement applies only to ordinary discovery/verification; required independent project gates remain separate. Coverage.verification describes completed ordinary verification, not project gates/planned passes. Unmet project gates require material coverage gaps. Retention verifies existing sources under [artifacts.md](../archive/artifacts.md); hashes/labels do not prove review truth.
