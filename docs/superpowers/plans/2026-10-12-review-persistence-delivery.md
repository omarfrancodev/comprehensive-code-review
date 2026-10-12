# Review Persistence and Typed Delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar reviews sin corromper su contrato, vincular checks locales con ejecutores reales y comprobar el cierre durable antes de anunciar éxito.

**Architecture:** La proyección distingue estructura, prosa, comandos y referencias. Final schema 9 añade procedencia tipada por check; un módulo puro valida esa relación y el archive gate la contrasta con el contexto/cierre existente. Un gate read-only comprueba cierre completo, conservando archive 6, trace/packet 1 y lectura histórica.

**Tech Stack:** Python estándar, unittest, Markdown y Git; sin nuevas dependencias.

**Spec:** [2026-10-12-review-persistence-delivery-design.md](../specs/2026-10-12-review-persistence-delivery-design.md), aprobada por el usuario el 2026-10-12.

## Global Constraints

- Worktree: `.worktrees/review-persistence-delivery`; rama `fix/review-persistence-delivery`; base main `eba4c54c4d40df7a877b22f79c572c4272b90eec`.
- Nuevo resultado final schema 9; lectura de schemas 1–8 sin migración. Archive schema 6, packet/trace schema 1 permanecen iguales.
- `execution.kind`: local/static/external/reused. `execution.executor`: ID de entorno propio o null según el caso, sin inferirlo desde command/status.
- Preparar 2.11.0 pendiente. README/instalación mantienen 2.10.0 como última release publicada; no publicar tag/release ni merge antes de aprobar el PR.
- No modificar reviews existentes, comentarios remotos, otros repositorios, instalaciones externas ni configuración del harness. El visor independiente queda fuera de alcance; anunciar su necesidad de schema 9.
- Sin sondeos, métricas, heartbeat, nuevo archivo de auditoría, registro por cada búsqueda o agentes adicionales para evaluar el perfil.
- Conservar ownership, hashes, selección de evidencia, interrupciones recuperables e inmutabilidad. Un error de persistencia no cambia el juicio de código ni autoriza cleanup.
- Reproducciones con datos sintéticos y recursos propios; usar `-B -X utf8`. No ejecutar pruebas contra los archivos persistidos del usuario.
- Seguimiento inline y checkboxes de este plan bajo el fallback opcional del controlador de tareas. Una tarea en progreso; gates RED/GREEN antes del commit.

## Review Focus

1. Un comando puede coincidir con un enum, ID, hash o identidad: Task 1 debe demostrar que la estructura y sus relaciones no cambian y que prosa/comandos privados se omiten.
2. Una identidad estructural histórica puede contener una ruta privada: Task 1 rechaza antes de crear destino sin imprimir el valor, en vez de filtrar la ruta o reescribir el ID.
3. Un check local bloqueado puede no haber obtenido entorno; CI, inspección y reuso tampoco crean un worktree: Task 2 diferencia estos casos de local passed/failed y prueba baseline/snapshot.
4. La limpieza elimina worktrees antes de la comprobación final: Tasks 2–3 revalidan la procedencia retenida sin exigir que sobreviva el checkout temporal, ni reconstruir Git o la ejecución.
5. Un run puede conservar eventos, una transacción interrumpida o cleanup pendiente: Task 3 prueba que ninguno acredita cierre completo; la recuperación preserva evidencia propia y rechaza ajena.

---

## Preparación y método

- [x] Main actualizado y limpio; worktree propio y directorio ignorado verificados.
- [x] Base: 292 tests en 209.807 s; 291 aprobados y una omisión por privilegios de symlinks en Windows.
- [x] Especificación escrita en `1009b57`, revisada inline y aprobada por el usuario.
- [x] Crear este plan y revisar cobertura/interfaces/proporción.
- [ ] Obtener aprobación del plan antes de implementar. Conservar ejecución nativa del flujo: implementar aquí, luego una revisión independiente de toda la rama, sin una revisión por tarea.

Runtime verificado: `C:/Users/Developer.INSCORSOF2/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`. Los comandos siguientes usan `python` como abreviatura de ese intérprete. En PowerShell se invoca con `& '<ruta>'`.

