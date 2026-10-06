# Bounded effectiveness and cost evaluation

Read only when explicitly maintaining/evaluating effectiveness or cost of this skill. Contract tests establish mechanical behavior; fixture executions establish their ground truth. Neither proves a model's review accuracy or token savings.

## Offline checks

Run `python -B -m unittest discover -s /absolute/skill/tests -v`. This covers record consistency, output omission rules, CLI Unicode/errors, explicit deduplication, schema4 presentation identity, optional measurements/legacy archive closure, executor provenance, ABCDE user-only coverage with material-gap precedence/legacy compatibility, and the evidence layout with cleanup refusal/recovery in a disposable Git repository. No paid model calls or third-party Python dependencies. Git integration explicitly reports a skip if Git is unavailable.

## Review inputs

Use `tests/fixtures/review_inputs.json`: three small before/after Python artifacts, consumers, requirements and PR descriptions. Give a fresh reviewer only its selected case, a requested profile and relevant skill instructions. No answer key, previous findings, parent analysis, or unrelated cases. Require the minimal worker record. Do not ask discovery workers to read evaluation.md or tests/test_review_scenarios.py.

Evaluator-only answer key:

| Case | Expected behavior |
|---|---|
| response-contract | Introduced code defect: removed id breaks the included consumer. Compare before/after; a compatible response is required. Description consistency is assessed separately. |
| normalization-control | Clean control: trims accepted names, rejects empty/blank names, preserves consumer navigation. No code finding. |
| description-only | Required default change and overrides work. Description incorrectly claims unchanged behavior; request a description correction, without inventing a code defect or automatically blocking. |

The tests execute these cases. Count distinct causes, not repeated worker findings. A worker candidate is not a confirmed final finding. Final verification must preserve decisive evidence and separate description issues from code defects.

## Comparable model runs

Use the same immutable inputs, profile, capability constraints and harness configuration for a comparison. Limit each run to the profile's assigned discovery/verification passes; do not retry to obtain a preferred answer. Record exact model identifier/date, input IDs, profile, actual sessions, independent/fallback verification, extra tool executions, unsupported findings, missed expected causes and elapsed time. Change one factor per comparison.

Record actual provider/harness input/output/cached tokens and charges when exposed; unavailable is **unknown**, never zero or an inferred price. Compare both accuracy and measured total cost. Do not infer savings from fewer reference words alone. Before/after comparisons require observations for both skill versions; planning probes are separate.

Use measurements.md and review_metrics.py for disjoint per-phase actual counters and incomplete totals. New discovery/verification probes use worker-packets.md; the final result still follows result-contract.md. Native counters are available only when exposed by the harness; the helpers do not instrument native tools automatically.

Worksheet: run ID | skill version | case/profile | model/harness/effort | verification mode | found/missed causes | false positives | repeated checks/reads | tool output size | elapsed | measured tokens/charge or unknown.

These three cases are a smoke evaluation, not representative accuracy or cost benchmarks. Add a real anonymized failure or clean control only when it tests a distinct behavior; keep expected outcomes separate from discovery inputs.
