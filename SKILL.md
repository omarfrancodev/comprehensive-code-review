---
name: comprehensive-code-review
description: Use when the user requests a code review, MR/PR review, re-review, assessment of local changes, commits, a feature, or current code, including a broad review invoked through another review skill.
metadata:
  version: "2.6.0"
---

# Comprehensive Code Review

Review the requested scope using concrete scenarios, consequences, precise locations and evidence. Report in the user's language. Discover project conventions at runtime; no other skill is required.

## Boundaries

Reviewing permits inspection and necessary temporary artifacts within existing permissions. Preserve the main checkout/index and user resources. Fixing product code, committing, pushing, remote description edits, publishing, approval and merge each need their own authorization. Respect read-only/no-execution requests. Remove only verified run-owned resources; retain the report first.

Static decisive flow can prove a defect; missing tests or unavailable tools cannot. Distinguish regressions, preexisting defects, description discrepancies and unresolved requirements. Passing checks cover their actual scenarios, not the entire change.

## Load by role

Assigned discovery/verification workers read [worker-packets.md](references/worker-packets.md), their stage's section and the pinned brief with binding project instructions. Return the compact packet; the coordinator workflow below handles profiles, presentation and resources. Missing facts trigger a targeted coordinator refresh.

The coordinator loads references by phase and embeds relevant rules in briefs. Use [reading-strategy.md](references/reading-strategy.md) to plan bounded access/checkpoints. Context identities bind exact inputs; routing preserves project gates.

Before the first artifact write, load [artifacts.md](references/artifacts.md). Use the archive helper when executable within permissions, preserve its exact returned `run_dir`, and keep review-created temporary evidence in an owned registered session. Existing review directories are history, not layout policy. Verify retained evidence before cleanup; a failed archive gate prevents claiming durable completion.

## Profiles

Keep an explicit profile; never escalate it silently. Without one, select extended only for justified independent discovery beyond deep's capacity, deep for observable material mechanisms, economy for demonstrated bounded eligibility, otherwise balanced under [profiles.md](references/profiles.md). Reuse discovered context and its ABCDE/flow assignment map; no extra selection agent/audit. Automatic selection can escalate with new facts. Project gates and execution isolation always apply.

| Profile | Discovery | Verification |
|---|---|---|
| economy | One reviewer, potentially the coordinator | Same-session skeptical pass over candidates/material questions |
| balanced | One reviewer, potentially the coordinator | Fresh verifier for substantive candidates/material questions; skip when none remain and coverage is adequate |
| deep | Two independent reviewers on named flows/risks; a third only for a distinct coverage need | Fresh verifier for grouped candidates and named invariants; unrelated flows retain ordinary coverage |
| extended | Automatic: four or five justified independent assignments; explicit: two to five as needed | One fresh grouped verification batch for candidates and assigned invariants |

Every discovery brief states assigned ABCDE areas, flows/interfaces, questions/invariants and expected evidence/coverage under [reviewers.md](references/reviewers.md). Group shared flows; split only for a distinct need. This skill requests coordinator delegation only for required profile sessions when available and authorized; workers do not delegate. Fresh discovery contexts exclude other findings and the full coordinator transcript. Shared execution facts do not establish independence. Missing delegation uses disclosed single-agent passes. Project-required independent gates still apply.

## Workflow and conditional references

1. **Scope/context.** Read [scopes.md](references/scopes.md), [capabilities.md](references/capabilities.md), [review-areas.md](references/review-areas.md) and [artifacts.md](references/artifacts.md). Pin inputs, discover common facts once, map applicable ABCDE areas to assigned flows/check owners. Separate MR/PR responsibility from version-bound change authors. Choose review kind and functional subject once for the canonical presentation. Establish the persistent run and initial closure; execution worktrees remain separate. Re-review/complement uses [re-review.md](references/re-review.md).
2. **Discovery/verification.** Assign packets under [worker-packets.md](references/worker-packets.md); read [reviewers.md](references/reviewers.md) when delegating/grouping. Preserve results, group evidenced shared causes and verify candidates/material questions in one batch per scope. Reopen only for new evidence or an uncompleted gate. Mark remaining uncertainty explicitly.
3. **Report/close.** Recheck code/description/attribution freshness. Use [report-format.md](references/report-format.md) for the same canonical title and heading hierarchy in user report/public comment; only the user report includes the ABCDE matrix. Retain and verify the report, final record, executor provenance and necessary evidence under artifacts.md before cleanup. Record observed closure; preserve interrupted/pending runs and user resources.

Read [workspaces.md](references/workspaces.md) before builds/tests/installs/reproductions or other writes. Those executors need owned Git worktrees, preferably the project's established location (normally .worktrees); read-only workers may share pinned inputs or immutable Git objects. Blocked creation is an explicit validation limitation, never an automatic switch to scratch/copies. Load [external-cli.md](references/external-cli.md) only for configured external execution and [publication.md](references/publication.md) only for remote publication.

## Helpers

Use an interpreter and absolute script paths; consult --help. The archive helper prepares/registers/validates/retains/closes durable runs without deleting resources; its native fallback and mandatory gates are in artifacts.md. Other helpers remain optional: review_packets.py validates/merges internal packets; complete the final record under [result-contract.md](references/result-contract.md). Existing workspace/runner/report helpers retain their roles. Measurement collection is opt-in for an explicitly requested cost evaluation: only then load [measurements.md](references/measurements.md) and [evaluation.md](references/evaluation.md). Normal reviews do not initialize measurement files, probe counters or estimate consumption. Helpers do not prove truth, select models or grant permissions.
