# Profile Session Topology Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** hacer explícita la topología de sesiones de cada perfil de revisión en un esquema nuevo (schema 11), con deep en 2 descubridores, extended en 3–5 y hasta 2 lotes de verificación particionados.

**Architecture:** schema 11 reutiliza la forma de campos de schema 10 y sólo cambia las reglas de cardinalidad y de agregación de `coverage.verification`. Schema 10 y anteriores quedan congelados con sus reglas actuales, de modo que los registros ya retenidos siguen validando. La partición candidatos/invariantes se expresa por una convención de nombres en el `id` de la asignación, sin tocar el contrato de `coverage.execution`.

**Tech Stack:** Python 3.10+, biblioteca estándar, unittest, Git y Markdown.

**Spec:** [Topología de sesiones por perfil](../specs/2026-10-21-profile-session-topology-design.md).

## Global Constraints

- Python 3.10+ y biblioteca estándar; no añadir dependencias de ejecución.
- Mantener archive schema 8/layout 2 nativo, trace schema 1; no migrar ni reescribir archivos históricos.
- Los esquemas de resultado 1–9 y 10 quedan congelados con sus reglas actuales. Schema 11 es la única versión con la topología nueva.
- Schema 11 tiene exactamente la misma forma de campos que schema 10: envoltura, `coverage.execution`, `profile_history` y fila de plan idénticas.
- No cambiar la forma del contrato de `coverage.execution`: la fila de plan conserva `{id, role, independent, required, reference, selection_id, superseded_by}`.
- No cambiar el enum de `coverage.verification` (`independent` / `same_session` / `skipped` / `unavailable`).
- No inferir autoridad, independencia, identidad de actor, éxito de comandos ni disponibilidad de procesos.
- No relajar gates de retención, aislamiento, cleanup, perfil ni requisitos independientes del proyecto: los gates de archive 8 siguen exigiendo un review final moderno con `coverage.execution` y `profile_history` coincidente.
- No reescribir los `docs/validation/*.md`; son registros históricos de corridas.
- Conservar la procedencia interna completa; publicar los bytes del render público verificado sin ediciones posteriores al render.
- No activar medición de tokens, precios o contadores.

## Review Focus

1. Un registro schema 10 con `deep` de 3 descubridores, `extended` explícito de 2 o `extended` automático de 4 debe seguir siendo válido, y un schema 10 con dos lotes finales debe seguir siendo inválido: schema 10 queda congelado; cubre Task 3 y Task 5.
2. Un registro schema 11 con `extended` de 2 descubridores debe ser rechazado (piso 3) tanto en selección explícita como automática: el piso no depende de la fuente de selección; cubre Task 3.
3. Un par de lotes en `extended` donde uno arranca antes del último descubrimiento debe invalidar el run, no contarse como un lote: un lote que no arranca después de todo el descubrimiento no es un lote final; cubre Task 5.
4. Un par a medio degradar (un lote con fallback del coordinador) debe reportar `same_session` y ser aceptado por los dos validadores a la vez: la agregación es la misma regla en `validate_execution` y en `validate_execution_sources`; cubre Task 4.
5. Un schema 11 que omita un sitio de reconocimiento queda validado con reglas parciales: el reconocimiento de schema 11 debe ser completo y verificable con un grep; cubre Task 1 y Task 2.

---

## Base y mapa de archivos

Base: `fd38df8`, `main`/CCR 2.14.0, worktree `.worktrees/profile-session-topology`, rama `docs/profile-session-topology`.

Schema 11 es la versión nueva. La forma de sus registros es la de schema 10; sólo cambian las reglas. Por eso el reconocimiento de schema 11 es un cambio mecánico y amplio, y las reglas de topología viven en un subconjunto acotado de condicionales.

| Task | Crear | Modificar |
|---|---|---|
| 1 | `tests/profile_topology_fixtures.py`, `tests/test_review_profile_topology.py` | `scripts/review_contract.py`, `scripts/review_execution.py`, `scripts/review_profiles.py` |
| 2 | — | `scripts/review_artifacts.py`, `scripts/review_delivery.py`, `scripts/review_publication.py`, `scripts/review_history.py`, `scripts/review_check_provenance.py`, `scripts/review_check_receipts.py`, `scripts/review_preflight.py` |
| 3 | — | `scripts/review_execution.py`, `scripts/review_profiles.py`, `tests/test_review_profile_topology.py` |
| 4 | — | `scripts/review_execution.py`, `tests/test_review_profile_topology.py` |
| 5 | — | `scripts/review_execution.py`, `tests/test_review_profile_topology.py` |
| 6 | — | `SKILL.md`, `references/workflow/profiles.md`, `references/contracts/result-contract.md`, `references/execution/reviewers.md`, `references/workflow/reading-strategy.md` |
| 7 | — | `docs/usage.md`, `README.md`, `CHANGELOG.md`, `SKILL.md` |

Los sitios de reconocimiento de schema 11 se localizan con:

```
rg -n "schema_version'?\]?\)?\s*(==|!=|not in|in)\s*\(?[0-9,\s]*10\)?" scripts/
```

