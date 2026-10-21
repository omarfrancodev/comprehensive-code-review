# Scripts Modularity and Single Entry Point Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** organizar y fragmentar los 27 helpers de CCR por responsabilidad y sustituir sus 12 CLI por una única entrada sin fachadas legacy.

**Architecture:** scripts/__main__.py delega a un registro estático de áreas con carga diferida; cada parser llama contratos, lectores u operaciones de su dominio. Las extracciones cortan dependencias inversas antes de mover transacciones y recursos. Las interfaces de ejecución cambian; los protocolos persistidos y garantías de 2.14.0 permanecen intactos.

**Tech Stack:** Python 3.10+, biblioteca estándar, unittest, Git y Markdown.

**Spec:** [Scripts modulares y entrada única](../specs/2026-10-21-scripts-modularity-design.md).

## Global Constraints

- Python 3.10+ y biblioteca estándar; no añadir dependencias de ejecución ni exigir instalación Python.
- Usar `python /ruta/skill/scripts <área> ...` como interfaz soportada, desde cualquier cwd y con rutas que contengan espacios.
- Retirar los 27 archivos `scripts/review_*.py` al completar la migración; no conservar fachadas, aliases en sys.modules ni imports legacy como interfaz soportada.
- Conservar archive schema 8/layout 2, result schemas 1–10 y trace schema 1; no migrar ni reescribir archivos históricos.
- Los layouts anteriores siguen sin soporte operativo nativo; su consulta histórica conserva paquetes de tres archivos y nunca habilita resume/restart por conservar un validador legible.
- Preservar identidades, bytes canónicos, hashes, reservas, nombres de artefactos y replay nativo v2; un cambio de módulo no cambia la identidad lógica del productor.
- Mantener locks, reentrancia, orden de adquisición, ownership, gates, idempotencia y causas/tipos de errores de coordinación.
- Preflight, diagnóstico, búsqueda y ayuda son de sólo lectura: no crean runs, locks, eventos, worktrees ni procesos de trabajo.
- Conservar selección explícita de latest, sus empates y búsqueda incompleta; no convertir inputs desconocidos o cambiados en aplicables.
- Mantener setup en sesiones propias, captura explícita sin shell y comentario público verificado por sus bytes; ninguna operación publica remotamente por este cambio.
- No activar mediciones, sondeos de modelos, instalación de herramientas ni dispatch adicional.
- No modificar el visor independiente ni las skills globales de Superpowers o todo.
- Mantener documentos históricos como evidencia; actualizar instrucciones vigentes, enlaces locales y guías de migración sin atribuirles comportamiento posterior.

## Review Focus

1. Una copia instalada en una ruta con espacios, desde cwd ajeno y sin PYTHONPATH, debe cargar catálogo/versión y las 12 áreas; pruebas de Task 12.
2. `checks run` debe devolver 0 si capturó correctamente un proceso con exit 7, manteniendo exit_code=7 en el recibo; prueba de Task 10.
3. Un intent v2 previo sin el campo derivado y un paquete histórico deben conservar bytes/identidad y su ruta de consulta, sin conversión a archivo nativo; pruebas de Tasks 8 y 9.
4. Un fallo después de borrar recursos pero antes del recibo de cleanup debe ser recuperable por el mismo propietario, con locks reentrantes y sin borrar recursos ajenos; pruebas de Task 7.
5. Root help, área desconocida y preflight inválido no deben cargar procesos de trabajo ni crear locks/artefactos; pruebas de Tasks 4, 12 y 13.

---

## Base, estado y ejecución

Base fijada: `fd38df82f2ea8ef2a921dd8a89e66540f0f01bfb`, main/CCR 2.14.0. Worktree de planificación: `.worktrees/scripts-modularity-spec-plan`, rama `docs/scripts-modularity-spec-plan`.

Estado: plan preparado por petición expresa junto con el spec; ambos pendientes de revisión antes de implementar. Método de ejecución aún no elegido. Se recomienda ejecución nativa secuencial por el acoplamiento entre interfaces y transacciones, con revisión de rama al finalizar; la elección corresponde al usuario. Este documento no inicia agentes ni ejecuta tareas de producto.

Si main avanza antes de implementar, comparar scripts, contratos, pruebas y reglas de contribución con esta base y actualizar ambos documentos antes de ejecutar. No mezclar cambios de otro worktree. Se puede reutilizar este worktree para ejecución una vez aprobados los documentos; no es necesario crear otra copia automáticamente.

Las tareas son secuenciales. Cada una termina con sus pruebas y un commit local de alcance explícito. Se permiten delegadores temporales en los archivos legacy durante las extracciones para mantener pasos verificables; Task 12 los retira todos y Task 13 comprueba su ausencia. No escribir producto para esta entrega de planificación.

Los comandos de pruebas se ejecutan en la raíz del worktree con un intérprete Python real, no el alias de WindowsApps. `python` en los ejemplos representa ese intérprete. Una prueba RED debe fallar por la API/comportamiento que se introduce, no por errores ambientales; no se instala ninguna dependencia para obtener verde.

Para tests nuevos, crear clases unittest y usar fixtures existentes en tests/recovery_fixtures.py, archive_layout_fixtures.py, restart_v2_fixtures.py y publication_fixtures.py según el flujo. Corregir imports históricos de esos fixtures al migrar sus propietarios. No añadir nuevas importaciones desde clases de otro módulo de tests.

## Mapa de entregas e interfaces

| Task | Responsabilidad | APIs que habilita para las siguientes |
|---|---|---|
| 1 | Caracterización y baseline | Inventario exacto de parsers, formatos y orden de locks de la base |
| 2 | Infraestructura y unidades pequeñas | raíz instalada, IO con formatos nombrados, Git, locks, layout, trace, harness, scope e inputs |
| 3 | Resultado y presentación pura | validate/render/IDs, perfiles y cumplimiento de ejecución |
| 4 | Reglas de 2.14.0 | referencias, preflight, recibos y observaciones de modelo puros |
| 5 | Lectura verificada | load_run, verify_files, lectura de sesión/intents sin servicios mutadores |
| 6 | Persistencia ordinaria | transacciones, checkpoints, preparación, retención y cierre |
| 7 | Workspaces y claims | coordinación de cleanup y transferencias; acciones físicas sin ciclos |
| 8 | Restart durable | reinicio, replay, rechazo y abandono bajo el mismo protocolo |
| 9 | Consulta y continuidad | inspect/lookup/latest/history sin importar mutadores |
| 10 | Ejecución y candidatos | setup, recibos capturados y runner |
| 11 | Entrega y comentario | render/verify público y entrega desde archivo verificado |
| 12 | Cambio de interfaz | entrada única, parsers con argv, retirada legacy y guía de migración |
| 13 | Registro e integración | grafo acíclico, layout registrado, documentación coherente y suite completa |

Las APIs que no cambian de firma se trasladan con sus nombres/argumentos actuales. Las nuevas firmas fijadas a continuación y en spec §5 son vinculantes. Helpers privados pueden renombrarse dentro de su propietario, pero todo caller externo al módulo usa una API nombrada, no imports de funciones con `_`.

## Convenciones para ejecutar los pasos

Las rutas de Files son relativas a la raíz del worktree. Cada bloque de prueba muestra métodos de una clase `unittest.TestCase`; usar los imports indicados en el bloque y el bootstrap de tests, sin modificar sys.path en producto. Los ejemplos son especificaciones de pruebas futuras, no resultados ya ejecutados.

En cada archivo nuevo de tests, importar `unittest` y llamar una vez a `script_test_support.enable_package_imports() -> None`, que añade scripts a sys.path sólo si falta. Ese helper se crea en Task 1. `ROOT` en los ejemplos es `Path(__file__).resolve().parents[1]`; importar Path desde pathlib cuando se use. Cada prueba adicional debe fijar una garantía del spec, no el número de líneas o la forma privada de una implementación.

Los comandos de regresión usan discovery para evitar imports accidentales de otro paquete tests. Cada línea Run se ejecuta por separado; Expected describe la evidencia requerida. Antes de cada commit revisar `git diff --name-only` y stagear únicamente los archivos de Files modificados por esa tarea. Los git add de cada paso incluyen su alcance explícito; no incluir cambios ajenos que aparezcan durante la ejecución.

### Task 1: Caracterizar la superficie actual y los protocolos

**Files:**
- Create: `tests/fixtures/scripts_cli_contracts.json`, `tests/fixtures/scripts_encoding_contracts.json`, `tests/script_test_support.py`
- Create: `docs/validation/2026-10-21-scripts-modularity-baseline.md`
- Test: `tests/test_script_characterization.py`

**Interfaces:**
- Consumes: CLI legacy de spec §3 y los encoders actuales; aún no consume APIs nuevas. El baseline se toma del commit fd38df8, antes de mover funciones.
- Produces: `script_test_support.run_cli(area: str, argv: list[str], *, cwd: Path) -> subprocess.CompletedProcess` elige el legacy actual y se actualiza a la entrada única en Task 12. `cli_inventory() -> dict` enumera las 12 áreas del spec con sus opciones, choices y acciones de argparse. Los fixtures guardan expectativas portables, no paths locales, UUID o timestamps de una ejecución real. `enable_package_imports() -> None`, `encoding_inventory() -> dict` y `module_dependencies(module: str) -> set[str]`: este último lee AST del módulo bajo scripts, resuelve imports relativos y locales y no lo importa ni lo ejecuta.

- [ ] **Step 1: Ejecutar la suite de la base antes de cambios de producto**

Run: `python -B -X utf8 -m unittest discover -s tests`
Expected: OK; registrar conteo, fallos o skips observados. Un fallo previo debe diagnosticarse antes de atribuirlo a esta migración.

- [ ] **Step 2: Capturar las expectativas portables de la base**

Guardar en tests/fixtures/scripts_cli_contracts.json las doce áreas, opciones, choices, defaults y requerimientos observados de los parsers de fd38df8. Guardar en scripts_encoding_contracts.json pares de entrada/bytes esperados para manifest, layout, restart, trace, recibos y setup. Excluir cwd, UUID y tiempos reales. Estas expectativas se inspeccionan antes de mover funciones; no se regeneran con la implementación refactorizada para hacer pasar un fallo.

- [ ] **Step 3: Escribir la prueba de caracterización**

Añadir los siguientes métodos a una clase unittest.TestCase en `tests/test_script_characterization.py`.

