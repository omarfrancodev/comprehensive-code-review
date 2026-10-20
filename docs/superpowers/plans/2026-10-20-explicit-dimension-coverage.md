# Cobertura explícita de dimensiones ABCDE — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** impedir omisiones silenciosas de dimensiones mediante 27 decisiones explícitas, validadas y visibles en los reportes nuevos.

**Architecture:** final schema 11 añade dimensiones obligatorias a las cinco filas ABCDE; un módulo puro concentra catálogo, agregación y validación. Los helpers existentes conservan persistencia, provenance y proyecciones, aceptando 10 para continuidad histórica y 11 para el flujo actualizado.

**Tech Stack:** Python 3.10+, biblioteca estándar, unittest, Git y Markdown.

**Spec:** [2026-10-20-explicit-dimension-coverage-design.md](../specs/2026-10-20-explicit-dimension-coverage-design.md).

**Estado:** plan propuesto; implementación pendiente de revisión del usuario y elección de ejecución. Base `main` / `09eeb03` / CCR 2.13.0. No hay autorización para ejecutar estos pasos por el hecho de haber solicitado los documentos.

## Global Constraints

- Python 3.10+ y biblioteca estándar; no agregar dependencias de producto.
- Los nuevos resultados finales usan schema 11; los schemas 1–10 conservan sus reglas y bytes históricos.
- Mantener archive schema 8, layout version 2, trace schema 1 y packet version 1.
- No migrar, reabrir ni reescribir archivos reales de revisiones para completar dimensiones antiguas.
- Mantener perfiles, independencia, gates de proyecto, IDs de hallazgos/checks y reglas de veredicto existentes.
- Los comentarios públicos omiten la taxonomía ABCDE y de dimensiones; las brechas materiales conservan su impacto público.
- El visor externo no se modifica ni se declara compatible con schema 11 en esta entrega.
- No asignar versión de release, publicar, hacer merge ni modificar datos reales de reviews durante esta preparación.

## Review Focus

1. Un ID ausente, repetido, ajeno al área o con un tipo no hashable debe producir errores de validación, nunca excepción ni una cobertura implícita: tarea 1.
2. Una mezcla de dimensiones cubiertas y pendientes no debe admitir un área cubierta ni perder el efecto de una brecha material: tareas 1 y 2.
3. Una rama `schema_version == 10` olvidada no debe permitir que 11 omita historia de perfiles, checks locales o fuentes de ejecución: tarea 2.
4. Una dimensión con rutas privadas o texto Markdown hostil no debe filtrar evidencia, alterar IDs ni romper las proyecciones: tarea 3.
5. Un archivo 10 abierto, cerrado o con operación interrumpida debe conservar sus bytes y su continuidad sin adquirir dimensiones inventadas: tareas 2 y 4.

## Preparación

Trabajar en el worktree aislado de esta rama, o en el aislamiento expresamente elegido para ejecutar el plan. No tocar el checkout principal ni el visor. No instalar dependencias: el proyecto utiliza la biblioteca estándar.

Los comandos usan `python` para el intérprete efectivo. Si WindowsApps no es ejecutable, usar el Python empaquetado disponible en `%USERPROFILE%/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`. Fijar TEMP/TMP a un temporal propio fuera del checkout principal y usar `-B` para evitar bytecode. No confundir una ejecución focalizada con la suite completa.

Las nuevas fixtures serán sintéticas. `tests/recovery_fixtures.py:record10`, `context10`, `source_events` y las factories de `tests/test_review_artifacts.py` ya modelan perfiles y ciclos de vida; no duplicarlos ni modificar en bloque las fixtures históricas para convertirlas a 11.

## Mapa de archivos e interfaces

| Archivo | Responsabilidad |
|---|---|
| `scripts/review_dimensions.py` (nuevo) | Catálogo puro de 27 IDs/etiquetas; agregación y validación de dimensiones |
| `scripts/review_contract.py` | Activar final 11, validar sus áreas y renderizar desglose privado |
| `scripts/review_profiles.py`, `review_execution.py`, `review_check_provenance.py`, `review_publication.py` | Aplicar a 11 las garantías existentes de 10 |
| `scripts/review_artifacts.py` | Admitir 11 en checkpoint/retain/validate sin cambiar archive 8 |
| `scripts/review_history.py`, `review_recovery.py` | Identidad, lectura y continuidad sin reconstruir cobertura |
| `scripts/review_delivery.py` | Política de nuevos campos, full y resumen brief |
| `tests/dimension_fixtures.py` (nuevo) | Datos sintéticos nuevos 11; reusar las factories históricas |
| `tests/test_review_dimensions.py`, `test_review_dimensions_integration.py` (nuevos) | Contrato puro, renderer y lifecycle 10/11 |
| `tests/test_review_delivery.py`, `test_review_areas.py`, `test_reference_layout.py` | Proyecciones y compatibilidad documental |
| `SKILL.md`, referencias de workflow/ejecución/contratos/archivo/reportes y `references/dimensions/*.md` | Selección, seguimiento y cierre obligatorio por dimensión |
| `README.md`, `docs/usage.md`, `CHANGELOG.md`, `docs/validation/2026-10-20-explicit-dimension-coverage.md` | Uso, límites, cambios y evidencia observada de implementación |

