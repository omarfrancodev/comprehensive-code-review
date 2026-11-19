# Validación de las tareas 3 y 4 de CCR

Se compararon los fixtures del worktree con los puntos de entrada de CCR 3.7.0 en `1ff71c50a7d1d1d6d83cfb811ec893f2f61a5feb`. La columna de lecturas cuenta las aperturas de los archivos de evidencia entregados al comando. La columna de renders incluye el de la lectura interna del destino compacto.

| Fixture | Lecturas de insumos antes → ahora | Renders antes → ahora |
|---|---:|---:|
| Retención completa con contexto y seis fuentes | 15 → 7 | 2 → 1 |
| Retención compacta sin disclosure | 4 → 4 | 4 → 2 |
| Retención compacta con disclosure | 5 → 5 | 4 → 2 |

La retención completa lee una vez el contexto y cada fuente explícita. El preflight, las comprobaciones de ejecución y la escritura usan esos bytes. Si cambia el archivo de entrada después de la captura, se conservan los bytes ya validados. Un cambio en el archivo retenido falla en la lectura independiente. Los reintentos vuelven a capturar las fuentes y solo completan el inventario de hashes fijado por la intención durable.

En ambos compactos se renderiza una vez para escribir y otra al leer el destino publicado. El informe y los hashes coinciden cuando el caller reintenta la misma retención con un informe válido explícito. Se rechaza un informe explícito incompatible. Las cifras cuentan operaciones del helper y no estiman tokens ni latencia de una revisión.

Se conservan los archivos separados para streams y pruebas de ejecución aunque coincida su hash. El receipt exige referencias distintas para stdout y stderr y verifica los bytes por referencia. Los receipts también vinculan cada check con su identidad, revisión y propósito. Compartir bytes de una misma referencia dentro de la operación evita lecturas repetidas sin cambiar esos roles ni el formato leído por archivos históricos.

`inspect --summary` distingue el preflight de candidato, el cambio de insumos, la recuperación de una intención y el cierre pendiente. El caso de candidato reparable conservó la traza y solo añadió el evento de retención al usar el candidato corregido. `finish` conserva el gate de retención, usa la observación y los receipts existentes para cerrar y pasa el resultado por `validate --require-complete`. Las pruebas cubren la limpieza pendiente con sesión presente y después de borrarla, los recibos conflictivos, la interrupción de la escritura del disclosure y un fallo en la lectura final.

Los cinco grupos de regresión ejecutaron 347 casos. Pasaron 344 y el entorno de Windows omitió tres por restricciones de enlaces. Las pruebas incluyen compatibilidad de CLI, retención y cierre, archivos históricos, disclosure, ejecución, checkpoints, claims y recuperación. La prueba de interrupción después del borrado confirmó que el resumen devuelve el recurso y el ID de la intención para recuperar el receipt. La inspección sin resumen conserva el formato anterior.

La matriz pendiente `test_review_restart_resources.RestartResourceReplayTests.test_claimed_workspace_all_transfer_replacements` pasó en el grupo original de las tareas 1 y 2. También pasó al ejecutarla de forma aislada en el worktree con los cambios de las tareas 3 y 4 (1 caso en 1 871,627 s). La matriz interrumpe las escrituras de transferencia antes y después de cada reemplazo y comprueba tanto el reintento como la recuperación.

[Plan](../superpowers/plans/2026-11-12-ccr-fiabilidad-y-eficiencia.md) · [Pruebas de retención y cierre](../../tests/test_review_closure_consistency.py) · [Pruebas del compacto](../../tests/test_review_compact_fixes.py)
