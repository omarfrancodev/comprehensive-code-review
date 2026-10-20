# Validación de consistencia de ejecución CCR

## Base y alcance observado

- Rama: `docs/review-execution-consistency`.
- Main actualizado: `09eeb034af211af4481206eb943abb6b85fd38db`.
- HEAD que precede a Task 8: `35dd94ec53e1261276aa29836cc2d987bbfcd555`.
- La implementación integra las Tasks 1–8 del plan. Las pruebas usan repositorios, runs, publicaciones y eventos sintéticos; no se ejecutó ni publicó una revisión contra MR 1021.

## Resultado de Task 8

`inspect` incluye `operational_summary` sólo para un archivo nativo 8/2 íntegro, sin transacciones pendientes. La proyección identifica disposición, fase, sucesor, limpieza y publicación observada; no infiere sucesores desde texto ni liveness desde `processing`. Una segunda lectura de traza/registro vuelve a comprobar sus hashes antes de usarla, para que una modificación concurrente no alimente el resumen.

`continuation_decision` separa recuperación exacta, continuación, reinicio enlazado, historia y preservación. Sólo recomienda reconstruir un candidato no retenido con entradas aplicables y errores `candidate.*`; esa ruta devuelve `new_work: false`. Los tests mantienen el mismo manifiesto sintético y no llaman dispatch. La proyección de publicación posterior usa la observación de traza y no modifica los bytes de `review.json`.

La guía operativa conserva la elección explícita entre rerun y latest, exige preflight antes del primer dispatch y de la retención, mantiene ABCDE/subaspectos, y corrige comentarios mediante contexto estructurado y nuevo render. La guía de archive 8 ahora permite ejecutar los comandos marcados de punta a punta e incluye el índice de referencias en la evidencia del checkpoint.

## Pruebas ejecutadas

Los comandos se ejecutaron desde la raíz del worktree con el intérprete Python empaquetado para la sesión, `PYTHONDONTWRITEBYTECODE=1` y TEMP/TMP dentro del directorio temporal autorizado.

| Comando o selección | Resultado observado |
|---|---|
| `python -m unittest discover -s tests -p test_review_operational_summary.py -v` | 11/11, exit 0, 19.922 s. Cubre reconstrucción en el mismo run, restart con autoridad, recover exacto, historia, fallo de resumen, publicación posterior y cambio de traza entre verificaciones. |
| `test_review_recovery.py` filtrado a los ocho casos de limpieza, continuidad, inspección, restart y fuente ausente | 8/8, exit 0, 43.607 s. |
| `test_review_recovery_followup.py` filtrado a ejemplo archive 8, ejemplo de restart, fuentes inválidas y asignación superseded | 4/4, exit 0, 20.504 s. |
| `test_artifact_lifecycle_policy.py -k selective_loading_and_unknown_observations` | 1/1, exit 0, 3.288 s. |
| `test_review_artifact_layout.py -k register_adds_planned_resources_before_use_without_final_record` | 1/1, exit 0, 3.454 s. |
| `test_reference_layout.py` | 1/1, exit 0. |
| `git diff --check` | Sin errores de whitespace. |

Los fixtures de integración que encontraron contratos anteriores se actualizaron, sin debilitar validación: milestones de agente incluyen el brief activo, contextos de registro conservan el `review_inputs` capturado y el perfil referencia la selección canónica. El test del ejemplo ejecutable comprueba ahora el preflight de ambas fases y los comandos realmente marcados en la documentación.

## Regresión global y límites del host

Se inició `python -m unittest discover -s tests -v`, pero se interrumpió manualmente después de que una prueba de replay de reservas dejó de producir salida durante más de 40 minutos. El proceso no emitió resumen final; esta ejecución no cuenta como suite completa y no se declara `OK`. Varias fallas de fixtures observadas durante esa ejecución se aislaron y sus casos correspondientes pasan en las selecciones focalizadas anteriores. No se reejecutó la suite completa tras esas correcciones.

