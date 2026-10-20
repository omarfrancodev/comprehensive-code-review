# Cobertura explícita de dimensiones ABCDE Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** impedir omisiones silenciosas mediante 27 dimensiones obligatorias con estado, evidencia o motivo, visibles en los reportes nuevos.

**Architecture:** un módulo puro define el catálogo y valida dimensiones y resúmenes. Final schema 11 incorpora ese contrato; los helpers existentes conservan provenance, archive 8 y continuidad de schema 10. Los renderers consumen los mismos datos para el informe, comentario público y entregas.

**Tech Stack:** Python 3.10+, biblioteca estándar, unittest, Git y Markdown.

**Spec:** [2026-10-20-explicit-dimension-coverage-design.md](../specs/2026-10-20-explicit-dimension-coverage-design.md).

## Global Constraints

- Python 3.10+ y biblioteca estándar; no agregar dependencias de producto.
- Los nuevos resultados finales usan schema 11; los schemas 1–10 conservan sus reglas y bytes históricos.
- Mantener archive schema 8, layout version 2, trace schema 1 y packet version 1.
- No migrar, reabrir ni reescribir archivos reales de revisiones para completar dimensiones antiguas.
- Mantener perfiles, independencia, gates de proyecto, IDs de hallazgos/checks y reglas de veredicto existentes.
- Los comentarios públicos omiten la taxonomía ABCDE y de dimensiones; las brechas materiales conservan su impacto público.
- El visor externo no se modifica ni se declara compatible con schema 11 en esta entrega.
- No asignar versión de release, publicar, hacer merge ni modificar datos reales de reviews durante esta preparación.

## Review Focus

1. IDs no hashables, ausentes, duplicados o colocados en otra área producen errores con ruta, nunca excepciones ni cobertura implícita: Task 1.
2. Una dimensión pendiente material impide aprobar aunque el resumen del área intente marcarse cubierto: Tasks 1–2.
3. Schema 11 conserva historia de perfiles, fuentes y provenance de checks; ninguna rama de versión los omite: Tasks 2–3.
4. Texto hostil y rutas privadas en dimensiones se escapan o sanean sin cambiar IDs ni el resultado original: Tasks 4–5.
5. Archivos y operaciones interrumpidas de schema 10 conservan sus bytes; recuperar no inventa dimensiones: Task 3.

---

## Estado y preparación

Plan propuesto, pendiente de revisión y elección del método de ejecución. Base `main` / `09eeb03` / CCR 2.13.0; worktree `.worktrees/explicit-dimensions-spec`, rama `docs/explicit-dimensions-spec`. Este documento no registra implementación.

Ejecutar desde el worktree aislado. `python` representa el intérprete efectivo; si WindowsApps no funciona, usar `%USERPROFILE%/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`. Fijar TEMP/TMP a un temporal propio y usar `-B`. Sin instalaciones ni datos reales de reviews.

Los bloques de tests son métodos para las clases indicadas, con imports explícitos por tarea. Son código a escribir durante implementación; no se ejecutan como parte de preparar este documento. No modificar fixtures históricas para que aparenten evidencia nueva.

## File Structure

| Archivo | Responsabilidad |
|---|---|
| `scripts/review_dimensions.py` (nuevo) | Catálogo, etiquetas, resumen y validación puros |
| `scripts/review_contract.py` | Schema 11 y presentación privada/pública |
| `scripts/review_profiles.py`, `scripts/review_execution.py`, `scripts/review_check_provenance.py`, `scripts/review_publication.py` | Garantías heredadas de schema 10 |
| `scripts/review_artifacts.py`, `scripts/review_history.py` | Gates de archivo, identidad y continuidad; recovery consume estos lectores sin cambiar su formato |
| `scripts/review_delivery.py` | Full/brief y política de datos portátiles |
| `tests/dimension_fixtures.py` (nuevo) | Construcción exclusivamente sintética de dimensiones y finales 11 |
| `tests/test_review_dimensions.py` (nuevo) | Contrato puro y envelope 11 |
| `tests/test_review_dimensions_archive.py` (nuevo) | Persistencia, lectura y checkpoint/recovery |
| `tests/test_review_dimensions_rendering.py` (nuevo) | Informe y comentario público |
| `tests/test_review_dimensions_delivery.py` (nuevo) | Entregas y saneamiento |
| `tests/test_review_dimension_policy.py` (nuevo) | Correspondencia de catálogo, packet 1 e instrucciones |
| Referencias y documentación de Task 6 | Contrato operativo y resultados observados |

### Task 1: Catálogo y validación pura de las 27 dimensiones

**Files:**
- Create: `scripts/review_dimensions.py`
- Create: `tests/dimension_fixtures.py`
- Test: `tests/test_review_dimensions.py`