Esa búsqueda debe quedar sin resultados sin que la tupla incluya 11. La forma de cada sitio se decide por su significado: casi todas las tuplas expresan **forma** (qué campos existen) y por tanto comparten la forma de schema 10; las dos excepciones son los gates de archive 8 de `scripts/review_artifacts.py`, que aceptan un conjunto de versiones de resultado y por tanto pasan a `not in (10, 11)`.

Las ubicaciones se identifican por función, no por líneas que cambiarán.

---

### Task 1: Reconocer schema 11 en el contrato de resultado

**Files:**
- Create: `tests/profile_topology_fixtures.py`, `tests/test_review_profile_topology.py`
- Modify: `scripts/review_contract.py` (soporte de versiones y forma), `scripts/review_execution.py` (forma de la fila de plan, flag de esquema de perfil)
- Test: `tests/test_review_profile_topology.py`

**Interfaces:**
- Consumes: `recovery_fixtures.record10(profile, source)`, `recovery_fixtures.selection(profile, source)`, `recovery_fixtures.source_events(record)`, `recovery_fixtures.context10(record)`.
- Produces:
  - `tests/profile_topology_fixtures.record11(profile='deep', source='explicit', discovery=2, verification=1, verification_ids=None) -> dict` — registro final schema 11 con `schema_version` 11, `profile_history` de una selección, plan reconstruido y `coverage.execution.results` coherentes.
  - `tests/profile_topology_fixtures.source_fixture11(record) -> tuple[dict, list[dict], set[str]]` — el mismo contrato de `tests/test_review_execution_policy.py:source_fixture` (contexto, eventos, referencias), usando `recovery_fixtures.source_events` para que los eventos lleven `event_id`.
  - `scripts/review_profiles.PROFILE_SCHEMAS` — tupla `(10, 11)`: esquemas con historia de perfil y bindings de asignación.
  - `scripts/review_profiles.NEW_TOPOLOGY_SCHEMAS` — tupla `(11,)`: esquemas con la topología de perfiles nueva.

- [ ] **Step 1: Escribir el fixture schema 11**

En `tests/profile_topology_fixtures.py`:

```python
"""Shared schema-11 fixtures for the profile session topology work."""
import copy

from recovery_fixtures import context10, record10, selection, source_events


def record11(profile='deep', source='explicit', discovery=2, verification=1,
             verification_ids=None):
    """Build a schema-11 record with the new profile topology cardinalities.

    Schema 11 reuses the schema-10 record shape; only the profile topology
    rules differ. The plan and results are rebuilt so the counts and the
    assignment ids are explicit for each test.
    """
    value = copy.deepcopy(record10(profile, source))
    value['schema_version'] = 11
    execution = value['coverage']['execution']
    initial = selection(profile, source)
    execution['profile_history'] = [initial]
    ids = list(verification_ids) if verification_ids else ['V1'] * verification
    plan = [dict(id='D%d' % index, role='discovery',
                 independent=profile in ('deep', 'extended'), required=True,
                 reference='evidence/briefs.json#D%d' % index)
            for index in range(1, discovery + 1)]
    plan.extend(dict(id=ids[index], role='verification', independent=profile != 'focused',
                     required=True, reference='evidence/briefs.json#%s' % ids[index])
                for index in range(verification))
    for row in plan:
        row['selection_id'] = initial['id']
        row['superseded_by'] = None
    execution['plan'] = plan
    execution['results'] = [
        dict(assignment_id=row['id'],
             reviewer_context=row['id'] if row['independent'] else 'coordinator',
             provider_id='provider-' + row['id'] if row['independent'] else None,
             reference='evidence/results.json#' + row['id'])
        for row in plan]
    value['coverage']['verification'] = 'independent' if profile != 'focused' else 'same_session'
    return value


def source_fixture11(record):
    """Return the context, trace events and retained references for a schema-11 record."""
    execution = record['coverage']['execution']
    context = context10(record)
    references = {context['profile_reference']}
    for row in execution['plan']:
        references.add(row['reference'])
    for result in execution['results']:
        references.add(result['reference'])
    return context, source_events(record), references
```

- [ ] **Step 2: Escribir la prueba que falla**

Crear `tests/test_review_profile_topology.py`:

```python
"""Profile session topology: schema-11 cardinality, aggregation and batches."""
import copy
import unittest

from profile_topology_fixtures import record11, source_fixture11
from test_review_contract import contract


class ProfileTopologyTests(unittest.TestCase):
    def assertValid(self, value):
        self.assertEqual(contract.validate(value), [])

    def assertInvalid(self, value, fragment):
        errors = contract.validate(value)
        self.assertTrue(any(fragment in error for error in errors), errors)

    def test_schema11_is_a_supported_version_with_the_schema10_shape(self):
        value = record11('deep', 'explicit', discovery=2, verification=1)
        self.assertValid(value)
        bad = copy.deepcopy(value)
        bad['schema_version'] = 12
        self.assertInvalid(bad, 'unsupported version')
```

- [ ] **Step 3: Ejecutar la prueba para verificar que falla**

Run: `cd tests && python -B -m unittest test_review_profile_topology 2>&1 | tail -20`
Expected: FAIL — `unsupported version` tanto para 11 como para 12.

- [ ] **Step 4: Reconocer schema 11 en `scripts/review_contract.py`**

