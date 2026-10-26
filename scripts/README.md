# Mapa de módulos de `scripts/ccr`

- `scripts/ccr/contracts/dimensions.py`: catálogo y coherencia de las 27 dimensiones de final 11, sin IO.

`scripts/__main__.py` es la entrada ejecutable instalada (`python <skill>/scripts ...`). `ccr.cli.main.AREAS` es el registro fijo de las doce áreas. Los parsers y traducciones de errores viven en `ccr.cli`; las operaciones de dominio viven en su propietario por área. El launcher carga sólo el parser solicitado, y la ayuda raíz no inicia servicios.

Las dependencias siguen responsabilidades observables: `shared` proporciona primitivas; `contracts` valida valores sin leer ni escribir archivos; `workflow` normaliza entradas y construye candidatos; `execution` observa procesos y opera sesiones temporales; `archive` lee o cambia el archivo durable; `reporting` forma proyecciones y entregas; `maintenance` resume mediciones. `archive` puede coordinar operaciones de `execution`; `execution` no invoca mutadores de `archive`. Los módulos de implementación no importan `ccr.cli`. `tests/test_script_dependencies.py` comprueba imports absolutos, relativos y locales, carga diferida registrada y ciclos, incluidos imports dentro de funciones.

Cada fila indica el contrato principal que consume código vecino, el efecto que debe esperarse y la prueba representativa. Las funciones marcadas como privadas son seams internos deliberados, no una interfaz CLI adicional.

## `ccr.cli` — interfaz de comandos

| Módulo | Responsabilidad y efecto | Contrato principal | Pruebas representativas |
|---|---|---|---|
| `scripts/ccr/cli/main.py` | Despachar las doce áreas permitidas; sólo analiza el primer token y carga un parser bajo demanda. | `AREAS`; `main(argv) -> int`; pasa el sufijo intacto y `prog='ccr AREA'`. | `test_script_cli.py`, `test_script_layout.py` |
| `scripts/ccr/cli/artifacts.py` | Traducir argumentos y errores de preparación, registro, validación, retención y cierre del archivo. | `preflight_run`; `main(argv, *, prog) -> int`. | `test_review_areas.py`, `test_review_artifacts.py`, `test_script_cli.py` |
| `scripts/ccr/cli/checks.py` | Recibir solicitudes acotadas de ejecución de checks y emitir recibos. | `main(argv, *, prog) -> int`; delega en `execution.checks`. | `test_review_check_receipts.py`, `test_script_cli.py` |
| `scripts/ccr/cli/comment.py` | Preparar/verificar bytes exactos de un comentario público; no publica. | `main(argv, *, prog) -> int`; delega en `reporting.comment`. | `test_review_comment.py`, `test_script_cli.py` |
| `scripts/ccr/cli/contract.py` | Validar contratos, renderizar reportes y agrupar candidatos explícitos de duplicados. | `main(argv, *, prog) -> int`. | `test_review_contract.py`, `test_review_presentation.py`, `test_script_cli.py` |
| `scripts/ccr/cli/delivery.py` | Solicitar una entrega explícita de una revisión retenida. | `main(argv, *, prog) -> int`; delega en `reporting.delivery`. | `test_review_delivery.py`, `test_script_cli.py` |
| `scripts/ccr/cli/history.py` | Inspeccionar/portar revisiones históricas como paquete de consulta. | `main(argv, *, prog) -> int`. | `test_review_history.py`, `test_script_cli.py` |
| `scripts/ccr/cli/metrics.py` | Recibir contadores provistos y resumir ejecuciones. | `main(argv, *, prog) -> int`. | `test_review_metrics.py`, `test_script_cli.py` |
| `scripts/ccr/cli/packets.py` | Validar paquetes internos y combinar deltas de decisión explícitos. | `main(argv, *, prog) -> int`. | `test_review_packets.py`, `test_script_cli.py` |
| `scripts/ccr/cli/recovery.py` | Exponer inspección de solo lectura y clasificación acotada. | `main(argv, *, prog) -> int`. | `test_review_recovery.py`, `test_review_latest.py`, `test_script_cli.py` |
| `scripts/ccr/cli/runner.py` | Aceptar una ejecución configurada con contexto nuevo. | `main(argv, *, prog) -> int`; delega en `execution.runner`. | `test_review_areas.py`, `test_review_execution_policy.py`, `test_script_cli.py` |
| `scripts/ccr/cli/setup.py` | Validar y guardar un candidato de preparación en una sesión propia. | `main(argv, *, prog) -> int`; expone `profile`, `context`, `event`, `inputs`, `changes`, `materials` y `reuse-context`. | `test_review_setup.py`, `test_review_reuse_context.py`, `test_script_cli.py`, `test_script_characterization.py` |
| `scripts/ccr/cli/workspace.py` | Exponer operaciones explícitas sobre workspaces Git propios. | `main(argv, *, prog) -> int`. | `test_workspace_layout.py`, `test_review_areas.py`, `test_script_cli.py` |

