# Profile Lifecycle and Review Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Capturar perfiles y transiciones antes de utilizarlos, conservar resultados provisionales y recuperar o sustituir reviews interrumpidos con continuidad verificable.

**Architecture:** Archive 7 separa transacciones, disposición operativa, historial, checkpoints y claims; final 10 vincula las asignaciones con su selección. Validadores puros mantienen las reglas históricas; review_artifacts conserva el único escritor durable y delega diagnóstico/lookup y verificación de claims a módulos acotados. Las operaciones mutantes usan bloqueo exclusivo y recuperación de intenciones propias, sin procesos auxiliares.

**Tech Stack:** Python 3.10+ estándar, unittest, Git, Markdown y bloqueo nativo Windows/POSIX; sin dependencias nuevas.

**Spec:** [2026-10-13-profile-lifecycle-recovery-design.md](../specs/2026-10-13-profile-lifecycle-recovery-design.md), aprobada por el usuario el 2026-10-13.

## Global Constraints

- Worktree `.worktrees/review-recovery-lifecycle`; rama `feat/review-recovery-lifecycle`; base main `5507c48715c558c9d366491f19fcce196780b37e`.
- Emitir archive **7** y final review **10**. Mantener lectura de archives 1–6 y resultados 1–9 sin migración ni reinterpretación de reglas.
- Trace **1**, packet **1** y manifest de workspace **1** conservan su estructura; reutilizar kinds/statuses/relations existentes.
- Canonical profiles focused/standard/deep/extended; aliases economy/balanced. Nuevos IDs de selección S001, S002…; no reutilizar IDs ni modificar selecciones anteriores.
- Estados transaccionales prepared/processing/retaining/closing/complete; disposition open/paused/blocked/superseded/complete. Ninguno acredita un proceso vivo.
- retained=true significa resultado canónico validado. pending y sus hashes no satisfacen retain/close/delivery/publicación.
- Un downgrade preserva resultados y obligaciones adquiridas. Solo asignaciones no iniciadas sin necesidad vigente pueden quedar sustituidas; project gates no se cancelan.
- Recuperar no inventa dispatch, memoria, independencia ni occurred_at; una pausa expresa requiere instrucción de continuar.
- No modificar artifacts de MR !42/!785, otros proyectos, configuración de harness o visor. No publicar/mergear/release antes del gate humano del PR.
- Preparar 2.12.0 pendiente; README/instalación mantienen 2.11.0 publicada hasta autorizar la release.
- Sin métricas, heartbeat, polling, caché entre reviews, índice global de recursos ni agentes de selección/recuperación.
- Fixtures sintéticas y recursos propios; intérprete con `-B -X utf8`. Una revisión independiente de la rama completa, sin un reviewer por tarea.
- Seguimiento por checkboxes y estados en chat bajo el fallback permitido del controlador de tareas. Una tarea en progreso; conservar decisiones/resultados reales de los gates.

## Review Focus

1. Reintentos de selección o una confirmación tardía pueden cambiar cuál se considera inicial: Tasks 1–2 prueban precedencia estable y operación idempotente sin duplicar eventos.
2. Un downgrade después de discovery puede ocultar verificaciones aún obligatorias: Task 1 conserva el gate más fuerte adquirido y resultados de epochs anteriores; no aplica el último perfil retroactivamente.
3. Un crash o dos escritores pueden dividir manifest/traza/checkpoint o transferir un recurso a medias: Tasks 2–4 prueban intenciones verificables, exclusión y ausencia de cleanup hasta completar la transición propia.
4. Un recovery desde otro harness puede confundir evidencia recuperada con nuevos workers, o interpretar ausencia de recursos como limpieza propia: Task 5 preserva origen/autoridad y bloquea afirmaciones o adopciones no demostradas.
5. Mismo MR/head y una página de candidatos pueden ocultar cambios de base/descripcion/requisitos o un resultado más pertinente: Task 6 comprueba inputs, múltiples candidatos y truncación explícita sin cargar todo el historial.

---

## Preparación y ejecución

- [x] Main limpio/sincronizado; worktree creado en el directorio ignorado solicitado.
- [x] Base `5507c48`: 317 tests en 264.225 s; 316 aprobados/1 omitido por privilegios de symlinks en Windows.
- [x] Spec guardada en `a270eda`, autorrevisada y aprobada.
- [x] Crear este plan y comprobar cobertura/interfaces/proporción.
- [x] Obtener aprobación del usuario antes de implementar; conservar ejecución nativa previamente acordada.

