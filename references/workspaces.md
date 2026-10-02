# Workspace lifecycle

Prefer a native workspace tool if it respects the requested location, ownership and cleanup policy. Otherwise use Git worktrees through the helper. Every workspace that builds or writes is isolated per reviewer. Never reuse another run's worktree based on its name.

Create workspaces for actual executors selected by the profile and validation assignments. The multi-role examples below illustrate supported arguments; they do not prescribe three discovery workspaces for every review. Read-only workers may share a pinned workspace. Keep shared context and validation evidence accessible without exposing other discovery findings before consolidation.

## Helper examples

Use an absolute interpreter/script path when the current directory is the project. The helper requires Python 3.10+ and Git; no Python packages.

```text
python /absolute/skill/scripts/review_workspace.py prepare --repo /absolute/project --ref exact-head-sha --role functional --role data --role integration
python /absolute/skill/scripts/review_workspace.py prepare --repo /absolute/project --mode working --include-untracked src/new-file.ts --role functional --role data
python /absolute/skill/scripts/review_workspace.py inspect --manifest /absolute/project/.worktrees/code-review-SESSION/manifest.json
python /absolute/skill/scripts/review_workspace.py record-artifact --manifest /absolute/project/.worktrees/code-review-SESSION/manifest.json --path /absolute/owned/worktree/tests/temporary-reproduction.py
python /absolute/skill/scripts/review_workspace.py cleanup --manifest /absolute/project/.worktrees/code-review-SESSION/manifest.json
```

`prepare` returns one JSON object with absolute manifest/workspace paths and the pinned SHA. Keep that output in the coordinator's review record. The session directory contains an ownership marker, manifest, captured patches and role worktrees. Logs/fixtures may live inside the owned session or worktrees. Reports that must survive cleanup belong outside it, in a user-authorized output location or the conversation.

For local modes, use current HEAD; `--ref` selecting another commit is rejected to prevent applying local edits to the wrong baseline. `commit` is the default; no local edits are imported in that mode. New files are opt-in for working/unstaged modes. Submodule patch scopes and symlink patches are rejected; arrange a reviewed alternative with accurate coverage disclosure. Git LFS content is not automatically hydrated. A clean index/worktree check can never stand in for in-scope content freshness.

The helper does not alter `.gitignore`, local excludes or global Git configuration. An unignored `.worktrees` root may appear transiently in status; its owned children are removed afterward. Existing root contents are preserved. Only explicitly trusted repository paths are passed to Git's per-process safe-directory setting. It never creates review commits or branches and never checks out the main repository.

## Execution and closure

Within an owned session, store shared facts only in `evidence/context.json` and neutral checks in `evidence/checks.json`. The coordinator owns those records. Store role packets as `evidence/discovery-<role>.json` and bounded verification as `evidence/verification.json`; workers must not read other discovery packets before collection. Logs may use `evidence/<role>/`. This layout fits the helper's existing allowed session children; placing new records at the session root causes cleanup refusal. Use separate session/role paths for independent executors and refresh only affected facts when the version changes.

Before cleanup, preserve the canonical final record and rendered report outside the session or in the conversation. When files/sharing are unavailable, embed the relevant record subset rather than create unsupported artifacts. Do not persist credentials or unrelated private data.

1. Record session output, exact scope and main-checkout baseline.
2. Dispatch only the assigned workspace to each writing reviewer.
3. Store meaningful evidence; do not export credentials or confidential unrelated files.
4. Stop owned workers and wait for file handles/processes before removing workspaces.
5. Preserve findings, version, commands/results and limitations in the final review record.
6. Record each newly created non-ignored reproduction file with `record-artifact` after its final write; record only files created by the review. Run cleanup from outside the session. The helper verifies ownership, paths, registration, unchanged workspace HEAD and tracked snapshot, and initial/registered untracked file hashes, then removes owned worktrees with Git. Unrecorded or subsequently changed source files cause refusal. Ignored build outputs inside those verified worktrees are intentionally discarded.
7. Verify returned `all_registered_removed`, absent session directory, and list of remaining Git worktrees. Inspect main checkout for drift, without undoing user edits.

Use a `try/finally` lifecycle in an available orchestration tool. A hard process kill or machine shutdown can interrupt any cleanup mechanism: retain the initial manifest path in the task record and run ownership-checked cleanup when resuming. The script does not install background jobs or persist an automation.

If ownership is uncertain, a path traverses a link, the workspace HEAD changed, or an unexpected resource exists in the session root, cleanup refuses rather than deleting it. Investigate and report the exact residual path. Do not run recursive deletion, `git clean`, global `worktree prune`, or reset as a workaround. Lost/corrupt manifests require manual ownership verification, not guessed deletion.

Do not edit existing tracked product files even for reproductions; use new temporary fixtures. Never register a user-created file as disposable. These temporary workspaces are dedicated to the review, not shared editing spaces. If the user edits them, stop and preserve their contributions before cleanup. The helper detects tracked and non-ignored file drift; it cannot distinguish a user-created ignored file from an ignored build output, or a replaced fixture with identical bytes. Its ownership record is an operational guard, not protection against a malicious actor editing the manifest and marker together. Git hooks are disabled for helper operations; project build/test commands still need their own effect inspection.

The manifest and inspect output permit explicit rerun/recovery; they are not a database lock. Do not run two prepare/cleanup operations on the same session concurrently. The helper checks capture drift, but cannot prevent a user edit immediately after its final check: recheck local state before the verdict using the captured patch hashes and included-file hashes.

Local snapshots reject unresolved merges, intent-to-add entries, assume-unchanged/skip-worktree flags, and changes to symlinks/submodules. The script does not change those flags or the main index to make capture succeed. Select a supported scope or use an explicitly verified alternative. Actual tracked contents/types are fingerprinted independently of Git diff visibility. Structural Git environment overrides are removed per invocation so another index/worktree cannot be targeted accidentally.