## `ccr.shared` — primitivas compartidas

| Módulo | Responsabilidad y efecto | Contrato principal | Pruebas representativas |
|---|---|---|---|
| `scripts/ccr/shared/encoding.py` | Serializar formatos nombrados que forman parte de documentos e hashes durables; puro. | `archive_bytes`, `compact_bytes`, `receipt_bytes`; cada formato conserva separadores y salto final. | `test_script_shared.py`, `test_script_characterization.py` |
| `scripts/ccr/shared/git.py` | Ejecutar consultas Git sin heredar variables de entorno que alteren la estructura del repositorio. | `git(path, *args)` y `repository_identity(path)`. | `test_script_shared.py`, `test_review_artifact_layout.py` |
| `scripts/ccr/shared/installation.py` | Resolver recursos del skill desde su ubicación instalada, sin depender del cwd. | `skill_root() -> Path`; `resource_path(relative) -> Path`. | `test_script_shared.py`, `test_review_harness.py`, `test_script_cli.py` |
| `scripts/ccr/shared/json_io.py` | Leer JSON acotado y escribir atómicamente bajo rutas validadas. | `read_bounded`, `read_json`, `atomic_write`; rechaza tamaño/JSON inválidos y conserva bytes comprometidos. | `test_script_shared.py`, `test_review_atomic_recovery.py` |
| `scripts/ccr/shared/paths.py` | Resolver y comprobar rutas locales con reglas comunes. | `safe_path`, `contains`; detecta escapes y enlaces según el caller. | `test_script_shared.py`, `test_review_lock_file_safety.py`, `test_review_resource_claims.py` |

## `ccr.contracts` — validación de valores y evidencia