**Interfaces:**
- Consumes: secciones 3–4 del spec; no depende todavía de schema 11 ni de archivos de reviews.
- Produces: `DIMENSIONS: dict[str, tuple[str, ...]]`, `DIMENSION_LABELS: dict[str, str]`, `dimension_summary(dimensions: list[dict]) -> dict`, `validate_dimensions(areas: object, finding_ids: set[str]) -> list[str]` en `review_dimensions.py`.
- Produces: `dimension_row(identifier: str, status='covered', **updates) -> dict` y `dimension_areas() -> list[dict]` en `dimension_fixtures.py`. La primera devuelve exactamente `{id, status, details, material, finding_ids}`; la segunda crea las cinco áreas sintéticas, todas cubiertas, con sus 27 dimensiones y resúmenes coherentes. No usa resultados retenidos.
- `dimension_summary` consume filas ya válidas y devuelve únicamente `{status, material, finding_ids}`, con referencias ordenadas y únicas. `validate_dimensions` recibe datos arbitrarios y devuelve errores con rutas `coverage.areas[i]...` sin lanzar errores de tipo.

- [ ] **Step 1: Write the failing test**

En `tests/test_review_dimensions.py`, crear `DimensionCatalogTests(unittest.TestCase)`; imports: `copy`, `unittest`, `contract` desde `test_review_contract` (establece scripts en sys.path), `review_dimensions as dimensions`, y `dimension_row`, `dimension_areas` desde `dimension_fixtures`. Añadir estos métodos:

```python
def test_exact_catalog_and_every_missing_dimension(self):
    expected = {a: tuple(f'{a}{i:02d}' for i in range(1, n + 1))
                for a, n in [('A', 5), ('B', 5), ('C', 5), ('D', 5), ('E', 7)]}
    self.assertEqual(dimensions.DIMENSIONS, expected)
    self.assertEqual(set(dimensions.DIMENSION_LABELS), {i for ids in expected.values() for i in ids})
    self.assertEqual(dimensions.validate_dimensions(dimension_areas(), set()), [])
    for index, area in enumerate(dimension_areas()):
        for identifier in expected[area['area']]:
            rows = dimension_areas()
            rows[index]['dimensions'] = [d for d in rows[index]['dimensions'] if d['id'] != identifier]
            self.assertTrue(any(f'coverage.areas[{index}].dimensions' in e
                                for e in dimensions.validate_dimensions(rows, set())))

def test_malformed_rows_return_errors(self):
    for bad in ('Z99', 'E01', [], {}, None):
        rows = dimension_areas()
        rows[0]['dimensions'][0]['id'] = bad
        self.assertTrue(dimensions.validate_dimensions(rows, set()))
    for change in ({'id': 'A02'}, {'details': ' '}, {'extra': True},
                   {'status': 'unknown'}, {'material': 'true'}, {'finding_ids': ['missing']}):
        rows = dimension_areas()
        rows[0]['dimensions'][0].update(change)
        self.assertTrue(dimensions.validate_dimensions(rows, set()))
    rows = dimension_areas()
    del rows[0]['dimensions'][0]['details']
    self.assertTrue(dimensions.validate_dimensions(rows, set()))

def test_summary_truth_table_and_finding_union(self):
    for states, expected in [(['not_applicable'], 'not_applicable'),
        (['covered', 'not_applicable'], 'covered'),
        (['not_evaluated', 'not_applicable'], 'not_evaluated'),
        (['covered', 'not_evaluated'], 'partial'), (['partial'], 'partial')]:
        rows = [dimension_row(f'A{i:02d}', status=s) for i, s in enumerate(states, 1)]
        self.assertEqual(dimensions.dimension_summary(rows)['status'], expected)
    rows = [dimension_row('A01', finding_ids=['F001']),
            dimension_row('A02', status='partial', material=True, finding_ids=['F001'])]
    self.assertEqual(dimensions.dimension_summary(rows),
                     {'status': 'partial', 'material': True, 'finding_ids': ['F001']})

def test_parent_and_nonapplicability_cannot_hide_inconsistency(self):
    for update in ({'status': 'partial'}, {'material': True}, {'finding_ids': ['F001']}):
        rows = dimension_areas()
        rows[0].update(update)
        self.assertTrue(dimensions.validate_dimensions(rows, {'F001'}))
    for update in ({'material': True}, {'finding_ids': ['F001']}):
        rows = dimension_areas()
        rows[0]['dimensions'][0].update(status='not_applicable', **update)
        self.assertTrue(dimensions.validate_dimensions(rows, {'F001'}))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -B -m unittest discover -s tests -p test_review_dimensions.py -v`

Expected: FAIL por `review_dimensions` ausente. Fallos del intérprete o permisos no son RED funcional.

- [ ] **Step 3: Implement `dimension_summary(dimensions: list[dict]) -> dict` and `validate_dimensions(areas: object, finding_ids: set[str]) -> list[str]` in `scripts/review_dimensions.py`**

