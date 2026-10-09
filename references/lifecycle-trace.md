# Compact review lifecycle trace

Every new durable run keeps `trazabilidad.jsonl` from preparation through observed closure. Archive schema 4 binds `review_id` to `CR-<run_id>` and records trace inventory/hash state in cierre.json. Preserve legacy archives without reconstructing a trace from narrative or guessed timestamps.

The helper records its lifecycle operations. The coordinator records only meaningful observed transitions: agent/profile assignment, discovery completion, a check/result, grouped verification, freshness, and authorized publication. Use `record-event --run-dir <exact returned run> --event-file <owned JSON>` and its help for the input contract. Existing context, packets and checks provide evidence references; the trace is their compact index, not copied reports, metrics, every search/tool call or a reason to reload workers.

Trace schema 1 includes sequence/event_id/run_id/review_id, recorded_at, recorder/actor/executor, provenance, kind/status/summary, evidence/relations and the hash chain. `recorded_at` is the time the event was recorded; exact execution timing/order is asserted only when an actual source provides it. Identify whether provenance is helper/tool/agent/recovered. Distinguish the recorder from the actor/executor; provider IDs stay null when unavailable. Supplied names/identities and references describe observed provenance, not proof of human identity or semantic truth.

Use concise summaries and selected durable evidence/hash references. Record interruption or capability limits honestly. Native fallback follows artifacts.md with the same verifiable structure; it reports limited observations rather than inventing helper execution, missing events or execution order. Pending helper recovery preserves observed facts. `validate` is read-only; optional `--record-checkpoint` records a requested checkpoint only on an open run.

A closed run is immutable. Later transfer/correction/publication is a separate linked operation with its own evidence and authorization; preserve the original review/report/trace. Trace records never grant permission or prove finding correctness.
