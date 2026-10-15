# Correcciones del segundo CCR del PR 19

**Alcance autorizado:** solicitud del usuario de revisar y corregir los nuevos comentarios del PR #19, en la misma rama/worktree. Sin merge ni release.

**Fuente:** [CR-34b04043a7044a519134](https://github.com/omarfrancodev/comprehensive-code-review/pull/19#issuecomment-6180923742), sobre `4bf09c0`. Complementa la [especificación aprobada](2026-10-14-review-recovery-corrections-design.md). Se conservan archive 7, final 10, trace 1 y Python 3.10+ sin dependencias nuevas.

## Invariantes y aceptación

1. **F004:** comprobar nombres casefold contra inventarios anteriores y todo el plan antes de persistir una transacción. `Brief.json` seguido de `brief.json` se rechaza sin cambiar bytes; el checkpoint anterior sigue válido.
2. **F034:** los sources históricos sin run ID mantienen ID null y bytes intactos. Solo la clave local de la operación se deriva de ruta canónica y owner ID. Restart/recover siguen funcionando en schemas 1/2, sin migración.
3. **F036/F037:** la reserva permanece hasta el manifiesto del sucesor. Reintentar una salida real del proceso después de mkdir, reservation staging o ownership/cierre completa el destino exacto. Solo se aceptan ownership/reservation coincidentes y staging cuyos nombres exactos derivan del reservation ID del intent; archivos ajenos se conservan y bloquean. Recover relee la intención bajo el mismo lock del origen que restart, antes de preparar el destino.
4. **F042:** todo input determinista de prepare se comprueba antes de guardar intención/descriptor: scope, perfil, controlador, inputs evidence/, repositorio vigente, paths y harness. Un input inválido no deja operación activa. Una intención ya existente puede abandonarse explícitamente solo antes de un sucesor con manifiesto: se registra recibo idempotente, motivo/autoridad/controlador y evento; no se borra el intent ni la asignación parcial. Un sucesor preparado exige recover. El replay abandonado se rechaza; otra decisión crea una petición nueva.
5. **F017/F041/F043:** inspection y mutación comparten la clasificación de recursos. `missing_unknown` no anuncia continue/resume y no acredita cleanup. El reinicio con cambio de scope deja claims en el origen; el origen superseded puede limpiar únicamente sus claims owned con su propio run-dir. Un run completo permanece inmutable. Lookup/inspect presentan la operación restart pendiente, ID, intent path y sucesor; no anuncian continuar.
6. **F002/F008/F015/F038/F039:** verificar ownership antes de crear locks también en restart/transfer/link; validar objetos e IDs antes de operaciones dict/set; context.json vía evidence-input sigue permitido en archives 1–6 si no existe context-input; eventos no pueden empezar briefs superseded/no requeridos y select-profile no puede afectar trabajo iniciado.
7. **F013/F014/F040:** documentar contexto exacto, execution_plan, selection_source inicial, select-profile/autoridad/fases/límites; separar historial full de síntesis brief y retirar profile de record-event para archive 7. Ejemplos copiados usan una sola continuación POSIX. Los tests extraen los bloques Markdown y ejecutan sus argumentos reales; no basta buscar subcadenas ni construir otra secuencia.
8. **Trazabilidad de la corrección:** la matriz usa los IDs exactos de los comentarios originales; no se cambian resultados/fechas de ejecuciones anteriores. La nueva evidencia acredita solo sus escenarios, con skips y límites de plataforma declarados.

## Interfaces

- `_resource_availability(run, manifest, verify_owned=True)` compartido entre inspect/resume/recover, sin escritura.
- `_restart_source_identity` permite `run_id: null` solo en una identidad histórica; el nuevo sucesor conserva un ID real único.
- `abandon_restart(run_dir, intent_path, controller, authority, reason)` y CLI `abandon-restart --intent-input`: lectura exacta, lock de origen y receipt `<request>.abandoned.json`, sin búsqueda global ni borrado. La operación no cancela reviews preparados ni transferencias.
- Prepare reservado usa nombres de staging deterministas vinculados al reservation ID solo durante la preparación; la reserva se retira después del manifiesto/trace verificables.

## Fuera del alcance

Artifacts de reviews reales, main, viewer, configuración del harness, nuevas versiones/schemas y publicación de comentarios a terceros. No se cambia la política de perfiles ni se suavizan gates para aceptar un resultado incompleto.
