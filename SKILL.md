---
name: comprehensive-code-review
description: Use when the user requests a code review, MR/PR review, re-review, assessment of local changes, commits, a feature, or current code, including a broad review invoked through another review skill.
metadata:
  version: "2.9.1"
---

# Comprehensive Code Review

Review the requested scope using concrete scenarios, consequences, precise locations and evidence. Report in the user's language. Discover project conventions at runtime; no other skill is required.

## Boundaries

Reviewing permits inspection and necessary temporary artifacts within existing permissions. Preserve the main checkout/index and user resources. Fixing product code, committing, pushing, remote description edits, publishing, approval and merge each need their own authorization. Respect read-only/no-execution requests. Remove only verified run-owned resources; retain the report first.

Static decisive flow can prove a defect; missing tests or unavailable tools cannot. Distinguish regressions, preexisting defects, description discrepancies and unresolved requirements. Passing checks cover their actual scenarios, not the entire change.

## Load by role

Assigned discovery/verification workers read [worker-packets.md](references/execution/worker-packets.md), their stage's section and the pinned brief with binding project instructions. Return the compact packet; the coordinator workflow below handles profiles, presentation and resources. Missing facts trigger a targeted coordinator refresh.

The coordinator loads references by phase and embeds relevant rules in briefs. Use [reading-strategy.md](references/workflow/reading-strategy.md) to plan bounded access/checkpoints. Context identities bind exact inputs; routing preserves project gates.

Before the first artifact write, load [artifacts.md](references/archive/artifacts.md). Use the archive helper when executable within permissions, preserve its returned `run_dir` and `CR-<run_id>` review identity, and keep temporary evidence in an owned registered session. New durable runs require the compact [trace](references/archive/lifecycle-trace.md); historical runs remain unchanged. Verify retained evidence before cleanup; a failed archive gate prevents claiming durable completion.

## Request options

Treat `--profile focused|standard|deep|extended`, `--delivery full|brief` and `--output <delivery-root>` as explicit request conventions, not shell commands or npx options. Equivalent clear natural-language requests apply. No profile means automatic selection below; an explicit profile stays fixed. Delivery is separate from review depth and only runs for an explicitly selected full/brief mode. Without a delivery request, respond normally and keep the internal archive. `--output` only chooses the delivery root: by itself it neither authorizes delivery nor redirects the internal archive. Ask for a missing/contradictory delivery choice without blocking independent review work. Read [delivery.md](references/reporting/delivery.md) only when delivering.

## Profiles

Canonical strategies are focused, standard, deep and extended. Normalize explicit request aliases economy → focused and balanced → standard before selection; aliases remain explicit fixed choices. Use canonical names in new schema7 results; preserve historical record names/versions without migration.

Keep an explicit profile; never escalate it silently. Without one, select extended only for justified independent discovery beyond deep's capacity, deep for observable material mechanisms, focused for demonstrated bounded eligibility, otherwise standard under [profiles.md](references/workflow/profiles.md). Reuse discovered context and its ABCDE/flow assignment map; no extra selection agent/audit. Automatic selection can escalate with new facts. Project gates and execution isolation always apply.

| Profile | Discovery | Verification |
|---|---|---|
| focused | One reviewer, potentially the coordinator | Same-session skeptical pass over candidates/material questions |
| standard | One reviewer, potentially the coordinator | Fresh verifier for substantive candidates/material questions; skip when none remain and coverage is adequate |
| deep | Two independent reviewers on named flows/risks; a third only for a distinct coverage need | Fresh verifier for grouped candidates and named invariants; unrelated flows retain ordinary coverage |
| extended | Automatic: four or five justified independent assignments; explicit: two to five as needed | One fresh grouped verification batch for candidates and assigned invariants |

Every discovery brief states assigned ABCDE areas, flows/interfaces, questions/invariants and expected evidence/coverage under [reviewers.md](references/execution/reviewers.md). Group shared flows; split only for a distinct need. This skill requests coordinator delegation only for required profile sessions when available and authorized; workers do not delegate. Fresh discovery contexts exclude other findings and the full coordinator transcript. Shared execution facts do not establish independence. Missing delegation uses disclosed single-agent passes. Project-required independent gates still apply.

## Workflow and conditional references

1. **Scope/context.** Read [scopes.md](references/workflow/scopes.md), [capabilities.md](references/workflow/capabilities.md), [review-areas.md](references/workflow/review-areas.md) and [artifacts.md](references/archive/artifacts.md). Pin inputs, discover common facts once, map applicable ABCDE areas to assigned flows/check owners. Separate MR/PR responsibility from version-bound change authors. Choose review kind and functional subject once for the canonical presentation. Establish the persistent run and initial closure; execution worktrees remain separate. Before discovery record `discovery/started`, or record `agent/started` after observing dispatch, reusing an equivalent existing milestone. This moves new runs from prepared to processing; selection/planning alone does not. Re-review/complement uses [re-review.md](references/workflow/re-review.md).
2. **Discovery/verification.** Assign packets under [worker-packets.md](references/execution/worker-packets.md); read [reviewers.md](references/execution/reviewers.md) when delegating/grouping. After independent discovery, contrast pertinent external notes before grouped verification. Preserve results, map provisional IDs under [identifiers.md](references/contracts/identifiers.md), group evidenced shared causes and verify candidates/material questions in one batch per scope. Reopen only for new evidence or an uncompleted gate. Mark uncertainty explicitly.
3. **Report/close.** Recheck code/description/attribution freshness. Use [report-format.md](references/reporting/report-format.md) for canonical user/public projections with findings counts and meaningful check evidence; only the user report includes the ABCDE matrix. Retain and verify report, record, trace, executor provenance and necessary evidence before cleanup. Record observed closure; preserve interrupted/pending runs and user resources. When full/brief delivery is explicitly requested, derive it from the retained result under [delivery.md](references/reporting/delivery.md); keep the archive immutable and omit raw evidence from the delivery.

Read [workspaces.md](references/execution/workspaces.md) before builds/tests/installs/reproductions or other writes. Those executors need owned Git worktrees, preferably the project's established location (normally .worktrees); read-only workers may share pinned inputs or immutable Git objects. Blocked creation is an explicit validation limitation, never an automatic switch to scratch/copies. Load [external-cli.md](references/execution/external-cli.md) only for configured external execution and [publication.md](references/reporting/publication.md) only for remote publication.

## Helpers

Use actual source timestamps for `occurred_at`; unknown stays null, while `recorded_at` remains recording time. Preserve observed actor/executor IDs and optional explicit links from existing results; infer neither identities nor parallel execution. Processing means work began, not that a process is currently alive. The [trace contract](references/archive/lifecycle-trace.md) supplies input examples and recovery rules; no heartbeat, extra agents or timing/counter probes are required.

Use an interpreter and absolute script paths; consult --help. The archive helper prepares/registers/validates/retains/closes durable runs without deleting resources; its native fallback and mandatory gates are in artifacts.md. Other helpers remain optional: review_packets.py validates/merges internal packets; complete the final record under [result-contract.md](references/contracts/result-contract.md). Existing workspace/runner/report helpers retain their roles. Measurement collection is opt-in for an explicitly requested cost evaluation: only then load [measurements.md](references/maintenance/measurements.md) and [evaluation.md](references/maintenance/evaluation.md). Normal reviews do not initialize measurement files, probe counters or estimate consumption. Helpers do not prove truth, select models or grant permissions.