```python
def test_cli_inventory_matches_the_locked_base(self):
    import json
    from script_test_support import cli_inventory
    expected = json.loads((ROOT / 'tests/fixtures/scripts_cli_contracts.json').read_text(encoding='utf-8'))
    self.assertEqual(cli_inventory(), expected)
    self.assertEqual(set(expected), {'artifacts', 'contract', 'delivery', 'history',
        'metrics', 'packets', 'recovery', 'runner', 'workspace', 'setup', 'checks', 'comment'})

def test_encoding_inventory_matches_original_bytes(self):
    import json
    from script_test_support import encoding_inventory
    expected = json.loads((ROOT / 'tests/fixtures/scripts_encoding_contracts.json').read_text(encoding='utf-8'))
    self.assertEqual(encoding_inventory(), expected)
```

- [ ] **Step 4: Ejecutar la prueba antes de implementar las APIs nuevas**

Run: `python -B -X utf8 -m unittest discover -s tests -p test_script_characterization.py -v`
Expected: FAIL por import/API nueva ausente en script_test_support; no por un comportamiento antiguo que ya es correcto.

- [ ] **Step 5: Implementar las interfaces producidas en sus archivos propietarios**

Crear run_cli/cli_inventory/encoding_inventory/enable_package_imports/module_dependencies con las firmas de Interfaces en tests/script_test_support.py. run_cli usa un mapa explícito de áreas a las rutas legacy de spec §3, subprocess sin shell y cwd suministrado; Task 12 cambia sólo ese routing. cli_inventory devuelve las expectativas observadas del parser, no lee el fixture para devolverlo. encoding_inventory devuelve para los seis roles lógicos manifest/layout/restart/trace/receipt/setup el hexadecimal de los bytes de entrada determinista capturados en Step 2, invocando al encoder real; no carga sus expectativas. Al mover cada encoder se adapta únicamente el routing de este helper. Registrar además el orden observado de locks de cleanup, transferencia y restart en el baseline documental.

- [ ] **Step 6: Ejecutar las pruebas para comprobar GREEN**

Run: `python -B -X utf8 -m unittest discover -s tests -p test_script_characterization.py -v`
Expected: OK; todos los asserts anteriores pasan. Esto no acredita todavía el resto de flujos.

- [ ] **Step 7: Ejecutar las regresiones del entregable**

Run: `python -B -X utf8 -m unittest discover -s tests -p test_review_run_lock.py -v`
Expected: OK; registrar cualquier skip ambiental y no afirmar cobertura de una suite no ejecutada.

- [ ] **Step 8: Crear el commit del entregable verificado**

```bash
git add -- tests/fixtures/scripts_cli_contracts.json tests/fixtures/scripts_encoding_contracts.json tests/script_test_support.py docs/validation/2026-10-21-scripts-modularity-baseline.md tests/test_script_characterization.py
git diff --cached --check
git commit -m "test(scripts): fijar superficie y protocolos de los helpers"
```

### Task 2: Extraer infraestructura, raíz instalada y contratos pequeños

**Files:**
- Create: `scripts/ccr/__init__.py`, `scripts/ccr/shared/__init__.py`, `scripts/ccr/workflow/__init__.py`
- Create: `scripts/ccr/contracts/__init__.py`, `scripts/ccr/archive/__init__.py`, `scripts/ccr/execution/__init__.py`
- Create: `scripts/ccr/maintenance/__init__.py`, `scripts/ccr/shared/encoding.py`, `scripts/ccr/shared/paths.py`
- Create: `scripts/ccr/shared/json_io.py`, `scripts/ccr/shared/git.py`, `scripts/ccr/shared/installation.py`
- Create: `scripts/ccr/contracts/scope.py`, `scripts/ccr/workflow/inputs.py`, `scripts/ccr/archive/layout.py`
- Create: `scripts/ccr/archive/trace.py`, `scripts/ccr/execution/locks.py`, `scripts/ccr/execution/harness.py`
- Create: `scripts/ccr/maintenance/metrics.py`
- Modify: `scripts/review_artifacts.py`, `scripts/review_inputs.py`, `scripts/review_layout.py`
- Modify: `scripts/review_trace.py`, `scripts/review_run_lock.py`, `scripts/review_harness.py`
- Modify: `scripts/review_metrics.py`, `scripts/review_recovery.py`, `tests/test_review_inputs.py`
- Modify: `tests/test_review_layout_v2.py`, `tests/test_review_trace.py`, `tests/test_review_run_lock.py`
- Modify: `tests/test_review_harness.py`, `scripts/review_contract.py`
- Test: `tests/test_script_shared.py`

- Modify: `tests/script_test_support.py`

**Interfaces:**
- Consumes: Task 1: `enable_package_imports() -> None`, `module_dependencies(module: str) -> set[str]` y fixtures deterministas de encodings; no consume servicios de archivo.
- Produces: `skill_root() -> Path`, `resource_path(relative: str) -> Path`; `validate_scope(scope: object) -> list[str]`, `require_scope(scope: object) -> None`; `normalize_inputs(raw: dict, *, caller: bool = True) -> dict` y `compare_inputs(retained: dict | None, current: dict) -> dict`. Extraer también `candidate_inputs(manifest: dict, record: dict | None = None) -> dict` y `validate_current_inputs(current_inputs, manifest, *, require_same_scope=True, compare_sources=True, require_applicable=False) -> dict` desde review_recovery; son reglas puras usadas por continuidad y lectura. IO/Git/locks mantienen firmas de los originales. Los formatos nombrados de encoding preservan los fixtures de Task 1; no se sustituye toda serialización por el formato de manifest. Encodings en scripts/ccr/shared/encoding.py: `archive_bytes(value: object) -> bytes` (indentación 2 y LF final), `compact_bytes(value: object) -> bytes` (compacto sin LF), `receipt_bytes(value: object) -> bytes` (compacto con LF); UTF-8, sort_keys=True, ensure_ascii=False y allow_nan=False en los tres. Los límites específicos de layout permanecen en layout.

- [ ] **Step 1: Escribir las pruebas del límite extraído**

Añadir los siguientes métodos a una clase unittest.TestCase en `tests/test_script_shared.py`.

```python
def test_encodings_preserve_distinct_bytes(self):
    from ccr.shared.encoding import archive_bytes, compact_bytes, receipt_bytes
    self.assertEqual(archive_bytes({'x': 1}), b'{\n  "x": 1\n}\n')
    self.assertEqual(compact_bytes({'x': 1}), b'{"x":1}')
    self.assertEqual(receipt_bytes({'x': 1}), b'{"x":1}\n')

def test_installation_root_ignores_cwd(self):
    import os
    from tempfile import TemporaryDirectory
    from ccr.shared.installation import skill_root
    previous = Path.cwd()
    with TemporaryDirectory() as directory:
        try:
            os.chdir(directory)
            self.assertEqual(skill_root(), ROOT)
        finally:
            os.chdir(previous)
```

- [ ] **Step 2: Ejecutar la prueba antes de implementar las APIs nuevas**

Run: `python -B -X utf8 -m unittest discover -s tests -p test_script_shared.py -v`
Expected: FAIL por import/API nueva ausente o por el límite de dependencia todavía incumplido. El fallo debe corresponder a la extracción de esta tarea.

- [ ] **Step 3: Implementar `skill_root() -> Path` en `scripts/ccr/shared/installation.py` y las interfaces compartidas de esta extracción**

Trasladar las funciones con su semántica actual. Extraer la validación de scope del validador general sin cambiar sus diagnósticos, y quitar la dependencia de inputs hacia review_artifacts. Resolver catálogo y SKILL.md con installation; mantener variantes de seguridad/errores de paths y Git donde hoy difieren.

- [ ] **Step 4: Ejecutar las pruebas para comprobar GREEN**

Run: `python -B -X utf8 -m unittest discover -s tests -p test_script_shared.py -v`
Expected: OK; todos los asserts anteriores pasan. Esto no acredita todavía el resto de flujos.

- [ ] **Step 5: Ejecutar las regresiones del entregable**

Run: `python -B -X utf8 -m unittest discover -s tests -p test_review_inputs.py -v`
Run: `python -B -X utf8 -m unittest discover -s tests -p test_review_layout_v2.py -v`
Run: `python -B -X utf8 -m unittest discover -s tests -p test_review_trace.py -v`
Run: `python -B -X utf8 -m unittest discover -s tests -p test_review_run_lock.py -v`
Run: `python -B -X utf8 -m unittest discover -s tests -p test_review_harness.py -v`
Expected: OK; registrar cualquier skip ambiental y no afirmar cobertura de una suite no ejecutada.

- [ ] **Step 6: Crear el commit del entregable verificado**

```bash
git add -- scripts/ccr scripts/review_artifacts.py scripts/review_inputs.py scripts/review_layout.py scripts/review_trace.py scripts/review_run_lock.py scripts/review_harness.py scripts/review_metrics.py scripts/review_recovery.py tests/test_review_inputs.py tests/test_review_layout_v2.py tests/test_review_trace.py tests/test_review_run_lock.py tests/test_review_harness.py scripts/review_contract.py tests/test_script_shared.py tests/script_test_support.py
git diff --cached --check
git commit -m "refactor(scripts): extraer infraestructura y contratos básicos"
```


### Task 3: Fragmentar contrato de resultado, perfiles y render puro

**Files:**
- Create: `scripts/ccr/contracts/validation.py`, `scripts/ccr/contracts/review.py`, `scripts/ccr/contracts/findings.py`
- Create: `scripts/ccr/contracts/identifier_types.py`, `scripts/ccr/contracts/identifiers.py`, `scripts/ccr/contracts/execution.py`
- Create: `scripts/ccr/contracts/provenance.py`, `scripts/ccr/contracts/packets.py`, `scripts/ccr/workflow/profiles.py`
- Create: `scripts/ccr/reporting/__init__.py`, `scripts/ccr/reporting/markdown.py`, `scripts/ccr/reporting/projections.py`
- Create: `scripts/ccr/reporting/render.py`
- Modify: `scripts/review_contract.py`, `scripts/review_profiles.py`, `scripts/review_execution.py`
- Modify: `scripts/review_publication.py`, `scripts/review_packets.py`, `tests/test_review_contract.py`
- Modify: `tests/test_review_presentation.py`, `tests/test_review_packets.py`, `tests/test_review_profiles.py`
- Modify: `tests/test_review_profile_names.py`, `tests/test_review_execution_policy.py`, `tests/test_review_publication_policy.py`
- Test: `tests/test_script_contract_boundaries.py`

