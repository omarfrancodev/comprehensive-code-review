# Preparación y validación de publicación de 3.2.0

La [re-review del PR 31](https://github.com/omarfrancodev/comprehensive-code-review/pull/31#issuecomment-6413408354) declaró **APROBABLE** `a18b81bd375ee397a17aa61012eb7cf3d6854afe`: F001–F006 resueltos, cero hallazgos confirmados. La comprobación C019 es un fallo de fixture por una expectativa superior al contrato de snapshot, sin defecto de producto confirmado; se conserva la obligación de revalidar al ejecutar una opción.

## Preparación en el mismo merge

La preparación forma parte del PR 31 antes de integrarlo: changelog fechado, metadata 3.2.0, enlaces README/instalación, ejemplo archive 8, expectativa de versión de la prueba de instalación y este registro. Se asigna una versión menor por las capacidades compatibles de captura/comparación y admisión. El árbol de ejecución `scripts/` conserva exactamente el del HEAD aprobado; no se requiere otro PR ni commit posterior en main para preparar la publicación.

Se mantienen archive 8/layout 2, final review schema 10, trace schema 1, packet version 1 y `ccr-effective-diff-v1`. Los sidecars nuevos no migran revisiones antiguas. Sin evidencia suficiente de equivalencia y cobertura ordinaria aplicable se exige una revisión nueva, conservando la consulta histórica. La protección de snapshot no garantiza frescura bajo escritores externos arbitrarios; el coordinador revalida antes de ejecutar una opción.

## Evidencia de producto

La [validación del ajuste](2026-10-26-pr31-lineage-fixes.md) conserva el inventario y resultados de **902 casos: 899 aprobados, 3 omitidos por privilegios de symlink en Windows, cero fallos y errores**. La suite probó el producto de 4922b4b; el fixture posterior aisló el cambio de contexto Y con diff equivalente y pasó por separado. La re-review aprobatoria verificó 86 casos focalizados sobre a18b81b y reprodujo las correcciones originales. No se atribuye una nueva corrida global a los cambios de metadatos del release.

## Validación de preparación

Antes del commit de preparación aprobaron **14 pruebas focalizadas y 13 ayudas CLI**, con cero fallos, errores u omisiones. Incluyen metadata 3.2.0, instalación desde cwd ajeno sin PYTHONPATH, enlaces locales, inventarios de CLI/encoding y el ejemplo archive 8 de extremo a extremo. [Resultado y runner reproducible](2026-10-26-v3-2-0-release-candidate.json). No se reejecuta la suite global por estos cambios de documentación y versión; se verifica que scripts/ sea idéntico al aprobado.

## Empaquetado y publicación

El ZIP se construye desde el commit integrado mediante `git archive --format=zip --prefix=comprehensive-code-review/`. Solo incorpora archivos versionados y se contrasta el inventario y cada archivo con sus blobs Git. Se compilan en memoria los Python y se ejecutan desde la extracción las trece ayudas CLI y los controles de CLI/instalación, enlaces y ejemplo documentado. Las notas de GitHub registran los resultados observados, el SHA integrado y el SHA-256 final; se adjunta `SHA256SUMS.txt`.

La etiqueta v3.2.0 apuntará al commit que integre este mismo PR. La fecha del changelog se contrasta con publishedAt de GitHub en America/Mexico_City. Los datos calculados después del merge se incorporan a las notas de la release, sin un commit posterior de preparación. No hay workflows/checks CI registrados para el HEAD aprobado; los resultados aquí identificados son locales en Windows y no certifican ejecución POSIX ni un MR real.
