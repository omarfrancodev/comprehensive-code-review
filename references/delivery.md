# Explicit portable delivery

Delivery is a projection of an existing retained result, not another review. Activate it only for an explicit full/brief choice, including natural language such as entrega completa/breve. A request to transfer without a mode needs clarification. Profile and delivery are independent; neither brevity nor a destination changes review depth, verdict, coverage or required internal retention.

The agent interprets `--delivery full|brief` and `--output <delivery-root>`. These are request conventions, not npx or shell flags. `--output` alone selects no mode, produces no export and does not redirect the internal archive. The user may separately request an internal archive location under artifacts.md.

## Contents and location

- Full: informe.md and a portable review.json, derived from the same final result. Preserve findings, scenarios, impacts, corrections, exact scope/version, attribution, validation summaries, uncertainties and applicable coverage.
- Brief: resumen.md with identity/version/scope, verdict and reason, confirmed counts, IDs/priorities/locations, concrete triggering scenarios/impacts and correction guidance, meaningful validation summaries and material pending matters. It remains sufficient to understand the requested next work; unresolved claims stay separate from confirmed corrections.
- Optional contexto.md: only additional collected context that changes the next agent's decisions and is absent from the report. Preserve sources and uncertainties; do not repeat findings or create a new plan.
- A small .ccr-delivery.json records projection/source identity and file hashes. It is transfer integrity metadata, not an execution log, review authorization or proof of correctness.

Default root is docs/ccr/reviews in the explicitly identified persistent project checkout. Append the stable scope slug and review identity to distinguish MR/PRs, local scopes and executions. An explicit output selects a different delivery root; relative paths anchor to that persistent checkout. Never infer the persistent destination from an executor's temporary worktree or silently switch to scratch. If the checkout is unclear, request it before writing. Project instructions and existing permissions still apply.

The export omits logs, fixtures, reproductions, trace/closure and dependency trees. Those remain in the internal archive. Avoid private absolute paths, environment commands and links that require undistributed evidence files. Preserve repository-relative code locations and useful verified URLs. The portable JSON is identified as a projection through the receipt; unavailable private source references remain explicitly withheld instead of becoming invented URLs or verification results. It cannot replace the original record for archive retention/closure.

## Additional context, when available

Use only facts already collected in the review or supplied continuation context; create no discovery/verification agents or additional inspection pass for these sections.

- Assumptions and decisions: interpretation, source, confirmed/pending state and affected work. Review version and missing verification are scope/limitations, not assumptions. Do not silently prefer Plan over Spec when they conflict.
- Sources and criteria analyzed: actual Spec/Plan or other requirements, input identity, sections inspected, partial-analysis limits and conclusions that affect corrections. Merely linking a document does not establish that it was analyzed. Missing Spec/Plan is not a defect; use available criteria or disclose unknown intended behavior.
- Observed implementation state: requirement/component, implemented/partial/not implemented/not evaluated/out of scope, evidence or finding/check IDs. State only what the review inspected. Keep implementation existence separate from executed behavioral validation; a passed build cannot establish all requirements are implemented.
- Pending decisions: material unresolved choices or work from the existing result/context. They do not enter a confirmed correction checklist.

Omit absent sections rather than fabricating sources, assessments or filler. Preserve exact version binding and supported IDs, and ask the recipient to recheck freshness before making corrections.

## Export and preservation

Use scripts/review_delivery.py with --help when executable. It validates the retained source read-only, requires an explicit mode and persistent project checkout, and creates a distinct delivery directory. It never modifies a closed run or copies evidence. Existing destinations and unsafe paths are refused rather than overwritten; a changed delivery requires a distinct explicit destination.

Invoke the helper through its absolute path; these are executable helper arguments, unlike the agent request conventions:

```text
python <skill-path>/scripts/review_delivery.py --run-dir <retained-run-dir> --delivery full --project-root <persistent-checkout>
python <skill-path>/scripts/review_delivery.py --run-dir <retained-run-dir> --delivery brief --project-root <persistent-checkout> --output-root docs/team-review
```

For collected additional context, supply `--context <context.json>`. Omit empty sections; observations in assumptions, decisions, implementation_state and pending use text, references and version. Sources require their actually analyzed sections and known identity:

```json
{
  "assumptions": [
    {"text": "Previously recorded interpretation, still pending confirmation", "references": ["F001"], "version": "<reviewed-head>"}
  ],
  "sources": [
    {"title": "Spec", "reference": "docs/spec.md", "identity": "<known-source-identity>", "sections": ["3.2 Responses"], "version": "<analyzed-version>"}
  ]
}
```

This input contains only supported observations already available, bound to their known version; the helper checks structure, not their truth. The total is limited to 32 KiB and 24 entries. Do not populate the example from invented IDs, sources or versions.

Do not commit, publish or authorize fixes merely because delivery was requested. Report the actual delivery path and any source/destination limitation. When the helper is unavailable, a native export follows the same contents, projection, path and non-overwrite rules. A delivery failure does not erase the retained review or fabricate successful delivery.
