# Historical review consultation

The `review_history.py` helper reads a bounded source archive without calling native mutation, recovery, cleanup or delivery operations. Start with `inspect --source-run <exact-path>`. It reports whether the retained `review.json` and `informe.md` are internally portable. A missing report, unknown schema, invalid hash/scope/ID, unsafe path or pending helper transaction remains a diagnostic; there is no force option.

```text
python scripts/review_history.py inspect --source-run <exact-old-run>
python scripts/review_history.py port --source-run <exact-old-run> [--output-root <history-root>]
python scripts/review_history.py show --history-dir <exact-package>
```

Port only creates a consultation package containing exactly:

| File | Purpose |
|---|---|
| `informe.md` | The verified original report bytes, unchanged |
| `consulta.json` | Original scope, verdict, review identity when known, source hashes and recorded closure facts |
| `.ccr-history.json` | Package inventory, historical schema and hashes binding the three files to their source bytes |

The default destination is `<archive-root>/.historical/<repository-group>/<scope-hint>--<source-UTC-date-or-undated>--<HP-id>/`. Dates identify the source directory and do not alter the report. Repeating the same verified port returns the existing package only if its bytes still validate. Destination collisions or edited packages are preserved and reported. Interrupted staging can be retried only when its bytes match this exact port operation.

The reader checks archive ownership/manifests, hashes, duplicate JSON keys, final-result contract, scope, review ID when available, report bytes, size bounds and stable source bytes before and after reading. It does not claim the old execution is fresh, re-run checks, resolve old evidence links or certify the original verdict. A pending cleanup observation may be copied as pending; pending retain/close/checkpoint/trace/restart/transfer/cleanup transactions are not ported. The source folder and files are never moved, rewritten or removed.

`show` rechecks the exact three-file inventory and content hashes, then displays the report with an external warning that it is a historical consultation, not revalidated, and its evidence or links may be unavailable. A package remains readable after the source disappears. It is never a run and cannot be used for resume, restart, recover, cleanup, transfer, retention, publication, delivery or native `--previous-run` lineage. `--previous-run` is valid only for a verified native archive schema 8/layout 2 source; a consultation package or unsupported historical source cannot seed operational lineage. To assess current code, start a new archive 8 review and cite the historical package only as a consultation reference.
