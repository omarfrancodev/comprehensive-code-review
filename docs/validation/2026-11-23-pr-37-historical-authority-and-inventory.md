# Autoridad histórica e inventario de cierre del PR 37

Fecha 2026-11-23. Base de las correcciones `e086ace6492b749fd27d7cd0f496274facee21e5`.

El [re-review CR-c43c7dc0ce79492db66c](https://github.com/omarfrancodev/comprehensive-code-review/pull/37#issuecomment-7109708019) confirmó F023–F025 y registró cuatro casos adicionales.

| Hallazgo | Caso comprobado | Comportamiento requerido |
| --- | --- | --- |
| F026 | El lector compacto rechaza una atribución v3 preliminar que aceptó su productor. | Leer los bytes históricos con las reglas acreditadas de ese formato y aplicar la atribución corregida a las escrituras nuevas. |
| F027 | Una disposición de v1 copiada a lineage v2 se interpreta como otro acto al adoptar v3. | Conservar las condiciones e IDs y distinguir los actos propios mediante la evidencia histórica seleccionada. Indicar incertidumbre cuando la procedencia sea incompleta. |
| F028 | Un cierre interrumpido escribe antes de detectar que falta evidencia ajena al plan de reemplazo. | Rechazar antes de escribir, incluso si la observación de cierre es válida. |
| F029 | Un plan íntegro sin sidecar de divulgación requiere un reintento expreso. | Reconstruir y verificar el plan exacto antes del reintento automático o expreso. |

El cierre valida los archivos retenidos ajenos al plan antes de aplicar la transición. Para los reemplazos usa los bytes reconstruidos y exige el inventario planeado exacto. Se conserva la comprobación de la observación y de los recursos bajo bloqueo. Si ya no se dispone del registro necesario para reconstruir el plan, el diagnóstico preserva el archivo.

Las regresiones de cierre reprodujeron la escritura prematura y el rechazo del plan recuperable en la base. Después del ajuste aprobaron seis pruebas focalizadas que cubren evidencia no planeada ausente, reconstrucción de informe, divulgación y handoff, un plan alterado y el reintento con el marcador consolidado o en transición. Se comprobaron además cierre temprano, replay histórico expreso y claims activos.

El lector compacto verificó los mismos once archivos de un resultado v3 preliminar producido con los módulos de `157a894`. El snapshot quedó intacto. La escritura guiada actual rechaza ese candidato con el AU adicional y el lector rechaza evidencia alterada. La compatibilidad histórica opera sobre archivos retenidos y mantiene sus comprobaciones de estructura, fuentes y captura.

Cuando el inventario del v2 acredita un precursor relevante, `followup-baseline` ofrece su ID, ruta local y SHA-256. El v3 puede retener una copia exacta con `previous.legacy_source` y verificarla contra el enlace del v2. Se conserva la primera publicación que los bytes seleccionados pueden acreditar. Si la evidencia no distingue dos atribuciones idénticas de un grupo, se mantiene la disposición y se conserva `history_incomplete`. La prueba nativa v1→v2→v3 conserva el alias y muestra la condición una vez. Otros casos preservan decisiones distintas de un alias y dos actos independientes de texto idéntico.

La revisión independiente del delta comprobó que dos actos acreditados sobreviven a la consolidación y que un tercer alias copiado comparte el AU existente. Rechazó un AU adicional sin evidencia. También recuperó dos puntos de interrupción con handoff y sin divulgación. El resumen dejó intacto el archivo, el lector completo verificó los hashes resultantes y la traza registró un único cierre.

## Verificación

La selección de adopción, procedencia, lineage, redacción, fixture histórico y dependencias ejecutó 72 pruebas en 28.235 s. Todas pasaron, incluida la proyección portable del descriptor adicional.

La batería integrada ejecutó 116 pruebas distintas con Python 3.14.3 en Windows, sin errores, fallos ni omisiones, en 407.977 s. Se repartió en tres procesos con temporales independientes. Pasaron 29 casos de proyección, preflight y referencias, 70 de reutilización, compactos, divulgación y recuperación atómica, y 17 de transiciones de cierre e integridad. La huella de scripts, tests y referencias se conservó durante la ejecución. Se excluyeron de los procesos de prueba únicamente los overrides de Sites que el harness inyecta en Git. La suite global de la ronda anterior conserva su propio resultado.

En una selección intermedia y en una repetición aislada se observó un error en `test_review_compact_archive.CompactPrepareTests.test_concurrent_preparations_remove_only_their_verified_losing_build`. En Windows, el proceso que perdió el rename recibió `WinError 183` y luego falló el cotejo de identidad de la reserva ganadora. Una comparación posterior en fixtures desechables obtuvo 16/16 con el módulo de `e086ace` y 16/16 con el actual. El contraste de funciones confirmó que el único cambio en `compact.py` dentro de este delta está en `read_compact`, fuera de esa ruta de preparación. El error previo sigue registrado y su causa específica queda sin establecer.