**Interfaces:**
- Consumes: Task 2: `validate_scope(scope: object) -> list[str]`, `require_scope(scope: object) -> None`, `normalize_inputs(raw: dict, *, caller: bool = True) -> dict` y encodings con formatos preservados.
- Produces: `contracts.review.validate(record) -> list[str]`; `contracts.identifiers.canonicalize_ids(record, reserved_ids=None) -> tuple[dict, dict]`, `deduplicate(findings, groups) -> list[dict]`; `reporting.render.render(record, audience='user', publication_context=None, *, check_publication_context=None) -> str`, `render_handoff(record, context=None, audience='user', publication_context=None) -> str`. Son las firmas observadas en la base, incluidos argumentos keyword-only. `workflow.profiles` conserva validate_selection, validate_history y merge_assignment_registry y expone `canonical_profile(value) -> str` para la normalización actualmente privada; cumplimiento final reside en contracts.execution/provenance.

- [ ] **Step 1: Escribir las pruebas del límite extraído**

Añadir los siguientes métodos a una clase unittest.TestCase en `tests/test_script_contract_boundaries.py`.

```python
def test_invalid_record_accumulates_errors_without_mutation(self):
    from copy import deepcopy
    from ccr.contracts.review import validate
    record = {'schema_version': 99}
    before = deepcopy(record)
    errors = validate(record)
    self.assertIsInstance(errors, list)
    self.assertTrue(any('unsupported version' in error for error in errors))
    self.assertEqual(record, before)

def test_profile_aliases_keep_their_meaning(self):
    from ccr.workflow.profiles import canonical_profile
    self.assertEqual(canonical_profile('economy'), 'focused')
    self.assertEqual(canonical_profile('balanced'), 'standard')
```

- [ ] **Step 2: Ejecutar la prueba antes de implementar las APIs nuevas**

Run: `python -B -X utf8 -m unittest discover -s tests -p test_script_contract_boundaries.py -v`
Expected: FAIL por import/API nueva ausente o por el límite de dependencia todavía incumplido. El fallo debe corresponder a la extracción de esta tarea.

- [ ] **Step 3: Implementar `validate(record) -> list[str]` en `scripts/ccr/contracts/review.py` y separar sus propietarios**

Extraer compositores y validadores por bloque de contrato, con validación estructural antes de accesos dependientes. Compartir escapes y bloques de Markdown. Mover canonical_id/review_id a identifier_types; review importa esas comprobaciones y nunca identifiers. canonicalize_ids en identifiers puede importar review.validate sin generar la dependencia inversa.

- [ ] **Step 4: Ejecutar las pruebas para comprobar GREEN**

Run: `python -B -X utf8 -m unittest discover -s tests -p test_script_contract_boundaries.py -v`
Expected: OK; todos los asserts anteriores pasan. Esto no acredita todavía el resto de flujos.

- [ ] **Step 5: Ejecutar las regresiones del entregable**

Run: `python -B -X utf8 -m unittest discover -s tests -p test_review_contract.py -v`
Run: `python -B -X utf8 -m unittest discover -s tests -p test_review_presentation.py -v`
Run: `python -B -X utf8 -m unittest discover -s tests -p test_review_packets.py -v`
Run: `python -B -X utf8 -m unittest discover -s tests -p test_review_profiles.py -v`
Run: `python -B -X utf8 -m unittest discover -s tests -p test_review_profile_names.py -v`
Run: `python -B -X utf8 -m unittest discover -s tests -p test_review_execution_policy.py -v`
Run: `python -B -X utf8 -m unittest discover -s tests -p test_review_publication_policy.py -v`
Expected: OK; registrar cualquier skip ambiental y no afirmar cobertura de una suite no ejecutada.

- [ ] **Step 6: Crear el commit del entregable verificado**

```bash
git add -- scripts/ccr scripts/review_contract.py scripts/review_profiles.py scripts/review_execution.py scripts/review_publication.py scripts/review_packets.py tests/test_review_contract.py tests/test_review_presentation.py tests/test_review_packets.py tests/test_review_profiles.py tests/test_review_profile_names.py tests/test_review_execution_policy.py tests/test_review_publication_policy.py tests/test_script_contract_boundaries.py
git diff --cached --check
git commit -m "refactor(contratos): separar validación y presentación de resultados"
```

### Task 4: Separar validación de referencias, recibos, preflight y modelos

**Files:**
- Create: `scripts/ccr/contracts/reference_types.py`, `scripts/ccr/contracts/references.py`, `scripts/ccr/contracts/reference_index.py`
- Create: `scripts/ccr/contracts/semantic_references.py`, `scripts/ccr/contracts/material_inputs.py`, `scripts/ccr/contracts/preflight.py`
- Create: `scripts/ccr/contracts/receipts.py`, `scripts/ccr/contracts/model_usage.py`
- Modify: `scripts/review_references.py`, `scripts/review_preflight.py`, `scripts/review_check_receipts.py`
- Modify: `scripts/review_model_usage.py`, `scripts/review_check_provenance.py`, `tests/test_review_references.py`
- Modify: `tests/test_review_reference_index.py`, `tests/test_review_preflight.py`, `tests/test_review_check_receipts.py`
- Modify: `tests/test_review_check_provenance.py`, `tests/test_review_model_usage.py`
- Test: `tests/test_script_pure_validation.py`

**Interfaces:**
- Consumes: Task 3: `canonical_profile(value) -> str` y APIs de perfiles; Task 2: `archive.trace` puro. Ningún validador consume execution.checks.
- Produces: `ReferenceIssue` mantiene exactamente code, field, reference, message, expected. `parse_reference(reference: str, *, field: str, allow_alias_key: bool = False)` y `resolve_reference(reference: str, sources: dict[str, bytes], *, field: str) -> object`; validate_reference_index, canonical_reference, validate_semantic_references y validate_material_inputs conservan sus firmas actuales en sus módulos propietarios. `validate_preflight(*, phase, manifest, logical_scope, selection, context, record, sources) -> dict` preserva prepare/register/discovery/retain y límite de 100 issues. APIs de receipts y model_usage mantienen las firmas actuales y no capturan procesos.

- [ ] **Step 1: Escribir las pruebas del límite extraído**

Añadir los siguientes métodos a una clase unittest.TestCase en `tests/test_script_pure_validation.py`.

```python
def test_preflight_does_not_execute_a_command(self):
    from unittest.mock import patch
    from ccr.contracts.preflight import validate_preflight
    with patch('subprocess.run', side_effect=AssertionError('unexpected process')):
        result = validate_preflight(phase='prepare', manifest=None,
            logical_scope=None, selection=None, context=None, record=None, sources={})
    self.assertEqual(result['phase'], 'prepare')
    self.assertFalse(result['ready'])
    self.assertEqual(set(result['issues'][0]), {'code', 'field', 'reference', 'message', 'expected'})

def test_reference_resolution_uses_only_supplied_bytes(self):
    from ccr.contracts.references import parse_reference, resolve_reference
    sources = {'evidence/context.json': b'{"profile":"focused"}'}
    self.assertEqual(resolve_reference('evidence/context.json#profile', sources, field='profile'), 'focused')
    with self.assertRaises(ValueError):
        parse_reference('../context.json', field='profile')
```

- [ ] **Step 2: Ejecutar la prueba antes de implementar las APIs nuevas**

Run: `python -B -X utf8 -m unittest discover -s tests -p test_script_pure_validation.py -v`
Expected: FAIL por import/API nueva ausente o por el límite de dependencia todavía incumplido. El fallo debe corresponder a la extracción de esta tarea.

- [ ] **Step 3: Implementar `validate_preflight(*, phase, manifest, logical_scope, selection, context, record, sources) -> dict` en `scripts/ccr/contracts/preflight.py`**

Extraer tipos comunes y contratos. Cambiar preflight/provenance a contracts.receipts, eliminando imports del capturador. No mover la gramática de fuentes ni cambiar los límites para facilitar la extracción.

- [ ] **Step 4: Ejecutar las pruebas para comprobar GREEN**

Run: `python -B -X utf8 -m unittest discover -s tests -p test_script_pure_validation.py -v`
Expected: OK; todos los asserts anteriores pasan. Esto no acredita todavía el resto de flujos.

- [ ] **Step 5: Ejecutar las regresiones del entregable**

Run: `python -B -X utf8 -m unittest discover -s tests -p test_review_references.py -v`
Run: `python -B -X utf8 -m unittest discover -s tests -p test_review_reference_index.py -v`
Run: `python -B -X utf8 -m unittest discover -s tests -p test_review_preflight.py -v`
Run: `python -B -X utf8 -m unittest discover -s tests -p test_review_check_receipts.py -v`
Run: `python -B -X utf8 -m unittest discover -s tests -p test_review_check_provenance.py -v`
Run: `python -B -X utf8 -m unittest discover -s tests -p test_review_model_usage.py -v`
Expected: OK; registrar cualquier skip ambiental y no afirmar cobertura de una suite no ejecutada.

- [ ] **Step 6: Crear el commit del entregable verificado**

```bash
git add -- scripts/ccr scripts/review_references.py scripts/review_preflight.py scripts/review_check_receipts.py scripts/review_model_usage.py scripts/review_check_provenance.py tests/test_review_references.py tests/test_review_reference_index.py tests/test_review_preflight.py tests/test_review_check_receipts.py tests/test_review_check_provenance.py tests/test_review_model_usage.py tests/test_script_pure_validation.py
git diff --cached --check
git commit -m "refactor(validaciones): aislar referencias y preflight de la ejecución"
```

### Task 5: Establecer lectura verificada sin coordinador mutador

**Files:**
- Create: `scripts/ccr/archive/reader.py`, `scripts/ccr/archive/integrity.py`, `scripts/ccr/archive/intent_contracts.py`
- Create: `scripts/ccr/archive/restart_state.py`, `scripts/ccr/archive/restart_contract.py`, `scripts/ccr/contracts/claims.py`
- Create: `scripts/ccr/execution/workspace_manifest.py`
- Modify: `scripts/review_artifacts.py`, `scripts/review_resource_claims.py`, `scripts/review_workspace.py`
- Modify: `scripts/review_restart.py`, `scripts/review_setup.py`, `tests/test_review_artifact_layout.py`
- Modify: `tests/test_review_archive8.py`, `tests/test_review_lock_file_safety.py`, `tests/test_review_authority_and_claim_safety.py`
- Test: `tests/test_script_archive_reader.py`

