## Verification

Add decisions: array of {id, status: confirmed/rejected/unresolved, evidence, optional updates}. One decision per assigned candidate. Unchanged scenario/impact need no repetition. Updates may supply changed location/scenario/impact or explicit priority/origin/title/correction/blocking/blocking_reason; blockers need confirmation and a reason. Preserve distinct scenarios in grouped causes; identify necessary splits for the coordinator.

Check claims/material questions against requirements, raw code, baseline and consumers. Decisive static flow is sufficient; run a targeted check for inadequate evidence. Fixture/environment failures cannot confirm a defect. Return new questions to the coordinator; this batch does not restart general discovery. Continuations need new evidence or an uncompleted gate. Missing information yields unresolved status/material coverage, not speculative retries.

## Verification packet

Supply minimal shared facts, exact version, groups, baseline access, decisive paths, referenced checks and assigned material questions/invariants. Validate/refute groups while preserving distinct scenarios; this is bounded verification, not another full discovery sweep.

Trace actual requirements/mechanisms, registration conventions and consumers. Use baseline for introduced/preexisting/unknown origin. Reproduce when evidence is insufficient; decisive static flow is acceptable. Validate fixtures before interpreting failures. In-memory stores do not establish relational translation, constraints or credible-scale performance.

Load worker-packets.md and its verification section. Return decisions for assigned IDs, decisive evidence and only changed assessments; unchanged candidate prose/check records stay referenced. Independence follows profiles.md; same-session fallback is disclosed. Decisions account for all assigned IDs; final rejected-claim retention stays limited to material uncertainty, withdrawal or likely repeat investigation. Preserve raw packets.

Grouped verification includes pertinent external claims and material questions after the contrast, with source provenance available to the verifier. Verify their mechanism/severity instead of adopting their conclusion. Missing tests or manually managed migrations are not automatically defects. Keep deployment prerequisites and uncertain business rules distinct; retain evidenced state/input defects. CI evidence must name its actual revision and result.

## Findings

Fields: id (stable text), type code/description, status candidate/confirmed/rejected/unresolved, priority P0/P1/P2/P3, blocking (boolean), blocking_reason (text/null), origin introduced/preexisting/unknown, title, location, scenario, impact, evidence, correction.

Discovery emits candidates, not confirmation. Suspected blockers remain blocking=false until confirmed; capture their potential consequence in impact. Final has no candidate state. Blocking requires confirmation and a reason; severity does not determine it automatically.

location: path/line/url/section (text/null except positive integer/null line). Code requires actual path/line; description requires section without invented code lines. Use exact-version links when available.

evidence: nonempty array with kind static/executed, details text, check_id (null for static; included ID for executed). Confirmation requires decisive static flow or actual supporting execution; fixture/environment failures alone cannot prove a product defect. Structural relationships do not establish truth.

## Verdict decision

Priority expresses consequence; blocking depends on affected requirements and verified policy. Preexisting defects block only for a demonstrated scope-relevant consequence/gate; no baseline means unknown origin. Precedence:

1. Confirmed blocker: not_approvable; also disclose uncertainties.
2. No blocker, but stale version, inadequate coverage or material unresolved limitation: insufficient_evidence.
3. No blocker/material uncertainty, concrete nonblocking reservations: approvable_with_reservations.
4. Otherwise: approvable within the exact scope.

Only the user/verified policy accepts material exceptions. Reservations cannot waive unknown required behavior. A recommendation is not a remote approval action.

Priority labels: 🔴 P0 — Crítico; 🟠 P1 — Alto; 🟡 P2 — Importante; 🔵 P3 — Menor. Translate labels as needed, preserve circle/code. P0 is demonstrated immediate severe compromise/outage/corruption; P1 serious credible failure; P2 concrete correctness defect; P3 limited consequence. Blocking and origin are separate. Conditions come from actual blockers/nonblocking reservations, never silent acceptance of material unknown behavior.