En la función que valida el registro, cambiar el conjunto de versiones soportadas para que incluya 11 y, en el mismo bloque, tratar 11 con la forma de 10. La forma de schema 10 y la de schema 11 son idénticas, de modo que **todas** las tuplas de versión de este archivo que terminan en 10 pasan a terminar en 11.

Concretamente, en `scripts/review_contract.py`:

- El conjunto de versiones soportadas pasa de `{1, 2, 3, 4, 5, 6, 7, 8, 9, 10}` a `{1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11}`.
- **Todas** las tuplas de versión de este archivo que hoy terminan en 10 pasan a terminar en 11, sin excepción. Ninguna de ellas expresa la topología de perfiles: la topología se valida en `scripts/review_execution.py` y `scripts/review_profiles.py`, que este archivo invoca con el registro completo.

La comprobación de versión soportada debe ocurrir **antes** de cualquier otra validación, de modo que un 12 no se procese como si fuera una versión conocida.

- [ ] **Step 5: Reconocer schema 11 en `scripts/review_execution.py` (sólo forma)**

En `scripts/review_execution.py`, el flag `schema10` de `validate_execution_sources` y los condicionales de forma de la fila de plan pasan a cubrir 10 y 11:

- `plan_fields` incluye `selection_id` y `superseded_by` para schema 10 y para schema 11.
- La validación de `selection_id`/`superseded_by`, la de `required: false` con supersesión y la de `project_gate` no supersedible se aplican a schema 10 y 11.
- La rama que detecta `profile_history` en la ejecución se aplica a schema 10 y 11.
- `validate_execution_sources` cambia el flag `schema10` por dos banderas: una para "esquema de perfil" (10 y 11) que gobierna la forma, y otra para "topología nueva" (sólo 11) que gobierna las reglas. Los usos de forma del flag pasan a la primera; el bloque de candidatos finales (que Task 5 modifica) usará la segunda.

En `scripts/review_profiles.py`:

- Añadir las constantes de módulo `PROFILE_SCHEMAS = (10, 11)` y `NEW_TOPOLOGY_SCHEMAS = (11,)`.
- `validate_profile_execution` acepta un registro cuyo `schema_version` esté en `PROFILE_SCHEMAS`; para cualquier otro devuelve `[]` como hasta ahora.

- [ ] **Step 6: Ejecutar la prueba para verificar que pasa**

Run: `cd tests && python -B -m unittest test_review_contract 2>&1 | tail -20`
Expected: PASS

- [ ] **Step 7: Ejecutar la regresión de contratos**

Run: `cd tests && python -B -m unittest test_review_execution_policy test_review_profiles test_review_profile_names test_review_delivery 2>&1 | tail -20`
Expected: PASS — sin cambios en los fixtures congelados de schema 8 y schema 10.

- [ ] **Step 8: Commit**

```bash
git add tests/profile_topology_fixtures.py tests/test_review_profile_topology.py scripts/review_contract.py scripts/review_execution.py scripts/review_profiles.py
git commit -m "feat(contratos): reconocer el esquema de resultado 11"
```

---

### Task 2: Reconocer schema 11 en la superficie durable

**Files:**
- Modify: `scripts/review_artifacts.py`, `scripts/review_delivery.py`, `scripts/review_publication.py`, `scripts/review_history.py`, `scripts/review_check_provenance.py`, `scripts/review_check_receipts.py`, `scripts/review_preflight.py`
- Test: `tests/test_review_artifacts.py`

**Interfaces:**
- Consumes: `scripts/review_profiles.PROFILE_SCHEMAS` de Task 1.
- Produces: nada nuevo; es reconocimiento de versión en la proyección durable.

- [ ] **Step 1: Escribir la prueba que falla**

En `tests/test_review_artifacts.py`, añadir una prueba que retenga un review final schema 11 y compruebe que el gate de archive 8 lo acepta:

```python
    def test_archive8_accepts_a_schema11_final_review(self):
        # A schema-11 final review keeps the schema-10 shape, so archive 8
        # accepts it with the same execution/profile_history requirements.
        ...
```

El cuerpo usa el flujo de preparación y retención ya existente en el archivo (el mismo que usa un review schema 10) cambiando únicamente `schema_version` a 11 y `expected_schema` a 11. La aserción es que la retención completa sin `ValueError` y que `contract.validate` del resultado retenido devuelve `[]`.

- [ ] **Step 2: Ejecutar la prueba para verificar que falla**

Run: `cd tests && python -B -m unittest test_review_artifacts 2>&1 | tail -30`
Expected: FAIL con `archive 8 requires final review schema 10` o `expected schema must be a supported integer 1–10`.

- [ ] **Step 3: Extender los sitios de versión de la superficie durable**

En `scripts/review_artifacts.py`:

