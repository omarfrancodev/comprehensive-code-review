# Profile selection and closure

Select once during shared scope/context discovery, before delegating. Reuse already collected facts; no separate selection agent, full audit, scoring system or measurement probe. Record selection source (explicit/automatic), effective profile and concrete basis in the existing profile_reason/context. Line count, urgency, model, available slots, technology names and ABCDE letters do not determine depth.

## Selection precedence

1. An explicit economy/balanced/deep is fixed for the requested scope. Observable deep mechanisms do not silently override it. Apply the selected review passes and any verified project gates; economy with a required independent gate still executes that gate. If proof or capabilities are inadequate, disclose the limitation and apply verdict precedence, never treat the profile as acceptance of an exception. A desired profile change needs user authorization; missing evidence is not automatically a reason to spend more sessions.
2. Without an explicit profile, choose deep when an observable trigger below applies. Otherwise choose economy only when all eligibility conditions below are established. Balanced is the fallback when bounded eligibility is not established, including material questions without a deep mechanism.
3. Automatic selection may escalate economy to balanced/deep or balanced to deep when new facts invalidate its basis. Record the fact and transition; reuse context, checks and unaffected discovery, refresh only changed inputs and assignments. Do not downgrade after discovery starts to avoid candidate verification or erase uncertainty. A later re-review/complement selects for its own current scope, not by blindly inheriting the earlier profile.

## Automatic economy eligibility

All conditions must be supported by the initial neutral context; absence of a known problem is not proof:

- The requested change is a contained behavior, a mechanical compatible transformation or a bounded follow-up whose affected consumers/interfaces are identified and can be checked directly. A follow-up includes adjacent affected behavior, not only the corrected line.
- Applicable requirements and expected outcomes are clear from supplied/verified sources; no material unknown requirement, version/input gap or unexplored dependency prevents assessing that behavior.
- No observable deep trigger applies to the affected mechanism, including an invariant still being reassessed in a follow-up. An unmodified sensitive filename alone does not disqualify economy.
- No verified gate requires independent review, and the change does not require discovery across unexplored independently deployed consumers or broad system boundaries.

Examples: local normalization with known consumers and explicit expected output; a description correction against pinned code; a compatible repeated internal rename with checked mappings. They remain subject to actual coverage. Many files do not prove breadth or simplicity; unsupported mappings keep balanced. Worktrees, tests, artifacts, description consistency and ABCDE coverage are unchanged across profiles. Economy is a review strategy, not a no-execution mode.

## Observable deep triggers

For automatic selection, use deep when the change materially:

- Alters authorization enforcement, tenant scoping or trust boundaries.
- Changes transaction boundaries, uniqueness/idempotency, irreversible writes or recovery guarantees.
- Adds a destructive/incompatible migration or changes schema assumptions used by existing consumers.
- Changes concurrent ordering/cancellation, distributed state or resource lifecycle with a credible failure scenario.
- Changes a contract across independently deployed producers/consumers or a rollout dependency that can break existing users.

An auth filename, ordinary query, compatible additive migration or isolated validation rule is not enough. Identify the altered mechanism, flow and consequence.

## Deep assignments by affected flow

The final record keeps one effective profile, deep; scoped depth/owners stay in the existing shared context and briefs, not a new profile enum or report matrix. Map triggering flows, adjacent producer/consumer paths and named invariants. Give two fresh discovery reviewers concrete flow/perspective assignments; justified overlap serves a named cross-interface risk or independent gate. A third requires a distinct uncovered need, never file count or one worker per area.

Non-triggering flows retain ordinary balanced coverage by an existing owner/coordinator; do not send every file to every independent reviewer. Substantive candidates/material questions from those flows still enter fresh verification. Use one grouped verification batch for candidates and explicitly assigned deep invariants, including invariants with no candidates. Reuse neutral checks through their single executor; independent reviewers inspect decisive raw inputs, not another reviewer's conclusions. No automatic second whole-scope audit.

An explicit deep without an automatic trigger still gets deep passes on actual affected flows/invariants; do not invent sensitive mechanisms to justify the user's choice.

## Verification and closure

Economy checks candidates/material questions skeptically in-session. If none remain, check coverage and close without another discovery sweep.

Balanced uses a fresh verifier for substantive code candidates, material uncertainty or a required independent gate. Mechanically evident description-only corrections can be checked by the coordinator using collected evidence; disputed required product behavior remains substantive. P3 alone does not exempt a code defect. Record verification mode/reason.

Deep independently verifies grouped candidates and assigned invariants. Missing independent sessions uses a disclosed skeptical fallback; a required independent gate may make evidence inadequate.

Close when affected flows are covered and candidates/questions are decided, or when a concrete capability/version constraint prevents adequate evidence. A diagnosed blocked check is not repeatedly retried unless inputs change or a viable permitted alternative exists. Repeated source movement ends with the exact reviewed version and remaining uncertainty.

## Verdict decision

Priority expresses consequence; blocking depends on affected requirements and verified policy. Preexisting defects block only for a demonstrated scope-relevant consequence/gate; no baseline means unknown origin. Precedence:

1. Confirmed blocker: not_approvable; also disclose uncertainties.
2. No blocker, but stale version, inadequate coverage or material unresolved limitation: insufficient_evidence.
3. No blocker/material uncertainty, concrete nonblocking reservations: approvable_with_reservations.
4. Otherwise: approvable within the exact scope.

Only the user/verified policy accepts material exceptions. Reservations cannot waive unknown required behavior. A recommendation is not a remote approval action.
