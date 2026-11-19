# Compact worker packets — packet version 1

Workers load this contract and their stage, plus the pinned brief/raw artifacts and project instructions. The coordinator owns profiles, ABCDE coverage, durable archives, reports and cleanup. New final records use result-contract.md schema 13; legacy full schema 1/2 workers remain supported. Packet version is independent of final schema; workers do not produce author registries, presentation identities or durable closure records.

## Common envelope

Available dispatch/tool timestamps and session IDs are coordinator observations for the archive trace, not new required packet fields. Keep missing times/IDs unknown; do not query provider history, emit extra logs or write durable milestones. The coordinator uses existing results under [lifecycle-trace.md](../archive/lifecycle-trace.md).

Keep model metadata out of ordinary briefs and packets. The coordinator records observed assignment and executor identities for the archive trace. For an explicit request with supplied model metadata, the coordinator handles any private sidecar under [artifacts.md](../archive/artifacts.md).

Required: packet_version (integer 1), stage (discovery/verification), context_id (coordinator-supplied nonempty identity binding exact scope/code/description inputs), check_ids (distinct assigned/referenced IDs), coverage: flows (text array), limitations (array of {detail: nonempty text, material: boolean}). Changed inputs need a new identity. Assignment briefs name applicable ABCDE areas and relevant subaspects in existing text; workers describe observed flows/evidence in the existing packet fields and do not add required aspect fields. Use role-qualified provisional finding IDs; the coordinator maps them consistently under identifiers.md before finalization. For receipt-bound checks, the coordinator allocates the canonical check ID before execution: never rename a check ID after capture. Workers reference the assigned check IDs. Fields are required unless marked optional; empty arrays are valid.

Evidence: kind static/executed, details (specific mechanism/result), optional check_id (null/absent for static; referenced executed ID otherwise). Location: actual path/positive line for code, section for description; remaining path/line/url/section fields are optional/null. Missing source mapping is a limitation, never an invented line.

## Discovery

Add findings: array of {id, type: code/description, location, scenario, impact, evidence}. These are candidates; priority, origin, blocking, title and correction are assessed after verification. Return this packet, not a canonical record/report.

Read changed hunks, affected symbols and required producer/consumer boundaries in bounded fragments. Expand to the next concrete dependency/unanswered requirement; inspect raw assigned code independently. Reuse neutral checks only for matching inputs/configuration. Stop once assigned flows/gates are covered and candidates have concrete triggers/consequences; return remaining material questions as limitations. Unsupported hypotheses stay outside findings. No delegation, product fixes or remote mutation.

## Verification

Apply [priority calibration](../contracts/priority-calibration.md) in this pass. Use existing updates.priority and updates.impact for the consequence-based judgment; no new required packet fields. The coordinator completes justification in final impact if a delta omits it. Discovery remains ungraded; purpose and receipt-bound check IDs remain unchanged.

Add decisions: array of {id, status: confirmed/rejected/unresolved, evidence, optional updates}. One decision per assigned candidate. Unchanged scenario/impact need no repetition. Updates may supply changed location/scenario/impact or explicit priority/origin/title/correction/blocking/blocking_reason; blockers need confirmation and a reason. Preserve distinct scenarios in grouped causes; identify necessary splits for the coordinator.

For a guided final assessment, include an optional packet `assessment` on each decision with `cause`, `relation` and `verification`. Give the stable cause and the relation to the reviewed scope. Verification supplies `obligation`, `trigger`, `consequence`, `consumer` and `question`, with null for unknown or inapplicable facts. For an affected consumer give both its identity and the specific question. Confirmed findings require an obligation, reachable trigger and concrete consequence. A decisive static observation suffices. The coordinator links these decisions to the shared evidence in the [final assessment](../contracts/assessment.md), preserving the already captured resolution authority and the source of any material change. Packet merge returns these decisions separately as `assessments`.

