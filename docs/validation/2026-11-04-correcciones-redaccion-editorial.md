# Correcciones de redacción editorial: F001–F004

**Estado:** correcciones y validación combinada completadas; tres omisiones de symlinks por permisos del host. **Base:** `6f9c869d960780c32f401fb4c14dda5fd34c3f9a`. **Rama:** `fix/redaccion-proyeccion-editorial`. Sin commit ni publicación de estas correcciones.

La revisión `CR-316a81af4670492db33f` confirmó cuatro hallazgos contra el [spec](../superpowers/specs/2026-11-04-redaccion-proyeccion-editorial-design.md) y el [plan](../superpowers/plans/2026-11-04-redaccion-proyeccion-editorial.md). Se corrigieron las causas, sin editar los artifacts ni los resultados de esa revisión.

| Hallazgo | Cambio | Verificación |
|---|---|---|
| F001, P1 introducido | Reconocer campos tras marcadores numerados con punto o paréntesis, conservando la prosa narrativa. | Ocultar valores en `safe_text` y draft 4; verificar el borrador resultante. |
| F002, P1 introducido | Identificar delimitadores completos de código y fences, en lugar de contar backticks por paridad. Los spans inline requieren cierre correspondiente; los fences comprueban contenedor/indentación, pueden cerrar con un marcador mayor o continuar hasta EOF. | Delimitadores dobles/cuádruples, ticks interiores, fences en listas/citas, marcadores que son contenido del bloque y prosa después del cierre; conservar el control negativo de prosa y marcador escapado. |
| F003, P2 introducido | Incluir IDs de revisiones previas en el rechazo de identidades sensibles. | Render, handoff público y prepare rechazan la colisión sin mutar el registro; una identidad no sensible permanece visible. |
| F004, P1 preexistente dentro del alcance | Validar todo el contexto de entrega y reunir sus valores antes de proyectar cualquier sección, incluida la vista acreditada de checks. | Entregas full/brief reales, copia anterior a su declaración, protección del contexto y del registro portable, comandos/recursos/explicaciones acreditados, rechazo de identidad sensible antes de salida e inventarios originales idénticos. |

## Evidencia observada

Las pruebas se añadieron antes de modificar producción. El primer RED ejecutó nueve pruebas y reportó 15 fallos, incluyendo subcasos; no tuvo errores ni omisiones. Dos de esas nueve eran tests importados con una clase de fixture. El import se cambió a un módulo para evitar descubrirlos dos veces: las siete pruebas propias y sus aserciones permanecen en `test_review_editorial_review_fixes.py`.

La revisión del flujo de F004 identificó que la vista acreditada se construía antes de reunir los secretos del contexto. Se añadieron dos pruebas propias más: fallaron en tres casos, sin errores de fixture, antes de extender el mismo conjunto a comandos, recursos y explicaciones. El módulo final contiene nueve pruebas propias. La vista se modifica como copia de presentación; los bytes del disclosure original no cambian.

| Ejecución | Pruebas | Fallos | Errores | Omitidas |
|---|---:|---:|---:|---:|
| F001 después de corregir | 1 | 0 | 0 | 0 |
| F002 y controles existentes de texto público | 7 | 0 | 0 | 0 |
| F003, rechazo y control positivo | 2 | 0 | 0 | 0 |
| Los cuatro hallazgos y controles asociados | 7 | 0 | 0 | 0 |
| Compatibilidad focal | 60 | 0 | 0 | 0 |
| F004, detalle de checks antes de completar la corrección | 2 | 3 | 0 | 0 |
| F004 completo, histórico, CLI y corpus de privacidad | 38 | 0 | 0 | 0 |
| Delimitadores de código y controles de texto público, después de simplificar el recorrido | 10 | 0 | 0 | 0 |
| Fences dentro de contenedores, antes del ajuste final de F002 | 1 | 3 | 0 | 0 |
| Contenido de un fence que no debe cerrarlo, antes de completar ese ajuste | 1 | 3 | 0 | 0 |
| F002 con contenedores/cierres y controles públicos | 10 | 0 | 0 | 0 |
| Suite completa | 1246 | 0 | 0 | 3 |
| Primera selección de todos los consumidores afectados | 184 | 0 | 0 | 0 |
| Consumidores afectados sobre el código definitivo | 184 | 0 | 0 | 0 |

La selección de 60 pruebas incluye fixtures de drafts 2/3, disclosure histórico transitivo, integridad de draft 4, la integración CLI prepare/overwrite, entregas y privacidad, y límites entre módulos. La CLI que falló por longitud de `$GIT_DIR` durante el review pasó ahora usando un TEMP propio y corto, sin cambios en el test ni en la configuración de Git.

Los logs y conteos de ejecución permanecen en `.worktrees/validation-editorial-fixes/`, fuera de los archivos versionados. Las pruebas usan Python con `-B -X utf8`, biblioteca estándar y un TEMP de pruebas propio. No se instalaron dependencias ni se usaron datos del proyecto del incidente.

## Cierre y compatibilidad

La primera ejecución amplia se detuvo al confirmar la salida adicional de F004, verificando primero el PID y el comando exactos del runner propio. Su log se conserva como incompleto y no cuenta como validación aprobada. La ejecución amplia posterior terminó en 2705,797 segundos, con 1246 pruebas: 1243 aprobadas, cero fallos/errores y tres omisiones.

Durante su cierre se añadieron los controles de F002 sobre contenedores y cierres, con fallo previo y corrección. La suite había cargado el clasificador anterior a ese último ajuste. Por ello se reejecutó sobre el código definitivo la selección completa de consumidores afectados: 184 pruebas de publicación, comentarios, entregas, disclosure e inmutabilidad pasaron en 260,297 segundos, sin errores ni omisiones. No se presenta la validación combinada como una única invocación completa del estado final. El recorrido de spans conserva posiciones por longitud de delimitador y evita materializar cada marcador individual.

Las omisiones son `test_symlink_roots_inputs_and_archived_files_are_refused`, `test_existing_final_symlink_is_refused_without_touching_target` y `test_final_link_replacement_after_identity_check_is_refused`. Windows devolvió `WinError 1314` al crear symlinks. No se modificaron esos tests ni se consideran aprobados.

No quedan fallos pendientes en la validación combinada. Los 103 módulos Python compilaron en memoria sin errores y `test_reference_layout.py` aprobó la comprobación de enlaces locales. El control de diff y espacios finales no detectó errores; los archivos de producción y la prueba nueva conservaron sus hashes durante la última selección. Se guardaron identidades de las fuentes para distinguir la ejecución amplia de la revalidación final.

No se cambian los schemas finales 1–13, las versiones de artifacts completos/compactos, el contrato editorial ni el draft 4. No se modifican los fixtures históricos ni el dispatch congelado de drafts 2/3. Las entregas nuevas con contexto usan el conjunto de privacidad completo; los archivos retenidos conservan su contenido y sus hashes. No se certifica el viewer externo ni se afirma fidelidad semántica a partir de un hash.