## Archivos y responsabilidades

| Archivo | Responsabilidad |
|---|---|
| `scripts/review_delivery.py` | Proyección por campo, privacidad, render full/brief y escritura segura del destino |
| `scripts/review_check_provenance.py` (nuevo) | Validación pura de execution por check y vínculo con ejecutores retenidos |
| `scripts/review_contract.py` | Envelope schema 9 e integración de la validación de checks, render/IDs/CLI compatibles |
| `scripts/review_execution.py`, `scripts/review_publication.py` | Conservar semántica schema 8 de perfiles/limitaciones al emitir schema 9 |
| `scripts/review_artifacts.py` | Expectativa de schema, gate de fuentes/ejecutores, cierre y validate read-only |
| `tests/test_review_check_provenance.py` (nuevo) | Fixtures schema 9, modelo y integración con archive/delivery |
| `tests/test_review_delivery.py` | Colisiones estructurales, privacidad e inmutabilidad |
| `tests/test_review_artifacts.py`, `tests/test_review_execution_policy.py` | Cierre completo, transacciones, fuentes e históricos |
| `SKILL.md`, referencias y `docs/usage.md` | Instrucciones por fase y contratos públicos de helpers |
| `CHANGELOG.md`, `docs/validation/2026-10-12-review-persistence-delivery.md` (nuevo) | Versión pendiente, compatibilidad y comprobaciones reales |

### Task 1: Entrega portable con estructura preservada

**Files:** Modify `scripts/review_delivery.py`; Test `tests/test_review_delivery.py`.

**Interfaces:**
- Consumes: `_Projection(record, manifest, project, source_hash)`, `contract.validate(record)` y `deliver(run_dir, delivery, project_root, output_root=None, context=None)` existentes.
- Produces: `_Projection.value(value, path='record')` con categorías explícitas de campos; `_Projection.structural(value: str, path: str) -> str`, que preserva identidad o rechaza una ruta privada con diagnóstico del campo; firmas de delivery sin cambios.

- [x] **Step 1: Añadir regresiones.** Implementar `test_projection_preserves_structure_when_commands_collide`, parametrizada por deep/passed/C001 y coincidencia con una identidad/hash. Partir de records válidos; comprobar `validate(source)==[]`, `validate(portable)==[]` e igualdad de IDs, perfil, estados, versiones y relaciones. Prosa y command conservan la omisión esperada. Añadir `test_private_structural_identity_refuses_delivery_without_writes`, con ruta privada en una identidad admitida por un schema histórico; comprobar excepción que nombra el campo sin divulgar el valor, destino ausente y snapshot de fuente intacto. Añadir `test_full_and_brief_share_typed_projection_and_lineage`, con referencias internas repetidas y URL pública, probando ambas modalidades y receipt.

  Núcleo de la regresión de colisión (imports desde fixtures y helper existentes):

  ```python
  value = record8('deep')
  value['checks'] = [dict(check(), command='deep')]
  self.assertEqual(contract.validate(value), [])
  projection = delivery._Projection(value, {
      'repository_path': str(self.repo), 'archive_root': str(self.archive)
  }, self.repo, 'a' * 64)
  portable = projection.value(value)
  self.assertEqual(portable['profile'], 'deep')
  self.assertEqual(portable['checks'][0]['id'], 'C001')
  self.assertEqual(contract.validate(portable), [])
  ```

- [x] **Step 2: Observar RED.** `python -B -X utf8 -m unittest discover -s tests -p test_review_delivery.py -v`. La colisión debe producir invalid value/ID antes de corregir; la protección estructural debe fallar por no existir aún. No aceptar un fallo de fixture o permisos como RED del defecto.
- [x] **Step 3: Implementar proyección tipada.** Enumerar rutas estructurales/prosa/referencias de los contratos soportados, incluidas claves de aliases y listas de IDs históricos. Preservar estructura; aplicar detección de rutas privadas únicamente para impedir divulgación, no para reemplazar enums/IDs. Mantener omisión de command, referencias estables, ubicación relativa, URLs válidas, context opcional y `projection.changed`. Una ruta nueva no cae automáticamente en sanitización genérica. No relajar `contract.validate` ni crear destino antes de validar/renderizar.
- [x] **Step 4: Observar GREEN.** Repetir el comando focalizado; comprobar full/brief, históricos y snapshot byte por byte. Ejecutar `git diff --check`.
- [x] **Step 5: Commit.** Stage explícito de los dos archivos; `git commit -m 'fix(delivery): preservar estructura al sanitizar reviews portables'`.

