# Scripts Modularity and Single Entry Point Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** organizar y fragmentar los 27 helpers de CCR por responsabilidad y sustituir sus 12 CLI por una única entrada sin fachadas legacy.

**Architecture:** scripts/__main__.py delega a un registro estático de áreas con carga diferida; cada parser llama contratos, lectores u operaciones de su dominio. Las extracciones cortan dependencias inversas antes de mover transacciones y recursos. Las interfaces de ejecución cambian; los protocolos persistidos y garantías de 2.14.0 permanecen intactos.

**Tech Stack:** Python 3.10+, biblioteca estándar, unittest, Git y Markdown.

**Spec:** [Scripts modulares y entrada única](../specs/2026-10-21-scripts-modularity-design.md).

## Global Constraints

- Python 3.10+ y biblioteca estándar; no añadir dependencias de ejecución ni exigir instalación Python.
- Usar `python /ruta/skill/scripts <área> ...` como interfaz soportada, desde cualquier cwd y con rutas que contengan espacios.
- Retirar los 27 archivos `scripts/review_*.py` al completar la migración; no conservar fachadas, aliases en sys.modules ni imports legacy como interfaz soportada.
- Conservar archive schema 8/layout 2, result schemas 1–10 y trace schema 1; no migrar ni reescribir archivos históricos.
- Los layouts anteriores siguen sin soporte operativo nativo; su consulta histórica conserva paquetes de tres archivos y nunca habilita resume/restart por conservar un validador legible.
- Preservar identidades, bytes canónicos, hashes, reservas, nombres de artefactos y replay nativo v2; un cambio de módulo no cambia la identidad lógica del productor.
- Mantener locks, reentrancia, orden de adquisición, ownership, gates, idempotencia y causas/tipos de errores de coordinación.
- Preflight, diagnóstico, búsqueda y ayuda son de sólo lectura: no crean runs, locks, eventos, worktrees ni procesos de trabajo.
- Conservar selección explícita de latest, sus empates y búsqueda incompleta; no convertir inputs desconocidos o cambiados en aplicables.
- Mantener setup en sesiones propias, captura explícita sin shell y comentario público verificado por sus bytes; ninguna operación publica remotamente por este cambio.
- No activar mediciones, sondeos de modelos, instalación de herramientas ni dispatch adicional.
- No modificar el visor independiente ni las skills globales de Superpowers o todo.
- Mantener documentos históricos como evidencia; actualizar instrucciones vigentes, enlaces locales y guías de migración sin atribuirles comportamiento posterior.

## Review Focus

1. Una copia instalada en una ruta con espacios, desde cwd ajeno y sin PYTHONPATH, debe cargar catálogo/versión y las 12 áreas; pruebas de Task 12.
2. `checks run` debe devolver 0 si capturó correctamente un proceso con exit 7, manteniendo exit_code=7 en el recibo; prueba de Task 10.
3. Un intent v2 previo sin el campo derivado y un paquete histórico deben conservar bytes/identidad y su ruta de consulta, sin conversión a archivo nativo; pruebas de Tasks 8 y 9.
4. Un fallo después de borrar recursos pero antes del recibo de cleanup debe ser recuperable por el mismo propietario, con locks reentrantes y sin borrar recursos ajenos; pruebas de Task 7.
5. Root help, área desconocida y preflight inválido no deben cargar procesos de trabajo ni crear locks/artefactos; pruebas de Tasks 4, 12 y 13.

---

## Base, estado y ejecución

Base fijada: `fd38df82f2ea8ef2a921dd8a89e66540f0f01bfb`, main/CCR 2.14.0. Worktree de planificación: `.worktrees/scripts-modularity-spec-plan`, rama `docs/scripts-modularity-spec-plan`.

Estado: plan preparado por petición expresa junto con el spec; ambos pendientes de revisión antes de implementar. Método de ejecución aún no elegido. Se recomienda ejecución nativa secuencial por el acoplamiento entre interfaces y transacciones, con revisión de rama al finalizar; la elección corresponde al usuario. Este documento no inicia agentes ni ejecuta tareas de producto.

Si main avanza antes de implementar, comparar scripts, contratos, pruebas y reglas de contribución con esta base y actualizar ambos documentos antes de ejecutar. No mezclar cambios de otro worktree. Se puede reutilizar este worktree para ejecución una vez aprobados los documentos; no es necesario crear otra copia automáticamente.

Las tareas son secuenciales. Cada una termina con sus pruebas y un commit local de alcance explícito. Se permiten delegadores temporales en los archivos legacy durante las extracciones para mantener pasos verificables; Task 12 los retira todos y Task 13 comprueba su ausencia. No escribir producto para esta entrega de planificación.

