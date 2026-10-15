# Changelog

Las fechas corresponden a la publicación en GitHub en America/Mexico_City. «Sin publicación registrada» identifica estados históricos sin una release en GitHub; no atribuye una fecha de publicación a su commit.

## 2.12.0 — unreleased

- Recuperar el restart reservado tras cortes dentro de transferencias/adopciones de workspaces, respetando el lock del sucesor. Conservar checkpoints interrumpidos del origen sustituido como historial provisional, con acciones realizables y limpieza de claims independiente; precisar el contenido real de la entrega breve.
- Corregir colisiones de evidencias entre checkpoints, reinicios legacy sin ID y recuperación del sucesor reservado ante cortes reales del proceso; validar entradas antes del intent y permitir su abandono explícito antes de preparar el sucesor.
- Alinear diagnóstico/recuperación/cleanup de claims ausentes o de un origen superseded; rechazar temprano estructuras malformadas y trabajo sobre asignaciones sustituidas. Verificar ejemplos CLI extraídos de Markdown y corregir sus contratos y referencias de hallazgos.

- Registrar el ciclo de vida del perfil desde su selección inicial, transiciones posteriores y asignaciones afectadas; validar la selección inicial y las obligaciones del perfil efectivo antes de retener.
- Añadir lookup acotado, lectura de vigencia y decisiones explícitas para mostrar, continuar, recuperar o iniciar una revisión vinculada, sin selección automática ni exploración global del archivo.
- Publicar el contrato de archive schema 7 y final schema 10, preservar lecturas históricas, y alinear las proyecciones full/brief y publicación con el nuevo resultado.
- Hacer idempotentes las operaciones de reinicio interrumpidas, registrar traspasos de controlador y resolver la identidad de harness vigente para cada run sucesor.
- Registrar transferencias y recibos de limpieza de recursos; mantener `missing_unknown` cuando no hay evidencia de liberación y limitar de forma explícita las entradas retenidas y su staging.
- Documentar recuperación exacta y criterios de vigencia, selección/perfiles, trazabilidad, limpieza y entrega; añadir regresiones integradas de secuencias de extremo a extremo.

## 2.11.0 — 2026-10-12

- Proyectar entregas full/brief por tipo de campo, preservando IDs, perfiles, estados y relaciones frente a colisiones con comandos; rechazar identidades privadas, incluidas rutas UNC normalizadas con `/`, antes de escribir el destino.
- Final review schema 9 vincula checks locales con ejecutores y versiones/snapshots retenidos; distingue inspección estática, CI externo y reuso sin inventar worktrees.
- Retener con expectativa explícita del schema y exigir un gate completo de resultado, fuentes y limpieza antes de declarar cierre durable. El cierre revalida fuentes, también en reintentos idempotentes.
- Mantener lectura de final schemas 1–8 sin migración, archive 6 y packet/trace 1. El visor independiente requiere soporte para final schema 9; no se verifica aquí.

## 2.10.0 — 2026-10-12

- Proteger el contexto retenido automáticamente frente a evidencia ajena, manteniendo reintentos de archivos propios inventariados o planificados. La entrega breve declara el estado de ejecución schema 8 y las reservas públicas se deduplican contra detalle fuente y resumen proyectado.
- Final review schema 8 clasifica limitaciones de comportamiento, validación y ejecución: el informe privado conserva el detalle interno y la publicación comunica impacto relevante. Limitaciones históricas requieren clasificación efímera vinculada al JSON original para republicarse; lectura privada de schemas 1–7 permanece sin migración.
- Registrar plan, resultados y fallback observado en coverage.execution. La invocación incluye la delegación prevista por el perfil; pocos slots usan tandas frescas. No presentar pases del mismo contexto como cumplimiento de deep/extended ni exigir una frase adicional solicitando subagentes.
- Verificar fuentes ya retenidas contra contexto/traza antes de retener y limpiar. Mantener archive schema 6, packet/trace schema 1 y procedencia estructural en entregas completas/breves; sin otro auditor, sondeo o medida de créditos.
- Los consumidores del resultado, incluido el visor independiente, deben admitir final review schema 8; su compatibilidad no se verifica ni implementa aquí.

- Conservar el nombre original del harness y resolver una vez su ID mediante catálogo canónico versionado, con fuente, configuración explícita por sesión y diagnóstico de identidades desconocidas/contradictorias.
- Ampliar el catálogo inicial a 52 identidades en 17 familias, distinguiendo las interfaces conocidas y conservando soporte para entornos personalizados no catalogados.
- Archivo schema 6 conserva la identidad durante todo el ciclo y mantiene lectura de schemas 1–5 sin migración; trace 1 permanece independiente. El cambio posterior de política de ejecución usa final review 8, con lectura de 1–7. Sin sondas, telemetría ni mediciones adicionales.
- Los consumidores de cierre.json, incluido el visor independiente, deben aceptar archive schema 6 para leer los nuevos runs. La compatibilidad del visor no se presume ni se verifica en este repositorio; su actualización corresponde al proyecto independiente.
- Normalizar mayúsculas y espacios exteriores de IDs declarados por argumento o CCR_HARNESS_ID; conservar conflictos reales y diagnósticos de IDs desconocidos sin sustituirlos silenciosamente por un alias del nombre.
- Tratar CCR_HARNESS_ID vacío o compuesto solo por espacios como configuración ausente; mantener el rechazo de IDs explícitos en blanco.
- Rechazar texto/referencias de harness no codificables en UTF-8 antes de crear el archivo de revisión, conservando referencias Unicode válidas.
- Unificar etiquetas de IDs en negrita en reporte, comentario, seguimiento e incertidumbres y entregas completas/breves; preservar valores y anclas y escapar contenido aportado.

## 2.9.1 — 2026-10-09

- Incluir el círculo de cada prioridad en los conteos de Hallazgos del reporte, comentario público y entregas completas/breves, también para conteos cero.
- Unificar el renderizado de conteos confirmados y cubrir la regresión con pruebas de reportes y entregas; conservar contratos y archivos históricos sin migración.

## 2.9.0 — 2026-10-09

- Agrupar las 20 referencias en workflow, execution, contracts, archive, reporting y maintenance; actualizar enlaces y conservar lectura selectiva por fase/rol.
- Archivo schema 5 con processing desde el primer hito de trabajo observado, unido a la transacción de trazabilidad y su recuperación; schemas 1–4 conservan compatibilidad sin migración.
- Capturar occurred_at de hitos lógicos del helper; aprovechar opcionalmente tiempos del metadata ya existente del runner. Mantener recorded_at separado y tiempos externos desconocidos en null, sin sondeos ni mediciones adicionales.
- Conservar actor, executor y recorder separados, con identidades disponibles y vínculos opcionales explícitos. Rechazar destinos locales de eventos inexistentes al emitir schema 5, sin búsquedas de otras revisiones ni reescritura histórica.
- Documentar inicio, límites de observación, recuperación y organización de referencias; el contrato final 7, packets y trace 1 permanecen sin cambios. El visor continúa como proyecto independiente.

## 2.8.0 — 2026-10-09

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