**Interfaces:**
- Consumes: Task 2: `read_json(path, *, max_bytes=None)`, `read_bounded(path, limit) -> bytes`, `safe_path(value) -> Path`; Task 4: tipos ReferenceIssue y validadores puros.
- Produces: `reader.load_run(run_dir: str | Path) -> tuple[Path, dict, dict]`; `integrity.verify_files(run, manifest, required=False, *, allow_checkpoint_transaction=False, allow_resource_transfer=False, allow_pending_trace=False) -> None`; `workspace_manifest.load(manifest_path) -> dict` y `owned_session(session_path) -> tuple[Path, Path, dict]`. `restart_contract` conserva normalize_restart_request, same_restart_request, build_restart_intent y validate_restart_intent. Los validadores de claims/intents operan sobre objetos/bytes suministrados; restart_state puede leer descriptores mediante shared IO pero no importa reader ni servicios.

- [ ] **Step 1: Escribir las pruebas del límite extraído**

Añadir los siguientes métodos a una clase unittest.TestCase en `tests/test_script_archive_reader.py`.

```python
def test_foreign_archive_is_refused_without_writes(self):
    from tempfile import TemporaryDirectory
    from ccr.archive.reader import load_run
    with TemporaryDirectory() as directory:
        run = Path(directory)
        before = sorted(run.rglob('*'))
        with self.assertRaisesRegex(ValueError, 'ownership manifest is missing'):
            load_run(run)
        self.assertEqual(sorted(run.rglob('*')), before)

def test_reader_does_not_depend_on_mutators(self):
    from script_test_support import module_dependencies
    forbidden = {'ccr.archive.lifecycle', 'ccr.archive.restart',
                 'ccr.archive.resources', 'ccr.workflow.setup'}
    self.assertFalse(module_dependencies('ccr.archive.reader') & forbidden)
```

- [ ] **Step 2: Ejecutar la prueba antes de implementar las APIs nuevas**

Run: `python -B -X utf8 -m unittest discover -s tests -p test_script_archive_reader.py -v`
Expected: FAIL por import/API nueva ausente o por el límite de dependencia todavía incumplido. El fallo debe corresponder a la extracción de esta tarea.

- [ ] **Step 3: Implementar `load_run(run_dir: str | Path) -> tuple[Path, dict, dict]` en `scripts/ccr/archive/reader.py`**

Trasladar _load_run/_verify_files y los validadores que necesitan, manteniendo diferencias entre diagnóstico estructural y operación nativa soportada. Sacar formas de intents/transferencias/cleanup de los servicios para impedir dependencias inversas. Separar lectura/ownership de sesión del borrado; conservar seguridad y errores de load.

- [ ] **Step 4: Ejecutar las pruebas para comprobar GREEN**

Run: `python -B -X utf8 -m unittest discover -s tests -p test_script_archive_reader.py -v`
Expected: OK; todos los asserts anteriores pasan. Esto no acredita todavía el resto de flujos.

- [ ] **Step 5: Ejecutar las regresiones del entregable**

Run: `python -B -X utf8 -m unittest discover -s tests -p test_review_artifact_layout.py -v`
Run: `python -B -X utf8 -m unittest discover -s tests -p test_review_archive8.py -v`
Run: `python -B -X utf8 -m unittest discover -s tests -p test_review_lock_file_safety.py -v`
Run: `python -B -X utf8 -m unittest discover -s tests -p test_review_authority_and_claim_safety.py -v`
Expected: OK; registrar cualquier skip ambiental y no afirmar cobertura de una suite no ejecutada.

- [ ] **Step 6: Crear el commit del entregable verificado**

```bash
git add -- scripts/ccr scripts/review_artifacts.py scripts/review_resource_claims.py scripts/review_workspace.py scripts/review_restart.py scripts/review_setup.py tests/test_review_artifact_layout.py tests/test_review_archive8.py tests/test_review_lock_file_safety.py tests/test_review_authority_and_claim_safety.py tests/test_script_archive_reader.py
git diff --cached --check
git commit -m "refactor(archivo): publicar lectura e integridad independientes"
```

### Task 6: Extraer transacciones, evidencia y ciclo de vida ordinario

**Files:**
- Create: `scripts/ccr/archive/coordination.py`, `scripts/ccr/archive/transactions.py`, `scripts/ccr/archive/evidence.py`
- Create: `scripts/ccr/archive/checkpoints.py`, `scripts/ccr/archive/lifecycle.py`, `scripts/ccr/archive/retention.py`
- Modify: `scripts/review_artifacts.py`, `tests/test_review_atomic_recovery.py`, `tests/test_review_checkpoints.py`
- Modify: `tests/test_review_artifacts.py`, `tests/test_review_traceability_contract.py`, `tests/test_review_preflight.py`
- Test: `tests/test_script_archive_transactions.py`

**Interfaces:**
- Consumes: Task 5: `load_run(run_dir: str | Path) -> tuple[Path, dict, dict]` y `verify_files(run, manifest, required=False, *, allow_checkpoint_transaction=False, allow_resource_transfer=False, allow_pending_trace=False) -> None`; Task 2: `run_locks(run_dirs, *, coordination_root=None)`.
- Produces: `owned_run_locks(run_dirs, *, reservation=None)` conserva context manager/revalidación. `transactions.save_manifest(run, manifest, marker) -> dict` conserva semántica actual de _save_manifest y devuelve el marker. `transactions.recover_trace(run, manifest, marker) -> dict` devuelve el marker original cuando no hay pending_trace, o el marker actualizado devuelto por save_manifest después del replay. Los mutadores prepare/select_profile/register/record_event/pause/block/resume/retain/validate/close y checkpoint mantienen sus firmas de la base y se reparten según el spec.

- [x] **Step 1: Escribir las pruebas del límite extraído**

Añadir los siguientes métodos a una clase unittest.TestCase en `tests/test_script_archive_transactions.py`.

```python
def test_trace_without_pending_returns_marker_without_writes(self):
    from tempfile import TemporaryDirectory
    from unittest.mock import patch
    from ccr.archive.transactions import recover_trace
    marker = {'owner_id': 'test-owner'}
    with TemporaryDirectory() as directory:
        with patch('ccr.archive.transactions.save_manifest',
                   side_effect=AssertionError('unexpected commit')):
            self.assertIs(recover_trace(Path(directory), {}, marker), marker)
        self.assertEqual(list(Path(directory).iterdir()), [])
```

- [x] **Step 2: Ejecutar la prueba antes de implementar las APIs nuevas**

Run: `python -B -X utf8 -m unittest discover -s tests -p test_script_archive_transactions.py -v`
Expected: FAIL por import/API nueva ausente o por el límite de dependencia todavía incumplido. El fallo debe corresponder a la extracción de esta tarea.

- [x] **Step 3: Implementar `recover_trace(run, manifest, marker) -> dict` en `scripts/ccr/archive/transactions.py` y trasladar los mutadores ordinarios**

Extraer planes de evidencia, publicación de manifest/trace, checkpoint y retención manteniendo orden de escrituras. La validación de procedencia recibe bytes seleccionados; el servicio no reemplaza fuentes desconocidas por búsquedas amplias. Conservar IDs lógicos de productor como constantes explícitas con sus valores anteriores.

- [x] **Step 4: Ejecutar las pruebas para comprobar GREEN**

Run: `python -B -X utf8 -m unittest discover -s tests -p test_script_archive_transactions.py -v`
Expected: OK; todos los asserts anteriores pasan. Esto no acredita todavía el resto de flujos.

- [x] **Step 5: Ejecutar las regresiones del entregable**

Run: `python -B -X utf8 -m unittest discover -s tests -p test_review_atomic_recovery.py -v`
Run: `python -B -X utf8 -m unittest discover -s tests -p test_review_checkpoints.py -v`
Run: `python -B -X utf8 -m unittest discover -s tests -p test_review_artifacts.py -v`
Run: `python -B -X utf8 -m unittest discover -s tests -p test_review_traceability_contract.py -v`
Run: `python -B -X utf8 -m unittest discover -s tests -p test_review_preflight.py -v`
Expected: OK; registrar cualquier skip ambiental y no afirmar cobertura de una suite no ejecutada.

- [x] **Step 6: Crear el commit del entregable verificado**

```bash
git add -- scripts/ccr scripts/review_artifacts.py tests/test_review_atomic_recovery.py tests/test_review_checkpoints.py tests/test_review_artifacts.py tests/test_review_traceability_contract.py tests/test_review_preflight.py tests/test_script_archive_transactions.py
git diff --cached --check
git commit -m "refactor(archivo): dividir evidencia y operaciones transaccionales"
```

### Task 7: Aislar workspaces, claims y coordinación de recursos

**Files:**
- Create: `scripts/ccr/execution/workspaces.py`, `scripts/ccr/execution/claims.py`, `scripts/ccr/archive/resources.py`
- Modify: `scripts/review_workspace.py`, `scripts/review_resource_claims.py`, `scripts/review_artifacts.py`
- Modify: `tests/test_review_resource_claims.py`, `tests/test_review_coordination_errors.py`, `tests/test_review_coordination_types.py`
- Modify: `tests/test_review_session_operations.py`, `tests/test_review_restart_resources.py`, `tests/test_workspace_layout.py`
- Test: `tests/test_script_resource_boundaries.py`

**Interfaces:**
- Consumes: Tasks 5–6: `workspace_manifest.load(manifest_path) -> dict`, `owned_run_locks(run_dirs, *, reservation=None)` y `save_manifest(run, manifest, marker) -> dict`; las validaciones de claims/intents son inferiores a los servicios.
- Produces: `archive.resources.cleanup_workspace(args) -> dict` conserva las salidas/errores de review_workspace.cleanup. `resources.transfer_resources(source_run, successor_run, paths, *, authority, controller, _restart_operation_id=None) -> dict`, begin_resource_cleanup, finish_resource_cleanup y recover_resource_cleanup conservan firmas actuales. `execution.workspaces` posee prepare/record_artifact y `plan_cleanup(args, manifest: dict, *, claim: dict | None = None) -> dict`, `remove_workspaces(plan: dict) -> dict`; éstas no importan archive.resources/restart/lifecycle. El plan contiene session_id/session_dir, entradas verificadas de workspaces y main_changed; remove_workspaces devuelve el resultado actual de cierre tras revalidar los paths y registros Git seleccionados. El servicio conserva los locks y revalida ownership antes de llamar esas acciones. `execution.claims` verifica identidad y prepara planes con datos de run seleccionados; sus APIs públicas sustituyen las llamadas privadas entre módulos. Toda entrada de cleanup reclamada pasa por resources, no por una función física expuesta como operación CLI.

