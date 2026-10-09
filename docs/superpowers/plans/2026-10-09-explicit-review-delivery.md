# Entregas explícitas y nombres de perfiles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar resultados completos o breves por petición explícita, aclarar la documentación y adoptar focused/standard/deep/extended con compatibilidad histórica.

**Architecture:** Un helper deriva entregas portables del registro retenido hacia un destino nuevo del checkout persistente. El coordinador distingue entrega, archivo interno y estrategia. El nuevo contrato final usa nombres canónicos; los aliases normalizan peticiones antiguas y los registros históricos conservan su versión, contenido y representación.

**Tech Stack:** Python 3.10+, biblioteca estándar, unittest, Git y Markdown.

**Spec:** [Entrega portable](../../../references/delivery.md), [archivo interno](../../../references/artifacts.md), [perfiles](../../../references/profiles.md) y requisitos aprobados en la conversación, incluido el renombrado en este PR.

**Estado documental:** Se creó después de iniciar Tasks 1–2; no se presenta como un plan previo. Sus pasos completados reflejan evidencia registrada. Task 3 se planifica antes de ejecutarla. Continúa la sesión actual en feat/explicit-review-delivery, basada en main e51dcb3a72afc123916cd90bdea277b9d494f9ed.

## Global Constraints

- Full/completa o brief/breve explícitos autorizan entrega; --output solo elige su raíz y no cambia el archivo interno.
- --profile/--delivery/--output son convenciones de petición al agente, no opciones de npx.
- Default: docs/ccr/reviews/<scope-slug>/<review-id>/ en el checkout persistente identificado, nunca inferido del ejecutor temporal.
- Full: informe.md/review.json. Brief: resumen.md. Ambos: .ccr-delivery.json y contexto.md solo si aporta datos adicionales recopilados, máximo 32 KiB y 24 entradas.
- No copiar evidencia cruda/logs/reproducciones/cierre/traza, abrir otra revisión o descubrir fuentes para completar contexto.
- Schema 7 hereda schema 6 y cambia solo los perfiles canónicos a focused/standard/deep/extended. Schemas 1–6 mantienen enums y representación originales.
- Aliases: economy → focused, balanced → standard; deep/extended permanecen. Perfil explícito fijo; mismas estrategias, caps y selección automática.
- Rechazar sobreescritura, traversal, enlaces/reparse, otro repositorio, archivo fuente y temporales registrados; rollback solo de recursos propios.
- Archivo fuente inmutable, APIs históricos de handoff compatibles ante solicitud explícita.
- 2.8.0 pendiente: PR y validación del usuario antes de merge/tag/release y limpieza del worktree activo.

## Review Focus

1. Sin modalidad/rutas relativas: no entregar implícitamente, anclar al proyecto y rechazar traversal/enlaces; tests en Task 1.
2. Fuente histórica/cerrada: conservar bytes, esquema, identidad y representación; tests en Tasks 1 y 3.
3. Proyección: omitir comandos/rutas privadas conservando escenarios, resultados y URLs útiles; tests en Task 1.
4. Contexto/escritura interrumpida: límites, ausencia legítima de Spec/Plan y rollback que preserve archivos ajenos; tests en Task 1.
5. Renombrado: standard conserva verificación sustantiva; aliases no alteran selección explícita; schema 7 conserva gates/IDs/vínculo de archivo; tests en Task 3.

---

### Task 1: Entrega portable

**Files:** Create scripts/review_delivery.py; Test tests/test_review_delivery.py. Consume scripts/review_artifacts.py y scripts/review_contract.py.

**Interfaces:**
- Consumes: validate(run_dir, require_retained=True), repository_identity(project), validate(record), render(record).
- Produces: deliver(run_dir, delivery, project_root, output_root=None, context=None) -> Path; CLI --run-dir/--delivery/--project-root, --output-root y --context opcionales.

- [x] **Step 1: Write the failing tests.** Fuente retenida, modalidad obligatoria, full/brief y destino existente. Assertions de test_full_is_portable_canonical_and_source_is_immutable:

```python
before = self.snapshot(run)
target = Path(delivery.deliver(run, 'full', self.repo))
self.assertEqual(before, self.snapshot(run))
self.assertEqual(set(p.name for p in target.iterdir()),
                 {'informe.md', 'review.json', '.ccr-delivery.json'})
```

- [x] **Step 2: Run tests to verify RED.** Run: python -B -X utf8 -m unittest discover -s tests -p test_review_delivery.py -v. Fallaron por helper ausente antes de implementarlo.
- [x] **Step 3: Implement deliver.** Validar/renderizar antes de escribir; neutralizar referencias privadas, conservar campos decisivos, escribir exclusivamente y registrar hashes/procedencia en recibo.
- [x] **Step 4: Add regression cases.** test_relative_output_root_is_anchored_at_project_in_api_and_cli; test_prepared_archive_cannot_be_delivered; test_business_paths_and_urls_survive_while_unc_and_absolute_paths_do_not; test_context_typed_references_hide_absolute_paths_and_are_bounded; test_write_failure_rolls_back_only_own_preparation. Expected: anclaje correcto, fuente intacta, rechazo sin entrega y archivos ajenos preservados.
- [x] **Step 5: Run tests to verify GREEN.** Comando de Step 2: 19 tests enfocados aprobados, incluidos en 214 tests previos al renombrado.
- [x] **Step 6: Commit.** Incluir el entregable verificado en el commit conjunto de Task 4.

### Task 2: Instrucciones y guías

**Files:** Modify SKILL.md, README.md, CHANGELOG.md; references/artifacts.md, capabilities.md, handoff.md, report-format.md, result-contract.md. Create references/delivery.md, docs/usage.md, docs/installation.md.

**Interfaces:**
- Consumes: modalidades y restricciones de Task 1 y contrato del archivo interno.
- Produces: convenciones inequívocas y ejemplos; README define conceptos por finalidad y enlaza guías detalladas.

- [x] **Step 1: Establish behavioral baseline.** Simular full, brief sin Spec/Plan, output sin modalidad y exportación de revisión cerrada contra instrucciones de base; registrar ambigüedades sin revisar producto.
- [x] **Step 2: Write delivery rules/examples.** Crear delivery.md; sustituir transferencia automática por modalidad explícita; preservar handoff histórico y distinguir raíces.
- [x] **Step 3: Split public documentation.** README de 185 a 95 líneas; uso e instalación/actualización en guías; descarga publicada sigue en 2.7.0.
- [x] **Step 4: Verify instructions/links.** Repetir cuatro escenarios; corregir contradicciones sobre handoff, raíces, versión y resumen. Checker local: 62 enlaces/anclas correctos después del primer plan.
- [x] **Step 5: Commit.** Incluir documentación en el commit de Task 4.

### Task 3: focused/standard con compatibilidad

**Files:** Create tests/test_review_profile_names.py. Modify scripts/review_contract.py, review_artifacts.py, review_delivery.py; tests/test_review_delivery.py; SKILL.md, README.md, docs/usage.md; references/profiles.md, reading-strategy.md, review-areas.md, worker-packets.md, result-contract.md, artifacts.md, report-format.md; CHANGELOG.md.

**Interfaces:**
- Consumes: schema 6 y gates existentes, nombres explícitos de petición y registros schemas 1–6.
- Produces: normalize_profile(value: str) -> str, sin modificar registros; schema 7 con focused/standard/deep/extended; retención/entrega/alocación de IDs conserva identidad.

- [x] **Step 1: Write the failing tests.** record7() deriva de record6() con schema_version=7 y profile='standard'. Assertions:

```python
self.assertEqual(contract.normalize_profile('economy'), 'focused')
self.assertEqual(contract.normalize_profile('balanced'), 'standard')
self.assertEqual(contract.validate(record7()), [])
value = record7()
value['coverage']['verification'] = 'skipped'
value['findings'] = [dict(finding(), id='F001')]
self.assertTrue(any('coverage.verification' in e for e in contract.validate(value)))
```