Los comandos de pruebas se ejecutan en la raíz del worktree con un intérprete Python real, no el alias de WindowsApps. `python` en los ejemplos representa ese intérprete. Una prueba RED debe fallar por la API/comportamiento que se introduce, no por errores ambientales; no se instala ninguna dependencia para obtener verde.

Para tests nuevos, crear clases unittest y usar fixtures existentes en tests/recovery_fixtures.py, archive_layout_fixtures.py, restart_v2_fixtures.py y publication_fixtures.py según el flujo. Corregir imports históricos de esos fixtures al migrar sus propietarios. No añadir nuevas importaciones desde clases de otro módulo de tests.

## Mapa de entregas e interfaces

| Task | Responsabilidad | APIs que habilita para las siguientes |
|---|---|---|
| 1 | Caracterización y baseline | Inventario exacto de parsers, formatos y orden de locks de la base |
| 2 | Infraestructura y unidades pequeñas | raíz instalada, IO con formatos nombrados, Git, locks, layout, trace, harness, scope e inputs |
| 3 | Resultado y presentación pura | validate/render/IDs, perfiles y cumplimiento de ejecución |
| 4 | Reglas de 2.14.0 | referencias, preflight, recibos y observaciones de modelo puros |
| 5 | Lectura verificada | load_run, verify_files, lectura de sesión/intents sin servicios mutadores |
| 6 | Persistencia ordinaria | transacciones, checkpoints, preparación, retención y cierre |
| 7 | Workspaces y claims | coordinación de cleanup y transferencias; acciones físicas sin ciclos |
| 8 | Restart durable | reinicio, replay, rechazo y abandono bajo el mismo protocolo |
| 9 | Consulta y continuidad | inspect/lookup/latest/history sin importar mutadores |
| 10 | Ejecución y candidatos | setup, recibos capturados y runner |
| 11 | Entrega y comentario | render/verify público y entrega desde archivo verificado |
| 12 | Cambio de interfaz | entrada única, parsers con argv, retirada legacy y guía de migración |
| 13 | Registro e integración | grafo acíclico, layout registrado, documentación coherente y suite completa |

Las APIs que no cambian de firma se trasladan con sus nombres/argumentos actuales. Las nuevas firmas fijadas a continuación y en spec §5 son vinculantes. Helpers privados pueden renombrarse dentro de su propietario, pero todo caller externo al módulo usa una API nombrada, no imports de funciones con `_`.

### Task 1: Caracterizar la superficie actual y los protocolos

**Files:** Create `tests/fixtures/scripts_cli_contracts.json`, `tests/fixtures/scripts_encoding_contracts.json`, `tests/script_test_support.py`, `tests/test_script_characterization.py`; crear `docs/validation/2026-10-21-scripts-modularity-baseline.md` durante la implementación.

**Interfaces:** `script_test_support.run_cli(area: str, argv: list[str], *, cwd: Path) -> subprocess.CompletedProcess` elige el legacy actual y se actualiza a la entrada única en Task 12. `cli_inventory() -> dict` enumera las 12 áreas del spec con sus opciones, choices y acciones de argparse. Los fixtures guardan expectativas portables, no paths locales, UUID o timestamps de una ejecución real.

- [ ] Ejecutar `python -B -X utf8 -m unittest discover -s tests` antes de cambios de producto. Registrar resultado observado y skips en el baseline; si falla, distinguir fallo previo de regresión antes de continuar.
- [ ] Añadir `test_all_twelve_cli_surfaces_match_baseline`, `test_persisted_encodings_keep_exact_bytes` y `test_read_only_inspection_has_no_writes`. Capturar opciones/defaults requeridos y bytes de entradas deterministas a partir de la implementación actual; no exigir un RED artificial a pruebas de caracterización que describen comportamiento existente.
- [ ] Registrar el orden observado de locks por limpieza, transferencia y restart, incluyendo reentrancia y excepciones, en el baseline. Referenciar los casos existentes que lo ejercen; no cambiar ese orden al caracterizarlo.
- [ ] Ejecutar `python -B -X utf8 -m unittest discover -s tests -p test_script_characterization.py -v`. Esperar OK; revisar los fixtures para evitar que simplemente copien resultados inválidos o incluyan datos ambientales.
- [ ] Crear commit `test(scripts): fijar superficie y protocolos de los helpers` con los cinco archivos de esta tarea.

### Task 2: Extraer infraestructura, raíz instalada y contratos pequeños

