# Plan de implementación para fiabilidad y eficiencia de CCR

> **Estado.** Las nueve tareas se completaron y los ensayos posteriores de cobertura, admisión de seguimientos y lectura real de GitLab están recogidos en las [notas de 3.8.0](../../releases/3.8.0.md).

**Objetivo.** Reducir el tiempo y los tokens dedicados a gestionar artefactos y hacer más consistentes los hallazgos, los seguimientos y los cierres de CCR.

**Diseño propuesto.** Concentrar la selección de evidencia, su lectura y las proyecciones deterministas en los helpers Python. Devolver al coordinador referencias y diagnósticos acotados. Mantener las comprobaciones de entrada, evidencia, independencia, retención, limpieza y cierre en sus puntos de autoridad.

**Base inspeccionada.** CCR 3.7.0, commit `1ff71c50a7d1d1d6d83cfb811ec893f2f61a5feb` de `main`, coincidente con la referencia local `origin/main`. El encargo y la evaluación del 7 de noviembre de 2026 sobre CCR 3.0.0+ sirven de especificación funcional. Este plan documenta las decisiones propuestas y la evidencia para evaluarlas.

## Restricciones

- Mantener el perfil que corresponde a los hechos del scope, los 27 IDs de dimensión, la investigación de consumidores afectados, las obligaciones de verificación independiente y las validaciones del proyecto. La falta de recursos se registra mediante el mecanismo de degradación aplicable.
- Conservar inputs fijados, selección explícita y límites de evidencia, identidad del run, atribución, orden observado de hitos, claims, hashes, privacidad y reintentos sobre los mismos bytes.
- Mantener la lectura de los formatos publicados y los bytes de sus archivos cerrados. Si una mejora exige un formato nuevo, separar su diseño, sus pruebas de compatibilidad y su integración con lectores.
- Respetar la elección automática entre persistencia completa y compacta. La modalidad inline observada sirve de comparación exploratoria. Toda propuesta de producción mantiene la persistencia exigida por CCR.
- Conservar la autorización de publicación, la proyección pública y la lectura de vuelta. Las ejecuciones autorizadas en este worktree abarcan las tareas 1 a 8.

## Diagnóstico al 12 de noviembre de 2026

| Tema | Estado en la base inspeccionada | Pendiente |
|---|---|---|
| Defecto frente a hipótesis | La regla exige obligación, escenario y consecuencia en la verificación existente. La estructura final admite un hallazgo con prosa que reconoce comportamiento correcto o evidencia insuficiente. | Hacer explícita la disposición del candidato antes de asignar prioridad, sin otra ronda de agentes. |
| Exclusión y continuidad | El resultado ya conserva origen, prioridad, bloqueo, motivo y estados de re-review. El formato de hallazgo no representa la disposición de resolución con su autoridad y alcance. | Mantener las decisiones acreditadas al agrupar, reabrir, redactar y proyectar. |
| Dictamen del seguimiento | La guía y el gate de reutilización ya separan cobertura del delta y cobertura ordinaria heredada. El dictamen se conserva como valor escalar y el alcance efectivo puede quedar en una limitación del informe. | Vincular el alcance del dictamen a la proyección visible en cada salida. |
| Cierre y degradación | Los gates por fase, el preflight de candidato, las intenciones durables y los receipts ya existen. El coordinador todavía debe encadenar comandos y entregar observaciones correctas. El contrato ya representa fallbacks de obligaciones conocidas. | Aplicar el mismo control al decidir el perfil con recursos limitados y simplificar la coordinación de un cierre recuperable. |
| Presentación pública | 3.7.0 añadió contexto editorial de hallazgos y draft 4 ligado a la fuente. La verificación remota acepta CRLF convertido a LF; sigue exigiendo el LF terminal del borrador. | Resolver la normalización de GitLab y comprobar UTF-8 y proyección canónica en el mismo flujo. La publicación desde compacto sin disclosure seleccionado conserva su gate actual. |

