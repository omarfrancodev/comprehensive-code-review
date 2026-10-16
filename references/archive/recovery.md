# Lookup, reuse and recovery

Load this reference only when a request may match an earlier review, when an archive is incomplete, or when a user asks to resume/recover a review. Lookup is read-only and local. It does not fetch remote data, dispatch agents, publish, modify, repair or clean resources.

## Before preparing another run

Registration, transfer and workspace cleanup coordinate by canonical session identity as well as by run. Session lock files persist in the repository's Git common directory under `ccr-session-locks`; they are outside the disposable session and do not alter checkout status. A conflict fails without waiting: preserve the resources and retry the authorized operation after the holder finishes. Do not delete coordination files to bypass a conflict. Locks release on exception or process exit; lock files remain to keep a single coordination inode. Linked/reparse or multiply linked final lock files are refused before any coordination write.

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

If a restart intent is pending, retry the exact captured request or call `recover` on its source with the same normalized captured inputs. The effective profile is fixed by the intent; recovery preserves the authority/controller of that recorded request. Exact equality permits transactional replay even when historical description/requirements/plan/configuration identities were not captured. The returned `input_appraisal` can remain `unknown`: completing the restart does not certify freshness or authorize a different request. A changed normalized input returns `restart_pending`, `replay_inputs_match: false` and the exact-retry action without dispatching work. The helper reuses its reserved successor. A different pending operation, a foreign occupied destination, or altered request is a conflict; preserve both runs instead of choosing a new path. While the intent is active, unrelated mutations, transfers and cleanup against that source are refused. Once it completes, continue work only from its returned successor `run_dir`.

During that transaction, when the owning source can be verified and has no known resource-exit plan, lookup/inspect/recover of the successor return `recover_source` with the exact owning `run_dir` and `operation_id`. Run recovery against that source; the successor does not invoke an independently forbidden transfer. If the source already has an abandonment or independent-review plan, the successor exposes that same action and recovery detail directly, with the exact source identity, rather than adding a recover_source hop. Errors for an incoming restart-owned transfer identify the same source/operation. A separate outgoing transfer identifies its actual source rather than a historical restart ancestor.

This historical lookup is optional: an absent, unreadable or unverifiable source archive does not invalidate an otherwise intact successor. Inspect/lookup/recover assess the successor's own bytes and pending transactions; they do not claim that the missing source was verified. A contradiction between the successor and an accessible, verified active source operation remains an error.

An incoming transfer still pending on that successor requires its exact source to finish. If that source cannot be verified, inspect/lookup/recover expose a preservation plan with recovery.status `source_unavailable`, can_complete false, and an explicitly authorized independent-review alternative using fresh resources. Local transfer gates continue to reject completion; the successor is never certified verified/ready by ignoring that dependency. Preserve its recorded transaction and resources. Contradictory source identity or corruption of the local run remains an error, not an alternative-work authorization.

For compatibility, integrity.status `recoverable` means a preserved helper-owned transaction is pending, not that recover can finish it now. The optional recovery object states known feasibility: `cancellation_available`, `independent_review_required`, or `source_unavailable`; can_complete false means no automatic completion is claimed. cancellation_supported is separate from completion. blocked_by distinguishes present/releasing source claims (`source_claims_present`), a durable transfer (`transfer_in_progress`), successor claims/work (`successor_claims_or_work`) and an unavailable source. Missing/foreign resource lists describe why the original continuation is blocked; no cancellation blocker is reported when cancellation is available. Omission of this diagnostic detail is not a guarantee of success: the mutator still verifies all gates.

`recover` and `resume` record a durable takeover event when the coordinating controller changes; the authority must come from an explicit user direction. Passing the same controller does not create a takeover event. A completed source is immutable, including its controller, trace and report. The successor records the controller for the new work.