**Files:** Create `scripts/ccr/__init__.py`; paquetes `shared`, `workflow`, `contracts`, `archive`, `execution`, `maintenance` con `__init__.py` mínimos. Create `shared/encoding.py`, `paths.py`, `json_io.py`, `git.py`, `installation.py`; `contracts/scope.py`; `workflow/inputs.py`; `archive/layout.py`, `trace.py`; `execution/locks.py`, `harness.py`; `maintenance/metrics.py`. Todas esas rutas son relativas a scripts/ccr. Create `tests/test_script_shared.py`. Modify los módulos legacy origen y sus tests afectados para delegar durante la transición.

**Interfaces:** `skill_root() -> Path`, `resource_path(relative: str) -> Path`; `validate_scope(scope: object) -> list[str]`, `require_scope(scope: object) -> None`; `normalize_inputs(raw: dict, *, caller: bool = True) -> dict` y `compare_inputs(retained: dict | None, current: dict) -> dict`. Extraer también `candidate_inputs(manifest: dict, record: dict | None = None) -> dict` y `validate_current_inputs(current_inputs, manifest, *, require_same_scope=True, compare_sources=True, require_applicable=False) -> dict` desde review_recovery; son reglas puras usadas por continuidad y lectura. IO/Git/locks mantienen firmas de los originales. Los formatos nombrados de encoding preservan los fixtures de Task 1; no se sustituye toda serialización por el formato de manifest.

- [ ] Escribir `test_installation_root_ignores_cwd`, `test_scope_validation_does_not_import_writer`, `test_named_encodings_preserve_hashes` y `test_lock_types_and_reentrancy_are_preserved`. La primera compara `skill_root()` con la raíz de la copia bajo prueba; la segunda valida scopes válidos e inválidos sin cargar review_artifacts.
- [ ] Ejecutar `python -B -X utf8 -m unittest discover -s tests -p test_script_shared.py -v`; esperar RED por ausencia de ccr/shared o sus APIs.
- [ ] Trasladar las funciones con su semántica actual. Extraer la validación de scope del validador general sin cambiar sus diagnósticos, y quitar la dependencia de inputs hacia review_artifacts. Resolver catálogo y SKILL.md con installation; mantener variantes de seguridad/errores de paths y Git donde hoy difieren.
- [ ] Ejecutar la prueba nueva y, por separado, las suites `test_review_inputs.py`, `test_review_layout_v2.py`, `test_review_trace.py`, `test_review_run_lock.py`, `test_review_harness.py` mediante unittest discover. Esperar OK; si alguna prueba parchea globals trasladados, parchear su propietario real.
- [ ] Crear commit `refactor(scripts): extraer infraestructura y contratos básicos` con las rutas de esta tarea y sus adaptaciones.

### Task 3: Fragmentar contrato de resultado, perfiles y render puro

**Files:** Create `contracts/validation.py`, `review.py`, `findings.py`, `identifier_types.py`, `identifiers.py`, `execution.py`, `provenance.py`, `packets.py`; `workflow/profiles.py`; paquete reporting con `__init__.py`, `markdown.py`, `projections.py`, `render.py`. Modify review_contract.py, review_profiles.py, review_execution.py, review_publication.py, review_packets.py y callers/tests. Create `tests/test_script_contract_boundaries.py`.

**Interfaces:** `contracts.review.validate(record) -> list[str]`; `contracts.identifiers.canonicalize_ids(record, reserved_ids=None) -> tuple[dict, dict]`, `deduplicate(findings, groups) -> list[dict]`; `reporting.render.render(record, audience='user', publication_context=None, *, check_publication_context=None) -> str`, `render_handoff(record, context=None, audience='user', publication_context=None) -> str`. Son las firmas observadas en la base, incluidos argumentos keyword-only. `workflow.profiles` conserva validate_selection, validate_history y merge_assignment_registry y expone `canonical_profile(value) -> str` para la normalización actualmente privada; cumplimiento final reside en contracts.execution/provenance.

- [ ] Escribir `test_validation_preserves_error_order_and_input`, `test_render_and_public_projection_match_baseline`, `test_profile_rules_have_one_owner` y `test_schema_one_through_ten_keep_existing_acceptance`. Comparar errores/texto con fixtures válidos e inválidos y comprobar copia profunda de entrada antes/después.
- [ ] Ejecutar `python -B -X utf8 -m unittest discover -s tests -p test_script_contract_boundaries.py -v`; esperar RED por APIs nuevas ausentes.
- [ ] Extraer compositores y validadores por bloque de contrato, con validación estructural antes de accesos dependientes. Compartir escapes y bloques de Markdown. Mover canonical_id/review_id a identifier_types; review importa esas comprobaciones y nunca identifiers. canonicalize_ids en identifiers puede importar review.validate sin generar la dependencia inversa.
- [ ] Ejecutar prueba nueva y suites afectadas de contract, presentation, packets, profiles, profile_names, execution_policy y publication_policy. Esperar mismos errores, render y decisiones. Mantener provenance preparado para incorporar recibos puros de Task 4, usando temporalmente el módulo legacy sólo hasta esa tarea.
- [ ] Crear commit `refactor(contratos): separar validación y presentación de resultados`.

