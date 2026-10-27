# Diagnóstico de prioridades P0–P3 de CCR

Fecha: 2026-10-26, America/Mexico_City.

Base: `main`, commit `559fc5c0f8eb2e9677ff738ed86c703017b4bf17`, CCR 3.2.0. La referencia local `origin/main` coincidía con ese commit; no se consultó el servidor remoto. Worktree: `.worktrees/priority-calibration-analysis`; rama: `docs/priority-calibration-analysis`.

Estado: análisis y propuesta; no modifica la skill activa ni reclasifica archivos históricos. El análisis de casos usa sus conclusiones y evidencias retenidas; no repite la revisión del código de los productos.

Actualización de planificación: el usuario seleccionó la propuesta B y pidió spec y plan. El worktree avanzó por fast-forward a `main` / `origin/main`, `d119fbc781312bd15c2eaf5e04f3768f542de7cc`, CCR 3.3.0. El [spec vigente](../superpowers/specs/2026-10-26-priority-calibration-design.md) y su [plan](../superpowers/plans/2026-10-26-priority-calibration.md) incorporan final 11, receipt 2 y las 27 dimensiones. Los números, hashes y versiones de este diagnóstico conservan el corte histórico original; no son un censo de la nueva versión.

## 1. Conclusión

La concentración en P2/P3 existe en el archivo local, pero su frecuencia por sí sola no demuestra una clasificación incorrecta. Sí aparece una razón de degradación inadecuada: un reporte dice expresamente que bajó P1 a P2 porque la base era peor. Eso mezcla la consecuencia del defecto con su origen. También hay consecuencias persistentes o destructivas clasificadas P3 que merecen una justificación más precisa.

La mejora recomendada es una rúbrica operativa con ejemplos de frontera y una justificación breve en los campos existentes. Debe impedir tanto la degradación por motivos ajenos a la consecuencia como la elevación basada en palabras alarmantes. No se recomienda una cuota de P1/P0 ni una subida general de prioridades.

## 2. Qué se examinó y qué prueban los números

Se inspeccionaron las instrucciones, el contrato y la consolidación de CCR en la base indicada. Para el censo se leyó el archivo local resuelto mediante `CCR_ARTIFACTS_DIR` o el destino predeterminado de la skill. No se buscaron reportes fuera de esa raíz.

El [censo reproducible](priority-calibration-census.cjs) y su [resultado agregado](2026-10-26-priority-calibration-census.json) conservan el alcance y el digest del conjunto de fuentes, sin copiar nombres de repositorios privados, rutas de productos ni contenido de sus reportes.

| Selección | Cantidad | Tratamiento |
|---|---:|---|
| `review.json` encontrados, excluyendo `.publications` | 99 | Las publicaciones son copias, no revisiones nuevas |
| Candidatos en `pending` sin `cierre.json` adyacente | 3 | Excluidos del censo final |
| Runs con cierre adyacente en `closing` | 1 | Excluido del censo final |
| Runs declarados `complete` | 95 | Población descriptiva principal |
| Repositorios / alcances lógicos | 11 / 44 | Hay sucesivas revisiones de los mismos alcances |
| Runs completos con algún hallazgo confirmado | 65 | Los otros 30 no aportan hallazgos confirmados |
| Grupos con mismos campos Git de scope | 94 | Un grupo contiene dos runs; igualdad Git no prueba igualdad de todos los materiales |

Los 95 `review.json` y sus 95 `informe.md` coinciden con los hashes de su `cierre.json` adyacente. Esto comprueba esa integridad interna concreta; no certifica todo el lifecycle, la autenticidad del cierre, la exactitud de los defectos ni la aplicabilidad actual de cada revisión. No se ejecutaron helpers de recuperación/migración sobre archivos históricos.

El rango de creación va de 2026-10-19 05:54 UTC a 2026-10-26 17:28 UTC, equivalente a 2026-10-18 23:54 a 2026-10-26 11:28 en America/Mexico_City.

### Distribución de hallazgos confirmados

Son **apariciones por revisión**, no defectos únicos: un mismo problema puede reaparecer en diferentes versiones.

| Cohorte | Runs | Apariciones | P0 | P1 | P2 | P3 |
|---|---:|---:|---:|---:|---:|---:|
| Todos los runs completos | 95 | 239 | 0 | 25 (10,5 %) | 117 (49,0 %) | 97 (40,6 %) |
| Primer registro cronológico por alcance | 44 | 134 | 0 | 21 (15,7 %) | 61 (45,5 %) | 52 (38,8 %) |
| Último registro cronológico por alcance | 44 | 59 | 0 | 15 (25,4 %) | 30 (50,8 %) | 14 (23,7 %) |

Porcentajes redondeados. La selección cronológica usa `cierre.created_at`, reconoce empates y timestamps inválidos; en esta muestra no hay ninguno. Sirve para describir el histórico, no reemplaza `lookup --select latest` ni determina cuál resultado sigue vigente. Para MR/PR se agrupa repositorio, modo, target y referencia; otros modos conservan los límites Git del scope. No es deduplicación por causa ni por equivalencia semántica.

