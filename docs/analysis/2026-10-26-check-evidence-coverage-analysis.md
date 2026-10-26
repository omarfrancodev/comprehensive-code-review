# Modelo y presentación de checks, evidencias y cobertura en CCR 3.2.0

## Base y método

Inspección local de `main` en `559fc5c` y su integración sin conflictos mediante `bc7d5b6` en el worktree `explicit-dimensions-spec`. Se preservaron `42a052b` y `6fc1821`, que solo contenían la propuesta documental anterior. El metadata de SKILL y el changelog identifican 3.2.0; no se infiere una release futura.

Esta inspección es análisis para el [spec actualizado](../superpowers/specs/2026-10-20-explicit-dimension-coverage-design.md) y su [plan](../superpowers/plans/2026-10-20-explicit-dimension-coverage.md), no un nuevo review archivado ni implementación. No se abrieron archivos reales de revisiones.

## Flujo observado

| Etapa | Fuente actual | Observación |
|---|---|---|
| Request de check | `scripts/ccr/execution/checks.py:_read_request` | Shape exacto: check_id, argv, command, cwd, executor_workspace, revision, executor; no purpose |
| Captura | `scripts/ccr/execution/checks.py:capture_check` | Ejecuta argv sin shell en workspace propio; devuelve recibo 1, no un check final |
| Recibo | `scripts/ccr/contracts/receipts.py:validate_receipt` | Vincula ID, command/argv, cwd, revisión, executor, exit y streams; no puede acreditar propósito |
| Modelo final | `scripts/ccr/contracts/findings.py:validate_checks` | Valida campos de checks por schema; 10 no admite un campo adicional de propósito |
| Evidencia de hallazgo | `scripts/ccr/contracts/findings.py:validate_findings` | Ya existe `{kind, details, check_id}`; ejecutada exige check conocido/aprobado o fallido, estática conserva check_id null |
| Merge de workers | `scripts/ccr/contracts/packets.py:merge` | Construye ledger neutral con schema 2; un check 11 completo requiere adaptación expresa y no una copia ciega |
| Informe/comentario | `scripts/ccr/reporting/render.py:render` | Concatena evidence con `'; '.join`; añade ID entre corchetes. Si details coincide exactamente con check.evidence usa «Comprobación», evitando ya una parte de duplicación |
| Validación mostrada | Mismo renderer | Check por ID/estado/versión, evidencia y referencia anidadas; command solo privado; no explica objetivo |
| Cobertura | Mismo renderer | `coverage.flows` es lista validada, pero se concatena con punto y coma y solo se muestra para audience=user |
| Proyección pública | `scripts/ccr/reporting/projections.py:public_checks` | Contexto ligado al digest del registro, filas exactas con evidence/reuse_reason/rerun_reason/reference; conserva solo URL pública y no admite purpose |
| Comentario canónico | `scripts/ccr/reporting/comment.py` | Draft 1 con hashes de fuente/cuerpo y contextos; verify exige un render fresco exacto, por lo que cambios de layout afectan drafts pendientes |
| Entrega | `scripts/ccr/reporting/delivery.py` | `_Projection` clasifica strings por campo; purpose/dimensions necesitan política explícita. Brief tiene su propio renderer y no basta con cambiar el informe principal |

`runner` controla un adaptador de agente externo; no es la ruta que captura checks locales. Agregar purpose únicamente a runner dejaría sin resolver request, recibo y ledger.

## Diferencias que invalidaron el plan anterior

- CCR 3.0 retiró los 27 entrypoints/imports `review_*.py`; hoy se usa `python <skill>/scripts <área>` y paquetes `ccr`. El spec/plan se actualizan en sitio, conservando enlaces y fechas de creación de sus archivos.
- 2.14–3.2 añadieron preflight, recibos, referencias materiales, publicación canónica, dispatch-identity y admisión por equivalencia. Deben seguir operando al ampliar final 10 a 11.
- Existen pruebas de arquitectura/imports e inventarios CLI. Los módulos nuevos deben figurar en `scripts/README.md`; contratos puros no pueden depender de ejecución, archivo o IO.
- Mantener final 11 como contrato propuesto no colisiona con la base: 3.2.0 todavía produce final 10. Archive 8/layout 2, trace 1 y packet 1 siguen vigentes.

## Decisiones propuestas y límites

1. Final 11 combina propósito obligatorio con las 27 dimensiones pendientes de implementación; no se agregan campos opcionales que vuelvan silenciosa la omisión.
2. Purpose se declara antes del proceso y queda en recibo 2 y JSON final; propósito, resultado e impacto son campos con responsabilidades distintas.
3. Evidencias siguen usando sus check_id reales y permanecen como lista en JSON. La presentación agrupa solo por origen demostrado y conserva detalles distintos; no se deduplica mediante similitud.
4. Cobertura pública necesita descripciones de producto ligadas al registro fuente. No se publican automáticamente los flows privados, que pueden contener IDs de dimensión, rutas o detalles internos.
5. Los comentarios continúan saliendo de un draft canónico verificado. Un layout nuevo no conserva por magia la verificabilidad de un draft antiguo: el spec define el diagnóstico y regeneración explícitos sin repetir review.
6. No se cambia el criterio de admisión/reuso de 3.2.0 por la ausencia histórica de purpose o dimensiones. Compatibilidad de datos no implica fabricar nuevos campos de cobertura.

## Evidencia de preparación

Los comandos ejecutados y sus límites se registran en [la validación de replanteamiento](../validation/2026-10-26-explicit-dimension-coverage-replanning.md). Los bloques de tests del plan describen implementación futura, no pruebas ya ejecutadas de schema 11.
