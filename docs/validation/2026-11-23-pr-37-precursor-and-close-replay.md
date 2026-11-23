# Precursor inventariado y reintentos de cierre del PR 37

Fecha 2026-11-23. Base `26856a3403c0786c1d1fed3bd9dc6421d01db4c6`. El [re-review CR-1d96b668c61743e2ae2d](https://github.com/omarfrancodev/comprehensive-code-review/pull/37#issuecomment-7112056296) confirmó F026–F029 y abrió F030 y F031.

**F030.** El punto de verificación compartido por la retención completa y compacta exige `assessment.previous.legacy_source` en una nueva adopción v3 si el v2 verificado ofrece ese precursor. El digest debe coincidir con el inventario del archivo. Las comprobaciones de fuentes del escritor verifican los bytes seleccionados y la continuidad de las autorizaciones. La lectura histórica sigue usando la evidencia de cada archivo retenido.

La regresión retiene dos v2. El primero acredita dos actos con igual contenido y el segundo consolida sus IDs. En la base, el escritor compacto aceptaba omitir el precursor y conservar un solo acto. Con la corrección, rechaza la omisión antes de persistir el payload o su intención. Seleccionar el precursor y releer el resultado conserva `F001` y `F002` como miembros de dos autorizaciones.

La selección de adopción histórica, autorizaciones, lineage, proyección y dependencias pasó 58 pruebas en 10.195 s, sin omisiones. Incluye el nuevo caso compacto y las regresiones de lectura v2/v3. Se ejecutó con Python 3.14.3 en Windows y temporales desechables.

**F031.** Si el registro que aún está en disco coincide con el hash previo, la recuperación usa ese registro tal como se guardó. Conserva sus residuales aunque difieran del manifiesto o el JSON tenga una representación no canónica. Si el reemplazo llegó a disco, solo se consideran las listas completas de residuales del manifiesto y del registro planeado verificado. La reconstrucción debe reproducir el hash previo y el nuevo plan debe coincidir con todo el inventario de reemplazo. Si falta información para acreditar esos bytes, ambos reintentos preservan el archivo.

El caso de dos interrupciones reprodujo el fallo para reintento automático y expreso, con JSON canónico y no canónico. También se reprodujo un caso posterior al reemplazo cuya lista de residuales ya estaba acreditada por el plan. Las regresiones conservan el rechazo sin escrituras cuando ninguna lista retenida permite reproducir el hash previo.

La revisión independiente comprobó el gate compartido de F030 y el orden de verificación previo a las escrituras de recuperación de F031. Seis comprobaciones adicionales de referencias e integridad del cierre terminaron sin fallos ni omisiones en 36.350 s, antes de ampliar el fallback de las listas.

La primera corrección pasó las 13 pruebas de transición en 222.130 s y 23 pruebas de divulgación y recuperación atómica en 334.995 s. Tras ampliar el fallback, las 14 pruebas del módulo de transiciones mostraron `ok` individualmente. Incluyen el caso posterior al reemplazo con residuales acreditados por el plan y la preservación con datos insuficientes. Se interrumpió la extensión repetida de divulgación y recuperación atómica después de ese módulo. Los 23 resultados corresponden a la invocación anterior completa.
