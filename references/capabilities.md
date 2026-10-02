# Capability routing

Inventory actual capabilities before choosing the mode. A skill supplies instructions and helper code; it cannot override permissions, grant network access, install tools silently, or guarantee activation by another skill.

| Available | Route |
|---|---|
| Native agents + filesystem/terminal | Delegate only the sessions required by the selected profile; pinned owned workspaces and safe validation; native tools preferred |
| Native agents but few slots | Queue the profile's required independent sessions; don't replace independence with shared-history prompts |
| Terminal + installed documented external agent CLI | Configured `review_runner.py` for the profile's delegated roles, fresh sessions in isolated workspaces |
| Terminal but no usable independent-agent mechanism | Single-agent perspective passes; explicitly disclose lack of independent review |
| Remote connector absent | Available authenticated CLI/API, otherwise user-supplied refs or exported review inputs |
| Git worktree unavailable | Owned copy/archive of exact scope, excluding secrets; document absence of Git/relational/full history coverage |
| No terminal/write access | Inspect supplied code/context, request material missing inputs and label unexecuted validation |

An absent capability triggers a supported alternative, not an invented command. Continue useful permitted work. Ask for missing information only if it materially blocks the next step; do not ask again for already authorized actions.

## Shared context record

The coordinator discovers common context once per reviewed version and supplies one compact record to all reviewers:

- Repository identity, exact scope/base/head or snapshot, profile and reason.
- Observable requirements and source references, without reviewer diagnoses.
- For MR/PR scopes, the captured description/source, text/hash identity and assigned description-check owner.
- Applicable repository instructions, relevant stack/configuration and verified conventions, with source paths; include binding instructions directly when the worker cannot access them.
- Affected entrypoints/interfaces, assigned flow/risk owners, relevant code paths and capability limitations.
- Discovered validation commands, inspected external effects, required gates and their assigned executors.

Use an accessible record reference or embed only the relevant subset in the brief when shared artifacts are unavailable. Workers use this record instead of repeating repository-wide instruction/configuration/command discovery. They inspect raw code for their own evidence and check any convention relevant to a finding; the record is an index of facts, not proof of correctness. Report missing or contradictory context to the coordinator, who updates affected fields and informs relevant workers. A changed revision invalidates affected context and validation evidence; refresh those portions before reuse.

Maintain a shared validation ledger: check ID, executor, exact command, revision/snapshot and relevant fixture/configuration, result and evidence location. Workers receive execution facts and raw results, not other reviewers' diagnoses or verdicts. A check has one assigned executor; see [reviewers.md](reviewers.md) for reuse and rerun rules.

## External CLI adapter

Read the installed CLI's help/documentation and establish noninteractive invocation, fresh context, workspace confinement and permissions. Do not guess vendor flags or reuse a persistent session. Use the helper only after a real adapter is configured. It does not provide vendor-specific integrations or install an agent.

An adapter JSON contains:

```json
{
  "argv": ["absolute-path-to-a-configured-adapter", "{prompt_file}", "{workspace}", "{output_dir}"],
  "fresh_context": true
}
```

The executable may be a user-maintained wrapper that translates these positional inputs into the installed CLI's documented flags. It must create a fresh model session, honor the brief, restrict mutations to the assigned workspace, keep remote writes disabled, wait for its worker descendants and terminate them on failure/cancellation. The boolean asserts an established contract, not proof of it. Validate the contract with a harmless disposable task before relying on it.

Invocation:

```text
python /absolute/skill/scripts/review_runner.py --config /absolute/adapter.json --prompt-file /absolute/brief.txt --workspace /absolute/owned/worktree --output-dir /absolute/session/evidence/functional --timeout 900
```

Arguments are passed as an argv list, without shell expansion. Output dirs must be new. Stdout, stderr and run metadata are captured; a successful process does not prove a valid review. Read the worker result and verify findings. Preserve relevant report evidence before cleanup. Do not put credentials in configuration, prompts or report logs. Use existing permitted authentication mechanisms.

This helper is not an OS process sandbox or a guaranteed descendant container. On timeout it attempts process-tree termination (Windows taskkill or a POSIX process group), but a daemonized/detached child or child surviving adapter exit can escape. A root exit code of zero therefore does not establish that cleanup is ready; metadata sets `workspace_cleanup_ready: false`. The coordinator must verify adapter completion and owned workers have stopped before deleting a workspace. If it cannot establish this, stop that fallback and preserve/report the owned resources. Do not run arbitrary code in a purported independent session whose ownership/lifecycle is unknown.

## Safe validation

The coordinator reads project instructions/configuration to discover test, build, lint and typecheck commands and assigns their execution in the shared ledger. Workers discover additional commands only for assignment-specific needs. Avoid autofix or generated modifications in the main checkout. Run necessary checks in owned workspaces. Inspect commands' external effects; use isolated disposable resources for database/storage/integration tests. Never run a suite against a production/shared database merely because it is the default connection. Do not apply real migrations, send emails, or mutate external business data as part of a review without corresponding authorization.

Select targeted checks for identified risks and required gates. Record actual command, workspace/revision, result, counts and evidence. Broaden only for a concrete remaining risk or required gate. If the environment blocks a required check, report the exact uncertainty and how it affects the verdict; don't claim it passed.

## Integration with existing review skills

This skill is self-contained. It can coordinate a Superpowers review when explicitly loaded alongside `requesting-code-review`, preserving the requested scope and compatible requirements. Installation alone does not redirect another skill or intercept a harness-native review button. Use an explicit invocation, personal routing instruction, or supported harness integration. Do not modify installed vendor skills to make that connection.
