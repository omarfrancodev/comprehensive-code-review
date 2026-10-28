# Topología de sesiones, checks publicables y modelos en CCR

Estado: decisiones funcionales aprobadas el 2026-10-21; correcciones documentales del 2026-10-22 y adaptación a main del 2026-10-26. No se ha implementado esta topología.

Ampliación solicitada el 2026-10-28: conservar comandos/recursos acreditados del proyecto en comentarios y delivery con ocultación selectiva de datos sensibles, y registrar/presentar la procedencia del modelo por participante. Las decisiones de topología siguen vigentes; los formatos auxiliares propuestos más abajo forman parte del diseño pendiente de implementación.

Base vigente: `main`/`origin/main`, commit `1d2626048a882cab510a59fd10fdbca7cf16dda5` (CCR 3.4.0), integrado en este worktree mediante `67633cf`. Worktree: `.worktrees/profile-session-topology`; rama: `docs/profile-session-topology`. Los archivos conservan su fecha y nombre originales para mantener los enlaces.

## 1. Objetivo y cambios de la base

Hacer explícita y verificable la topología de descubrimiento y verificación de los perfiles, con deep en dos descubridores y extended en tres a cinco y uno o dos lotes finales particionados. Conservar la historia y evitar que un segundo lote se convierta en otro barrido completo del alcance.

La ampliación evita que propósito y resultado pierdan contexto al ocultarse el comando completo: los lectores deben reconocer qué test, script o recurso del proyecto se verificó. Las reproducciones, tests y scripts creados o alterados por CCR para su comprobación se explican sin presentarlos como recursos originales del proyecto. Además, las revisiones nuevas deben dejar una observación de modelo o una ausencia explícita para coordinación y cada reviewer despachado, sin deducir el modelo del harness.

La base original era `fd38df8`/CCR 2.14.0. Desde entonces:

- CCR 3.0.0 retiró las fachadas `scripts/review_*.py`. La entrada vigente es `python <skill>/scripts <area> ...`; los propietarios están bajo `scripts/ccr/`.
- CCR 3.1.0 vinculó la frescura a la identidad completa y al despacho original; una anotación tardía conserva la secuencia original.
- CCR 3.2.0 añadió admisión por cambios efectivos y contexto de reutilización; esas reglas no forman parte de este cambio.
- CCR 3.3.0 publicó final schema 11 con propósito de checks y las 27 dimensiones explícitas. Los recibos nuevos y drafts públicos usan schema 2, independientemente de la versión del resultado.
- CCR 3.4.0 añadió calibración de prioridades como instrucción editorial, sin nuevos campos.

Por ello, el número 11 propuesto inicialmente ya está ocupado por un contrato publicado. La topología usará **final schema 12**, con la misma forma de campos de **schema 11 actual**, preservando los esquemas 1–11. No puede reutilizarse 11 ni partir del fixture 10 omitiendo sus campos nuevos.

## 2. Comportamiento actual verificado en la base vigente

| Perfil | Descubrimiento actual | Verificación actual |
|---|---|---|
| focused | 1, no independiente | 1, mismo contexto que descubrimiento |
| standard | 1 | 0 o 1; fresca cuando hay candidatos sustantivos o dudas materiales |
| deep | 2–3 independientes | Un verificador final independiente |
| extended | Automático 4–5 / explícito 2–5 independientes | Un verificador final independiente |

La fuente es `scripts/ccr/contracts/execution.py`: `validate_execution` conserva límites y agregado por última fila para 10/11; `validate_execution_sources` exige un único candidato final; `validate_profile_execution` conserva obligaciones adquiridas. Esta última función ahora pertenece al mismo módulo, **no** a `ccr.workflow.profiles`.

La historia y la normalización de selecciones pertenecen a `scripts/ccr/workflow/profiles.py`. Independencia conserva su significado: contexto de reviewer separado; `context_id` neutral compartido no es identidad de reviewer. Reutilizar contexto o provider observado no acredita independencia.

La frescura actual usa `dispatch.project_dispatches` y `original_dispatch`: el primer despacho que coincide en nombre **y provider_id** debe ser anterior a su finalización y posterior a `last_discovery`. No basta encontrar un arranque posterior. Véanse [reviewers.md](../../../references/execution/reviewers.md) y [la implementación de ejecución](../../../scripts/ccr/contracts/execution.py).

