# Preparación de cobertura explícita de dimensiones

## Alcance

El usuario pidió un worktree desde main y la preparación conjunta del [spec](../superpowers/specs/2026-10-20-explicit-dimension-coverage-design.md) y [plan](../superpowers/plans/2026-10-20-explicit-dimension-coverage.md), siguiendo Superpowers. Base observada: `09eeb03`, CCR 2.13.0. Rama: `docs/explicit-dimensions-spec`; worktree: `.worktrees/explicit-dimensions-spec`.

La propuesta adopta final schema 11 con 27 decisiones de dimensión explícitas y obligatorias, manteniendo el soporte de los contratos históricos. Este registro documenta preparación, no implementación ni una run de revisión del producto.

## Aislamiento y ejecución

- El checkout principal estaba en main, limpio; `.worktrees/` ya estaba ignorado.
- La herramienta nativa devolvió `Not a git repository` desde la raíz contenedora del chat. Git creó el worktree desde main en el repositorio CCR identificado.
- No se instalaron dependencias. Las comprobaciones usaron el Python empaquetado en `%USERPROFILE%/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`, con `-B` y TEMP/TMP exclusivos dentro del worktree.
- El seguimiento fue en línea, usando la opción de fallback de todo-workflow-controller al no estar disponible una herramienta todo. No se delegaron tareas.

## Evidencia observada

En los siguientes comandos `python` representa el intérprete efectivo anterior; todos se ejecutaron desde el worktree aislado.

| Comprobación | Resultado observado |
|---|---|
| `python -B -m unittest discover -s tests -p test_review_areas.py -v` | 16 pruebas, OK, exit 0 |
| `python -B -m unittest discover -s tests -p test_review_contract.py -v` | 34 pruebas, OK, exit 0 |
| `python -B -m unittest discover -s tests -p test_reference_layout.py -v` | 1 prueba, OK, exit 0; enlaces locales de spec y plan incluidos |

Son 51 pruebas existentes aprobadas. No prueban el comportamiento futuro de schema 11. La suite completa no se ejecutó: el alcance actual es exclusivamente documental. El plan exige ejecutarla durante la implementación, incluidas las matrices extensas de restart/resources.

## Revisión propia de los documentos

- Se compararon tres alternativas; una lista completa evita confundir una dimensión omitida con una excluida intencionalmente.
- Se fijaron 27 IDs, pertenencia al área, campos exactos, estados y agregación, incluida la precedencia material y la unión de hallazgos.
- Se mantuvo packet version 1 y el uso de los revisores y verificaciones existentes, sin nuevos agentes obligatorios.
- El plan incluye los guards de versión de perfiles, fuentes, checks, checkpoint, retención, history y proyección; no basta con aceptar el número 11 en el validador raíz.
- Las cinco clases de Review Focus tienen pruebas asignadas. AC1–AC10 se vinculan a cuatro tareas con pasos RED/GREEN y commits focalizados.
- Se distinguió la obligación del flujo nuevo de producir 11 del soporte explícito de 10 para continuidad; recovery conserva bytes reservados y no reconstruye cobertura antigua.
- El renderer privado y full muestran las 27 filas; brief resume todos los IDs y explica pendientes/exclusiones. Los comentarios públicos conservan incertidumbre material sin taxonomía interna.
- Los documentos definen garantías estructurales, sin afirmar que un test certifique el criterio del modelo o la verdad de la evidencia.

Solo se prepararon los tres documentos. No se modificaron SKILL, helpers, referencias operativas, tests, visor ni archivos reales de reviews. El spec y el plan permanecen propuestos, pendientes de revisión del usuario y elección del método de implementación. No hay publicación ni release.

## Corrección de estructura solicitada por el usuario

La primera versión del plan agrupó acciones, presentó pruebas en prosa y omitió comandos explícitos de commit; no satisfacía la estructura de `superpowers:writing-plans`. La afirmación inicial de revisión propia no detectó esas omisiones. Se conserva arriba como registro de la primera preparación, no como certificación del plan corregido.

Se reescribió el plan en seis entregables verificables: módulo puro, contrato final, archivo/continuidad, reportes, entregas y reglas operativas. Cada tarea declara Files, Consumes/Produces, tests con aserciones en código, comandos RED/GREEN y commit. La validación final y su registro son pasos separados. El spec y el alcance funcional se conservan.

Se contrastaron firmas y factories con el código actual. El plan conserva el retorno real `(record, source_maps)` de canonicalize_ids, exige remapear referencias de dimensiones y evita usar un helper de entrega que convertiría fixtures 11 de vuelta a 10. Los casos heredados de checkpoint ejercitan también 11; las clases de tests se importan mediante módulos para evitar redescubrimiento accidental.

Comprobaciones ejecutadas en esta corrección:

- Verificador documental puntual: PASS para encabezado y orden requeridos, restricciones idénticas al spec, seis tareas, Files/Interfaces, pasos consecutivos, RED/GREEN/commit y ausencia de placeholders/whitespace final.
- `ast.parse` de los seis bloques Python: PASS. Es validación de sintaxis, no ejecución de las pruebas propuestas ni validación de schema 11.
- `python -B -m unittest discover -s tests -p test_reference_layout.py -v`: una prueba aprobada, exit 0.
- `git diff --check`: exit 0.

Esta corrección modifica únicamente plan y registro de preparación. Las 51 pruebas de la tabla inicial pertenecen a la preparación anterior; aquí no se vuelven a declarar como una nueva ejecución. El seguimiento continuó en línea; no se implementó producto ni se seleccionó método de ejecución.