- La tupla de versiones de resultado que exige `review_id` coherente con el `run_id` pasa a incluir 11. Aparece en dos sitios: la verificación de un review retenido y la de un review final retenido.
- La comprobación `value.get('schema_version') in (8, 9, 10)` que decide si se aplica el gate de ejecución pasa a incluir 11. Aparece en dos sitios: la verificación de un review retenido y la construcción de la evidencia retenida.
- La condición `create_directory=value.get('schema_version') not in (8, 9, 10)` pasa a excluir 11.
- La tupla de versiones que decide si se validan los recibos de checks pasa a incluir 11.
- El rango `expected_schema not in range(1, 11)` pasa a `range(1, 12)`, y el `choices=range(1, 11)` de la opción `--expected-schema` pasa a `range(1, 12)`.
- **Los dos gates de archive 8** —el que rechaza un review final schema distinto de 10— cambian a "distinto de 10 **y** distinto de 11", es decir, aceptan `{10, 11}`. Son los dos sitios que hoy emiten el mensaje `archive 8 requires final review schema 10` y el diagnóstico `archive 8 checkpoints require review schema 10`. El resto de las exigencias de archive 8 sobre el review final (que `coverage` y `coverage.execution` sean objetos JSON, que `execution.profile_history` coincida con el manifiesto, que la operación esté abierta) **no cambian** y se siguen aplicando a schema 11.
- El diagnóstico de checkpoint que exige review schema 10 pasa a aceptar 10 y 11.

En los demás archivos, cada tupla de versión que hoy termina en 10 y expresa forma pasa a incluir 11:

- `scripts/review_delivery.py`: la tupla de la proyección de entrega y las tres comprobaciones de `review_id` frente a `run_id`.
- `scripts/review_publication.py`: la tupla de la proyección pública.
- `scripts/review_history.py`: la tupla de la verificación de `review_id` en la consulta histórica.
- `scripts/review_check_provenance.py`: las dos tuplas de versión soportada.
- `scripts/review_check_receipts.py`: la tupla de versión soportada.
- `scripts/review_preflight.py`: la tupla de `phase == 'retain'` que dispara la validación de recibos.

- [ ] **Step 4: Ejecutar la prueba para verificar que pasa**

Run: `cd tests && python -B -m unittest test_review_artifacts 2>&1 | tail -30`
Expected: PASS

- [ ] **Step 5: Verificar que no queda ningún sitio sin reconocer**

Run: `rg -n "schema_version'?\]?\)?\s*(==|!=|not in|in)\s*\(?[0-9,\s]*10\)?" scripts/`
Expected: cada coincidencia incluye 11 en su tupla, o es una de las dos formas admitidas: el gate de archive 8 (que acepta `{10, 11}`) o una comparación con `range(1, 12)`.

- [ ] **Step 6: Ejecutar la regresión de artefactos y entrega**

Run: `cd tests && python -B -m unittest test_review_artifacts test_review_delivery test_review_publication test_review_history test_review_check_provenance test_review_check_receipts test_review_preflight 2>&1 | tail -20`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add scripts/review_artifacts.py scripts/review_delivery.py scripts/review_publication.py scripts/review_history.py scripts/review_check_provenance.py scripts/review_check_receipts.py scripts/review_preflight.py tests/test_review_artifacts.py
git commit -m "feat(archivo): aceptar el esquema de resultado 11 en la superficie durable"
```

---

### Task 3: Cardinalidad de descubrimiento de schema 11

**Files:**
- Modify: `scripts/review_execution.py` (tabla de límites), `scripts/review_profiles.py` (mínimo de obligaciones)
- Test: `tests/test_review_profile_topology.py`

**Interfaces:**
- Consumes: `tests/profile_topology_fixtures.record11` de Task 1, `scripts/review_profiles.NEW_TOPOLOGY_SCHEMAS` de Task 1.
- Produces: `scripts/review_execution.PROFILE_LIMITS` — tupla de dos diccionarios `(legacy_limits, new_limits)` con las tablas de cardinalidad por perfil.

- [ ] **Step 1: Escribir la prueba que falla**

En `tests/test_review_profile_topology.py`, añadir a la clase `ProfileTopologyTests`:

```python
    def test_schema11_deep_accepts_exactly_two_discoveries(self):
        self.assertValid(record11('deep', 'explicit', discovery=2, verification=1))
        value = record11('deep', 'explicit', discovery=3, verification=1)
        self.assertInvalid(value, 'discovery cardinality')

    def test_schema11_extended_requires_three_discoveries(self):
        self.assertValid(record11('extended', 'explicit', discovery=3, verification=1))
        value = record11('extended', 'explicit', discovery=2, verification=1)
        self.assertInvalid(value, 'discovery cardinality')

    def test_schema11_extended_accepts_up_to_five_discoveries(self):
        self.assertValid(record11('extended', 'explicit', discovery=5, verification=1))

    def test_schema10_keeps_its_frozen_discovery_cardinality(self):
        from test_review_execution_policy import record8
        self.assertValid(record8('deep'))
        self.assertValid(record8('extended', 'explicit'))
        self.assertValid(record8('extended', 'automatic'))
```

- [ ] **Step 2: Ejecutar la prueba para verificar que falla**

Run: `cd tests && python -B -m unittest test_review_profile_topology 2>&1 | tail -20`
Expected: FAIL en `test_schema11_deep_accepts_exactly_two_discoveries` y `test_schema11_extended_requires_three_discoveries` — schema 11 usa hoy la tabla de schema 10 (deep 2–3, extended 2–5), así que `deep` con 3 pasa y `extended` con 2 pasa.

- [ ] **Step 3: Bifurcar la tabla de límites en `scripts/review_execution.py`**

En `validate_execution`, la tabla de límites pasa a dos diccionarios seleccionados por `schema_version`:

```python
LEGACY_PROFILE_LIMITS = {'focused': (1, 1), 'standard': (1, 1), 'deep': (2, 3),
                         'extended': (4, 5) if profile_source == 'automatic' else (2, 5)}
