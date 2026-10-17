# Plan: replay de recursos y diagnóstico del historial sustituido

> **Ejecución:** nativa en esta sesión; seguimiento en el chat autorizado por el usuario.

**Goal:** corregir F044/F045/F014 del tercer CCR del PR 19 sin cambiar la versión pendiente ni integrar el PR.

**Architecture:** reconocer primero el sucesor exacto de un restart durable; delegar la finalización a los helpers de recursos existentes. Tratar el checkpoint pendiente de un origen superseded como provisional histórico, sin promoverlo ni reconstruir entradas ausentes.

**Tech stack:** Python stdlib, unittest, Markdown, Git/GitHub.

**Spec:** [diseño](../specs/2026-10-15-review-restart-resource-replay-design.md).

### Task 1: reproducir F044 y completar el replay

**Files:** `scripts/review_artifacts.py`, `scripts/review_resource_claims.py`, `tests/test_review_restart_resources.py`.

1. Agregar regresiones de corte al reemplazar el sidecar en transferencia y adopción; observar RED.
2. Ordenar la preparación reservada y recuperar la traza vinculada al intent sin rebajar identidad ni hashes.
3. Ejecutar la matriz de reemplazos antes/después, con retry y recover, y verificar un único sucesor válido.
4. Comprobar el conflicto de lock del sucesor con snapshot inmutable durante el conflicto y replay posterior.

### Task 2: corregir F045

**Files:** `scripts/review_artifacts.py`, `scripts/review_recovery.py`, mismo módulo de pruebas.

1. Interrumpir un checkpoint antes de staging, reiniciar y observar la recomendación imposible.
2. Alinear validate/inspect/lookup/recover con el estado superseded; conservar todos los bytes.
3. Verificar que gates finales y mutaciones no certifican el historial provisional; comprobar que las acciones apuntan al sucesor.
4. Reproducir y cubrir checkpoint+claim: limpieza remanente recuperable tras cambiar de scope y transferencia dentro del mismo scope bajo el intent exacto, conservando el checkpoint solo en el origen.

### Task 3: corregir F014 y comprobar compatibilidad

**Files:** `references/reporting/delivery.md`, `docs/usage.md`, documentación de recuperación, `tests/test_review_delivery.py`, registro de validación.

1. Precisar las garantías de brief y el alcance real de los ejemplos ejecutados.
2. Ejecutar regresiones focales y suite completa, controles de sintaxis/enlaces/diff y revisión independiente acotada.
3. Registrar resultados observados, hacer commits descriptivos y subir al PR 19; actualizar su descripción. Esperar revisión humana, sin merge/release.

## Resultado de la ejecución

Implementación y documentación de F044/F045/F014 completadas. Las interacciones adicionales de lock del sucesor y checkpoint+claim se reprodujeron antes de corregirse; la revisión independiente posterior no encontró otra secuencia concreta rota en el alcance leído.

Se cubrieron los 498 tests descubiertos en una tanda general de 496 (1528.677 s, exit 0, dos omisiones de permisos Windows) y dos matrices separadas: 132 casos de transferencia (1627.482 s) y 32 de registro bootstrap (413.738 s), ambas OK. Los cambios finales de orden de mkdir y la variante legacy sin sidecar se comprobaron además con regresiones focales. Sintaxis, enlaces, referencias a tests y diff-check pasaron.

El detalle, las reproducciones y sus límites están en el [registro de validación](../../validation/2026-10-15-review-restart-resource-replay.md). La versión 2.12.0 sigue pendiente de publicación y la integración del PR requiere la revisión humana posterior; se conserva este worktree.
