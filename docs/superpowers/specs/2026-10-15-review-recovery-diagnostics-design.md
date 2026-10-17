# Diagnóstico y cancelación conservadora del quinto CCR del PR 19

Fuente: [CR-23096898b877445ab11c](https://github.com/omarfrancodev/comprehensive-code-review/pull/19#issuecomment-6205406873), HEAD `c2048ae`.

## Decisiones

- **F051:** el origen histórico no forma parte de la integridad local del sucesor. Si no puede leerse o verificarse, no proporciona una ruta `recover_source`; los gates locales del sucesor siguen verificando sus propios bytes. Un origen accesible con el restart exacto pendiente conserva la orientación actual; una identidad contradictoria entre ambos sigue siendo error.
- **F053:** separar planificación de traza de su commit. Comprobar el origen y la elegibilidad del sucesor sin aplicar eventos pendientes ni reconstruir archivos. Solo una cancelación aceptada recupera sus trazas y persiste el recibo. Un rechazo conserva archivos de dominio en ambos runs y sesiones; los locks de coordinación pueden crearse.
- **F052:** ampliar la excepción de cancelación a un sucesor reservado todavía vacío si todos los claims activos del origen están ausentes. Conservarlos como `missing_unknown`, sin recibo de cleanup ni liberación sintética. No permitir esta vía si queda un claim presente, transferencia iniciada, evidencia o trabajo en el sucesor. Después del abandono puede solicitarse otro restart autorizado que excluya las rutas ausentes.
- **F050 residual:** cumplir la alternativa mínima indicada por el revisor: regresión reproducible de dos sesiones y documentación explícita de la falta de salida automática cuando ya existe un sidecar propio. No introducir rollback de claims ni reservas de sesiones en esta corrección. Preservar ambos runs y sesiones, no limpiar recursos ajenos para desbloquearlos, y permitir una revisión nueva independiente solo con autorización explícita. El restart anterior permanece pendiente: no presentarlo como resuelto.

## Límites y compatibilidad

No modificar reviews reales, migrar formatos ni publicar una versión. Mantener el recibo terminal de archive 7 y sus guards. Verificar origen ausente/inválido, integridad alterada del sucesor, rechazo con traza pendiente, cancelación por ausencia, replay interrumpido y la limitación de adopción múltiple. La traza pendiente solo admite bytes previos o planeados con sus hashes y eventos verificados; el preflight no relaja los gates finales.
