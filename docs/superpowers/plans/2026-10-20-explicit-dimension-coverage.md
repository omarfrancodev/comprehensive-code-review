# Dimensiones, checks y evidencias de CCR Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Estado:** implementación autorizada y completada el 26 de octubre de 2026; [validación y límites observados](../../validation/2026-10-26-check-evidence-coverage-implementation.md).

**Goal:** hacer explícitos las 27 dimensiones y el propósito de cada check, enlazar evidencias a sus orígenes y presentar cobertura legible en informes y comentarios.

**Architecture:** ampliar final 10 a 11 con dimensiones/purpose y capturar propósito en recibo 2. Compartir bloques Markdown puros y proyecciones por audiencia; conservar archive 8, preflight y reutilización de 3.2.0. Actualizar el camino canónico de comentarios y entregas sin duplicar un ledger de evidencias.

**Tech Stack:** Python 3.10+, biblioteca estándar, unittest, Git y Markdown; paquetes `scripts/ccr`.

**Spec:** [2026-10-20-explicit-dimension-coverage-design.md](../specs/2026-10-20-explicit-dimension-coverage-design.md).

## Global Constraints

- Python 3.10+ y biblioteca estándar; sin dependencias nuevas de producto.
- Usar paquetes scripts/ccr y CLI python <skill>/scripts <área>; no restaurar scripts/review_*.py ni imports legacy.
- Nuevos finales: schema 11 con checks.purpose y las 27 dimensiones; schemas 1–10 conservan sus contratos.
- Mantener archive 8/layout 2, trace 1 y packet version 1; nuevos recibos locales usan schema 2 y se siguen leyendo recibos 1.
- No modificar archivos reales de revisiones, informes retenidos ni comentarios remotos durante esta preparación.
- Conservar criterios, prioridades, hallazgos, perfiles, veredictos, aislamiento, preflight y reglas de reutilización de CCR 3.2.0.
- La matriz ABCDE y los IDs de dimensiones siguen siendo privados; la cobertura pública describe flujos de producto.
- Mantener fuera del alcance el visor, publicación, merge a main y asignación de release. La restricción inicial de no implementar correspondía a la preparación; el usuario autorizó después ejecutar este plan.

## Review Focus

1. Una dimensión ausente o ID no hashable debe dar diagnóstico, no excepción o cobertura implícita: Task 1.
2. Purpose se valida antes del subprocess y coincide con el recibo; recibos 1 históricos no provocan otra ejecución: Tasks 2–4.
3. Dos evidencias del mismo check no duplican su resultado, pero no se pierde un delta o una inspección estática: Task 5.
4. Una clasificación pública de otra fuente, flow omitido o purpose alterado no puede acreditarse con el draft previo: Task 6.
5. Los schemas históricos, recovery exacto y la prueba de cobertura/reuso de 3.2.0 siguen vigentes pese al nuevo layout: Tasks 4, 7–8.

---

## Base, entorno y método

Plan reescrito el 26 de octubre de 2026 sobre CCR 3.2.0, `main=559fc5c`, integrado mediante `bc7d5b6`. Conserva el nombre del archivo y reemplaza las rutas/imports de 2.13.0 del plan anterior. Es propuesta, no evidencia de implementación. [Análisis actual](../../analysis/2026-10-26-check-evidence-coverage-analysis.md).

Trabajar en el worktree `explicit-dimensions-spec` o en el aislamiento acordado para ejecutar el plan. `python` representa el intérprete efectivo; aquí existe en `%USERPROFILE%/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`. Usar `-B`. En Windows, las fixtures que crean worktrees pueden exceder el límite de Git si TEMP/CWD son largos: usar un directorio temporal propio de ruta corta y rutas absolutas a tests/scripts, sin copiar código ni modificar la instalación.

Los bloques Python siguientes son métodos de tests futuros, no comprobaciones ya ejecutadas. Establecer imports con `from script_test_support import enable_package_imports; enable_package_imports()`. Importar módulos de tests existentes mediante alias, no sus clases TestCase, para evitar redescubrimiento accidental.

## File Structure

| Unidad | Archivos y responsabilidad |
|---|---|
| Contrato puro | Nuevos `scripts/ccr/contracts/dimensions.py`, `checks.py`: catálogo/agregación y validación de propósito |
| Captura | `execution/checks.py`, `contracts/receipts.py`: request, captura y binding de recibo 2 |
| Resultado/ledger | `contracts/review.py`, `findings.py`, `packets.py`, `identifiers.py`, `semantic_references.py`: datos 11 y enlaces existentes |
| Garantías heredadas | `contracts/execution.py`, `provenance.py`, `preflight.py`: conservar gates de 10 usando las funciones de perfiles existentes |
| Archivo | `archive/retention.py`, `lifecycle.py`, `inspection.py`, `checkpoints.py`, `history.py`, `cli/artifacts.py`: 10/11 y continuidad |
| Presentación | Nuevo `reporting/blocks.py`; `render.py`, `projections.py`, `comment.py`, `delivery.py`: listas, audiencias y drafts |
| CLI editorial | `cli/comment.py`, `cli/contract.py`: contexto de cobertura explícito |
| Fixtures | Nuevo `tests/traceability_fixtures.py`: solo datos sintéticos, preservando factories históricas |
| Integración/documentación | Tests de cada tarea, `scripts/README.md`, referencias operativas y documentos de Task 8 |

Las rutas de unidades de esta tabla son relativas a `scripts/ccr/`; cada Files de tarea vuelve a indicar rutas completas. Mantener dependencias contratos → contratos/shared puros; no importar ejecución/archivo/reporting desde el contrato nuevo.

### Task 1: Catálogo completo y coherencia de dimensiones

**Files:**

- Create: `scripts/ccr/contracts/dimensions.py`
- Create: `tests/traceability_fixtures.py`
- Test: `tests/test_review_dimensions.py`
- Modify: `scripts/README.md` (registrar el módulo nuevo)

**Interfaces:**

- Consumes: catálogo y agregación de §3 del spec.
- Produces: `DIMENSIONS: dict[str, tuple[str, ...]]`, `DIMENSION_LABELS: dict[str, str]`, `dimension_summary(dimensions: list[dict]) -> dict`, `validate_dimensions(areas: object, finding_ids: set[str]) -> list[str]`.
- Produces fixtures: `dimension_row(identifier: str, status='covered', **updates) -> dict` y `dimension_areas() -> list[dict]`, con cinco áreas y sus 27 dimensiones sintéticas cubiertas. Summary devuelve solo `{status, material, finding_ids}`; referencias ordenadas/únicas. No incorpora aún un envelope 11.

