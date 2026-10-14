# Review Recovery Corrections Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolver los defectos confirmados del PR #19 y demostrar que las secuencias de cambio de perfil, recuperación, transferencia y cierre conservan sus garantías.

**Architecture:** Mantener validación pura separada del escritor durable. El contexto/archivo preservan registro de asignaciones e inputs; las operaciones conservan intenciones verificables y recibos. Unificar appraisal de vigencia y contrastar planes contra todo el trabajo observado, con reintentos de restart y cleanup que no dependan de memoria del coordinador.

**Tech Stack:** Python 3.10+ estándar, unittest, Git, JSON/Markdown y locks Windows/POSIX; sin dependencias nuevas.

**Spec:** [2026-10-14-review-recovery-corrections-design.md](../specs/2026-10-14-review-recovery-corrections-design.md), propuesta pendiente de aprobación junto con este plan. La creación de estos documentos no autoriza implementación.

## Global Constraints

- Mantener 2.12.0 pendiente, archive schema **7**, final schema **10**, trace **1**, packet **1** y workspace manifest **1**. Los campos privados adicionales pertenecen al contrato 7 aún no publicado; documentarlos antes del merge.
- Conservar lectura y comportamiento histórico de archives **1–6** y resultados **1–9**, sin migración ni campos nuevos escritos retroactivamente en esos archives. Un archivo completo permanece inmutable.
- Python **3.10+**, biblioteca estándar, Git y unittest; sin dependencias nuevas, daemon, polling, métricas, índice global ni un agente por hallazgo.
- Cambios en el mismo worktree/rama/PR. No tocar artifacts reales, configuración de harness, el visor ni main. No merge/tag/release durante la implementación.
- Los módulos de validación no escriben archivos. `review_artifacts.py` sigue siendo el escritor del archivo durable; workspace cleanup elimina exclusivamente sus recursos verificados y comunica observaciones al helper.
- Ninguna ruta ausente acredita por sí sola cleanup. Un archivo temporal con un nombre parecido no acredita ownership. No reconstruir dispatch, identidad, tiempos de ocurrencia ni autoridad desde texto libre.
- La recuperación de una transacción no acredita vigencia ni cumplimiento del perfil. Cambiar scope/base/head/snapshot requiere otro run.
- Base de correcciones: `b758c559143776b610469e2103a24be48ef2c182`; rama `feat/review-recovery-lifecycle`, worktree `.worktrees/review-recovery-lifecycle`, PR #19.
- Ejecución nativa en esta sesión, conforme al método ya elegido, únicamente tras aprobación de spec/plan. Una revisión independiente final en el HEAD corregido; no lanzar revisores por tarea.
- Seguimiento por checkboxes e inline status si el harness no dispone de todo. Una tarea en progreso; registrar gates/resultados reales, no marcar aprobación por haber escrito documentos.

## Review Focus

1. Crash dentro de fsync/replace, staging parcial o nombre imitado: Task 1 distingue intención propia de archivos ajenos y prueba recuperación sin adoptar bytes no comprometidos.
2. Plan/contexto finales regenerados después de un downgrade: Task 2 preserva filas iniciadas aun si el emisor las omite en ambos, y mantiene extended automático adquirido con mínimo 4.
3. A→B→register(B)→C→cleanup→close→close y transferencia parcial: Tasks 4–6 y Task 7 ejercitan historial entrante/saliente, exclusión y recibos repetidos con el mismo request.
4. HEAD idéntico con descripción/spec cambiado, fuentes desconocidas o 70 outputs: Task 3 exige appraisal uniforme y separa integridad de vigencia sin contar outputs como inputs.
5. Checkpoint pendiente + HEAD movido + sesión ausente + controlador/harness distinto: Tasks 5–7 permiten mantenimiento/reinicio atribuible sin certificar cleanup, memoria o cumplimiento ficticio.

---

## Preparación y archivos

- [x] Leer comentario completo del PR #19 y contrastar con `b758c55`.
- [x] Reproducir cuatro bloqueantes y escenarios adicionales en repositorios sintéticos; limpiar scratch y comprobar worktree limpio.
- [x] Escribir spec y este plan por solicitud expresa del usuario.
- [x] Obtener aprobación escrita de ambos documentos antes de implementar.

