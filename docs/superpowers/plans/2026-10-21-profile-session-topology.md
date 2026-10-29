# Session Topology, Check Disclosure and Model Provenance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** introducir final schema 12 para la topología aprobada y ampliar sus salidas con comandos/recursos originales del proyecto saneados y procedencia de modelos por participante, preservando historia y contratos publicados.

**Architecture:** partir de la forma de final 11 vigente en CCR 3.4.0, incluidos propósito y 27 dimensiones. Cambiar sólo en 12 las reglas de topología/agregación; reutilizar los propietarios modulares y el despacho original proyectado. Añadir sidecar de exposición de checks, draft público 3 y receipt de delivery 2 para la proyección nueva; reutilizar model-usage schema 1. Finales 1–11 y formatos auxiliares publicados conservan su lectura histórica.

**Tech Stack:** Python 3.10+, biblioteca estándar, unittest, Git y Markdown.

**Spec:** [Topología de sesiones por perfil](../specs/2026-10-21-profile-session-topology-design.md).

**Estado y base:** adaptación documental del 2026-10-26 a main `1d2626048a882cab510a59fd10fdbca7cf16dda5` (CCR 3.4.0), integrado mediante `67633cf` en `docs/profile-session-topology`. La base original `fd38df8` y las rutas monolíticas quedaron superadas. Ampliación solicitada el 2026-10-28: ocultación selectiva de comandos/rutas y captura/visualización de modelos del coordinador y reviewers despachados. Tareas 1–9 implementadas, revisadas y verificadas. Cierre del 2026-10-28: 1048 pruebas cubiertas, 1045 aprobadas y tres omisiones por privilegios de symlink; cero fallos. Véase el [informe de validación](../../validation/2026-10-28-profile-session-topology-implementation.md).

## Global Constraints

- Respetar las decisiones funcionales del spec §3. La versión nueva es 12 porque 11 ya está publicada con otro cambio de contrato; no reinterpretar ni migrar 11.
- Schema 12 conserva exactamente la forma de 11: propósito de checks, 27 dimensiones, referencias, execution e historia.
- Mantener archive 8/layout 2, trace 1, packet 1, reference index 1, receipt de comandos 2 y model-usage 1. Draft público 3 y receipt de delivery 2 identifican la proyección nueva; sus versiones anteriores quedan congeladas.
- Mantener validación de despacho original, identidad completa, proyección de anotaciones, fuentes, retención, cleanup y gates de proyecto.
- Agregar todas las verificaciones activas, incluidas históricas; conservar asignaciones/identidades/bindings iniciados o completados. El máximo de verificación aplica sólo a los lotes finales.
- No alterar calibración de prioridades, admisión por cambios efectivos, reutilización, evidencia ni veredictos. Conservar fidelidad de propósito/flows públicos y ampliar la política de comandos según spec §10; modelos siguen privados según §11.
- No añadir dependencias ni recrear fachadas `scripts/review_*.py`. CLI vigente: `python <skill>/scripts <area> ...`.
- No cambiar builders congelados de 8/10/11, paquetes instalados, releases ni evidencias históricas.
- Los pasos conservan las instrucciones de ejecución y sus pruebas previstas. La implementación se ejecutó en este worktree; la publicación remota sigue fuera de alcance. Las tareas 6/7 comparten un commit de integración por sus superficies de retención y rendering.

## Review Focus

1. 11 ya tiene campos y usuarios propios: 12 debe conservar propósito/dimensiones y dejar intacta la topología de 10/11. Tasks 1/2/3/5.
2. Una verificación anterior no puede borrarse para caber en el límite; una escalación puede conservar historia y uno/dos finales. Task 5.
3. Un arranque independiente temprano no se vuelve fresco con un segundo start o una anotación tardía; el provider equivocado no reemplaza al resultado. Task 5.
4. Completo/coordinador/ausencia deben producir el mismo agregado al validar registro y fuentes; degraded no exime del orden. Tasks 4/5.
5. Reconocer 12 en el parser no basta: merge, preflight, archive y salidas conservan los requisitos de 11; además deben acreditar origen de recursos para mostrar comandos y registrar modelos/ausencias por participante. Tasks 2/6/7/8/9.

## Orden, comandos y propietarios

Ejecutar Tasks 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9. Task 1 habilita forma y admisión básica; Task 4 prueba sólo agregado; Task 5 añade clasificación y gate final. No anticipar una prueba de dos lotes con fuentes antes de que exista su implementación en Task 5.

Los comandos unittest se ejecutan desde `tests/`; Git, rg y CLI desde la raíz del worktree. Usar `-B` para no generar bytecode. No ocultar el código de salida con tuberías a tail. La suite final se ejecuta una vez; no se afirma un número o duración de tests basándose en la línea base anterior.

| Task | Crear | Modificar |
|---|---|---|
| 1 | tests/profile_topology_fixtures.py, tests/test_review_profile_topology.py | scripts/ccr/contracts/review.py, findings.py, execution.py (rutas completas bajo scripts/ccr/contracts/) |
| 2 | tests/test_review_topology_integration.py | Contratos, archive, reporting y CLI enumerados en Task 2; fixtures nuevos |
| 3 | — | scripts/ccr/contracts/execution.py y tests/test_review_profile_topology.py |
| 4 | — | scripts/ccr/contracts/execution.py y tests/test_review_profile_topology.py |
| 5 | — | scripts/ccr/contracts/execution.py y los dos módulos nuevos de fixtures/tests de topología |
| 6 | Contrato/proyección de checks y tests de exposición nuevos | Reporting, captura y gates de fuentes detallados en Task 6 |
| 7 | Tests de captura/presentación de modelos nuevos | Setup/builders, renderer, retención y coordinación de Task 7 |
| 8 | docs/examples/check-disclosure-and-models.md | SKILL.md, ejemplos mantenidos y referencias enumeradas en Task 8 |
| 9 | — | README.md, docs/usage.md, CHANGELOG.md, SKILL.md |

`validate_profile_execution` está en `ccr.contracts.execution`, no en `ccr.workflow.profiles`. Este último conserva selección/registry y no necesita cambios salvo que una prueba demuestre una dependencia adicional.