## 3. Decisiones aprobadas y adaptación de versión

| # | Decisión que se conserva |
|---|---|
| 1 | Techo de descubrimiento de extended: **5** |
| 2 | Piso de extended: **3**, automático y explícito |
| 3 | Dos lotes de extended particionados en **candidatos** e **invariantes asignadas** |
| 4 | Ambos lotes finales después de todo el descubrimiento; pueden ejecutarse en paralelo |
| 5 | Una tercera perspectiva necesaria que no cabe en deep exige **extended** |
| 6 | `coverage.verification` permanece **escalar** |
| 7 | Agregación con tres estados sobre **todas las verificaciones activas**, incluidas históricas |
| 8 | Convención de IDs de partición, sin nuevos campos en `coverage.execution` |
| 9 | Publicar las reglas en un **esquema nuevo** y congelar los anteriores |

La decisión 9 mencionaba originalmente 11. Su intención de compatibilidad requiere ahora **12**: schema 11 ya tiene usuarios y conserva la topología anterior. Las decisiones 1–8 no cambian; la renumeración no amplía el alcance funcional.

## 4. Topología objetivo de final schema 12

| Perfil | Descubrimiento | Lotes finales | Independencia final |
|---|---|---|---|
| focused | 1 | 1 | false; mismo contexto que descubrimiento |
| standard | 1 | 0–1 | true cuando hay sustancia material; conserva excepciones de cierre limpio/descripción mecánica |
| deep | Exactamente 2 independientes | 1 | true |
| extended | 3–5 independientes, automático y explícito | 1–2 | true en todos los lotes |

Los conteos de verificación son de obligaciones **finales**, no de todas las filas conservadas. Los gates de proyecto siguen fuera de los límites ordinarios y conservan su política.

Un deep automático puede escalar a extended reutilizando descubrimiento válido. Un deep explícito solicita cambio autorizado o declara el hueco material; no escala silenciosamente. No se borran ni se superseden asignaciones iniciadas/completadas para satisfacer los conteos.

## 5. Partición y orden

Un solo lote agrupado puede cubrir candidatos e invariantes. Dos lotes requieren una separación justificada:

- `V-candidatos`: candidatos sustantivos y preguntas materiales agrupados por causa.
- `V-invariantes`: invariantes nombradas en los briefs, incluidas las que no produjeron candidatos.

Los IDs son una convención de briefs/plan, no una gramática nueva impuesta por el validador. No prueban por sí solos el contenido del trabajo. Ambos lotes requieren identidades independientes distintas; no se autoriza un segundo barrido completo.

`last_discovery` conserva la definición actual: máximo de secuencias de finalización observadas del descubrimiento activo, con el default actual si no existen. Es la única frontera temporal de frescura; no se añaden campos ni ejes temporales.

Para un lote final independiente se conserva el vínculo al **despacho original** con identidad completa, incluida la proyección de anotaciones `dispatch-identity`. Una anotación tardía no mueve el arranque. Un segundo arranque no reemplaza uno original temprano; un provider distinto no sustituye la identidad del resultado.

## 6. Historia, forma y cumplimiento

### 6.1 Clasificación histórica/final

Tras validar historia, bindings, fuentes y milestones:

- **Histórica:** la fila activa tiene binding validado a un perfil anterior menor que `strongest`, o un resultado con finalización válida cuya última secuencia sea `<= last_discovery`.
- **Final:** cualquier otra fila activa de verificación, incluidas las del perfil exigible sin resultado. La falta de resultado no acredita historia. Un resultado presente sin evidencia válida sigue siendo error de procedencia en ambos conjuntos.

`strongest` se deriva de las obligaciones activas con las reglas actuales. La condición de binding preserva intentos del perfil anterior incluso si el nuevo descubrimiento resulta impedido y no mueve la frontera. Conservan sus resultados o sus fallbacks exigidos y siguen afectando al agregado.

Deep puede conservar una histórica y un lote final. Extended puede conservar históricas y uno/dos finales. Se conservan IDs, selección, referencias e identidades originales; no se cambia el rol para esconder trabajo. Esta clasificación no autoriza a planear los dos lotes finales entre olas.

