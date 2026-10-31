# Preparación de publicación de 3.5.0

## Preparación incluida en el mismo merge

El [comentario APROBABLE del PR #34](https://github.com/omarfrancodev/comprehensive-code-review/pull/34#issuecomment-6536758682) corresponde a ba8cd295dc6f3d309b4065591c78031e8c4eba69 y confirma F016/F017 resueltos. La petición de merge y publicación autoriza preparar changelog, enlaces, notas y validación en esta rama antes de integrarla. SKILL.md ya declara 3.5.0; la preparación no modifica scripts ni tests respecto de ese código aprobado.

El changelog consolida las correcciones de la versión por categoría y scope, sin cambiar decisiones ni atribuirlas a versiones anteriores. Se preparan los enlaces de descarga de 3.5.0 y las [notas de release](../releases/3.5.0.md). La fecha preparada 2026-10-30 se contrastará con publishedAt de GitHub en America/Mexico_City; este documento no afirma que la publicación externa ya ocurrió.

## Validación y empaquetado

El [candidato de release](2026-10-30-v3-5-0-release-candidate.json) pasó **214 pruebas distintas en 141.750 s, 13 ayudas CLI y 95 compilaciones Python en memoria**, sin fallos, errores ni omisiones. Comprueba instalación desde cwd ajeno sin PYTHONPATH, enlaces e inventarios, evidencia congelada, prioridades, topología, disclosure, publicación/entrega y modelos. El runner y la selección quedan registrados; no se atribuye una nueva ejecución de la suite completa de implementación. Se conserva aparte el alcance y la limitación de WinError 5 de la evidencia aprobada de implementación.

El ZIP candidato y el definitivo se generan con git archive, prefijo comprehensive-code-review/, sin temporales ni cachés. Se contrastan inventario y bytes contra todos los blobs del commit correspondiente y los hashes declarados de evidencia. Desde la extracción sin .git se ejecuta la selección aplicable; se excluyen expresamente las dos comprobaciones de índice/filtros Git que requieren el checkout de desarrollo.

La etiqueta v3.5.0 apuntará al SHA integrado de este PR. Tras verificar el paquete definitivo se adjuntarán comprehensive-code-review-v3.5.0.zip, release-validation.json y SHA256SUMS.txt. No se publicará un paquete npm propio ni se actualizarán instalaciones locales de la skill. La publicación de GitHub y sus assets se verificarán por separado después del merge.
