# Validación del décimo CCR del PR 19 — 2026-10-16

Fuente: [CR-139ef46a80564e4a883c](https://github.com/omarfrancodev/comprehensive-code-review/pull/19#issuecomment-6229938583), HEAD revisado 713e507.

## Correcciones

| ID | Resultado | Evidencia |
|---|---|---|
| F065 | Conflictos de lock tipados; otros fallos conservan su causa sin recibir instrucciones de contención | Errores de Git por API y CLI, permisos de apertura, hardlink final inseguro, JSON/Unicode/E/S del cuerpo y fallo E/S del bloqueo |
| F066 | Prueba sensible a la relectura interna ya existente | Otro registro compromete su entrada entre el snapshot externo y la adquisición del lock; se conservan dos entradas |
| F067 | Descripción del PR consistente con la exclusión de F050/F052 | Sección Fuera de alcance con #20/#21, comentario del mantenedor y compatibilidad/referencias actualizadas |

La exclusión procede de [la decisión del mantenedor](https://github.com/omarfrancodev/comprehensive-code-review/pull/19#issuecomment-6228895961). No se reevalúan esos dos hallazgos ni se presentan como reservas o condiciones pendientes de este PR. Sus issues conservan el seguimiento independiente.

## RED/GREEN

La primera tanda de seis pruebas reprodujo diez fallos de aserción, contando subcasos: clasificación incorrecta de Git, causa de apertura perdida, reclasificación de errores JSON/Unicode y consejo de contención ante un hardlink inseguro. El caso CLI reprodujo un traceback porque el ReviewError del módulo importado no coincidía con el del script ejecutado como __main__. Los OSError del cuerpo ya se propagaban sin conversión y el caso de relectura ya pasaba; no se afirma una regresión de datos en F066.

Tras la corrección, 26 pruebas focales pasaron en 114.501 s, y el caso adicional de bloqueo con EIO pasó en 0.669 s. Son **27 IDs distintos aprobados, sin omisiones**; no se suman otra vez a la suite completa.

La prueba de F066 registra ambos archivos con operaciones reales del helper. Solo se intercala el segundo escritor después de la primera lectura externa. Un mutante compilado en memoria toma ese snapshot inicial y lo pasa al cuerpo sin releer: pierde la entrada del otro escritor y la aserción falla. El mutante no modifica archivos productivos y no presenta un fallo de fixture como detección.

## Suite completa

La suite descubierta contiene **563 IDs únicos: 560 aprobados, cero fallos/errores y tres omitidos por privilegios de symlink**. Cuatro procesos ejecutaron grupos disjuntos: dos para los casos generales y uno para cada matriz extensa. Se comprobaron los inventarios de selección y los IDs con resultado observado de cada log: su unión coincide exactamente con los 563 IDs descubiertos, sin duplicados ni pendientes. Todos terminaron con exit 0; no se modificaron fuentes Python después de iniciarlos.

| Grupo | Casos | Omitidos | Duración del proceso | Resultado |
|---|---:|---:|---:|---|
| General 0 | 281 | 0 | 662.480 s | OK |
| General 1 | 280 | 3 | 835.975 s | OK |
| Matriz de transferencia | 1 | 0 | 844.143 s | OK |
| Matriz de adopción | 1 | 0 | 201.425 s | OK |

Los procesos se ejecutaron en paralelo; esas duraciones no se suman como duración de pared. Las tandas focales y el mutante no se suman al resultado global. Las tres omisiones son test_symlink_roots_inputs_and_archived_files_are_refused y las dos pruebas de symlink del archivo final del lock; los hardlinks reales sí se probaron.

También pasaron los comandos documentados de archive 7, la recuperación de cleanup interrumpido, los conflictos reales entre procesos, la preservación del checkout y las regresiones de perfiles/contratos/proyecciones. Controles estáticos: AST de cinco Python, enlaces relativos de cinco Markdown, jerarquía/orden del changelog y git diff --check.

## Compatibilidad y límites

Windows con Python 3.12.14 y recursos de prueba desechables, biblioteca estándar. Los tipos nuevos heredan de ValueError y mantienen compatibles los consumidores que ya lo capturan. Los mensajes de conflicto conservan su texto identificable para el reintento existente; errores E/S distintos de contención mantienen su causa y liberan el descriptor. No cambian schemas, versión preparada, estrategias de perfiles ni contratos de archivo.

Las inyecciones de permisos, Git y decodificación ejercitan las fronteras del helper; no se presentan como permisos reales alterados o como ejecución en un Git antiguo. El hardlink y los conflictos entre procesos sí se ejecutan sobre archivos/procesos reales. No se verifica runtime POSIX. Los guards específicos de propiedad/hashes y el registro de intent durable siguen exigiendo preservación cuando corresponde; ningún mensaje nuevo autoriza borrar recursos. No se modifican reviews reales ni se publica una release.