| Módulo | Responsabilidad y efecto | Contrato principal | Pruebas representativas |
|---|---|---|---|
| `scripts/ccr/contracts/claims.py` | Validar autoridad, filas y bytes de claims sin consultar el filesystem. | `_authority`, `_claim_row`, `_encoded`, `_digest`; no normaliza rutas ni lee sidecars. | `test_review_resource_claims.py`, `test_script_resource_boundaries.py` |
| `scripts/ccr/contracts/dispatch.py` | Distinguir anotaciones de identidad de hitos genéricos y proyectarlas sobre inicios originales sin alterar la traza. | `is_identity_annotation`, `validate_dispatch_identity_event`, `project_dispatches`; sólo usa eventos y registry recibidos, no hace IO. | `test_review_dispatch.py`, `test_review_execution_policy.py`, `test_script_pure_validation.py` |
| `scripts/ccr/contracts/effective_changes.py` | Validar descriptores completos y comparar la identidad efectiva de cambios sin consultar Git. | `normalize_effective_changes`, `change_digest`, `compare_effective_changes`; preserva bytes significativos y separa procedencia de identidad. | `test_review_effective_changes.py`, `test_review_change_scope.py` |
| `scripts/ccr/contracts/execution.py` | Comprobar coherencia de planes, resultados, perfiles y fuentes de ejecución. | `validate_execution`, `validate_execution_sources`, `validate_profile_execution`. | `test_review_execution_policy.py`, `test_review_profiles.py`, `test_review_traceability_contract.py` |
| `scripts/ccr/contracts/findings.py` | Validar checks y hallazgos incluidos en el resultado. | `validate_checks`, `validate_findings`. | `test_review_contract.py`, `test_review_flow_v27.py` |
| `scripts/ccr/contracts/identifier_types.py` | Definir sintaxis canónica elemental de IDs. | `canonical_id`, `review_id`. | `test_review_contract.py`, `test_script_pure_validation.py` |
| `scripts/ccr/contracts/identifiers.py` | Canonicalizar y deduplicar IDs/filas con reglas tipadas. | `deduplicate`, `canonicalize_ids`; no cambia el registro original. | `test_review_contract.py`, `test_review_scenarios.py` |
| `scripts/ccr/contracts/material_inputs.py` | Comprobar que identidades de entradas materiales coincidan con bytes seleccionados. | `validate_material_inputs`, `validate_captured_material_sources`. | `test_review_inputs.py`, `test_review_source_selection.py`, `test_script_pure_validation.py` |
| `scripts/ccr/contracts/model_usage.py` | Normalizar y validar observaciones de uso declaradas u observadas. | `normalize_model_observation`, `append_model_observation`, `validate_model_usage`; no invoca modelos. | `test_review_model_usage.py`, `test_review_archive8.py` |
| `scripts/ccr/contracts/packets.py` | Validar paquetes compactos y fusionar deltas explícitos. | `validate`, `merge`; no infiere veredictos. | `test_review_packets.py` |
| `scripts/ccr/contracts/preflight.py` | Validar requisitos de fase, admisión de eventos nuevos e historia observada de asignaciones. | `validate_assignment_event`, `validate_assignment_history`, `validate_preflight`; proyecta recuperaciones sobre la traza original sin reemitirla ni ejecutar checks. | `test_review_preflight.py`, `test_review_closure_consistency.py`, `test_review_check_receipts.py` |
| `scripts/ccr/contracts/provenance.py` | Validar procedencia registrada de checks y sus referencias. | `validate_check_execution`, `validate_check_sources`. | `test_review_check_provenance.py`, `test_review_traceability_contract.py` |
| `scripts/ccr/contracts/receipts.py` | Validar estructura, IDs y referencias de recibos capturados. | `validate_receipt`, `receipt_reference`, `is_receipt_reference`, `validate_record_receipts`. | `test_review_check_receipts.py`, `test_review_preflight.py` |
| `scripts/ccr/contracts/reference_index.py` | Validar índices y su selección agregada acotada; canonicalizar aliases en un paso. | `validate_selection_reference`, `validate_reference_index`, `validate_reference_selection`, `reference_source_paths`, `canonical_reference`. | `test_review_reference_index.py`, `test_review_references.py`, `test_review_preflight.py` |
| `scripts/ccr/contracts/reference_types.py` | Compartir tipos de issue y constantes de la gramática local acotada. | `ReferenceIssue` y límites de referencia. | `test_review_references.py`, `test_review_reference_index.py` |
| `scripts/ccr/contracts/references.py` | Parsear y resolver referencias con el índice suministrado, sin abrir archivos. | `parse_reference`, `resolve_reference`. | `test_review_references.py`, `test_review_preflight.py` |
| `scripts/ccr/contracts/review.py` | Componer validación estructural y semántica de registros de revisión. | `validate(record) -> list[str]`; errores ordenados, entrada sin mutar. | `test_review_contract.py`, `test_review_archive8.py`, `test_script_contract_boundaries.py` |
| `scripts/ccr/contracts/scope.py` | Validar el scope fijado de una revisión y exigirlo cuando corresponde. | `validate_scope`, `require_scope`; diagnósticos estables. | `test_review_contract.py`, `test_review_inputs.py` |
| `scripts/ccr/contracts/semantic_references.py` | Comprobar relaciones semánticas entre referencias y afirmaciones internas. | `validate_semantic_references`. | `test_review_references.py`, `test_review_traceability_contract.py` |
| `scripts/ccr/contracts/validation.py` | Compartir enumeraciones y acumulación ordenada de diagnósticos. | `ValidationState` y tipos de esquema; estado por validación. | `test_review_contract.py`, `test_script_pure_validation.py` |

## `ccr.workflow` — normalización y preparación

