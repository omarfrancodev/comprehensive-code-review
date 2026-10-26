# Priority Calibration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Este documento no inicia implementación ni elige todavía el método de ejecución.

**Goal:** Aplicar la propuesta B para justificar y calibrar P0–P3 según consecuencias sustentadas, evitando degradación e inflación, sobre CCR 3.3.0.

**Architecture:** Una referencia canónica concentra la rúbrica y llega al verificador/coordinador por las rutas existentes. La justificación se conserva en `impact`, con deltas packet 1 y final 11. Corpus sintético y evaluación de conducta separados comprueban uso de la guía; las pruebas mecánicas solo comprueban estructura, transporte y compatibilidad.

**Tech Stack:** Markdown, fixtures JSON, Python estándar y `unittest` ya usados por el repositorio. Sin dependencias, CLI, framework de evaluación o servicio nuevos.

**Spec:** [2026-10-26-priority-calibration-design.md](../specs/2026-10-26-priority-calibration-design.md), base `d119fbc781312bd15c2eaf5e04f3768f542de7cc` (CCR 3.3.0).

## Global Constraints

- Se conserva final 11; ningún nuevo campo, enum o migración.
- Archive 8/layout 2; trace 1; packet 1.
- `context.check_schema_version=11` para mezclar ledger actual.
- 27 dimensiones: A01–A05, B01–B05, C01–C05, D01–D05, E01–E07.
- La justificación aparece una vez en `impact`; no duplica logs, propósito o resultados.
- No se fija una proporción esperada de P0/P1 ni se reclasifican archivos históricos.
- No cambiar `scripts/ccr` salvo un defecto de transporte nuevo, demostrado y aprobado como ajuste de alcance.

Conservar `checks[].purpose`, receipt 2, IDs de checks vinculados, referencias/digests públicos y precedencia de veredictos. No publicar, instalar ni elegir una versión futura desde este plan. En implementación registrar el cambio como `unreleased`; preparar release y su metadata será una acción posterior autorizada.

## Review Focus

- Origen antiguo o riesgo reconocido con daño idéntico: conservar prioridad sin forzar idéntico bloqueo. Task 1: PC01–PC04, repetición en orden inverso; Task 3: `test_priority_origin_and_blocking_remain_independent`.
- Guard/flag desconocido que determina la existencia del defecto: devolver incertidumbre en lugar de P2 confirmado. Task 1: PC13/14 y PC28; Task 3: evaluación y `test_unresolved_does_not_enter_confirmed_counts`.
- P0 demostrado antes de desplegar frente a operación interceptada: permitir el primero sin elevar la segunda. Task 1: PC11/12 y PC21/22; Task 3: validación de conducta, no inferencia por palabras.
- Final 11 con ledger actual y 27 dimensiones: no perder purpose, referencias ni justificación durante merge/render. Task 3: `test_packet1_merge11_preserves_judgment_delta` y `test_render11_preserves_impact_and_traceability`.
- Archivos finales 1–10 y nuevas salidas públicas: no exigir justificación retroactiva ni alterar bytes/contextos históricos. Task 3: `test_final10_without_new_justification_stays_readable` y `test_public_draft_and_portable_outputs_preserve_impact`.

Estas son fronteras que una prueba de presencia documental no cubre. Cada una tiene propietario y comprobación abajo; no se requiere un revisor por frontera.

## Estado de partida y orden

Worktree existente `.worktrees/priority-calibration-analysis`, rama `docs/priority-calibration-analysis`, actualizado por fast-forward desde `559fc5c` a `d119fbc` tras fetch de `origin/main`. Los cuatro archivos iniciales del análisis siguen presentes. Mantener el censo original y su digest; no reetiquetarlo como medición de 3.3.0 ni sobrescribirlo con nuevos reportes.

Ya ejecutado para preparar el diseño, no como validación de la implementación: `test_review_traceability_policy.py` (3 tests) y `test_review_traceability_contract11.py` (6 tests), ambos OK. No se ejecutó toda la suite ni se evaluó todavía el comportamiento de la nueva rúbrica.

Orden obligatorio: Task 1 fija entradas/referencia y baseline; Task 2 aplica la guía usando únicamente desarrollo; Task 3 comprueba transporte y candidato sobre aceptación reservada. Completar cada tarea antes de la siguiente. Si la referencia humana o la ejecución de baseline no están disponibles, se puede preparar material mecánico independiente, pero conservar el pendiente y no declarar eficacia ni disposición para distribuir.