### 6.2 Responsabilidad de cada validador

`validate_execution` comprueba forma, descubrimiento, obligaciones básicas, resultados, independencia y agregado. Sin traza **no impone un máximo global** de verificaciones activas, porque puede haber historia conservada.

`validate_execution_sources` clasifica historia/finales y aplica los mínimos/máximos finales de §4 en ambos estados. Standard conserva cero lotes cuando su excepción lo permite. Los demás necesitan al menos una fila final requerida: un impedimento se representa con la fila y su fallback, no eliminando la obligación.

Cada fila final se vincula al perfil de mayor obligación activa y planifica la independencia exigida. Los eventos de arranque y finalización que corresponden a la identidad del lote deben ser posteriores a `last_discovery`, y el arranque debe preceder a su finalización. Un arranque de otro provider no acredita frescura ni sustituye el despacho original de la identidad correcta. Para independencia se usa el despacho original proyectado de §5, no una búsqueda nueva de cualquier start conveniente.

Un fallback documentado de esa asignación al coordinador puede acreditar su arranque mediante el milestone observado de inicio de etapa, sin inventar un despacho independiente. Si existe un despacho original coincidente, su orden no se reemplaza por otro start posterior. Un fallback de otra asignación o el estado global degraded no habilitan esta excepción.

- `fulfilled`: todos los lotes finales completados con independencia, orden y procedencia válidos.
- `degraded`: permite ausencia o pérdida de independencia con fallback y fuente/milestone observados; **no exime del orden** de los eventos finales presentes.
- Una verificación completada antes de la frontera permanece histórica; un lote final que cruza la frontera desde un arranque temprano se rechaza en ambos estados.

Retención, preflight y validación durable conservan los gates de fuentes. Un registro estructuralmente válido sin fuentes no acredita por sí solo cardinalidad final ni frescura.

### 6.3 Agregado único de todas las filas activas

Sin cambiar el enum, aplicar en este orden:

1. `unavailable` si falta cualquier resultado de verificación requerido.
2. `same_session` si todos están presentes y alguno es en la misma sesión o no satisface independencia prevista, con el fallback que corresponda.
3. `independent` si todos completaron con independencia observada.

Incluye historia y finales. Un fallback histórico no se oculta por completar después una verificación independiente. Sin filas, standard limpio puede usar `skipped`; las verificaciones obligatorias deben conservar su fila aunque no produzcan resultado.

| Caso | Agregado / aceptación |
|---|---|
| Dos lotes independientes y orden válido | independent; fulfilled si se cumplen las demás obligaciones |
| Uno independiente y otro del coordinador, ambos presentes | same_session; degraded con fallback y evidencia |
| Falta uno o ambos | unavailable; degraded con fallbacks por obligaciones incumplidas |
| Coordinador más ausencia | unavailable; la ausencia domina |
| Lote final con despacho original temprano | Rechazo, aunque otro start o anotación sea tardío, en ambos estados |
| Histórica con fallback más final independiente | El agregado sigue mostrando el fallback histórico |

La agregación tiene una sola implementación en el validador sin traza, reutilizada al entrar en fuentes. No se recalcula desde `final_candidates[0]`. Los controles temporales son adicionales y no se sustituyen por el escalar.

## 7. Versiones, adopción y compatibilidad

| Contrato | Tratamiento |
|---|---|
| Final 1–10 | Congelados; validación y proyección propias |
| Final 11 publicado en CCR 3.3/3.4 | Congelado: propósito, 27 dimensiones y topología previa |
| Final 12 | Misma forma de 11; nuevas reglas de topología y agregado |
| Archive 8/layout 2 | Sin cambio de versión; gates aceptarán finales 10/11/12 |
| Trace 1, packet 1, reference index 1 | Sin cambio |
| Receipt de captura de comandos 2 | Sin cambio; conserva propósito y ejecución originales |
| Draft público 2 / nuevo 3 | 2 conserva su contrato publicado; 3 incorpora la proyección verificable de comandos/recursos de §10 |
| Receipt de delivery 1 / nuevo 2 | 1 conserva su contrato; 2 identifica política/digests de la nueva proyección y resumen de modelos |
| model-usage sidecar 1 | Se reutiliza sin nuevos campos; captura y presentación dejan de depender de un paso opcional no visible |

