# Preparación de publicación de 3.6.0

## Preparación incluida en el mismo merge

El [comentario APROBABLE del PR #35](https://github.com/omarfrancodev/comprehensive-code-review/pull/35#issuecomment-6599433321) corresponde a `d5af52b6e313aa72b9201a33e5952ed1e6a0835e`. La petición de merge y publicación autoriza preparar versión, changelog, enlaces, notas y evidencia en esta rama antes de integrarla. La preparación conserva sin cambios scripts y contratos respecto de ese código aprobado; en los tests sólo actualiza a 3.6.0 la aserción de versión de la copia instalada.

Se actualiza la versión de la skill a 3.6.0 y se consolidan las correcciones sucesivas del changelog por resultado final, conservando las versiones históricas. Las [notas de release](../releases/3.6.0.md) documentan compatibilidad, límites del visor y mediciones sintéticas. La fecha preparada 2026-11-03 se contrastará con `publishedAt` de GitHub en America/Mexico_City; este documento no afirma que la publicación externa ya ocurrió.

## Validación y empaquetado

El [candidato del checkout](2026-11-03-v3-6-0-release-candidate.json) registra la selección de release, resultados, ayudas CLI, compilación y runner reproducible. La selección une los checks de distribución usados en 3.5.0 con los grupos afectados de cobertura13, compactos, entrega, privacidad, trazabilidad y reutilización. No equivale a toda la suite general.

Los últimos resultados de los módulos suman **479 pruebas distintas aprobadas**, sin errores ni omisiones, además de **13 ayudas CLI y 98 compilaciones Python en memoria**. El primer intento registró dos fallos de preparación: el fixture de caída de promoción requiere el cwd del código fuente y la copia instalada aún esperaba 3.5.0. Se corrigieron el cwd del runner y esa aserción de versión; los módulos completos de promoción (7 pruebas) y CLI (5) pasaron después. El candidato conserva los dos resultados originales y los rechecks; no se presenta como una sola invocación limpia. Las ayudas CLI se comprobaron desde cwd ajeno sin PYTHONPATH.

Los paquetes candidato y definitivo se generan con `git archive`, prefijo `comprehensive-code-review/` y `core.autocrlf=false` sólo para ese comando. Se contrastan inventario y bytes con todos los blobs del commit correspondiente. Desde la extracción del candidato sin `.git` se ejecuta la misma selección, excluyendo explícitamente las dos comprobaciones de índice/filtros Git que sólo son aplicables al checkout de desarrollo.

La etiqueta `v3.6.0` apuntará al SHA integrado de este PR. Tras verificar el paquete definitivo se publicarán `comprehensive-code-review-v3.6.0.zip`, `release-validation.json` y `SHA256SUMS.txt`. No se publicará un paquete npm ni se cambiarán instalaciones locales. La publicación y sus assets se comprobarán después del merge, sin otro commit en main.

## ZIP candidato antes del merge

El [resultado del paquete candidato](2026-11-03-v3-6-0-package-candidate.json), construido desde `c5c51c422bfb87934592f05ba12db382e89b26ae`, pasó **477 pruebas distintas en 355.953 s, 13 ayudas CLI y 98 compilaciones Python**, sin fallos, errores ni omisiones. Las dos pruebas de índice/filtros Git se excluyen explícitamente y ya están cubiertas en el checkout.

Los 443 archivos del ZIP coinciden byte a byte con todos los blobs Git del candidato. Tamaño: 1608105 bytes; SHA-256: `656615e031d3dac4fd8b409109787918a8adc6d8d718b4c06470675a87a4b545`. Esta evidencia precede a la incorporación de su propio registro y esta documentación al árbol.

El ZIP definitivo se reconstruirá desde el merge y volverá a contrastarse completo con sus blobs. Antes de reutilizar la cobertura del candidato se exigirá que las únicas diferencias sean estas notas y evidencia documental de release, manteniendo idénticos scripts, tests, contratos y fixtures. Sobre la extracción definitiva se repetirán los controles de distribución y funcionamiento de CLI, cobertura13, compactos, promoción y privacidad. El resultado externo distinguirá esas ejecuciones nuevas de las 477 pruebas del candidato; no las contará como una nueva ejecución. Si cambia cualquier otra entrada, se ejecutará de nuevo la selección completa del paquete. Los resultados finales y sus hashes irán en los assets, sin otro commit en main.
