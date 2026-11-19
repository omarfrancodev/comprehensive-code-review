# Duración de la verificación independiente de CCR

En la repetición con un bloque de uso por turno de V1, el brief breve consumió 83 tokens totales menos en cuatro pares (−0,08 %). Ahorró tokens en dos casos y consumió más en los otros dos. La serie anterior de navegación y timeout había registrado reducciones en sus seis pares.

En la comparación anterior, el turno independiente V1 pasó de 19,02 a 40,57 s en la regresión de navegación y de 24,93 a 39,85 s en la descripción del timeout. Desde el inicio del turno hasta el primer fragmento de texto transcurrieron entre 1,79 y 2,75 s en las cuatro sesiones. La diferencia se concentró después de ese primer fragmento. En navegación, el texto final pasó de 981 a 3025 caracteres y la salida medida pasó de 481 a 1259 tokens. En timeout, pasó de 1032 a 2300 caracteres y de 788 a 1359 tokens de salida. Las respuestas más largas repetían el análisis en la síntesis, los hallazgos y la cobertura. Los eventos acreditan más tiempo en esa parte del turno y más salida. El tiempo atribuible a la infraestructura del proveedor queda sin aislar. [Comparación anterior](2026-11-13-ccr-comparacion-controlada-de-guias.md)