Restart resolves the harness from the current invocation. It never copies the source run's `harness_id` as if that ID had been declared for the new session. Without a current identity declaration or environment value, use `--harness unknown` and let the helper retain an unknown canonical ID. When a current canonical ID and its provenance are observed, provide them explicitly:

```text
python /absolute/skill/scripts/review_artifacts.py restart \
  --run-dir /absolute/archive/exact-source-run \
  --profile-input /absolute/owned/session/profile-selection.json \
  --controller-input /absolute/owned/session/controller.json \
  --authority-input /absolute/owned/session/authority.json \
  --current-inputs /absolute/owned/session/current-inputs.json \
  --harness "Claude Code Desktop" \
  --harness-id claude-code-desktop \
  --harness-source-input /absolute/owned/session/harness-source.json
```

`harness-source.json` is an existing JSON object such as `{ "kind": "user", "reference": "--harness-id" }`; use `kind: platform` only for a source the harness actually exposes. The raw `harness` string stays as observed. An unknown or contradictory ID is retained as a diagnostic, not guessed from the model name. `--transfer-path` may be repeated for the exact active claims being transferred; transfers require the current source owner and all present claims. Never pass a missing path to imply cleanup.

Before closing any run, retain and validate the final result/evidence, then observe cleanup and require `validate --require-complete`. If a gate fails, preserve the exact run and registered resources and report the unfinished phase. Completed archives remain immutable. A post-close publication or delivery is a separate operation and cannot rewrite the original review.

### Missing resources, superseded cleanup and explicit abandonment

A claimed session absent without a release receipt is `missing_unknown`. Inspect, recover and resume use the same classifier: they never announce continuation for that state. Start an authorized linked restart without transferring the missing path. If a changed-scope restart leaves present owned sessions in the superseded source, dispose them with `review_workspace.py cleanup --manifest <source-session>/manifest.json --run-dir <source-run>`; cleanup changes only that source claim/receipt, never the successor. Completed archives remain immutable.

A pending restart appears in `pending_transaction` with operation ID, exact intent path and reserved successor. Recover takes the source lock before any prepare/replay. The original authority/controller remain bound to the pending request.

Once that exact successor is prepared, retry/recover recognizes it before running a new resource-registration preflight. A partially moved workspace sidecar is replayed only through the recorded transfer or registration helper; it is not adopted as a new session. The successor is reread and its pending trace recovered under its own mutation lock. Hash-bound pending trace appends are recovered before integrity checks. Invalid identity or modified bytes still stop recovery.

A checkpoint interrupted before a successful restart remains provisional in its superseded source, including any missing planned bytes. `inspect` labels that checkpoint `superseded`; lookup/inspect/recover point to the recorded successor rather than offering `retry_checkpoint` or continuation on the source. Basic read-only `validate` verifies ownership, the transaction inventory and any existing bytes without committing it. This does not certify a final result: retained/complete gates and `--record-checkpoint` still reject that provisional source. Preserved source bytes are not copied into or certified by the successor.

If present claims remain with that source after a scope change, their verified cleanup and cleanup recovery remain available independently of the historical checkpoint. Neither operation commits its provisional inputs or changes the successor.

If the coordinator explicitly decides to abandon a pending restart **before** the successor has a manifest, use its exact `intent_path`. If that file is missing after the active descriptor was written, the helper reconstructs only that exact hash-bound intent under the source lock; an arbitrary missing path is refused:

```sh
python /absolute/skill/scripts/review_artifacts.py abandon-restart \
  --run-dir /absolute/archive/exact-source-run \
  --intent-input /absolute/archive/exact-intent.json \
  --controller-input /absolute/owned/session/controller.json \
  --authority-input /absolute/owned/session/authority.json \
  --reason "Collect corrected inputs before a new review"
```

This records an idempotent abandonment receipt and preserves the immutable intent and any partial allocation. It deletes no directory. A prepared successor normally must be recovered. An exception handles a selected resource that is now absent or claimed by another review, while the exact successor still has only its initial prepare/profile trace and no work, evidence, assignments, executors, checkpoints, cleanup, transfers or own claims. No active source claim may remain present or releasing. The helper checks sidecars as well as manifest rows; a sidecar already owned by the successor prevents abandonment even if its row was not committed. Unknown files or ambiguous ownership also prevent this exception.