Inventario inicial: `rg -n 'schema_version|check_schema_version|expected.schema|== 11|in \(10, 11\)' scripts/ccr`. Clasificar cada coincidencia por forma, requisitos de 11, topología congelada o formato independiente; no hacer reemplazos globales.

---

### Task 1: Forma de schema 12 y fixtures separados

**Files:**
- Create: `tests/profile_topology_fixtures.py`, `tests/test_review_profile_topology.py`.
- Modify: `scripts/ccr/contracts/review.py`, `scripts/ccr/contracts/findings.py`, `scripts/ccr/contracts/execution.py`.

**Interfaces:**
- Consumes: `traceability_fixtures.record11(profile, source)`, `recovery_fixtures.context10(record)`, `selection`, `source_events`.
- Produces: en `ccr.contracts.execution`, `PROFILE_SCHEMAS = (10, 11, 12)`, `NEW_TOPOLOGY_SCHEMAS = (12,)`; no constantes nuevas en workflow.
- Produces: `record12(profile='deep', source='explicit', discovery=2, verification=1, verification_ids=None) -> dict`.
- Produces: `source_fixture12(record) -> tuple[dict, list[dict], set[str]]` (contexto, eventos, referencias), compatible también con registros sintéticos 10/11 para comparar.
- Los módulos nuevos llaman `script_test_support.enable_package_imports()` antes de importar `ccr`. No importar archivos retirados ni cambiar sys.path de producción.

- [x] **Step 1: Añadir fixture y pruebas rojas**

`record12` copia profundamente `traceability_fixtures.record11`, cambia sólo la versión a 12 y reconstruye plan/resultados para las cantidades solicitadas. Conserva checks con purpose, dimensiones y demás campos. Cada asignación recibe S001 y superseded_by null; IDs únicos D1...Dn y V1...Vn, o los explícitos recibidos. Cada resultado conserva identidad propia cuando se exige independencia; focused usa coordinator en descubrimiento y verificación. Verification inicial: skipped si no hay filas, same_session en focused, independent en otro caso.

`source_fixture12` usa context10/source_events sin modificar sus builders. Incluye todas las referencias de selección, briefs y resultados; para cada fallback añade su fuente y un evento sintético interruption/blocked con secuencia/event_id únicos. No acredita éxito por el estado declarado. Las transiciones históricas complejas se incorporan en Task 5.

En el módulo nuevo importar `review` de `ccr.contracts` directamente. Añadir:

```python
def test_schema12_keeps_purpose_dimensions_and_rejects_13(self):
    value = record12()
    self.assertEqual(review.validate(value), [])
    self.assertEqual(sum(len(row['dimensions']) for row in value['coverage']['areas']), 27)
    self.assertTrue(all(row['purpose'] for row in value['checks']))
    bad = copy.deepcopy(value)
    bad['schema_version'] = 13
    self.assertTrue(any('unsupported version' in error for error in review.validate(bad)))
```

Añadir variantes que omitan purpose o una dimensión en 12 y afirmen el error correspondiente. Comparar también `review.validate(traceability_fixtures.record11()) == []` antes/después, sin modificarlo.

- [x] **Step 2: Verificar el rojo**

Run: `python -B -m unittest test_review_profile_topology`.
Expected: falla el registro 12 por versión no soportada; no interpretar otros errores derivados como prueba de topología.

- [x] **Step 3: Habilitar forma y admisión básica**

En review, extender las tuplas de forma a 12 y el conjunto soportado a 1–12. Los dos bloques que añaden/validan dimensiones para 11 pasan a `in (11, 12)`. En findings, los campos/procedencia existentes incluyen 12 y los bloques de purpose cubren 11/12. No relajar purpose_errors ni el catálogo de dimensiones.

En execution, introducir las constantes indicadas; los guards de forma/historia/bindings y descubridores independientes pasan a PROFILE_SCHEMAS, incluido validate_profile_execution. El bloque de admisión básica de 10/11 admite 12 sin un máximo global de filas de verificación. No enviar 12 a la rama legacy que exige una sola fila activa.

Dejar congeladas las reglas de 10/11. Para 12 usar provisionalmente las tablas actuales y el agregado binario legacy hasta Tasks 3/4, y el gate de único candidato final actual hasta Task 5. Esto permite los verdes de forma con un único lote; no presume que la topología esté implementada.

- [x] **Step 4: Verificar verde y regresión**

Run: `python -B -m unittest test_review_profile_topology test_review_contract test_review_traceability_contract11 test_review_dimensions test_review_profiles test_review_execution_policy`.
Expected: PASS para las pruebas incorporadas hasta aquí; ningún cambio a los fixtures 8/10/11.

- [x] **Step 5: Commit de implementación futura**

Staging sólo de los cinco archivos de esta task. Mensaje: `feat(contratos): reconocer final 12 conservando proposito y dimensiones`.

---

### Task 2: Reconocimiento integrado sin perder requisitos de 11

**Files:**
- Create: `tests/test_review_topology_integration.py`; extender `tests/profile_topology_fixtures.py`.
- Modify, donde exista un guard de versión relevante:
  - `scripts/ccr/contracts/identifiers.py`, `provenance.py`, `receipts.py`, `packets.py`, `preflight.py`.
  - `scripts/ccr/archive/retention.py`, `lifecycle.py`, `checkpoints.py`, `history.py`.
  - `scripts/ccr/cli/artifacts.py`.
  - `scripts/ccr/reporting/render.py`, `projections.py`, `delivery.py`; comprobar `comment.py` sin cambiar su draft 2.

**Interfaces:**
- Consumes: record12 de Task 1, `traceability_fixtures.receipt2_bundle` y los seams actuales de `test_review_traceability_archive.Archive11Tests` / `TraceabilityCheckpointTests`.
- Produces: `publication_context12(record) -> dict` en el fixture nuevo: clasificación de checks/flows ligada al digest real de 12, con propósito público explícito. Puede reutilizar los constructores de publication_fixtures y completar purpose, sin cambiar los fixtures históricos.
- El módulo de integración crea casos nuevos o subclases locales de los seams citados; no modifica la versión ni los expected_schema de tests 11 existentes.

- [x] **Step 1: Añadir pruebas de integración rojas**

Estas pruebas fijan el reconocimiento de 12 heredado de 11. Antes de Task 6 usan provisionalmente draft 2/receipt de delivery 1; Task 6 amplía los casos nuevos 12 a los formatos y sidecar de exposición, conservando los tests históricos 11 sin cambios.

