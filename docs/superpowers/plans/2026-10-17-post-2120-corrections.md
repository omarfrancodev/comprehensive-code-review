# Correcciones posteriores a 2.12.0

**Goal:** atender #22, #20 y #21 en el worktree preparado, preservando evidencia y ownership.

**Architecture:** completar errores tipados antes de ampliar el protocolo durable existente. Mantener locks por run y sesión, autoridad explícita, preflight de solo lectura y replay idempotente. Una cancelación no certifica cleanup ni modifica sesiones ajenas.

**Tech stack:** Python 3.10+, stdlib, unittest, Markdown.

**Spec y alcance:** [análisis de las issues](../../triage/2026-10-17-v2.12.0-issues.md). El usuario autorizó comenzar la implementación el 2026-10-17. Ejecución inline en el worktree existente; sin publicación, merge o release.

## Tareas

- [x] #22: añadir regresiones de taxonomía, preservación bajo lock, retry independiente del mensaje y conservación de tipo; observar RED, aplicar correcciones y comprobar GREEN. Archivos: `review_run_lock.py`, `review_resource_claims.py`, `review_workspace.py`, `review_artifacts.py`, tests de coordinación/restart.
- [x] #20: reproducir la adopción parcial, definir una salida durable y no destructiva, verificar negativas por identidad/trabajo y replay tras interrupciones. Archivos: helpers de artifacts/claims/recovery y tests de recuperación.
- [x] #21: cubrir adopción y transferencia durable con recurso ausente, conservar `missing_unknown` y probar interrupciones y negativas por fase. Usar el protocolo de la tarea anterior sin inventar liberaciones.
- [x] Actualizar recovery/workspaces y CHANGELOG; ejecutar módulos afectados y suite completa; obtener una revisión independiente de todo el cambio y registrar resultados y límites.

## Invariantes de revisión

- El texto de una excepción no decide si se reintenta.
- Los errores del cuerpo de una operación conservan su causa y tipo cuando no son coordinación.
- Ninguna negativa modifica evidencia; los cambios aceptados requieren autoridad y quedan registrados.
- La cancelación no convierte ownership ausente en cleanup, ni toca claims ajenos.
- Un recibo viejo no cancela un restart nuevo; cortes entre escrituras convergen a la misma decisión.

## Ledger

- Base: `6d520f7a2e51ec8ab5894a1c21f8a687d1939327` (`v2.12.0`). Solo existía el análisis de preparación sin seguimiento en Git. Baseline previa: 11/12 aprobadas, un fixture de hardlink bloqueado por permisos del sandbox.
- Ruling: se eligió la alternativa de negativa explícita admitida por los criterios de #20/#21, con decisión autorizada retenida en la traza; no un rollback general. Conserva intactos los ownership records y deja el restart pendiente. El coste de esta opción es que no permite reutilizar recursos comprometidos; una revisión independiente necesita recursos nuevos. No se cerraron issues remotas.
- #22: RED observado en siete regresiones iniciales; GREEN de las nueve pruebas finales del módulo y de contención real. Los seis tests originales de coordinación, incluido hardlink real, aprobaron fuera de la restricción del sandbox; se actualizó el contrato de sus aserciones de preservación.
- #20/#21: cuatro regresiones iniciales RED/GREEN, más CLI, adopción ausente, corrupción y dos casos derivados de revisión independiente. Se reprodujeron y corrigieron los tres hallazgos de las dos pasadas estáticas: el gate que ocultaba el tipo de negativa; sidecar ausente/bootstrap con ownership durable; y sucesor ausente degradando una transferencia a estado no preparado.
- Suite congelada: 581 IDs únicos, repartidos en 290/289 casos generales y las dos matrices extensas separadas, sin solapamiento. Los resultados definitivos quedan en el registro de validación.
- Cierre: la suite inicial obtuvo 577 aprobados, 3 omitidos por symlink y un fallo textual; el diagnóstico de recuperación se restauró y una tanda focal final de 10 casos pasó. Estado consolidado: 578 IDs aprobados y 3 omitidos, sin fallos pendientes. Hashes, inventarios y límites constan en [validación](../../validation/2026-10-17-post-2120-corrections.md).
