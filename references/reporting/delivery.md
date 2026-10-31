# Explicit portable delivery

Delivery is a projection of an existing retained result, not another review. Activate it only for an explicit full/brief choice, including natural language such as entrega completa/breve. A request to transfer without a mode needs clarification. Profile and delivery are independent; neither brevity nor a destination changes review depth, verdict, coverage or required internal retention.

The agent interprets `--delivery full|brief` and `--output <delivery-root>`. These are request conventions, not npx or shell flags. `--output` alone selects no mode, produces no export and does not redirect the internal archive. The user may separately request an internal archive location under artifacts.md.

## Contents and location

- Full: informe.md and a portable review.json, derived from the same final result. Preserve findings, scenarios, impacts, corrections, exact scope/version, attribution, validation summaries, uncertainties, applicable coverage, `previous_reviews` lineage and schema 10/11/12 profile/assignment history.
- Brief: resumen.md with identity/version/scope, verdict and reason, confirmed counts, IDs/priorities/locations, concrete triggering scenarios/impacts and correction guidance, meaningful validation summaries and material pending matters. It shows the prior review ID/source link and keeps the result summary; it does not promise full profile/assignment history. It remains sufficient to understand the requested next work; unresolved claims stay separate from confirmed corrections.
- Optional contexto.md: only additional collected context that changes the next agent's decisions and is absent from the report. Preserve sources and uncertainties; do not repeat findings or create a new plan.
- A small .ccr-delivery.json records projection/source identity and file hashes. It is transfer integrity metadata, not an execution log, review authorization or proof of correctness.

Default root is docs/ccr/reviews in the explicitly identified persistent project checkout. Append the stable scope slug and review identity to distinguish MR/PRs, local scopes and executions. An explicit output selects a different delivery root; relative paths anchor to that persistent checkout. Never infer the persistent destination from an executor's temporary worktree or silently switch to scratch. If the checkout is unclear, request it before writing. Project instructions and existing permissions still apply.

The export omits logs, fixtures, reproductions, trace/closure and dependency trees. Those remain in the internal archive. Avoid private absolute paths, environment commands and links that require undistributed evidence files. Preserve repository-relative code locations and useful verified URLs. The portable JSON is identified as a projection through the receipt; unavailable private source references remain explicitly withheld instead of becoming invented URLs or verification results. It cannot replace the original record for archive retention/closure.

## Additional context, when available

Use only facts already collected in the review or supplied continuation context; create no discovery/verification agents or additional inspection pass for these sections.

- Assumptions and decisions: interpretation, source, confirmed/pending state and affected work. Review version and missing verification are scope/limitations, not assumptions. Do not silently prefer Plan over Spec when they conflict.
- Sources and criteria analyzed: actual Spec/Plan or other requirements, input identity, sections inspected, partial-analysis limits and conclusions that affect corrections. Merely linking a document does not establish that it was analyzed. Missing Spec/Plan is not a defect; use available criteria or disclose unknown intended behavior.
- Observed implementation state: requirement/component, implemented/partial/not implemented/not evaluated/out of scope, evidence or finding/check IDs. State only what the review inspected. Keep implementation existence separate from executed behavioral validation; a passed build cannot establish all requirements are implemented.
- Pending decisions: material unresolved choices or work from the existing result/context. They do not enter a confirmed correction checklist.

Omit absent sections rather than fabricating sources, assessments or filler. Preserve exact version binding and supported IDs, and ask the recipient to recheck freshness before making corrections.

## Export and preservation

Use scripts delivery with --help when executable. It validates the retained source read-only, requires an explicit mode and persistent project checkout, and creates a distinct delivery directory. It never modifies a closed run or copies evidence. Existing destinations and unsafe paths are refused rather than overwritten; a changed delivery requires a distinct explicit destination.

Invoke the helper through its absolute path; these are executable helper arguments, unlike the agent request conventions:

```text
python <skill-path>/scripts delivery --run-dir <retained-run-dir> --delivery full --project-root <persistent-checkout>
python <skill-path>/scripts delivery --run-dir <retained-run-dir> --delivery brief --project-root <persistent-checkout> --output-root docs/team-review
```

For collected additional context, supply `--context <context.json>`. Omit empty sections; observations in assumptions, decisions, implementation_state and pending use text, references and version. Sources require their actually analyzed sections and known identity:

```json
{
  "assumptions": [
    {"text": "Previously recorded interpretation, still pending confirmation", "references": ["F001"], "version": "<reviewed-head>"}
  ],
  "sources": [
    {"title": "Spec", "reference": "docs/spec.md", "identity": "<known-source-identity>", "sections": ["3.2 Responses"], "version": "<analyzed-version>"}
  ]
}
```

This input contains only supported observations already available, bound to their known version; the helper checks structure, not their truth. The total is limited to 32 KiB and 24 entries. Do not populate the example from invented IDs, sources or versions.

