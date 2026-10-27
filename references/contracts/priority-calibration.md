# Priority calibration

Load for candidate verification and coordinator consolidation, including focused's same-session pass and documented fallbacks. Priority describes the evidenced consequence; confirmation, origin and blocking answer different questions. Discovery still returns candidates without priority. A clean scope needs no empty calibration pass or example-corpus load.

## Consequence rubric

| Level | Evidence required | Boundary |
|---|---|---|
| P0 — Critical | Demonstrated catastrophic compromise, outage or corruption, immediate when the change is activated/executed, requiring immediate containment | Explain the essential asset/boundary, magnitude, urgency and effective controls. A serious defect is not automatically catastrophic; a security label or one affected tenant alone establishes neither P0 nor a ceiling |
| P1 — High | Reachable serious failure of a principal function, sensitive-data authorization, important integrity, or supported deployment/operation | One materially affected entity can suffice. Conditional network/concurrency failures and specific supported inputs can qualify. Blocking a supported deployment can be P1 even when its transaction rolls back and the previous service remains available |
| P2 — Important | Concrete functional/result defect with bounded consequence and no demonstrated serious damage | Identify what bounds the damage and recovery. A recoverable secondary function can still violate its contract; automatic recovery does not turn every functional defect into P3 |
| P3 — Minor | Demonstrably limited consequence without relevant functional damage | Examples include a local help typo with correct validation/payload or a secondary diagnostic discrepancy. Explain the limit instead of assigning P3 by elimination |

P0 does not require a production incident, universal impact or irreversible damage. A catastrophic immediate outage may qualify even when later rollback restores service. A control that prevents damage differs from a hypothetical or later recovery. Conversely, disclosure/editing of sensitive records within one entity is a serious authorization failure, ordinarily P1 on those facts, without inventing a catastrophic chain. Trace additional consequences before claiming P0.

## Six decision questions

1. What obligation or invariant is violated? A permitted fallback with its required partial-result signal is not itself a defect.
2. What actual input/state and inspected path reach the failure? Confirm, reject or leave unresolved before settling consequence.
3. What damage, affected scope, recovery and effective controls are demonstrated? Preserve unknowns rather than inventing incident frequency or latency.
4. Which rubric level does that consequence support, and what fact separates it from the plausible adjacent level? No numerical score, default P2 or quota applies.
5. What are origin and scope-specific blocking separately? The same consequence has the same priority when only its age or the author's acknowledgement changes.
6. Does `impact` concisely explain that choice through damage, scope and recovery? The coordinator completes this explanation even if the verifier returned no priority/impact delta.

For every new confirmed finding, write one concise justification in existing `impact`, beside its concrete consequence. No fixed prefix, new field or four-level dismissal is required. `scenario` supplies trigger/preconditions; `evidence` supports facts; `blocking_reason` explains acceptance of this scope. Check `purpose` remains the question declared before execution and check result remains the observation, neither a copy of this justification. Dimensions identify inspected mechanisms, not severity.

Use existing packet-1 `updates.priority` and, when needed, `updates.impact`. The parser does not make these deltas mandatory or judge prose semantically. Final records still require priority for unresolved/rejected rows under their existing contract, but those are not confirmed-severity claims and do not enter confirmed counts. Keep final 11, its 27 dimensions, purpose/receipt and all historical shapes unchanged; old records need no retroactive justification.

## Separate uncertainty and acceptance

If the basic defect is proved but a larger consequence is not, classify the proved effect and disclose the larger uncertainty. If an unknown guard/flag determines whether the defect exists at all, retain unresolved status; P2 is not a substitute for confirmation.

Preexisting origin, a worse baseline, improvement over baseline, an author's risk acknowledgement or nonblocking status alone do not lower priority. A reduction needs an evidenced change in effective damage/exposure. An accepted business decision can change the obligation: reassess whether a defect exists and its residual consequence rather than treating acceptance as proof of minor harm. A preexisting P1 may be nonblocking for this MR when no scope-relevant requirement/gate is violated; record that decision separately.

A permission, difficult-to-guess ID, feature flag, off-happy-path input or manual recovery is a concrete precondition/control to evaluate, not an automatic downgrade. Inspect reachable existing callers/contracts without inventing future integrations or treating the UI as server validation. Static decisive flow can prove serious consequences without a benchmark; counted extra operations alone do not prove an outage. Missing tests, style and preferences need an actual obligation/consequence before becoming findings.

Reassess prior labels against current evidence while preserving IDs and immutable history. Contrast comparable decisions within the current grouped verification; a change needs facts or a reasoned correction, not deference to a previous label. Keep existing profile/independence and verdict rules. This guide adds no reviewer, discovery sweep, mandatory benchmark or general new phase.

## Two boundaries

- A valid catalog entry exceeds a migration column and deterministically aborts its atomic seed. P1 can be justified by the supported deployment being impossible; avoiding partial writes does not remove that failure. A startup path that instead destroys the entire sole essential store immediately without an effective barrier can justify P0.
- A secondary panel violates promised immediate visibility but recovers automatically with stored data intact: a bounded functional defect can be P2. A help typo with correct behavior is P3. A missing test with no demonstrated defect belongs in coverage or recommendations, not an invented P3.

The optional [calibration exercises](../../docs/examples/priority-calibration.md) illustrate these boundaries; do not load the corpus on every ordinary review.
