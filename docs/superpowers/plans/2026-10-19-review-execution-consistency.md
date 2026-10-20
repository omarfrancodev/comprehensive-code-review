# Review Execution Consistency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** detectar preparación incompatible antes del dispatch, conservar referencias y recibos auditables, y continuar sólo el trabajo realmente incompleto.

**Architecture:** compartir validación pura entre preflight y retención; mantener los mutadores de archivo existentes como autoridad durable; añadir constructores de candidatos locales, recibos y una proyección operativa de sólo lectura. Evitar una nueva operación de reparación de identidad capturada.

**Tech Stack:** Python 3.10+, biblioteca estándar, unittest, Git y Markdown.

**Spec:** [Consistencia de preparación, evidencia y continuidad](../specs/2026-10-19-review-execution-consistency-design.md).

## Global Constraints

- Python 3.10+ y biblioteca estándar; no añadir dependencias de ejecución.
- Mantener archive schema 8/layout 2 nativo, result schemas 1–10 legibles y trace schema 1; no migrar ni reescribir archivos históricos.
- Los archives anteriores a schema 8/layout 2 son unsupported_layout para operación; la consulta histórica usa review_history.py y sus paquetes exactos de tres archivos.
- Conservar logical_scope_identity y el replay nativo v2 existentes; no recalcular identidades persistidas ni seleccionar la última revisión de forma implícita.
- Los runs completos son inmutables; ninguna corrección administrativa altera sus bytes.
- Preflight, diagnóstico y vista operativa son de sólo lectura: no crean runs, locks, eventos, worktrees ni procesos.
- Sólo el coordinador modifica metadata durable, usando locks, transacciones y comprobaciones de ownership existentes.
- No inferir autoridad, independencia, identidad de actor, éxito de comandos ni disponibilidad de procesos.
- No reutilizar resultados con scope, inputs, configuración o procedencia desconocidos o cambiados.
- No relajar gates de retención, aislamiento, cleanup, perfil ni requisitos independientes del proyecto.
- No implementar cambios en el visor independiente ni en las skills globales de Superpowers o todo.
- No activar medición de tokens, precios o contadores; usar sólo hechos operativos ya registrados.
- Conservar la procedencia interna completa; publicar los bytes del render público verificado sin ediciones posteriores al render.
- Registrar modelos sólo con datos ya expuestos por el entorno; no inferirlos, sondear APIs ni activar mediciones para completar ese registro.

## Review Focus

1. Referencias con fragmentos escapados, traversal, URL y nombres Windows deben producir el mismo diagnóstico antes y después de registrar fuentes; cubre Task 1.
2. Un evento completed sin evidencia o sin inicio no puede convertirse en un resultado independiente válido; cubre Task 2, además de las reglas de ejecución existentes.
3. IDs C004 en código o ejemplos externos no son checks; C004 en cobertura interna sí debe resolver; cubre Task 3.
4. El comentario debe omitir referencias/reintentos internos sin ocultar fallos de producto o revisiones base; el cuerpo editado después de render no puede publicarse como canónico; cubre Task 6.
5. Un sucesor con transferencia pendiente, fuente inaccesible o layout histórico no puede aparecer como ready; el replay nativo v2 y los rechazos de latest ambiguo/incompleto deben conservarse; cubre Tasks 2 y 8.

---

## Base y mapa de archivos

Estado: ejecución autorizada por el usuario el 2026-10-20. Método: ejecución inline, tarea por tarea, con TDD y commits locales según este plan.

Base actualizada: `09eeb034af211af4481206eb943abb6b85fd38db`, main/CCR 2.13.0, incorporada mediante fast-forward en este worktree. Incluye los PR 25 y 26. El spec §2.1 identifica lo ya implementado: layout 2, archive 8, logical_scope_identity, consulta histórica HP, lookup/latest explícito, replay v2 compatible y subaspectos ABCDE. Estas capacidades se reutilizan y se protegen con regresiones; no son nuevas tasks de implementación.

Si main vuelve a avanzar antes de ejecutar el plan, contrastar sus contratos antes de cambiar estas interfaces. No usar ejemplos archive 7 como operaciones actuales ni reclamar soporte operativo legacy por conservar el validador puro de resultados.

Los nombres nuevos son decisiones de este plan. Las ubicaciones de integración existentes se identifican por función, no por líneas que cambiarán:

| Task | Crear | Integrar o modificar |
|---|---|---|
| 1 | `scripts/review_references.py`, `tests/test_review_references.py` | `_capture_review_inputs`, `_retained_name`, `_execution_gate` en `review_artifacts.py` |
| 2 | `scripts/review_preflight.py`, `tests/test_review_preflight.py` | `prepare`, `_register_locked`, `record_event`, CLI de `review_artifacts.py`; tests de artifacts/trace |
| 3 | `tests/test_review_reference_index.py` | `review_references.py`, `review_contract.py`, `review_packets.py`, `_execution_gate`; contrato documental |
| 4 | `scripts/review_setup.py`, `tests/test_review_setup.py` | Ejemplos operativos y referencias de workflow |
| 5 | `scripts/review_check_receipts.py`, `tests/test_review_check_receipts.py` | `review_check_provenance.py`, preflight/retención y documentación de checks |
| 6 | `scripts/review_comment.py`, `tests/test_review_comment.py`, `tests/publication_fixtures.py` | Proyección de checks por audiencia, renderer, política y tests de publicación |
| 7 | `scripts/review_model_usage.py`, `tests/test_review_model_usage.py` | Registro privado de modelo por actividad, contexto y evidencia del harness |
| 8 | `tests/test_review_operational_summary.py` | `review_recovery.py`, rutas de inspect/recover/restart; documentación y validación final |

No crear un paquete de dependencias ni un runner de agentes alternativo. Todos los tests nuevos siguen el patrón del proyecto: insertar `scripts/` en sys.path, unittest y fixtures sintéticos en directorios temporales. Usar `tests/recovery_fixtures.py` para recuperación nativa, `tests/archive_layout_fixtures.py` para fuentes históricas y `tests/restart_v2_fixtures.py` para productores v2 previos; no importar clases de tests entre módulos nuevos. `scripts/review_layout.py`, `review_history.py` y `review_restart.py` mantienen sus autoridades actuales, sin un protocolo paralelo.

Los métodos de test de las tareas se añaden a la clase unittest indicada. Preambulo compartido para las rutas e imports usados en los ejemplos; importar después el módulo nuevo de cada task con el alias indicado:

```python
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path[:0] = [str(SCRIPTS), str(Path(__file__).resolve().parent)]
from recovery_fixtures import record10, context10, selection_input
```

Los fragmentos de aserciones de integración se insertan en los métodos nombrados y usan las variables de su fixture explícitamente descritas. No son scripts de implementación ni sustituyen los guards de producción. Las líneas de modificación corresponden al commit base y sólo son anclas de lectura.

## Orden y verificación

Orden: Task 1 → Task 2 → Task 3 → Task 4 → Task 5 → Task 6 → Task 7 → Task 8. Task 3 conserva su validador puro separado de IO; Tasks 4/5 consumen sus contratos. No introducir independencia paralela ficticia en esta secuencia.

Comandos de este documento se ejecutan desde la raíz del worktree con un Python real compatible. En Windows seleccionar TEMP/TMP de sesión dentro de los permisos existentes si el entorno requiere una ruta más corta; registrar ese ajuste y no cambiar configuración global. No usar los archives reales para probar recovery, cleanup o aliases.

Cada task realiza RED, cambio mínimo, GREEN y commit de sus archivos. El ledger `.superpowers/sdd/2026-10-19-review-execution-consistency/progress.md` registra evidencia y avance.

### Task 1: gramática y resolución compartidas de referencias

**Files:**
- Create: `scripts/review_references.py`
- Modify: `scripts/review_artifacts.py:1101` — `_capture_review_inputs`
- Modify: `scripts/review_artifacts.py:1223` — `_retained_name`
- Modify: `scripts/review_artifacts.py:3891` — `_execution_gate`
- Test: `tests/test_review_references.py`

**Interfaces:**

