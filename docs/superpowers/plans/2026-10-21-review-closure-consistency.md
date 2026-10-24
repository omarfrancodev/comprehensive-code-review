# Review Closure Consistency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** detectar fuentes y despachos incompletos antes del trabajo, conservar la selección al revalidar un archivo retenido y corregir identidad omitida sin repetir eventos de ejecución.

**Architecture:** respetar la separación `ccr.contracts` / `ccr.workflow` / `ccr.archive` / `ccr.execution` de CCR 3.0.0 y extender los validadores puros existentes para compartir selección y captura de fuentes, y añadir un módulo puro para identidad/anotaciones de dispatch. Los builders y mutadores existentes consumen esas reglas; los locks, transacciones, ownership y cleanup siguen bajo su autoridad actual.

**Tech Stack:** Python 3.10+, biblioteca estándar, unittest, Git y Markdown.

**Spec:** [Consistencia de fuentes, despachos y cierre](../specs/2026-10-21-review-closure-consistency-design.md).
**Estado:** implementación terminada y pruebas focalizadas aprobadas. La suite completa quedó inconclusa; el detalle está en el informe de validación.

## Global Constraints

- Python 3.10+ y biblioteca estándar; no añadir dependencias de ejecución.
- Respetar el paquete `scripts/ccr`, las 12 áreas CLI existentes y la entrada `python <skill>/scripts AREA SUBCOMMAND`; no restaurar scripts `review_*.py` ni facades agregadas.
- Mantener contratos puros sin IO, sin imports de `ccr.cli` desde módulos de implementación y sin ciclos; `archive.resources` coordina cleanup y `execution.workspaces` las operaciones físicas. Documentar cada módulo nuevo en `scripts/README.md`.
- Mantener archive schema 8/layout 2, final schema 10 y trace schema 1; no migrar ni reescribir historia.
- Los runs completos son inmutables; ningún cambio de este trabajo modifica sus bytes.
- No inferir identidades, timestamps, modelos, independencia ni resultados a partir de nombres de archivos, briefs o resúmenes.
- Las lecturas se limitan a fuentes explícitamente seleccionadas o declaradas en el inventario de hashes del run exacto; no recorrer otros archives, historias del proveedor ni árboles completos.
- Mantener los límites existentes de 64 fuentes/archivos seleccionados y 64 MiB agregados, así como los guards de rutas, links, ownership, locks y transacciones.
- Un gate de retención fallido conserva los recursos; cleanup y close siguen requiriendo observación y recibos válidos.
- No modificar el run auditado, sus workspaces, el MR, el visor independiente ni las skills globales de Superpowers.
- Registrar modelos sólo si la ejecución ya expone metadata; su ausencia no bloquea una revisión ni origina probes o despachos adicionales.

## Review Focus

1. Un archivo existente pero sin hash seleccionado debe seguir rechazado, mientras un alias de un salto sí resuelve su destino seleccionado; prueba en Tasks 1 y 3.
2. Un run iniciado con descripción unverified y mapa inicial incompleto debe poder verificar evidencia ya retenida sin alterar su snapshot; prueba en Task 3.
3. El límite de fuentes y la captura desconocida no deben convertirse en completeness=true ni perderse al pasar por CLI; prueba en Task 2.
4. Una identidad anotada después del resultado debe conservar el orden del despacho original; un target ajeno, inexistente o con identidad previa debe rechazarse; prueba en Task 4.
5. Un replay de anotación o un intento sobre run completo no debe añadir eventos, disparar procesos ni modificar el archivo; prueba en Task 5.

---

## Base, alcance y mapa de archivos

Base de planificación: `9c3fd6bd7e3a21226e2fcd6dca65c42f512bceea`, main, CCR 3.0.0. Implementación autorizada por el usuario el 2026-10-23; ejecución secuencial en el worktree `docs/review-closure-consistency`.

Se recomiendan tareas secuenciales: comparten resolución de fuentes, validación del archivo y proyección de trazas. Antes de implementar, comparar HEAD/main con esta base y ajustar anclas si cambiaron sus contratos. La revalidación documental del 2026-10-23 aprobó 40 pruebas focalizadas sobre esta base (detalle en spec §8); las pruebas y los resultados esperados de las Tasks siguen pendientes de implementación. No volver a ejecutar la revisión del MR para validar los helpers.

Main ya resolvió la modularización y retiró los entrypoints `review_*.py`; los fallos de selección/captura e identidad tardía siguen pendientes. Se conservaron los nombres de los documentos para no romper sus enlaces; esta revisión es del 2026-10-23.

| Task | Crear | Modificar / responsabilidad |
|---|---|---|
| 1 | `tests/test_review_source_selection.py` | `contracts/reference_index.py`: enumeración; `contracts/material_inputs.py`: captura validada; `workflow/builders.py`: hashes de candidatos |
| 2 | Ninguno | `workflow/setup.py`, `workflow/builders.py`, `cli/setup.py`, `contracts/preflight.py`: inputs y gate temprano; tests CLI y bootstrap |
| 3 | `tests/test_review_closure_consistency.py` | `archive/retention.py`: selección común; `archive/lifecycle.py`: consumidores validate/close, sin cambiar su protocolo |
| 4 | `scripts/ccr/contracts/dispatch.py`, `tests/test_review_dispatch.py` | `contracts/preflight.py`, `contracts/execution.py`: identidad y proyección; `scripts/README.md`: índice del módulo |
| 5 | Ninguno | `workflow/builders.py`, `archive/lifecycle.py`, `archive/retention.py`: registro/replay/procedencia; tests y documentación |