Schema 12 **hereda** `checks[].purpose`, las 27 dimensiones por área, referencias semánticas, procedencia de checks, recibos y publicación de 11. Omitir propósito o una dimensión debe rechazarse. La calibración de prioridades de 3.4.0, admisión por cambios efectivos y reutilización conservan su comportamiento.

Extender cada reconocimiento por su significado:

- Forma/historia/procedencia: incluir 12 junto a los esquemas compatibles existentes.
- Requisitos introducidos por 11: aplicar a `(11, 12)`; no convertirlos en `== 12` y desactivar 11.
- Topología: **sólo 12**; 10/11 conservan tablas, agregado y regla de único verificador final actuales.
- Versión desconocida: 13 y superiores siguen rechazándose.
- Merge de packets: admitir `check_schema_version=12` junto a 2/11 y preservar propósito, sin cambiar packet 1 ni su default.
- Retención: `--expected-schema 12` para nuevas revisiones; la igualdad exacta sigue vigente, por lo que expected 11 no admite un candidato 12.

Los fixtures `record8`, `recovery_fixtures.record10` y `traceability_fixtures.record11` no se modifican. El builder de 12 deriva de una copia del fixture 11 actual, no del 10. Tampoco se cambia a ciegas `publication_contexts`, que hoy trata expresamente 11: los casos nuevos deben producir la clasificación de propósito para 12.

Las instrucciones operativas de SKILL, contratos, archive, packets, reporte, publicación y uso deben acordar finales nuevos 12. Las descripciones históricas conservan sus versiones. Mantener los cambios incorporados en main, incluidos propósito, dimensiones y prioridad editorial. Versión de skill **propuesta 3.5.0**, a revalidar con main antes de publicar; no preparar aquí una publicación real.

## 8. Propietarios y validación prevista

Las rutas son vigentes en la base fijada; las ubicaciones se identifican por función, no por números de líneas de los monolitos retirados.

| Superficie | Propietarios actuales |
|---|---|
| Forma de final, checks y dimensiones | `scripts/ccr/contracts/review.py`, `findings.py`, `dimensions.py` |
| Topología, historia aplicada y agregado | `scripts/ccr/contracts/execution.py`: validate_execution, validate_execution_sources, validate_profile_execution |
| Historia de selección y registry | `scripts/ccr/workflow/profiles.py`; preservar sus invariantes, sin mover funciones allí |
| Despachos/frescura | `scripts/ccr/contracts/dispatch.py` y consumidores de ejecución; preservar proyección e identidad original |
| Checks, recibos, merge y preflight | `scripts/ccr/contracts/provenance.py`, `receipts.py`, `packets.py`, `preflight.py`, `identifiers.py` |
| Retención y validación del archive | `scripts/ccr/archive/retention.py`, `lifecycle.py`, `checkpoints.py`, `history.py`; parser en `scripts/ccr/cli/artifacts.py` |
| Presentación y entrega | `scripts/ccr/reporting/render.py`, `projections.py`, `delivery.py`, `comment.py` |
| Fixtures nuevos | `tests/profile_topology_fixtures.py` |
| Pruebas nuevas | `tests/test_review_profile_topology.py`, `tests/test_review_topology_integration.py` |

No es necesario modificar todos estos módulos: donde ya hay un contrato genérico, demostrar su funcionamiento con 12. Auditar también consumidores reales mediante `rg`; el inventario no autoriza reemplazos globales ni cambios fuera del alcance.

La matriz de pruebas del plan debe demostrar:

- 12: deep exactamente 2 y extended 3–5 para ambas fuentes; uno/dos finales, tres finales rechazados en fuentes.
- Conservación de historia y escalación; historia sola no satisface el mínimo final; historia ausente/fallback sigue visible en agregado.
- Combinaciones completas, coordinador, ausencias y sus negativos con fuentes válidas; orden temprano/igual rechazado incluso degraded.
- Despacho original temprano + segundo start tardío; anotación tardía; provider distinto; dos finales frescos válidos con proyección.
- 10 **y 11**: deep 3 y extended explícito 2/automático 4 válidos; dos finales realmente posteriores al descubrimiento siguen rechazados. Preservar el caso de histórica + final.
- 12: propósito/27 dimensiones obligatorios, receipts de comandos 2, merge, render, full/brief, preflight, retención y validación durable; la ampliación de §10 añade draft 3/receipt de delivery 2. Los contratos históricos se prueban por separado.
- Regresión de los límites modulares/imports y de las políticas de prioridad, reutilización y cierre existentes.