Además se excluyen de estos porcentajes 14 apariciones rechazadas y cuatro no resueltas. De las cuatro no resueltas, dos tienen P1 y dos P2 en el censo preliminar; no son fallos graves confirmados.

### Prioridad y bloqueo en los 95 runs

| Prioridad | Bloqueantes | No bloqueantes |
|---|---:|---:|
| P1 | 25 | 0 |
| P2 | 62 | 55 |
| P3 | 0 | 97 |

La asociación observada no demuestra que el motor convierta prioridad en bloqueo. El contrato los separa explícitamente. Sí conviene comprobar que el revisor no trate «no bloquea este MR» como sinónimo de «impacto menor».

### Versiones declaradas en los cierres

| CCR | Runs | P1 | P2 | P3 |
|---|---:|---:|---:|---:|
| 2.12.1 | 9 | 0 | 8 | 4 |
| 2.13.0 | 16 | 10 | 27 | 43 |
| 2.14.0 | 34 | 5 | 40 | 41 |
| 3.0.0 | 22 | 6 | 24 | 1 |
| 3.1.0 | 7 | 0 | 4 | 4 |
| 3.2.0 | 7 | 4 | 14 | 4 |

Todos los resultados leídos declaran schema 10; eso no significa que se hayan producido con una sola versión de la skill. Las diferencias entre versiones están confundidas con proyectos, cambios y re-revisiones distintos. No permiten atribuir causalmente una mejora o empeoramiento a una release, perfil o modelo.

## 3. Diagnóstico de las reglas actuales

| Fuente | Regla observada | Oportunidad |
|---|---|---|
| [Formato de reporte](../../references/reporting/report-format.md), «Presentation rules» | P0: compromiso/caída/corrupción grave inmediata demostrada; P1: fallo serio creíble; P2: defecto de corrección concreto; P3: consecuencia limitada | Es una definición breve dentro de presentación; faltan límites operativos y ejemplos comparables |
| [Contrato](../../references/contracts/result-contract.md), «Findings» | Status, prioridad, origen y bloqueo separados; evidencia estática decisiva o ejecución real | Mantener esa separación y hacer explícito qué razones no pueden rebajar prioridad |
| [Paquetes](../../references/execution/worker-packets.md) | Discovery no asigna prioridad; verificación puede suministrarla en `updates` | Hacer llegar la rúbrica al verificador y al coordinador en esa fase, sin anclar discovery a una etiqueta |
| [Revisores](../../references/execution/reviewers.md) | Se pide verificar mecanismo/severidad y conservar defectos limitados | Falta pedir una explicación de por qué la consecuencia encaja en un nivel y no en el adyacente |
| [Veredicto](../../references/workflow/profiles.md), «Verdict decision» | La consecuencia define prioridad; el alcance/requisito/política define bloqueo | Reforzar esta regla con el caso de un defecto preexistente grave que puede quedar fuera del bloqueo del MR |
| [Validador](../../scripts/ccr/contracts/findings.py), `validate_findings` | Valida enum, evidencia y requisitos estructurales de bloqueo | No evalúa semánticamente si el impacto narrado es P1 o P3; no debe fingir hacerlo con palabras clave |
| [Consolidación](../../scripts/ccr/contracts/packets.py), `merge` | Conserva las actualizaciones verificadas; no introduce una prioridad ausente | No se encontró un fallback de ejecución que asigne P2 por defecto |
| [Ejercicios](../examples/review-scenario-disposition.md) | Ilustran confirmación, incertidumbre y bloqueo | Añadir parejas de calibración P1/P2/P3 y positivos/negativos P0 |

El fixture `finding()` de `tests/test_review_contract.py` usa P2. Eso es un valor de datos de prueba, no evidencia de que el revisor o la consolidación tengan ese default. Las pruebas actuales comprueban contratos y presentación; no demuestran calibración semántica de un modelo.

## 4. Casos concretos para calibrar

Los identificadores permiten localizar las fuentes locales; sus hashes están en `selectedCaseSources` del censo. Las descripciones siguientes están generalizadas. Las alternativas son **propuestas de evaluación**, no veredictos nuevos sobre versiones de producto ni cambios a los reportes originales.