Usar `record12('focused', 'automatic', discovery=1)` para no depender de Tasks 3/5 y coincidir con la selección inicial de los montajes nativos 11 reutilizados.

| Prueba nueva | Aserciones |
|---|---|
| test_schema12_archive_roundtrip | Preparar, retener con expected_schema=12, cerrar y validar require_complete; review.json sigue en 12 y conserva purpose/27 dimensiones |
| test_schema12_checkpoint_promotes_exact_bytes | Nuevo caso de checkpoint final 12; promoción conserva los bytes exactos y su historia |
| test_schema11_expectation_rejects_schema12 | expected_schema=11 con candidato 12 falla antes de retener; no se ignora la igualdad solicitada |
| test_schema12_preflight_rejects_missing_traceability | Adaptar el seam Preflight11Tests.evaluate a datos 12; purpose ausente/dimensión omitida bloquean candidate.structure |
| test_schema12_receipt2_and_provenance | Recibo 2 válido con purpose y fuentes pasa; recibo 1 para nuevo check local 12 o purpose distinto se rechaza; preservar política de reused |
| test_schema12_packet_merge_keeps_purpose | check_schema_version=12 admite ledger válido y conserva purpose; faltante se rechaza; defaults 2 y casos 11 no cambian |
| test_schema12_render_and_delivery | Reporte privado y full/brief conservan propósito y dimensiones donde corresponda; portable review.json de full mantiene 12; fuente retenida no muta |
| test_schema12_public_draft2 | prepare/verify con publication_context12: draft sigue en 2, propósito y flows públicos clasificados, sin matriz/dimensiones ni rutas privadas; digest equivocado o clasificación incompleta se rechazan |

Los tests de archive reutilizan el montaje sintético vigente de Archive11Tests, suministrando un final 12 y expected_schema=12 a los seams correspondientes; los nuevos casos de checkpoint sobreescriben final_record y preservan los campos de dimensión. No convertir bytes históricos ni asumir que publication_contexts(record12) ya agrega propósito.

- [x] **Step 2: Confirmar el rojo**

Run: `python -B -m unittest test_review_topology_integration`.
Expected: fallos de admisión de 12, gates de archive o pérdida de requisitos/clasificación; identificar el guard responsable antes de editar.

- [x] **Step 3: Extender los consumidores por semántica**

Incluir 12 en versiones de identidad, ejecución y procedencia. Los guards de propósito/recibo nuevo, preflight estructural, render de dimensiones y clasificación pública que hoy son `== 11` cubren `(11, 12)`. Una comparación de **receipt.schema_version** o **draft.schema_version** no es una versión de final y no se cambia en esta task; los formatos nuevos se implementan expresamente en Task 6.

En packets, admitir check_schema_version 2/11/12, aplicar a 11/12 la validación de procedencia y conservar el default 2. El contrato del packet sigue en 1.

Archive: extender los gates de retention, lifecycle y checkpoints a finales 10/11/12, sin saltar execution_gate ni fuentes. Actualizar identidad de review, recibos y creación de evidencia para 12. En retention y parser artifacts, expected_schema admite range(1, 13), conserva igualdad exacta y actualiza diagnósticos. Verificar history sin cambiar su límite de **archive** histórico.

Los bloques de render/full/brief y public_checks deben reconocer 12 con los requisitos de 11, no caer en proyecciones legacy que omitan dimensiones o propósito. En esta task comment conserva provisionalmente draft 2; Task 6 implementa la proyección nueva y actualiza los casos 12 a draft 3.

- [x] **Step 4: Verificar verde y regresiones**

Run: `python -B -m unittest test_review_topology_integration test_review_traceability_contract11 test_review_traceability_archive test_review_traceability_preflight test_review_traceability_comments test_review_traceability_delivery test_review_check_receipts test_review_packets`.
Expected: PASS. Inspeccionar además el inventario de versiones, explicando ramas congeladas y formatos independientes.

- [x] **Step 5: Commit futuro**

Staging sólo de los propietarios modificados y tests nuevos de esta task. Mensaje: `feat(archivo): admitir final 12 en retencion y proyecciones`.

---

### Task 3: Cardinalidad de descubrimiento sólo en 12

**Files:** modificar `scripts/ccr/contracts/execution.py` y `tests/test_review_profile_topology.py`.

**Interfaces:** produce `NEW_PROFILE_LIMITS = {'focused': (1, 1), 'standard': (1, 1), 'deep': (2, 2), 'extended': (3, 5)}` en execution; consume NEW_TOPOLOGY_SCHEMAS de Task 1.

- [x] **Step 1: Añadir pruebas de fronteras y compatibilidad**

Para **explicit y automatic**: deep 2 válido, 1/3 inválidos; extended 3/5 válidos, 2/6 inválidos. Error: `discovery cardinality does not match profile/selection`.

Construir casos independientes de schema 10 mediante recovery_fixtures.record10 y de 11 mediante traceability_fixtures.record11: deep con tres descubridores, extended explícito con dos y automático con cuatro siguen válidos. Añadir D3 con ID/referencias/resultado únicos sin cambiar el builder congelado ni quitar propósito/dimensiones de 11.

- [x] **Step 2: Confirmar el rojo**

Run: `python -B -m unittest test_review_profile_topology`.
Expected: límites antiguos aceptan deep 3/extended explícito 2 y rechazan extended automático 3 en 12.

- [x] **Step 3: Bifurcar ambas reglas en execution**

En validate_execution, sólo para 12 usar NEW_PROFILE_LIMITS. El legacy conserva deep 2–3 y extended automático 4–5 / explícito 2–5.

En **validate_profile_execution del mismo archivo**, mínimo de extended 12 = 3 para ambas fuentes. Los cálculos de acquired_extended_auto y obligación heredada 4/2 se conservan para 10/11. Mantener la elección strongest, historia/registry y reglas de independencia adquirida.

- [x] **Step 4: Verificar verde**

Run: `python -B -m unittest test_review_profile_topology test_review_profiles test_review_execution_policy test_review_traceability_contract11`.
Expected: PASS; los tres builders históricos quedan intactos.

- [x] **Step 5: Commit futuro**