Interfaces nuevas, sin framework ni IO en el módulo puro:

```python
# scripts/review_dimensions.py
DIMENSIONS: dict[str, tuple[str, ...]]  # A..D: cinco IDs; E: siete IDs
DIMENSION_LABELS: dict[str, str]        # etiquetas españolas
dimension_summary(dimensions: list[dict]) -> dict
# Entrada ya validada; devuelve {status, material, finding_ids}.
# finding_ids ordenados y sin duplicados. No infiere details ni cobertura.
validate_dimensions(areas: object, finding_ids: set[str]) -> list[str]
# Lista de errores con rutas coverage.areas[i].dimensions[j] o del resumen.
# Acepta entradas hostiles como datos: reporta errores, no lanza TypeError.

# tests/dimension_fixtures.py
record11(profile='focused', source='automatic') -> dict
# Reusa record10; cambia solo schema y añade dimensiones sintéticas coherentes.
dimension_row(identifier: str, status='covered', **updates) -> dict
# {id, status, details, material, finding_ids}; no afirma evidencia real.
```

El contrato existente sigue entrando por `review_contract.validate(record) -> list[str]` y `render(record, audience='user', publication_context=None) -> str`. `review_artifacts.retain(..., expected_schema=None)` conserva firma; amplía el conjunto válido a 1–11. `context10(record)` y `source_events(record)` pueden usarse con 11 porque sus campos de ejecución no cambian; su nombre histórico no autoriza alterar `record10`.

### Task 1: Catálogo y coherencia de dimensiones

**Files:** Create `scripts/review_dimensions.py`, `tests/dimension_fixtures.py`, `tests/test_review_dimensions.py`. Modify `scripts/review_contract.py`.

**Interfaces:** produce las constantes, `dimension_summary`, `validate_dimensions` y factories anteriores. `review_contract.validate` consume `validate_dimensions` solo para final 11; mantiene las reglas de 1–10. Las ramas de ejecución de 11 se completan en la tarea 2 antes de usarlo como resultado durable.

- [ ] **Step 1: Escribir casos RED del catálogo y el resumen.** En `test_review_dimensions.py`, crear `DimensionContractTests`. `test_catalog_has_exactly_27_stable_ids` afirma A01–A05, B01–B05, C01–C05, D01–D05 y E01–E07; es la única expectativa literal completa del catálogo en tests. `test_every_dimension_is_required` elimina sucesivamente cada ID y exige su ruta en errores. `test_rejects_duplicate_foreign_unknown_and_nonhashable_ids` prueba repetido, A01 dentro de E, Z99, lista y objeto como ID. `test_requires_exact_fields_and_nonempty_details` cubre ausencia, extra, whitespace y tipos no válidos.
- [ ] **Step 2: Escribir casos RED de agregación.** `test_summary_state_truth_table` afirma: todo N/A → N/A; cubiertas más N/A → cubierta; sin evaluar más N/A → no evaluada; cubierta más sin evaluar → parcial; cualquier parcial → parcial. `test_summary_material_and_finding_union` exige OR material y unión de IDs, con un hallazgo compartido sin duplicación. `test_rejects_inconsistent_parent` altera por separado estado, materialidad y referencias del área y exige errores. `test_nonapplicable_cannot_hold_findings_or_material_gap` y `test_rejected_or_missing_findings_are_not_references` fijan las restricciones del spec.
- [ ] **Step 3: Ejecutar RED.** `python -B -m unittest discover -s tests -p test_review_dimensions.py -v`. Esperado: falla por módulo nuevo ausente o contrato todavía sin soporte; no aceptar problemas del entorno como RED funcional.
- [ ] **Step 4: Implementar catálogo, resumen y validador puro.** Adoptar exactamente los IDs de la sección 3 del spec. Validar tipos antes de pertenencia/conjuntos. Integrar esquema 11 final sin aceptar nuevos campos en 10 ni asignar dimensiones por defecto. Las constantes y funciones producen únicamente los campos definidos en Interfaces.
- [ ] **Step 5: Ejecutar GREEN.** Repetir el comando anterior y `python -B -m unittest discover -s tests -p test_review_areas.py -v`. Esperado: sin fallos; tests de schemas históricos intactos. La prueba histórica que acepta registros sin dimensiones continúa probando su versión original.
- [ ] **Step 6: Commit focalizado.** Incluir exclusivamente los cuatro archivos de esta tarea con mensaje `feat(cobertura): validar dimensiones explícitas por área`.

