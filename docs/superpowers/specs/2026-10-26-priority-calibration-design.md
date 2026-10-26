# Spec: calibración de prioridades P0–P3, propuesta B

Fecha: 2026-10-26, America/Mexico_City. Base verificada: `main` / `origin/main`, commit `d119fbc781312bd15c2eaf5e04f3768f542de7cc`, CCR 3.3.0. Se consultó `origin/main` con `git fetch origin main` y se actualizó el worktree por fast-forward conservando los documentos anteriores.

El usuario eligió B y solicitó este spec y el [plan de implementación](../plans/2026-10-26-priority-calibration.md). Este documento define el diseño; no registra implementación, resultados de calibración ni autorización para publicar una release.

## 1. Problema, alcance y alternativas

El [diagnóstico](../../analysis/2026-10-26-priority-calibration-diagnosis.md) encontró definiciones breves, falta de explicación de fronteras y una degradación expresamente atribuida a que la base era peor. La concentración histórica en P2/P3 no mide por sí sola errores de clasificación. El objetivo es que el revisor justifique la consecuencia y la clasifique de manera consistente, conservando confirmación, origen y bloqueo como decisiones separadas.

Se consideraron A: ampliar únicamente las definiciones; B: rúbrica, ejemplos y justificación en campos existentes; C: puntuación y nuevos campos. A no asegura uso en verificación; C introduce pesos sin calibrar y migración de consumidores. El usuario seleccionó B. No se fija una proporción esperada de P0/P1 ni se reclasifican archivos históricos.

La entrega de implementación será documentación operativa, casos sintéticos y comprobaciones de integración con contratos existentes. No crea un clasificador automático, API, comando nuevo ni framework de evaluación. Tampoco cambia perfiles, número de revisores, reglas de independencia o veredictos.

## 2. Alineación obligatoria con CCR 3.3.0

| Contrato actual | Decisión de este diseño |
|---|---|
| Nuevos resultados: final 11; históricos finales 1–10 | Se conserva final 11; ningún nuevo campo, enum o migración |
| Archive 8/layout 2; trace 1; packet 1 | Se conservan esas versiones y los gates de selección, retención y limpieza |
| `checks[].purpose`, declarado antes de ejecutar, capturado en receipt 2 | No escribir prioridad ni justificación de hallazgo en purpose; el objetivo del check sigue siendo una pregunta verificable |
| `context.check_schema_version=11` para mezclar ledger actual | Mantener el selector y purpose intactos; no volver implícitamente al merge histórico 2 |
| 27 dimensiones: A01–A05, B01–B05, C01–C05, D01–D05, E01–E07 | Mantener decisiones, agregados y referencias; ni el área ni el ID determinan prioridad |
| Evidencia por check/origen, propósito y resultado separados, cobertura en sublistas | La justificación aparece una vez en `impact`; no duplica logs, propósito o resultados |
| Comentario draft 2 y contextos editoriales vinculados a la fuente | Preservar selección de audiencia, digest y sanitización; nada autoriza publicar |

La trazabilidad nueva no resuelve por sí misma la semántica de prioridades. Por ejemplo, E02 puede cubrir aislamiento con un fallo confirmado P1 o una inspección sin defecto; un gap material sigue afectando evidencia/veredicto, no se convierte en P1 por su dimensión.

## 3. Fuente canónica y rúbrica

Crear `references/contracts/priority-calibration.md` como referencia operativa única. Es un documento compacto, con esta tabla, reglas de separación, proceso de decisión y dos ejemplos breves; el corpus amplio vive fuera de la carga normal de reviews.

| Nivel | Condición exigida | Límite de interpretación |
|---|---|---|
| P0 — Crítico | Cadena demostrada de compromiso, interrupción o corrupción catastrófica, con daño inmediato al activar/ejecutar el cambio y necesidad de contención inmediata | Explicar activo/frontera esencial, alcance y ausencia de barrera/recuperación efectiva. No exige observar antes un incidente ni afectar literalmente a todos los usuarios |
| P1 — Alto | Fallo serio alcanzable sobre función principal, autorización/datos sensibles, integridad relevante o despliegue/operación soportados | Puede afectar una sola entidad material y depender de concurrencia, entrada soportada específica o fallo de dependencia; no exige caída global |
| P2 — Importante | Defecto funcional concreto de consecuencia acotada, sin daño serio sustentado | Explicar qué acota el daño/recuperación; no es un default para información insuficiente |
| P3 — Menor | Consecuencia demostrablemente limitada, sin daño funcional relevante | Explicar el límite; no se obtiene por ser preexistente, raro, aceptado, no bloqueante o ajeno al camino feliz |