### Task 4: Separar validación de referencias, recibos, preflight y modelos

**Files:** Create `contracts/reference_types.py`, `references.py`, `reference_index.py`, `semantic_references.py`, `material_inputs.py`, `preflight.py`, `receipts.py`, `model_usage.py`. Modify los seis legacy nuevos de 2.14.0 y sus callers; la captura de review_check_receipts.py sigue temporalmente fuera del contrato puro. Create `tests/test_script_pure_validation.py`.

**Interfaces:** `ReferenceIssue` mantiene exactamente code, field, reference, message, expected. `parse_reference(reference: str, *, field: str, allow_alias_key: bool = False)` y `resolve_reference(reference: str, sources: dict[str, bytes], *, field: str) -> object`; validate_reference_index, canonical_reference, validate_semantic_references y validate_material_inputs conservan sus firmas actuales en sus módulos propietarios. `validate_preflight(*, phase, manifest, logical_scope, selection, context, record, sources) -> dict` preserva prepare/register/discovery/retain y límite de 100 issues. APIs de receipts y model_usage mantienen las firmas actuales y no capturan procesos.

- [ ] Escribir `test_preflight_never_runs_receipt_commands`, `test_reference_fragments_and_aliases_keep_diagnostics`, `test_validation_is_bounded_and_read_only` y `test_model_ledger_stays_private_and_observed`. Comprobar también recibos inválidos, material inputs cambiados y issues truncados con el orden vigente.
- [ ] Ejecutar `python -B -X utf8 -m unittest discover -s tests -p test_script_pure_validation.py -v`; esperar RED por imports nuevos ausentes.
- [ ] Extraer tipos comunes y contratos. Cambiar preflight/provenance a contracts.receipts, eliminando imports del capturador. No mover la gramática de fuentes ni cambiar los límites para facilitar la extracción.
- [ ] Ejecutar prueba nueva y suites review_references, review_reference_index, review_preflight, review_check_receipts, review_check_provenance y review_model_usage; esperar OK sin tocar disco desde funciones puras.
- [ ] Crear commit `refactor(validaciones): aislar referencias y preflight de la ejecución`.

### Task 5: Establecer lectura verificada sin coordinador mutador

**Files:** Create `archive/reader.py`, `integrity.py`, `intent_contracts.py`, `restart_state.py`, `restart_contract.py`; `contracts/claims.py`; `execution/workspace_manifest.py`. Modify review_artifacts.py, review_resource_claims.py, review_workspace.py, review_restart.py, review_setup.py y lectores que deleguen. Create `tests/test_script_archive_reader.py`.

**Interfaces:** `reader.load_run(run_dir: str | Path) -> tuple[Path, dict, dict]`; `integrity.verify_files(run, manifest, required=False, *, allow_checkpoint_transaction=False, allow_resource_transfer=False, allow_pending_trace=False) -> None`; `workspace_manifest.load(manifest_path) -> dict` y `owned_session(session_path) -> tuple[Path, Path, dict]`. `restart_contract` conserva normalize_restart_request, same_restart_request, build_restart_intent y validate_restart_intent. Los validadores de claims/intents operan sobre objetos/bytes suministrados; restart_state puede leer descriptores mediante shared IO pero no importa reader ni servicios.

- [ ] Escribir `test_reader_does_not_import_mutators`, `test_pending_intent_is_reported_without_replay`, `test_foreign_owner_or_changed_hash_is_refused` y `test_workspace_loading_has_no_archive_back_reference`.
- [ ] Ejecutar `python -B -X utf8 -m unittest discover -s tests -p test_script_archive_reader.py -v`; esperar RED por APIs ausentes.
- [ ] Trasladar _load_run/_verify_files y los validadores que necesitan, manteniendo diferencias entre diagnóstico estructural y operación nativa soportada. Sacar formas de intents/transferencias/cleanup de los servicios para impedir dependencias inversas. Separar lectura/ownership de sesión del borrado; conservar seguridad y errores de load.
- [ ] Ejecutar prueba nueva y suites review_artifact_layout, review_archive8, review_lock_file_safety y review_authority_and_claim_safety. Comparar inventario/bytes antes y después de los lectores y comprobar que no se crean locks.
- [ ] Crear commit `refactor(archivo): publicar lectura e integridad independientes`.

