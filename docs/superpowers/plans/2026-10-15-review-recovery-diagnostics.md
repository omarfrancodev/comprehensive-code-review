# Plan de correcciones del quinto CCR del PR 19

> Ejecución nativa en esta sesión; seguimiento en el chat autorizado por el usuario.

**Goal:** corregir F051/F052/F053 y registrar con precisión la limitación F050 sin descartar ownership.

**Architecture:** consulta histórica opcional, preflight de traza sin escrituras y reutilización del recibo de cancelación para un sucesor vacío con recursos ausentes.

**Tech stack:** Python stdlib, unittest, Markdown y Git/GitHub.

**Spec:** [diseño](../specs/2026-10-15-review-recovery-diagnostics-design.md).

### Task 1: regresiones RED y límite de adopción

**Files:** tests/test_review_recovery_diagnostics.py.

1. Reproducir origen ausente/inválido y rechazo que aplica una traza pendiente.
2. Reproducir cancelación por sesión ausente, conservando el claim y la ausencia de recibos de limpieza.
3. Añadir la variante de dos sesiones con un sidecar propio y otro ajeno; comprobar rechazo y preservación, sin afirmar resolución del protocolo.

### Task 2: implementación mínima y GREEN

**Files:** scripts/review_artifacts.py.

1. Hacer opcional la consulta del origen, sin ocultar contradicciones entre identidades verificadas.
2. Extraer la planificación pura del replay de traza y usarla en el preflight de abandono; posponer toda escritura hasta aceptar la decisión.
3. Ampliar la elegibilidad a claims ausentes sin certificar cleanup; comprobar continuación con una selección nueva y cortes durante el recibo.
4. Ejecutar las regresiones y las pruebas existentes de reservas, recuperación, traza y ownership afectadas.

### Task 3: documentación, verificación y entrega

**Files:** referencias de recuperación/archivo, changelog, este spec/plan y docs/validation/2026-10-15-review-recovery-diagnostics.md.

1. Documentar F050 como límite vigente, alternativas y prohibición de limpiar recursos ajenos para sortearlo.
2. Registrar resultados reales y límites; verificar sintaxis, enlaces y diff.
3. Commit descriptivo, push al PR 19 y descripción actualizada. Conservar el worktree para revisión humana; sin merge ni release.

## Resultado de ejecución

Tasks 1 y 2 completadas. Se reprodujeron F051/F052/F053 antes de cambiar código; las primeras nueve regresiones pasaron en 74.925 s. Se añadió y verificó aparte el caso de traza inicial del sucesor pendiente, 9.630 s. F050 conserva la exclusión de rollback, con prueba y alternativas documentadas; no se declara resuelto.

La selección de compatibilidad pasó con 85 pruebas en 515.516 s, sin omisiones. Junto al test focal adicional son 86 pruebas distintas; no se repitió la suite completa ni las dos matrices extensas de la ronda anterior. La revisión independiente estática no señaló otro hallazgo concreto. Sintaxis, enlaces, referencias a pruebas, ayuda CLI y diff pasaron. Resultados y límites: [registro de validación](../../validation/2026-10-15-review-recovery-diagnostics.md).

La entrega actualiza el PR 19 y conserva su worktree para revisión humana. 2.12.0 permanece sin publicar; no incluye merge, tag ni release.
