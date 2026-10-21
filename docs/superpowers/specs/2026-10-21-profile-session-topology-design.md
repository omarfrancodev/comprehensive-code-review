# Topología de sesiones por perfil en CCR

Estado: diseño aprobado por el usuario el 2026-10-21 (decisiones 1–6 resueltas en la conversación previa; agregación, convención de partición y versión de esquema confirmadas tras el builder check).

Base de trabajo: `main`, commit `fd38df8` (CCR 2.14.0). Worktree: `.worktrees/profile-session-topology`; rama: `docs/profile-session-topology`.

## 1. Objetivo

Hacer explícita la topología de sesiones de cada perfil de revisión y eliminar la ambigüedad actual entre "más descubrimiento" y "más verificación". Hoy la topología está implícita y repartida entre la tabla de `SKILL.md`, la prosa de `profiles.md`, la fórmula condensada de `result-contract.md` y dos tablas de cardinalidad en los validadores. Esta revisión la convierte en un contrato único, verificable y con una regla de partición que impide que "más verificadores" se degrade en un segundo barrido completo del alcance.

## 2. Comportamiento actual verificado

La topología efectiva hoy, con la evidencia que la fija:

| Perfil | Descubrimiento | Verificación | Evidencia |
|---|---|---|---|
| focused | 1, `independent: false` | 1, `independent: false`, **mismo `reviewer_context` que el discovery** | `scripts/review_execution.py:136`, `scripts/review_execution.py:150` |
| standard | 1 | 0 o 1; `independent: true` sólo si hay candidato de código sustantivo o límite material | `scripts/review_execution.py:120` |
| deep | **2–3** `independent: true` | 1 `independent: true` | `scripts/review_execution.py:107`, `scripts/review_profiles.py:396` |
| extended | auto **4–5** / explícito **2–5** `independent: true` | **exactamente 1** `independent: true` | `scripts/review_execution.py:107`, `scripts/review_profiles.py:396`, `scripts/review_execution.py:401` |

Dos reglas actuales que hoy limitan la topología propuesta:

- `scripts/review_execution.py:401` exige `len(final_candidates) == 1` cuando el estado es `fulfilled`. Dos verificadores que terminen después del último discovery invalidan el run.
- `references/workflow/profiles.md:48` establece "Use one grouped verification batch… No automatic second whole-scope audit", y `references/execution/reviewers.md:46` lo reitera ("this is bounded verification, not another full discovery sweep").

La semántica de `independent` no cambia: un contexto de reviewer realmente separado con inputs neutrales. El `context_id` compartido del brief es válido; la identidad de reviewer no ([references/execution/reviewers.md:5](references/execution/reviewers.md)). Reutilizar `reviewer_context` entre asignaciones independientes anula la independencia, y lo mismo ocurre con `provider_id` cuando no es nulo (`scripts/review_execution.py:171-179`). Un par de lotes necesita por tanto contextos de reviewer distintos, y `provider_id` distintos cuando ambos lo exponen.

## 3. Decisiones del usuario

| # | Decisión |
|---|---|
| 1 | Techo de descubrimiento de extended: **se mantiene en 5** |
| 2 | Piso de extended: **3**, también para la selección explícita |
| 3 | Partición de los dos verificadores de extended: **candidatos** frente a **invariantes asignadas** |
| 4 | Orden de los dos lotes: se deriva de la decisión 3 (ver §6) |
| 5 | El hueco que deja eliminar el tercer descubridor de deep: **escalar a extended** |
| 6 | `coverage.verification` **sigue siendo escalar**; ambos lotes son `independent` |
| 7 | Agregación de `coverage.verification` con dos lotes: **precedencia de tres niveles** (ver §7.3) |
| 8 | Partición verificable por **convención de nombres** en el `id` de la asignación, sin cambiar el contrato (ver §6.1) |
| 9 | Las reglas nuevas viven en un **esquema nuevo, schema 11**; schema 10 queda congelado con sus reglas actuales (ver §7.4) |

## 4. Topología objetivo

Para `schema_version == 11`:

| Perfil | Descubrimiento | Verificación | Cambio respecto al actual |
|---|---|---|---|
| focused | 1, `independent: false`, en la misma sesión que la verificación | 1, `independent: false`, mismo `reviewer_context` | **ninguno** |
| standard | 1, sesión propia | 1 en sesión propia; `independent: true` si hay sustancia material, si no puede ser el coordinador | **ninguno** |
| deep | **exactamente 2** `independent: true` | 1 `independent: true` | se elimina el tercer descubridor |
| extended | **3 a 5** `independent: true` (auto y explícito) | **1 o 2** `independent: true` | piso 3, hasta 2 verificadores |

