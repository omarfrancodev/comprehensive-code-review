# Propuesta: calibración de prioridades de CCR

Fecha: 2026-10-26. Base original del análisis: CCR 3.2.0 / `559fc5c0f8eb2e9677ff738ed86c703017b4bf17`. Base vigente para diseñar/implementar: CCR 3.3.0 / `d119fbc781312bd15c2eaf5e04f3768f542de7cc`.

Estado: el usuario seleccionó el enfoque B y autorizó pasar a spec y plan. Esta propuesta queda como antecedente; el [spec](../superpowers/specs/2026-10-26-priority-calibration-design.md) y el [plan](../superpowers/plans/2026-10-26-priority-calibration.md) son la referencia vigente para la siguiente etapa. La implementación y su validación se registran en [evaluación](../validation/2026-10-26-priority-calibration-evaluation.md). Se apoya en el [diagnóstico local](2026-10-26-priority-calibration-diagnosis.md).

## 1. Objetivo y alternativas

Clasificar la consecuencia con criterios repetibles, hacer visible la justificación y evitar tanto subestimar defectos serios como exagerar fallos limitados. La cantidad de P1/P0 no es un objetivo de éxito.

| Enfoque | Ventaja | Límite |
|---|---|---|
| A. Ampliar solo la frase de P0–P3 | Cambio pequeño | No asegura que la regla llegue a la verificación ni permite auditar decisiones de frontera |
| B. Rúbrica + ejemplos comparables + justificación en campos existentes | Hace operativa y auditable la clasificación, conserva compatibilidad | Requiere evaluar que el revisor aplique la guía; no basta con pruebas del parser |
| C. Puntuación numérica y campos nuevos obligatorios | Mayor estructura para explotar decisiones | Pesos no calibrados producirían precisión aparente y exigirían migración de contratos/consumidores |

El usuario eligió B. C queda como evolución opcional solo si la evaluación muestra que la prosa existente es insuficiente.

## 2. Rúbrica propuesta

La prioridad representa la urgencia técnica de corregir **la consecuencia sustentada en el escenario alcanzable**, considerando daño, exposición real y recuperación. Status establece si el defecto está demostrado; origin establece procedencia; blocking establece aceptación de este alcance. Son decisiones relacionadas, pero diferentes.

| Nivel | Condición operativa | Qué lo distingue |
|---|---|---|
| P0 — Crítico | Compromiso, interrupción o corrupción catastrófica cuya cadena e impacto inmediato al activar/ejecutar el cambio están demostrados; requiere contención inmediata | Impacto extremo sobre una frontera crítica o activos esenciales, sin barrera/recuperación efectiva demostrada. No exige incidente previo ni que afecte absolutamente a todos los usuarios |
| P1 — Alto | Fallo serio alcanzable: rompe una función principal, autoriza acciones/datos ajenos sensibles, pierde o altera datos importantes, o impide un despliegue/operación soportados | Basta un ámbito afectado material. Puede depender de una entrada válida específica, concurrencia o fallo de dependencia; no necesita caída global |
| P2 — Importante | Comportamiento/resultado incorrecto con impacto funcional concreto y acotado, sin consecuencia seria demostrada | Fallo parcial con alcance o recuperación sustentados. No es el contenedor de todo lo que no llegó a P1 |
| P3 — Menor | Consecuencia demostrablemente limitada: discrepancia documental local, diagnóstico secundario o molestia de uso sin daño funcional relevante | Hay evidencia de que el efecto es menor. No se obtiene simplemente por ser difícil, antiguo, no bloqueante o poco visible |

«Catastrófico», «serio» y «limitado» deben explicarse en términos del producto: activos afectados, función perdida, alcance alcanzable y recuperación. Ni la palabra «seguridad» implica P1, ni «corrupción» implica P0. Una pérdida irreversible de un documento puede justificar P1; una operación inevitable que destruye el almacén esencial completo al arrancar, sin barrera efectiva, puede justificar P0. No se suman puntuaciones.

### Preguntas de decisión, dentro de la verificación existente