Mensaje: `feat(perfiles): fijar limites de descubrimiento de final 12`, sólo execution y tests de esta task.

---

### Task 4: Agregado único de verificaciones activas

**Files:** modificar `scripts/ccr/contracts/execution.py` y `tests/test_review_profile_topology.py`.

**Interfaces:** `verification_status(verification, observed, missing) -> str | None` en execution; todas las filas activas, históricas y finales. None sólo cuando no hay filas; el caller conserva el caso permitido skipped.

- [x] **Step 1: Añadir casos de agregado sin traza**

| Resultados requeridos | coverage.verification | Montaje |
|---|---|---|
| Dos independientes | independent | Un resultado por cada ID |
| Independiente + coordinador | same_session | Mutar el resultado de V-invariantes, no duplicar V-candidatos; fallback de V-invariantes |
| Uno o ambos ausentes | unavailable | Mantener las filas del plan; fallback por cada obligación incumplida |
| Coordinador + ausencia | unavailable | Documentar ambos impedimentos; la ausencia domina |

Afirmar IDs de resultados únicos y conocidos. El estado es degraded en los casos de fallback; cada fallback tiene fuente y razón admitida. Estas pruebas llaman sólo review.validate/validate_execution: la admisión básica existe desde Task 1; el gate de fuentes con pares llega en Task 5.

- [x] **Step 2: Confirmar el rojo de agregación**

Run: `python -B -m unittest test_review_profile_topology`.
Expected: al menos ausencia parcial devuelve el estado incorrecto con la agregación provisional. Los errores no deben deberse a IDs duplicados o rechazo anticipado de varias filas.

- [x] **Step 3: Implementar sólo en 12**

Algoritmo: sin filas → None; cualquier fila sin resultado → unavailable; con todos presentes, cualquier fila en missing o no independiente → same_session; resto → independent. missing incorpora las pérdidas de independencia y fallbacks según la validación existente. El caller resuelve skipped para standard limpio sin filas y conserva el enum.

No recalcular el estado desde un único candidato final. Mantener intactos los agregados congelados de 10/11 y legacy. Esta función no decide frescura ni clasifica historia.

- [x] **Step 4: Verificar verde**

Run: `python -B -m unittest test_review_profile_topology test_review_profiles test_review_execution_policy`.
Expected: PASS para las pruebas sin traza incorporadas.

- [x] **Step 5: Commit futuro**

Mensaje: `feat(ejecucion): agregar verificaciones activas en final 12`, sólo execution y tests de esta task.

---

### Task 5: Historia, lotes finales y despacho original

**Files:** modificar `scripts/ccr/contracts/execution.py`, `tests/profile_topology_fixtures.py`, `tests/test_review_profile_topology.py`.

**Interfaces:**
- `verification_batches(record, trace_events) -> tuple[list[dict], list[dict], int]` en execution: historical, final, last_discovery, tras validar bindings/fuentes.
- `historical_fixture12(profile='deep', verification=1) -> tuple[dict, dict, list[dict], set[str]]` en fixtures nuevos: record, context, events, references.
- Consumir la proyección existente de dispatch y **original_dispatch**; no cambiar su API ni recrear la búsqueda vulnerable por cualquier start.

- [x] **Step 1: Construir escenarios y pruebas rojas**

Fixture deep: D1/D2 y V-previa bajo S001; V-previa termina antes del cierre de D2; V1 final posterior. Fixture extended: S001 deep automático ejecuta D1/D2/V-previa; después S002 extended explícito con autoridad sintética antes de D3/finales, que se vinculan a S002. Mantener selection_source inicial automático y las filas previas requeridas. verification 0 omite sólo finales, 1 añade V1, 2 añade V-candidatos/V-invariantes. Construir eventos intercalados con IDs/secuencias coherentes; source_events emite selecciones al principio y no se reutiliza sin adaptar esa cronología. Nunca reescribir una traza retenida.

| Prueba / grupo | Resultado exigido |
|---|---|
| deep con previa + un final | Ambos validadores aceptan; historia conserva binding/resultado e identidad |
| escalación con previa + uno/dos finales | Ambos aceptan; el total activo puede exceder el máximo final |
| historia sola sin obligación final | Fuentes rechaza requires at least 1 final verification batches |
| descubrimiento nuevo impedido al escalar | Previa conserva carácter histórico por binding anterior; degraded representa el impedimento sin borrar trabajo |
| resultado histórico ausente / histórico con coordinador | Fallback/fuentes exigidos; agregado unavailable / same_session aunque los finales sean independientes |
| extended con tres finales observados | Contrato sin traza puede aceptar; **fuentes** rechaza at most 2 final verification batches |
| focused/standard/deep con dos finales | Fuentes rechaza at most 1 final verification batches |
| standard limpio sin verificación / material sin final | skipped aceptado / ausencia de obligación final rechazada |
| lote final comienza antes o igual a frontera y termina después | Rechazo de fuentes en fulfilled y degraded, sin esconderlo como histórico |
| original temprano + segundo start tardío | Sigue rechazado; no elegir el segundo start para acreditar frescura |
| anotación tardía sobre original temprano | Sigue rechazado, conservando secuencia original |
| anotación sobre original fresco y provider correcto | Par final válido; otro provider no suplanta ni invalida la identidad correcta |
| provider/contexto compartido entre lotes | No acredita independencia; fulfilled se rechaza |
| fallback del coordinador con inicio de etapa, sin agent/started | Degraded con same_session y fuentes válidas; no inventar despacho. Quitar el fallback de esa asignación o su inicio se rechaza |
| schema 10 y 11 con dos finales realmente posteriores | Fuentes conserva el rechazo one fresh verifier after the final discovery batch |
| schema 10 y 11 con histórica + final | Sigue admitiéndose según sus reglas congeladas |

Ampliar aquí todos los casos de Task 4 con source_fixture12: los pares válidos y sus fallbacks deben pasar fuentes; quitar fuente o milestone de impedimento se rechaza. Los tests de tres finales llaman explícitamente validate_execution_sources, no sólo review.validate.

Reutilizar como referencia los escenarios existentes test_late_verifier_identity_does_not_move_early_dispatch_after_discovery, test_later_start_cannot_replace_early_independent_dispatch y test_fresh_recovered_verifier_ignores_other_provider_dispatch de test_review_execution_policy; construir variantes nuevas para **dos lotes en 12**, sin cambiar la versión de esos tests congelados.

