# Migrar a la entrada única de scripts

CCR sustituye los ejecutables `scripts/review_*.py` por una sola entrada de Python. Se requiere conservar una copia completa de la carpeta `scripts/`; no hay que instalar un paquete Python ni cambiar el directorio actual.

```bash
python "/ruta a la skill/scripts" --help
python "/ruta a la skill/scripts" artifacts --help
python "/ruta a la skill/scripts" setup context --help
```

En Windows, usa la ruta absoluta a la carpeta `scripts` entre comillas si contiene espacios. La ayuda raíz enumera las doce áreas sin cargar sus servicios. La ayuda específica de cada área conserva las opciones del helper correspondiente.

| Entrada anterior | Invocación actual |
|---|---|
| `python scripts/review_artifacts.py <comando> ...` | `python scripts artifacts <comando> ...` |
| `python scripts/review_contract.py <comando> ...` | `python scripts contract <comando> ...` |
| `python scripts/review_delivery.py <argumentos> ...` | `python scripts delivery <argumentos> ...` |
| `python scripts/review_history.py <comando> ...` | `python scripts history <comando> ...` |
| `python scripts/review_metrics.py <comando> ...` | `python scripts metrics <comando> ...` |
| `python scripts/review_packets.py <comando> ...` | `python scripts packets <comando> ...` |
| `python scripts/review_recovery.py <argumentos> ...` | `python scripts recovery <argumentos> ...` |
| `python scripts/review_runner.py <argumentos> ...` | `python scripts runner <argumentos> ...` |
| `python scripts/review_workspace.py <comando> ...` | `python scripts workspace <comando> ...` |
| `python scripts/review_setup.py <comando> ...` | `python scripts setup <comando> ...` |
| `python scripts/review_check_receipts.py run ...` | `python scripts checks run ...` |
| `python scripts/review_comment.py <comando> ...` | `python scripts comment <comando> ...` |

Las áreas `artifacts`, `setup`, `checks` y `comment` incluyen las funciones incorporadas en 2.14.0: preflight, construcción de entradas, captura explícita de checks y preparación/verificación de comentarios públicos.

Los 27 módulos anteriores se dividieron por responsabilidad. Esta tabla ubica sus reemplazos para orientar imports internos o enlaces a código; `ccr.*` es el paquete incluido dentro de `scripts/`, no una API de compatibilidad para imports `review_*`.

| Módulo anterior | Nuevo propietario |
|---|---|
| `review_artifacts` | `ccr.archive` (lectura, integridad, transacciones, lifecycle, retención y recursos), `ccr.shared` y `ccr.cli.artifacts` |
| `review_contract` | `ccr.contracts`, `ccr.reporting` y `ccr.cli.contract` |
| `review_recovery` | `ccr.archive.inspection`, `ccr.archive.lookup`, `ccr.workflow.inputs` y `ccr.cli.recovery` |
| `review_workspace` | `ccr.execution.workspace_manifest`, `ccr.execution.workspaces`, `ccr.archive.resources` y `ccr.cli.workspace` |
| `review_resource_claims` | `ccr.contracts.claims`, `ccr.execution.claims` y `ccr.archive.resources` |
| `review_execution` | `ccr.contracts.execution` y `ccr.contracts.provenance` |
| `review_delivery` | `ccr.reporting` y `ccr.cli.delivery` |
| `review_profiles` | `ccr.workflow.profiles`, `ccr.contracts.execution` y `ccr.contracts.provenance` |
| `review_history` | `ccr.archive.history` y `ccr.cli.history` |
| `review_packets` | `ccr.contracts.packets` y `ccr.cli.packets` |
| `review_run_lock` | `ccr.execution.locks` |
| `review_layout` | `ccr.archive.layout` |
| `review_restart` | `ccr.archive.restart_contract` |
| `review_trace` | `ccr.archive.trace` y `ccr.archive.transactions` |
| `review_runner` | `ccr.execution.runner` y `ccr.cli.runner` |
| `review_restart_refusal` | `ccr.archive.restart`, `ccr.archive.intent_contracts` y `ccr.archive.restart_state` |
| `review_metrics` | `ccr.maintenance.metrics` y `ccr.cli.metrics` |
| `review_harness` | `ccr.execution.harness` y `ccr.shared.installation` |
| `review_inputs` | `ccr.workflow.inputs` y `ccr.contracts.scope` |
| `review_publication` | `ccr.reporting.projections` |
| `review_check_provenance` | `ccr.contracts.provenance` |
| `review_references` | `ccr.contracts.reference_types`, `references`, `reference_index`, `semantic_references` y `material_inputs` |
| `review_preflight` | `ccr.contracts.preflight` |
| `review_setup` | `ccr.workflow.builders`, `ccr.workflow.setup`, `ccr.execution.candidates` y `ccr.cli.setup` |
| `review_check_receipts` | `ccr.contracts.receipts`, `ccr.execution.checks` y `ccr.cli.checks` |
| `review_comment` | `ccr.reporting.comment` y `ccr.cli.comment` |
| `review_model_usage` | `ccr.contracts.model_usage` |

Los imports Python directos de `review_*`, las rutas de archivo de esos módulos y los alias de módulos en `sys.modules` se retiraron. Para actualizar un consumidor, usa el módulo `ccr.*` propietario indicado arriba; consulta [el índice de módulos](../scripts/README.md) para su responsabilidad, efectos, contratos y pruebas. Los datos persistidos y sus esquemas no cambian.


## Admisión por equivalencia (3.2.0)

Se añaden `setup changes`, `setup materials`, `setup reuse-context` y `artifacts assess-reuse`. Los tres builders mantienen el envelope `{session, arguments}` y salida nueva dentro de evidence de una sesión propia. `assess-reuse` añade `--repo`, `--scope-file`, `--current-inputs`, `--effective-changes`, `--current-materials` y `--session`; no muta el archive. Consulta [reuse.md](../references/workflow/reuse.md) para el orden de bootstrap y acciones.

No se retiran comandos existentes. `lookup --select latest` sigue permitiendo consulta histórica explícita y no certifica aplicabilidad por sí solo. `compare_inputs`, resume/recover, ownership, fuentes y dispatch-identity conservan sus contratos exactos. Los nuevos sidecars son opcionales para lectores de archives anteriores; su ausencia impide certificar reutilización salvo reconstrucción verificable.

## Traceability contract update (3.3.0)

Current guided producers complete final 11 and retain with --expected-schema 11. `checks run` requires purpose in its exact request before process launch and emits receipt 2; existing receipt 1 readers retain historical semantics. `packets merge` uses context.check_schema_version=11 for purpose-bearing checks, with legacy default 2. Packet version remains 1.

`contract render-comment` and `comment prepare` accept --coverage-publication-context in addition to the existing limitation/check contexts. Every source flow needs one indexed source-bound summary; final-11 check contexts also require purpose. New canonical drafts are schema 2; verify reports stale_draft for historical draft 1. Full/brief/handoff share evidence-origin and coverage blocks. These changes do not restore removed CLI/import paths or authorize publication. Archive 8/layout 2, trace 1 and delivery receipt 1 are unchanged; older final readers may require an update for final 11. No independent viewer change is included.
