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

## Segundo seguimiento del PR #30 — 2026-10-23

Cambios posteriores a `0f4c07186c0d399841318eb17a849c22b47c3660`, tras confirmar que F001–F004 quedaron resueltos y reproducir los escenarios nuevos:

| Hallazgo | Corrección y prueba |
|---|---|
| F005 | `validate_reference_selection` comparte la enumeración y límites entre builder/preflight. Las pruebas aceptan exactamente 64 archivos y 64 MiB incluyendo el índice, rechazan un archivo o byte adicional y deduplican destinos de aliases en register/discovery/retain. |
| F006 | `selected_source_bytes` y `select_preflight_sources` comparten lectura entre gate, retain y preflight CLI, con prioridad del candidato explícito y fallback exclusivo a inventario verificado. Se comprueban re-retención sin evidence_inputs, lectura CLI sin mutación, rechazo del candidato cambiado y rechazo de un archivo presente sin inventario. |
| F007 | El validador puro admite la gramática de alias keys anidadas seguras. Las pruebas pasan por builder, proyección, mutador closing, replay y cierre, manteniendo los rechazos de rutas inseguras, aliases no declarados y fragmentos inexistentes. |

Las regresiones de F005–F007 fallaron antes de corregir el producto. Una prueba negativa adicional necesitó crear su directorio evidence para alcanzar el guard que pretendía comprobar; ese error del fixture no se contó como reproducción funcional. Las siete pruebas nuevas pasaron después: 7/7, exit 0, 7.428 s. La comprobación positiva de F006 se amplió además al adaptador CLI antes de iniciar la suite completa.

La validación usa el Python administrado con TEMP explícito propio y ejecución fuera del sandbox para evitar las restricciones observadas en los intentos anteriores. El runner conserva la selección completa de `unittest.discover`, emite progreso por subcaso y no modifica resultados, omisiones ni aserciones.

### Suite completa y repetición acotada

La ejecución completa concluyó los 789 casos en 2191.694 s: 785 aprobados, 1 error y 3 omisiones, exit 1. Las 158 pruebas de los módulos focalizados (los 151 anteriores más siete regresiones nuevas) pasaron sin omisiones ni errores dentro de esa misma corrida.

El error fue `PermissionError: [WinError 5]` en `os.replace` del marcador `.review-ownership.json`, dentro de `test_review_restart_resources.RestartResourceReplayTests.test_unclaimed_workspace_all_adoption_replacements`, subcaso `write=2, boundary=after, route=retry`. No fue una aserción de los contratos modificados. El prefijo de la matriz pasó en una reproducción diagnóstica; después se ejecutó la prueba completa original, sin filtrar subcasos ni modificar su comportamiento:

```text
python -B -m unittest -v test_review_restart_resources.RestartResourceReplayTests.test_unclaimed_workspace_all_adoption_replacements
Ran 1 test in 113.667s
OK
```

La repetición completa obtuvo exit 0. La causa externa específica del permiso denegado no quedó determinada; no se atribuye a antivirus, ACL ni otro proceso sin evidencia. Se conserva la incidencia de la primera corrida y no se afirma que haya existido una ejecución monolítica limpia.

Las tres omisiones fueron por falta de privilegios de symlinks en Windows: `ArchiveTests.test_symlink_roots_inputs_and_archived_files_are_refused`, `LockFileSafetyTests.test_existing_final_symlink_is_refused_without_touching_target` y `LockFileSafetyTests.test_final_link_replacement_after_identity_check_is_refused`. Los casos de junctions, hardlinks y sincronización entre clones que antes se omitieron sí concluyeron en esta ejecución.

No quedan casos sin observar de la selección ampliada: los 23 pendientes anteriores se ejecutaron. Sigue pendiente una corrida global con exit 0 para aprobar estrictamente el gate amplio del plan; la matriz que registró el error sí pasó completa en aislamiento. `git diff --check origin/main` terminó sin errores sobre el candidato acumulado.

## Tercer seguimiento del PR #30 — 2026-10-24

El comentario `issuecomment-6387350881`, sobre `d0847ed47fbdf3bb72d62950026de274462181b4`, confirma F001–F007 y señala F008: el emparejamiento independiente usa despachos proyectados, pero el gate del verificador final consultaba los eventos originales. Un inicio V1 con actor coordinador y executor null seguía rechazándose aunque una anotación válida recuperase su identidad.

Se comparte una vista de inicios entre el orden de perfil, el emparejamiento independiente y el gate final. Los inicios agent se proyectan; los inicios estáticos y los resultados conservan su representación original. La anotación sólo aporta identidad: no mueve sequence ni modifica los eventos suministrados.

