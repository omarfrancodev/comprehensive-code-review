# Diagnóstico de reutilización y cobertura de CCR 3.1.0

Fecha: 2026-10-25, America/Mexico_City.

Base inspeccionada: `main` / `origin/main`, commit `4fab30695bb3c0c47071eb887b38f92328b03ea2`, versión declarada `3.1.0`. La referencia remota se actualizó mediante `git fetch origin main` antes de crear este worktree. Rama de documentos: `docs/review-equivalence-and-coverage`.

Este diagnóstico y sus documentos asociados son una propuesta para implementar. No cambian el comportamiento de la skill ni constituyen otra revisión del MR 97.

## 1. Resultado

El problema existe, con un matiz: CCR ya compara las identidades exactas de entradas y distingue `applicable`, `changed` y `unknown`. Lo que falta es una comparación de cambios efectivos y una decisión de inicio que use esa comparación **antes** de ofrecer reutilización. No debe eliminarse la comprobación exacta actual: protege recuperación, reanudación e integridad.

| Capa | Comportamiento observado | Consecuencia |
|---|---|---|
| `SKILL.md`, workflow 1 | Cualquier run del mismo alcance lógico dispara la pregunta, salvo petición explícita de repetir/consultar | Un MR con cambios reales requiere una confirmación innecesaria |
| `references/archive/recovery.md` | Repite la regla de preguntar por mera existencia | Cambiar solo `SKILL.md` dejaría instrucciones contradictorias |
| `scripts/ccr/archive/lookup.py:find_candidates` | Agrupa por repositorio y selector lógico del MR/PR, con búsqueda acotada | Encuentra revisiones del mismo MR aunque cambien sus commits; esto es correcto |
| `lookup.py:select_latest` | Selecciona un resultado completo e íntegro por timestamp de metadata, con detección de empates y revalidación | Seleccionar el último no certifica que siga siendo aplicable |
| `scripts/ccr/workflow/inputs.py:compare_inputs` | Compara cada campo de `scope`, fuentes completas e identidades materiales | Un cambio de `scope.head` o `scope.base` resulta `changed` sin comparar contenido |
| `inputs.py:validate_current_inputs` | Exige scope exacto para operaciones de recuperación | Es un gate válido que debe preservarse |
| `references/workflow/re-review.md` | Reconoce que la base móvil cambia el diff y exige revisar consumidores adyacentes | La guía contiene la intención, pero falta el mecanismo de admisión y evidencia de equivalencia |

El test `test_requested_rebuild_does_not_require_identical_mr_head_to_reuse_latest` de `tests/test_review_latest.py` confirma la distinción: devuelve el último resultado con `status=selected` y `applicability=changed`. No prueba equivalencia ni permite presentarlo como vigente.

## 2. Qué persiste hoy

| Dato | Utilidad | Límite para reutilizar |
|---|---|---|
| `scope.repository/mode/reference/target` y `logical_scope` | Identifican el proyecto y la solicitud | Mismo MR no significa mismos cambios |
| `scope.base/head/snapshot` | Fijan los objetos de la revisión | Commits diferentes pueden producir cambios equivalentes |
| `review_inputs.sources`, `source_set_complete` e identidades de descripción/requisitos/plan/configuración | Vinculan fuentes declaradas a hashes | No describen por sí mismos el diff de Git |
| `evidence/reference-index.json` | Selección y aliases de entradas materiales, verificados desde 3.1.0 | No es un inventario automático de archivos Git inspeccionados |
| `cierre.json.hashes` | Integridad de evidencia seleccionada | Un hash correcto no demuestra vigencia semántica |
| `review.json`, checks y cobertura | Conclusiones y revisiones realmente ejecutadas | No permiten atribuir esas ejecuciones a un HEAD nuevo |
| Diffs opcionales en `evidence/` | Pueden ayudar a auditar | Un `delta.diff` puede ser entre revisiones, no el diff completo del MR; no se debe adivinar su semántica |

Faltan un descriptor uniforme del cambio efectivo, la procedencia de la comparación (base efectiva, target observado y política de diff) y un inventario compacto del contexto Git realmente consumido. Los archivos históricos son inmutables; su ausencia de metadata no debe convertirse en una falsa equivalencia.

## 3. Actualización del análisis del MR 97

La versión 3.1.0 corrige selección/retención de fuentes y la identidad de despachos independientes. Esas correcciones atienden los fallos de cierre observados al final de aquel caso. No corrigen la calidad del descubrimiento ni la pregunta de reutilización. Se excluyen del nuevo plan las correcciones de cierre ya publicadas.

