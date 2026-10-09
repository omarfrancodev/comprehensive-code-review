# Validación de referencias y lifecycle

**Fecha:** 2026-10-09

**Alcance:** implementación del [plan](../plans/2026-10-09-artifact-lifecycle-and-reference-layout.md), basada en la [spec](../specs/2026-10-09-artifact-lifecycle-and-reference-layout-design.md). Los comandos usan fixtures propios, no los reviews reales del equipo.

## Pruebas mecánicas

| Cambio | RED observado | GREEN observado |
|---|---|---|
| Referencias | Faltaban las 20 rutas canónicas. | Layout y enlaces pasan; 32 pruebas de perfiles/presentación/flujo pasan. |
| Lifecycle | Schema era 4, faltaba predicate de inicio y recuperación conservaba prepared. | 96 pruebas pasan, una omitida por capacidad ambiental; cuatro casos centrales de estado/recuperación se verificaron de nuevo al cerrar tarea. |
| Tiempos | Helper sin occurred_at; adaptador/flag ausentes; source no exigido al emitir schema 5. | Cinco casos de tiempos/metadata/recuperación pasan. El barrido de 72 pruebas detectó únicamente un fixture nuevo que solicitaba mediciones de forma explícita; se corrigió la prueba para usar la retención normal y se verificaron cuatro casos centrales. |
| Vínculos | Evento futuro E aceptado. | 69 pruebas de trace, contrato, packets, presentación y enlaces pasan; atribución/límites existentes se conservaron. |
| Política | SKILL no exigía discovery/started y faltaba ejemplo de inicio. | El ejemplo JSON se ejecuta: processing, retención/validación/cierre, tiempo desconocido null y ningún measurements.json. |

La base anterior pasó 224 pruebas, una omitida. Los intentos fallidos por permisos y rutas de TEMP se descartaron por causas ambientales; no se relajaron políticas del producto.

Gate final: `python -B -X utf8 -m unittest discover -s tests` pasó **237 pruebas, una omitida**, en 199.425 segundos; cero errores y cero fallos. La omisión corresponde al privilegio de symlink no disponible en Windows. También pasaron resolución de enlaces, `git diff --check`, las ayudas de prepare/record-event/validate y la correspondencia entre versión del ejemplo de preparación y metadata de SKILL.md.

La revisión independiente de la rama detectó un detalle P3: el ejemplo operativo aún fijaba 2.8.0. Se completó la actualización de versión prevista por la tarea 6 a 2.9.0 y se indicó obtener siempre metadata.version del SKILL cargado; el ejemplo se comprobó mecánicamente. No hubo otros hallazgos accionables, preguntas pendientes ni asuntos menores diferidos. Las excepciones consideradas de estado histórico, retención directa, orden de registro, recuperación e inmutabilidad corresponden al contrato aprobado y sus pruebas. README/instalación siguen identificando 2.8.0 como última release efectivamente publicada mientras 2.9.0 permanece Unreleased.

## Aplicación en contextos frescos

Se realizaron dos muestras acotadas con los mismos tres escenarios de urgencia, presupuesto bajo y presión de presentación/limpieza. La muestra baseline leyó exclusivamente instrucciones v2.8.0 capturadas del commit base; la segunda leyó únicamente la guía nueva y sus referencias aplicables. Ninguna ejecutó un review real ni modificó archivos. Estas pruebas evalúan comprensión de instrucciones, no tiempos de ejecución ni ahorro de tokens.

| Escenario | Baseline | Guía nueva |
|---|---|---|
| Descubrimiento estático focused | No encontró inicio formal ni processing; mantuvo schema 4/prepared. | Eligió discovery/started, archive 5/processing, actor coordinador y tiempos/IDs desconocidos null. |
| Dispatch standard sin relojes/IDs | Conservó orden de registro, pero no encontró occurred_at explícito en la guía. | Distinguió dispatch y resultado, actor/executor/recorder; dejó occurred_at/provider_id null, sin inferir simultaneidad. |
| Interrupción y presión de cleanup | Conservó gates y recursos; recuperación concreta insuficientemente descrita. | Conservó bytes/tiempos y los gates; pidió más precisión del comando de recuperación. Se aclaró register con lista verificada antes de retención o retry de retain/close con entradas originales. |

Citas de resultados baseline:

> “no especifica un evento de inicio de discovery ni una transición a `processing`”

> “El snapshot no define `occurred_at`”

Citas de la muestra nueva:

> “Emitiría `discovery/started` al comenzar el descubrimiento, reutilizando un hito equivalente existente.”

> “No añadiría mediciones, sondas, scripts, spec/plan ni baseline”

Las dos muestras conservaron carga selectiva de workers y rechazaron inventar identidad/actividad. La mejora comprobada es la eliminación de ambigüedad de inicio/tiempos; las reglas anteriores que ya funcionaban no se presentan como defectos corregidos. La aclaración final de recuperación se sustenta también en las pruebas ejecutables de register/retry y no implica una nueva campaña de agentes.

## Límites

El JSONL sigue acreditando registro e integridad respecto al cierre, no la verdad del hallazgo, una identidad humana, un proceso vivo o el orden total entre hosts. Tiempos no expuestos permanecen desconocidos. El visor no se implementó ni se verificó como consumidor en esta rama. No se midieron porcentajes de ahorro ni créditos.