- [ ] **Step 1: Escribir las pruebas del límite extraído**

Añadir los siguientes métodos a una clase unittest.TestCase en `tests/test_script_resource_boundaries.py`.

```python
def test_physical_workspace_actions_do_not_import_archive_services(self):
    from script_test_support import module_dependencies
    deps = module_dependencies('ccr.execution.workspaces')
    self.assertFalse(deps & {'ccr.archive.resources', 'ccr.archive.restart', 'ccr.archive.lifecycle'})
    self.assertFalse(any(name.startswith('review_') for name in deps))
```

- [ ] **Step 2: Ejecutar la prueba antes de implementar las APIs nuevas**

Run: `python -B -X utf8 -m unittest discover -s tests -p test_script_resource_boundaries.py -v`
Expected: FAIL por import/API nueva ausente o por el límite de dependencia todavía incumplido. El fallo debe corresponder a la extracción de esta tarea.

- [ ] **Step 3: Implementar `cleanup_workspace(args) -> dict` en `scripts/ccr/archive/resources.py` y sus acciones físicas separadas**

Separar planificación pura de claims, verificación por IO y aplicación durable; mover coordinación al servicio de archive. Conservar el orden observado de Task 1 y toda la sección crítica. Validar toda la sesión antes del primer borrado y conservar recibos/recovery ante fallo posterior. No pasar el módulo archive como dependencia general.

- [ ] **Step 4: Ejecutar las pruebas para comprobar GREEN**

Run: `python -B -X utf8 -m unittest discover -s tests -p test_script_resource_boundaries.py -v`
Expected: OK; todos los asserts anteriores pasan. Esto no acredita todavía el resto de flujos.

- [ ] **Step 5: Ejecutar las regresiones del entregable**

Run: `python -B -X utf8 -m unittest discover -s tests -p test_review_resource_claims.py -v`
Run: `python -B -X utf8 -m unittest discover -s tests -p test_review_coordination_errors.py -v`
Run: `python -B -X utf8 -m unittest discover -s tests -p test_review_coordination_types.py -v`
Run: `python -B -X utf8 -m unittest discover -s tests -p test_review_session_operations.py -v`
Run: `python -B -X utf8 -m unittest discover -s tests -p test_review_restart_resources.py -v`
Run: `python -B -X utf8 -m unittest discover -s tests -p test_workspace_layout.py -v`
Expected: OK; registrar cualquier skip ambiental y no afirmar cobertura de una suite no ejecutada.

Preservar expresamente las aserciones de `tests/test_review_restart_resources.py::test_superseded_checkpoint_keeps_remaining_claim_cleanup_usable`: inyecta la interrupción después del borrado y exige recuperación del cleanup. No sustituir ese escenario por el test estructural nuevo.

- [ ] **Step 6: Crear el commit del entregable verificado**

```bash
git add -- scripts/ccr scripts/review_workspace.py scripts/review_resource_claims.py scripts/review_artifacts.py tests/test_review_resource_claims.py tests/test_review_coordination_errors.py tests/test_review_coordination_types.py tests/test_review_session_operations.py tests/test_review_restart_resources.py tests/test_workspace_layout.py tests/test_script_resource_boundaries.py
git diff --cached --check
git commit -m "refactor(recursos): separar ownership y coordinación de limpieza"
```

### Task 8: Extraer restart, replay, rechazos y abandono

**Files:**
- Create: `scripts/ccr/archive/restart.py`
- Modify: `scripts/review_restart_refusal.py`, `scripts/review_artifacts.py`, `tests/test_review_restart.py`
- Modify: `tests/test_review_restart_v2.py`, `tests/test_review_restart_refusals.py`, `tests/test_review_restart_phase_consistency.py`
- Modify: `tests/test_review_recovery_reservations.py`, `tests/test_review_recovery_sequences.py`
- Test: `tests/test_script_restart_boundaries.py`

**Interfaces:**
- Consumes: Task 7: `transfer_resources(source_run, successor_run, paths, *, authority, controller, _restart_operation_id=None) -> dict`; Tasks 5–6: contrato de restart, restart_state y publicación transaccional.
- Produces: `restart(source_run, *, profile_input, controller, authority, current_inputs, transfer_paths=None, harness=None, logical_scope_input=None)`, `recover(run_dir, *, controller, authority, current_inputs)`, `record_restart_refusal(run_dir, *, intent_path, controller, authority, reason)` y `abandon_restart(run_dir, *, intent_path, controller, authority, reason)` conservan las firmas actuales y sus resultados. restart_state no importa estas funciones; la inspección las describe mediante hechos observados y contratos inferiores.

- [ ] **Step 1: Escribir las pruebas del límite extraído**

Añadir los siguientes métodos a una clase unittest.TestCase en `tests/test_script_restart_boundaries.py`.

```python
def test_restart_service_has_no_legacy_or_cli_dependencies(self):
    from script_test_support import module_dependencies
    deps = module_dependencies('ccr.archive.restart')
    self.assertFalse(any(name.startswith(('review_', 'ccr.cli.')) for name in deps))

def test_restart_state_is_independent_of_reader_and_mutators(self):
    from script_test_support import module_dependencies
    deps = module_dependencies('ccr.archive.restart_state')
    self.assertFalse(deps & {'ccr.archive.reader', 'ccr.archive.restart', 'ccr.archive.lifecycle'})
    self.assertFalse(any(name.startswith('review_') for name in deps))
```

- [ ] **Step 2: Ejecutar la prueba antes de implementar las APIs nuevas**

Run: `python -B -X utf8 -m unittest discover -s tests -p test_script_restart_boundaries.py -v`
Expected: FAIL por import/API nueva ausente o por el límite de dependencia todavía incumplido. El fallo debe corresponder a la extracción de esta tarea.

- [ ] **Step 3: Implementar `restart(source_run, *, profile_input, controller, authority, current_inputs, transfer_paths=None, harness=None, logical_scope_input=None)` en `scripts/ccr/archive/restart.py`**

Mover intent/completion/abandonment y recuperación de restart, reutilizando recursos y transacciones sin cambiar reservas o construir un segundo motor de estados. Extraer clasificadores compartidos a contratos/estado; el servicio no importa inspection para resolver reglas que inspection también necesite.

- [ ] **Step 4: Ejecutar las pruebas para comprobar GREEN**

Run: `python -B -X utf8 -m unittest discover -s tests -p test_script_restart_boundaries.py -v`
Expected: OK; todos los asserts anteriores pasan. Esto no acredita todavía el resto de flujos.

- [ ] **Step 5: Ejecutar las regresiones del entregable**

Run: `python -B -X utf8 -m unittest discover -s tests -p test_review_restart.py -v`
Run: `python -B -X utf8 -m unittest discover -s tests -p test_review_restart_v2.py -v`
Run: `python -B -X utf8 -m unittest discover -s tests -p test_review_restart_refusals.py -v`
Run: `python -B -X utf8 -m unittest discover -s tests -p test_review_restart_phase_consistency.py -v`
Run: `python -B -X utf8 -m unittest discover -s tests -p test_review_recovery_reservations.py -v`
Run: `python -B -X utf8 -m unittest discover -s tests -p test_review_recovery_sequences.py -v`
Expected: OK; registrar cualquier skip ambiental y no afirmar cobertura de una suite no ejecutada.

Preservar `tests/test_review_restart_v2.py::test_previous_v2_recover_preserves_reservation_before_and_after_prepare` y `test_previous_v2_retry_preserves_reservation_and_reconstructs_only_missing_file`: las aserciones de bytes originales, sucesor único y retry idempotente son parte del entregable.

- [ ] **Step 6: Crear el commit del entregable verificado**

```bash
git add -- scripts/ccr scripts/review_restart_refusal.py scripts/review_artifacts.py tests/test_review_restart.py tests/test_review_restart_v2.py tests/test_review_restart_refusals.py tests/test_review_restart_phase_consistency.py tests/test_review_recovery_reservations.py tests/test_review_recovery_sequences.py tests/test_script_restart_boundaries.py
git diff --cached --check
git commit -m "refactor(reinicio): aislar operaciones durables y replay"
```

### Task 9: Separar inspección, búsqueda, continuidad e historia

**Files:**
- Create: `scripts/ccr/archive/inspection.py`, `scripts/ccr/archive/lookup.py`, `scripts/ccr/archive/history.py`
- Modify: `scripts/review_recovery.py`, `scripts/review_history.py`, `tests/test_review_latest.py`
- Modify: `tests/test_review_history.py`, `tests/test_review_operational_summary.py`
- Test: `tests/test_script_read_only_flows.py`

**Interfaces:**
- Consumes: Task 5: load_run/verify_files y lectores de restart_state; Task 2: `candidate_inputs(manifest: dict, record: dict | None = None) -> dict` y validate_current_inputs. No consume mutadores de Tasks 6–8.
- Produces: inspection conserva `inspect_run(run_dir, *, current_inputs=None)`, `operational_summary(manifest: dict, events: list[dict], record: dict | None)` y `continuation_decision(manifest: dict, *, input_appraisal: dict, pending_operation: dict | None, candidate_issues: list[dict])`. lookup conserva find_candidates y select_latest con sus parámetros/defaults actuales; history conserva inspect_source, verify_history, port_review y show_history. Portar historia es IO explícito y queda separado de inspeccionar/mostrar.

- [ ] **Step 1: Escribir las pruebas del límite extraído**

Añadir los siguientes métodos a una clase unittest.TestCase en `tests/test_script_read_only_flows.py`.

```python
def test_history_inventory_stays_exactly_three_files(self):
    from ccr.archive.history import HISTORY_FILES
    self.assertEqual(set(HISTORY_FILES), {'informe.md', 'consulta.json', '.ccr-history.json'})

def test_lookup_and_inspection_do_not_import_mutators(self):
    from script_test_support import module_dependencies
    forbidden = {'ccr.archive.restart', 'ccr.archive.lifecycle', 'ccr.archive.resources'}
    for name in ('ccr.archive.inspection', 'ccr.archive.lookup'):
        with self.subTest(module=name):
            self.assertFalse(module_dependencies(name) & forbidden)
```

- [ ] **Step 2: Ejecutar la prueba antes de implementar las APIs nuevas**

