# Validación del cuarto CCR del PR 19 — 2026-10-15

Fuente: [CR-b981159ddf25415487ea](https://github.com/omarfrancodev/comprehensive-code-review/pull/19#issuecomment-6201338987), HEAD revisado `4fa3474`. Se conservan sus IDs originales.

| ID | Corrección | Pruebas nuevas en test_review_recovery_reservations.py |
|---|---|---|
| F046 | Reconstruir únicamente el intent ausente indicado por el descriptor activo verificado | `test_abandon_reconstructs_missing_intent_from_exact_active_descriptor` |
| F047 | Orientar el sucesor al origen exacto y distinguir transfer actual de ancestro histórico | `test_successor_recovery_points_to_exact_restart_source`, `test_outgoing_transfer_error_does_not_route_to_an_old_restart_ancestor` |
| F048 | Replay por igualdad normalizada sin transformar freshness unknown en applicable | `test_exact_restart_recovery_with_unknown_identities_preserves_freshness`, `test_changed_restart_inputs_do_not_replay_an_unknown_intent` |
| F049 | Mensajes de rechazo del checkpoint superseded indican el sucesor registrado | `test_superseded_pending_checkpoint_errors_name_registered_successor` |
| F050 | Abandono explícito del sucesor de adopción vacío con claim ajeno; historial terminal y recibo recuperable | `test_foreign_claim_allows_explicit_empty_successor_abandonment`, `test_sidecar_owned_by_successor_without_manifest_row_cannot_be_abandoned`, `test_started_or_nonempty_successor_cannot_be_abandoned`, `test_interrupted_prepared_cancellation_replays_original_receipt`, `test_old_abandonment_replay_does_not_retire_a_new_active_restart`, `test_foreign_owner_pending_work_does_not_block_safe_cancellation` |

## RED/GREEN y variantes

La tanda RED inicial de cinco pruebas reprodujo el intent ausente, el desvío de recover del sucesor, el bloqueo de replay unknown y los mensajes del checkpoint. El caso de adopción ajena falló posteriormente con el rechazo previo de sucesor preparado. Las primeras siete pruebas corregidas terminaron **OK en 82.892 s**.

El módulo se amplió a doce pruebas: siete variantes de schemas 1–7 sin identidades capturadas; requests diferentes sin mutación; rechazo de nueve mutadores/gates del origen superseded; preservación del workspace/claim ajeno; doce mutadores bloqueados sobre historial abandonado; rechazo de un sidecar propio aún sin fila, trabajo observado y evidencia presente; y repetición de una cancelación antigua frente a un restart nuevo pendiente.

La revisión independiente detectó que un descriptor nuevo del origen invalidaba la lectura del sucesor abandonado anterior. Se reprodujo en RED y el GREEN focal pasó en **17.629 s**. La inspección de ownership separada de evidencia ajena se comprobó con un checkpoint ajeno pendiente: verify_claim completo sigue rechazándolo, la cancelación propia no lo modifica y el test pasó en **11.262 s**. La variante de mensaje de una transferencia saliente cuyo origen fue antes un sucesor también se reprodujo en RED; su GREEN pasó en **16.537 s**.

Hubo correcciones de fixtures: record-event y checkpoint requieren rutas de entrada, no objetos; el rechazo de un archivo propio puede crear su lock de coordinación, por lo que la prueba de ausencia de mutación compara origen, sucesor, owner ajeno y sesión, sin confundir el lock con contenido del review. El caso de trabajo/evidencia corregido pasó en **19.180 s**. No se relajaron contratos del producto para acomodar esos fixtures.

## Interrupciones de cancelación

Se probaron **27 combinaciones**: nueve puntos antes/después de fases durables × abandon-retry, recover del origen o ruta desde el sucesor. Incluyen commit del manifiesto terminal del sucesor, su traza, recibo del origen, traza del origen y retiro del descriptor. Después del primer commit durable, recuperar con requirements actuales diferentes completa solo la cancelación ya autorizada. Se comprueba igualdad del recibo, un solo evento por extremo, ausencia de adopción repetida y workspace/claim ajeno idénticos.

Estas 27 combinaciones pasaron en la tanda focal de diez pruebas; esa tanda tuvo un fallo separado del fixture de comparación de locks, corregido y repetido después. También pasaron en la suite general definitiva; no se presenta la tanda focal con fallo como suite aprobada. No es una enumeración de todos los reemplazos de todas las ramas, ni simula un segundo corte dentro del replay.

## Suite y controles finales

La tanda general terminó con **508 pruebas en 1524.680 s, exit 0, OK (skipped=2)**: 506 aprobadas y dos omitidas por permisos de symlink/junction en Windows. Se descubren 510 pruebas; esta ejecución selecciona 508 e incluye las doce nuevas y la matriz de cancelación. Las dos matrices extensas de transferencia/registro bootstrap de la tanda anterior se excluyen de esta repetición: sus resultados previos están en [el registro anterior](2026-10-15-review-restart-resource-replay.md), no se cuentan como pruebas nuevas ejecutadas aquí.

Pasaron el parseo AST de los cuatro archivos Python modificados/nuevos, los enlaces Markdown relativos de los seis documentos de esta ronda, la existencia de los tests referenciados, la ayuda CLI de abandon-restart y git diff --check. No hubo cambios de código posteriores al inicio de esta tanda definitiva.

Los bloques generales iniciales se interrumpieron al corregir el fixture de locks y la variante del mensaje de transferencia saliente; no se cuentan como tandas completas.

## Revisión independiente y límites

La consulta independiente fue solo lectura, sin tests, cambios ni artifacts CCR. Verificó el orden del recibo, guards, ownership y rutas de recuperación; su hallazgo de R1 abandonado/R2 pendiente fue corregido y la última lectura no señaló otra falla concreta. El contraste de transferencia saliente se añadió además por el coordinador al comprobar el mensaje. Ninguna lectura afirma ausencia universal de defectos.

Las pruebas usan archivos y repositorios desechables en Windows; no se alteran reviews reales del usuario. Los cortes son KeyboardInterrupt alrededor de os.replace y conservan la lógica real de ownership/hashes/Git. No se certifican todos los fallos de proceso, todos los intercalados concurrentes ni rutas POSIX. La lectura identity-only ajena no certifica ni repara sus evidencias y no autoriza su limpieza. El visor independiente no se verificó.
