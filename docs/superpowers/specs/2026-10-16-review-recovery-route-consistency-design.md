# Rutas de recuperación coherentes entre origen y sucesor

Correcciones del séptimo CCR del PR 19: [CR-bcb75bf8adc74fa5a797](https://github.com/omarfrancodev/comprehensive-code-review/pull/19#issuecomment-6218944810), HEAD `009459f`.

## Decisiones

- F055: ampliar el diagnóstico puro a sesiones seleccionadas con claim ajeno verificado. Una sesión propia del origen/sucesor no es un conflicto ajeno. Un claim externo no verificable produce preservación/error, sin recuperar su trabajo ni modificarlo. Reutilizar el preflight para distinguir cancelación soportada de review independiente.
- F056: compartir la salida calculada en el origen con inspect/lookup/recover del sucesor, evitando un salto recover_source cuando ya se conoce el bloqueo. Conservar los campos legacy de integridad; añadir recovery con estado explícito, can_complete false, cancellation_supported y bloqueantes. recoverable significa transacción pendiente preservada, no promesa de que recover la termina. Una transferencia entrante con fuente no verificable ofrece preservación y una alternativa independiente explícita, nunca ready ni un recover que se sabe imposible.
- F057: distinguir claims presentes/releasing del origen, transferencia pendiente y estado no vacío del sucesor. La razón y recovery.blocked_by deben nombrar la causa observada. Repetir la condición de origen sin claims presentes/releasing en el resumen documental.
- F052, mejora opcional: conservar el error de reintento exacto, añadiendo una referencia a inspect/recover del origen para descubrir su salida. No implementar rollback de transferencias ni nuevas reservas.
- F050/F052 permanecen como reservas del protocolo. Las indicaciones son planes sin escrituras ni autoridad implícita; los mutadores vuelven a validar bajo locks. Identidad/reserva y corrupción local se verifican antes de clasificar falta de soporte.

## Pruebas y límites

Cubrir claim ajeno simple y adopción parcial, propagación desde el sucesor, fuente de transferencia no disponible, dos claims del origen con solo uno ausente, owner ajeno alterado, error exacto con referencia al diagnóstico y preservación de todos los archivos. Conservar missing_unclaimed, igualdad de inputs y replay de cancelaciones ya decididas. No modificar artifacts reales, mergear ni publicar 2.12.0.

La revisión estática añade dos controles de integridad al mismo alcance: sidecars propios se verifican antes de clasificar un impedimento operativo, admitiendo el preflight puro de una adopción cuyo sidecar precede a su fila y los bytes exactos del intent de transferencia; una fuente ausente no exime de validar la reserva y los IDs locales del sucesor. Se reproducen ambas corrupciones en RED y se conserva la adopción parcial válida como regresión.

El control de disponibilidad histórica verifica los bytes propios de la fuente dentro de su lookup opcional; una traza corrupta de la fuente conserva source_unavailable en un sucesor íntegro. Las contradicciones de identidad y la corrupción/reserva del propio sucesor quedan fuera de ese fallback.