NEW_PROFILE_LIMITS = {'focused': (1, 1), 'standard': (1, 1), 'deep': (2, 2), 'extended': (3, 5)}
```

El legacy depende de `profile_source`, que se calcula más arriba; por eso la tabla legacy se construye donde hoy se construye la actual, y la nueva se declara como constante de módulo aparte.

La selección es: si `schema_version` está en `NEW_TOPOLOGY_SCHEMAS` se usa la tabla nueva; si no, la legacy. El mensaje de error de cardinalidad no cambia: `discovery cardinality does not match profile/selection`.

En `scripts/review_execution.py:99-106`, la rama que fuerza `profile_source = 'automatic'` deja de ejecutarse para schema 11, porque la tabla nueva no distingue la fuente de selección. Para schema 10 y anteriores se conserva tal cual.

- [ ] **Step 4: Ajustar el mínimo de obligaciones en `scripts/review_profiles.py`**

En `validate_profile_execution`, el mínimo por perfil se bifurca igual:

- Schema 11: `{'focused': 1, 'standard': 1, 'deep': 2, 'extended': 3}`.
- Schema 10 y anteriores: se conserva `{'focused': 1, 'standard': 1, 'deep': 2, 'extended': 4 if acquired_extended_auto or source == 'automatic' else 2}`.

La rama `acquired_extended_auto` se conserva para schema 10 y deja de ejecutarse para schema 11, donde el mínimo adquirido y el actual coinciden en 3. El mensaje de error no cambia: `'{strongest} profile obligations require at least {minimum} active discovery assignments'`.

- [ ] **Step 5: Ejecutar la prueba para verificar que pasa**

Run: `cd tests && python -B -m unittest test_review_profile_topology 2>&1 | tail -20`
Expected: PASS

- [ ] **Step 6: Ejecutar la regresión de perfiles**

Run: `cd tests && python -B -m unittest test_review_execution_policy test_review_profiles test_review_profile_names 2>&1 | tail -20`
Expected: PASS — los fixtures congelados de schema 8 y schema 10 no cambian.

- [ ] **Step 7: Commit**

```bash
git add scripts/review_execution.py scripts/review_profiles.py tests/test_review_profile_topology.py
git commit -m "feat(perfiles): fijar la cardinalidad de descubrimiento del esquema 11"
```

---

### Task 4: Agregación de `coverage.verification` con precedencia de tres niveles

**Files:**
- Modify: `scripts/review_execution.py`
- Test: `tests/test_review_profile_topology.py`

**Interfaces:**
- Consumes: `tests/profile_topology_fixtures.record11`, `source_fixture11`.
- Produces: `scripts/review_execution.verification_status(verification, observed, missing) -> str` — devuelve `'independent'`, `'same_session'` o `'unavailable'`.

- [ ] **Step 1: Escribir la prueba que falla**

En `tests/test_review_profile_topology.py`, añadir:

```python
    def test_schema11_aggregates_two_batches_over_all_rows(self):
        value = record11('extended', 'explicit', discovery=3, verification=2,
                         verification_ids=['V-candidatos', 'V-invariantes'])
        self.assertValid(value)

    def test_schema11_half_degraded_pair_reports_same_session(self):
        value = record11('extended', 'explicit', discovery=3, verification=2,
                         verification_ids=['V-candidatos', 'V-invariantes'])
        execution = value['coverage']['execution']
        execution['results'] = [row for row in execution['results']
                                if row['assignment_id'] != 'V-invariantes']
        execution['results'].append(dict(assignment_id='V-candidatos',
                                         reviewer_context='coordinator', provider_id=None,
                                         reference='evidence/results.json#V-candidatos'))
        execution['status'] = 'degraded'
        execution['fallbacks'] = [dict(assignments=['V-invariantes'], reason='explicit_restriction',
                                       detail='Second batch dispatched without a separate context',
                                       source='evidence/context.json#restriction')]
        value['coverage']['verification'] = 'same_session'
        self.assertValid(value)
```

- [ ] **Step 2: Ejecutar la prueba para verificar que falla**

Run: `cd tests && python -B -m unittest test_review_profile_topology 2>&1 | tail -30`
Expected: FAIL — `validate_execution` deriva el escalar de la última fila de verificación, de modo que un par con una fila degradada y otra no produce un valor que el otro validador contradice.

- [ ] **Step 3: Implementar la agregación en `scripts/review_execution.py`**

Añadir a nivel de módulo:

```python
def verification_status(verification, observed, missing):
    """Aggregate coverage.verification over the active verification rows.

    'unavailable' when a required row produced no observed result,
    'same_session' when a required row ran in the same session or was
    impeded, 'independent' when every required row completed independently.
    """
    if not verification:
        return None
    if any(row['id'] not in observed for row in verification):
        return 'unavailable'
    if any(row['id'] in missing or row.get('independent') is not True
           for row in verification):
        return 'same_session'
    return 'independent'