- Consumes: `_capture_review_inputs(raw, scope, profile, label, *, logical_scope_identity=None)` y las reglas de fragmentos de `_execution_gate` actuales.
- Produces: `ReferenceIssue`, TypedDict con `code: str`, `field: str`, `reference: str | None`, `message: str`, `expected: str`.
- Produces: `parse_reference(reference: str, *, field: str, allow_alias_key: bool = False) -> tuple[str, str | None]`: retorna ruta y fragmento; ValueError para formato inválido.
- Produces: `resolve_reference(reference: str, sources: dict[str, bytes], *, field: str) -> object`: bytes sin fragmento o valor JSON/evento/ancla según el contrato vigente; sin IO.
- Produces: `validate_selection_reference(selection: dict, sources: dict[str, bytes] | None) -> list[ReferenceIssue]`: valida sintaxis sin fuentes; con fuentes, exige valor de perfil exacto.
- Los caller convierten ValueError en issues acotados; no se relajan los límites de lectura existentes.

- [ ] **Step 1: escribir los tests de gramática y perfil (RF1)**

En `tests/test_review_references.py`, importar `review_references as refs`, unittest y `selection_input` de `recovery_fixtures`. Añadir estos métodos a `ReferenceTests(unittest.TestCase)`:

```python
def test_references_and_profile(self):
    self.assertEqual(refs.parse_reference('evidence/context.json#profile',
        field='reference'), ('evidence/context.json', 'profile'))
    for bad in ('https://example.test/pr/1', 'evidence/a/b.cs',
                'evidence/../x', 'evidence/CON', 'evidence/a%2Fb'):
        with self.subTest(reference=bad), self.assertRaises(ValueError):
            refs.parse_reference(bad, field='reference')
    selected = selection_input()
    self.assertEqual(refs.validate_selection_reference(selected, None), [])
    self.assertEqual(refs.validate_selection_reference(selected, {
        'evidence/context.json': b'{"profile":"focused"}'}), [])
    self.assertTrue(refs.validate_selection_reference(
        dict(selected, reference='evidence/scope.json'), None))

def test_json_fragment_escapes_and_indices(self):
    data = {'evidence/a.json': b'{"a/b":[{"~key":"focused"}]}'}
    self.assertEqual(refs.resolve_reference('evidence/a.json#a~1b/0/~0key',
        data, field='reference'), 'focused')
```

- [ ] **Step 2: ejecutar RED**

Run: `python -m unittest discover -s tests -p test_review_references.py -v`

Expected: fallo por módulo/interfaz nueva ausente o por la aceptación/resolución incorrecta descrita; no aceptar un error de fixture como reproducción.

- [ ] **Step 3: implementar parser y resolver puros en `review_references.py`**

Implementar las tres firmas de Produces según spec §5.1. Conservar semántica de fragmentos vigente, sin IO ni interpretación física de claves de alias.

- [ ] **Step 4: integrar la gramática en captura y retención**

Usar el módulo desde las tres funciones de Files. Conservar logical_scope_identity y el rechazo operativo de archives anteriores a 8/2; no modificar `_load_run` para admitir historia.

- [ ] **Step 5: ejecutar test_review_references.py**

Run: `python -m unittest discover -s tests -p test_review_references.py -v`

Expected: el módulo termina OK, exit 0; no acredita la suite completa por sí solo.

- [ ] **Step 6: ejecutar test_review_inputs.py**

Run: `python -m unittest discover -s tests -p test_review_inputs.py -v`

Expected: el módulo termina OK, exit 0; no acredita la suite completa por sí solo.

- [ ] **Step 7: ejecutar test_review_layout_v2.py**

Run: `python -m unittest discover -s tests -p test_review_layout_v2.py -v`

Expected: el módulo termina OK, exit 0; no acredita la suite completa por sí solo.

- [ ] **Step 8: commit**

```powershell
git add -- scripts/review_references.py scripts/review_artifacts.py tests/test_review_references.py
git commit -m "feat(referencias): unificar validación de fuentes retenidas"
```

### Task 2: preflight por fase y barrera de asignaciones

**Files:**
- Create: `scripts/review_preflight.py`
- Modify: `scripts/review_artifacts.py:1169` — record-event
- Modify: `scripts/review_artifacts.py:1610` — prepare
- Modify: `scripts/review_artifacts.py:1845` — register
- Modify: `scripts/review_artifacts.py:3797` — retain
- Modify: `scripts/review_artifacts.py:4117` — CLI
- Modify: `references/archive/artifacts.md`
- Test: `tests/test_review_preflight.py`
- Test: `tests/test_review_trace.py`

**Interfaces:**

- Consumes: `ReferenceIssue` y `validate_selection_reference(selection, sources)` de Task 1; `review_layout.logical_scope(scope, selector_input=None) -> dict` y `review_trace.event_input(raw, *, helper=False) -> dict` existentes.
- Produces: `validate_preflight(*, phase: str, manifest: dict | None, logical_scope: dict | None, selection: dict | None, context: dict | None, record: dict | None, sources: dict[str, bytes]) -> dict`: resultado exacto `{phase, ready, issues}`; phases `prepare|register|discovery|retain`. logical_scope es el descriptor ya normalizado por review_layout en prepare o el capturado por el manifest nativo; no se deriva de hints.
- Produces: `validate_assignment_event(event: dict, registry: list[dict]) -> list[ReferenceIssue]`: exige identidad activa para hitos de trabajo; no despacha ni construye evidencia.
- CLI público de preflight: el definido en spec §5.2; `prepare` usa la función pura antes de crear un run y no exige un `--run-dir` inexistente.
- La capa IO de prepare sigue usando `review_layout.logical_scope(scope, logical_scope_input)` y pasa al validador el descriptor canónico y las entradas ya leídas; el preflight de run existente recibe el manifest nativo completo. No derivar selectores en un segundo módulo ni normalizar intents persistidos como parte del preflight.

- [ ] **Step 1: escribir los tests de entrada inválida y asignación omitida (RF2)**

Importar `review_preflight as preflight`, `review_trace` y selection_input en `PreflightTests(unittest.TestCase)`:

```python
def test_completed_without_assignment_is_rejected(self):
    event = review_trace.event_input({'kind': 'discovery', 'status': 'completed',
        'summary': 'Observed completion', 'evidence': []})
    issues = preflight.validate_assignment_event(event, [])
    self.assertIn('missing_assignment', {i['code'] for i in issues})

def test_prepare_checks_syntax_without_future_results(self):
    selected = selection_input()
    args = dict(phase='prepare', manifest=None, logical_scope=None,
                context=None, record=None, sources={})
    self.assertEqual(preflight.validate_preflight(selection=selected, **args),
                     {'phase': 'prepare', 'ready': True, 'issues': []})
    result = preflight.validate_preflight(selection=dict(selected,
        reference='https://example.test/pr/1'), **args)
    self.assertFalse(result['ready'])
    self.assertIn('invalid_reference', {i['code'] for i in result['issues']})
```

logical_scope null aquí significa validación pura de sintaxis; el adaptador prepare siempre valida su selector antes de asignar el run.

- [ ] **Step 2: ejecutar RED**

Run: `python -m unittest discover -s tests -p test_review_preflight.py -v`

Expected: interfaz nueva ausente o evento sin identidad aceptado; el fixture usa un evento válido de review_trace para aislar el bypass.

- [ ] **Step 3: implementar los dos validadores puros**

Implementar las firmas de Produces por fase: plan vacío preparado permitido, trabajo sin asignación activa rechazado, identidad lógica contrastada cuando hay descriptor. Acumular issues independientes ordenados y acotados a 100; no acumular lecturas después de fallo de acceso/integridad.

- [ ] **Step 4: integrar preflight, barrera y CLI**

Conectar prepare/register/retain y record-event con los validadores anteriores. CLI: exit 0 ready, exit 1 contrato, exit 2 acceso/parseo/integridad/unsupported_layout. Conservar revalidación bajo lock de mutadores y ausencia de locks nuevos en el comando read-only.

- [ ] **Step 5: añadir aserciones de integración con repositorios temporales**

Seguir el fixture de preparación de `tests/test_review_artifacts.py`, con context10/record10; `historical_prepare` crea la fuente histórica. run es el Path devuelto por prepare y context_file contiene su context10 actualizado con historial/identidades observados. Ejecutar el CLI sin shell:

```python
completed = subprocess.run([
    sys.executable, str(SCRIPTS / 'review_artifacts.py'), 'preflight',
    '--run-dir', str(run), '--context-input', str(context_file),
    '--phase', 'register'], capture_output=True, text=True, encoding='utf-8')
```