| Módulo | Responsabilidad y efecto | Contrato principal | Pruebas representativas |
|---|---|---|---|
| `scripts/ccr/workflow/builders.py` | Construir selecciones, contexto y eventos de preparación; puro. | `build_profile_selection`, `initial_selection`, `build_review_inputs`, `capture_input_sources`, `build_context`, `build_assignment_event`. | `test_review_profiles.py`, `test_review_setup.py` |
| `scripts/ccr/workflow/inputs.py` | Normalizar y comparar entradas de review sin ejecutar comandos. | `normalize_inputs`, `capture_review_inputs`, `compare_inputs`, `candidate_inputs`, `validate_current_inputs`. | `test_review_inputs.py`, `test_review_recovery.py` |
| `scripts/ccr/workflow/profiles.py` | Validar selección/historia de perfiles y combinar el registro de asignaciones. | `validate_selection`, `validate_history`, `merge_assignment_registry`, `canonical_profile`; puro. | `test_review_profiles.py`, `test_review_profile_names.py` |
| `scripts/ccr/workflow/reuse.py` | Validar mapas de materiales y contexto observado; decidir reutilización sin IO. | `build_material_map`, `build_review_context`, `compare_review_context`, `compare_material_identities`, `validate_reuse_evidence`, `coverage_reuse_issue`, `decide_reuse`. | `test_review_reuse_context.py`, `test_review_reuse_decision.py`, `test_review_reuse_flow.py` |
| `scripts/ccr/workflow/setup.py` | Preparar solicitudes usando catálogo, fuentes y sesión validada; realiza consultas y crea evidencia propia. | `run_command` y operaciones de preparación consumidas por `cli.setup`. | `test_review_setup.py`, `test_workspace_layout.py` |

## `ccr.execution` — procesos y sesiones temporales

| Módulo | Responsabilidad y efecto | Contrato principal | Pruebas representativas |
|---|---|---|---|
| `scripts/ccr/execution/candidates.py` | Crear una sola vez candidatos JSON dentro de una sesión validada. | `write_new_json(session_dir, output, value) -> Path`; rechaza sobrescritura. | `test_review_setup.py`, `test_review_comment.py` |
| `scripts/ccr/execution/change_scope.py` | Capturar diff y contenidos de objetos Git fijados, con salida bytes/NUL y límites. | `collect_effective_changes`, `collect_context_files`; clasificación por prefijo y lecturas reutilizadas por OID dentro de cada captura; hashes completos para binarios/contexto, sin filtros externos ni cambios del worktree. | `test_review_change_scope.py`, `test_review_reuse_context.py` |
| `scripts/ccr/execution/checks.py` | Capturar salida/código de un comando local explícito y producir recibo. | `capture_check`; sin shell ni expansión implícita. | `test_review_check_receipts.py`, `test_script_cli.py` |
| `scripts/ccr/execution/claims.py` | Leer/verificar sidecars, coordinar locks de sesiones y planear receipts de cleanup. | `verify_claim`, `inspect_claim_identity`, `validate_release_observation`, `session_claim_locks`. | `test_review_resource_claims.py`, `test_review_authority_and_claim_safety.py`, `test_script_resource_boundaries.py` |
| `scripts/ccr/execution/harness.py` | Validar catálogo y resolver identidad declarada sin arrancar un ejecutor. | `validate_catalog`, `load_catalog`, `validate_identity`, `resolve`. | `test_review_harness.py`, `test_script_shared.py` |
| `scripts/ccr/execution/locks.py` | Adquirir locks exclusivos entre procesos para runs. | `run_locks`; distingue conflicto temporal y error de coordinación. | `test_review_run_lock.py`, `test_review_coordination_errors.py`, `test_review_coordination_types.py` |
| `scripts/ccr/execution/runner.py` | Ejecutar adaptadores CLI configurados sin expansión de shell y manejar cancelación. | `run`, `stop`; fronteras temporales y salida capturada. | `test_review_execution_policy.py`, `test_review_areas.py` |
| `scripts/ccr/execution/workspace_manifest.py` | Validar manifiestos y ownership de sesiones temporales en solo lectura. | `load`, `owned_session`; errores `ReviewError` conservan diagnóstico. | `test_workspace_layout.py`, `test_script_execution_boundaries.py` |
| `scripts/ccr/execution/workspaces.py` | Inspeccionar, planear y ejecutar operaciones físicas sobre worktrees propios. | APIs `plan_cleanup`/`remove_workspaces` y operaciones Git; valida el lote antes de borrar. | `test_workspace_layout.py`, `test_review_session_operations.py`, `test_review_resource_claims.py` |

