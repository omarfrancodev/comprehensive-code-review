# Authorized remote publication

Load only for an explicitly authorized remote action. Review/draft does not authorize publication, description edits, approval, merge or push; these remain distinct. Honor existing authorization rather than ask again.

Before sending, verify project/MR identity, current base/head, description identity, operational responsible mapping and commit-author attribution. Refresh affected evidence only; insufficient current evidence means an exact older-scope report and material limitation. Render the public format, including separate responsible and author fields. No worker mechanics/private archive paths/measurements/comparisons unless requested.

Use verified assignment and version-bound commit metadata for their respective roles. An assignee/MR creator is not automatically a change author. Introducing-author attribution for a particular finding needs actual commit/account mapping, never guessed emails/names; the general authors slot does not prove which person introduced a defect. If unavailable, state No identificado(s) or ask only when the user requires that exact identity for publication. Never mention unverified accounts.

Publish only authorized content/action and verify returned evidence. Draft is not published. If completion is uncertain, inspect the remote result before retrying; avoid duplicates. Prior-comment updates need corresponding authorization, with stable IDs supporting consistent updates.

Record an authorized publication observation in the open run's compact trace with actual authority and returned evidence. After closure, use a separate operation linked to the review ID/source; preserve the original immutable report/record/trace. A requested handoff or review source never supplies publication authority.

## Audience selection and historical publication

Final schemas 8–12 select limitations by kind/material/public_summary under [result-contract.md](../contracts/result-contract.md). Nonmaterial execution stays private; material execution publishes relevant pending-check/gate impact. Product/validation limitations and material ABCDE gaps remain visible. Merge matching area/limitation details before audience projection, retaining the selected public summary once; an unmatched material area uses its publishable detail. A material area matching an execution limitation requires a public impact summary even if that limitation was marked nonmaterial; missing classification blocks public rendering rather than hiding the gap or exposing internal detail. Deduplicate the same uncertainty across limitations, area gaps and reservations; never downgrade materiality to hide mechanics.

Before already-authorized publication, the coordinator makes one draft pass over verdict_reason, reservations, finding text, check evidence/reuse reasons and re-review details. These describe change/evidence/acceptance conditions. Internal permissions, models/harness, workers and sensitive local path components belong in execution/trace/internal limitations. Accredited project-relative resources and sanitized project commands follow the source-bound disclosure policy below. Product sessions/agents remain valid terminology; no blacklist, extra reviewer or code sweep.

### Canonical comment bytes

For schemas 1–7, `--publication-context` remains the source-bound classification for historical limitations. Check summaries use the separate `--check-publication-context` argument with exactly `{source_sha256, checks}`; its digest uses the canonical `publication_digest(record)`. For final schemas 1–10, each check row has exactly `{id, evidence, reuse_reason, rerun_reason, reference}`. IDs, original revisions, status, failure kind and reused state always come from the record. Local execution references are private by construction; the context may retain only the same public HTTP(S) URL already present on the source check. A free-text reuse or rerun reason, or evidence that contains a local path/command, requires an explicit public summary before rendering. Classify a mechanical retry as nonmaterial only when it leaves the product conclusion intact; keep material pending validation visible.

Prepare the comment after the authorized review is current and the one editorial pass is complete:

```sh
python /absolute/skill/scripts comment prepare \
  --input /absolute/retained/review.json \
  --session /absolute/owned/publication-session/manifest.json \
  --output /absolute/owned/publication-session/evidence/public-comment.json \
  --check-publication-context /absolute/owned/publication-session/evidence/check-publication.json \
  --coverage-publication-context /absolute/owned/publication-session/evidence/coverage-publication.json
```

The draft records the source hash, all three classification contexts (when applicable), the exact `render(comment)` body and its UTF-8 hash. Before sending, run `scripts comment verify` against the exact outbound body. Do not edit, trim, translate or normalize the draft after that check; change the structured public context and prepare a new draft instead. If a value is private, correct its source classification/context before rendering rather than patching generated text. This corrects presentation without repeating discovery or code verification while the source record remains current. A post-close publication is recorded as a separate verified event; it does not rewrite the retained result or draft.

After an authorized send, read the body returned by the remote service and verify it with `scripts comment verify --remote`; this permits CRLF-to-LF comparison only. Verification does not mean published. If the response is missing or differs, preserve the observation and inspect the existing remote comment before retrying. Record publication afterward as an observed trace event, in the open run or a separate post-close operation linked to the review.

