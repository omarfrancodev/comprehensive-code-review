# Salidas realizables del restart pendiente

Corrección del sexto CCR del PR 19: [CR-fe27ebb2cf1447d1bf10](https://github.com/omarfrancodev/comprehensive-code-review/pull/19#issuecomment-6209607442), HEAD `3169d27`.

## Alcance

Atender F054 y la alternativa mínima de F052/F050 sin introducir un protocolo nuevo de rollback, reservas ni liberación de claims. F051 y F053 conservan sus garantías. Una salida sugerida es orientativa: nunca concede autoridad para cancelar, continuar o crear una review nueva.

## Decisiones

- Corregir la documentación: el cleanup normal de un owner elimina su sesión. El reintento posterior puede completar sin esa ruta; no vuelve usable ese workspace ni debe buscarse para desbloquear otra revisión. Quitar el ID interno de la etiqueta de la limitación en las instrucciones de uso.
- Ante una ruta seleccionada ausente con claim o transferencia capturados que bloquean el replay, consultar las mismas validaciones puras de abandon-restart. Inspect/lookup del origen mostrarán `abandon_restart` con run, operación e intent exactos solo si el preflight actual lo admite. Recover con inputs exactos devolverá un plan `restart_pending`, sin intentar mutar ni cancelar por su cuenta. Una ruta `missing_unclaimed` no impide el replay existente y no activa esta alternativa.
- Si ya existe una transferencia durable, un sidecar propio o trabajo que impiden cancelar, el diagnóstico propondrá `new_independent_review`: prepare autorizado sin previous-run y con recursos nuevos. El restart anterior seguirá pendiente, preservado y sin recibos sintéticos. No se afirma resolución de F052 en esta fase.
- Los errores de integridad de los archivos propios, incluida la reserva, se conservan como errores; el diagnóstico no los transforma en una autorización para trabajar. Una excepción privada derivada de ValueError distingue estados verificados que no admiten cancelación de errores de identidad/integridad; el mutador mantiene sus mismos rechazos. La lectura no toma decisiones durables; la cancelación real vuelve a validar bajo locks.
- La adopción parcial de varias sesiones (F050) mantiene su límite. Su prueba debe ejecutar la alternativa independiente usando recursos nuevos, verificar su ownership y demostrar que origen, sucesor, otro owner y sesiones anteriores no cambian.
- Aclarar el alcance de recover_source: requiere un origen verificable. Un traspaso entrante pendiente sin origen no se certifica ready ni se recupera eludiendo sus gates.

## Verificación

Regresiones RED de inspect/lookup/recover antes y después de la intención durable con workspace ausente; una ejecución CLI de recover; prueba de la review independiente con recursos nuevos; preservación de archivos y claims. Reutilizar las pruebas de F051/F053 y del recibo de cancelación. No repetir módulos ajenos ni publicar una versión.
