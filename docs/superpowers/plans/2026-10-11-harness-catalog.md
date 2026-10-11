# Harness Catalog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Identificar el harness con un catálogo estable y completar los IDs visibles en negrita sin alterar revisiones históricas.

**Architecture:** Resolver identidad una vez al preparar el cierre schema 6 mediante un módulo pequeño y un catálogo JSON local. Las operaciones posteriores preservan esa identidad; reporte y entrega breve comparten la convención de etiquetas.

**Tech Stack:** Python 3.10+, biblioteca estándar, unittest, Git y Markdown.

**Spec:** [Diseño aprobado](../specs/2026-10-11-harness-catalog-design.md).

## Global Constraints

- Final review 7 y trace 1 sin cambios; lectura de archive 1–6, sin migrar históricos.
- Sin red, telemetría, sondas de identidad ni dependencias nuevas.
- Preservar los tres cambios locales del usuario; trabajo dentro de `.worktrees/harness-catalog`.
- Implementación nativa autorizada en esta sesión; PR pendiente de aprobación humana antes de merge/release.

## Review Focus

- Nombre genérico Claude Code no prueba Desktop; solo un ID específico respaldado precisa interfaz.
- Configuración global compartida puede contaminar CLI: configuración por sesión, conflictos visibles.
- Un nuevo catálogo instalado no reinterpreta una identidad persistida ni invalida catálogos históricos.
- Schema 6 debe conservar recuperación processing y validación de tiempos/referencias de schema 5.
- Escape de contenido hostil no debe escapar las negritas generadas ni consumir listas tras anclas.

### Task 1: Catálogo y resolución

**Files:** Crear `references/archive/harness-catalog.json`, `scripts/review_harness.py`, `tests/test_review_harness.py`.

**Interfaces:** `resolve(harness, harness_id=None, source=None, environ=None) -> dict`; `validate_identity(manifest) -> None` valida forma sin cargar catálogo. Resolver devuelve las cuatro propiedades canónicas sin modificar el texto original.

- [x] Añadir pruebas de nombre, alias, familia/interfaz, argumento sobre entorno, unknown, conflictos y entrada malformada; ejecutar y observar RED.
- [x] Implementar catálogo versión 1 y resolución conforme al diseño; entradas duplicadas o alias ambiguos/malformados fallan antes de escritura.
- [x] Ejecutar `python -B -X utf8 -m unittest discover -s tests -p test_review_harness.py -v`; esperado PASS.
- [x] Commit `feat(harness): resolver identidad mediante catálogo canónico`.

### Task 2: Archivo schema 6 y CLI

**Files:** Modificar `scripts/review_artifacts.py`, `tests/test_review_harness.py`, `tests/test_review_trace.py`.

**Interfaces:** Añadir argumentos keyword-only `harness_id=None, harness_source=None` a `prepare`; CLI `--harness-id`, `--harness-source-file`; fuente JSON existente validada antes de escritura.

- [x] Añadir regresiones de CLI real, cierre completo, alteración protegida y schemas 1–5 sin campos canónicos; comprobar RED.
- [x] Integrar resolución única, cargar schema 5 explícitamente y heredar las cuatro ramas `== 5` para 5/6; conservar requisitos de trace y recuperación.
- [x] Ejecutar pruebas de harness y trace; comprobar PASS e identidad igual desde prepare hasta complete con entorno cambiado.
- [x] Commit `feat(archivo): persistir identidad de harness en cierre schema 6`.

### Task 3: Etiquetas de reporte y entrega

**Files:** Modificar `scripts/review_contract.py`, `scripts/review_delivery.py`, `tests/test_review_traceability_contract.py`, `tests/test_review_delivery.py`.

**Interfaces:** Mantener `render(record, audience)` y `_brief(record)`; cambiar solo Markdown generado.

- [x] Añadir expectativas de `**C001**`, `**F001**` y seguimiento con contenido escapado; actualizar la expectativa antigua de anclas conservando espacios; comprobar fallo de brief.
- [x] Incorporar los tres cambios del usuario y extenderlos al resumen breve sin escapar marcadores generados; conservar enlaces e IDs históricos.
- [x] Ejecutar módulos de contract, traceability y delivery; comprobar PASS.
- [x] Commit `fix(reportes): unificar etiquetas de IDs en negrita`.

