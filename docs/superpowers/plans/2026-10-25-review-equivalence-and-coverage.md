# Equivalencia y cobertura de revisiones — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ofrecer reutilización solo con cambios y contexto equivalentes demostrados; iniciar CCR automáticamente ante cambios o incertidumbre y mejorar las preguntas de revisión que dejaron omisiones en el MR 97.

**Architecture:** Conservar comparación exacta y gates de recuperación de 3.1.0. Añadir contratos privados, captura Git binaria y decisión pura de reutilización, conectados al lookup verificado; mejorar los briefs y la consolidación usando los campos actuales.

**Tech Stack:** Python/stdlib, Git CLI con objetos inmutables y salida bytes/NUL, unittest, Markdown.

**Spec:** [2026-10-25-review-equivalence-and-coverage-design.md](../specs/2026-10-25-review-equivalence-and-coverage-design.md).

**Estado:** implementación autorizada por el usuario; tareas 1–8 realizadas y validación integrada completada en 868 casos (865 aprobados y 3 omitidos por privilegio Windows). Base `4fab30695bb3c0c47071eb887b38f92328b03ea2` / CCR 3.1.0. El registro de pruebas y decisiones se conserva en [validación](../../validation/2026-10-25-review-equivalence-and-coverage.md).

## Global Constraints

- La reutilización depende de la equivalencia de los cambios revisados, no de la existencia de una revisión previa ni únicamente de los commits o SHA.
- No se cambian archive 8/layout 2, final review schema 10, trace schema 1 ni packet version 1.
- No se retocan los gates de cierre e identidad de dispatch publicados en 3.1.0.
- Límites iniciales: 10.000 entradas, 32 MiB de patch agregado sin codificar, 64 MiB para descriptor serializado y 100 diagnósticos.
- Se respetan además los límites existentes de selección: 64 fuentes y 64 MiB agregados, incluido reference-index; se aplica el límite más restrictivo.
- `compare_inputs()` no se convierte en un comparador tolerante.
- Los archivos históricos son inmutables. Checks históricos conservan sus revisiones; no atribuir ejecuciones a un HEAD nuevo.
- La implementación autorizada se limita al worktree; no se publica, instala una nueva skill ni incrementa versión.

## Review Focus

- Igual patch con consumidor, requisito o política modificados: nuevo review por contexto; pruebas en tareas 3–5.
- Texto con tab/newline, CR, whitespace significativo o newline final: comparación por bytes sin colisiones; tarea 2.
- Merge vacío, rebase y rama destino móvil: evaluar diff completo y su contexto, no mensajes/HEAD aislados; tareas 2 y 6.
- Archive ambiguo, incompleto o modificado entre lookup y uso: no reutilizar ni enlazar una identidad inventada; tareas 4 y 5.
- Un test verde exige comportamiento incorrecto o una observación no bloqueante queda oculta: revisar requisito y disposición pública sin inflar severidad; tarea 7.

## Preparación y comandos

Trabajar en este worktree o uno aislado desde su rama documental; no implementar en el checkout instalado de `main`. Leer spec y diagnóstico antes de ejecutar tareas. Usar el Python disponible como `python` en los comandos siguientes; en esta sesión se verificó el intérprete empaquetado, sin instalar dependencias.

Baseline observado: `test_review_inputs.py` 7/7 y `test_review_latest.py` 9/9. Los tests de Git requieren un directorio temporal escribible y un ejecutable Git; un fallo de setup/ACL no constituye el RED funcional de TDD.

Los comandos de commit son hitos propuestos para una implementación autorizada, no acciones ya realizadas.

## Task 1: Contrato y comparación canónica de cambios

**Files:**
- Create: `scripts/ccr/contracts/effective_changes.py`.
- Create: `tests/test_review_effective_changes.py`.

**Interfaces:**
- Produces: `normalize_effective_changes(raw: object) -> dict`, validando la forma exacta del spec, límites, OID, base64, duplicados y digest.
- Produces: `effective_projection(descriptor: dict) -> list[dict]`, con entries ordenados y sin provenance `old_blob/new_blob`.
- Produces: `compare_effective_changes(retained: dict | None, current: dict) -> dict`, con `{code_equivalence, changed_paths, metadata_only, reasons}`. `changed_paths` son objetos `{old_path_b64,new_path_b64}` únicos; razones `{code,detail}`.
- Consumes: solo diccionarios; sin archivos, Git, selección ni decisiones de ejecución.

