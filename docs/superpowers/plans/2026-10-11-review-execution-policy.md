# CCR Publication and Profile Fulfillment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Publicar solo información relevante para el cambio y acreditar el cumplimiento o la degradación real de los perfiles.

**Architecture:** Schema 8 añade limitaciones clasificadas y un registro compacto de ejecución. Dos módulos puros separan las decisiones de audiencia y de cumplimiento; el renderer y el gate de retención usan fuentes existentes, sin otro proceso de auditoría. Mantener lectura histórica y actualizar la rama desde main después del PR #14 antes de integrar el cambio.

**Tech Stack:** Python estándar, unittest, Markdown, Git; sin nuevas dependencias.

**Spec:** [2026-10-11-review-execution-policy-design.md](../specs/2026-10-11-review-execution-policy-design.md).

## Global Constraints

- Resultado nuevo: schema 8, frente a schema 7 actual. Packet schema 1 y trace schema 1 permanecen independientes.
- No añadir campos obligatorios a `cierre.json` por este cambio; adoptar archive schema 6 de #14 cuando se integre.
- Invocar CCR solicita las delegaciones necesarias del perfil explícito o seleccionado automáticamente.
- Skills no habilitan herramientas ni conceden autorización para acciones remotas o ejecutores externos.
- El `context_id` de los packets vincula inputs y puede compartirse; no identifica por sí solo un contexto de agente independiente.
- No modificar reviews cerradas, comentarios de otros autores, configuración del harness, el PR #14 ni la skill instalada durante esta preparación.
- Reutilizar contexto, briefs, resultados y traza; clasificación y gate son trabajo del coordinador.
- Sin nueva medición de créditos, sondeo temporal, heartbeat, auditor/reviewer de perfiles ni segunda revisión completa.
- No publicar/mergear/releasear esta rama antes del gate humano. La versión de release se decide contra el `main` integrado.

## Review Focus

1. Un contexto de inputs compartido entre workers no equivale a reutilizar el mismo contexto de agente: comprobar ambas identidades por separado en Task 2.
2. Una denegación con tiempos/IDs desconocidos sigue siendo evidencia válida, pero una etiqueta de fallback sin fuente no lo es: Task 2 y Task 4.
3. Un gap material presente solo en ABCDE sigue visible públicamente sin copiar los motivos internos: Task 3.
4. Un consumidor antiguo puede leer la fuente sin soportar schema 8; anunciar compatibilidad pendiente, sin asumir soporte del visor: Task 5.
5. Referencias saneadas de una entrega portable no resuelven como archivos locales; validar estructura allí y fuentes reales en el archive original: Task 4.

## Preparación observada

- [x] Confirmar main limpio y PR #14 abierto, crear `feat/review-execution-policy` desde `origin/main` en `.worktrees/review-execution-policy`.
- [x] Verificar `.worktrees/` ignorado e identidad Git `omarfrancodev` / `fofe2803@gmail.com`.
- [x] Suite base: `python -B -X utf8 -m unittest discover -s tests -q`; 237 pruebas, 236 pass / una omitida por Windows, 203.192 s.
- [x] Preparar especificación y este plan; no modificar implementación.
- [x] Obtener revisión de documentos escritos y confirmar método de ejecución; conservar ejecución nativa si el usuario confirma el método usado en este flujo.

## Estructura y responsabilidades

| Archivo | Responsabilidad |
|---|---|
| `scripts/review_execution.py` (nuevo) | Validación pura del plan/resultados/fallback y vínculos con observaciones retenidas |
| `scripts/review_publication.py` (nuevo) | Clasificación/proyección de limitaciones y contexto de publicación histórica |
| `scripts/review_contract.py` | Envelope schema 8, veredicto, renderizado y CLI; no duplicar validaciones de los módulos |
| `scripts/review_artifacts.py` | Binding de identidad y gate de fuentes antes de retener/cerrar |
| `scripts/review_delivery.py` | Compatibilidad de proyecciones full/brief e inmutabilidad de fuente |
| `tests/test_review_execution_policy.py` (nuevo) | Fixture schema 8 y regresiones de cumplimiento/fallback |
| `tests/test_review_publication_policy.py` (nuevo) | Proyecciones públicas/privadas e históricos |
| Tests existentes de contrato, profile names, archive, traceability y delivery | Compatibilidad y bordes entre schemas/helpers |
| Referencias workflow/execution/contracts/reporting/archive, `SKILL.md`, `docs/usage.md` | Política coherente y progresiva; detalles en su referencia propia |
| `CHANGELOG.md`, `docs/validation/2026-10-11-review-execution-policy.md` (nuevo) | Compatibilidad requerida y evidencia del cambio futuro |