Fuentes de la base. [Guía de CCR](../../../SKILL.md), [calibración](../../../references/contracts/priority-calibration.md), [contrato final](../../../references/contracts/result-contract.md), [re-review](../../../references/workflow/re-review.md), [reutilización](../../../references/workflow/reuse.md), [publicación](../../../references/reporting/publication.md), [notas de 3.7.0](../../releases/3.7.0.md).

La muestra local incluye hipótesis confirmadas sin obligación acreditada, deuda aceptada que reapareció como corrección requerida, diferencias de cobertura con el mismo código, retención fallida seguida por limpieza, degradación de independencia sin estado verificable y fallos de codificación de comentarios.

### Costo de la persistencia

| Fase | Trabajo que debe realizarse | Oportunidad |
|---|---|---|
| Admisión y preparación | Fijar scope, cambios efectivos y materiales. Seleccionar perfil y modalidad. Preparar o recuperar el run exacto. | Referenciar los mismos inputs y catálogos en lugar de volver a construirlos para cada invocación. Mantener la comprobación de aplicabilidad y la frescura en el momento que corresponda. |
| Discovery y verificación | Registrar asignaciones e hitos observados, investigar y ejecutar los checks que exige el scope. | Pasar a los workers referencias acotadas al brief y al código fijado. Pasar al coordinador el propósito, estado y referencia del check. Leer el fragmento decisivo cuando se necesite. |
| Retención completa | Preflight del candidato, selección y comprobación de fuentes, render, retención y validación anterior a la limpieza. | `preflight_run` y `retain` cargan el candidato y la evidencia en procesos separados. Dentro de `retain` también se carga la selección para preflight y se construye el inventario para retener. Compartir los bytes de la misma operación y comprobar el resultado escrito. |
| Retención compacta | Reservar, conservar ejecución observada, ligar identidad antes del disclosure, retener y validar. | `bind-compact` devuelve el final completo por stdout. `retain-compact` y el escritor también construyen versiones del informe. Escribir el resultado ligado en el workspace y preparar una sola proyección canónica por transacción cuando el caller no suministra un informe. |
| Limpieza y cierre | Verificar retención, limpiar claims exactos con receipts, observar estado, cerrar y validar lectura final. | El cierre vuelve a comprobar evidencia y recursos. Automatizar los pasos contiguos con los gates existentes y un estado recuperable para cada interrupción. Mantener la lectura independiente posterior a la escritura. |
| Publicación solicitada | Verificar vigencia, preparar proyección y borrador, enviar por el canal autorizado, releer y comprobar. | Mantener archivos canónicos en la sesión y emitir recibos breves. Resolver el LF en la comparación remota para evitar comprobaciones manuales repetidas. |

Fuentes del recorrido. [Comandos de archivo](../../../scripts/ccr/cli/artifacts.py), [retención completa](../../../scripts/ccr/archive/retention.py), [evidencia](../../../scripts/ccr/archive/evidence.py), [compacto](../../../scripts/ccr/archive/compact.py), [ciclo de vida](../../../scripts/ccr/archive/lifecycle.py), [limpieza](../../../scripts/ccr/archive/resources.py).

Tomé las entradas top-level completas de 3.6.0 y 3.7.0 del archivo local. Conté únicamente archivos de `evidence/` enumerados en los hashes del cierre o manifiesto, con inventario presente, y sumé sus tamaños actuales. El recuento de duplicados usa hashes registrados dentro de cada run. Esta consulta de metadatos describe el volumen archivado, sin medir lecturas del modelo.

| Versión y modalidad | Corridas | Perfiles | Mediana de archivos | Mediana de bytes |
|---|---:|---|---:|---:|
| 3.6.0 completa | 96 | 77 deep, 11 standard, 8 focused | 37 | 565 467 |
| 3.6.0 compacta | 15 | 13 focused, 2 standard | 4 | 8 664 |
| 3.7.0 completa | 13 | 10 deep, 2 standard, 1 focused | 41 | 5 215 115 |