Intérprete: `C:/Users/Developer.INSCORSOF2/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`. En los comandos, `python` representa ese ejecutable; PowerShell usa `& '<ruta>'`. Baseline ya comprobado: repetirlo solo si cambian base/runtime o aparece un fallo pertinente.

## Archivos y responsabilidades

| Archivo | Responsabilidad |
|---|---|
| `scripts/review_profiles.py` (nuevo) | Selecciones/historial y obligaciones por fase, sin IO |
| `scripts/review_run_lock.py` (nuevo) | Context manager de exclusión Windows/POSIX; sin daemon ni detección de liveness |
| `scripts/review_resource_claims.py` (nuevo) | Verificar sesiones/claims e intenciones de transferencia, sin escribir cierre/trace |
| `scripts/review_recovery.py` (nuevo) | Inspección read-only, clasificación de continuidad/inputs y lookup acotado |
| `scripts/review_artifacts.py` | Mutaciones, archive 7, checkpoints, selección, recuperación/transferencia y CLI |
| `scripts/review_contract.py`, `review_execution.py`, `review_check_provenance.py` | Envelope final 10, reglas de epochs y fuentes; lectura histórica exacta |
| `scripts/review_workspace.py` | Exigir el claim cuando exista al limpiar; conservar workspace schema 1 |
| `scripts/review_delivery.py`, `review_publication.py` | Aceptar resultados nuevos validados y excluir metadata privada; pending bloqueado |
| `tests/recovery_fixtures.py` (nuevo) | Inputs schema 10, eventos y creación de archives históricos sintéticos compartidos |
| `tests/test_review_profiles.py`, `test_review_run_lock.py`, `test_review_resource_claims.py`, `test_review_recovery.py`, `test_review_checkpoints.py` (nuevos) | Invariantes de los componentes y sus efectos |
| Tests existentes de artifact/execution/contract/delivery/trace/workspace | Compatibilidad, gates integrados y no regresiones |
| `references/archive/recovery.md` (nuevo) y referencias actuales | Contratos, decisiones y procedimientos por necesidad |
| `SKILL.md`, `README.md`, `docs/usage.md`, `CHANGELOG.md` | Routing, uso, versión pendiente y límites de consumidores |
| `docs/validation/2026-10-13-profile-lifecycle-recovery.md` (nuevo) | Evidencia de RED/GREEN, integración, decisiones y revisión final |

## Interfaces y valores comunes

Selección de entrada: `{profile, selection_source, reason, reference, phase, actor, authority, affected_assignments}`. authority es texto/null; phase es prepare/discovery/verification/report/retain/cleanup/close; actor conserva la forma del contrato de trace. reason/reference son no vacíos y acotados. affected_assignments contiene IDs existentes y es [] en preparación. El helper añade `{id, changed_from, event_id}` y preserva esa selección inmutable. Máximo 32 selecciones por run; al alcanzar el límite se informa la restricción, sin descartar historia ni continuar silenciosamente.

Final 10 añade `coverage.execution.profile_history`. Cada fila de plan conserva sus campos actuales y añade `selection_id` y `superseded_by` (null/ID de selección). required=false solo corresponde a una sustitución válida y no iniciada; resultados siempre conservan assignment_id original. Supersession no equivale a fallback. No cambiar enums de fallbacks de schema 8/9 para justificar errores de registro.

Cada selección que adquirió trabajo ordinario conserva sus obligaciones; la selección efectiva final también determina las restantes. Reutilizar discovery válido cuenta únicamente si satisface independencia/inputs requeridos. La verificación requerida es la más fuerte adquirida; límites se aplican a las perspectivas necesarias, sin contar un pass previo de menor independencia como una perspectiva fresca ni perderlo del historial.

Fixtures `selection(profile='focused', source='automatic', **updates) -> dict`, `record10(profile='focused', source='automatic') -> dict`, `context10(record: dict) -> dict`, `source_events(record: dict) -> list[dict]` y `legacy_prepare(artifacts, repo: Path, scope: Path, **kwargs) -> Path`. La última crea archives sintéticos 1–6 usando factories de test, no añade una opción de bypass a la CLI/producto.