### Task 1: Envelope schema 8 y limitaciones clasificadas

**Files:**
- Modify: `scripts/review_contract.py` (`validate`, `canonicalize_ids` y branches por schema).
- Create/Test: `tests/test_review_execution_policy.py` (fixture `record8`).
- Test: `tests/test_review_profile_names.py`, `tests/test_review_traceability_contract.py`.

**Interfaces:**
- Consumes: `record7(profile='standard')` de `tests/test_review_profile_names.py`.
- Produces: `record8(profile='focused') -> dict`, con identidad canónica, limitaciones `{kind, detail, material, public_summary}` y ejecución según la spec; fixture reusable por Tasks 2–4.
- El envelope llama posteriormente `validate_execution(record: dict) -> list[str]` de Task 2; no dejar un final schema 8 utilizable sin su gate.

- [x] **Step 1: Añadir regresiones `test_schema8_requires_typed_limitations`, `test_schema8_keeps_ids_authors_and_verdict_precedence` y `test_legacy_validation_does_not_mutate_source`.** Afirmar: kind desconocido, campos ausentes o material execution sin resumen fallan; execution no material con resumen no null falla; IDs/autores/binding siguen obligatorios; registros 1–7 mantienen sus bytes semánticos y reglas.
- [x] **Step 2: Ejecutar RED.** Run: `python -B -X utf8 -m unittest discover -s tests -p test_review_execution_policy.py -v`. Expected: schema 8 no soportado o ausencia del contrato nuevo, no fallo de importación accidental.
- [x] **Step 3: Extender envelope/limitaciones y canonicalización en `review_contract.py`.** Aceptar schema 8 con nombres focused/standard/deep/extended y todas las obligaciones de schema 7. Conservar branches históricos y packet/merge. No clasificar texto por heurísticas.
- [x] **Step 4: Ejecutar GREEN y regresiones existentes de profiles/traceability.** Repetir comando del Step 2 y `python -B -X utf8 -m unittest discover -s tests -p test_review_profile_names.py -v`; todos los casos aplicables pasan. Task 2 completa el gate de ejecución antes del commit conjunto si separar Task 1 dejara un contrato permisivo.
- [x] **Step 5: Commit del deliverable testable.** `git add scripts/review_contract.py tests/test_review_execution_policy.py`; `git commit -m 'feat(contract): definir resultado de revisión schema 8'`. Si el gate de Task 2 es inseparable, realizar este commit junto con esa tarea, sin checkpoint que declare completo un gate ausente.

### Task 2: Cumplimiento de plan, independencia y fallback

**Files:**
- Create: `scripts/review_execution.py`.
- Modify: `scripts/review_contract.py` (`validate`).
- Test/Modify: `tests/test_review_execution_policy.py`.

**Interfaces:**
- Consumes: spec `coverage.execution` y `record8` de Task 1; no importa `review_contract` para evitar ciclo.
- Produces: `validate_execution(record: dict) -> list[str]`, sin I/O ni mutación; `validate_execution_sources(record: dict, context: dict, trace_events: list[dict], retained_references: set[str]) -> list[str]` para Task 4.
- Resultados/plan usan referencias a contexto/briefs/packets existentes. Una referencia portable puede ser una etiqueta de provenance; su existencia real se verifica solo en el archive original.

