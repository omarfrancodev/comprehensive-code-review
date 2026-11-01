# Evaluación de cobertura agrupada y artifacts proporcionales

Medición sintética reproducible con `tests/profile_topology_fixtures.py:record12` y `tests/test_review_coverage13.py:record13`: perfil focused, una asignación de discovery y una de verificación, mismas decisiones cubiertas y mismo contenido general. Se codificaron los registros con `archive_bytes` y los informes con `render`, en UTF-8.

| Proyección | Schema 12 | Schema 13 | Variación |
|---|---:|---:|---:|
| Registro JSON | 9.773 bytes | 6.127 bytes | −37,3 % |
| Informe Markdown | 4.016 bytes | 1.869 bytes | −53,5 % |

El caso usa datos sintéticos y detalles repetidos; no mide archivos adicionales, reservas, locks, tiempo, tokens ni costo del modelo. No demuestra un ahorro equivalente en revisiones reales ni en todos los artifacts. La selección de persistencia no reduce obligaciones ni sustituye validaciones necesarias.

El visor independiente inspeccionado declara soporte para finales 1–7 y archives 1–5. Su adaptador clasifica `final 7/archive 5` como `supported` y `final 12/archive 8` y `final 13/archive 8` como `limited`. Con un fixture compacto sintético, el descubrimiento encontró una corrida y el adaptador devolvió `limited`, sin reconocer un schema de cierre. No se ha actualizado ni validado como lector íntegro de compactos; la integración del visor es trabajo separado.

## Validación de implementación

La suite se ejecutó por sus 107 módulos `test_*.py`, en procesos con directorios temporales aislados. En esa corrida pasaron 104 módulos; fallaron tres comprobaciones por referencias documentales al schema anterior, un ciclo de dependencias y la ausencia de módulos nuevos en el índice. Los tres módulos se corrigieron y pasaron en una reejecución conjunta posterior. La corrida original y su registro no se presentan como una única corrida sin fallos. El ejecutor por módulos no conservó el detalle de skips de cada módulo.

Tras las correcciones pasaron nuevamente 24 pruebas de cobertura/render, 31 de compactos/promoción, 7 de selección de persistencia, el ciclo completo de archive 8 con final 13, y las comprobaciones de dependencias, índice, políticas y caracterización CLI. Se probó la negativa a modificar un archivo externo enlazado mediante hardlink con permisos de Windows que permiten crearlo. `git diff --check` no reportó errores.

## Correcciones posteriores al code review

Se corrigieron los seis hallazgos: staging reservado en promoción, handoff privado de final 13, resolución de aliases, uso del disclosure retenido en ambas entregas, proyección del ledger de modelos en el informe compacto y límite de 256 KiB sobre los bytes originales del ledger. La recuperación de promoción se comprobó terminando un subproceso con `os._exit` antes de reemplazar el primer marcador, y reintentando luego el mismo destino.

Pasaron 185 pruebas en 14 grupos de validación, sin skips reportados: compactos/promoción/regresiones, cobertura 13, entregas históricas y URLs sensibles, disclosure/credenciales, modelos/captura, integración de topología 12, archivo completo 13, render histórico, dependencias, contratos CLI y transacciones. Esta validación usó temporales cortos y aislados en Windows; no se repitió toda la suite general. Una ejecución con temporales largos detectó una discrepancia preexistente de representación `C:\...` frente a `\\?\C:\...` en una prueba concurrente; no se presenta como resuelta por estas correcciones.

## Comentarios del PR #35: F001 y F002

El escritor compacto y el lector comparten la comprobación de tamaños: registro final serializado de hasta 16 MiB, contenido conjunto de hasta 80 MiB y evidencia seleccionada de hasta 64 MiB. El escritor comprueba además el máximo de 1 MiB por metadato antes de crear la intención o el payload. Un rechazo por tamaño no publica un destino terminal ni fija bytes inválidos en la reserva.