| Archivo | Responsabilidad de la corrección |
|---|---|
| `scripts/review_artifacts.py` | Preflight, escritor durable, staging/intenciones, registro/contexto, cleanup/restart y CLI |
| `scripts/review_run_lock.py` | Identidad canónica y exclusión; no determina propiedad del archivo |
| `scripts/review_profiles.py`, `scripts/review_execution.py`, `scripts/review_contract.py` | Tipos, autoridades, registro observado y obligaciones por selección |
| `scripts/review_inputs.py` (nuevo) | Normalizar/comparar inputs, puro; sin lecturas ni selección de candidatos |
| `scripts/review_recovery.py` | Adaptar inspect/lookup a appraisal común e integridad/disponibilidad separadas |
| `scripts/review_resource_claims.py` | Preflight de claims, comparación exacta, historial de transferencias y recibos |
| `scripts/review_workspace.py` | Cleanup bajo lock del propietario, comunicar intención/observación durable al helper |
| `scripts/review_restart.py` (nuevo) | Modelo puro de petición/intención/reserva de restart; sin escritor paralelo |
| `tests/recovery_fixtures.py` | Fixtures comunes actualizadas, inputs completos explícitos y contexto con registro |
| Tests existentes de artifacts/profiles/execution/claims/recovery/contract | Regresiones de causas y compatibilidad histórica |
| `tests/test_review_atomic_recovery.py` (nuevo) | Fallos dentro de escritura, staging y límites de lectura |
| `tests/test_review_inputs.py` (nuevo) | Forma común, fuentes/identidades y appraisal |
| `tests/test_review_restart.py` (nuevo) | Reserva durable, reintentos y concurrencia de reinicios |
| `tests/test_review_recovery_sequences.py` (nuevo) | Secuencias completas entre módulos y continuidad tras interrupciones |
| Referencias de archive/execution/workflow/reporting y `docs/usage.md` | Contratos y ejemplos operativos acordes con el código |
| `docs/validation/2026-10-14-review-recovery-corrections.md` (nuevo) | RED/GREEN, suite nueva, plataformas, feedback y pendientes reales |

No extraer todo `review_artifacts.py` ni crear un framework de workflows. Los dos módulos nuevos tienen fronteras puras y mantienen el helper como único escritor.

### Valores e interfaces comunes

- `execution_plan` del contexto y `assignment_registry` del archivo usan filas `{id, role, independent, required, reference, selection_id, superseded_by}`. Registro append-preserving; una fila no iniciada puede recibir sustitución validada, nunca desaparecer.
- Inputs comunes: `{scope, sources, source_set_complete?, description_identity?, requirements_identity?, plan_identity?, configuration_identity?, profile?}`. Scope/sources obligatorios; fuentes actuales ≤64; `source_set_complete` omitido significa unknown. `review_inputs` guarda la captura externa en archive 7, no todos sus outputs.
- Appraisal: `{applicability: applicable|changed|unknown, differences: [{field, status, reason}]}`. Inspect convierte applicable en freshness verified; mutadores aplican su gate, no interpretan igualdad de scope como aplicabilidad completa.
- Nuevas selecciones explícitas exigen autoridad/fuente. Obligación acquired extended automático: discovery mínimo 4; explícito sin obligaciones anteriores: mínimo 2. Máximo 32 selecciones, IDs S001… preservados.
- Transferencias: `resource_transfers` con registros por `transfer_id`, máximo 64 y una pendiente; lectura compatible del slot anterior. Replay compara petición completa. No transferir parcialmente claims activos presentes ni runs retaining/closing/complete.
- Recibos: `{session_id, run_id, claim_id, claim_sha256}`; `cleanup_receipts` y `resource_cleanup` conservan observación/intención privada 7. Close inline admite `released_claims`; CLI añade `--released-claims-input`.
- Restart intent privado schema 1: `{operation_id, request_digest, source_run, source_manifest_sha256, request, successor, status}`. Request contiene selección, controller, authority, current_inputs, transfer_paths y harness observado; successor contiene run_dir, run_id, owner_id, created_at. Se conserva en `.restart-intents/<source-key>/<request-digest>.json`, fuera del run original, bajo su scope group.
- `context10(record, *, execution_plan=None, review_inputs=None)` y `current_inputs(scope, sources=None, *, source_set_complete=False, **identities)` se definen en `tests/recovery_fixtures.py`. Factories de tests positivos declaran explícitamente captura completa; no agregar campos al producir fixtures 1–6.

### Comandos de prueba

En los comandos `python` representa `C:/Users/Developer.INSCORSOF2/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`; PowerShell usa `& '<ruta>'`. Siempre `-B -X utf8`.

No reutilizar el temp predeterminado del sandbox ni una ruta tan larga que Git no pueda crear worktrees. Usar un directorio temporal corto, nuevo y propiedad de este ciclo dentro de la raíz autorizada de skills; verificar su ruta antes de limpieza. El wrapper local ignorado `.superpowers/sdd/review-recovery-lifecycle/run-unittest.py` puede ajustarse solo para apuntar a ese scratch. No versionarlo ni cambiar configuración global. Guardar logs de pruebas allí; al terminar conservar el resumen en validation y retirar recursos temporales propios.