Run: `python -B -X utf8 -m unittest discover -s tests -p test_script_read_only_flows.py -v`
Expected: FAIL por import/API nueva ausente o por el límite de dependencia todavía incumplido. El fallo debe corresponder a la extracción de esta tarea.

- [ ] **Step 3: Implementar `inspect_run(run_dir, *, current_inputs=None)` en `scripts/ccr/archive/inspection.py` y sus flujos de lectura**

Sustituir _artifacts() y accesos privados por reader/integrity/restart_state; separar paginación, clasificación y selección. Mantener límites/cursors, estados desconocidos, paquetes históricos y layout no operable. Las sugerencias nuevas usan el prefijo CLI acordado; no se alteran comandos históricos guardados.

- [ ] **Step 4: Ejecutar las pruebas para comprobar GREEN**

Run: `python -B -X utf8 -m unittest discover -s tests -p test_script_read_only_flows.py -v`
Expected: OK; todos los asserts anteriores pasan. Esto no acredita todavía el resto de flujos.

- [ ] **Step 5: Ejecutar las regresiones del entregable**

Run: `python -B -X utf8 -m unittest discover -s tests -p test_review_latest.py -v`
Run: `python -B -X utf8 -m unittest discover -s tests -p test_review_history.py -v`
Run: `python -B -X utf8 -m unittest discover -s tests -p test_review_operational_summary.py -v`
Run: `python -B -X utf8 -m unittest discover -s tests -p 'test_review_recovery*.py' -v`
Expected: OK; registrar cualquier skip ambiental y no afirmar cobertura de una suite no ejecutada.

Preservar los casos `test_same_timestamp_is_ambiguous`, `test_scan_limit_does_not_return_partial_selection` y `test_port_contains_only_three_files_and_preserves_source_bytes` en sus suites existentes. El inventario estructural no sustituye esas comprobaciones funcionales.

- [ ] **Step 6: Crear el commit del entregable verificado**

```bash
git add -- scripts/ccr scripts/review_recovery.py scripts/review_history.py tests/test_review_latest.py tests/test_review_history.py tests/test_review_operational_summary.py tests/test_script_read_only_flows.py
git diff --cached --check
git commit -m "refactor(consulta): independizar recuperación e historial de los mutadores"
```

### Task 10: Extraer setup, candidatos, captura de checks y runner

**Files:**
- Create: `scripts/ccr/workflow/builders.py`, `scripts/ccr/workflow/setup.py`, `scripts/ccr/execution/candidates.py`
- Create: `scripts/ccr/execution/checks.py`, `scripts/ccr/execution/runner.py`
- Modify: `scripts/review_setup.py`, `scripts/review_check_receipts.py`, `scripts/review_runner.py`
- Modify: `tests/test_review_setup.py`, `tests/test_review_check_receipts.py`, `tests/test_review_model_usage.py`
- Modify: `tests/script_test_support.py`
- Test: `tests/test_script_execution_boundaries.py`

**Interfaces:**
- Consumes: Task 5: `owned_session(session_path) -> tuple[Path, Path, dict]`, load_run/verify_files; Task 4: validate_preflight y contratos de recibos/modelos; Task 7: workspaces propios y verificación de sesión.
- Produces: builders conserva build_profile_selection, build_context, build_model_usage_update y build_assignment_event con sus firmas actuales. setup expone `run_command(command: str, input_path: str, output_path: str) -> dict`, extraído de _run_command. candidates expone `write_new_json(session_dir: Path, output: str, value: dict) -> Path`. checks mantiene `capture_check(*, check_id, argv, command, cwd, executor_workspace, revision, executor, output_dir) -> dict`; runner conserva run(args) y stop(process). Helper sólo de tests `owned_check_request(root: Path, *, exit_code: int = 0) -> dict` en tests/script_test_support.py: crea repo Git sintético y sesión/workspace propios mediante execution.workspaces.prepare, usando el setup vigente de las pruebas de captura; devuelve exactamente check_id, argv, command, cwd, executor_workspace, revision, executor y output_dir. argv ejecuta sys.executable con raise SystemExit(exit_code); command representa ese argv según el contrato vigente. No mockea el gate de ownership.

- [ ] **Step 1: Escribir las pruebas del límite extraído**

Añadir los siguientes métodos a una clase unittest.TestCase en `tests/test_script_execution_boundaries.py`.

```python
def test_candidate_never_overwrites_existing_output(self):
    from tempfile import TemporaryDirectory
    from ccr.execution.candidates import write_new_json
    with TemporaryDirectory() as directory:
        session = Path(directory)
        target = session / 'evidence' / 'candidate.json'
        self.assertEqual(write_new_json(session, str(target), {'x': 1}), target)
        original = target.read_bytes()
        self.assertEqual(original, b'{"x":1}\n')
        with self.assertRaises(FileExistsError):
            write_new_json(session, str(target), {'x': 2})
        self.assertEqual(target.read_bytes(), original)

def test_capture_keeps_the_observed_nonzero_exit(self):
    from tempfile import TemporaryDirectory
    from script_test_support import owned_check_request
    from ccr.execution.checks import capture_check
    with TemporaryDirectory() as directory:
        request = owned_check_request(Path(directory), exit_code=7)
        receipt = capture_check(**request)
        self.assertEqual(receipt['exit_code'], 7)
        self.assertEqual(receipt['schema_version'], 1)
        self.assertIsNotNone(receipt['finished_at'])
```

- [ ] **Step 2: Ejecutar la prueba antes de implementar las APIs nuevas**

Run: `python -B -X utf8 -m unittest discover -s tests -p test_script_execution_boundaries.py -v`
Expected: FAIL por import/API nueva ausente o por el límite de dependencia todavía incumplido. El fallo debe corresponder a la extracción de esta tarea.

- [ ] **Step 3: Implementar `write_new_json(session_dir: Path, output: str, value: dict) -> Path` en `scripts/ccr/execution/candidates.py` y las APIs de ejecución**

Separar IO/ownership de construcción pura; cambiar setup a reader e inputs públicos. Conservar el escritor de candidatos con su formato propio, límite y rechazo de sobrescritura. Capturar argv sin shell y sin inferir éxito del comando por haber escrito un recibo.

Crear también owned_check_request en tests/script_test_support.py con el contrato de Interfaces, extrayendo el setup de la suite de captura existente, sin importar su clase TestCase.

- [ ] **Step 4: Ejecutar las pruebas para comprobar GREEN**

Run: `python -B -X utf8 -m unittest discover -s tests -p test_script_execution_boundaries.py -v`
Expected: OK; todos los asserts anteriores pasan. Esto no acredita todavía el resto de flujos.

- [ ] **Step 5: Ejecutar las regresiones del entregable**

Run: `python -B -X utf8 -m unittest discover -s tests -p test_review_setup.py -v`
Run: `python -B -X utf8 -m unittest discover -s tests -p test_review_check_receipts.py -v`
Run: `python -B -X utf8 -m unittest discover -s tests -p test_review_model_usage.py -v`
Expected: OK; registrar cualquier skip ambiental y no afirmar cobertura de una suite no ejecutada.

- [ ] **Step 6: Crear el commit del entregable verificado**

```bash
git add -- scripts/ccr scripts/review_setup.py scripts/review_check_receipts.py scripts/review_runner.py tests/test_review_setup.py tests/test_review_check_receipts.py tests/test_review_model_usage.py tests/script_test_support.py tests/test_script_execution_boundaries.py
git diff --cached --check
git commit -m "refactor(ejecucion): separar candidatos y captura de comandos"
```

### Task 11: Consolidar entrega y preparación/verificación pública

**Files:**
- Create: `scripts/ccr/reporting/delivery.py`, `scripts/ccr/reporting/comment.py`
- Modify: `scripts/review_delivery.py`, `scripts/review_comment.py`, `tests/test_review_delivery.py`
- Modify: `tests/test_review_comment.py`, `tests/test_review_publication_policy.py`, `tests/test_review_presentation.py`
- Modify: `tests/publication_fixtures.py`
- Test: `tests/test_script_reporting_boundaries.py`

**Interfaces:**
- Consumes: Task 3: `render(record, audience='user', publication_context=None, *, check_publication_context=None) -> str`; Task 9: lectura verificada; Task 10: `write_new_json(session_dir: Path, output: str, value: dict) -> Path`.
- Produces: delivery conserva `deliver(run_dir, delivery, project_root, output_root=None, context=None) -> Path`. comment conserva `prepare_public_comment(record: dict, *, publication_context: dict | None = None, check_publication_context: dict | None = None) -> dict` y `verify_public_comment(record: dict, draft: dict, body: str, *, remote: bool = False) -> dict`. Render permanece puro y no importa delivery. Los handlers usan candidates para guardar en sesión propia, sin acoplar comment a workflow.setup.

- [ ] **Step 1: Escribir las pruebas del límite extraído**

Añadir los siguientes métodos a una clase unittest.TestCase en `tests/test_script_reporting_boundaries.py`.

```python
def test_edited_public_body_is_not_canonical(self):
    from publication_fixtures import publication_record, check_classification
    from ccr.reporting.comment import prepare_public_comment, verify_public_comment
    record = publication_record()
    draft = prepare_public_comment(record, check_publication_context=check_classification(record))
    self.assertTrue(verify_public_comment(record, draft, draft['body'])['verified'])
    with self.assertRaisesRegex(ValueError, 'body_mismatch'):
        verify_public_comment(record, draft, draft['body'] + 'edited')
```

- [ ] **Step 2: Ejecutar la prueba antes de implementar las APIs nuevas**

Run: `python -B -X utf8 -m unittest discover -s tests -p test_script_reporting_boundaries.py -v`
Expected: FAIL por import/API nueva ausente o por el límite de dependencia todavía incumplido. El fallo debe corresponder a la extracción de esta tarea.

- [ ] **Step 3: Implementar `verify_public_comment(record: dict, draft: dict, body: str, *, remote: bool = False) -> dict` en `scripts/ccr/reporting/comment.py`**

Mover proyecciones locales de delivery a su propietario sólo si son compartidas; conservar formatos de entrega y salida. Sustituir _git/_contains y utilidades de setup por APIs compartidas/candidates, sin ampliar fuentes o efectos.

- [ ] **Step 4: Ejecutar las pruebas para comprobar GREEN**

Run: `python -B -X utf8 -m unittest discover -s tests -p test_script_reporting_boundaries.py -v`
Expected: OK; todos los asserts anteriores pasan. Esto no acredita todavía el resto de flujos.

