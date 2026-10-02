# Reports and publication

Return one verdict per requested project/scope. Keep reviewer mechanics in the private review record. A public MR/PR comment contains product-relevant findings and validation, not worktree details, internal assets errors, agent names or comparisons with another reviewer.

## Verdict

Start with an explicit verdict:

- **APPROVABLE / APROBABLE:** no confirmed blocking defects and adequate relevant evidence for the reviewed version.
- **APPROVABLE WITH RESERVATIONS / APROBABLE CON RESERVAS:** no confirmed blockers; concrete accepted limitations or nonblocking risks, with conditions stated.
- **NOT APPROVABLE / NO APROBABLE:** confirmed defects prevent recommending merge.
- **INSUFFICIENT EVIDENCE / EVIDENCIA INSUFICIENTE:** material uncertainty or stale version prevents an approval recommendation. Missing capabilities alone are not an invented product defect.

Technical recommendation is not a GitLab/GitHub approval action. State selected profile and reason, delegated/single-agent, static/executed and coverage limitations in the user-facing report; use a separate coverage section so capability limitations do not masquerade as defects. Report whether verification was independent, same-session, skipped under the profile's conditions or unavailable. Shared test evidence does not establish independent discovery or verification.

## Priority

| Priority | Circle color | Spanish label | Meaning |
|---|---|---|---|
| 🔴 P0 | Red | Crítico | Immediate severe compromise, outage or irreversible corruption on a demonstrated path |
| 🟠 P1 | Orange | Alto | Serious functional, security or data failure on a credible affected path |
| 🟡 P2 | Yellow | Importante | Concrete correctness defect that requires correction; blocking depends on affected requirements and impact |
| 🔵 P3 | Blue | Menor | Nonblocking defect or improvement with limited consequence |

In user-facing reports and public comments, show the corresponding colored circle whenever a priority is displayed, including finding headings, priority fields and summary tables. Keep the priority code and label alongside the circle so the meaning does not depend on color alone. For example: `### 🟡 Importante — P2` or `**Prioridad:** 🟡 P2 — Importante`.

Severity follows scenario and consequence, not dramatic wording. Reservations need explicit conditions; do not quietly waive a confirmed issue. Separate optional suggestions from defects.

The reviewer may classify a demonstrated minor risk as nonblocking and justify it. Only the user or a verified project policy can accept a material business exception; do not silently accept it for them. Material uncertainty about a required behavior produces insufficient evidence rather than an approval with reservations.

## User report contract

1. Verdict and short justification.
2. Scope/version: project, MR/PR or local mode, exact base/head or snapshot identity.
3. Findings, descending priority: ID, priority with its colored circle, title, location, scenario, impact, evidence/confidence, introduced/preexisting status and expected correction.
4. Validation: what actually ran and results, identifying reused evidence and material rerun reasons; distinguish fixture failures and environmental limits.
5. Coverage: profile/reason, inspected flows and perspectives, verification mode, independence, material omissions.
6. Re-review changes: resolved, still valid, withdrawn, new findings, when relevant.
7. Cleanup status and any residual owned resource requiring action; publication status.

For MR/PR scopes, include a concise description-consistency result: **aligned**, **needs update**, or **unverified**, tied to the reviewed version and captured description. Under **needs update**, distinguish documentation discrepancies from code defects, cite the claim or material omission and supporting change evidence, and state what the description should declare. Location may be the MR/PR description section plus an evidence code link; do not invent a code line for a documentation-only issue. Severity and any blocking recommendation follow demonstrated impact or verified project policy, not description length or stylistic preferences. This check and suggested wording do not authorize editing the remote description.

Use code links to the reviewed SHA or accurate file/line references. Do not link a removed temporary worktree as if it were still present. Keep full logs out of concise summaries.

## Public comment example

```markdown
## Code Review — [functional scope]

### Veredicto: **NO APROBABLE EN SU ESTADO ACTUAL**

**MR/PR:** [reference] · **Versión revisada:** [SHA] · **Destino:** [branch]
**Responsable:** @[verified username]

### 🟡 Importante — P2

#### 1. [Specific defect title]

**Ubicación:** [SHA-specific code link and line].
**Escenario:** [concrete conditions and expected/actual behavior].
**Impacto:** [consequence for users/data].
**Evidencia:** [reproduction or decisive code path].
**Corrección requerida:** [observable behavior the change must ensure].

### Validación

- [Relevant executed check and result, without internal setup noise].
- [Material unvalidated behavior, if it affects the recommendation].

### Condiciones para aprobar

- [ ] [Necessary correction or explicit reservation].
```

For a clean review, state that no blocking defects were found within the reviewed scope; do not claim that no defects can exist. Mention the verified assignee/author when publishing; when the user specifies commit authors, map each finding's introducing commit to an actual verified account. Do not invent @usernames from names/emails. If identity is unresolved, disclose it or obtain the needed account mapping.

## Publication gate

Preparing a draft or reviewing does not authorize publication. On explicit authorization, recheck project/MR identity and current version, publish only the approved scope/content, and verify the returned comment. Updating comments, approving, merging and pushing are distinct actions. Avoid duplicate comments on retries: inspect the remote result before retrying a request with uncertain completion.