- [x] **Step 1: Write the failing test**

Crear `DimensionTests(unittest.TestCase)`; importar `ccr.contracts.dimensions as dims` y las factories de `traceability_fixtures`.

```python
def test_catalog_completeness_and_hostile_ids(self):
    expected = {a: tuple(f'{a}{i:02d}' for i in range(1, n + 1))
                for a, n in [('A', 5), ('B', 5), ('C', 5), ('D', 5), ('E', 7)]}
    self.assertEqual(dims.DIMENSIONS, expected)
    self.assertEqual(dims.validate_dimensions(dimension_areas(), set()), [])
    for index, area in enumerate(dimension_areas()):
        for item in area['dimensions']:
            rows = dimension_areas()
            rows[index]['dimensions'] = [d for d in rows[index]['dimensions'] if d['id'] != item['id']]
            self.assertTrue(dims.validate_dimensions(rows, set()))
    for invalid in ([], {}, None, 'Z99', 'E01', 'A02'):
        rows = dimension_areas()
        rows[0]['dimensions'][0]['id'] = invalid
        self.assertTrue(dims.validate_dimensions(rows, set()))

def test_summary_states_and_no_hidden_material_gap(self):
    for states, expected in [(['not_applicable'], 'not_applicable'),
        (['covered', 'not_applicable'], 'covered'), (['not_evaluated'], 'not_evaluated'),
        (['covered', 'not_evaluated'], 'partial'), (['partial'], 'partial')]:
        rows = [dimension_row(f'A{i:02d}', status=s) for i, s in enumerate(states, 1)]
        self.assertEqual(dims.dimension_summary(rows)['status'], expected)
    rows = dimension_areas()
    rows[0]['dimensions'][0].update(status='partial', material=True, finding_ids=['F001'])
    self.assertTrue(dims.validate_dimensions(rows, {'F001'}))
    rows[0].update(dims.dimension_summary(rows[0]['dimensions']))
    self.assertEqual(dims.validate_dimensions(rows, {'F001'}), [])
    rows[0]['dimensions'][0].update(status='not_applicable')
    self.assertTrue(dims.validate_dimensions(rows, {'F001'}))

def test_exact_fields_and_details_are_required(self):
    for mutation in ({'details': ' '}, {'extra': 1}, {'material': 'true'}):
        rows = dimension_areas()
        rows[0]['dimensions'][0].update(mutation)
        self.assertTrue(dims.validate_dimensions(rows, set()))
```

- [x] **Step 2: Run test to verify it fails**

Run: `python -B -m unittest discover -s tests -p test_review_dimensions.py -v`

Expected: FAIL por módulo/factories ausentes.

- [x] **Step 3: Implement `dimension_summary` and `validate_dimensions` in `scripts/ccr/contracts/dimensions.py`**

Usar exactamente los IDs de §3, validar tipos antes de conjuntos y rechazar resúmenes contradictorios. Implementar factories de Interfaces y registrar el módulo en el índice; no habilitar parcialmente final 11 todavía.

- [x] **Step 4: Run test to verify it passes**

Run: `python -B -m unittest discover -s tests -p test_review_dimensions.py -v`

Expected: PASS, incluyendo los 27 casos de eliminación e IDs no hashables.

- [x] **Step 5: Commit**

```powershell
git add -- scripts/ccr/contracts/dimensions.py scripts/README.md tests/traceability_fixtures.py tests/test_review_dimensions.py
git commit -m 'feat(cobertura): validar dimensiones explícitas por área'
```

### Task 2: Propósito antes de ejecución y recibo 2

**Files:**

- Create: `scripts/ccr/contracts/checks.py`
- Modify: `scripts/ccr/execution/checks.py` (`_read_request`, `capture_check`)
- Modify: `scripts/ccr/contracts/receipts.py` (`validate_receipt`)
- Modify: `scripts/README.md`
- Modify: `tests/traceability_fixtures.py`, `tests/test_review_check_receipts.py` (requests nuevos de captura)
- Test: `tests/test_review_check_purpose.py`

**Interfaces:**

- Consumes: captura existente de `execution.checks`; `test_review_check_receipts.valid_receipt`, `valid_binding` y `CaptureCheckTests.make_workspace`, conservados para fuentes 1.
- Produces: `purpose_errors(value: object, field: str) -> list[str]` en `contracts/checks.py`: no vacío, máximo 4000, sin controles U+0000–U+001F.
- Produces: `capture_check(*, check_id: str, purpose: str, argv: list[str], command: str, cwd: str, executor_workspace: str, revision: str, executor: str, output_dir: str) -> dict`, con purpose obligatorio y recibo 2. CLI conserva `python <skill>/scripts checks run --request ... --output-dir ...`.
- Produces fixture: `receipt2_bundle() -> tuple[dict, dict[str, bytes], dict, list[dict]]`: receipt, streams seleccionados, check y executors, derivados de las factories 1 sintéticas, añadiendo el mismo purpose al check/recibo. `PURPOSE = 'Verificar que una reclamación conserve una sola ejecución.'`.

- [x] **Step 1: Write the failing test**

Crear `PurposeTests(unittest.TestCase)`; imports: `patch` de unittest.mock; `ccr.contracts.checks.purpose_errors`, `ccr.execution.checks as capture`, `ccr.contracts.receipts as receipts`, `test_review_check_receipts as old`, `receipt2_bundle`, `PURPOSE`.

```python
def test_purpose_validation_precedes_any_process_or_attempt(self):
    for value in (None, '', ' ', 'x' * 4001, 'objetivo\nresultado', 'a\tb'):
        self.assertTrue(purpose_errors(value, 'purpose'))
        with patch.object(capture, '_validate_owned_workspace') as owned:
            with patch.object(capture.subprocess, 'run') as process:
                with self.assertRaises(ValueError):
                    capture.capture_check(check_id='C001', purpose=value, argv=['python', '-V'],
                        command='python -V', cwd='unused', executor_workspace='unused',
                        revision='head', executor='X1', output_dir='unused')
                owned.assert_not_called()
                process.assert_not_called()

def test_receipt2_binds_purpose_and_keeps_legacy_receipt1(self):
    receipt, sources, check, executors = receipt2_bundle()
    self.assertEqual(receipts.validate_receipt(receipt, sources, check=check, executors=executors), [])
    receipt['purpose'] = 'Otro objetivo'
    self.assertTrue(receipts.validate_receipt(receipt, sources, check=check, executors=executors))
    old_check, old_executors = old.valid_binding()
    old_receipt = old.valid_receipt()
    old_sources = {old_receipt['stdout']['reference']: b'', old_receipt['stderr']['reference']: b''}
    self.assertEqual(receipts.validate_receipt(old_receipt, old_sources,
                     check=old_check, executors=old_executors), [])
```