«Catastrófico» requiere justificar activos esenciales, magnitud, urgencia y barreras reales; la palabra corrupción no basta. Pérdida irreversible de un documento relevante puede ser P1; borrado inmediato e inevitable del almacén esencial completo sin barrera efectiva puede ser P0. Un fallo serio de deducciones del producto también puede ser P1 aunque no trate dinero o infraestructura.

P0 no exige irreversibilidad: una interrupción catastrófica inmediata puede requerir contención aunque un rollback posterior permita recuperar. Una recuperación solo hipotética o posterior al daño no equivale a una barrera que lo evite; documentar qué limita realmente la consecuencia, sin bajar prioridad por la mera existencia de un rollback.

### 3.1 Decisión y justificación

Para cada candidato, verificar obligación, disparador y camino alcanzable. Resolver status primero; sobre la consecuencia demostrada, evaluar el mayor nivel que sus hechos sostienen y contrastar únicamente la frontera adyacente plausible. Completar después origin y blocking. No redactar cuatro descartes mecánicos por hallazgo ni utilizar una suma numérica.

`scenario` expresa precondiciones y fallo; `impact` describe daño, ámbito, recuperación y una frase que justifica la prioridad; `evidence` respalda hechos; `blocking_reason` responde por qué impide aceptar este alcance. La frase no necesita formato literal, prefijo ni etiqueta adicional: debe poder comprenderse sin leer instrucciones internas de la skill.

Se exige esta justificación en los nuevos hallazgos confirmados. Rechazados/no resueltos no reciben una gravedad confirmada ficticia ni una explicación forzada: mantienen las reglas actuales y el contrato de prioridad obligatorio cuando se consolida un resultado final. Una evaluación sintética, que no es un resultado final CCR, puede usar prioridad nula para esos dos estados.

Si el defecto básico está probado pero una consecuencia mayor no, clasificar el efecto probado y declarar la incertidumbre mayor. Si el hecho desconocido determina la existencia misma del defecto, mantenerlo no resuelto. No degradar un bypass sin demostrar a P2 y presentarlo como confirmado.

### 3.2 Razones que no bastan para bajar o subir

- Origin preexisting, base peor o mejora parcial no reducen prioridad sin cambio efectivo de daño/exposición; sí pueden cambiar relevancia y bloqueo del MR.
- La aceptación del autor no cambia por sí sola la consecuencia. Si una decisión válida cambia el contrato, reevaluar si existe defecto y qué obligación residual queda.
- Un disparador condicionado, permiso requerido o recuperación manual necesitan análisis concreto; no equivalen a impacto menor ni garantizan urgencia alta.
- Un consumidor alternativo a la UI debe ser alcanzable y estar sujeto al contrato. No inventar integraciones futuras ni considerar la UI una validación de servidor.
- No usar benchmarks ausentes para ocultar evidencia estática decisiva; tampoco convertir operaciones extra en saturación medida sin sustento.
- Falta de test, preferencia de diseño y estilo no son defectos sin obligación/consecuencia. No llenar P3 con recomendaciones.
- P0 no requiere incidente consumado y sigue siendo excepcional por daño y evidencia. Seguridad, GUID, tenant o pérdida no son palabras que asignen niveles automáticamente.
- Una revisión anterior aporta procedencia, no autoridad para repetir su etiqueta. Recalibrar con hechos y conservar identidad/linaje sin reescribir el archivo anterior.

## 4. Integración en el flujo existente

Discovery sigue emitiendo candidatos sin prioridad. No se carga todo el corpus ni se muestra una etiqueta histórica antes del descubrimiento independiente. Los briefs conservan preguntas por dimensión/flujo y evidencia concreta.

Al preparar la verificación, el coordinador carga la referencia canónica y proporciona sus reglas pertinentes al verificador agrupado; si no se puede leer el archivo, incluye el extracto necesario en el brief. El verificador devuelve `updates.priority` y, cuando corresponda, `updates.impact`, ya permitidos en packet 1. No se hacen obligatorios esos updates en el parser ni se agregan campos a los paquetes. El coordinador es responsable de completar la justificación si no llegó en un delta.

