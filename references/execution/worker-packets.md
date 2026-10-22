# Compact worker packets — packet version 1

Workers load this contract and their stage, plus the pinned brief/raw artifacts and project instructions. The coordinator owns profiles, ABCDE coverage, durable archives, reports and cleanup. New final records use result-contract.md schema 10; legacy full schema 1/2 workers remain supported. Packet version is independent of final schema; workers do not produce author registries, presentation identities or durable closure records.

## Common envelope

Available dispatch/tool timestamps and session IDs are coordinator observations for the archive trace, not new required packet fields. Keep missing times/IDs unknown; do not query provider history, emit extra logs or write durable milestones. The coordinator uses existing results under [lifecycle-trace.md](../archive/lifecycle-trace.md).

Model metadata is also optional coordinator-owned provenance. Preserve a model already exposed by a dispatch or result with its source; do not add required worker fields, infer the effective model from the harness/provider ID, or query history when the value is absent. The coordinator links eligible observations through the private sidecar in [artifacts.md](../archive/artifacts.md).

Required: packet_version (integer 1), stage (discovery/verification), context_id (coordinator-supplied nonempty identity binding exact scope/code/description inputs), check_ids (distinct assigned/referenced IDs), coverage: flows (text array), limitations (array of {detail: nonempty text, material: boolean}). Changed inputs need a new identity. Assignment briefs name applicable ABCDE areas and relevant subaspects in existing text; workers describe observed flows/evidence in the existing packet fields and do not add required aspect fields. Use role-qualified provisional finding/check IDs; the coordinator maps them consistently under identifiers.md before finalization. Fields are required unless marked optional; empty arrays are valid.

Evidence: kind static/executed, details (specific mechanism/result), optional check_id (null/absent for static; referenced executed ID otherwise). Location: actual path/positive line for code, section for description; remaining path/line/url/section fields are optional/null. Missing source mapping is a limitation, never an invented line.

## Discovery

Add findings: array of {id, type: code/description, location, scenario, impact, evidence}. These are candidates; priority, origin, blocking, title and correction are assessed after verification. Return this packet, not a canonical record/report.

Read changed hunks, affected symbols and required producer/consumer boundaries in bounded fragments. Expand to the next concrete dependency/unanswered requirement; inspect raw assigned code independently. Reuse neutral checks only for matching inputs/configuration. Stop once assigned flows/gates are covered and candidates have concrete triggers/consequences; return remaining material questions as limitations. Unsupported hypotheses stay outside findings. No delegation, product fixes or remote mutation.

## Verification

Add decisions: array of {id, status: confirmed/rejected/unresolved, evidence, optional updates}. One decision per assigned candidate. Unchanged scenario/impact need no repetition. Updates may supply changed location/scenario/impact or explicit priority/origin/title/correction/blocking/blocking_reason; blockers need confirmation and a reason. Preserve distinct scenarios in grouped causes; identify necessary splits for the coordinator.

Check claims/material questions against requirements, raw code, baseline and consumers. Decisive static flow is sufficient; run a targeted check for inadequate evidence. Fixture/environment failures cannot confirm a defect. Return new questions to the coordinator; this batch does not restart general discovery. Continuations need new evidence or an uncompleted gate. Missing information yields unresolved status/material coverage, not speculative retries.

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

Workers keep provisional check ownership/observed execution facts in packets; the coordinator maps them to final schemas 9/10 check.execution and registered executor identities. A role or trace actor is not automatically a writing executor. No new required worker field or workspace per worker.
