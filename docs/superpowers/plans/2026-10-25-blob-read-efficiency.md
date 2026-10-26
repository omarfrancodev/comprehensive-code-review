# Lecturas eficientes de blobs — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox syntax for tracking.

**Goal:** Reducir lecturas redundantes de blobs grandes conservando exactamente la evidencia y la compatibilidad histórica; publicar la rama y crear el PR autorizado.

**Architecture:** Prefijo de clasificación acotado, hash completo bajo demanda y cachés efímeras por objeto en los colectores existentes.

**Tech Stack:** Python/stdlib, Git y unittest.

**Spec:** [Diseño](../specs/2026-10-25-blob-read-efficiency-design.md).

## Global Constraints

- Preservar algoritmo, schemas, hashes completos, streams cerrados y recaptura de integridad.
- Caché limitada a cada captura; no nuevas dependencias ni instalación o release.
- Conservar el worktree y publicar su rama hacia main mediante PR, sin merge.

## Review Focus

- Mezclas texto/binario y symlink: no confundir digest ausente con hash completo.
- Objetos repetidos en rutas y lados distintos: reutilizar bytes leídos sin omitir filas del descriptor.
- NUL en posición 7999 frente a 8000: conservar el clasificador anterior.
- Fallos y cierres anticipados: liberar siempre el proceso Git.
- Contexto y archivos anteriores: hashes completos y gates intactos.

## Task 1: Reducir lecturas y demostrar preservación

**Files:** `scripts/ccr/execution/change_scope.py`, `tests/test_review_change_scope.py`, `CHANGELOG.md`, `scripts/README.md`.

**Interfaces:** Mantener firmas públicas de collect_effective_changes y collect_context_files; permitir internamente solicitar digest completo sin cambiar evidencia serializada.

- [x] Escribir tests con Git real y medición de bytes del adaptador real para texto grande duplicado, binario duplicado, transición texto/binario, límite NUL y contexto compartido.
- [x] Ejecutarlos y observar RED por lecturas completas/repetidas; los tests de caracterización pueden pasar inicialmente.
- [x] Implementar prefijo acotado, cierre explícito y cachés por invocación. Mantener hashes completos de ambos lados binarios y contexto.
- [x] Ejecutar pruebas focalizadas de captura, contratos, contexto, decisiones, flujo y archivos reales; esperar cero fallos.
- [x] Documentar el coste resuelto y sus límites; commit de rendimiento.

## Task 2: Validar y publicar

**Files:** Registro nuevo en `docs/validation/`; spec/plan e informe anterior con enlace al cierre de la mejora.

**Interfaces:** Consume el colector y evidencia de tarea 1; conserva el inventario completo de unittest y los contratos publicados.

- [ ] Ejecutar los 80 módulos completos en procesos disjuntos y registrar casos, omisiones y errores observados.
- [ ] Revisión final independiente, clasificar hallazgos y corregir importantes con RED→GREEN si existen; comprobar diff y limpieza del worktree.
- [ ] Guardar evidencia reproducible y decisiones; commit de validación.
- [ ] Push normal de la rama, crear PR con la plantilla del repositorio hacia main, verificar título/cuerpo/refs y adjuntarlo al chat.