```

En la rama de schema 11 de `validate_execution`, la derivación de `effective` pasa a usar `verification_status(verification, observed, missing)`. La rama de schema 10 conserva su derivación por última fila, y la rama legacy su agregación binaria.

El comportamiento para un único lote es idéntico al actual: una fila sin resultado observada da `unavailable`; una fila impedida o no independiente da `same_session`; en otro caso `independent`.

- [ ] **Step 4: Ejecutar la prueba para verificar que pasa**

Run: `cd tests && python -B -m unittest test_review_profile_topology 2>&1 | tail -30`
Expected: PASS

- [ ] **Step 5: Ejecutar la regresión de ejecución**

Run: `cd tests && python -B -m unittest test_review_execution_policy test_review_profiles 2>&1 | tail -20`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add scripts/review_execution.py tests/test_review_profile_topology.py
git commit -m "feat(ejecucion): agregar la verificacion de lotes con precedencia de tres niveles"
```

---

### Task 5: Dos lotes de verificación en `extended` de schema 11

**Files:**
- Modify: `scripts/review_execution.py`
- Test: `tests/test_review_profile_topology.py`

**Interfaces:**
- Consumes: `verification_status` de Task 4, `record11` y `source_fixture11` de Task 1.
- Produces: regla de forma de plan y regla de lotes finales de schema 11 en `validate_execution_sources`.

- [ ] **Step 1: Escribir la prueba que falla**

En `tests/test_review_profile_topology.py`, añadir:

```python
    def test_schema11_extended_accepts_two_partitioned_batches(self):
        value = record11('extended', 'explicit', discovery=3, verification=2,
                         verification_ids=['V-candidatos', 'V-invariantes'])
        self.assertValid(value)
        context, events, references = source_fixture11(value)
        self.assertEqual(validate_execution_sources(value, context, events, references), [])

    def test_schema11_three_verification_rows_is_a_plan_shape_error(self):
        value = record11('extended', 'explicit', discovery=3, verification=3,
                         verification_ids=['V-candidatos', 'V-invariantes', 'V-extra'])
        self.assertInvalid(value, 'at most two verification batches')

    def test_schema11_batch_started_before_the_last_discovery_is_rejected(self):
        value = record11('extended', 'explicit', discovery=3, verification=2,
                         verification_ids=['V-candidatos', 'V-invariantes'])
        context, events, references = source_fixture11(value)
        # Give the second batch a start sequence earlier than the last discovery
        # completion, then renumber so the sequence values stay unique and rising.
        start = next(event for event in events
                     if event['kind'] == 'agent' and 'V-invariantes' in event['evidence'])
        start['sequence'] = 2
        for index, event in enumerate(sorted(events, key=lambda item: item['sequence']), 1):
            event['sequence'] = index
        errors = validate_execution_sources(value, context, events, references)
        self.assertTrue(any('verification batch' in error for error in errors), errors)
```

El módulo necesita importar `validate_execution_sources` desde `test_review_execution_policy`.

- [ ] **Step 2: Ejecutar la prueba para verificar que falla**

Run: `cd tests && python -B -m unittest test_review_profile_topology 2>&1 | tail -30`
Expected: FAIL — `validate_execution_sources` exige `len(final_candidates) != 1` y rechaza cualquier par.

- [ ] **Step 3: Implementar la regla de forma de plan y la de lotes finales**

En `validate_execution_sources`, el bloque `if schema10:` se divide en dos ramas: la de schema 10 conserva el comportamiento actual tal cual (`len(final_candidates) != 1` con sus dos mensajes), y la de schema 11 aplica:

1. **Forma de plan.** El número de filas de verificación activas no puede superar 2 en `extended` ni 1 en los demás perfiles. El mensaje es `'{strongest} permits at most {n} verification batches'`.
2. **Lotes finales.** En `extended`, el número de candidatos finales debe igualar el número de filas de verificación activas. Si no iguala y el estado de ejecución es `fulfilled`, el error es `fulfilled review requires every planned verification batch to run after the final discovery batch`. Si el estado es `degraded`, el desfase no es un error de forma de plan: el valor agregado de `coverage.verification` ya fue validado contra las filas activas por `validate_execution`, que `validate_execution_sources` ejecuta antes y cuyo fallo devuelve temprano.
3. En `deep`, `standard` y `focused` el número de candidatos finales sigue siendo exactamente 1, con los mensajes actuales.

La comprobación de `coverage.verification` contra el lote final que hoy hace la rama de schema 10 se sustituye en schema 11 por la agregación de Task 4, que ya corre dentro de `validate_execution` sobre las mismas filas activas. La rama de schema 10 conserva esa comprobación tal cual.

- [ ] **Step 4: Ejecutar la prueba para verificar que pasa**

Run: `cd tests && python -B -m unittest test_review_profile_topology 2>&1 | tail -30`
Expected: PASS

- [ ] **Step 5: Añadir la prueba de convención de partición y de identidad de reviewer**

En `tests/test_review_profile_topology.py`, añadir:

```python
    def test_schema11_partitioned_batches_use_distinct_reviewer_identities(self):
        value = record11('extended', 'explicit', discovery=3, verification=2,
                         verification_ids=['V-candidatos', 'V-invariantes'])
        ids = [row['id'] for row in value['coverage']['execution']['plan']
               if row['role'] == 'verification']
        self.assertEqual(ids, ['V-candidatos', 'V-invariantes'])
        contexts = [row['reviewer_context'] for row in value['coverage']['execution']['results']]
        self.assertEqual(len(set(contexts)), len(contexts))

    def test_schema11_reused_provider_identity_cannot_claim_independence(self):
        value = record11('extended', 'explicit', discovery=3, verification=2,
                         verification_ids=['V-candidatos', 'V-invariantes'])
        execution = value['coverage']['execution']
        for result in execution['results']:
            if result['assignment_id'] == 'V-invariantes':
                result['provider_id'] = 'provider-V-candidatos'
        self.assertInvalid(value, 'independence')
```

