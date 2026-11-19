# Comparación de CCR de principio a fin

Se comparó CCR 3.7.0, commit `1ff71c50a7d1d1d6d83cfb811ec893f2f61a5feb`, con las tareas 1 a 8 de `docs/ccr-fiabilidad-y-eficiencia`. La unidad de medida empieza al fijar el diff y termina con la lectura independiente del resultado cerrado. Incluye preparación, descubrimiento, verificación, generación del candidato, retención y limpieza cuando corresponde. [Piloto previo de la fase de archivo](2026-11-12-ccr-piloto-controlado.md)

## Diseño

Se usaron cinco casos sintéticos del repositorio y el mismo Git base/HEAD, requisito, descripción y consumidor en ambos lados de cada par. Los revisores recibieron solo el caso asignado. Las etiquetas y el resultado esperado quedaron fuera de sus prompts. La referencia para la evaluación posterior fueron las pruebas ejecutables de los escenarios. [Insumos](../../tests/fixtures/review_inputs.json) · [Resultados esperados](../../tests/test_review_scenarios.py)

- **Completo, perfil `deep`.** Regresión de respuesta y discrepancia de descripción. Dos descubrimientos con contextos nuevos y un tercer contexto de verificación, con un check real capturado por CCR dentro de un worktree propio. El coordinador permaneció en su sesión original. Se verificó el retenido antes de limpiar y el archivo completo después.
- **Compacto, perfil `focused`.** Normalización, consumidor con IDs enteros y deuda aceptada. El coordinador hizo descubrimiento y una segunda pasada escéptica dentro del mismo contexto. La comprobación fue estática y el cierre exigió `validate --require-complete`.

Se usó Codex app-server con `gpt-6.1-sol`, esfuerzo `high` y herramientas dinámicas acotadas a los fixtures. La guía común fijó las obligaciones y cada versión siguió su secuencia de archivo. La nueva añadió la evaluación estructurada de hallazgos. El controlador montó el esquema 13 a partir de las decisiones que devolvieron los modelos y capturó las sesiones observadas, las salidas y los recibos. Los helpers usados fueron los de cada variante.

La prueba usó PR sintéticos nuevos, un archivo vacío por ejecución y una captura local de Git. Evalúa el recorrido de una revisión nueva desde el alcance hasta la entrega privada. Las rutas de reutilización de un archivo previo, re-review, publicación remota y promoción de compacto a completo tienen sus propias pruebas de contrato.

El tiempo de pared incluye el arranque del coordinador, las sesiones de revisión, los helpers y sus esperas. Excluye la creación inicial de los repositorios de prueba y la comprobación posterior de los bytes. Las llamadas del modelo, los procesos de CCR y los turnos de modelo son contadores distintos. En completo, el coordinador esperó a los dos descubrimientos consecutivos. Los tokens se sumaron a partir de los contadores reales de sesiones distintas, cada una de un solo turno. La entrada incluye la caché y la salida incluye el razonamiento. La caché funcionó según el proveedor. La cuota de cinco horas y los cargos quedaron sin medir.

La guía acotada se derivó del perfil y las obligaciones de ambas versiones. El coordinador no cargó el árbol completo de referencias como en una instalación corriente. La comparación atribuye las diferencias observadas a las variantes de la prueba, que combinan secuencia de artefactos, formato de salida y exigencia de evaluación estructurada. El [piloto previo](2026-11-12-ccr-piloto-controlado.md) aísla el tramo de archivo.

## Criterios de verificación

Para comparar las validaciones se inspeccionaron tres fuentes. Los eventos de Codex acreditan el orden de las llamadas, los turnos y sus contadores. Los archivos retenidos y las respuestas de los helpers acreditan perfil, asignaciones, recibos, evidencia y cierre. Los requisitos, el consumidor y las pruebas del escenario sirven para juzgar omisiones, confirmaciones sin sustento y decisiones de cobertura. Una estructura válida con los 27 IDs solo acredita que cada dimensión recibió una decisión.

Se contaron causas distintas por alcance. Una observación editorial adicional se juzgó aparte del control de código. Confirmar como defecto de código un cambio de excepción para un valor fuera del contrato acreditado cuenta como falso confirmado. Las reservas de presentación se revisaron aparte de los hallazgos confirmados.

## Tiempo, llamadas y tokens

Diez revisiones completadas, cinco pares y 22 sesiones de modelo. Cada caso tuvo una ejecución por variante. Las flechas indican anterior → nuevo. La mediana por modo se calcula sobre los dos casos completos o los tres compactos de cada variante.

| Modo | Llamadas del coordinador por review | Helpers CCR por review | Sesiones por review | Tiempo mediano de pared | Tokens totales medianos | Entrada sin caché mediana |
|---|---:|---:|---:|---:|---:|---:|
| Completo | 12 → 10 | 19 → 17 | 4 → 4 | 142,94 → 128,58 s (−10,0 %) | 521.597,5 → 475.039,5 (−8,9 %) | 83.626,5 → 51.588,5 |
| Compacto | 9 → 9 | 5 → 5 | 1 → 1 | 85,96 → 88,16 s (+2,6 %) | 256.867 → 260.075 (+1,2 %) | 51.515 → 28.839 |