### Task 6: Extraer transacciones, evidencia y ciclo de vida ordinario

**Files:** Create `archive/coordination.py`, `transactions.py`, `evidence.py`, `checkpoints.py`, `lifecycle.py`, `retention.py`. Modify review_artifacts.py y sus callers/tests. Create `tests/test_script_archive_transactions.py`.

**Interfaces:** `owned_run_locks(run_dirs, *, reservation=None)` conserva context manager/revalidación. `transactions.save_manifest(run, manifest, marker) -> dict` conserva semántica actual de _save_manifest y devuelve el marker. `transactions.recover_trace(run, manifest, marker) -> dict` devuelve el marker original cuando no hay pending_trace, o el marker actualizado devuelto por save_manifest después del replay. Los mutadores prepare/select_profile/register/record_event/pause/block/resume/retain/validate/close y checkpoint mantienen sus firmas de la base y se reparten según el spec.

- [ ] Escribir `test_checkpoint_interruptions_replay_reserved_bytes`, `test_retention_preserves_logical_producer_identity`, `test_complete_archive_is_immutable` y `test_prepare_profile_and_close_keep_native_gates` usando fixtures nativos y fallos inyectados en los mismos puntos del protocolo.
- [ ] Ejecutar `python -B -X utf8 -m unittest discover -s tests -p test_script_archive_transactions.py -v`; esperar RED por las nuevas rutas.
- [ ] Extraer planes de evidencia, publicación de manifest/trace, checkpoint y retención manteniendo orden de escrituras. La validación de procedencia recibe bytes seleccionados; el servicio no reemplaza fuentes desconocidas por búsquedas amplias. Conservar IDs lógicos de productor como constantes explícitas con sus valores anteriores.
- [ ] Ejecutar prueba nueva y suites review_atomic_recovery, review_checkpoints, review_artifacts, review_traceability_contract y review_preflight. Mantener aún restart/transferencias en el legacy hasta sus tareas; los extractos no lo importan para pedir servicios de vuelta. Toda regla compartida se baja a contracts/reader/intent_contracts.
- [ ] Crear commit `refactor(archivo): dividir evidencia y operaciones transaccionales`.

### Task 7: Aislar workspaces, claims y coordinación de recursos

**Files:** Create `execution/workspaces.py`, `claims.py`; `archive/resources.py`. Modify review_workspace.py, review_resource_claims.py, review_artifacts.py y tests de recursos. Create `tests/test_script_resource_boundaries.py`.

**Interfaces:** `archive.resources.cleanup_workspace(args) -> dict` conserva las salidas/errores de review_workspace.cleanup. `resources.transfer_resources(source_run, successor_run, paths, *, authority, controller, _restart_operation_id=None) -> dict`, begin_resource_cleanup, finish_resource_cleanup y recover_resource_cleanup conservan firmas actuales. `execution.workspaces` posee prepare/record_artifact y `plan_cleanup(args, manifest: dict, *, claim: dict | None = None) -> dict`, `remove_workspaces(plan: dict) -> dict`; éstas no importan archive.resources/restart/lifecycle. El plan contiene session_id/session_dir, entradas verificadas de workspaces y main_changed; remove_workspaces devuelve el resultado actual de cierre tras revalidar los paths y registros Git seleccionados. El servicio conserva los locks y revalida ownership antes de llamar esas acciones. `execution.claims` verifica identidad y prepara planes con datos de run seleccionados; sus APIs públicas sustituyen las llamadas privadas entre módulos. Toda entrada de cleanup reclamada pasa por resources, no por una función física expuesta como operación CLI.

- [ ] Escribir `test_claimed_cleanup_revalidates_session_then_run_under_locks`, `test_cleanup_after_removal_recovers_same_operation`, `test_transfer_interruption_preserves_both_owners` y `test_foreign_or_modified_workspace_is_never_deleted`.
- [ ] Ejecutar `python -B -X utf8 -m unittest discover -s tests -p test_script_resource_boundaries.py -v`; esperar RED por APIs nuevas.
- [ ] Separar planificación pura de claims, verificación por IO y aplicación durable; mover coordinación al servicio de archive. Conservar el orden observado de Task 1 y toda la sección crítica. Validar toda la sesión antes del primer borrado y conservar recibos/recovery ante fallo posterior. No pasar el módulo archive como dependencia general.
- [ ] Ejecutar prueba nueva y suites workspace_layout, review_resource_claims, review_coordination_errors, review_coordination_types, review_session_operations y review_restart_resources. Incluir subprocesos de contención y reentrancia; cambiar sus imports embebidos, no sólo los del proceso padre.
- [ ] Crear commit `refactor(recursos): separar ownership y coordinación de limpieza`.