### Reproducción y regresiones

Antes de corregir el producto se ejecutaron tres pruebas: el subcaso D1 pasó, el subcaso V1 falló y la integración retain/close produjo el mismo `fulfilled review requires one fresh verifier after the final discovery batch`. El control negativo de V1 anticipado pasó. Resultado: 3 pruebas, un failure y un error, exit 1; ambos fallos positivos alcanzaron el gate reportado.

Después de corregirlo, `python -B -m unittest -v test_review_execution_policy test_review_closure_consistency` pasó 46/46 en 72.385 s, exit 0, sin omisiones. Incluye:

- Proyección pura para D1 y V1 con actor coordinador, identidad ausente en el original e inmutabilidad de la entrada.
- Rechazo de un V1 cuyo inicio precede al último discovery, aunque su anotación sea posterior.
- Retain, validate y close reales con identidad V1 recuperada mediante alias anidado, prefijo de traza intacto y exactamente un inicio y resultado V1.

### Entorno de la suite completa

Se cargan los 791 casos mediante `unittest.defaultTestLoader.discover` desde las rutas absolutas del repositorio y se ejecutan con CWD y TEMP/TMP en un directorio temporal corto propio. Esto también acorta los fixtures de recibos que usan `Path.cwd()`, responsables del `$GIT_DIR too big` observado por el revisor. El observador registra resultados y progreso de subcasos sin alterar la selección, las aserciones ni los skips. Los intentos históricos anteriores conservan sus resultados; no se sustituyen por los de esta corrida.

### Resultado global

La ejecución completa terminó los 791 casos en 1970.371 s, exit 0: **788 aprobados, cero fallos, cero errores y 3 omisiones**. Las regresiones D1/V1 y el rechazo del verificador anticipado pasaron dentro de esa misma selección. También pasaron `CaptureCheckTests.test_capture_accepts_canonical_command_with_literal_newline_and_tab` y la matriz completa `RestartResourceReplayTests.test_unclaimed_workspace_all_adoption_replacements`; no se necesitó repetir ni interrumpir esta corrida.

Las omisiones corresponden exclusivamente al privilegio de symlinks de Windows:

- `ArchiveTests.test_symlink_roots_inputs_and_archived_files_are_refused`.
- `LockFileSafetyTests.test_existing_final_symlink_is_refused_without_touching_target`.
- `LockFileSafetyTests.test_final_link_replacement_after_identity_check_is_refused`.

El gate amplio del plan queda completado con esas tres limitaciones de entorno declaradas. Los resultados históricos incompletos o con errores siguen registrados arriba; ya no representan el estado de la validación actual. `git diff --check origin/main` se verifica además sobre el diff acumulado antes del commit.

## Cuarto seguimiento del PR #30 — 2026-10-24

