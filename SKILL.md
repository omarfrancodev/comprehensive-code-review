---
name: comprehensive-code-review
description: Use when the user requests a code review, MR/PR review, re-review, assessment of local changes, commits, a feature, or current code, including a broad review invoked through another review skill.
metadata:
  version: "2.2.0"
---

# Comprehensive Code Review

Review the requested scope using concrete scenarios, consequences, precise locations and evidence. Report in the user's language. Discover project conventions at runtime; no other skill is required.

## Boundaries

Reviewing permits inspection and necessary temporary artifacts within existing permissions. Preserve the main checkout/index and user resources. Fixing product code, committing, pushing, remote description edits, publishing, approval and merge each need their own authorization. Respect read-only/no-execution requests. Remove only verified run-owned resources; retain the report first.

Static decisive flow can prove a defect; missing tests or unavailable tools cannot. Distinguish regressions, preexisting defects, description discrepancies and unresolved requirements. Passing checks cover their actual scenarios, not the entire change.

## Load by role

Assigned discovery/verification workers read [worker-packets.md](references/worker-packets.md), their stage's section and the pinned brief with binding project instructions. Return the compact packet; the coordinator workflow below handles profiles, presentation and resources. Missing facts trigger a targeted coordinator refresh.

The coordinator loads references by phase and embeds relevant rules in briefs. Use [reading-strategy.md](references/reading-strategy.md) to plan bounded access/checkpoints. Context identities bind exact inputs; routing preserves project gates.

## Profiles

Honor an explicit profile; otherwise use balanced. Escalate to deep for observable material risk under [profiles.md](references/profiles.md), not merely because a file concerns security/storage.

| Profile | Discovery | Verification |
|---|---|---|
| economy | One reviewer, potentially the coordinator | Same-session skeptical pass over candidates/material questions |
| balanced | One reviewer, potentially the coordinator | Fresh verifier for substantive candidates/material questions; skip when none remain and coverage is adequate |
| deep | Two or three independent reviewers assigned distinct flows/risks | Fresh verifier for grouped candidates and explicitly assigned high-risk invariants |

This skill requests coordinator delegation only for required profile sessions when available and authorized; workers do not delegate. Fresh discovery contexts exclude other findings and the full coordinator transcript. Shared execution facts do not establish independence. Missing delegation uses disclosed single-agent passes. Project-required independent gates still apply.

## Workflow and conditional references

1. **Scope/context.** Read [scopes.md](references/scopes.md), [capabilities.md](references/capabilities.md) and [review-areas.md](references/review-areas.md). Pin inputs, discover common facts once, map applicable ABCDE areas to assigned flows/check owners. MR/PR includes description consistency and verified responsible-person metadata. Re-review uses [re-review.md](references/re-review.md).
2. **Discovery/verification.** Assign packets under [worker-packets.md](references/worker-packets.md); read [reviewers.md](references/reviewers.md) when delegating/grouping. Preserve results, group evidenced shared causes and verify candidates/material questions in one batch per scope. Reopen only for new evidence or an uncompleted gate. Mark remaining uncertainty explicitly.
3. **Report/close.** Recheck code/description freshness. Use [report-format.md](references/report-format.md) for a user report/public draft; only the user report includes the ABCDE matrix. Preserve the final record/report, then clean owned resources without undoing user changes.

Read [workspaces.md](references/workspaces.md) only for isolated-resource operations, [external-cli.md](references/external-cli.md) only for configured external execution, and [publication.md](references/publication.md) only for remote publication. Builds/writes need isolated executor workspaces; read-only workers may share pinned inputs. Commit-only static inspection can read immutable Git objects without a worktree.

## Optional helpers

Use an interpreter and absolute script paths; consult --help. review_packets.py validates/merges internal packets; complete the final record under [result-contract.md](references/result-contract.md). Existing workspace/runner/report helpers retain their roles. [measurements.md](references/measurements.md) defines counters and optional review_metrics.py; unavailable usage stays unknown. Read [evaluation.md](references/evaluation.md) only to evaluate effectiveness/cost. Helpers do not prove truth, select models or grant permissions.