### Task 8: Extraer restart, replay, rechazos y abandono

**Files:** Create `archive/restart.py`. Modify review_restart_refusal.py, review_artifacts.py y tests de restart. Los contratos/lectores ya existen por Task 5. Create `tests/test_script_restart_boundaries.py`.

**Interfaces:** `restart(source_run, *, profile_input, controller, authority, current_inputs, transfer_paths=None, harness=None, logical_scope_input=None)`, `recover(run_dir, *, controller, authority, current_inputs)`, `record_restart_refusal(run_dir, *, intent_path, controller, authority, reason)` y `abandon_restart(run_dir, *, intent_path, controller, authority, reason)` conservan las firmas actuales y sus resultados. restart_state no importa estas funciones; la inspección las describe mediante hechos observados y contratos inferiores.

- [ ] Escribir `test_old_native_v2_reservation_keeps_exact_bytes`, `test_same_request_retries_same_successor`, `test_partial_transfer_denies_unsafe_cancellation` y `test_refusal_receipt_keeps_owner_and_operation_identity` usando restart_v2_fixtures.py y escenarios existentes de adopción parcial.
- [ ] Ejecutar `python -B -X utf8 -m unittest discover -s tests -p test_script_restart_boundaries.py -v`; esperar RED por el nuevo servicio.
- [ ] Mover intent/completion/abandonment y recuperación de restart, reutilizando recursos y transacciones sin cambiar reservas o construir un segundo motor de estados. Extraer clasificadores compartidos a contratos/estado; el servicio no importa inspection para resolver reglas que inspection también necesite.
- [ ] Ejecutar prueba nueva y suites review_restart, review_restart_v2, review_restart_refusals, review_restart_phase_consistency, review_recovery_reservations y review_recovery_sequences. Esperar misma identidad/bytes en retry y mismas negativas ante entradas distintas.
- [ ] Crear commit `refactor(reinicio): aislar operaciones durables y replay`.

### Task 9: Separar inspección, búsqueda, continuidad e historia

**Files:** Create `archive/inspection.py`, `lookup.py`, `history.py`. Modify review_recovery.py, review_history.py y callers. Create `tests/test_script_read_only_flows.py`.

**Interfaces:** inspection conserva `inspect_run(run_dir, *, current_inputs=None)`, `operational_summary(manifest: dict, events: list[dict], record: dict | None)` y `continuation_decision(manifest: dict, *, input_appraisal: dict, pending_operation: dict | None, candidate_issues: list[dict])`. lookup conserva find_candidates y select_latest con sus parámetros/defaults actuales; history conserva inspect_source, verify_history, port_review y show_history. Portar historia es IO explícito y queda separado de inspeccionar/mostrar.

- [ ] Escribir `test_inspection_is_read_only_with_pending_restart`, `test_latest_refuses_ties_and_incomplete_scan`, `test_history_keeps_exact_three_file_package` y `test_continuation_does_not_dispatch_or_infer_liveness`.
- [ ] Ejecutar `python -B -X utf8 -m unittest discover -s tests -p test_script_read_only_flows.py -v`; esperar RED por APIs nuevas.
- [ ] Sustituir _artifacts() y accesos privados por reader/integrity/restart_state; separar paginación, clasificación y selección. Mantener límites/cursors, estados desconocidos, paquetes históricos y layout no operable. Las sugerencias nuevas usan el prefijo CLI acordado; no se alteran comandos históricos guardados.
- [ ] Ejecutar prueba nueva y suites review_latest, review_history, review_operational_summary y todas las `test_review_recovery*.py` con unittest discover. Esperar OK y ninguna mutación por consulta.
- [ ] Crear commit `refactor(consulta): independizar recuperación e historial de los mutadores`.

### Task 10: Extraer setup, candidatos, captura de checks y runner

**Files:** Create `workflow/builders.py`, `setup.py`; `execution/candidates.py`, `checks.py`, `runner.py`. Modify review_setup.py, review_check_receipts.py, review_runner.py y callers/tests. Create `tests/test_script_execution_boundaries.py`.

**Interfaces:** builders conserva build_profile_selection, build_context, build_model_usage_update y build_assignment_event con sus firmas actuales. setup expone `run_command(command: str, input_path: str, output_path: str) -> dict`, extraído de _run_command. candidates expone `write_new_json(session_dir: Path, output: str, value: dict) -> Path`. checks mantiene `capture_check(*, check_id, argv, command, cwd, executor_workspace, revision, executor, output_dir) -> dict`; runner conserva run(args) y stop(process).