Los puntos de prueba son:

```python
# test_preflight_does_not_create_lock_or_checkpoint: run preparado válido
self.assertEqual(completed.returncode, 0)
self.assertEqual(after, before)
# test_preflight_rejects_unsupported_layout_without_writes: histórico sintético
self.assertEqual(completed.returncode, 2)
self.assertIn('unsupported_layout', completed.stdout + completed.stderr)
self.assertEqual(after, before)
# test_preflight_preserves_logical_scope_identity: identidad distinta del descriptor
self.assertFalse(result['ready'])
self.assertIn('input_changed', {i['code'] for i in result['issues']})
self.assertEqual(context, original_context)
```

before/after son mapas de rutas relativas a bytes de todos los archivos del root temporal; así también se detecta creación de locks. original_context es deepcopy antes de validar. result es validate_preflight en register con manifest/contexto del fixture y logical_scope del manifest, tras cambiar sólo context.review_inputs.logical_scope_identity a `'0'*64`. Añadir el par del mismo MR con otro head: mismo grupo lógico no produce inputs aplicables.

- [ ] **Step 6: documentar el comando preflight**

Actualizar `references/archive/artifacts.md` con fases, códigos de salida y la distinción entre preflight parcial y retain completo. No exigir resultados inexistentes durante prepare.

- [ ] **Step 7: ejecutar test_review_preflight.py**

Run: `python -m unittest discover -s tests -p test_review_preflight.py -v`

Expected: el módulo termina OK, exit 0; no acredita la suite completa por sí solo.

- [ ] **Step 8: ejecutar test_review_trace.py**

Run: `python -m unittest discover -s tests -p test_review_trace.py -v`

Expected: el módulo termina OK, exit 0; no acredita la suite completa por sí solo.

- [ ] **Step 9: ejecutar test_review_archive8.py**

Run: `python -m unittest discover -s tests -p test_review_archive8.py -v`

Expected: el módulo termina OK, exit 0; no acredita la suite completa por sí solo.

- [ ] **Step 10: commit**

```powershell
git add -- scripts/review_preflight.py scripts/review_artifacts.py tests/test_review_preflight.py tests/test_review_trace.py references/archive/artifacts.md
git commit -m "feat(preparacion): validar contratos antes de iniciar trabajo"
```

### Task 3: índice retenido, checks y fuentes materiales coherentes

**Files:**
- Modify: `scripts/review_references.py` — módulo de Task 1
- Modify: `scripts/review_contract.py:93`
- Modify: `scripts/review_packets.py:12`
- Modify: `scripts/review_artifacts.py:3891`
- Modify: `references/contracts/result-contract.md`
- Test: `tests/test_review_reference_index.py`

**Interfaces:**

- Consumes: `ReferenceIssue`, `parse_reference` y `resolve_reference` de Task 1; `validate_preflight` de Task 2 como punto de integración.
- Produces: `validate_reference_index(index: dict, sources: dict[str, bytes]) -> list[ReferenceIssue]`: forma y aliases/inputs del spec §8; alias de un salto y hash igual.
- Produces: `validate_semantic_references(record: dict, packets: list[dict], index: dict | None, sources: dict[str, bytes]) -> list[ReferenceIssue]`: IDs tipados, tokens internos de checks y referencias explícitas; no escanear fuentes externas por tokens.
- Produces: `validate_material_inputs(record: dict, context: dict, index: dict, sources: dict[str, bytes]) -> list[ReferenceIssue]`: descripción/inputs del spec §9.1.
- Produces: `canonical_reference(reference: str, aliases: dict[str, dict[str, str]]) -> str`: devuelve el campo `reference` del alias de un salto después de validar su digest; no resuelve rutas físicas ni busca archivos.

- [ ] **Step 1: escribir tests de C004, alias y fuente material (RF3)**

Importar `review_references as refs`, hashlib y record10/context10. En `ReferenceIndexTests(unittest.TestCase)`:

```python
def test_current_c004_is_required_but_external_example_is_not(self):
    record = record10()
    record['coverage']['areas'][0]['details'] = 'Comprobado por C004'
    issues = refs.validate_semantic_references(record, [], None, {})
    self.assertIn('unknown_check', {i['code'] for i in issues})
    record['coverage']['areas'][0]['details'] = 'Inspección estática'
    issues = refs.validate_semantic_references(record, [], None,
        {'evidence/example.py': b'# Example C004'})
    self.assertNotIn('unknown_check', {i['code'] for i in issues})

def test_renamed_source_requires_matching_original_digest(self):
    data = b'original producer bytes'
    aliases = {'evidence/producer/handler.cs': {
        'reference': 'evidence/producer-handler.cs',
        'sha256': hashlib.sha256(data).hexdigest()}}
    index = {'schema_version': 1, 'aliases': aliases, 'inputs': []}
    self.assertEqual(refs.validate_reference_index(index,
        {'evidence/producer-handler.cs': data}), [])
    self.assertEqual(refs.canonical_reference(
        'evidence/producer/handler.cs', aliases), 'evidence/producer-handler.cs')
    self.assertTrue(refs.validate_reference_index(index,
        {'evidence/producer-handler.cs': b'changed'}))

def test_aligned_description_requires_selected_content(self):
    record = record10()
    issues = refs.validate_material_inputs(record, context10(record),
        {'schema_version': 1, 'aliases': {}, 'inputs': []}, {})
    self.assertIn('missing_input', {i['code'] for i in issues})
```

- [ ] **Step 2: ejecutar RED**

Run: `python -m unittest discover -s tests -p test_review_reference_index.py -v`

Expected: interfaz ausente o C004/fuente ausente no diagnosticados. No introducir un record inválido para provocar otro error.

- [ ] **Step 3: implementar índice y resolución canónica en `review_references.py`**

Implementar validate_reference_index y canonical_reference con el schema exacto del spec §8. Verificar hash original, destinos seleccionados, alias de un salto y rechazo de cadena/ciclo; no tocar bytes de paquetes originales.

- [ ] **Step 4: implementar validación semántica y de inputs materiales**

Implementar validate_semantic_references y validate_material_inputs según spec §8–9.1. La comparación de identidad acepta hexadecimal o prefijo sha256 sin reescribirlo. La descripción sin fuente verificable no acredita aligned.

- [ ] **Step 5: integrar sidecar y preservar los formatos existentes**

Conectar los validadores con contract/packets y el gate seleccionado de artifacts. Capturar el hash del índice antes del trabajo; nunca incluirlo en su propio inputs. Añadir al fixture temporal las siguientes aserciones de compatibilidad:

```python
# test_existing_native8_without_index: run completo construido sin sidecar
self.assertEqual(artifacts.validate(run, require_complete=True)['state'], 'complete')
# test_history_package_inventory: paquete del lector histórico existente
self.assertEqual({p.name for p in history_dir.iterdir()},
                 {'informe.md', 'consulta.json', '.ccr-history.json'})
```

Crear run/history_dir siguiendo los fixtures de `test_review_artifacts.py` y `test_review_history.py`. No admitir archive 7 en el helper nativo. Añadir dos subcasos al test del índice: claves planas `evidence/a→evidence/b→evidence/c` y `evidence/a→evidence/b→evidence/a` devuelven issues, incluso si todas sus fuentes seleccionadas contienen bytes vacíos y digests correctos; el rechazo debe deberse a cadena/ciclo, no a una ruta inválida.

- [ ] **Step 6: documentar sidecar y las tres garantías diferentes**

Actualizar `references/contracts/result-contract.md`: integridad nativa existente, auditoría semántica guiada y consulta HP. El sidecar no amplía los campos exactos del resultado schema 10 ni de HP.

- [ ] **Step 7: ejecutar test_review_reference_index.py**

Run: `python -m unittest discover -s tests -p test_review_reference_index.py -v`

Expected: el módulo termina OK, exit 0; no acredita la suite completa por sí solo.

- [ ] **Step 8: ejecutar test_review_contract.py**

Run: `python -m unittest discover -s tests -p test_review_contract.py -v`

Expected: el módulo termina OK, exit 0; no acredita la suite completa por sí solo.

- [ ] **Step 9: ejecutar test_review_packets.py**

Run: `python -m unittest discover -s tests -p test_review_packets.py -v`

Expected: el módulo termina OK, exit 0; no acredita la suite completa por sí solo.