El brief de V1 pide una decisión por candidato, evidencia decisiva por causa y resultados de los invariantes y dimensiones afectados. Mantiene la comprobación de obligación, disparador dentro del contrato, consecuencia, preguntas materiales y disposiciones aceptadas. El coordinador conserva la conciliación de las 27 dimensiones con los hallazgos y checks antes de retener. [Brief de verificación independiente](../../references/execution/worker-packets.md#independent-verification-brief)

La repetición compara el brief anterior de V1 con el breve. Conserva las instrucciones del coordinador, los insumos, perfiles, esquema, plazos y helpers. Los dos completos alternan el orden de las variantes. Los compactos sirven de control porque su verificación ocurre dentro de la sesión del coordinador, con las mismas instrucciones en ambos lados. Se usó el mismo modelo y esfuerzo de la comparación anterior y se cotejaron los tokens con los eventos del harness. Cada par usa hilos nuevos. La caché funciona normalmente.

| Caso completo | V1 activo, s | Arranque de V1, s | Tokens de salida de V1 | Tokens totales de V1 | Tiempo de la revisión, s |
|---|---:|---:|---:|---:|---:|
| Navegación | 33,96 → 26,21 | 1,39 → 4,22 | 1240 → 891 | 50.153 → 49.297 | 162,53 → 173,79 |
| Descripción del timeout | 23,86 → 22,39 | 32,29 → 1,54 | 801 → 763 | 74.091 → 49.307 | 177,48 → 136,69 |

El tiempo activo de V1 bajó 22,8 % en navegación y 6,2 % en timeout. La salida bajó 28,1 % y 4,7 %, respectivamente. En timeout, la diferencia de arranque domina el ahorro observado de principio a fin. El harness registró tres bloques de uso en V1 con el brief anterior y dos con el breve. El bloque adicional contabilizó aproximadamente 24.500 tokens, principalmente de entrada, y representa casi toda la diferencia de tokens totales de V1 en ese caso. Los tiempos de revisión completa variaron en ambos sentidos.

Los completos pasaron de 170,00 a 155,24 s de mediana de pared y de 558.374,5 a 480.863,5 tokens totales. Su entrada sin caché subió de 38.103 a 48.101,5 tokens. En los tres pares compactos con prompts idénticos, la mediana de tiempo fue 110,03 → 99,09 s y la de tokens totales 264.109 → 262.789. En ese control, las diferencias por par de tiempo variaron entre −15,80 y +24,27 s. El tamaño de la muestra y esa variación limitan lo que se puede atribuir al brief. La reducción más directa observada fue la de salida y tiempo activo de V1.

Las diez revisiones conservaron el perfil, el orden de validaciones y la lectura final. Los completos mantuvieron 10 llamadas de coordinación, 17 helpers y cuatro sesiones, con dos descubrimientos y V1 independientes. Los compactos mantuvieron nueve llamadas, cinco helpers y una sesión. El cotejo comprobó los 27 IDs de cobertura, el propósito y resultado de cada check y la identidad de insumos.

- Navegación mantuvo el fallo bloqueante, `C001` fallido y B02–B04 cubiertas en ambos lados.
- Timeout mantuvo `C001` aprobado y el hallazgo editorial sin bloqueo. Los dos controles compactos de normalización e IDs enteros quedaron sin defectos de código confirmados. Sus decisiones editoriales variaron entre sesiones.
- Deuda aceptada conservó F001 como preexistente y no bloqueante, la fuente de requisitos y la condición de reconsiderar antes de habilitar escrituras.

Pasaron 44 pruebas focalizadas de referencias, evaluación, escenarios, cobertura y medición. Los resultados y eventos de las 22 sesiones están en `.superpowers/sdd/2026-11-12-ccr-fiabilidad-y-eficiencia/verification-paired/`. El resumen `verification-paired-comparison.json` conserva los tiempos y contadores por sesión. El cotejo comprueba que la diferencia de instrucciones está en V1 y que los resultados observados de descubrimiento pueden variar.

## Ampliación de la muestra completa

Se completaron dos series adicionales con los mismos casos completos, navegación y descripción del timeout. Cada serie usó los mismos helpers de CCR, perfil `deep`, modelo `gpt-6.1-sol`, esfuerzo `high` y plazos en ambos lados. En la primera serie se invirtió el orden de los briefs de la comparación inicial y en la segunda se recuperó ese orden. Las revisiones se ejecutaron en secuencia, con hilos nuevos. Se añadieron cuatro pares y 32 sesiones. El conjunto reúne seis pares completos, 12 revisiones y 48 sesiones, con tres pares por caso y tres pares en cada orden. Las repeticiones amplían la muestra de ejecuciones sobre dos casos conocidos.

El arranque de V1 abarca desde el lanzamiento de app-server hasta `turn/started`. El tiempo activo abarca desde `turn/started` hasta `turn/completed`. Los totales y sus componentes proceden de la última notificación de uso del turno, con caché incluida en la entrada y razonamiento en la salida. Se cotejaron los tiempos y contadores con los eventos originales.

| Serie y caso | Arranque de V1, s | Tiempo activo de V1, s | Tokens de salida | Tokens totales |
|---|---:|---:|---:|---:|
| Inicial, navegación | 1,39 → 4,22 | 33,96 → 26,21 | 1240 → 891 | 50.153 → 49.297 |
| Inicial, timeout | 32,29 → 1,54 | 23,86 → 22,39 | 801 → 763 | 74.091 → 49.307 |
| Ampliación 1, navegación | 1,42 → 1,33 | 27,38 → 27,54 | 924 → 899 | 81.312 → 49.515 |
| Ampliación 1, timeout | 1,37 → 1,42 | 26,27 → 22,40 | 866 → 748 | 78.026 → 73.622 |
| Ampliación 2, navegación | 0,99 → 0,98 | 30,15 → 33,86 | 1074 → 1227 | 74.779 → 49.811 |
| Ampliación 2, timeout | 1,05 → 1,26 | 28,28 → 35,06 | 948 → 1245 | 78.025 → 73.598 |

Las flechas comparan el brief anterior con el breve. La columna de cambio toma la mediana de los porcentajes calculados dentro de cada par, por lo que puede diferir del porcentaje calculado a partir de las medianas de cada variante.

| Métrica de V1 | Medianas, cuatro pares nuevos | Medianas, seis pares | Cambio mediano por par, seis pares | Pares con reducción |
|---|---:|---:|---:|---:|
| Arranque, s | 1,21 → 1,29 | 1,38 → 1,38 | +1,6 % | 3/6 |
| Tiempo activo, s | 27,83 → 30,70 | 27,83 → 26,88 | −2,8 % | 3/6 |
| Tokens de entrada | 77.118,5 → 60.484,5 | 75.391 → 48.600 | −19,9 % | 6/6 |
| Tokens de entrada en caché | 48.640 → 43.264 | 48.640 → 42.624 | −23,4 % | 4/6 |
| Tokens de entrada sin caché | 26.792,5 → 17.204,5 | 24.893 → 9.755,5 | −12,2 % | 5/6 |
| Tokens de salida | 936 → 1063 | 936 → 895 | −3,7 % | 4/6 |
| Tokens de razonamiento | 215,5 → 469 | 280,5 → 332,5 | +87,3 % | 2/6 |
| Tokens totales | 78.025,5 → 61.704,5 | 76.402 → 49.663 | −19,5 % | 6/6 |

En los cuatro pares nuevos, el tiempo activo solo bajó en uno. En los seis acumulados, la diferencia por par fue de −7,75 a +6,78 s. El tiempo de pared de la revisión completa bajó en tres y subió en tres. Los arranques de la ampliación variaron entre 0,98 y 1,42 s, frente al arranque de 32,29 s del caso inicial de timeout.

El texto final de V1 fue más corto en los seis pares, con una reducción mediana por par de 25,5 % en caracteres. Los contadores de salida incluyen razonamiento, que subió en los cuatro pares nuevos. En tres pares el harness contabilizó un bloque de uso menos con el brief breve. Al limitar el análisis a los tres pares con el mismo número de bloques, los tokens totales también bajaron en los tres, con una reducción mediana por par de 5,6 %. La reducción observada de tokens totales se mantuvo en esta muestra y su magnitud varió con los bloques y la caché. El ahorro de tiempo activo sigue sin confirmarse.

Las doce revisiones completas mantuvieron la secuencia de 10 llamadas de coordinación, 17 helpers y cuatro sesiones, con D1, D2 y V1 independientes. Conservaron la lectura retenida, la limpieza y la lectura final. En navegación, todos los resultados conservaron `C001` fallido con `KeyError`, un único hallazgo de código bloqueante y B02–B04 cubiertas. En timeout, todos conservaron `C001` aprobado con salida `20 5` y el hallazgo editorial sin bloqueo. Se verificaron los 27 IDs de cobertura, el propósito de los checks y la identidad de los insumos en cada par. Las ocho revisiones nuevas terminaron sin reintentos. Pasaron las 44 pruebas focalizadas.

Los eventos y resultados de la ampliación están en `.superpowers/sdd/2026-11-12-ccr-fiabilidad-y-eficiencia/verification-expansion-1/` y `.superpowers/sdd/2026-11-12-ccr-fiabilidad-y-eficiencia/verification-expansion-2/`. El resumen consolidado `verification-expansion-comparison.json` incluye los contadores reales por par. Se puede regenerar con `summarize_verification_expansion.py` sobre esas dos carpetas y `verification-paired/`.

## Casos completos distintos a navegación y timeout

Se añadieron cuatro PR sintéticos con un par por caso. Las pruebas de referencia se ejecutaron sobre base y head antes de la medición. Los casos cubren una regresión de atomicidad al rechazar un lote, un cambio compatible en la prioridad de trabajos, una regresión en el umbral exacto de una categoría y un cambio compatible que preserva los espacios aceptados en una exportación. En ambos lados se mantuvieron el perfil `deep`, dos descubrimientos independientes, V1, la prueba `C001` en el worktree propio y el cierre completo. El modelo recibió el diff, el consumidor, los requisitos y la descripción. V1 recibió además los resultados observados de descubrimiento y del check.

Se alternó qué brief se ejecutaba primero y se conservaron los tiempos de arranque y de turno activo por separado. La comparación mide la misma modificación de instrucciones de V1 que la serie anterior. Las sesiones de descubrimiento y coordinación mantuvieron sus prompts. Las métricas de V1 provienen de los eventos de cada sesión y conservan el desglose de entrada, caché, salida y razonamiento.

| Caso | Arranque de V1, s | Tiempo activo de V1, s | Tokens de salida | Tokens totales de V1 | Bloques de uso |
|---|---:|---:|---:|---:|---:|
| Atomicidad del lote | 0,91 → 1,04 | 32,69 → 36,15 | 1154 → 1305 | 79.143 → 50.482 | 3 → 2 |
| Empates de prioridad | 1,25 → 0,96 | 31,20 → 25,87 | 1113 → 850 | 49.893 → 74.028 | 2 → 3 |
| Umbral exacto | 1,19 → 1,05 | 38,56 → 46,25 | 1406 → 1704 | 50.507 → 50.626 | 2 → 2 |
| Espacios del exportador | 1,36 → 1,28 | 41,22 → 21,43 | 1427 → 725 | 75.378 → 49.412 | 3 → 2 |

Las flechas comparan brief anterior → breve. En los cuatro pares nuevos, la mediana de arranque pasó de 1,22 a 1,05 s, la de tiempo activo de 35,63 a 31,01 s y la de tokens totales de 62.942,5 a 50.554. El cambio mediano por par fue −3,2 % para tiempo activo y −17,1 % para tokens totales. Ambas métricas bajaron en dos pares y subieron en dos. El texto final fue más corto en los cuatro casos, con una reducción mediana por par de 38,8 % en caracteres.

En los tres pares con distinto número de bloques, la variante con menos bloques usó menos tokens totales. En el único par con dos bloques por lado, el brief breve usó 119 tokens más (+0,24 %). Los nuevos casos muestran que el ahorro observado en navegación y timeout no se repite de forma uniforme. La muestra conserva las diferencias de caché y de bloques que se observaron en el harness.

Las ocho revisiones comparadas pasaron la lectura final y conservaron 10 llamadas de coordinación, 17 helpers, cuatro sesiones y el check `C001`. Las dos regresiones mantuvieron su check fallido y un único hallazgo de código bloqueante. El control de empates mantuvo el check aprobado sin defectos de código. El exportador mantuvo el check aprobado y la aceptación de los espacios con su condición de reconsideración antes de usar las etiquetas como claves. Ambos informes del exportador documentaron la decisión como reserva. Se conservaron las 27 decisiones de cobertura, con variación de aplicabilidad en dimensiones secundarias. En particular, el brief breve marcó E04 como no aplicable en atomicidad, mientras el anterior la marcó cubierta. Ambas variantes cubrieron D03 y B01–B05 en ese caso.

El primer intento del umbral con el brief anterior encontró la regresión, pero el banco rechazó etiquetas libres en los grupos de cobertura. Su par breve sí cerró. Se conservaron ambos intentos y se repitió el par con la misma aclaración sobre IDs canónicos para ambas variantes. Solo el par repetido entra en la tabla. Pasaron las 44 pruebas focalizadas.

Los eventos y resultados están en `.superpowers/sdd/2026-11-12-ccr-fiabilidad-y-eficiencia/verification-new-cases/` y `.superpowers/sdd/2026-11-12-ccr-fiabilidad-y-eficiencia/verification-new-cases-retry/`. El resumen `verification-new-cases-comparison.json` contiene los contadores reales de las 32 sesiones comparadas. El archivo `verification-new-cases.json` contiene los cuatro insumos sintéticos y `summarize_verification_new_cases.py` regenera el cotejo.

## Repetición con bloques de uso controlados

Se repitieron los cuatro casos con un esquema común de JSON final para V1 y una instrucción de emitir una sola respuesta. Se desactivó la herramienta dinámica en V1. El coordinador mantuvo su herramienta y siguió los pasos de la revisión completa. Los dos briefs recibieron la misma configuración de respuesta y el mismo perfil, modelo, esfuerzo, insumos, plazo y criterio de IDs de cobertura. El orden se invirtió respecto a la serie anterior.

El esquema común conserva una decisión por candidato, evidencia, obligación, disparador, consecuencia, descripción y limitaciones. La instrucción común pide citar el check o ubicación y registrar condiciones de disposiciones aplicables, invariantes y dimensiones. Cada variante conserva su instrucción de V1. Este ensayo mide el efecto de la longitud y contenido del brief dentro del formato común de una sola respuesta. Se cotejaron las instrucciones y los insumos fijados dentro de cada par. D1 y D2 volvieron a ejecutarse en cada revisión, por lo que sus textos llegaron a V1 con variación. La caché del harness siguió activa. El control iguala bloques, mensajes y herramientas de V1. La muestra conserva esas fuentes de variación.

El cotejo cuenta las notificaciones `thread/tokenUsage/updated` observadas en V1 y contrasta la suma de los componentes de cada bloque con el total final. También cuenta los mensajes del verificador y las llamadas a herramientas. El total de V1 suma entrada y salida. La entrada incluye tokens en caché y la salida incluye tokens de razonamiento.

El arranque se mide desde la entrada al cliente hasta el evento `turn/started` del turno correspondiente. El tiempo activo se mide desde ese evento hasta `turn/completed`. En una sesión, el inicio llegó antes que la respuesta a la llamada RPC. Se recuperó su marca de tiempo del evento original asociado al mismo turno.

| Caso | Bloques de V1 | Arranque de V1, s | Tiempo activo de V1, s | Tokens de entrada | Tokens de salida | Tokens totales de V1 | Diferencia |
|---|---:|---:|---:|---:|---:|---:|---:|
| Atomicidad del lote | 1 → 1 | 2,11 → 3,01 | 28,03 → 35,89 | 24.800 → 24.476 | 1.037 → 1.215 | 25.837 → 25.691 | −146 |
| Empates de prioridad | 1 → 1 | 4,82 → 2,62 | 13,08 → 20,03 | 24.459 → 24.324 | 447 → 618 | 24.906 → 24.942 | +36 |
| Umbral exacto | 1 → 1 | 3,75 → 1,17 | 23,49 → 32,65 | 24.613 → 24.455 | 868 → 1.232 | 25.481 → 25.687 | +206 |
| Espacios del exportador | 1 → 1 | 1,49 → 1,40 | 26,95 → 25,82 | 24.507 → 24.374 | 992 → 946 | 25.499 → 25.320 | −179 |
| **Total de tokens** | **4 → 4** | | | **98.379 → 97.629** | **3.344 → 4.011** | **101.723 → 101.640** | **−83 (−0,08 %)** |

Cada turno registró un mensaje de respuesta, un bloque de uso y cero herramientas en V1. En los cuatro casos bajó la entrada, que en conjunto se redujo en 750 tokens. La salida subió 667 e incluyó 1.004 tokens adicionales de razonamiento. En empates y en el exportador, el brief anterior reutilizó 22.656 tokens de entrada en cada caso. Los otros seis turnos registraron cero tokens en caché. La entrada sin caché pasó de 53.067 a 97.629 tokens. En los dos pares con cero caché a ambos lados, los tokens totales pasaron de 51.318 a 51.378 (+60). Los contadores son del harness y no equivalen a consumo de cuota.

La mediana de arranque de V1 bajó de 2,93 a 2,01 s. La mediana de tiempo activo subió de 25,22 a 29,24 s y el tiempo activo subió en tres de los cuatro casos. El formato breve volvió a reducir la entrada. Con los bloques igualados, la muestra no confirma un ahorro estable de tokens totales ni de tiempo activo. En la serie anterior, la variación de bloques podía mover el total por decenas de miles de tokens. Aquí, cada diferencia quedó entre −179 y +206.

En la revisión de principio a fin, la mediana de tiempo de pared fue 159,60 → 197,37 s y la suma de tokens de las cuatro sesiones por revisión fue 2.035.214 → 2.207.329 (+8,46 % en los cuatro casos combinados). Esos totales incluyen D1, D2 y el coordinador, cuyos bloques de uso no se igualaron en este ensayo.

### Validaciones y diferencias de cobertura

Las ocho revisiones completaron 10 llamadas de coordinación y 17 ejecuciones de helpers, sin reintentos ni fallbacks. Cada revisión produjo tres resultados independientes (D1, D2 y V1) más el del coordinador, registró el check `C001` en su worktree y completó la lectura retenida, la limpieza y la verificación final. Los dos fallos de producto conservaron un único hallazgo de código bloqueante cada uno y el mismo resultado de la prueba. Los dos controles pasaron `C001` sin defectos de código confirmados. Ambos informes del exportador mantuvieron la aceptación de los espacios para la exportación de solo lectura y la condición de reconsiderarla antes de usar las etiquetas como claves.

Cada resultado registró los 27 IDs de cobertura. En empates, ambos V1 verificaron la entrada vacía y `C001` informó el resultado. El coordinador con el brief breve marcó B02 como no aplicable al dar por hecho que solo se refería a ramas explícitas de validación. La definición de B02 incluye entradas vacías alcanzables. El informe perdió la asociación de esa evidencia con B02 aunque la validación se ejecutó. En el exportador, E04 también pasó de cubierta a no aplicable, pese a que ambos V1 trazaron la propagación de `ValueError` y delimitaron lo que se conoce más allá de `export`. El detalle por dimensión registra además las diferencias en D01 y E07 en empates, D05 en umbral y E06 en atomicidad. La evaluación editorial de atomicidad pasó de descripción alineada a necesita actualización porque la variante breve señaló el efecto omitido de modificar el inventario antes de validar el lote completo. El hallazgo de código y su carácter bloqueante se conservaron.

Pasaron las 44 pruebas focalizadas de estructura, evaluación, escenarios, cobertura y métricas. El ensayo usó el mismo esquema de respuesta acotada para ambos briefs. Las cifras corresponden a ese formato y a los cuatro casos de la muestra.

Los eventos y resultados están en `.superpowers/sdd/2026-11-12-ccr-fiabilidad-y-eficiencia/verification-new-cases-matched/`. El archivo `verification-new-cases-matched-comparison.json` conserva el desglose de bloques, tiempos, tokens, checks y diferencias de cobertura. El banco `run_end_to_end.py` reproduce la serie con `--compare-verification --single-response-v1 --canonical-coverage-hint --reverse-order` sobre `verification-new-cases.json`. El script `summarize_verification_new_cases.py` regenera el cotejo a partir de los eventos guardados.

## Cierre de las discrepancias de cobertura para 3.8.0

El 14 de noviembre se repitieron empates de prioridad y espacios del exportador con los mismos insumos fijados, perfil `deep`, dos descubrimientos independientes y salida de V1 en un bloque de uso por turno. El coordinador recibió las reglas que concilian los invariantes de V1 con los checks y las exclusiones propuestas. Se ensayó la guía detallada que selecciona la skill y la instrucción abreviada con los ejemplos de B02 y E04.

| Caso | Guía detallada de 3.8.0 | Variante abreviada | C001 |
|---|---|---|---|
| Empates | B02 cubierta con evidencia de cola vacía | B02 cubierta con la misma clase de evidencia. Marcó también E04 como cubierta sin cambio de excepción para entradas soportadas. | Aprobado |
| Exportador | E04 cubierta con la traza de `ValueError` hasta el llamador inspeccionado | E04 cubierta con la misma traza y límite de evidencia | Aprobado |

Las cuatro revisiones conservaron los 27 IDs de dimensión, el perfil, las cuatro sesiones, 10 llamadas de coordinación, 17 ejecuciones de helpers, la lectura del retenido, la limpieza y la lectura final. Ninguna confirmó defectos de código. Los dos informes del exportador conservaron la aceptación para la exportación de solo lectura y la condición de reevaluar la decisión antes de usar etiquetas como claves. El cotejo automático de esa condición admitió las formulaciones «reconsiderar» y «reevaluar», corroboradas en los informes.

La skill conserva las instrucciones detalladas de confirmación y cobertura en el encargo de V1 y la reconciliación de las 27 dimensiones antes de retener. Los cuatro turnos registraron un bloque por variante. La abreviada pasó de 25.594 a 25.360 tokens en empates y de 25.848 a 26.091 en el exportador. Esta repetición valida la corrección de cobertura para la guía detallada y mantiene abierta la cuestión del ahorro general.

Los eventos sintéticos y el resumen `stable-coverage-comparison.json` quedan en el área local de validación del worktree.
