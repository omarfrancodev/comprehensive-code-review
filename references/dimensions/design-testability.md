# Design, behavior and testability dimensions

Load this reference when the selected scope contains a material architecture/design (A) or behavior/business (B) question. It adds inspection prompts to the existing brief; it does not prescribe a score, test count, reviewer count or severity.

## A — Architecture and design

- **A01 — Boundaries and ownership:** identify the component that owns each state transition or decision; trace producer, consumer and nearby unchanged code where responsibility crosses a boundary.
- **A02 — Dependency direction:** follow concrete calls/data from entry point to effect. Check whether the change introduces hidden coupling, a cycle, duplicated source of truth or a bypass around an established owner.
- **A03 — Lifecycle and state:** enumerate observable states and transitions relevant to the change. Inspect retry, cancellation, partial completion and cleanup only where those paths exist.
- **A04 — Failure isolation:** find what happens when a dependency fails, times out or returns partial data. Check whether one failure corrupts unrelated work or leaves unowned state.
- **A05 — Test seams:** determine whether the changed behavior can be exercised at its real boundary and whether existing tests distinguish the relevant outcomes. A missing test alone is not a product defect.

## B — Behavior and business rules

- **B01 — Preconditions and postconditions:** derive them from the actual requirement, API contract or established behavior; compare each branch and side effect against those conditions.
- **B02 — Validation and branching:** trace accepted, rejected, empty, malformed and boundary values that are reachable for the changed path.
- **B03 — Invariants and edge cases:** state the invariant in concrete terms (for example, an ID remains bound to its owner) and inspect the exact branch that could violate it.
- **B04 — Fallback behavior:** verify which fallback is taken and whether it preserves the required result, authority and visible error state.
- **B05 — User-visible outcome:** connect the triggering input to the response/state a caller sees. Use a short before/after example when it makes a behavior defect reproducible.

Record the relevant aspect names, flow, invariant and decisive source/check in existing brief and evidence fields. Keep findings tied to a concrete trigger and consequence.

For test seams, also compare the assertion's expected behavior with the requirement: a green test may explicitly require the wrong order, audit classification or fallback. For state changes, include a permitted state other than the nominal pair and a failure after an irreversible side effect. For new/default parameters, verify current call sites and omission consequences; a hypothetical future misuse alone is a recommendation, not a confirmed defect.