- [x] **Step 1:** Escribir casos `test_equal_payload_with_different_commits_is_equivalent`, `test_changed_hunk_path_mode_or_binary_is_different`, `test_absent_or_incomplete_descriptor_is_unknown`, `test_digest_and_payload_must_agree`, `test_duplicate_entries_and_unsupported_algorithm_are_unknown_or_invalid`.
  Assertions: el primer caso devuelve `equivalent` y `metadata_only=true`; cada cambio de contenido/ruta/modo devuelve `different`; ausencia/completitud falsa nunca devuelve equivalente; corrupción se rechaza, no se convierte en identidad vacía. `changed_paths` describe altas, bajas y modificaciones.
- [x] **Step 2:** Run `python -B -m unittest discover -s tests -p test_review_effective_changes.py -v`; esperar fallo de import/interfaz nueva, sin errores ambientales.
- [x] **Step 3:** Implementar las tres funciones. Comparar proyecciones completas además del digest. Separar `invalid` (ValueError al validar una captura suministrada) de evidencia histórica ausente/incompleta (`unknown` en appraisal).
- [x] **Step 4:** Repetir el comando; esperar PASS de todos los casos nuevos.
- [x] **Step 5:** `git add scripts/ccr/contracts/effective_changes.py tests/test_review_effective_changes.py`; `git commit -m "feat(reutilizacion): definir identidad de cambios efectivos"`.

## Task 2: Captura de objetos Git y patch determinista

**Files:**
- Create: `scripts/ccr/execution/change_scope.py`.
- Modify: `scripts/ccr/shared/git.py` — añadir adaptador bytes sin alterar `git()` existente.
- Create: `tests/test_review_change_scope.py`.

**Interfaces:**
- Consumes: contrato de tarea 1 y política del spec §4–5.
- Produces: `git_bytes(repo, *args: str, max_output_bytes: int) -> bytes`; comparte saneamiento de entorno, sin `.strip()` ni decoding con reemplazo, salida acotada durante lectura y sin ejecutar shell. El límite se aplica antes de acumular todo stdout; no es una comprobación posterior a captura ilimitada.
- Produces: `collect_effective_changes(repo, scope: dict, *, target_head: str) -> dict`; resuelve objetos, merge-base única y retorna descriptor validado. No hace fetch.
- Produces: `collect_context_files(repo, comparison: dict, files: list[dict]) -> list[dict]`, que relee el inventario de side/path contra diff_base/head actuales.

- [x] **Step 1:** Crear repositorios temporales reales y casos `test_empty_commit_is_equivalent`, `test_no_change_merge_is_equivalent`, `test_rebase_with_equivalent_change_is_equivalent`, `test_new_content_and_edit_of_reviewed_file_are_different`, `test_target_advance_changes_effective_diff_at_same_head`.
  Assertions: capturas completas; hunks equivalentes con HEAD distinto se mantienen; merge/rebase alteran solo provenance en los fixtures equivalentes; editar un hunk o absorber parte del cambio en target modifica entries aunque HEAD no cambie.
- [x] **Step 2:** Añadir `test_shifted_hunk_keeps_identity_but_changed_context_does_not`, `test_binary_mode_symlink_gitlink_and_rename`, `test_significant_whitespace_and_missing_newline`, `test_nul_paths_and_external_diff_are_safe`, `test_missing_objects_multiple_bases_and_limits_never_equal`. En Windows, symlinks reales solo se omiten con motivo de capacidad; el parser se prueba siempre con modos/bytes sintéticos. Probar rutas no UTF-8 en parser por bytes, y archivos reales cuando el SO lo permita.
- [x] **Step 3:** Run `python -B -m unittest discover -s tests -p test_review_change_scope.py -v`; esperar RED funcional.
- [x] **Step 4:** Implementar raw/NUL, patch textual y hashes streaming con las flags del spec, sin heurísticas de renames ni omisión de whitespace. Conservar un separador `@@\n` por hunk al retirar coordenadas. Un límite/fallo no produce un descriptor `complete=true`. Diferencias de OID no alteran el digest salvo gitlinks.
- [x] **Step 5:** Repetir las suites de tareas 1–2; esperar PASS. Verificar que los fixtures no cambien el worktree/index del repositorio evaluado.
- [x] **Step 6:** `git add scripts/ccr/execution/change_scope.py scripts/ccr/shared/git.py tests/test_review_change_scope.py`; `git commit -m "feat(reutilizacion): capturar diffs por contenido"`.

