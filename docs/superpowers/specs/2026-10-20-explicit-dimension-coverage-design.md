# Dimensiones, propósito de checks y trazabilidad de evidencias

## Estado, base y alcance

Actualizado el 26 de octubre de 2026 a petición del usuario. Base vigente observada: CCR **3.2.0**, `main` en `559fc5c0f8eb2e9677ff738ed86c703017b4bf17`. Se integró en este worktree mediante el merge `bc7d5b6`, conservando los dos commits documentales previos. El nombre del archivo se conserva para mantener sus enlaces; sustituye la propuesta basada en 2.13.0.

Se solicita análisis y planificación, no implementación. El alcance reúne la cobertura explícita de las 27 dimensiones previamente propuesta y los nuevos requisitos sobre propósito de checks, presentación de evidencias y cobertura privada/pública. El [análisis del modelo vigente](../../analysis/2026-10-26-check-evidence-coverage-analysis.md) describe las fuentes inspeccionadas; el [plan](../plans/2026-10-20-explicit-dimension-coverage.md) utiliza módulos e imports de 3.2.0.

**Regla principal:** cada check comunica qué verifica; cada evidencia conserva su origen; el hallazgo explica el problema y su impacto sin repetir innecesariamente los resultados de los checks.

## 1. Objetivos y alternativas

El informe debe permitir seguir requisito o hipótesis → propósito del check → ejecución/resultado → evidencia del hallazgo → problema/impacto. La cobertura conserva cada flujo como elemento independiente y muestra el estado de cada dimensión.

| Alternativa | Ventaja | Motivo de la decisión |
|---|---|---|
| Exigir todo mediante plantillas de prosa | Menor cambio estructural | No detecta dimensiones ausentes ni propósito omitido |
| Añadir propósito y dimensiones opcionales a schema 10 | Incorporación gradual | Desvirtúa un contrato estricto y permite nuevas omisiones silenciosas |
| Final 11 obligatorio para productores nuevos, recibo 2 y proyecciones compartidas | Valida completitud, vincula propósito a captura y conserva contratos antiguos | Propuesta elegida para revisión; no se atribuye al usuario una aprobación de esta solución concreta |

Se mantiene el modelo de evidencia existente `{kind, details, check_id}`; no se crea un registro paralelo de evidencias. Agrupar para presentar no modifica, elimina ni reinterpreta los elementos JSON.

## 2. Restricciones globales

- Python 3.10+ y biblioteca estándar; sin dependencias nuevas de producto.
- Usar paquetes scripts/ccr y CLI python <skill>/scripts <área>; no restaurar scripts/review_*.py ni imports legacy.
- Nuevos finales: schema 11 con checks.purpose y las 27 dimensiones; schemas 1–10 conservan sus contratos.
- Mantener archive 8/layout 2, trace 1 y packet version 1; nuevos recibos locales usan schema 2 y se siguen leyendo recibos 1.
- No modificar archivos reales de revisiones, informes retenidos ni comentarios remotos durante esta preparación.
- Conservar criterios, prioridades, hallazgos, perfiles, veredictos, aislamiento, preflight y reglas de reutilización de CCR 3.2.0.
- La matriz ABCDE y los IDs de dimensiones siguen siendo privados; la cobertura pública describe flujos de producto.
- No modificar el visor, publicar, hacer merge a main, asignar versión de release ni ejecutar la implementación.

## 3. Dimensiones explícitas

El catálogo queda ligado a final 11 y reside en `ccr/contracts/dimensions.py`, módulo puro sin IO. Nombres operativos en inglés; etiquetas españolas en los renderers actuales. No se reciclan IDs ni se modifica retrospectivamente el catálogo de este schema.