Focused usa su pase escéptico en la misma sesión. Standard, deep y extended conservan sus obligaciones y excepciones. Un cierre limpio no requiere una evaluación de prioridades vacía ni otra carga del corpus. Una ambigüedad se resuelve en la verificación ya prevista; nuevos hechos/gates pueden exigir seguimiento según las reglas actuales, pero no se crea un agente por hallazgo o una fase adicional universal.

En consolidación, contrastar decisiones comparables del mismo ámbito para detectar razones inconsistentes, sin imponer que todos los defectos del mismo archivo compartan prioridad. La precedencia del veredicto no cambia: blocker confirmado; si no, evidencia insuficiente/gap material; después reservas y aprobación acotada.

## 5. Archivos, responsabilidades e interfaces

| Archivo | Responsabilidad del cambio |
|---|---|
| Nuevo `references/contracts/priority-calibration.md` | Definición canónica de prioridad, decisión y exclusiones de §3 |
| `SKILL.md` workflow 2–3 | Ruta de carga para verificación/consolidación; preservar `--expected-schema 11` |
| `references/execution/reviewers.md` y `worker-packets.md` | Brief, deltas existentes y responsabilidad final del coordinador; conservar packet 1, purpose y IDs vinculados |
| `references/contracts/result-contract.md` | Obligación semántica de justificación en `impact` para nuevos confirmados; sin nuevo requisito estructural retroactivo |
| `references/reporting/report-format.md` | Enlace a fuente única y ubicación de la justificación; conservar evidencia/listas de 3.3.0 |
| `references/workflow/profiles.md` | Reforzar separación de prioridad y bloqueo con ejemplo preexistente |
| Nuevo `docs/examples/priority-calibration.md`; ejemplo de disposición existente | Parejas sintéticas y enlace desde ejemplos; fuera de carga ordinaria |
| Nuevo `tests/test_review_priority_policy.py` | Presencia/ruta canónica y consistencia del flujo; no mide juicio del modelo |
| Nuevo `tests/test_review_priority_roundtrip.py` | Transporte de deltas y texto con contratos actuales sin inferir prioridad ni modificar fuente |
| Nuevo `tests/fixtures/priority_calibration/` | Corpus y referencias separados, sin datos de productos privados ni schemas de runtime |
| Nuevo `tests/test_review_priority_corpus.py` | Integridad del conjunto: IDs, separación, parejas y resultados de referencia bien formados |
| Nuevo `docs/validation/priority-calibration-protocol.md` | Protocolo manual reproducible y ficha de resultados, sin afirmar ejecuciones inexistentes |
| `CHANGELOG.md` | Entrada `unreleased` del cambio final si se implementa; este spec no asigna versión futura |

No cambiar `scripts/ccr` salvo un defecto de transporte nuevo, demostrado y aprobado como ajuste de alcance. Las APIs ya disponibles son `packets.validate(packet, ...)`, `packets.merge(context, discoveries, verification=None, ...)`, `review.validate(record)`, `render.render(record, audience='user', ..., check_publication_context=..., coverage_publication_context=...)`, `comment.prepare_public_comment(record, **publication_contexts(record))` y `comment.verify_public_comment(record, draft, body)`. Los tests deben usarlas sin introducir wrappers de producción.

Fixtures de integración: `test_review_packets.inputs()` produce contexto/candidato/decisión neutrales; `traceability_fixtures.record11()`, `set_dimension(record, id, **updates)` y `publication_contexts(record)` producen el contrato actual, las referencias por dimensión y los contextos públicos; `recovery_fixtures.record10()` comprueba historia. Para un finding final sintético usar `test_review_contract.finding()` con ID canónico y campos actualizados. No convertir el bundle de merge en final 11 solo añadiendo schema_version.

## 6. Corpus y evaluación de conducta

Crear cuatro JSON: `development-cases.json` (PC01–PC20), `development-reference.json`, `acceptance-cases.json` (PC21–PC28) y `acceptance-reference.json`, dentro de `tests/fixtures/priority_calibration/`.

Inputs son listas de objetos exactos `{id, obligation, trigger, observed_flow, consequence, affected_scope, recovery, controls, proof, unknowns}`. Valores de texto no vacíos; `proof` es lista no vacía de hechos estáticos/ejecutados descritos, `unknowns` lista de textos, posiblemente vacía. No incluyen prioridad, estado esperado, título con etiqueta, ID de reporte histórico o explicación normativa. La neutralidad del lenguaje se revisa editorialmente; un parser no la certifica.