Para cada patrón indicado: `python -B -X utf8 .superpowers/sdd/review-recovery-lifecycle/run-unittest.py discover -s tests -p <patrón> -v`. Un RED válido falla por el defecto concreto; errores del sandbox/fixture no son evidencia del producto.

### Task 1: Locks, atomic_write e inventario de checkpoint

**Feedback:** F001, F002, F003, F004, F009.

**Files:** Modify `scripts/review_run_lock.py`, `scripts/review_artifacts.py`; Create `tests/test_review_atomic_recovery.py`; Test `tests/test_review_run_lock.py`, `tests/test_review_checkpoints.py`, `tests/test_review_artifacts.py`.

**Interfaces:**
- Consumes: `_load_run`, safe_path, marker/hash e intención de checkpoint existentes.
- Produces: `_owned_run_locks(run_dirs: list[Path], *, reservation: dict | None = None) -> ContextManager`; valida ownership antes de locks, recarga después y admite solo una reserva de restart propia para un destino aún preparándose.
- Produces: `atomic_write(path: Path, data: bytes, *, staging_path: Path | None = None) -> None`; limpieza ordinaria en finally, error original preservado. `read_json(path: Path, *, max_bytes: int | None = None) -> object` conserva el rechazo de claves duplicadas/nonfinite y admite el límite antes de parsear.
- Produces: `checkpoint_transaction.staging`, mapa destino relativo → `{name, sha256}` exactos dentro del run. `_verify_pending` reconoce ese inventario; `_checkpoint_commit` usa sus staging. `read_bounded(path: Path, limit: int) -> bytes` verifica regularidad/tamaño y lee como máximo limit+1.

- [x] **Step 1: Añadir regresiones.** `test_alias_83_conflicts_between_processes`, `test_foreign_run_rejection_creates_no_locks`, `test_fsync_and_replace_failure_remove_owned_staging`, `test_crash_staging_recovery_requires_exact_intent`, `test_foreign_staging_pattern_is_preserved`, `test_casefold_collision_rejected_before_intent`, `test_checkpoint_input_size_checked_before_read`, `test_growing_input_cannot_exceed_read_budget`. Snapshot antes/después y destino viejo intacto.

  ```python
  before = self.snapshot(run)
  with patch.object(artifacts.os, 'replace', side_effect=PermissionError('replace failed')):
      with self.assertRaises(PermissionError):
          artifacts.atomic_write(target, b'new bytes')
  self.assertEqual(target.read_bytes(), b'old bytes')
  self.assertEqual(list(target.parent.glob('.*.tmp')), [])
  self.assertEqual(before, self.snapshot(run))
  ```

- [x] **Step 2: Observar RED.** Ejecutar atomic_recovery, run_lock y checkpoints; reproducir el temporal de F003 y la adquisición por alias F001. Si 8.3 no existe en el host, registrar skip y mantener control de normalización más prueba real disponible; no fabricar una aprobación de plataforma.
- [x] **Step 3: Implementar.** Resolver identidad canónica, preflight de ownership y staging exacto; deduplicar casefold antes de intención y usar lecturas acotadas para contexto/evidencia/final. Reconocer staging 7 anterior solo cuando su intención lo declara; no limpieza por regex. Adaptar wrappers de fault injection para aceptar el keyword de staging.
- [x] **Step 4: Observar GREEN.** Repetir los cuatro patrones. Probar reintento de checkpoint/recover tras fsync/replace y crash; foreign staging queda intacto y el run no certifica retención. Inyectar también fallo de unlink: error original y staging conservado identificable.
- [x] **Step 5: Commit.** Stage de archivos exactos; `fix(recovery): preservar checkpoints ante fallos de escritura y alias de rutas`.

### Task 2: Registro de asignaciones y obligaciones adquiridas

**Feedback:** F010, F011, F015.

**Files:** Modify `scripts/review_profiles.py`, `scripts/review_execution.py`, `scripts/review_contract.py`, `scripts/review_artifacts.py`, `tests/recovery_fixtures.py`; Test `tests/test_review_profiles.py`, `tests/test_review_execution_policy.py`, `tests/test_review_artifacts.py`.

**Interfaces:**
- Consumes: Task 1 exclusión y escritor; filas comunes de ejecución e historial de selección.
- Produces: `merge_assignment_registry(previous: list[dict], incoming: list[dict], history: list[dict], trace_events: list[dict]) -> list[dict]`, puro en review_profiles; rechaza eliminación/cambio de identidad de trabajo iniciado.
- Produces: `validate_profile_execution(record: dict, trace_events: list[dict] | None = None, *, assignment_registry: list[dict] | None = None) -> list[str]`; fuentes de contexto/archivo/plan se contrastan en `_execution_gate` y `validate_execution_sources`.
- Produces: context.execution_plan, archive.assignment_registry y helpers de fixture comunes. Register guarda el registro antes de trabajo por asignación; checkpoint/retain lo preservan y seleccionan sus fuentes históricas pertinentes.