Definir los 27 IDs y sus etiquetas según el spec. Validar shape exacto y tipos antes de usar conjuntos; aplicar la tabla de agregación y unión, materialidad y restricciones N/A. Implementar las dos factories sintéticas de Interfaces en `tests/dimension_fixtures.py`. Mantener esta tarea pura: no habilitar parcialmente schema 11 en el contrato raíz.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -B -m unittest discover -s tests -p test_review_dimensions.py -v`

Expected: PASS, cuatro métodos y todos sus casos internos, sin excepción ante IDs no hashables.

- [ ] **Step 5: Commit**

```powershell
git add -- scripts/review_dimensions.py tests/dimension_fixtures.py tests/test_review_dimensions.py
git commit -m 'feat(cobertura): validar catálogo y dimensiones explícitas'
```

### Task 2: Final schema 11 con veredicto y provenance íntegros

**Files:**
- Modify: `scripts/review_contract.py:93` (`validate`) y `:553` (`canonicalize_ids`)
- Modify: `scripts/review_profiles.py:258` (`validate_profile_execution`)
- Modify: `scripts/review_execution.py:10` (`validate_execution`) y `:208` (`validate_execution_sources`)
- Modify: `scripts/review_check_provenance.py:8` y `:37` (validación de checks y fuentes)
- Modify: `scripts/review_publication.py:11` (`public_limitations`)
- Modify: `tests/dimension_fixtures.py`
- Test: `tests/test_review_dimensions.py`

**Interfaces:**
- Consumes: catálogo, factories y funciones puras de Task 1.
- Produces: `review_contract.validate(record) -> list[str]` y `canonicalize_ids(record, reserved_ids=None) -> tuple[dict, dict]` aceptan 11 con todas las garantías heredadas de 10; la segunda conserva su retorno `(record, source_maps)`. Schemas 1–10 mantienen sus reglas. Se conservan firmas existentes de los validadores de ejecución/perfiles/checks.
- Produces: `record11(profile='focused', source='automatic') -> dict`, que copia `recovery_fixtures.record10(profile, source)`, fija schema 11 y usa `dimension_areas()`; y `set_dimension(record: dict, identifier: str, **updates) -> None`, que actualiza una dimensión sintética y recomputa únicamente status/material/finding_ids de su área usando `dimension_summary`.

- [ ] **Step 1: Write the failing test**

Añadir `DimensionFinalTests(unittest.TestCase)` en `test_review_dimensions.py`. Imports adicionales: `record11`, `set_dimension`; `record10` desde `recovery_fixtures`; `finding` desde `test_review_contract`; `check` desde `test_review_traceability_contract`; `validate_check_sources` desde `review_check_provenance`.

```python
def test_schema11_requires_dimensions_but_10_does_not(self):
    self.assertEqual(contract.validate(record10()), [])
    for profile in ('focused', 'standard', 'deep', 'extended'):
        for source in ('automatic', 'explicit'):
            self.assertEqual(contract.validate(record11(profile, source)), [])
    value = record11()
    self.assertEqual(contract.validate(value), [])
    del value['coverage']['areas'][0]['dimensions']
    self.assertTrue(any('dimensions' in e for e in contract.validate(value)))

def test_material_gap_and_confirmed_blocker_precedence(self):
    value = record11()
    set_dimension(value, 'E05', status='partial', material=True, details='Concurrent claim remains unverified')
    self.assertTrue(any('verdict' in e for e in contract.validate(value)))
    value['verdict'] = 'insufficient_evidence'
    self.assertEqual(contract.validate(value), [])
    value['findings'] = [dict(finding(blocking=True), id='F001')]
    set_dimension(value, 'B01', finding_ids=['F001'])
    value['verdict'] = 'not_approvable'
    self.assertEqual(contract.validate(value), [])
    value['findings'][0]['status'] = 'rejected'
    self.assertTrue(any('finding_ids' in e for e in contract.validate(value)))

def test_schema11_keeps_profile_and_check_guards(self):
    for field, bad in [('profile_history', []), ('plan', [])]:
        value = record11()
        value['coverage']['execution'][field] = bad
        self.assertTrue(contract.validate(value))
    value = record11()
    value['coverage']['execution']['plan'][0]['selection_id'] = 'S999'
    self.assertTrue(contract.validate(value))
    value = record11()
    value['coverage']['execution']['plan'][0]['superseded_by'] = 'S999'
    self.assertTrue(contract.validate(value))
    value = record11()
    value['checks'] = [dict(check(), execution={'kind': 'local', 'executor': None})]
    self.assertTrue(any('executor' in e for e in contract.validate(value)))
    value['checks'][0]['execution']['executor'] = 'X1'
    self.assertTrue(validate_check_sources(value, []))
    self.assertTrue(validate_check_sources(value, [dict(executor='X1', revision='unrelated', snapshot=None)]))

