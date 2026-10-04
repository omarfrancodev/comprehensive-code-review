# Changelog

## 2.1.0

- ABCDE coverage areas map to existing flow owners without adding per-area agents or tests.
- New user reports include a five-row coverage matrix with evidence/reasons and canonical finding references. Public comments omit the matrix and classifications while retaining material uncertainty.
- Schema version 2 validates complete area coverage, references and verdict consistency. Legacy version 1 records remain supported unchanged.
- No change-risk level or quality score added; existing profile/priority/verdict rules preserved.

## 2.0.0

- Canonical discovery, verification and final records, with an optional standard-library validator and Spanish report renderer.
- Fixed user/public report order, verified responsible-person metadata, separate code/description findings and precise verdict rules.
- Common context/check owners and evidence layout; mode-specific references load only when relevant.
- Observable deep-profile triggers, bounded verification and explicit same-session fallback.
- Provisional same-cause grouping preserving scenarios, stable IDs/aliases and justified evidence reuse across incremental reviews.
- Unit/CLI/workspace integration checks, executable evaluation inputs and a protocol for measuring model accuracy/cost.
- Workspace and external runner safety implementations preserved.

## 1.1.1

Preserved baseline before this revision. Includes economy/balanced/deep profiles, shared context discovery, reduced worker duplication and MR/PR description consistency checks.