- [x] **Step 1: Añadir regresiones.** `test_downgrade_omits_started_assignments_from_final_and_context`, `test_started_assignment_identity_cannot_change`, `test_completed_result_and_brief_are_retained_after_transition`, `test_focused_to_deep_preserves_coordinator_without_counting_it_as_fresh`, `test_prior_verification_preserved_but_final_batch_requires_new_verifier`, `test_explicit_same_profile_requires_authority`, `test_acquired_automatic_extended_minimum_survives_explicit_selection`, `test_generic_start_is_not_fabricated_assignment`, `test_nonhashable_selection_fields_return_errors`. El caso principal conserva D1/D2 en registro/traza aunque el final intente quedarse solo con D3/V3.

  ```python
  final['coverage']['execution']['plan'] = later_focused_plan
  context['execution_plan'] = later_focused_plan
  with self.assertRaisesRegex(ValueError, 'started assignment'):
      artifacts.retain(run, input_file=self.write('final.json', final),
                       context_input=self.write('context.json', context),
                       evidence_inputs=packets)
  self.assertEqual(self.read(run / 'cierre.json')['assignment_registry'], original_registry)
  ```

  Assert adicional: guardar un extended automático adquirido con solo dos discoveries falla aun con autoridad posterior; los resultados válidos originales cuentan sin redispatch.
- [x] **Step 2: Observar RED.** Las regresiones nuevas se añadieron sobre fixtures que antes aceptaban la omisión de asignaciones; la suite focalizada se usó para detectar y ajustar una fixture cuyo downgrade automático tampoco cumplía la regla de evidencia. No se atribuye a ese fallo de fixture el defecto de producto.
- [x] **Step 3: Implementar.** Tipar campos antes de lookup/set; registrar/merger filas y resolver eventos/briefs contra registro completo. Calcular obligaciones adquiridas por epoch más selección final: contar solo discoveries que satisfacen la independencia requerida y una verificación efectiva posterior a la tanda final, conservando filas de otras epochs sin aplicarles retroactivamente la cardinalidad final. Exigir autoridad para selecciones explícitas posteriores incluso si solo cambia source; preservar política explícita inicial y IDs. No contar eventos generales como revisores nuevos. Un downgrade automático requiere nueva fuente y razón basada en evidencia; urgencia, coste, capacidad o ausencia de hallazgos no son justificación.
- [x] **Step 4: Observar GREEN.** `test_review_profiles.py` 25/25; `test_review_execution_policy.py` 29/29; `test_review_recovery.py` 25/25; `test_review_artifacts.py` 54, 52 aprobadas y 2 omitidas por permisos de symlink/junction en Windows; py_compile y `git diff --check` aprobados. Compatibilidad legacy permanece cubierta por las suites existentes.
- [x] **Step 5: Commit.** `fix(profiles): conservar asignaciones iniciadas y obligaciones de cada selección`.

### Task 3: Inputs comunes, vigencia y fronteras de diagnóstico

**Feedback:** F008, F022, F023, F024, F026, F034, F035.

**Files:** Create `scripts/review_inputs.py`, `tests/test_review_inputs.py`; Modify `scripts/review_recovery.py`, `scripts/review_artifacts.py`, `scripts/review_resource_claims.py`, `tests/recovery_fixtures.py`; Test `tests/test_review_recovery.py`, `tests/test_review_contract.py`.

**Interfaces:**
- Consumes: Task 2 contexto preservado; contratos scope/hash actuales.
- Produces: `normalize_inputs(raw: dict, *, caller: bool = True) -> dict`, `compare_inputs(retained: dict | None, current: dict) -> dict` en review_inputs; sin IO. caller limita fuentes a 64; lectura de inventarios retenidos no reutiliza ese límite para clasificar integridad.
- Produces: `validate_current_inputs(current_inputs, manifest, *, require_same_scope=True, compare_sources=True, require_applicable=False) -> dict` como adaptador; devuelve los campos normalizados de inputs, sin añadir metadata derivada a su forma. Inspect/recover obtienen el appraisal de compare_inputs. `require_applicable=True` rechaza changed/unknown.
- Produces: prepare `current_inputs=None` y CLI `--current-inputs`; register puede capturar context.review_inputs antes del trabajo. Archive.review_inputs guarda inputs externos; `_execution_gate` verifica sus hashes seleccionados. Inspect/lookup separan appraisal, hashes y recursos.
- Produces: `_workspace` convierte ReviewError a ValueError con causa; retain valida estructura antes de pre-gates. inspect usa run_id opcional para schemas 1–2.

