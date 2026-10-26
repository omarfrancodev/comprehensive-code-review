# Validación de lecturas eficientes de blobs

Fecha local: 2026-10-25, America/Mexico_City. Cambio sobre `8ebb952`; implementación en `0ae6509`. Rama `docs/review-equivalence-and-coverage`, base CCR 3.1.0 / `4fab306`. Push y PR autorizados por el usuario, sin merge ni release.

[Diseño](../superpowers/specs/2026-10-25-blob-read-efficiency-design.md) · [Plan](../superpowers/plans/2026-10-25-blob-read-efficiency.md) · [Inventario y resultados reproducibles](2026-10-25-blob-read-efficiency-suite.json) · [Validación anterior](2026-10-25-review-equivalence-and-coverage.md).

## Estado

Implementación y validación completadas: **874 casos en 80 módulos; 871 aprobados, 3 omitidos por privilegio de enlaces simbólicos en Windows, cero fallos y errores**. Revisión estática independiente sin hallazgos accionables. La publicación de la rama mediante PR es el paso posterior autorizado.

## Resultado funcional y de lecturas

Se deja de hashear texto completo únicamente para clasificarlo: se examinan los primeros 8000 bytes y se cierra el stream una vez observados, con un bloque máximo de 64 KiB del adaptador existente. Los hashes completos siguen siendo obligatorios para binarios, symlinks y contexto. Una transición texto/binario completa bajo demanda el hash del lado textual, sin guardar un hash parcial.

Las cachés por OID viven únicamente en cada llamada del colector. Se conservan todas las filas por ruta/lado, pero un blob repetido no vuelve a leerse. La captura siguiente lee de nuevo: no hay caché global o persistida.

| Fixture sintético con Git real | Bytes auxiliares anteriores | Bytes auxiliares nuevos |
|---|---:|---:|
| Dos rutas con texto de unos 2 MB; dos OID distintos | 8.000.028 | 131.072 |
| Dos rutas con binarios de unos 2 MB; dos OID distintos | 8.000.016 | 4.000.008 |
| Cuatro lecturas de contexto del mismo blob de 2 MB, por captura | 8.000.000 | 2.000.000 |

Se observaron bytes efectivamente entregados por `iter_git_bytes`, conservando Git real; no son bytes físicos de disco ni incluyen el trabajo interno de Git, la descompresión adelantada o las lecturas necesarias para calcular el diff. No se midió latencia ni CPU. Los streams observados se cerraron.

## Pruebas observadas

- RED: 17 casos, cuatro fallos esperados por lecturas completas/repetidas; cero errores. Los contratos de patch y hash ya pasaban antes de optimizar.
- GREEN: los mismos 17 casos aprobados. Se añadió una caracterización de stream binario interrumpido: no certifica un hash parcial y cierra la lectura.
- Regresión focalizada: 66/66 casos aprobados, sin omisiones. Incluye captura, contratos, contextos, decisión, archivo real, flujo histórico y comparación exacta de inputs.
- La suite completa se reparte en tres procesos con inventario disjunto: matriz heredada de restart/resources aislada y los otros 79 módulos entre los dos restantes. Incluye todos los casos heredados; no afirma una prueba adicional de orden monolítico.

Los seis casos añadidos cubren texto grande duplicado, binario duplicado, transición texto/binario con NUL en posición 7999, contexto compartido entre rutas/lados y dos capturas, NUL después de los 8000 bytes y cierre/error de stream binario. Las pruebas existentes preservan modos, symlinks, gitlinks, whitespace, CR y newline.

## Suite completa

| Lote | Módulos | Casos | Fallos | Errores | Omitidos | Duración observada |
|---|---:|---:|---:|---:|---:|---:|
| Restart/resources | 1 | 9 | 0 | 0 | 0 | 1515.385 s |
| Resto A | 40 | 433 | 0 | 0 | 0 | 1422.535 s |
| Resto B | 39 | 432 | 0 | 0 | 3 | 1266.419 s |

El JSON enlazado conserva los módulos exactos y el runner. Los 80 módulos se ejecutaron completos y sin solapamiento por módulo, incluidos casos heredados. Los tres procesos devolvieron exit 0. Las omisiones son los tres tests existentes que requieren symlinks reales: uno de roots/inputs/archive files y dos de lock-file safety. Windows devolvió WinError 1314; no se deshabilitaron tests ni modificaron sus assertions.

También aprobó la comprobación focalizada de enlaces documentales (1/1). `git diff --check` no mostró errores. No hubo cambios de código de ejecución después del commit `0ae6509` evaluado por la suite. Los grupos focalizados anteriores se solapan con el inventario completo y no se suman como casos adicionales.

## Compatibilidad

Se conserva `ccr-effective-diff-v1`, la estructura del descriptor y los schemas publicados. No se modifica ningún archivo histórico. Se mantienen la reconstrucción demostrable de revisiones antiguas, las decisiones conservadoras ante evidencia desconocida, la recaptura actual para verificar integridad y los gates exactos de resume/recover. El cambio afecta a la adquisición auxiliar, sin atribuir checks antiguos a un HEAD nuevo.

## Decisiones de ejecución

| Decisión | Motivo y coste si resulta insuficiente |
|---|---|
| Progreso inline | No hay herramienta todo; alternativa opcional de la skill. Menor visibilidad que un checklist nativo |
| Implementar la mejora autorizada con prefijo/caché local | Alcance establecido por el usuario y el informe previo; no se promete reducir todos los procesos con un protocolo batch |
| Conservar bloques de 64 KiB y clasificador de 8000 bytes | Evita cambiar el adaptador compartido; no prueba ahorro equivalente en lecturas físicas o descompresión |
| Suite completa en tres procesos, matriz pesada aislada | Conserva inventario y casos heredados; no ensaya además el orden monolítico |

## Revisión independiente

Revisión de solo lectura de `4fab306..0ae6509`, con prioridad al delta de rendimiento `8ebb952..0ae6509`, en contexto fresco configurado con gpt-6-astra/high. Sin hallazgos críticos, importantes o menores, ni comportamientos dejados sin juzgar por alcance. El reviewer no ejecutó pruebas y condicionó la preparación para PR a la suite completa del coordinador.

Comprobó clasificación y promoción de digest, mezclas texto/binario/symlink, gitlinks, objetos repetidos, límites NUL, texto corto/vacío, cierre y errores del stream, cachés locales, contexto compartido, consumidores de reutilización y archivos históricos, límites de memoria y alcance real de la medición. También verificó `git diff --check` del rango. La lista inicial etiquetada como descartes fue aclarada por el reviewer: eran comprobaciones efectuadas, sin comportamientos omitidos del juicio.