| Área | IDs y significado |
|---|---|
| A | A01 Boundaries and ownership; A02 Dependency direction; A03 Lifecycle and state; A04 Failure isolation; A05 Test seams |
| B | B01 Preconditions and postconditions; B02 Validation and branching; B03 Invariants and edge cases; B04 Fallback behavior; B05 User-visible outcome |
| C | C01 API/event shape; C02 Producer-consumer agreement; C03 Serialization; C04 Compatibility/versioning; C05 Ordering and rollout |
| D | D01 Identity and ownership; D02 Query/filter semantics; D03 Transactions; D04 Constraints and migrations; D05 Consistency and recovery |
| E | E01 Authentication and authorization; E02 Tenant and resource isolation; E03 Trust boundaries and validation; E04 Error disclosure; E05 Concurrency and idempotency; E06 Lifecycle and cleanup; E07 Performance |

Cada fila de `coverage.areas` incorpora `dimensions`: exactamente cinco elementos para A–D y siete para E. Cada dimensión tiene exactamente `{id, status, details, material, finding_ids}`. Se rechazan ausencias, IDs repetidos/desconocidos/ajenos al área, tipos inválidos, campos extra y detalles vacíos.

- `covered`: mecanismo inspeccionado con fuente o check observado; no significa ausencia de defectos.
- `partial`: parte inspeccionada y pregunta pendiente concreta.
- `not_evaluated`: aplicable, pero sin inspección; indicar causa y materialidad.
- `not_applicable`: exclusión justificada por el alcance; nunca por falta de tiempo o de respuesta.

El estado del área es N/A si todas son N/A; cubierta si todas las aplicables están cubiertas; no evaluada si todas las aplicables están no evaluadas; parcial en cualquier otra combinación. Su materialidad es el OR de sus dimensiones y sus hallazgos son exactamente la unión de sus IDs. Solo una dimensión parcial/no evaluada puede ser material. Una N/A no tiene hallazgos ni materialidad. El validador rechaza resúmenes contradictorios; no los corrige ni fabrica evidencia.

El catálogo completo exige 27 decisiones, no 27 ejecuciones. Se inspeccionan solo mecanismos afectados. Briefs, flows y limitaciones de packet 1 nombran los IDs aplicables en sus textos existentes. Respuesta ausente implica `not_evaluated`, no cobertura. La comprobación semántica usa la verificación ya exigida por el perfil, sin agente adicional obligatorio.

En re-review se clasifica el alcance actual; un área histórica cubierta no prueba sus dimensiones. `canonicalize_ids` remapea también `dimensions[].finding_ids` de forma atómica. Se mantiene una sola causa/hallazgo aunque varias dimensiones lo referencien.

## 4. Propósito de checks: declaración y captura

En final 11, cada check incorpora `purpose` obligatorio: string no vacío tras strip, máximo 4000 caracteres, sin caracteres de control U+0000–U+001F. No se normaliza ni se deriva del comando. Las mismas reglas se comparten mediante `ccr/contracts/checks.py`; no confundir este propósito con `reference-index.inputs[].purpose`, que clasifica materiales.

Ejemplo: «Verificar que dos reclamaciones simultáneas no ejecutan dos veces el mismo job». Es anterior al resultado; no dice «confirmar el bug», no presupone un fallo ni repite impacto o corrección del hallazgo.

| Ejecución | Captura del propósito |
|---|---|
| Local nueva | Declararlo en el request de `checks run`, antes de validar/ejecutar el proceso; copiarlo al recibo 2 y al ledger final |
| Static/external/blocked/not_run | Declararlo en la planificación/observación correspondiente; no crear recibo local ni executor ficticio |
| Reutilizada | Conservar propósito histórico si existe y es aplicable; si faltaba, explicar su uso en esta revisión desde la evidencia disponible, sin atribuir esa declaración al instante de ejecución anterior |

`capture_check` añade argumento keyword-only obligatorio `purpose: str`; `_read_request` exige el campo. Los requests nuevos sin propósito fallan antes de crear attempt o iniciar subprocess. Es un cambio explícito del productor; no se añade una ruta silenciosa que siga capturando checks nuevos sin propósito.