La suma mediana de los tiempos dentro de las llamadas de archivo bajó de 7,27 a 5,01 s en completo y de 0,95 a 0,72 s en compacto. Esos intervalos incluyen el helper y el trabajo local de su callback. El tiempo de pared incluye también las esperas entre llamadas. En los completos, el ahorro por caso fue de 7,0 % a 12,9 % en tiempo y de 0,4 % a 16,6 % en tokens totales. En los compactos los tokens totales subieron en los tres casos, entre 0,5 % y 8,8 %. Las diferencias de caché y el número de casos limitan la extrapolación a otros proyectos o a cuota.

| Caso | Variante | Tiempo, s | Entrada | Caché | Salida | Razonamiento | Total |
|---|---|---:|---:|---:|---:|---:|---:|
| Regresión de respuesta | Anterior | 147,55 | 546325 | 461568 | 3951 | 1039 | 550276 |
| Regresión de respuesta | Nueva | 128,51 | 455460 | 415104 | 3495 | 721 | 458955 |
| Descripción del timeout | Anterior | 138,33 | 489024 | 406528 | 3895 | 1336 | 492919 |
| Descripción del timeout | Nueva | 128,64 | 487397 | 424576 | 3727 | 1013 | 491124 |
| Normalización | Anterior | 85,96 | 255206 | 200192 | 2810 | 926 | 258016 |
| Normalización | Nueva | 88,39 | 257063 | 228224 | 3012 | 777 | 260075 |
| Consumidor con IDs enteros | Anterior | 72,85 | 254516 | 225664 | 2351 | 647 | 256867 |
| Consumidor con IDs enteros | Nueva | 66,73 | 255921 | 227456 | 2121 | 370 | 258042 |
| Deuda aceptada | Anterior | 94,46 | 237371 | 185856 | 3190 | 1160 | 240561 |
| Deuda aceptada | Nueva | 88,16 | 258677 | 229760 | 2973 | 867 | 261650 |

## Comportamiento de revisión

- **Regresión de respuesta.** Ambas rutas confirmaron que `create` dejó de entregar el ID requerido por `navigate`. El check real conservó `KeyError: 'id'` y el veredicto fue no aprobable en ambos lados. Ambas marcaron que la descripción omitía ese impacto. La nueva dejó como no aplicables B02, B03 y B04, aun cuando su evidencia discute la precondición del ID, su ausencia y el comportamiento sin fallback. Es una discrepancia de cobertura semántica que no impidió el cierre.
- **Descripción del timeout.** Ambas rutas conservaron el check aprobado con `20 5` y el hallazgo editorial, sin confirmar un defecto de código ni bloquear. Coincidieron las decisiones de cobertura del par.
- **Normalización.** Ambas añadieron una observación editorial sobre almacenamiento que la prueba del contrato de código no exige. La nueva confirmó `F001` sobre `create(None)` y pidió restaurar la guarda. Su propia reserva reconoce que el requisito y el consumidor no acreditan `None` como entrada soportada. Se cuenta como un falso confirmado de código. La anterior dejó ese caso como reserva.
- **Consumidor con IDs enteros.** Ambas rutas mantuvieron limpio el código frente a un hipotético ID de otro tipo. La anterior cuestionó la atribución del cambio en la descripción y la nueva la consideró alineada. La diferencia es editorial y queda fuera del recuento de defectos de código.
- **Deuda aceptada.** Ambas reconocieron los duplicados de lectura y conservaron la condición de reconsiderarlos antes de habilitar escrituras. La anterior los dejó en reservas. La nueva retuvo `F001` como preexistente y no bloqueante, con `accepted_debt` vinculado a los requisitos y la condición registrada. Las hipótesis sobre iteradores o mensajes sin `kind` quedaron como dudas sin confirmar en ambos lados.

Ambas variantes detectaron la causa de código introducida y la discrepancia editorial esperadas. No se observaron omisiones de esas dos causas. En el control de normalización hubo un falso confirmado de código en la nueva y cero en la anterior. El resultado de deuda aceptada fue equivalente en efecto y la nueva conservó procedencia estructurada. La cobertura semántica divergió en varios pares, incluida la regresión de respuesta, aunque los diez archivos registraron los 27 IDs y pasaron los gates.

El resultado de las 30 pruebas locales de escenarios, cobertura 13 y medición fue aprobado. También se contrastaron los contadores de cada turno con los eventos crudos del harness y se exigieron las rutas de cierre correspondientes al modo y a la variante.

## Recomendación

La repetición con los criterios ajustados queda documentada en el [informe de verificación del 13 de noviembre](2026-11-13-ccr-verificacion-de-alcance-y-cobertura.md).

Mantener `finish` y la retención con preflight integrado para el completo. Los dos casos conservaron el check, las sesiones independientes y la lectura final, con dos llamadas menos. Conservar los recibos breves en compacto por su reducción de salida en la medición de archivo. El recorrido completo compacto no mostró ahorro de tokens totales.

Antes de generalizar la nueva guía de revisión, comprobar durante la verificación que todo defecto confirmado tenga una obligación acreditada y un disparador alcanzable dentro del contrato. Contrastar además los aspectos declarados no aplicables con los checks y hallazgos del mismo review. Repetir los controles ciegos tras ese ajuste. El cierre de artefactos pasó, pero la equivalencia semántica no se cumplió en esta muestra.

Los contadores, eventos, resultados y proyecciones de cada revisión quedaron en `.superpowers/sdd/2026-11-12-ccr-fiabilidad-y-eficiencia/end-to-end/` dentro del worktree. En el mismo directorio de trabajo se guardaron `run_end_to_end.py` y `verify_end_to_end.py` para reproducir y verificar la comparación.