Las rutas de módulos abreviadas de la tabla son relativas a `scripts/ccr/`. No crear runner, registro paralelo de assignments ni nuevo mecanismo de cleanup. Anclas: `workflow.setup.run_command`, `contracts.preflight.validate_assignment_event`, `archive.retention._execution_gate`, `archive.lifecycle.record_event/validate/close`, `contracts.execution.validate_execution_sources`. Usar nombres de función, no números de línea de la base anterior.

Los tests insertan `scripts/` y `tests/` en sys.path como los existentes. Los tests nuevos importan directamente sus módulos propietarios (`from ccr.archive import lifecycle, retention, resources`, `from ccr.execution import workspaces`); no ampliar los facades de compatibilidad de `tests/script_test_support.py`. Reutilizar `record10`, `context10`, `selection_input`, `current_inputs` y `source_events` de `tests/recovery_fixtures.py`; no convertir fixtures históricos en nuevos schemas para hacerlos pasar. Los fixtures nuevos son sintéticos.

Los comandos se ejecutan en la raíz del worktree con un Python 3.10+ real. `python` representa ese ejecutable, no un alias de WindowsApps. Elegir un TEMP de sesión accesible si hace falta; no cambiar configuración global ni confundir un PermissionError de TEMP con una regresión del producto.

### Task 1: selección pura y captura de los inputs del índice

**Files:**
- Modify: `scripts/ccr/contracts/reference_index.py` — enumeración pura con gramática/aliases existentes.
- Modify: `scripts/ccr/contracts/material_inputs.py` — comparación de captura inicial.
- Modify: `scripts/ccr/workflow/builders.py` — captura de hashes de candidatos sin IO.
- Create: `tests/test_review_source_selection.py` — `SourceSelectionTests`.
- Modify: `tests/test_review_reference_index.py` — conservar semántica de identities y aliases.

**Interfaces:**
- Consumes: `parse_reference`, `canonical_reference`, `validate_reference_index`, `ReferenceIssue` y la estructura actual `{schema_version, aliases, inputs}`.
- Produces: `ccr.contracts.reference_index.reference_source_paths(index: dict) -> list[str]`: rutas seleccionadas, únicas y ordenadas de inputs y destinos de aliases; no incluye el propio índice ni abre archivos. Índice/ruta malformados producen ValueError.
- Produces: `ccr.contracts.reference_index.validate_reference_selection(index, sources) -> list[ReferenceIssue]`: valida el índice y los límites comunes de 64 archivos/64 MiB, incluyendo el índice y deduplicando destinos. Usarlo desde builder y preflight. Cubrir 64 archivos exactos frente a 65, y 64 MiB exactos frente a un byte extra, en register/discovery/retain.
- Produces: `ccr.workflow.builders.capture_input_sources(index_bytes: bytes, sources: dict[str, bytes]) -> dict[str, str]`: valida bytes y devuelve hashes del índice y sus inputs materiales; los destinos de alias que sólo son outputs no se capturan como inputs. Errores producen ValueError con el diagnóstico de referencia concreto.
- Produces: `ccr.contracts.material_inputs.validate_captured_material_sources(captured_inputs: dict, index: dict, sources: dict[str, bytes]) -> list[ReferenceIssue]`: exige que cada input material esté capturado directamente o mediante alias validado con el mismo hash. Extraer/reutilizar la comparación de `validate_material_inputs`, sin debilitar esa función.

- [x] **Step 1: Escribir las pruebas unitarias de selección y captura**

Importar `reference_index as refs` y `material_inputs as material` desde `ccr.contracts`, y `builders` desde `ccr.workflow`. En `SourceSelectionTests`, definir `test_capture_includes_material_inputs_not_output_aliases`, `test_missing_or_changed_input_is_rejected` y `test_captured_material_accepts_only_hash_matching_one_hop_alias`. Crear el índice y bytes en cada método; el caso principal usa:

```python
description, notes, output = b'description-v1', b'notes-v1', b'worker-result'
sha = lambda value: hashlib.sha256(value).hexdigest()
index = {'schema_version': 1,
         'aliases': {'evidence/worker/result.json': {
             'reference': 'evidence/result.json', 'sha256': sha(output)}},
         'inputs': [
             {'reference': 'evidence/description.md', 'purpose': 'description', 'sha256': sha(description)},
             {'reference': 'evidence/notes.json', 'purpose': 'notes', 'sha256': sha(notes)}]}
raw = json.dumps(index, sort_keys=True, separators=(',', ':')).encode()
sources = {'evidence/reference-index.json': raw, 'evidence/description.md': description,
           'evidence/notes.json': notes, 'evidence/result.json': output}
assert refs.reference_source_paths(index) == [
    'evidence/description.md', 'evidence/notes.json', 'evidence/result.json']
assert builders.capture_input_sources(raw, sources) == {
    'evidence/reference-index.json': sha(raw), 'evidence/description.md': sha(description),
    'evidence/notes.json': sha(notes)}
assert material.validate_captured_material_sources({'sources': {'evidence/reference-index.json': sha(raw)}},
                                               index, sources)
```