- [x] **Step 2: Confirmar el rojo**

Run: `python -B -m unittest test_review_profile_topology`.
Expected: el gate provisional de único final rechaza pares 12; los tests congelados pueden estar verdes.

- [x] **Step 3: Implementar clasificación y gate sólo en 12**

verification_batches aplica exactamente spec §6.1: históricas por binding válido a perfil anterior menor que strongest o finalización válida <= frontera; resto finales, incluidas obligaciones actuales sin resultado. Obtener strongest de las mismas obligaciones existentes, sin inventar selección ni depender del orden del array/ID.

En validate_execution_sources, conservar la rama de 10/11. Para 12:

1. Mantener registry/historia; no cambiar identidad, role, selection_id ni superseder trabajo iniciado/completado.
2. Validar cantidad final: focused/deep (1,1), standard (0,1) si su excepción aplica y (1,1) en caso material, extended (1,2), incluso degraded. Diagnósticos exactos: `{strongest} requires at least {minimum} final verification batches` y `{strongest} permits at most {maximum} final verification batches`.
3. Exigir binding al perfil de mayor obligación activa e independencia planificada en cada final cuando corresponda; conservar los bindings históricos.
4. Reutilizar observed_starts proyectados y original_dispatch con nombre/provider completos y **primer despacho** coincidente anterior a la finalización. Exigir original > last_discovery. En un fallback documentado de esa asignación al coordinador sin despacho coincidente, validar el milestone observado de inicio de etapa posterior a la frontera, sin simular independencia; si existe despacho original coincidente, no reemplazar su orden por otro start. Un fallback ajeno o el estado global degraded no habilitan la excepción. El diagnóstico temprano es `final verification batch must start and complete after the final discovery batch`. Una anotación no aporta una fecha nueva ni un provider alternativo.
5. Rechazar orden observado inválido en ambos estados. Permitir ausencia o fallback real sólo con su fuente/milestone; una fila final ausente sigue contando en el límite. Una histórica ausente conserva su obligación y efecto unavailable sobre el agregado.
6. Reutilizar el agregado de Task 4 sobre todas las filas activas; no compararlo de nuevo con final_candidates[0]. Fulfilled exige cumplimiento; independent agregado no implica por sí solo fulfilled.

- [x] **Step 4: Verificar verde y regresión de cierre**

Run: `python -B -m unittest test_review_profile_topology test_review_profiles test_review_execution_policy test_review_dispatch test_review_closure_consistency test_review_traceability_contract11`.
Expected: PASS, incluidos los casos de identidad tardía y despacho original incorporados desde main.

- [x] **Step 5: Commit futuro**

Mensaje: `feat(perfiles): validar lotes finales sin descartar historia ni frescura`, sólo los tres archivos de esta task.

---

### Task 6: Exposición selectiva de comandos y recursos acreditados

**Files:**
- Create: `scripts/ccr/contracts/check_disclosure.py`, `scripts/ccr/reporting/check_disclosure.py`, `tests/test_review_check_disclosure.py`, `tests/test_review_disclosure_integration.py`.
- Modify: `scripts/ccr/reporting/projections.py`, `render.py`, `delivery.py`, `comment.py`; `scripts/ccr/cli/contract.py`, `comment.py`, `delivery.py`; `scripts/ccr/execution/checks.py`, `scripts/ccr/workflow/builders.py`, `scripts/ccr/archive/retention.py` y su gate de fuentes, sólo para conectar la captura/proyección seleccionada.
- Extend: fixtures e integración nuevos de Tasks 1/2; los tests/formatos históricos 11 no se convierten en pruebas de la política nueva.

**Interfaces:**
- En contracts/check_disclosure: `validate_check_disclosure(record, disclosure, sources, input_identity) -> list[str]`, puro. Contrato exacto y modos: spec §10.4. sources contiene bytes seleccionados de ejecución/pertenencia al input; input_identity proviene del scope fijado.
- En workflow/builders: `build_check_disclosure(record, input_identity, execution_observations, sources) -> dict`, constructor puro del sidecar. La captura acotada de recursos/argv/hashes ocurre en el ejecutor/recorrido vigente, antes del check, sin introducir IO en contracts/reporting.
- En reporting/check_disclosure: `project_check_disclosure(record, disclosure, sources, input_identity) -> dict`, valida el contrato y produce `{source_sha256, check_disclosure_sha256, checks}`. Filas de vista: `{id, mode, command, resources, explanation}`; resources son paths acreditados ya saneados, con marcadores visibles si se ocultaron segmentos. Nunca devolver argv/fuentes privadas en esa vista.
- Propagar keywords `check_disclosure_context` y `check_disclosure_sources` por prepare/verify/render/delivery. Los wrappers CLI aceptan el sidecar de exposición y resuelven únicamente sus fuentes seleccionadas con los guards de rutas existentes.
- La fuente canónica sigue intacta. El nuevo draft 3 contiene la vista/digest y rerenderiza con la evidencia contrastada; el receipt de delivery 2 identifica política y digests según spec §10.4.

- [x] **Step 1: Escribir pruebas de política y sus negativos**

