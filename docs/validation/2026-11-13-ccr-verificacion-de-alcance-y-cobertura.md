# Verificación de alcance y cobertura en CCR

La guía del worktree `docs/ccr-fiabilidad-y-eficiencia` añade dos criterios a la revisión. El verificador debe acreditar la obligación, el disparador que cubre el contrato y la consecuencia antes de confirmar un hallazgo de código. El coordinador debe cotejar las dimensiones propuestas como no aplicables con los flujos, los hallazgos y los checks antes de retener el resultado. Ambos criterios se aplican en los pasos existentes. [Criterio de confirmación](../../references/contracts/assessment.md#confirming-a-code-finding) · [Criterio de cobertura](../../references/contracts/result-contract.md#reconciling-applicability-before-retention)

Se repitieron los controles ciegos de la variante nueva con los insumos, perfiles, modelo y configuración de la comparación del 12 de noviembre. El coordinador y V1 independiente recibieron las secciones actualizadas de la guía. Las expectativas se cotejaron después con los escenarios del repositorio. La comparación usa como referencia las ejecuciones previas de esa misma variante. Cada caso se ejecuta en un contexto nuevo y la caché del proveedor puede variar entre fechas. [Comparación previa](2026-11-12-ccr-comparacion-principio-a-fin.md)

Pasaron 44 pruebas focalizadas de referencias, evaluación, cobertura, escenarios y medición. El primer intento de la regresión de respuesta ejecutó los pasos hasta `finish` y agotó el plazo del coordinador antes del evento de fin del turno. El segundo devolvió un resumen estructurado de V1 donde el banco esperaba una cadena. En otros intentos el coordinador devolvió una lista de citas como evidencia y el banco la pasó al campo de texto sin convertirla. Se amplió el plazo a 300 segundos, se precisó el formato y se convirtió la lista de citas a texto conservando su contenido. Se guardaron las trazas de los intentos y las cifras corresponden a los turnos completados.

| Control | Resultado con la guía ajustada |
|---|---|
| Regresión de respuesta | Conservó el hallazgo bloqueante y `C001` fallido. B02, B03 y B04 pasaron de no aplicables a cubiertas. |
| Normalización | Descartó el defecto sobre `create(None)` al comprobar el contrato y el llamador. La afirmación de almacenamiento quedó sin verificar. |
| Descripción del timeout | Conservó `C001` aprobado y el hallazgo editorial sin bloqueo. |
| Consumidor con IDs enteros | Cerró como aprobable y sin hallazgos. |
| Deuda aceptada | Retuvo F001 como preexistente y no bloqueante. La decisión sigue ligada a los requisitos y exige reconsiderar la aceptación antes de habilitar escrituras. |

Los cinco archivos pasaron la lectura final. Cada repetición completa mantuvo 10 llamadas del coordinador, 17 helpers y cuatro sesiones. Las compactas mantuvieron nueve llamadas, cinco helpers y una sesión por revisión. La comparación comprobó la identidad de los insumos, la secuencia de operaciones y el propósito y resultado de cada check.

| Modo | Casos | Tiempo mediano, guía previa → ajustada | Tokens totales medianos, guía previa → ajustada |
|---|---:|---:|---:|
| Completo | 2 | 128,58 → 171,03 s | 475.039,5 → 548.789 |
| Compacto | 3 | 88,16 → 99,96 s | 260.075 → 262.573 |

Las medianas subieron en esta repetición. Las sesiones se ejecutaron en fechas distintas, con diferencias de caché y dos repeticiones coincidiendo en el tiempo. El banco añadió una aclaración de formato y amplió su plazo. La muestra permite verificar las correcciones observadas y la conservación de las operaciones, pero el costo atribuible al cambio de guía queda sin aislar.

Los eventos, contadores y resultados retenidos están en `.superpowers/sdd/2026-11-12-ccr-fiabilidad-y-eficiencia/end-to-end-guidance-confirmation/` y `.superpowers/sdd/2026-11-12-ccr-fiabilidad-y-eficiencia/end-to-end-guidance-debt/`. `compare_guidance.py` coteja ambas carpetas con las ejecuciones anteriores.
