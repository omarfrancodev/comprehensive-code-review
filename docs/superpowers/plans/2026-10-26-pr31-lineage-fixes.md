# Alcance ordinario acreditado y OID delimitados — Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans and test-driven-development. Preserve historical archives and existing schemas.

**Goal:** Corregir F001 residual y F006 del [re-review](https://github.com/omarfrancodev/comprehensive-code-review/pull/31#issuecomment-6409107394), base `eea23b0`, y actualizar el PR 31.

**Spec:** El comentario indicado y el [diseño de equivalencia](../specs/2026-10-25-review-equivalence-and-coverage-design.md).

**Architecture:** No inferir alcance ordinario de cinco filas cubiertas en un seguimiento. Para admitir un rereview, recorrer solo su linaje nativo explícito, verificar identidad/estado/integridad y encontrar una revisión ordinaria completa que siga siendo equivalente y aplicable al alcance actual. Reutilizar la comparación normal de diff/contexto/materiales para ese antecedente. Revalidar las fuentes de la prueba antes de ofrecer elección. Delimitar los OID del diff con --.

**Tech Stack:** Python/stdlib, Git y unittest.

## Global Constraints

- Conservar schemas y sidecars actuales, algoritmo, límites, protección de lazy fetch y correcciones F002–F005.
- No buscar una revisión anterior conveniente fuera de la cadena explícita. El resultado elegido sigue siendo el latest verificado.
- previous_run y previous_reviews deben concordar con el ID del antecedente nativo real; identidad declarada sola no demuestra cobertura.
- El antecedente debe estar completo y en el mismo repositorio/alcance lógico; sus propios cambios, materiales y contexto completos deben seguir siendo aplicables. Una revisión pendiente o un flujo Y cambiado impiden heredar cobertura.
- Linaje ausente, cíclico, corrupto, demasiado profundo o con aplicabilidad desconocida: nueva revisión conservadora. Máximo 32 enlaces y revalidación de los manifiestos de prueba.
- Sin formato nuevo que adivine alcance histórico. Un rereview sin prueba suficiente sigue consultable, pero requiere revisión nueva para una solicitud ordinaria. No se certifica semántica de programas ni verdad de declaraciones humanas.

## Review Focus

- Dos archivos vinculados reales: antecedente con Y pendiente y seguimiento X-only con cinco áreas covered.
- Control positivo: antecedente ordinario completo y contexto X/Y todavía aplicable, incluido HEAD distinto o rebase equivalente.
- Cambios en Y fuera del inventario del seguimiento deben invalidar la prueba heredada.
- Identidad de linaje discordante, corrupción, ciclos/límite y mutación durante la decisión no admiten reutilización.
- Rutas locales llamadas como cualquiera de los dos OID no deben cambiar el descriptor.

## Task 1: Reproducir y corregir

**Files:** scripts/ccr/archive/reuse.py, scripts/ccr/workflow/reuse.py, scripts/ccr/execution/change_scope.py y tests de captura/flujo/archivo existentes.

- [ ] Añadir escenarios independientes con archivos nativos realmente vinculados y ruta untracked llamada como OID; observar RED.
- [ ] Conservar controles de revisión ordinaria, material gaps y consultas históricas; cambiar el antiguo positivo de rereview sin antecedente para que aporte prueba nativa real.
- [ ] Compartir la comparación de un resultado retenido, verificar la cadena nativa de cobertura ordinaria y revalidar sus fuentes; añadir -- al diff por blobs.
- [ ] Ejecutar regresiones focalizadas, incluyendo herencia válida y contexto Y cambiado; commit de implementación.

## Task 2: Validación y publicación

- [ ] Revisión final independiente del ajuste, con una sola pasada de corrección si hay hallazgos importantes.
- [ ] Suite completa con inventario disjunto de todos los módulos; conservar omisiones de capacidad y resultados reproducibles.
- [ ] Actualizar documentación de alcance heredado y evidencia de validación; commit y push normal.
- [ ] Verificar HEAD, cuerpo y base del PR 31; conservar worktree y consulta histórica, sin merge ni respuestas públicas no solicitadas.