El comentario [F009](https://github.com/omarfrancodev/comprehensive-code-review/pull/30#issuecomment-6388770274), sobre `711e89ee4a8925250c01fcf597b2a629d8d1f4d7`, confirma F008 y detecta un defecto preexistente dentro de A7: un despacho V1 anticipado acredita independencia y otro `grouped-verification/started` tardío acredita frescura. Las dos comprobaciones podían aprobar eventos distintos del mismo contexto.

### Corrección

El emparejamiento independiente y el gate final comparten la selección del primer despacho proyectado del brief y la identidad completa del resultado (`executor.name` y `executor.provider_id`), anterior al hito de finalización correspondiente. El despacho original debe ser posterior al último discovery. Un hito de etapa posterior, otra identidad con el mismo nombre, una coincidencia sólo por actor o repetir el mismo contexto no renuevan ese despacho. Se conserva el inicio de etapa estático/same-session, ordenado antes de su resultado.

No se reescriben eventos ni se generan despachos, resultados o runs adicionales para completar metadata. El spec, el plan y el changelog incorporan la correlación explícita.

### Reproducción previa a la corrección

| Selección | Resultado sobre el producto anterior |
|---|---|
| `test_later_start_cannot_replace_early_independent_dispatch` y control positivo same-session | 2 métodos, 8 fallos de subcaso y ningún error, exit 1, 0.010 s. Las variantes combinan identidad explícita/recuperada con etapa tardía, provider distinto, coincidencia sólo por actor y repetición del despacho. Cada negativo obtuvo indebidamente `errors=[]`; el control same-session pasó. |
| `test_retention_rejects_early_verifier_with_later_stage_start_without_writes` | 1 método, 2 fallos de subcaso, exit 1, 2.298 s. La retención real aceptó tanto la identidad explícita como la recuperada, sin lanzar el rechazo esperado. Los eventos se registraron mediante el mutador real y con secuencias consecutivas. |

### Validación de la corrección

La batería de 16 módulos pasó **199/199 en 190.547 s, exit 0, sin omisiones**. Se cargó con `unittest.defaultTestLoader.loadTestsFromNames`, importando tests/scripts mediante rutas absolutas y usando CWD/TEMP/TMP cortos propios:

- `test_review_trace`, `test_review_closure_consistency`, `test_review_setup`, `test_review_preflight`, `test_review_source_selection`, `test_review_reference_index`, `test_review_dispatch`, `test_review_execution_policy`, `test_review_recovery_followup`, `test_review_profiles` y `test_review_profile_names`.
- `test_script_dependencies`, `test_script_layout`, `test_script_pure_validation`, `test_script_execution_boundaries` y `test_script_resource_boundaries`.

Los ocho negativos puros ahora rechazan el inicio anticipado sin modificar la entrada. Los dos negativos de retención rechazan antes de escribir y conservan el snapshot completo del run. Pasan además D1/V1 recuperados, retain/validate/close con alias anidado, el inicio de etapa same-session y un V1 recuperado con provider explícito distinto del de un despacho anterior homónimo.

La suite global de 791 casos documentada arriba corresponde a `711e89e`, antes de F009. No se repitió la suite completa para este ajuste acotado del contrato; el resultado nuevo es la batería de 199 casos de sus consumidores y perfiles. No se atribuye la corrida global histórica a este candidato. `git diff --check origin/main` también se comprueba sobre el diff acumulado antes del commit.

## Quinto seguimiento del PR #30 — 2026-10-24

El comentario [F010](https://github.com/omarfrancodev/comprehensive-code-review/pull/30#issuecomment-6389433786), sobre `61681362231b20379daaaa2186304468268abb44`, confirma F008/F009 y señala una incompatibilidad introducida por el PR: seleccionar toda observación `agent/unchanged` como anotación obliga a recuperar una identidad y una fuente que el hito histórico nunca declaró.

### Corrección y reproducción

`is_identity_annotation` centraliza la intención semántica: provenance recovered o relación records al namespace de eventos locales `E` seguido de dígitos. El estado unchanged por sí solo no basta. Builder, preflight, mutador/replay, proyección, comprobación de fuente retenida y las tres fases de selección/verificación durable usan el mismo predicado. Las observaciones genéricas no aportan identidad a un despacho ni añaden una obligación de retener su source. Los marcadores parciales de recuperación siguen activando la validación y el rechazo antes de escribir.

La reproducción inicial ejecutó cinco métodos: seis fallos de subcaso y dos errores funcionales, exit 1, 2.073 s. Fallaron cuatro combinaciones genéricas del contrato de dispatch y los controles de ejecución final schema 8/10. El mutador rechazó el hito por campos de anotación ausentes y la retención histórica falló al canonicalizar source null. El control de anotaciones parciales inválidas pasó. Después de corregir el producto, diez pruebas dirigidas pasaron en 3.555 s, exit 0.

### Compatibilidad entre versiones

Se extrajeron los scripts/tests y el catálogo original de `9c3fd6b` en un temporal propio, sin modificar código del helper base. Se usó el fixture sintético focused con entradas capturadas y sin un alias de salida ajeno a F010, para aislarlo del defecto de relectura de aliases ya documentado. La preparación auxiliar necesitó incorporar ese catálogo y retirar ese alias del fixture antes de obtener el control base válido; esos intentos no se contaron como reproducciones de F010.

El helper original grabó un hito genérico agent/unchanged, retuvo y validó dos archivos archive8/layout2/final10/trace1: uno en closing y otro completo. El helper corregido validó ambos sin cambios en sus snapshots. Después cerró el primero conservando el prefijo completo de su traza original; ambos pasaron require-complete y la segunda validación conservó todos los bytes. No se usó un run real ni se parcheó un gate de ejecución.

### Regresiones y alcance

La batería de los mismos 16 módulos del cuarto seguimiento pasó **206/206 en 189.321 s, exit 0, sin fallos, errores ni omisiones**. Incluye siete métodos nuevos: hitos genéricos en dispatch, ejecución schema8/schema10 y preflight; registro en processing/closing; historia retenida y validación completa inmutable; anotaciones parciales rechazadas en contrato y mutador sin escritura. Las regresiones F008/F009 y los límites de arquitectura también pasan.

La revisión final añadió dos controles de referencias externas cuyo texto empieza con E: fallaron al usar sólo startswith y justificaron acotar el namespace a E seguido de dígitos. Tras ese ajuste se volvió a ejecutar todo `test_review_dispatch`: **7/7, exit 0, 0.002 s**, incluidos los nuevos subcasos y los rechazos de anotaciones inválidas. Este ajuste final no se presenta como otra corrida de los 206 casos.

No se repitió la suite global: los 791 casos históricos siguen correspondiendo a `711e89e`. Spec, plan, referencia de trazas, índice de módulos y changelog se actualizan con el criterio compartido. Se comprueba además `git diff --check origin/main` sobre el diff acumulado antes del commit.

## Sexto seguimiento del PR #30 — 2026-10-24

El [seguimiento de F010](https://github.com/omarfrancodev/comprehensive-code-review/pull/30#issuecomment-6390585077), sobre `39b41152a480f6a59dfd5ed3e7ff367095e2fe1b`, demuestra que la corrección anterior era parcial: recovered y records locales ya eran legales en la base. Ninguno podía reservarse retrospectivamente para identificar una recuperación de identidad.

### Discriminador explícito

Se añade el tipo externo `dispatch-identity` a trace schema 1. `is_identity_annotation` reconoce sólo ese tipo, sin depender del status ni de sus otros campos. Una anotación explícita incompleta o con status incorrecto sigue pasando por la validación completa y se rechaza antes de escribir. Parser, builder, preflight y los consumidores existentes usan este tipo; la identidad se proyecta sobre el despacho original y no crea otra ejecución.

Todo agent/unchanged antiguo conserva su semántica, incluso con recovered, records locales, ambos combinados o todos los campos que antes se parecían a una anotación. No se reinterpretan ni reescriben esos eventos y tampoco se usan para completar una identidad ausente. Se conservan archive8/layout2/final10 y el número de versión trace1; los helpers anteriores necesitan actualizarse para aceptar el nuevo valor del enum. Las instrucciones, ejemplos, spec, plan y changelog describen esa condición de lectura.

### Reproducción y comprobaciones dirigidas

Antes del cambio, cinco métodos produjeron nueve fallos de aserción y seis errores funcionales en 8.131 s, exit 1. Los controles históricos recovered, records y ambos fallaron en el contrato; su retención y su emisión durable fallaron al exigir campos o fuentes de identidad que no correspondían. Los controles del nuevo tipo mostraron que todavía no se proyectaba ni se validaban sus payloads parciales. Después del cambio pasaron 15 pruebas dirigidas en 54.407 s, exit 0, incluidos el cierre válido V1 y el rechazo sin escritura de anotaciones incompletas.

La prueba nueva de referencias extrajo los JSON y comprobó las instrucciones principales: detectó cinco referencias al protocolo anterior. Tras actualizarlas, los ejemplos pasan por el builder real y conservan sus campos, con authority null normalizado por defecto. El primer assert posterior a la edición omitía ese default; se ajustó la expectativa del test, sin cambiar el producto. La comprobación dirigida final de documentación, dispatch y rechazo de recuperación implícita pasó 13/13 en 0.007 s, exit 0.

### Historia producida por la base

Se usaron scripts/tests y catálogo originales de `9c3fd6b`, aislados del checkout, con el fixture focused sin alias de salida ajeno al caso. No se modificó código del helper base ni se simularon gates. Un control auxiliar de ubicación de módulo tuvo que comparar rutas Windows sin distinguir mayúsculas antes de ejecutar los casos; ese intento no se contó como fallo funcional.

El helper base creó y validó ocho archivos del formato vigente: plain, recovered, records a un E existente y recovered+records, cada variante en closing y complete. El helper nuevo validó los ocho con snapshots idénticos. Cerró los cuatro pendientes conservando exactamente el prefijo de traza anterior, y los ocho pasaron require-complete sin cambios de bytes durante la validación final. Esto comprueba las dos variantes del review y su combinación, sin migrar una traza completa.

### Batería actual y límites

Los 16 módulos de la batería del cuarto seguimiento pasaron **214/214 en 247.844 s, exit 0, sin fallos, errores ni omisiones**. Incluyen ocho métodos nuevos sobre el candidato anterior: variantes históricas, proyección y rechazo del tipo explícito, historia durable, observaciones nuevas compatibles, prohibición de recuperar identidad desde eventos no marcados y ejemplos documentados ejecutados por el builder. Las regresiones previas, los ejemplos CLI y los límites de arquitectura siguen pasando.

No se repitió la suite global: la corrida histórica de 791 casos permanece ligada a `711e89e`. Esta validación usa el protocolo final explícito y los ocho controles entre versiones; no atribuye al candidato nuevo las corridas anteriores. Se comprueba `git diff --check origin/main` antes del commit.