Referencias son listas exactas `{id, expected_status, accepted_priorities, rationale, pair, invariant}`. Status: confirmed/rejected/unresolved. Confirmados tienen una lista no vacía de prioridades P0–P3 aceptables; los otros, lista vacía. `pair` es el ID de pareja o null, `invariant` es `same_priority`, `contrast` o null. La referencia documenta por qué, no exige un modelo de fraseo. Una persona con contexto debe ratificarla antes de medir eficacia; sin esa ratificación el resultado es exploratorio y no se declara calibración conseguida.

| IDs de desarrollo | Hechos a expresar en los inputs | Referencia propuesta |
|---|---|---|
| PC01/PC02 | Mismo acceso de lectura/escritura a datos ajenos sensibles demostrado; solo cambia introducido/preexistente | confirmed P1/P1, same_priority |
| PC03/PC04 | Misma alteración persistente de todas las unidades de una entidad; solo cambia que el autor reconoce el riesgo. Contrato rechaza semánticamente vacío accidental | confirmed P1/P1, same_priority |
| PC05/PC06 | Misma migración que falla atómicamente para catálogo válido, impide despliegue y deja operando la instancia anterior; solo cambia que no hay incidente desplegado frente a que la ejecución ya reprodujo el fallo. Traza estática concluyente en ambos | confirmed P1/P1, same_priority |
| PC07/PC08 | Pérdida no recuperable de actualización obligatoria del proceso principal frente a retraso acotado que incumple visibilidad inmediata de una opción secundaria, sin pérdida y con recuperación automática comprobada | confirmed P1/P2, contrast |
| PC09/PC10 | Error revela credencial que permite acceso demostrado a datos sensibles acotados de una entidad, sin administración global ni propagación, frente a identificador público sin acceso/contenido sensible adicional | confirmed P1/P3, contrast |
| PC11/PC12 | Activación elimina el único almacén esencial completo sin barrera ni restauración frente a la misma operación interceptada antes de escribir, sin efecto incorrecto residual | confirmed P0 / rejected, contrast |
| PC13/PC14 | Bypass demostrado de todos los guards aplicables frente a guard externo no inspeccionado que determina si el bypass existe | confirmed P1 / unresolved, contrast |
| PC15/PC16 | Fallback incompleto explícitamente permitido, resultado parcial señalado, frente a obligación de completitud vigente y éxito incorrecto sin señal; alcance recuperable acotado | rejected / confirmed P2, contrast |
| PC17/PC18 | Falta de test sin defecto demostrado frente a resultado funcional incorrecto acotado probado estáticamente aunque tampoco tenga test | rejected / confirmed P2, contrast |
| PC19/PC20 | Errata de ayuda con validación/envío correctos frente a campo válido transformado incorrectamente que impide una opción secundaria recuperable | confirmed P3/P2, contrast |

La referencia de aceptación contiene PC21/22 P0 (compromiso administrativo inmediato de activos esenciales e interrupción inmediata de todo el servicio esencial que requiere contención urgente aunque admita rollback posterior, respectivamente, con cadena completa); PC23/24 P1 (corrupción seria de la función principal y pérdida de original tras fallo condicional); PC25/26 P2 (fallo parcial recuperable y compatibilidad de una opción secundaria); PC27 P3 (discrepancia de ayuda sin efecto funcional) y PC28 unresolved (condición de activación desconocida determina la existencia del fallo). Las etiquetas solo van en referencias, no en inputs. Quien implemente concreta nombres de archivos/pseudocódigo sintéticos y redacta hechos suficientes para esas diferencias; no cambia la frontera de referencia por conveniencia.

### 6.1 Ejecución y medidas

Usar una sesión limpia para baseline y otra para candidato, con los mismos inputs y configuración/modelo observables; no reutilizar el contexto de respuestas entre condiciones. Conservar copia/hash de las instrucciones de 3.3.0 para baseline antes de editar la guía. Los ejecutores reciben inputs e instrucciones de su condición, nunca los archivos reference ni etiquetas históricas. No se usa la skill activa instalada como baseline si ya cambió. Las herramientas disponibles determinan la ejecución; no se fija un proveedor o CLI ficticio.