## Task 3: Persistir descriptor y contexto sin cambiar la identidad inicial

**Files:**
- Modify: `scripts/ccr/workflow/setup.py`, `scripts/ccr/cli/setup.py`.
- Create: `scripts/ccr/workflow/reuse.py` — builders y comparación de contexto.
- Modify: `scripts/ccr/contracts/material_inputs.py` — validar sidecars declarados en las fuentes seleccionadas.
- Create: `tests/test_review_reuse_context.py`.
- Modify: `tests/test_review_setup.py`, `tests/test_review_source_selection.py`, `tests/test_review_preflight.py`.

**Interfaces:**
- Produces: `build_review_context(scope: dict, files: list[dict], materials: list[dict], *, logical_scope_identity: str, complete: bool, diagnostics: list[dict]) -> dict`, según spec §5.4.
- Produces: `build_material_map(materials: list[dict], *, complete: bool, diagnostics: list[dict]) -> dict`, con `{schema_version:1,complete,entries,diagnostics}`. Validación de bytes/cobertura del índice pertenece al routing de setup.
- Produces: `compare_review_context(retained: dict | None, current: dict | None) -> dict` con `{applicability, reasons}`. SHA de provenance distintos se evalúan por contenido; el inventario completo y materiales deben ser equivalentes.
- CLI nueva: `python -B scripts setup changes --input <envelope> --output <owned-evidence-file>`; envelope `{session,arguments}`; arguments exactos `{repo,scope,target_head}`. Genera effective-changes; usa los gates de sesión/salida existentes.
- CLI nueva: `python -B scripts setup materials --input <envelope> --output <owned-evidence-file>`; arguments exactos `{materials,complete,diagnostics,reference_index}`. Genera reuse-materials tras validar el índice de fuentes externas. El coordinador añade después solo los dos sidecars generados al índice final, antes de `setup inputs` y prepare. `assess-reuse` revalida la cobertura del índice final, excluyendo únicamente esos dos sidecars.
- CLI nueva: `python -B scripts setup reuse-context --input <envelope> --output <owned-evidence-file>`; arguments exactos `{scope,logical_scope_identity,files,materials,complete,diagnostics}`. Valida contenido contra el Git fijado y materiales contra el índice capturado; no modifica ese índice.

- [x] **Step 1:** Casos nuevos: `test_capture_descriptor_before_discovery_and_retain_it`, `test_material_map_bootstrap_and_final_index_have_no_cycle`, `test_unmapped_other_source_prevents_complete_materials`, `test_context_is_derived_from_pinned_objects_not_new_material`, `test_changed_consumer_or_requirement_changes_applicability`, `test_absent_inventory_is_unknown`, `test_optional_material_absence_differs_from_unknown`, `test_stable_material_keys_ignore_transport_names`, `test_material_key_collision_is_rejected`.
  Assertions: una nueva lectura Git del scope inicial puede documentarse al consolidar; un requisito externo no capturado no puede añadirse retroactivamente; caller no puede inventar digest/completitud mediante un builder. Igual patch con consumidor modificado devuelve contexto `changed`.
- [x] **Step 2:** Probar CLI con salida nueva propia, colisión, escape, symlink/reparse, bytes cambiados y selección agregada >64 MiB. Probar envelope reuse-context >128 KiB pero dentro de 64 MiB, y rechazo antes de leer un envelope >64 MiB; comandos setup anteriores mantienen 128 KiB. Error no modifica archivos previos. Run suites `test_review_reuse_context.py`, `test_review_setup.py` y `test_review_source_selection.py`; esperar fallo por ausencia de soporte nuevo.
- [x] **Step 3:** Implementar builders/routing y validación condicional de los sidecars declarados. Capturar effective-changes y reuse-materials por `purpose=other` en el índice inicial. Retener review-context final como evidencia derivada, sin sumarlo a `review_inputs.sources` tras discovery. Los archivos nuevos de reviews guiados se exigen por workflow; un histórico sin ellos sigue legible y aporta equivalencia desconocida.
- [x] **Step 4:** Repetir suites anteriores y `test_review_preflight.py`; esperar PASS, sin relajar selección inicial, aliases ni hash gates de 3.1.0.
- [x] **Step 5:** Commit propuesto: `feat(reutilizacion): conservar alcance y contexto verificables`, con los archivos de esta tarea.