Extender `CaptureCheckTests.test_receipt_preserves_literal_argv_and_previous_attempt` con `purpose=PURPOSE` en capturas/request y aserciones `self.assertEqual(receipt['schema_version'], 2)`, `self.assertEqual(receipt['purpose'], PURPOSE)`. Mantener las aserciones actuales sobre argv literal, hashes, exit y preservación del intento previo. Añadir propósito a los otros requests nuevos del mismo archivo, sin alterar `valid_receipt()` histórica.

- [x] **Step 2: Run test to verify it fails**

Run: `python -B -m unittest discover -s tests -p test_review_check_purpose.py -v`

Expected: FAIL por módulo nuevo, argumento no soportado o recibo 2 no aceptado; no por un workspace sintético inexistente.

- [x] **Step 3: Implement `purpose_errors`, extend capture and version receipt validation**

Validar purpose antes de `_validate_owned_workspace` y de mkdir/subprocess. Request exige el campo y el recibo nuevo copia exactamente el string; no inferirlo del comando/exit. `validate_receipt` distingue shapes 1/2 y compara purpose solo en 2, conservando los demás bindings. Registrar el módulo puro en scripts/README.

- [x] **Step 4: Run test to verify it passes**

```powershell
python -B -m unittest discover -s tests -p test_review_check_purpose.py -v
python -B -m unittest discover -s tests -p test_review_check_receipts.py -v
```

Expected: PASS en ambos; los attempts nuevos producen 2 y las fixtures antiguas 1 siguen válidas.

- [x] **Step 5: Commit**

```powershell
git add -- scripts/ccr/contracts/checks.py scripts/ccr/contracts/receipts.py scripts/ccr/execution/checks.py scripts/README.md tests/traceability_fixtures.py tests/test_review_check_purpose.py tests/test_review_check_receipts.py
git commit -m 'feat(checks): capturar propósito verificable en recibos nuevos'
```

### Task 3: Final 11 y ledger de packets sin pérdida de propósito

**Files:**

- Modify: `scripts/ccr/contracts/review.py`, `scripts/ccr/contracts/findings.py`, `scripts/ccr/contracts/identifiers.py`, `scripts/ccr/contracts/packets.py`, `scripts/ccr/contracts/semantic_references.py`
- Modify: `scripts/ccr/contracts/execution.py`, `scripts/ccr/contracts/provenance.py`, `scripts/ccr/contracts/receipts.py`, `scripts/ccr/contracts/preflight.py`
- Modify: `tests/traceability_fixtures.py`
- Test: `tests/test_review_traceability_contract11.py`
- Modify: `tests/test_review_packets.py`

**Interfaces:**

- Consumes: `validate_dimensions`, `purpose_errors`, recibos 1/2 y contrato final 10 vigente.
- Produces: `review.validate(record, *, reference_index=None, reference_sources=None, reference_context=None, packets=None) -> list[str]` admite final 11 con purpose/dimensiones, conservando las demás garantías de 10.
- Produces: `packets.merge(context, discoveries, verification=None, *, reference_index=None, reference_sources=None) -> dict` admite selector opcional `context.check_schema_version` en {2, 11}; default 2 histórico. Para 11 valida ledger con proyección discovery 11 y execution estructural, sin fabricar historia final; gates de fuentes siguen en preflight.
- Produces fixtures: `record11(profile='focused', source='automatic') -> dict` reusa `recovery_fixtures.record10`, añade `dimension_areas()` y un check C001 estático/aprobado con command `python -V`, revisión head, reference null, execution {kind: static, executor: null}, evidence `Resultado observado` y purpose `PURPOSE`.
- Produces: `set_dimension(record: dict, identifier: str, **updates) -> None`, actualiza la dimensión y su resumen sintético; `record11()` nunca es una migración de un archivo real.
- `identifiers.canonicalize_ids(record, reserved_ids=None) -> tuple[dict, dict]` conserva record/source_maps y remapea también los finding_ids de dimensiones.

- [x] **Step 1: Write the failing test**

Crear `Contract11Tests(unittest.TestCase)`; importar `ccr.contracts.review`, `identifiers`, `packets`, `provenance`; factories de `traceability_fixtures`, `record10` de recovery_fixtures y `finding` de test_review_contract.

```python
def test_new_contract_requires_purpose_and_dimensions_without_changing_10(self):
    self.assertEqual(review.validate(record10()), [])
    for profile in ('focused', 'standard', 'deep', 'extended'):
        for source in ('automatic', 'explicit'):
            self.assertEqual(review.validate(record11(profile, source)), [])
    value = record11()
    del value['checks'][0]['purpose']
    self.assertTrue(any('purpose' in e for e in review.validate(value)))
    value = record11()
    value['coverage']['areas'][0]['dimensions'].pop()
    self.assertTrue(any('dimensions' in e for e in review.validate(value)))

def test_material_gap_and_typed_identifier_allocation(self):
    value = record11()
    set_dimension(value, 'E05', status='partial', material=True)
    self.assertTrue(any('verdict' in e for e in review.validate(value)))
    value['verdict'] = 'insufficient_evidence'
    self.assertEqual(review.validate(value), [])
    value = record11()
    value['findings'] = [dict(finding(), id='D1-F001')]
    set_dimension(value, 'B01', finding_ids=['D1-F001'])
    allocated, sources = identifiers.canonicalize_ids(value)
    self.assertEqual(sources['findings']['D1-F001'], 'F001')
    self.assertEqual(allocated['coverage']['areas'][1]['dimensions'][0]['finding_ids'], ['F001'])
    self.assertEqual(review.validate(allocated), [])

def test_profile_and_executor_guards_are_not_skipped_for_11(self):
    value = record11()
    value['coverage']['execution']['profile_history'] = []
    self.assertTrue(review.validate(value))
    value = record11()
    value['checks'][0]['execution'] = {'kind': 'local', 'executor': 'X1'}
    self.assertTrue(provenance.validate_check_sources(value, []))

def test_historical_reuse_does_not_require_a_new_local_receipt(self):
    value = record11()
    source_url = 'https://example.test/reviews/previous/review.json'
    value['previous_reviews'] = [dict(review_id='CR-' + 'b' * 20,
        reference=source_url, verified=True)]
    value['checks'][0].update(reused=True, reuse_reason='Mismos inputs del comportamiento verificado',
        reference=source_url + '#C001', execution={'kind': 'reused', 'executor': None})
    self.assertEqual(review.validate(value), [])
    self.assertEqual(value['checks'][0]['execution']['kind'], 'reused')
    self.assertFalse(value['checks'][0]['reference'].endswith('-receipt.json'))

def test_merge11_keeps_purpose_without_changing_packet1(self):
    value = record11()
    context = dict(context_id='ctx', scope=value['scope'], checks=value['checks'], check_schema_version=11)
    packet = dict(packet_version=1, stage='discovery', context_id='ctx', findings=[],
        check_ids=['C001'], coverage=dict(flows=['Inspección del contrato'], limitations=[]))
    result = packets.merge(context, [packet])
    self.assertEqual(result['checks'][0]['purpose'], value['checks'][0]['purpose'])
    self.assertEqual(packet['packet_version'], 1)
    del context['checks'][0]['purpose']
    with self.assertRaises(ValueError):
        packets.merge(context, [packet])
```