Schemas 1–7 remain readable privately. Public historical limitations require ephemeral classification: --publication-context for render-comment, or publication_context for public renderer/handoff APIs. Schemas 8–12 already contain their classification and reject an extra override. Exact fields: {source_sha256, limitations: [{index, kind, public_summary}]}. SHA-256 binds canonical JSON: ensure_ascii=False, sorted keys, compact separators, allow_nan=False, UTF-8. One row per original index; detail/materiality stay sourced. Reject duplicate/missing indices and wrong hash. Do not save classification by default, rewrite history or guess kind from wording. Unclassified limits leave publication pending privately. Historical records without limitations need no classification.

## Draft schema 2: public purpose and indexed coverage

Final 11 requires check classification whenever checks exist. Its exact check-row shape is `{id, purpose, evidence, reuse_reason, rerun_reason, reference}`; legacy rows keep their original five fields and the historical-purpose label. The public purpose is a nonempty editorial statement of the same source objective, without private mechanics or an invented failure. IDs/state/revision/classification remain sourced. A structurally valid summary is not proof that it is semantically faithful; verify that in the single editorial pass.

Whenever coverage.flows is nonempty, including historical records, supply `--coverage-publication-context` to comment prepare/render-comment, or `coverage_publication_context` to render/public handoff. Exact shape: `{source_sha256, flows:[{index, summary}]}`. The digest uses publication_digest(record); every zero-based source index appears exactly once with a nonempty product-flow summary. Preserve duplicates as separate indices. Empty source flows need no context. Do not publish internal dimension taxonomy, command/workspace names or raw flow notes as a substitute for an editorial summary. Do not infer correspondence by text similarity. The source remains immutable.

Historical schema-2 drafts have: source_sha256, publication_context, check_publication_context, coverage_publication_context, exact body and body_sha256. Verify rerenders all three contexts and compares exact bytes/hashes. A historical draft 1 returns `stale_draft`; preserve it and prepare a new draft from the same still-current source without rerunning review. Changed source purpose yields source_mismatch; a modified public purpose/coverage summary without a new canonical body yields body_mismatch. CRLF tolerance applies only to observed remote transport. This never authorizes sending a comment or modifying an old publication.

Complete synthetic coverage context (replace digest with publication_digest of the actual source):

```json
{"source_sha256":"0000000000000000000000000000000000000000000000000000000000000000","flows":[{"index":0,"summary":"Creación de trabajos"},{"index":1,"summary":"Cancelación"}]}
```

## Draft schema 3: accredited commands and resources

Historical final-12 public projections use draft 3; new preparations use draft 4 below. It preserves draft-2 source and editorial contexts, body and body hash, and adds check_disclosure_context with the validated sanitized check view and selected sidecar digest. Preparation and verification receive the selected disclosure sidecar and proof sources; neither a view/hash supplied without proof nor an origin=project label establishes eligibility. Verify rerenders the exact body from the same selected bytes. Changed classification/proof requires a new draft. Draft 2 preserves its historical verification; draft 1 remains stale_draft. Preparing/verifying never authorizes sending.

Accredited project commands retain tool, selectors and project-relative resources while removing sensitive checkout prefixes, path components, credential values and private URL arguments. Original project content can itself contain secrets, which remain withheld. A sanitized command is labeled as a representation when changed. A test/script/reproduction created or modified by CCR is explained concretely without publishing its invocation as a project asset. A mixed check may identify original resources separately; unknown/opaque origin uses explanation rather than a reconstructed shell. Do not execute a command to discover its origin or repeat a historical check to improve a comment.

Use the same check decision in comments, requested public handoff and local full/brief/JSON; protect evidence/prose/references too. Keep purpose, observed result and check explanation distinct. Models, harness and worker identities remain private by default. See [the maintained disclosure/model example](../../docs/examples/check-disclosure-and-models.md).

### Selected disclosure files

Standalone contract rendering, comment prepare/verify and delivery accept paired `--check-disclosure-context <sidecar.json>` and `--check-disclosure-sources <catalog.json>`. The catalog contains `{input_identity, sources}` and may additionally select `run_dir` for verified snapshot inputs; `input_identity` is the initially pinned identity, and sources maps each selected `evidence/<file>.json` reference to `{path, sha256}` for existing bytes. The loader refuses links, unsafe paths, changed hashes, unused/unselected sources and oversized input. A snapshot requires the verified run and its initially registered identity; a standalone commit command requires the commit/tree/blob proof anchored to scope.head. Never construct the initial identity from an after-the-fact execution claim.