- [x] **Step 1: Añadir casos parametrizados de perfiles y degradación.** `test_deep_requires_two_fresh_discoveries_and_grouped_verifier`; `test_extended_counts_follow_selection_source`; `test_same_input_context_is_not_reviewer_identity`; `test_reused_reviewer_context_cannot_claim_independence`; `test_fallback_requires_observed_source`; `test_restriction_does_not_invent_product_defect`; `test_focused_and_clean_standard_do_not_overdelegate`; `test_standard_p3_requires_fresh_verification`. Afirmar deep 2/3 justificados +1 verifier distinto; extended automático 4/5, explícito 2–5; fallback cubre asignaciones incumplidas y no convierte una sesión en independiente.
- [x] **Step 2: Ejecutar RED.** `python -B -X utf8 -m unittest discover -s tests -p test_review_execution_policy.py -v`; los planes incumplidos deben fallar por el gate ausente.
- [x] **Step 3: Implementar interfaces y conectar el gate.** Validar IDs/references, enums, requirements por perfil y verificación real. `fulfilled` satisface asignaciones obligatorias; `degraded` documenta impedimentos para requisitos no cumplidos. Mantener source/IDs null cuando la herramienta no los proporciona. No aceptar «no pidió subagentes» ni pocos slots como impedimento. Separar project gates con fuente propia y límites de discovery; no cambiar precedencia de veredicto por número de agentes.
- [x] **Step 4: Ejecutar GREEN.** Repetir suite focalizada. Añadir `test_profile_transition_needs_observed_source` con contexto/traza coherentes y una transición ausente; la ausencia no se repara fabricando un evento.
- [x] **Step 5: Commit.** `git add scripts/review_execution.py scripts/review_contract.py tests/test_review_execution_policy.py`; `git commit -m 'feat(review): verificar cumplimiento de perfiles y fallback'`.

### Task 3: Proyección pública y clasificación histórica

**Files:**
- Create: `scripts/review_publication.py`, `tests/test_review_publication_policy.py`.
- Modify: `scripts/review_contract.py` (`render`, `render_handoff`, CLI).
- Test: `tests/test_review_contract.py`, `tests/test_review_traceability_contract.py`.

**Interfaces:**
- Consumes: finales validados y limitaciones schema 8; `record8` de Task 1.
- Produces: `publication_digest(record: dict) -> str` (SHA-256 de JSON UTF-8 `ensure_ascii=False`, `sort_keys=True`, `separators=(',', ':')`, `allow_nan=False`); `public_limitations(record: dict, classification: dict | None = None) -> list[dict]` (salida `{detail, material}`, sin mutación).
- `render(record, audience='user', publication_context=None)` y `render_handoff(record, context=None, audience='user', publication_context=None)` preservan llamadas existentes. `--publication-context <json>` se acepta solo para proyección pública; no confundir con el `--context` de handoff.

- [x] **Step 1: Escribir regresiones observables.** `test_internal_execution_detail_stays_private`; `test_material_execution_publishes_impact`; `test_product_session_text_survives`; `test_material_abcde_gap_survives_without_duplicates`; `test_legacy_publication_needs_bound_classification`; `test_public_handoff_uses_same_policy`. Afirmar detalle interno visible en usuario, ausente en comentario; gap material visible, verdict idéntico; frase de sesión del producto intacta; ningún cambio al JSON original.
- [x] **Step 2: Ejecutar RED.** `python -B -X utf8 -m unittest discover -s tests -p test_review_publication_policy.py -v`; reproducción del leak actual y ausencia de clasificación histórica.
- [x] **Step 3: Implementar proyección antes de escribir Markdown.** La spec gobierna `kind/public_summary`. Aplicar saneamiento existente de comandos/rutas después de seleccionar datos. En histórico con limitaciones, exigir hash y una clasificación por índice; no adivinar categorías ni modificar su materialidad. Rechazar contexto duplicado, incompleto, ajeno o inválido antes de producir salida. Conservar lectura/render-user histórico.
- [x] **Step 4: Ejecutar GREEN y CLI.** Repetir suite; añadir subprocess de `render-comment --publication-context`, hash incorrecto y `render-user` con argumento no aplicable. Actualizar tests públicos históricos para proporcionar clasificación explícita cuando corresponde, conservando aserciones de formato y escaping. Revisar que razón del veredicto/reservas/check evidence solo contienen información funcional en fixtures; no declarar un filtro semántico que el código no implementa.
- [x] **Step 5: Commit.** `git add scripts/review_publication.py scripts/review_contract.py tests/test_review_publication_policy.py tests/test_review_contract.py tests/test_review_traceability_contract.py`; `git commit -m 'fix(report): separar limitaciones internas de publicación'`.

