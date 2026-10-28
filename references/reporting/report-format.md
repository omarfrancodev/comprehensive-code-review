# User reports and public comments

Use one canonical final record from result-contract.md. Report in the user's language; internal enums remain stable. The optional renderer produces Spanish Markdown; other languages/requested formats map the same fields manually. Persist canonical JSON internally under artifacts.md; do not duplicate full JSON in the user response unless requested. Explicit full/brief project delivery uses delivery.md; the brief projection never replaces the required complete internal report or changes its verdict/coverage.

## Presentation rules

After the title, verdict first; one result per project/scope; one finding per cause. Use exact base/head/snapshot and verified links. Code needs a real version-specific file/line; description issues use the MR/PR section plus change evidence. Never link removed temporary workspaces.

Use H2 for the review title, H3 for verdict, Hallazgos and each icon/priority-name/code/ID block, H4 for its finding title. Hallazgos always includes confirmed P0/P1/P2/P3 counts with their respective colored circle, including zero; use the same summary in user reports, public comments and brief deliveries. Separate verdict reason from heading and use one metadata field per Markdown list item. Finding fields are list items too; plain consecutive newlines are soft breaks. Separate headings, paragraphs and lists with blank lines. Escape literal untrusted text. Translate user-facing values; internal enums remain in records. Manual rendering follows this contract.

Confirmed findings appear as findings; unresolved claims/material limits appear as uncertainties. Rejected candidates stay internal unless withdrawing prior claims. Omit empty conditional sections, full logs, duplicate findings tables and speculative defects. Give observable corrections, not an unsolicited patch. Finding evidence is concise decisive static evidence or linked check IDs; Validación adds the existing meaningful check output/results, skipped checks, blockage and retained log references instead of copying scenario/impact paragraphs.

Priority labels: 🔴 P0 — Crítico; 🟠 P1 — Alto; 🟡 P2 — Importante; 🔵 P3 — Menor. Translate labels as needed, preserve circle/code. Apply the canonical [priority calibration](../contracts/priority-calibration.md), preserving its separate confirmation, origin and blocking decisions. New confirmed findings justify the chosen boundary once in existing Impacto, not in check purpose/result. Conditions come from actual blockers/nonblocking reservations, never silent acceptance of material unknown behavior.

## Canonical title

Select presentation once from scope/context, without extra discovery: kind review -> Code Review; rereview -> Re-review; complement -> Complement Code Review. subject is a short functional description of the reviewed change, not a worker/profile name or invented outcome. Render `## <kind label> — <subject>` in both projections. Re-review/complement meaning and continuity follow re-review.md. Preserve stable finding IDs separately from display ordinals. Legacy schemas 1–3 retain Code Review without guessed presentation; their current rendering uses the same heading hierarchy.

## User Report Format — fixed order

Required: verdict/reason; persistent review ID and relevant previous report links; project/mode/reference/version/target; MR/PR responsible person (local: Responsable); change authors; profile/reason and verification mode; MR/PR description result (local: No aplica; revisión local); Hallazgos with confirmed counts and blocks or clean-review sentence; meaningful validation and covered flows; ABCDE coverage matrix for new reviews. Preserve historical IDs and missing legacy fields honestly.

For final schemas 10/11, the private report states the initial and effective profiles separately. If the selection changed, it also lists each transition with phase and reason. The public comment omits profile history and fulfillment details; legacy reports retain their historical profile line.

Then conditional sections, in this order: uncertainties; conditions/reservations; re-review ID changes; residual resources or actual publication outcome. Omit successful cleanup mechanics. Residual resources need exact paths and next actions. Reused evidence/substantive reruns are identified. No executed checks means an explicit static-only statement.