def test_allocation_remaps_dimension_and_parent_references_atomically(self):
    value = record11()
    value['findings'] = [dict(finding(), id='D1-F001')]
    set_dimension(value, 'B01', finding_ids=['D1-F001'])
    allocated, sources = contract.canonicalize_ids(value)
    self.assertEqual(sources['findings']['D1-F001'], 'F001')
    self.assertEqual(allocated['coverage']['areas'][1]['finding_ids'], ['F001'])
    self.assertEqual(allocated['coverage']['areas'][1]['dimensions'][0]['finding_ids'], ['F001'])
    self.assertEqual(contract.validate(allocated), [])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -B -m unittest discover -s tests -p test_review_dimensions.py -v`

Expected: FAIL por factory nueva o schema 11 sin soporte, mientras los tests puros de Task 1 siguen pasando.

- [ ] **Step 3: Extend the schema dispatch in the functions listed under Files**

Implementar `record11` y `set_dimension` según Interfaces. Admitir final 11, exigir `dimensions` solo allí y validar con `validate_dimensions`. Extender explícitamente a 11 los guards de 10 para perfiles, fuentes, checks, IDs y limitaciones públicas; no hacer reemplazo global de versiones. Remapear también `dimensions[].finding_ids` en la asignación atómica de IDs. Reutilizar el efecto actual de brecha material desde el área agregada y conservar prioridad de bloqueantes.

- [ ] **Step 4: Run test to verify it passes**

```powershell
python -B -m unittest discover -s tests -p test_review_dimensions.py -v
python -B -m unittest discover -s tests -p test_review_areas.py -v
python -B -m unittest discover -s tests -p test_review_contract.py -v
python -B -m unittest discover -s tests -p test_review_profiles.py -v
python -B -m unittest discover -s tests -p test_review_check_provenance.py -v
```

Expected: PASS en cada comando; legacy válido sin dimensiones. Ante cualquier exit distinto de cero, resolver antes de seguir.

- [ ] **Step 5: Commit**

```powershell
git add -- scripts/review_contract.py scripts/review_profiles.py scripts/review_execution.py scripts/review_check_provenance.py scripts/review_publication.py tests/dimension_fixtures.py tests/test_review_dimensions.py
git commit -m 'feat(contratos): conservar garantías de schema 10 en schema 11'
```

### Task 3: Archive 8 y continuidad 10/11 sin reconstruir resultados

**Files:**
- Modify: `scripts/review_artifacts.py:1492` (`checkpoint`), `:3624` (`validate`), `:3797` (`retain`) y guards de su diagnóstico de checkpoint/CLI
- Modify: `scripts/review_history.py:62` (`_source_snapshot`)
- Modify: `tests/test_review_artifacts.py:210` (`ArchiveTests.retain`, helper sintético)
- Test: `tests/test_review_dimensions_archive.py`

**Interfaces:**
- Consumes: finales 11 válidos de Task 2; `archive.ArchiveTests` de `test_review_artifacts`; `checkpoints.CheckpointTests` de `test_review_checkpoints`; `record10`, `current_inputs` de `recovery_fixtures`.
- Produces: soporte final 10/11 en archive 8; `retain(run_dir, input_file=None, measurement_inputs=None, unavailable_reason=None, temporary_paths=None, evidence_inputs=None, context_input=None, handoff=False, handoff_context_input=None, *, expected_schema=None) -> dict`, `checkpoint(run_dir, *, context_input, evidence_inputs=None, input_record=None, phase, gate_errors=None, max_evidence_bytes=CHECKPOINT_EVIDENCE_LIMIT) -> dict` y `validate(run_dir, require_retained=False, record_checkpoint=False, *, require_complete=False) -> dict` conservan sus firmas. Expected-schema 11 rechaza 10 antes de escribir resultados. No cambia manifest, layout, reservas ni locks.
- Test support: reutilizar setUp, git, write, read, snapshot, prepare, retain y close de `ArchiveTests` como atributos de `DimensionArchiveTests(unittest.TestCase)`. Su helper `retain` extiende las comparaciones de 10 a `(10, 11)` y el conjunto `(None, 10)` a `(None, 10, 11)`, preservando binding de scope/CR ID/historia y eventos. No altera el resultado de las fixtures 10.
- Test support: `DimensionCheckpointTests(checkpoints.CheckpointTests)` sobrescribe solo `final_record(self, run, profile='focused', late_profile=False) -> dict`: consume el resultado sintético del método padre y le aplica schema 11 y `dimension_areas()`. Los tests heredados de interrupción y promoción se ejecutan así contra 11; los originales siguen ejercitando 10. Importar módulos de tests, no sus clases, evita que unittest redescubra además la clase importada.

- [ ] **Step 1: Write the failing test**

Crear las dos clases anteriores. Imports: `unittest`; `Path` desde `pathlib`; `test_review_artifacts as archive`; `test_review_checkpoints as checkpoints`; `record10`, `current_inputs` desde `recovery_fixtures`; `record11`, `dimension_areas` desde `dimension_fixtures`; `review_history`, `review_recovery`. Definir `artifacts = archive.artifacts`. En `DimensionArchiveTests`, añadir:

```python
def test_retain_close_and_read_both_versions_without_mutation(self):
    for version, factory in [(10, record10), (11, record11)]:
        archive_root = self.root / f'archive-{version}'
        run = self.prepare(output_root=archive_root)
        self.final = self.write(f'final-{version}.json', factory())
        self.retain(run, expected_schema=version)
        self.assertTrue(artifacts.validate(run, require_retained=True)['retained'])
        self.close(run)
        self.assertEqual(artifacts.validate(run, require_complete=True)['state'], 'complete')
        before = self.snapshot(run)
        value = self.read(run / 'review.json')
        self.assertEqual(value['schema_version'], version)
        self.assertEqual(review_history.inspect_source(run)['review_schema'], version)
        result = review_recovery.select_latest(self.repo, value['scope'],
            current_inputs=current_inputs(value['scope'], source_set_complete=True),
            archive_root=archive_root)
        self.assertEqual(result['status'], 'selected')
        self.assertEqual(self.snapshot(run), before)

