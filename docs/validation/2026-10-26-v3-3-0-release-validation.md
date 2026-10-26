# Preparación y validación de publicación de 3.3.0

## Preparación en el mismo merge

La [revisión del PR 32](https://github.com/omarfrancodev/comprehensive-code-review/pull/32#issuecomment-6425920308) declaró **APROBABLE** `56b7234194e5f9845204eaf6eeb0c4341df0b478`, sin defectos confirmados y con 117 casos distintos focalizados aprobados tras repetir los afectados por errores del entorno. El PR incorpora antes del merge changelog, metadata 3.3.0, enlaces README/instalación, ejemplo archive 8, expectativa de instalación y este registro. Las referencias vigentes identifican 3.3.0; se conserva la documentación histórica.

Se asigna una versión menor por las capacidades nuevas de trazabilidad y la lectura de contratos anteriores. Los consumidores de resultados nuevos necesitan final 11; no se afirma compatibilidad del visor independiente. Cada check nuevo captura propósito antes de ejecutarse en recibo 2; los informes registran las 27 dimensiones y presentan evidencias y cobertura como sublistas. Los comentarios usan contextos editoriales ligados a la fuente y draft 2. Un draft 1 se preserva y se prepara de nuevo desde la misma fuente vigente, sin reejecutar el review.

Finales 1–10 y recibos 1 conservan sus contratos históricos; archive 8/layout 2, trace 1, packet 1, recibo de entrega 1 y criterios de evaluación/reutilización mantienen su significado. La preparación no cambia archivos Python ejecutables respecto al HEAD aprobado. Solo cambia la expectativa de versión de la prueba de instalación y documentación, incluido scripts/README.md.

## Evidencia de producto

La [validación de implementación](2026-10-26-check-evidence-coverage-implementation.md) conserva el resultado de 953 casos: **950 aprobados, 3 omitidos por privilegios de symlink en Windows, sin fallos pendientes**. Un caso recibió WinError 5 en reemplazo de manifiesto no modificado y pasó en reintento aislado con código idéntico. La revisión del PR verificó otros 117 casos focalizados. No se atribuye una nueva ejecución global a los cambios de documentación y versión.

## Validación de preparación

El [resultado y runner reproducible](2026-10-26-v3-3-0-release-candidate.json) registran las pruebas de instalación desde cwd ajeno sin PYTHONPATH, inventarios de CLI/encoding, enlaces locales, política de trazabilidad, ejemplo archive 8 y las trece ayudas CLI. Resultado observado: **17 casos distintos y 13 ayudas CLI aprobados, sin omisiones ni fallos pendientes**. La primera pasada dejó 16 aprobados y un enlace faltante al JSON de esta misma evidencia, aún no guardado; después de escribirlo, se repitió exclusivamente la comprobación de enlaces y aprobó (1 caso, 0.110 s). El JSON conserva ambos resultados y el runner reproducible. Se contrastaron los **91 archivos Python de scripts/** con sus blobs del HEAD aprobado (normalizando solo CRLF a LF): todos idénticos. git diff --check aprobó antes del commit de preparación.

## Empaquetado y publicación

El ZIP se construye desde el commit integrado con git archive, prefijo comprehensive-code-review/ y LF explícito por comando, sin cambiar configuración persistente. Se contrasta el inventario y cada archivo contra sus blobs Git, se compilan los Python en memoria y se repite desde la extracción la validación del candidato. Solo se incluyen archivos versionados, sin temporales o cachés.

La etiqueta v3.3.0 apunta al commit que integra este mismo PR. Las notas de la release registrarán el SHA integrado, inventario, SHA-256 del ZIP y resultados observados de la extracción; se adjunta SHA256SUMS.txt. La fecha preparada del changelog se contrasta con publishedAt de GitHub en America/Mexico_City. No se añadirá un commit posterior en main para preparar el release.

No hay workflows/checks CI registrados para el HEAD aprobado. Esta validación local en Windows no certifica ejecución POSIX, un MR real ni el visor independiente.