1. ¿Qué obligación, invariante o contrato se viola y qué camino real permite llegar a ello? Confirmar o refutar el defecto antes de asignar gravedad definitiva.
2. ¿Qué daño produce, sobre qué datos/personas/proceso, y qué recuperación existe realmente? Seguir al consumidor necesario cuando cambie la clasificación.
3. ¿Está sustentada una consecuencia catastrófica e inmediata? Si sí, evaluar P0; si solo es una posibilidad añadida al defecto, mantenerla como incertidumbre.
4. ¿Está sustentado un fallo serio en la función, seguridad, integridad o despliegue? Si sí, evaluar P1 aunque el disparador sea condicional o el alcance sea un solo tenant/entidad relevante.
5. Si no, ¿hay un fallo funcional concreto acotado (P2) o únicamente una consecuencia menor demostrada (P3)? No elegir P3 por descarte ni P2 por costumbre.
6. Separar después origin y blocking. Registrar qué hecho diferencia el nivel elegido del nivel adyacente plausible; no escribir cuatro descartes rituales.

La guía debe ser breve en ejecución: una explicación por hallazgo y una comprobación agrupada de coherencia. No añade una ronda de descubrimiento, un agente por hallazgo ni benchmarks obligatorios.

## 3. Reglas que evitan degradación e inflación

| Situación | Tratamiento propuesto |
|---|---|
| Preexistente, base peor o mejora parcial | No reducen prioridad por sí mismos. La reducción requiere que el daño/exposición efectivo haya disminuido. Origin y relevancia para bloqueo se resuelven aparte |
| Riesgo aceptado o descrito por el autor | La aceptación puede cambiar el contrato o permitir una excepción de integración; no reduce automáticamente el daño residual. Si el comportamiento es deliberadamente permitido, no inventar un defecto |
| Depende de un error de red, carrera o entrada no nominal | Exigir alcanzabilidad y mecanismo. No degradar solo por ser condicional ni inventar frecuencia estadística |
| La UI nunca lo envía | Comprobar quién puede invocar la interfaz y qué contrato tiene. No fabricar consumidores, pero tampoco usar una UI como prueba de validación en el servidor |
| No hay benchmark o volumen de producción | Puede haber evidencia estática de una consecuencia seria, sin latencias inventadas. Si solo se demuestra trabajo extra acotado, no afirmar indisponibilidad |
| No se conoce una condición que determina el daño | Investigar acotadamente o declarar incertidumbre. Si el defecto básico está demostrado, clasificar su consecuencia demostrada y explicitar la mayor no comprobada; no confirmar un bypass cuya propia existencia depende del hecho desconocido |
| Existe recuperación manual | Documentar viabilidad, costo y efectos irreversibles. Un procedimiento teórico no convierte pérdida/alteración seria en P3 |
| GUID difícil de adivinar, permiso requerido o feature flag | Son precondiciones/controles que pueden cambiar exposición. Evaluar su eficacia concreta; no anulan automáticamente el daño cuando se cumple la precondición |
| Falta una prueba, estilo o preferencia de diseño | No promoverlo a defecto sin obligación/consecuencia concreta. Separar cobertura y recomendaciones; no llenar P3 con sugerencias |
| Defecto ya clasificado en una revisión anterior | Mantener su identidad y contrastar la etiqueta con la consecuencia actual. Cambiar prioridad exige hechos o corrección razonada, sin editar el resultado anterior |

P0 debe seguir siendo excepcional por sus requisitos de evidencia y daño, no por una cuota ni por exigir una caída ya consumada. Una alarma urgente sobre una hipótesis todavía no confirmada se comunica como incertidumbre material y acción requerida, no como P0 confirmado.

## 4. Justificación sin modificar schemas

Usar `scenario` para disparador y precondiciones; `impact` para consecuencia, alcance, recuperación y una frase que justifique el nivel; `evidence` para mecanismo/hechos. `blocking_reason` conserva exclusivamente el motivo de bloqueo cuando aplique.

