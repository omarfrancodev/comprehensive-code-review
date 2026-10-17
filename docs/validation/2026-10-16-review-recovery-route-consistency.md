# Validación del séptimo CCR del PR 19 — 2026-10-16

Fuente: [CR-bcb75bf8adc74fa5a797](https://github.com/omarfrancodev/comprehensive-code-review/pull/19#issuecomment-6218944810), HEAD revisado `009459f`.

## Resultado por observación

| ID | Corrección | Límite |
|---|---|---|
| F055 | Clasificar recursos ausentes o reclamados por terceros verificados; compartir una salida de cancelación explícita o review independiente entre origen y sucesor | El diagnóstico no ejecuta decisiones, no recupera evidencia ajena y no revierte adopciones/transferencias |
| F056 | Añadir recovery con viabilidad conocida y propagar directamente el plan del origen; fuente de transferencia no verificable conserva la transacción | recoverable mantiene su sentido legacy de transacción pendiente; no promete que recover la termine |
| F057 | Separar source_claims_present de transfer_in_progress y successor_claims_or_work; repetir la condición en la documentación | Un claim presente/releasing del origen sigue bloqueando la cancelación |
| F052 | El error del reintento exacto remite a inspect/recover del origen | Mejora de descubrimiento; la reserva del protocolo permanece |

F050 y la fase durable de F052 siguen siendo reservas explícitas. Una review independiente con recursos nuevos no cancela el restart anterior ni autoriza limpiar recursos de terceros.

## Regresiones

En test_review_recovery_route_consistency.py:

- `test_foreign_claim_shares_exact_abandonment_on_source_and_successor`: las tres superficies comparten la cancelación exacta; diagnóstico sin escrituras y cancelación explícita sin modificar owner/sesión ajenos.
- `test_partial_foreign_claim_shares_independent_route_and_exact_retry_hint`: adopción parcial válida ofrece review independiente en ambos runs; reintento informa cómo descubrir la salida y conserva los propietarios.
- `test_missing_durable_transfer_propagates_feasibility_without_a_hop`: transferencia durable con sesión ausente comparte viabilidad y acción directamente. Diagnósticos sin escrituras; el mutador restart puede actualizar updated_at y el digest, sin avanzar claims/estado ni inventar limpieza.
- `test_present_source_claim_is_named_separately`: dos claims del origen y solo uno ausente identifican explícitamente el claim fuente aún presente.
- `test_unavailable_transfer_source_offers_preservation_instead_of_failing_recover`: fuente renombrada deja preservación y alternativa independiente, nunca ready; sucesor/sesión sin escrituras.
- `test_unverifiable_foreign_owner_never_becomes_an_abandonment_offer`: owner ajeno alterado conserva error/preserve.
- `test_corrupt_local_sidecar_is_not_an_independent_review_plan`: identidad propia alterada en adopción parcial conserva error/preserve en origen y sucesor.
- `test_corrupt_local_reservation_is_not_a_source_unavailable_plan`: la falta de fuente no omite la reserva local.
- `test_corrupt_source_trace_does_not_invalidate_intact_successor`: la fuente corrupta mantiene error local y no invalida un sucesor íntegro; su transferencia sigue pendiente sin escrituras.

El fixture parcial se extrae del test existente sin reducir sus garantías de propietarios y prepare independiente. Los planes siguen sujetos a revalidación bajo locks por los mutadores.

## RED/GREEN y revisión

Las regresiones iniciales reprodujeron rutas faltantes y ausencia de metadatos de viabilidad. Se corrigió primero un fixture de dos claims para conservar su contexto de registro original. La primera tanda definitiva de seis pruebas pasó en 116.686 s, exit 0. La prueba de reintento distingue las escrituras legítimas de updated_at/digest del mutador de la ausencia de escrituras del diagnóstico; no afirma que todo error de restart sea de solo lectura.

La revisión estática independiente encontró dos controles omitidos: sidecar propio contradictorio y reserva local alterada con fuente ausente. Ambos reprodujeron RED: dos fallos en 21.692 s. Se añadieron controles de identidad antes de clasificar imposibilidad operativa. La relectura detectó la ventana legítima de adopción con sidecar aún sin fila: se reutiliza su preflight puro, limitado al par actual. Los bytes exactos de una transferencia pendiente conservan su replay; la historia de otros pares no impide la adopción. La tanda intermedia de ocho pruebas detectó la fila legítimamente ausente (un error, 225.129 s), corregida con ese preflight. Una última comprobación estática señaló que el nuevo plan podía propagar la corrupción de traza del origen como invalidez del sucesor: se reprodujo en RED (un error, 37.604 s) y se movió la verificación propia del origen al lookup histórico opcional, conservando fuera del catch la identidad y reserva del sucesor. Las selecciones preliminares se interrumpieron para incorporar ese control y exigir un sucesor preparado antes del preflight de adopción; no se cuentan como aprobadas. El revisor no ejecutó pruebas ni escribió archivos.

## Verificación final

La selección definitiva terminó **OK: 122 pruebas en 1223.067 s, exit 0, sin omisiones**, sobre 535 pruebas descubiertas. Abarca recuperación, seguimiento, diagnóstico, salidas, reservas, coherencia de rutas y replay de recursos. Incluye las nueve regresiones nuevas y las combinaciones existentes de interrupción de cancelación; no se suman otra vez las tandas focales. Las dos matrices extensas sin cambios y los módulos ajenos no se ejecutaron en esta selección.

Pasaron AST de los cuatro archivos Python modificados/nuevos, enlaces relativos de los cinco documentos de esta ronda, existencia de los tests referenciados y git diff --check. No hubo cambios de código del producto después de iniciar la selección definitiva. Se conserva el worktree y el PR abierto para revisión; no se publica versión ni se ejecuta merge.

## Límites

Pruebas con repositorios y archivos desechables en Windows; no se alteran reviews reales. No se verifican POSIX ni el visor independiente. La selección afectada excluye las dos matrices extensas sin cambios de transferencia/registro bootstrap y los módulos ajenos; no equivale a la suite completa. Los cortes inyectados no enumeran todos los intercalados. La [ronda anterior](2026-10-16-review-recovery-exit-guidance.md) conserva sus propios resultados y no se suma a los actuales. 2.12.0 permanece sin publicar.