## 9. Riesgos y límites

La partición por nombres sigue dependiendo de contrato/revisión para acreditar contenido real. Separar filas históricas/finales no autoriza borrar trabajo ni alterar la agregación. El piso 3 eleva el mínimo explícito anterior de 2 por decisión aprobada.

La alta de 12 cruza contratos, proyecciones y archive: omitir una rama `== 11` puede perder propósito, dimensiones o clasificación pública. La prueba integrada debe detectar estos casos; un grep limpio no basta.

La compatibilidad de consumidores externos, incluido el viewer independiente, no se presume ni se modifica en esta tarea. La versión nueva debe comunicarse al integrar; los registros históricos no se migran. No se reescriben `docs/validation/`, evidencias ni releases anteriores.

Fuera de alcance: implementar durante esta corrección documental; nuevas dependencias; cambios a independencia, forma de execution, elegibilidad ajena a los conteos aprobados, veredictos, calibración, gates de proyecto, reutilización, esquemas de archive/trace/receipt de comandos/packet/model-usage; recrear fachadas retiradas; publicar o modificar repositorios consumidores. Las nuevas versiones de draft y receipt de delivery de §10 sí pertenecen a la ampliación solicitada.


## 10. Comandos y recursos identificables con ocultación selectiva

### 10.1 Estado observado y criterio de diseño

Actualmente `render.py` sólo muestra el comando en el informe privado; `projections.public_projection` elimina comandos completos y rutas absolutas, y `delivery._PortableProjection` sustituye `checks[].command` por un marcador y también elimina comandos incrustados en prosa. El campo purpose no permite reconstruir por sí solo qué recurso se validó.

Se adopta el criterio funcional solicitado: **mostrar comandos/recursos originales acreditados del proyecto con ocultación selectiva**. No sirve habilitar comandos brutos ni desactivar la sanitización. La alternativa de conservar únicamente explicaciones para todos los checks mantendría el problema descrito; se reserva a recursos de CCR, procedencia desconocida o argumentos no proyectables con seguridad.

Criterio técnico propuesto: una proyección tipada compartida por comentario y delivery, ligada a la revisión y a evidencia de origen. No usar reemplazos globales de texto para reinsertar comandos después de sanitizar ni convertir en público todo archivo situado dentro del worktree.

### 10.2 Qué pertenece al proyecto

Un recurso es original del proyecto cuando su ruta/contenido está acreditado en los inputs fijados **antes de la verificación de CCR**: árbol Git de la revisión o snapshot/material explícitamente capturado del alcance. Puede ser un archivo nuevo del cambio revisado, aunque no existiera en la base; no puede ser un archivo añadido por CCR después de fijar esos inputs.

Capturar de forma acotada, para los recursos referidos por el check, identidad de revisión/snapshot, ruta relativa y hashes del contenido fijado y del usado al ejecutar. El nombre, extensión, estar tracked después de la ejecución o estar dentro de tests/ no prueban origen. Un archivo original sobrescrito por CCR con una reproducción tampoco se publica como si se hubiera ejecutado su versión original.

Una tarea nombrada sin ruta explícita, como `npm test` o `make check`, también puede acreditarse mediante su definición original en el manifiesto/configuración del proyecto fijado y su vínculo con la ejecución. No basta reconocer el nombre del comando; una definición modificada por CCR no acredita la tarea original y un wrapper opaco conserva la regla de explicación.

La lectura adicional se limita a acreditar esos recursos y sus argumentos; no abre otra revisión del repositorio ni ejecuta nada para descubrir su origen. En validación posterior al cleanup se usan las evidencias seleccionadas retenidas, sin visitar el antiguo worktree.

### 10.3 Reglas de presentación