En test_review_packets conservar los casos existentes sin selector como regresiones del ledger 2. El test nuevo de arriba cubre el ledger 11 con referencias a C001 y rechazo de propósito ausente; no añadir purpose al shape de packet 1.

- [x] **Step 2: Run test to verify it fails**

Run: `python -B -m unittest discover -s tests -p test_review_traceability_contract11.py -v`

Expected: FAIL por schema 11/factories todavía no soportados.

- [x] **Step 3: Extend schema dispatch and typed check preservation**

Exigir purpose solo en 11 e integrar dimensiones; extender a 11 validación de perfiles, provenance, referencias y recibos en sus módulos propietarios. Ledger nuevo usa checks canónicos conocidos; merge conserva el campo, nunca los recorta a schema 2. Recibo 1 no acredita una captura local nueva 11; reutilización histórica conserva kind=reused y fuente original, sin requerir otra ejecución. Preflight mantiene sus diagnósticos, inputs, dispatch-identity y fuentes, sin bypass por cambio de versión.

- [x] **Step 4: Run test to verify it passes**

```powershell
python -B -m unittest discover -s tests -p test_review_traceability_contract11.py -v
python -B -m unittest discover -s tests -p test_review_packets.py -v
python -B -m unittest discover -s tests -p test_review_preflight.py -v
python -B -m unittest discover -s tests -p test_review_check_provenance.py -v
```

Expected: PASS; tipos 11 no eluden guards y ledger 2/packet 1 se mantienen.

- [x] **Step 5: Commit**

```powershell
git add -- scripts/ccr/contracts/review.py scripts/ccr/contracts/findings.py scripts/ccr/contracts/identifiers.py scripts/ccr/contracts/packets.py scripts/ccr/contracts/semantic_references.py scripts/ccr/contracts/execution.py scripts/ccr/contracts/provenance.py scripts/ccr/contracts/receipts.py scripts/ccr/contracts/preflight.py tests/traceability_fixtures.py tests/test_review_traceability_contract11.py tests/test_review_packets.py
git commit -m 'feat(contratos): conservar propósito y dimensiones en final 11'
```

### Task 4: Archivo, preflight y recovery de resultados 10/11

**Files:**

- Modify: `scripts/ccr/archive/retention.py`, `scripts/ccr/archive/lifecycle.py`, `scripts/ccr/archive/inspection.py`, `scripts/ccr/archive/checkpoints.py`, `scripts/ccr/archive/history.py`
- Modify: `scripts/ccr/cli/artifacts.py`
- Modify: `tests/test_review_artifacts.py` (helper retain sintético, guards 10 → 10/11)
- Test: `tests/test_review_traceability_archive.py`

Lookup/reuse no deben cambiar de criterio; sus suites son regresiones, no excusa para reescribirlas.

**Interfaces:**

- Consumes: final 11 y gates de Task 3; helpers `test_review_artifacts as old`, `test_review_checkpoints as checkpoints`.
- Produces: mismas firmas de `retention.retain(..., *, expected_schema=None) -> dict`, `lifecycle.validate(..., require_complete=False) -> dict`, `checkpoints.checkpoint`; archive 8 acepta finales 10/11 y CLI expected-schema 1–11.
- Test support: `TraceabilityCheckpointTests(checkpoints.CheckpointTests)` sobrescribe solo final_record con la misma firma del padre, aplicando schema 11 y dimension_areas a su fixture sintética, añadiendo purpose solo si contiene checks. Los tests originales siguen ejercitando 10; la subclase ejecuta los mismos cortes contra 11.
- Test support: `Archive11Tests(unittest.TestCase)` reutiliza solo atributos de fixture setUp/git/write/read/snapshot/prepare/retain/close de old.ArchiveTests, no hereda sus tests.

- [x] **Step 1: Write the failing test**

Imports: Path, unittest; `ccr.archive.retention as retention`, `ccr.archive.lifecycle as lifecycle`; factories y módulos anteriores.

```python
def test_checkpoint_promotes_exact_11_bytes(self):
    case = TraceabilityCheckpointTests('test_valid_final_checkpoint_can_be_promoted_without_external_files')
    self.addCleanup(case.doCleanups)
    case.setUp()
    run, _, _ = case.prepare_promotable_checkpoint()
    before = (run / 'pending' / 'review.json').read_bytes()
    retention.retain(run, expected_schema=11)
    self.assertEqual((run / 'review.json').read_bytes(), before)
    self.assertEqual(case.read(run / 'review.json')['schema_version'], 11)

def test_missing_purpose_rejected_without_retained_output(self):
    run = self.prepare()
    self.final = self.write('final11.json', record11())
    value = self.read(self.final)
    del value['checks'][0]['purpose']
    self.final = self.write('invalid11.json', value)
    with self.assertRaisesRegex(ValueError, 'purpose'):
        self.retain(run, expected_schema=11)
    self.assertFalse((run / 'review.json').exists())
```

Herencia de TraceabilityCheckpointTests conserva aserciones actuales de retry por límite de escritura, modificación ajena de pending y gate de fuente de perfil. Añadir variante 11 de `test_review_check_receipts.CheckReceiptTests.test_retain_preflight_rejects_missing_selected_receipt` y afirmar `ready=False`, issue `invalid_receipt`; luego proporcionar recibo 2/streams válidos y exigir que desaparezca ese issue, sin suprimir otros gates.