### Task 2: Schema 11 completo y gates durables

**Files:** Modify `scripts/review_contract.py`, `review_profiles.py`, `review_execution.py`, `review_check_provenance.py`, `review_publication.py`, `review_artifacts.py`, `review_history.py`, `review_recovery.py` solo donde su dispatch de versión lo requiera. Create `tests/test_review_dimensions_integration.py`; extend `tests/test_review_dimensions.py`.

**Interfaces:** consume `record11` y las validaciones de tarea 1. Produce aceptación integral de 11 en `validate`, checkpoint, `retain(expected_schema=11)`, `validate_execution_sources`, recuperación y lectura histórica; archive 8 conserva su forma. Mantiene aceptación explícita de 10 para operaciones existentes. No cambia firmas ni reservas/locks/claims.

- [ ] **Step 1: Escribir RED de herencia y veredicto.** En `DimensionContractTests`, `test_material_gap_and_blocker_precedence` usa una dimensión pendiente material: `approvable` inválido; `insufficient_evidence` válido; con hallazgo bloqueante confirmado, `not_approvable` válido. `test_schema11_keeps_schema10_profile_and_executor_guards` corrompe por separado history, selection_id, superseded_by y executor/revision y exige los mismos rechazos de 10. `test_legacy_1_to_10_have_no_dimensions_requirement` reutiliza factories existentes por versión sin añadirles datos.
- [ ] **Step 2: Escribir RED del lifecycle sintético.** `DimensionArchiveTests` reutiliza `ArchiveTests` y los patrones de `test_review_archive8.py`. `test_archive8_retain_validate_close_schema11` prepara, registra contexto/fuentes observadas sintéticas, retiene con expected 11, verifica, cierra y exige validación completa. `test_expected_11_rejects_10_and_missing_dimensions_without_output_change` compara hashes antes/después del rechazo. `test_schema11_does_not_bypass_source_or_check_provenance` prueba fuente de perfil contradictoria y ejecución local sin binding, sin permitir retención.
- [ ] **Step 3: Escribir RED de continuidad histórica.** `test_schema10_open_closed_and_pending_operations_remain_schema10` cubre run abierta, cerrada y reserva interrumpida; permite solo las escrituras propias de la recuperación ya autorizada sobre su fixture y exige idénticos bytes del resultado 10. `test_recovery_replays_reserved_schema11_bytes` reanuda bytes reservados 11 válidos sin volver a generar dimensiones. `test_checkpoint_and_history_bind_review_id_for_11` rechaza CR ID ajeno en ambos lectores. `test_latest_reads_both_versions_without_starting_run` compara árboles antes/después, conserva la selección por entradas/vigencia existente y no inventa cobertura.
- [ ] **Step 4: Ejecutar RED.** Ejecutar las suites nuevas con `python -B -m unittest discover -s tests -p test_review_dimensions*.py -v`. Esperado: fallos por guards de versión o lifecycle aún restringidos a 10.
- [ ] **Step 5: Extender soporte explícito de 11.** Revisar guards `== 10`, `!= 10`, tuplas que terminan en 10 y rangos de schema en los archivos enumerados. Aplicar a 11 todas las garantías heredadas; no sustituir globalmente 10 por 11. Archive 8 admite finales 10/11 en checkpoint, retain y validate; CLI `--expected-schema` admite 1–11. El error de expected 11 ante 10 permanece anterior a la escritura de resultados. Mantener el formato de contexto, trace, manifiesto y packets.
- [ ] **Step 6: Ejecutar GREEN y regresiones de provenance.** Repetir suites nuevas y ejecutar individualmente `test_review_execution_policy.py`, `test_review_check_provenance.py`, `test_review_profiles.py`, `test_review_archive8.py` y `test_review_history.py` con unittest discover. Esperado: sin fallos; legacy no cambia schema ni representación. Registrar cualquier omisión de plataforma.
- [ ] **Step 7: Commit focalizado.** Mensaje `feat(contratos): conservar provenance y archivo para schema 11` con los archivos concretos modificados y los tests de esta tarea.

