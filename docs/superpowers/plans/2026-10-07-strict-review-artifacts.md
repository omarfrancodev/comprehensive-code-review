# Strict review artifacts implementation plan

> Implement inline with test-driven-development and a fresh final reviewer.

**Goal:** Enforce the approved archive layout, registered evidence locations and verified retention before cleanup; open a PR and await user validation before merge/release.

**Design:** Use the archive helper whenever its interpreter/script can execute within permissions. Native fallback must implement the same contract. Validate the actual archive path against pinned identities, independently of a valid ownership marker. Preserve legacy archives and user overrides of the output root. Bootstrap scope/evidence only inside an owned session, registering it with the durable run before discovery or validation begins.

**Architecture:** Archive schema 3 stores normalized repository identity and unique run ID for deterministic layout validation without requiring the source checkout to survive. Schemas 1/2 retain their existing records and receive compatible structural layout checks. A read-only `validate` command checks ownership, layout and hashes; `--require-retained` is the cleanup gate. Retain, close and previous-run loading also validate layout automatically.

**Tech stack:** Python 3.10+, standard library, Git, unittest; no new dependencies.

**Constraints:** Preserve final review schemas and renderer behavior. Never migrate historical runs or mutate another worktree. Root overrides change only the root. Validation cannot prove findings, actual execution or disposal ownership. Target patch release 2.4.1; publish only after the human validates the PR.

## Task 1: Archive layout gate

Files: `scripts/review_artifacts.py`, `tests/test_review_artifact_layout.py`.

- [x] Add real filesystem regressions for renamed/reparented repository, scope and run directories with internally consistent ownership records.
- [x] Observe missing gate failures before implementation.
- [x] Add shared layout derivation, schema 3 identity fields and read-only `validate(run_dir, require_retained=False)` / CLI.
- [x] Verify prepared/retained runs, legacy schema 1/2, source checkout disappearance, custom roots, altered evidence and failed retain/close without writes.

## Task 2: Instructions and release preparation

Files: `SKILL.md`, `references/artifacts.md`, `references/workspaces.md`, `references/capabilities.md`, `README.md`, `CHANGELOG.md`.

- [x] Require artifacts.md before the first artifact write and helper use when executable.
- [x] Define owned-session bootstrap, exact returned run_dir, native fallback invariants and explicit evidence selection before cleanup.
- [x] Treat old run layouts as historical data, not current policy; document immutable legacy handling and limitations.
- [x] Fresh-context workflow probe, complete suite, CLI/help/frontmatter/local-link checks and independent review.
- [x] Prepare 2.4.1 metadata.
- [ ] Commit/push branch and create/attach PR (handoff step after this validation record).
- [ ] Await explicit human PR validation, then merge and publish tag/release with verified ZIP/checksums.

## Review focus

- Current repository remotes or missing original checkouts must not invalidate durable stored identities.
- Legacy schemas remain readable and pending legacy runs remain closable without migration.
- Overrides of the archive root must not bypass the three-level layout.
- Renaming a run and rewriting its marker must not bypass the deterministic path gate.
- Evidence retention is selective copying, not automatic movement of a session or all context.

## Evidence and rulings

- Base: main `d780bc2503dc47ea7f700c4d7f1ecb54bd4f694e`.
- Real failure supplied by the user: native 2.3.0 runs omitted repository IDs; a later run created a sibling scratch directory. Existing helper validates marker containment but does not reconstruct layout.
- Baseline probe: helper optional even when available; bootstrap scope location is unspecified; --context-input does not copy evidence. This confirms the instructions permit divergent preparation paths.
- Final review: fixed generated repository slugs truncated at a separator without changing historical slug derivation; regression exercises schemas 1/2/3 (RED before correction).
- Workflow probe: fixed post-cleanup observation circularity with inline cleanup/residual flags; regression observes real session removal before close (RED before correction).
- Ruling: add `register` and inline close observations because mandatory helper use and session-only temporary artifacts otherwise require native metadata writes or a new post-cleanup temporary session.
- Initial baseline suite encountered sandbox TEMP permission errors before meaningful execution. Retry uses an ignored worktree-owned temporary directory; this is an environment result, not a product failure.
- The worktree-owned TEMP retry exposed the intentional default-root/skill-installation guard in one fixture. Moving disposable test fixtures to the separate writable visualization root produced a clean baseline: 133 tests, 131 pass/two host-permission skips.
- Final integrated suite: 150 tests in 150.897 seconds, 148 pass/two host-permission skips. The 17 new layout/lifecycle regressions pass. Sources compile, local Markdown links/direct frontmatter/CLI help and diff checks pass; quick_validate cannot run because bundled Python lacks PyYAML.
- Todo tool unavailable: inline status fallback selected; checkboxes track the implementation. The user's approved design and explicit implementation request authorize inline execution without another design approval gate.
