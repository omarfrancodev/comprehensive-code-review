# Strict review artifacts validation

Base: main `d780bc2503dc47ea7f700c4d7f1ecb54bd4f694e`. Target release: 2.4.1. Implementation is isolated in `.worktrees/strict-review-artifacts`; merge and release await explicit human validation of the PR.

## Mechanical checks

- Baseline suite: 133 tests, 131 passed and two host-permission skips. Initial sandbox TEMP errors were environmental; a worktree-local TEMP then exercised the deliberate archive-root/skill-installation restriction. Final fixtures use the separate task-owned writable visualization root.
- Layout/lifecycle regressions failed first against the old helper: relocated paths with updated ownership metadata were accepted; register/validate and inline close were absent. A separate scope-bound retention gate also failed before correction.
- Final command: bundled Python `-B -m unittest discover -s tests -v`, with TEMP/TMP at the task-owned visualization fixture root. Result: 150 tests in 150.897 seconds, 148 passed, zero failures/errors, two skips. Skips: `test_symlink_roots_inputs_and_archived_files_are_refused` and `test_windows_junction_root_is_refused`, due missing Windows privileges/permissions.
- All 17 new regression methods pass. Coverage includes invalid repository/scope/run paths despite coherent marker writes, custom roots, previous-run gates, prepared versus retained validation, selected-file integrity, scope binding, source checkout disappearance, schema 1/2 compatibility, registration before final records and inline observed closure after session removal.
- Sixteen Python source/test files compile in memory; local Markdown links, direct frontmatter checks, helper/register/validate/close help and `git diff --check` pass.
- `skill-creator/scripts/quick_validate.py` could not execute: bundled Python lacks PyYAML. No dependency was added; direct frontmatter/link checks do not substitute for claiming that validator ran.

## Independent checks

A fresh baseline coordinator probe chose native preparation despite an executable helper, citing undefined scope-file bootstrap. Revised instructions require helper preparation, exact returned run_dir, registered evidence-session bootstrap and explicit selected evidence retention; the independent forward probe followed those rules.

The code reviewer found that reapplying `_slug` rejected valid labels truncated at a separator. A real remote-name regression reproduced it, then passed for schemas 1/2/3 after shape validation replaced repeated normalization; historical slug derivation is unchanged. Layout validation now occurs before the exclusive run directory is created.

The forward probe found a closure circularity: a cleanup-file created after removing sessions would violate the new temporary-location rule. Inline observed cleanup/residuals remove that file requirement. Real CLI regressions passed after actual owned-session removal, and the probe confirmed the final instructions can complete without extra temporaries.

## Practical limits

The validator checks recorded identities, ownership-marker integrity, layout and selected file hashes. It does not prove finding truth, executed commands, disposal authority or completeness of the coordinator's evidence selection; it does not scan unrelated directories for stray artifacts. Native fallback requires equivalent recorded checks and is available only when the helper cannot execute, not when its gate fails.

Historical helper schemas 1/2 remain readable/closable without migration. Unowned or nonconforming manual archives remain unchanged and may fail validation; this is disclosed as a compatibility limitation. No actual MR review, historical archive migration, merge, tag or release publication was performed during these checks.
