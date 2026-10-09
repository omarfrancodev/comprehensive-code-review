# Stable review, finding and check identities

New durable reviews use `CR-<run_id>` from the prepared archive, not a title, MR number or invented timestamp. Carry it into the final record, report and requested handoff. Link prior reviews by their actual durable reference/verified URL and known review ID; legacy unknown IDs remain null.

New final finding/check IDs are uppercase `F001`/`C001`, padded to three digits, no hyphen and no all-zero ID. Continue with `F1000`/`C1000` as needed; redundant padding such as `F0001` is invalid. A display ordinal is not an ID. Preserve IDs for the same cause/check across re-review; new causes/check executions receive unused IDs. Never rewrite historical archives to normalize IDs.

Workers may return qualified provisional IDs, such as `D01-F001` and `D02-F001` (checks use `D01-C001`). The coordinator preserves raw packets and maps every source ID once, consistently updating evidence, coverage, decisions and re-review references. Keep the source-to-canonical mapping with retained evidence. `canonicalize-ids --reserved-ids <known-chain.json>` takes findings/checks arrays from verified prior lineage to avoid recycling earlier IDs; it performs structural remapping, not same-cause decisions, truth or automatic aliases.

Deduplication is an evidenced same-cause decision. Preserve distinct scenarios and map duplicate aliases directly to the surviving ID. Source native note IDs remain source provenance, not canonical finding IDs. Re-review preserves genuine legacy IDs through `grandfathered_ids`; declare only IDs supported by the linked prior record. A new `F-01`/`c1` is invalid, while an evidenced historical ID is retained exactly.