En las 13 completas de 3.7.0 la mediana fue de cuatro entradas con hash ya presente en el mismo run y cero bytes repetidos. La mayoría de las entradas repetidas eran archivos de stderr. El volumen repetido agregado fue de 8 043 153 bytes, repartido de forma desigual. Esto justifica investigar los insumos de checks que se vuelven a copiar en ciertos runs, con menor prioridad que reducir lo que se envía al coordinador. Los perfiles de las muestras difieren y no encontré compactos 3.7.0 completos en ese corte.

Los **5–7 reviews completos** frente a **8–12 inline** dentro de una cuota de cinco horas son observaciones del usuario. Los artefactos consultados carecen de contadores comparables por fase para atribuir la diferencia a tokens, cuota, tiempo o complejidad. Los tamaños anteriores no se convierten a tokens.

La rama local `docs/archive-layout-dedup-spec` en `0e5c62f` ya trabaja en el layout 3 y el acortamiento de rutas. Integrar el trabajo futuro sobre la base que corresponda al momento de ejecución, comprobando lookup, promoción y restart en ambos layouts si esa rama se integra primero. El rediseño de nombres queda a cargo de esa rama. La optimización de este plan se centra en lecturas, llamadas, datos repetidos y recuperación.

### Opciones de implementación

| Opción | Ventaja | Límite |
|---|---|---|
| Solo simplificar las instrucciones | Entrega rápida que reduce lecturas repetidas y transferencias al chat. | Deja al coordinador la secuencia de fases y parte de los reintentos. |
| Helpers por fase con resultados breves | Reduce pasos manuales y permite compartir bytes dentro de una operación. Usa las transacciones y gates actuales. | Requiere pruebas de equivalencia, cambio de inputs e interrupción antes de ampliar el uso. |
| Un proceso que abarque el review completo | Podría conservar más estado en memoria. | Introduce dependencias del harness y dificulta los límites de aprobación, la independencia y la recuperación. |

**Recomendación del plan.** Aplicar primero la simplificación de instrucciones y las salidas acotadas. Añadir después operaciones por fase donde las pruebas demuestren que las mismas comprobaciones siguen activas. Tratar el ahorro de disco como una optimización posterior, a partir del inventario y sin compartir archivos mutables entre runs.

La ejecución de las tareas 1 y 2 incluye retirar la captura habitual del modelo. El modelo queda como dato suministrado en una evaluación solicitada o en un ledger explícito o histórico. Se conserva la identidad del harness y la procedencia observada de la ejecución. El [registro de validación](../../validation/2026-11-12-ccr-fiabilidad-y-eficiencia-tareas-1-2.md) documenta la línea base y el alcance de las mediciones.

## Orden de implementación

| Orden | Prioridad | Tarea | Dependencia |
|---|---|---|---|
| 1 | Alta | Fijar un conjunto de regresiones y una línea base de costo | Base actual |
| 2 | Alta | Reducir el contexto y las transferencias de artefactos | 1 |
| 3 | Alta | Unificar la lectura y preparación de evidencia por fase | 1 y 2 |
| 4 | Alta | Simplificar finalización y recuperación | 3 |
| 5 | Alta | Confirmación, agrupación y reapertura de hallazgos | 1 |
| 6 | Alta | Disposición de resolución y alcance visible del dictamen | 5 |
| 7 | Media | Selección de perfil y degradación observada | 1 |
| 8 | Media | Comparación remota y proyección canónica | 6 para la integración de salidas. El cambio de LF puede validarse por separado. |
| 9 | Alta para adoptar el flujo | Comparar costo y calidad y documentar la ruta recomendada | 2–8 |

### 1. Fijar la línea base y los casos de regresión