| Prueba nueva | Aserción concreta |
|---|---|
| test_project_command_keeps_tool_selector_and_relative_resource | pytest + test original conserva herramienta/-k/ruta relativa y elimina únicamente el prefijo del checkout |
| test_reviewed_new_file_is_project_but_ccr_file_is_not | Archivo nuevo del cambio fijado es elegible; mismo path añadido por CCR después no lo es, aunque esté dentro de tests/ |
| test_ccr_overwrite_is_not_original_execution | Hash de recurso usado distinto del input no acredita ejecución del original; explicación sin invocación falsa |
| test_project_task_is_bound_to_original_manifest | npm test/make check se muestran cuando definición original y ejecución están acreditadas; rechazar esa atribución si CCR alteró el manifiesto o el wrapper es opaco |
| test_generated_entrypoint_is_explained | Script/reproducción CCR no aparece por nombre/ruta/comando; explicación concreta del caso y resultado con ID real |
| test_mixed_check_preserves_only_accredited_project_details | Entry point del proyecto con fixture privado marca el argumento omitido; entry point CCR omite comando y puede listar sólo recursos originales realmente validados |
| test_unknown_or_opaque_command_falls_back_to_explanation | Sin argv/procedencia verificables o con shell anidado opaco, no se reconstruye un comando |
| test_sensitive_values_are_redacted_in_all_fields | Tokens, password/URL sensible, home/host/workspace/archive no salen en comando, evidencia, prosa, contexto ni referencias |
| test_paths_quotes_and_aliases_do_not_escape_projection | Windows/POSIX, espacios/comillas, symlink/traversal, rutas externas, Markdown y colisiones de sustitución no publican datos privados ni inventan destinos |
| test_forged_project_origin_and_hashes_are_rejected | Label origin=project/path/hash sin prueba seleccionada no acredita pertenencia; revisión/snapshot/comando/bytes cambiados invalidan la proyección |
| test_one_projection_for_comment_full_brief_handoff_json | Misma vista de comando/recursos y explicación en todas las salidas; el antiguo blanket sanitizer no la elimina otra vez |
| test_draft3_is_bound_to_disclosure | Prepare/verify exige sidecar/fuentes/digests y cuerpo exacto; modificarlos falla sin enviar ni ejecutar checks |
| test_delivery_receipt2_preserves_source | Política project-resources-v1 y digests correctos; fuente canónica inmutable, sin evidencia privada exportada |
| test_legacy_drafts_and_deliveries_keep_their_policy | Draft 2 verifica con su política y draft 1 conserva stale_draft; no reinterpretar cuerpos ni migrar archivos; sin evidencia histórica no se inventa origen |

Usar datos sintéticos con comandos/rutas distintos para que no puedan pasar sólo por reemplazar todo con un marcador. Los asserts positivos comprueban el comando **y** los recursos que deben quedar visibles; los negativos comprueban la ausencia de valores sensibles. Extender aquí los casos nuevos de Task 2 para esperar draft 3/receipt de delivery 2 con sidecar válido; no dejar tests 12 contradictorios que sigan esperando draft 2 sin clasificación nueva.

- [x] **Step 2: Confirmar el rojo**

Run: `python -B -m unittest test_review_check_disclosure test_review_disclosure_integration`.
Expected: funciones inexistentes o comportamiento actual que omite por completo comandos acreditados; no aceptar un rojo originado sólo por un fixture de propósito/dimensiones inválido.

- [x] **Step 3: Capturar y validar procedencia acotada**

Capturar sólo los recursos/argv del check y ligarlos a los inputs previos a CCR y a los bytes usados al ejecutar. Usar los seams de captura actuales y evidencia seleccionada, sin un barrido adicional del repositorio. Construir el sidecar schema 1 y registrar su selección/hash antes de cleanup; posteriormente validar mediante fuentes retenidas.

El constructor no convierte «está dentro del repo» o «ahora está tracked» en prueba. Las comprobaciones con metadata insuficiente producen modo explanation con explicación fiel, sin degradar el veredicto del producto. Un sidecar seleccionado incoherente mantiene el error de integridad y debe corregirse antes de generar la salida.

- [x] **Step 4: Implementar una proyección tipada común**

Sustituir el descarte indiscriminado sólo en la ruta nueva y acreditada: public_checks/render/public_projection y _PortableProjection consumen la vista común por ID real. No insertar cadenas brutas después de sanitizar ni volver a deduplicar evidencia ya agrupada. Eliminar prefijos locales/valores sensibles, conservar recursos/flags acreditados y escape Markdown. Un comando parcialmente saneado se etiqueta como representación saneada, no invocación exacta garantizada para otro entorno.

Conservar campos estructurales/relaciones, forma de final 12 y separación Propósito/Resultado; añadir **Comando saneado**, **Recursos del proyecto** y/o **Explicación del check** según modo. En JSON portable, command lleva la vista saneada o el marcador de explicación requerido por el contrato, nunca null ni el raw privado.

Draft 3 añade check_disclosure_context a los campos de draft 2 y liga su sidecar/digest; receipt de delivery 2 añade projection_policy/check_disclosure_sha256/model_usage_sha256. Este último empieza en null hasta Task 7. Receipt de comandos sigue en 2 y model ledger en 1. El modo nuevo se aplica a finales 12 y, para históricos, sólo a una nueva proyección explícita con evidencia suficiente; no se modifican sus originales.

- [x] **Step 5: Verificar verde y regresión**

Run: `python -B -m unittest test_review_check_disclosure test_review_disclosure_integration test_review_topology_integration test_review_traceability_comments test_review_traceability_delivery test_review_publication_policy test_review_comment test_review_delivery test_script_reporting_boundaries test_script_dependencies`.
Expected: PASS, incluidos positivos visibles y negativos de privacidad/bindings. No publicar comentarios ni crear entregas reales del usuario para probarlo.

- [x] **Step 6: Commit futuro**

Mensaje: `feat(reportes): mostrar comandos acreditados con ocultacion selectiva`. Staging sólo de propietarios y tests de esta task.

---

### Task 7: Captura, retención y presentación de modelos por participante

**Files:**
- Create: `tests/test_review_model_capture.py`.
- Modify: `scripts/ccr/workflow/builders.py`, `setup.py`; `scripts/ccr/cli/setup.py`; `scripts/ccr/reporting/render.py`, `delivery.py`; integración de `scripts/ccr/execution/runner.py` y `scripts/ccr/archive/retention.py` cuando reciban metadata ya suministrada.
- Preserve: forma/límites de `scripts/ccr/contracts/model_usage.py` y comportamiento de `tests/test_review_model_usage.py`; extender sólo si un requisito no queda cubierto por el contrato existente.

**Interfaces:**
- Consumir `build_model_usage_update(context, ledger, metadata, *, actor, phase, activity, review_id, harness_id, assignment_id=None, check_id=None) -> tuple[dict, dict | None]`, ya existente, y model-usage schema 1.
- Exponer subcomando `scripts setup model-usage` con el sobre vigente `{session, arguments}`: arguments contiene context, ledger (objeto o null), metadata, actor, phase, activity, review_id, harness_id, assignment_id y check_id (null cuando no apliquen). El resultado es el candidato `{context, ledger}` escrito dentro de la sesión propia, sin mutar archive/contexto del producto automáticamente.
- En reporting/render.py, `model_summary(context, ledger) -> dict` produce hechos ya validados por participante/fase, modelo configurado/observado, estado y fuente/diagnóstico. El renderer privado y delivery reciben keyword `model_usage_context` con el ledger/contexto validado y su digest; no realizan consultas al proveedor.
- El recorrido del coordinador invoca la captura al preparar coordinación y al observar dispatch/resultado/cambio de modelo. No crear otra identidad de reviewer para un dispatcher de proceso ni una fila de agente ficticio por una asignación nunca despachada; la ausencia de ejecución queda en la traza/diagnóstico correspondiente.

