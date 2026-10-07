# Adaptive profile selection validation

Baseline: main d780bc2503dc47ea7f700c4d7f1ecb54bd4f694e (skill 2.4.0). Target: 2.5.0, pending human PR review.

## Isolation and preparation

PR #5 changed only .gitignore to exclude .worktrees/ and was merged with explicit user authorization. It did not change the skill version or publish a release. The development worktree .worktrees/adaptive-review-profiles was created from that updated main; main remains clean and the worktree inherits the exclusion.

## Behavioral RED/GREEN

One fresh baseline probe followed 2.4.0 in five planning scenarios. The contained normalization and compatible repeated internal rename both chose balanced; current rules had no automatic economy selection. Explicit economy with a required independent gate and scoped deep assignments already worked in the baseline and were clarified rather than described as new failures.

One fresh forward probe followed the revised skill before inspecting the diff or validation notes. It selected economy for the two demonstrated bounded scenarios, balanced for a missing external requirement, preserved explicit economy while executing its independent project gate, and focused automatic deep on tenant enforcement rather than UI text/documentation. Additional cases escalated automatic economy when a separately deployed contract appeared and kept deep for a one-line transaction re-review with idempotency still in scope.

The forward reviewer inspected the final nine-file instruction diff and related references; no material contradiction or defect was identified. These are instruction-planning probes, not real MR reviews, measured savings or a statistical accuracy benchmark.

## Mechanical verification

- Clean worktree baseline: 133 tests in 69.118 seconds; 132 passed and one Windows symlink privilege skip.
- Final suite: 133 tests in 71.531 seconds; 132 passed and the same skip. Actual Windows junction coverage passed.
- Six helper sources compile; local Markdown links, direct frontmatter/version checks and git diff --check pass. Existing helpers, final schema 4 and profile enums were not changed.
- skill-creator quick_validate cannot run because the bundled interpreter lacks PyYAML; no dependency was installed. Direct frontmatter checks were used.

Independent gates, evidence adequacy, verdict precedence, execution isolation, persistent artifacts, user-only ABCDE and explicit publication permissions remain in effect. Merge, tag and release await human validation of the feature PR; the worktree stays available for further edits.