### Task 1: Historial puro y contrato de resultado 10

**Files:** Create `scripts/review_profiles.py`, `tests/recovery_fixtures.py`, `tests/test_review_profiles.py`; Modify `scripts/review_contract.py`, `scripts/review_execution.py`, `scripts/review_check_provenance.py`; Test `tests/test_review_execution_policy.py`, `tests/test_review_contract.py`, `tests/test_review_check_provenance.py`.

**Interfaces:**
- Consumes: normalización de perfiles, validadores de actor/ID y contratos 1–9 actuales; fixtures existentes.
- Produces: `validate_selection(raw: dict, previous: dict | None = None) -> dict` (normaliza o ValueError); `validate_history(history: list[dict]) -> list[str]`; `validate_profile_execution(record: dict, trace_events: list[dict] | None = None) -> list[str]`. integrate validate_execution/sources solo para schema 10; schemas anteriores conservan rutas existentes.
- Produces: schema 10 con campos comunes anteriores; check.execution local/static/external/reused sigue vinculando revisión/snapshot y ejecutor, también en schema 10.

- [x] **Step 1: Escribir regresiones.** `test_selection_aliases_and_first_identity`, `test_explicit_transition_requires_user_source`, `test_automatic_upgrade_and_supported_downgrade`, `test_same_selection_replay_preserves_first`, `test_history_limit_is_visible`, `test_downgrade_preserves_started_obligations`, `test_supersession_cannot_cancel_project_gate`, `test_prior_coordinator_pass_is_not_new_independent_discovery`, `test_schema10_does_not_relax_local_check_bindings`. Verificar fuentes/eventos, no solo etiquetas.

  ```python
  raw = selection('balanced')
  normalized = profiles.validate_selection(raw)
  self.assertEqual(normalized['profile'], 'standard')
  self.assertEqual(raw['profile'], 'balanced')
  value = record10('focused')
  self.assertEqual(contract.validate(value), [])
  value['checks'][0]['execution']['executor'] = None
  self.assertTrue(contract.validate(value))
  ```

  El test de downgrade parte de deep con dos resultados independientes y verificación pendiente, cambia a focused con fuente y exige mantener verificador fresco; eliminarlo falla. El de supersession intenta cancelar una fila ya iniciada y un project_gate y debe fallar; una fila no iniciada con necesidad invalidada admite sustitución.
- [x] **Step 2: Observar RED.** Ejecutar `python -B -X utf8 -m unittest discover -s tests -p test_review_profiles.py -v` y `-p test_review_check_provenance.py -v`. Esperar falta del módulo/schema o violación concreta, no fixture inválida de otro tipo.
- [x] **Step 3: Implementar el modelo.** Separar shape del historial de su contraste con eventos/fuentes. Usar las firmas/valores comunes; exigir primer id S001, changed_from=null y phase=prepare, IDs siguientes contiguos y event_id distinto para cada transición. No inferir autoridad o tiempos. Resolver obligaciones preservadas para validar cardinalidad/independencia sin reinterpretar schemas 1–9.
- [x] **Step 4: Observar GREEN.** Repetir pruebas nuevas y execution_policy/contract/check_provenance. Control histórico conserva bytes de fixture y comportamiento de selección/precedencia/downgrade del schema 9.
- [x] **Step 5: Commit.** Stage explícito; `feat(profiles): conservar selecciones y obligaciones por fase del review`.

### Task 2: Archive 7, exclusión y preparación con perfil

**Files:** Create `scripts/review_run_lock.py`, `tests/test_review_run_lock.py`; Modify `scripts/review_artifacts.py`, `tests/test_review_artifacts.py`, `tests/test_review_trace.py`, `tests/recovery_fixtures.py`.

**Interfaces:**
- Consumes: Task 1 selecciones/historial; `_append_trace_events`, `_recover_trace`, atomic_write y ownership actuales.
- Produces: `run_locks(run_dirs: list[Path]) -> ContextManager[None]`; paths únicos/ordenados, adquisición no bloqueante y reentrada del mismo contexto para llamadas anidadas, liberación en finally. Windows msvcrt/POSIX fcntl; archivo privado de lock fuera del inventario de evidencia.
- Produces: `prepare(..., *, profile_input=None, controller=None, ...existing kwargs) -> str` con validación de selección obligatoria para nuevas emisiones; `select_profile(run_dir, selection_input) -> dict`; `register(run_dir, temporary_paths, *, context_input=None) -> dict`. Comandos --profile-input, select-profile --selection-input, register --context-input.
- Produces: archive 7 con metadata de spec §1 y primeros hitos prepare/profile en una intención común. Nuevos runs requieren final 10 al retener; APIs de operaciones sobre archives existentes 1–6 conservan su comportamiento. Omitir una selección no debe permitir emitir archive antiguo desde el helper actual.

