# Validación de correcciones de recuperación — 2026-10-14

Esta ejecución verifica las correcciones del review del PR #19. El spec registra 33 hallazgos originales; la matriz relaciona cada ID con la regla corregida y una regresión representativa. F012 documenta la política aprobada de downgrade y no relaja los gates de verificación.

## Matriz de cobertura

| ID | Corrección cubierta | Regresión representativa |
|---|---|---|
| F001 | Lock usa ruta canónica para alias 8.3 y procesos concurrentes | `test_alias_83_conflicts_between_processes` |
| F002 | Rechazo de run ajeno sin crear locks ni directorios | `test_foreign_run_rejection_creates_no_locks` |
| F003 | Fallo de write/fsync/replace limpia solo su staging y conserva error | `test_fsync_and_replace_failure_remove_owned_staging` |
| F004 | Recuperar staging requiere intención exacta y bytes íntegros | `test_crash_staging_recovery_requires_exact_intent` |
| F005 | Ausencia sin recibo se mantiene como `missing_unknown` | `test_missing_without_receipt_is_reported_as_unknown` |
| F006 | Register preserva compatibilidad y campos de workspace histórico | `test_legacy6_workspace_register_keeps_historical_fields` |
| F007 | Reintentar reinicio reutiliza el sucesor reservado | `test_restart_link_failure_retry_reuses_reserved_successor` |
| F008 | Retención de resultado no objeto devuelve error estructurado | `test_nonobject_final_retention_is_structured_error` |
| F009 | Inputs cambiantes y crecientes respetan límites antes y durante lectura | `test_growing_input_cannot_exceed_read_budget` |
| F010 | Asignaciones iniciadas no desaparecen del registro ni eluden retención | `test_started_assignment_identity_cannot_change` |
| F011 | Downgrade conserva trabajo iniciado y obligaciones del perfil adquirido | `test_downgrade_preserves_started_obligations` |
| F012 | Documentar downgrade automático justificado; no permite evadir verificación | `test_automatic_upgrade_and_supported_downgrade` |
| F013 | Ejemplos de Archive 7 se ejecutan por el CLI documentado | `test_documented_archive7_commands_end_to_end` |
| F014 | Full conserva linaje y Brief muestra síntesis con vínculo al origen | `test_full_contains_lineage_brief_keeps_summary_and_source_link` |
| F015 | Resultado final conserva identidad y cumplimiento de asignaciones | `test_schema10_sources_bind_profile_ids_and_work_order` |
| F017 | Replay de recibos requiere la misma identidad exacta | `test_released_receipt_replay_requires_exact_identity` |
| F018 | Transferencia registra origen/destino y vuelve a enlazar ownership | `test_transfer_records_both_runs_and_rebinds_claim` |
| F019 | Register del receptor es idempotente tras transferencia | `test_register_after_incoming_transfer_is_idempotent` |
| F020 | Transferencia parcial se rechaza sin mutar claims | `test_partial_transfer_is_refused_without_mutation` |
| F021 | Transferencias encadenadas preservan linaje entrante y saliente | `test_second_outgoing_transfer_preserves_incoming_history` |
| F022 | Lookup, inspect y resume usan la misma forma de inputs | `test_same_inputs_shape_for_lookup_inspect_and_resume` |
| F023 | Outputs internos no se convierten en fuentes externas de vigencia | `test_internal_outputs_are_not_external_sources` |
| F024 | Inputs omitidos o incompletos permanecen `unknown` | `test_empty_sources_without_completeness_are_unknown` |
| F025 | Cambio de controlador en recover exige autoridad y deja evento durable | `test_recover_records_controller_takeover` |
| F026 | Archives históricos sin run ID se inspeccionan sin inventar identidad | `test_schema1_and_schema2_inspect_without_run_id` |
| F027 | Reinicio registra el harness vigente y conserva la identidad de origen | `test_restart_uses_current_harness_identity` |
| F028 | Reinicio pendiente bloquea mutaciones distintas sobre el origen | `test_pending_restart_blocks_other_source_mutations` |
| F029 | Interrupción de transferencia permite recuperación de la operación exacta | `test_transfer_crash_boundaries_are_recoverable` |
| F031 | Cleanup no compite con una transferencia activa | `test_cleanup_conflicts_with_transfer` |
| F032 | Checkpoint con HEAD cambiado puede iniciar sucesor sin reclamar vigencia | `test_pending_checkpoint_with_changed_head_can_restart` |
| F033 | Cleanup registra recibo durable antes de cerrar el review | `test_cleanup_records_receipt_before_return` |
| F034 | Review histórico completo conserva sus bytes al reiniciar | `test_complete_and_legacy_source_bytes_remain_unchanged_on_restart` |
| F035 | Límite del llamador no trunca inventario retenido para validar integridad | `test_caller_limit_does_not_limit_retained_inventory` |

## Resultados observados

La ejecución final en Windows completó **467 tests en 1018.988 s; exit 0**, con **2 skips**: symlink (`WinError 1314`, privilegio no disponible) y junction (acceso denegado). La primera ejecución completa expuso ocho errores: cuatro pruebas atómicas no llegaban al escenario porque el fixture no delegaba `final_record`, y cuatro cierres de archivos legacy 1–2 consultaban un `run_id` inexistente. Se corrigió el fixture y el helper dejó de buscar intents de restart cuando el archivo no tiene identidad estable; las suites focalizadas y la segunda ejecución completa pasaron.

Verificaciones adicionales: AST de cuatro archivos Python; las 14 ayudas CLI de prepare/register/select-profile/checkpoint/lookup/inspect/pause/block/resume/recover/restart/retain/close/cleanup; enlaces Markdown relativos de 13 documentos; flujo CLI integrado de Archive 7; y `git diff --check` pasaron. La matriz contiene 33 IDs únicos. Las pruebas focalizadas posteriores a la corrección pasaron: atomic recovery 8/8 y archive layout 17/17. Los tests de entrega 29/29, secuencias integradas 3/3 y referencia 1/1 también pasaron antes de la suite final. Las validaciones históricas citadas en el plan permanecen como registros de sus ejecuciones originales.
