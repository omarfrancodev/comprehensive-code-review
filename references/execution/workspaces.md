# Workspace lifecycle

Before builds, tests, dependency installation, reproductions or any writing command, create and verify an owned Git worktree for its actual executor. Discover the project's established worktree location once; prefer it, normally <project>/.worktrees/code-review-<run>/<executor>/. The helper uses the selected checkout's .worktrees directory; for another established project location use native Git/tool operations with equivalent ownership/cleanup guards. A native tool is preferred only when it honors that location and policy. Never reuse user development or another run's worktrees by name.

Verify actual worktree registration/root, common repository, exact HEAD and selected local snapshot before execution. Static immutable Git reads need no worktree; read-only workers may share pinned inputs. If creation is blocked, use the harness approval route within existing authorization. If still unavailable, mark required execution blocked and continue useful static inspection. Never silently replace the worktree with git archive, a directory copy or provider scratch. An explicit user-authorized alternative needs recorded authorization, exact content identity and limitations.

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

`prepare` returns one JSON object with absolute manifest/workspace paths and the pinned SHA. Keep that output in the coordinator's durable closure under artifacts.md. The session directory contains an ownership marker, manifest, captured patches and role worktrees. Logs/fixtures may live inside the owned session or worktrees. Retained reports/evidence belong in the common persistent archive outside this session. A user development worktree is not disposable merely because it lives under .worktrees.

For local modes, use current HEAD; `--ref` selecting another commit is rejected to prevent applying local edits to the wrong baseline. `commit` is the default; no local edits are imported in that mode. New files are opt-in for working/unstaged modes. Submodule patch scopes and symlink patches are rejected; arrange a reviewed alternative with accurate coverage disclosure. Git LFS content is not automatically hydrated. A clean index/worktree check can never stand in for in-scope content freshness.

The helper does not alter `.gitignore`, local excludes or global Git configuration. An unignored `.worktrees` root may appear transiently in status; its owned children are removed afterward. Existing root contents are preserved. Only explicitly trusted repository paths are passed to Git's per-process safe-directory setting. It never creates review commits or branches and never checks out the main repository.

## Execution and closure

Shared dependencies/caches and junctions are permitted when compatible and their inspected operations preserve user resources. They do not substitute for code isolation. Prefer owned outputs/temp directories and avoid concurrent writers to shared state. If a check exposes incompatible dependencies, cache/permission problems, locks or cross-executor writes, stop using that shared setup: give the affected executor its own dependencies/cache/output paths, then retry only with the changed environment recorded. Preserve the first environment failure; do not infer a product defect or a pass from it. Never remove a shared dependency target during cleanup; unlink only a verified run-owned junction if necessary before ownership-checked cleanup. No blanket link prohibition applies to dependency reuse; the helper's session/evidence path and cleanup guards still apply.

Record context.executors using existing neutral context: executor (unique ID), method (git-worktree/native-worktree; authorized-copy only with explicit authorization), workspace (absolute root), revision (actual HEAD), snapshot (pinned local snapshot or null for immutable input), manifest (owned manifest path or null for a native operation), dependencies (shared/local/none), dependency_reason (compatibility or recovery basis). Baseline checks use actual base HEAD and null snapshot; never attribute selected local edits to the unchanged base. An authorized copy additionally records authorization. Use a new executor ID when the environment/workspace changes; don't rewrite retained provenance. checks.json links each command/result to its executor and actual inputs. Recheck local captured content before verdict; a matching HEAD alone does not prove an uncommitted snapshot. Retain this subset in cierre.json (helper --context-input), not a new audit agent/file. Git-root/HEAD helper checks validate provenance structure, not executed results or fixture correctness.

Within an owned session, store shared facts only in `evidence/context.json` and neutral checks in `evidence/checks.json`. The coordinator owns those records. Store role packets as `evidence/discovery-<role>.json` and bounded verification as `evidence/verification.json`; workers must not read other discovery packets before collection. Logs may use `evidence/<role>/`. This layout fits the helper's existing allowed session children; placing new records at the session root causes cleanup refusal. Use separate session/role paths for independent executors and refresh only affected facts when the version changes.

Before cleanup, retain and verify the canonical final record, rendered report, executor context and selected necessary evidence under artifacts.md. Initial durable closure records exact temporary paths/manifest locations; finalize it from observed cleanup after removal. When files/sharing are unavailable, embed the relevant record subset and disclose persistence limits. Do not persist credentials or unrelated private data.

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

Follow artifacts.md before the first artifact write. Workspace creation/manifest and owned evidence/scope.json may bootstrap durable preparation; register that session before review discovery/validation. Later sessions need durable `register` before use. Keep descriptions, captures and hashes in session evidence/, and pass the durable retention gate before cleanup; a parallel unregistered scratch folder is not a valid evidence location.

Local snapshots reject unresolved merges, intent-to-add entries, assume-unchanged/skip-worktree flags, and changes to symlinks/submodules. The script does not change those flags or the main index to make capture succeed. Select a supported scope or use an explicitly verified alternative. Actual tracked contents/types are fingerprinted independently of Git diff visibility. Structural Git environment overrides are removed per invocation so another index/worktree cannot be targeted accidentally.
