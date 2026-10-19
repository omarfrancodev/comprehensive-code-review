# Archivo legible, consulta histórica y subaspectos ABCDE — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** identificar ejecuciones desde sus carpetas, consultar resultados anteriores con decisiones explícitas y ampliar ABCDE sin migrar archivos históricos.

**Architecture:** un contrato puro de layout concentra agrupación y nombres; los helpers existentes conservan toda la coordinación nativa. Un lector/exportador independiente produce consultas históricas de tres archivos, sin adoptar recursos ni operaciones. Latest extiende lookup y las dimensiones amplían briefs y cobertura existentes.

**Tech Stack:** Python 3.10+, biblioteca estándar, Git, unittest y Markdown.

**Spec:** [2026-10-18-readable-archive-history-coverage-design.md](../specs/2026-10-18-readable-archive-history-coverage-design.md).

**Estado:** implementación nativa secuencial validada: 621 casos, 618 aprobados y 3 omisiones de plataforma, sin fallos ni errores; ambas matrices extensas completadas. Base `715726377ad95acbb1cbad114d7a55968228ab79`, release 2.12.1. Rama `feat/archive-layout-portability`. Este documento conserva la secuencia prevista; los comandos y resultados observados se registran en [la validación de implementación](../../validation/2026-10-18-readable-archive-history-coverage.md).

## Global Constraints

**Ajustes posteriores al CCR del PR 25:** F001–F004 corregidos con 174 pruebas
aprobadas, sin fallos ni omisiones. Véase el [registro de ajustes](../../validation/2026-10-19-pr25-ccr-adjustments.md)
para las regresiones y el alcance de esta validación posterior.

**Re-review nativo v2 (F005):** lectura y replay de reservas anteriores corregidos,
con 151 pruebas aprobadas y cuatro contrastes con el productor exacto anterior.
Véase [la validación de reservas v2](../../validation/2026-10-19-pr25-native-v2-replay.md).

- Python 3.10+ y biblioteca estándar; Git solo para operaciones que ya lo requieren.
- Mantener final review schema 10, trace schema 1 y packet version 1. No reconstruir datos históricos para actualizar sus schemas.
- Emitir archive schema 8 con layout_version 2; los archivos nativos anteriores se clasifican como unsupported_layout para operación.
- Ninguna operación escribe en un archivo histórico ni migra sus carpetas, ownership, claims, trazas o transacciones.
- Portar produce únicamente informe.md, consulta.json y .ccr-history.json; no produce cierre.json, review.json, marcador de ownership ni traza nativa.
- Consultar y seleccionar son operaciones de solo lectura: no crean sesiones, worktrees, runs, locks ni entregas.
- No añadir fechas al contenido de informes nuevos; las fechas de rutas y selección conservan UTC explícito.
- Conservar el nombre comprehensive-code-review; el visor, publicaciones, merge, tags y release quedan fuera del alcance.

No ejecutar el plan sobre archivos reales de reviews. Usar fixtures públicas sintéticas en temporales propios. No agregar un modo force ni un bypass de validación. La versión futura de release queda sin asignar hasta preparar su publicación.

## Review Focus

1. Referencias truncadas o SHAs abreviados iguales no deben agrupar límites distintos ni reemplazar identidades completas: tareas 1 y 2.
2. Una reserva de restart interrumpida debe recuperar exactamente su sucesor en layout 2, conservando locks/claims: tarea 2.
3. Un archivo antiguo con resultado visible pero hashes o estado transaccional contradictorios debe conservarse sin exportar un resultado certificado: tarea 4.
4. Un candidato potencialmente más reciente situado después de la primera página o ilegible debe impedir una selección latest injustificada: tarea 5.
5. Una consulta histórica cuyo origen desaparece debe seguir siendo legible, sin convertirse en resultado vigente ni operación recuperable: tareas 4 y 5.

## Preparación y verificación

Trabajar únicamente en el worktree indicado. El usuario autorizó implementar después de revisar la propuesta. Método elegido: ejecución nativa secuencial; no lanzar agentes.

Comando de suite documentado en docs/usage.md:

```text
python -B -m unittest discover -s tests -v
```

En este host el alias python de WindowsApps no es ejecutable. Para comprobaciones usar el Python efectivo registrado en [la validación de preparación](../../validation/2026-10-18-readable-archive-planning.md), con TEMP/TMP exclusivos. Los comandos siguientes presuponen que `python` representa ese ejecutable y no el alias roto. No instalar dependencias: el proyecto usa la biblioteca estándar.

