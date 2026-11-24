# Comparación controlada de la guía de CCR

El seguimiento sobre el tiempo adicional de V1 está en la [comparación de verificación independiente](2026-11-13-ccr-verificacion-independiente.md).

Se compararon la guía anterior al ajuste de verificación y la guía ajustada en el mismo worktree. Las dos usaron la versión actual de los helpers y del flujo de archivo. La variante ajustada añadió al coordinador y a V1 independiente los criterios sobre disparadores acreditados y aplicabilidad de cobertura. Los revisores recibieron los insumos del caso sin la respuesta esperada. [Ajuste de la guía](2026-11-13-ccr-verificacion-de-alcance-y-cobertura.md)

Se usaron los mismos cinco escenarios, perfiles, Git base y HEAD, requisitos, descripciones, herramientas, formato de salida y plazos. Los dos completos usaron perfil `deep` y los tres compactos usaron `focused`. La serie utilizó Codex app-server con `gpt-6.1-sol` y esfuerzo `high`. Los casos se ejecutaron en serie dentro de la misma corrida, en hilos efímeros, con los dos lados de cada par consecutivos y la guía que comenzó alternada por caso. La caché del proveedor operó durante la serie.

El tiempo de pared va desde el arranque del coordinador hasta el fin del turno. Incluye la preparación de CCR, las sesiones asignadas, los helpers y la espera del modelo. El tiempo acumulado de helpers también se registró. Los tokens se tomaron de los eventos de uso del harness por sesión. La entrada incluye la caché y la salida incluye el razonamiento. Se cotejaron los totales contra los eventos originales.

La muestra estima el efecto observado con un par por caso. La variación del modelo y la caché permanecen en la medición. La cuota de cinco horas y los cargos por revisión quedan fuera de estos datos.

## Tiempo y tokens

Completaron las diez revisiones, con 22 sesiones medidas y ningún reintento en esta serie. Las cifras comparan guía anterior → ajustada.

| Modo | Pares | Tiempo mediano | Tokens totales medianos | Entrada sin caché mediana | Tiempo mediano acumulado de helpers |
|---|---:|---:|---:|---:|---:|
| Completo | 2 | 148,64 → 173,80 s (+16,9 %) | 537.704,5 → 537.912 (+0,04 %) | 86.921,5 → 67.605 (−22,2 %) | 17,47 → 13,86 s |
| Compacto | 3 | 118,25 → 104,49 s (−11,6 %) | 244.638 → 246.854 (+0,9 %) | 12.748 → 13.051 (+2,4 %) | 1,50 → 1,49 s |

| Caso | Tiempo de pared, s | Tokens totales | Entrada sin caché |
|---|---:|---:|---:|
| Regresión de navegación | 157,63 → 192,56 | 489.589 → 500.300 | 66.774 → 42.721 |
| Normalización | 123,40 → 107,74 | 244.638 → 263.267 | 12.748 → 34.352 |
| Descripción del timeout | 139,66 → 155,05 | 585.820 → 575.524 | 107.069 → 92.489 |
| Consumidor con IDs enteros | 81,86 → 102,26 | 239.136 → 246.854 | 12.011 → 7.257 |
| Deuda aceptada | 118,25 → 104,49 | 263.087 → 246.063 | 28.874 → 13.051 |

El aumento de tiempo en los completos coincidió con sesiones V1 más largas. La regresión de navegación pasó de 19,02 a 40,57 s en V1 y el timeout pasó de 24,93 a 39,85 s. Los helpers tardaron menos en ambos casos. Los tokens totales subieron en un completo y bajaron en el otro. Los compactos muestran variación en ambos sentidos para tiempo y tokens. El aumento simultáneo de las dos métricas observado en la repetición anterior solo se reprodujo en dos de los cinco pares. Las medianas de tokens quedaron a menos de 1 % de diferencia en ambos modos.

## Correcciones y validaciones

- **Regresión de navegación.** Las dos guías confirmaron el fallo del consumidor y conservaron `C001` fallido. En esta comparación, B03 y B04 ya estaban cubiertas con la guía anterior. B02 pasó de no aplicable a cubierta con la ajustada. Las tres quedaron cubiertas con la evidencia del check y del hallazgo bloqueante.
- **Normalización.** La guía anterior confirmó el defecto sobre `create(None)`. La ajustada descartó el defecto de código porque el requisito y el consumidor acreditan entradas textuales. Ambas señalaron la descripción sobre almacenamiento.
- **Descripción del timeout.** Las dos guías conservaron `C001` aprobado, la discrepancia editorial y la ausencia de un defecto de código.
- **Consumidor con IDs enteros.** Ninguna guía confirmó un defecto de código. La anterior marcó la descripción para corregir y la ajustada la consideró alineada.
- **Deuda aceptada.** Ambas conservaron los duplicados de lectura como preexistentes y no bloqueantes, con la condición de reconsiderar la aceptación antes de habilitar escrituras. La guía anterior también confirmó un defecto para iteradores de un solo uso sin acreditar ese tipo de entrada en el contrato. La ajustada conservó la deuda como su único hallazgo de código.

Los cinco pares conservaron los insumos, la secuencia de validaciones, los resultados de los checks y la lectura final. Cada completo usó 10 llamadas del coordinador, 17 ejecuciones de helpers y cuatro sesiones. Cada compacto usó nueve llamadas, cinco ejecuciones de helpers y una sesión. Los resultados conservaron las 27 decisiones de cobertura. En estos controles, la guía ajustada eliminó los dos falsos confirmados de código de la guía anterior y mantuvo el hallazgo de navegación, el hallazgo editorial esperado y la deuda aceptada.

Las 31 pruebas focalizadas de referencias, escenarios, cobertura y medición pasaron con el directorio temporal de fixtures del worktree. La primera ejecución local de pruebas usó la ruta temporal predeterminada del sandbox y cinco casos del runner fallaron al interpretar esa ruta. Los 31 pasaron al fijar el directorio temporal usado en las evaluaciones previas.

La verificación de los eventos compara los prompts de descubrimiento de forma íntegra. En V1, compara instrucciones, insumos y check, y permite que cambien los resultados observados del descubrimiento. En el coordinador y V1, comprueba que las dos secciones de guía son la diferencia en las instrucciones. Los eventos y resultados por caso quedan en `.superpowers/sdd/2026-11-12-ccr-fiabilidad-y-eficiencia/guidance-paired/`.

El resumen `guidance-paired-comparison.json` conserva los contadores de entrada, caché, salida y razonamiento por revisión, junto con el tiempo y los tokens por sesión. El banco se ejecutó con `run_end_to_end.py --compare-guidance` y los pares se cotejaron con `summarize_guidance_pairs.py` en el mismo directorio de trabajo.