- [ ] **Step 5: Ejecutar las regresiones del entregable**

Run: `python -B -X utf8 -m unittest discover -s tests -p test_review_delivery.py -v`
Run: `python -B -X utf8 -m unittest discover -s tests -p test_review_comment.py -v`
Run: `python -B -X utf8 -m unittest discover -s tests -p test_review_publication_policy.py -v`
Run: `python -B -X utf8 -m unittest discover -s tests -p test_review_presentation.py -v`
Expected: OK; registrar cualquier skip ambiental y no afirmar cobertura de una suite no ejecutada.

- [ ] **Step 6: Crear el commit del entregable verificado**

```bash
git add -- scripts/ccr scripts/review_delivery.py scripts/review_comment.py tests/test_review_delivery.py tests/test_review_comment.py tests/test_review_publication_policy.py tests/test_review_presentation.py tests/publication_fixtures.py tests/test_script_reporting_boundaries.py
git diff --cached --check
git commit -m "refactor(reportes): separar entrega y comentario público"
```

### Task 12: Introducir entrada única y retirar la superficie legacy

**Files:**
- Create: `scripts/__main__.py`, `scripts/ccr/cli/__init__.py`, `scripts/ccr/cli/main.py`
- Create: `scripts/ccr/cli/artifacts.py`, `scripts/ccr/cli/contract.py`, `scripts/ccr/cli/delivery.py`
- Create: `scripts/ccr/cli/history.py`, `scripts/ccr/cli/metrics.py`, `scripts/ccr/cli/packets.py`
- Create: `scripts/ccr/cli/recovery.py`, `scripts/ccr/cli/runner.py`, `scripts/ccr/cli/workspace.py`
- Create: `scripts/ccr/cli/setup.py`, `scripts/ccr/cli/checks.py`, `scripts/ccr/cli/comment.py`
- Create: `docs/script-migration.md`
- Modify: `tests/script_test_support.py`, `tests/publication_fixtures.py`, `tests/recovery_fixtures.py`
- Modify: `tests/restart_v2_fixtures.py`, `tests/test_artifact_lifecycle_policy.py`, `tests/test_review_archive8.py`
- Modify: `tests/test_review_areas.py`, `tests/test_review_artifact_layout.py`, `tests/test_review_artifacts.py`
- Modify: `tests/test_review_atomic_recovery.py`, `tests/test_review_authority_and_claim_safety.py`, `tests/test_review_check_provenance.py`
- Modify: `tests/test_review_check_receipts.py`, `tests/test_review_checkpoints.py`, `tests/test_review_comment.py`
- Modify: `tests/test_review_contract.py`, `tests/test_review_coordination_errors.py`, `tests/test_review_coordination_types.py`
- Modify: `tests/test_review_delivery.py`, `tests/test_review_execution_policy.py`, `tests/test_review_extended.py`
- Modify: `tests/test_review_flow_v24.py`, `tests/test_review_flow_v27.py`, `tests/test_review_harness.py`
- Modify: `tests/test_review_history.py`, `tests/test_review_inputs.py`, `tests/test_review_latest.py`
- Modify: `tests/test_review_layout_v2.py`, `tests/test_review_lock_file_safety.py`, `tests/test_review_metrics.py`
- Modify: `tests/test_review_model_usage.py`, `tests/test_review_operational_summary.py`, `tests/test_review_packets.py`
- Modify: `tests/test_review_preflight.py`, `tests/test_review_presentation.py`, `tests/test_review_profile_names.py`
- Modify: `tests/test_review_profiles.py`, `tests/test_review_publication_policy.py`, `tests/test_review_recovery.py`
- Modify: `tests/test_review_recovery_diagnostics.py`, `tests/test_review_recovery_exit_guidance.py`, `tests/test_review_recovery_followup.py`
- Modify: `tests/test_review_recovery_reservations.py`, `tests/test_review_recovery_route_consistency.py`, `tests/test_review_recovery_sequences.py`
- Modify: `tests/test_review_reference_index.py`, `tests/test_review_references.py`, `tests/test_review_resource_claims.py`
- Modify: `tests/test_review_restart.py`, `tests/test_review_restart_phase_consistency.py`, `tests/test_review_restart_refusals.py`
- Modify: `tests/test_review_restart_resources.py`, `tests/test_review_restart_v2.py`, `tests/test_review_run_lock.py`
- Modify: `tests/test_review_scenarios.py`, `tests/test_review_session_operations.py`, `tests/test_review_setup.py`
- Modify: `tests/test_review_trace.py`, `tests/test_review_traceability_contract.py`, `tests/test_workspace_layout.py`
- Modify: `SKILL.md`, `README.md`, `docs/usage.md`
- Modify: `docs/installation.md`, `CHANGELOG.md`, `references/archive/artifacts.md`
- Modify: `references/archive/history.md`, `references/archive/lifecycle-trace.md`, `references/archive/recovery.md`
- Modify: `references/contracts/result-contract.md`, `references/execution/external-cli.md`, `references/execution/reviewers.md`
- Modify: `references/execution/worker-packets.md`, `references/execution/workspaces.md`, `references/maintenance/evaluation.md`
- Modify: `references/maintenance/measurements.md`, `references/reporting/delivery.md`, `references/reporting/publication.md`
- Remove: `scripts/review_artifacts.py`, `scripts/review_check_provenance.py`, `scripts/review_check_receipts.py`
- Remove: `scripts/review_comment.py`, `scripts/review_contract.py`, `scripts/review_delivery.py`
- Remove: `scripts/review_execution.py`, `scripts/review_harness.py`, `scripts/review_history.py`
- Remove: `scripts/review_inputs.py`, `scripts/review_layout.py`, `scripts/review_metrics.py`
- Remove: `scripts/review_model_usage.py`, `scripts/review_packets.py`, `scripts/review_preflight.py`
- Remove: `scripts/review_profiles.py`, `scripts/review_publication.py`, `scripts/review_recovery.py`
- Remove: `scripts/review_references.py`, `scripts/review_resource_claims.py`, `scripts/review_restart.py`
- Remove: `scripts/review_restart_refusal.py`, `scripts/review_run_lock.py`, `scripts/review_runner.py`
- Remove: `scripts/review_setup.py`, `scripts/review_trace.py`, `scripts/review_workspace.py`
- Test: `tests/test_script_cli.py`

**Interfaces:**
- Consumes: Tasks 2–11: APIs propietarias de las 12 áreas según spec §3; Task 1: run_cli/cli_inventory y baseline; Task 10: `owned_check_request(root: Path, *, exit_code: int = 0) -> dict` para captura real.
- Produces: cada área `main(argv: list[str] | None = None, *, prog: str | None = None) -> int`; raíz `main(argv: list[str] | None = None) -> int`, prog='ccr'. Registro exacto: artifacts, contract, delivery, history, metrics, packets, recovery, runner, workspace, setup, checks, comment. El root procesa sólo el primer token y pasa argv[1:] intacto al área elegida del registro fijo, con prog='ccr ' + area. __main__ propaga el exit, sin importación de áreas en ayuda raíz. `AREAS: dict[str, str]` en scripts/ccr/cli/main.py contiene las doce equivalencias del spec; importar `import_module` explícitamente desde importlib y cargar sólo AREAS[area], para poder verificar forwarding sin lanzar servicios.

- [ ] **Step 1: Escribir las pruebas del límite extraído**

Añadir los siguientes métodos a una clase unittest.TestCase en `tests/test_script_cli.py`.

```python
def test_root_forwards_the_suffix_without_requoting(self):
    from types import SimpleNamespace
    from unittest.mock import Mock, patch
    from ccr.cli.main import main
    handler = Mock(return_value=7)
    suffix = ['--prompt-file', 'a b.txt', '--', 'literal value']
    with patch('ccr.cli.main.import_module', return_value=SimpleNamespace(main=handler)):
        self.assertEqual(main(['runner', *suffix]), 7)
    handler.assert_called_once_with(suffix, prog='ccr runner')

def test_root_help_does_not_load_work_services(self):
    import io
    from unittest.mock import patch
    from ccr.cli.main import main
    with patch('ccr.cli.main.import_module', side_effect=AssertionError('unexpected service import')):
        with patch('sys.stdout', new=io.StringIO()):
            try:
                code = main(['--help'])
            except SystemExit as result:
                code = result.code
    self.assertEqual(code, 0)

def test_installed_copy_works_from_foreign_cwd(self):
    import os, shutil, subprocess, sys
    from tempfile import TemporaryDirectory
    from ccr.cli.main import AREAS
    with TemporaryDirectory() as directory:
        installed = Path(directory) / 'skill with spaces'
        shutil.copytree(ROOT, installed, ignore=shutil.ignore_patterns('.git', '.worktrees', '__pycache__'))
        env = {key: value for key, value in os.environ.items() if key.upper() != 'PYTHONPATH'}
        original_files = {p.relative_to(installed) for p in installed.rglob('*') if p.is_file()}
        for area in AREAS:
            result = subprocess.run([sys.executable, '-B', str(installed / 'scripts'), area, '--help'],
                cwd=directory, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, (area, result.stderr))
            self.assertIn('ccr ' + area, result.stdout)
        for args, expected in [([], 2), (['unknown-area'], 2), (['--help'], 0)]:
            result = subprocess.run([sys.executable, '-B', str(installed / 'scripts'), *args],
                cwd=directory, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, expected)
        self.assertEqual({p.relative_to(installed) for p in installed.rglob('*') if p.is_file()}, original_files)

def test_checks_cli_reports_successful_capture_of_exit_seven(self):
    import json, subprocess, sys
    from tempfile import TemporaryDirectory
    from script_test_support import owned_check_request
    with TemporaryDirectory() as directory:
        request = owned_check_request(Path(directory), exit_code=7)
        output_dir = request.pop('output_dir')
        request_path = Path(directory) / 'request.json'
        request_path.write_text(json.dumps(request), encoding='utf-8')
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts'), 'checks', 'run',
            '--request', str(request_path), '--output-dir', output_dir], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['receipt']['exit_code'], 7)
```

- [ ] **Step 2: Ejecutar la prueba antes de implementar las APIs nuevas**

Run: `python -B -X utf8 -m unittest discover -s tests -p test_script_cli.py -v`
Expected: FAIL por import/API nueva ausente o por el límite de dependencia todavía incumplido. El fallo debe corresponder a la extracción de esta tarea.