## `ccr.archive` — archivo durable

| Módulo | Responsabilidad y efecto | Contrato principal | Pruebas representativas |
|---|---|---|---|
| `scripts/ccr/archive/checkpoints.py` | Planear checkpoints y commits escalonados recuperables. | `checkpoint`; verifica artefactos antes del avance durable. | `test_review_checkpoints.py`, `test_review_atomic_recovery.py` |
| `scripts/ccr/archive/coordination.py` | Coordinar locks de runs y coordinación de restart ligada a fuente. | `owned_run_locks`; adquisición estable y revalidación bajo lock. | `test_review_run_lock.py`, `test_review_restart.py`, `test_review_resource_claims.py` |
| `scripts/ccr/archive/evidence.py` | Capturar y preparar bytes acotados; seleccionar candidatos explícitos o inventario hash-verificado sin escanear archivos. | `selected_source_bytes`, `select_preflight_sources`; rutinas internas de captura consumidas por lifecycle/retention/CLI; no publica el manifiesto. | `test_review_artifacts.py`, `test_review_archive8.py`, `test_review_closure_consistency.py` |
| `scripts/ccr/archive/history.py` | Verificar y portar reviews históricos como paquetes de consulta. | `inspect_source`, `verify_history`, `port_review`, `show_history`; sólo copia campos permitidos. | `test_review_history.py` |
| `scripts/ccr/archive/inspection.py` | Inspeccionar integridad/estado y decidir continuidad sin mutar el run. | `inspect_run`, `operational_summary`, `continuation_decision`. | `test_review_recovery.py`, `test_review_recovery_diagnostics.py`, `test_review_operational_summary.py` |
| `scripts/ccr/archive/integrity.py` | Verificar archivos, checkpoints, transferencias y trazas sin escribir. | `verify_files`; admite sólo estados transitorios declarados por opciones explícitas. | `test_review_artifacts.py`, `test_review_checkpoints.py`, `test_review_restart_v2.py` |
| `scripts/ccr/archive/intent_contracts.py` | Validar intents de ownership/transferencia y normalizar historial. | `normalize_transfer_history`; contrato de valores. | `test_review_authority_and_claim_safety.py`, `test_review_restart_refusals.py` |
| `scripts/ccr/archive/layout.py` | Definir layout versionado y scope lógico del archivo; puro. | `logical_scope`, `scope_group`, `run_name`, `validate_layout`, `classify_header`. | `test_review_artifact_layout.py`, `test_review_layout_v2.py` |
| `scripts/ccr/archive/lifecycle.py` | Componer preparación, perfil, eventos, registro, pausa/bloqueo y cierre. | `prepare`, `select_profile`, `register`, `pause`, `block`, `close`; cambia el estado durable. | `test_review_artifacts.py`, `test_review_archive8.py`, `test_review_profile_names.py` |
| `scripts/ccr/archive/lookup.py` | Buscar candidatos con recorrido acotado y seleccionar resultado latest explícitamente. | `find_candidates`, `select_latest`; lectura solamente. | `test_review_latest.py`, `test_artifact_lifecycle_policy.py` |
| `scripts/ccr/archive/reader.py` | Cargar y validar un archivo propio sin importar mutadores. | `load_run(run_dir) -> (Path, manifest, marker)`; sólo lectura. | `test_script_archive_reader.py`, `test_review_artifacts.py` |
| `scripts/ccr/archive/resources.py` | Aplicar claims/transferencia y coordinar cleanup durable con sesión. | `transfer_resources`, `cleanup_workspace`, transiciones de cleanup y artefactos. | `test_review_resource_claims.py`, `test_review_session_operations.py`, `test_script_resource_boundaries.py` |
| `scripts/ccr/archive/restart.py` | Ejecutar restart durable, replay, cancelación y recuperación. | `restart`, `recover`, `abandon_restart`, `record_restart_refusal`; conserva lock/ownership. | `test_review_restart.py`, `test_review_restart_v2.py`, `test_review_restart_refusals.py`, `test_review_restart_resources.py` |
| `scripts/ccr/archive/restart_contract.py` | Normalizar solicitudes e intents de restart y comparar identidad canónica. | `normalize_restart_request`, `same_restart_request`, `build_restart_intent`, `validate_restart_intent`; puro. | `test_review_restart.py`, `test_review_restart_refusals.py`, `test_review_restart_phase_consistency.py` |
| `scripts/ccr/archive/restart_observations.py` | Observar recursos del restart sin aplicar cambios. | `resource_availability`; lectura. | `test_review_restart_resources.py`, `test_review_recovery.py` |
| `scripts/ccr/archive/restart_state.py` | Leer descriptores y recibos de restart para determinar estado recuperable. | Lectores/verificadores internos; no llama lifecycle ni mutadores. | `test_review_restart.py`, `test_review_recovery_reservations.py`, `test_script_restart_boundaries.py` |
| `scripts/ccr/archive/retention.py` | Validar gates y preparar contenido durable antes de retener. | `retain`; persiste contenido/manifiesto después de validarlo. | `test_review_artifacts.py`, `test_review_checkpoints.py`, `test_review_archive8.py` |
| `scripts/ccr/archive/reuse.py` | Evaluar aplicabilidad del último resultado verificado y reconstruir evidencia histórica demostrable, sin mutar archives. | `assess_reuse`; revalida selección, cambios, contexto, materiales y prueba ordinaria del linaje explícito de un re-review; emite decisión conservadora. | `test_review_reuse_archive.py`, `test_review_reuse_flow.py` |
| `scripts/ccr/archive/trace.py` | Definir codificación y validación compacta de eventos/hitos; puro. | `encoded`, `event_input`, `event_from_execution`, `append`, `verify`. | `test_review_trace.py`, `test_review_traceability_contract.py` |
| `scripts/ccr/archive/transactions.py` | Escribir transiciones atómicas y recuperar trazas pendientes. | `save_manifest`, `recover_trace`; escrituras durable/replay. | `test_script_archive_transactions.py`, `test_review_atomic_recovery.py`, `test_review_trace.py` |