**Archivos.** `references/maintenance/evaluation.md`, `tests/fixtures/review_inputs.json`, `tests/test_review_scenarios.py`, `tests/test_review_comment.py` y el registro de validación. Se reutilizaron el esquema y las pruebas de métricas existentes.

- [x] Preparar fixtures mínimos anonimizados con respuesta esperada fuera del contexto del reviewer. Cubrir defecto introducido y consumidor adyacente, riesgo hipotético, deuda explícita, mismo HEAD con cobertura distinta, cambio de materiales con mismo HEAD, interrupción de cierre y verificación remota con LF omitido.
- [x] Fijar por fixture el input, perfil, obligaciones, resultados esperados y punto donde el flujo puede detenerse. Capturar el comportamiento actual con los helpers existentes.
- [x] Registrar fase, modalidad, versión, harness, contadores disponibles y la base de comparación. Para mediciones solicitadas, usar modelo y esfuerzo solo cuando se suministren. Reutilizar el esquema de métricas actual.

**Aceptación.** Cada caso tiene una aserción sobre un comportamiento observado o un contrato explícito. Cada contador ausente queda como desconocido y los totales inclusivos se cuentan una sola vez.

### 2. Mantener los datos grandes fuera de la conversación

**Archivos principales.** `SKILL.md`, `references/workflow/reading-strategy.md`, `references/archive/artifacts.md`, `scripts/ccr/cli/artifacts.py`, `scripts/ccr/workflow/setup.py`, `tests/test_review_compact_cli_output.py` y `tests/fixtures/scripts_cli_contracts.json`. Se reutilizó el escritor de candidatos existente.

- [x] Extender la lectura por fase existente con una ruta breve de archivo. Fijar los nombres y referencias de inputs, catálogo, candidato, diagnósticos y resultado una vez por run. Pedir el archivo o rango decisivo solo si el juicio o un gate lo necesita.
- [x] Proponer en `bind-compact` una salida a archivo explícitamente seleccionado de una sesión propia y devolver solo estado, identidad, ruta y hash. Usar el escritor de candidatos existente y mantener la salida actual sin esa opción. El disclosure y la retención consumen exactamente el archivo ligado.
- [x] Revisar las otras salidas de archivo con el mismo criterio. Priorizar comandos que devuelven el cuerpo completo o inventarios que el coordinador vuelve a introducir en otra llamada. Dejar el diagnóstico completo consultable en los límites actuales.

**Aceptación.** La ruta nueva y la actual producen el mismo registro ligado y pasan los mismos gates. Un destino ajeno, un intento de sobrescritura o una identidad incompatible se rechazan. Un diagnóstico breve permite localizar el fallo sin volcar evidencia al chat.

### 3. Reutilizar bytes y render dentro de la misma fase

**Archivos.** `scripts/ccr/archive/evidence.py`, `scripts/ccr/archive/retention.py`, `scripts/ccr/archive/compact.py`, `scripts/ccr/cli/artifacts.py`, `scripts/ccr/contracts/preflight.py`, `tests/test_review_preflight.py`, `tests/test_review_compact_archive.py`, `tests/test_review_atomic_recovery.py`.

- [x] Hacer que el preflight interno de retención y el escritor consuman la misma selección acotada de bytes. Usar el mapa actual de referencia a bytes y mantener el preflight independiente para diagnóstico. Ejecutar las validaciones de selección, material, referencias semánticas, origen y topología antes de escribir.
- [x] Evitar la lectura repetida de una fuente durante una operación cuando sus bytes ya fueron verificados y son exactamente los que se persistirán. Revalidar en cambios de fase, tras reintentos y al leer del destino según el contrato. No sustituir la selección por un caché entre corridas ni inferir identidad a partir de mtime.
- [x] Dar a la ruta CLI compacta un modo de render desde el registro ligado y las fuentes seleccionadas, manteniendo la comprobación de un informe explícito para los callers que lo suministran. Medir el número de lecturas y renders en fixtures con y sin disclosure.
- [x] Revisar las copias de inputs de check con hash repetido. El contrato de receipts mantiene las referencias y los roles separados. Se reutiliza la lectura por referencia dentro de cada fase.