- [x] **Step 1: Añadir tests de integración.** `test_prepare_requires_selection_before_directory_creation`, `test_prepare_records_selection_atomically`, `test_select_profile_idempotent_retry`, `test_work_start_without_profile_is_refused_without_changes`, `test_paused_operation_cannot_start_work`, `test_register_executor_survives_retention_failure`, `test_mutating_lock_conflicts_between_processes`, `test_lock_releases_after_exception`, `test_multi_run_locks_use_stable_order`. Crash injection antes/después de marker, manifest y ambos eventos; verificar bytes/IDs y reintento.

  ```python
  before = self.snapshot_archive_root()
  with self.assertRaises(ValueError):
      artifacts.prepare(self.repo, self.scope, '2.12.0', 'codex')
  self.assertEqual(before, self.snapshot_archive_root())
  run = self.prepare7()
  self.assertEqual(self.read(run / 'cierre.json')['profile_history'][0]['id'], 'S001')
  self.assertEqual([e['kind'] for e in self.events(run)][:2], ['prepare', 'profile'])
  ```

- [x] **Step 2: Observar RED.** Ejecutar artifact/trace/run_lock focalizados; fallos deben corresponder a contrato o lock ausente. Las factories históricas mantienen snapshots propios y no dependen de aceptar legacy final en nuevos runs.
- [x] **Step 3: Implementar transiciones protegidas.** Validar perfil antes de reservar carpeta; preservar intención propia de prepare/selection; aplicar precondición al trabajo y gates finales. Bloquear escrituras concurrentes de todas las mutaciones, incluidas operaciones históricas, sin escribir locks en inspect/validate. Capturar ejecutores en register con `_executors` y revalidar al retener. operation.controller no acredita actividad viva. completed continúa inmutable.
- [x] **Step 4: Observar GREEN.** Artifact/trace/run_lock y layout existentes. Confirmar que un worker arbitrario no es interceptado por el helper; la precondición del coordinador se implementa en documentación de Task 7. Help de prepare/select-profile/register muestra argumentos nuevos.
- [x] **Step 5: Commit.** `feat(archive): preparar perfiles y proteger mutaciones del review`.

### Task 3: Checkpoints provisionales recuperables

**Files:** Create `tests/test_review_checkpoints.py`; Modify `scripts/review_artifacts.py`, `tests/test_review_delivery.py`, `tests/recovery_fixtures.py`.

**Interfaces:**
- Consumes: locks/metadata/selecciones de Task 2 y validación pura Task 1.
- Produces: `checkpoint(run_dir, *, context_input, evidence_inputs=None, input_record=None, phase, gate_errors=None, max_evidence_bytes=67108864) -> dict`; CLI checkpoint --context-input, --evidence-input repetible, --input opcional, --phase, --diagnostic-input opcional y --max-evidence-bytes para elegir un límite explícito dentro de los permisos disponibles.
- Produces: pending/context.json, pending/evidence/<basename> y opcional pending/review.json/informe.md; checkpoint ID K001…/inventario/hashes. La intención/hash permite reintento propio y sustitución de su snapshot conocido, sin adoptar bytes ajenos. `_verify_files` distingue nombres/inventarios provisionales de canónicos.

- [x] **Step 1: Añadir regresiones.** `test_packet_checkpoint_without_verdict`, `test_final_checkpoint_with_source_gate_error_is_not_retained`, `test_checkpoint_retry_after_each_write_boundary`, `test_modified_or_foreign_pending_bytes_are_refused`, `test_checkpoint_duplicate_names_links_and_size_limits`, `test_pending_cannot_close_deliver_or_publish`. Reproducir !42 con schema 10 estructural válido y selección tardía importada como fuente, sin adulterar la selección del run nuevo. Se añadieron además regresiones para invalidar un informe provisional obsoleto y recuperar esa eliminación tras interrupciones.

  ```python
  result = artifacts.checkpoint(run, context_input=context,
      evidence_inputs=packets, phase='verification')
  self.assertEqual(self.read(run / 'cierre.json')['retained'], False)
  self.assertFalse((run / 'review.json').exists())
  self.assertTrue((run / 'pending/context.json').exists())
  with self.assertRaises(ValueError):
      artifacts.validate(run, require_retained=True)
  ```

