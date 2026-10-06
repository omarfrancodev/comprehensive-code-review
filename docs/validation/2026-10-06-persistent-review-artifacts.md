# Persistent review archive and presentation validation

Source baseline: main 6b34b621f4abb6550dfe04ab0a3a396b1ca888c4 (skill 2.2.0). Release target: 2.3.0. The results below were obtained before publication; the user reviewed PR #3 and approved merge/publication on 2026-10-06.

## Mechanical RED/GREEN

- Existing baseline: 73 tests passed outside the sandbox. The sandbox attempt failed on temporary fixture write/delete permissions; no product failure was inferred.
- New presentation/attribution tests first observed unsupported schema3, missing author slot and soft-break metadata/finding blocks. A later RED case showed escaped underscores breaking verified mentions; the renderer now preserves validated account identifiers. All 12 presentation cases passed. Legacy contract and ABCDE suites passed (34 and 15 tests).
- Archive tests begin with the helper absent; additional regressions cover real Git/worktree grouping, root precedence, owned nested review sessions, interrupted persistence, unknown measurements, explicit cleanup and evidence hashes.
- Final integrated suite: 123 tests in 62.200 seconds; 122 passed and one Windows symbolic-link case skipped. All six helper sources compile, local Markdown links resolve and git diff --check passes. The ignored local Python bytecode cache is not part of the change.

## Independent review and corrections

A fresh reviewer identified two defects, then another fresh verifier reproduced both in real owned temporary Git fixtures. Two new regression tests failed before correction and passed afterward:

- Retention copied a premature successful-cleanup claim from the input although registered resources still existed. Retention now keeps the canonical record/report and closure pending with observed residuals; close must establish completion. Declared residuals must be registered rather than silently discarded.
- A relative local origin resolved against each checkout and split one repository's linked-worktree history. These origins now use the shared Git common directory for stable archive grouping; a nested-worktree re-review preserves its previous-run link.

The reviewer rechecked the changed source and tests and closed both findings without additional candidates. This recheck was static; execution results come from the actual unittest runs. The archive suite ran 38 tests: 37 passed and one symbolic-link case was skipped for missing Windows privileges; the Windows junction case passed.

## Fresh-context behavioral probes

Five no-guidance controls and five revised-skill samples used matching local/MR/native scenarios. Each sample had a fresh agent context and no execution of a real review. All returned outputs were read manually; these are instruction-shape tests, not token/credit measurements or a statistical model benchmark.

| Pair | No-guidance observed output | Revised-skill observed output |
|---|---|---|
| A: local feature/Codex | Saved files in user worktree review-artifacts; three differently named files | Common per-user root, four prescribed files, verified retention before owned cleanup |
| B: two MRs/Kiro | External review-reports layout with different records per MR | Separate durable MR runs, exact closure and unknown per-review consumption |
| C: local worktree/history | Project .review-artifacts layout; report/consumption/manifest | Common root, prescribed files, linked new run and original worktree preserved |
| D: MR attribution/Kiro | Unspecified root; three files, separated roles | Common root/four files; separate responsible/commit authors as Markdown items |
| E: feature/native sessions | User checkout review-artifacts; two files | Common root/four files, disjoint execution counters and explicit unavailable usage |

Unknown usage was handled sensibly by several controls already; the guidance standardizes its durable availability slot/location rather than claiming the previous agents always invented costs. Likewise some controls separated authorship naturally. The measured shaping gap was inconsistent location/file/lifecycle contracts. All revised samples distinguished user resources from disposable review resources and avoided inferred account mentions or per-review credit attribution.

## Limits

- Native Codex/Kiro usage remains unavailable unless exposed by the harness/adapter. Account-wide credits are not attributable review consumption.
- Optional helpers verify structure, ownership markers and filesystem evidence; they do not establish review truth, commit membership, semantic disjointness or disposal authorization.
- Link creation tests depend on host capability. Actual Windows junction coverage is used when symbolic-link creation lacks privileges; any skipped case is reported with final test results.