- Mostrar herramienta, subcomando, selector/filtro y rutas relativas acreditadas del proyecto; quitar el prefijo local del checkout/entorno y segmentos expresamente clasificados como sensibles. Si una ruta parcial lleva marcadores de ocultación, identificarla como representación saneada y no inventar un enlace exacto. No exponer usuario, máquina, raíz de workspace/archive, credenciales, tokens, valores de entorno secretos ni parámetros sensibles de URLs. Ser original del proyecto no convierte sus secretos o componentes sensibles en publicables.
- No ejecutar, evaluar o reconstruir shells arbitrarios para proyectarlos. Si argv, un wrapper, una expresión anidada o el origen de un argumento no son verificables, usar explicación; no fabricar un comando reproducible.
- Los comandos son representaciones saneadas de la ejecución real, identificadas como tales cuando haya sustituciones. Mantener literalmente los argumentos no sensibles; no mostrar otro comando como si se hubiera ejecutado.
- Si el entrypoint es un test/script/reproducción creado o alterado por CCR, no mostrar su ruta, nombre ni invocación como recurso del proyecto. Explicar concretamente método, condición/caso validado y resultado, enlazado al ID real del check.
- En checks mixtos se puede conservar un comando del proyecto con argumentos privados marcados, siempre que el ejecutable/entrypoint y el resto puedan acreditarse. Si el entrypoint es de CCR, el comando se omite; se pueden listar aparte los recursos originales del proyecto realmente validados, sin atribuirles una ejecución de test inexistente.
- Con procedencia desconocida, conservar propósito, resultado y una explicación específica de qué se pudo acreditar. La incertidumbre de exposición no se convierte en un hallazgo del producto ni cambia su veredicto; impide publicar la parte no acreditada.
- Aplicar la misma decisión a comentario, full, brief, handoff solicitado y JSON portable. No volver a insertar el comando bruto en prose, evidencia, contexto o referencias. IDs, versiones, resultados, relaciones y registro interno permanecen intactos.

Ejemplos normativos, con datos sintéticos:

| Caso acreditado | Vista pública/portable |
|---|---|
| `pytest C:\\Users\\persona\\repo\\tests\\test_queue.py -k retry`, archivo original y argv conocidos | `pytest tests/test_queue.py -k retry`; prefijo privado omitido |
| `dotnet test tests/Queue.Tests.csproj --filter RetryTests`, recursos originales | Conservar comando, proyecto y filtro |
| `npm test -- --runInBand`, tarea acreditada en el package.json original y ejecución vinculada | Conservar comando y selector; identificar la tarea del proyecto |
| `python <sesión-CCR>/repro_retry.py`, reproducción creada por CCR | Sin esa invocación: «Se simuló un reintento con respuesta vacía y se comprobó si conservaba el identificador» + resultado real |
| Script original con `--token <secreto>` | Conservar el script acreditado y marcar el valor como omitido; nunca copiarlo a otra sección |
| Ruta dentro de tests/ añadida por CCR tras capturar inputs | Explicación, no clasificación automática como recurso original |
| Comando/origen no recuperable desde evidencia disponible | Explicación y ausencia explícita de detalle verificable; no inferir ni repetir el check |

### 10.4 Evidencia y formatos auxiliares propuestos

La forma de final 12 sigue siendo la de final 11. Su `checks[].command` interno conserva la ejecución original; no se añade un campo de origen a coverage.execution ni se cambia el recibo de comandos 2.

Introducir `evidence/check-disclosure.json` schema 1 como sidecar privado seleccionado y ligado al run. Envelope: `{schema_version, review_id, source_sha256, input_identity, checks}`, donde input_identity contiene las identidades head/snapshot fijadas. Cada fila: `{id, command_sha256, execution_reference, mode, command, resources, explanation, evidence_reference}`.