Recibo 2 conserva exactamente los campos de recibo 1 y añade `purpose`. Conserva argv literal, command canónico, cwd, executor, revisión, timestamps, exit code y hashes/bytes de stdout/stderr. El valor de propósito del ledger y del recibo 2 debe coincidir exactamente. Una ejecución nueva de final 11 con `execution.kind=local` y `reused=false` que referencia un recibo necesita versión 2; un recibo 1 no acredita un propósito capturado. Finales antiguos con recibo 1 mantienen su validación original. No se obliga a capturar un recibo donde antes era opcional.

La reutilización histórica es distinta: conserva `execution.kind=reused`, versión y referencia duradera al resultado fuente según las reglas actuales, con el recibo 1 validado en su archivo original. No se obliga a ejecutar de nuevo ni se cambia el executor original para hacerla pasar por captura nueva. El propósito añadido explica su uso actual; no afirma haber sido declarado antes de aquella ejecución. No se introduce un bypass de recibos para checks marcados reused ni se hace pasar una referencia flat local a un recibo por un linaje histórico verificado.

El coordinador copia el campo al check JSON sin volver a redactarlo a partir del resultado. Reintentos conservan el propósito cuando no cambia el objetivo y mantienen attempts/IDs separados según las reglas vigentes; un objetivo distinto se declara explícitamente. No se alteran códigos de salida ni clasificación product/fixture/environment.

## 5. Ledger, packets y validación de extremo a extremo

Packet version 1 sigue devolviendo check_ids y evidencias, no checks completos nuevos. Sin embargo, `ccr/contracts/packets.py:merge` hoy valida el ledger neutral como schema 2: se adapta para aceptar explícitamente un contexto con `check_schema_version: 11`, validar shape/propósito/IDs del ledger mediante una proyección discovery 11 y comprobar la forma de execution. Los bindings de fuentes, linaje y executor conservan su gate completo en preflight/retención; el merge no inventa un envelope final ni reduce checks a campos legacy. Los check IDs del ledger nuevo son canónicos y se suministran como conocidos a packets.

Contextos sin `check_schema_version` mantienen el comportamiento 2 anterior. El selector solo admite 2 u 11; un ledger 11 incompleto se rechaza, no se rebaja. El bundle conserva los checks y su propósito, además de los check_ids enlazados en evidencias; no altera decisiones ni prioridad. El envelope de packet no cambia.

Extender los guards de schema 10 a 11 en review, findings/checks, identifiers, profiles, execution, provenance, receipts, semantic references, preflight y consumidores de archivo/reporting. No basta con aceptar el número 11 en el validador raíz. Se mantienen selección de fuentes iniciales, aliases planos, hashes, dispatch-identity, historia de perfiles, executors, material inputs y captura Git sin lazy fetch.

Preflight retain rechaza dimensiones o propósito ausentes antes de escribir resultados. Si solo falla la construcción de un candidato y los inputs siguen vigentes, se reconstruye en el mismo run, sin repetir discovery/verificación. Archive 8 admite 10/11 en sus gates; el flujo nuevo fija `--expected-schema 11`. Recovery reproduce el schema/bytes reservados de la operación exacta, sin insertar campos retrospectivamente.

La admisión y reutilización efectiva de 3.2.0 conserva comparación de cambios/materiales/contexto y prueba de cobertura ordinaria heredada. No se confunde ausencia histórica de dimensiones/propósito con un nuevo defecto de código, ni se usa una mejora de presentación para cambiar un veredicto anterior. Mostrar un resultado histórico y ejecutar un nuevo review mantienen sus reglas vigentes.

## 6. Evidencias como sublistas con origen

La presentación privada y pública usa un helper puro compartido `ccr/reporting/evidence.py`, sin IO ni decisiones de veredicto. Agrupa por `check_id` cuando existe, manteniendo orden de primera aparición.

