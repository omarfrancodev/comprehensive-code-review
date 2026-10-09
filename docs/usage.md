# Guía de uso

## Peticiones de revisión

Invoca `comprehensive-code-review` desde un agente compatible. En entornos que lo admitan, puedes usar `$comprehensive-code-review`. Indica proyecto y alcance: cambios locales, rango, commit, MR/PR o un área concreta de código.

```text
Usa comprehensive-code-review para revisar los cambios actuales.
Reporta tus hallazgos sin modificar código ni publicar comentarios.

Usa comprehensive-code-review --profile standard para revisar los MR 995 y 997 del proyecto core.

Usa comprehensive-code-review --profile focused para volver a revisar este PR.
Conserva los IDs anteriores y comprueba las correcciones pendientes.

Usa comprehensive-code-review --profile deep --delivery full --output docs/revisiones para revisar estos commits.

Revisa este MR con comprehensive-code-review y entrega un resumen breve para otro agente.
```

Estas convenciones se escriben en la petición al agente; no son un CLI ejecutable de la skill ni opciones de `npx` o de los helpers:

| Convención | Efecto |
|---|---|
| `--profile focused\|standard\|deep\|extended` | Fija el perfil de revisión solicitado. |
| `--delivery full\|brief` | Solicita una entrega portable completa o breve. |
| `--output <raíz>` | Elige la raíz de esa entrega, si se solicita una modalidad. |

Las peticiones explícitas en español «perfil deep», «entrega completa» y «entrega breve» tienen el mismo efecto. Sin perfil, se mantiene la selección automática. Sin entrega solicitada, se conserva el archivo interno habitual. `--output` por sí solo no autoriza exportar ni cambia la raíz del archivo interno: el agente confirma la modalidad antes de entregar y continúa la revisión independiente de esa elección.

Revisar autoriza inspección y los recursos temporales necesarios dentro de los permisos disponibles. Modificar código del producto, commit, push, cambios remotos de descripción, publicación, aprobación y merge requieren su propia autorización. Las restricciones de solo lectura o de no ejecución se respetan y se reflejan en el resultado.

## Profundidad y perfiles

El perfil define la estrategia de descubrimiento y verificación; la modalidad de entrega solo define la presentación. El coordinador utiliza el contexto ya descubierto para decidir, sin otro agente de preevaluación. `economy` es alias de `focused` y `balanced` de `standard`: se normalizan al interpretar una petición y permanecen fijos si son explícitos. Los registros históricos conservan sus nombres y representación; los nuevos resultados usan los nombres canónicos.

| Perfil | Descubrimiento | Verificación |
|---|---|---|
| focused | Un revisor, que puede ser el coordinador. | Comprobación escéptica de candidatos y dudas materiales en la misma sesión. |
| standard | Un revisor, que puede ser el coordinador. | Verificador independiente para candidatos sustantivos o dudas materiales; se omite si no quedan y la cobertura es suficiente. |
| deep | Dos revisores sobre flujos e invariantes concretos; un tercero solo por una necesidad distinta. | Verificación independiente agrupada de candidatos e invariantes asignadas. |
| extended | Automático: cuatro o cinco asignaciones justificadas; explícito: dos a cinco según necesidades distintas. | Una verificación independiente agrupada de candidatos e invariantes. |

Un perfil explícito permanece fijo; no escala silenciosamente. En automático, focused requiere alcance acotado demostrado, requisitos claros, consumidores identificados y ausencia de incertidumbres materiales o gates independientes. Deep corresponde a mecanismos materiales observables, como cambios de autorización, transacciones, migraciones incompatibles, concurrencia o contratos entre consumidores desplegados por separado. Extended exige además cuatro o cinco asignaciones independientes necesarias que no puedan agruparse en tres sin omitir una perspectiva o gate requerido. Standard es la alternativa cuando no se demuestra elegibilidad para focused ni corresponde mayor profundidad.

El modo automático puede escalar con hechos nuevos, reutilizando contexto, checks y asignaciones válidas. El número de líneas, la urgencia, los nombres de tecnologías o las letras ABCDE no determinan el perfil. Los gates obligatorios siguen aplicándose y sus sesiones adicionales se identifican por separado. Sin delegación se declaran los pases en una sola sesión y sus limitaciones; la falta de una independencia exigida puede impedir un veredicto favorable. Consulta [profiles.md](../references/workflow/profiles.md).