## `ccr.reporting` y `ccr.maintenance`

| Módulo | Responsabilidad y efecto | Contrato principal | Pruebas representativas |
|---|---|---|---|
| `scripts/ccr/reporting/comment.py` | Preparar y verificar bytes exactos de comentario; no publica. | `prepare_public_comment`, `verify_public_comment`; comprueba digest/cuerpo. | `test_review_comment.py` |
| `scripts/ccr/reporting/delivery.py` | Entregar proyecciones portables de un resultado retenido. | `deliver`; escribe destino nuevo con manifiesto de entrega. | `test_review_delivery.py` |
| `scripts/ccr/reporting/markdown.py` | Proporcionar escapes, celdas y referencias seguras para renderers; puro. | `one_line`, `table_cell`, `markdown_text`, `reference_text`. | `test_review_presentation.py`, `test_review_delivery.py` |
| `scripts/ccr/reporting/projections.py` | Proyectar datos por audiencia y aplicar límites de publicación. | `public_projection`, `public_checks`, `public_limitations`, `publication_digest`; puro. | `test_review_publication_policy.py`, `test_review_presentation.py` |
| `scripts/ccr/reporting/render.py` | Componer informe de usuario y handoff público desde registros validados. | `render`, `render_handoff`; sólo produce texto. | `test_review_presentation.py`, `test_review_contract.py` |
| `scripts/ccr/maintenance/metrics.py` | Normalizar contadores suministrados y resumir runs distintos. | `normalize_usage`, `summarize`; no estima tokens. | `test_review_metrics.py` |

## Entrada y validación de instalación

La copia de la skill debe conservar completo `scripts/`, incluidos `scripts/__main__.py` y todos los paquetes `scripts/ccr`. No se admiten imports desde `review_*.py`; la ruptura y equivalencias están en [la guía de migración](../docs/script-migration.md). Los contratos CLI registrados, la copia instalada en una ruta con espacios y el grafo se verifican en `tests/test_script_cli.py`, `tests/test_script_layout.py` y `tests/test_script_dependencies.py`.