Ejemplo sintético de `impact`:

> Un lote aceptado cambia persistentemente todas las unidades de la entidad y crea movimientos falsos. Se propone P1 por pérdida del flujo principal y alteración amplia dentro de ese ámbito; requiere otra sincronización y reconciliar el histórico. No se acredita una consecuencia catastrófica que justifique P0.

No repetir la justificación en múltiples campos ni insertar una cadena de etiquetas que el helper finja verificar. Para P2/P3 de frontera, explicar el límite efectivo; por ejemplo, «solo cambia un texto de ayuda, el valor enviado y la validación permanecen correctos».

El verificador usa `updates.priority` y, cuando haga falta, `updates.impact`, ya existentes. No enviar prioridad desde discovery. El coordinador completa y comprueba la justificación de toda conclusión confirmada, incluida la verificación en la misma sesión de focused; una reducción respecto de un resultado anterior debe explicar el hecho que cambió. Una reevaluación entre P1 y P2 no necesita otro agente por sí misma.

Una futura justificación estructurada solo se consideraría tras evaluar esta fase. Añadir hoy `severity_score`, `confidence` o `priority_reason` al schema 11 violaría su contrato de campos cerrados. No se propone hacerlo ni migrar archivos históricos. La justificación sigue en `impact`; `checks[].purpose`, los resultados de checks y las 27 decisiones de dimensiones conservan sus obligaciones de CCR 3.3.0.

## 5. Integración propuesta por archivo

| Archivo | Cambio propuesto |
|---|---|
| Nuevo `references/contracts/priority-calibration.md` | Fuente canónica compacta: rúbrica, preguntas y reglas de frontera |
| `SKILL.md`, workflow 2–3 | Cargar la guía al preparar verificación/consolidación con candidatos; preservar selección de perfil y límites de ejecución |
| `references/execution/reviewers.md` | Incluir la guía en el brief del verificador; contrastar gravedad, origen y bloqueo por separado |
| `references/execution/worker-packets.md` | Documentar el uso de los `updates` existentes y conservar discovery sin prioridad |
| `references/contracts/result-contract.md` | Exigir justificación semántica en `impact` por instrucción, sin cambiar campos/schema ni prometer validación automática de su verdad |
| `references/reporting/report-format.md` | Enlazar la definición canónica y mantener etiquetas/colores; mostrar la justificación en el impacto ya existente |
| `references/workflow/profiles.md` | Ejemplo explícito de prioridad alta preexistente cuya decisión de bloqueo requiere alcance/gate |
| Nuevo `docs/examples/priority-calibration.md` | Parejas mínimas y casos sintéticos con razón, precondición y límites |
| `docs/examples/review-scenario-disposition.md` | Enlace a la calibración; conservar la separación de confirmación/incertidumbre |
| Tests documentales/contrato pertinentes | Comprobar enlaces, reglas consistentes y compatibilidad; no afirmar que un test de strings mide el juicio del agente |
| `CHANGELOG.md` y versión declarada | Actualizarlos si se implementa y distribuye la nueva política; no anticipar una release ahora |

No se propone modificar el motor de veredictos, automatizar severidad por palabras, crear agentes adicionales, alterar la selección de scopes/perfiles ni modificar el viewer en esta fase. El JSON, renderer y entregas ya transportan `impact` y `priority`.

## 6. Evaluación antes de distribuir la mejora

### A. Casos y referencia humana

Preparar un conjunto sintético y anonimizado basado en C01–C09 del diagnóstico más casos P0 positivos y negativos. Anotar cada caso con hechos suficientes, consecuencia, prioridad de referencia o frontera aceptable, motivo de bloqueo independiente y cuestiones aún abiertas. La referencia debe validarla una persona con contexto; este análisis no constituye por sí solo una verdad de referencia sobre los productos.

Incluir al menos estas parejas:

| Pareja | Distinción esperada |
|---|---|
| Mismo daño serio introducido / preexistente | Misma prioridad; origin y bloqueo pueden cambiar |
| Riesgo serio reconocido por el autor / no mencionado | Misma prioridad si obligación y consecuencia son idénticas |
| Fallback expresamente permitido / obligación de completitud vigente | Puede cambiar si existe defecto y qué parte residual se evalúa |
| Fallo funcional local recuperable / pérdida irreversible de datos importantes | P2 frente a P1 según hechos sustentados |
| Identificador no sensible / secreto que permite acceso real | P3 o P2 frente a P1; justificar exposición y contenido |
| Migración que falla atómicamente con entrada soportada / borrado catastrófico inmediato demostrado | P1 frente a P0; la atomicidad y barreras importan |
| Trabajo extra contado / saturación seria sustentada | No inventar latencias para convertir el primero en P1 |
| Falta de test sin defecto / comportamiento concreto que viola contrato | Cobertura o recomendación frente a hallazgo; no inflar P3 |
| Hipótesis de bypass con guard desconocido / bypass demostrado | Incertidumbre frente a hallazgo confirmado, no simplemente P2 frente a P1 |

No usar información privada ni títulos históricos como sustituto de entradas de prueba completas. Los casos sin fallo y con gravedad limitada son controles esenciales contra inflación.

### B. Comparación del comportamiento del revisor

Comparar instrucciones actuales y propuestas con los mismos hechos, configuración/modelo observados y recursos. Ocultar la prioridad histórica y la de referencia al ejecutor; mezclar el orden y repetir una muestra para observar variabilidad. Mantener un subconjunto reservado que no se utilice al ajustar la rúbrica.

Medir desacuerdo por frontera, subclasificación de P0/P1, elevaciones injustificadas a P0/P1, cambios indebidos por origin/aceptación y calidad de la justificación. Separar confirmación del defecto de prioridad: no contar una hipótesis convertida en P1 como una mejora. Informar numeradores, denominadores y casos disputados; no solo un porcentaje global.

Criterios de aceptación propuestos: ningún fallo conocido en las parejas que solo cambian origin/mención del riesgo; ningún P0 positivo omitido ni P0 falso en el conjunto sintético de aceptación; reducción de errores graves sin nuevas elevaciones injustificadas en los controles; desacuerdos de frontera restantes revisados y documentados. Estos criterios aplican a esa muestra y no certifican rendimiento general. Si aparecen fallos, ajustar con el subconjunto de desarrollo y repetir sobre casos reservados adicionales, sin entrenar informalmente sobre toda la evaluación.

La distribución real de prioridades se observa como diagnóstico, nunca como meta de evaluación. No se ha realizado todavía este experimento ni existe una medición que permita prometer más precisión, ahorro de tokens o tiempo.

### C. Comprobaciones mecánicas de una futura implementación

Verificar que sigan aceptándose resultados históricos sin nuevos campos; que confirmación, prioridad y bloqueo permanezcan separados; que los paquetes conserven su versión y los `updates` existentes; que la justificación salga en `impact` sin duplicación; y que la guía llegue al coordinador y a cada modo de verificación. Ejecutar los tests pertinentes de contrato, paquetes, reporte/entrega y política de ejecución, más las comprobaciones documentales que realmente existan en ese momento.

Una prueba del renderer confirma que el texto se conserva; no que el modelo eligió el nivel correcto. Un censo de reportes confirma su distribución; no mide recall ni defectos que nunca se descubrieron.

## 7. Secuencia sugerida y decisión de enfoque

Primero acordar la rúbrica y sus ejemplos, especialmente qué distingue un efecto serio dentro de una entidad de una consecuencia catastrófica. Después preparar referencias/casos y realizar la evaluación controlada. Implementar la guía con los campos existentes y distribuirla cuando las comprobaciones y la calibración sean satisfactorias. Si la evaluación exige cambiar la rúbrica, actualizar la propuesta antes de distribuir.

La decisión de enfoque ya está tomada: B. El spec y el plan enlazados concretan su ejecución sobre CCR 3.3.0; la guía ya está implementada en este worktree y queda pendiente una publicación autorizada.