- [x] **Step 1: Añadir regresiones.** `test_same_inputs_shape_for_lookup_inspect_resume`, `test_empty_sources_without_completeness_are_unknown`, `test_explicit_complete_empty_input_set_is_applicable`, `test_known_description_identity_omitted_is_unknown`, `test_unknown_inputs_cannot_resume`, `test_internal_outputs_are_not_external_sources`, `test_changed_description_and_spec_at_same_head`, `test_seventy_retained_outputs_do_not_invalidate_candidate`, `test_unknown_legacy_inputs_remain_unknown`, `test_nonobject_final_retention_is_structured_error`, `test_claim_owner_error_becomes_invalid_preserve`, `test_schema1_and_schema2_inspect_without_run_id`.

  ```python
  current = {'scope': manifest['scope'], 'sources': {}}
  self.assertEqual(review_inputs.compare_inputs(manifest['review_inputs'], current)['applicability'], 'unknown')
  current['source_set_complete'] = True
  result = recovery.find_candidates(self.repo, manifest['scope'],
                                   archive_root=self.output, current_inputs=current)
  self.assertEqual(result['candidates'][0]['applicability'], 'applicable')
  self.assertEqual(recovery.inspect_run(run, current_inputs=current)['freshness']['status'], 'verified')
  ```

  La prueba usa el mismo fixture completo sin inputs externos; ninguna aprobación se obtiene copiando context/briefs/results al mapa del llamador.
- [x] **Step 2: Observar RED.** Las regresiones reprodujeron la importación aún ausente del módulo común, la omisión de identidad de descripción marcada como vigente, inputs incompletos rechazados por forma distinta, confusión de outputs internos con fuentes, retención no-object como `AttributeError` y metadata de runs antiguos sin `run_id`.
- [x] **Step 3: Implementar.** Unificar normalización/comparación y la captura de fuentes externas antes de trabajo; legacy sin captura queda unknown. Validar cada shape antes de pre-gates y convertir excepciones específicas en las fronteras. Mantener JSON de error compatible, sin catch genérico que oculte interrupciones.
- [x] **Step 4: Observar GREEN.** `test_review_inputs.py` 7/7; recovery 34/34; checkpoints 11/11 más regresión de hash de fuente 1/1; artifacts 54 con 52 aprobadas y 2 omitidas por permisos Windows; resource claims 8/8; contract 34/34. `py_compile` y `git diff --check` se repetirán antes del commit.
- [ ] **Step 5: Commit.** `fix(review): unificar vigencia de inputs y diagnósticos de archivos históricos`.

### Task 4: Claims y transferencias repetibles

**Feedback:** F006, F018, F019, F020, F021, F029, F031.

**Files:** Modify `scripts/review_artifacts.py`, `scripts/review_resource_claims.py`; Test `tests/test_review_resource_claims.py`, `tests/test_review_recovery.py`, `tests/test_review_artifacts.py`.

**Interfaces:**
- Consumes: Tasks 1–3 locks, contexto/inputs y fronteras de error.
- Produces: `plan_resource_registration(paths: list[Path], manifest: dict, *, authority: str | None = None) -> list[dict]`, verificación read-only de bootstrap/owned/foreign; ejecutada antes de mutar prepare/register/retain. Legacy 1–6 omite claims y conserva su registro histórico.
- Produces: `resource_transfers` y `normalize_transfer_history(manifest: dict) -> list[dict]`; acepta lectura del slot 7 previo, sin escritura automática. Mismo RT/petición exacta es replay; una transferencia nueva usa otro RT.
- Produces: transfer_resources existente con preflight completo y todas las rutas activas presentes; tipos/valores comunes. `_claim_row`/plan_claim conservan transfer_id ya registrado y verify_claim permanece consistente.

- [x] **Step 1: Añadir regresiones.** `test_legacy6_workspace_register_keeps_historical_fields`, `test_prepare_and_retain_refuse_foreign_claim_before_mutation`, `test_register_preflights_all_resources_before_claiming_any`, `test_register_after_incoming_transfer_is_idempotent`, `test_second_outgoing_transfer_preserves_incoming_history`, `test_partial_transfer_is_refused_without_mutation`, `test_completed_transfer_changed_request_is_conflict`, `test_transfer_rejects_retaining_and_closing_runs`, `test_transfer_rejects_conflicting_previous_run`, `test_transfer_history_limit_is_checked_before_mutation`.

  ```python
  artifacts.transfer_resources(a, b, [session], authority=authority, controller=controller)
  artifacts.register(b, [], context_input=context_b)
  artifacts.transfer_resources(b, c, [session], authority=authority, controller=controller)
  self.assertEqual(claims.verify_claim(session, c)['run_id'], self.read(c / 'cierre.json')['run_id'])
  self.assertEqual(len(self.read(b / 'cierre.json')['resource_transfers']), 2)
  ```