En el segundo test quitar notes y luego cambiar sus bytes: assertRaisesRegex con `notes.json` y el diagnóstico de hash respectivamente. En el tercero capturar descripción mediante alias de un salto y assertEqual de issues a []; cambiar su digest, introducir chain y traversal por separado y assertTrue de issues/rechazo. Conservar el test existente que impide certificar descripción no capturada.

- [x] **Step 2: Comprobar RED**

Run: `python -B -m unittest discover -s tests -p test_review_source_selection.py -v`

Expected: FAIL por ausencia de las funciones nuevas, no por error de import del entorno.

- [x] **Step 3: Implementar las interfaces en sus tres módulos propietarios**

Reutilizar la gramática y validadores, no hacer scans de texto ni lecturas de filesystem. Hash SHA-256 lowercase sobre bytes exactos. Mantener `validate_material_inputs` compatible para runs iniciados y sus estados unverified.

- [x] **Step 4: Comprobar GREEN y regresiones de referencias**

Run: `python -B -m unittest discover -s tests -p test_review_source_selection.py -v`

Run: `python -B -m unittest discover -s tests -p test_review_reference_index.py -v`

Expected: OK en ambos; aliases válidos e identities de contenido siguen verificados.

- [x] **Step 5: Commit**

```bash
git add scripts/ccr/contracts/reference_index.py scripts/ccr/contracts/material_inputs.py scripts/ccr/workflow/builders.py tests/test_review_source_selection.py tests/test_review_reference_index.py
git commit -m "refactor(fuentes): compartir selección y captura del índice"
```

### Task 2: builder de inputs y barrera previa al dispatch

**Files:**
- Modify: `scripts/ccr/workflow/builders.py` — `build_review_inputs` puro.
- Modify: `scripts/ccr/workflow/setup.py` — `_validate_session_reference_index` y `run_command`, IO acotado de sesión.
- Modify: `scripts/ccr/cli/setup.py` — parser del nuevo subcomando inputs.
- Modify: `scripts/ccr/contracts/preflight.py` — validación pura de fases register/discovery/retain.
- Test: `scripts/ccr/cli/artifacts.py::preflight_run` — adaptador existente de bytes explícitos; no mover IO a contratos.
- Modify: `tests/fixtures/scripts_cli_contracts.json` — sólo contratos afectados de setup.
- Test: `tests/test_script_cli.py`, `tests/test_script_characterization.py`.
- Modify: `tests/test_review_setup.py`, `tests/test_review_preflight.py`.
- Modify: `references/archive/artifacts.md` — bootstrap y ejemplo de captura.

**Interfaces:**
- Consumes: las tres funciones de Task 1; políticas de sesión/colisión de setup existentes.
- Produces: `build_review_inputs(scope: dict, index_bytes: bytes, sources: dict[str, bytes], *, source_set_complete: bool | None, identities: dict) -> dict` en `ccr.workflow.builders`.
- Produces: CLI `python -B scripts setup inputs --input <envelope> --output <new-evidence.json>` con `{session, arguments}`. `arguments` contiene exactamente `scope`, `reference_index`, `source_set_complete`, `identities`; identities sólo admite `description_identity`, `requirements_identity`, `plan_identity`, `configuration_identity`.
- Maintains: firma y forma de retorno de `validate_preflight`; los issues siguen ordenados y `ready` sólo es true sin errores.

- [x] **Step 1: Escribir pruebas del builder y barrera**

Importar `builders` desde `ccr.workflow` y `reference_index as refs` desde `ccr.contracts` directamente en los tests nuevos. Añadir a `SetupTests`:

```python
def test_inputs_builder_pins_every_material_source_and_preserves_unknowns(self):
    # Índice sin aliases, inputs description/notes y bytes locales como en Task 1.
    # Definir scope con record10()['scope']; construir raw y sources en este método.
    result = builders.build_review_inputs(scope, raw, sources, source_set_complete=None,
                                      identities={'description_identity': description_hash})
    self.assertEqual(result['scope'], scope)
    self.assertEqual(result['sources'], builders.capture_input_sources(raw, sources))
    self.assertNotIn('source_set_complete', result)
    self.assertEqual(result['description_identity'], description_hash)
    self.assertNotIn('logical_scope_identity', result)
```

Crear además `test_context_rejects_index_only_capture_before_work`: construir sesión de archivos como en el test existente de `_validate_session_reference_index`, usar manifest.state=prepared y un índice material no vacío, e invocar el adaptador context (`ccr.workflow.setup.run_command`), que sí recibe acceso a la sesión. Comprobar rechazo del mapa con sólo índice. No pedir al builder puro `build_context`, sin bytes de fuentes, que abra archivos. Actualizar el test de sesión existente, que hoy acepta esa omisión, para esperar rechazo; agregar variante con las tres fuentes que sí pasa.

En `SetupCliTests` extender la sesión sintética existente: inputs escribe un nuevo archivo con las tres fuentes, y colisión/escape/fuente cambiada no modifican ninguna entrada ni salida previa. Probar source_set_complete true, false y null; 65 fuentes rechazan el límite existente; identities con claves desconocidas rechaza.

En `PreflightIntegrationTests`, añadir `test_prepared_material_capture_fails_before_dispatch` y `test_retain_preflight_reports_index_source_errors`: snapshots antes/después iguales, `ready=False`, referencia a notes.json al omitirla o cambiarla. Usar --evidence-input explícitos y el índice seleccionado; no recorrer la sesión para completar fuentes faltantes.