La progresión de descubrimiento pasa a ser **1 → 1 → 2 → 3+** perspectivas independientes, y la diferenciación entre `deep` y `extended` queda en la cardinalidad con una justificación uniforme: por qué N asignaciones independientes y no N−1.

## 5. Reparto de responsabilidades de `deep` con 2 descubridores

Al eliminar el tercer descubridor se pierde la vía in-profile para cubrir "una necesidad de cobertura distinta". La decisión 5 del usuario es escalar a `extended`, y esa ruta ya existe: el mecanismo de escalamiento automático de `profiles.md:13` permite `deep → extended` cuando hechos nuevos invalidan la base del perfil.

Reglas:

- Un `deep` explícito **no** escala en silencio. Si aparece una necesidad de cobertura distinta, el coordinador la declara, solicita el cambio de perfil al usuario o reporta el hueco material. Esta regla ya existe en `profiles.md:11` ("request a profile change or report the material gap") y se mantiene sin cambios de contrato.
- Un `deep` automático escala a `extended` y **reutiliza** el descubrimiento independiente ya válido, tal como establece `profiles.md:13` ("Count valid existing independent discovery toward the new plan"). La escalación no autoriza un segundo equipo completo.
- El salto `deep` (2) → `extended` (3) es coherente con la cardinalidad: la necesidad que no cabe en 2 descubridores justifica 3.

## 6. Partición y orden de la verificación de `extended`

### 6.1 Partición y su convención verificable

Cuando `extended` planifica dos lotes de verificación, la partición es **candidatos** frente a **invariantes asignadas**:

- **Lote de candidatos**: los candidatos de código sustantivos y las preguntas materiales agrupadas por causa raíz compartida, tal como se agrupan hoy.
- **Lote de invariantes**: las invariantes nombradas en los briefs de descubrimiento, incluidas las que no tienen candidatos.

La partición es la condición que distingue un segundo lote de un segundo barrido completo del alcance. Un lote cuyo alcance no sea uno de estos dos no es admisible, porque violaría la prohibición de `profiles.md:48`.

**Convención verificable (decisión 8).** La fila del plan no tiene campo de alcance (`scripts/review_execution.py:31` y `:43-44` limitan los campos a `id`, `role`, `independent`, `required`, `reference` más `selection_id` y `superseded_by` en schema 10, y schema 11 conserva la misma forma), y §10 prohíbe cambiar el contrato de `coverage.execution`. La partición se expresa entonces por una **convención de nombres en el `id` de la asignación**:

| `id` | Alcance del lote |
|---|---|
| `V-candidatos` | Candidatos de código sustantivos y preguntas materiales agrupadas |
| `V-invariantes` | Invariantes asignadas en los briefs, incluidas las que no tienen candidatos |

La convención es la regla de admisión que un test puede afirmar sobre los briefs y el plan. El validador no puede leer el contenido de un brief, así que la garantía de que el lote cubre de verdad ese alcance es de contrato y revisión; la convención hace que la desviación sea visible y no ambigua.

### 6.2 Orden (derivado de la decisión 3)

Ambos lotes se ejecutan **después de que termina todo el descubrimiento**, y pueden correr en paralelo entre sí.

Razón: los dos lotes necesitan el conjunto completo de evidencia del descubrimiento para poder decidir, y la regla vigente de orden (`scripts/review_execution.py:397-400`) exige `sequence > last_discovery` **tanto para el arranque como para la finalización** del verificador final. `last_discovery` es el máximo de las secuencias de finalización de **todas** las asignaciones de descubrimiento activas (`scripts/review_execution.py:344-364`).

Un lote que arrancara entre olas de descubrimiento no calificaría como lote final y dejaría el run en `degraded`. Por eso el orden es único y `last_discovery` sigue siendo la única referencia temporal; no se introduce un segundo eje.

### 6.3 Un lote o dos

`extended` puede planear un solo lote de verificación cuando la partición no lo justifique: por ejemplo, cuando no hay invariantes asignadas y todos los candidatos caben en un lote, o cuando las invariantes asignadas son las únicas decisiones pendientes. La regla de admisión es la partición, no la cardinalidad: un segundo lote requiere un alcance de invariantes asignadas no absorbible por el lote de candidatos, o un lote de candidatos cuyo volumen justifique separación.