Las pruebas focalizadas siguen la forma `python -B -m unittest discover -s tests -p 'test_nombre.py' -v`. No inventar un resultado antes de ejecutar. La suite descubierta ya incluye las dos matrices extensas de `test_review_restart_resources.RestartResourceReplayTests`: `test_claimed_workspace_all_transfer_replacements` y `test_unclaimed_workspace_all_adoption_replacements`; no necesitan una variable opt-in. No ejecutarlas de nuevo si la suite completa ya las cubrió. Para aislarlas durante diagnóstico: establecer PYTHONPATH a `scripts` y `tests` del worktree y ejecutar `python -B -m unittest -v test_review_restart_resources.RestartResourceReplayTests.test_claimed_workspace_all_transfer_replacements test_review_restart_resources.RestartResourceReplayTests.test_unclaimed_workspace_all_adoption_replacements`.

## Mapa de archivos e interfaces compartidas

| Archivo | Responsabilidad |
|---|---|
| scripts/review_layout.py (nuevo) | Descriptor lógico, grupos, nombres y reconocimiento puros |
| scripts/review_history.py (nuevo) | Diagnóstico histórico, portabilidad mínima y show verificable |
| scripts/review_artifacts.py | Archive 8, integración del layout en preparación, reservas y gates |
| scripts/review_restart.py, scripts/review_resource_claims.py, scripts/review_restart_refusal.py, scripts/review_run_lock.py | Mantener coordinación y rechazo de cancelaciones; adaptar únicamente bindings que el cambio de layout afecte |
| scripts/review_recovery.py, scripts/review_inputs.py | Lookup, logical_scope_identity, selección latest y catálogo histórico |
| scripts/review_delivery.py | Entregas nativas con ubicación nueva; rechazo de HP como run |
| tests/archive_layout_fixtures.py (nuevo) | Factories sintéticas nativas/históricas y snapshots de archivos |
| tests/test_review_layout_v2.py, test_review_archive8.py, test_review_history.py, test_review_latest.py (nuevos) | Contratos, operación, consultas históricas y selección |
| references/workflow/review-areas.md y references/dimensions/*.md (tres nuevos) | Catálogo y referencias selectivas |
| SKILL.md, references/archive/artifacts.md, recovery.md y referencias de ejecución | Routing, contratos y restricciones |
| README.md, docs/usage.md, CHANGELOG.md y registro de validación nuevo | Uso, cambio incompatible y resultados observados |

Interfaces nuevas, sin clases/framework adicional:

```python
# review_layout.py (puro; Mapping de inputs, dict normalizado de salida)
logical_scope(scope: dict, selector_input: dict | None = None) -> dict
scope_group(logical: dict) -> str
run_name(scope: dict, created_at: str, run_id: str) -> str
validate_layout(run_dir: Path, manifest: dict) -> None
classify_header(manifest: dict) -> dict
# classify_header: {status: native|unsupported_layout|invalid, actions: list[str]}

# review_history.py (IO acotado; no invoca mutadores de archive)
inspect_source(source_run: Path) -> dict
port_review(source_run: Path, output_root: Path | None = None) -> dict
verify_history(history_dir: Path) -> dict
show_history(history_dir: Path) -> str

# review_recovery.py; reutiliza find_candidates para la lista
select_latest(repo: Path, scope: dict, *, current_inputs: dict,
              logical_scope_input: dict | None = None,
              archive_root: Path | None = None, max_scan: int = 10000) -> dict
# selection.status: selected|no_match|ambiguous|incomplete_search
```

La factory nueva define `native_scope(mode='mr', **overrides) -> dict`, `selector_input(mode='mr', **overrides) -> dict`, `make_native(root: Path, **overrides) -> Path`, `make_legacy(root: Path, **overrides) -> Path`, `tree_hashes(root: Path) -> dict[str, str]`. Las factories generan ownership/result/report sintéticos válidos o alteraciones nombradas; nunca introducen un parámetro para forzar versiones antiguas en la CLI de producto. Reutilizar record10/context10/selection_input/source_events de recovery_fixtures.py para no duplicar sus contratos.

### Task 1: Contrato puro de ubicación y alcance lógico

**Files:** Create scripts/review_layout.py, tests/archive_layout_fixtures.py y tests/test_review_layout_v2.py. Modify references/archive/artifacts.md con el contrato nuevo propuesto, sin retirar aún gates operativos.

**Interfaces:** produce las cinco funciones puras listadas arriba. Consume el scope de siete campos y el JSON canónico del archivo; no consulta Git, paths externos ni red. Fixture factories de esta tarea deben poder representar headers antes de integrar prepare.

- [ ] Escribir tests `test_same_mr_different_heads_share_logical_group`, `test_different_boundaries_same_head_do_not_share_group`, `test_local_snapshots_share_group_only_for_equal_boundaries`, `test_sha_only_range_has_no_invented_branch_identity`. Afirmar igualdad/desigualdad de grupos y preservar scope original.
- [ ] Añadir `test_windows_reserved_traversal_length_and_prefix_collision` y `test_timestamp_hint_and_unique_id_are_bound`: fecha exacta `20261018T150000Z`, prefijo head de 12, 20 hex de run_id, cambio de ruta inválido, abreviaturas iguales con identidades completas diferentes, selector normalizado estable. Límite 64/500/64 KiB según spec.
- [ ] Ejecutar test_review_layout_v2.py y observar RED por interfaces nuevas ausentes.
- [ ] Implementar únicamente lógica pura, esquema de selector por modo, strings seguros y clasificación archive 8/layout 2. Para module/feature sin límites: error explícito. No agregar derivación heurística del contenido del título.
- [ ] Repetir focalizadas hasta GREEN y registrar comandos/resultados. Commit sugerido: `feat(archivo): definir ubicación legible y alcance lógico`.

### Task 2: Integrar archive 8 en toda operación nativa

**Files:** Modify scripts/review_artifacts.py, scripts/review_restart.py, scripts/review_resource_claims.py, scripts/review_restart_refusal.py, scripts/review_recovery.py, scripts/review_delivery.py y, solo si lo exige el binding, scripts/review_run_lock.py. Create tests/test_review_archive8.py; Modify tests/test_review_artifact_layout.py, test_review_recovery_sequences.py y recovery_fixtures.py.

**Interfaces:** consume review_layout. prepare añade keyword `logical_scope_input=None`; restart usa el mismo keyword y reutiliza descriptor previo solo para límites iguales. CLI `--logical-scope-input` lee el documento validado. No cambiar firmas no afectadas. Marker/manifiesto enlazan layout_version/logical_scope; todas las mutaciones exigen archive 8.

- [ ] Escribir `test_prepare_and_reserved_restart_use_identical_layout`, `test_restart_crash_replays_one_successor`, `test_locks_and_claims_bind_native8`, `test_old_layout_refused_before_any_write`. Afirmar preservación exacta del árbol histórico y de los guards de selección/perfil/fuentes.
- [ ] Añadir `test_module_boundary_change_requires_new_selector` y `test_native_delivery_uses_logical_scope_group`. Verificar CR estable por run, ninguna fecha añadida al informe, y rechazo de HP como --previous-run.
- [ ] Ejecutar test_review_archive8.py y observar RED por emisión actual de archive 7 o nombre antiguo.
- [ ] Integrar funciones únicas en prepare, reserva de restart, validación e inspección. Toda detección de formato anterior devuelve unsupported_layout antes de un lock/escritura; no usar _load_run legacy para intentar recuperarlo. Mantener contratos puros de resultados 1–10.
- [ ] Actualizar fixtures operativas a archive 8. Convertir tests de operación legacy a rechazo tipado; conservar tests de render/validación histórica. No quitar asserts de ownership, cleanup, perfiles, rollback excluido o coordinación para lograr GREEN.
- [ ] Ejecutar focalizadas de archive8, artifact_layout, atomic_recovery, recovery_sequences, resource claims y locks. Los archivos exactos se toman de `rg --files tests`; repetir suite completa tras tareas integradas. Commit: `feat(archivo): aplicar formato nuevo a ejecución y recuperación`.

### Task 3: Lookup y diagnóstico de incompatibilidad sin adopción

**Files:** Modify scripts/review_recovery.py, scripts/review_inputs.py y references/archive/recovery.md. Extend tests/test_review_archive8.py y tests/test_review_recovery.py.

**Interfaces:** find_candidates conserva su firma y añade keywords `logical_scope_input=None, include_history=False`. current_inputs admite logical_scope_identity como SHA-256/null, comparada como identidad conocida; su ausencia histórica permanece unknown. Cursor nuevo versionado y ligado al grupo lógico, repositorio y scope exacto. Candidate añade kind=native|historical_source|historical_port y acciones por tipo.

- [ ] Escribir `test_lookup_finds_changed_head_in_one_logical_group`, `test_cursor_v1_rejected_without_mutation`, `test_old_folder_is_classified_without_opening_resources`, `test_missing_logical_identity_is_unknown`. Probar varios repositorios y páginas de 1/100 elementos.
- [ ] Ejecutar test_review_recovery.py y test_review_archive8.py; confirmar RED de casos nuevos.
- [ ] Actualizar listado acotado y matcher. Nativos usan descriptor; legacy solo inventario de headers dentro del prefijo consultado. No explorar evidence/sesiones ajenas ni validar transacciones históricas para adoptarlas. Un header inválido no se reclasifica como compatible.
- [ ] Conectar errores de inspect/mutadores con acciones port_history/new_review/preserve, sin ofrecer resume/restart sobre layouts anteriores. Documentar que una versión productora anterior queda fuera de este flujo.
- [ ] Repetir focalizadas y comprobar tree_hashes idéntico antes/después de lookup/inspect. Commit: `feat(recuperacion): identificar formatos históricos sin adoptarlos`.

### Task 4: Paquete mínimo de consulta histórica

**Files:** Create scripts/review_history.py, tests/test_review_history.py y references/archive/history.md. Modify tests/test_reference_layout.py para registrar la referencia, references/archive/artifacts.md y recovery.md para enlazarla. Extender fixtures sintéticas.

**Interfaces:** implementa inspect_source/port_review/verify_history/show_history del mapa. inspect devuelve status=portable|incomplete|invalid|unsupported_source, facts y acciones. port devuelve status=created|existing y history_dir/port_id; los fallos son errores tipados sin tocar la fuente. CLI inspect/port/show según spec. verify_history solo consulta sus tres archivos.

- [ ] Escribir `test_port_minimal_inventory_source_unchanged`: afirmar exactamente tres archivos, informe original idéntico, IDs/scope/veredicto conservados y ausencia de recursos/evidence/traza/ownership nativo.
- [ ] Añadir `test_missing_or_altered_source_bytes_rejected`, `test_pending_transaction_not_exported`, `test_pending_cleanup_remains_pending`, `test_unknown_identity_stays_null`, `test_schema_and_size_limits`. El informe sin JSON/manifiesto verificable no se convierte en portada válida.
- [ ] Añadir `test_source_changed_during_read_refused`, `test_destination_collision_preserved`, `test_interrupted_staging_retry_is_idempotent`, `test_source_removed_after_port_still_readable`, `test_history_cannot_be_passed_to_native_mutators`. Comprobar que show no añade archivos/locks y conserva el aviso fuera de informe.md.
- [ ] Ejecutar test_review_history.py y observar RED; implementar lector histórico acotado independiente del cargador operativo. Reusar validación pura, JSON sin duplicados y guards seguros; no importar mutadores legacy ni reconstruir schemas de resultados.
- [ ] Implementar staging exclusivo/rename sin overwrite y reintento verificable. No crear comando migrate/rollback del origen; no seguir enlaces de informe al leerlo. Revalidar paquete existente antes de devolver existing.
- [ ] Ejecutar tests históricos, referencia local y el rechazo por helpers nativos. Commit: `feat(historial): portar informes verificados para consulta mínima`.

### Task 5: Selección explícita del último resultado y guard

**Files:** Modify scripts/review_recovery.py, scripts/review_artifacts.py (CLI), SKILL.md y references/archive/recovery.md. Create tests/test_review_latest.py; Extend tests/test_review_recovery.py.

**Interfaces:** select_latest según mapa; CLI lookup `--select latest`, `--logical-scope-input` y `--include-history`. max_scan=10000 no se convierte en una opción de ignorar candidatos; al agotarlo devuelve incomplete_search. El show de HP usa review_history, no inspect nativo. Latest no introduce show automático en el helper de listado.

- [ ] Escribir `test_default_lookup_does_not_select`, `test_explicit_latest_pages_to_last_eligible_result`, `test_latest_uses_created_at_not_name_mtime_or_id`, `test_same_time_is_ambiguous`, `test_incomplete_scan_selects_nothing`.
- [ ] Añadir `test_changed_or_unknown_appraisal_is_shown_as_historical`, `test_wrong_scope_or_boundaries_excluded`, `test_unreadable_potential_candidate_blocks_selection`, `test_no_native_result_does_not_promote_hp_to_current`. Afirmar exactitud de scope y del selector lógico; perfil distinto no se oculta.
- [ ] Añadir `test_selected_candidate_revalidated_before_show` y `test_guard_show_has_no_session_run_dispatch_or_delivery`. Repetir explícitamente autorizada no vuelve a preguntar; petición genérica sí resuelve elección. Antiguos resultados ofrecen portabilidad sin adopción.
- [ ] Ejecutar test_review_latest.py y confirmar RED; implementar selección exhaustiva acotada y resultado estructurado, más routing del guard. Mantener lookup solo lectura y tomar fechas de metadata verificable.
- [ ] Ejecutar focalizadas latest/recovery/history. Commit: `feat(recuperacion): consultar el último resultado por petición explícita`.

### Task 6: Subaspectos y referencias selectivas ABCDE

**Files:** Modify references/workflow/review-areas.md, references/execution/reviewers.md, worker-packets.md, SKILL.md y tests/test_review_areas.py, test_reference_layout.py. Create references/dimensions/design-testability.md, contracts-data.md y security-operation.md.

**Interfaces:** cinco filas de coverage.areas sin campos nuevos. Los briefs existentes añaden texto de subaspectos/flujo/invariante; cada uno se enlaza a evidencia/gap en details. No se agregan campos obligatorios a packet version 1 ni a final schema 10. Las dimensiones no seleccionan agentes ni alteran perfiles.

- [ ] Añadir casos `test_multiple_subaspects_one_cause_one_finding`, `test_dimension_detail_does_not_add_public_matrix`, `test_dimensions_preserve_profile_and_packet_contract`. Validar datos sintéticos por el contrato actual y comprobar no duplicación; no simular que un test prueba calidad del juicio del modelo.
- [ ] Extender catálogo exacto de referencias y verificar enlaces. Revisar manualmente cada disparador/evidencia de los tres documentos y el mapeo A/B/C/D/E de la spec.
- [ ] Redactar índice y referencias: preguntas observables, evidencia decisiva, ejemplos por foco y antes/después breves cuando aclaren un defecto. Severidad por consecuencia; sin reglas ACE Engine, umbrales universales ni puntuaciones.
- [ ] Ajustar briefs y routing selectivo previo al trabajo, conservando selection_id y obligaciones actuales. No relabel de asignaciones ejecutadas.
- [ ] Ejecutar tests de areas, packets, profiles y reference_layout; registrar revisión documental. Las reglas de evidencia/asignación se evalúan también mediante escenarios documentados con entradas y salidas esperadas; los tests mecánicos no demuestran calidad del criterio del modelo. Commit: `feat(cobertura): detallar subaspectos y referencias ABCDE`.

### Task 7: Integración, guía de actualización y cierre de implementación

**Files:** Modify README.md, docs/usage.md, CHANGELOG.md, referencias afectadas, tests/test_review_recovery_sequences.py y test_review_flow_v27.py si sus expectativas lo requieren. Create docs/validation/YYYY-MM-DD-readable-archive-history-coverage.md con la fecha real de ejecución.

**Interfaces:** no añadir otro contrato. Documentar cambio incompatible archive 8/layout 2, final 10 sin promoción histórica, tres archivos HP y visor pendiente por separado. Mantener descarga de la release publicada mientras la futura no exista; cambios van a unreleased sin inventar fecha/tag.

- [ ] Añadir secuencia integrada prepare8 → resultado → cierre → lookup latest → show, y legacy → diagnóstico → port → fuente ausente → show → rechazo de continuación. Verificar fuente legacy byte por byte intacta.
- [ ] Ejecutar suite completa con Python efectivo/temporales propios y verificar que sus IDs incluyen ambas matrices nombradas en Preparación, sin duplicarlas. Registrar comandos, exit codes, counts, skips y límites de plataforma; no atribuir al cambio errores de entorno sin diagnóstico.
- [ ] Revisar CLI --help, enlaces locales, ausencia de fechas nuevas en informes, nombre de skill, compatibilidad de entregas y errores unsupported_layout. Comprobar que no se modificó el repositorio del visor.
- [ ] Hacer revisión de rama completa frente a la spec, con especial atención a latest incompleto, staging, identidad de selectors y restart reservado. Corregir hallazgos y reejecutar únicamente comprobaciones afectadas antes de integración final.
- [ ] Registrar validación y preparar commits revisables. No portar datos reales, publicar, mergear ni releasear sin la autorización correspondiente. Commit documental: `docs(archivo): documentar actualización y consulta histórica`.

## Trazabilidad de requisitos y revisión del plan

| Requisito de spec | Tareas |
|---|---|
| Ubicación visible, límites y versionado | 1–2 |
| Reserva/recovery/locks/claims sin regresión | 2–3 y 7 |
| Formatos anteriores incompatibles sin migración | 2–4 |
| Tres archivos históricos, integridad y cero adopción | 4–5 y 7 |
| Guard y latest explícito sin selección implícita | 3 y 5 |
| ABCDE y referencias bajo demanda | 6 |
| Reporte sin fechas, nombre conservado, visor fuera | 2 y 7 |

La implementación comenzó después de revisar que spec y plan reflejan la decisión de no migrar y que los cinco Review Focus tienen pruebas asignadas. La dependencia entre layout, reservas y lookup mantiene la ejecución secuencial.