La segunda prueba reutiliza el `provider_id` del primer lote: el validador de ejecución no puede tratar ese lote como independiente, y el run queda degradado en lugar de afirmar independencia.

- [ ] **Step 6: Ejecutar la regresión de ejecución y perfiles**

Run: `cd tests && python -B -m unittest test_review_execution_policy test_review_profiles test_review_profile_names 2>&1 | tail -20`
Expected: PASS — schema 10 con dos lotes finales sigue siendo inválido.

- [ ] **Step 7: Commit**

```bash
git add scripts/review_execution.py tests/test_review_profile_topology.py
git commit -m "feat(perfiles): admitir dos lotes de verificacion particionados en extended"
```

---

### Task 6: Contratos y prosa en inglés

**Files:**
- Modify: `SKILL.md`, `references/workflow/profiles.md`, `references/contracts/result-contract.md`, `references/execution/reviewers.md`, `references/workflow/reading-strategy.md`

**Interfaces:**
- Consumes: las reglas de Task 3, Task 4 y Task 5.
- Produces: la prosa normativa que el coordinador y los workers leen.

- [ ] **Step 1: Actualizar la tabla de perfiles de `SKILL.md`**

La tabla de perfiles pasa a:

| Profile | Discovery | Verification |
|---|---|---|
| focused | One reviewer, potentially the coordinator | Same-session skeptical pass over candidates/material questions |
| standard | One reviewer, potentially the coordinator | Fresh verifier for substantive candidates/material questions; skip when none remain and coverage is adequate |
| deep | Two independent reviewers on named flows/risks | Fresh verifier for grouped candidates and named invariants; unrelated flows retain ordinary coverage |
| extended | Three to five justified independent assignments | One or two fresh grouped verification batches for candidates and assigned invariants |

La sección que introduce los perfiles dice que las reglas de cardinalidad nuevas aplican a schema 11 y que schema 10 conserva las suyas.

- [ ] **Step 2: Actualizar `references/workflow/profiles.md`**

- La sección de asignaciones deep y extended: deep usa dos descubridores frescos; un tercero ya no pertenece a deep y la necesidad que no cabe escala a extended. Extended admite de tres a cinco asignaciones justificadas, y el argumento pasa de "un plan de tres revisores" a "un plan de dos revisores".
- La línea de extended explícito: arranca en tres, no en dos; el máximo de cinco se mantiene; el "plus one fresh grouped verifier" pasa a "one or two fresh grouped verification batches".
- La línea del lote agrupado: se admite un segundo lote, particionado en candidatos e invariantes asignadas, con la convención de identificadores `V-candidatos` y `V-invariantes`. La prohibición de un segundo barrido completo del alcance se mantiene y ahora exige que el segundo lote cubra uno de esos dos alcances.
- La sección de verificación y cierre: deep conserva un lote agrupado; extended admite hasta dos lotes particionados, ambos posteriores a todo el descubrimiento.
- El escalamiento: una necesidad de cobertura distinta que no cabe en los dos descubridores de deep escala a extended; un deep explícito declara la necesidad, solicita el cambio de perfil o reporta el hueco material.

- [ ] **Step 3: Actualizar `references/contracts/result-contract.md`**

- La línea que enumera las versiones de esquema declara schema 11: misma forma que schema 10, con las reglas de cardinalidad y agregación nuevas; schema 10 queda congelado con deep 2–3, extended automático 4–5 y explícito 2–5, y un verificador final.
- La fórmula de los cuatro perfiles pasa a: focused un descubrimiento y una comprobación escéptica en la misma sesión; standard un descubrimiento y un verificador agrupado fresco; deep dos descubrimientos frescos justificados y un verificador fresco; extended de tres a cinco descubrimientos frescos justificados y uno o dos verificadores agrupados frescos.

- [ ] **Step 4: Actualizar `references/execution/reviewers.md` y `references/workflow/reading-strategy.md`**

- `reviewers.md`: la segunda enunciación de la prohibición de un barrido completo admite el segundo lote particionado de extended, y nombra la convención de identificadores.
- `reading-strategy.md`: la frase sobre los límites de asignación de deep y extended refleja el nuevo conteo.

- [ ] **Step 5: Comprobar que la prosa no contradice los validadores**

Run: `rg -n "four or five|three-reviewer|two to five|a third only|un tercero|one grouped verification batch|one fresh grouped verifier" SKILL.md references/ README.md docs/usage.md`
Expected: sin coincidencias en las afirmaciones de conteo; cada una está actualizada al conteo de schema 11 o pertenece a una descripción explícita del comportamiento congelado de schema 10.

- [ ] **Step 6: Ejecutar la regresión de enlaces de referencia**

