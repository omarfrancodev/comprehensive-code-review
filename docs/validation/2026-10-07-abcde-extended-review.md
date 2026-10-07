# Explicit ABCDE assignments and extended profile validation

Base: main 78aae326e34ee4b9739dd7e9fa3ae17143b9a6fe, released as v2.5.0 after user approval of PR #6. Target: 2.6.0 Unreleased, pending review of this separate feature PR.

## Isolation and approved decisions

Implementation lives in .worktrees/abcde-review-assignments, branch feat/abcde-review-assignments, created from updated main after checking its clean state and inherited .worktrees exclusion. Main retains the released skill. Git identity remains omarfrancodev <fofe2803@gmail.com>.

The user selected automatic extended when additional independent reviewers are justified. Briefs explicitly declare ABCDE aspects, flows/files/interfaces, questions/invariants and expected evidence/coverage. Group shared flows; do not impose an agent per area. Deep retains two discovery reviewers and a justified optional third. Automatic extended requires a deep mechanism and four/five necessary independent assignments that cannot fit a three-reviewer plan. Explicit extended uses two to five as needed. One grouped fresh verifier handles candidates/invariants; concurrency may require waves. Preserve valid existing discovery/checks/context when escalating. Verified project gates remain separately named/countable even with an explicit profile; optional extra discovery cannot masquerade as a gate.

The final record uses schema 5 for the new extended enum, retaining schema 4's fields and rendering. Schemas 1–4 retain their accepted inputs/profile enums. Compact packets remain version 1; durable archive manifests remain schema 3. No new assignment packet fields, area reports, measurement collection or selection agent were introduced.

## Behavioral RED/GREEN

A fresh baseline worker read the released 2.5.0 instructions and planned five scenarios before any instruction edits. Its five-perspective required-gate case exposed the unresolved tension between the deep two/three-reviewer plan and the required independent perspectives. It did not invent an extended profile or claim three reviewers satisfied the gate. Grouped multitenant and compatible-rename scenarios already avoided five agents per area; those behaviors were preserved.

A fresh forward worker read only the proposed instructions before inspecting the diff and planned eight scenarios. It selected automatic extended for five required independent perspectives, preserved grouped coverage for one shared tenant flow, selected economy for a demonstrated compatible rename, respected explicit deep while separately accounting for verified gate sessions, reused valid work during escalation, used only two reviewers for explicit extended without extra needs, retained deep when two/three assignments suffice and disclosed inadequate independence when delegation is unavailable. It then reviewed the changed helper/tests/references and ran seven additional in-memory contract probes.

The reviewer identified a malformed profile regression during inspection: list/dict values raised TypeError in a newly added set-membership condition. A targeted test reproduced both failures; tuple membership fixed the problem. The reviewer rechecked schemas 1/5 and found no remaining defect in the corrected state. These planning probes are not reviews of real MRs or a measured cost/accuracy benchmark.

## Mechanical RED/GREEN and final verification

- Baseline suite: 150 tests in 101.116 seconds, 149 passed and one Windows symlink privilege skip.
- Eight new tests first failed on unsupported schema/profile, inherited fields and invariant gates. After implementation, the archive fixture was corrected to use the local scope's not-applicable MR description, then all eight passed. The malformed-profile regression was added afterward and observed failing before its correction.
- Nine targeted tests pass in 1.644 seconds: schema/profile compatibility, required fields, invariant verification, material-gap verdict, rendering/CLI, malformed input and actual prepare/retain/validate/close with schema5 review and schema3 archive, without automatic measurements.
- Final suite after the correction: 159 tests in 133.384 seconds, 158 passed and one Windows symlink privilege skip. Actual Windows junction coverage passed.
- Six helper sources compile; direct frontmatter/version checks, local Markdown links, conflict-marker checks, four-column profile table, consistent changelog headings and git diff --check pass. skill-creator quick_validate remains unavailable because the bundled interpreter lacks PyYAML; no dependency was added.

Structural validation does not prove reviewer independence, assignment necessity, coverage truth or finding correctness. Those remain coordinator decisions based on pinned sources and returned evidence.

## Changelog publication dates

Queried the GitHub release catalog after publishing v2.5.0. Dates use America/Mexico_City, verified with the host timezone conversion:

- [v2.2.0](https://github.com/omarfrancodev/comprehensive-code-review/releases/tag/v2.2.0): published_at 2026-10-06T00:57:59Z, local date 2026-10-05.
- [v2.1.1](https://github.com/omarfrancodev/comprehensive-code-review/releases/tag/v2.1.1): published_at 2026-10-04T03:59:30Z, local date 2026-10-03.
- No GitHub releases were registered for 2.1.0, 2.0.0 or 1.1.1; the user chose the explicit Sin publicación registrada label instead of invented dates.

The proposed 2.6.0 remains Unreleased and the README download still points to published 2.5.0. Merge/tag/release for this feature await human PR validation.