Los comandos siguientes usan `python` como nombre portable. En este host se verificó el ejecutable empaquetado devuelto por `load_workspace_dependencies`; `python` del PATH apunta a un alias de Windows inaccesible. Usar ese ejecutable real con `-B`, sin instalaciones, y ejecutar desde la raíz del worktree.

## Task 1: Corpus, referencia y baseline de calibración

**Files:**

- Create: `tests/fixtures/priority_calibration/development-cases.json`.
- Create: `tests/fixtures/priority_calibration/development-reference.json`.
- Create: `tests/fixtures/priority_calibration/acceptance-cases.json`.
- Create: `tests/fixtures/priority_calibration/acceptance-reference.json`.
- Create: `tests/test_review_priority_corpus.py`.
- Create: `docs/validation/priority-calibration-protocol.md`.
- Create at actual execution only: `docs/validation/YYYY-MM-DD-priority-calibration-evaluation.md` (fecha observada, no plantilla con resultados ficticios).

**Interfaces:**

- Consumes: spec §6, las 10 parejas PC01–PC20 y ocho casos PC21–PC28 allí definidos, e instrucciones inmutables de CCR 3.3.0 en `d119fbc`.
- Produces: cuatro listas JSON con campos exactos de §6. Inputs no tienen etiquetas; referencias tienen `expected_status`, `accepted_priorities`, `rationale`, `pair`, `invariant`. IDs únicos, desarrollo/aceptación disjuntos.
- Produces: protocolo de dos condiciones, campos de respuesta `{id, status, priority, justification}` y registro observado con hash de entradas/instrucciones, contexto/configuración real, respuestas y ratificación/pendientes. No es un contrato de runtime CCR.
- Modelos/harness no están fijados por la política: usar capacidades disponibles y conservar la identidad observada o desconocida, sin inventar proveedor/modelo.

- [x] **Step 1: Escribir `tests/test_review_priority_corpus.py`** con `PriorityCorpusTests.test_case_and_reference_shapes_are_exact`, `test_ids_split_and_pairs_are_complete`, `test_inputs_do_not_contain_reference_fields` y `test_reference_matches_spec_boundaries`.

Assertions: listas de 20 y 8 entradas con IDs PC01–PC20 y PC21–PC28; igualdad entre IDs de cada input y su reference; campos exactos de §6; proof no vacío; unknowns lista; prioridades no vacías solo para confirmed; pair/invariant completos y coherentes; prioridades de referencia de la tabla y de los ocho reservados. La prueba de separación inspecciona campos y no pretende certificar neutralidad de prosa.

- [x] **Step 2: Ejecutar** `python -B -m unittest discover -s tests -p test_review_priority_corpus.py -v`. Esperado inicialmente: fallo por corpus ausente; no contar errores de importación/entorno como el RED buscado.
- [x] **Step 3: Preparar los cuatro JSON** con escenarios completamente sintéticos de §6, suficientes para distinguir la consecuencia y sus barreras. El implementador redacta desarrollo; un evaluador separado prepara/custodia los hechos concretos de aceptación y sus referencias, sin entregarlos al contexto que ajustará la guía. Si no hay separación posible, etiquetar reserva expuesta y evaluación exploratoria. La referencia puede admitir frontera múltiple solo si se razona y se actualiza el acuerdo del spec; no cambiar niveles para hacer pasar una ejecución.
- [x] **Step 4: Ejecutar de nuevo el comando de Step 2**. Esperado: los cuatro tests pasan; revisar además lenguaje neutral, coherencia de contratos y que los inputs no copien títulos de reportes privados.
- [x] **Step 5: Escribir el protocolo** con pasos de baseline/candidato, separación de contextos, reserva PC21–PC28, repetición inversa de PC01/02 y PC03/04, respuesta exacta y criterios de spec §6.1. Registrar que corpus estructural correcto no mide juicio ni discovery.
- [x] **Step 6: Ratificar referencia y ejecutar baseline** con instrucciones de `d119fbc` antes de cargar guía nueva. El ejecutor recibe solo los inputs y las instrucciones; el evaluador recibe las referencias. Guardar respuestas crudas, hechos de ejecución y desacuerdos. Si la ratificación humana no existe, etiquetar referencia propuesta/evaluación exploratoria y mantener pendiente el gate de calibración. No fabricar un baseline fallido si el revisor ya acierta.
- [x] **Step 7: Conservar snapshot/hash de baseline y fuentes** antes de Task 2; verificar que las instrucciones utilizadas corresponden al commit fijado, no a la instalación activa. Mantener inputs concretos, referencias y respuestas de aceptación fuera del contexto que ajuste la guía. Los tests automáticos pueden leerlos sin imprimir el contenido. Si no puede garantizarse independencia, documentarlo y no usar esa comparación como concluyente.
- [x] **Step 8: Crear un commit de esta tarea durante ejecución autorizada**, con los paths exactos anteriores y mensaje sugerido `test(prioridades): fijar corpus y baseline de calibración`. No incluir respuestas privadas ni evidencia no anonimizada.