- [x] **Step 2: Observar RED.** `test_new_checkpoint_without_final_invalidates_previous_provisional_report` falló inicialmente porque un checkpoint parcial heredaba el informe final previo. La regresión de recuperación confirmó después los límites de eliminación incompleta.
- [x] **Step 3: Implementar checkpoint.** Copiar solo selección regular propia/segura. Aplicar límite de contexto existente 131072 bytes, máximo 64 evidencias por checkpoint y total 16 MiB de metadata JSON/Markdown; logs/fixtures seleccionados mantienen sus bytes y el total de evidencia tiene límite configurable de 64 MiB por defecto. Para resultado final validar shape y renderizar, registrar gates pendientes aparte. Un parcial sin final no adquiere informe/veredicto artificial. Usar intención distinta a retaining: un checkpoint nunca queda confundido con promoción canónica. Los checkpoints posteriores sin resultado final invalidan el informe provisional anterior mediante una intención hash-bound recuperable.
- [x] **Step 4: Observar GREEN.** `test_review_checkpoints.py`: 11/11; `test_review_artifacts.py`: 51 aprobados/2 omitidos por permisos del host; CLI/retención/cierre focalizados aprobados. Un final provisional válido se promueve mediante los gates normales; los pendientes no permiten cierre, entrega ni publicación.
- [x] **Step 5: Commit.** `feat(archive): conservar checkpoints provisionales sin certificar cierre`.

### Task 4: Claims y transferencia de recursos

**Files:** Create `scripts/review_resource_claims.py`, `tests/test_review_resource_claims.py`; Modify `scripts/review_artifacts.py`, `scripts/review_workspace.py`, `tests/test_workspace_layout.py`.

**Interfaces:**
- Consumes: sesiones workspace 1, sidecar owner existente, locks y escrituras propias Task 2.
- Produces: `verify_claim(session_dir: Path, run_dir: Path) -> dict`; `plan_claim(session_dir: Path, run_dir: Path, manifest: dict, *, source_run=None, authority=None) -> dict` con bytes/intención esperados, sin escribir cierre. review_artifacts escribe `.review-run-owner.json` y resource_claims; los tokens de sesión permanecen privados.
- Produces: `transfer_resources(source_run, successor_run, paths, *, authority, controller) -> dict`; intención hash-bound a ambos runs y claims. CLI transfer-resources requiere paths explícitos y fuente de autoridad, sin escaneo global. Cleanup valida claim cuando existe; nuevas sesiones reclamadas no se limpian desde otro run.

- [x] **Step 1: Añadir regresiones.** `test_duplicate_resource_claim_is_refused`, `test_transfer_records_both_runs_and_claim`, `test_transfer_crash_boundaries_are_recoverable`, `test_cleanup_refuses_other_run_claim`, `test_missing_resource_does_not_prove_own_cleanup`, `test_legacy_session_adoption_requires_authority`, `test_claim_reparse_or_foreign_owner_preserves_files`. Usar dos runs y las mismas sesiones como !785, registrando continuidad verificable.

  ```python
  before = self.snapshot([source, successor, session])
  with self.assertRaises(ValueError):
      self.register_same_session_in_successor_without_transfer()
  self.assertEqual(before, self.snapshot([source, successor, session]))
  artifacts.transfer_resources(source, successor, [session],
      authority='User requested restart; source ended', controller=self.controller)
  self.assertEqual(claims.verify_claim(session, successor)['run_id'], self.run_id(successor))
  ```