## Task 4: Decisión pura de reutilización

**Files:**
- Modify: `scripts/ccr/workflow/reuse.py`.
- Create: `tests/test_review_reuse_decision.py`.
- Preserve: `scripts/ccr/workflow/inputs.py` y sus semánticas exactas.

**Interfaces:**
- Consumes: resultados de comparación de tareas 1 y 3.
- Produces: `decide_reuse(code: dict, context: dict, *, has_prior: bool, current_scope_ready: bool) -> dict` con `{action,code_equivalence,applicability,reasons,changed_paths,metadata_only}`. Toma los enums exactos de spec §6, sin I/O ni archivos.
- La intención explícita `new review` o `show latest` se enruta antes por el coordinador; no inferirla del nombre de una rama.

- [x] **Step 1:** Tabla de pruebas: equivalente+aplicable -> `offer_choice`; diferente -> `new_review`; equivalente+contexto changed/unknown -> `new_review`; anterior ausente -> `new_review`; actual no fijado -> `blocked_current_scope`. Probar que ninguna incertidumbre genere oferta de reutilización.
- [x] **Step 2:** Run `python -B -m unittest discover -s tests -p test_review_reuse_decision.py -v`; esperar RED.
- [x] **Step 3:** Implementar precedencias deterministas; motivos distinguen cambio de código, contexto, ausencia e incertidumbre. Un perfil explícito o alcance autorizado incompatible con el review anterior nunca se presenta como satisfecho automáticamente.
- [x] **Step 4:** Repetir suite y `test_review_inputs.py`; PASS. Añadir assertion de regresión en inputs: scope con HEAD distinto sigue `changed` en la comparación exacta, aunque la decisión tolerante acepte oferta por equivalencia.
- [x] **Step 5:** Commit propuesto: `fix(reutilizacion): decidir antes de ofrecer resultados previos`.

## Task 5: Lookup verificado, comparación histórica y CLI de admisión

**Files:**
- Create: `scripts/ccr/archive/reuse.py`, `tests/test_review_reuse_archive.py`.
- Modify: `scripts/ccr/archive/lookup.py`, `scripts/ccr/cli/artifacts.py`.
- Modify: `tests/test_review_latest.py`, `tests/test_script_cli.py`, `tests/fixtures/scripts_cli_contracts.json`.

**Interfaces:**
- Produces: `assess_reuse(repo, scope: dict, *, current_inputs: dict, effective_changes: dict, current_materials: dict, current_sources: dict[str, bytes], logical_scope_input: dict | None = None, archive_root=None, max_scan: int = 10000) -> dict`, con la salida exacta de spec §6 incluyendo `schema_version=1` y `prior_run`.
- CLI: `python -B scripts artifacts assess-reuse --repo <repo> --scope-file <scope.json> --current-inputs <inputs.json> --effective-changes <descriptor.json> --current-materials <reuse-materials.json> --session <owned-manifest.json> [--archive-root <root>] [--logical-scope-input <selector.json>] [--max-scan 10000]`.
- Consumes: selección interna única de latest y verificación de hashes existentes. Refactorizar selección común sin cambiar `lookup --select latest` ni su salida. La CLI carga `current_sources` solo desde la sesión verificada e índice final capturado. Comparar contexto actual releyendo exactamente el inventario antiguo con `collect_context_files`; materiales actuales proceden del reuse-materials anticipado, comprobado contra esos bytes. El evaluador puede construir ese contexto antes de discovery sin confundirlo con un inventario de lecturas nuevas.