- [ ] **Step 10: commit**

```powershell
git add -- scripts/review_references.py scripts/review_contract.py scripts/review_packets.py scripts/review_artifacts.py tests/test_review_reference_index.py references/contracts/result-contract.md
git commit -m "feat(evidencia): comprobar referencias e insumos materiales"
```

### Task 4: constructores de preparación y eventos

**Files:**
- Create: `scripts/review_setup.py`
- Modify: `docs/examples/archive8-lifecycle.md`
- Modify: `references/archive/artifacts.md`
- Modify: `references/archive/lifecycle-trace.md`
- Modify: `references/execution/worker-packets.md`
- Test: `tests/test_review_setup.py`

**Interfaces:**

- Consumes: validación de selección de Task 1; validate_preflight/validate_assignment_event de Task 2; validate_reference_index de Task 3; review_trace.event_input existente.
- Produces: `build_profile_selection(raw: dict) -> dict`: selección validada con referencia canónica, sin inventar autoridad.
- Produces: `build_context(manifest: dict, *, execution_plan: list[dict], executors: list[dict], review_inputs: dict, reference_index: dict) -> dict`: exige manifest nativo 8/2; conserva historial exacto, inputs con logical_scope_identity y plan; incluye referencia al sidecar seleccionado. Rechaza reemplazar las identidades ya capturadas.
- Produces: `build_assignment_event(raw: dict, assignment: dict) -> dict`: valida con `review_trace.event_input` y mantiene provider/time observados o null.
- CLI `review_setup.py profile|context|event --input <json> --output <json>`: cada input tiene exactamente `{session, arguments}`; session identifica una sesión de evidencia propia con manifest verificable y arguments contiene los argumentos de la función correspondiente. Rechazar destino existente, enlaces y salida fuera de esa sesión; no invocar prepare/register/dispatch.

- [ ] **Step 1: escribir los tests de autoridad y observaciones preservadas**

Importar `review_setup as setup`, unittest y selection_input/record10. En `SetupTests(unittest.TestCase)`:

```python
def test_authority_is_required_and_execution_facts_are_not_invented(self):
    explicit = selection_input(source='explicit')
    with self.assertRaises(ValueError):
        setup.build_profile_selection(dict(explicit, authority=None))
    self.assertEqual(setup.build_profile_selection(explicit)['authority'],
                     explicit['authority'])
    assignment = record10()['coverage']['execution']['plan'][0]
    event = setup.build_assignment_event({
        'kind': 'discovery', 'status': 'started', 'summary': 'Observed start',
        'actor': {'kind': 'coordinator', 'name': 'coordinator', 'provider_id': None},
        'occurred_at': None, 'evidence': [assignment['reference']]}, assignment)
    self.assertIsNone(event['actor']['provider_id'])
    self.assertIsNone(event['occurred_at'])
    self.assertEqual(event['evidence'], [assignment['reference']])
```

- [ ] **Step 2: ejecutar RED**

Run: `python -m unittest discover -s tests -p test_review_setup.py -v`

Expected: builder ausente o autoridad/observación modificada; no inventar autoridad para hacer pasar el fixture.

- [ ] **Step 3: implementar los tres constructores puros**

Usar las firmas de Produces y los validadores consumidores. build_context copia el historial y las entradas capturadas, incluido logical_scope_identity; identidad contradictoria falla con ValueError. No generar event/provider IDs.

- [ ] **Step 4: implementar CLI y sus tests de salida propia**

Sobre exacto `{session, arguments}`, manifest de sesión verificable y destino nuevo dentro de la sesión. Escribir JSON canónico UTF-8 sin salida parcial; fallo por colisión/enlace/escape deja los bytes iguales. Añadir al fixture de Task 2 las aserciones:

```python
# test_context_preserves_captured_values: resultado de build_context
self.assertEqual(context['profile_history'], manifest['profile_history'])
self.assertEqual(context['review_inputs'], manifest['review_inputs'])
self.assertEqual(context['review_inputs']['logical_scope_identity'],
                 manifest['logical_scope']['identity'])
self.assertEqual(manifest, original_manifest)
# test_cli_output_collision_or_escape: destino existente o ajeno a la sesión
self.assertNotEqual(completed.returncode, 0)
self.assertEqual(after, before)
```

manifest/original_manifest son el manifest del fixture y su deepcopy antes de llamar; context proviene de build_context con su plan/executors/inputs/índice registrados. completed es el CLI de Produces, lanzado sin shell con el sobre serializado en input; before/after usan el inventario de bytes de Task 2.

- [ ] **Step 5: actualizar el ejemplo canónico y los contratos de workers**

Modificar los cuatro documentos de Files: lookup/elección explícita → prepare → construir desde cierre → preflight/register → dispatch observado → record-event. Conservar archive7-lifecycle como histórico; el builder no selecciona latest ni normaliza intents antiguos.

- [ ] **Step 6: ejecutar test_review_setup.py**

Run: `python -m unittest discover -s tests -p test_review_setup.py -v`

Expected: el módulo termina OK, exit 0; no acredita la suite completa por sí solo.

- [ ] **Step 7: ejecutar test_reference_layout.py**

Run: `python -m unittest discover -s tests -p test_reference_layout.py -v`

Expected: el módulo termina OK, exit 0; no acredita la suite completa por sí solo.

- [ ] **Step 8: commit**

```powershell
git add -- scripts/review_setup.py tests/test_review_setup.py docs/examples/archive8-lifecycle.md references/archive/artifacts.md references/archive/lifecycle-trace.md references/execution/worker-packets.md
git commit -m "feat(preparacion): generar candidatos con contratos verificables"
```

### Task 5: recibos de checks y comandos reproducibles

**Files:**
- Create: `scripts/review_check_receipts.py`
- Modify: `scripts/review_check_provenance.py:37`
- Modify: `scripts/review_preflight.py` — módulo de Task 2
- Modify: `scripts/review_artifacts.py:3891`
- Modify: `references/contracts/result-contract.md`
- Modify: `references/execution/workspaces.md`
- Test: `tests/test_review_check_receipts.py`

**Interfaces:**

- Consumes: ReferenceIssue y resolución de Task 1; `validate_check_sources(record, executors)` existente; guards actuales de workspace/ownership antes de ejecutar.
- Produces: `validate_receipt(receipt: dict, sources: dict[str, bytes], *, check: dict, executors: list[dict]) -> list[ReferenceIssue]`: campos exactos del spec §9.2, hashes y vinculación de revisión/executor.
- Produces: `capture_check(*, check_id: str, argv: list[str], cwd: str, revision: str, executor: str, output_dir: str) -> dict`: ejecuta sólo la orden indicada y produce el recibo con observaciones reales; output_dir debe ser nuevo y propio.
- CLI `review_check_receipts.py run --request <json> --output-dir <owned-new-dir>`: request contiene check_id/argv/cwd/revision/executor; salida no mezcla exit del helper con exit del check. La validación de permisos/ownership y workspace precede a iniciar proceso.

- [ ] **Step 1: escribir el test de log vacío y exit observado**

Importar `review_check_receipts as receipts` y hashlib en `CheckReceiptTests(unittest.TestCase)`:

```python
def test_empty_streams_need_observed_exit(self):
    empty = hashlib.sha256(b'').hexdigest()
    stream = {'reference': 'evidence/C001-out.log', 'sha256': empty, 'bytes': 0}
    executor = {'executor': 'X1', 'revision': 'head-456', 'snapshot': None}
    check = {'id': 'C001', 'revision': 'head-456', 'status': 'passed',
             'execution': {'kind': 'local', 'executor': 'X1'}}
    receipt = {'schema_version': 1, 'check_id': 'C001', 'argv': ['python', '-V'],
        'cwd': '/owned/executor', 'revision': 'head-456', 'executor': 'X1',
        'started_at': '2026-10-19T18:00:00+00:00',
        'finished_at': '2026-10-19T18:00:01+00:00', 'exit_code': 0,
        'stdout': stream, 'stderr': dict(stream, reference='evidence/C001-err.log')}
    sources = {'evidence/C001-out.log': b'', 'evidence/C001-err.log': b''}
    self.assertEqual(receipts.validate_receipt(receipt, sources,
        check=check, executors=[executor]), [])
    incomplete = dict(receipt, exit_code=None, finished_at=None)
    issues = receipts.validate_receipt(incomplete, sources,
        check=check, executors=[executor])
    self.assertIn('invalid_receipt', {i['code'] for i in issues})
```

