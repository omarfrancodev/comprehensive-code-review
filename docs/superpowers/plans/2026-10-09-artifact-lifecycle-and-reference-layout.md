# Referencias y ciclo de vida de artefactos Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Organizar las referencias y emitir estados, tiempos y vínculos observables sin aumentar la instrumentación obligatoria de una revisión.

**Architecture:** Mantener `review_artifacts` como escritor transaccional y `review_trace` como contrato sin IO. Introducir archive schema 5 para processing, conservar trazabilidad schema 1 y mejorar la emisión a partir de información que ya existe.

**Tech Stack:** Python 3.10+, biblioteca estándar, unittest, Git y Markdown.

**Spec:** [Especificación aprobable](../specs/2026-10-09-artifact-lifecycle-and-reference-layout-design.md).

## Global Constraints

- Python 3.10 o superior; helpers con biblioteca estándar y pruebas con unittest.
- Worktree de desarrollo dentro de `.worktrees/`, desde main actualizado; `.worktrees/` permanece ignorado por Git.
- Nuevo archivo interno: schema 5; lectura compatible con schemas 1, 2, 3 y 4, sin migración automática.
- Contrato final de review: schema 7; packets: schema 1; trazabilidad: schema 1, sin campos nuevos.
- Solo el coordinador persiste la trazabilidad mediante el helper o una alternativa nativa equivalente autorizada por el contrato.
- `recorded_at` conserva el instante real de registro; `occurred_at` desconocido permanece null.
- Sin nuevas mediciones, sondeos de contadores, heartbeats, agentes ni barridos de contexto obligatorios.
- Revisiones cerradas y archivos históricos permanecen inmutables.
- El visor se mantiene en su proyecto separado y no se implementa ni modifica aquí.
- Crear PR para revisión humana; no fusionar, etiquetar ni publicar release sin autorización posterior.

## Review Focus

1. Una interrupción entre manifest y trace no puede aparentar un processing validado ni cambiar los tiempos al recuperar: tarea 2, test_processing_recovery_preserves_pending_event.
2. Un archivo schema 4 no admite processing ni adquiere una migración al abrirlo: tarea 2, test_legacy_states_and_complete_bytes_are_preserved.
3. Un tiempo de metadata contradictorio, ausente o no UTC no se sustituye por la hora de ingestión: tarea 3, test_execution_metadata_rejects_conflicts_and_keeps_unknown_times.
4. Una relación con evento futuro o un destino histórico no canónico no provoca reparación retrospectiva ni búsquedas externas: tarea 4, test_new_local_event_targets_and_legacy_references.
5. Workers con acceso limitado o harness sin reloj no leen todos los contratos ni hacen sondeos adicionales: tarea 5, escenarios de presión documentados y test_selective_loading_and_unknown_observations.

## Preparación y ejecución

Worktree preparado: `.worktrees/feat-artifact-lifecycle`; rama `feat/artifact-lifecycle`; base main `e227349d8082784949c2504f709b033e2231870d`. Las tareas siguientes están pendientes; este documento no registra una implementación ya realizada.

Base verificada el 2026-10-09: `python -B -X utf8 -m unittest discover -s tests`, 224 pruebas, OK con una omisión, 181.551 segundos. Se ejecutó con el temporal normal de Windows y permisos disponibles. Dos intentos ambientales previos quedaron descartados: el sandbox no permitía escribir en su temporal y un temporal anidado en la skill interfería con la política de archivo y los límites de rutas Git. No se modificó producto ni pruebas para obtener este resultado.

Usar `$taskPython` para la ruta del Python disponible y comandos PowerShell `& $taskPython -B -X utf8 ...`. El temporal debe estar fuera de la instalación de la skill y tener permisos de escritura; no usar un temporal anidado dentro del worktree para la suite de fixtures Git. No cambiar las políticas del producto para acomodar restricciones del sandbox.

Método recomendado: ejecución nativa en esta sesión, seguida de revisión independiente de la rama, porque las tareas comparten helpers y gates de recuperación. El usuario selecciona el método al revisar los documentos antes de comenzar código.

---

### Task 1: Ubicaciones canónicas y enlaces de referencias