| Caso y fuente | Lo retenido | Qué debe mejorar |
|---|---|---|
| C01 — `CR-049d6d2daa954740834f/F001` | P2 no bloqueante. Lote vacío convierte todo el inventario disponible de una entidad en vendido, escribe movimientos y lo oculta de consultas. Incluye reproducciones ejecutadas | Candidato sólido para evaluar P1 por alteración persistente masiva dentro de la entidad. Verificar contrato de snapshot vacío, alcance y recuperación; que el MR admita el riesgo no reduce su consecuencia. El reporte no demuestra un P0 |
| C02 — `CR-646b7d7accdd438ca36e/F003` | P2 no bloqueante. La evidencia dice que bajó de P1 a P2 «al confirmar que la base era peor». También reconoce incertidumbre sobre un guard de autorización externo | La razón de degradación es impropia. Si se demuestra la operación entre empresas, evaluar P1 por el límite de autorización; si el guard no inspeccionado impide demostrarla, resolver esa incertidumbre. No convertir incertidumbre en P2 automáticamente |
| C03 — `CR-24f3526a12c74347bfe9/F010` | P2 no bloqueante. Un evento confirmado durante un envío queda consumido sin entregar la actualización; hay recuperación manual o por otro disparo | P2 puede ser defendible; P1 requiere demostrar una obligación crítica de entrega/consistencia o daño grave. Ser preexistente no rebaja el daño; una recuperación posible tampoco demuestra por sí sola que sea menor |
| C04 — `CR-83f0422a6be6486aa147/F013` | P3. Documento incompleto queda aprobado y la regeneración devuelve éxito. El fallback con página de error consta como aceptado en el reporte | Separar el fallback aceptado del éxito engañoso y de las obligaciones residuales. P2 es candidato por estado/resultado incorrecto; P1 necesita consecuencia seria sustentada. No anular automáticamente una aceptación ni declarar todo el fallback un defecto |
| C05 — `CR-6c6e27ae88284511a9fb/F003` | P3. Un PUT sin clave borra configuración persistida; el reporte lo llama endurecimiento porque la UI envía la clave y existe permiso de edición | Evaluar P2 si la omisión debe rechazarse según el contrato. La existencia de autenticación limita la exposición, pero no demuestra que el borrado sea correcto. No inventar un consumidor externo ni asumir que PATCH y PUT tienen la misma semántica |
| C06 — `CR-646b7d7accdd438ca36e/F023` | P3. Un error revela identificadores ajenos; se invocan GUID difíciles de adivinar y falta de validación anterior | Control de frontera: P3 puede ser adecuado para identificadores no sensibles y exposición limitada. Suponer que un GUID siempre es secreto o siempre es inofensivo sería incorrecto; separar la precondición del contenido revelado |
| C07 — `CR-dd305a6e426c46e3862f/F001` | P1. Una entrada válida del catálogo excede un varchar de la siembra y aborta atómicamente la migración | Buen positivo P1: evidencia estática puede demostrar imposibilidad de despliegue en un escenario soportado. La atomicidad evita corrupción parcial, pero no elimina el fallo serio |
| C08 — `CR-d857fbf306f947098456/F018` | P1. Una escritura de resultado ambiguo dispara una compensación que elimina el original persistido | Buen positivo P1: el fallo de red es condicional y aun así hay pérdida seria demostrable. No se necesita fingir que ya ocurrió un incidente de producción |
| C09 — `CR-2d2ef29e245840f683af/F001` | P1. Una operación aceptada reasigna evidencia privada a otro participante y no se deshace por el flujo normal | Buen positivo P1 fuera de infraestructura: la gravedad se evalúa respecto de la función principal del producto, no solo por caída global o datos financieros |

C04 contiene aceptación de negocio y C02 incertidumbre externa; ambos son ejemplos de por qué no basta leer el título para subir prioridades. La selección de casos fue dirigida por consecuencias llamativas, no aleatoria: sirve para diseñar la rúbrica, no para estimar la tasa de clasificación incorrecta de los 239 hallazgos.

## 5. Causas sustentadas e hipótesis

**Sustentado:** definiciones poco operativas; ausencia de justificación dedicada a la frontera; al menos una degradación explícita por origen; mezcla histórica de versiones y revisiones que distorsiona el porcentaje global.

**Hipótesis que debe probar la evaluación:** anclaje a clasificaciones anteriores; interpretar un fallback aceptado como impacto menor; tratar un fallo condicionado o un consumidor distinto de la UI como simple endurecimiento; preferir P2 cuando falta contexto. No se ha medido la contribución de cada mecanismo ni se ha probado un sesgo de un modelo específico.

La ausencia de P0 puede ser razonable en esta población. No hay base para afirmar que deba contener alguno. La rúbrica debe permitir reconocer un P0 antes del despliegue cuando la cadena catastrófica sea concluyente; no debe exigir observar primero el incidente ni elevar una corrupción local a P0 por su nombre.

## 6. Propuesta y validación del análisis

La [propuesta de calibración](2026-10-26-priority-calibration-proposal.md) concreta niveles, reglas, ejemplos de aceptación y archivos a cambiar en una futura implementación. Recomendación del agente, pendiente de decisión del usuario.

Se reprodujo el censo sin diferencias respecto del JSON guardado; digest de fuentes: `e87ec97addf6bec30fe3180480c5f5f2edfc0d8dc65bc1d9e732f2e036b00b99`. Se verificaron la suma por prioridades/versiones, las ocho fuentes de los nueve casos, los 95 pares de hashes de reporte/resultado, la sintaxis del script con `node --check`, los 12 enlaces locales y el whitespace/nueva línea final de los cuatro archivos agregados. `git diff --check` no informó errores; los archivos nuevos también se comprobaron directamente porque todavía están sin seguimiento. El checkout principal permaneció limpio en `main`.

No se ejecutó la suite de producto: este trabajo agrega análisis y soporte de lectura, no cambia el comportamiento de CCR. No se midieron tokens, tiempo de reviews ni capacidad de descubrir/reclasificar defectos.