Este test valida contenido y vínculos puros. No prueba ownership del cwd: captura y retención deben verificarlo con el workspace registrado, sin probes de filesystem dentro de validate_receipt.

- [ ] **Step 2: ejecutar RED**

Run: `python -m unittest discover -s tests -p test_review_check_receipts.py -v`

Expected: módulo/interfaz ausente o aceptación incorrecta del recibo incompleto. Un comando silencioso no falla sólo por producir cero bytes.

- [ ] **Step 3: implementar validate_receipt**

Validar campos exactos, hashes/bytes, timestamps ordenados y vínculo check/executor/revision. exit_code null no acredita passed/failed. No ejecutar procesos ni cambiar check.execution.

- [ ] **Step 4: implementar capture_check y su CLI**

Comprobar ownership/workspace y salida nueva antes de subprocess con argv y shell=False; conservar streams y tiempos reales. No inferir intérpretes ni instalar dependencias. Un comando fallido conserva exit_code no cero aunque se haya escrito el recibo.

- [ ] **Step 5: añadir test de argv literal y conservación del primer intento**

Crear executor propio temporal con `review_workspace.prepare` y registrarlo siguiendo `test_review_check_provenance.py`. Lanzar capture_check con argv exacto `[sys.executable, '-c', 'import json,sys; print(json.dumps(sys.argv[1:]))', 'a b', '$value', '`tick`']`. El programa sólo imprime argumentos. Las aserciones decisivas son:

```python
self.assertEqual(receipt['argv'], argv)
self.assertEqual(receipt['exit_code'], 0)
self.assertEqual(json.loads(stdout_path.read_text(encoding='utf-8')),
                 ['a b', '$value', '`tick`'])
self.assertEqual(receipt['stdout']['sha256'],
                 hashlib.sha256(stdout_path.read_bytes()).hexdigest())
with self.assertRaises((ValueError, OSError)):
    receipts.capture_check(**same_request)
self.assertEqual(after, before)
```

receipt es la primera salida de capture_check; stdout_path es el archivo de stdout identificado por ella; same_request contiene los mismos argumentos/output_dir; before/after son inventarios de bytes del output_dir. Nombrar el método `test_receipt_preserves_literal_argv_and_previous_attempt`. Añadir subcasos de bytes alterados, executor/revisión distintos y validate sin subprocess: invalid_receipt y cero llamadas a procesos.

- [ ] **Step 6: integrar y documentar recibos**

Conectar validación en preflight/retención; check.reference apunta al recibo, logs seleccionados aparte. Mostrar comando desde argv exacto. Documentar intérprete explícito para entrypoints shell y retries con nuevas rutas. No modificar review_runner.py ni activar mediciones.

- [ ] **Step 7: ejecutar test_review_check_receipts.py**

Run: `python -m unittest discover -s tests -p test_review_check_receipts.py -v`

Expected: el módulo termina OK, exit 0; no acredita la suite completa por sí solo.

- [ ] **Step 8: ejecutar test_review_check_provenance.py**

Run: `python -m unittest discover -s tests -p test_review_check_provenance.py -v`

Expected: el módulo termina OK, exit 0; no acredita la suite completa por sí solo.

- [ ] **Step 9: commit**

```powershell
git add -- scripts/review_check_receipts.py scripts/review_check_provenance.py scripts/review_preflight.py scripts/review_artifacts.py tests/test_review_check_receipts.py references/contracts/result-contract.md references/execution/workspaces.md
git commit -m "feat(validacion): conservar recibos reproducibles de checks"
```

### Task 6: proyección pública de checks y borrador canónico (R7)

**Files:**
- Create: `scripts/review_comment.py`
- Modify: `scripts/review_publication.py:11` — añadir proyección de checks junto a limitaciones
- Modify: `scripts/review_contract.py:703` — render por audiencia
- Modify: `scripts/review_contract.py:786` — filas de validación
- Modify: `scripts/review_contract.py:934` — argumento CLI separado
- Modify: `references/reporting/report-format.md`
- Modify: `references/reporting/publication.md`
- Create: `tests/publication_fixtures.py`
- Test: `tests/test_review_comment.py`
- Test: `tests/test_review_contract.py`
- Test: `tests/test_review_publication_policy.py`
- Test: `tests/test_review_presentation.py`

**Interfaces:**
- Consumes: `publication_digest(record) -> str`, `public_limitations(record, classification=None) -> list[dict]` y `public_url(value) -> bool` existentes; registro/recibos de Tasks 3–5 sin alterarlos.
- Produces: `public_checks(record: dict, classification: dict | None = None) -> list[dict]` en review_publication.py, con filas exactas del spec §11.2. Error de contrato: ValueError.
- Produces: `render(record, audience='user', publication_context=None, *, check_publication_context=None) -> str`, conservando los argumentos anteriores y añadiendo sólo el keyword nuevo. render-comment recibe `--check-publication-context`; no reutiliza el override legacy de limitaciones.
- Produces: `prepare_public_comment(record: dict, *, publication_context: dict | None = None, check_publication_context: dict | None = None) -> dict` en review_comment.py; borrador schema 1 exacto del spec §11.3.
- Produces: `verify_public_comment(record: dict, draft: dict, body: str, *, remote: bool = False) -> dict` en review_comment.py. Retorna `{verified: True, source_sha256: str, body_sha256: str}`; mismatch lanza ValueError, no retorna publicado.
- Produces: CLI `prepare --input <record> --session <owned-session> --output <draft.json> [--publication-context <json>] [--check-publication-context <json>]` y `verify --input <record> --draft <draft.json> --body <body.md> [--remote]`. Exit 0 preparado/verificado; 1 contrato/mismatch; 2 acceso/parseo. Sin cliente remoto.
- Produces (test fixture): `publication_record() -> dict` y `check_classification(record: dict) -> dict` en tests/publication_fixtures.py. No importar clases de tests para construir datos compartidos.

- [ ] **Step 1: escribir fixture y tests de la fuga reproducida en MR 1021 (RF4)**

publication_record parte de record10() y crea C001 passed/head, C002 failed/product/head y C003 passed/base; checks locales sintéticos X1/X2, con los campos exactos actuales. reference son `evidence/scheduling.log`, `evidence/repro-head.log`, `evidence/repro-base.log`; evidence contiene sólo resultados de producto. C003 conserva `rerun_reason='CS2012; log evidence/attempt1.log; reintento -m:1'`, command `dotnet test -m:1` y revision=scope.base. Ningún comando se ejecuta.

check_classification usa publication_digest(record) y una fila por check con exactamente `{id, evidence, reuse_reason, rerun_reason, reference}`: evidencia de producto original, reference=null, reuse_reason=null y rerun_reason=null porque ese fixture identifica un reintento de entorno no material. Importar `review_contract as contract` y `public_checks` de review_publication en los tests de renderer/política; el fixture importa record10 y publication_digest. No usar los bytes del MR real.

```python
def test_public_checks_do_not_publish_internal_execution_data(self):
    record = publication_record()
    original = copy.deepcopy(record)
    context = check_classification(record)
    public = contract.render(record, audience='comment',
                             check_publication_context=context)
    private = contract.render(record, audience='user')
    for internal in ('evidence/', 'CS2012', '-m:1'):
        self.assertNotIn(internal, public)
        self.assertIn(internal, private)
    rows = public_checks(record, context)
    self.assertEqual(rows[1]['status'], 'failed')
    self.assertEqual(rows[1]['failure_kind'], 'product')
    self.assertEqual(rows[2]['revision'], record['scope']['base'])
    self.assertEqual(record, original)
```

Añadir test sin contexto sobre un check sin motivos libres, pero con reference relativa: el renderer debe omitir la referencia sin requerir clasificación innecesaria. Reuso sustantivo mantiene su revisión original y resumen público; actualizar el test existente de reutilización para suministrar ese contexto cuando corresponda.

- [ ] **Step 2: ejecutar RED del renderer/política**

Run: `python -m unittest discover -s tests -p test_review_publication_policy.py -v`

Expected: interfaz/keyword nuevo ausente o exposición de referencias/motivo interno. No borrar reference/rerun_reason del fixture para hacerlo pasar.

- [ ] **Step 3: implementar public_checks y conectar render-comment**

