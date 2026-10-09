# ABCDE coverage matrix

Use these lenses to assign affected mechanisms explicitly, then consolidate coverage in the final user report. Applicable letters alone add no sessions/checks, change-risk rating or quality scores. Profile selection and independent verification follow profiles.md; verdict rules remain unchanged.

| Area | Applicable mechanisms |
|---|---|
| A — Architecture/design | Responsibilities, dependencies, established project patterns and change boundaries |
| B — Behavior/business | Requirements, validation, branching, edge cases and expected results |
| C — Contracts/integration | APIs, events, serialization, consumers, compatibility and rollout ordering |
| D — Data/persistence | Queries, transactions, constraints, migrations and data integrity |
| E — Security/operation | Authorization, tenant isolation, errors, concurrency, resource lifecycle and credible performance scenarios |

Discover applicability once in common context; assign every applicable mechanism to a named flow owner using reviewers.md. Briefs declare areas/aspects, files/interfaces, questions/invariants and expected evidence/coverage. Group areas sharing a flow; split when independent mechanisms/perspectives justify it within profile limits. Focused/standard can cover all applicable areas through one discovery reviewer. A dedicated reviewer per area is allowed when supported by distinct needs, including extended eligibility, never a default five-agent plan. Workers return existing flow coverage/limitations; the coordinator derives the final matrix from evidence, not assignments. Each common check still has one executor.

Every final matrix has one row per area:

- covered: applicable aspects were inspected within scope; details cite decisive paths/checks. Findings may exist.
- partial: some applicable aspects remain pending; details state what was covered and what remains.
- not_evaluated: applicable coverage could not be performed; details explain the constraint.
- not_applicable: no affected mechanism within scope; details justify that conclusion.

Mark a pending gap material when it prevents establishing required affected behavior or meeting a verified gate. Missing execution alone is not a gap when static evidence is decisive. Material gaps follow insufficient-evidence precedence unless a confirmed blocker already determines the verdict.

Use canonical finding IDs as cross-references. A cause spanning areas may be referenced in multiple rows; retain one finding block. Description consistency remains its existing check, not five new checks. Re-review refreshes only affected rows with justified evidence reuse.

The user report includes the matrix. Public comments include the existing findings/validation and material uncertainty needed to explain the verdict; they omit the matrix, area labels and classifications. Covered means inspected, not defect-free or a production guarantee.
