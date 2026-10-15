# Validación de correcciones de recuperación — 2026-10-14

Esta ejecución verifica las correcciones del review del PR #19. El spec registra 33 hallazgos originales; la matriz relaciona cada ID con la regla corregida y una regresión representativa. F012 documenta la política aprobada de downgrade y no relaja los gates de verificación.

## Matriz de cobertura (asociaciones corregidas tras el segundo CCR)

Los IDs corresponden al [CCR original](https://github.com/omarfrancodev/comprehensive-code-review/pull/19#issuecomment-6159108237). La tabla anterior asociaba varios IDs con causas distintas; esta tabla corrige esas referencias y apunta a cobertura actual. No altera los resultados históricos de abajo. La evidencia de las nuevas regresiones se registra [por separado](2026-10-14-review-recovery-rereview.md).

| ID del CCR | Regla/escenario | Regresión representativa |
|---|---|---|
| F001 | Lock canónico para alias 8.3 | `test_alias_83_conflicts_between_processes` |
| F002 | Ownership antes de locks en register/restart/transfer/link | `test_foreign_restart_transfer_and_link_create_no_locks` |
| F003 | Staging propio ante fallos write/fsync/replace | `test_fsync_and_replace_failure_remove_owned_staging` |
| F004 | Colisión casefold también entre checkpoints, sin mutación | `test_checkpoint_case_collision_across_calls_is_read_only_rejection` |
| F005 | Close reintentable e idempotente con recibos | `test_close_same_cleanup_observation_after_interruption_and_complete` |
| F006 | Register de sesiones en archives 1–6 | `test_legacy6_workspace_register_keeps_historical_fields` |
| F007 | Restart reusa un solo sucesor ante interrupción/concurrencia | `test_restart_link_failure_retry_reuses_reserved_successor` |
| F008 | Resultados raíz y coverage/execution malformados dan error estructurado | `test_nested_malformed_final_has_structured_cli_error` |
| F009 | Lectura acotada antes y durante carga de evidencia | `test_growing_input_cannot_exceed_read_budget` |
| F010 | No eliminar ni reetiquetar asignaciones iniciadas | `test_started_assignment_identity_cannot_change` |
| F011 | Selección explícita autorizada no reduce extended adquirido | `test_acquired_automatic_extended_minimum_survives_explicit_selection` |
| F012 | Downgrade automático solo con justificación pertinente | `test_automatic_upgrade_and_supported_downgrade` |
| F013 | Contexto y CLI exactos extraídos de ejemplos Markdown | `test_extracted_documented_archive7_commands_execute_end_to_end` |
| F014 | Corrección documental parcial en esta tanda; la promesa residual de perfil/historial en brief se corrige tras el tercer CCR | Prueba renombrada a `test_full_contains_lineage_brief_keeps_summary_and_previous_review_link`; verifica vínculo a una review anterior |
| F015 | Tipos no hashables devuelven errores, incluido extended | `test_extended_unhashable_assignment_id_returns_errors` |
| F017 | Claims ausentes no anuncian continuación ni liberación | `test_missing_session_diagnostics_match_recover_and_resume` |
| F018 | Transferencia encadenada conserva historial entrante/saliente | `test_second_outgoing_transfer_preserves_incoming_history` |
| F019 | Transferencia parcial rechazada sin mutar claims | `test_partial_transfer_is_refused_without_mutation` |
| F020 | Transferencia rechazada desde retaining/closing | `test_transfer_rejects_retaining_and_closing_runs` |
| F021 | Prepare/retain rechazan recursos reclamados por otro run | `test_prepare_and_retain_refuse_foreign_claim_before_mutation` |
| F022 | Outputs internos no cuentan como inputs externos de vigencia | `test_internal_outputs_are_not_external_sources` |
| F023 | Forma común de inputs para lookup/inspect/resume | `test_same_inputs_shape_for_lookup_inspect_and_resume` |
| F024 | Inputs vacíos/incompletos se mantienen unknown | `test_empty_sources_without_completeness_are_unknown` |
| F025 | Checkpoint pendiente con HEAD movido permite reinicio enlazado | `test_pending_checkpoint_with_changed_head_can_restart` |
| F026 | Rechazo de ownership/claim alterado sin adopción | `test_claim_reparse_or_foreign_owner_preserves_files` |
| F027 | Harness vigente en cada reinicio, sin heredar procedencia | `test_restart_uses_current_harness_identity` |
| F028 | Recover registra takeover autorizado de controlador | `test_recover_records_controller_takeover` |
| F029 | Register idempotente tras recibir transferencia | `test_register_after_incoming_transfer_is_idempotent` |
| F031 | Transferencia respeta previous_run y linaje | `test_transfer_rejects_conflicting_previous_run` |
| F032 | Adopción valida el objeto contexto antes del sucesor | `test_adopt_context_object_before_successor_creation` |
| F033 | Cleanup deja recibo durable antes del cierre | `test_cleanup_records_receipt_before_return` |
| F034 | Restart/recover en schemas 1/2 sin fabricar run ID | `test_schema1_and_schema2_restart_and_recover_without_synthetic_id` |
| F035 | Inventario retenido no se trunca con el límite del caller | `test_caller_limit_does_not_limit_retained_inventory` |

## Resultados observados

La ejecución final en Windows completó **467 tests en 1018.988 s; exit 0**, con **2 skips**: symlink (`WinError 1314`, privilegio no disponible) y junction (acceso denegado). La primera ejecución completa expuso ocho errores: cuatro pruebas atómicas no llegaban al escenario porque el fixture no delegaba `final_record`, y cuatro cierres de archivos legacy 1–2 consultaban un `run_id` inexistente. Se corrigió el fixture y el helper dejó de buscar intents de restart cuando el archivo no tiene identidad estable; las suites focalizadas y la segunda ejecución completa pasaron.

Verificaciones adicionales: AST de cuatro archivos Python; las 14 ayudas CLI de prepare/register/select-profile/checkpoint/lookup/inspect/pause/block/resume/recover/restart/retain/close/cleanup; enlaces Markdown relativos de 13 documentos; flujo CLI integrado de Archive 7 construido por el test (no extracción literal de los ejemplos); y `git diff --check` pasaron. La matriz contiene 33 IDs únicos. Las pruebas focalizadas posteriores a la corrección pasaron: atomic recovery 8/8 y archive layout 17/17. Los tests de entrega 29/29, secuencias integradas 3/3 y referencia 1/1 también pasaron antes de la suite final. Las validaciones históricas citadas en el plan permanecen como registros de sus ejecuciones originales.