La reserva corresponde a los hechos concretos de PC21–PC28, no a sus arquetipos públicos en este spec. Un evaluador separado prepara/custodia esos inputs y referencias; quien ajusta la guía no los recibe antes de congelarla. Si un mismo autor ya redactó o leyó los casos concretos de aceptación, registrar reserva expuesta y tratar la comparación como exploratoria hasta disponer de variantes nuevas ratificadas y custodiadas por separado. Las respuestas del baseline sobre aceptación tampoco se muestran a quien ajuste la guía.

Cada respuesta de ejercicio es `{id, status, priority, justification}`: prioridad nula si no confirmó; es un formato de evaluación, no un packet ni un final CCR. Si el ejecutor confirma una hipótesis, se cuenta como error de confirmación, no como mejora por asignar P1. Registrar omisiones/respuestas inválidas por separado, sin convertirlas en P3.

Evaluar PC01–PC20 para ajustar; conservar PC21–PC28 sin exponerlos a ajustes. Repetir en contextos limpios las parejas PC01/02 y PC03/04 invirtiendo orden; informar si cambia el juicio. Comparar frontera, subclasificación P0/P1, sobreclasificación, confirmación indebida y justificación, con numeradores/denominadores y casos disputados. No medir ahorro/costos ni inferir recall sobre defectos no descubiertos.

Criterios propuestos: ninguna diferencia indebida en same_priority; ningún P0 positivo omitido ni P0 falso confirmado en la aceptación; ninguna confirmación de los negativos/no resueltos de referencia; reducción de errores graves respecto de baseline cuando baseline los tenga, sin nuevas elevaciones injustificadas. Si baseline ya coincide, exigir conservar acierto y justificar la mejora de claridad, sin inventar una ganancia de precisión. Los resultados de una muestra no certifican rendimiento general.

Una aceptación fallida no se convierte en material de ajuste silencioso: registrar exposición y usar una nueva variante reservada ratificada para reevaluar. Los cambios de referencia por desacuerdo humano se versionan y justifican, nunca para hacer pasar al candidato. Un bloqueo de herramientas o referencia pendiente deja la validación de conducta pendiente y no autoriza afirmar éxito.

## 7. Aceptación mecánica y límites

Los tests nuevos prueban ruta/integridad documental, conservación de campos y ausencia de efectos sobre fuentes. Deben aceptar un final 10 histórico sin justificación nueva y rechazar campos extra en final 11; preservar los 27 IDs y el propósito/recibo, mantener discovery sin prioridad, conservar `updates.priority`/`impact` en merge y presentar el texto en informe/comentario/breve sin duplicar los checks. Prioridad alta no fuerza bloqueo en el validador ni aprobación remota.

No se añade al parser una comprobación semántica basada en palabras. Un test verde de `impact` solo demuestra transporte; los ensayos de §6 prueban aplicación por el agente a esa muestra. La implementación puede finalizar con comprobaciones mecánicas correctas y validación de conducta pendiente, pero la política no se declara calibrada/lista para distribuir hasta resolver ese pendiente.

## 8. Verificación de esta base y decisiones

Al preparar este spec se ejecutaron con Python empaquetado: `python -B -m unittest discover -s tests -p test_review_traceability_policy.py -v` (3 pruebas) y `python -B -m unittest discover -s tests -p test_review_traceability_contract11.py -v` (6 pruebas), ambas sin fallos. Es evidencia focalizada de la base, no de la política todavía inexistente ni de toda la suite.

Una revisión independiente del diseño no dejó preguntas importantes pendientes para construir el plan. Se realizó además la autorrevisión de cobertura del spec y de interfaces del plan; se comprobaron 19 enlaces locales entre los cuatro documentos de diagnóstico/propuesta/spec/plan, sus finales de línea y whitespace. Las tres tareas y sus 24 pasos permanecen sin ejecutar. HEAD, main y origin/main coinciden con la base fijada y no hay cambios de implementación respecto de ella. El censo conserva su corte original de 3.2.0.

Decisiones del diseño: guía única, sin migración, prosa existente, evaluación separada y manual sin framework nuevo. Quien implemente decide redacción idiomática de tests y nombres sintéticos; no decide nuevos campos, pesos, cuotas, umbrales de producción ni cambios al bloqueo. No hay implementación o publicación solicitada en esta etapa.