Do not commit, publish or authorize fixes merely because delivery was requested. Report the actual delivery path and any source/destination limitation. When the helper is unavailable, a native export follows the same contents, projection, path and non-overwrite rules. A delivery failure does not erase the retained review or fabricate successful delivery.

Use bold ID labels in full/brief delivery for confirmed findings (brief), checks, unresolved findings and previous-review ledger entries. Preserve the underlying IDs, historical source IDs and link targets; escape supplied text separately from generated formatting. Full delivery inherits report-format.md.

## Schema 8–11 provenance

Full delivery preserves source schema/review ID, truthful execution status, profile history and assignment selection bindings without collecting new sources. Brief preserves review identity and summarizes execution fulfillment; it does not include the effective profile name, profile history or a link to that history. Prior-review IDs/links identify the recorded previous reviews, when available. Consult the original archive or a full delivery for profile history. The portable JSON may contain sanitized provenance labels; validate its structure, not local filesystem references from another machine. The original archive verifies actual selected sources before cleanup. An explicitly private handoff retains relevant internal limitations; a public handoff uses the same typed/historical classification policy as comments. Delivery never grants permission to publish it.

Both modes use the same typed portable projection: preserve enums, IDs, versions, snapshot identities and relationships; sanitize only prose/commands and reference/location fields according to their meaning. A private structural identity is refused with a field-only diagnostic before any output is created. Unclassified new string fields require an explicit policy; never rewrite IDs or weaken contract validation to make an export pass. The retained source and receipt lineage remain intact on failure.

## Schema 11 traceability

Full retains all 27 dimension rows and finding/evidence/check relationships in portable JSON and the report. Brief lists each check's purpose and result, links finding evidence to that check with distinct deltas/static observations, and keeps coverage as a nested list. It summarizes dimension IDs/states with pending/not-applicable reasons. Private handoff keeps check purpose, evidence origins and flow items; public handoff requires the same source-bound check/coverage contexts as public comments and omits internal matrices.

Purpose and dimension details are PROSE; dimension IDs/status/finding IDs are STRUCTURAL. Sanitize prose, preserve relationships and reject private structural identities or unclassified new string fields. Both modes retain the same original review ID/source hash/schema in .ccr-delivery.json and never modify the source archive. Receipt schema 2 is the command-capture receipt, not the separate delivery receipt (whose historical schema remains 1; new policy uses delivery receipt 2).

Group and compare evidence against the original retained result before sanitizing any prose. Project those groups afterward and render them without another deduplication pass: two different private observations may legitimately become identical portable text. Keep both origins/deltas rather than collapsing them because their projected strings happen to match.

## Project-resource policy and private model summary

For the new schema-12 projection, both modes show the same sanitized command/resources accredited by selected pinned-input and execution proof. CCR-created/modified checks and unknown origins receive concrete explanations instead of being represented as project scripts. Preserve tool/selectors and eligible relative paths; remove only sensitive path components/values, label sanitized representations and do not fabricate a runnable command or link. The policy applies to prose, evidence and references as well as checks[].command. Historical projections retain their published policy unless a new explicit evidence-backed projection is requested; originals are never rewritten.

Delivery receipt 2 retains source identity/hash and file inventory/hashes, adding projection_policy=project-resources-v1, check_disclosure_sha256 and model_usage_sha256 (null without an applicable sidecar). These are distinct from command receipt 2, draft 3 and model ledger 1. Portable JSON keeps the final contract shape; a check with no exposable command carries an explanation marker, never raw private text or null. The archive remains the canonical provenance source.

Private full/brief include the sanitized participant/phase model summary from selected retained bytes. Show configured and observed separately, explicit unknown/absence, and missing capture for actually dispatched reviewers; do not fabricate historical observations or query deleted sessions. Preserve model changes/conflicts, bind the ledger digest and do not export the raw ledger. Public comment/handoff exclude this private summary. See [capture and disclosure example](../../docs/examples/check-disclosure-and-models.md).

### Selected disclosure files

Standalone contract rendering, comment prepare/verify and delivery accept paired `--check-disclosure-context <sidecar.json>` and `--check-disclosure-sources <catalog.json>`. The catalog contains `{input_identity, sources}` and may additionally select `run_dir` for verified snapshot inputs; `input_identity` is the initially pinned identity, and sources maps each selected `evidence/<file>.json` reference to `{path, sha256}` for existing bytes. The loader refuses links, unsafe paths, changed hashes, unused/unselected sources and oversized input. A snapshot requires the verified run and its initially registered identity; a standalone commit command requires the commit/tree/blob proof anchored to scope.head. Never construct the initial identity from an after-the-fact execution claim.

For a retained result, delivery uses the selected `context.check_disclosure_reference` and `context.check_disclosure_input_identity`. Registration pins that identity before work; a later sidecar cannot replace it. Retain/checkpoint the sidecar and every selected proof input using the normal evidence flags. Validation and delivery after cleanup use those retained bytes. A historical result without adequate proof receives explanation rather than a new execution or guessed command. See artifacts.md and the maintained example for capture before cleanup.
