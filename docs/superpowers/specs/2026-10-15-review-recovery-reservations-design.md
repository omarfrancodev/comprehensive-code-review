# Reservas del cuarto CCR del PR 19

Fuente: [CR-b981159ddf25415487ea](https://github.com/omarfrancodev/comprehensive-code-review/pull/19#issuecomment-6201338987), HEAD `4fa3474`.

## Alcance

Corregir F046–F050 dentro de la 2.12.0 pendiente, manteniendo los archivos históricos, autorización, identidad, locks y hashes. No fusionar ni publicar.

## Decisiones

- F046: reconstruir el intent ausente exclusivamente desde el descriptor activo verificado y su ruta exacta, bajo el lock del origen, antes de abandonarlo.
- F047: desde el sucesor de un restart activo, lookup/inspect/recover indican `recover_source`, con ruta y operación. No ejecutar el transfer independiente ni afirmar que recover del sucesor lo completa. Los errores de transferencia pendiente incluyen el origen cuando está registrado.
- F048: replay de restart exige igualdad de los inputs normalizados capturados, con el perfil efectivo fijado por el intent. La igualdad autoriza completar la transacción, no declara frescura: el appraisal histórico puede seguir unknown. Inputs diferentes no disparan trabajo.
- F049: el rechazo de un checkpoint pendiente superseded indica su sucesor registrado, sin recomendar reintentar un checkpoint que ya no acepta escrituras.
- F050: no introducir un protocolo nuevo de reservas de sesiones. Mantener el rechazo ante claims ajenos y ofrecer abandono explícito del sucesor exacto que sigue preparado, sin trabajo, evidencia, ejecutores, asignaciones, checkpoints, cleanup, transferencias ni claims propios. Debe existir un conflicto de adopción con un claim ajeno válido. Comprobar también sidecars: register puede escribir el claim antes que su fila del manifiesto.

La comprobación ajena es de identidad de ownership (manifiesto, token, sidecar y fila), independiente de la integridad de su evidencia de trabajo. Un checkpoint ajeno pendiente no obliga a recuperar ese otro review para cancelar el sucesor vacío propio. Esto no permite usar esa comprobación reducida para trabajar, transferir, retener o limpiar recursos: esos mutadores conservan verify_claim completo.

## Abandono del sucesor preparado

Se conserva su archivo, sin borrar ni mover evidencias o sesiones. Archive-7 incorpora el campo opcional validado `restart_abandonment`, con el recibo ya existente; `operation` queda blocked. La marca define un historial terminal: todos los mutadores lo rechazan, la lectura básica sigue disponible y los diagnósticos orientan al origen. No se cambia el enum de disposition ni se migra un archivo histórico.

Bajo locks del origen y sucesor, validar identidad reservada, integridad y ausencia de trabajo/claims, guardar primero el recibo embebido y evento del sucesor, completar su traza, y después guardar el mismo recibo en el origen. Finalmente registrar el evento idempotente del origen y retirar solo su descriptor exacto. El replay de una interrupción entre esas fases reutiliza el recibo original y completa la cancelación; nunca vuelve a adoptar. Una decisión ya durable se recupera aunque la frescura sea unknown o haya cambiado. Un sucesor con trabajo, con sidecar propio aun sin fila, o con datos ambiguos no se abandona por esta vía.

## Verificación

RED/GREEN por los cinco IDs; conflictos y rechazos sin mutación; fixtures de archives 1–6 y archive-7 sin identidades; ambos extremos de transfer; cancelación interrumpida y repetición idempotente; preservación del workspace/claim ajeno y nueva solicitud desde el origen. Pruebas focales y suite general, sin repetir matrices extensas que no ejerciten el cambio. Documentar límites concretos de las verificaciones.
