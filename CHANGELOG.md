# Changelog

Las fechas corresponden a la publicación en GitHub en America/Mexico_City. «Sin publicación registrada» identifica estados históricos sin una release en GitHub; no atribuye una fecha de publicación a su commit.

## 2.8.0 — Pendiente de publicación

- Perfiles focused/standard/deep/extended: economy y balanced permanecen como alias de entrada. El contrato final 7 conserva las estrategias y gates existentes; los registros históricos mantienen sus esquemas, nombres y representación.
- Entrega explícita completa o breve desde el resultado retenido, con destino estable en el checkout persistente elegido y sin copiar evidencias, logs o reproducciones.
- Registro y reporte portables, resumen autocontenido y contexto adicional opcional para supuestos, fuentes analizadas, estado observado de implementación y pendientes.
- Convenciones de solicitud --profile, --delivery y --output, equivalentes al lenguaje natural explícito; perfil y entrega se eligen por separado.
- README más breve con definiciones y ejemplos; instalación, actualización y uso detallado en documentación separada.
- Archivo interno e historial conservados; handoff histórico compatible sin generarlo en los nuevos flujos de entrega.

## 2.7.0 — 2026-10-09

- Añadir ID público de revisión y formatos estables de hallazgos/checks, conservando referencias y excepciones históricas explícitas en el seguimiento.
- Mostrar siempre Hallazgos y conteos confirmados P0–P3; conservar prioridad/icono/ID en H3 y título en H4. Presentar la evidencia de checks ya recopilada sin duplicar los detalles del defecto.
- Formalizar referencias y estados del re-review, incluyendo asuntos no reevaluados. Contrastar comentarios de otros formatos después del descubrimiento independiente y antes de la verificación agrupada.
- Conservar trazabilidad compacta del ciclo de revisión con participantes, procedencia, tiempos observados, relaciones y comprobaciones de integridad; sin registrar cada búsqueda ni recopilar mediciones por defecto.
- Generar opcionalmente handoff.md para transferir revisiones de MR/PR o locales desde el mismo resultado, separando correcciones confirmadas de decisiones pendientes y conservando el archivo fuera del proyecto por defecto.
- Evolucionar contratos finales y de archivo con compatibilidad de lectura de los registros históricos y sin modificar revisiones cerradas.

## 2.6.0 — 2026-10-07

- Explicit ABCDE assignment briefs name areas/aspects, affected flows/files/interfaces, questions/invariants and expected evidence/coverage. Related areas share owners; dedicated reviewers require distinct needs, not a quota per letter.
- Add automatic/explicit extended with at most five justified discovery reviewers and one grouped verification batch. Automatic selection requires deep mechanisms and four/five independent assignments that cannot be covered by a three-reviewer plan; preserve valid work when escalating.
- Final schema 5 adds extended while retaining presentation, attribution, coverage and verdict gates. Schemas 1–4 preserve their existing profiles; internal packets and archive schema 3 remain unchanged.
- Separate profile names from selection/use descriptions in the README table. Complete verified release dates and identify historical versions without a registered publication.

## 2.5.0 — 2026-10-07

- Automatic selection uses economy for demonstrated bounded scope/requirements/consumers without deep mechanisms or independent gates, deep for observable material mechanisms, otherwise balanced. Initial selection reuses common context without an extra agent or audit.
- Explicit profiles remain fixed; required project gates, isolation and evidence adequacy still apply. Automatic escalation records new facts and reuses unaffected work; no downgrade after discovery to evade verification.
- Deep assignments target named flows/invariants with two independent discovery reviewers and a justified optional third. Other flows keep ordinary coverage and substantive candidates still receive fresh verification.
- Follow-ups select on their current affected mechanisms/adjacent behavior rather than blindly inheriting the earlier profile. Existing profile enums, final schema 4 and user/public rendering remain unchanged.

## 2.4.1 — 2026-10-07

- Require archive helper use when executable, its exact returned run directory, and owned registered evidence sessions. Historical layouts are not current policy; native fallback must verify the same contract.
- Define the pre-run scope bootstrap and add `register` for temporary sessions before discovery/execution, without creating or deleting resources.
- Add read-only `validate` and `--require-retained` as the pre-cleanup gate; retention, closure and previous-run loading reject incorrect repository/scope/run paths.
- Accept inline observed cleanup/residuals in `close` so closure needs no temporary file after registered sessions have been removed; existing cleanup-file input remains supported.
- Archive schema 3 binds layout to stored repository identity, scope, creation time and run ID without relying on surviving source checkouts. Legacy schemas 1/2 retain compatible checks without migration.
- Make selected evidence copying explicit: context provenance does not automatically retain files, and required evidence survives cleanup as part of the review contract.

