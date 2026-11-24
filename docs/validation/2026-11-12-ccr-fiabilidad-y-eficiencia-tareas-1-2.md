# Validación de las tareas 1 y 2 de CCR

La base es CCR 3.7.0 en `1ff71c50a7d1d1d6d83cfb811ec893f2f61a5feb`. La ejecución cubre las tareas 1 y 2 y el retiro de la captura habitual del modelo. [Plan](../superpowers/plans/2026-11-12-ccr-fiabilidad-y-eficiencia.md).

Se añadieron entradas sintéticas para un riesgo hipotético y una deuda aceptada. El evaluador conserva la respuesta esperada fuera de los insumos del reviewer. Los controles de reutilización, recuperación de cierre y comparación remota fijan el comportamiento de la base para tareas posteriores. [Casos y controles](../../references/maintenance/evaluation.md).

Se usan los mismos validadores con ambas opciones de salida. El camino a archivo ejecuta el binding de siempre y luego escribe el objeto en una sesión propia. El disclosure puede leer esos mismos bytes por referencia y hash, respetando el límite de 128 KiB de la solicitud expandida. Su resultado es idéntico al que genera la ruta con el objeto embebido. La retención calcula el inventario y valida antes de emitir el resumen. La comprobación independiente con `validate --require-complete` sigue siendo parte de la ruta. Se comprobaron equivalencia del objeto, hash del archivo, disclosure, rechazo de evidencia de ejecución ausente, rechazo de ruta ajena y colisión, identidad del run y lectura final. [Pruebas del CLI](../../tests/test_review_compact_cli_output.py).

## Medición mecánica

Fixture de compacto con perfil focused, inputs fijados y reserva común para ambos modos. Host Windows, Codex Desktop y Python 3.14.3. Cada par ejecutó el CLI en procesos separados con el mismo candidato. El binding a archivo usó una sesión propia ya creada. La retención se midió al repetir una retención válida con la misma reserva y el mismo inventario. La suite local corría en paralelo. El ensayo mide stdout y tiempo del subprocess, sin convertirlos a costo del modelo.

| Fase y salida | Invocaciones | Mediana de bytes stdout | Mediana de caracteres stdout | Mediana en ms |
|---|---:|---:|---:|---:|
| Binding por stdout | 5 | 4 149 | 4 145 | 876,1 |
| Binding a archivo | 5 | 337 | 337 | 1 410,1 |
| Retención repetida con inventario en stdout | 5 | 819 | 819 | 1 216,9 |
| Retención repetida con resumen | 5 | 261 | 261 | 1 130,0 |

Antes de modificar el CLI, una invocación del binding en este fixture produjo 4 149 bytes y tardó 887,8 ms. El modo a archivo redujo la transferencia al coordinador en la muestra y añadió comprobación de ownership y escritura local. El modo de retención breve redujo la salida del mismo procesamiento. Estas cifras excluyen selección, discovery, checks, verificación de candidatos y publicación remota.

Para repetir la comparación, usar `CompactOutputTests.inputs_for_bind` del archivo de pruebas, crear una sesión propia y alternar cinco invocaciones del CLI por variante. Medir `len(stdout)` en bytes, `len(stdout.decode('utf-8'))` en caracteres y el tiempo de `subprocess.run`. Para retención, guardar una vez el fixture en el archivo local, repetir con y sin `--summary` y cerrar con la validación del directorio. Las rutas del fixture tienen longitud variable.

Modelo, esfuerzo, tokens de entrada y salida, caché, razonamiento, cuota y costo quedaron desconocidos para ambos modos. Cada fila contiene invocaciones distintas. Las cifras mecánicas y los contadores del proveedor se informan por separado. [Contrato de métricas](../../references/maintenance/measurements.md).

## Decisiones de ejecución

- La ruta a archivo se usa cuando ya existe una sesión propia. En los demás casos se redirige el stdout original directamente a un archivo seleccionado. La elección de persistencia sigue dependiendo de los recursos y obligaciones reales.
- La captura del modelo y del valor desconocido deja de ser parte del flujo habitual. Se conserva la lectura de archivos históricos y la validación de ledgers que se seleccionen explícitamente. La revisión independiente detectó una instrucción que volvía a exigirla en los briefs. Se corrigió en [la referencia de paquetes](../../references/execution/worker-packets.md).
- En Windows, el temporal por defecto produjo un error de permisos y la primera ruta alternativa excedió el límite de Git. Las pruebas se ejecutaron con `TEMP` y `TMP` apuntando a un temporal local autorizado de ruta corta.

## Verificación focalizada

Después de incorporar el disclosure por referencia pasaron 56 casos distintos de CLI, preparación, disclosure, integración, codificación, compatibilidad, dependencias y enlaces. El escenario compacto ejercitó la ruta desde binding hasta lectura del archivo completo, incluidos los rechazos por hash incorrecto, ruta ajena y tamaño excesivo. La prueba de inventario confirmó que los únicos cambios de opciones del CLI son `--session`, `--output` y `--summary`.

La suite amplia se ejecutó por grupos. De 1 331 casos descubiertos, 1 322 pasaron, 8 se omitieron por restricciones del host (enlaces o Git Bash) y una matriz de interrupciones de transferencia de recursos quedó sin resultado al cierre de esta verificación. Las tres pruebas de clonación parcial pasaron al repetirlas fuera de la restricción de Git Bash; el caso de entrega que recibió un acceso denegado al reemplazar un archivo temporal pasó al repetirlo de forma aislada. El inventario del CLI volvió a pasar tras incorporar las tres opciones al fixture de caracterización.

La matriz pendiente, `test_claimed_workspace_all_transfer_replacements`, terminó correctamente. El grupo original cerró con 119 casos y una omisión ya contabilizada. El registro de las [tareas 3 y 4](2026-11-12-ccr-fiabilidad-y-eficiencia-tareas-3-4.md) da continuidad a la verificación.