- [x] **Step 1:** Casos: `test_latest_selection_is_not_applicability`, `test_older_equivalent_review_does_not_hide_latest_different`, `test_tie_scan_limit_or_corruption_never_offer_reuse`, `test_open_run_is_not_reusable_and_is_not_mutated`, `test_candidate_changed_before_return_is_not_reused`.
- [x] **Step 2:** Añadir `test_old_archive_reconstructs_only_proven_range`, `test_delta_diff_without_provenance_is_unknown`, `test_missing_context_is_unknown_unless_full_trees_and_materials_are_proven`, `test_unsupported_layout_is_historical_only`, `test_assessment_never_mutates_previous_run`.
  Assertions: reconstructible no significa escribir sidecars históricos; corrupción/empate no produce previous-run operativo; mostrar último explícito conserva resultado histórico `changed` y no inicia CCR.
- [x] **Step 3:** Run `test_review_reuse_archive.py` y `test_review_latest.py`; confirmar RED en comportamiento nuevo.
- [x] **Step 4:** Implementar orquestación read-only, selección compartida y salida JSON. Verificar hashes de cada sidecar, scope y fuentes de donde se derive contexto; no confiar solo en hashes del informe. Snapshot de refs y revalidación final detectan carreras. Error estructural CLI devuelve JSON y exit 1; decisiones válidas `new_review/offer_choice/blocked_current_scope` se devuelven con exit 0 y acción explícita.
- [x] **Step 5:** Repetir suites anteriores y `test_script_cli.py`; PASS. Extender solo contratos CLI afectados, sin regenerar fixtures de comandos ajenos.
- [x] **Step 6:** Commit propuesto: `feat(archivo): evaluar reutilizacion por alcance efectivo`.

## Task 6: Integrar el flujo automático y probar los casos del usuario

**Files:**
- Modify: `SKILL.md`, `references/archive/recovery.md`, `references/archive/artifacts.md`, `references/workflow/re-review.md`, `references/workflow/scopes.md`.
- Create: `tests/test_review_reuse_flow.py`.
- Modify: `tests/test_review_recovery_followup.py`, `tests/test_review_restart.py`, `tests/test_review_reference_index.py` cuando afecten interfaces nuevas.

**Interfaces:**
- Consumes: CLIs de setup/assess-reuse y gates nativos existentes de prepare/restart.
- Produces: un único orden de admisión documentado: fijar alcance -> lookup/comparar -> nueva revisión automática u oferta por equivalencia -> revalidar -> preparar y revisar. La CLI decide; no despacha revisores por sí sola.

- [x] **Step 1:** Escribir fixtures de integración con repositorios+archives reales para cada fila de aceptación del spec. Assertion principal: al obtener `new_review`, la capa de flujo no pide elección; con `offer_choice` devuelve exactamente las opciones nueva revisión / último resultado. El test comprueba routing y parámetros, no simula que un modelo ya revisó el código.
- [x] **Step 2:** Añadir casos con HEAD idéntico/base distinta, rebase con archivo upstream ajeno al contexto, mismo diff con consumidor relevante cambiado, metadata generada distinta, perfil explícito incompatible y nuevas notas materiales. Probar selección revalidada después de la respuesta del usuario; refs nuevas invalidan una oferta vieja.
- [x] **Step 3:** Run `test_review_reuse_flow.py`; esperar RED por falta de flujo nuevo. Luego actualizar las referencias de forma coherente y completar el routing verificable en las funciones de tareas 4–5 si falta un branch.
- [x] **Step 4:** Run suites de esta tarea más `test_review_inputs.py`, `test_review_latest.py`, `test_review_reference_index.py`; PASS. Revisar manualmente los ejemplos naturales «revisa MR», «haz nueva revisión» y «muéstrame la última» contra la misma tabla de decisiones.
- [x] **Step 5:** Commit propuesto: `fix(flujo): iniciar CCR ante cambios efectivos o equivalencia desconocida`.

## Task 7: Cobertura, expectativas de tests y observaciones no bloqueantes

**Files:**
- Modify: `references/execution/reviewers.md`, `references/execution/worker-packets.md`, `references/workflow/re-review.md`, `references/workflow/review-areas.md`.
- Modify: `references/dimensions/design-testability.md`, `references/dimensions/security-operation.md`, `references/reporting/report-format.md`.
- Create: `docs/examples/review-scenario-disposition.md`.
- Extend only where missing: `tests/test_review_areas.py`, `tests/test_review_presentation.py`.

**Interfaces:**
- Consumes: candidatos, flows, limitations, priority/blocking y public_summary existentes. No introduce nuevos campos, etapas de reviewer ni más dispatches.
- Produces: briefs con escenario/efecto y disposición de cada observación relevante: finding confirmado, limitación/incertidumbre o propuesta refutada con razón.