def test_expected11_rejects10_or_missing_dimension_before_retention(self):
    for name in ('legacy', 'missing'):
        case = DimensionCheckpointTests('test_valid_final_checkpoint_can_be_promoted_without_external_files')
        self.addCleanup(case.doCleanups)
        case.setUp()
        run, _, _ = case.prepare_promotable_checkpoint()
        value = case.read(run / 'pending' / 'review.json')
        if name == 'legacy':
            value['schema_version'] = 10
            for area in value['coverage']['areas']:
                del area['dimensions']
        if name == 'missing':
            value['coverage']['areas'][0]['dimensions'].pop()
        before = case.snapshot(run)
        with self.assertRaisesRegex(ValueError, 'expected schema|dimensions'):
            artifacts.retain(run, case.write(f'{name}.json', value), expected_schema=11)
        self.assertEqual(case.snapshot(run), before)

def test_reserved_checkpoint_keeps_exact_schema11_bytes(self):
    case = DimensionCheckpointTests('test_valid_final_checkpoint_can_be_promoted_without_external_files')
    self.addCleanup(case.doCleanups)
    case.setUp()
    run, _, _ = case.prepare_promotable_checkpoint()
    reserved = (run / 'pending' / 'review.json').read_bytes()
    artifacts.retain(run, expected_schema=11)
    self.assertEqual((run / 'review.json').read_bytes(), reserved)
    self.assertEqual(case.read(run / 'review.json')['schema_version'], 11)
```

`DimensionCheckpointTests` hereda también `test_final_checkpoint_with_profile_source_gate_error_is_not_retained`: sus aserciones exigen ausencia de `review.json` retenido y `archive profile history` en gate_errors. Hereda `test_checkpoint_retry_after_each_write_boundary` y `test_modified_or_foreign_pending_bytes_are_refused`, con las mismas aserciones de bytes e integridad. No copiar sus cuerpos; ejecutar el módulo original prueba 10 y el nuevo prueba 11.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -B -m unittest discover -s tests -p test_review_dimensions_archive.py -v`

Expected: FAIL porque archive 8, expected-schema y/o checkpoint todavía exigen final 10; no aceptar como GREEN una fixture que convierte 11 otra vez a 10.

- [ ] **Step 3: Extend `retain(..., expected_schema=None)`, checkpoint gates and archive readers**

Aplicar a 11 las mismas comprobaciones de identidad, historia, fuentes y ejecutores que a 10. Admitir 10/11 en archive 8 y rango 1–11 en expected-schema, sin modificar el formato del archivo. Implementar únicamente el soporte de tests descrito en Interfaces. Extender el binding CR ID de `review_history._source_snapshot`; conservar bytes de recovery, sin regenerar dimensiones. `review_recovery` ya delega en los lectores actualizados y queda intacto.

- [ ] **Step 4: Run test to verify it passes**

```powershell
python -B -m unittest discover -s tests -p test_review_dimensions_archive.py -v
python -B -m unittest discover -s tests -p test_review_checkpoints.py -v
python -B -m unittest discover -s tests -p test_review_atomic_recovery.py -v
python -B -m unittest discover -s tests -p test_review_execution_policy.py -v
python -B -m unittest discover -s tests -p test_review_archive8.py -v
python -B -m unittest discover -s tests -p test_review_history.py -v
python -B -m unittest discover -s tests -p test_review_latest.py -v
```

Expected: PASS; se registran omisiones reales de plataforma. Las interrupciones simuladas se resuelven según sus tests, sin escribir fuera del temporal sintético.

- [ ] **Step 5: Commit**

```powershell
git add -- scripts/review_artifacts.py scripts/review_history.py tests/test_review_artifacts.py tests/test_review_dimensions_archive.py
git commit -m 'feat(archivo): retener schema 11 y conservar continuidad histórica'
```

### Task 4: Informe explícito y comentario público sin taxonomía interna

**Files:**
- Modify: `scripts/review_contract.py:703` (`render`) y `:851` (`render_handoff`)
- Test: `tests/test_review_dimensions_rendering.py`

**Interfaces:**
- Consumes: `DIMENSIONS`, `DIMENSION_LABELS`, `record11`, `set_dimension` y finales 11 validados de Tasks 1–2.
- Produces: `render(record, audience='user', publication_context=None) -> str` con sección `### Dimensiones evaluadas` entre matriz e incertidumbres; 27 filas ID/nombre/estado/details/hallazgos, ordenadas A–E/ID. `audience='comment'` no genera taxonomía; mantiene impacto material agregado sin duplicados. `render_handoff` hereda la misma cobertura privada. Firmas existentes sin cambios.

- [ ] **Step 1: Write the failing test**

Crear `DimensionRenderingTests(unittest.TestCase)`; imports: `copy`, `unittest`; `contract` desde `test_review_contract`; `record10` desde `recovery_fixtures`; `record11`, `set_dimension` desde `dimension_fixtures`; `DIMENSIONS`, `DIMENSION_LABELS` desde `review_dimensions`. Añadir:

```python
def test_private_report_has_every_dimension_in_order(self):
    value = record11()
    set_dimension(value, 'A01', status='not_applicable', details='No ownership boundary changed')
    set_dimension(value, 'E05', status='not_evaluated', details='Concurrent claim not inspected')
    set_dimension(value, 'D05', status='partial', details='Recovery path partly inspected')
    report = contract.render(value)
    self.assertLess(report.index('### Matriz ABCDE'), report.index('### Dimensiones evaluadas'))
    ordered = [i for ids in DIMENSIONS.values() for i in ids]
    positions = [report.index(f'| {i} |') for i in ordered]
    self.assertEqual(positions, sorted(positions))
    for identifier in ordered:
        self.assertIn(DIMENSION_LABELS[identifier], report)
        self.assertIn(f'| {identifier} |', contract.render_handoff(value))
    for text in ('No ownership boundary changed', 'Concurrent claim not inspected',
                 'Recovery path partly inspected'):
        self.assertIn(text, report)

def test_escaping_legacy_and_input_immutability(self):
    value = record11()
    set_dimension(value, 'A01', details='src/a.py | <script>alert(1)</script>\nnext')
    before = copy.deepcopy(value)
    report = contract.render(value)
    self.assertIn(r'\|', report)
    self.assertNotIn('<script>', report)
    self.assertEqual(value, before)
    self.assertNotIn('### Dimensiones evaluadas', contract.render(record10()))

def test_public_gap_remains_once_without_generated_taxonomy(self):
    value = record11()
    gap = 'Concurrent claim remains unverified'
    set_dimension(value, 'E05', status='partial', material=True, details=gap)
    value['coverage']['areas'][4]['details'] = gap
    value['coverage']['limitations'] = [dict(kind='validation', detail=gap, material=True, public_summary=None)]
    value['verdict'] = 'insufficient_evidence'
    comment = contract.render(value, audience='comment')
    self.assertEqual(comment.count(gap), 1)
    for text in ('### Matriz ABCDE', '### Dimensiones evaluadas', '| E05 |'):
        self.assertNotIn(text, comment)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -B -m unittest discover -s tests -p test_review_dimensions_rendering.py -v`

Expected: FAIL por sección y filas de dimensiones inexistentes; los finales 11 ya son válidos desde Task 2.

- [ ] **Step 3: Extend `render(record, audience='user', publication_context=None) -> str`**

Añadir las tablas privadas desde el catálogo con `table_cell` y escapes existentes; no copiar el catálogo al renderer. Mantener schema 1–10, ausencia de mutación y publicación de brechas por el área agregada. Asegurar que la proyección privada de `render_handoff` usa este mismo resultado sin perder las dimensiones.

- [ ] **Step 4: Run test to verify it passes**

```powershell
python -B -m unittest discover -s tests -p test_review_dimensions_rendering.py -v
python -B -m unittest discover -s tests -p test_review_presentation.py -v
python -B -m unittest discover -s tests -p test_review_publication_policy.py -v
```

Expected: PASS; no taxonomía generada en comentarios ni cambios de representación histórica.

- [ ] **Step 5: Commit**

```powershell
git add -- scripts/review_contract.py tests/test_review_dimensions_rendering.py
git commit -m 'feat(reportes): mostrar las 27 dimensiones con su evidencia'
```

### Task 5: Dimensiones en full/brief y política portátil explícita

**Files:**
- Modify: `scripts/review_delivery.py` (`_Projection`, `_brief`, `deliver`)
- Test: `tests/test_review_dimensions_delivery.py`

**Interfaces:**
- Consumes: archivo 11 válido de Task 3 y renderer de Task 4; fixtures `archive_tests.DimensionArchiveTests` y `record11`.
- Produces: `deliver(run_dir, delivery, project_root, output_root=None, context=None) -> Path` conserva firma y recibo de origen; full mantiene JSON/Markdown con 27 dimensiones; brief enumera todos los IDs por área/estado y motivos pendientes/N/A. `_Projection.value(self, value, path='record')` conserva sus convenciones de ruta y clasifica campos nuevos explícitamente.
- Test support: `DimensionDeliveryTests(unittest.TestCase)` reutiliza solo los atributos de fixture setUp, git, write, read, snapshot, prepare, retain y close de `archive_tests.DimensionArchiveTests`, sin heredar sus tests. No usar `DeliveryTests.retained`, que normaliza a 10, ni importar una clase TestCase adicional que unittest redescubra.

- [ ] **Step 1: Write the failing test**

Imports: `Path` desde `pathlib`; `unittest`; `test_review_dimensions_archive as archive_tests`; `record11`, `set_dimension` desde `dimension_fixtures`; `DIMENSIONS` desde `review_dimensions`; `review_delivery as delivery`. Definir `artifacts = archive_tests.artifacts`. Añadir en `DimensionDeliveryTests`:

