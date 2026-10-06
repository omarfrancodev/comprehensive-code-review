# User reports and public comments

Use one canonical final record from result-contract.md. Report in the user's language; internal enums remain stable. The optional renderer produces Spanish Markdown; other languages/requested formats map the same fields manually. Persist canonical JSON internally under artifacts.md; do not duplicate full JSON in the user response unless requested.

## Presentation rules

Verdict first; one result per project/scope; one finding per cause. Use exact base/head/snapshot and verified links. Code needs a real version-specific file/line; description issues use the MR/PR section plus change evidence. Never link removed temporary workspaces.

Use a separate verdict paragraph, a blank line, and one metadata field per Markdown list item. Use list items for finding fields too; plain consecutive newlines are soft breaks, not a portable visual layout. Separate headings, paragraphs and lists with blank lines. Preserve literal untrusted names/text through escaping. User-facing values are translated (e.g. No aprobable, equilibrado, independiente); enums such as not_approvable/balanced remain only in records. Manual rendering follows this same contract.

Confirmed findings appear as findings; unresolved claims/material limits appear as uncertainties. Rejected candidates stay internal unless withdrawing prior claims. Omit empty sections, full logs, duplicate findings tables, generic praise and speculative defects. Give observable corrections, not an unsolicited patch.

Priority labels: 🔴 P0 — Crítico; 🟠 P1 — Alto; 🟡 P2 — Importante; 🔵 P3 — Menor. Translate labels as needed, preserve circle/code. P0 is demonstrated immediate severe compromise/outage/corruption; P1 serious credible failure; P2 concrete correctness defect; P3 limited consequence. Blocking and origin are separate. Conditions come from actual blockers/nonblocking reservations, never silent acceptance of material unknown behavior.

## User Report Format — fixed order

Required: verdict/reason; project/mode/reference/version/target; MR/PR responsible person (local: Responsable); change authors; profile/reason and verification mode; MR/PR description result (local: No aplica; revisión local); confirmed findings or clean-review sentence; actual validation and covered flows; ABCDE coverage matrix for new reviews. Legacy schemas 1/2 lack authors; do not invent them.

Then conditional sections, in this order: uncertainties; conditions/reservations; re-review ID changes; residual resources or actual publication outcome. Omit successful cleanup mechanics. Residual resources need exact paths and next actions. Reused evidence/substantive reruns are identified. No executed checks means an explicit static-only statement.

```markdown
## Code Review

**Veredicto:** [translated allowed value] — [specific reason].

- **Alcance:** [project] · [translated mode]
- **Versión:** [base] → [head/snapshot]
- **Destino:** [if applicable]
- **Responsable del MR/PR:** [verified account/name or No identificado; local label: Responsable]
- **Autores del cambio:** [verified accounts/display names or No identificados]
- **MR/PR:** [verified reference link; local label: Referencia]
- **Perfil:** [translated profile] — [observable reason]
- **Verificación:** [translated mode]
- **Descripción:** [status and concise result; local: No aplica; revisión local]

### Hallazgos confirmados
#### [colored priority] — [stable ID]: [specific title]

- **Ubicación:** [precise reference] · **Origen:** [translated origin]
- **Escenario e impacto:** [conditions → expected/actual failure → consequence]
- **Evidencia:** [decisive flow or check ID/result]
- **Corrección requerida:** [observable behavior]
- **Bloqueante:** [yes/no; reason when yes]

### Validación

- [Actual check/result, reuse/rerun reason or static-only statement]

**Cobertura:** [inspected flows; material gaps appear under uncertainties]

### Matriz ABCDE

| Área | Estado | Evidencia o motivo | Hallazgos |
|---|---|---|---|
| A — Arquitectura y diseño | [state] | [decisive paths/checks or applicability/pending reason] | [IDs or —] |
| B — Comportamiento y negocio | [state] | [evidence/reason] | [IDs or —] |
| C — Contratos e integración | [state] | [evidence/reason] | [IDs or —] |
| D — Datos y persistencia | [state] | [evidence/reason] | [IDs or —] |
| E — Seguridad y operación | [state] | [evidence/reason] | [IDs or —] |
```

Use review-areas.md states and scope rules; Cubierta means inspected, including any confirmed findings. Each row is concise and references existing findings. No overall risk level or quality score. Legacy version 1 records keep their original presentation; no guessed matrix.

Replace an empty findings section with: no blocking defects were confirmed within the reviewed scope. Target 60–120 words per finding, retaining decisive evidence; never omit confirmed findings to meet a word target. Report resolved/withdrawn IDs in re-review changes even if absent from current findings.

## Public Comment Format — fixed order

Use the same structural Markdown, verdict, scope/version/reference, **MR/PR responsible person and change authors**, description result, confirmed finding blocks and validation. Public validation uses check IDs, actual execution revision, outcomes and concise public-safe reuse/rerun reasons; raw commands remain in the user/internal record. Then conditional uncertainties, conditions/reservations and re-review changes. Omit the ABCDE matrix/area classifications, profile selection, worker names, internal resource/archive paths, measurements and cleanup mechanics. Material coverage gaps still appear as uncertainties explaining the verdict. Use the finding block above unchanged.

Variants:

- Clean: metadata, description, clean-review sentence, validation/limits.
- Findings: metadata, description, confirmed blocks, validation, uncertainties/conditions if applicable.
- Insufficient evidence: metadata, description, validation and specific material uncertainty/pending proof; no invented defect heading. Confirmed nonblockers can still appear.

Responsibility is operational MR/PR assignment: explicit verified user mapping, otherwise assignee(s), otherwise MR/PR creator as a disclosed source fallback, otherwise No identificado. It does not establish change authorship. Multiple assignees use a verified designated account or verified display names. Local responsibility needs a supplied/verified mapping; do not assign uncommitted changes to the HEAD author automatically.

Change authors are separately collected once from actual version-bound platform commits or the selected Git range. Retain each identity source and relevant commit IDs under result-contract.md. Co-author trailers can supply declared display-name provenance; mentions require a verified platform account mapping. Git author metadata proves recorded attribution, not real-world identity or account ownership. Deduplicate only identities with supported equivalence. The MR/PR creator, assignee, committer and reviewers are not automatically authors. Uncommitted local authors stay unknown unless an explicit attribution maps them to the reviewed snapshot. Always render the schema3 authors slot; unknown is No identificados. Mention only verified accounts; never derive @usernames from names/emails. Missing identity alone is not a code defect or reason to repeat discovery.

Publishing uses publication.md. A draft or description correction does not authorize a remote edit.