### Task 2: Schema 9 y procedencia de checks

**Files:** Create `scripts/review_check_provenance.py`, `tests/test_review_check_provenance.py`; Modify `scripts/review_contract.py`, `scripts/review_execution.py`, `scripts/review_publication.py`, `scripts/review_artifacts.py`, `scripts/review_delivery.py` y `references/contracts/result-contract.md`.

**Interfaces:**
- Consumes: fixtures `record8`/`source_fixture` de `tests/test_review_execution_policy.py`, `check` de `tests/test_review_traceability_contract.py`, validadores de perfil/fuentes y `_executors` existentes.
- Produces: `validate_check_execution(record: dict) -> list[str]` para estructura schema 9; `validate_check_sources(record: dict, executors: list[dict]) -> list[str]` para IDs/revisión/snapshot. Los schemas anteriores no adquieren gates nuevos. Fixture `record9(profile='focused', selection='explicit') -> dict` en el nuevo módulo de pruebas, basada en record8 y con execution en cada check.

- [x] **Step 1: Añadir regresiones.** `test_local_completed_check_requires_executor` prueba passed/failed sin ID y IDs vacíos. `test_nonlocal_and_unexecuted_checks_do_not_invent_executors` prueba static/external/reused y local blocked/not_run. `test_reuse_and_external_source_are_explicit` comprueba correspondencia reused/kind y referencia externa de passed/failed. `test_executor_binding_covers_head_baseline_and_snapshot` comprueba ID presente, revisión head/base y snapshot correspondiente; incluye un executor con ID desconocido. `test_schema9_archive_binds_checks_before_writing` comprueba guard de retención y snapshot intacto al fallar. `test_closed_schema9_source_survives_executor_cleanup` revalida desde cierre/contexto después de retirar el worktree propio. `test_schema9_delivery_keeps_execution_ids_and_public_report_omits_workspaces` cubre full/brief y privacidad. `test_legacy_checks_keep_original_shape` conserva schema 1–8 sin campos añadidos.

  Núcleo del contrato local (probar también failed con failure_kind/evidence válidos):

  ```python
  value = record9()
  value['checks'] = [dict(check(), execution={'kind': 'local', 'executor': None})]
  self.assertTrue(any('executor' in error for error in validate_check_execution(value)))
  value['checks'][0]['execution']['executor'] = 'X1'
  self.assertEqual(validate_check_execution(value), [])
  self.assertTrue(validate_check_sources(value, []))
  ```

- [x] **Step 2: Observar RED.** `python -B -X utf8 -m unittest discover -s tests -p test_review_check_provenance.py -v`. Esperar schema 9 no admitido/validador faltante, no errores de importación ajenos al módulo nuevo ni fixtures inválidos antes de la mutación.
- [x] **Step 3: Implementar contrato y bindings.** Añadir schema 9 a cada capability correspondiente de contrato, IDs, render, publication, delivery y archive; packet/trace/archive conservan su versión. Validar execution local/static/external/reused, executor según status y reglas de reuso/referencia. Integrar ambos validadores puros: validar contra executors del contexto fuente y contra el cierre proyectado antes de escribir; después usar la procedencia retenida, sin exigir la existencia del recurso eliminado. Reutilizar `_executors` para raíz Git/HEAD/registro antes de cleanup. Conservar los gates de fuentes/perfil de schema 8 y sus limitaciones clasificadas; no cambiar legacy ni mostrar mecánica local en comentario público.
- [x] **Step 4: Observar GREEN.** Repetir tests nuevos y `python -B -X utf8 -m unittest discover -s tests -p test_review_execution_policy.py -v`; repetir Task 1 tras integrar schema 9 y las pruebas de publicación. Confirmar que fixture schema 8 original sigue emitida/validada sin modificarla a schema 9.
- [x] **Step 5: Commit.** Stage explícito de archivos de esta tarea; `git commit -m 'feat(checks): vincular validaciones locales con ejecutores en schema 9'`.