- [x] **Step 2: Observar RED.** Las regresiones iniciales reprodujeron la pérdida del ID entrante, la transferencia parcial aceptada, el replay con autoridad distinta aceptado, la falta de límite, el lineage ajeno aceptado y el error al registrar workspaces en archives 1–6. Una primera versión de la prueba encadenada también mostró que las rutas deben compararse con normalización de Windows.
- [x] **Step 3: Implementar.** Centralizar preflight de todas las rutas, separar historial entrante/saliente, validar replay completo y lineage. Rechazar parcial y estados retaining/closing antes de intención; transferir bajo ambos locks con hashes y recuperación existente. El registro conserva el `transfer_id` de entrada y no edita sidecars ajenos.
- [x] **Step 4: Observar GREEN.** `test_review_resource_claims.py`: 18/18; `test_review_recovery.py`: 34/34; `test_review_artifacts.py`: 54/54 (2 skips de permisos de junction/symlink). Replays, transferencias encadenadas, legacy singular, preparación/registro/cierre y límites pasan; `py_compile` y `git diff --check` pasan.
- [ ] **Step 5: Commit.** `fix(workspaces): preservar ownership y reintentos de transferencias encadenadas`.

### Task 5: Recibos de cleanup y cierre idempotente

**Feedback:** F005, F017, F033.

**Files:** Modify `scripts/review_artifacts.py`, `scripts/review_workspace.py`, `scripts/review_resource_claims.py`, `scripts/review_recovery.py`; Test `tests/test_review_resource_claims.py`, `tests/test_review_workspace.py`, `tests/test_review_artifacts.py`, `tests/test_review_recovery.py`.

**Interfaces:**
- Consumes: Task 4 claims/historial y locks; appraisal de Task 3.
- Produces: `begin_resource_cleanup(run_dir: Path, session_dir: Path) -> dict`, `finish_resource_cleanup(run_dir: Path, observation: dict) -> dict`, `recover_resource_cleanup(run_dir: Path) -> dict` en review_artifacts. Los tres preservan intención/recibos bajo lock; workspace cleanup los usa sin escribir cierre por separado.
- Produces: resource_cleanup/cleanup_receipts privados; close `released_claims=None` y CLI `--released-claims-input`, en combinación con la vía inline. Sin recibos explícitos usa los durables observados; no los fabrica.
- Produces: validate_release_observation acepta replay de fila released solo con recibo exacto; disponibilidad missing_unknown no se interpreta como released. Inspect y mutadores comparten diagnóstico/condiciones.

- [ ] **Step 1: Añadir regresiones.** `test_cleanup_records_receipt_before_return`, `test_cleanup_claim_requires_run_dir`, `test_close_inline_uses_durable_receipt`, `test_close_same_cleanup_observation_after_interruption_and_complete`, `test_cleanup_crash_after_delete_recovers_own_intent`, `test_missing_without_receipt_remains_unknown`, `test_missing_resource_allows_linked_restart_without_transfer`, `test_cleanup_conflicts_with_transfer`, `test_altered_replay_receipt_refused`.

  ```python
  review_workspace.cleanup(argparse.Namespace(manifest=str(session / 'manifest.json'), run_dir=str(run)))
  self.assertFalse(session.exists())
  self.assertTrue(self.read(run / 'cierre.json')['cleanup_receipts'])
  artifacts.close(run, cleanup='complete')
  before = self.snapshot(run)
  artifacts.close(run, cleanup='complete')
  self.assertEqual(self.snapshot(run), before)
  ```

- [ ] **Step 2: Observar RED.** Ejecutar resource_claims/workspace/artifacts/recovery. Confirmar F005/F033: recibo aplicado debe poder repetirse sin cambiarlo; la falta de receipt no se corrige omitiendo ese campo.
- [ ] **Step 3: Implementar.** Guardar intención previa a eliminación y recibo posterior con el mismo lock; validar registrations para recovery de cleanup. Close consume observación durable, conserva gate fuente/ownership en replay y no pierde recibos durante retaining. Ausencia sin intención permanece diagnosticada y permite únicamente las acciones condicionadas de la spec.
- [ ] **Step 4: Observar GREEN.** Inyectar interrupción antes/después de eliminación y de review/informe/manifest; replay mantiene bytes completos. Probar dueño distinto, ruta reaparecida modificada y claim transferred cuyo sidecar confirma otro propietario: preservar o excluir del cleanup del origen, nunca borrarlo.
- [ ] **Step 5: Commit.** `fix(cleanup): conservar recibos de liberación y permitir reintentar el cierre`.

### Task 6: Restart transaccional, adopción y takeover

**Feedback:** F007, F025, F027, F028, F032.

**Files:** Create `scripts/review_restart.py`, `tests/test_review_restart.py`; Modify `scripts/review_artifacts.py`, `scripts/review_recovery.py`; Test `tests/test_review_recovery.py`, `tests/test_review_harness.py`.