Se reprodujo el caso de F001 con 9 MiB en `coverage.flows` y 63 MiB de evidencia: se rechazó antes de crear la intención y el destino terminal permaneció ausente. Tras reducir el contenido, se publicó y leyó correctamente utilizando la misma reserva. Las regresiones automatizadas comprueban los límites exactos, el registro tras añadir su identidad compacta, los metadatos y el reintento tras rechazos repetidos.

La admisión de full13 para reutilización deriva estado y materialidad mediante `summarize_area13`. Se conservan los rechazos por áreas indeterminadas, brechas o limitaciones materiales y la exigencia de verificar el linaje ordinario para re-review. La prueba de integración crea archivos completos 13 reales y comprueba tanto la reutilización ordinaria como la heredada por re-review. Los compactos siguen sin acreditar equivalencia de código, dado que no conservan su inventario.

La validación focalizada reunió 196 casos en nueve grupos: 195 pasaron y uno quedó omitido, sin fallos. Cubrió las nuevas regresiones, compactos/promoción, reutilización, archivo histórico y full13, selección del último resultado, cobertura 13, dependencias y caracterización CLI. Se ejecutó con `python -B -m unittest discover -s tests -p <patrón> -q`, en temporales cortos aislados de Windows. Después de adelantar la validación de nombres antes de consultar tamaños en el lector, se repitieron las 49 pruebas de regresiones, compactos y dependencias, todas satisfactorias. `git diff --check` pasó. No se repitió toda la suite general.

## Comentarios del PR #35: F003, F004 y F005

`artifacts bind-compact` verifica la reserva y emite una copia del final con su identidad compacta antes de construir el disclosure. El CLI se probó desde un final sin identidad manual: binding, builder público `setup check-disclosure`, retención del mismo registro y sidecar, lectura y ambas entregas. Se comprueban idempotencia e inmutabilidad de la entrada y se rechazan identidades conflictivas, cambios del final posteriores al disclosure y alteraciones del anclaje de entrada. El digest sigue incluyendo el final completo; no se reconstruyen anclajes de recursos.

La entrega aplica el filtro de secretos y URLs antes de su política tipada de rutas, que relativiza las raíces conocidas del repositorio y preserva endpoints HTTP `/api/...` y `/vN/...`. Los demás consumidores de `safe_text` conservan por defecto el filtro de rutas absolutas. La regresión entrega un compacto13 sin checks ni disclosure en full y brief, verifica el JSON portable, conserva escenarios y `src/api.py`, y sigue ocultando credenciales, URLs sensibles y rutas ajenas; compara también los bytes retenidos antes y después.

Un full13 con checks y sin selección de disclosure genera ahora el contexto explicativo ligado al final retenido, igual que un compacto. La prueba crea, retiene, cierra y valida un archivo completo real antes de solicitar ambas entregas; verifica el marcador de comando no acreditado, el digest del disclosure, el hash del origen y la conservación de todos los bytes fuente. La rama de pruebas seleccionadas y los contratos históricos mantienen sus validaciones.

Se validaron 189 casos en doce grupos focalizados, sin skips. La corrida ampliada obtuvo 188 aprobados y un fallo de caracterización por faltar el nuevo comando en el inventario CLI. Se actualizó únicamente esa entrada y sus dos argumentos obligatorios, comprobando que todos los contratos anteriores permanecen idénticos; las cuatro pruebas de caracterización pasaron después. También se repitieron las dos pruebas de archivo full13 tras reforzar la aserción del marcador de comando no acreditado, ambas satisfactorias. El conjunto cubre regresiones del PR, compactos/promoción, archivo completo13, entregas históricas y URLs sensibles, disclosure/credenciales/recuperación, trazabilidad, cobertura13, dependencias y CLI. Las pruebas usaron `python -B -X utf8 -m unittest discover -s tests -p <patrón> -v` con temporales cortos aislados. `git diff --check` pasó; no se repitió toda la suite general.

