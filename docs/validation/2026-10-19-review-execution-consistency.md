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

## Segunda revisión del comentario CCR de PR #27

El 2026-10-20 se repasaron otra vez F001, F002, F003 y F004 contra el código y se detectó que la primera corrección de F004 sólo protegía la validación retenida: la captura comparaba `cwd` con un campo `executor_workspace` del mismo request, pero no comprobaba que ese ID estuviera ligado a ese workspace en el contexto registrado. Una reproducción con X1 registrado en A confirmó que se aceptaba y ejecutaba un request atribuido a X1 desde B. La captura ahora lee `evidence/context.json`, requiere una única entrada para el executor y compara su workspace normalizado con `cwd` y `executor_workspace` antes de consultar Git o iniciar el proceso. Se añadió una regresión con dos workspaces de la misma sesión para este caso.

| Verificación actualizada | Resultado |
|---|---|
| `test_review_check_receipts.py` | 11/11, exit 0; incluye captura exitosa, rechazos previos al proceso y el binding X1/A frente a captura en B. |
| `test_retention_preflight_and_gate_verify_selected_receipt_bytes` | 1/1, exit 0; integración de captura, preflight, retención y verificación de recibo. |
| Re-revisión de F001/F002/F003 | Referencias históricas S001/S002+, digest aliasado y binding `command`/`argv` quedan cubiertos por las pruebas focalizadas existentes. |
| Regresión global | No se volvió a ejecutar; este resultado focalizado no acredita toda la suite. |

Para estas pruebas se usó el intérprete Python empaquetado y TEMP/TMP dentro del worktree autorizado. Esto evitó el fallo de permisos del directorio temporal de Windows observado en el primer intento; los resultados no se extrapolan a la suite completa.

## Re-revisión CCR posterior del PR #27

El comentario `CR-8941793c82294bc38ed5` evaluó `24bb9e7` y confirmó que la transición todavía hacía mutable la referencia de S001. También encontró que el gate de descripción/requisitos no seguía aliases validados hasta las claves capturadas y que el filtro de texto rechazaba `command` con saltos de línea o tabuladores aunque coincidiera con `shlex.join(argv)`. Las tres reproducciones fallaban antes de corregir el código.

La selección inicial nueva se almacena desde preparación como `evidence/context.json#profile_history/0/profile`. Para runs abiertos anteriores, el gate resuelve la referencia legacy `#profile` a esa fila histórica cuando el contexto ya contiene historia; conserva el valor/evento de S001 y permite validar la transición completa sin reiniciar. La pertenencia de descripción y requisitos ahora acepta una clave capturada solo cuando el índice valida su alias y su digest; una clave ajena con el mismo hash sigue siendo rechazada. La captura y la validación del recibo comparan el comando completo con `shlex.join(argv)` y conservan el límite de longitud mientras admiten controles literales permitidos por `argv`.

| Verificación posterior | Resultado |
|---|---|
| `test_review_references.py` | 7/7, exit 0; referencia histórica estable y compatibilidad legacy de S001. |
| `test_review_reference_index.py` | 13/13, exit 0; gate de retención con transición, aliases para descripción/requisitos y rechazo de una fuente ajena con hash coincidente. |
| `test_review_check_receipts.py` | 13/13, exit 0; captura y validación aceptan `argv` multilínea/tabulado; mismatches anteriores de comando y workspace siguen rechazándose. |
| `test_review_setup.py`, `test_review_preflight.py`, `test_review_profiles.py` | 8/8, 9/9 y 25/25, respectivamente, exit 0. |
| `test_review_artifacts.py` | 54 pruebas, 2 omitidas por plataforma, exit 0 con TEMP fuera de la instalación del skill. |
| `test_review_check_provenance.py` | 12/12, exit 0; incluye integración de recibo y retención. |
| `test_review_delivery.DeliveryTests.test_reused_historical_check_preserves_execution_provenance` | 1/1, exit 0 con TEMP dentro del worktree después del error de limpieza observado en la batería. |
| Batería de 11 módulos relacionados | 209 pruebas, 2 omitidas; un error de limpieza de `TemporaryDirectory` al apuntar TEMP fuera del checkout. El test afectado pasó aislado con TEMP dentro del worktree. El test de prioridad de raíz pasó aislado con TEMP fuera de la instalación del skill. |
| `git diff --check` | Exit 0, sin errores de whitespace. |

Los hallazgos anteriores F002/F003/F004 siguen cubiertos por la resolución del digest aliasado y las regresiones de binding comando/argv y cwd/workspace. Esta validación es focalizada: no repite la suite global, que anteriormente quedó atascada en una prueba de replay de reservas, ni ejecuta una revisión CCR real contra un MR.