**Gate:** corpus íntegro y protocolo concreto; baseline observado o pendiente explícito. Sin baseline válido no puede afirmarse mejora por el candidato.

## Task 2: Guía canónica e integración en verificación/consolidación

**Files:**

- Create: `references/contracts/priority-calibration.md`.
- Create: `docs/examples/priority-calibration.md`.
- Create: `tests/test_review_priority_policy.py`.
- Modify: `SKILL.md`, workflow 2–3.
- Modify: `references/execution/reviewers.md`, discovery/verification briefs.
- Modify: `references/execution/worker-packets.md`, verification/coordinator merge.
- Modify: `references/contracts/result-contract.md`, Findings.
- Modify: `references/reporting/report-format.md`, prioridad e impacto.
- Modify: `references/workflow/profiles.md`, Verdict decision.
- Modify: `docs/examples/review-scenario-disposition.md`, referencias de calibración.

**Interfaces:**

- Consumes: spec §3–5, corpus y baseline de Task 1. Durante ajustes, usar solo PC01–PC20 y sus referencias.
- Produces: referencia única `references/contracts/priority-calibration.md`, enlazada desde cada punto de uso, con rúbrica/razones de §3 y responsabilidad por la justificación en `impact`.
- Produces: deltas `updates.priority` y `updates.impact` de packet 1, y `impact` final 11 semánticamente justificado; ningún cambio al parser ni a sus shapes.

- [ ] **Step 1: Escribir `PriorityPolicyTests`** en `tests/test_review_priority_policy.py` con `test_canonical_reference_is_reachable_from_verification_and_consolidation`, `test_focused_and_independent_verification_routes_share_the_reference` y `test_policy_preserves_current_contract_boundaries`.

Assertions: el archivo canónico existe; los enlaces desde SKILL/reviewers/worker-packets/result-contract/report-format/profiles resuelven al mismo archivo; la ruta del coordinador cubre focused y fallback; permanecen los marcadores actuales de final 11, packet 1, selector check_schema_version y dimensiones. Revisar semántica de las reglas mediante el corpus, no exigir un párrafo literal con regex ni usar un test de strings como prueba de calibración.

- [ ] **Step 2: Ejecutar** `python -B -m unittest discover -s tests -p test_review_priority_policy.py -v`. Esperado RED por referencia/ruta ausente, con causa explícita.
- [ ] **Step 3: Escribir la referencia canónica** con la tabla de §3, seis preguntas breves de decisión, razones impropias de degradación/inflación y justificación compacta. La guía no debe cargar los 28 casos durante un review ordinario.
- [ ] **Step 4: Integrar los enlaces y reglas en los archivos modificados**. Mantener discovery sin prioridad, propagación al verificador en el brief y responsabilidad del coordinador aun cuando `updates` no incluya prioridad/impacto. Reemplazar la definición abreviada del formato por enlace/resumen compatible, sin dos fuentes normativas contradictorias.
- [ ] **Step 5: Escribir los ejemplos sintéticos** con parejas y límites de §6, enlazarlos desde el ejemplo de disposición. Separar caso permitido, incertidumbre, defecto confirmado y bloqueo; no convertir cada caso en una nueva fase de trabajo.
- [ ] **Step 6: Ejecutar** `python -B -m unittest discover -s tests -p test_review_priority_policy.py -v`, después `python -B -m unittest discover -s tests -p test_review_traceability_policy.py -v`. Esperado: todas pasan; la segunda suite debe conservar sus tres tests de 3.3.0.
- [ ] **Step 7: Evaluar desarrollo PC01–PC20 con la guía candidata**, compararlo con baseline e inspeccionar justificaciones. Ajustar solo con desarrollo. Conservar errores, cambios e incertidumbres en el registro de Task 1, sin abrir aceptación para ajustar. Si baseline y candidato ya aciertan, informar conservación/claridad, no mejora de precisión inventada.
- [ ] **Step 8: Crear commit** con paths de esta tarea y mensaje sugerido `feat(prioridades): calibrar consecuencias en la verificación`. La guía modifica la política de review aunque su implementación sea Markdown.