Check claims/material questions against requirements, raw code, baseline and consumers. Apply [the confirmation criteria](../contracts/assessment.md#confirming-a-code-finding) to each code candidate and record the supporting contract or caller in the existing evidence. Name the relevant dimension IDs in the existing flow notes when a finding or check establishes their behavior. Run a targeted check when static evidence is inadequate. Fixture or environment failures cannot confirm a defect. Return new questions to the coordinator. Continuations need new evidence or an uncompleted gate.

In the existing flow notes, give each assigned invariant's canonical dimension ID, observed behavior and decisive reference, including applicable dimensions on a clean review. The coordinator uses these observations in the [final coverage reconciliation](../contracts/result-contract.md#reconciling-applicability-before-retention).

## Coordinator merge

Preserve raw packets; map provisional IDs consistently before verification. Supply context.json with context_id, complete scope and referenced neutral checks projection:

```text
python /absolute/skill/scripts packets validate --input /absolute/discovery.json
python /absolute/skill/scripts packets merge --context /absolute/context.json --discovery /absolute/discovery.json --verification /absolute/verification.json
```

Merge emits a consolidation bundle, not a canonical/final record. Evidence/check revisions remain; amendments retain superseded claim fields and missing judgments stay absent. Complete final fields through actual assessment, then validate under result-contract.md; amendments stay internal. Keep raw packets. For clean scopes eligible to skip verification, omit --verification; candidates/material questions require an explicit packet. Without helpers use the same contracts in supported structured tools/chat.

## Coordinator fulfillment record

Schemas 8–10 coverage.execution belongs to the coordinator and links these existing packets/results. Workers retain packet version 1, never add required execution IDs, infer other workers, delegate or write durable trace. The coordinator records observed reviewer contexts separately from shared context_id and classifies limitation deltas when completing the final result. Schema 10 also binds assignments to the applicable profile selection; workers still do not own that history.

The coordinator uses `scripts setup profile` before prepare and `scripts setup context` after reading the exact returned cierre.json. The context builder preserves profile history, captured inputs and the selected reference-index digest; the coordinator runs phase preflight before registration or dispatch. `scripts setup event` builds only observed assignment milestones. Every agent/discovery/grouped-verification work event, including completion, retains the active required brief reference in `evidence`, with an observed result reference added when available. These helpers do not change packet fields or dispatch workers.

For an independent `agent/started`, the coordinator records the observed executor name; an unknown provider ID stays null. If an earlier dispatch was already run without an executor identity, the coordinator may add one `dispatch-identity/unchanged` annotation tied to the original start and a selected local dispatch/result metadata object. Workers do not add packets or repeat work to recover that identity. The annotation does not create another start or result, and the same replay is a no-op.

Workers keep assigned check ownership/observed execution facts in packets; the coordinator binds final schemas 9/10/11/12 check.execution to registered executor identities. A role or trace actor is not automatically a writing executor. No new required worker field or workspace per worker.

## Scenario evidence and reuse context

Use existing flow notes and limitations to distinguish the scenario inspected from the letter assigned. Challenge a test expectation against the requirement and actual sequence; inspect effects introduced by a correction, neighboring consumers and resource cleanup. A passing test is evidence only for its assertions. Return limited but evidenced behavior/resource defects as candidates even when likely nonblocking; assess priority separately during verification. Keep speculative future callers and unmeasured outage claims out of confirmed findings.

When the coordinator is preparing reusable MR/PR evidence, preserve the list of complete pinned Git files consumed in the assigned evidence context, including producer/consumer, instruction, configuration and test files. The coordinator consolidates it with setup reuse-context; this is not a new packet schema, command trace or permission to add external inputs after discovery.

## Traceability without a packet migration

Packet version 1 stays unchanged. Put dimension IDs and inspected flows/pending reasons into existing coverage.flows/limitations text; report decisive static evidence with check_id=null and executed evidence with its real assigned check ID. The coordinator consolidates all 27 decisions in final 12 and keeps purpose in the neutral check ledger. It supplies `context.check_schema_version=12` when merging the new check shape; a missing selector still means legacy schema 2. Do not add required dimension/purpose fields to packet 1 or fabricate separate checks for static observations. An unbound legacy provisional check ID may still be canonicalized before capture; receipt-bound IDs remain stable across merge and retention.
