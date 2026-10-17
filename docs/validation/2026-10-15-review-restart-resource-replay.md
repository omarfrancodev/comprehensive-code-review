# Validación del tercer CCR del PR 19 — 2026-10-15

Fuente: [CR-137e48103e1d4402ae23](https://github.com/omarfrancodev/comprehensive-code-review/pull/19#issuecomment-6182635449), HEAD revisado `0d10fed`.

| ID fuente | Corrección | Evidencia |
|---|---|---|
| F044 | Reconocer el sucesor exacto antes del preflight fresh; recuperar las trazas vinculadas al intent y respetar el lock del sucesor | `test_sidecar_replaced_restart_retries_and_recovers`, `test_claimed_workspace_all_transfer_replacements`, `test_unclaimed_workspace_all_adoption_replacements`, `test_reserved_successor_trace_replay_respects_its_mutation_lock` |
| F045 | Checkpoint superseded preservado como provisional; acciones dirigidas al sucesor y gates finales estrictos | `test_superseded_pending_checkpoint_is_historical_not_retryable`, `test_superseded_checkpoint_with_staged_bytes_is_not_committed`, `test_superseded_checkpoint_still_rejects_modified_bytes`, `test_superseded_checkpoint_keeps_remaining_claim_cleanup_usable`, `test_pending_checkpoint_workspace_transfer_recovers_without_promoting_inputs` |
| F014 | Brief documenta identidad/cumplimiento y enlaces a reviews anteriores; no promete perfil/historial/vínculo inexistente | Documentación alineada con `_brief`; `test_full_contains_lineage_brief_keeps_summary_and_previous_review_link`, `test_schema10_projection_preserves_profile_lineage_and_fulfillment` |

## Regresiones observadas

Antes del arreglo, las cuatro variantes de sidecar reemplazado fallaron al reintentar o recuperar la transferencia/adopción. El caso de checkpoint superseded sin bytes falló en validate básico. La revisión independiente detectó y se reprodujeron dos interacciones: el replay modificaba bytes del sucesor pese a un lock ocupado y el checkpoint+claim bloqueaba restart/cleanup. Una segunda lectura señaló la variante same-scope+transfer: se reprodujo el rechazo después de persistir el intent y se corrigieron los gates del camino completo.

Los GREEN focales observados fueron: sidecar/retry/recover (cuatro variantes iniciales), 56.967 s; checkpoint sin bytes, con bytes pendientes y modificados (tres pruebas), 17.059 s; conflicto de lock, 18.359 s; cleanup remanente con interrupción tras retirar la sesión y recuperación del recibo, 15.730 s; transferencia con checkpoint pendiente y recuperación posterior al reemplazo de sidecar, 18.117 s. La repetición final de sidecar amplió a **seis variantes**: transferencia, registro bootstrap y adopción legacy sin sidecar, cada una por retry y recover; **78.891 s, exit 0, OK**. Hubo además una corrección de fixture: el corte de cleanup debía parchear el módulo que importa review_workspace, no la instancia cargada por importlib en los tests. No se relajaron gates para compensar el fixture.

## Ejecución final

La tanda general descubre 498 tests y ejecuta 496. Las dos matrices se ejecutan aparte para cubrir todas las pruebas descubiertas sin duplicar sus combinaciones:

- Registro de sesión bootstrap sin claim del review: **32 casos**, ocho reemplazos reales dentro de register × antes/después × retry/recover. **1 test, 413.738 s, exit 0, OK**. La variante legacy sin sidecar se verifica en el corte posterior a su reemplazo, por ambas vías, en las seis variantes focales; no se presenta como otra matriz exhaustiva.
- Transferencia: **132 casos**, 33 reemplazos dentro de transfer_resources × antes/después × retry/recover. **1 test, 1627.482 s, exit 0, OK**.
- Suite general: **496 tests, 1528.677 s, exit 0, OK (skipped=2)**. Las omisiones son symlink (WinError 1314) y junction (acceso denegado) en Windows. Con las dos matrices se cubrieron los **498 tests descubiertos**, con nueve tests nuevos en test_review_restart_resources.py.

Cada caso de matriz restaura solo el archivo desechable y el sidecar de su fixture; los worktrees/evidencias del workspace permanecen iguales. Tras el replay comprueba un único sucesor reservado, integridad del origen y sucesor, claim válido y replay posterior sin cambios. No se mockean Git, ownership, hashes ni escrituras. Los 33/8 reemplazos se observaron además en una ejecución sin fallos de los helpers.

Se repitieron las 17 pruebas de estructura/layout después de mover mkdir(scoped) detrás del preflight: **57.243 s, exit 0, OK**. El caso de preflight de claims antes de mutación dio **24.452 s, exit 0, OK**. Esta repetición focal corresponde al último ajuste de orden de creación; no altera la identidad ni la lógica de replay.

Pasaron AST de los cinco archivos Python modificados/nuevos, enlaces relativos de los once documentos del cambio, referencias a nombres de pruebas existentes y git diff --check. No se modificó código de producto tras esas ejecuciones; las actualizaciones posteriores solo registran los resultados documentales. La ampliación final del fixture de sidecar a legacy sin claim se verificó mediante su repetición focal de seis variantes.

## Límites y revisión independiente

Las matrices inyectan KeyboardInterrupt antes/después de los 33/8 reemplazos observados en el recorrido inicial sin fallos de los helpers. No inyectan otro corte durante la recuperación del primer corte, ni certifican cada punto posible de os._exit o todos los intercalados concurrentes. La suite conserva las regresiones existentes con salida real del proceso, pero esas prueban sus límites declarados. Se validó en Windows; no se ejecutó un shell POSIX ni las rutas de lock POSIX. El test nuevo de lock usa dos threads con exclusión real del sucesor. Las pruebas usan repositorios/archivos desechables, no reviews reales del usuario.

La revisión independiente fue estática y acotada, sin ejecutar tests ni producir artifacts. Después de corregir sus dos interacciones y la variante same-scope+transfer, no encontró otra secuencia concreta rota en los últimos cambios leídos. Esto no implica cobertura universal. Las tandas generales/matrices anteriores se interrumpieron al incorporar esas correcciones y no se presentan como ejecuciones completas.
