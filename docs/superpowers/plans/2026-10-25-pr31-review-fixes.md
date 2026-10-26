# Correcciones del review del PR 31 — Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans with test-driven-development. Preserve existing schemas and historical archives.

**Goal:** Corregir los cinco escenarios del [comentario de revisión](https://github.com/omarfrancodev/comprehensive-code-review/pull/31#issuecomment-6408128291), con pruebas independientes, y actualizar el PR autorizado.

**Spec:** El comentario F001–F005 y el [diseño de equivalencia](../specs/2026-10-25-review-equivalence-and-coverage-design.md). Base de este ajuste: `993c3c0`.

**Architecture:** Centralizar elegibilidad de cobertura en la política pura; endurecer el entorno Git compartido; obtener patches textuales por objetos exactos; aplicar el conteo al conjunto indexado y el límite de bytes a toda la evidencia adquirida.

**Tech Stack:** Python/stdlib, Git 2.45.0.windows.1 y unittest; partial clones reales con remoto file:// local.

## Global Constraints

- Conservar schemas, `ccr-effective-diff-v1`, hashes completos y lecturas acotadas; no mutar archivos históricos ni adquirir objetos implícitamente.
- Una revisión ordinaria exige cobertura completa demostrada y ausencia de incertidumbre material. Findings confirmados y limitaciones no materiales por sí solos no impiden reutilización.
- Un rereview acotado sin cobertura ordinaria completa demostrada requiere nueva revisión; identidad de lineage por sí sola no certifica cobertura heredada.
- Mantener 64 fuentes seleccionadas contando el índice y 64 MiB agregados; review-context sigue siendo evidencia derivada.
- El usuario autorizó corregir todo el comentario, incluidos sus tres P3, y actualizar el PR existente; sin merge ni publicación de release.

## Review Focus

- Un blocker confirmado no debe ocultar incertidumbre material por tener verdict not_approvable.
- Las dos APIs Git y la lectura de contexto deben respetar la ausencia de blobs promisor y no alterar objetos/packs.
- Las altas/bajas, archivos vacíos, CR y falta de newline deben producir los mismos hunks normalizados que antes.
- El contexto derivado cuenta en bytes, pero no como una fuente inicial adicional.
- La consulta histórica conserva resultados insuficientes; solo su reutilización ordinaria queda limitada.

## Task 1: Reproducir y corregir F001/F004

**Files:** workflow/reuse.py, archive/reuse.py, shared/git.py y tests de flujo/captura existentes bajo scripts/ccr y tests.

- [x] Tests reales independientes: área parcial material, área no evaluada material, limitación material, rereview acotado, controles de cobertura completa/reservas no materiales.
- [x] Partial clones reales: captura bytes, consulta textual y contexto; comprobar objetos/packs antes/después y captura incompleta sin adquisición implícita.
- [x] Observar RED, centralizar elegibilidad y desactivar lazy fetch en las dos APIs Git; obtener GREEN y conservar consultas históricas.

## Task 2: Corregir F002/F003/F005

**Files:** shared/git.py, execution/change_scope.py, archive/reuse.py y tests existentes.

- [x] RED independiente de GIT_DIFF_OPTS, archivo→directorio, directorio→archivo, y 64 fuentes indexadas más contexto derivado.
- [x] Aislar entorno, generar patch por objetos exactos y validar conteo indexado frente a bytes agregados; GREEN, incluyendo controles de empty/newline y límites.
- [x] Ejecutar regresiones focalizadas y registrar resultados separados por escenario; commit de correcciones.

## Task 3: Validar y actualizar PR

- [ ] Revisión final independiente del ajuste; resolver hallazgos importantes si aparecen con regresión RED→GREEN.
- [ ] Ejecutar todo el inventario unittest en tres lotes disjuntos, conservar skips de capacidad e informe reproducible.
- [ ] Actualizar changelog/referencias y evidencia; commit, push normal, verificar HEAD y descripción del PR #31. No publicar respuestas al comentario sin autorización explícita.