Deep y extended concentran sus revisores en los flujos que requieren esa profundidad; otras partes conservan cobertura por un responsable existente. Cada brief declara áreas ABCDE, archivos/interfaces, preguntas/invariantes y evidencia esperada. Se agrupan áreas que comparten flujo y solo se separan por necesidades distintas demostradas. Consulta [reviewers.md](../references/execution/reviewers.md) y [worker-packets.md](../references/execution/worker-packets.md).

## Cobertura, hallazgos y veredictos

La matriz ABCDE del informe muestra **A** arquitectura y diseño, **B** comportamiento y negocio, **C** contratos e integración, **D** datos y persistencia y **E** seguridad y operación. Cada área queda Cubierta, Parcial, No evaluada o No aplica, con evidencia o motivo y referencias a los hallazgos. Cubierta significa inspeccionada y puede contener defectos. Un mismo hallazgo puede afectar varias áreas y conserva un solo bloque. No se añade puntuación global ni nivel de riesgo del cambio. Consulta [review-areas.md](../references/workflow/review-areas.md).

Los defectos confirmados se cuentan por P0, P1, P2 y P3, incluso cuando los conteos son cero. Las incertidumbres no aumentan esos conteos. Cada hallazgo identifica ubicación, escenario, impacto, evidencia y corrección requerida; prioridad, carácter bloqueante y origen se declaran por separado. La evidencia estática concluyente puede demostrar un defecto. Un check omitido, bloqueado o fallido por el entorno no equivale a una prueba aprobada ni demuestra por sí solo un defecto.