- [x] **Step 2: Comprobar RED**

Run: `python -B -m unittest discover -s tests -p test_review_setup.py -v`

Run: `python -B -m unittest discover -s tests -p test_review_preflight.py -v`

Expected: fallan las nuevas pruebas por builder ausente/captura parcial aceptada.

- [x] **Step 3: Implementar builder y gates**

Construir sources mediante Task 1, normalizar con `ccr.workflow.inputs.normalize_inputs`, omitir completeness cuando es null y conservar identities. Comparar identidades con forma SHA-256 (con o sin prefijo `sha256:`) cuando haya un input único del propósito correspondiente; no transformar identidades opacas en hashes inventados.

El adaptador inputs resuelve sólo los archivos enumerados dentro de la sesión propia con los guards existentes, verifica el descriptor y escribe un candidato nuevo. No prepara un run ni modifica el manifest.

En el adaptador context (no en build_context puro) y preflight CLI register/discovery exigir captura material completa cuando manifest.state sea prepared. El preflight interno de archive.lifecycle.register recibe sólo context JSON y conserva sus validaciones de fase; el flujo soportado verifica antes con setup context, que tiene acceso a los bytes de la sesión. En otras fases verificar selección/hashes sin completar inputs inmutables retrospectivamente. Retain preflight usa el índice y fuentes explícitas para validar referencias materiales y semántica del candidato, además de recibos; no requiere una traza futura ni crea eventos. Un contexto sin reference_index conserva el contrato no guiado existente.

Documentar inputs antes de prepare y que un gate fallido no autoriza restart/dispatch. Conservar los códigos de salida 0/1/2 existentes del CLI y actualizar sólo las entradas setup afectadas de los snapshots de ayuda/contratos. Mantener escritura en `execution.candidates.write_new_json`. Importar `validate_captured_material_sources` directamente en `contracts.preflight` para que los tests históricos puedan sustituir únicamente esa nueva regla.

- [x] **Step 4: Comprobar GREEN**

Run: los dos comandos de Step 2; `python -B -m unittest discover -s tests -p test_script_cli.py -v` y `python -B -m unittest discover -s tests -p test_script_characterization.py -v`.

Expected: OK; el CLI inputs crea sólo la salida permitida y preflight permanece de sólo lectura.

- [x] **Step 5: Commit**

```bash
git add scripts/ccr/workflow/builders.py scripts/ccr/workflow/setup.py scripts/ccr/cli/setup.py scripts/ccr/contracts/preflight.py tests/fixtures/scripts_cli_contracts.json tests/test_review_setup.py tests/test_review_preflight.py references/archive/artifacts.md
git commit -m "fix(preparacion): fijar fuentes materiales antes del despacho"
```

### Task 3: paridad retain/validate/close sin recapturar inputs históricos

**Files:**
- Modify: `scripts/ccr/archive/retention.py` — `_execution_gate` y retain.
- Modify: `scripts/ccr/archive/evidence.py` — lector de candidatos/inventario y selección acotada compartida.
- Modify: `scripts/ccr/cli/artifacts.py` — preflight CLI reutiliza la selección exacta del archivo.
- Modify: `scripts/ccr/archive/lifecycle.py` — validate/close comparten gate; el registro valida bytes en el adaptador de sesión que puede leerlos.
- Modify: `scripts/ccr/contracts/reference_index.py` — hacer cumplir el límite de 64 fuentes al reconstruir selección.
- Create: `tests/test_review_closure_consistency.py` — `ClosureConsistencyTests`.
- Modify: `tests/test_review_reference_index.py`.
- Modify: `references/archive/artifacts.md` — selección y compatibilidad de runs iniciados.
- Modify: este spec/plan — registrar el límite de captura y la frontera de bytes entre adaptadores.

**Interfaces:**
- Consumes: `reference_source_paths` de Task 1 y gates puros de Task 2.
- Maintains: `_execution_gate(run, manifest, value, contents)` y los CLI existentes; retorna/eleva como ahora. `contents` candidato y `manifest.hashes` son las únicas autoridades para leer fuentes.
- Produces (sólo tests): `ClosureConsistencyTests.make_guided_run(*, complete_capture: bool) -> dict`, con `run: Path`, `record: Path` (JSON candidato), `context: Path`, `evidence_inputs: list[Path]`, `index: dict`, `description: bytes` y `notes: bytes`.

- [x] **Step 1: Escribir regresiones de retención y reconstrucción**

La clase usa TemporaryDirectory y un repositorio Git mínimo con identidad local de fixture. `make_guided_run` crea un record10 focused con description unverified, scope/head real del repo, sesión sintética sin ejecutores de comandos, índice con description/notes, briefs/results de `context10` y los eventos genuinos sintéticos requeridos mediante los helpers. Prepara/registra las asignaciones antes de los eventos. Con complete_capture=false, para representar un archivo anterior, parchear sólo el nuevo `ccr.contracts.preflight.validate_captured_material_sources` a devolver [] durante el bootstrap preparado de esa fixture; retirar el parche al empezar processing y antes de retain/validate. Los guards originales de ownership, hashes y transacciones se ejecutan realmente. No añadir este bypass a código de producción ni modificar archivos reales.

