# Independent reviewer briefs and verification

## Select perspectives

Use the profile selected in [SKILL.md](../SKILL.md), not a fixed reviewer count. One reviewer combines relevant perspectives in `economy` and `balanced`; `deep` distributes them across two or three reviewers. For a large change, partition by coherent flows and interfaces rather than spawning arbitrary extra agents. Match depth to observable risks.

| Perspective | Checks adapted to actual code |
|---|---|
| Functional correctness | Requirements, business invariants, normal/boundary/error paths, calculations, state transitions, idempotency, cancellation |
| Data and architecture | Persistence/query semantics, keys, tenancy, transactions, concurrency, migrations and rollback, DI conventions, caches, resource lifecycle, performance at credible scale |
| Integration and security | API/DTO compatibility, callers and consumers, authorization, input/output handling, async UI state, configuration and external failures; frontend accessibility where affected |

Use the technology facts in the shared context and trace the assigned code paths. Examples: a backend review traces controller → validation → handler → repositories → storage; a frontend review traces component/state → request/BFF → API contract → response and stale-response handling. These are perspectives, not hardcoded .NET or React rules.

## Coverage and validation ownership

Before dispatch, map each materially affected flow/risk to one discovery owner. Include adjacent interfaces and needed unchanged code in the assignment. At shared boundaries, name who traces producer and consumer behavior; assign overlap only for a concrete cross-interface risk or required independent check. Different perspectives are lenses, not instructions for every reviewer to audit the entire scope. Workers report uncovered boundaries for coordinator reassignment.

For MR/PR scopes, one owner performs the [description-consistency check](scopes.md#mrpr-description-consistency) using the captured description and collected change evidence. Other reviewers report assignment-relevant discrepancies to the coordinator without repeating the complete check. Keep these observations in independent discovery records until collection; the owner consolidates them afterward. This check applies in every profile and does not itself require another agent. Candidates follow the profile's normal verification rules.

Assign each common build/lint/typecheck/test gate to one executor in the shared validation ledger. Other reviewers reuse its evidence when revision, relevant configuration and fixtures match; passing common checks does not replace their assigned code inspection. Run an additional or repeated check only for a distinct scenario, changed inputs, unreliable evidence or a required independent gate, and record the reason. A verifier still independently traces the candidate and reproduces it when existing evidence is insufficient. Every executor that builds/writes keeps its own isolated workspace.

## Dispatch contract

Give each discovery reviewer this brief, populated from the scope record:

```text
Role: [chosen perspective]. Review independently; do not delegate.
Repository/workspace: [absolute isolated path].
Shared context: [accessible versioned record, or relevant embedded subset].
Assignment: [owned flows/risks, code paths and adjacent interfaces].
Validation ownership: [assigned check IDs; reusable evidence references].
Permitted actions: inspect; run assigned safe validation commands and
necessary scenario-specific checks, recording any additional/rerun reason;
create temporary reproduction fixtures only in this owned workspace.
Record each new non-ignored fixture and its final hash using the
workspace helper, or an equivalent coordinator-owned artifact record.
Do not fix product code or mutate remote systems. Do not read other
reviewers' reports or existing review comments during discovery.
Use the shared context for common instructions/configuration/commands;
inspect raw code and assignment-relevant callers/dependencies/consumers.
Report missing context or uncovered interfaces to the coordinator.
Return: inspected flows/files; candidate findings with location,
scenario, consequence, evidence, origin and confidence; validations
actually run and their results; uncertainty and unreviewed areas;
claims examined and rejected with a short reason. If no defect is
supported, say so; do not manufacture findings to fill a quota.
```

Raw requirements belong in the shared context. Coordinator hypotheses and another reviewer's conclusions do not. Fresh context should not inherit the coordinator's full transcript or force workers to reload every skill reference. Each worker that builds/writes gets a distinct workspace. Discoverers can run concurrently; verification follows candidate collection. Concurrency limits change scheduling, not independence.

If the description mixes requirements with another reviewer's diagnosis, extract the observable requirements and defer the diagnosis to verification. Before calling the review broad, map each materially affected flow/interface to an inspected perspective and its evidence, or explicitly list it as uncovered. Headcount alone does not establish coverage.

## Verification brief

Apply the profile's verification trigger first. A triggered verifier receives the shared context, candidates or assigned material questions/invariants, exact code/version and reusable validation evidence, not an instruction to agree:

```text
Validate or refute each candidate and resolve assigned material questions
or high-risk invariants. Trace actual mechanisms
and requirements. Attempt the concrete scenario using safe reproduction
or inspect decisive control/data flow. Check the baseline to establish
whether the defect is introduced, preexisting, or newly exposed.
Reuse version-matched checks; run additional reproductions when existing
evidence is insufficient, recording their distinct purpose.
Return confirmed/rejected/unresolved for each, evidence, assumptions,
priority justification and any test-fixture/setup defects. Do not fix
product code. Rejected/unresolved claims must not become confirmed bugs.
```

For triggered `balanced` or `deep` verification, use a fresh independent session where available, sequentially if needed. In `economy`, or when independent sessions are unavailable, make a distinct skeptical pass and label the lack of independence. Omit an empty `balanced` verification session only when its skip conditions in SKILL.md are met.

## Evidence and prioritization

Prefer tests through real public flows with actual relevant repositories/renderers/state handlers; mock only unavoidable external boundaries. Validate any fixture itself before interpreting a failing assertion. In-memory data stores do not establish relational translation, constraints or query performance. Static reasoning can confirm a defect if the failure path is decisive; label unexecuted reproductions accurately.

Passing existing tests supports their covered scenarios, not the entire change. An absent test is not automatically a defect. Migration execution managed manually is a deployment prerequisite unless changed code demonstrably breaks it. Confirm business assumptions; the user's clarified business rules govern the verdict.

Before consolidating, preserve the independent findings. Then inspect existing reviews if requested or relevant. Reproduce their claims rather than inheriting severity or approval. Deduplicate by cause, withdraw disproved earlier findings explicitly, and identify what remains unresolved without implying it is proven.