### Task 4: Retención, fuentes y entrega portable

**Files:**
- Modify: `scripts/review_artifacts.py`, `scripts/review_delivery.py`.
- Test: `tests/test_review_artifacts.py`, `tests/test_review_delivery.py`, `tests/test_review_execution_policy.py`.

**Interfaces:**
- Consumes: helpers de Tasks 1–3, `validate_execution_sources`, contexto/traza/evidence del run observado y archivo schema 6 después de integrar #14.
- Produces: `retain`/`validate(require_retained=True)` compatibles con schema 8, binding de review ID y fuentes coherentes antes de limpieza; proyecciones full/brief válidas sin exigir acceso a archivos de otro equipo.

- [x] **Step 1: Escribir RED de archive y entrega.** `test_schema8_archive_requires_matching_run_identity`; `test_execution_sources_must_exist_before_retention`; `test_context_trace_profile_mismatch_blocks_retention`; `test_failed_dispatch_is_not_a_completed_reviewer`; `test_schema8_delivery_preserves_source_and_execution_provenance`. Afirmar errores previos a mutación/cleanup; contexto compartido e IDs de provider null admitidos cuando hay evidencia de dispatch/resultados; fuentes ajenas/movidas no pasan.
- [x] **Step 2: Ejecutar suites específicas.** `python -B -X utf8 -m unittest discover -s tests -p test_review_artifacts.py -v` y equivalente `test_review_delivery.py`; observar fallos propios de soporte/gate pendiente.
- [x] **Step 3: Integrar binding schema 8 y gate de fuentes.** Usar evidencia que ya se selecciona para retención y trace verificada; no recorrer todo el archive ni consultar provider history. Referencias con fragmentos se contrastan con sus archivos y registros realmente observados. Tras retener, validar la misma información en lectura. Entregas saneadas conservan la identidad de fuente y satisfacen el contrato estructural; no convierten una etiqueta portable en prueba de ejecución.
- [x] **Step 4: Ejecutar GREEN y comprobar inmutabilidad.** Repetir comandos; cubrir validate read-only, cleanup pending/interrupted y entrega historical/full/brief. No aumentar archive/trace schema ni alterar los cambios de #14 salvo soporte explícito schema 8.
- [x] **Step 5: Commit.** `git add scripts/review_artifacts.py scripts/review_delivery.py tests/test_review_artifacts.py tests/test_review_delivery.py tests/test_review_execution_policy.py`; `git commit -m 'feat(archive): enlazar cumplimiento y retención de schema 8'`.

### Task 5: Instrucciones, pruebas de flujo y PR

**Files:**
- Modify: `SKILL.md`, `references/workflow/profiles.md`, `references/workflow/capabilities.md`, `references/execution/reviewers.md`, `references/execution/worker-packets.md`, `references/contracts/result-contract.md`, `references/reporting/report-format.md`, `references/reporting/publication.md`, `references/reporting/delivery.md`, `references/archive/artifacts.md`, `references/archive/lifecycle-trace.md`, `docs/usage.md`, `CHANGELOG.md`.
- Create: `docs/validation/2026-10-11-review-execution-policy.md`.
- Test: behavioral probes y suite integrada existente; sin tests que solo busquen frases de instrucciones.

**Interfaces:**
- Consumes: resultados y CLI de Tasks 1–4; catálogo/archive integrado desde #14.
- Produces: invocación que solicita la delegación prevista, adaptación nativa con fallback verificable, política pública coherente y PR reviewable.