When a selected session is held by another verified review, or a missing selected workspace with a captured claim/transfer blocks the restart, inspect/lookup of the source and recover with the exact captured inputs return `abandon_restart` only when the current read-only preflight permits it. A foreign owner is verified by identity without certifying or recovering its work evidence. The action supplies the exact `run_dir`, `operation_id` and `intent_path`, and requires explicit authority; it does not perform cancellation. Invoke `abandon-restart` with that intent and the command above. The mutator rechecks eligibility under locks. A missing source claim remains `missing_unknown`; no cleanup receipt, released status or successful cleanup is invented. Once cancellation completes, a newly authorized selection can restart without the blocked path. An unclaimed path already handled as `missing_unclaimed` does not block the existing exact replay and does not trigger this exit plan.

That exit applies only before a transfer intent or an adoption sidecar is durable, while the prepared successor is otherwise empty, and when no active source claim remains present or releasing. The reason names remaining source claims separately from a durable transfer or successor claims/work. If these conditions prevent cancellation, the resource diagnostic returns `new_independent_review`: an explicitly authorized `prepare` without `--previous-run`, using fresh resources. The source and successor expose the same plan. The original restart remains pending and must be preserved and reported as unfinished. There is no supported cancellation/rollback for this phase, and changing the existing restart request is refused. Local corruption still requires preservation rather than this alternative-work action. A recorded cancellation already in progress continues through `recover`, not a new decision. A resource-conflict error from the exact retry names inspect/recover of its source to discover the recorded plan.

**Multiple-session adoption limitation:** if a restart adopted one session's sidecar and another review then claimed a different selected session, retry/recover and abandonment are refused. There is currently no non-destructive helper rollback for that partial adoption. Preserve both archives, all sessions and their ownership records; do not delete or clean another review's workspace to unblock this restart. An explicitly authorized independent review may use a new `prepare` without `--previous-run` and fresh resources; the old restart remains pending and must be reported as such. The other owner's normal cleanup removes its session: it does not make that workspace available for adoption. A subsequent retry may complete without that resource (`missing_unclaimed`), which does not recover the intended workspace and must not be pursued as a workaround. The independent review does not cancel or resolve the original partial adoption.

Abandonment eligibility and pending-trace integrity are checked without applying trace events or reconstructing an intent file. Only an accepted cancellation writes them. Rejections preserve the domain files of source, successor and sessions; coordination lock files may be created. A valid pending helper event is replayed once as part of completing the authorized cancellation.

For that exception, abandonment retains the successor as terminal history: archive-7 stores the existing receipt in `restart_abandonment`, and `operation.disposition` is `blocked`. The receipt marker distinguishes terminal history from an ordinarily resumable blocker. All mutators refuse it, basic validation remains read-only, and lookup/inspect/recover direct to `inspect_source`. No claim or workspace belonging to the other review is modified. Ownership identity is checked independently of that review's pending work evidence; this does not certify, recover or permit cleanup of the foreign review.

The helper commits the terminal successor before the source receipt. If interrupted, `recover` on the source finishes only that already authorized cancellation, using the original receipt and without re-adopting; unknown/changed freshness cannot revive it. Inspect/recover on a successor with a still-pending source cancellation provide `recover_source` when that source can be verified. After completion they provide `inspect_source`, including when the source has another active restart. A replay of an old cancellation never retires that newer operation.

A new request after abandonment must have a new selection decision/reason/reference; replaying the abandoned request is rejected. Neither restart nor abandonment rewrites a completed/legacy source or gives it a synthetic run ID. Errors from strict mutators on a superseded source with a provisional checkpoint name its recorded successor instead of suggesting an impossible checkpoint retry.