- mode: `project_command`, `mixed` o `explanation`; command es texto proyectado o null en explanation; explanation siempre es texto concreto no sensible.
- resources contiene únicamente recursos originales elegibles para proyectar: filas `{path, revision, project_sha256, executed_sha256}`, con path original relativo al proyecto y hashes concordantes cuando se afirma uso de su contenido original. Esa prueba es privada; la vista saneada no copia sus componentes sensibles.
- execution_reference/evidence_reference resuelven a evidencia seleccionada de argv/ejecución y pertenencia al input. La prueba privada puede conservar detalles sensibles; sólo se proyectan las vistas saneadas. Una declaración origin=project, un path o un digest suministrados sin evidencia contrastada no acreditan origen.
- source_sha256 usa el publication_digest canónico existente; command_sha256 es SHA-256 de los bytes UTF-8 exactos del comando original. El digest del sidecar corresponde a sus bytes seleccionados exactos. Cada check aparece exactamente una vez. Un modo project_command sin prueba suficiente se rechaza o se reconstruye como explanation, sin relajar evidencia de la revisión.
- Construir/actualizar el sidecar a partir de las observaciones de ejecución y inputs disponibles; el nuevo helper valida hashes/bindings y la coherencia de la proyección. La fidelidad editorial de una explicación sigue verificándose en la pasada existente de comentario, sin crear otro reviewer.
- Para resultados anteriores se usa información retenida verificable, si existe. Sin ella, explanation. No migrar ni reescribir el review original para mejorar la presentación, ni repetir comandos para llenar este sidecar.

Draft público **3** conserva los campos actuales del draft 2 y añade `check_disclosure_context`: la vista saneada por check y el digest del sidecar contrastado. prepare/verify reciben el sidecar seleccionado y sus fuentes, validan sus bindings y rerenderizan los bytes exactos. Sin checks, ese contexto puede ser null. Draft 2 conserva su verificación histórica y draft 1 conserva su respuesta actual stale_draft; no reinterpretar cuerpos anteriores ni habilitar como válido un draft ya obsoleto. Un cambio de clasificación genera un draft nuevo, no una edición posterior del texto ya verificado. La ampliación no autoriza enviar comentarios.

Receipt de delivery **2** conserva la identidad/source hash/inventario/hash de archivos actuales y añade `projection_policy: project-resources-v1`, `check_disclosure_sha256` y `model_usage_sha256` (null si no hay sidecar aplicable). Congelar receipt 1. El JSON portable preserva final schema 12: command lleva la vista saneada o el marcador explícito de explicación, nunca el valor privado bruto. La proyección no sirve como registro canónico de retención.

## 11. Modelos del harness y participantes despachados

### 11.1 Diagnóstico y objetivo

Ya existen `ccr.contracts.model_usage`, `workflow.builders.build_model_usage_update`, el sidecar opcional `evidence/model-usage.json` y su gate de retención. El contrato distingue modelo configurado/observado y conserva unknown/conflict. Sin embargo, la captura es pasiva/opcional y los ejemplos de ciclo de vida no muestran el recorrido completo; los renderers tampoco presentan sistemáticamente ese ledger.

Una referencia puntual a modelo no expuesto en evidencias de calibración no demuestra captura por participante. Tampoco la ausencia en un comentario/delivery demuestra por sí sola que no exista un sidecar privado. El cambio debe cubrir **captura, retención y presentación**, con pruebas de los tres pasos.

### 11.2 Captura en nuevas revisiones

- Registrar una observación para la coordinación y para cada asignación real de descubrimiento/verificación/gate despachada, enlazada por assignment_id y actor observado; los cambios de modelo/fase relevantes se conservan como observaciones adicionales.
- Distinguir el proceso/tool dispatcher de su reviewer: el proceso de despacho no se atribuye un modelo; el reviewer despachado es el participante que debe tener observación. Un coordinador que además revisa conserva ese vínculo sin inventar otra identidad independiente.
- Registrar únicamente metadata ya expuesta por plataforma, adaptador, argumentos del runner/dispatch o declaración explícita. configured_model no demuestra observed_model; un nombre del harness, provider ID o la frase «modelo por defecto heredado» no dan un ID de modelo efectivo.
- observed_model requiere fuente platform/adapter_observed y referencia contrastable. Sin ella, conservar configured_only cuando existe un identificador configurado conocido, o unknown con modelos null y un diagnóstico acotado de la ausencia. No sustituir ausencia por un nombre plausible.
- Registrar not_applicable para procesos que no usan modelo cuando aparezcan en el ledger; no heredan el modelo del coordinador. Registrar una observación no selecciona ni cambia el modelo usado.
- Reutilizar model-usage schema 1 y sus campos/estados/límites (256 entradas y 256 KiB); actor/provider/timestamp desconocidos permanecen según el contrato, sin tiempos inventados. La explicación de límites/metadata ausente usa los diagnostics existentes del contexto.
- Integrar la captura al recorrido de coordinación/dispatch/resultado, no limitarse a que exista un helper aislado. Exponer una operación de setup utilizable por el coordinador y documentar cuándo invocarla con metadata suministrada; no lanzar otros agentes, consultar historiales/APIs/counters, activar costes ni sondear configuración global para completar modelos.
- Para revisiones nuevas, la instrucción de captura cubre todos los participantes conocidos aunque su estado sea unknown. La falta de información o un límite de captura queda visible y no cambia la validez/veredicto del producto. Un sidecar seleccionado corrupto o de otro review conserva el rechazo de integridad actual; no se ignora para ocultar el problema.

