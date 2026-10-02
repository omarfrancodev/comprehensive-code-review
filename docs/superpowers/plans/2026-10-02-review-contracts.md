# Review contracts implementation plan

> For agentic workers: use superpowers:executing-plans inline. The user approved the nine proposals and requires a baseline Git commit before implementation.

**Goal:** Make reviews predictable and economical through canonical findings, consistent reports, conditional guidance, evidence reuse and incremental re-review.

**Architecture:** Keep essential routing in SKILL.md. Store mode-specific instructions in focused references. Use a dependency-free Python contract validator/renderer as an optional mechanical check; it cannot establish whether findings are true.

**Spec:** The user's accepted proposals in this chat, including mandatory responsible-person metadata in public comments and a formal user report.

**Constraints:** Preserve isolation, evidence, permission and cleanup protections. No remote publication or repository creation is requested. Explicit user instructions override presentation defaults. Common evidence is neutral; discovery findings remain independent until collection. Unknown identities/usage remain unknown.

## Progress

- [x] Baseline repository: commit d8b47c3, tag v1.1.1, before editing skill content; identity and .git owner corrected at the user's request with unchanged baseline tree.
- [x] Block 1 — Result contracts and report templates.
  - Write meaningful failing tests for final verdict consistency, evidence references, responsible identity, description-only locations and rendering omissions.
  - Implement scripts/review_contract.py with validate/render-user/render-comment/deduplicate commands and a versioned minimal worker/final record.
  - Add references/result-contract.md; formalize user/public outputs, including the responsible person.
- [x] Block 2 — Conditional workflow and reusable evidence.
  - Shorten SKILL.md; split external CLI and publication instructions into conditional references.
  - Specify evidence/context.json, evidence/checks.json and per-role result ownership within existing cleanup rules.
  - Define observable deep-profile triggers, provisional deduplication, bounded rejected-claim records, verdict rules and incremental re-review with stable IDs.
  - Preserve unchanged workspace-helper behavior and use its ownership guards.
- [x] Block 3 — Verification and versioning (release commit containing this plan; tag v2.0.0).
  - Add small executable review scenarios with real code artifacts and known defects/clean controls; provide an offline decision answer key and a telemetry worksheet without fabricated results.
  - Run unit/CLI/integration tests, reference/frontmatter checks and an independent bounded behavioral review.
  - Fix substantive failures; commit the completed revision and tag its version.

## Validation

Python 3.10+, unittest, JSON and subprocess only; no third-party dependency or paid API call. Tests must exercise behavior, including stale evidence and blocked/fixture checks, rather than match documentation headings. Compare workspace cleanup with the specified artifact layout using a disposable Git repository. Report planning probes separately from actual model effectiveness and cost measurements.

## Rulings

- Work in this newly initialized, dedicated checkout: the user expressly requested preserving its state then applying these changes. No unrelated checkout or branch exists to isolate.
- Use inline progress because no todo tool is exposed. This plan is the persistent execution record.
- Final release: 2.0.0, reflecting the new strict result/report contract; the external CLI remains opt-in.

## Validation results

- 38 unittest checks passed, including Unicode/error CLI behavior, original-revision reuse, balanced verification, stable aliases, public-command omission, three executable ground-truth scenarios and ownership-aware workspace cleanup refusal/recovery.
- Independent bounded review found prior-revision reuse rejection, skipped balanced verification and public raw-command exposure. Each was corrected with a regression check.
- Markdown targets, Python syntax, fixture JSON and limited frontmatter/config checks passed; the core SKILL.md body is 423 words. Official quick_validate.py requires unavailable PyYAML, so these checks are explicitly narrower than a general YAML validator.
- Existing review_workspace.py/review_runner.py implementation unchanged. Git identity/ownership and normal Git access were checked as INSCORSOF2\\Developer; baseline author/committer are omarfrancodev <fofe2803@gmail.com>.
- Actual model accuracy, provider tokens and charges were not benchmarked. The three scenarios establish executable ground truth and a future comparable-run protocol, not measured cost savings.
