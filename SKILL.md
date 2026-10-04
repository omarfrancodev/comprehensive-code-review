---
name: comprehensive-code-review
description: Use when the user requests a code review, MR/PR review, re-review, assessment of local changes, commits, a feature, or current code, including a broad review invoked through another review skill.
metadata:
  version: "2.1.1"
---

# Comprehensive Code Review

Review the requested scope using concrete scenarios, consequences, precise locations and evidence. Report in the user's language. Discover project conventions at runtime; no other skill is required.

## Boundaries

Reviewing permits inspection and necessary temporary artifacts within existing permissions. Preserve the main checkout/index and user resources. Fixing product code, committing, pushing, remote description edits, publishing, approval and merge each need their own authorization. Respect read-only/no-execution requests. Remove only verified run-owned resources; retain the report first.

Static decisive flow can prove a defect; missing tests or unavailable tools cannot. Distinguish regressions, preexisting defects, description discrepancies and unresolved requirements. Passing checks cover their actual scenarios, not the entire change.

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
2. **Discovery/verification.** Use compact records under [result-contract.md](references/result-contract.md). Read [reviewers.md](references/reviewers.md) when delegating/grouping. Preserve independent results, provisionally group shared causes, then verify under the profile. Discard unsupported claims; mark unresolved ones explicitly.
3. **Report/close.** Recheck code/description freshness. Use [report-format.md](references/report-format.md) for a user report/public draft; only the user report includes the ABCDE matrix. Preserve the final record/report, then clean owned resources without undoing user changes.

Read [workspaces.md](references/workspaces.md) only for isolated-resource operations, [external-cli.md](references/external-cli.md) only for configured external execution, and [publication.md](references/publication.md) only for remote publication. Builds/writes need isolated executor workspaces; read-only workers may share pinned inputs. Commit-only static inspection can read immutable Git objects without a worktree.

## Optional helpers

Use an available interpreter and absolute script paths; consult --help. review_workspace.py manages owned snapshots; review_runner.py runs configured adapters; review_contract.py validates/groups records and renders Spanish reports. No helper proves finding truth or grants permissions. Read [evaluation.md](references/evaluation.md) only when evaluating this skill's effectiveness/cost.