### 11.3 Retención, vistas y ejemplos

Conservar ledger/contexto seleccionados y sus hashes antes de cleanup. La validación posterior usa esos bytes, sin sesiones vivas. No mezclar model_usage con review_inputs.sources de la revisión del producto ni con mediciones de tokens/precio.

Añadir al informe privado una tabla por participante/fase: harness conocido, actor/assignment, modelo configurado, observado, estado y procedencia o motivo de ausencia. Una columna sin metadata dice «no disponible»; no queda vacía ni se presenta como modelo observado. Los conflictos mantienen las observaciones originales.

Contrastar la cobertura de captura con participantes realmente observados en dispatch/resultados. Un ledger que sólo registra coordinación no se presenta como completo si hubo reviewers: mostrar cuáles no tienen observación capturada. Ese diagnóstico no fabrica una fila histórica ni cambia el veredicto del producto.

El delivery local full/brief puede mostrar el mismo resumen privado saneado, breve en brief, ligado al digest del ledger y sin rutas locales de sus fuentes. El comentario público y handoff público no muestran modelos/harness/identidades de workers por defecto. No exportar el ledger crudo; la fuente canónica y los límites siguen en el archive.

Actualizar los **ejemplos mantenidos** de ciclo de vida para incluir una observación de coordinación y reviewers despachados con selección/retención/presentación. Los ejemplos sintéticos usarán IDs de modelo ficticios claramente etiquetados y un caso unknown. No rellenar retrospectivamente ejemplos de corridas reales, validaciones, paquetes o archives cerrados con modelos inferidos.

## 12. Criterios de aceptación de la ampliación

| Área | Casos imprescindibles |
|---|---|
| Origen del proyecto | Archivo existente, archivo del cambio revisado, snapshot local; mismo path sobrescrito/creado por CCR y procedencia desconocida |
| Proyección selectiva | Windows/POSIX, prefijo checkout, intérprete local, filtros, espacios/comillas, secretos en argumentos/URL, pipeline opaco, symlink/traversal y cambio de hashes |
| Checks auxiliares | Entry point CCR siempre explicado; checks mixtos conservan sólo detalles acreditados, sin invocación falsa |
| Consistencia | Mismo comando/recursos visibles en comentario/full/brief/handoff y JSON portable; no filtrado accidental por el antiguo blanket sanitizer ni fuga en prose/evidence |
| Formatos | Draft 3 prepare/verify y receipt de delivery 2 ligados a sidecars; lectura histórica 1/2 sin reinterpretar; fuente original inmutable |
| Modelos | Configurado vs observado, unknown, conflicto/cambio por fase, N/A del dispatcher, coordinación y cada assignment real |
| Integración | Captura desde metadata real suministrada → sidecar/contexto → retención/cleanup → informe y delivery; modelos ausentes del comentario |
| Límites | Sin telemetría ni consultas de historial, sin backfill, bounded diagnostics; integridad seleccionada sigue obligatoria |

Los propietarios adicionales previstos son reporting/projections.py, render.py, delivery.py, comment.py y los CLI de contract/comment/delivery; un módulo puro de proyección de checks y su sidecar; contracts/model_usage.py, workflow/builders.py y setup.py, cli/setup.py y la integración existente del runner/retención. El plan fija sus interfaces y pruebas antes de la documentación operativa y del cierre.
