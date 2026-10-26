## Verification

Apply [priority calibration](../contracts/priority-calibration.md) in this pass. Use existing updates.priority and updates.impact for the consequence-based judgment; no new required packet fields. The coordinator completes justification in final impact if a delta omits it. Discovery remains ungraded; purpose and receipt-bound check IDs remain unchanged.

Add decisions: array of {id, status: confirmed/rejected/unresolved, evidence, optional updates}. One decision per assigned candidate. Unchanged scenario/impact need no repetition. Updates may supply changed location/scenario/impact or explicit priority/origin/title/correction/blocking/blocking_reason; blockers need confirmation and a reason. Preserve distinct scenarios in grouped causes; identify necessary splits for the coordinator.

Check claims/material questions against requirements, raw code, baseline and consumers. Decisive static flow is sufficient; run a targeted check for inadequate evidence. Fixture/environment failures cannot confirm a defect. Return new questions to the coordinator; this batch does not restart general discovery. Continuations need new evidence or an uncompleted gate. Missing information yields unresolved status/material coverage, not speculative retries.

## Verification packet

Include the applicable [priority calibration](../contracts/priority-calibration.md) rules in the existing verifier brief. Confirm the obligation and reachable consequence before grading; assess origin and blocking separately. Return existing priority/impact deltas when needed; the coordinator completes the final impact justification. Preserve the current grouped pass, profile and independence requirements.

Supply minimal shared facts, exact version, groups, baseline access, decisive paths, referenced checks and assigned material questions/invariants. Validate/refute groups while preserving distinct scenarios; this is bounded verification, not another full discovery sweep.

Trace actual requirements/mechanisms, registration conventions and consumers. Use baseline for introduced/preexisting/unknown origin. Reproduce when evidence is insufficient; decisive static flow is acceptable. Validate fixtures before interpreting failures. In-memory stores do not establish relational translation, constraints or credible-scale performance.

Load worker-packets.md and its verification section. Return decisions for assigned IDs, decisive evidence and only changed assessments; unchanged candidate prose/check records stay referenced. Independence follows profiles.md; same-session fallback is disclosed. Decisions account for all assigned IDs; final rejected-claim retention stays limited to material uncertainty, withdrawal or likely repeat investigation. Preserve raw packets.

Grouped verification includes pertinent external claims and material questions after the contrast, with source provenance available to the verifier. Verify their mechanism/severity instead of adopting their conclusion. Missing tests or manually managed migrations are not automatically defects. Keep deployment prerequisites and uncertain business rules distinct; retain evidenced state/input defects. CI evidence must name its actual revision and result.

## Findings

Fields: id (stable text), type code/description, status candidate/confirmed/rejected/unresolved, priority P0/P1/P2/P3, blocking (boolean), blocking_reason (text/null), origin introduced/preexisting/unknown, title, location, scenario, impact, evidence, correction.

Discovery emits candidates, not confirmation. Suspected blockers remain blocking=false until confirmed; capture their potential consequence in impact. Final has no candidate state. Blocking requires confirmation and a reason; severity does not determine it automatically.

location: path/line/url/section (text/null except positive integer/null line). Code requires actual path/line; description requires section without invented code lines. Use exact-version links when available.

evidence: nonempty array with kind static/executed, details text, check_id (null for static; included ID for executed). Confirmation requires decisive static flow or actual supporting execution; fixture/environment failures alone cannot prove a product defect. Structural relationships do not establish truth.

For new confirmed findings, existing impact also contains a concise consequence-based priority justification under [priority calibration](priority-calibration.md): damage, scope, recovery and the relevant boundary. This is a producer instruction, not a new field or parser inference. Do not put it in check purpose/result or require it retroactively in historical records.

## Verdict decision

Priority expresses consequence under [priority calibration](../contracts/priority-calibration.md); blocking depends on affected requirements and verified policy. A serious preexisting P1 can be nonblocking for this MR when no demonstrated scope-relevant obligation/gate requires correction: origin changes responsibility, not the evidenced consequence. Preexisting defects block only for a demonstrated scope-relevant consequence/gate; no baseline means unknown origin. Precedence:

1. Confirmed blocker: not_approvable; also disclose uncertainties.
2. No blocker, but stale version, inadequate coverage or material unresolved limitation: insufficient_evidence.
3. No blocker/material uncertainty, concrete nonblocking reservations: approvable_with_reservations.
4. Otherwise: approvable within the exact scope.

Only the user/verified policy accepts material exceptions. Reservations cannot waive unknown required behavior. A recommendation is not a remote approval action.

Priority labels: 🔴 P0 — Crítico; 🟠 P1 — Alto; 🟡 P2 — Importante; 🔵 P3 — Menor. Translate labels as needed, preserve circle/code. Apply the canonical [priority calibration](../contracts/priority-calibration.md), preserving its separate confirmation, origin and blocking decisions. New confirmed findings justify the chosen boundary once in existing Impacto, not in check purpose/result. Conditions come from actual blockers/nonblocking reservations, never silent acceptance of material unknown behavior.

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