Agregar `test_retain_then_validate_reloads_all_indexed_sources`, `test_processing_unverified_snapshot_is_preserved` y `test_uninventoried_or_changed_source_blocks_without_cleanup`. Capturar los bytes de inputs/context y la traza antes de las operaciones de sólo lectura.

```python
case = self.make_guided_run(complete_capture=True)
retention.retain(case['run'], case['record'], context_input=case['context'],
                 evidence_inputs=case['evidence_inputs'], expected_schema=10)
before = self.snapshot(case['run'])  # helper local: mapa ruta relativa -> bytes.
result = lifecycle.validate(case['run'], require_retained=True)
self.assertTrue(result['retained'])
self.assertEqual(result['state'], 'closing')
self.assertEqual(self.snapshot(case['run']), before)
```

Importar `retention` y `lifecycle` desde `ccr.archive` para las llamadas del ejemplo. En la variante histórica comprobar `review_inputs` y `description.status` idénticos después de validar y que aligned/needs_update sin fuente capturada siguen rechazados. En pruebas de negativos usar fixtures separadas: falta hash de inventory con archivo presente (pasar una copia del manifest sin esa entrada a _execution_gate, sin alterar metadata durable); bytes distintos con entrada original; alias target ausente; link y ruta insegura. Tomar el snapshot después de configurar el defecto y antes del gate. AssertRaises y snapshots inmutables; cleanup sigue pending.

- [x] **Step 2: Comprobar RED**

Run: `python -B -m unittest discover -s tests -p test_review_closure_consistency.py -v`

Expected: el caso con índice no vacío reproduce el rechazo posterior a retain; las pruebas de compatibilidad no deben fallar por una fixture con schema/layout inválido.

- [x] **Step 3: Reconstruir la misma selección en cada gate**

En `_execution_gate`, parsear el índice seleccionado, enumerar sus rutas mediante Task 1 e incluirlas en requested antes de formar selected_sources. Resolverlas por source(name), que sólo acepta contents o manifest.hashes, conservando verificación y límites existentes. Aplicar el límite de 64 a la selección reconstruida. No usar rglob ni leer un archivo sólo porque exista.

Al reconstruir `selected_sources`, cargar cada `reference_index.inputs[].reference` bajo su clave original, además del destino canónico que utilicen sus consumidores. El preflight debe pasar cualquier JSON parseado a `validate_reference_selection` (que integra `validate_reference_index`), incluidos lista, null, booleano y string, antes de permitir register/discovery/retain.

Extraer `selected_source_bytes` y `select_preflight_sources` en `archive.evidence`: candidatos explícitos tienen prioridad; el fallback exige una entrada del inventario del run exacto, lectura acotada y cotejo del hash. Compartir la lectura con `_execution_gate`, `retention.retain` y `cli.artifacts.preflight_run`. Seleccionar únicamente índice, rutas enumeradas y recibos/streams requeridos, sin escanear el directorio. Cubrir re-retención sin evidence_inputs, preflight CLI de sólo lectura, candidato explícito cambiado y archivo presente sin inventario.

Mantener la validación inicial de descripción y requirements; no añadir captura directa a runs processing/closing. Verificar que close usa la misma selección incluso en replay y que validate no escribe checkpoint por defecto. Documentar que conservar evidencia permite verificarla, pero no certificar retroactivamente su captura inicial. El preflight interno de `archive.lifecycle.register` sólo dispone del contexto serializado; por eso no suplanta la comprobación de bytes. El flujo soportado ejecuta antes `setup context`, adaptador que tiene los bytes de la sesión y exige la captura material en estado prepared. El CLI preflight también exige los bytes explícitos. No presentar la llamada directa al mutador con un contexto fabricado como captura probada.

- [x] **Step 4: Comprobar GREEN y regresiones del índice**

Run: el comando de Step 2, `python -B -m unittest discover -s tests -p test_review_reference_index.py -v`, `python -B -m unittest discover -s tests -p test_review_artifacts.py -v`, `python -B -m unittest discover -s tests -p test_review_preflight.py -v` y `python -B -m unittest discover -s tests -p test_review_setup.py -v`.

Expected: OK; retain exitoso se revalida sin volver a pasar fuentes externas. --require-complete todavía exige cleanup auténtico.

- [x] **Step 5: Commit**

```bash
git add scripts/ccr/archive/retention.py tests/test_review_closure_consistency.py tests/test_review_reference_index.py references/archive/artifacts.md
git commit -m "fix(archivo): conservar selección al revalidar evidencia retenida"
```

### Task 4: identidad inicial y anotación pura del despacho original

**Files:**
- Create: `scripts/ccr/contracts/dispatch.py`, `tests/test_review_dispatch.py`.
- Modify: `scripts/ccr/contracts/preflight.py::validate_assignment_event`.
- Modify: `scripts/ccr/contracts/execution.py::validate_execution_sources`.
- Modify: `tests/test_review_preflight.py` — gate de executor antes de registrar el inicio independiente.
- Modify: `tests/test_review_execution_policy.py`.
- Modify: `scripts/README.md` — registrar el módulo puro nuevo.
- Test: `tests/test_script_dependencies.py`, `tests/test_script_layout.py`, `tests/test_script_pure_validation.py`.