- [ ] **Step 3: Implementar `main(argv: list[str] | None = None) -> int` en `scripts/ccr/cli/main.py` y los parsers de área**

Trasladar parsers/handlers, cambiando parse_args() a parse_args(argv). Preservar defaults/choices/errores y traducción específica por operación. Crear root con tabla estática y carga diferida por allowlist; no usar parse_known_args sobre toda la línea si consume opciones destinadas al área.

La entrada y registro se implementan en scripts/__main__.py y scripts/ccr/cli/main.py; los doce main(argv, *, prog) pertenecen a los archivos de área listados. Importar import_module en cli.main para la carga diferida del mapa AREAS, no desde una ruta elegida por el caller.

- [ ] **Step 4: Migrar los consumidores activos a sus propietarios nuevos**

Cambiar llamadas subprocess, imports normales/dinámicos y monkeypatch al propietario real. Verificar especialmente spec_from_file_location, código Python embebido en tests de locks, references a artifacts.__file__ y mocks de _finish_resource_cleanup_locked. No mantener aliases sys.modules ni importar la fachada retirada desde el paquete.

- [ ] **Step 5: Retirar los 27 scripts legacy**

Eliminar exactamente los paths Remove de Files tras transferir handlers y constantes; comprobar que los tests activos ya no los importan.

- [ ] **Step 6: Actualizar la documentación vigente y la guía de migración**

Actualizar guía de migración con las 12 equivalencias, ruptura de imports, copia completa y nueva ayuda; incluir preflight, setup/checks/comment de 2.14.0. Actualizar instrucciones vigentes; mantener texto histórico y reparar enlaces a código retirado dirigiéndolos a la equivalencia documentada. Registrar ruptura bajo versión pendiente de CHANGELOG sin inventar release publicada.

- [ ] **Step 7: Ejecutar las pruebas para comprobar GREEN**

Run: `python -B -X utf8 -m unittest discover -s tests -p test_script_cli.py -v`
Expected: OK; todos los asserts anteriores pasan. Esto no acredita todavía el resto de flujos.

- [ ] **Step 8: Ejecutar las regresiones del entregable**

Run: `python -B -X utf8 -m unittest discover -s tests`
Run: `git diff --check`
Expected: OK; registrar cualquier skip ambiental y no afirmar cobertura de una suite no ejecutada.

- [ ] **Step 9: Crear el commit del entregable verificado**

```bash
git add -- scripts tests SKILL.md README.md docs/usage.md docs/installation.md docs/script-migration.md CHANGELOG.md references
git diff --cached --check
git commit -m "refactor(cli)!: unificar acceso a los helpers y retirar entradas anteriores"
```

### Task 13: Registrar arquitectura y cerrar integración

**Files:**
- Create: `scripts/README.md`, `docs/validation/2026-10-21-scripts-modularity.md`
- Modify: `tests/script_test_support.py`, `docs/usage.md`
- Test: `tests/test_script_layout.py`, `tests/test_script_dependencies.py`

**Interfaces:**
- Consumes: Task 12: `ccr.cli.main.AREAS: dict[str, str]`, root main y áreas instaladas; Task 1: `module_dependencies(module: str) -> set[str]`; todas las APIs de dominio de Tasks 2–11.
- Produces: el registro estático de cli.main es autoridad de áreas y módulos de parser. README registra los módulos reales y su responsabilidad/efectos/contrato/pruebas. La prueba de dependencias analiza AST, resuelve imports relativos/locales y carga diferida del registro fijo. No exige un número de líneas por módulo ni acceso a todos los documentos durante cada revisión. Helpers sólo de tests en tests/script_test_support.py: `import_graph(scripts_root: Path) -> dict[str, set[str]]`, `cyclic_components(graph: dict[str, set[str]]) -> list[tuple[str, ...]]`; componentes con dos o más nodos o self-loop, nodos y resultados ordenados. Resolver también las aristas fijas del registro AREAS; no ejecutar módulos para analizar el grafo.

- [ ] **Step 1: Escribir las pruebas del límite extraído**

Añadir los dos métodos de grafo siguientes a una clase unittest.TestCase en `tests/test_script_dependencies.py` y los métodos de registro a una clase en `tests/test_script_layout.py`.

```python
def test_dependency_detector_finds_a_cycle(self):
    from script_test_support import cyclic_components
    self.assertEqual(cyclic_components({'a': {'b'}, 'b': {'a'}}), [('a', 'b')])
    self.assertEqual(cyclic_components({'a': {'b'}, 'b': set()}), [])
    self.assertEqual(cyclic_components({'a': {'a'}}), [('a',)])

def test_implementation_graph_has_no_cycles_or_legacy_nodes(self):
    from script_test_support import import_graph, cyclic_components
    graph = import_graph(ROOT / 'scripts')
    self.assertEqual(cyclic_components(graph), [])
    self.assertFalse(list((ROOT / 'scripts').glob('review_*.py')))
    self.assertFalse(any(dep.startswith('review_') for deps in graph.values() for dep in deps))
    forbidden = ('ccr.execution.', 'ccr.cli.', 'ccr.shared.json_io', 'ccr.shared.git',
                 'ccr.shared.paths', 'ccr.archive.reader', 'ccr.archive.integrity',
                 'ccr.archive.transactions', 'ccr.archive.resources', 'ccr.archive.restart_state',
                 'ccr.archive.lifecycle', 'ccr.archive.retention', 'ccr.archive.restart',
                 'ccr.archive.coordination', 'ccr.archive.checkpoints', 'ccr.archive.evidence',
                 'ccr.archive.history', 'ccr.archive.inspection', 'ccr.archive.lookup', 'ccr.workflow.setup')
    for module, deps in graph.items():
        if module.startswith('ccr.contracts.'):
            self.assertFalse(any(dep == blocked or dep.startswith(blocked + '.')
                                 for dep in deps for blocked in forbidden), module)

def test_cli_registry_has_the_twelve_supported_areas(self):
    from ccr.cli.main import AREAS
    self.assertEqual(set(AREAS), {'artifacts', 'contract', 'delivery', 'history',
        'metrics', 'packets', 'recovery', 'runner', 'workspace', 'setup', 'checks', 'comment'})

def test_every_implementation_module_is_registered(self):
    index = (ROOT / 'scripts/README.md').read_text(encoding='utf-8')
    for module in (ROOT / 'scripts/ccr').rglob('*.py'):
        if module.name != '__init__.py':
            self.assertIn(module.relative_to(ROOT).as_posix(), index)
```

- [ ] **Step 2: Ejecutar la prueba antes de implementar las APIs nuevas**

Run: `python -B -X utf8 -m unittest discover -s tests -p test_script_layout.py -v`
Run: `python -B -X utf8 -m unittest discover -s tests -p test_script_dependencies.py -v`
Expected: FAIL por import/API nueva ausente o por el límite de dependencia todavía incumplido. El fallo debe corresponder a la extracción de esta tarea.

- [ ] **Step 3: Implementar `import_graph(scripts_root: Path) -> dict[str, set[str]]` en `tests/script_test_support.py` y registrar los módulos**

Completar el registro y corregir dependencias moviendo validación/política al propietario inferior, sin duplicarla ni resolverla con imports tardíos ocultos. Comprobar copia/ZIP completo y documentación de ruptura. Si la distribución se genera fuera del repo y no está disponible, registrar esa limitación en vez de afirmar que se validó una release externa.

Implementar import_graph/cyclic_components en tests/script_test_support.py. El detector resuelve imports relativos/locales y módulos del registro estático; no ignora aristas por encontrarlas dentro de una función. En el README registrar cada módulo real con responsabilidad, efectos, contrato y pruebas.

- [ ] **Step 4: Ejecutar las pruebas para comprobar GREEN**

Run: `python -B -X utf8 -m unittest discover -s tests -p test_script_layout.py -v`
Run: `python -B -X utf8 -m unittest discover -s tests -p test_script_dependencies.py -v`
Expected: OK; todos los asserts anteriores pasan. Esto no acredita todavía el resto de flujos.

- [ ] **Step 5: Ejecutar las regresiones del entregable**

Run: `python -B -X utf8 -m unittest discover -s tests`
Run: `git diff --check`
Expected: OK; registrar cualquier skip ambiental y no afirmar cobertura de una suite no ejecutada.

Registrar resultados de integración y copia instalada en docs/validation/2026-10-21-scripts-modularity.md. Comprobar además los diez criterios de aceptación de spec §9 contra evidencia concreta; documentar distribución externa no disponible en vez de certificar una release.

- [ ] **Step 6: Crear el commit del entregable verificado**

```bash
git add -- scripts/README.md docs/validation/2026-10-21-scripts-modularity.md tests/script_test_support.py docs/usage.md tests/test_script_layout.py tests/test_script_dependencies.py
git diff --cached --check
git commit -m "docs(scripts): registrar arquitectura y validación de la migración"
```

## Self-Review

- Cobertura del spec: §3 → Task 12; §4 → Files de Tasks 2–13; §5 → Consumes/Produces; §6 → extracciones de Tasks 3–11; §7 → regresiones de Tasks 6–9; §8 → Tasks 12–13; §9 → cierre de Task 13.
- Granularidad: cada Step contiene escribir tests, observar RED, implementar una entrega, observar GREEN, ejecutar regresiones o commit; la caracterización inicial conserva sus pasos propios de captura de expectativas.
- Tipos: se preservan las firmas de la base declaradas en Interfaces; los helpers nuevos de pruebas, encodings y dispatcher están definidos en la tarea que los produce antes de cualquier consumidor.
- Review Focus: copia instalada/argv/exit codes → tests de Task 12; captura de exit 7 → Tasks 10 y 12; replay histórico → escenarios existentes de Task 8; HP/latest → Task 9; cleanup interrumpido → Task 7; read-only y grafo → Tasks 4, 5, 12 y 13.
- Proporción: los bloques de código contienen aserciones y comandos; la implementación queda descrita por interfaces y decisiones, no por cuerpos completos de producto.

## Execution Handoff

Spec y plan pendientes de revisión; checks sin marcar porque no se ha iniciado implementación. Recomendada ejecución nativa secuencial: las tareas comparten contratos de lectura, locks e intents y requieren mantener esos límites entre extracciones. La alternativa con subagentes debe conservar el mismo orden y sus gates de revisión. Elegir el método después de revisar ambos documentos; no crear PR, publicar release ni fusionar por haber preparado este plan.