### Task 4: Instrucciones y PR

**Files:** Modificar `SKILL.md`, `references/archive/artifacts.md`, `references/archive/lifecycle-trace.md`, `references/reporting/report-format.md`, `references/reporting/delivery.md`, `docs/usage.md`, `CHANGELOG.md`; crear registro de validación.

- [x] Documentar catálogo/configuración, fuente y fallback sin detección ni nuevas medidas; versión 2.10.0 pendiente, conservar enlaces a releases publicadas.
- [x] Ejecutar suite completa `python -B -X utf8 -m unittest discover -s tests -v`, CLI help, enlaces locales y `git diff --check`; corregir fallos del alcance.
- [x] Revisar diff completo y registrar resultados y límites en `docs/validation/2026-10-11-harness-catalog.md`.
- [x] Push y crear/adjuntar PR; main y los cambios originales del usuario siguen intactos.
- [ ] Esperar revisión humana; merge/release y limpieza del worktree quedan pendientes.

## Execution ledger

- Tasks 1/2: implementación conjunta 042fe1d; resolver/archivo RED→GREEN, trace 27/27; sin cambios de interfaces entre tareas.
- Task 3: 16e9a10 y corrección final de escape; brief RED→GREEN, traceability 19/19, suite integrada validada.
- Task 4: catálogo ampliado a petición del usuario; null-source independiente RED→GREEN. Suite final 249 pruebas, 248 pass/una omisión del host; ver registro de validación para resultados y alcance. Sin decisiones de alcance pendientes ni menores diferidos.
- PR es el gate humano restante; no merge/tag/release en esta ejecución.

- Handoff: [PR #14](https://github.com/omarfrancodev/comprehensive-code-review/pull/14) abierto y adjunto; rama publicada, worktree conservado para feedback.

## Seguimiento del PR: observaciones F001/F002

- [x] Verificar ambas observaciones contra el código y el diseño; alcance acotado autorizado por el usuario.
- [x] Reproducir normalización de argumento/configuración con regresión RED; implementar strip/casefold y verificar GREEN sin ocultar conflictos.
- [x] Corregir evaluación archive 1–6 y anunciar en CHANGELOG la compatibilidad requerida por lectores/visor.
- [x] Verificar suite integrada: 250 pruebas, 249 pass/una omisión del host; AST, enlaces y diff válidos.
- [x] Subir correcciones y actualizar descripción del PR con el estado actual de validación (748f6d7).
- [ ] Esperar aprobación para merge/release. Los nuevos puntos sobre formato público/delegación quedan solo como propuesta, fuera de estas correcciones.

## Seguimiento de re-review: F003

- [x] Confirmar el caso de CCR_HARNESS_ID solo con whitespace y reproducirlo con una regresión RED (tres variantes fallaron).
- [x] Normalizar el entorno vacío/en blanco como no configurado; conservar prioridad de IDs explícitos, conflictos y errores de argumento en blanco. Doce pruebas de harness GREEN.
- [x] Actualizar spec, artifacts y changelog con la diferencia entre entorno no configurado y argumento explícito inválido.
- [x] Verificar suite integrada: 251 pruebas, 250 pass/una omisión del host; AST, enlaces y diff válidos.
- [x] Publicar corrección F003 (1a77e76) y actualizar descripción del PR #14.

## Seguimiento de CCR: F004

- [x] Verificar el comentario y reproducir referencias JSON con surrogate alto/bajo aislado mediante CLI real (RED).
- [x] Rechazar texto/referencias no codificables en UTF-8 durante validación de identidad, antes de crear directorios; preservar referencias con acentos y emoji. Trece pruebas de harness GREEN.
- [x] Verificar suite integrada: 252 pruebas en 208.151 s, 251 pass/una omisión del host; sin fallos ni errores.
- [x] Documentar el contrato en artifacts, spec y changelog; registrar evidencia y preparar actualización del PR.