Proyectar por campos antes de construir Markdown. Bloquear digest incorrecto, filas faltantes/duplicadas, campos extra que intenten cambiar status/revision y URL nueva no procedente del check. Referencias locales siempre privadas. Razones libres requieren clasificación explícita; no inferir materialidad por blacklist ni aplicar reemplazos al cuerpo final. La evidencia/validación material conserva su impacto público. Mantener public_projection como defensa existente, sin convertirla en otro saneador de texto.

- [ ] **Step 4: escribir tests de borrador reproducible y retoque posterior**

Importar prepare_public_comment/verify_public_comment de review_comment y el fixture. En tests/test_review_comment.py:

```python
def test_draft_matches_render_and_rejects_manual_edit(self):
    record = publication_record()
    original = copy.deepcopy(record)
    context = check_classification(record)
    draft = prepare_public_comment(record, check_publication_context=context)
    self.assertEqual(draft, prepare_public_comment(record,
                     check_publication_context=context))
    self.assertEqual(draft['body'], contract.render(record, audience='comment',
                     check_publication_context=context))
    self.assertEqual(draft['body_sha256'],
                     hashlib.sha256(draft['body'].encode('utf-8')).hexdigest())
    self.assertTrue(verify_public_comment(record, draft, draft['body'])['verified'])
    with self.assertRaisesRegex(ValueError, 'body_mismatch'):
        verify_public_comment(record, draft, draft['body'] + '\nRetoque manual')
    self.assertEqual(record, original)

def test_crlf_is_only_allowed_for_remote_transport(self):
    record = publication_record()
    draft = prepare_public_comment(record,
                    check_publication_context=check_classification(record))
    remote_body = draft['body'].replace('\n', '\r\n')
    with self.assertRaisesRegex(ValueError, 'body_mismatch'):
        verify_public_comment(record, draft, remote_body)
    self.assertTrue(verify_public_comment(record, draft,
                    remote_body, remote=True)['verified'])
```

Añadir subcasos que cambian source_sha256, una fila de contexto, status añadido y body_sha256. Cada uno falla sin modificar record/draft ni empezar un envío. Un ajuste editorial se realiza en el contexto público de un nuevo borrador, nunca mutando el borrador vinculado por hashes o el archive.

- [ ] **Step 5: ejecutar RED del borrador**

Run: `python -m unittest discover -s tests -p test_review_comment.py -v`

Expected: módulo aún ausente o diferencia aceptada incorrectamente. Los tests son puros y no envían comentarios.

- [ ] **Step 6: implementar preparación/verificación canónica y CLI local**

Implementar las firmas de Produces: verificar source_sha256 canónico, forma exacta del borrador, contextos y re-render independiente antes de comparar el cuerpo. Usar UTF-8 exacto antes de envío; sólo remote=True permite CRLF→LF, nunca strip, traducción, espacios ni reemplazos. ValueError incluye body_mismatch para diferencia de cuerpo; source_mismatch para fuente distinta.

El CLI prepare escribe sólo en sesión propia verificada/destino nuevo usando los guards de Task 4; verify es read-only y nunca crea locks del archivo. No añadir una herramienta de publicación. Si hay resultado de envío incierto o cuerpo remoto distinto, el flujo inspecciona la nota existente antes de reintentar.

- [ ] **Step 7: documentar la única pasada editorial antes del render**

Actualizar report-format.md y publication.md: redactar/validar campos públicos → render canónico → verificar cuerpo enviado → leer/verificar cuerpo remoto → registrar publicación observada. Si falla la redacción, ajustar contexto público y re-renderizar. Conservar freshness, autorización y post-close separado; no repetir code review por un retoque editorial. No recortar Markdown ni borrar trazabilidad para satisfacer el comentario público.

- [ ] **Step 8: ejecutar GREEN de publicación**

Run: `python -m unittest discover -s tests -p test_review_publication_policy.py -v`

Expected: módulo OK, exit 0; incertidumbres/materialidad y clasificación legacy de limitaciones mantienen sus gates.

- [ ] **Step 9: ejecutar GREEN del borrador**

Run: `python -m unittest discover -s tests -p test_review_comment.py -v`

Expected: módulo OK, exit 0; mismatches no se presentan como publicados y no producen cambios ni envíos.

- [ ] **Step 10: ejecutar regresión de formato/renderer**

Run: `python -m unittest discover -s tests -p test_review_contract.py -v`

Expected: módulo OK, exit 0; orden fijo, IDs/conteos, revisión base y evidencia de producto siguen visibles. La suite final de Task 8 incluye presentation e integración.

- [ ] **Step 11: commit**

```powershell
git add -- scripts/review_publication.py scripts/review_contract.py scripts/review_comment.py tests/publication_fixtures.py tests/test_review_comment.py tests/test_review_contract.py tests/test_review_publication_policy.py tests/test_review_presentation.py references/reporting/report-format.md references/reporting/publication.md
git commit -m "fix(publicacion): generar comentarios canónicos sin retoques manuales"
```

### Task 7: registrar el modelo por actividad cuando sea observable (R8)

**Files:**
- Create: `scripts/review_model_usage.py`
- Modify: `scripts/review_setup.py` — integración opcional posterior a Task 4
- Modify: `scripts/review_artifacts.py:3891` — validar evidencia seleccionada, sin alterar el header schema 8
- Modify: `references/archive/artifacts.md` — vínculo del registro de modelos al harness
- Modify: `references/archive/lifecycle-trace.md` — observaciones pasivas y límites de identidad
- Modify: `references/execution/worker-packets.md` — metadata ya expuesta, sin campos obligatorios nuevos
- Test: `tests/test_review_model_usage.py`
- Test: `tests/test_review_harness.py`

**Interfaces:**
- Consumes: ReferenceIssue de Task 1; contexto/captura de Task 4 y selección de evidencia de artifacts existentes. Sólo metadata ya suministrada por dispatch, respuesta o runner utilizado; no iniciar consultas para obtenerla.
- Produces: `normalize_model_observation(raw: dict) -> dict`. raw contiene los campos de una entrada del spec §12 salvo id/status; la función valida y calcula status sin inferir un modelo. Error de forma: ValueError.
- Produces: `append_model_observation(ledger: dict | None, observation: dict, *, review_id: str, harness_id: str | None) -> dict`. Recibe la observación normalizada sin id, conserva entradas previas y asigna M0001… como ID administrativo. No modifica sus argumentos ni cuenta invocaciones a partir de las filas.
- Produces: `validate_model_usage(ledger: dict, *, review_id: str, harness_id: str | None) -> list[ReferenceIssue]`. Valida schema, vínculo, filas y límites 256 entradas/256 KiB; no prueba liveness ni identidad del modelo mediante sondeos.
- Produces: `observation_from_metadata(metadata: dict, *, actor: dict, phase: str, activity: str, assignment_id: str | None = None, check_id: str | None = None) -> dict`. model del run.json actual se trata como configured_model; observed_model sólo se acepta con model_source explícito platform/adapter_observed. occurred_at no se inventa.
- Produces: sidecar privado `evidence/model-usage.json`, seleccionado por checkpoint/retain e identificado por context.model_usage_reference y cierre.hashes, sin campos nuevos en resultado/trace/harness catalog.

- [ ] **Step 1: escribir tests de modelo configurado, observado y ausente**

Importar `review_model_usage as models` y copy. En ModelUsageTests(unittest.TestCase):