- [x] **Step 2: Observar RED.** La transferencia focalizada falló al verificar el owner porque las filas archivadas omitían los campos de adopción/lineage que la verificación exigía. El test de doble claim también se corrigió para declarar el recurso en el successor y llegar a la condición bajo prueba.
- [x] **Step 3: Implementar claims/transferencia.** Comprobar ruta absoluta, sesión/owner_token, repo y run. Adquirir locks en orden; congelar intento en fuente/destino antes de cambiar claim. Estado superseded del run abierto compatible y vínculo successor; legacy se conserva y el sucesor registra adopción/lineage. En interrupción, gates de ambos runs/cleanup bloquean hasta resolver la intención propia. Sin índices de recursos, timers ni daemon.
- [x] **Step 4: Observar GREEN.** `test_review_resource_claims.py`: 7/7; `test_review_artifacts.py`: 51 aprobados/2 omitidos por privilegios de Windows; `test_workspace_layout.py`: 1/1. Transferencia repetida tras fallos inyectados conserva un solo evento y verifica el claim destino.
- [x] **Step 5: Commit.** `feat(workspaces): vincular y transferir recursos entre runs de review`.

### Task 5: Inspección, pausa y continuación

**Files:** Create `scripts/review_recovery.py`, `tests/test_review_recovery.py`; Modify `scripts/review_artifacts.py`, `tests/test_review_artifacts.py`, `tests/recovery_fixtures.py`.

**Interfaces:**
- Consumes: perfiles/checkpoints/claims y transacciones de Tasks 1–4.
- Produces: `inspect_run(run_dir: Path, *, current_inputs=None) -> dict` read-only con integrity, phase, operation, known_sources, missing_sources, resources, pending_transaction, actions/reasons y activity unknown salvo fuente comprobada.
- Produces (writer review_artifacts): `pause(run_dir, *, authority, reason, phase) -> dict`, `block(run_dir, *, source, reason, phase) -> dict`, `resume(run_dir, *, controller, authority, current_inputs) -> dict`, `recover(run_dir, *, controller, authority, current_inputs) -> dict`, `restart(run_dir, *, profile_input, controller, authority, current_inputs, transfer_paths=None) -> dict`. current_inputs contiene scope y referencias/identidades actuales verificadas; no realiza fetch ni reviews.
- CLI: inspect/pause/block/resume/recover/restart; entradas estructuradas --controller-input, --authority-input, --current-inputs y --profile-input donde corresponde. Diagnósticos conservan error y añaden code/phase/run_id/gate/inventory/actions.

- [x] **Step 1: Añadir regresiones.** `test_inspect_is_read_only_for_all_states`, `test_explicit_pause_requires_continue_authority`, `test_cross_harness_resume_preserves_prior_worker_identity`, `test_unknown_concurrent_controller_blocks_takeover`, `test_recovery_plan_does_not_dispatch_or_execute`, `test_recover_original_pending_bytes_without_backdating`, `test_tampered_run_is_not_adopted`, `test_late_profile_remains_provisional`, `test_restart_links_source_without_relabelling_results`, `test_legacy_recovery_creates_linked7_without_migration`, `test_completed_repeat_preserves_original`; se añadieron checks de scope modificado, transferencia exacta e interfaz CLI.

  ```python
  before = self.snapshot_run(run)
  outcome = recovery.inspect_run(run)
  self.assertEqual(before, self.snapshot_run(run))
  self.assertEqual(outcome['activity'], 'unknown')
  artifacts.pause(run, authority='User: stop review', reason='User stop', phase='verification')
  with self.assertRaises(ValueError):
      artifacts.resume(run, controller=other_controller, authority=None, current_inputs=current)
  ```

- [x] **Step 2: Observar RED.** La importación inicial falló porque `review_recovery` no existía. Una prueba de transferencia expuso que `register()` consultaba solo rutas ya persistidas, aunque la sesión se estaba registrando en la misma llamada; una regresión confirma el rechazo de doble claim después de aplicar el cambio.
- [x] **Step 3: Implementar diagnóstico y writer.** inspect no crea locks/eventos, no recupera y no confía en metadata dañada. resume mantiene CR solo en archive 7 íntegro/scope igual, revalida fuentes y autoridad; recover completa intenciones propias o devuelve un plan acotado sin ejecutar agentes/checks. Registro tardío queda provisional. restart emite otro CR/lineage/previous_run, admite scope nuevo dentro del mismo repositorio y no copia resultados; los recursos temporales solo se transfieren/adoptan desde sesiones explícitas con autoridad.
- [x] **Step 4: Observar GREEN.** `test_review_recovery.py`: 14/14; `test_review_artifacts.py`: 51 aprobados/2 omitidos por privilegios de symlink/junction en Windows; `test_review_checkpoints.py`: 11/11; `test_review_trace.py`: 27/27; `test_review_resource_claims.py`: 7/7; `test_workspace_layout.py`: 1/1. `py_compile`, `git diff --check` y `--help` de los seis comandos nuevos pasaron. Ningún agente o comando de build/test se ejecuta desde recover.
- [x] **Step 5: Commit.** `feat(recovery): inspeccionar pausar y continuar reviews con procedencia`.

