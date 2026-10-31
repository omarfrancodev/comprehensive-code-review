# Identifiable checks and private model provenance

This is a synthetic, maintained example for new final-schema-12 reviews. Model IDs below are fictitious fixture values, not observations about a real harness or a historical run. Start with the owned-session and archive lifecycle in [archive8-lifecycle.md](archive8-lifecycle.md). Keep the selected review inputs, context, receipt streams and proof bytes before cleanup.

## Project checks and CCR reproductions

For an original project test, the captured invocation might be `pytest C:\Users\example\repo\tests\test_queue.py -k retry`. When selected proof binds the original test content to the pinned input and the executed bytes, the portable/public view retains `pytest tests/test_queue.py -k retry`. It preserves the tool, selector and project resource, omitting the local checkout prefix. A project task such as `npm test -- --runInBand` requires the original task definition and its execution binding; recognizing a familiar command name is insufficient.

A reproduction at `python <owned-session>/repro_retry.py` is created by CCR. Its public/portable view does not claim that script is a project asset. Instead it explains the actual method, for example: “Se simuló una respuesta vacía durante el reintento y se comprobó si conservaba el identificador”, followed separately by the observed result. If the reproduction inspected an original project resource, that resource may be named separately only when its origin is accredited. The explanation must describe the actual check, not infer a successful outcome.

A check that overwrote a tracked project script cannot claim execution of the original script merely because the path is tracked. Missing proof, opaque nested shells and unknown origin use a concrete explanation. Credentials, tokens, sensitive URL values and private path components remain withheld in every field even when the containing script belongs to the project. A sanitized representation is labeled accordingly; it is not a promise that the displayed string is an exact runnable command in another environment.

The same validated decision belongs in comment, full, brief, requested handoff and portable JSON. Canonical review bytes retain the original command. Draft 3 and delivery receipt 2 bind the new projection to selected proof; historical drafts and deliveries retain their original policies. Examples are exercised by `test_review_check_disclosure` and `test_review_disclosure_integration`.

## Selecting capture evidence before cleanup

`setup context` obtains `check_disclosure_input_identity` from the workspace’s initial resource baseline and pinned head/snapshot. Register that context before review work; preserve the returned identity. For each captured check retain the returned input/resource and literal-execution evidence, not just the purpose/result text.

```sh
python /absolute/skill/scripts setup check-disclosure \
  --input /absolute/owned/session/evidence/disclosure-request.json \
  --output /absolute/owned/session/evidence/check-disclosure.json
```

The request uses `{session, arguments}`. Arguments are exactly `record` (the current final object), `input_identity` (the initially pinned identity), `execution_observations` and `sources`. Each observation is keyed by the actual check ID and selects the captured execution/input references plus a safe specific explanation. Each source selects an owned-session `reference` and exact `sha256`; these are supplied from observed capture, not guessed fixture hashes. Set `context.check_disclosure_reference` and retain the sidecar plus every selected proof source before cleanup. This example is exercised in `test_review_disclosure_integration`; the synthetic expected command does not authorize a real run.

For standalone comment/render, use paired `--check-disclosure-context` and `--check-disclosure-sources`. The source catalog contains initially pinned `input_identity` and `sources` mapping logical references to `{path, sha256}`; snapshots additionally require `run_dir` so the loader verifies that original registration and selected inventory. A standalone commit source needs the retained commit/tree/blob chain. Rehashing a fabricated sidecar and fabricated resource map together cannot establish original membership.

## Supplied model metadata

After preparing the run, use its actual review ID and known harness ID. Prepare this setup request with the current context and ledger; the empty context/null ledger below illustrate only the first synthetic observation:

```json
{
  "session": "/absolute/owned/session/manifest.json",
  "arguments": {
    "context": {},
    "ledger": null,
    "metadata": {"model": "synthetic-configured-model"},
    "actor": {"kind": "coordinator", "name": "coordinator", "provider_id": null},
    "phase": "prepare",
    "activity": "coordination",
    "review_id": "CR-aaaaaaaaaaaaaaaaaaaa",
    "harness_id": null,
    "assignment_id": null,
    "check_id": null
  }
}
```

```sh
python /absolute/skill/scripts setup model-usage \
  --input /absolute/owned/session/evidence/model-input.json \
  --output /absolute/owned/session/evidence/model-candidate.json
```

The output candidate contains `{context, ledger}`. Preserve the current context fields when supplying a real request, and accumulate each observation using the returned context and ledger. The operation does not overwrite an archive. Select the context plus `evidence/model-usage.json` for checkpoint/retention, where their exact bytes are hashed; keep model data out of `review_inputs.sources`.

For each actually dispatched reviewer, use the observed actor/provider and assignment ID. An explicitly configured model produces `configured_only`. Metadata such as `{"observed_model":"synthetic-observed-model","model_source":{"kind":"platform","reference":"synthetic-call-17"}}` produces `observed` only when that source/ref is actually supplied by the platform. An empty metadata object produces `unknown` with null model values. Never manufacture a platform reference to populate the table. A dispatcher process is separate from the model reviewer and does not inherit its model.

Retain changes of phase/model as additional observations. Compare capture coverage with real dispatch/results so coordination alone cannot hide uncaptured reviewers. Missing metadata remains visible without another dispatch, provider/history query, cost probe or product finding. A selected corrupt ledger still fails integrity validation.

The private report and local full/brief delivery show configured model, observed model, status and sanitized source/absence by participant. The delivery binds the selected ledger digest without exporting its raw contents. Public comments and public handoff omit these model/worker details. After cleanup, views use selected retained bytes; historical runs with no ledger say the model was not recorded and receive no fabricated backfill. This flow is covered by `test_review_model_capture` and the historical-contract tests in `test_review_model_usage`.
