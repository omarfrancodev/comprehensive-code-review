# Recovery Route Consistency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans for native execution. Workflow progress uses the user-authorized chat fallback.

**Goal:** resolver F055–F057 con clasificación compartida de salidas y causas, sin ampliar el protocolo de rollback.

**Architecture:** ampliar el diagnóstico puro de recursos; propagar su plan desde el origen a las tres superficies del sucesor; separar integridad legacy de viabilidad recovery y preservar fuentes no verificables.

**Tech Stack:** Python stdlib, unittest, Markdown, Git/GitHub.

**Spec:** [diseño](../specs/2026-10-16-review-recovery-route-consistency-design.md).

## Global Constraints

- No liberar ni modificar claims ajenos, ni ejecutar decisiones durante diagnóstico.
- Conservar identidad/reserva, inputs exactos y cancelación durable existente.
- Mantener F050/F052 como reservas; 2.12.0 sigue sin publicar.

## Review Focus

- Claims ajenos con trabajo pendiente se verifican por identidad, sin adoptar su evidencia.
- Origen y sucesor deben indicar la misma salida sin saltos innecesarios.
- Corrupción local o contradicción de identidad no se confunden con imposibilidad operativa.
- Fuente no disponible de una transferencia entrante no permite continuar esa transacción.
- Un claim del origen aún presente impide la cancelación y debe nombrarse.

### Task 1: reproducir las rutas inconsistentes

**Files:** tests/test_review_recovery_route_consistency.py, tests/test_review_recovery_diagnostics.py.

- [x] Extraer el fixture de adopción parcial sin reducir sus aserciones existentes.
- [x] Añadir pruebas de las seis clases de entrada del spec y los tres controles de integridad de la revisión estática y observar RED.

### Task 2: diagnóstico compartido y GREEN

**Files:** scripts/review_artifacts.py, scripts/review_recovery.py.

- [x] Generalizar el filtro de recursos a claims ajenos verificados y añadir causas/recovery explícitos.
- [x] Propagar las acciones al sucesor y preservar transferencias con fuente no verificable.
- [x] Añadir al error del reintento exacto la referencia al origen; verificar GREEN y no mutación.

### Task 3: documentación, regresión y entrega

**Files:** references/archive/recovery.md, CHANGELOG.md, docs/validation/2026-10-16-review-recovery-route-consistency.md y este spec/plan.

- [x] Documentar recovery, límites de recoverable y condiciones de cancelación.
- [x] Ejecutar módulos afectados, revisión independiente y controles estáticos; registrar resultados y límites.
- [ ] Commit descriptivo y push al PR 19; actualizar descripción y verificar SHA remoto/árbol limpio en el chat.
- [ ] Conservar worktree y PR abierto para revisión humana, sin merge/release.

## Resultado de ejecución

Implementación y verificación completadas: 122 pruebas afectadas en 1223.067 s, sin omisiones. La [validación](../../validation/2026-10-16-review-recovery-route-consistency.md) registra RED/GREEN, revisión estática y límites. Los dos pasos de entrega se cierran en el chat después del commit/push y de comprobar GitHub; no se marcan anticipadamente dentro del propio commit.