**Files:**
- Create: `tests/test_reference_layout.py`.
- Move: los 20 archivos de `references/` a las seis carpetas exactas de la tabla de la spec.
- Modify: `SKILL.md`, `README.md`, `docs/usage.md`, `docs/installation.md`, enlaces locales de `docs/superpowers/` y de los archivos movidos.
- Modify: pruebas que fijan rutas antiguas, identificadas con `rg -n 'references|REFS|read_text' tests`.

**Interfaces:**
- Consumes: enlaces Markdown y rutas operativas actuales; tabla de ubicaciones de la spec.
- Produces: una sola ruta canónica por referencia; mismas reglas operativas y carga por fase, sin stubs.

- [ ] **Step 1: Escribir la prueba de estructura y resolución de enlaces.**

En `ReferenceLayoutTests.test_canonical_locations_and_local_links`, fijar el mapa de la spec y comprobar `set(relative_md_paths) == set(expected_paths)`, que ningún `.md` vive directamente en references y que cada destino local Markdown existe. Ignorar URLs, anclas y ejemplos de comandos; resolver rutas desde el archivo fuente, sin interpretar menciones históricas como enlaces.

```python
# expected_paths se define como el mapa literal de 20 rutas de la spec.
self.assertEqual(set(relative_md_paths), set(expected_paths))
self.assertEqual(list((root / 'references').glob('*.md')), [])
```

- [ ] **Step 2: Ejecutar RED.**

Run: `& $taskPython -B -X utf8 -m unittest discover -s tests -p test_reference_layout.py -v`.
Expected: fallo porque faltan las ubicaciones nuevas, no por errores del parser de enlaces.

- [ ] **Step 3: Mover y actualizar rutas.**

Usar `git mv` según la tabla exacta. Actualizar enlaces relativos entre carpetas y desde cada rol. Conservar el contenido histórico de planes; cambiar sus enlaces rotos, no reescribir versiones antiguas. Actualizar constantes de lectura de tests que usan las referencias actuales.

- [ ] **Step 4: Ejecutar GREEN y comprobar diff.**

Ejecutar la prueba de layout y las pruebas de presentación/perfiles/flujo que cargan Markdown. `git diff --check` no debe producir errores. Verificar que la reorganización no añadió lecturas obligatorias ni copias.

- [ ] **Step 5: Commit.**

Commit: `refactor(references): organiza los contratos por responsabilidad`.

### Task 2: Archive schema 5 y transición transaccional a processing

**Files:**
- Modify: `scripts/review_artifacts.py`, `references/archive/artifacts.md`.
- Modify/Test: `tests/test_review_artifacts.py`, `tests/test_review_trace.py`, expectativas de nuevos prepare en `tests/test_review_extended.py` y `tests/test_review_flow_v24.py`.

**Interfaces:**
- Consumes: `review_trace.event_input(raw, helper=False) -> dict`, `_append_trace_events(run, manifest, marker, events, helper=True)` y recuperación existente.
- Produces: `ARCHIVE_SCHEMA_VERSION = 5`, `TRACE_ARCHIVE_SCHEMAS = frozenset({4, 5})`; mismos retornos públicos de prepare/register/retain/close.
- Produces: `_starts_processing(event: dict) -> bool`, predicate puro con kinds/statuses exactos de la spec.

- [ ] **Step 1: Escribir pruebas de estado y compatibilidad.**

`test_processing_starts_on_observed_work_only`: prepare.schema_version == 5 y state == prepared; profile/selected, agent/pending y validation preparatoria conservan prepared; discovery/started cambia a processing; register sigue permitido; retain/close llegan a complete.

```python
run = self.prepare()
self.assertEqual(self.read(run / 'cierre.json')['schema_version'], 5)
self.assertEqual(self.read(run / 'cierre.json')['state'], 'prepared')
artifacts.record_event(run, self.write('start.json', {
    'kind': 'discovery', 'status': 'started', 'summary': 'Pinned discovery began'}))
self.assertEqual(self.read(run / 'cierre.json')['state'], 'processing')
artifacts.register(run, [])
self.retain(run)
self.close(run)
self.assertEqual(self.read(run / 'cierre.json')['state'], 'complete')
```

`test_legacy_states_and_complete_bytes_are_preserved`: fixtures válidos 1–4 se verifican sin modificar bytes; schema 4 rechaza processing; schema 4 abierto conserva prepared al registrar trabajo. Crear fixtures históricos independientes, no cambiar solamente el número de un manifest sin rehacer su ownership/hash como exige el fixture.