For a retained result, delivery uses the selected `context.check_disclosure_reference` and `context.check_disclosure_input_identity`. Registration pins that identity before work; a later sidecar cannot replace it. Retain/checkpoint the sidecar and every selected proof input using the normal evidence flags. Validation and delivery after cleanup use those retained bytes. A historical result without adequate proof receives explanation rather than a new execution or guessed command. See [artifacts.md](../archive/artifacts.md) and the maintained example for capture before cleanup.


## Draft schema 4: editorial findings after closure

New `comment prepare` emits draft 4, with optional `--finding-publication-context`. The context has exactly `{schema_version: 1, source_sha256, findings}` and binds `publication_digest` of the complete original record. Sparse rows contain a real visible finding `id` and at least one edited field: `title`, `scenario`, `impact`, `correction`, an existing `blocking_reason`, or `evidence: [{index, summary}]`. Original zero-based indices bind summaries to the same evidence. Missing fields/rows inherit source content; omission never hides findings or evidence. Structural fields, rejected/new IDs, duplicates, null suppression, unknown versions and extra fields fail.

Original and normalized UTF-8 JSON are limited to 256 KiB; each edited string is nonempty and at most 16 KiB. The JSON reader rejects duplicate keys and nonfinite values. Normalize finding rows by source order and evidence rows by index. Metadata, verdict, priorities, blocking, counts, locations, evidence kinds/check IDs and disclosure proof remain sourced from the original. Edited correction text is shared with acceptance conditions and requested public handoff. Private reporting and full/brief exports do not apply finding edits.

Draft 4 retains source and earlier contexts/body/hashes, and includes `render_policy=publication-editorial-v1`, `finding_publication_context` and `finding_publication_sha256`. Context/digest are null together when absent; `check_disclosure_context` is the selected verified view or null. Verify uses the embedded normalized context, original source and selected disclosure proof to rerender exact bytes. Recomputed hashes do not authorize semantic changes. Only observed remote CRLF transport is tolerated. Drafts 2/3 keep their historical rerender policy, including old redaction results; successful integrity does not make a defective historical body suitable to publish. Older readers must update for draft 4.

After closure, keep the original archive and earlier drafts untouched. Open/reuse a separate owned publication session, save the contexts there and prepare a new filename. Never append editorial files to the archive, rewrite closure/trace or repeat discovery/checks merely to improve prose. Recheck applicability before an authorized send; editorial projection supplies neither freshness nor authority. See [the synthetic editorial example](../../docs/examples/finding-publication-context.md).

Sanitize original source text before Markdown escaping. Formatting backslashes cannot establish a filesystem path. A narrative colon alone is not an unknown credential assignment; structured fields, JSON, explicit assignments/quoted credentials, authorization headers, URLs and known values remain protected. Learn marked values from original selected text and editorial contexts before replacing fields, so copying a source-only credential without its label does not reveal it. Sensitive structural identities block projection rather than being rewritten. A final check protects known values/URLs without inferring path or assignment authority from generated Markdown.

Complete one editorial pass over the entire body, including fields without overrides and material limitations. No blacklist of worker IDs or script names proves privacy or semantics. The context does not establish command provenance or a new execution. Correct technical errors with the linked review/correction workflow, not a misleading editorial summary. Prepare/verify do not publish; retain existing authorization and remote-observation gates.

Structured credential fields include ordered-list markers (`1.` or `1)`) and explicit Markdown code. Match complete backtick delimiters and fenced blocks so a closing delimiter does not grant credential authority to later narrative prose. Previous review IDs are structural identities too: a collision with a learned sensitive value rejects public rendering and preparation.


Sidecar schema 1 did not carry a sanitization version. Durable readers therefore recognize an exact current or historical row reconstruction under the same selected resource-proof checks; historical draft verification explicitly selects its old reconstruction and view. This preserves existing archives without accepting arbitrary rows or hashes as proof. New public output still uses current privacy. Credential collection includes lexical and valid decoded JSON strings, all selected editorial/disclosure text and the handoff context before cross-field projection. Build handoff links derived from source reports only after their original locator passes the public-URL policy; do not turn withheld paths or omission markers into destinations.