**Interfaces:**
- Consumes: Tasks 1–5 reservations/locks, inputs, transfer/cleanup y disponibilidad; revisión histórica sin mutación.
- Produces: `normalize_restart_request(profile_input: dict, controller: dict, authority: str, current_inputs: dict, transfer_paths: list[str], harness: dict) -> dict`, `build_restart_intent(source: dict, request: dict, successor: dict) -> dict`, `validate_restart_intent(intent: dict) -> list[str]` en review_restart, puras.
- Produces: `_prepare_from_restart_intent(intent_path: Path) -> str`, privado en review_artifacts; no flag público para forzar IDs. La reserva se valida contra intención/ownership y se reutiliza tras crash, nunca adopta un directorio ajeno.
- Produces: `_restart_intent_path(source_run: Path, source_manifest: dict, request: dict) -> Path`, privado y estable por identidad de origen/digest de petición, no por la fecha del reintento ni hashes de manifests que la misma operación actualiza.
- Produces: `_active_restart_operation(source_run: Path, source_manifest: dict) -> dict | None`, lectura del descriptor local `active.json` de ese origen; verifica ownership e intent/hashes autorizados. Los mutadores lo consultan bajo lock y solo el replay/recover de la operación exacta puede continuar mientras esté pendiente. La retirada del descriptor después de finalizar también es reintentable.
- Produces: restart existente añade `harness='unknown', harness_id=None, harness_source=None`, con argumentos CLI correspondientes; defaults resuelven el entorno, no los valores del origen. El raw no observado permanece unknown. Su operación local usa la forma de intención común y mantiene source→successor coherente.
- Produces: `_takeover_controller(run: Path, manifest: dict, marker: dict, controller: dict, authority: str | None) -> tuple[dict, dict]`, compartido por resume/recover; cambio exige autoridad y evento. Un source complete no se modifica.

- [ ] **Step 1: Añadir regresiones.** `test_restart_link_failure_retry_reuses_reserved_successor`, `test_two_process_restarts_have_one_successor`, `test_restart_each_reservation_boundary`, `test_pending_restart_blocks_other_source_mutations`, `test_active_descriptor_retry_after_commit_and_retirement`, `test_adopt_context_object_before_successor_creation`, `test_pending_checkpoint_with_changed_head_can_restart`, `test_recover_owned_bytes_with_changed_inputs_cannot_continue`, `test_takeover_recorded_by_recover`, `test_restart_uses_current_harness_source`, `test_complete_and_legacy_source_bytes_unchanged`, `test_foreign_reserved_target_is_not_adopted`.

  ```python
  with patch.object(artifacts, '_link_restart', side_effect=OSError('link interrupted')):
      with self.assertRaises(OSError):
          artifacts.restart(source, **request)
  result = artifacts.restart(source, **request)
  successors = [p for p in self.output.rglob('cierre.json')
                if self.read(p).get('previous_run') == str(source)]
  self.assertEqual(len(successors), 1)
  self.assertEqual(result, str(successors[0].parent))
  self.assertEqual(artifacts.restart(source, **request), result)
  ```

  Helpers de la prueba usan el request/intent exactos, no un barrido global. Para otra petición tras un sucesor existente: conflict o nuevo reinicio explícito desde ese sucesor, sin reemplazar un intent completado ni crear huérfanos.
- [ ] **Step 2: Observar RED.** Ejecutar restart/recovery/harness. Reproducir F007/F032 y el círculo de F025 antes de implementar; una TypeError tras prepare no se considera adopción parcial aceptable.
- [ ] **Step 3: Implementar.** Preflight completo, intención/reserva durable y finalización del destino exacto bajo locks ordenados. Adoptar objeto mediante `_input_object`, sin dict-as-path. Preservar provisionales; completar mantenimiento de transacción con inputs movidos solo devuelve changed/restart. Fuente con ownership válido pero evidencia no verificable puede servir únicamente de vínculo de un nuevo run, sin copia/promoción ni reescritura del original. Registrar takeover real y harness vigente.
- [ ] **Step 4: Observar GREEN.** Fault injection antes/después de intención/reserva/prepare/adopción/transfer/link y entre dos procesos. Cada replay tiene un sucesor o un conflicto conservador; no aumenta run_count por error. Inputs cambiados/missing_unknown no permiten transferencia ficticia ni ready engañoso.
- [ ] **Step 5: Commit.** `fix(restart): reutilizar sucesores tras interrupciones y registrar el controlador actual`.

### Task 7: Secuencias completas, documentación y actualización del PR

**Feedback:** F012, F013, F014; aceptación integrada de los 33 IDs anteriores.