**Gate:** rutas presentes y reglas consistentes con 3.3.0, decisión de desarrollo documentada; sin campos nuevos ni rondas/agentes obligatorios nuevos.

## Task 3: Compatibilidad, transporte y aceptación del candidato

**Files:**

- Create: `tests/test_review_priority_roundtrip.py`.
- Modify: `docs/validation/priority-calibration-protocol.md` solo para aclaraciones que no cambien umbrales tras observar aceptación.
- Update: el registro observado `docs/validation/YYYY-MM-DD-priority-calibration-evaluation.md` de Task 1.
- Modify: `CHANGELOG.md`, entrada `unreleased`, categoría Changed, scope Reportes y entregas.

**Interfaces:**

- Consumes: `test_review_packets.inputs()`, `traceability_fixtures.record11()`, `set_dimension(record, id, **updates)`, `publication_contexts(record)`, `recovery_fixtures.record10()` y `test_review_contract.finding()`.
- Consumes: APIs existentes de `ccr.contracts.packets`, `ccr.contracts.review`, `ccr.reporting.render`, `ccr.reporting.comment` y helpers privados de `delivery` ya ejercitados por tests (`_Projection`, `_brief`). No son APIs nuevas ni cambios de producto.
- Produces: tests de caracterización del transporte actual y un informe de aceptación observado; mantiene schemas/shape y bytes de los inputs. Un bundle merge no se presenta como final 11.

- [ ] **Step 1: Escribir `PriorityRoundtripTests`** en `tests/test_review_priority_roundtrip.py` con los siguientes casos y assertions:

| Test | Assertions exactas relevantes |
|---|---|
| `test_packet1_merge11_preserves_judgment_delta` | Partir de `inputs()`, contexto con scope/ledger de `record11()` y `check_schema_version=11`, referenciar el check en packet 1. Decisión con `updates.priority='P1'`, `updates.impact=<justificación sintética>`. Merge conserva ambos textos, purpose exacto y fuentes deep-equal; discovery permanece sin priority. Mantener `test_merge_keeps_scenario_and_evidence_without_guessing_final_judgments` existente |
| `test_render11_preserves_impact_and_traceability` | `record11()` con finding F001 confirmado P1, justificación sintética, origin preexisting, blocking false y reserva/veredicto coherentes. Asociar B01 vía `set_dimension`. `review.validate` devuelve `[]`; render muestra impacto una vez en su campo, Propósito/Resultado separados y los 27 IDs; no cambia el input |
| `test_priority_origin_and_blocking_remain_independent` | Mismo finding con P1 y luego P2, origin introduced/preexisting, blocking false y reservas coherentes: contrato válido sin forzar not_approvable. La variante con blocking true y razón requiere not_approvable. Cambiar solo etiqueta no inventa un gate |
| `test_unresolved_does_not_enter_confirmed_counts` | Finding unresolved no bloqueante, limitación material de comportamiento y veredicto insufficient_evidence. Conserva prioridad formal requerida en final 11, pero no aparece en conteos confirmados; no se convierte en P2 confirmado |
| `test_final10_without_new_justification_stays_readable` | `record10()` y finding histórico canónico con impacto original sin frase nueva; validación/render siguen funcionando y fuentes deep-equal. Final 11 con `priority_reason` extra genera error; quitar purpose o una dimensión también genera error como en 3.3.0 |
| `test_public_draft_and_portable_outputs_preserve_impact` | Con fixture final 11 completo, regenerar contextos públicos tras fijar impact; prepare/verify draft 2 conserva consecuencia/justificación pública y excluye matrices internas. `_Projection.value` y `_brief` conservan priority/impact y estructura actual. Ninguna publicación, filesystem archive o patch de bytes renderizados; inputs permanecen deep-equal |

Una fixture local de test puede construir el record sintético y sus reservas; no se exporta como API de producción. El propósito/check nunca se rellena copiando el impacto del finding.