- [x] **Step 1:** Definir ejemplos sintéticos: test que exige rechazar BAJA sin validar contraseña; fallback que inserta éxito ficticio; transición desde estado permitido; índice sin limpieza con crecimiento por operación; lector nuevo con datos antiguos; parámetro opcional sin consumidor actual defectuoso; N lecturas extra sin benchmark; sugerencia externa que elimina protección legacy.
- [x] **Step 2:** Para cada ejemplo, anotar requisito observado, secuencia real, prueba que lo contradice o no lo cubre, consecuencia, evidencia faltante y disposición. No copiar fixtures privados ni prometer que una prueba contractual mide la capacidad de descubrimiento del modelo.
- [x] **Step 3:** Antes de cambiar renderers, ejecutar `test_review_areas.py` y `test_review_presentation.py` y revisar la proyección actual. Añadir RED solo si falta garantía concreta: confirmed P3 no bloqueante visible; behavior limitation relevante no perdida al ser no material; ningún rejected privado se vuelve público. Si ya están cubiertas, reutilizar esos tests y registrar el resultado; no duplicarlos.
- [x] **Step 4:** Actualizar guías: cuestionar assertions frente al contrato; enumerar transiciones; revisar ciclo de vida y consumidores nuevos; derivar cobertura de escenarios en vez de letras asignadas; preservar hallazgos no bloqueantes y límites relevantes. Revisar las 8 filas de ejemplo como ejercicio de aceptación de política. No tocar código de render si la proyección existente ya cumple.
- [x] **Step 5:** Repetir suites de presentación/áreas y `test_review_comment.py`; PASS sin exposición de rejected, paths o mecánica privada. Commit propuesto: `fix(revision): cubrir efectos adyacentes y conservar observaciones relevantes`.

## Task 8: Validación integrada y cierre de implementación

**Files:**
- Update when implementing: `README.md`, `CHANGELOG.md`, `docs/script-migration.md` si incorpora nuevos comandos.
- Validation: los tests nuevos y suites actuales de inputs/latest/setup/source-selection/preflight/recovery/restart/references/contract/comment/trace.

- [x] **Step 1:** Recorrer los ocho criterios del spec y registrar tarea/test responsable; no afirmar completitud si falta inventario, equivalencia o validación. Mantener release `unreleased` hasta publicación real, siguiendo CONTRIBUTING.md.
- [x] **Step 2:** Ejecutar el inventario completo de `python -B -m unittest discover -s tests -v` con TEMP escribible, repartido en tres procesos disjuntos por módulo según el registro de validación; comprobar todos los casos y skips justificados por capacidad. La omisión del índice documental detectada en el lote 3 se corrigió y sus 7 comprobaciones afectadas se repitieron con exit 0. Si falla, corregir la causa dentro del cambio y repetir solo lo afectado antes de la comprobación final.
- [x] **Step 3:** Run `git diff --check`; comprobar que no se modificaron archives históricos, el checkout principal ni datos de otros reviews. Recorrer permisos/trace/source-selection de 3.1.0 sin debilitarlos.
- [x] **Step 4:** Verificar un ejemplo CLI reproducible de cada decisión y distinguir evidencia reutilizada de checks nuevos. Medir costos solo si el usuario lo solicita; no inferir ahorro de tokens del número de comandos.
- [x] **Step 5:** Commit de integración/documentación según la política del repositorio. Entregar alcance implementado, pruebas efectivamente ejecutadas, limitaciones y pasos de release; no publicar ni instalar sin autorización.

## Autorrevisión y handoff

La implementación debe conservar nombres/interfaces de tareas 1–5, las dos formas de identidad y la separación captura inicial/contexto derivado. Los tests nuevos deben demostrar comportamiento y seguridad de routing; tests que solo busquen palabras en Markdown no prueban que el agente detecte defectos.

Este plan cubre diagnóstico, regla de reutilización, casos especiales, persistencia compatible y las mejoras del análisis previo. El baseline de 16 pruebas corresponde a 3.1.0. La implementación fue autorizada y los resultados posteriores figuran en el registro de validación; la publicación e integración en main quedan fuera de este encargo.