- [x] **Step 2: Run test to verify it fails**

Run: `python -B -m unittest discover -s tests -p test_review_traceability_archive.py -v`

Expected: FAIL por restricción a final 10 o expected-schema 11.

- [x] **Step 3: Admit 11 in archive gates without changing archive schema**

Extender guards explícitos y CLI; conservar preflight de candidato, selección de fuentes retenidas, perfiles y executors. Actualizar solo el helper sintético retain para tratar 11 como trata 10; ninguna fixture histórica adquiere campos. Checkpoints/recovery conservan bytes, no regeneran purpose/dimensiones. No cambiar admisión por equivalencia ni prueba de cobertura heredada de 3.2.0.

- [x] **Step 4: Run test to verify it passes**

```powershell
python -B -m unittest discover -s tests -p test_review_traceability_archive.py -v
python -B -m unittest discover -s tests -p test_review_checkpoints.py -v
python -B -m unittest discover -s tests -p test_review_atomic_recovery.py -v
python -B -m unittest discover -s tests -p test_review_source_selection.py -v
python -B -m unittest discover -s tests -p test_review_reuse*.py -v
```

Expected: PASS; 10 permanece consultable/recuperable y la admisión ordinaria conserva sus decisiones.

- [x] **Step 5: Commit**

```powershell
git add -- scripts/ccr/archive/retention.py scripts/ccr/archive/lifecycle.py scripts/ccr/archive/inspection.py scripts/ccr/archive/checkpoints.py scripts/ccr/archive/history.py scripts/ccr/cli/artifacts.py tests/test_review_artifacts.py tests/test_review_traceability_archive.py
git commit -m 'feat(archivo): conservar gates y recovery para resultados 11'
```

### Task 5: Bloques legibles sin duplicar resultados

**Files:**

- Create: `scripts/ccr/reporting/blocks.py`
- Modify: `scripts/ccr/reporting/render.py`
- Modify: `scripts/README.md`
- Test: `tests/test_review_traceability_rendering.py`

**Interfaces:**

- Consumes: registros ya validados y ledger original; no recibe ni produce un veredicto nuevo.
- Produces: en blocks.py, `evidence_groups(evidence: list[dict], checks: dict[str, dict]) -> list[dict]`, filas `{check_id: str | None, details: list[str]}` en orden estable; `evidence_lines(groups: list[dict]) -> list[str]`; `coverage_lines(flows: list[str]) -> list[str]`.
- Groups elimina solo detalles exactos repetidos en mismo origen, y omite el resultado que coincide exactamente con checks[id].evidence. Un grupo con details=[] todavía genera el enlace a Validación. Estáticas distintas siguen separadas.
- `render(..., audience='user')` muestra purpose/resultado separados, evidencias anidadas, cobertura por elemento y tabla de 27 dimensiones. Estos mismos bloques de evidencias se usan ya en comentario; proyección pública de purpose/cobertura se completa en Task 6. Ausencia histórica de purpose muestra el texto exacto del spec.

- [x] **Step 1: Write the failing test**

Crear RenderingTests; importar `ccr.reporting.blocks`, `ccr.reporting.render as renderer`, `record11` desde `traceability_fixtures`, `DIMENSIONS` desde `ccr.contracts.dimensions` y copy.

```python
def test_same_origin_keeps_delta_static_and_distinct_check(self):
    ledger = {'C001': {'evidence': 'Resultado observado'}, 'C002': {'evidence': 'Otro resultado'}}
    evidence = [dict(kind='executed', check_id='C001', details='Resultado observado'),
        dict(kind='executed', check_id='C001', details='Delta del caso'),
        dict(kind='executed', check_id='C001', details='Delta del caso'),
        dict(kind='static', check_id=None, details='src/jobs.py:claim'),
        dict(kind='executed', check_id='C002', details='Resultado observado')]
    groups = blocks.evidence_groups(evidence, ledger)
    self.assertEqual(groups[0], {'check_id': 'C001', 'details': ['Delta del caso']})
    self.assertEqual(groups[1], {'check_id': None, 'details': ['src/jobs.py:claim']})
    self.assertEqual(groups[2]['check_id'], 'C002')
    lines = '\n'.join(blocks.evidence_lines(groups))
    self.assertEqual(lines.count('**[C001](#C001)**'), 1)
    self.assertIn('**Inspección estática**', lines)

def test_coverage_preserves_order_duplicates_and_escapes(self):
    lines = blocks.coverage_lines(['Flujo A', 'Flujo A', '<script>'])
    self.assertEqual(lines.count('  - Flujo A'), 2)
    self.assertNotIn('<script>', '\n'.join(lines))
    self.assertIn('Sin flujos de cobertura registrados', '\n'.join(blocks.coverage_lines([])))

def test_full_report_preserves_input_and_exposes_objective(self):
    value = record11()
    before = copy.deepcopy(value)
    text = renderer.render(value)
    self.assertIn('  - **Propósito:**', text)
    self.assertIn('  - **Resultado:**', text)
    self.assertIn('- **Cobertura:**\n', text)
    for ids in DIMENSIONS.values():
        for identifier in ids:
            self.assertIn(f'| {identifier} |', text)
    self.assertEqual(value, before)
```

- [x] **Step 2: Run test to verify it fails**

Run: `python -B -m unittest discover -s tests -p test_review_traceability_rendering.py -v`

Expected: FAIL por blocks ausente o layout aún concatenado.

- [x] **Step 3: Implement pure blocks and consume them in render**

Usar markdown_text/table_cell y generar enlaces solo desde IDs validados. Agrupar contra el resultado privado antes de proyección; no inferir origins por similitud ni concatenar evidence/flows. Mantener escenarios/impactos y counts existentes. Registrar blocks.py en scripts/README; no duplicar catálogo ni lógica en cada renderer.

- [x] **Step 4: Run test to verify it passes**

```powershell
python -B -m unittest discover -s tests -p test_review_traceability_rendering.py -v
python -B -m unittest discover -s tests -p test_review_contract.py -v
python -B -m unittest discover -s tests -p test_review_areas.py -v
```

Expected: PASS. Actualizar en estas suites únicamente expectativas Markdown afectadas por el layout deliberado; conservar aserciones semánticas y fixtures originales.

- [x] **Step 5: Commit**