Run: `cd tests && python -B -m unittest test_review_reference_layout test_review_references test_review_reference_index 2>&1 | tail -20`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add SKILL.md references/workflow/profiles.md references/contracts/result-contract.md references/execution/reviewers.md references/workflow/reading-strategy.md
git commit -m "docs(contratos): describir la topologia de sesiones por perfil"
```

---

### Task 7: Documentación de usuario, CHANGELOG y versión

**Files:**
- Modify: `docs/usage.md`, `README.md`, `CHANGELOG.md`, `SKILL.md`

**Interfaces:**
- Consumes: las reglas de Task 3, Task 4 y Task 5.
- Produces: la versión 2.15.0 de la skill.

- [ ] **Step 1: Actualizar la tabla de perfiles de `docs/usage.md`**

La tabla en español pasa a: focused, un revisor y comprobación escéptica en la misma sesión; standard, un revisor y verificador independiente para candidatos sustantivos o dudas materiales; deep, dos revisores independientes sobre flujos e invariantes concretos, con verificación independiente agrupada; extended, de tres a cinco asignaciones independientes justificadas, con una o dos verificaciones independientes agrupadas.

El párrafo de elegibilidad de extended cambia "cuatro o cinco asignaciones independientes necesarias que no puedan agruparse en tres" por "tres o más asignaciones independientes necesarias que no puedan agruparse en dos". La sección de delegación cambia "Deep requiere dos descubridores independientes (tercero justificado)" por "Deep requiere dos descubridores independientes y un verificador fresco agrupado; extended amplía las asignaciones necesarias y admite un segundo lote de verificación particionado".

- [ ] **Step 2: Actualizar la tabla de perfiles de `README.md`**

La fila de deep deja de mentionar el tercero; la de extended pasa a "de tres a cinco asignaciones justificadas, y una o dos verificaciones independientes agrupadas".

- [ ] **Step 3: Añadir la entrada de CHANGELOG**

En `CHANGELOG.md`, añadir una sección nueva al principio:

```markdown
## 2.15.0 — 2026-10-21

### Added

#### Perfiles y ejecución

- Introducir el esquema de resultado 11 con la topología de sesiones explícita por perfil: deep con dos descubridores independientes, extended con tres a cinco y hasta dos lotes de verificación particionados.
- Admitir un segundo lote de verificación agrupado en extended, particionado entre candidatos e invariantes asignadas, con la convención de identificadores `V-candidatos` y `V-invariantes`.
- Agregar el estado de verificación de los lotes con precedencia de tres niveles: `independent`, `same_session` y `unavailable`.

### Changed

#### Perfiles y ejecución

- Subir el piso de descubrimiento de extended a tres asignaciones justificadas, también en la selección explícita, y fijar deep en dos.
- Declarar la escalación a extended como la vía para una necesidad de cobertura distinta que no cabe en los dos descubridores de deep.

### Fixed

#### Perfiles y ejecución

- Conservar el descubrimiento independiente válido al escalar de deep a extended, sin lanzar un segundo equipo completo.
```

La sección se fecha con la fecha de publicación que se acuerde al publicar.

- [ ] **Step 4: Subir la versión de `SKILL.md`**

En el frontmatter de `SKILL.md`, `metadata.version` pasa de `"2.14.0"` a `"2.15.0"`.

- [ ] **Step 5: Comprobar que no quedan conteos antiguos**

Run: `rg -n "cuatro o cinco|un tercero|four or five|two to five|a third only" SKILL.md README.md docs/usage.md references/`
Expected: sin coincidencias, salvo que una mencione explícitamente el comportamiento congelado de schema 10.

- [ ] **Step 6: Ejecutar la suite completa**

Run: `cd tests && python -B -m unittest discover -s . 2>&1 | tail -10`
Expected: PASS — la suite completa, incluidos los 717 tests de la línea base y los nuevos de schema 11.

- [ ] **Step 7: Commit**

```bash
git add docs/usage.md README.md CHANGELOG.md SKILL.md
git commit -m "chore(release): preparar la version 2.15.0"
```

---

## Matriz de trazabilidad

| Requisito del spec | Task |
|---|---|
| §7.4 Schema 11 registrado, schema 10 congelado | 1, 2 |
| §7.4 Gate de archive 8 acepta `{10, 11}` sin relajar el resto | 2 |
| §7.1 Cardinalidad de descubrimiento de schema 11 | 3 |
| §5 Escalación de deep a extended | 3, 6 |
| §7.3 Agregación con precedencia de tres niveles | 4 |
| §7.2 Cardinalidad de verificación y forma de plan | 5 |
| §6.1 Convención de partición | 5, 6 |
| §6.2 Orden de los lotes tras `last_discovery` | 5, 6 |
| §8.3 Cobertura de pruebas | 3, 4, 5 |
| §8.2 Prosa y versión | 6, 7 |

## Revisión del plan y entrega

El plan se revisó contra el spec: cada sección del spec tiene al menos una task; los pasos de código fijan firma, archivo y valores exactos; los nombres de las funciones nuevas (`verification_status`, `record11`, `source_fixture11`) son consistentes entre tasks. La cobertura de Review Focus está repartida: R1 en Task 3 y 5, R2 en Task 3, R3 en Task 5, R4 en Task 4, R5 en Task 1 y 2.

La suite completa tarda del orden de 35 minutos; Task 7 la ejecuta una sola vez al final. Las tasks intermedias usan los módulos de prueba acotados.