- [x] **Step 1: Escribir pruebas del recorrido completo**

| Prueba nueva | Resultado exigido |
|---|---|
| test_setup_model_usage_records_supplied_coordinator_and_assignments | Metadata suministrada del coordinador y D1/D2/V1 produce filas ligadas a actor/assignment reales y sidecar/contexto seleccionado |
| test_configured_is_not_observed_and_default_name_is_unknown | Argumento model explícito produce configured_only; harness/provider/default heredado sin ID no se convierten en observed_model |
| test_observed_requires_source_and_preserves_changes | Plataforma/adaptador y referencia válidos acreditan observed; cambios/conflictos conservan filas previas, no las sobrescriben |
| test_missing_metadata_is_visible_without_probes | Por participante conocido, modelos null/unknown y diagnóstico; ledger sólo de coordinación no oculta reviewers sin captura; mocks fallan si hay API/history/counter/config probe o nuevo dispatch |
| test_dispatch_process_is_not_a_model_actor | Proceso/tool N/A si se registra; no hereda modelo. Reviewer despachado sí conserva su observación; asignación no ejecutada no inventa actor |
| test_capture_limits_do_not_become_product_findings | 256 entradas/256 KiB y diagnósticos acotados, sin cambiar veredicto ni seleccionar modelo; sidecar seleccionado corrupto conserva rechazo de integridad |
| test_models_survive_retention_and_cleanup | Captura → selección/hashes → retención → cleanup → render desde bytes retenidos; no requiere sesión/worktree vivo |
| test_private_report_and_local_delivery_show_models | Informe/full/brief muestran configured/observed/unknown y procedencia saneada; receipt de delivery 2 liga model_usage_sha256; no exporta ledger crudo |
| test_public_comment_and_handoff_do_not_leak_models | Comentario/handoff público no muestran modelos, fuentes privadas ni identidades de workers por defecto |
| test_historical_model_absence_is_not_backfilled | Archives/validaciones anteriores permanecen byte a byte intactos; una ausencia histórica se muestra como no registrada, sin fabricar filas |

Usar modelos ficticios etiquetados únicamente como fixtures. Un string genérico «heredado» no acredita un ID real. Los asserts distinguen captura inexistente de modelo no expuesto y de ledger capturado que el renderer omitía.

- [x] **Step 2: Confirmar el rojo**

Run: `python -B -m unittest test_review_model_capture`.
Expected: falta de integración/operación/vista, aun cuando los tests del helper pasivo existente ya pasen.

- [x] **Step 3: Integrar captura sin mediciones**

Reutilizar el builder y sus diagnostics; no añadir campos al final ni al ledger 1. Conservar context.model_usage_reference y el sidecar seleccionado/hash, fuera de review_inputs.sources. Registrar metadata disponible en los puntos observados, o unknown cuando el participante existe pero su modelo no fue expuesto. Un modelo solicitado por runner/dispatch es configuración; observado requiere su fuente explícita.

La ausencia/metadata sobredimensionada no bloquea el análisis del producto y queda visible. Un sidecar seleccionado ilegible, manipulado o de otro review/harness conserva su gate actual. Capturar no cambia modelos, presupuestos, límites ni topología; no repetir reviewers para completar metadata.

- [x] **Step 4: Presentar datos privados y vincular entregas**

Usar model_summary en informe privado y local full/brief: campos claros por participante/fase, ambos modelos cuando existan, estado y fuente/ausencia. El resumen de delivery elimina rutas privadas y liga el digest del ledger, sin copiarlo íntegro; no altera la forma del review.json portable. Comentario público y handoff público siguen excluidos. Si sólo hay un record histórico sin sidecar, indicar «modelo no registrado», sin inventar participantes ni modelos.

- [x] **Step 5: Verificar verde y regresión**

Run: `python -B -m unittest test_review_model_capture test_review_model_usage test_review_archive8 test_review_setup test_review_disclosure_integration test_review_topology_integration test_review_traceability_comments test_script_cli test_script_dependencies`.
Expected: PASS; cubrir con datos sintéticos el ciclo real de captura hasta las vistas y los negativos de integridad, sin telemetría ni llamadas de modelo pagadas.

- [x] **Step 6: Commit futuro**

Mensaje: `feat(trazabilidad): registrar y mostrar modelos por participante`. Staging sólo de propietarios y tests de esta task.

---

### Task 8: Contratos e instrucciones operativas

**Files:** `SKILL.md`; `references/workflow/profiles.md`, `reading-strategy.md`; `references/contracts/result-contract.md`; `references/execution/reviewers.md`, `worker-packets.md`; `references/archive/artifacts.md`; `references/reporting/report-format.md`, `delivery.md`, `publication.md`, `handoff.md`; `docs/examples/archive8-lifecycle.md` y un ejemplo mantenido nuevo `docs/examples/check-disclosure-and-models.md`. No modificar validaciones/evidencias históricas.

**Interfaces:** consumir Tasks 1–7 y la forma publicada de 11; producir instrucciones coherentes para finales nuevos 12, exposición de checks y captura privada de modelos, sin reescribir historia.

- [x] **Step 1: Actualizar perfiles y contrato**

Describir deep 2, extended 3–5 y uno/dos finales; conservar standard condicional, escalación autorizada y excepción de gates de proyecto. Incorporar separación histórica/final, agregado de todas las activas y despacho original. Declarar 12 con forma de 11; congelar 1–11. Preservar propósito, catálogo de dimensiones, prioridades justificadas en impact y admisión/reutilización añadidos por main.

- [x] **Step 2: Actualizar creación, retención y presentación**