`deep` conserva exactamente un lote agrupado, que cubre candidatos e invariantes asignadas a la vez, como hoy.

## 7. Contrato de resultado

### 7.1 Cardinalidad de descubrimiento

Para `schema_version == 11`:

| Perfil | Mínimo | Máximo |
|---|---|---|
| focused | 1 | 1 |
| standard | 1 | 1 |
| deep | 2 | 2 |
| extended | 3 | 5 |

El mínimo de `extended` es 3 tanto para la selección automática como para la explícita (decisión 2). El máximo de 5 se mantiene (decisión 1).

Consecuencia: con el mismo piso para auto y explícito, la distinción `automatic`/`explicit` deja de producir tablas de cardinalidad distintas **en schema 11**. Las ramas que la producían (`scripts/review_execution.py:99-106` y `scripts/review_profiles.py:388-397`) siguen siendo necesarias para schema 10 y anteriores, y quedan congeladas con ellas.

### 7.2 Cardinalidad de verificación

Para `schema_version == 11`:

| Perfil | Mínimo | Máximo | `independent` |
|---|---|---|---|
| focused | 1 | 1 | `false`; mismo `reviewer_context` que el descubrimiento |
| standard | 0 | 1 | `true` cuando hay sustancia material |
| deep | 1 | 1 | `true` |
| extended | 1 | 2 | `true` en ambos lotes |

**Regla de forma de plan (decisión derivada de §6.2).** En `extended`, el número de candidatos finales debe ser **igual** al número de filas de verificación activas requeridas. Si el plan declara dos lotes, los dos deben calificar como lotes finales; un lote que arranque antes de `last_discovery` es un error de forma de plan, no un lote tolerado que simplemente no cuenta. Una tercera fila de verificación activa es un error de forma de plan en todos los perfiles. En `deep`, `standard` y `focused` el número de candidatos finales sigue siendo exactamente 1.

### 7.3 `coverage.verification` permanece escalar con precedencia de tres niveles

`coverage.verification` conserva su enum actual (`independent` / `same_session` / `skipped` / `unavailable`, `scripts/review_contract.py:32-33`) porque los dos lotes de `extended` son siempre `independent` (decisión 6). El escalar describe el estado agregado de la verificación ordinary completada, no la cantidad de lotes.

**Regla de agregación (decisión 7).** Se agrega sobre **todas las filas de verificación activas**, en los dos validadores:

1. `independent` — todas las filas de verificación requeridas completaron con independencia observada.
2. `same_session` — alguna fila requerida se ejecutó en la misma sesión (fallback del coordinador).
3. `unavailable` — falta alguna fila requerida.

Esta regla reemplaza las dos computaciones divergentes actuales: `scripts/review_execution.py:187-192` (schema 10, sin traza) deriva el escalar sólo de `verification[-1]`, y `scripts/review_execution.py:407` (con traza) sólo de `final_candidates[0]`. Ambas deben usar el mismo conjunto agregado; de lo contrario, un par medio degradado sería rechazado por los dos validadores a la vez (`final_candidates` excluye las filas no independientes o sin resultado en `scripts/review_execution.py:366-378`, mientras que `verification[-1]` sí las cuenta).

La precedencia de tres niveles se distingue de la agregación binaria de la rama legacy (`scripts/review_execution.py:193-197`, que devuelve `same_session` ante cualquier ausencia). Esa rama y la de schema 10 quedan congeladas con sus esquemas.

### 7.4 Versiones de esquema y compatibilidad

El cambio de reglas afecta a la versión de esquema vigente, no a las congeladas. `references/contracts/result-contract.md:9` congela explícitamente las versiones 1–9, y los validadores `scripts/review_execution.py` y `scripts/review_profiles.py` no han cambiado desde que se introdujo schema 10 (último commit que los toca: `8bf539d`). La consecuencia es que schema 10 no puede reutilizarse para reglas nuevas sin invalidar los registros schema 10 ya retenidos.

Decisión 9: las reglas nuevas viven en **schema 11**. Schema 11 tiene **la misma forma de campos que schema 10** —misma envoltura, mismo `coverage.execution`, misma `profile_history`, misma fila de plan— y cambia únicamente las reglas de cardinalidad de descubrimiento, cardinalidad de verificación y agregación de `coverage.verification`. Siguiendo el patrón del repo (5 introduce extended, 7 adopta los nombres focused/standard, 8 añade execution, 9 añade procedencia, 10 añade la historia de perfil), cada cambio de contrato es una versión nueva.