`test_processing_recovery_preserves_pending_event`: interrumpir atomic_write del trace, comprobar que validate falla por pendiente; recuperar mediante register, y comparar event_id, occurred_at, recorded_at y sha256 con el evento pendiente original. Probar también interrupción de manifest/marker y no aceptar cambios de hash.

- [ ] **Step 2: Ejecutar RED.**

Run: `& $taskPython -B -X utf8 -m unittest discover -s tests -p test_review_trace.py -v` y el módulo de artifacts.
Expected: nuevas aserciones de schema/processing fallan; las pruebas históricas existentes no se alteran para ocultar regresiones.

- [ ] **Step 3: Implementar estados y soporte compartido de traces.**

Usar constantes en todas las rutas de schema 4, incluyendo `_load_run`, `_verify_files`, `_recover_trace`, append, validate y checkpoints. Validar estados según versión. En `record_event`, después de recuperar y verificar el run, aplicar la transición solo desde prepared/schema 5 antes de la misma transacción append. No crear una segunda escritura independiente ni un nuevo comando start. Mantener retain directo desde prepared y los gates de closing/complete.

- [ ] **Step 4: Ejecutar GREEN.**

Ejecutar modules artifacts, trace, artifact-layout, workspace-layout y extended. Todas las pruebas pasan; los únicos skips deben corresponder a capacidades ambientales realmente ausentes.

- [ ] **Step 5: Commit.**

Commit: `feat(artifacts): registra el inicio efectivo de las revisiones`.

### Task 3: Tiempos observados del helper y metadata opcional

**Files:**
- Modify: `scripts/review_trace.py`, `scripts/review_artifacts.py`, `references/archive/lifecycle-trace.md`, `references/execution/external-cli.md`.
- Modify/Test: `tests/test_review_trace.py`; usar metadata sintético con las claves ya emitidas por `scripts/review_runner.py`, sin modificar su contrato.

**Interfaces:**
- Consumes: metadata existente con `started_at` y `finished_at`; raw event con status/actor/executor/provenance.
- Produces: `review_trace.event_from_execution(raw: dict, metadata: dict, source: str) -> dict`, función pura, sin IO ni cambio de identidad.
- Produces: `record_event(run_dir, event_file, execution_metadata=None) -> dict`, extensión compatible; CLI `--execution-metadata` opcional en record-event.
- Preserves: `_milestone(kind, summary, status='completed', evidence=None) -> dict`, añadiendo campos ya existentes de trace schema 1.

- [ ] **Step 1: Escribir pruebas de tiempos y fuentes.**

`test_helper_milestones_capture_observed_utc_time`: todos los hitos nuevos del helper tienen occurred_at UTC y source `review_artifacts:<kind>`; un evento externo sin reloj conserva null.

`test_execution_metadata_rejects_conflicts_and_keeps_unknown_times`: started elige started_at; passed elige finished_at; timestamps propios coincidentes pasan y contradictorios fallan; null/clave ausente deja null; valor inválido/no UTC falla; estados sin correspondencia fallan si se pide conversión. actor/executor conservan igualdad exacta con el input. La CLI y la función producen el mismo evento temporal.

```python
raw = self.event()
metadata = {'started_at': '2026-10-09T12:00:00+00:00',
            'finished_at': '2026-10-09T12:01:00+00:00'}
value = artifacts.review_trace.event_from_execution(raw, metadata, 'review_runner:run.json')
self.assertEqual(value['occurred_at'], metadata['finished_at'])
self.assertEqual(value['actor'], raw['actor'])
self.assertEqual(value['executor'], raw['executor'])
self.assertIsNone(artifacts.review_trace.event_input(raw)['occurred_at'])
```

`test_historical_time_validation_is_unchanged`: traza schema 1 antigua con occurred_at y source null sigue verificándose; una emisión nueva de archive schema 5 con tiempo externo no null/source null se rechaza.

- [ ] **Step 2: Ejecutar RED.**

Run: `& $taskPython -B -X utf8 -m unittest discover -s tests -p test_review_trace.py -v`.
Expected: ausencia del adaptador y tiempos null de helper. Cambiar la expectativa anterior de prepare null únicamente en la prueba de nuevos runs; mantener fixtures históricos.

- [ ] **Step 3: Implementar captura y adaptador.**