### Task 6: Lookup acotado y elección de reporte vigente

**Files:** Modify `scripts/review_recovery.py`, `scripts/review_artifacts.py`, `tests/test_review_recovery.py`; Test integración de contract/delivery/publication.

**Interfaces:**
- Consumes: identidad/layout de archive e inspect_run; current_inputs neutral ya descubierto.
- Produces: `find_candidates(repo: Path, scope: dict, *, archive_root=None, limit=20, cursor=None, current_inputs=None) -> dict` con candidates/next_cursor/truncated; `classify_candidate(manifest: dict, retained_inputs: dict, current_inputs: dict) -> dict` puro con applicable/changed/unknown y diferencias por fuente.
- CLI lookup --repo --scope-file --current-inputs --limit --cursor. Página máximo 100; cursor se valida dentro del repositorio/grupo solicitado. Candidato explícito usa inspect por ruta/CR seleccionado, no matching por finding ID.

- [x] **Step 1: Añadir regresiones.** `test_same_scope_complete_offers_show_or_new`, `test_incomplete_offers_resume_or_restart`, `test_base_description_requirements_or_profile_change_visible`, `test_multiple_candidates_are_not_selected_by_timestamp`, `test_lookup_cursor_is_scoped_and_truncation_visible`, `test_unknown_freshness_is_not_current`, `test_show_report_has_no_review_or_cleanup_side_effects`, `test_lookup_finds_changed_head_by_stable_merge_request_reference` y `test_lookup_cli_returns_json_page_without_selecting_candidate`. Spy de filesystem/IO verifica que no abre informes ajenos al grupo ni escanea otros repositorios.

  ```python
  page = recovery.find_candidates(self.repo, self.scope_value, limit=1, current_inputs=self.current)
  self.assertEqual(len(page['candidates']), 1)
  self.assertTrue(page['truncated'])
  self.assertIsNotNone(page['next_cursor'])
  self.assertNotIn('selected_run', page)
  changed = dict(self.current, description_identity='different')
  result = recovery.classify_candidate(self.manifest, self.retained_inputs, changed)
  self.assertEqual(result['applicability'], 'changed')
  ```

- [x] **Step 2: Observar RED.** Las ocho regresiones iniciales fallaron porque `find_candidates` y `classify_candidate` aún no existían; las fallas quedaron acotadas a esas APIs. No se consultó GitLab real para establecer freshness.
- [x] **Step 3: Implementar selección acotada.** `find_candidates` deriva identidad de repositorio y grupo estable de scope/MR, pagina hasta 100 con cursor ligado a repositorio y scope, y verifica solo el cierre propio y los hashes de informes completos con lectura limitada a 8 MiB por archivo. No escanea otros repositorios ni elige un candidato. `classify_candidate` distingue applicable/changed/unknown, incluyendo base/head, fuentes, descripción, requisitos, plan, configuración y perfil cuando el coordinador aporta esas identidades. La integridad distingue manifiesto de reporte verificado y expone acciones mostrar histórico/nuevo o inspeccionar-recuperar/reiniciar. Se agregó CLI `review_artifacts.py lookup`.
- [x] **Step 4: Observar GREEN.** `test_review_recovery.py`: 24/24; `test_review_artifacts.py`: 51 aprobadas/2 omitidas por permisos Windows de symlink/junction. CLI lookup help, ejemplo CLI JSON, `py_compile` y `git diff --check` pasaron. No se alteró retain/delivery/public renderer; el conjunto completo se ejecutará en Task 7.
- [x] **Step 5: Commit.** `972f3ed feat(recovery): detectar reviews aplicables y ofrecer continuidad acotada`.

### Task 7: Routing, contratos, verificación y PR