- Generar el enlace **[C001](#C001)** una vez por grupo dentro de cada hallazgo.
- Si un detalle es exactamente igual al resultado registrado en `checks[C001].evidence`, usar «Resultado en Validación» y enlazar, sin copiarlo.
- Conservar detalles distintos que aporten observaciones específicas al hallazgo; eliminar únicamente duplicados exactos dentro del mismo origen.
- Checks diferentes con el mismo texto siguen siendo orígenes distintos.
- Una evidencia estática sin check permanece en su propia fila con **Inspección estática** y su detalle/fuente observada. Si un resultado antiguo no registró una fuente concreta, indicarlo sin inventar una ruta ni asignarle un check. Eliminar solo duplicados exactos; no agrupar dos inspecciones distintas porque suenen parecidas.
- No inferir check_id mediante búsquedas en prosa, no elegir un log arbitrario y no eliminar evidencia del JSON.

Formato objetivo; el hallazgo conserva Escenario/Impacto/Corrección por separado:

```markdown
- **Evidencia:**
  - **[C001](#C001)** — Resultado en Validación.
    - El caso con dos reclamaciones alcanza el mismo owner antes del commit.
  - **Inspección estática** — src/jobs.py:claim permite observar el mismo estado pendiente.

### Validación

- **C001** — Falló · versión head-456
  - **Propósito:** Verificar que la reclamación concurrente conserve una sola ejecución.
  - **Resultado:** Dos reclamaciones completaron el mismo efecto.
```

Los markers/IDs/enlaces generados llevan negrita. Referencias verificadas disponibles en el check usan etiquetas de origen en negrita y links seguros; rutas o texto no confiable se escapan con los helpers existentes. La agrupación se decide contra el ledger original antes de seleccionar texto público; jamás se vuelve a publicar un resultado privado porque su resumen público tenga otra redacción.

El propósito y el resultado de cada check se imprimen una vez en Validación. Cada hallazgo mantiene el enlace necesario para entender su evidencia, más el delta específico si existe. No se usa similitud textual para eliminar escenario o impacto.

## 7. Cobertura y proyecciones por audiencia

El informe completo muestra `coverage.flows` como sublista Markdown, en su orden original, sin joins ni separación por punto y coma. La lista vacía se expresa como «Sin flujos de cobertura registrados», sin inventar cobertura. Los elementos iguales en JSON se conservan como elementos independientes: renderizar no altera la cardinalidad del registro.

```markdown
- **Cobertura:**
  - Creación de jobs y asignación inicial.
  - Reintentos tras una respuesta parcial.
```

Después se conserva la matriz ABCDE y se añade «Dimensiones evaluadas», 27 filas explícitas con nombre, estado, evidencia/motivo y hallazgos. Full mantiene también todas las filas en JSON; brief resume IDs por estado, explica pendientes/N/A y conserva propósito de checks y resultados significativos sin duplicar toda la evidencia cubierta.

Los comentarios muestran también la lista de cobertura, con descripciones de producto seguras, y mantienen oculta la matriz/taxonomía de dimensiones. Para no publicar textos privados de flows se añade `coverage_publication_context`, ligado a `publication_digest(record)`:

```json
{
  "source_sha256": "<digest del registro exacto>",
  "flows": [{"index": 0, "summary": "Creación de jobs y asignación inicial."}]
}
```

Cuando hay flows públicos, el contexto incluye cada índice original exactamente una vez; rechaza duplicados, omisiones, índices fuera de rango, summaries vacíos o digest ajeno. Puede sustituir detalles internos por una descripción de producto equivalente; no elimina flujos ni añade cobertura. La lista vacía no necesita contexto. Se requiere también al renderizar comentarios nuevos de resultados antiguos con flows: es clasificación editorial del dato existente, no una nueva revisión ni migración.

`public_checks` incorpora propósito y lo muestra cuando lista ese check. En final 11, la clasificación editorial de checks es obligatoria si existen checks, ligada al mismo digest y con filas exactas que añaden `purpose` a los campos actuales. Su propósito público es no vacío y expresa el mismo objetivo; no puede reemplazarlo por una afirmación de fallo. Los contextos legacy conservan su shape anterior y muestran «Propósito no registrado (resultado anterior)»; no se infiere desde command ni desde un hallazgo.

`checks[].purpose` se clasifica como PROSE en la proyección portátil; IDs/enums y referencias tipadas no se reescriben para facilitar una entrega. Las nuevas dimensiones tienen política STRUCTURAL/PROSE explícita. Las políticas nuevas de comentarios no se usan para mutar ni sobrescribir resultados del archivo.

## 8. Comentarios publicados y compatibilidad

La publicación usa la ruta canónica `reporting.comment → render`, pasando los contextos de limitaciones, checks y cobertura. No editar a mano el Markdown tras prepararlo. `comment prepare` y el CLI contract render-comment incorporan `--coverage-publication-context`.

Los drafts nuevos usan schema 2: todos los campos actuales de draft 1, más `coverage_publication_context`. Hash de fuente y hash del cuerpo siguen ligados al registro y Markdown exactos. Verify recalcula con esos contextos y rechaza fuente, propósito público, cobertura o cuerpo alterados; CRLF solo se tolera como transporte remoto, como hoy.

Los drafts 1 previos no se regeneran ni sobrescriben. Verify devuelve diagnóstico explícito `stale_draft` y se prepara un draft 2 nuevo desde el mismo resultado retenido y sus contextos, sin otro review. Es una limitación de compatibilidad de drafts pendientes, no invalida review.json ni los comentarios ya publicados. No hay publicaciones automáticas ni ediciones remotas en este trabajo.

| Fuente | Lectura y presentación nuevas |
|---|---|
| Final 1–10 sin purpose/dimensiones | Válido por su contrato; propósito desconocido explícito; no inventar dimensiones |
| Final 11 | Purpose y dimensiones obligatorios; conserva todos los gates de 10 |
| Recibo 1 | Validación legacy; no demuestra captura de purpose para un local nuevo 11 |
| Recibo 2 | Purpose ligado exactamente al check, más todos los bindings anteriores |
| Archive 8/layout 2 | Mantiene forma, ownership y archivos históricos; admite finales 10/11 |
| Draft 1 | Preservar; diagnóstico stale_draft, preparar otro draft 2 si se requiere publicar/verificar con el renderer nuevo |
| Draft 2 | Verificación exacta con los tres contextos editoriales |

Cambiar la presentación nueva puede modificar las expectativas de snapshots Markdown de pruebas, nunca los bytes de informes cerrados. Actualizar solo expectativas afectadas por la decisión, no regrabar inventarios completos para esconder regresiones. El visor externo y herramientas antiguas pueden rechazar final 11/recibo 2/draft 2; no se declara su compatibilidad.

## 9. Aceptación y alcance final

| ID | Resultado verificable |
|---|---|
| AC1 | Las 27 dimensiones están presentes, clasificadas y agregadas sin contradicción |
| AC2 | Check nuevo con purpose ausente/vacío/inválido falla antes de ejecución y retención |
| AC3 | Request, recibo 2, ledger, merge y final conservan exactamente el propósito |
| AC4 | Recibo 1, resultados 1–10 y recovery mantienen semántica y bytes originales |
| AC5 | Evidencias forman sublistas con origen en negrita; conservan estáticas y observaciones distintas |
| AC6 | Un resultado compartido se enlaza; no se repite entre check y hallazgo ni se fusionan checks distintos |
| AC7 | Cobertura privada/pública conserva cada elemento, con orden y cardinalidad verificados |
| AC8 | Full, brief, handoff y comentario mantienen propósito, resultado, relaciones y política de privacidad correspondientes |
| AC9 | Draft 2 y CLI verifican cuerpo/contextos exactos; draft 1 tiene tratamiento explícito |
| AC10 | Preflight, dispatch, materiales, límites 64/64 MiB, reutilización y veredictos de 3.2.0 no se debilitan |

La validación estructural no certifica la verdad de una evidencia ni su equivalencia editorial; se contrasta con fuentes en la verificación ya prevista por el perfil. Pruebas y escenarios usan fixtures públicas sintéticas. La entrega actual modifica solo análisis/spec/plan y su registro de preparación. Su revisión y la elección de ejecución preceden a cualquier implementación.