Capturar UTC en `_milestone`, conservar recorded_at en append. Leer metadata solo cuando se proporciona la opción y usar safe_path/read_json existentes. El adaptador usa el mapping exacto de status de la spec, valida UTC, no rellena con datetime.now ni cambia identidad. Con metadata fuente `review_runner:<ruta metadata>` identifica límites del wrapper; sin metadata, validar fuente de ocurrencia solo para emisiones nuevas de schema 5. Mantener `verify` compatible con registros antiguos y recuperación con bytes originales.

- [ ] **Step 4: Ejecutar GREEN.**

Ejecutar trace, artifacts y las pruebas existentes del runner en test_review_metrics.py. Confirmar que el caso normal no produce measurements.json ni obliga a generar metadata adicional.

- [ ] **Step 5: Commit.**

Commit: `feat(trace): conserva tiempos observados y su procedencia`.

### Task 4: Atribución y vínculos explícitos verificables

**Files:**
- Modify: `scripts/review_trace.py`, `scripts/review_artifacts.py`, `references/archive/lifecycle-trace.md`, `references/execution/reviewers.md`, `references/contracts/identifiers.md`.
- Modify/Test: `tests/test_review_trace.py`.

**Interfaces:**
- Consumes: raw normalizado, bytes de trace ya verificados y manifest.schema_version.
- Produces: `review_trace.validate_local_event_targets(event: dict, previous_data: bytes) -> None`; falla con ValueError solo para E locales con seis dígitos inexistentes, sin resolver otras revisiones.
- Preserves: schema 1, tipos de relaciones actuales, actor/executor/recorder separados y límites actuales.

- [ ] **Step 1: Escribir pruebas de destinos e identidad.**

`test_new_local_event_targets_and_legacy_references`: E000001 existente pasa; E000000 y un E futuro fallan; CR de otro run no dispara IO; C001/F001 y referencias heredadas acotadas pasan; el lector histórico mantiene bytes intactos.

```python
run = self.prepare()
event = self.event()
event['relations'] = [{'relation': 'follows', 'target': 'E999999'}]
with self.assertRaises(ValueError):
    artifacts.record_event(run, self.write('future.json', event))
event['relations'][0]['target'] = 'E000001'
artifacts.record_event(run, self.write('observed.json', event))
self.assertEqual(self.events(run)[-1]['relations'], event['relations'])
```

`test_actor_executor_and_recorder_remain_distinct`: actor de worker y executor con IDs conocidos se conservan; recorder es review_artifacts; IDs ausentes siguen null; no se generan relaciones para dos eventos consecutivos sin vínculos de input. Probar 25 relaciones y evento mayor de 8 KiB para conservar rechazo.

- [ ] **Step 2: Ejecutar RED.**

Run: `& $taskPython -B -X utf8 -m unittest discover -s tests -p test_review_trace.py -v`.
Expected: destinos E futuros aún aceptados; no exigir que pruebas de preservación ya válidas fallen.

- [ ] **Step 3: Implementar gate de emisión y reglas de briefs.**

Invocar validación local solo al emitir eventos externos schema 5 después del gate de integridad. No cambiar `verify` para imponer nuevos destinos a trazas históricas. Documentar referencias canónicas F001/C001/E000001 y `CR-<run_id>#<id>`; no renumerar eventos/finding/checks anteriores. Los briefs propagan identidades disponibles y el coordinador emite hitos desde resultados existentes, sin nuevos campos obligatorios de packet.

- [ ] **Step 4: Ejecutar GREEN.**

Ejecutar trace, traceability-contract, packets y tests de identificación/presentación. Confirmar que los checks no leen un archivo externo al resolver una relación cross-review.

- [ ] **Step 5: Commit.**

Commit: `feat(trace): valida vínculos locales y conserva la atribución`.

### Task 5: Instrucciones operativas, documentación y presión de coste

**Files:**
- Modify: `SKILL.md`, `README.md`, `docs/usage.md`, `references/archive/artifacts.md`, `references/archive/lifecycle-trace.md`, `references/workflow/reading-strategy.md`, `references/execution/worker-packets.md`, `references/maintenance/evaluation.md`.
- Create: `tests/test_artifact_lifecycle_policy.py`, `docs/superpowers/validation/2026-10-09-artifact-lifecycle.md`.

