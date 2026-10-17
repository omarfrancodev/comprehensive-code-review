# Recovery Exit Guidance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans for native execution in this session. Steps use checkbox syntax; workflow progress uses the user-authorized chat fallback.

**Goal:** indicar salidas realizables para recursos ausentes y corregir el remedio destructivo descrito en el sexto CCR.

**Architecture:** compartir un diagnóstico puro basado en el preflight existente de cancelación entre inspect, lookup y recover. Conservar los protocolos de ownership/transferencia y sus límites; solo la cancelación explícita puede escribir su recibo.

**Tech Stack:** Python stdlib, unittest, Markdown, Git/GitHub.

**Spec:** [diseño](../specs/2026-10-16-review-recovery-exit-guidance-design.md).

## Global Constraints

- Sin rollback de claims ni limpieza ajena; F050 y la fase durable de F052 siguen como reservas.
- No certificar recuperación ni cancelación en un diagnóstico; mantener autoridad explícita y gates bajo locks.
- Mantener 2.12.0 sin publicar y conservar el worktree del PR 19.

## Review Focus

- No convertir corrupción local en una sugerencia de continuación.
- No anunciar cancelación si hay trabajo, sidecars propios o una transferencia durable.
- Conservar el replay de cancelación ya autorizado antes de evaluar recursos ausentes.
- Mantener igualdad de inputs antes de ofrecer un plan para el request exacto.
- No inferir que cleanup ajeno preserva la sesión que elimina.

### Task 1: pruebas y diagnóstico realizable

**Files:** scripts/review_artifacts.py, scripts/review_recovery.py, tests/test_review_recovery_exit_guidance.py, tests/test_review_recovery_diagnostics.py.

- [x] Escribir pruebas de rutas ausentes antes/después del intent de transferencia y observar RED.
- [x] Añadir el preflight puro compartido y conectar inspect/lookup/recover conservando el protocolo de cancelación; factorizar su validación de identidad/reserva antes de clasificar falta de soporte.
- [x] Verificar GREEN, salida CLI, igualdad de inputs y rechazo de corrupción.
- [x] Ejercitar prepare independiente con recursos nuevos preservando los runs y sesiones anteriores.

### Task 2: documentación y entrega

**Files:** references/archive/recovery.md, CHANGELOG.md, este spec/plan y docs/validation/2026-10-16-review-recovery-exit-guidance.md.

- [x] Corregir el texto de cleanup y la etiqueta interna; documentar fases y límites vigentes.
- [x] Ejecutar módulos afectados y controles estáticos; registrar evidencia y alcance.
- [ ] Crear commit descriptivo, subirlo al PR 19 y actualizar su descripción sin declarar resueltos los residuos.
- [ ] Comprobar SHA remoto, estado del PR y árbol limpio; esperar revisión humana sin merge/release.

## Resultado de implementación y verificación

Se completaron las correcciones de instrucciones y diagnóstico con seis pruebas focales, 72.736 s, y una selección de 113 regresiones, 669.074 s, ambas OK sin omisiones. No se suman dos veces las focales. La reserva corrupta combinada con transferencia/work se reprodujo y corrigió tras la revisión independiente; también se comprobaron alias de Windows y replay missing_unclaimed. Sintaxis, enlaces, referencias de tests y diff pasaron.

Resultados y límites: [registro de validación](../../validation/2026-10-16-review-recovery-exit-guidance.md). F050 y la fase durable de F052 siguen como reservas. Las dos acciones de entrega se ejecutan y registran en el chat después de este commit, mediante el fallback autorizado; este documento no las marca realizadas por adelantado. 2.12.0 permanece sin publicar.
