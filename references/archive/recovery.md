# Lookup, reuse and recovery

Load this reference only when a request may match an earlier review, when an archive is incomplete, or when a user asks to resume/recover a review. Lookup is read-only and local. It does not fetch remote data, dispatch agents, publish, modify, repair or clean resources.

## Before preparing another run

Pin the repository and the exact requested scope first. When the same MR/PR or stable local target may already have a run, call the bounded lookup before creating a new archive. For unrelated new scopes, skip lookup. Each project is queried separately; never scan the global archive or another repository to infer a match.

```text
python /absolute/skill/scripts/review_artifacts.py lookup \
  --repo /absolute/project \
  --scope-file /absolute/owned/session/scope.json \
  --current-inputs /absolute/owned/session/current-inputs.json \
  --limit 20
```

`--current-inputs` is optional. Supplying it permits comparison; omitting it makes freshness unknown. Its `scope` must exactly equal the lookup scope. `sources` maps at most 64 retained source references to SHA-256. `source_set_complete` must be `true` to treat source equality as established. Optional identities are compared when both the archived run and current inputs preserve them:

```json
{
  "scope": {
    "repository": "group/project",
    "mode": "mr",
    "base": "<base-sha>",
    "head": "<head-sha>",
    "snapshot": null,
    "target": "develop",
    "reference": "https://git.example/group/project/-/merge_requests/42"
  },
  "sources": {
    "evidence/requirements.md": "<64-lowercase-hex-sha256>"
  },
  "source_set_complete": true,
  "description_identity": "<captured-description-identity>",
  "requirements_identity": "<captured-requirements-identity>",
  "plan_identity": "<captured-plan-identity>",
  "configuration_identity": "<captured-configuration-identity>",
  "profile": "standard"
}
```

Use only identities actually observed and retained. An omitted/unrecoverable identity stays unknown. The matcher compares all pinned scope fields, available source hashes, archived final description identity and archive-7 profile history. It does not infer hashes for unretained files or use finding IDs as a shortcut. Description/requirements/plan/configuration identities absent from a historical archive cannot be reconstructed from prose; report them as unknown. Current profile is shown when supplied, and is compared when its prior value is available.

The query opens only this repository's archive group and scope folders sharing the stable reference/target/snapshot. A merge request reference allows a changed base/head to appear as a candidate so the difference can be reported. Without a stable anchor, the query uses the exact scope group. Each page has 1–100 rows (default 20). `truncated: true` means more candidates exist; continue with the returned opaque cursor. A cursor is bound to the repository and exact scope; do not edit or reuse it for another request. The result never selects a candidate. Ordering is for pagination only and does not imply the newest run is correct.

Candidate `integrity` is `manifest_verified`, `report_verified`, or `invalid`. `report_verified` checks only the bounded retained final JSON/report bytes against the hashes in the owned closure; it does not replace full run inspection. A file over the lookup read limit, modified report, invalid final record, missing file, or untrusted closure cannot be offered as current. Select the exact `run_dir`/`CR-...` and inspect it before showing or continuing.

## Choose an explicit outcome

| Candidate | Safe next step |
|---|---|
| Complete, report verified, `applicable` | Show the exact archived report or create a new linked review. Use the caller's explicit request if it resolves that choice; otherwise ask. |
| Complete, `changed` or `unknown` | Label it historical, explain the differences/unknowns, and offer a new linked review. Do not present it as current. |
| Incomplete, manifest verified | Inspect the exact run and its phase/transactions, then decide whether to continue, recover, or restart. Do not infer that `processing` means a process is alive. |
| Invalid ownership/report/source | Preserve the run and any resources. Do not adopt, rewrite, show as verified, or clean it. Offer a fresh linked review if appropriate. |
| Several candidates or more pages | Ask which run the user means unless their request already identifies one. Never choose by timestamp or finding ID. |

Showing a report is read-only: inspect the selected run, verify it, and display its retained `informe.md`/record. It does not create a run, dispatch reviewers, resume checks, publish, export a delivery or clean workspaces. State the reviewed version and whether freshness is known.

## Inspect and recover an incomplete run

Use the exact returned path. Inspection has no write side effects:

```text
python /absolute/skill/scripts/review_artifacts.py inspect \
  --run-dir /absolute/archive/repository/scope/date-run-id \
  --current-inputs /absolute/owned/session/current-inputs.json
```

`inspect` reports integrity, phase, disposition, retained/missing sources, owned resources, pending helper transaction, freshness and allowed actions. It does not infer worker liveness or fix errors. If there are pending helper-owned bytes, `recover` can complete only the recorded hash-bound transaction; otherwise it returns a bounded plan or provisional result and does not run commands, checks or agents.

Mutation commands require structured controller/authority/current-input files and an explicit user direction when the operation needs continuation authority:

```text
python /absolute/skill/scripts/review_artifacts.py pause --help
python /absolute/skill/scripts/review_artifacts.py block --help
python /absolute/skill/scripts/review_artifacts.py resume --help
python /absolute/skill/scripts/review_artifacts.py recover --help
python /absolute/skill/scripts/review_artifacts.py restart --help
```

`pause` records an explicit user-directed stop; `block` records a failure actually observed by the harness. `resume` is limited to an intact archive-7 run whose exact scope and source hashes still match, and requires authority to continue a paused/blocked run or take over a different controller. It preserves old worker/executor events; it does not call them new independent work. `recover` consumes only an exact recorded helper transaction and never dispatches.

`restart` creates a fresh run ID linked to the selected source and can use a changed scope within the same repository. It does not copy findings, checks or execution results into the new run as current work. It transfers workspaces only when each exact owned path is explicitly selected and authority is recorded; otherwise preserve those resources for their owner.

### Recover or restart without duplicating a run

Treat recovery and freshness as separate decisions. `recover` may finish only the helper's exact hash-bound checkpoint/cleanup/transfer/restart transaction. It does not establish that the reviewed inputs are still current. If appraisal is `changed` or `unknown`, use the returned actions and start a linked run for the current scope; never mark the old bytes as current by updating only the head or description. A missing session without a cleanup receipt remains `missing_unknown`; preserve its source claim and do not report successful cleanup.

If a restart intent is pending, retry the exact captured request or call `recover` with the same current inputs, authority and controller. The helper reuses its reserved successor. A different pending operation, a foreign occupied destination, or altered request is a conflict; inspect and preserve both runs instead of choosing a new path. While the intent is active, unrelated mutations, transfers and cleanup against that source are refused. Once the successor is complete, continue work only from its returned `run_dir`.

`recover` and `resume` record a durable takeover event when the coordinating controller changes; the authority must come from an explicit user direction. Passing the same controller does not create a takeover event. A completed source is immutable, including its controller, trace and report. The successor records the controller for the new work.

Restart resolves the harness from the current invocation. It never copies the source run's `harness_id` as if that ID had been declared for the new session. Without a current identity declaration or environment value, use `--harness unknown` and let the helper retain an unknown canonical ID. When a current canonical ID and its provenance are observed, provide them explicitly:

```text
python /absolute/skill/scripts/review_artifacts.py restart \\
  --run-dir /absolute/archive/exact-source-run \\
  --profile-input /absolute/owned/session/profile-selection.json \\
  --controller-input /absolute/owned/session/controller.json \\
  --authority-input /absolute/owned/session/authority.json \\
  --current-inputs /absolute/owned/session/current-inputs.json \\
  --harness "Claude Code Desktop" \\
  --harness-id claude-code-desktop \\
  --harness-source-input /absolute/owned/session/harness-source.json
```

`harness-source.json` is an existing JSON object such as `{ "kind": "user", "reference": "--harness-id" }`; use `kind: platform` only for a source the harness actually exposes. The raw `harness` string stays as observed. An unknown or contradictory ID is retained as a diagnostic, not guessed from the model name. `--transfer-path` may be repeated for the exact active claims being transferred; transfers require the current source owner and all present claims. Never pass a missing path to imply cleanup.

Before closing any run, retain and validate the final result/evidence, then observe cleanup and require `validate --require-complete`. If a gate fails, preserve the exact run and registered resources and report the unfinished phase. Completed archives remain immutable. A post-close publication or delivery is a separate operation and cannot rewrite the original review.