```python
def test_runner_argument_does_not_prove_actual_model(self):
    actor = {'kind': 'agent', 'name': 'reviewer', 'provider_id': 'ctx-1'}
    item = models.observation_from_metadata({'model': 'configured-A'},
        actor=actor, phase='discovery', activity='discovery', assignment_id='D1')
    self.assertEqual(item['configured_model'], 'configured-A')
    self.assertIsNone(item['observed_model'])
    self.assertEqual(item['status'], 'configured_only')
    self.assertEqual(item['actor']['provider_id'], 'ctx-1')

def test_missing_model_is_unknown_without_extra_work(self):
    item = models.observation_from_metadata({}, actor={
        'kind': 'coordinator', 'name': 'coordinator', 'provider_id': None},
        phase='report', activity='reporting')
    self.assertEqual(item['status'], 'unknown')
    self.assertIsNone(item['observed_model'])
    self.assertIsNone(item['configured_model'])

def test_model_switch_preserves_each_observation_and_assignment(self):
    actor = {'kind': 'agent', 'name': 'reviewer', 'provider_id': 'ctx-1'}
    first = models.observation_from_metadata({
        'observed_model': 'observed-A', 'model_source': {
            'kind': 'platform', 'reference': 'call-1'}}, actor=actor,
        phase='discovery', activity='discovery', assignment_id='D1')
    second = models.observation_from_metadata({
        'observed_model': 'observed-B', 'model_source': {
            'kind': 'platform', 'reference': 'call-2'}}, actor=actor,
        phase='verification', activity='verification', assignment_id='V1')
    ledger = models.append_model_observation(None, first,
        review_id='CR-' + 'a'*20, harness_id='codex-desktop')
    before = copy.deepcopy(ledger)
    updated = models.append_model_observation(ledger, second,
        review_id=ledger['review_id'], harness_id=ledger['harness_id'])
    self.assertEqual(ledger, before)
    self.assertEqual(updated['entries'][:-1], before['entries'])
    self.assertEqual([e['observed_model'] for e in updated['entries']],
                     ['observed-A', 'observed-B'])
    self.assertEqual([e['assignment_id'] for e in updated['entries']], ['D1', 'V1'])
```

configured-A/observed-A/B son etiquetas sintéticas, no elecciones reales de modelo. Añadir un proceso de tests con source.kind=not_applicable y ambos modelos null: status not_applicable, sin heredar el modelo del actor que escribió la reproducción.

- [ ] **Step 2: ejecutar RED**

Run: `python -m unittest discover -s tests -p test_review_model_usage.py -v`

Expected: módulo nuevo ausente o model del argumento promovido incorrectamente a observado. No añadir datos de configuración para ocultar el caso unknown.

- [ ] **Step 3: implementar normalización y acumulación puras**

Implementar las cuatro firmas de Produces con las formas exactas del spec §12. Sólo platform/adapter_observed con referencia verificable acredita observed_model. Una configuración distinta del observado se conserva en ambos campos; no demuestra conflicto por sí sola. Observaciones incompatibles para el mismo source.reference/actor/contexto se conservan con status conflict en la nueva fila, sin reescribir la anterior. Ante un límite, el caller conserva el prefijo válido y agrega captura incompleta en context.model_usage_diagnostics (32 textos/500 caracteres); no convertirlo en fallo del producto ni iniciar trabajo para rellenar lo desconocido.

- [ ] **Step 4: integrar el sidecar en la evidencia del flujo guiado**

Añadir observación inicial del coordinador y posteriores observaciones sólo con información ya disponible. Acumular en la sesión propia, seleccionar el estado del registro en checkpoint/retain y enlazarlo desde context.model_usage_reference. No agregarlo a review_inputs.sources ni al catálogo del harness: es metadata de ejecución acumulable. No reinterpretar ni cambiar provider IDs, tiempos de trace ni el campo model legacy del runner.

Para un run ya cerrado o una publicación posterior, usar la operación separada vinculada al review, sin rellenar el archive anterior. El registro ausente sigue permitido en runs existentes; un paquete HP no adquiere este sidecar. La identidad de modelo no afecta las obligaciones de independencia del perfil ni llega al comentario público.

- [ ] **Step 5: añadir aserciones de vínculo, límites y ausencia de sondeos**

En fixtures temporales, conservar bytes de manifest/catalog/trace antes y después; validar sidecar con review_id/harness_id correctos y luego con IDs distintos. Las aserciones decisivas son:

```python
self.assertEqual(models.validate_model_usage(ledger,
    review_id=ledger['review_id'], harness_id=ledger['harness_id']), [])
self.assertTrue(models.validate_model_usage(ledger,
    review_id='CR-' + 'b'*20, harness_id=ledger['harness_id']))
self.assertEqual(after_catalog_bytes, before_catalog_bytes)
self.assertEqual(after_trace_bytes, before_trace_bytes)
self.assertNotIn('model-usage', public_comment)
```

ledger es el registro creado por el test anterior; public_comment es render(comment) del fixture de Task 6, sin mezclar el sidecar privado con su contexto público. Añadir pruebas con 257 entradas, >256 KiB y modelos >200 caracteres: diagnóstico acotado sin nueva invocación. En la llamada pura con metadata vacía, mockear subprocess.run y afirmar assert_not_called(); revisar que el módulo no abra red ni lea historiales por su cuenta.

- [ ] **Step 6: documentar procedencia y datos desconocidos**

Actualizar los tres documentos de Files con distinción harness/model/provider_id, configured_only frente a observed, vínculo por asignación/fase y dato ausente no bloqueante. Conservar el registro literal suministrado y su fuente; no presentar argumentos de configuración como prueba del modelo efectivo ni calcular costes a partir de ellos.

- [ ] **Step 7: ejecutar GREEN del registro de modelos**

Run: `python -m unittest discover -s tests -p test_review_model_usage.py -v`

Expected: módulo OK, exit 0; cambios de modelo conservados por actividad y ausencia sin sondeos/reintentos.

- [ ] **Step 8: ejecutar regresión del harness**

Run: `python -m unittest discover -s tests -p test_review_harness.py -v`

Expected: módulo OK, exit 0; no hay modelos convertidos en alias del harness ni cambios en su catálogo/identidad.

- [ ] **Step 9: commit**

```powershell
git add -- scripts/review_model_usage.py scripts/review_setup.py scripts/review_artifacts.py tests/test_review_model_usage.py tests/test_review_harness.py references/archive/artifacts.md references/archive/lifecycle-trace.md references/execution/worker-packets.md
git commit -m "feat(trazabilidad): registrar modelo observado por actividad"
```

### Task 8: continuidad segura, estado operativo y regresión integrada

**Files:**
- Modify: `scripts/review_recovery.py:486` — inspect y nuevas proyecciones puras
- Modify: `scripts/review_artifacts.py:4117` — CLI consumidor
- Modify: `references/archive/recovery.md`
- Modify: `references/archive/history.md`
- Modify: `references/workflow/reading-strategy.md`
- Modify: `references/reporting/publication.md`
- Modify: `SKILL.md`
- Modify: `docs/usage.md`
- Modify: `CHANGELOG.md`
- Create: `docs/validation/2026-10-19-review-execution-consistency.md`
- Test: `tests/test_review_operational_summary.py`

**Interfaces:**

- Consumes: validate_preflight de Task 2, resultados/registros de Tasks 3–5, borrador/verificación de Task 6, registro privado de modelos de Task 7 e inspect_run/select_latest/restart v2 existentes. Un draft verificado no es un evento de publicación; modelo desconocido no altera el veredicto ni dispara recuperación.
- Produces: `operational_summary(manifest: dict, events: list[dict], record: dict | None) -> dict`: sólo manifest nativo 8/2; exactos `disposition`, `phase`, `successor`, `cleanup`, `publication`; publicación contiene `status`, `source`, `occurred_at` y `reason`, usando null cuando no hay observación. No infiere links desde prosa.
- Produces: `continuation_decision(manifest: dict, *, input_appraisal: dict, pending_operation: dict | None, candidate_issues: list[dict]) -> dict`: `{action, reason, requires_authority, new_work}`; los dos últimos son bool. Actions `rebuild_candidate|recover|resume|restart|show_history|preserve`; diagnóstico, no ejecución.
- `inspect_run` añade `operational_summary` sólo después de verificar layout nativo, sin cambiar el significado de campos actuales. Un origen unsupported_layout conserva su diagnóstico actual; no pasa a operational_summary ni recibe resume/restart/ready. La matriz de continuidad es la del spec §7; las autoridades y el restart durable siguen a cargo de las operaciones existentes. `select_latest` y review_history.py conservan sus interfaces y garantías.

- [ ] **Step 1: escribir tests de candidato regenerable y transferencia bloqueada (RF5)**

Importar `review_recovery as recovery` y copy en `OperationalSummaryTests(unittest.TestCase)`:

```python
def test_unknown_inputs_with_pending_transfer_preserve_state(self):
    manifest = {'schema_version': 8, 'layout_version': 2,
                'state': 'processing', 'operation': {'disposition': 'open'}}
    before = copy.deepcopy(manifest)
    decision = recovery.continuation_decision(manifest,
        input_appraisal={'applicability': 'unknown'},
        pending_operation={'kind': 'transfer', 'can_complete': False},
        candidate_issues=[])
    self.assertEqual(decision['action'], 'preserve')
    self.assertFalse(decision['new_work'])
    self.assertEqual(manifest, before)

def test_candidate_rebuild_requires_no_new_review(self):
    manifest = {'schema_version': 8, 'layout_version': 2,
                'state': 'processing', 'operation': {'disposition': 'open'}}
    decision = recovery.continuation_decision(manifest,
        input_appraisal={'applicability': 'applicable'}, pending_operation=None,
        candidate_issues=[{'code': 'missing_source', 'field': 'candidate.reference',
            'reference': 'evidence/result.json', 'message': 'Candidate incomplete',
            'expected': 'Regenerate the unretained candidate'}])
    self.assertEqual(decision['action'], 'rebuild_candidate')
    self.assertFalse(decision['new_work'])
```

Estos dicts prueban clasificación pura, no integridad durable. La capa IO verifica el manifest completo y su ownership antes de invocarla. Una identidad capturada inválida no se representa como candidate.reference regenerable.

- [ ] **Step 2: ejecutar RED**

Run: `python -m unittest discover -s tests -p test_review_operational_summary.py -v`

Expected: interfaz ausente o decisión diferente de preserve/rebuild_candidate. No forzar ready sobre una transferencia incompletable.

- [ ] **Step 3: implementar continuation_decision en `review_recovery.py`**

Aplicar spec §7: preservación para transacción bloqueada/frescura desconocida, regeneración sólo de candidatos no retenidos con inputs idénticos y recover/resume/restart delegados al protocolo existente. No iniciar agentes ni crear un sucesor desde esta función.

- [ ] **Step 4: implementar operational_summary e integrarlo con inspect**

Derivar los cinco campos de cierre/traza verificados. No inferir successor desde prosa ni liveness desde processing. unsupported_layout conserva su diagnóstico antes de lectura operativa; no cambiar select_latest ni el lector histórico.

- [ ] **Step 5: añadir tests de snapshot, historia y límite de continuidad**

En el fixture temporal de recovery, retener record10, añadir un authorized-publication con autoridad explícita sintética y conservar la traza observada. Nombrar los tests `test_publication_after_retain_preserves_snapshot`, `test_historical_source_never_gets_native_summary` y `test_complete_source_never_resumes`. Sus aserciones son:

```python
self.assertEqual(summary['publication']['status'], 'published')
self.assertEqual(summary['publication']['source'], publication_event['event_id'])
self.assertEqual(summary['publication']['occurred_at'], publication_event['occurred_at'])
self.assertEqual(record['resources']['publication'], original_publication)
self.assertEqual(after_snapshot_bytes, before_snapshot_bytes)
# Histórico creado mediante historical_prepare del fixture existente.
self.assertEqual(inspected['integrity']['status'], 'unsupported_layout')
self.assertNotIn('operational_summary', inspected)
# Origen completo: no volver a un candidato ni a procesamiento.
self.assertNotIn(decision['action'], {'resume', 'rebuild_candidate'})
```

summary es operational_summary sobre el manifest y los eventos verificados del fixture; publication_event es la fila real de su traza, con event_id/occurred_at observados; record es el JSON retenido antes de ese evento, original_publication su valor previo y before/after_snapshot_bytes sus bytes. inspected procede de inspect_run histórico y decision de continuation_decision sobre un manifest completo. No cambiar metadata para fabricar esa observación.

- [ ] **Step 6: actualizar el flujo operativo y changelog**

Actualizar los siete documentos operativos de Files conservando lookup/elección explícita de rerun/latest y subaspectos ABCDE; insertar preflight antes del primer dispatch. Documentar restart nativo y previous-run sólo con origen nativo válido; HP no es lineage operativo. Changelog registra el comportamiento sin inventar una release publicada.

- [ ] **Step 7: ejecutar GREEN y regresión integrada sobre el estado final**

Run: `python -m unittest discover -s tests -v`

Expected: suite completa `OK`, exit 0; descubrir los ocho módulos nuevos más archive8/layout_v2/history/latest/restart_v2. Estos módulos existentes deben conservar empate/barrido incompleto de latest y bytes/reserva del productor v2 previo. Una selección parcial o interrumpida no acredita suite completa. No repetir primero todos los módulos individualmente: repetir sólo por cambio, fallo o preocupación nueva.

- [ ] **Step 8: registrar evidencia de implementación realmente observada**

Crear el documento de validación de Files con base/HEAD, comandos, exit codes, duraciones observadas, resultados RED/GREEN, omisiones y límites de plataforma. Relacionar las regresiones sintéticas de MR 781/PR 1/MR 47 con los tests previos de plan/perfil/alias y MR 1021 con la proyección/borrador de Task 6; registrar exactamente un run y cero dispatches adicionales al regenerar un candidato o ajustar el contexto público. No declarar comprobaciones futuras como realizadas.

- [ ] **Step 9: comprobar whitespace final**

Run: `git diff --check`

Expected: sin salida de errores y exit 0.

- [ ] **Step 10: ejecutar test_reference_layout.py**

Run: `python -m unittest discover -s tests -p test_reference_layout.py -v`

Expected: el módulo termina OK, exit 0; no acredita la suite completa por sí solo.

- [ ] **Step 11: commit de integración y evidencia**

```powershell
git add -- scripts/review_recovery.py scripts/review_artifacts.py tests/test_review_operational_summary.py references/archive/recovery.md references/archive/history.md references/workflow/reading-strategy.md references/reporting/publication.md SKILL.md docs/usage.md CHANGELOG.md docs/validation/2026-10-19-review-execution-consistency.md
git commit -m "feat(continuidad): proyectar estado operativo sin repetir revisiones"
```

## Matriz de trazabilidad

| Requisito del spec | Task(s) | Resultado verificable |
|---|---|---|
| R1, §5 | 1–2 | URL, fragmento incorrecto y ruta anidada rechazados antes del trabajo |
| R2, §6 | 2 y 4 | Plan capturado y evento asociado, incluso con evidencia omitida |
| R3, §7 | 2 y 8 | Corregir candidato no crea sucesor; identidad inválida conserva restart |
| R4, §8 | 1 y 3 | C004 y paths resueltos, aliases acotados y paquetes originales intactos |
| R5, §9.1 | 3–4 | Descripción material seleccionada o unverified con limitación |
| R5, §9.2 | 5 | argv/exit/logs verificables, sin éxito inferido ni shell implícita |
| R6, §10 | 8 | Sustitución estructurada y snapshot separado del estado posterior |
| R7, §11 | 6 y 8 | Checks públicos sin procedencia interna, fuente privada intacta y cuerpo canónico verificado antes/después del envío |
| R8, §12 | 7 y 8 | Modelo configurado/observado por actividad, null cuando no se expone y vínculo privado al harness sin sondeos |
| Compatibilidad, §2.1/§3/§13 | 1–8 | Operación sólo 8/2, historia pura/HP sin migración, read-only sin locks, identidad lógica y replay v2 conservados |
| Consulta existente, §2.1/§10 | 4 y 8 | Lookup/rerun/latest explícitos y rechazos de empate/barrido incompleto sin selector nuevo |

## Revisión del plan y entrega

Comprobar antes de ejecutar: nombres y tipos de interfaces coinciden entre tasks; cada fila de la matriz tiene regresión; ningún paso exige resultados futuros como parte de prepare; no se añade un mutador de identidad ni una migración encubierta. Se reutilizan layout/latest/historia/replay de 2.13.0 y no se propone reabrir archives schema 7. Los módulos nuevos de preflight/referencias son puros; sólo la captura de checks ejecuta la orden explícitamente autorizada.

Las tasks siguen sin marcar porque todavía no se implementan. La ejecución requiere revisión del plan y elección de método; no se presupone ejecución con subagentes.

## Execution Handoff

- **Subagent-driven:** implementador y revisor frescos por tarea, con revisión de rama al final; más contextos e independencia por task.
- **Native:** ejecución inline de las ocho tareas, seguida de una revisión independiente de la rama; conserva las interfaces compartidas en el mismo contexto.

Se recomienda Native por las dependencias secuenciales de estas ocho tareas. Antes de implementar, solicitar revisión del plan y elección explícita de método. No ejecutar push, PR, publicación, merge ni release como parte de esta preparación.