| Esquema | Reglas de topología | Estado |
|---|---|---|
| 1–9 | las vigentes al publicarse | congelado |
| 10 | las de CCR 2.14.0 (deep 2–3, extended auto 4–5 / explícito 2–5, un verificador final) | congelado, pasa a legacy |
| 11 | las de §7.1–§7.3 | nuevo |

Reglas de implementación:

- `scripts/review_contract.py:148` acepta 11 como versión soportada; 12 y superiores siguen siendo un error de versión.
- Los condicionales que hoy son `schema_version == 10` pasan a `schema_version in (10, 11)` **cuando no dependen de la topología** (forma de la fila de plan, `profile_history`, validación de check, proyección de informe). Donde sí dependen de la topología (tabla de límites, mínimo de obligaciones, agregación del escalar, regla del verificador final) la condición discrimina schema 11 del resto.
- `scripts/review_profiles.py:261` sigue devolviendo `[]` para `schema_version` distinto de 10 y 11, de modo que sus mínimos no admiten esquemas legacy.
- Los fixtures `record8` de `tests/test_review_execution_policy.py:12` y `record10` de `tests/recovery_fixtures.py:34` quedan **intactos** como fixtures congelados. `record10` deriva de `record8`, así que cualquier cambio en `record8` se propagaría a todos los fixtures schema 10; el plan usa fixtures schema 11 nuevos.
- Los `docs/validation/*.md` son registros históricos de corridas; no se reescriben. El cambio se documenta en `CHANGELOG.md`.

## 8. Archivos afectados

### 8.1 Alta de schema 11

| Archivo | Cambio |
|---|---|
| `scripts/review_contract.py:148` | La versión soportada pasa a `{1, …, 11}`; 12 y superiores siguen siendo un error |
| `scripts/review_contract.py:145` | `in (6, 7, 8, 9, 10)` → `in (6, 7, 8, 9, 10, 11)` (campos de review final) |
| `scripts/review_contract.py:299` | `in (8, 9, 10)` → `in (8, 9, 10, 11)` (`coverage.execution` presente) |
| `scripts/review_contract.py:300` | `in (2, 3, 4, 5, 6, 7, 8, 9, 10)` → añade 11 (`coverage.areas` presente) |
| `scripts/review_contract.py:309`, `scripts/review_contract.py:313` | `in (8, 9, 10)` → `in (8, 9, 10, 11)` (limitaciones tipadas) |
| `scripts/review_contract.py:325` | `in (8, 9, 10)` → `in (8, 9, 10, 11)` (ejecuta `validate_execution`) |
| `scripts/review_contract.py:327` | `in (9, 10)` → `in (9, 10, 11)` (procedencia de checks) |
| `scripts/review_contract.py:329` | `== 10` → `in (10, 11)` (historia de perfil) |
| `scripts/review_contract.py:747`, `scripts/review_contract.py:761` | `== 10` / `in (8, 9, 10)` → incluyen 11 (proyección de informe) |
| `scripts/review_execution.py:31-72` | Los condicionales de forma de plan (`selection_id`, `superseded_by`, `required: false`) pasan a `in (10, 11)` |
| `scripts/review_execution.py:81`, `:214`, `:221`, `:232`, `:259`, `:266`, `:271`, `:273`, `:278`, `:287`, `:294`, `:301`, `:327` | El flag `schema10` pasa a cubrir 10 y 11; se renombra para reflejar que cubre ambos esquemas de perfil |
| `scripts/review_profiles.py:261` | `!= 10` → `not in (10, 11)` |
| `scripts/review_artifacts.py:3687`, `:3920`, `:3922` | `in (8, 9, 10)` → `in (8, 9, 10, 11)` (proyección de resultado retenido) |
| `scripts/review_delivery.py:241` | `in (8, 9, 10)` → `in (8, 9, 10, 11)` (entrega) |
| `scripts/review_publication.py:122` | `in (8, 9, 10)` → `in (8, 9, 10, 11)` (publicación) |

### 8.2 Reglas de topología

