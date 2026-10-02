---
name: comprehensive-code-review
description: Use when the user requests a code review, MR/PR review, re-review, assessment of local changes, commits, a feature, or current code, including a broad review invoked through another review skill.
metadata:
  version: "1.1.1"
---

# Comprehensive Code Review

Coordinate an evidence-based review of the requested scope. Discover project context at runtime; no project-specific installation or Superpowers dependency is required. Report in the user's language.

## Contract

- Reviewing authorizes inspection and necessary temporary review artifacts within the user's permitted environment. Respect explicit read-only/no-create instructions and tool permissions; use the applicable fallback.
- Preserve the main checkout, index, existing worktrees, branches and user files. Never reset, stash, fix product code, commit, push, merge, approve remotely, or publish comments without authorization for that action.
- Select reviewer count and verification from the profile below. This skill explicitly requests coordinator delegation when the selected profile needs independent sessions and delegation is available and authorized; reviewers do not spawn children. The coordinator may perform the single discovery review itself.
- Each reviewer executing builds or modifying fixtures gets its own isolated workspace. Read-only reviewers may share a pinned workspace. Independent sessions can run sequentially when slots are limited.
- A finding requires a concrete scenario, real consequence, precise location and evidence. Verify actual conventions such as automatic DI registration before declaring missing wiring.
- Keep independent discovery separate from other reviewers' findings and existing MR/PR review comments. Read those comments afterward to validate unresolved claims when relevant or requested.
- Finish by removing only resources owned by this run. A failed validation still requires cleanup. Retain a concise report outside temporary workspaces before removing evidence files; report any resource that could not safely be removed.

## Review profiles

Honor an explicit profile; otherwise start with **balanced**. Record the profile and reason before dispatch. Judge risk by affected behavior and interfaces, not diff size alone.

| Profile | Discovery | Verification | Use |
|---|---|---|---|
| `economy` | One reviewer covering relevant perspectives | Same-session skeptical pass over candidates/material questions; disclose lack of independence | Narrow, low-risk changes |
| `balanced` (default) | One reviewer covering relevant perspectives | One fresh verifier only for candidate findings or material unresolved questions | Ordinary PRs and scoped reviews |
| `deep` | Two or three fresh reviewers with assigned flows/risks | One fresh verifier for candidates and material high-risk invariants | Authorization/tenancy boundaries, data integrity, concurrency, migrations or substantial cross-interface changes |

Without an explicit profile, select `deep` when affected mechanisms show those material risks, and explain the choice. Do not expand reviewer count merely because agents are available. An explicit `economy` request does not waive required project gates or make unresolved risk acceptable; preserve the request and state any resulting evidence limitations. Missing delegation uses the supported single-agent fallback with accurate independence disclosure.

In `balanced`, skip the verifier when there are no candidates or material unanswered questions and relevant discovery coverage is adequate. A required independent project gate still applies. In `deep`, verification of high-risk invariants remains relevant even without candidates; assign those invariants explicitly rather than repeating the whole discovery review.

In `economy`, an empty candidate/question list closes the skeptical pass after checking coverage; it does not start another discovery sweep. Honor static-only/no-execution constraints in every profile and report any unexecuted required gate.

## Workflow

1. **Scope.** Load [scopes.md](references/scopes.md). Resolve the requested local view, feature boundary, exact commits or MR/PR base/head. For MR/PR reviews, capture the description and include its accuracy against the actual changes in scope. Identify requirements and uncertainties; clarify only material ambiguity. For a whole-code review, audit the requested module rather than inventing a diff.
2. **Capabilities and shared context.** Load [capabilities.md](references/capabilities.md). The coordinator discovers common project context once, creates the versioned context record and validation ledger described there, and selects the profile. Select actual supported alternatives; never fabricate capabilities.
3. **Isolation.** Load [workspaces.md](references/workspaces.md). Prefer temporary worktrees inside the project. Pin revisions or capture the exact selected local state, including only explicitly scoped untracked files. Create an ownership record before work. The bundled Python helper automates this if Git and Python 3.10+ are available.
4. **Discovery.** Load [reviewers.md](references/reviewers.md). Assign flow/risk coverage and test ownership; give reviewers the shared context record, raw code access and their bounded assignment. Follow relevant callers, dependencies and consumers. Parallelism is optional; delegated discovery remains independent of other findings.
5. **Verification.** Follow the selected profile's trigger and independence requirements. Validate candidates and assigned unresolved questions/invariants against scenarios, baseline behavior and existing mechanisms. Reuse applicable validation evidence; reproduce only what still needs proof. Distinguish product failures from fixture/setup failures. Discard unsupported claims; don't inflate priorities for hypothetical edge cases.
6. **Consolidation.** Deduplicate by root cause; distinguish introduced regressions, preexisting defects, deployment prerequisites and unknown business assumptions. After independent findings are fixed in the review record, inspect other reviews if relevant. Do not attribute comparisons in a public comment unless requested.
7. **Freshness and report.** Recheck the selected local state or remote head/base. A moving version invalidates approval for the new version until affected analysis is refreshed. Use [report-format.md](references/report-format.md), with verdict first, priority per issue, evidence, coverage and concrete validation limitations. Never equate passing tests with absence of defects.
8. **Close.** Stop owned worker processes, preserve the report, remove owned workspaces and verify both filesystem and Git registration. Check main-checkout drift without undoing user changes. If publication is requested, verify the current MR/PR revision and publish only the authorized content/action.

## Optional executors

Run helpers with an available Python interpreter and an absolute script path; use `--help` for details:

- `python scripts/review_workspace.py prepare|inspect|cleanup ...`: isolated snapshots and ownership manifest.
- `python scripts/review_runner.py --config ...`: an explicitly configured external CLI, fresh process per reviewer, timeout and recorded output. The adapter must itself guarantee fresh agent context and suitable permissions; a new OS process alone does not prove independence.

## Common mistakes

| Temptation | Required response |
|---|---|
| Reuse an old review worktree to save time | Create a workspace owned by this run; leave the old one intact. |
| Use HEAD to review uncommitted edits | Capture the selected index/working tree and included new files. |
| Search only explicit DI registrations | Trace assembly scanning and actual service resolution. |
| Seed reviewers with an admin's diagnosis | Discover independently, then contrast the claim. |
| Call repeated self-review independent | Disclose it as a single-agent review. |
| Delete every review-looking directory | Remove only verified owned paths and Git registrations. |