Los veredictos son **Aprobable**, **Aprobable con reservas**, **No aprobable** y **Evidencia insuficiente**. Un bloqueante confirmado lleva a No aprobable; sin bloqueantes, una limitación material, versión desactualizada o cobertura inadecuada lleva a Evidencia insuficiente. Las reservas corresponden a asuntos concretos no bloqueantes; no aceptan silenciosamente requisitos desconocidos. En MR/PR se comprueba también que la descripción refleje los cambios. Consulta [profiles.md](../references/workflow/profiles.md#verdict-decision) y [report-format.md](../references/reporting/report-format.md).

Cada revisión usa `CR-<run_id>`, los hallazgos `F001`, `F002`, etc. y los checks `C001`, `C002`, etc. Los IDs conservan su identidad al ordenar por prioridad o cambiar estado. El coordinador asigna los definitivos y mantiene el mapeo desde los candidatos. Los IDs históricos conocidos se preservan sin renombrar archivos ni comentarios publicados. Consulta [identifiers.md](../references/contracts/identifiers.md).

## Revisiones incrementales y aportaciones externas

Una re-review comprueba hallazgos y condiciones anteriores contra las entradas actuales. Un complemento añade un área o check acotado solicitado. Ambos crean un registro nuevo enlazado al anterior; no afirman haber revalidado partes ajenas al alcance actual.

Se conservan los IDs de la misma causa y se declara cada hallazgo previo como corregido, vigente, retirado o no reevaluado según la evidencia. Se revisan también consumidores y flujos afectados por la corrección. Los checks anteriores solo se reutilizan con entradas aplicables y motivo documentado; los cambios de versión, configuración o fixtures requieren refrescar las comprobaciones afectadas o justificar su vigencia. Si no se recupera una fuente anterior fiable, se declara la limitación sin inventar continuidad. Consulta [re-review.md](../references/workflow/re-review.md).

Las afirmaciones pertinentes de otros revisores se contrastan después del descubrimiento independiente y antes de la verificación agrupada. Se conserva su autor/herramienta, referencia y versión conocida, sin heredar automáticamente prioridad ni resolución. Las consultas al historial u otros MR/PR responden a preguntas concretas; no añaden otro barrido por defecto.

## Entrega portable

Solo una solicitud explícita de modalidad completa/full o breve/brief genera la entrega. Su origen es el resultado de la revisión; no abre otra revisión, cambia el perfil ni sustituye el archivo interno.

| Modalidad | Contenido |
|---|---|
| `full` / completa | `informe.md` y `review.json` portables. `contexto.md` es opcional y aporta únicamente datos adicionales relevantes. |
| `brief` / breve | `resumen.md` autocontenido, adecuado para consultar el resultado o transferirlo a otro agente. |

El resumen incluye ID de revisión, versión revisada, alcance, veredicto y motivo, conteos confirmados P0–P3, e ID, prioridad, ubicación, impacto y corrección de cada hallazgo. Resume los checks y los pendientes o limitaciones que condicionan el resultado. Conserva los datos necesarios para entenderlo sin abrir archivos internos; no inventa fuentes o checks.

Cuando hay contexto adicional relevante, `contexto.md` organiza **Supuestos y decisiones**, **Fuentes analizadas** —Spec, Plan u otras fuentes realmente utilizadas, con las secciones revisadas—, **Estado de implementación** con evidencia o IDs y **Pendientes**. Usa solo datos ya recopilados; no abre otro pase de inspección. Se incluyen solo apartados con datos disponibles; no se exige una Spec o un Plan inexistente ni se duplican el informe o los logs. Los conflictos entre fuentes y los límites de implementación observada se declaran; un build aprobado no prueba el cumplimiento de todos los requisitos. Sin contexto adicional, el archivo se omite.

La raíz predeterminada es `<checkout-persistente>/docs/ccr/reviews/`; el resultado queda en `<raíz>/<alcance>/<review-id>/`. El coordinador elige el checkout persistente del proyecto, nunca el worktree temporal ejecutor. Una raíz relativa de `--output` se resuelve respecto a ese checkout. El destino se comprueba dentro de los permisos disponibles y se informa su ubicación real.

La entrega contiene las proyecciones solicitadas y metadatos portables de identidad e integridad en `.ccr-delivery.json`. No copia `evidence/`, logs, reproducciones, cierre ni trazabilidad internos. Conserva ubicaciones de código relativas al repositorio y URLs verificadas útiles; omite rutas privadas y enlaces que dependan de evidencia no distribuida, sin inventar referencias. Exportar después del cierre conserva el archivo original inmutable y registra la entrega por separado, vinculada a su revisión. Los destinos existentes no se sobrescriben; una entrega distinta necesita otro destino explícito. Un fallo de entrega no elimina la revisión conservada.

La transferencia nueva usa full/brief. Los handoff históricos siguen intactos; las opciones legacy solo se usan si se solicita expresamente ese artefacto, según [handoff.md](../references/reporting/handoff.md). Pedir una entrega no autoriza corregir código ni publicar el resultado. El contrato canónico, las comprobaciones de portabilidad y el helper están en [delivery.md](../references/reporting/delivery.md).

## Archivo interno y ejecución

El archivo interno es independiente del checkout del usuario, la instalación de la skill y los recursos temporales. La raíz se elige una vez: ubicación explícitamente solicitada para el archivo interno, después `CCR_ARTIFACTS_DIR`, después `<home>/.comprehensive-code-review/reviews/`. `--output` de una entrega no interviene en esa selección. Una ubicación bloqueada se informa como limitación; no se cambia silenciosamente a `docs/` o al scratch del proveedor.

El layout es `<raíz>/<proyecto>-<id-repositorio>/<alcance>/<fecha>-<id-ejecucion>/`. Se usa exactamente el `run_dir` devuelto por el helper. Cada MR/PR tiene su propio registro, y una re-review crea otro enlazado. Los archivos históricos no se renombran ni migran por cambios de contrato.

| Artefacto | Propósito |
|---|---|
| `informe.md` | Informe legible desde el registro final. |
| `review.json` | Registro final completo, ligado a la versión y los IDs. |
| `cierre.json` | Identidad de ejecución, alcance, recursos registrados, integridad y limpieza observada. |
| `trazabilidad.jsonl` | Hitos compactos de alcance, perfil, asignaciones, checks, verificación, conservación y cierre. |
| `evidence/` | Evidencia seleccionada necesaria para reproducir o auditar el resultado. |
| `measurements.json` | Solo para una evaluación de coste solicitada; los archivos anteriores se conservan. |

La trazabilidad distingue ejecutor y registrador, procedencia observada o declarada y orden de registro frente a acciones paralelas. No registra cada búsqueda ni reconstruye eventos desconocidos. Los hashes comprueban integridad respecto al cierre conservado; no demuestran la verdad de un hallazgo. Consulta [lifecycle-trace.md](../references/archive/lifecycle-trace.md).

Las escrituras de builds, tests, instalaciones y reproducciones usan worktrees propios del proyecto, preferentemente su ubicación establecida, normalmente `.worktrees`. Las lecturas estáticas pueden usar objetos Git. Si no puede crearse el worktree, se declara bloqueada la validación; una copia en scratch necesita autorización explícita. Las dependencias, cachés compartidas y junctions son admisibles cuando son compatibles; ante conflictos se usan recursos propios del ejecutor afectado. La procedencia se conserva en el contexto/cierre existentes. Consulta [workspaces.md](../references/execution/workspaces.md).

La evidencia temporal vive en `evidence/` de una sesión propia registrada antes de usarla. Se selecciona explícitamente qué evidencia sobrevivirá; no se copian todas las salidas ni credenciales o datos ajenos. El archivo final y su evidencia necesaria se conservan y verifican antes de limpiar recursos propios. Un fallo de retención o validación conserva los temporales para recuperación. El cierre registra la limpieza observada o las rutas residuales; no borra recursos por sí mismo.

Una revisión cerrada es inmutable. Correcciones, otra revisión, publicación o entrega posterior usan una operación nueva vinculada. El archivo permanece hasta que se solicite eliminarlo; no hay caché automática entre revisiones ni retención automática que lo borre. La ubicación real se comunica al usuario y se omite del comentario público. Los comandos, gates, compatibilidad histórica y recuperación se documentan en [artifacts.md](../references/archive/artifacts.md).

## Comentarios públicos

Solo se publican con autorización explícita. Comparten el título, veredicto, ID, alcance, versión, hallazgos confirmados y validación del informe; incorporan la consistencia de la descripción y las incertidumbres pertinentes. Omiten la matriz ABCDE, selección de perfil, rutas del archivo interno y mecánica de los revisores.

El responsable del MR/PR y los autores del cambio se declaran por separado usando fuentes verificadas. La asignación, creación del MR/PR y autoría de commits no son equivalentes. Los nombres o correos de Git no se convierten en menciones sin verificar su cuenta; las identidades no disponibles se declaran como no identificadas. Antes de publicar se comprueba la vigencia de código, descripción y atribución. Consulta [report-format.md](../references/reporting/report-format.md) y [publication.md](../references/reporting/publication.md).

## Helpers y validación

La lectura de instrucciones no requiere ejecutar helpers. Todos usan Python 3.10+ y biblioteca estándar. Se invocan mediante intérprete y ruta absoluta; consulta `--help` para la interfaz exacta. Las convenciones de la petición al agente no sustituyen sus argumentos.

| Helper | Propósito |
|---|---|
| `scripts/review_contract.py` | Validar registros, asignar IDs y generar informes y comentarios en español. |
| `scripts/review_packets.py` | Validar y combinar candidatos y decisiones incrementales sin inventar conclusiones. |
| `scripts/review_artifacts.py` | Preparar, registrar, conservar, validar y cerrar el archivo interno sin eliminar recursos. |
| `scripts/review_delivery.py` | Generar la entrega solicitada desde un resultado conservado. |
| `scripts/review_workspace.py` | Preparar y limpiar snapshots temporales con comprobaciones de propiedad; requiere Git. |
| `scripts/review_runner.py` | Ejecutar un adaptador CLI previamente configurado; no selecciona ni configura el proveedor. |
| `scripts/review_metrics.py` | Registrar y agregar contadores suministrados para una evaluación explícita de coste. |

El helper de artifacts es obligatorio cuando puede ejecutarse dentro de los permisos disponibles. Una alternativa nativa por indisponibilidad comprueba el mismo contrato; un fallo de validación no justifica eludir el gate. Para entregar se usa el helper de delivery cuando puede ejecutarse, con alternativa nativa equivalente si está indisponible. Los demás helpers son opcionales. Un validador estructural no determina si un hallazgo es verdadero. Consulta [result-contract.md](../references/contracts/result-contract.md), [artifacts.md](../references/archive/artifacts.md) y [delivery.md](../references/reporting/delivery.md).

Desde una copia del código fuente:

```bash
python -B -m unittest discover -s tests -v
```

Las pruebas cubren contratos, helpers, cobertura ABCDE, compatibilidad, escenarios ejecutables y limpieza en repositorios temporales. Git es necesario para la integración; sin él se informa una omisión. Ejecuta las comprobaciones que escriben en espacios aislados.

Las mediciones se activan solo para una evaluación de coste solicitada: no se crean archivos de medición ni se buscan contadores en revisiones normales. Los contadores no disponibles permanecen desconocidos. No hay captura automática de tokens/créditos en Codex/Kiro, ni se ha medido un porcentaje de ahorro. Las pruebas mecánicas no son un benchmark de coste ni garantizan integridad del producto; consulta [measurements.md](../references/maintenance/measurements.md) y [evaluation.md](../references/maintenance/evaluation.md). La skill no selecciona modelos ni cambia su esfuerzo.
