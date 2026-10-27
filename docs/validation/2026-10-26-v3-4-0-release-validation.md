# Preparación de publicación de 3.4.0

## Preparación incluida en el mismo merge

El [re-review del PR #33](https://github.com/omarfrancodev/comprehensive-code-review/pull/33#issuecomment-6432361599) declaró APROBABLE `e22e429ac571dc7081b88a6eb4914b89492c47f3` y confirmó F001 resuelto. La petición de publicación autoriza preparar metadata 3.4.0, changelog, enlaces de descarga, notas y validación en este PR antes del merge. La versión menor corresponde a la guía operativa nueva; se conservan schemas y runtime.

Los cambios de preparación no modifican `scripts/ccr` ni las fuentes, respuestas, referencias o hashes de la calibración. Se actualiza la expectativa de instalación a 3.4.0 y el inventario documental con la nueva referencia. Los dos inputs Markdown congelados de evaluación conservan sus bytes: la prueba documental verifica su hash declarado, en lugar de interpretar sus enlaces relativos de origen como enlaces de documentación independiente.

## Comprobaciones

El [runner reproducible y resultado del candidato](2026-10-26-v3-4-0-release-candidate.json) conserva el alcance de la ejecución. La expectativa de instalación hizo RED con 3.3.0 frente a 3.4.0. La primera ejecución usó un temporal con alias corto 8.3 de Windows y se repitió con una ruta local canónica antes de interpretar la expectativa. El inventario documental hizo RED por referencia ausente y después por enlaces reubicados de snapshots; ambos se corrigieron conservando los bytes originales. Un intento de 33 pruebas no llegó a una de las assertions porque Git rechazó la longitud de ruta de su worktree sintético; la misma selección pasó al usar un temporal canónico más corto. No se modificó runtime para corregir esa limitación del entorno.

Resultado observado: **33 pruebas distintas, 13 ayudas CLI y 91 compilaciones Python en memoria aprobadas, sin fallos ni omisiones pendientes**. Se seleccionan las pruebas de prioridades, CLI/instalación desde cwd ajeno sin PYTHONPATH, layout, inventarios de CLI/encoding, enlaces, política de trazabilidad y ejemplo archive 8. No se atribuye una ejecución global nueva a la preparación. Las pruebas que consultan el índice/filtros de Git son específicas del checkout de desarrollo; en un ZIP sin `.git` se excluyen esas dos, manteniendo la comprobación de SHA-256 declarado de todos los artefactos.

## Preflight del ZIP antes del merge

El [resultado de extracción del candidato](2026-10-26-v3-4-0-package-candidate.json) corresponde a `bf0f7e096b950283fbd4255fab3391ab88787c4e`. Se contrastaron los **383 archivos del ZIP contra todos sus blobs Git**, incluidos los **23 hashes de evidencia**, sin diferencias. La extracción sin .git pasó **31 pruebas, 13 ayudas CLI y 91 compilaciones Python**, sin fallos ni omisiones inesperadas. Se excluyeron explícitamente las dos pruebas de filtros/índice Git, ya aprobadas en el checkout de desarrollo; no se atribuyen a una instalación ZIP sin repositorio. El ZIP definitivo se reconstruirá desde el SHA integrado y se verificará de nuevo.

## Empaquetado posterior al merge

La etiqueta `v3.4.0` apuntará al SHA integrado de este mismo PR. El ZIP `comprehensive-code-review-v3.4.0.zip` se generará desde él con `git archive`, prefijo `comprehensive-code-review/`, sin temporales ni cachés. Se verificará su inventario y cada archivo contra los blobs del commit, incluidos los 23 hashes de evidencia y el baseline recuperado. No se normalizarán esos bytes.

Se compilarán los Python en memoria y se ejecutará desde la extracción el conjunto aplicable sin repositorio Git, más las trece ayudas CLI. La release adjuntará ZIP y `SHA256SUMS.txt`, y sus notas registrarán SHA integrado, hash del ZIP y resultados observados del paquete. La fecha preparada `2026-10-26` del changelog se contrastará con `publishedAt` de GitHub en America/Mexico_City. No se preparará un commit posterior en main para este release.

[Notas de release preparadas](../releases/3.4.0.md). La publicación todavía debe verificarse como operación externa; este documento no afirma que ya ocurrió.