La auditoría histórica de esta conversación se apoyó en los comentarios 21741–21749, objetos Git y paquetes retenidos de CCR; no se repitió aquí el review remoto. Sus lecciones se mantienen con estas precisiones:

| Lección | Ajuste propuesto en 3.1.0 |
|---|---|
| Contraseña vs. comprobación de BAJA | Examinar la secuencia completa de validaciones y efectos, aunque las pruebas aprueben |
| Pruebas que exigían omitir el hash o registrar un éxito ante catálogo ausente | Contrastar la expectativa del test con requisito, contrato y consecuencia; un test verde no certifica el requisito |
| Limpieza del índice actor y compatibilidad antigua ya observadas internamente | Separar detección, confirmación, severidad y bloqueo; comunicar un defecto no bloqueante o una limitación relevante en los campos existentes |
| ALTA desde estados distintos de BAJA | Enumerar las transiciones permitidas y los fallos entre SQL y Redis |
| Versiones opcionales y nuevas lecturas | Revisar contratos nuevos y costos por petición/lote de las correcciones, no solo sus casos originales |
| Propuesta de eliminar validaciones intermedias | Mantener el contraste independiente: una sugerencia externa no demuestra que su remedio literal sea seguro |

Las dimensiones actuales ya incluyen ciclo de vida, efectos de fallbacks, consumidores y rendimiento basado en escenarios. El cambio debe volver operativas esas preguntas en los briefs y en la consolidación, sin crear un reviewer por dimensión ni imponer benchmarks a todos los reviews.

El cuello de botella no es simplemente el número de agentes: el caso ya tuvo dos descubrimientos y verificación. La propuesta mejora preguntas y disposición de observaciones con el mismo perfil, reutiliza comprobaciones justificadas y evita consultas/confirmaciones sin valor. No hay medición que permita prometer un ahorro porcentual de tokens o tiempo.

## 4. Opciones consideradas

1. **Solo reescribir el prompt o comparar SHA.** Barato, pero no demuestra equivalencia ni cubre rebases, binarios y base móvil. Descartado.
2. **Usar solo `git patch-id --stable`.** Tolera cambios de historia, pero omite información relevante y normaliza whitespace; tampoco conserva requisitos, modos, contexto o procedencia suficiente. Descartado como autoridad única.
3. **Descriptor versionado del diff + contexto/entradas verificadas + decisión separada.** Recomendado. Reutiliza la integridad, selección acotada y campos públicos existentes, y mantiene estrictas las operaciones exactas de recuperación.

La opción 3 es una decisión de diseño propuesta por el agente, pendiente de revisión del usuario; no se registra como una aprobación recibida.

## 5. Evidencia de validación de la base

Ejecutado desde este worktree con el Python empaquetado y `-B`:

| Comando portable | Resultado |
|---|---|
| `python -B -m unittest discover -s tests -p test_review_inputs.py -v` | 7 pruebas, 0 fallos |
| `python -B -m unittest discover -s tests -p test_review_latest.py -v` | 9 pruebas, 0 fallos en repetición con permisos normales |

La primera ejecución de `test_review_latest.py` no alcanzó sus assertions: el sandbox negó crear/eliminar los repositorios de `TemporaryDirectory`. Se identificó `PermissionError/WinError 5` en setup/cleanup y se repitió el mismo comando con permisos normales, sin cambios de producto. No se presenta ese incidente de entorno como un defecto de CCR ni se ha ejecutado la suite completa.

Un revisor independiente del diseño identificó que faltaba concretar el mapa de materiales actuales antes de discovery. Se resolvió mediante reuse-materials anticipado y sus argumentos de CLI/sesión, sin modificar la identidad inicial del archive. La segunda lectura del revisor no dejó preguntas importantes pendientes. Esto valida la claridad del diseño, no su implementación ni su rendimiento.

## 6. Entregables enlazados

- [Spec: equivalencia y calidad del review](../superpowers/specs/2026-10-25-review-equivalence-and-coverage-design.md).
- [Plan de implementación](../superpowers/plans/2026-10-25-review-equivalence-and-coverage.md).

El criterio principal es la equivalencia demostrada de los cambios y de los insumos materiales necesarios para aplicar el resultado. La existencia de un run, un SHA igual o el conteo de pruebas no sustituyen esa demostración.