```powershell
git add -- scripts/ccr/reporting/blocks.py scripts/ccr/reporting/render.py scripts/README.md tests/test_review_traceability_rendering.py tests/test_review_contract.py tests/test_review_areas.py
git commit -m 'feat(reportes): mostrar evidencia y cobertura en listas trazables'
```

### Task 6: Propósito y cobertura públicos con draft canónico 2

**Files:**

- Modify: `scripts/ccr/reporting/projections.py`, `scripts/ccr/reporting/render.py`, `scripts/ccr/reporting/comment.py`
- Modify: `scripts/ccr/cli/comment.py`, `scripts/ccr/cli/contract.py`
- Modify: `tests/traceability_fixtures.py`
- Test: `tests/test_review_traceability_comments.py`
- Modify: `tests/test_review_comment.py`, `tests/test_review_publication_policy.py`, `tests/publication_fixtures.py`, `tests/fixtures/scripts_cli_contracts.json`
- Modify: `tests/test_review_contract.py`, `tests/test_review_areas.py`, `tests/test_review_extended.py`, `tests/test_review_flow_v24.py`, `tests/test_review_model_usage.py`, `tests/test_review_presentation.py`, `tests/test_review_profiles.py`, `tests/test_review_traceability_contract.py`, `tests/test_script_reporting_boundaries.py` (llamadores públicos existentes)

**Interfaces:**

- Consumes: bloques de Task 5; public_checks y digest canónico actuales; §7–8 del spec.
- Produces: `public_coverage(record: dict, classification: dict | None = None) -> list[str]` en projections.py, con correspondencia índice/summary de todos los flows y digest exacto.
- Extends: `render(record, audience='user', publication_context=None, *, check_publication_context=None, coverage_publication_context=None) -> str`; `prepare_public_comment(record, *, publication_context=None, check_publication_context=None, coverage_publication_context=None) -> dict`.
- Draft 2 añade coverage_publication_context a los campos 1; verify conserva firma y usa los tres contextos. Draft 1 devuelve stale_draft y se preserva; no implementa un renderer legacy paralelo ni retoca publicaciones.
- Produces fixture: `publication_contexts(record: dict) -> dict`, con kwargs check_publication_context (filas purpose para 11) y coverage_publication_context (cada índice con summary seguro). Los valores son semánticamente los de la fixture, nunca una clasificación del resultado real.
- Produces fixture compartida: `tests/publication_fixtures.py:coverage_classification(record: dict) -> dict`, con digest y filas indexadas de los flows sintéticos. Los tests públicos antiguos la pasan explícitamente; si una fixture contiene detalles privados, suministran su summary de producto explícito. No cambiar `contract_api` para inyectar contextos ocultamente.

- [x] **Step 1: Write the failing test**

Crear CommentTraceTests. Imports: copy, `ccr.reporting.comment as comments`, `ccr.reporting.projections as projections`; factories de Task 3/6.

```python
def test_draft2_contains_public_goal_and_each_flow(self):
    value = record11()
    value['coverage']['flows'] = ['Creación de jobs', 'Reintento de jobs']
    before = copy.deepcopy(value)
    contexts = publication_contexts(value)
    draft = comments.prepare_public_comment(value, **contexts)
    self.assertEqual(draft['schema_version'], 2)
    self.assertIn(value['checks'][0]['purpose'], draft['body'])
    self.assertIn('  - Creación de jobs\n', draft['body'])
    self.assertIn('  - Reintento de jobs\n', draft['body'])
    self.assertNotIn('### Matriz ABCDE', draft['body'])
    self.assertTrue(comments.verify_public_comment(value, draft, draft['body'])['verified'])
    self.assertEqual(value, before)

def test_coverage_context_cannot_omit_duplicate_or_bind_other_source(self):
    value = record11()
    contexts = publication_contexts(value)
    for mutation in ('missing', 'duplicate', 'source'):
        context = copy.deepcopy(contexts['coverage_publication_context'])
        if mutation == 'missing':
            context['flows'].pop()
        elif mutation == 'duplicate':
            context['flows'].append(copy.deepcopy(context['flows'][0]))
        else:
            context['source_sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            projections.public_coverage(value, context)

def test_old_draft_is_stale_and_changed_goal_invalidates_source(self):
    value = record11()
    draft = comments.prepare_public_comment(value, **publication_contexts(value))
    legacy = {k: v for k, v in draft.items() if k != 'coverage_publication_context'}
    legacy['schema_version'] = 1
    with self.assertRaisesRegex(ValueError, 'stale_draft'):
        comments.verify_public_comment(value, legacy, legacy['body'])
    value['checks'][0]['purpose'] = 'Otro objetivo'
    with self.assertRaisesRegex(ValueError, 'source_mismatch'):
        comments.verify_public_comment(value, draft, draft['body'])
```

En tests de CLI ya existentes añadir --coverage-publication-context al prepare/render-comment y verificar body idéntico al renderer, rechazo de cobertura inválida antes de salida, y CRLF solo remoto. Extender la matriz de manipulación existente: cambiar purpose público o summary dentro del draft sin rehacer cuerpo produce body_mismatch; no puede cambiar purpose/status reales.

- [x] **Step 2: Run test to verify it fails**

Run: `python -B -m unittest discover -s tests -p test_review_traceability_comments.py -v`

Expected: FAIL por argumentos/contexto/campos nuevos no soportados.

- [x] **Step 3: Implement source-bound public projections and draft2**

public_checks exige filas con purpose para 11 y conserva shape legacy; public_coverage exige todos los índices. Comentarios con flows necesitan contexto editorial incluso para registros antiguos, sin alterar su JSON. Adaptar todos los llamadores de tests enumerados en Files mediante coverage_classification y pasar el argumento por ambos CLIs; actualizar solo las dos entradas nuevas del inventario CLI. No desactivar validación ni inyectar summaries en el adaptador contract_api. Reutilizar blocks para la misma jerarquía de evidence/coverage; no publicar taxonomía interna. Verify compara render fresco exacto; no aceptar una alteración porque su texto parezca equivalente.

- [x] **Step 4: Run test to verify it passes**

```powershell
python -B -m unittest discover -s tests -p test_review_traceability_comments.py -v
$ccrPublicationSuites = @('test_review_comment.py', 'test_review_publication_policy.py', 'test_review_contract.py', 'test_review_areas.py', 'test_review_extended.py', 'test_review_flow_v24.py', 'test_review_model_usage.py', 'test_review_presentation.py', 'test_review_profiles.py', 'test_review_traceability_contract.py', 'test_script_reporting_boundaries.py')
foreach ($ccrPublicationSuite in $ccrPublicationSuites) {
    python -B -m unittest discover -s tests -p $ccrPublicationSuite -v
    if ($LASTEXITCODE -ne 0) { throw "Falló $ccrPublicationSuite" }
}
python -B -m unittest discover -s tests -p test_script_characterization.py -v
```

