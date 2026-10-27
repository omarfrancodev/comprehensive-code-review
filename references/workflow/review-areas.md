# ABCDE coverage matrix

Use these lenses to assign affected mechanisms explicitly, then consolidate coverage in the final user report. Applicable letters alone add no sessions/checks, change-risk rating or quality scores. Profile selection and independent verification follow profiles.md; verdict rules remain unchanged.

Use the aspect names below in the existing discovery brief and flow notes. Select only aspects connected to observed code, requirements, interfaces or operational boundaries; load a linked dimension reference only when that aspect is material to the selected scope. Final schema 11 records all 27 dimension decisions explicitly under each area. Dimension IDs refine inspection questions and evidence; they create no automatic checks or reviewer assignments.

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

Derive covered rows from inspected scenarios, not the assignment's area list or test count. State relevant accepted/rejected/fallback states, failure transitions, compatibility windows and resource lifecycle boundaries when the change owns them. The existing packet flow notes and limitation fields are sufficient; no new matrix columns, automatic five-agent topology or quality score is introduced.

## Required schema-11 dimensions

Persist A01–A05, B01–B05, C01–C05, D01–D05 and E01–E07 exactly once, under their area. The linked dimension references define their stable meanings. Every row has exactly `{id, status, details, material, finding_ids}`. Details state decisive paths/check IDs or the explicit pending/applicability reason; an assignment or passing unrelated check does not establish coverage. Use `not_applicable` with a reason, `material=false`, no findings; use `not_evaluated` for applicable uninspected work. Never omit a dimension or mark the whole area covered from one inspected aspect.

Aggregate the parent from dimensions: exclude not_applicable; no remaining rows means not_applicable, all covered means covered, all not_evaluated means not_evaluated, every other combination means partial. Parent material is the OR of dimension material; parent finding_ids is their sorted distinct union. Material is true only for pending required coverage. Covered dimensions may reference defects; multiple dimensions may reference the same finding without copying it. Apply the existing verdict rules to material gaps, with no new score or severity rule.

Schemas 1–10 retain their original coverage shape and bytes; absence of historical dimension decisions is not retroactively a review failure. New final records require the explicit decisions; historical reuse retains its existing applicability gates.
