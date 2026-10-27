# Ejemplos de frontera de prioridades

Ejercicios sintéticos para aplicar la [rúbrica canónica](../../references/contracts/priority-calibration.md). No son hallazgos de productos ni pruebas de que un modelo clasifique correctamente; el [protocolo](../validation/priority-calibration-protocol.md) define cómo evaluarlo. No es necesario cargar este documento durante cada review.

| Hechos comparables | Decisión y motivo |
|---|---|
| Acceso de lectura/escritura a historias privadas de otra entidad, introducido o preexistente | P1 en ambos por autorización e integridad serias. El origen puede cambiar si bloquea ese MR; no cambia por sí solo el daño |
| Lote vacío accidental marca vendido todo el inventario de una entidad y escribe ventas falsas; el autor reconoce o no el riesgo | P1 con el contrato que exige rechazar ese vacío. El reconocimiento no cambia obligación ni reconciliación necesaria |
| Catálogo válido aborta migración por longitud; instancia anterior disponible | P1 por impedir despliegue soportado, con evidencia estática decisiva o reproducción. Atomicidad evita corrupción parcial, no evita ese fallo |
| Actualización obligatoria del proceso principal se pierde sin replay, frente a panel secundario retrasado y recuperado automáticamente | P1 por la pérdida seria; P2 si se prueba solo incumplimiento funcional acotado con recuperación |
| Error entrega credencial que permite leer datos privados acotados, frente a un ID público sin contenido/acceso adicional | P1 en el primero; P3 puede encajar en la discrepancia diagnóstica limitada del segundo. No clasificar por la palabra token o GUID |
| Arranque destruye el único almacén esencial, frente a guard que impide toda escritura destructiva y permite operar | P0 si cadena y consecuencia catastrófica inmediata están demostradas; rechazar la hipótesis en el segundo cuando no queda efecto incorrecto |
| Escritura ajena con todos los guards inspeccionados, frente a un guard externo desconocido que determina si se autoriza | Confirmar y evaluar P1 en el primero; unresolved en el segundo, no P2 confirmado por falta de información |
| Fallback parcial permitido y señalado, frente a éxito completo incorrecto en reporte secundario regenerable | Rechazar la acusación contra el fallback permitido; P2 para la obligación de completitud incumplida y acotada |
| Falta de test con flujo correcto, frente a filtro que descarta una categoría válida | Cobertura/recomendación en el primero, defecto P2 acotado en el segundo. El test ausente no determina prioridad |
| Ayuda con errata y envío correcto, frente a un filtro que elimina ceros iniciales válidos | P3 frente a P2: diferencia textual limitada frente a opción funcional incorrecta |

Ejemplo de `impact` para un finding nuevo confirmado:

> El lote altera persistentemente todas las unidades de la entidad y crea movimientos falsos. Corresponde P1 por impedir las reservas de ese ámbito y requerir reconciliar el histórico; no se acredita una cadena catastrófica sobre el servicio completo.

La explicación cabe en el impacto existente. Purpose del check describe la hipótesis a comprobar, su resultado conserva lo observado y blocking_reason trata el bloqueo del alcance. Una misma dimensión puede cubrir hallazgos de distintas prioridades o no tener hallazgos.
