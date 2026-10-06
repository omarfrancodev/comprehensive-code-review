# Project worktree review flow validation

Baseline: main 047c77b5810407e9708e4c2411fe86da5bf136db (2.3.0). Target: 2.4.0, pending human PR review and release preparation.

## Mechanical checks

- New regressions first failed for mandatory default measurement creation, missing schema4/title hierarchy and executor context support. They passed after implementation.
- Legacy pending retry without flags first failed, then passed while preserving measurement bytes. A local baseline executor first failed, then passed with actual base HEAD and null snapshot.
- Final complete offline suite: 133 tests in 79.505 seconds, exit 0; 132 passed and one Windows symbolic-link test skipped for missing host privileges. The actual Windows junction case passed.
- All six helper sources compile and their CLI help succeeds. Local Markdown links, direct frontmatter checks and git diff --check pass.
- skill-creator quick_validate could not run because the bundled interpreter lacks PyYAML. Direct checks confirmed the required name/description, metadata version and frontmatter size; no dependency was installed.

## Behavior and independent review

A fresh baseline planning probe following 2.3.0 chose archive-copy fallback on blocked Git, initialized unknown measurements and used the generic Code Review heading. A fresh whole-branch reviewer checked the edited instructions against the approved scenario: worktree approval or blocked validation; local dependency recovery after shared-cache failure; no normal measurement probing; linked complement archive with canonical title.

The reviewer identified documentation remnants and a legacy retry edge; they were corrected and the latter has a regression. A bounded static recheck found no remaining material defects in legacy measurement preservation or baseline provenance. No real MR was executed, no new review archive was created and no model-token/credit savings were measured.

## Limits

Provenance validation checks structure, registered paths, Git root/common repository and HEAD. It does not prove command execution, copy content, local snapshot truth or fixture correctness; the coordinator still checks those inputs. Shared dependencies remain allowed within inspected effects/ownership. Metrics utilities and existing archives remain supported for explicit evaluations. Merge, release date, tag and release assets remain pending human review.
