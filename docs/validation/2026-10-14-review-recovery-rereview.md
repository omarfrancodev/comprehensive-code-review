# Validación del segundo CCR del PR 19 — 2026-10-14

Fuente: [CR-34b04043a7044a519134](https://github.com/omarfrancodev/comprehensive-code-review/pull/19#issuecomment-6180923742), HEAD revisado `4bf09c0`. Las filas conservan los IDs exactos del CCR; no son IDs nuevos ni renumeración por tarea.

| ID | Corrección | Regresión nueva en test_review_recovery_followup.py |
|---|---|---|
| F004 | Preflight casefold contra el checkpoint previo y plan completo | `test_checkpoint_case_collision_across_calls_is_read_only_rejection` |
| F013 | Context/history/plan y comandos reales extraídos del Markdown | `test_extracted_documented_archive7_commands_execute_end_to_end` |
| F017 | Clasificador compartido, ausencia sin recibo solo permite restart | `test_missing_session_diagnostics_match_recover_and_resume` |
| F034 | Intent legacy por ruta/owner; origen e IDs preservados | `test_schema1_and_schema2_restart_and_recover_without_synthetic_id` |
| F036 | Reserva durable hasta el manifiesto y staging exacto recuperable | `test_reserved_prepare_survives_baseexception_at_ownership_boundaries`, `test_reserved_prepare_recovers_actual_process_exit_with_staging_left` |
| F037 | Recover relee/prepara bajo lock del origen | `test_recover_pending_restart_takes_source_lock_before_prepare` |
| F038 | No reservar context.json cuando falta context-input | `test_legacy_context_as_selected_evidence_without_context_flag` |
| F039 | Gates tempranos para dispatch superseded y transición de trabajo iniciado | `test_started_assignment_cannot_be_affected_by_selection`, `test_superseded_assignment_cannot_start` |
| F041 | Cleanup fuente superseded únicamente sobre sus claims owned | `test_superseded_source_can_cleanup_its_remaining_claim` |
| F042 | Preflight antes del intent; abandono autorizado/idempotente y acotado | `test_invalid_restart_sources_leave_no_durable_intent`, `test_changed_repository_identity_rejected_before_restart_intent`, `test_adoption_cannot_contain_archive_root_before_restart_intent`, `test_foreign_repository_adoption_rejected_before_successor_or_intent`, `test_abandon_unprepared_restart_is_authorized_durable_and_idempotent`, `test_abandon_cannot_orphan_prepared_successor` |
| F002 | Verificar ownership antes de locks también en restart/transfer/link | `test_foreign_restart_transfer_and_link_create_no_locks` |
| F008 | Validar objetos coverage/execution antes de .get | `test_nested_malformed_final_has_structured_cli_error` |
| F014 | Limitar la promesa de historial completo a full | Docs revisadas; regresión existente `test_full_contains_lineage_brief_keeps_summary_and_source_link` |
| F015 | Comprobar tipo del ID extended antes de set membership | `test_extended_unhashable_assignment_id_returns_errors` |
| F040 | Continuaciones POSIX únicas en el restart documentado | `test_extracted_recovery_restart_example_executes` |
| F043 | Inspect/lookup muestran restart pendiente y no continue | `test_pending_restart_is_visible_in_inspect_and_lookup` |

## Evidencia y límites

La tanda inicial de 16 regresiones terminó OK en 108.987 s. Las dos pruebas adicionales de ejemplos y las de salida real del proceso se verifican en la suite final. La ejecución literal de los bloques se hace con parsing POSIX de tokens/continuaciones y subprocess sin shell; verifica los argumentos reales en Windows, sin afirmar que se haya ejecutado un shell POSIX.

Se observaron fallos RED de producto antes de corregirlos. También hubo errores de preparación de nuevas pruebas (TEMP del sandbox sin permisos, uso de stdout en vez de stderr para errores JSON, reason omitido en pause y contexto sintético con description/source incompatibles); se corrigieron los fixtures, sin relajar contratos del producto.

La revisión independiente del diff detectó tres variantes adicionales: referencias activas e inactivas mezcladas, campos ausentes de los archives 1/2 auténticos y preflight incompleto de paths/repositorio al adoptar. Se reprodujeron los dos primeros y la variante de path que contiene el archive root en RED; se corrigieron y se amplió la cobertura al repositorio distinto. La segunda pasada independiente no encontró otros defectos concretos en esas correcciones ni en reserva/staging/abandonment. No ejecutó pruebas ni creó artifacts.

AST de 6 archivos Python, enlaces relativos de 12 documentos, matrices con 33/16 IDs únicos y nombres de pruebas existentes, 18 ayudas CLI y git diff --check pasaron.

La suite completa final terminó con **489 tests en 1387.466 s, exit 0, OK (skipped=2)**. Las omisiones fueron por permisos de symlink (WinError 1314) y junction (acceso denegado) en Windows. Incluye las 22 regresiones nuevas y las variantes finales de referencias mixtas started/completed, repository_identity ausente en legacy y preflight de adopción. La tanda focal anterior de 22 tests dio OK en 171.882 s; el resultado completo corresponde al código final.

No se ejecutaron las rutas de locks ni un shell POSIX. La prueba de hard-exit sí termina un proceso real con os._exit, deja el staging en disco y verifica recuperación del destino reservado. Los artifacts reales de reviews no se usaron como fixtures ni fueron modificados. La suite inicial general se interrumpió al incorporar las variantes detectadas por la revisión independiente; no se presenta esa ejecución parcial como validación completa.

**Confirmación independiente final:** se revisó el commit exacto `8445ed63c852dde405804e86891c9261ce61c4fc` contra `4bf09c02c12f35f512ba4b424e4f2e7f61f80ea4`, sin hallazgos accionables en el alcance asignado. Fue revisión estática del código y sus afirmaciones documentales; los resultados de la suite son los observados por el coordinador.
