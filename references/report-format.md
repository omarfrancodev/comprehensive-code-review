# User reports and public comments

Use one canonical final record from result-contract.md. Report in the user's language; internal enums remain stable. The optional renderer produces Spanish Markdown; other languages/requested formats map the same fields manually. No full JSON plus Markdown unless requested.

## Presentation rules

Verdict first; one result per project/scope; one finding per cause. Use exact base/head/snapshot and verified links. Code needs a real version-specific file/line; description issues use the MR/PR section plus change evidence. Never link removed temporary workspaces.

Confirmed findings appear as findings; unresolved claims/material limits appear as uncertainties. Rejected candidates stay internal unless withdrawing prior claims. Omit empty sections, full logs, duplicate findings tables, generic praise and speculative defects. Give observable corrections, not an unsolicited patch.

Priority labels: 🔴 P0 — Crítico; 🟠 P1 — Alto; 🟡 P2 — Importante; 🔵 P3 — Menor. Translate labels as needed, preserve circle/code. P0 is demonstrated immediate severe compromise/outage/corruption; P1 serious credible failure; P2 concrete correctness defect; P3 limited consequence. Blocking and origin are separate. Conditions come from actual blockers/nonblocking reservations, never silent acceptance of material unknown behavior.

## User Report Format — fixed order

Required: verdict/reason; project/mode/reference/version/target; responsible person; profile/reason and verification mode; MR/PR description result; confirmed findings or clean-review sentence; actual validation and covered flows.

Then conditional sections, in this order: uncertainties; conditions/reservations; re-review ID changes; residual resources or actual publication outcome. Omit successful cleanup mechanics. Residual resources need exact paths and next actions. Reused evidence/substantive reruns are identified. No executed checks means an explicit static-only statement.

```markdown
## Code Review

**Veredicto:** [allowed value] — [specific reason].
**Alcance:** [project] · [mode/reference]
**Versión:** [base] → [head/snapshot] · **Destino:** [if applicable]
**Responsable:** [verified account/name or No identificado]
**Perfil:** [profile] — [observable reason]
**Verificación:** [independent/same session/justified skip/unavailable]
**Descripción:** [MR/PR only: status and concise result]

### Hallazgos confirmados
#### [colored priority] — [stable ID]: [specific title]

**Ubicación:** [precise reference] · **Origen:** [introduced/preexisting/unknown]
**Escenario e impacto:** [conditions → expected/actual failure → consequence]
**Evidencia:** [decisive flow or check ID/result]
**Corrección requerida:** [observable behavior]
**Bloqueante:** [yes/no; reason when yes]

### Validación

- [Actual check/result, reuse/rerun reason or static-only statement]

**Cobertura:** [inspected flows; material gaps appear under uncertainties]
```

Replace an empty findings section with: no blocking defects were confirmed within the reviewed scope. Target 60–120 words per finding, retaining decisive evidence; never omit confirmed findings to meet a word target. Report resolved/withdrawn IDs in re-review changes even if absent from current findings.

## Public Comment Format — fixed order

Use the same verdict, scope/version/reference, **responsible person**, description result, confirmed finding blocks and validation. Public validation uses check IDs, actual execution revision, outcomes and concise public-safe reuse/rerun reasons; raw commands remain in the user/internal record. Then conditional uncertainties, conditions/reservations and re-review changes. Omit profile selection, worker names, internal resource paths and cleanup mechanics. Use the finding block above unchanged.

Variants:

- Clean: metadata, description, clean-review sentence, validation/limits.
- Findings: metadata, description, confirmed blocks, validation, uncertainties/conditions if applicable.
- Insufficient evidence: metadata, description, validation and specific material uncertainty/pending proof; no invented defect heading. Confirmed nonblockers can still appear.

Responsibility: explicit verified user mapping, otherwise assignee(s), otherwise author metadata. Always include the field; unresolved is No identificado. Mention only verified accounts; never derive @usernames from names/emails. Multiple assignees use a verified designated account or their verified display names. Missing identity alone is not a code defect or reason to repeat discovery.

Publishing uses publication.md. A draft or description correction does not authorize a remote edit.