### Task 3: Expectativa de contrato y cierre completo

**Files:** Modify `scripts/review_artifacts.py`; Test `tests/test_review_artifacts.py`, `tests/test_review_execution_policy.py`, `tests/test_review_check_provenance.py`.

**Interfaces:**
- Consumes: validadores de Task 2 y los gates actuales de ownership, hashes, scope, fuentes y recursos.
- Produces: `retain(..., *, expected_schema: int | None = None)` manteniendo todos los argumentos existentes; CLI `retain --expected-schema 9`. `validate(run_dir, require_retained=False, record_checkpoint=False, *, require_complete=False)` y CLI `validate --require-complete`. Retornos existentes y archive schema 6 sin campos nuevos. `close` conserva su firma y aplica validación completa de lo retenido.

- [x] **Step 1: Añadir regresiones.** `test_expected_schema_blocks_legacy_emission_without_rewriting_history`: schema 8 retenible históricamente falla cuando se espera 9, sin archivos nuevos; lectura/delivery del mismo histórico permanecen válidos. `test_trace_without_final_result_cannot_pass_complete_gate`: prepare y evento completed no satisfacen require-complete. `test_pending_and_interrupted_runs_are_not_complete`: prepared/processing/retaining/closing fallan; comprobar transacción interrumpida, planned hashes y reintento sin borrar evidencia. `test_complete_gate_is_read_only_and_matches_resources`: complete válido pasa con snapshot igual; cleanup pendiente, resources contradictorios, evidencia modificada y checkpoint solicitado fallan sin escribir. `test_close_rechecks_execution_sources_before_completion` comprueba sources/provenance mediante los gates, no solo existencia de informe. Cubrir API y CLI, incluyendo datos legacy válidos.

  Núcleo del caso sin resultado en ArchiveTests, con los defaults observados del evento:

  ```python
  run = self.prepare()
  artifacts.record_event(run, self.write('event.json', {
      'kind': 'discovery', 'status': 'completed', 'summary': 'Static review completed'
  }))
  before = {str(p.relative_to(run)): p.read_bytes() for p in run.rglob('*') if p.is_file()}
  with self.assertRaises(ValueError):
      artifacts.validate(run, require_complete=True)
  self.assertEqual(before, {str(p.relative_to(run)): p.read_bytes()
                           for p in run.rglob('*') if p.is_file()})
  self.assertFalse((run / 'review.json').exists())
  ```

- [x] **Step 2: Observar RED.** Ejecutar las pruebas focalizadas de archive y check provenance. Esperar flag/signature faltante o cierre que omita el nuevo gate; distinguir fixture/control positivo de la mutación que debe fallar.
- [x] **Step 3: Implementar gates.** Expected-schema valida la expectativa de la operación antes de copiar resultado/evidencia, sin derivarla de skill_version. Ausencia conserva llamadas históricas. Require-complete implica require-retained, exige state complete/retained true/cleanup complete o not_needed/sin residuals y coherencia con review.resources; no recupera transacciones ni escribe eventos. Close recupera únicamente la transacción propia cuando corresponda y después aplica el gate de retención completo antes de finalizar. Mantener el orden retain → validate requerido → cleanup observado → close → gate final, sin borrar recursos desde el helper.
- [x] **Step 4: Observar GREEN.** Repetir tests focalizados; `python -B -X utf8 scripts/review_artifacts.py retain --help` y `validate --help` muestran ambos flags. Verificar reintentos propios, rechazo de evidencia ajena y cierre idempotente sin cambios de bytes/eventos.
- [x] **Step 5: Commit.** Stage explícito; `git commit -m 'fix(archive): verificar contrato esperado y cierre durable completo'`.

### Task 4: Política operativa, verificación y PR

