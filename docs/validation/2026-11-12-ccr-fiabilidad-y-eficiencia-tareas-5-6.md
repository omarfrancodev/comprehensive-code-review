# Validación de las tareas 5 y 6 de CCR

Los re-reviews guiados de final 13 usan la [extensión de evaluación versión 1](../../references/contracts/assessment.md). La extensión conserva el alcance fijado, la evidencia del delta, la identidad anterior y la disposición de cada hallazgo. Los registros históricos sin la extensión conservan su lectura y presentación.

| Caso | Resultado verificado |
|---|---|
| Hipótesis futura, cobertura ausente y consumidor existente | Confirmar exige obligación, disparador alcanzable y consecuencia. La regresión del consumidor del fixture sigue demostrable. Los datos faltantes y los casos externos quedan fuera de los confirmados. |
| Misma causa con cambios de línea o agrupación | El ID publicado sobrevive. Una causa conocida con otro ID, la reutilización de un alias y la pérdida del ID previo se rechazan. |
| Deuda del fixture de la nota 23244 | Persiste como deuda aceptada con sus condiciones. El riesgo mantiene su prioridad y el informe, comentario y entrega no lo presentan como corrección exigida. |
| Reapertura | Se rechazan la falta de evidencia, el hash ya usado y el cambio de causa. Una observación del delta con evidencia nueva puede justificar el cambio de una condición y recuperar la corrección con el mismo ID. |
| Exclusión limitada al review anterior | Se rechaza usar la misma decisión como autoridad para el siguiente. Se probó el fallo antes de corregirlo y se volvió a ejecutar el caso. |
| Dos resultados con el mismo HEAD | El original muestra revisión completa y el re-review muestra seguimiento acotado. La reutilización ordinaria solo se ofrece cuando el archivo nativo anterior prueba cobertura aplicable, incluida la parte fuera del delta. El resultado identifica ese archivo por separado. |
| Archivo compacto y origen equivocado | La retención rechaza una copia alterada del resultado anterior y un archivo de otro alcance lógico. La lectura independiente conserva `F001`, la deuda y el dictamen acotado. |

La prueba de alcance usa revisiones retenidas reales sobre un repositorio sintético. Los casos de política, comentario y entrega también prueban la presentación con evidencia estática y las cuatro vías de captura de una decisión. El contrato verifica identidad, fuente y hash. La autoridad de quien decide y el significado material de la evidencia se establecen durante la revisión.

La regresión combinó cuatro grupos de contrato, escenarios, reutilización, retención, cierre, entrega y publicación. De 283 casos, pasaron 282 y el host omitió el caso de hardlinks por permisos. La prueba de integración nativa volvió a pasar después de corregir la preparación de sus materiales. Se verificaron también dependencias, inventario del CLI y enlaces.

[Plan](../superpowers/plans/2026-11-12-ccr-fiabilidad-y-eficiencia.md) · [Pruebas de evaluación](../../tests/test_review_assessment.py) · [Prueba de reutilización](../../tests/test_review_reuse_flow.py)

## Admisión del seguimiento en 3.8.0

`artifacts followup-baseline` verifica el archivo seleccionado antes de preparar el seguimiento y devuelve solo el ID, la ruta de `review.json` y el hash verificado. Se probó con archivos completos y compactos. Un archivo de otro alcance lógico se rechazó y los bytes retenidos permanecieron intactos. La retención vuelve a comprobar el vínculo, rechaza una copia alterada y conserva el ID y la deuda aceptada bajo las mismas condiciones. Una URL remota por sí sola sirve como contexto para una nueva revisión acotada.

El lector nuevo acepta a la vez un registro final 13 con `assessment` y su forma previa sin esa extensión. En una comparación local, el lector 3.7.0 rechazó la extensión y aceptó el registro sin ella. El visor independiente identifica el registro de esquema 13 como de compatibilidad limitada. La documentación de uso y las notas explican cómo coordinar la actualización de lectores y productores.