## 2.4.0 — 2026-10-06

- Builds/tests/installs/reproductions require owned project Git worktrees; blocked creation is disclosed and scratch/copy execution requires explicit user authorization. Static immutable reads remain workspace-optional.
- Compatible shared dependencies/caches/junctions remain permitted; conflicts trigger executor-owned dependencies/cache/outputs and an evidenced retry.
- Executor isolation, revision/snapshot, manifest and dependency decisions persist in existing context/closure. Optional --context-input verifies Git-root/common-repository/HEAD provenance without adding audit agents.
- Normal reviews omit measurement creation/probing. Archive schema 2 retains report/record/closure with opt-in measurement evidence; legacy schema 1 archives and integrity protections remain supported.
- Final schema 4 stores explicit review/re-review/complement kind and functional subject once. Both projections use H2 review title, H3 verdict/priority/ID, H4 finding title and separate scenario/impact. Schemas 1–3, attribution, user-only ABCDE and review gates remain supported.

## 2.3.0 — 2026-10-06

- Common per-user persistent review archive with configurable root, stable repository grouping, unique runs and retained report/final record/closure/measurement availability before temporary cleanup.
- Standard-library archive helper with scope binding, atomic writes, hashes, registered temporary resources and observed closure; no resource deletion, automatic retention or cross-run context cache.
- Schema 3 final records distinguish MR/PR responsibility from version-bound commit authors. Legacy schema 1/2 inputs remain supported; account mentions require verified mappings.
- Structural Markdown metadata/finding lists, translated user-facing values and separate user/public projections prevent soft-line-break headers from collapsing.
- Native missing usage stays unknown with an explicit reason; account-wide credits do not become per-review consumption. No automatic native usage interception or savings claim.

## 2.2.0 — 2026-10-05

- Independently versioned compact discovery candidates and verification decision deltas; optional merge preserves scenarios, amended claims and referenced check revisions without inventing final judgments.
- Role-specific instruction loading, progressive bounded source/log access and explicit expansion/stopping checkpoints. Required gates, material uncertainty and independent balanced verification remain in force.
- Standard-library per-phase usage accounting, partial totals and optional runner capture of adapter-normalized counters. Unknown usage stays unknown; cached/reasoning subsets are not double-counted.
- Final schema 1/2, user/public report format, ABCDE user-only coverage, responsible/description checks and workspace safeguards preserved. No persistent project cache or automatic model-setting changes.
- Installation update documentation for current skills CLI project/global scopes. No measured token/credit savings claimed.

## 2.1.1 — 2026-10-03

- Public GitHub distribution with installation documentation for the existing `skills` CLI, project/global scope and Codex/Claude Code targets.
- Versioned ZIP download with SHA-256 checksums for manual installation without cloning.
- README covering scope, profiles, ABCDE coverage, permissions, optional helpers, updates/removal and validation.
- Review behavior and schema unchanged from 2.1.0.

## 2.1.0 — Sin publicación registrada

- ABCDE coverage areas map to existing flow owners without adding per-area agents or tests.
- New user reports include a five-row coverage matrix with evidence/reasons and canonical finding references. Public comments omit the matrix and classifications while retaining material uncertainty.
- Schema version 2 validates complete area coverage, references and verdict consistency. Legacy version 1 records remain supported unchanged.
- No change-risk level or quality score added; existing profile/priority/verdict rules preserved.

## 2.0.0 — Sin publicación registrada

- Canonical discovery, verification and final records, with an optional standard-library validator and Spanish report renderer.
- Fixed user/public report order, verified responsible-person metadata, separate code/description findings and precise verdict rules.
- Common context/check owners and evidence layout; mode-specific references load only when relevant.
- Observable deep-profile triggers, bounded verification and explicit same-session fallback.
- Provisional same-cause grouping preserving scenarios, stable IDs/aliases and justified evidence reuse across incremental reviews.
- Unit/CLI/workspace integration checks, executable evaluation inputs and a protocol for measuring model accuracy/cost.
- Workspace and external runner safety implementations preserved.

## 1.1.1 — Sin publicación registrada

Preserved baseline before this revision. Includes economy/balanced/deep profiles, shared context discovery, reduced worker duplication and MR/PR description consistency checks.