- [ ] Escribir `test_candidates_require_owned_session_and_never_overwrite`, `test_setup_preserves_context_identity`, `test_captured_exit_seven_is_a_valid_receipt` y `test_runner_timeout_keeps_metadata_and_logs`. Para el recibo usar `[sys.executable, '-c', 'raise SystemExit(7)']` en workspace propio y afirmar receipt['exit_code'] == 7 con logs/hash válidos.
- [ ] Ejecutar `python -B -X utf8 -m unittest discover -s tests -p test_script_execution_boundaries.py -v`; esperar RED por APIs nuevas.
- [ ] Separar IO/ownership de construcción pura; cambiar setup a reader e inputs públicos. Conservar el escritor de candidatos con su formato propio, límite y rechazo de sobrescritura. Capturar argv sin shell y sin inferir éxito del comando por haber escrito un recibo.
- [ ] Ejecutar prueba nueva y suites review_setup, review_check_receipts, review_model_usage y las pruebas existentes de runner en sus suites de integración; identificar esos casos por AST/rg antes de ejecutarlos, sin inventar un archivo test_review_runner.py que no existe.
- [ ] Crear commit `refactor(ejecucion): separar candidatos y captura de comandos`.

### Task 11: Consolidar entrega y preparación/verificación pública

**Files:** Create `reporting/delivery.py`, `comment.py`. Modify review_delivery.py, review_comment.py y callers/tests; adaptar publication_fixtures.py a propietarios nuevos. Create `tests/test_script_reporting_boundaries.py`.

**Interfaces:** delivery conserva `deliver(run_dir, delivery, project_root, output_root=None, context=None) -> Path`. comment conserva `prepare_public_comment(record: dict, *, publication_context: dict | None = None, check_publication_context: dict | None = None) -> dict` y `verify_public_comment(record: dict, draft: dict, body: str, *, remote: bool = False) -> dict`. Render permanece puro y no importa delivery. Los handlers usan candidates para guardar en sesión propia, sin acoplar comment a workflow.setup.

- [ ] Escribir `test_delivery_uses_only_verified_retained_files`, `test_comment_body_edit_invalidates_canonical_hash`, `test_public_summary_keeps_product_failures_without_internal_sources` y `test_preparing_comment_never_publishes_remote_content`.
- [ ] Ejecutar `python -B -X utf8 -m unittest discover -s tests -p test_script_reporting_boundaries.py -v`; esperar RED por nuevas APIs.
- [ ] Mover proyecciones locales de delivery a su propietario sólo si son compartidas; conservar formatos de entrega y salida. Sustituir _git/_contains y utilidades de setup por APIs compartidas/candidates, sin ampliar fuentes o efectos.
- [ ] Ejecutar prueba nueva y suites review_delivery, review_comment, review_publication_policy y review_presentation. Esperar mismo body_sha256/cuerpo y negativas ante edición posterior.
- [ ] Crear commit `refactor(reportes): separar entrega y comentario público`.

### Task 12: Introducir entrada única y retirar la superficie legacy

**Files:** Create `scripts/__main__.py`; paquete `scripts/ccr/cli` con __init__.py, main.py y artifacts.py, contract.py, delivery.py, history.py, metrics.py, packets.py, recovery.py, runner.py, workspace.py, setup.py, checks.py, comment.py. Create `tests/test_script_cli.py`, `docs/script-migration.md`. Modify todos los tests/fixtures activos que invoquen/importen legacy y el helper de Task 1; SKILL.md, README.md, docs/usage.md, docs/installation.md, referencias operativas y CHANGELOG.md según CONTRIBUTING.md. Remove los 27 scripts/review_*.py sólo tras transferir sus últimos handlers/constantes.

**Interfaces:** cada área `main(argv: list[str] | None = None, *, prog: str | None = None) -> int`; raíz `main(argv: list[str] | None = None) -> int`, prog='ccr'. Registro exacto: artifacts, contract, delivery, history, metrics, packets, recovery, runner, workspace, setup, checks, comment. El root procesa sólo el primer token y pasa argv[1:] intacto al área elegida del registro fijo, con prog='ccr ' + area. __main__ propaga el exit, sin importación de áreas en ayuda raíz.

