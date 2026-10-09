# Compact worker packets — packet version 1

Workers load this contract and their stage, plus the pinned brief/raw artifacts and project instructions. The coordinator owns profiles, ABCDE coverage, durable archives, reports and cleanup. New final records use result-contract.md schema 7; legacy full schema 1/2 workers remain supported. Packet version is independent of final schema; workers do not produce author registries, presentation identities or durable closure records.

## Common envelope

Required: packet_version (integer 1), stage (discovery/verification), context_id (coordinator-supplied nonempty identity binding exact scope/code/description inputs), check_ids (distinct assigned/referenced IDs), coverage: flows (text array), limitations (array of {detail: nonempty text, material: boolean}). Changed inputs need a new identity. Use role-qualified provisional finding/check IDs; the coordinator maps them consistently under identifiers.md before finalization. Fields are required unless marked optional; empty arrays are valid.

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
python /absolute/skill/scripts/review_packets.py validate --input /absolute/discovery.json
python /absolute/skill/scripts/review_packets.py merge --context /absolute/context.json --discovery /absolute/discovery.json --verification /absolute/verification.json
```

Merge emits a consolidation bundle, not a canonical/final record. Evidence/check revisions remain; amendments retain superseded claim fields and missing judgments stay absent. Complete final fields through actual assessment, then validate under result-contract.md; amendments stay internal. Keep raw packets. For clean scopes eligible to skip verification, omit --verification; candidates/material questions require an explicit packet. Without helpers use the same contracts in supported structured tools/chat.
