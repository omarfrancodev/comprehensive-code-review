# Authorized remote publication

Load only for an explicitly authorized remote action. Review/draft does not authorize publication, description edits, approval, merge or push; these remain distinct. Honor existing authorization rather than ask again.

Before sending, verify project/MR identity, current base/head, description identity, operational responsible mapping and commit-author attribution. Refresh affected evidence only; insufficient current evidence means an exact older-scope report and material limitation. Render the public format, including separate responsible and author fields. No worker mechanics/private archive paths/measurements/comparisons unless requested.

Use verified assignment and version-bound commit metadata for their respective roles. An assignee/MR creator is not automatically a change author. Introducing-author attribution for a particular finding needs actual commit/account mapping, never guessed emails/names; the general authors slot does not prove which person introduced a defect. If unavailable, state No identificado(s) or ask only when the user requires that exact identity for publication. Never mention unverified accounts.

Publish only authorized content/action and verify returned evidence. Draft is not published. If completion is uncertain, inspect the remote result before retrying; avoid duplicates. Prior-comment updates need corresponding authorization, with stable IDs supporting consistent updates.

Record an authorized publication observation in the open run's compact trace with actual authority and returned evidence. After closure, use a separate operation linked to the review ID/source; preserve the original immutable report/record/trace. A requested handoff or review source never supplies publication authority.

## Audience selection and historical publication

Final schemas 8–10 select limitations by kind/material/public_summary under [result-contract.md](../contracts/result-contract.md). Nonmaterial execution stays private; material execution publishes relevant pending-check/gate impact. Product/validation limitations and material ABCDE gaps remain visible. Merge matching area/limitation details before audience projection, retaining the selected public summary once; an unmatched material area uses its publishable detail. A material area matching an execution limitation requires a public impact summary even if that limitation was marked nonmaterial; missing classification blocks public rendering rather than hiding the gap or exposing internal detail. Deduplicate the same uncertainty across limitations, area gaps and reservations; never downgrade materiality to hide mechanics.

Before already-authorized publication, the coordinator makes one draft pass over verdict_reason, reservations, finding text, check evidence/reuse reasons and re-review details. These describe change/evidence/acceptance conditions. Internal permissions, models/harness, workers and local paths belong in execution/trace/internal limitations. Product sessions/agents remain valid terminology; no blacklist, extra reviewer or code sweep.

### Canonical comment bytes

For schemas 1–7, `--publication-context` remains the source-bound classification for historical limitations. Check summaries use the separate `--check-publication-context` argument with exactly `{source_sha256, checks}`; its digest uses the canonical `publication_digest(record)`. Each check row has exactly `{id, evidence, reuse_reason, rerun_reason, reference}`. IDs, original revisions, status, failure kind and reused state always come from the record. Local execution references are private by construction; the context may retain only the same public HTTP(S) URL already present on the source check. A free-text reuse or rerun reason, or evidence that contains a local path/command, requires an explicit public summary before rendering. Classify a mechanical retry as nonmaterial only when it leaves the product conclusion intact; keep material pending validation visible.

Prepare the comment after the authorized review is current and the one editorial pass is complete:

```sh
python /absolute/skill/scripts comment prepare \
  --input /absolute/retained/review.json \
  --session /absolute/owned/publication-session/manifest.json \
  --output /absolute/owned/publication-session/evidence/public-comment.json \
  --check-publication-context /absolute/owned/publication-session/evidence/check-publication.json
```

The draft records the source hash, both optional classification contexts, the exact `render(comment)` body and its UTF-8 hash. Before sending, run `scripts comment verify` against the exact outbound body. Do not edit, trim, translate or normalize the draft after that check; change the structured public context and prepare a new draft instead. If a value is private, correct its source classification/context before rendering rather than patching generated text. This corrects presentation without repeating discovery or code verification while the source record remains current. A post-close publication is recorded as a separate verified event; it does not rewrite the retained result or draft.

After an authorized send, read the body returned by the remote service and verify it with `scripts comment verify --remote`; this permits CRLF-to-LF comparison only. Verification does not mean published. If the response is missing or differs, preserve the observation and inspect the existing remote comment before retrying. Record publication afterward as an observed trace event, in the open run or a separate post-close operation linked to the review.

Schemas 1–7 remain readable privately. Public historical limitations require ephemeral classification: --publication-context for render-comment, or publication_context for public renderer/handoff APIs. Schemas 8–10 already contain their classification and reject an extra override. Exact fields: {source_sha256, limitations: [{index, kind, public_summary}]}. SHA-256 binds canonical JSON: ensure_ascii=False, sorted keys, compact separators, allow_nan=False, UTF-8. One row per original index; detail/materiality stay sourced. Reject duplicate/missing indices and wrong hash. Do not save classification by default, rewrite history or guess kind from wording. Unclassified limits leave publication pending privately. Historical records without limitations need no classification.