- [ ] Escribir `test_root_help_lists_exact_twelve_areas`, `test_no_or_unknown_area_returns_two_without_side_effects`, `test_each_area_preserves_options_and_exit_codes`, `test_argv_with_spaces_and_separator_is_forwarded_unchanged`, `test_installed_copy_runs_from_foreign_cwd_without_pythonpath` y `test_checks_cli_returns_zero_for_captured_exit_seven`.
- [ ] Ejecutar `python -B -X utf8 -m unittest discover -s tests -p test_script_cli.py -v`; esperar RED porque aún falta scripts/__main__.py o áreas. La prueba de copia usa TemporaryDirectory fuera de la copia, ruta con espacios, entorno sin PYTHONPATH y no depende del cwd del repo.
- [ ] Trasladar parsers/handlers, cambiando parse_args() a parse_args(argv). Preservar defaults/choices/errores y traducción específica por operación. Crear root con tabla estática y carga diferida por allowlist; no usar parse_known_args sobre toda la línea si consume opciones destinadas al área.
- [ ] Cambiar llamadas subprocess, imports normales/dinámicos y monkeypatch al propietario real. Verificar especialmente spec_from_file_location, código Python embebido en tests de locks, references a artifacts.__file__ y mocks de _finish_resource_cleanup_locked. No mantener aliases sys.modules ni importar la fachada retirada desde el paquete.
- [ ] Eliminar los 27 legacy. Actualizar guía de migración con las 12 equivalencias, ruptura de imports, copia completa y nueva ayuda; incluir preflight, setup/checks/comment de 2.14.0. Actualizar instrucciones vigentes; mantener texto histórico y reparar enlaces a código retirado dirigiéndolos a la equivalencia documentada. Registrar ruptura bajo versión pendiente de CHANGELOG sin inventar release publicada.
- [ ] Ejecutar prueba CLI y caracterización, seguidas de `python -B -X utf8 -m unittest discover -s tests`. Esperar OK, incluidos contratos de ayudas/errores y captura exit 7. Comprobar ausencia de scripts/review_*.py e imports legacy activos antes de crear commit.
- [ ] Crear commit `refactor(cli)!: unificar acceso a los helpers y retirar entradas anteriores`.

### Task 13: Registrar arquitectura y cerrar integración

**Files:** Create `scripts/README.md`, `tests/test_script_layout.py`, `tests/test_script_dependencies.py`, `docs/validation/2026-10-21-scripts-modularity.md`. Modify docs/usage.md para enlazar el registro y completar documentación de tareas anteriores.

**Interfaces:** el registro estático de cli.main es autoridad de áreas y módulos de parser. README registra los módulos reales y su responsabilidad/efectos/contrato/pruebas. La prueba de dependencias analiza AST, resuelve imports relativos/locales y carga diferida del registro fijo. No exige un número de líneas por módulo ni acceso a todos los documentos durante cada revisión.

- [ ] Escribir `test_all_modules_have_registered_responsibility`, `test_cli_registry_matches_documented_areas`, `test_no_legacy_entry_or_import_remains`, `test_implementation_import_graph_is_acyclic`, `test_pure_contracts_do_not_import_io_services_or_cli` y `test_root_help_does_not_load_work_services`. Los tests de arquitectura deben fallar también sobre grafos sintéticos con un ciclo o import local prohibido para demostrar que su detector funciona.
- [ ] Ejecutar `python -B -X utf8 -m unittest discover -s tests -p test_script_layout.py -v` y, por separado, el equivalente para test_script_dependencies.py. Esperar RED hasta registrar todas las responsabilidades o corregir un límite real; no añadir excepciones de grafo sólo para permitir ciclos remanentes.
- [ ] Completar el registro y corregir dependencias moviendo validación/política al propietario inferior, sin duplicarla ni resolverla con imports tardíos ocultos. Comprobar copia/ZIP completo y documentación de ruptura. Si la distribución se genera fuera del repo y no está disponible, registrar esa limitación en vez de afirmar que se validó una release externa.
- [ ] Ejecutar `python -B -X utf8 -m unittest discover -s tests`, `git diff --check` y prueba de copia instalada de Task 12. Registrar comando, resultado observado, skips y límites en docs/validation; no usar como evidencia la suite antigua de 2.14.0.
- [ ] Revisar spec §9 contra evidencia y verificar que sólo cambió la interfaz de ejecución acordada, sin schema bump, reserialización histórica o integración del visor. Crear commit `docs(scripts): registrar arquitectura y validación de la migración`.

## Self-review y traspaso

Cobertura: entrada/interfaz → Task 12; mapa de los 27 orígenes → Tasks 2–11; límites puros → Tasks 2–5 y 13; protocolos durables → Tasks 6–8; lectura/continuidad/historia → Task 9; garantías nuevas de 2.14.0 → Tasks 4, 9–11; instalación/documentación/registro → Tasks 12–13. Los cinco riesgos de Review Focus tienen tests asignados.

Los commits de implementación son propuestas para una ejecución posterior; sus checks permanecen sin marcar. Antes de implementar, revisar spec y plan y elegir ejecución nativa o con subagentes. No crear PR, publicar release, fusionar ni comenzar una migración de archivos persistidos como consecuencia de aprobar únicamente estos documentos.