- [ ] **Step 2: Ejecutar** `python -B -m unittest discover -s tests -p test_review_priority_roundtrip.py -v`. Estos tests pueden pasar desde la base porque las APIs ya transportan los campos: registrar caracterización GREEN, sin fabricar RED ni modificar scripts para aparentar un cambio funcional. Investigar cualquier fallo real antes de ampliar alcance.
- [ ] **Step 3: Ejecutar los controles existentes pertinentes**, en invocaciones separadas:

```sh
python -B -m unittest discover -s tests -p test_review_packets.py -v
python -B -m unittest discover -s tests -p test_review_contract.py -v
python -B -m unittest discover -s tests -p 'test_review_traceability_*.py' -v
python -B -m unittest discover -s tests -p test_review_check_purpose.py -v
```

Esperado: cero fallos, conservando gates y compatibilidad de 3.3.0. Las suites con archivos temporales requieren permisos reales; un fallo de fixture/entorno no demuestra un defecto ni habilita degradar el resultado. No repetir sin causa corregida/alternativa viable.

- [ ] **Step 4: Congelar el candidato y ejecutar aceptación PC21–PC28** en contexto limpio, sin referencia visible y con configuración comparable al baseline. Puntuar después con referencia ratificada. Ejecutar además las repeticiones inversas de PC01/02 y PC03/04 previstas por el protocolo.
- [ ] **Step 5: Evaluar criterios de spec §6.1** y registrar cada error/omisión/resultado inválido, numeradores/denominadores y justificación. Si falla aceptación, conservar el fallo; ajustar con desarrollo y crear una variante reservada ratificada antes de reevaluar. Si falta ratificación, herramienta o independencia, dejar calibración pendiente y no declarar aptitud para distribuir.
- [ ] **Step 6: Registrar el resultado final real y el changelog**. En `unreleased` describir la política aplicada y sus límites; sin fecha/versión publicada inventada. No afirmar mejoras porcentuales con el censo histórico. El informe distingue tests mecánicos, conducta exploratoria/ratificada y pendientes.
- [ ] **Step 7: Ejecutar cierre acotado**: suites nuevas `python -B -m unittest discover -s tests -p 'test_review_priority_*.py' -v`, comprobar enlaces locales de documentos nuevos/modificados y `git diff --check`. No ampliar a toda la suite si los controles anteriores pasan y no aparece riesgo nuevo. Inspeccionar que `scripts/ccr` y archivos históricos no cambiaron.
- [ ] **Step 8: Crear commit** con paths de esta tarea y mensaje sugerido `test(prioridades): verificar compatibilidad y aceptación`. Conservar documentación de pendientes si los hay; commit no equivale a distribución aprobada.

**Gate:** transporte/compatibilidad verificados y estado de conducta honesto. Solo con aceptación satisfactoria y referencia ratificada se puede afirmar que la propuesta pasó su calibración de muestra; no equivale a rendimiento general ni publicación autorizada.

## Cobertura del spec y cierre de planificación

| Requisito del spec | Tarea que lo materializa |
|---|---|
| §1 alternativas, enfoque B y objetivo sin cuotas | Task 2 guía; Task 3 informe/changelog |
| §2 final 11, 27 dimensiones, purpose/receipt y publicación | Task 2 rutas y preservación; Task 3 suites de contrato y transporte |
| §3 rúbrica, frontera y separación de decisiones | Task 1 casos/referencia; Task 2 guía; Task 3 evaluación |
| §4 carga en verificación y cierre por coordinador | Task 2 policy/briefs, focused e independencia existentes |
| §5 archivos e interfaces actuales | Mapa Files/Interfaces de cada tarea |
| §6 corpus, baseline, referencia y aceptación reservada | Task 1 y aceptación Task 3 |
| §7 pruebas mecánicas frente a juicio del modelo | Task 3; resultados separados |
| §8 base observada y ausencia de implementación/publicación | Este plan y spec; se conserva el corte histórico |

Autorrevisión: las tareas tienen interfaces y comprobaciones concretas; no se añade schema 12, campo de severidad, score o motor nuevo. Los tests de transporte caracterizan APIs existentes y los de política comprueban alcanzabilidad documental. Solo la evaluación puede aportar evidencia sobre decisiones del agente. La referencia humana pendiente y la falta de herramientas no se convierten en éxito.

Plan escrito para implementación posterior. Se recomienda ejecución nativa en la misma sesión por tratarse de tres tareas muy dependientes de una guía y corpus comunes, con revisión final independiente; esta recomendación no registra elección del usuario ni inicia ejecución.