### Task 3: Desglose en reportes y proyección portátil

**Files:** Modify `scripts/review_contract.py`, `scripts/review_delivery.py`, `scripts/review_publication.py` si hace falta para la selección pública, `tests/test_review_dimensions.py`, `tests/test_review_delivery.py`, `tests/test_review_dimensions_integration.py`.

**Interfaces:** consume catálogo, labels y finales 11 válidos. `render(..., audience='user')` añade `### Dimensiones evaluadas` después de la matriz y antes de incertidumbres. `render(..., audience='comment')` conserva política pública. `deliver` mantiene firma y entrega full/brief según sección 6 del spec.

- [ ] **Step 1: Escribir RED del renderer.** Añadir `DimensionRenderingTests`: `test_user_report_lists_every_dimension_in_canonical_order` afirma 27 filas con etiqueta, estado, detalle y referencias; incluye las cuatro clases de estado. `test_hostile_text_is_escaped_without_mutating_record` usa pipes, HTML, saltos y Markdown, y compara deep copy antes/después. `test_schema10_render_has_no_invented_dimension_section` conserva salida histórica. `test_public_comment_omits_taxonomy_but_keeps_one_material_gap` exige una sola incertidumbre material, sin tabla ni etiquetas generadas de dimensiones.
- [ ] **Step 2: Escribir RED de entrega.** En `test_review_delivery.py`, `test_schema11_full_preserves_27_dimension_rows_and_identity` valida JSON portátil, CR ID y recibo de origen. `test_schema11_brief_accounts_for_every_id_and_pending_reason` exige todos los IDs agrupados por estado y motivos pendientes/N/A. `test_dimension_details_are_sanitized_but_ids_preserved` inserta rutas Windows/POSIX y evidencia privada en details y comprueba su saneamiento. `test_unknown_dimension_fields_are_not_silently_projected` rechaza antes de crear salida; no reemplazar errores con un JSON degradado a 10.
- [ ] **Step 3: Ejecutar RED.** Ejecutar `test_review_dimensions.py` y `test_review_delivery.py` con unittest discover. Esperado: fallos por sección inexistente o campo nuevo aún sin política portátil.
- [ ] **Step 4: Implementar proyecciones.** El renderer usa el catálogo y helpers existentes de escape; conserva 1–10. Full mantiene todas las dimensiones. Brief representa todos los IDs y motivos pendientes/N/A sin duplicar evidencia cubierta. En `_Projection`, clasificar explícitamente `coverage.areas[].dimensions[].id`, `.status`, `.finding_ids[]` como STRUCTURAL y `.details` como PROSE; los booleanos siguen el manejo tipado existente. Extender los guards de versión de identidad y limitaciones en delivery/publication para heredar las garantías de 10.
- [ ] **Step 5: Ejecutar GREEN.** Repetir ambas suites y `test_review_publication_policy.py`. Esperado: sin fallos; ni rutas privadas ni campos desconocidos pasan por una política permisiva. Verificar que las brechas agregadas conservan impacto público y no duplican limitaciones.
- [ ] **Step 6: Commit focalizado.** Mensaje `feat(reportes): mostrar dimensiones y conservarlas en entregas`.

### Task 4: Flujo obligatorio, compatibilidad y validación final

**Files:** Modify `SKILL.md`, `references/workflow/review-areas.md`, `references/execution/reviewers.md`, `worker-packets.md`, `references/contracts/result-contract.md`, `references/archive/artifacts.md`, `references/reporting/report-format.md`, `delivery.md`, `references/dimensions/design-testability.md`, `contracts-data.md`, `security-operation.md`, `README.md`, `docs/usage.md`, `CHANGELOG.md`, `tests/test_reference_layout.py` cuando proceda. Add scenarios to `tests/test_review_scenarios.py` o pruebas documentales en `tests/test_review_dimensions.py`. Create `docs/validation/2026-10-20-explicit-dimension-coverage.md` para resultados de implementación, distinto del registro de preparación.

**Interfaces:** consume soporte 11 completo de tareas 1–3. Produce instrucciones coherentes con catálogo, packets 1, reporte y `retain --expected-schema 11`, además de evidencia observada de implementación. No cambia la versión de release ni el visor.