**Files:** Create `tests/test_review_recovery_sequences.py`, `docs/validation/2026-10-14-review-recovery-corrections.md`; Modify `references/archive/artifacts.md`, `references/archive/recovery.md`, `references/archive/lifecycle-trace.md`, `references/execution/workspaces.md`, `references/workflow/profiles.md`, `references/contracts/result-contract.md`, `references/reporting/delivery.md`, `docs/usage.md`, `SKILL.md`, `CHANGELOG.md`, este plan; Test `tests/test_reference_layout.py`, `tests/test_review_delivery.py`.

**Interfaces:**
- Consumes: APIs/contratos/CLI reales de Tasks 1–6 y plantilla `.github/PULL_REQUEST_TEMPLATE.md`.
- Produces: secuencias integradas, documentación reproducible, nueva evidencia y PR #19 actualizado; no merge/release ni cleanup del worktree en este paso.

- [ ] **Step 1: Añadir regresiones de aceptación.** `test_a_b_register_c_retain_cleanup_close_replay`, `test_interrupted_checkpoint_changed_head_missing_session_new_harness_restart`, `test_documented_archive7_commands_end_to_end`, `test_full_contains_lineage_brief_keeps_summary_and_source_link`. Los tests CLI leen datos producidos por helpers, no construyen recibos para fingir cleanup.

  ```python
  # Flujo íntegro con inputs externos capturados y cada transición observada.
  self.assertEqual(artifacts.validate(c, require_complete=True)['state'], 'complete')
  self.assertEqual(self.read(c / 'cierre.json')['controller'], current_controller)
  self.assertEqual(self.read(c / 'cierre.json')['harness_id'], current_harness_id)
  self.assertEqual(self.events(a)[:len(events_a_before)], events_a_before)
  self.assertEqual(self.snapshot(legacy_complete), original_source_bytes)
  ```

- [ ] **Step 2: Observar RED y corregir integración.** Ejecutar recovery_sequences antes de ajustar referencias; fallos solo por contrato/CLI/secuencia reales. Completar conexiones omitidas sin debilitar validadores; repetir patrones afectados hasta GREEN.
- [ ] **Step 3: Actualizar documentación.** Registrar todos los campos/ejemplos de register/select-profile/staging/inputs/transfer/cleanup/restart; explicar límites 32/64 y defaults desconocidos. profiles aclara downgrade justificado. La promesa de historial completo es de full; brief mantiene síntesis. No añadir mechanics al comentario público ni modificar la fecha/resultados de validaciones anteriores. Guardar tabla F→corrección→regresión con los 33 IDs y el matiz de F012.
- [ ] **Step 4: Verificación final.** Ejecutar suite completa una vez después del último cambio funcional: `python -B -X utf8 .superpowers/sdd/review-recovery-lifecycle/run-unittest.py discover -s tests -v`. Exigir exit 0, registrar conteo/duración/skip reales. AST de Python tocados, enlaces Markdown, 14 ayudas CLI (prepare/register/select-profile/checkpoint/lookup/inspect/pause/block/resume/recover/restart/retain/close/cleanup), ejemplos CLI end-to-end y `git diff --check`. Si aparece un nuevo fallo funcional, repetir focalizados y suite después de corregirlo; no repetir solo por rutina.
- [ ] **Step 5: Commit, push y gate del PR.** Git safety e identidad; commit `docs(review): documentar recuperaciones corregidas y sus regresiones`, push a la rama existente y actualizar cuerpo del PR #19 conforme a plantilla con resultados/contratos/compatibilidad. Verificar head remoto, adjuntar PR y pedir una revisión independiente del HEAD corregido; dejar explícito que el review anterior fue NO APROBABLE. Esperar validación humana antes de merge/tag/release; preservar worktree para comentarios.

## Autorrevisión y handoff

- Spec §2→Task 1; §3→Task 2; §4 y diagnóstico de §8→Task 3; §5→Task 4; §6→Task 5; §7→Task 6; documentación/aceptación de §8–9→Task 7.
- Todos los 33 IDs tienen tarea/regresión asignada; los cinco Review Focus aparecen en tests de sus tareas y en las secuencias integradas.
- Interfaces: helpers de inputs/restart son puros; writer y locks compartidos; cleanup devuelve observaciones pero no fabrica metadata de review. API objeto/ruta de register utiliza `_input_object` consistentemente.
- Compatibilidad: control histórico con fixtures reales de schemas 1–6; no se reetiquetan archives ni se atribuye vigencia a fuentes desconocidas. Tests distinguen legacy/current, real/provisional, actual/heredado.
- Proporción: siete entregables por causa, cada uno con RED/GREEN/commit; una revisión independiente final. No transcribir cuerpos de implementación ni dividir en 33 mini-PRs.
- Estado: documentos escritos y autorrevisados; aprobación pendiente. Los checkboxes de implementación permanecen sin marcar hasta observar sus resultados. El método nativo ya elegido se mantiene si el usuario aprueba este plan.
