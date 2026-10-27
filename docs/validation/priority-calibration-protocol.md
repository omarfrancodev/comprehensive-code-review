# Protocolo de calibración de prioridades

Este protocolo evalúa aplicación de instrucciones a hechos sintéticos suministrados. No mide discovery de defectos, ejecución completa de CCR, incidentes reales ni ahorro de tiempo/tokens. La referencia propuesta requiere ratificación humana para declarar calibración conseguida; mientras falte, todos los resultados son exploratorios.

## Entradas y separación

Los cuatro archivos de `tests/fixtures/priority_calibration/` separan inputs de referencias. PC01–PC20 son desarrollo; PC21–PC28 son aceptación. Los arquetipos son públicos en el spec; un custodio separado redacta y guarda los hechos concretos de aceptación antes de ajustar la guía. El implementador no lee esos inputs, referencias ni respuestas hasta congelar candidato. Si ya los vio, marcar la reserva como expuesta y pedir variantes nuevas custodiadas antes de una aceptación concluyente.

Congelar con hashes SHA-256 los bytes de corpus, referencias e instrucciones de baseline/candidato. Para baseline usar las fuentes de `d119fbc` (CCR 3.3.0), no la instalación activa. La evaluación de rol puede usar los extractos pertinentes de verificación, findings, prioridad y veredicto, siempre que se conserven fuentes/extracción y se aplique la misma base a ambas condiciones. El candidato añade la guía y sus rutas nuevas. Distinguir esta prueba de rol de una ejecución de toda la skill.

## Ejecución

1. Comprobar `test_review_priority_corpus.py`; revisar neutralidad del lenguaje y ratificar referencias, o registrar explícitamente que siguen propuestas.
2. En contexto limpio, entregar al ejecutor de baseline solo instrucciones de baseline e inputs. Nunca entregar reference, etiquetas esperadas, historial de respuestas o la conversación del implementador.
3. Conservar respuestas crudas y su hash. Los hechos que describen pruebas dentro de un caso son sintéticos; no registrarlos como ejecuciones reales de producto.
4. Ajustar guía usando únicamente desarrollo. Congelar bytes e identidad del candidato antes de abrir aceptación.
5. En otro contexto limpio con la misma configuración/modelo disponibles, entregar candidato e inputs idénticos. Identidad/configuración no expuesta por la plataforma queda desconocida; no sondearla ni inventarla.
6. Ejecutar las parejas PC01/02 y PC03/04 de nuevo en orden inverso, en contextos limpios de cada condición; no reutilizar al clasificador anterior. La primera ejecución sigue siendo comparable porque ambos usan orden normal; la inversa mide variación de orden, no cinco repeticiones ni estabilidad general.
7. El evaluador compara con reference después de emitir respuestas; el custodio puede puntuar aceptación sin entregar sus hechos al autor antes de congelar.

Formato de respuesta del ejercicio: lista de `{id, status, priority, justification}`. Status: confirmed/rejected/unresolved. Priority P0–P3 solo para confirmed, null en los otros. Esto no es packet 1 ni final 11: estos contratos conservan su forma actual y final exige priority incluso para unresolved. No usar una prioridad nula del ejercicio para crear un resultado CCR final inválido.

## Medidas y decisión

Registrar por caso omisión, respuesta inválida, status correcto/incorrecto y, solo si confirmó correctamente un defecto, prioridad dentro/fuera de `accepted_priorities`. Una hipótesis confirmada es un error de confirmación, no una mejora por asignar P1. Informar además:

- Subclasificaciones de positivos P0/P1, con numerador/denominador de positivos esperados.
- Elevaciones injustificadas a P0/P1, incluyendo confirmaciones erróneas, con denominadores explícitos.
- Positivos P0 omitidos y falsos P0 confirmados.
- Consistencia de las parejas `same_priority` y cambios en repeticiones inversas.
- Explicación de consecuencia, alcance y recuperación; una comparación automática de etiquetas no mide fidelidad semántica de la justificación.

Criterios: ninguna diferencia indebida en same_priority; ningún positivo P0 omitido ni falso P0 en aceptación; ninguna confirmación indebida de negativos/no resueltos; menos errores graves que baseline cuando baseline los tenga, sin nuevas elevaciones injustificadas. Si baseline ya acierta, conservar acierto y describir mejora de claridad sin afirmar una ganancia de precisión. Sin ratificación humana o con independencia/reserva no demostradas, no declarar calibrada ni lista para distribuir.

Si aceptación falla, conservar ese resultado. Ajustar con desarrollo y usar una nueva variante reservada ratificada, registrando la exposición anterior. No cambiar referencias, añadir repeticiones hasta conseguir un acierto ni descartar errores del denominador para aprobar. La distribución histórica de prioridades nunca es una cuota objetivo.

## Registro observado

El registro con fecha real debe enlazar el commit/base, manifiestos y respuestas anonimizadas, identidades de contextos observadas, selección de modelos disponible/desconocida, ratificación y reserva, resultados por caso, medidas con denominadores, fallos/pendientes y comandos mecánicos con resultados. Separar tests estructurales, caracterización de transporte y conducta exploratoria/ratificada. Mantener baseline, candidato y referencias inmutables durante cada comparación. No publicar, instalar la skill ni crear release como consecuencia de este protocolo.