**Files:** Create `references/archive/recovery.md`, `docs/validation/2026-10-13-profile-lifecycle-recovery.md`; Modify `SKILL.md`, `README.md`, `docs/usage.md`, `CHANGELOG.md`, `references/archive/artifacts.md`, `references/archive/lifecycle-trace.md`, `references/workflow/profiles.md`, `references/workflow/scopes.md`, `references/workflow/re-review.md`, `references/execution/workspaces.md`, `references/execution/worker-packets.md`, `references/contracts/result-contract.md`, `references/reporting/report-format.md`, `references/reporting/delivery.md`, `references/reporting/publication.md`; actualizar referencias de schema vigente solo cuando resulten contradictorias, preservando docs históricas.

**Interfaces:**
- Consumes: APIs/CLI y gates de Tasks 1–6; spec aprobada; plantilla .github/PULL_REQUEST_TEMPLATE.md.
- Produces: workflow coordinador de selección/lookup/elección/continuidad/checkpoint/retención/cierre, versión 2.12.0 pendiente, documentación reproducible y PR abierto para validación humana.

- [ ] **Step 1: Actualizar instrucciones y ejemplos.** Bootstrap scope+selección → lookup/decisión pertinente → prepare con perfil → register executors → gate de inicio. Cambios select-profile antes de utilizarlos; checkpoint en tandas/fallo/pausa. Recovery se carga solo ante candidatos/interrupción; explicitar show/nuevo/continuar/reiniciar como lenguaje natural, sin inventar flags ejecutables del instalador. Ejemplos JSON/CLI siguen interfaces comunes. Informe privado separa juicio/conservación/cumplimiento/cleanup y perfil inicial/efectivo. Público conserva audiencia. SKILL breve, detalles en referencias; README describe utilidad y enlaza docs.
- [ ] **Step 2: Verificar integración.** Ejecutar `python -B -X utf8 -m unittest discover -s tests -v`; expectativa exit 0 y solo omisiones reales documentadas. AST de Python modificado/nuevo; enlaces relativos de Markdown actual, help de todos los subcomandos nuevos y helpers contract/delivery; `git diff --check`; `skill-creator/scripts/quick_validate.py <worktree>` si admite frontmatter existente. No modificar frontmatter útil por una limitación del validador. Persistir RED/GREEN y baseline separado en validation.
- [ ] **Step 3: Revisión final.** Un contexto independiente revisa la rama completa contra spec/plan y cinco Review Focus; ejecución nativa conserva el reviewer más capaz según herramientas disponibles. Usar fixtures reproducibles/acceso mínimo, no artifacts reales ni un reviewer por gate. Contrastar feedback, corregir causas con regresiones y repetir pruebas afectadas; una suite integrada nueva si cambia runtime. Documentar pendientes reales antes de publicar el PR.
- [ ] **Step 4: Commit de documentación/validación.** Git safety/identidad y stage explícito. `docs(review): documentar continuidad perfiles y gates de recuperación`; actualizar checkboxes a hechos observados, sin atribuir suite base al código nuevo.
- [ ] **Step 5: Publicar rama y crear PR.** Push normal de feat/review-recovery-lifecycle, cuerpo por archivo siguiendo plantilla, describir problemas/resultado/contratos 7 y 10, omisiones y visor externo. Adjuntar URL con attach_artifact y comprobar base/head/cuerpo remoto. Conservar worktree para feedback; esperar revisión humana del PR antes de merge/tag/release y cleanup.

## Autorrevisión y handoff

- Cobertura: spec §1–2 en Task 1/2; §3 en Task 2; §4 en Task 3; §6 en Task 4; §5 en Task 5; §7 en Task 6; §8–9 en Task 7.
- Interfaces: puro vs IO vs escritor durable delimitados; recovery/claims no escriben cierre por su cuenta. Cross-run transfer emplea locks ordenados y la misma intención verificable.
- Compatibilidad: read históricos y fixtures de emisión legacy separados de prepare actual; archive 7 exige selección/final 10, sin escape por schema antiguo. Trace/packet/workspace 1 no adquieren campos nuevos.
- Proporción: siete entregables con un ciclo TDD/commit propio y una única revisión independiente final. Tests mantienen escenarios/efectos; cuerpos de funciones no están transcritos.
- Estado: plan aprobado y en ejecución nativa. Tasks 1–5 implementadas y verificadas; Tasks 6–7 siguen pendientes. La revisión de la rama y el PR se realizan al completar Task 7.
