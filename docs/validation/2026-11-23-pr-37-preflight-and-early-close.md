# Preflight y recuperación temprana del PR 37

Fecha 2026-11-23. Base `8966c556c15d13ccc786614fb8b20691391abc7c`. El [re-review CR-520b59d8df864eaaa049](https://github.com/omarfrancodev/comprehensive-code-review/pull/37#issuecomment-7113783099) confirmó F030 y F031 y abrió F032 y F033 como reservas.

**F032.** El preflight de retención consulta la misma verificación del antecedente que usa el escritor cuando el candidato supera los controles estructurales. Si el v2 ofrece un precursor inventariado, el preflight verifica el descriptor y sus bytes seleccionados. La incidencia señala `candidate.assessment.previous.legacy_source` y el archivo del inventario que aporta la evidencia. El resumen de inspección consume el mismo diagnóstico. El validador puro conserva sus comprobaciones sin acceso a archivos.

La regresión usa un antecedente compacto válido y un candidato nativo v3. En la base, el preflight devolvió código 0 tanto sin descriptor como con descriptor sin bytes seleccionados. La corrección rechaza esas entradas y una copia alterada, sin modificar el candidato ni el antecedente. Con la copia exacta, el preflight pasa y la retención y el cierre validan el archivo completo.

La revisión independiente detectó que el primer ajuste podía perder el diagnóstico JSON al recibir un campo `assessment` con tipo inesperado en un esquema anterior. Se reprodujo y se acotó la comprobación adicional a candidatos final 13, que es el esquema que admite la extensión. Se agregó una regresión para la respuesta estructurada.

**F033.** Si el segundo cierre aún está en `closing`, tanto el manifiesto como el registro retenido todavía indican limpieza pendiente y el hash autentica el registro previo, el replay puede usar la observación terminal guardada aunque las dos listas de residuales difieran. Las comprobaciones de la observación y los recursos siguen bajo bloqueo antes de aplicar el cierre. La transición temprana entre estados terminales sigue requiriendo la ruta expresa.

La regresión reproduce dos cortes consecutivos. El primero conserva en el registro una lista de residuales más reciente que la del manifiesto. El segundo guarda la observación terminal y se interrumpe antes de persistir el plan. En la base, el resumen indicaba conservar. En el ajuste, recomienda el reintento sin cambiar archivos y `finish` completa el cierre automático y pasa la lectura final.

La selección final de preflight, compatibilidad histórica, dependencias y referencias pasó 33 pruebas en 51.713 s. La selección focalizada de cierre pasó nueve pruebas en 253.396 s, sin omisiones. Cubre metadatos y recibos durables, observaciones ambiguas o desprendidas, recursos y reintentos interrumpidos. El caso temprano comprueba un único evento terminal, lectura completa e idempotencia por bytes. Ambas selecciones se ejecutaron con Python 3.14.3 en Windows.
