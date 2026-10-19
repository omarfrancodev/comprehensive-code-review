# Contract, integration and data dimensions

Load this reference only when an affected interface or persisted state makes contract (C) or data (D) questions material. Keep these prompts in existing brief/evidence text; they do not add record fields or automatic compatibility checks.

## C — Contracts and integration

- **API/event shape:** inspect field names, types, requiredness, null/empty behavior, defaults and error representation at both producer and consumer.
- **Producer-consumer agreement:** trace the actual serialized value through the nearest consumer; verify that neither side silently drops or reinterprets it.
- **Serialization:** inspect encoding, canonicalization, ordering and round-trip behavior only where the changed path depends on them.
- **Compatibility/versioning:** identify supported readers/writers and rollout order from project evidence. Check old/new combinations that can coexist in deployment; do not invent support obligations.
- **Ordering:** follow migrations, events, callbacks or deployments that must occur before another step. Name the actual invariant and evidence.

## D — Data and persistence

- **Identity and ownership:** verify which key identifies the entity and which boundary owns it; test same-label/different-identity cases where relevant.
- **Query/filter semantics:** inspect exact predicates, joins, pagination and null behavior; compare the query result with the intended scope.
- **Transactions:** trace begin/commit/rollback boundaries and intermediate states. Check interruption and retry when the implementation has those paths.
- **Constraints and migrations:** compare schema constraints/defaults/indexes with reads/writes and migration ordering. A migration is relevant only when the change touches persisted shape or behavior.
- **Consistency and recovery:** establish what is durable after partial failure and whether the existing recovery path can distinguish committed from pending work.

Capture the exact contract/data boundary and its decisive evidence in existing assignment or check references. Preserve one finding for one cause even when several dimensions point to it.
