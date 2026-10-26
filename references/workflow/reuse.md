# Effective-change admission before reuse

For an ordinary MR/PR review request, pin the current repository, logical MR/PR selector, source commit, target commit and unique effective diff base. Compare the entire current MR diff, not only the commits since the previous review. A changed target may change the effective diff even when source HEAD is identical.

Three identities remain separate: exact scope/inputs for recovery; effective changes for code comparison; and consumed context/materials for applicability. Never relax `compare_inputs`, resume/recover, source-selection, receipts or dispatch-identity gates to make a review reusable. An old result and its checks retain their original revisions.

## Bootstrap once

Use the existing owned evidence session; capture immutable objects without running product code. Do not create multiple executors or new reviewers merely to compare revisions. Follow workspaces.md for any actual writing executor. If this harness cannot capture comparable evidence within its permissions, record that limitation and start a new ordinary review through the supported path; missing reuse metadata is never proof of equality.

1. Select external material sources and a provisional reference index. Establish stable semantic keys (MR description, requirement URI, note ID), observed absence and completeness. A guessed empty material set is unknown.
2. Run `setup materials` against that index; run `setup changes` against the pinned full scope and target HEAD. Their existing `{session,arguments}` envelopes produce `evidence/reuse-materials.json` and `evidence/effective-changes.json`.
3. Add both generated files with `purpose=other` to the final reference index, then use `setup inputs` to capture that final index and source hashes before preparing/discovering. Do not modify it after starting work.
4. Assess the latest verified complete native result using the current files:

```text
python /absolute/skill/scripts artifacts assess-reuse \
  --repo /absolute/project \
  --scope-file /owned/session/evidence/scope.json \
  --current-inputs /owned/session/evidence/current-inputs.json \
  --effective-changes /owned/session/evidence/effective-changes.json \
  --current-materials /owned/session/evidence/reuse-materials.json \
  --session /owned/session/manifest.json
```

The helper reads only the selected repository/logical group, fully scans up to 10,000 candidates, checks hashes and rechecks the chosen result. It uses metadata timestamps only after canonical verification and rejects ties/incomplete scans. It never silently searches for an older result whose diff happens to match. It does not fetch, dispatch, publish or mutate an archive.

## Follow the action

| Action | Coordinator behavior |
|---|---|
| `offer_choice` | Effective changes and necessary inputs are equivalent: offer **start a new review** / **consult the latest verified result** |
| `new_review` | Automatically start the authorized new CCR with the current scope. No confirmation merely because an earlier run exists. Explain whether code, context, materials or missing evidence caused the new review |
| `blocked_current_scope` | Acquire the missing current scope; never claim a review of an unknown range |

A partial complement cannot stand in for an ordinary complete MR review. Inadequate or stale prior coverage also requires a new review. Supplemental observed description/requirements/plan/configuration identities remain material, including opaque labels: changed labels require review, and omitted known identities remain unknown.

Ordinary reuse requires all five applicable coverage rows to be covered or explicitly not applicable, with no material area gaps or material limitations, independently of the verdict. Confirmed findings (including blockers) and nonmaterial reservations do not by themselves disqualify an otherwise complete result. A rereview matrix describes its follow-up scope, even when all five rows are covered. It proves ordinary coverage only through an explicit native previous_run chain bound to verified previous_reviews identities, reaching a complete ordinary review in the same repository/logical scope. Every ancestor used as proof must have sufficient coverage and equivalent effective changes, complete applicable context/materials and any explicitly requested profile against the current request. Recheck the ancestor's full consumed-file inventory, including files outside the latest follow-up. Revalidate retained proof manifests/hashes after canonical latest selection. Follow at most 32 parents; absent, mismatched, cyclic, corrupt, changed or deeper evidence requires a new review. This proof does not replace the selected latest result with an older one. Historical consultation remains available.

An empty commit, no-change merge or equivalent rebase can reuse a result. New edits, removed edits, file/mode/binary/gitlink changes or target changes that alter the patch require review. So do changed requirements, relevant notes, requested profiles or consumed files even when the hunks remain equivalent. Description-only impact can be a new bounded review, with explicit reasons for reusing unaffected evidence.

Reacquire source/target references from the provider before acting on a delayed choice or publishing. The helper validates the supplied immutable objects; it cannot establish remote freshness without the coordinator's observation. A later scope invalidates the earlier admission decision.

Explicit **new review** bypasses the offer. Explicit **show latest** remains historical consultation and never starts a review unexpectedly. Display changed/unknown results with their original scope and applicability warning. For local/non-MR scopes, preserve exact-input comparison; unknown inputs require a new bounded review.

## Retain evidence without rewriting history

The change descriptor uses algorithm `ccr-effective-diff-v1`: ordered raw Git paths, modes and content/hunks; whitespace, newline and binary content remain significant. Transport headers, hunk coordinates and commit OIDs do not by themselves define equivalence. `patch-id`, changed-file lists, HEAD, mtime and successful test counts alone are insufficient.

Capture obtains text modifications from exact blob pairs and whole-file additions/deletions from their single blob, preserving normalized hunks without recursive pathspec matches. Both tree and blob diff queries delimit revision arguments with --, so local filenames equal to an object ID cannot alter capture. Git queries disable lazy fetch and deny transports; missing promisor objects yield incomplete/unknown capture and require explicit acquisition by the coordinator. The caller's `GIT_DIFF_OPTS` cannot change retained context. These settings apply to helper subprocesses, not the coordinator's explicit fetch.

During discovery, each owner returns the compact inventory of complete Git files actually consumed (base/head, byte path, mode and content digest). Consolidate that inventory and the initial material map using `setup reuse-context` into `evidence/review-context.json`. The builder checks the original owning run/inputs and pinned Git objects; it cannot introduce external requirements after discovery. Select and hash this derived evidence at retention. No extra review.json/trace schema or command-per-line trace is needed.

Initial sidecars are in `review_inputs.sources`; final review-context is derived evidence, not a late input. Unknown completeness stays false. Sources retain the 64-file/64 MiB selection bounds; the diff also has 10,000-entry, 32 MiB patch and 64 MiB serialized limits. Read failures/limits never certify a partial capture as complete.

The 64-file count applies to the same indexed selection used by producers, including the reference index; derived review-context is outside that count. Its bytes still count in the reader's aggregate 64 MiB budget. The indexed limit is enforced by the shared reference selector, including alias targets.

Old archives remain immutable/readable. Reconstruct only an evidenced exact base/head range and complete materials; never assume an arbitrary `delta.diff` is the full MR patch. Without a complete consumed-file inventory, matching whole base/head trees plus verified materials may establish equivalence. Otherwise start a new review. Unsupported layouts remain historical consultation; corrupt/ambiguous runs do not become operational previous-run links. Pending resource transactions are preserved, not adopted or cleaned automatically.