| Archivo | Cambio |
|---|---|
| `scripts/review_execution.py:107-108` | Tabla de límites bifurcada: schema 11 usa deep `(2, 2)` y extended `(3, 5)`; schema 10 y anteriores conservan deep `(2, 3)` y extended auto `(4, 5)` / explícito `(2, 5)` |
| `scripts/review_execution.py:99-106` | La rama que fuerza `profile_source = 'automatic'` queda congelada con schema 10; en schema 11 la cardinalidad ya no distingue auto de explícito |
| `scripts/review_execution.py:187-192` | En schema 11, la derivación de `effective` pasa a agregar sobre **todas** las filas de verificación activas con la precedencia de tres niveles de §7.3; schema 10 conserva su derivación por última fila |
| `scripts/review_execution.py:401` | En schema 11 y `extended`, se aceptan 1 o 2 lotes finales y el número de candidatos finales debe igualar el número de filas de verificación activas; una tercera fila activa es error de forma de plan. Schema 10 y anteriores conservan `len(final_candidates) != 1` |
| `scripts/review_execution.py:407` | En schema 11, el `expected` de `coverage.verification` se agrega sobre **todos** los lotes finales con la precedencia de §7.3 |
| `scripts/review_profiles.py:396` | En schema 11, el mínimo de `extended` es 3 y `deep` sigue en 2; schema 10 conserva extended 4 automático / 2 explícito |
| `scripts/review_profiles.py:388-397` | La rama `acquired_extended_auto` queda congelada con schema 10; en schema 11 el mínimo adquirido y el actual coinciden en 3 |
| `scripts/review_contract.py:374` | El enum de `coverage.verification` no cambia; se documenta la regla de agregación de §7.3 |

### 8.3 Documentación

| Archivo | Cambio |
|---|---|
| `SKILL.md:5` | Sube `metadata.version` a `2.15.0` |
| `SKILL.md:38-44` | Tabla de perfiles: deep 2, extended 3–5, verificación 1–2. La fila de `extended` (`:43`) debe reflejar el texto de uno o dos lotes, no sólo los conteos de descubrimiento |
| `references/workflow/profiles.md:42` | Se elimina el tercer descubridor de deep y su ruta in-profile |
| `references/workflow/profiles.md:44` | "four or five" → "three or more"; el argumento "three-reviewer plan" pasa a "two-reviewer plan" |
| `references/workflow/profiles.md:46` | Extended explícito arranca en 3, no en 2; el máximo 5 se mantiene. La misma línea dice "plus one fresh grouped verifier" y "the justified four/five assignments": ambos pasan a "one or two" y "three or more" |
| `references/workflow/profiles.md:48` | "one grouped verification batch" → 1 o 2 lotes con partición candidatos/invariantes y la convención de `id` de §6.1; la prohibición de segundo barrido completo se mantiene y se hace verificable |
| `references/workflow/profiles.md:52-58` | Reglas de verificación por perfil (la sección empieza en `:52`; la regla de deep/extended está en `:58`): deep conserva 1 lote; extended admite 2 lotes particionados |
| `references/execution/reviewers.md:46` | Segunda enunciación de la prohibición de segundo barrido completo: debe admitir el segundo lote particionado |
| `references/contracts/result-contract.md:9` | Declara schema 11: misma forma que schema 10, reglas de topología nuevas; schema 10 queda congelado |
| `references/contracts/result-contract.md:82` | Fórmula canónica condensada de los cuatro perfiles, con el piso 3 y los lotes 1–2 |
| `references/workflow/reading-strategy.md:18` | "deep/extended retain distinct flow owners within their justified assignment limits" |
| `docs/usage.md:37-44` | Tabla de perfiles en español y el párrafo de elegibilidad de extended ("cuatro o cinco asignaciones" → "tres o más") |
| `README.md:39-44` | Tabla de perfiles en español; la fila de `extended` (`:44`) incluye "y una verificación independiente agrupada" → "y una o dos verificaciones independientes agrupadas" |
| `CHANGELOG.md` | Nueva sección `## 2.15.0` con los cambios de perfiles y ejecución |

### 8.4 Pruebas