Expected: PASS; diagnósticos stale_draft/source_mismatch/body_mismatch según el caso. Las pruebas de versiones antiguas reciben contexto de presentación cuando hay flows, no campos nuevos en los registros.

- [x] **Step 5: Commit**

```powershell
git add -- scripts/ccr/reporting/projections.py scripts/ccr/reporting/render.py scripts/ccr/reporting/comment.py scripts/ccr/cli/comment.py scripts/ccr/cli/contract.py tests/traceability_fixtures.py tests/test_review_traceability_comments.py tests/test_review_comment.py tests/test_review_publication_policy.py tests/publication_fixtures.py tests/fixtures/scripts_cli_contracts.json tests/test_review_contract.py tests/test_review_areas.py tests/test_review_extended.py tests/test_review_flow_v24.py tests/test_review_model_usage.py tests/test_review_presentation.py tests/test_review_profiles.py tests/test_review_traceability_contract.py tests/test_script_reporting_boundaries.py
git commit -m 'feat(comentarios): vincular propósito y cobertura a drafts verificables'
```

### Task 7: Full, brief y handoff conservan información y privacidad

**Files:**

- Modify: `scripts/ccr/reporting/delivery.py`
- Modify: `scripts/ccr/reporting/render.py` (`render_handoff`)
- Test: `tests/test_review_traceability_delivery.py`
- Modify: `tests/test_review_delivery.py` (solo expectativas de layout)

**Interfaces:**

- Consumes: archivo 11 válido de Task 4; bloques/proyecciones de Tasks 5–6.
- Produces: `deliver(run_dir, delivery, project_root, output_root=None, context=None) -> Path` conserva firma y recibo de origen. Purpose es PROSE; dimensiones id/status/finding_ids son STRUCTURAL y details es PROSE.
- Brief lista propósito y resultado de cada check, evidencia como origen/delta y coverage por elemento; dimensiones resumidas por ID/estado con motivos pendientes/N/A. Full conserva todas las dimensiones/relaciones en JSON.
- Extends: `render_handoff(record, context=None, audience='user', publication_context=None, *, check_publication_context=None, coverage_publication_context=None) -> str`. Mantiene purpose, origen de evidencia y cobertura privada sin replicar la interpretación del hallazgo; cuando es público usa las mismas clasificaciones mediante esos kwargs, no publica raw flows.

- [x] **Step 1: Write the failing test**

Crear DeliveryTraceTests. Importar `ccr.reporting.delivery as delivery`, `ccr.reporting.render as renderer`, `record11`, `publication_contexts`, `PURPOSE`; Path y copy. Para tests puramente portátiles usar _Projection con repository_path/archive_root sintéticos. Para entregas de archivo reutilizar los atributos fixture de Archive11Tests de Task 4, sin importar su TestCase como símbolo global.

```python
def test_portable_policy_preserves_purpose_ids_and_sanitizes_prose(self):
    value = record11()
    value['checks'][0]['purpose'] = PURPOSE + r' C:\private\notes.txt'
    before = copy.deepcopy(value)
    projection = delivery._Projection(value,
        {'repository_path': str(self.repo), 'archive_root': str(self.output)},
        self.repo, 'a' * 64)
    portable = projection.value(value)
    self.assertIn(PURPOSE, portable['checks'][0]['purpose'])
    self.assertNotIn('C:\\private', portable['checks'][0]['purpose'])
    self.assertEqual(portable['checks'][0]['id'], 'C001')
    self.assertEqual(sum(len(a['dimensions']) for a in portable['coverage']['areas']), 27)
    self.assertEqual(value, before)

def test_private_handoff_keeps_check_objective_and_coverage(self):
    value = record11()
    text = renderer.render_handoff(value)
    self.assertIn(value['checks'][0]['purpose'], text)
    self.assertIn('- **Cobertura:**\n', text)
```

Añadir full/brief sobre un archivo 11 cerrado: afirmar en ambos Markdown purpose y cada flow, en JSON full schema=11 y 27 dimensiones, en .ccr-delivery source_schema_version=11 y mismo review_id. Comparar snapshot del archivo antes/después para probar lectura sin mutación. Conservar los casos de privado estructural, destinos existentes y rollback de entrega de test_review_delivery.

- [x] **Step 2: Run test to verify it fails**

Run: `python -B -m unittest discover -s tests -p test_review_traceability_delivery.py -v`

Expected: FAIL por purpose/dimensiones sin política portátil o handoff/brief sin los nuevos bloques.

- [x] **Step 3: Extend portable fields and consume shared rendering blocks**

Clasificar explícitamente los campos; conservar IDs y relaciones, rechazar strings desconocidos. Usar bloques compartidos en brief/handoff; no duplicar evidencia del check en el hallazgo. Extender a 11 los guards de identidad/provenance de delivery, sin admitir un JSON sanitizado como fuente de retención.

- [x] **Step 4: Run test to verify it passes**

```powershell
python -B -m unittest discover -s tests -p test_review_traceability_delivery.py -v
python -B -m unittest discover -s tests -p test_review_delivery.py -v
```

Expected: PASS; originales y receipt lineage intactos, sin paths privados en prosa portable.

- [x] **Step 5: Commit**

```powershell
git add -- scripts/ccr/reporting/delivery.py scripts/ccr/reporting/render.py tests/test_review_traceability_delivery.py tests/test_review_delivery.py
git commit -m 'feat(entregas): conservar objetivos y relaciones sin duplicación'
```

### Task 8: Contrato operativo, compatibilidad y validación final

**Files:**

- Modify: `SKILL.md`, `README.md`, `CHANGELOG.md`, `docs/usage.md`, `docs/script-migration.md`, `scripts/README.md`
- Modify: `references/workflow/review-areas.md`, `references/execution/reviewers.md`, `references/execution/worker-packets.md`, `references/execution/workspaces.md`
- Modify: `references/contracts/result-contract.md`, `references/archive/artifacts.md`
- Modify: `references/reporting/report-format.md`, `references/reporting/publication.md`, `references/reporting/delivery.md`
- Modify: `references/dimensions/design-testability.md`, `references/dimensions/contracts-data.md`, `references/dimensions/security-operation.md`
- Create: `docs/validation/2026-10-26-check-evidence-coverage-implementation.md`
- Test: `tests/test_review_traceability_policy.py`