En este host Windows, las pruebas de symlink/junction indicaron falta de privilegios y se omitieron. La prueba de clon entre repositorios falló dentro de Git for Windows/MSYS2 al crear un objeto con `NtCreateDirectoryObject` (`0xC0000022`). Las pruebas restantes de hardlink/coordinación no se consideran cubiertas por el subconjunto focalizado.

## Evidencia heredada de Tasks 1–7

Estas verificaciones se ejecutaron y quedaron registradas en el ledger local antes de Task 8:

- **R1–R2 / MR 781:** referencias canónicas y perfil rechazado antes de asignar un run; plan vacío y milestone sin asignación rechazados antes de discovery. `test_review_references.py` (3), `test_review_preflight.py` (9) y `test_review_trace.py` (27).
- **R3 / PR 1:** entrada de selección externa no habilita continuidad y la decisión requiere un run enlazado; la barrera conserva briefs y asignaciones. `test_review_setup.py` (6), `test_review_profiles.py` (25) y `test_review_preflight.py` (9).
- **R1/R4 / MR 47:** gramática común rechaza rutas anidadas; índice valida aliases y referencias C004 huérfanas. `test_review_inputs.py` (7), `test_review_layout_v2.py` (6) y `test_review_reference_index.py` (9).
- **R5:** recibos enlazan argv, salida, código de salida, ejecutor y revisión; falta de evidencia queda visible. `test_review_check_receipts.py` (7) y `test_review_check_provenance.py` (12).
- **R7 / MR 1021 sintético:** proyección elimina paths, logs, CS2012 y `-m:1` privados, conserva la validación fallida de producto y revisión base; el borrador es exacto y no admite retoque manual. `test_review_publication_policy.py` (17), `test_review_comment.py` (4), `test_review_contract.py` (34) y `test_review_presentation.py` (12).
- **R8:** sidecar privado registra modelo configurado/observado por actividad sin elevar configuración a observación ni iniciar probes. `test_review_model_usage.py` (9), `test_review_setup.py` (8), `test_review_harness.py` (14) y `test_review_checkpoints.py` (14).

La regeneración y edición de contexto se validaron en fixtures puros: una sola identidad de run, acción `rebuild_candidate` y cero trabajo/dispatch nuevo recomendado. No se atribuye esa comprobación sintética a una ejecución real de CCR.

Después de redactar este informe, se repitió `test_review_operational_summary.py`: 11/11, exit 0, 20.386 s; `test_reference_layout.py`: 1/1, exit 0, 0.079 s; y `git diff --check`: exit 0 (aviso de conversión CRLF/LF del plan). La repetición confirma también que este documento conserva los enlaces y ubicaciones canónicas.

## Seguimiento de hallazgos CCR del PR #27

Se verificaron los cuatro hallazgos del comentario sobre el commit `1d037b76bbe0273f3df869ffb89f0cb58093e598`; todos reproducían una discrepancia real entre código y contrato. El commit `d7bcb0ea82f121cb8712576e0cf712d3c67f26d8` corrige referencias S001/S002+, resolución de digest por alias, y bindings de `command`/`argv` y `cwd`/workspace del executor. El spec y el plan incorporan esos contratos y casos de regresión.

| Verificación posterior | Resultado |
|---|---|
| `test_review_references.py` | 4/4, exit 0; incluye la transición S002 y rechazo de un índice incorrecto. |
| `test_review_reference_index.py` | 10/10, exit 0; incluye una fuente aliasada anidada y hash capturado. |
| `CheckReceiptTests` | 7/7, exit 0; incluye discrepancias de command y workspace en la validación retenida. |
| Barreras de captura para comando/workspace y workspace no propio | 2/2, exit 0. |
| `PreflightTests` | 2/2, exit 0. |
| `test_review_profiles.py` | 25/25, exit 0. |
| `CheckProvenanceTests` | 6/6, exit 0. |
| `git diff --check` | Exit 0, sin errores de whitespace. |

Las pruebas de captura exitosa y retención que crean worktrees no pudieron ejecutar la preparación con Git for Windows en este host: el proceso falla antes de iniciar el helper con `fatal: '$GIT_DIR' too big`. Por eso estas pruebas permanecen pendientes de un runner compatible y la validación posterior es focalizada, no una declaración de suite completa.