- [x] **Step 2: Run tests to verify RED.** Run: python -B -X utf8 -m unittest discover -s tests -p test_review_profile_names.py -v. Expected: normalize_profile ausente/schema 7 no soportado.
- [x] **Step 3: Implement versioned names.** Normalizar aliases de petición; schema 7 acepta solo nombres canónicos, schemas 1–6 conservan enums. Extender gates/renderer/IDs, binding review_id y entrega a schema 7.
- [x] **Step 4: Add regression checks.** Standard con candidatos/dudas materiales; deep/extended con cero hallazgos; profile malformado; IDs inválidos; schema 6 sin mutación/cambio de render; retención/cierre/entrega full de schema 7 e identidad adulterada rechazada.
- [x] **Step 5: Verify GREEN.** Comando de Step 2 y suite test_review_delivery.py: aprobadas nuevas reglas y lectura histórica.
- [x] **Step 6: Update instructions/aliases.** focused/standard en instrucciones/ejemplos actuales; estrategias explícitas y aliases normalizados antes de seleccionar. No editar changelog/documentos históricos.
- [x] **Step 7: Commit.** Incorporar código, tests y documentación al commit de Task 4 tras gate integrado.

### Task 4: Integración y PR

**Files:** Create docs/validation/2026-10-09-explicit-review-delivery.md; update este plan y archivos exactos de Tasks 1–3. Logs/cuerpo PR en .worktrees ignorado.

**Interfaces:**
- Consumes: entregables verificados de Tasks 1–3 y main remoto actualizado.
- Produces: commit Conventional Commits en español y PR adjunto para validación; ninguna release sin aprobación.

- [x] **Step 1: Verify base.** 195 tests: 194 aprobados/uno omitido por privilegios de symlinks en Windows. Base e51dcb3; Git omarfrancodev / fofe2803@gmail.com.
- [x] **Step 2: Verify integration before added renaming.** Run python -B -X utf8 -m unittest discover -s tests -v con TEMP/TMP fuera de instalación: 214 tests en 162.119s, 213 aprobados/uno omitido. Sintaxis ocho scripts y siete --help correctos.
- [x] **Step 3: Verify final integration.** Mismo comando tras Task 3: 224 tests en 159.616s, 223 aprobados y uno omitido por privilegios de symlink. Sintaxis de ocho scripts, siete --help, 63 enlaces/anclas y git diff --check correctos; resultados registrados.
- [x] **Step 4: Inspect stage/commit.** Prechecks Git; stage solo archivos de Tasks 1–3, validación y plan. Commit: feat(revision): añadir entregas explícitas y aclarar perfiles.
- [x] **Step 5: Publish branch/create PR.** Fetch/confirmar main; git push -u origin feat/explicit-review-delivery. gh pr create --body-file con cuerpo preparado hacia main; PR #10 creado y adjunto al chat: https://github.com/omarfrancodev/comprehensive-code-review/pull/10. Comprobar head/estado después del push final del plan.
- [x] **Step 6: Record user validation.** El usuario aprobó el PR el 2026-10-09 y autorizó continuar el flujo de merge/release/actualización local/limpieza propia. El estado efectivo de estas operaciones se verifica en GitHub y Git; no lo establece este plan.

## Self-Review

Task 1 cubre entrega/contexto, Task 2 explicitud/documentación, Task 3 nombres compatibles sin alterar estrategia y Task 4 integración/publicación. Las firmas/options/schema son consistentes; los cinco grupos de Review Focus tienen tests asignados. Se detallan decisiones y checks sin transcribir el algoritmo. No se añade otro review ni mediciones de coste.

La implementación verificada quedó en 7c7510a. La aprobación explícita del usuario el 2026-10-09 habilita el cierre del flujo; las operaciones remotas y la limpieza requieren comprobación de sus resultados reales.