**Interfaces:**
- Owner: las dos interfaces nuevas viven en `ccr.contracts.dispatch`; los tests usan `from ccr.contracts import dispatch`.
- Consumes: trace schema 1, ReferenceIssue, registry y evento original verificado por el coordinador; ninguna función nueva hace IO.
- Produces: `validate_dispatch_identity_event(event: dict, registry: list[dict], trace_events: list[dict] | None = None) -> list[ReferenceIssue]`. Sin trace_events valida sólo forma; con traza también verifica destino y conflicto.
- Produces: `project_dispatches(trace_events: list[dict], registry: list[dict]) -> tuple[list[dict], list[ReferenceIssue]]`: copias de despachos originales con identidad explícitamente anotada, sequence/occurred_at originales y sin alterar entradas dadas.
- Uses: la anotación exacta definida en spec §6.2 (`agent/unchanged`, recovered, records E######, executor y fuente local explícita en evidence).

- [x] **Step 1: Escribir pruebas unitarias de dispatch/anotación**

En `DispatchTests` crear `test_independent_start_requires_executor`, `test_late_annotation_keeps_original_order_and_result`, `test_annotation_target_and_conflicts_are_rejected`, `test_static_start_and_unknown_provider_remain_valid`. Usar registry con D1 independiente/activo, brief evidence/briefs.json#D1, original E000004 sequence=4 y executor=null, resultado sequence=7, anotación E000008 sequence=8 como en spec.

```python
before = copy.deepcopy(events)
projected, issues = dispatch.project_dispatches(events, registry)
self.assertEqual(issues, [])
self.assertEqual(events, before)
self.assertEqual(len(projected), 1)
self.assertEqual(projected[0]['sequence'], 4)
self.assertEqual(projected[0]['event_id'], 'E000004')
self.assertEqual(projected[0]['executor'], {'name': 'worker-a', 'provider_id': None})
self.assertIsNone(projected[0]['occurred_at'])
```

Parameterizar target inexistente/futuro/de otro brief/no independiente, executor previo no null, source ausente/URL/sin fragmento, occurred_at inventado, dos anotaciones divergentes y ausencia total de dispatch. Ninguno puede producir un despacho utilizable. Un discovery/started estático y provider_id null siguen permitidos.

En tests de ejecución, reutilizar record10('deep')/source_events: quitar executor sólo del despacho D1, añadir una anotación posterior al resultado y comprobar que valida sin duplicar resultado; sin anotación debe conservar el error de independencia. D2 y V1 conservan sus despachos válidos. Aportar el brief y fuente observada seleccionados al conjunto de referencias del gate, sin inferir identidad del resultado.

- [x] **Step 2: Comprobar RED**

Run: `python -B -m unittest discover -s tests -p test_review_dispatch.py -v`

Expected: FAIL por módulo/interfaces ausentes. El caso de ejecución nuevo falla porque hoy no se proyectan anotaciones.

- [x] **Step 3: Implementar validación y proyección**

En el módulo nuevo usar únicamente identidades explícitas y exactamente un destino original. La proyección no convierte la anotación en started ni desplaza sequence. La forma de dispatch nuevo exige executor sólo para agent/started independiente; el registro de un resultado no necesita duplicar executor si actor ya lo identifica.

Para la procedencia de anotaciones, permitir la gramática de alias keys anidadas seguras mediante `parse_reference(..., allow_alias_key=True)`. Probar builder, proyección y mutador closing con `evidence/harness/dispatch.json#D1`; la resolución posterior exige destino plano seleccionado y digest/fragmento/executor coincidentes. Mantener rechazos de traversal, rutas externas, separadores codificados y alias no declarado.

Importar `validate_dispatch_identity_event` directamente en `contracts.preflight` y reutilizarlo desde validate_assignment_event para eventos nuevos. En validate_execution_sources usar los dispatches proyectados para la comprobación de independencia, manteniendo los resultados originales y todos los otros gates de perfil/cobertura. No volver a validar eventos históricos originales como si fueran una nueva emisión prohibida.

- [x] **Step 4: Comprobar GREEN**

Run: comando de Step 2 y `python -B -m unittest discover -s tests -p test_review_execution_policy.py -v`.

Run: `python -B -m unittest discover -s tests -p test_script_dependencies.py -v`, `python -B -m unittest discover -s tests -p test_script_layout.py -v` y `python -B -m unittest discover -s tests -p test_script_pure_validation.py -v`.

Expected: OK; grafo sin ciclos, módulo documentado, contratos sin IO; la anotación no fabrica independencia para un target ausente ni impide consultar trazas históricas con executor desconocido.

- [x] **Step 5: Commit**

```bash
git add scripts/ccr/contracts/dispatch.py scripts/ccr/contracts/preflight.py scripts/ccr/contracts/execution.py scripts/README.md tests/test_review_dispatch.py tests/test_review_execution_policy.py
git commit -m "fix(trazabilidad): vincular identidad al despacho original"
```

### Task 5: registro idempotente, ciclo completo y documentación de orquestación

**Files:**
- Modify: `scripts/ccr/workflow/builders.py::build_assignment_event`.
- Modify: `scripts/ccr/archive/lifecycle.py::record_event`, `scripts/ccr/archive/retention.py::_execution_gate`.
- Test: `scripts/ccr/archive/resources.py::cleanup_workspace`, `scripts/ccr/execution/workspaces.py::prepare`; conservar coordinación/operaciones actuales.
- Modify: `tests/test_review_trace.py`, `tests/test_review_setup.py`, `tests/test_review_closure_consistency.py`, `tests/test_review_recovery_followup.py`.
- Modify: `SKILL.md`, `references/archive/artifacts.md`, `references/archive/lifecycle-trace.md`, `references/execution/worker-packets.md`, `docs/examples/archive8-lifecycle.md`.
- Modify: `CHANGELOG.md` — resultados pendientes en Fixed, scopes Artefactos y contratos / Perfiles y ejecución, sin asignar una versión ni fecha de publicación.

**Interfaces:**
- Consumes: validador/proyección de Task 4 y selección de Tasks 1–3.
- Maintains: CLI setup event y record-event; mismo resultado del mutador para replay idéntico, sin append ni nuevo recorded_at.
- Produces: reconocimiento del patrón agent/unchanged en builder y mutador, seleccionando provenance.source como evidencia local requerida en retención.

- [x] **Step 1: Escribir regresiones del mutador y ciclo completo**

Añadir a TraceTests `test_dispatch_annotation_replay_is_idempotent`, `test_dispatch_annotation_preserves_previous_trace_bytes` y `test_dispatch_annotation_rejects_complete_run_and_conflict`. Crear la traza previa con el patrón antiguo sólo en fixture sintético; llamar record_event con anotación, comparar el prefijo previo de trazabilidad.jsonl byte a byte y snapshot completo después del primer registro.

```python
lifecycle.record_event(run, annotation_file)
after_first = self.snapshot(run)  # helper local de test, no API de producto.
lifecycle.record_event(run, annotation_file)
self.assertEqual(self.snapshot(run), after_first)
```

Registrar payload divergente para el mismo target: assertRaises y snapshot idéntico. Repetir sobre run completo: rechazo sin bytes nuevos. Comprobar que un dispatch independiente nuevo sin executor se rechaza antes de alterar la traza, también al llamar al mutador sin pasar por setup.

Importar `resources` desde `ccr.archive` y `workspaces` desde `ccr.execution`, sin usar el facade de test anterior. Extender ClosureConsistencyTests con `test_annotation_and_sources_survive_real_owned_cleanup`: usar `workspaces.prepare(argparse.Namespace(repo=str(repo), ref='HEAD', mode='commit', role=['review'], include_untracked=[]))`, registrar su manifest/claim auténticos y seleccionar dispatch.json. Usar record10('deep'), con D1/D2 discovery y V1 verification independientes, los helpers de registro y un único resultado por asignación. Representar el dispatch D1 antiguo incompleto parcheando sólo `ccr.contracts.preflight.validate_dispatch_identity_event` durante su primera emisión de fixture; retirar ese parche antes del resultado y de la única anotación posterior. D2/V1 usan la validación normal. Retener, validar require-retained, ejecutar `resources.cleanup_workspace(argparse.Namespace(manifest=str(session / 'manifest.json'), run_dir=str(run)))` y cerrar con la observación/recibo real que usa el protocolo existente. Assert de validate(require_complete=True), inputs/identidades conservados, ausencia de recursos y ninguna segunda pareja started/completed. No simular borrado con un flag cleanup=complete ni mockear el gate de evidencia.

En SetupTests comprobar que el builder permite la anotación bien formada, conserva actor/provider/occurred_at y rechaza anotación sin brief/fuente/target. En integración quitar dispatch.json de la selección y comprobar rechazo antes de cleanup. Añadir el caso complementario donde la fuente sí está seleccionada, pero su executor no coincide con el registrado; retention debe fallar antes de escribir el archivo o iniciar cleanup.

- [x] **Step 2: Comprobar RED**

Run: `python -B -m unittest discover -s tests -p test_review_trace.py -v`

Run: `python -B -m unittest discover -s tests -p test_review_closure_consistency.py -v`

Expected: fallos nuevos por rechazo del status unchanged en builder, falta de guard del mutador, replay que hoy añade otra línea o fuente de anotación no seleccionada. No aceptar fallos de ownership artificiales como RED válido.

- [x] **Step 3: Integrar sin saltar ownership ni transacciones**

Builder event acepta el patrón de Task 4 además de hitos de trabajo. Record_event verifica shape, target y conflictos bajo el lock existente y después de verificar la traza; sólo un replay del mismo payload normalizado retorna sin append. En closing, resolver el alias con el índice retenido, verificar sus bytes/digest y fragmento, y cotejar executor antes de anexar; un replay con alias devuelve el ID y sequence originales. Una anotación diferente para ese target falla. Conservar recover de transacciones pendientes y prohibiciones de runs completos/superseded; una anotación no inicia processing ni regresa closing a processing.

En _execution_gate seleccionar la provenance.source de cada anotación reconocida, resolver su fragmento local y comprobar su retención; no hacer IO contra URLs ni interpretar un resumen como fuente. Verificar consistencia de la identidad declarada con el objeto observado seleccionado: éste contiene `executor: {name, provider_id}` y debe coincidir exactamente. La fuente del harness se captura como ese objeto acotado, conservando su procedencia; no se genera desde el paquete de hallazgos.

Actualizar los seis documentos junto con la integración: ejemplo inputs completo, dispatch con executor, anotación única tardía, selección explícita del índice para cada preflight, separación de recorded_at/occurred_at y secuencia original. Mostrar check del coordinador desde recibo con relación records C001; los checks de worker pueden quedar bajo su resultado compacto. Modelos sólo si ya expuestos; sin API probes. Retención fallida conserva recursos, corrección administrativa no relanza revisores ni altera la descripción del MR.

- [x] **Step 4a: Comprobar GREEN focalizado y límites arquitectónicos**

Run: los dos comandos de Step 2; además setup, preflight, source_selection, reference_index, dispatch, execution_policy y recovery_followup.

Expected: OK en los módulos seleccionados; el caso completo pasa después de eliminar la sesión propia y las pruebas negativas mantienen snapshots. El caso de identidad seleccionada pero discrepante también deja recursos y bytes intactos. Evidencia: 134/134 pruebas focalizadas, con 285.902 s.

Run: `python -B -m unittest discover -s tests -p test_script_execution_boundaries.py -v` y `python -B -m unittest discover -s tests -p test_script_resource_boundaries.py -v`.

Expected: OK; ningún módulo de implementación importa CLI y execution no coordina mutaciones del archivo. Evidencia: 5/5.

Run: `git diff --check`

Expected: sin errores. Revisar contra A1–A10 del spec y dejar evidencia en `docs/validation/2026-10-21-review-closure-consistency.md`: base/head probados, comandos, resultados, skips y límites. Incluir el ejemplo archive8 y changelog en la revisión documental. No copiar rutas privadas, notas de MR ni logs del caso real. Evidencia: diff check limpio y aceptación A1–A10 trazada en el informe.

- [ ] **Step 4b: Completar gate amplio**

Run una sola vez `python -B -m unittest discover -s tests -p 'test_*.py'`.

Estado: se inició y avanzó sin errores visibles, pero dejó de emitir salida durante varios minutos; se interrumpió manualmente y no emitió resumen. No cuenta como suite aprobada ni se marca como terminada.

Seguimiento del PR #30: 151/151 pruebas focalizadas aprobadas. La ampliación observó 759 de 782 casos (752 aprobados, 7 omitidos por el entorno); se detuvo por duración en la matriz de transferencia de recursos de reinicio y quedaron 23 sin resultado. El intento monolítico anterior tampoco emitió resumen; su error de recibos pasó aisladamente. Conservar este gate pendiente y consultar el alcance exacto en `docs/validation/2026-10-21-review-closure-consistency.md`.

Segundo seguimiento: la suite completa terminó 789 casos en 2191.694 s (785 aprobados, un PermissionError de Windows en os.replace y 3 omisiones de symlinks). Los 23 casos antes pendientes ya se ejecutaron. La matriz completa que registró el error pasó después sin filtrar subcasos: 1/1, exit 0, 113.667 s. Las 158 pruebas focalizadas pasaron en la corrida amplia. El gate se conserva pendiente de una ejecución global con exit 0; no presentar el reintento aislado como una corrida monolítica limpia.

- [x] **Step 5: Commit**

```bash
git add scripts/ccr/workflow/builders.py scripts/ccr/archive/lifecycle.py scripts/ccr/archive/retention.py tests/test_review_trace.py tests/test_review_setup.py tests/test_review_closure_consistency.py tests/test_review_recovery_followup.py SKILL.md references/archive/artifacts.md references/archive/lifecycle-trace.md references/execution/worker-packets.md docs/examples/archive8-lifecycle.md CHANGELOG.md docs/superpowers/plans/2026-10-21-review-closure-consistency.md docs/superpowers/specs/2026-10-21-review-closure-consistency-design.md docs/validation/2026-10-21-review-closure-consistency.md
git commit -m "fix(cierre): conservar procedencia sin repetir ejecuciones"
```

## Cobertura y handoff

| Aceptación | Task / prueba principal |
|---|---|
| A1 | 1–2: capture_input_sources y CLI inputs con tres hashes |
| A2 | 2: prepared_material_capture_fails_before_dispatch; preflight_rejects_non_object_reference_index_with_matching_digest; límites exactos de 64 archivos/64 MiB en register/discovery/retain |
| A3 | 3: retain_then_validate_reloads_all_indexed_sources; material_input_alias_survives_revalidation_and_close; reretain_reuses_inventoried_index_material_and_alias_sources, incluido preflight CLI sin evidence_inputs |
| A4 | 1–3: aliases/rutas/hashes y uninventoried_or_changed_source_blocks_without_cleanup |
| A5 | 3: processing_unverified_snapshot_is_preserved |
| A6 | 4–5: independent_start_requires_executor y rechazo durable directo |
| A7 | 4–5: late_annotation_keeps_original_order_and_result; closing_annotation_alias_replay_returns_original_event_without_writes; nested_dispatch_alias_passes_builder_closing_mutator_and_replay y proyección pura |
| A8 | 4–5: targets/conflictos y preservación del prefijo de traza; closing_annotation_rejects_invalid_fragment_and_executor_without_writes, con y sin alias y anotación válida posterior |
| A9 | 5: annotation_and_sources_survive_real_owned_cleanup |
| A10 | 2 y 5: ejemplos operativos, checks/modelos y gates de cierre |

Para ejecutar, leer este plan y el spec juntos. Las cinco tareas comparten interfaces pequeñas y un mismo contrato de archivo, por lo que esta implementación las ejecuta de forma secuencial en el mismo worktree. No crear PR, release, publicar en el MR o modificar el run real como parte de este plan.
