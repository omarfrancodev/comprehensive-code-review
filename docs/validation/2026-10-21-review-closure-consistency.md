# Validación de consistencia de fuentes, despachos y cierre

## Alcance

- Rama: `docs/review-closure-consistency`.
- Base: `9c3fd6bd7e3a21226e2fcd6dca65c42f512bceea` (main, CCR 3.0.0).
- HEAD previo a Task 5: `4cf55603915f2a6ab5c13a3d8c1804c8ca8a0ac1`.
- La implementación y las pruebas usan archivos, trazas, sesiones y repositorios sintéticos. No se modificó el run de `prosur-packages`, un MR ni recursos reales de revisión.

## Resultado

Las cinco tareas del plan están implementadas. La captura inicial y retención comparten la selección del índice; una fuente de despacho debe estar seleccionada y coincidir con la identidad anotada; el replay idéntico no agrega eventos; y el ciclo de anotación, retención, cleanup de workspace propio y cierre se valida con las operaciones reales. La guía de archive 8 ahora incluye el índice en cada preflight y distingue el flujo focused de la recuperación tardía para un despacho independiente.

La validación focalizada pasó. La suite amplia se inició, pero quedó sin salida durante varios minutos y fue interrumpida manualmente; no emitió resumen y no se considera aprobada.

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

La suite focalizada valida los cambios y límites cercanos. Al no haber un resumen final de la suite completa, este informe no afirma que todos los tests del repositorio hayan pasado.