**Aceptación.** Un cambio de fuente, alias ambiguo, path ajeno, material ausente, candidato inválido o disclosure con digest distinto falla en el gate correspondiente. Una interrupción permite recuperar solo los bytes fijados. El informe canónico y la selección de evidencia coinciden con la ruta vigente para el mismo fixture.

### 4. Simplificar finalización y recuperación

**Archivos.** `scripts/ccr/cli/artifacts.py`, `scripts/ccr/archive/lifecycle.py`, `scripts/ccr/archive/resources.py`, `scripts/ccr/archive/inspection.py`, `references/archive/recovery.md`, `tests/test_review_closure_consistency.py`, `tests/test_review_disclosure_close_recovery.py`, `tests/test_review_operational_summary.py`.

- [x] Exponer un estado breve por run que identifique el gate fallido, el recurso afectado y el siguiente paso permitido. Reusar el resumen de `inspect` y los diagnósticos del preflight. Separar la corrección de candidato, el cambio de insumos, la intención pendiente y el cierre pendiente.
- [x] Añadir `artifacts finish` para consumir las observaciones y receipts existentes, ejecutar `close` y hacer la lectura independiente de `validate --require-complete`. Mantener la limpieza física en `workspace cleanup` con sus claims y autorizaciones. La ruta guiada exige validar retención antes de invocar esa limpieza.
- [x] Cubrir interrupciones después de retener, durante el cleanup, después de guardar el receipt y durante el cierre. Un retry debe retomar el mismo run y detectar observaciones conflictivas. Si una fase no está demostrada, devolver el estado pendiente correspondiente y su evidencia.
- [x] Verificar que un candidato reparable pueda regenerarse sobre los mismos inputs sin repetir discovery, verificación ni checks observados.

**Aceptación.** Con evidencia incompleta la ruta guiada conserva los recursos. Con limpieza no acreditada el cierre no pasa. Cada interrupción reproduce una recuperación segura o un bloqueo preciso. `complete` solo se devuelve cuando la lectura final pasa.

[Resultados de validación y mediciones de las tareas 3 y 4](../../validation/2026-11-12-ccr-fiabilidad-y-eficiencia-tareas-3-4.md).

### 5. Confirmar, agrupar y reabrir por evidencia

**Archivos.** `references/contracts/priority-calibration.md`, `references/execution/worker-packets.md`, `references/workflow/re-review.md`, `scripts/ccr/contracts/findings.py`, `scripts/ccr/contracts/identifiers.py`, `tests/test_review_priority_policy.py`, `tests/test_review_scenarios.py`.

- [x] Incluir en la verificación ya prevista una decisión explícita sobre obligación, disparador alcanzable y consecuencia. Conservar el análisis estático decisivo como evidencia suficiente cuando corresponda. Colocar la mera falta de pruebas en cobertura o en una recomendación según la obligación real.
- [x] Para cada candidato relacionado con una corrección, identificar la causa y si fue introducida, preexistente o de origen desconocido. Ampliar el análisis cuando se pueda señalar el consumidor o contrato afectado y la pregunta pendiente.
- [x] Usar el mismo ID cuando sobreviva la causa. Actualizar escenario, título, impacto y corrección según lo que quedó vigente. Registrar la evidencia nueva, el insumo cambiado o el gate pendiente que justifique reapertura.
- [x] Conservar las reglas para discrepancias de documentación, defectos demostrados de bajo impacto y restricciones del proyecto.

**Aceptación.** Los casos de hipótesis futura y cobertura ausente quedan fuera de confirmados cuando carecen de obligación y daño. Una regresión de consumidor comprobada sigue visible. La misma causa conserva ID aunque cambien líneas o mitigaciones.

