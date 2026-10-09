# Optional correction or transfer handoff

Create `handoff.md` only when the user requests transfer or correction planning. It works for any review scope, including a commit range, local changes or a module. Derive it from the existing canonical review/context with `retain --handoff` or `render-handoff`; it requires no new review, agents or discovery. Keep the archive copy by default. Create a project copy only when the user explicitly requests that destination.

The compact handoff contains:

1. Review ID, exact scope/version and source record/report references; known prior review references when relevant.
2. Relevant requirements/plan with proven source title, reference and input identity. Omit unknown provenance rather than inventing it.
3. Correction checklist for confirmed findings: stable ID/title and required behavior, with source-report references for precise locations/evidence and existing acceptance checks.
4. Separate unresolved requirements/claims, skipped or blocked checks, pending decisions and material coverage limits.
5. Receiver instructions: verify current version/freshness, inspect linked evidence and rerun only checks affected by changed inputs or unresolved gates.

This is an actionable index into the retained record, not a second full report. An unresolved finding never enters the confirmed correction checklist. Existing check output belongs in validation/evidence references; do not repeat scenario/impact prose. Use only known requirements/plan/decisions from supplied context. Optional context fields are source_record/source_report references, requirements/plan arrays with sourced {title, reference, identity}, and decisions_pending text. Archive `--handoff-context-input` requires `--handoff` and actual retained evidence references; standalone `render-handoff --context` accepts the same collected context. The receiving agent gets fix/publication authority from the user, never this file, a source note or a trace.

Generate an optional handoff before closing when requested. A request after close creates a separate linked transfer operation/artifact and preserves the original immutable run. Use public-safe projection for any externally requested handoff: no private commands/paths or worker mechanics. Publication remains separately authorized under publication.md.