## Comentarios del PR #35: F006 y F007 (2026-11-01)

Se reprodujeron las dos fugas antes de corregirlas, usando un full13 retenido, cerrado y validado. El aprendizaje de secretos de la proyección incluye ahora argumentos de credenciales, asignaciones, headers y URLs del comando canónico retenido, aun sin observación argv. Se prueban valores entre comillas, Bearer, copias Markdown/HTML/porcentuales y un comando con cola malformada. Este aprendizaje sólo amplía la ocultación: no acredita ejecución, recursos ni procedencia. El constructor y validador del sidecar conservan los hashes y anclajes originales.

Las pruebas comprueban ambas entregas, evidencia, contexto adicional y JSON portable, mantienen el marcador de comando no acreditado y comparan todos los bytes del archivo fuente antes y después. También se rechaza un secreto en una identidad estructural antes de exportar, y se oculta una copia en la vista de otro check con prueba válida sin modificar su sidecar retenido.

La clasificación de rutas conserva `/api` o `/vN` sólo ante un método HTTP o una etiqueta explícita de endpoint/ruta HTTP, admitiendo listas adyacentes de esos endpoints. Oculta rutas ambiguas y archivos locales con esos prefijos, con o sin extensión, también en frases mixtas y contexto adicional. Se mantienen las pruebas de relativización del repositorio y los controles de secretos, URLs y rutas Windows/UNC/POSIX.

La corrida ampliada pasó 291 casos en catorce grupos. Tras incorporar la regresión de la copia cruzada entre checks y sanear también ese comando en la vista, se repitieron sus seis grupos consumidores: pasaron 180 casos de entregas, disclosure/credenciales/recuperación, checks, trazabilidad, presentación y comentarios. Ambas corridas terminaron sin fallos ni skips. Los otros grupos cubrieron compactos/promoción, regresiones previas del PR, archivo full13, modelos, cobertura13, dependencias, caracterización CLI y límites de reporting. Se usaron temporales cortos aislados y `python -B -X utf8 -m unittest discover -s tests -p <patrón> -v`. `git diff --check` pasó. No se repitió toda la suite general.

## Re-review del PR #35: F006 shell y F008 (2026-11-01)

La corrección anterior de F006 cubría comandos directos pero no un script citado que quedaba como argumento indivisible. Se reprodujo esa fuga y se amplió el aprendizaje de redacciones al texto de scripts citados y anidados, separando operadores shell sin ejecutar, expandir ni acreditar comandos. La inspección deduplica textos y limita el trabajo léxico total según el tamaño original; superar el límite rechaza la proyección en vez de omitir silenciosamente credenciales internas. El constructor del sidecar y sus hashes/anclajes no cambian.

Se reprodujo también F008: la coma consumida por el primer match impedía reconocer el siguiente endpoint. Se conserva la puntuación editorial para la continuidad y se clasifican los elementos adyacentes sin espacios, manteniendo privados los archivos locales con comas. Las regresiones incluyen comas con y sin espacios, conjunciones, backticks, comillas y una ruta privada intercalada entre endpoints. Las pruebas de archivo full13 verifican full, brief, contexto, JSON, el fallback no acreditado y la conservación de los bytes fuente.

La corrida ampliada pasó 294 casos en catorce grupos. Tras reforzar el caso de una ruta privada intercalada con espacios, se repitieron cuatro grupos consumidores: pasaron 99 casos de entregas, disclosure/credenciales/recuperación, trazabilidad de entregas y presentación. Ambas corridas terminaron sin fallos ni skips. Los demás grupos cubrieron checks, regresiones previas del PR, compactos/promoción, archivo full13, trazabilidad, comentarios, modelos, cobertura13, dependencias y caracterización CLI. Se usó `python -B -X utf8 -m unittest discover -s tests -p <patrón> -v` con temporales cortos aislados de Windows. `git diff --check` pasó. No se repitió toda la suite general.