**Interfaces:**

- Consumes: Tasks 1–7 completas; AC1–AC10 del spec.
- Produces: instrucciones coherentes de solicitud/captura/ledger/preflight/retención/publicación, con propósito anterior al resultado y referencias del hallazgo a checks existentes. Nuevo flujo requiere final 11 y recibos 2 cuando capture; packet 1 y datos históricos se conservan.
- Sin cambios en criterios de severidad/veredicto ni reglas de reuse. Documentación operativa en inglés y textos de usuario en español.

- [x] **Step 1: Write the failing test**

Crear PolicyTests; importar Path desde pathlib, unittest, DIMENSIONS desde `ccr.contracts.dimensions` y `from ccr.contracts.packets import validate as validate_packet`. ROOT es `Path(__file__).resolve().parents[1]`.

```python
def test_workflow_requires_new_contract_and_keeps_packet1(self):
    skill = (ROOT / 'SKILL.md').read_text(encoding='utf-8')
    self.assertIn('--expected-schema 11', skill)
    rules = (ROOT / 'references/contracts/result-contract.md').read_text(encoding='utf-8')
    self.assertIn('purpose', rules)
    packet = dict(packet_version=1, stage='discovery', context_id='synthetic',
        findings=[], check_ids=[], coverage=dict(flows=['E05 inspected'],
        limitations=[dict(detail='D05 pending recovery boundary', material=True)]))
    self.assertEqual(validate_packet(packet), [])

def test_dimension_ids_are_documented_in_their_area(self):
    files = {'A': 'design-testability.md', 'B': 'design-testability.md',
             'C': 'contracts-data.md', 'D': 'contracts-data.md', 'E': 'security-operation.md'}
    for area, filename in files.items():
        text = (ROOT / 'references/dimensions' / filename).read_text(encoding='utf-8')
        for identifier in DIMENSIONS[area]:
            self.assertIn(identifier, text)
```

- [x] **Step 2: Run test to verify it fails**

Run: `python -B -m unittest discover -s tests -p test_review_traceability_policy.py -v`

Expected: FAIL por reglas/IDs todavía no documentados, manteniendo el caso packet 1 válido.

- [x] **Step 3: Update operating instructions and compatibility documentation**

Documentar purpose request → recibo → ledger → resultado, grupos de evidencia, listas de flows, contexto público obligatorio, draft 1 stale/draft 2, 27 dimensiones y reuse histórico sin rerun. Mostrar ejemplos completos sintéticos y distinguir fragmentos parciales. Actualizar solo productores vigentes a 11, nunca los ejemplos históricos identificados. Añadir bloque unreleased según CONTRIBUTING sin número de release. Documentar límites de compatibilidad con consumidores antiguos y mantener el visor fuera de alcance.

- [x] **Step 4: Run focused policy and architecture verification**

```powershell
python -B -m unittest discover -s tests -p test_review_traceability_policy.py -v
python -B -m unittest discover -s tests -p test_reference_layout.py -v
python -B -m unittest discover -s tests -p test_script_*.py -v
```

Expected: PASS, módulos nuevos indexados y sin ciclos ni dependencias IO desde contratos puros.

- [x] **Step 5: Run complete verification**

```powershell
python -B -m unittest discover -s tests -v
git diff --check
```

Expected: exit 0 en ambos. La suite incluye matrices extensas de restart/resources y admisión por equivalencia; no repetirlas si ya terminaron. Registrar omisiones reales, no convertirlas en aprobación.

- [x] **Step 6: Record observed evidence**

Crear el registro de implementación de Files con comandos/resultados/exit codes, conteos y límites. Contrastar AC1–AC10 y la separación propósito/resultado/impacto con ejemplos antes/después, escenarios estáticos sin check, dos checks con mismo resultado, reuse de recibo 1 y clasificación pública equivocada. No atribuir calidad de juicio del modelo a simples assertions estructurales.

- [x] **Step 7: Commit**

```powershell
git add -- SKILL.md README.md CHANGELOG.md docs/usage.md docs/script-migration.md scripts/README.md references/workflow/review-areas.md references/execution/reviewers.md references/execution/worker-packets.md references/execution/workspaces.md references/contracts/result-contract.md references/archive/artifacts.md references/reporting/report-format.md references/reporting/publication.md references/reporting/delivery.md references/dimensions/design-testability.md references/dimensions/contracts-data.md references/dimensions/security-operation.md docs/validation/2026-10-26-check-evidence-coverage-implementation.md tests/test_review_traceability_policy.py
git commit -m 'docs(trazabilidad): exigir propósito y presentación coherente de evidencias'
```

## Self-Review

| Criterio | Tareas y comprobación |
|---|---|
| AC1 dimensiones completas/agregadas | 1 y 3 |
| AC2 purpose antes de proceso y retención | 2 y 4 |
| AC3 propósito request/recibo/ledger/final | 2 y 3 |
| AC4 datos históricos/recovery sin nuevo proceso | 2 y 4; suites 10 existentes preservadas |
| AC5–AC6 orígenes, estáticas y no duplicación | 5 |
| AC7 cobertura por elemento y cardinalidad pública | 5 y 6 |
| AC8 full/brief/handoff y privacidad | 6 y 7 |
| AC9 drafts/CLI/contextos exactos | 6 |
| AC10 garantías y reutilización de 3.2.0 | 3, 4 y suite completa 8 |

Cada tarea tiene Files, Consumes/Produces, aserciones concretas en código, RED/GREEN y commit. No se asigna un nuevo campo a propósito de materiales ni se usa runner como capturador de checks. No hay cuerpos de implementación de producto en el plan. Los bloques de tests y fixtures se completan en su tarea, con firmas definidas antes de consumirlas.

## Execution Handoff

Las ocho tareas se completaron en el worktree acordado mediante ejecución Native. La revisión fresca de toda la rama confirmó tres defectos importantes, reproducidos y corregidos en una única pasada RED→GREEN. La suite completa final ejecutó 953 casos: 950 aprobados y 3 omitidos por privilegios de symlink en Windows; un caso con acceso denegado temporal pasó en su reintento con código idéntico. Se conservan rama y worktree para integración posterior. El [registro de validación](../../validation/2026-10-26-check-evidence-coverage-implementation.md) recoge resultados, decisiones, compatibilidad y límites.
