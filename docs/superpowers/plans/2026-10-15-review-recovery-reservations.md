# Plan: reservas del cuarto CCR del PR 19

> **Ejecución:** nativa, con seguimiento en el chat autorizado por el usuario.

**Goal:** resolver F046–F050 conservando la recuperación existente y sin integración/release.

**Architecture:** reutilizar descriptor/intent/recibo verificados; separar igualdad de replay y frescura; orientar la recuperación al origen; conservar un sucesor de adopción imposible como historial terminal mediante un recibo opcional archive-7.

**Tech stack:** Python stdlib, unittest, Markdown, Git/GitHub.

**Spec:** [diseño](../specs/2026-10-15-review-recovery-reservations-design.md).

### Task 1: reproducir y corregir F046/F047/F048/F049

**Files:** scripts/review_artifacts.py, scripts/review_recovery.py, tests/test_review_recovery_reservations.py.

1. Añadir pruebas de intent ausente, diagnósticos del sucesor, replay con identidades desconocidas y mensajes del origen sustituido; observar RED.
2. Aplicar correcciones mínimas sin rebajar hashes, ownership ni equivalencia del request.
3. Verificar GREEN y rechazos sin escrituras para requests diferentes y mutadores estrictos.

### Task 2: salida durable de F050

**Files:** mismos scripts y módulo de pruebas.

1. Reproducir el claim ajeno después de preparar el sucesor; confirmar que ni retry ni abandon ofrecen salida directa.
2. Validar el recibo opcional y la elegibilidad del sucesor bajo ambos locks, incluyendo sidecars, traza y archivos presentes.
3. Guardar primero la decisión terminal en el sucesor; compartir finalización idempotente con abandon/recover del origen.
4. Bloquear mutadores del historial abandonado y alinear lookup/inspect/recover. Preservar claims/workspaces ajenos y el abandono histórico previo a prepare.
5. Inyectar cortes en la cancelación, verificar convergencia y rechazo de trabajo/claim propio; comprobar que un replay antiguo no retira una solicitud nueva.

### Task 3: verificación y entrega

**Files:** documentación de recuperación/archivo, changelog, spec/plan y registro de validación.

1. Ejecutar regresiones focales, suite general y controles de sintaxis, enlaces y diff.
2. Obtener revisión independiente acotada, corregir sus hallazgos reproducibles y registrar resultados/límites.
3. Commit descriptivo, push al PR 19 y descripción actualizada; comprobar SHA remoto. Esperar revisión humana, sin merge/release.

## Resultado de ejecución

Tasks 1 y 2 completadas: F046–F050 cuentan con regresiones RED/GREEN, contratos documentados y una salida terminal para la adopción ajena bloqueada que preserva los recursos de la otra revisión. La revisión independiente señaló la interacción de cancelación antigua/restart nuevo; se reprodujo y corrigió. También se añadió el diagnóstico de una transferencia saliente cuyo origen fue antes un sucesor.

La verificación de Task 3 terminó con 508 pruebas en 1524.680 s, exit 0 y dos omisiones por permisos de Windows; incluye las doce nuevas y las 27 combinaciones de interrupción de la cancelación. Las dos matrices extensas de la ronda anterior no se repitieron. Sintaxis, enlaces, referencias a pruebas, ayuda CLI y diff pasaron. El alcance y sus límites constan en [el registro de validación](../../validation/2026-10-15-review-recovery-reservations.md).

La entrega actualiza la rama del PR 19 para revisión humana y conserva el worktree. No autoriza merge, tag ni release; 2.12.0 permanece sin publicar.
