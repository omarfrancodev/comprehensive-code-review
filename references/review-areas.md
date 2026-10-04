# ABCDE coverage matrix

Use these lenses to map affected flows, then consolidate coverage in the final user report. They do not add sessions, checks, a change-risk rating or quality scores. Profile selection, independent verification and verdict rules remain unchanged.

| Area | Applicable mechanisms |
|---|---|
| A — Architecture/design | Responsibilities, dependencies, established project patterns and change boundaries |
| B — Behavior/business | Requirements, validation, branching, edge cases and expected results |
| C — Contracts/integration | APIs, events, serialization, consumers, compatibility and rollout ordering |
| D — Data/persistence | Queries, transactions, constraints, migrations and data integrity |
| E — Security/operation | Authorization, tenant isolation, errors, concurrency, resource lifecycle and credible performance scenarios |

Discover applicability once in common context; attach areas to existing flow owners. Review only applicable mechanisms within the requested scope, including affected adjacent interfaces. Economy/balanced can cover all applicable areas through one discovery reviewer. Workers return their assigned flows and limitations; the coordinator builds one final matrix from that evidence. Do not dispatch one agent or repeat tests per letter.

Every final matrix has one row per area:

- covered: applicable aspects were inspected within scope; details cite decisive paths/checks. Findings may exist.
- partial: some applicable aspects remain pending; details state what was covered and what remains.
- not_evaluated: applicable coverage could not be performed; details explain the constraint.
- not_applicable: no affected mechanism within scope; details justify that conclusion.

Mark a pending gap material when it prevents establishing required affected behavior or meeting a verified gate. Missing execution alone is not a gap when static evidence is decisive. Material gaps follow insufficient-evidence precedence unless a confirmed blocker already determines the verdict.

Use canonical finding IDs as cross-references. A cause spanning areas may be referenced in multiple rows; retain one finding block. Description consistency remains its existing check, not five new checks. Re-review refreshes only affected rows with justified evidence reuse.

The user report includes the matrix. Public comments include the existing findings/validation and material uncertainty needed to explain the verdict; they omit the matrix, area labels and classifications. Covered means inspected, not defect-free or a production guarantee.