- [ ] **Step 1: Escribir RED documental.** `test_dimension_catalog_matches_operational_references` comprueba que los 27 IDs y sus áreas se encuentran en las referencias correspondientes. `test_new_workflow_requires_schema11_and_no_silent_downgrade` exige el guard de retención e instrucciones de no inferir cobertura desde asignación/área. `test_worker_packet_stays_version1_with_dimension_flow_text` valida packet 1 con IDs en flows/limitations y sin campos nuevos; el coordinador conserva ausencia de respuesta como brecha. `test_rereview_cannot_infer_dimensions_from_legacy_area_status` fija esa regla en los escenarios documentados.
- [ ] **Step 2: Ejecutar RED.** Ejecutar `test_review_dimensions.py` y `test_reference_layout.py`. Esperado: fallos por instrucciones y referencias todavía de schema 10, no por enlaces inexistentes fabricados.
- [ ] **Step 3: Actualizar referencias y ejemplos.** Documentar los 27 estados obligatorios, precedencia agregada, selección por mecanismo, texto de IDs en packet 1, verificación existente, re-review y compatibilidad 10/11. Revisar todos los «new final schema 10»/«expected-schema 10» operativos: cambiar solo los productores nuevos; preservar ejemplos históricos identificados. Mostrar un ejemplo completo sintético 11 en las pruebas y fragmentos explícitamente parciales en Markdown. Conservar instrucciones operativas en inglés y reportes/docs de usuario en español. Añadir un único bloque unreleased según CONTRIBUTING, sin número de release.
- [ ] **Step 4: Registrar tres escenarios de flujo y su contraste.** (a) Cambio de reintentos: E05, A03 y D05 comparten evidencia y una causa; un hallazgo. (b) Revisor omite respuesta a E05: queda no evaluada/material cuando impide establecer idempotencia, no cubierta/N/A. (c) Re-review de schema 10: no deriva A01–A05 desde A cubierta, conserva original y produce nueva clasificación. Diferenciar expectativas documentadas de una run realmente ejecutada; no afirmar calidad del modelo a partir de strings de tests.
- [ ] **Step 5: Ejecutar GREEN focalizado.** Ejecutar `test_review_dimensions*.py`, `test_review_areas.py`, `test_review_packets.py`, `test_reference_layout.py`, `test_review_delivery.py`, `test_review_publication_policy.py`, `test_review_archive8.py`, `test_review_history.py`, `test_review_latest.py` y `test_review_profiles.py` con unittest discover. Esperado: sin fallos y omisiones explicadas.
- [ ] **Step 6: Ejecutar suite completa una vez.** `python -B -m unittest discover -s tests -v`. Incluye matrices extensas de restart/resource replay; no repetirlas si ya terminaron en esta ejecución. Registrar exit code, conteo, omisiones y duración real. `git diff --check` debe salir sin errores. Fallos de entorno se registran y no equivalen a suite aprobada.
- [ ] **Step 7: Revisar alcance y evidencia.** Confirmar AC1–AC10 del spec con sus tests/escenarios; comprobar que solo se usaron fixtures sintéticas y que el visor no fue tocado. Registrar comandos/resultados observados y compatibilidad no verificada en el nuevo documento de validación. El original de preparación no se reescribe como si hubiese ejecutado implementación.
- [ ] **Step 8: Commit focalizado.** Mensaje `docs(cobertura): exigir trazabilidad explícita de dimensiones` y cierre de implementación solo después de la revisión de rama correspondiente al método elegido.

## Cobertura del spec y revisión propia del plan

| Criterios | Tareas |
|---|---|
| AC1–AC3: catálogo, completitud y agregación | 1 |
| AC4: veredicto y provenance heredada | 2 |
| AC5–AC6: informe, full/brief y comentario público | 3 |
| AC7: gates, identidad y continuidad sin migración | 2, 4 |
| AC8: asignación, respuesta omitida y verificación existente | 4 |
| AC9: política portátil y texto hostil | 3 |
| AC10: legacy sin reconstrucción y datos sintéticos | 1, 2, 4 |

No hay tareas de UI del visor, release, migración ni nuevos agentes de revisión. Las cinco clases de Review Focus tienen pruebas asignadas. Los pasos RED/GREEN son trabajo pendiente; este documento no afirma que el contrato 11 ya exista.

## Handoff

Revisar spec y plan antes de implementar. La petición actual autoriza prepararlos juntos. Para ejecución posterior se recomienda el método nativo secuencial: cuatro tareas relacionadas por un mismo contrato, con revisión de la rama al final según Superpowers. El usuario puede elegir subagent-driven-development; no se lanzan agentes por la preparación de estos documentos.
