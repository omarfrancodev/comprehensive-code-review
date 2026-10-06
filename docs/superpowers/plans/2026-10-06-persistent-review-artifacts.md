# Persistent review artifacts and presentation implementation plan

> **For agentic workers:** Use superpowers:executing-plans or superpowers:subagent-driven-development task by task; each task follows RED/GREEN verification.

**Goal:** Implement the approved common archive, durable closure/measurements and portable Markdown, distinguishing MR responsibility from authorship.

**Architecture:** Keep execution evidence in owned temporary sessions. Archive each review independently under a user-level root, with a small closure and measurements record. Upgrade new canonical final records to schema 3 for explicit change authors, accepting schemas 1/2 unchanged as input.

**Tech stack:** Python 3.10+, standard library, unittest, Git; no new runtime dependency.

**Spec:** Four proposals approved in the conversation on 2026-10-06, plus separate assignee and commit-author identities. Create a PR for user review; merge and release are pending.

## Global constraints

- Root precedence: explicit output root, CCR_ARTIFACTS_DIR, user home/.comprehensive-code-review/reviews.
- Every run has a collision-resistant directory; repository identity survives worktree changes. Archive defaults stay outside the project and skill installation.
- Preserve permitted report/final record/closure/measurements before cleaning only owned temporary resources. No automatic history deletion or cross-run context cache.
- Native unavailable consumption is null with a reason; no credits estimates or inclusive-parent/child double counting.
- User and public metadata use Markdown list items. Public reports retain their existing exclusions. Internal enums remain stable; user-facing values are translated.
- Authors come from version-bound commits/co-author metadata, not assignees or MR creator. Account mentions need verified mappings; show unknown when unavailable.
- Preserve local Git identity omarfrancodev <fofe2803@gmail.com>, tests, independent verification, ABCDE and prior required gates.

## Review focus

1. Unsafe roots or symlinks must not redirect archive writes or cleanup.
2. Interrupted or refused cleanup must retain the archive and precise residual paths.
3. Re-reviews and concurrent same-scope reviews must not overwrite history.
4. Native unavailable or partial usage must not become zero/complete consumption.
5. An assigned reviewer must not be rendered as the author; malformed identities must not become mentions.

## Tasks / status

- [x] Update clean main and create feat/persistent-review-artifacts; baseline 73 tests pass outside sandbox. Sandbox temporary-write failures are environmental.
- [x] RED: run independent no-guidance behavioral controls and identify actual shaping gaps.
- [x] RED/GREEN: archive helper and integration tests in scripts/review_artifacts.py and tests/test_review_artifacts.py. Interface: prepare from pinned scope; retain validated final report and supplied disjoint run measurements; close from explicit observed cleanup evidence. Atomic writes and no arbitrary resource deletion.
- [x] RED/GREEN: schema 3 final change_authors and structural Markdown in scripts/review_contract.py, tests/test_review_presentation.py; cover different assignee/author, multiple authors, unknown accounts, legacy records, escaping and user/public projections.
- [x] Update SKILL.md, archive/workspace/metrics/scope/context/presentation/publication/result-contract references, README and CHANGELOG; prepare 2.3.0.
- [x] GREEN: fresh-context scenarios with the revised full skill; verify archive location/lifecycle, missing measurements, role separation and rendered Markdown.
- [x] Run the complete suite and independent final code/skill review; fix evidenced defects and rerun affected checks. Final: 123 tests, 122 passed/one host-privilege skip; both independently verified archive defects corrected.
- [x] Commit, push and create/attach PR #3 with actual validation evidence. Stopped before merge/tag/public release; the user then reviewed and approved publication on 2026-10-06.

## Verification

Run targeted RED tests before implementation, then python -B -m unittest discover -s tests -q from the skill repository. Test real temporary directories/Git repositories, portable Markdown block structure and failure persistence. Keep simulations separate from real model cost benchmarks.