### 6. Mantener la decisión de resolución y el alcance del dictamen

**Archivos.** `references/workflow/re-review.md`, `references/workflow/reuse.md`, `references/contracts/result-contract.md`, `references/reporting/report-format.md`, `scripts/ccr/contracts/review.py`, `scripts/ccr/reporting/render.py`, `scripts/ccr/reporting/projections.py`, `tests/test_review_reuse_flow.py`, `tests/test_review_comment.py`.

- [x] Diseñar una representación ligada a fuente para disposición de resolución con ID del hallazgo, estado, alcance de la decisión y referencia acreditada. Conservar prioridad, origen, confirmación y bloqueo como decisiones separadas. Una propuesta del autor o un texto sin autoridad identificada queda como contexto hasta que se acredite su efecto.
- [x] Vincular la decisión antes de verificar y reutilizarla en informe, seguimiento y comentario. Una deuda aceptada con condiciones conserva esas condiciones y su evidencia. Un cambio material posterior se evalúa con la condición que cambió.
- [x] Fijar el alcance del dictamen con base, HEAD o snapshot, delta revisado y antecedentes aplicables. Derivar la etiqueta de seguimiento o revisión completa de esa cobertura observada. Aplicar la misma etiqueta en informe, respuesta y proyección pública mediante la extensión de evaluación versión 1 para final 13.
- [x] Conservar registros históricos y verificación de proyecciones anteriores. Exigir cobertura ordinaria comprobada para ofrecer un resultado como revisión global reutilizable.

**Aceptación.** La nota 23244 produce una recomendación acorde a la decisión ya registrada. Una exclusión de resolución conserva el riesgo comprobado con su disposición. Los dos casos del mismo HEAD presentan dictámenes de alcance diferente y el seguimiento por sí solo no certifica el PR completo.

[Resultados de validación de las tareas 5 y 6](../../validation/2026-11-12-ccr-fiabilidad-y-eficiencia-tareas-5-6.md).

### 7. Conservar la degradación como dato de ejecución

**Archivos.** `references/workflow/profiles.md`, `scripts/ccr/workflow/profiles.py`, `scripts/ccr/workflow/persistence.py`, `scripts/ccr/contracts/execution.py`, `tests/test_review_profiles.py`, `tests/test_review_profile_topology.py`, `tests/test_review_compact_promotion.py`.

- [x] Hacer explícita la selección técnica antes de evaluar capacidad del harness. Cuando una obligación de independencia no puede cumplirse, usar las filas de fallback y la fuente observada existentes. Retener la limitación material correspondiente.
- [x] Comprobar que una restricción operativa no reduzca el perfil ni habilite compacto cuando los hechos exigen completo. Mantener la promoción antes del trabajo dependiente si se descubre una obligación posterior.

**Aceptación.** Cuando el harness carece de capacidad para una asignación independiente la salida refleja la independencia realmente disponible. Un scope elegible para standard y verificación omitida por ausencia de candidatos conserva esa decisión válida.

### 8. Verificar publicación y presentación

**Archivos.** `scripts/ccr/reporting/comment.py`, `scripts/ccr/cli/comment.py`, `references/reporting/publication.md`, `tests/test_review_comment.py`, `tests/test_review_comment_editorial.py`, `tests/test_review_publication_legacy.py`.

- [x] Añadir `--remote-transport gitlab` para la verificación remota. Tras el render canónico y la comparación CRLF vigente, admitir exclusivamente que el cuerpo observado sea el canónico sin un único LF terminal. Conservar digest del draft y de los bytes observados y registrar la transformación aplicada.
- [x] Verificar coincidencia exacta local, coincidencia remota ordinaria y LF único de GitLab. Rechazar cambios internos, whitespace adicional, pérdida de más bytes o texto con codificación inválida. Mantener la política histórica de drafts 2/3.
- [x] Usar el render canónico y archivos UTF-8 para generar y comprobar el borrador. Cubrir acentos, puntuación y enlaces en los casos editoriales. Mantener los gates de disclosure, privacidad, vigencia, autorización y comprobación remota.