```markdown
## [Code Review | Re-review | Complement Code Review] — [functional subject]

### Veredicto: **[translated allowed value]**

[specific reason].

- **Alcance:** [project] · [translated mode]
- **ID de revisión:** CR-[actual run_id]
- **Revisión anterior:** [previous report link and review ID, if applicable]
- **Versión:** [base] → [head/snapshot]
- **Destino:** [if applicable]
- **Responsable del MR/PR:** [verified account/name or No identificado; local label: Responsable]
- **Autores del cambio:** [verified accounts/display names or No identificados]
- **MR/PR:** [verified reference link; local label: Referencia]
- **Perfil:** [translated profile] — [observable reason]
- **Verificación:** [translated mode]
- **Descripción:** [status and concise result; local: No aplica; revisión local]

### Hallazgos

**Confirmados:** 🔴 P0: [count] · 🟠 P1: [count] · 🟡 P2: [count] · 🔵 P3: [count]

### [icon] [priority name] · [P0–P3] — [stable ID]

#### [display ordinal]. [specific title]

- **Ubicación:** [precise reference] · **Origen:** [translated origin]
- **Escenario:** [conditions → expected/actual failure]
- **Impacto:** [concrete consequence]
- **Evidencia:**
  - **[canonical check ID](#canonical-check-ID)** — Resultado en Validación.
    - [distinct observation beyond the check result]
  - **Inspección estática** — [decisive static source/flow without a check]
- **Corrección requerida:** [observable behavior]
- **Bloqueante:** [yes/no; reason when yes]

### Validación

- **[canonical check ID]**: [state and actual execution revision; reuse/rerun reason where applicable]
  - **Propósito:** [behavior, condition or hypothesis declared before execution]
  - **Resultado:** [observed output, skipped/blocked reason]
  - **Referencia de ejecución:** [actual safe source link]

- **Cobertura:**
  - [one inspected flow per item; material gaps appear under uncertainties]

### Matriz ABCDE

| Área | Estado | Evidencia o motivo | Hallazgos |
|---|---|---|---|
| A — Arquitectura y diseño | [state] | [decisive paths/checks or applicability/pending reason] | [IDs or —] |
| B — Comportamiento y negocio | [state] | [evidence/reason] | [IDs or —] |
| C — Contratos e integración | [state] | [evidence/reason] | [IDs or —] |
| D — Datos y persistencia | [state] | [evidence/reason] | [IDs or —] |
| E — Seguridad y operación | [state] | [evidence/reason] | [IDs or —] |
```

Use review-areas.md states and scope rules; Cubierta means inspected, including any confirmed findings. Each row is concise and references existing findings. No overall risk level or quality score. Legacy version 1 records have no guessed matrix.

When no findings are confirmed, keep Hallazgos and four zero counts, then say no defects were confirmed within the reviewed scope. Target 60–120 words per finding without omitting decisive evidence. Validation summarizes checks.evidence and actual observed outputs; command text alone is insufficient. With no executions, state static-only and any unexecuted required checks. Report every prior ID's reassessed or not_reevaluated status and provenance in re-review changes, even when absent from findings.

## Public Comment Format — fixed order

Use `**ID**` for check labels, unresolved finding labels and re-review ledger labels in both projections, keeping punctuation outside the bold span. Preserve the actual ID, link target, blank lines around HTML anchors and the established finding heading hierarchy. Escape supplied text separately from generated Markdown. Equivalent full/brief delivery labels follow the same convention; inline cross-references need not repeat label formatting. Historical IDs remain unchanged.

Reuse the canonical title/hierarchy, verdict, review ID, scope/version/reference, **MR/PR responsible person and change authors**, description result, Hallazgos/counts, confirmed blocks and validation. Public validation includes check IDs, actual execution revision, meaningful public-safe output/results, blockage and safe evidence links. Keep private commands, paths, worker mechanics and raw logs in internal/user records. Then conditional uncertainties, conditions/reservations and re-review changes with safe source links. Omit ABCDE, profile selection, archive paths and measurements. Material gaps still explain the verdict. Use the same finding block.

Variants:

- Clean: metadata, description, clean-review sentence, validation/limits.
- Findings: metadata, description, confirmed blocks, validation, uncertainties/conditions if applicable.
- Insufficient evidence: metadata, description, validation and specific material uncertainty/pending proof; no invented defect heading. Confirmed nonblockers can still appear.

Responsibility is operational MR/PR assignment: explicit verified user mapping, otherwise assignee(s), otherwise MR/PR creator as a disclosed source fallback, otherwise No identificado. It does not establish change authorship. Multiple assignees use a verified designated account or verified display names. Local responsibility needs a supplied/verified mapping; do not assign uncommitted changes to the HEAD author automatically.

