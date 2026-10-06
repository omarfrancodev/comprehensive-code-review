# Per-phase measurements

Load only for an explicitly requested cost/effectiveness evaluation. Normal reviews do not create measurements.json, probe native counters or load this reference. The optional runner may preserve already supplied adapter usage without extra model/tool calls; do not aggregate it by default. Explicit measurement flags opt into retention; old measurement archives remain intact.

Initialize and retain measurements.json in the persistent run under artifacts.md, outside public comments/final schema. Recording availability is required even when the helper/counters are unavailable. Native missing usage uses null and an explicit reason; interruption preserves the partial record. Use actual counters; absence is unknown. Count disjoint executions once, not both inclusive parent totals and children. Role/phase/model/harness labels identify actual execution; they do not configure it.

Normalized usage: input_tokens, output_tokens, cached_input_tokens, reasoning_tokens (nonnegative integers/null), credits and cost (actual finite nonnegative numbers/null), currency (explicit text/null, required for cost). Omitted fields become null. Input includes cached tokens; output includes reasoning tokens. Adapters map provider counters to these semantics. Credits/currency costs stay separate, never inferred from tokens.

## External runner

review_runner.py captures elapsed time, stdout/stderr byte sizes and one executor invocation. Provider session count stays unknown unless independently supplied; process completion does not prove one model session. Optional --role/--phase/--model/--harness label measurements. A configured adapter may write normalized usage.json in its new output_dir; the runner captures it into run.json. Missing usage is unavailable; malformed usage is invalid with a diagnostic/unknown counters, preserving execution outcome. Output bytes are not tool-output characters/token estimates.

## Native environments

No automatic interception of Codex/Kiro/native tools is provided. The coordinator/supported adapter supplies exposed actual counters; otherwise fields stay unknown. Optional counters: sessions, tool_calls, repeated_reads, tool_output_chars. Avoid extra agents/API calls merely to estimate measurements.

```text
python /absolute/skill/scripts/review_metrics.py record --phase discovery --role reviewer --model actual-model-id --harness actual-harness --usage-file /absolute/normalized-usage.json
python /absolute/skill/scripts/review_metrics.py summarize --input /absolute/discovery/run.json /absolute/verification/run.json
```

record emits JSON to stdout; explicitly save it to a permitted owned location or capture it using supported tools. Omit --usage-file when unavailable. Counter flags use hyphens, e.g. --tool-calls. summarize recomputes totals without double-counting subsets, exposes known_subtotal/unknown_runs and leaves incomplete totals unknown. Monetary subtotals stay separated by currency. Feed disjoint records only; retain input/model identities alongside them. Archive the compact records/summary before removing execution evidence. Account-wide credit snapshots are not attributable per-review usage and must not populate review credits/cost fields.

Compare immutable inputs under one changed factor using evaluation.md, including missed defects/false positives. Smaller packets/files alone do not establish savings. Model effort, caching and billing remain provider/harness behavior; this skill does not change them or guarantee savings.
