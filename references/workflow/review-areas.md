# ABCDE coverage matrix

Use these lenses to assign affected mechanisms explicitly, then consolidate coverage in the final user report. Applicable letters alone add no sessions/checks, change-risk rating or quality scores. Profile selection and independent verification follow profiles.md; verdict rules remain unchanged.

Use the aspect names below in the existing discovery brief and flow notes. Select only aspects connected to observed code, requirements, interfaces or operational boundaries; load a linked dimension reference only when that aspect is material to the selected scope. Aspects refine inspection questions and evidence; they add no final-record fields, reviewer assignments or automatic checks.

| Area | Applicable mechanisms |
|---|---|
| A — Architecture/design | Boundaries and ownership; dependency direction; lifecycle/state; failure isolation; test seams. See [design and testability](../dimensions/design-testability.md). |
| B — Behavior/business | Preconditions and postconditions; validation/branching; edge cases and invariants; fallback behavior; user-visible outcomes. See [design and testability](../dimensions/design-testability.md). |
| C — Contracts/integration | API/event shape; producer-consumer agreement; serialization and defaults; compatibility/versioning; ordering and rollout. See [contracts and data](../dimensions/contracts-data.md). |
| D — Data/persistence | Identity and ownership; query/filter semantics; transaction boundaries; constraints and migration; consistency and recovery. See [contracts and data](../dimensions/contracts-data.md). |
| E — Security/operation | Authentication/authorization; tenant/resource isolation; trust boundaries and validation; error disclosure; concurrency/idempotency; lifecycle/cleanup; measured performance risk. See [security and operation](../dimensions/security-operation.md). |

Discover applicability once in common context; assign every applicable mechanism to a named flow owner using reviewers.md. Briefs declare areas/aspects, files/interfaces, questions/invariants and expected evidence/coverage. Group areas sharing a flow; split when independent mechanisms/perspectives justify it within profile limits. Focused/standard can cover all applicable areas through one discovery reviewer. A dedicated reviewer per area is allowed when supported by distinct needs, including extended eligibility, never a default five-agent plan. Workers return existing flow coverage/limitations; the coordinator derives the final matrix from evidence, not assignments. Each common check still has one executor.

Every final matrix has one row per area:

- covered: applicable aspects were inspected within scope; details cite decisive paths/checks. Findings may exist.
- partial: some applicable aspects remain pending; details state what was covered and what remains.
- not_evaluated: applicable coverage could not be performed; details explain the constraint.
- not_applicable: no affected mechanism within scope; details justify that conclusion.

Mark a pending gap material when it prevents establishing required affected behavior or meeting a verified gate. Missing execution alone is not a gap when static evidence is decisive. Material gaps follow insufficient-evidence precedence unless a confirmed blocker already determines the verdict.

Use canonical finding IDs as cross-references. A cause spanning areas may be referenced in multiple rows; retain one finding block. Description consistency remains its existing check, not five new checks. Re-review refreshes only affected rows with justified evidence reuse.

The user report includes the matrix. Public comments include the existing findings/validation and material uncertainty needed to explain the verdict; they omit the matrix, area labels and classifications. Covered means inspected, not defect-free or a production guarantee.
