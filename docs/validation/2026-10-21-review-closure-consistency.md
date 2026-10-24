# Validación de consistencia de fuentes, despachos y cierre

## Alcance

- Rama: `docs/review-closure-consistency`.
- Base: `9c3fd6bd7e3a21226e2fcd6dca65c42f512bceea` (main, CCR 3.0.0).
- HEAD previo a Task 5: `4cf55603915f2a6ab5c13a3d8c1804c8ca8a0ac1`.
- La implementación y las pruebas usan archivos, trazas, sesiones y repositorios sintéticos. No se modificó el run de `prosur-packages`, un MR ni recursos reales de revisión.

## Resultado

Las cinco tareas del plan están implementadas. La captura inicial y retención comparten la selección del índice; una fuente de despacho debe estar seleccionada y coincidir con la identidad anotada; el replay idéntico no agrega eventos; y el ciclo de anotación, retención, cleanup de workspace propio y cierre se valida con las operaciones reales. La guía de archive 8 ahora incluye el índice en cada preflight y distingue el flujo focused de la recuperación tardía para un despacho independiente.

La validación inicial focalizada pasó. Su intento de suite amplia quedó sin salida durante varios minutos y fue interrumpido manualmente; no emitió resumen y no se considera aprobado. El seguimiento del PR se registra al final de este documento.

## Pruebas ejecutadas

Se usó el Python administrado de la sesión con TEMP/TMP en un directorio temporal de trabajo, retirado después de eliminar el único directorio que dejó la suite interrumpida.

| Comando / selección | Resultado |
|---|---|
| `test_review_trace`, `test_review_closure_consistency`, `test_review_setup`, `test_review_preflight`, `test_review_source_selection`, `test_review_reference_index`, `test_review_dispatch`, `test_review_execution_policy`, `test_review_recovery_followup` | 134/134, exit 0, 285.902 s. Incluye replay idempotente, conflicto, run completo inmutable, fuente ausente/discrepante, cleanup real, y ejemplo documentado ejecutado de punta a punta. |
| `test_script_dependencies`, `test_script_layout`, `test_script_pure_validation` | 8/8, exit 0, 0.638 s. |
| `test_script_execution_boundaries.py` y `test_script_resource_boundaries.py` | 5/5, exit 0, 3.819 s. |
| `python -B -m unittest discover -s tests -p 'test_*.py'` | Inconclusa: avanzó sin errores visibles, dejó de emitir salida por varios minutos y se interrumpió; sin resumen final ni total verificable. |
| `git diff --check` | Exit 0, sin errores de whitespace. |

## Cobertura A1–A10

| Aceptación | Evidencia |
|---|---|
| A1 | Builder y setup conservan hashes del índice y de inputs materiales; `test_review_source_selection` y `test_review_setup`. |
| A2 | Setup/preflight rechazan inputs ausentes o modificados antes del dispatch; `test_review_setup` y `test_review_preflight`. |
| A3 | Retain y validate vuelven a resolver las mismas fuentes; `test_retain_then_validate_reloads_all_indexed_sources`. |
| A4 | Fuentes no inventariadas, ausentes, modificadas, no seleccionadas o con identidad discrepante bloquean sin iniciar cleanup; pruebas de `test_review_closure_consistency`. |
| A5 | La descripción unverified y el snapshot de un run ya iniciado se preservan; `test_processing_unverified_snapshot_is_preserved`. |
| A6 | Un despacho independiente nuevo sin executor se rechaza antes de mutar la traza; `test_independent_dispatch_requires_executor` y prueba del mutador. |
| A7 | La anotación proyecta la identidad sobre el inicio original y el replay idéntico es idempotente; `test_late_annotation_keeps_original_order_and_result` y `test_dispatch_annotation_replay_is_idempotent`. |
| A8 | Destinos/conflictos inválidos fallan y los bytes previos de la traza se conservan; pruebas de dispatch y trace. |
| A9 | Workspace propio eliminado con cleanup real; el run pasa `validate(require_complete=True)` sin duplicar resultados. |
| A10 | Skill, referencias, ejemplo y changelog actualizados; el ejemplo archive 8 se ejecuta de extremo a extremo. |

La suite focalizada inicial valida los cambios y límites cercanos. Ese primer intento no obtuvo un resumen final de la suite completa y no demuestra que todos los tests del repositorio hayan pasado.

## Seguimiento del PR #30 — 2026-10-23

Cambios posteriores a `46939c578a7b2d3b66a8246ed0ea5f418fc7f8eb`, contrastados con los cuatro escenarios del comentario de revisión:

| Hallazgo | Corrección y regresión comprobada |
|---|---|
| F001 | Conservar los bytes bajo la clave original de cada entrada material al reconstruir fuentes, además de resolver el alias. `test_material_input_alias_survives_revalidation_and_close` reproduce el fallo de revalidación después de retener y comprueba el cierre real. |
| F002 | Validar cualquier valor JSON parseado como índice. `test_preflight_rejects_non_object_reference_index_with_matching_digest` rechaza lista, null, booleano y string en register/discovery/retain, sin mutar entradas. |
| F003 | Resolver el alias mediante el índice retenido antes del guard de inventario. `test_closing_annotation_alias_replay_returns_original_event_without_writes` verifica el ID/sequence originales y un snapshot inalterado. |
| F004 | Resolver el fragmento de la fuente retenida y cotejar su executor antes del append. `test_closing_annotation_rejects_invalid_fragment_and_executor_without_writes` prueba ambos rechazos con y sin alias, conserva el snapshot y registra después la anotación correcta antes de cerrar. |

Las cuatro regresiones se ejecutaron primero contra el código previo y fallaron por las causas descritas; después pasaron con las correcciones. Una primera ejecución de las pruebas de archivo no alcanzó sus fixtures por permisos del TEMP del sandbox; se repitió con un TEMP explícito permitido. Ese error de entorno no se contó como reproducción funcional. La suite amplia de seguimiento utiliza el mismo TEMP y salida detallada para identificar el último test observado.

También se retiraron las líneas vacías nuevas al final de los cuatro archivos señalados y se corrigieron las rutas del spec y plan en la descripción del PR.

### Resultado del seguimiento

Se ejecutó `python -B -c "import faulthandler, unittest; faulthandler.dump_traceback_later(180, repeat=True); unittest.main(module=None)" discover -s tests -p 'test_*.py' -v`. Ese intento registró un `ERROR` en `test_review_check_receipts.CaptureCheckTests.test_receipt_preserves_literal_argv_and_previous_attempt`, perdió su sesión antes del resumen final y no conservó el traceback de cierre. La prueba se volvió a ejecutar aisladamente: 1/1, exit 0, 11.920 s. No se atribuye una causa al error inicial a partir de ese resultado.

La continuación cargó la misma selección de `unittest` (782 casos), excluyó los casos con resultado confirmado y repartió los 640 pendientes por módulo en tres grupos. Los dos primeros finalizaron: 174 casos en 618.085 s (3 omisiones) y 298 casos en 1168.237 s (sin omisiones), ambos exit 0. El tercero se detuvo deliberadamente por duración en `test_review_restart_resources.RestartResourceReplayTests.test_claimed_workspace_all_transfer_replacements`, con fixtures aún activos y sin resultado de ese caso. Después se ejecutaron sólo las seis pruebas focalizadas que todavía no tenían resultado: 6/6, exit 0, 4.798 s.

| Alcance | Resultado observado |
|---|---|
| Trace, closure_consistency, setup, preflight, source_selection, reference_index, dispatch, execution_policy y recovery_followup | 138/138 aprobadas, incluidas las cuatro nuevas regresiones y sus subcasos. Resultados reunidos de los intentos y grupos, sin repetir casos ya confirmados. |
| script_dependencies, script_layout y script_pure_validation | 8/8 aprobadas. |
| script_execution_boundaries y script_resource_boundaries | 5/5 aprobadas. |
| Total focalizado | 151/151 aprobadas, sin omisiones. |
| Cobertura ampliada con resultado confirmado | 759 de 782 casos: 752 aprobados y 7 omitidos por el entorno. Los 23 restantes incluyen la matriz interrumpida y casos no iniciados; la suite completa permanece inconclusa. |
| `git diff --check origin/main` | Exit 0, también sobre el diff acumulado base → candidato. |

Las siete omisiones corresponden a privilegios Windows de symlinks/junctions/hardlinks y al objeto de sincronización de Git Bash: `ArchiveTests.test_symlink_roots_inputs_and_archived_files_are_refused`, `ArchiveTests.test_windows_junction_root_is_refused`, `SessionClaimSafetyTests.test_registration_accepts_sessions_from_two_clones_of_same_repository`, `LockFileSafetyTests.test_existing_final_symlink_is_refused_without_touching_target`, `LockFileSafetyTests.test_final_hardlink_is_refused_before_writing_foreign_bytes`, `LockFileSafetyTests.test_final_link_replacement_after_identity_check_is_refused` y `CoordinationErrorTests.test_unsafe_final_lock_is_not_reported_as_contention`.

El gate amplio del plan sigue pendiente; estos resultados no equivalen a una ejecución monolítica completa aprobada.
