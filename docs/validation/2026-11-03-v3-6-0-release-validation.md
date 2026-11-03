# Preparación de publicación de 3.6.0

## Preparación incluida en el mismo merge

El [comentario APROBABLE del PR #35](https://github.com/omarfrancodev/comprehensive-code-review/pull/35#issuecomment-6599433321) corresponde a `d5af52b6e313aa72b9201a33e5952ed1e6a0835e`. La petición de merge y publicación autoriza preparar versión, changelog, enlaces, notas y evidencia en esta rama antes de integrarla. La preparación conserva sin cambios scripts y contratos respecto de ese código aprobado; en los tests sólo actualiza a 3.6.0 la aserción de versión de la copia instalada.

Se actualiza la versión de la skill a 3.6.0 y se consolidan las correcciones sucesivas del changelog por resultado final, conservando las versiones históricas. Las [notas de release](../releases/3.6.0.md) documentan compatibilidad, límites del visor y mediciones sintéticas. La fecha preparada 2026-11-03 se contrastará con `publishedAt` de GitHub en America/Mexico_City; este documento no afirma que la publicación externa ya ocurrió.

## Validación y empaquetado

El [candidato del checkout](2026-11-03-v3-6-0-release-candidate.json) registra la selección de release, resultados, ayudas CLI, compilación y runner reproducible. La selección une los checks de distribución usados en 3.5.0 con los grupos afectados de cobertura13, compactos, entrega, privacidad, trazabilidad y reutilización. No equivale a toda la suite general.

Los últimos resultados de los módulos suman **479 pruebas distintas aprobadas**, sin errores ni omisiones, además de **13 ayudas CLI y 98 compilaciones Python en memoria**. El primer intento registró dos fallos de preparación: el fixture de caída de promoción requiere el cwd del código fuente y la copia instalada aún esperaba 3.5.0. Se corrigieron el cwd del runner y esa aserción de versión; los módulos completos de promoción (7 pruebas) y CLI (5) pasaron después. El candidato conserva los dos resultados originales y los rechecks; no se presenta como una sola invocación limpia. Las ayudas CLI se comprobaron desde cwd ajeno sin PYTHONPATH.

Los paquetes candidato y definitivo se generan con `git archive`, prefijo `comprehensive-code-review/` y `core.autocrlf=false` sólo para ese comando. Se contrastan inventario y bytes con todos los blobs del commit correspondiente. Desde la extracción sin `.git` se ejecuta la misma selección, excluyendo explícitamente las dos comprobaciones de índice/filtros Git que sólo son aplicables al checkout de desarrollo.

La etiqueta `v3.6.0` apuntará al SHA integrado de este PR. Tras verificar el paquete definitivo se publicarán `comprehensive-code-review-v3.6.0.zip`, `release-validation.json` y `SHA256SUMS.txt`. No se publicará un paquete npm ni se cambiarán instalaciones locales. La publicación y sus assets se comprobarán después del merge, sin otro commit en main.
