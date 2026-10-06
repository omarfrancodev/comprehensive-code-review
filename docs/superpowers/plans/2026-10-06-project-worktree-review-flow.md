# Project worktree review flow Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this approved plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Deliver 2.4.0 with project worktree execution, optional measurements and consistent review headings.

**Architecture:** Keep the existing workspace helper and canonical report renderer. Extend final records to schema 4 for presentation identity; archive schema 2 omits default measurements while supporting older archives. Record executor facts in the existing closure from the neutral context.

**Tech Stack:** Python 3.10+, standard library, Git, Markdown.

**Spec:** User-approved six proposals in this conversation: shared dependencies remain permitted with local fallback on problems; titles are Code Review, Re-review or Complement Code Review. Create a PR for human review before merge/release.

## Global Constraints

- Preserve user resources, old archives, schemas 1–3 and existing review gates.
- No extra measurement agents/probes, new dependencies or automatic copy fallback.
- Builds/tests/installs/reproductions use owned project worktrees; static reads may omit them.
- ABCDE stays user-only; public comments exclude internal resources and measurements.

## Review Focus

- Legacy pending archives still close without losing measurement evidence.
- A cleanup rewrite preserves the same presentation identity.
- Unknown counters cause no default file or probe.
- Executor records cannot attribute another checkout/revision to the review.
- Shared dependency failures trigger owned dependency recovery, not a global link ban.

### Task 1: Archives and provenance

**Files:** scripts/review_artifacts.py; tests/test_review_artifacts.py.

- [x] Add failing tests for no-default metrics, explicit metrics, legacy closure and executor provenance.
- [x] Observe RED; implement archive schema 2 and optional --context-input using existing neutral context.executors.
- [x] Run focused tests, preserving archive integrity/recovery guards.

### Task 2: Presentation identity

**Files:** scripts/review_contract.py; tests/test_review_presentation.py; references/result-contract.md.

- [x] Test schema 4 presentation {kind, subject}, portable heading hierarchy and retained identity after closure.
- [x] Observe RED; validate/render the single canonical identity with legacy fallback.
- [x] Run focused contract/presentation/archive checks.

### Task 3: Instructions and distribution

**Files:** SKILL.md; references/workspaces.md, capabilities.md, artifacts.md, report-format.md, re-review.md, measurements.md, evaluation.md, external-cli.md; README.md; CHANGELOG.md.

- [x] Baseline pressure probe, then update instructions to the approved worktree/dependency/measurement/presentation rules.
- [x] Fresh forward probe and bounded independent review; repair confirmed issues.
- [x] Full offline suite, link/frontmatter/CLI validation and git diff checks.
- [ ] Commit/push authorized branch, create and attach PR; leave release pending human approval.

## Execution ledger

- RED: current 2.3.0 behavior probe permits archive-copy fallback, mandatory unknown measurements and one Code Review title. New mechanical cases failed before implementation.
- GREEN: schema4 heading identity, opt-in measurements, legacy cleanup/retry and executor provenance focused checks pass. A baseline-executor regression failed first, then passed with actual base HEAD and null snapshot.
- Ruling: keep the existing workspace helper's .worktrees default; another established project location uses native Git with equivalent safeguards — avoids changing its cleanup ownership boundary.
- Ruling: preserve measurement bytes in legacy retry instead of demanding fresh flags — backwards compatibility without collection overhead.
- Ruling: compare immutable baseline with null snapshot — never attribute selected local edits to the base.
- One fresh whole-branch reviewer and a bounded recheck found no remaining material defects; clarified schema4 in worker/author documentation.
- Release stays pending human PR review; the existing 2.3.0 published download link remains accurate until release preparation.

- Final integrated validation: 133 tests in 79.505s, 132 passed/one Windows symlink privilege skip; six helpers compile/help pass, direct frontmatter/local links and diff checks pass. quick_validate lacks PyYAML; no dependency added.
