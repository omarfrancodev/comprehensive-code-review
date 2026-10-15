# Plan de correcciones del segundo CCR del PR 19

> **Ejecución:** nativa en esta sesión; seguimiento mediante fallback en el chat autorizado por el usuario.

**Objetivo:** corregir los 16 hallazgos vigentes/nuevos de CR-34b04043a7044a519134 sin perder identidad, history ni ownership y actualizar el PR existente.

**Arquitectura:** conservar writers/locks/receipts actuales; compartir clasificación de recursos y preflight, sin migración ni gestor adicional. [Spec](../specs/2026-10-14-review-recovery-rereview-design.md).

**Stack:** Python 3.10+, stdlib, Git, unittest. Rama `feat/review-recovery-lifecycle`, worktree `.worktrees/review-recovery-lifecycle`, PR #19.

### Task 1: Reproducción y alcance

**Files:** Create `tests/test_review_recovery_followup.py`; Read scripts de artifacts/profiles/recovery/restart y los dos comentarios CCR.

- [x] Leer el comentario completo y contrastar paths/condiciones; mantener IDs fuente.
- [x] Añadir regresiones sin mocks que fabriquen éxito: colisión entre llamadas, legacy 1/2, malformed final, locks ajenos, missing claims, transitions y reinicios interrumpidos.
- [x] Observar RED y distinguir errores del fixture: temporal del sandbox sin permisos, argumento reason de pause y canal stderr JSON de CLI no son defectos de producto.

### Task 2: Checkpoints, perfiles y compatibilidad

**Files:** Modify `scripts/review_artifacts.py`, `scripts/review_profiles.py`; Test `tests/test_review_recovery_followup.py`, `tests/test_review_checkpoints.py`, `tests/test_review_profiles.py`.

- [x] Validar inventario casefold completo antes de persistir; reservar context.json solo si se suministra context-input.
- [x] Rechazar estructuras coverage/execution e IDs malformados antes de .get/set; rechazar dispatch sobre superseded y affected_assignments iniciadas sin guardar evento/transición.
- [x] Verificar ownership antes de lock-directory en restart/transfer/link.
- [x] Verificar regresiones nuevas y suites existentes; conservar RED/GREEN reales.

### Task 3: Reinicio recuperable y diagnóstico

**Files:** Modify `scripts/review_artifacts.py`, `scripts/review_restart.py`, `scripts/review_recovery.py`; Test `tests/test_review_recovery_followup.py`, `tests/test_review_recovery.py`, `tests/test_review_resource_claims.py`.

- [x] Clave local legacy sin fabricar run ID; completar la reserva exacta y mantenerla hasta el manifiesto.
- [x] Releer restart bajo lock en recover; preflight común antes del intent; añadir abandono autorizado/idempotente solo antes del sucesor preparado, preservando el partial y su receipt.
- [x] Compartir resource availability y alinear acciones; permitir cleanup de claims aún propios de sources superseded.
- [x] Verificar salida real del proceso con staging abandonado, replay y preservación de archivos ajenos; ejecutar suites afectadas.

### Task 4: Documentación, trazabilidad y PR

**Files:** Create `docs/examples/archive7-lifecycle.md`, `docs/validation/2026-10-14-review-recovery-rereview.md`; Modify referencias archive/execution/reporting, `docs/usage.md`, matriz anterior y `CHANGELOG.md`.

- [x] Documentar context/history/plan/select-profile, recovery/abandonment y cleanup; corregir full/brief y continuaciones.
- [x] Ejecutar bloques extraídos del Markdown desde prepare hasta close/validate, y el restart real documentado; corregir los IDs de la matriz frente al comentario original sin reescribir resultados históricos.
- [x] Suite completa, ayudas CLI nuevas, AST/enlaces/diff; revisión independiente de los cambios finales y solución de hallazgos si los hay.
- [ ] Commit/push y actualizar descripción/evidencia del PR #19; verificar SHA remoto y esperar revisión del usuario. No merge/release ni cleanup de este worktree.

**Verificación observada:** suite completa 489 tests, 1387.466 s, exit 0 y 2 skips de permisos Windows; focal 22 tests, 171.882 s, OK. AST 6 archivos, enlaces 12 documentos, matrices 33/16 IDs, 18 ayudas CLI y diff-check OK. Detalle en [registro de validación](../../validation/2026-10-14-review-recovery-rereview.md).