| Archivo | Cambio |
|---|---|
| `tests/test_review_profile_topology.py` (nuevo) | Módulo nuevo con el fixture schema 11 y las pruebas de la topología nueva. Importa de `recovery_fixtures` y `test_review_execution_policy`; ningún módulo lo importa, de modo que no hay ciclo |
| `tests/test_review_profile_topology.py` (nuevo) | Fixture schema 11 con el builder `record11(profile, source, discovery, verification, verification_ids)`, derivado de `record10` de `tests/recovery_fixtures.py` con el plan y los resultados reconstruidos |
| `tests/test_review_profile_topology.py` (nuevo) | Schema 11: `deep` con 3 descubridores es inválido; `extended` con 2 descubridores es inválido (piso 3); `extended` con 3 y con 5 es válido |
| `tests/test_review_profile_topology.py` (nuevo) | Schema 11: `extended` con dos lotes finales es válido cuando ambos arrancan y terminan después de `last_discovery`; un lote que arranca antes invalida el run; una tercera fila de verificación activa es error de forma de plan |
| `tests/test_review_profile_topology.py` (nuevo) | Schema 11: agregación de `coverage.verification` — par completo → `independent`; par medio degradado → `same_session`; lote ausente → `unavailable`. Debe pasar en los dos validadores (`validate_execution` y `validate_execution_sources`) |
| `tests/test_review_profile_topology.py` (nuevo) | Schema 11: la convención de partición usa `V-candidatos` y `V-invariantes`; los dos lotes exigen `reviewer_context` distinto y `provider_id` distinto cuando ambos lo exponen |
| `tests/test_review_profile_topology.py` (nuevo) | Schema 11 válido: un record con `schema_version: 11` pasa `contract.validate`; `schema_version: 12` produce el error `unsupported version` |
| `tests/test_review_execution_policy.py` (nuevo) | Schema 10 congelado: `deep` con 3 descubridores, `extended` explícito con 2 y `extended` automático con 4 siguen siendo válidos; `extended` schema 10 con dos lotes finales sigue siendo inválido |
| `tests/test_review_profiles.py:328` | `test_acquired_automatic_extended_minimum_survives_explicit_selection` sigue probando el piso congelado de schema 10 (4); el piso 3 único de schema 11 se cubre en el módulo nuevo |
| `tests/test_review_execution_policy.py:97` | `test_deep_requires_two_fresh_discoveries_and_grouped_verifier` conserva el conjunto inválido legacy (`'one'`, `'four'`); la mutación `'three'` se añade al fixture schema 11 nuevo, **no** a este fixture schema 8 |
| `tests/test_review_execution_policy.py:115` | `test_extended_counts_follow_selection_source` sigue probando la tabla congelada sin cambios |

Nota de importación: `tests/recovery_fixtures.py:5` importa `record8` desde `test_review_execution_policy`, de modo que un módulo de pruebas nuevo que importe `recovery_fixtures` no crea ciclo siempre que nada importe ese módulo nuevo.

## 9. Riesgos y límites

- **Un segundo lote mal justificado se convierte en un segundo barrido completo.** Mitigación: la partición candidatos/invariantes es la condición de admisión, la convención de `id` la hace visible, y la regla de forma de plan impide lotes que no califiquen como finales. El validador no puede verificar el contenido de un brief, así que la garantía de cobertura real es de contrato y revisión, no puramente mecánica.
- **El piso 3 de `extended` explícito rompe el escalonado progresivo 2→5.** Es una consecuencia directa de la decisión 2 y reduce el coste de una selección explícita mal dimensionada. Se acepta.
- **`coverage.verification` escalar con dos lotes pierde granularidad.** Aceptado por la decisión 6: ambos lotes son independientes, y el escalar expresa el estado agregado con precedencia de tres niveles.
- **La eliminación del tercer descubridor de `deep` reduce la cobertura de una "necesidad distinta" no prevista.** Compensado por la escalación a `extended` (§5). El hueco es visible y declarado, no silencioso.
- **Alta de schema 11 amplía la superficie de código.** Cada condicional `== 10` que no depende de la topología pasa a `in (10, 11)`. El riesgo real es olvidar un sitio y que un record schema 11 se valide con reglas parciales; la prueba de regresión de §8.4 cubre el reconocimiento de schema 11 de extremo a extremo.
- **Los registros históricos de `docs/validation/` no se actualizan.** Describen corridas con los límites vigentes en su momento. El CHANGELOG documenta el cambio de contrato.
- **El `id` de la asignación es texto libre.** La convención de §6.1 no la impone el validador; un plan que no la siga sigue siendo válido pero pierde la señal explícita de partición. Se acepta para no cambiar el contrato de `coverage.execution`.

## 10. Fuera de alcance

- Cambiar la semántica de `independent` o las reglas de reused-context.
- Cambiar el enum de `coverage.verification` o la forma del contrato de `coverage.execution` (en particular, no añadir un campo de alcance a la fila del plan).
- Introducir un segundo eje temporal para los lotes de verificación.
- Migrar o reescribir archivos históricos, archives schema < 8 o resultados schema < 11.
- Cambiar las reglas de elegibilidad, precedencia de veredicto, gates de proyecto o entrega.
- Añadir dependencias de ejecución, servicios o migraciones de base de datos.