- [x] **Step 1: Actualizar la rama desde main tras integrar PR #14.** `git fetch origin main`; revisar estado/diff y `git merge origin/main` en este worktree. Resolver únicamente conflictos del alcance; detenerse si aparece una decisión funcional no cubierta. No mergear #14 como parte de esta tarea.
- [x] **Step 2: Escribir las instrucciones mínimas.** Entrypoint: delegación incluida en perfil dentro de permisos y separación interna/pública; detalles de cumplimiento en profiles/capabilities/reviewers, contrato en result-contract, clasificación en reporting. Tandas cuando faltan slots, sin fallback por omisión de petición. Describir fuente requerida, status degraded y relación con verdict; actualizar referencias a nuevo resultado sin reescribir historia.
- [x] **Step 3: Verificar comportamiento con un escenario sintético acotado.** Solicitud deep sin mencionar subagentes, herramientas nativas disponibles y raw inputs neutros: observar dispatch/results independientes y verifier agrupado. Otro escenario con prohibición explícita: observar fallback/gap honesto, sin dispatch. Simular capacidad de una tanda para comprobar que slots limitados no degradan; extender automáticamente solo con cuatro/cinco necesidades documentadas. No consultar ni publicar MRs reales para probarlo. Reusar estos resultados como revisión de comportamiento, sin sumar otro barrido general.
- [x] **Step 4: Verificación integrada.** `python -B -X utf8 -m unittest discover -s tests -v`; helpers `--help`; `git diff --check`; verificar AST/enlaces Markdown y `skill-creator/scripts/quick_validate.py` sobre el worktree. No repetir suite completa sin cambios/fallos que lo justifiquen. Registrar resultados, omisiones y límites sin afirmar prueba semántica o soporte del visor no verificado.
- [ ] **Step 5: Commit de documentación/validación y crear PR.** Elegir versión contra main actual y marcar publicación pendiente; anunciar schema 8 y requisitos del visor independiente, sin implementar el visor. Revisar diff, `git add` con rutas explícitas y commit convencional en español. Push de esta rama; crear descripción con problema, comportamiento y validación real; adjuntar el PR al chat. Esperar validación humana antes de merge/release/limpieza.

## Execution ledger

- Preparación histórica: base `d54be59`, PR #14 abierto con HEAD `3f7a403`; sin cambios de producto/helper ni artifacts de CCR.
- Suite base observada: 237 tests, 236 pass, 1 skip del host. Este resultado no cubre cambios todavía no implementados.
- Estado actual: implementación de Tasks 1–5 y revisión final completadas; PR pendiente de creación/validación humana. No merge/tag/release en este paso.

- Implementación autorizada el 2026-10-11; ejecución nativa. Rama actualizada desde main 28ef2fa en 8b0ee45. Tasks 1–2 se implementan juntas por gate inseparable. RED: schema 8 no soportado; GREEN: contrato y fuentes, compatibilidad de perfiles/trazabilidad.
- Ruling: Contexto retenido registra profile/profile_reference y profile_history opcional; referencia apunta a la observación ya recogida. El gate contrasta dispatch/resultados de la traza, sin inferir identidad desde el contexto de inputs ni consultar provider history.
- Ruling: El cargador del fixture de contrato añade scripts a sys.path, igual que el fixture de archive, para importar los módulos puros sin afectar el CLI de producción.

- Verificación integrada inicial: 282 tests, 281 pass/una omisión del host; AST/enlaces/CLI/diff válidos. quick_validate opcional no disponible por PyYAML; frontmatter idéntico a main.
- Revisión final fresca: dos Important y un Minor reclasificado Important por potencial filtración de detalle interno. Una pasada de corrección RED→GREEN de focused/gate independiente, transición de perfiles y proyección del gap ABCDE; sin re-review. Suite posterior: 288 tests, 287 pass/una omisión del host. Decisiones y límites persistidos en [validación](../../validation/2026-10-11-review-execution-policy.md).