```python
def test_full_and_brief_account_for_every_dimension(self):
    value = record11()
    set_dimension(value, 'A01', status='not_applicable', details='No ownership boundary changed')
    set_dimension(value, 'E05', status='not_evaluated', details='Concurrent claim not inspected')
    run = self.prepare()
    self.final = self.write('dimension-final.json', value)
    self.retain(run, expected_schema=11)
    self.close(run)
    before = self.snapshot(run)
    full = Path(delivery.deliver(run, 'full', self.repo, self.root / 'full'))
    brief = Path(delivery.deliver(run, 'brief', self.repo, self.root / 'brief'))
    portable = self.read(full / 'review.json')
    retained = self.read(run / 'review.json')
    self.assertEqual(portable['schema_version'], 11)
    self.assertEqual(portable['review_id'], retained['review_id'])
    self.assertEqual(artifacts.review_contract.validate(portable), [])
    self.assertEqual(sum(len(a['dimensions']) for a in portable['coverage']['areas']), 27)
    self.assertEqual(self.read(full / '.ccr-delivery.json')['source_schema_version'], 11)
    for filename, directory in [('informe.md', full), ('resumen.md', brief)]:
        text = (directory / filename).read_text(encoding='utf-8')
        for identifier in [i for ids in DIMENSIONS.values() for i in ids]:
            self.assertIn(identifier, text)
        self.assertIn('No ownership boundary changed', text)
        self.assertIn('Concurrent claim not inspected', text)
    self.assertEqual(self.snapshot(run), before)

def test_dimension_prose_is_sanitized_and_unknown_fields_refused(self):
    value = record11()
    set_dimension(value, 'A01', details=r'C:\private\notes.txt and /srv/private/notes.txt')
    projection = delivery._Projection(value,
        {'repository_path': str(self.repo), 'archive_root': str(self.output)}, self.repo, 'a' * 64)
    portable = projection.value(value)
    row = portable['coverage']['areas'][0]['dimensions'][0]
    self.assertEqual(row['id'], 'A01')
    self.assertNotIn('C:\\private', row['details'])
    self.assertNotIn('/srv/private', row['details'])
    value['coverage']['areas'][0]['dimensions'][0]['extra'] = 'unclassified'
    with self.assertRaises(ValueError):
        projection.value(value)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -B -m unittest discover -s tests -p test_review_dimensions_delivery.py -v`

Expected: FAIL por nuevos campos sin política portátil o brief sin resumen de dimensiones.

- [ ] **Step 3: Extend `_Projection`, `_brief(record) -> str` and identity guards in `deliver`**

Clasificar `coverage.areas[].dimensions[].id`, `.status`, `.finding_ids[]` como STRUCTURAL y `.details` como PROSE; `.material` usa el manejo booleano actual. Full conserva las filas y brief agrupa todos los IDs por estado con motivos pendientes/N/A, sin reproducir evidencia cubierta. Extender a 11 los guards de identidad y ejecución de 10. Campos desconocidos siguen rechazándose; no sanear IDs ni convertir la salida a 10.

- [ ] **Step 4: Run test to verify it passes**

```powershell
python -B -m unittest discover -s tests -p test_review_dimensions_delivery.py -v
python -B -m unittest discover -s tests -p test_review_delivery.py -v
```

Expected: PASS; el resultado original conserva sus bytes, la entrega valida como 11 y el recibo identifica la fuente real.

- [ ] **Step 5: Commit**

```powershell
git add -- scripts/review_delivery.py tests/test_review_dimensions_delivery.py
git commit -m 'feat(entregas): conservar dimensiones con política portátil explícita'
```

### Task 6: Reglas operativas, escenarios y evidencia de implementación

**Files:**
- Modify: `SKILL.md`
- Modify: `references/workflow/review-areas.md`
- Modify: `references/execution/reviewers.md`, `references/execution/worker-packets.md`
- Modify: `references/contracts/result-contract.md`, `references/archive/artifacts.md`
- Modify: `references/reporting/report-format.md`, `references/reporting/delivery.md`
- Modify: `references/dimensions/design-testability.md`, `references/dimensions/contracts-data.md`, `references/dimensions/security-operation.md`
- Modify: `README.md`, `docs/usage.md`, `CHANGELOG.md`
- Create: `docs/validation/2026-10-20-explicit-dimension-coverage.md`
- Test: `tests/test_review_dimension_policy.py`

**Interfaces:**
- Consumes: soporte completo de Tasks 1–5 y secciones 5–8 del spec.
- Produces: instrucciones en inglés que exigen IDs en briefs/flows/limitations, final 11 y `retain --expected-schema 11`; documentación de usuario en español. Packet version 1 no cambia shape. El registro nuevo distingue resultados observados de escenarios esperados.
- No se crea un motor que interprete prosa de packets. Los escenarios de respuesta omitida y re-review se evalúan en las verificaciones existentes; los tests documentales solo verifican que la regla esté presente.

- [ ] **Step 1: Write the failing test**

Crear `DimensionPolicyTests(unittest.TestCase)`. Imports: `unittest`, `Path`, `contract` desde `test_review_contract`, `DIMENSIONS` desde `review_dimensions`, `validate as validate_packet` desde `review_packets`. Definir `ROOT = Path(__file__).resolve().parents[1]`. Añadir:

```python
def test_catalog_ids_are_present_in_their_operational_references(self):
    files = {'A': 'design-testability.md', 'B': 'design-testability.md',
             'C': 'contracts-data.md', 'D': 'contracts-data.md', 'E': 'security-operation.md'}
    for area, filename in files.items():
        text = (ROOT / 'references/dimensions' / filename).read_text(encoding='utf-8')
        for identifier in DIMENSIONS[area]:
            self.assertIn(identifier, text)

def test_workflow_names_schema_guard_and_no_inferred_coverage(self):
    text = (ROOT / 'SKILL.md').read_text(encoding='utf-8')
    self.assertIn('--expected-schema 11', text)
    rules = (ROOT / 'references/workflow/review-areas.md').read_text(encoding='utf-8')
    self.assertIn('An unanswered applicable dimension remains not_evaluated.', rules)
    self.assertIn('Do not infer dimensions from a legacy area status.', rules)

def test_worker_packet1_accepts_dimension_ids_without_new_fields(self):
    packet = dict(packet_version=1, stage='discovery', context_id='synthetic-context',
        findings=[], check_ids=[], coverage=dict(flows=['E05 inspected in src/jobs.py:claim'],
        limitations=[dict(detail='D05 recovery boundary remains unverified', material=True)]))
    self.assertEqual(validate_packet(packet), [])
    self.assertEqual(set(packet['coverage']), {'flows', 'limitations'})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -B -m unittest discover -s tests -p test_review_dimension_policy.py -v`

Expected: FAIL por IDs y reglas todavía ausentes; el test de packet 1 debe pasar sin cambiar su schema.

- [ ] **Step 3: Update the operational contract and user documentation**

Documentar catálogo, estados, agregación, seguimiento en las asignaciones existentes, re-review y la obligación de cierre con 11. Incluir literalmente las dos reglas inglesas de Step 1 en `review-areas.md`. Actualizar productores nuevos que dicen schema/expected-schema 10; preservar ejemplos históricos identificados. Añadir el bloque unreleased según CONTRIBUTING, sin número de release. Crear el registro de implementación con estos tres escenarios, sus entradas y resultados esperados: E05/A03/D05 comparten una causa y un hallazgo; respuesta omitida a E05 queda pendiente/material cuando impide establecer idempotencia; área antigua cubierta no prueba dimensiones de la nueva revisión. No atribuir resultados observados al modelo si solo se documentaron expectativas.

- [ ] **Step 4: Run focused tests to verify they pass**

```powershell
python -B -m unittest discover -s tests -p test_review_dimension_policy.py -v
python -B -m unittest discover -s tests -p test_reference_layout.py -v
```

Expected: PASS en ambos comandos, sin añadir campos a packet 1 ni referencias locales rotas.

- [ ] **Step 5: Run complete verification**

```powershell
python -B -m unittest discover -s tests -v
git diff --check
```

Expected: ambos comandos con exit 0; identificar omisiones reales de plataforma. La suite completa ya incluye matrices extensas de restart/resources: no repetirlas si completaron aquí.

- [ ] **Step 6: Record observed implementation evidence**

Completar `docs/validation/2026-10-20-explicit-dimension-coverage.md` con comandos, conteos, exit codes, omisiones y alcance real de Steps 4–5. Vincular AC1–AC10 con la tabla de Self-Review y distinguir los tres escenarios documentados de ejecuciones reales del modelo. El registro separado de preparación permanece histórico.

- [ ] **Step 7: Commit**

```powershell
git add -- SKILL.md references/workflow/review-areas.md references/execution/reviewers.md references/execution/worker-packets.md references/contracts/result-contract.md references/archive/artifacts.md references/reporting/report-format.md references/reporting/delivery.md references/dimensions/design-testability.md references/dimensions/contracts-data.md references/dimensions/security-operation.md README.md docs/usage.md CHANGELOG.md docs/validation/2026-10-20-explicit-dimension-coverage.md tests/test_review_dimension_policy.py
git commit -m 'docs(cobertura): exigir trazabilidad explícita y registrar validación'
```

## Self-Review

| Spec | Tareas y evidencia prevista |
|---|---|
| AC1–AC3: catálogo, ausencia/shape y coherencia | Task 1; `DimensionCatalogTests` |
| AC4: materialidad y veredicto | Task 2; `test_material_gap_and_confirmed_blocker_precedence` |
| AC5: informe/full/brief explícitos | Tasks 4–5; `DimensionRenderingTests`, `DimensionDeliveryTests` |
| AC6: impacto público sin taxonomía | Task 4; `test_public_gap_remains_once_without_generated_taxonomy` |
| AC7: identidad, fuentes, recovery y bytes 10/11 | Tasks 2–3; `DimensionFinalTests`, `DimensionArchiveTests`, `DimensionCheckpointTests` |
| AC8: asignación y brechas sin agentes adicionales | Task 6; reglas operativas, packet 1 y escenarios documentados |
| AC9: política portátil | Task 5; `test_dimension_prose_is_sanitized_and_unknown_fields_refused` |
| AC10: legacy y datos sintéticos | Tasks 2–3 y suite completa de Task 6 |

Los seis entregables tienen ciclo RED/GREEN y commit independiente. Ninguna tarea habilita parcialmente schema 11 para que otra deba arreglar sus tests. Los nombres y shapes de fixtures y funciones se definen en Interfaces antes de usarlos. Las cinco clases de Review Focus tienen aserciones asignadas. El plan contiene contratos y tests, no cuerpos de implementación de producto.

## Execution Handoff

Revisar este plan y el spec antes de ejecutar. No se ha seleccionado un método. Se recomienda **Native**, porque las seis tareas dependen del mismo contrato y pueden ejecutarse en secuencia con una revisión de rama al final. **Subagent-driven** permite un implementador y revisor nuevos por tarea, más revisión final; implica contextos adicionales. La elección y revisión del usuario preceden a la implementación.