Change authors are separately collected once from actual version-bound platform commits or the selected Git range. Retain each identity source and relevant commit IDs under result-contract.md. Co-author trailers can supply declared display-name provenance; mentions require a verified platform account mapping. Git author metadata proves recorded attribution, not real-world identity or account ownership. Deduplicate only identities with supported equivalence. The MR/PR creator, assignee, committer and reviewers are not automatically authors. Uncommitted local authors stay unknown unless an explicit attribution maps them to the reviewed snapshot. Always render the schemas3–10 authors slot; unknown is No identificados. Mention only verified accounts; never derive @usernames from names/emails. Missing identity alone is not a code defect or reason to repeat discovery.

Publishing uses publication.md. Public validation is projected from typed check fields before rendering: it keeps IDs, source revisions, statuses, failure kinds and product evidence, while omitting local execution references. Free-text reuse/rerun reasons and evidence containing internal paths or commands need a source-bound `check-publication-context`; this is separate from historical limitation classification. A draft must be prepared and verified against the exact UTF-8 body before an already-authorized send. A draft or description correction does not authorize a remote edit.

## Execution information by audience

Final schemas 8–10 private metadata include “Ejecución del perfil: cumplida/degradada”, alongside actual verification. Public metadata omits both the profile and its fulfillment mechanics. Do not present a degraded requested strategy as fulfilled.

Schemas 8–10 keep typed limitations and execution provenance in the private report/record. Public/manual rendering follows [publication.md](publication.md): relevant product/check/gate impact, no review mechanics. Material ABCDE gaps remain visible without the matrix; deduplicate uncertainties/reservations. Historical public limitations require source-bound classification. One coordinator draft pass covers all public fields; helpers do not certify arbitrary prose as semantically safe.

Separate confirmation, priority and blocking when consolidating observations. Confirmed P3/nonblocking findings remain findings; relevant behavior/compatibility uncertainty uses the existing typed limitation and public_summary even when it does not block integration. Do not hide an observed issue only because exact production volume is unknown, and do not promote an unsupported suggestion to a defect. Rejected hypotheses remain private under the existing rule. Examples: [scenario disposition](../../docs/examples/review-scenario-disposition.md).

## Traceable validation, evidence and coverage

For each listed check show ID/state/revision, then nested **Propósito** and **Resultado** items, followed by any actual safe reference. Missing historical purpose displays `Propósito no registrado (resultado anterior)`; no inferred objective. Findings keep scenario/impact/correction and a nested evidence list. Group by the real check ID, link to its Validación anchor, omit an exact copy of that check's original result, retain distinct deltas as subitems and keep a link even when no delta remains. Different check IDs remain distinct even with identical outputs. Each distinct static observation remains an **Inspección estática** item without a fabricated check. Remove only exact duplicates from the same origin.

The same Markdown hierarchy applies to full reports and public comments. Private final 11/12 shows the five-area summary plus all 27 dimension rows, each with name, status, details and finding references; historical records get no invented dimension table. Public comments omit both internal matrices and present editorial product-flow summaries. Coverage always preserves each source element, its order and duplicates as a nested list:

```markdown
- **Evidencia:**
  - **[C001](#C001)** — Resultado en Validación.
    - La segunda reclamación conserva al primer propietario.
  - **Inspección estática** — src/jobs.py:cancel conserva el estado final.

- **Cobertura:**
  - Creación de trabajos
  - Cancelación
```

This is a partial presentation fragment, not a complete result. Escape all supplied prose separately from generated Markdown; encode legacy ID fragments. Purpose/result/impact remain different facts, rather than three restatements of the defect.

## Accredited checks and private models

Final 12 uses the validated check-disclosure projection. Alongside purpose/result, show the sanitized command and eligible project resources when selected proof accredits the pinned input and executed bytes. A CCR-created/modified entrypoint or unknown origin uses a concrete explanation of method, scenario and result; do not label that invocation as a project resource. Remove sensitive path components/arguments and mark sanitized representations. The same decision applies across public comment, requested handoff and local full/brief/JSON, without reintroducing raw commands in evidence or prose.

Private reports and local full/brief include a model summary by actual participant/phase: configured model, observed model, status, and sanitized provenance or reason for absence. Unknown is explicit and is never guessed from harness/provider IDs. A ledger with coordination alone must disclose reviewers missing capture. Preserve observed changes/conflicts and link the selected ledger digest; do not export raw ledger bytes. Public comments and public handoff omit model/worker provenance. See [the maintained example](../../docs/examples/check-disclosure-and-models.md).