**Interfaces:**
- Consumes: ubicaciones de tarea 1; estado y CLI de tareas 2–4.
- Produces: instrucciones selectivas consistentes, ejemplos de nuevos eventos y registro de evidencia de validación, sin introducir un nuevo artefacto obligatorio por review.

- [ ] **Step 1: Escribir prueba de contrato y preparar escenarios RED.**

`test_selective_loading_and_unknown_observations`: el flujo de coordinador enlaza el inicio significativo y la política de tiempos; el worker sigue usando packet schema 1 y brief; la sección de carga no exige maintenance ni todos los archivos. Validar ejemplos JSON con helpers, no solo buscar frases. Registrar tres escenarios: harness sin tiempos/IDs; ejecución estática de un solo coordinador; interrupción tras lanzamiento y antes de retención. Usar skills writing-skills/TDD para comprobar omisiones de comportamiento antes y después del cambio de instrucciones, sin ejecutar reviews sobre proyectos reales.

- [ ] **Step 2: Ejecutar RED.**

Run: `& $taskPython -B -X utf8 -m unittest discover -s tests -p test_artifact_lifecycle_policy.py -v`.
Expected: instrucciones actuales aún no requieren el hito de inicio ni distinguen los nuevos estados; registrar resultados de escenarios sin atribuirles ahorro medido.

- [ ] **Step 3: Actualizar instrucciones y uso.**

Mantener SKILL.md breve: enlazar reglas nuevas y registrar inicio antes de descubrir/lanzar, según evidencia disponible. Expandir solo contratos operativos y docs/usage. Explicar que processing no prueba actividad en vivo, que los consumidores usan orden de registro como fallback y que las fuentes no demuestran veracidad. README enlaza al detalle y describe artefactos por su utilidad actual.

- [ ] **Step 4: Ejecutar GREEN y documentar presión.**

Ejecutar pruebas de policy y flujo existentes; repetir escenarios después de las instrucciones. Confirmar ausencia de timestamps inventados, recorridos completos de references, contadores y agentes adicionales. Registrar exactamente qué comportamiento fue observado y qué quedó limitado, sin afirmar beneficios de tokens sin medición.

- [ ] **Step 5: Commit.**

Commit: `docs(skill): explica el ciclo de vida y las observaciones verificables`.

### Task 6: Verificación de rama y PR de la versión

**Files:**
- Modify: metadata de versión en `SKILL.md`, `CHANGELOG.md` y menciones vigentes que fijen la versión actual.
- Modify: `docs/superpowers/validation/2026-10-09-artifact-lifecycle.md`, estado de ejecución de este plan.

**Interfaces:**
- Consumes: cambios probados de tareas 1–5 y contratos de release actuales.
- Produces: PR completo para revisión humana; 2.9.0 Unreleased, sin tag/release todavía.

- [ ] **Step 1: Preparar versión y changelog.**

Añadir 2.9.0 Unreleased con layout, lifecycle, tiempos/relaciones y compatibilidad. No alterar fechas o versiones de entradas históricas ni prometer que el visor está implementado.

- [ ] **Step 2: Ejecutar verificación completa.**

Run: `& $taskPython -B -X utf8 -m unittest discover -s tests`; `git diff --check`; prueba de resolución de enlaces de tarea 1; ayuda CLI de record-event/prepare/validate. Esperar PASS sin errores/fallos; registrar skips de entorno. No repetir la suite después de pasar salvo cambios nuevos o inquietudes no resueltas.

- [ ] **Step 3: Revisar la rama completa.**

Aplicar requesting-code-review y los gates pertinentes con revisión independiente una vez; corregir defectos y volver a probar solo lo afectado, ampliando si la corrección lo exige. Comprobar compatibilidad schema 4, recuperación, carga selectiva y que no se tocaron archivos del visor ni reviews reales.

- [ ] **Step 4: Commit final y crear PR.**

Comprobar identidad Git omarfrancodev / fofe2803@gmail.com, cambios propios, ausencia de secretos/residuos y main vigente. Commit `feat(skill): prepara la versión 2.9.0`. Push de la rama; crear PR con descripción y validación concreta usando body-file; adjuntarlo a la sesión.

- [ ] **Step 5: Entregar para validación y detener publicación.**

Compartir PR y límites observados. Esperar revisión del usuario. La fecha real del changelog, merge, tag v2.9.0, release, actualización local y limpieza de worktrees corresponden a la autorización posterior; preservar este worktree mientras el PR esté pendiente.
