# Optional external executor

Load only for an installed documented CLI when native sessions are unavailable or the user requests it. Establish noninteractive invocation, fresh context, confinement and permissions from actual help/docs. Never invent flags or silently install an agent.

Adapter JSON needs argv with {prompt_file}/{workspace} placeholders, optional {output_dir}, and fresh_context: true. Use an executable or explicit interpreter argv, not a shell/batch entrypoint. The adapter creates a fresh session, honors permissions, disables remote writes, waits for descendants and terminates them on failure/cancellation. The boolean asserts an established contract, not proof; exercise a harmless disposable task first.

```json
{"argv": ["absolute-adapter", "{prompt_file}", "{workspace}", "{output_dir}"], "fresh_context": true}
```

Run review_runner.py through an absolute interpreter/script path with documented --config, --prompt-file, --workspace, --output-dir and --timeout arguments. Output dirs must be new; prefer evidence/<role>/ for logs/metadata. No credentials in configuration/prompts/logs; use permitted authentication.

Zero exit means process completion, not review validity. Validate new worker output with review_packets.py, and final/legacy records with review_contract.py; structural validity is not finding truth. Distinguish process state, contract validity and semantic verification; preserve evidence before cleanup. Optional measurement labels and adapter-supplied usage.json follow measurements.md; they do not configure the model or infer credits.

The runner is not an OS sandbox or guaranteed descendant container. Timeout termination is best effort; detached descendants may survive. workspace_cleanup_ready stays false until the coordinator confirms owned workers stopped. If lifecycle/ownership cannot be established, stop that fallback and preserve/report resources. Root exit alone never authorizes deletion.