**Files:** Modify `SKILL.md`, `references/archive/artifacts.md`, `references/archive/lifecycle-trace.md`, `references/execution/workspaces.md`, `references/execution/worker-packets.md`, `references/reporting/delivery.md`, `references/maintenance/evaluation.md`, `docs/usage.md`, `CHANGELOG.md`; Create `docs/validation/2026-10-12-review-persistence-delivery.md`. Actualizar otras referencias solo si afirman el schema actual y quedan contradictorias, sin reescribir documentación histórica de planes/validación.

**Interfaces:**
- Consumes: APIs/flags implementados en Tasks 1–3; spec aprobada y formato de `.github/PULL_REQUEST_TEMPLATE.md`.
- Produces: instrucciones actuales con schema 9/versión 2.11.0 pendiente, evidencia de comprobaciones reales y PR enlazado para revisión del usuario. No merge/tag/release.

- [x] **Step 1: Actualizar instrucciones.** Elegir/registrar perfil antes del trabajo sin redescubrir contexto. Completar schema 9 y `retain --expected-schema 9`; no inferir executors de temporales/eventos. Ante gate fallido conservar run/recursos y comunicar fase/error, sin reclamar cierre o limpiar. Tras close usar `validate --require-complete` como comprobación final, reemplazando la validación genérica de cierre. Distinguir review realizado, resultado retenido y cleanup/cierre pendiente/completo. Documentar ejemplos de static/CI/reuso/local bloqueado y nuevo contrato del visor, con enlaces progresivos y sin extender README innecesariamente.
- [x] **Step 2: Ejecutar comprobaciones integradas.** `python -B -X utf8 -m unittest discover -s tests -v`; exigir exit 0 y documentar la omisión real de Windows sin contabilizarla como pass. AST de scripts afectados, enlaces relativos de documentación modificada, `--help` de contract/archive/delivery y `git diff --check`. Guardar resultados y alcance RED→GREEN en el documento de validación; no atribuir la suite base al head nuevo.
- [x] **Step 3: Revisión independiente final.** Un contexto fresco revisa toda la rama contra spec/plan y los cinco Review Focus. No otra pasada de discovery ni agentes por cada gate. Contrastar hallazgos, corregir causas confirmadas con regresión y repetir únicamente verificaciones afectadas; después suite completa si cambió runtime/tests. Documentar riesgos o asuntos pendientes reales antes del PR.
- [ ] **Step 4: Commit y publicar rama.** Prechecks de Git/identidad, stage explícito de documentación/validación y plan actualizado; commit convencional descriptivo. Push normal de `fix/review-persistence-delivery`; ningún force-push salvo autorización explícita. Confirmar base/head y archivos incluidos.
- [ ] **Step 5: Crear y adjuntar PR.** Describir los tres problemas, nuevo comportamiento, final schema 9/lectura 1–8 y verificación real; usar la plantilla. Crear contra main, adjuntar el URL al chat y comprobar cuerpo/head remoto. Conservar worktree para feedback y esperar aprobación humana; no aprobar, mergear ni publicar release en este paso.

## Autorrevisión del plan

- Cobertura: Task 1 implementa spec §1; Task 2 implementa §2 y relaciones portables; Task 3 implementa §3; Task 4 integra operación, compatibilidad y gate humano.
- Interfaces: check.execution se valida en el módulo puro y se contrasta con los executors verificados por archive; delivery solo exige estructura portable y valida fuentes desde el archivo original. No exigir un executor activo al leer un cierre histórico.
- Review Focus: colisión y datos privados en Task 1; categorías y baseline/snapshot en Task 2; recursos eliminados entre Tasks 2–3; eventos/interrupciones/pendientes en Task 3.
- Proporción: cuatro entregables con regresiones y commits propios; no transcribir algoritmos completos, añadir un auditor, duplicar fixtures históricos ni migrar archivos.
- Estado: plan escrito y revisado inline; spec y plan aprobados por el usuario; ejecución nativa autorizada. Implementación y única revisión independiente final completadas; cuatro hallazgos corregidos y suite final de 315 tests (314 aprobados/1 omitido). Publicación de rama y PR en curso.
