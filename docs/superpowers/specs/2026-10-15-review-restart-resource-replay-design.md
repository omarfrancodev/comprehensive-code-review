# Correcciones del tercer CCR del PR 19

Fuente: [CR-137e48103e1d4402ae23](https://github.com/omarfrancodev/comprehensive-code-review/pull/19#issuecomment-6182635449), HEAD `0d10fed`.

## Objetivo y límites

Resolver F044, F045 y la promesa documental residual F014 dentro de la 2.12.0 pendiente. Mantener el sucesor reservado, los hashes, ownership, locks, autorización y lectura de archivos históricos. No publicar ni fusionar el PR.

## Comportamiento requerido

- F044: el replay de una reserva exacta reconoce su sucesor ya preparado antes del preflight de una sesión todavía en transferencia/adopción. Recupera exclusivamente sus transacciones verificadas y permite que el helper de recursos termine su intent. No adopta un sucesor ajeno ni oculta errores de integridad como si fuera una preparación parcial.
- F045: un origen sustituido conserva su checkpoint interrumpido como historial provisional. La validación básica puede verificar ese contenedor sin certificar el resultado; los gates retained/complete y la escritura de checkpoints de validación lo rechazan. Inspect, lookup y recover orientan al sucesor; no ofrecen reintentar un checkpoint que ya no puede ejecutarse en el origen.
- Si el origen conserva claims tras cambiar de scope, su limpieza y recuperación siguen disponibles sin promover el checkpoint. Si se transfiere la sesión dentro del mismo scope, la tolerancia del checkpoint se limita al restart durable exacto; el transfer independiente mantiene el gate estricto. El sucesor nunca hereda los inputs provisionales del origen.
- F014: documentar lo que brief muestra actualmente: identidad, resultado y cumplimiento de ejecución; los enlaces previos corresponden a reviews anteriores. El historial de perfil pertenece al archivo original y a la entrega full, sin prometer un vínculo que brief no genera.

## Evidencia requerida

Regresiones RED/GREEN de transferencia y adopción, cortes antes/después de cada reemplazo dentro de esos helpers con retry y recover, unicidad del sucesor y replay idempotente; conflicto real entre threads para impedir escrituras sobre un sucesor bloqueado; casos superseded con checkpoint sin bytes, con bytes pendientes y con bytes modificados; limpieza interrumpida del claim remanente y transferencia con checkpoint pendiente. Pruebas de delivery y documentación coherentes. Las pruebas usan archivos desechables, nunca reviews reales. La matriz usa interrupciones inyectadas: no certifica todas las salidas abruptas del proceso ni todos los ordenamientos concurrentes.
