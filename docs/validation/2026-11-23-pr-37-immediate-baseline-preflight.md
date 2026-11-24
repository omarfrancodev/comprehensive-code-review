# Copia del antecedente inmediato en el preflight del PR 37

Base `1c40f24271af7a30535934341d60bd764cf65493`. El [re-review CR-b3f25f4a77fc4ef1aab0](https://github.com/omarfrancodev/comprehensive-code-review/pull/37#issuecomment-7118066143) confirmó F032 y F033 y abrió la reserva F036.

El preflight coteja la copia seleccionada en `assessment.previous.source` con el SHA-256 del archivo previo verificado. El mismo cotejo se usa para la copia del precursor histórico cuando corresponde. Si falta o difiere una copia, el preflight indica el campo y la ruta del archivo verificado. El resumen conserva esa ruta como el recurso que requiere atención.

La regresión usa un candidato nativo v3 con un antecedente compacto v2 y su precursor histórico. Sobre la base, la copia inmediata ausente y la alterada devolvieron `ready=true`. Con el ajuste, el preflight y el resumen detectan las dos variantes y la retención rechaza ambas sin modificar los archivos. Se conservan los casos de precursor ausente o alterado. Con las copias exactas, la retención y el cierre pasan el lector completo.

Pasaron 33 pruebas focalizadas de preflight, compatibilidad histórica, dependencias y referencias en 41.522 s, con Python 3.14.3 en Windows y sin omisiones. La selección incluye la respuesta estructurada para esquemas anteriores y el flujo completo con las dos copias verificadas.