**Aceptación.** Un LF terminal omitido por el transporte identificado produce comprobación acreditada. Una diferencia material conserva el estado de discrepancia. La comprobación de contenido no afirma por sí sola que hubo publicación.

[Resultados de validación de las tareas 7 y 8](../../validation/2026-11-12-ccr-fiabilidad-y-eficiencia-tareas-7-8.md).

### 9. Comparar costo y conservar resultados antes de recomendar la nueva ruta

**Archivos.** `references/maintenance/evaluation.md`, `references/maintenance/measurements.md`, `tests/test_review_metrics.py` y el registro futuro de validación en `docs/validation/`.

- [x] Comparar primero, sin modelo, los mismos fixtures con los helpers base y nuevos. Medir llamadas externas, lecturas y renders repetidos, bytes emitidos al coordinador y tiempo por fase. Incluir rutas normales, reintento de candidato y cierre interrumpido.
- [x] Comparar la fase guiada de archivo anterior y nueva con scopes fijados y el mismo perfil, harness, capacidades, modelo y esfuerzo. Se ejecutaron dos pares completos y dos por cada variante compacta. La referencia inline tiene otra persistencia y quedó fuera de la medición.
- [x] Medir tokens reales de entrada, salida, caché y razonamiento en la fase de archivo. Se midieron arranque, turno activo, llamadas y salida del helper. El consumo de cuota por revisión queda pendiente de medición atribuible.
- [x] Comparar cobertura, checks requeridos, veredictos, proyecciones y estados recuperables en fixtures deterministas. Informar distribuciones y tamaños de muestra y ejecutar la suite de contratos.
- [x] Comparar defectos omitidos y falsos confirmados en ejecuciones guiadas ciegas desde el inicio del review. Se completaron cinco pares. Se conservaron los gates, con divergencias de cobertura y un falso confirmado de código en la variante nueva. [Informe de principio a fin](../../validation/2026-11-12-ccr-comparacion-principio-a-fin.md)
- [x] Probar el inventario de `unittest discover -s tests` desde el worktree de implementación. Se ejecutaron los mismos IDs en diez procesos, con 1358 aprobados y tres omisiones de enlaces simbólicos tras repetir los casos afectados por el host.

**Aceptación.** En fixtures equivalentes se reduce el trabajo redundante que se decidió atacar y los casos de integridad, independencia, recuperación y privacidad conservan su resultado esperado. Se informa ahorro de tokens solo cuando los contadores comparables lo demuestran. Si el cambio ahorra llamadas pero degrada el resultado o el cierre, se conserva la ruta vigente y se corrige la causa.

La prueba inicial de Codex CLI quedó bloqueada al lanzar PowerShell. El piloto posterior usó Codex app-server con una herramienta dinámica que ejecutó los helpers reales y devolvió sus salidas al coordinador. [Informe y recomendación de la tarea 9](../../validation/2026-11-12-ccr-fiabilidad-y-eficiencia-tarea-9.md) · [Piloto controlado](../../validation/2026-11-12-ccr-piloto-controlado.md).

## Casos que requieren comprobación explícita

- Los requisitos o la descripción cambian con HEAD idéntico. Tareas 1, 3 y 6.
- El archivo observado cambia entre la captura y la fase siguiente, o hay un cambio de layout con un intento anterior pendiente. Tareas 3 y 4.
- El proceso se interrumpe después de remover un recurso y antes de persistir su receipt. Tarea 4.
- Una aceptación de riesgo tiene autoridad y alcance distintos al comentario que la cita. Tarea 6.
- La lectura remota difiere por algo adicional a la normalización admitida o carece de procedencia. Tarea 8.