Nuevos finales schema 12 en SKILL, workers y guía; retención `python <skill>/scripts artifacts retain ... --expected-schema 12`. Archive 8 acepta 10/11/12 con sus reglas propias. Mantener recibos de comandos 2, introducir draft 3 y receipt de delivery 2 con sus digests, y preservar versiones históricas. Explicar clasificación pública de propósito/flows, comandos y origen de recursos; describir modelos configurado/observado/unknown en vistas privadas y su exclusión pública. Sustituir expresamente la instrucción pasiva/opcional de captura en artifacts.md/worker-packets.md por el recorrido de Task 7: registrar metadata o ausencia por participante observado, con límites y diagnóstico no bloqueante. No declarar que 12 tiene forma de 10 ni publicar internals en comentarios.

- [x] **Step 3: Añadir ejemplos completos y comprobar coherencia normativa**

Los ejemplos mantenidos deben mostrar un test original con comando saneado y una reproducción CCR explicada; incluir captura de coordinación/reviewers, caso unknown, selección/retención de sidecars y vistas resultantes. Usar metadata sintética etiquetada, nunca modelos atribuidos retrospectivamente a corridas reales. Vincular cada ejemplo a pruebas de Tasks 6/7.

Run: `rg -n 'schema.?11|schema.?12|expected-schema|four or five|two to five|a third only|one grouped verification batch' SKILL.md references/`.
Expected: revisar cada coincidencia; 11 queda como contrato publicado compatible, las instrucciones nuevas usan 12, los conteos aplican a finales y las excepciones por perfil son correctas. Los comandos activos no usan fachadas retiradas.

- [x] **Step 4: Verificar referencias y políticas preservadas**

Run: `python -B -m unittest test_reference_layout test_review_references test_review_reference_index test_review_priority_policy test_review_reuse_flow test_review_traceability_policy`.
Expected: PASS. Sin nuevas mediciones, rondas de revisión ni cambios a prioridad/reutilización.

- [x] **Step 5: Commit futuro**

Mensaje: `docs(contratos): describir topologia y adopcion de final 12`, sólo los documentos operativos de esta task.

---

### Task 9: Documentación de usuario y comprobación final

**Files:** `README.md`, `docs/usage.md`, `CHANGELOG.md`, `SKILL.md`.

**Interfaces:** versión propuesta de skill 3.5.0, a confirmar con main antes de publicar; esta task no autoriza publicación ni merge remoto.

- [x] **Step 1: Actualizar uso y changelog**

Tablas con conteos finales; explicar conservación de historia, schema 12 y compatibilidad congelada de 11 con propósito/dimensiones. Documentar entrada modular vigente. Changelog añade una sección nueva, sin modificar 3.4.0 ni sus evidencias; incluir exposición selectiva y modelos además de topología, y fechar la publicación real. La versión propuesta 3.5.0 sustituye la antigua propuesta 2.15.0.

- [x] **Step 2: Verificar todas las superficies actuales**

Run: `python -B -m unittest test_review_profile_topology test_review_topology_integration test_script_layout test_script_dependencies test_script_contract_boundaries test_script_pure_validation test_script_cli test_review_priority_policy test_review_priority_roundtrip test_review_reuse_context test_review_reuse_flow test_review_check_disclosure test_review_disclosure_integration test_review_model_capture`.
Expected: PASS; imports no recrean fachadas ni ciclos. Revisar inventario final de guards 11/12, ejemplos CLI y expected_schema; no confundir final con archive/receipt/draft.

- [x] **Step 3: Ejecutar suite completa una vez**

Run: `python -B -m unittest discover -s .`.
Expected: PASS; registrar número real, duración, skips y limitaciones observados. La validación no afirma soporte de un viewer externo sin probarlo.

- [x] **Step 4: Revisar diff y commit futuro**

Run desde raíz: `git diff --check`.
Expected: sin errores. Mensaje: `chore(release): preparar la version 3.5.0`, sujeto a verificar versión disponible; no crear release, tag ni push sin autorización.

## Matriz de trazabilidad y cierre documental

| Requisito del spec | Task / comprobación ejecutada |
|---|---|
| §1/§7: colisión de 11, forma de 12 y módulo vigente | 1/2; purpose/dimensiones obligatorios y consumidores actuales |
| §3/§4: decisiones y cardinalidad de descubrimiento | 3; fronteras explicit/automatic y congelación 10/11 |
| §5: partición, identidad y despacho original | 5; dos lotes, anotaciones tardías, providers y primer start |
| §6.1: historia conservada | 5; deep, escalación, historia ausente/impedida y mínimo final |
| §6.2: cantidad final y orden incluso degraded | 5; tests de fuentes con mensajes numéricos coincidentes |
| §6.3: agregado único | 4 sin traza; 5 con fuentes y negativos de impedimentos |
| §7: retención, preflight, packets y presentación heredada | 2; roundtrip completo 12 sin relajar 11 |
| §10: comandos/recursos originales y formatos de proyección | 6; procedencia, negativos, comentario/full/brief/handoff y JSON |
| §11: captura, retención y presentación privada de modelos | 7; coordinación/assignments, unknown, configured_only, observed y cleanup |
| §12: aceptación conjunta de la ampliación | 6/7/9; sidecars, fuentes y digests independientes |
| §7/§8: instrucciones, ejemplos y versión propuestas | 8/9; CLI modular y expected-schema 12 |
| §9: preservar límites/políticas/consumidores | 9; suite real, sin migración ni soporte externo supuesto |

Los seis hallazgos de la revisión anterior siguen cubiertos: historia (Task 5), orden degraded (5), adopción operativa (2/8), fixture de fallback (4/5), ubicación de validadores y orden de tareas (1/4/5) y regresión histórica (3/5). La adaptación añade colisión de esquema, modularización, despacho original y trazabilidad actual. La ampliación del 2026-10-28 añade Tasks 6/7 y spec §10–§12; no sustituye esos controles.

Las nueve tareas están completadas con revisiones independientes, correcciones verificadas y la repetición completa de las 1048 pruebas descubiertas. La ejecución secuencial y la corrección del fixture CLI se documentan sin presentarlas como una suite aprobada; la repetición íntegra posterior terminó sin fallos. Se conserva la rama y el worktree. La versión 3.5.0 está preparada sobre la base indicada; antes de una publicación futura habrá que comprobar si main avanzó, sin renumerar registros históricos. No se realizó publicación remota.
