# Referencias organizadas y ciclo de vida observable de las revisiones

**Fecha:** 2026-10-09

**Proyecto:** comprehensive-code-review

**Base:** v2.8.0, commit `e227349d8082784949c2504f709b033e2231870d`

**Versión prevista:** 2.9.0; publicación pendiente del flujo de revisión del PR.

**Estado:** especificación y plan aprobados por el usuario; ejecución nativa en la rama de trabajo.

## Objetivo y alcance aprobado

Organizar las referencias operativas de la skill y hacer que sus artefactos describan mejor el estado, los participantes y los tiempos observados de una revisión. El resultado servirá como contrato para consumidores como el visor independiente, sin incorporar el visor ni observadores a la ejecución de la skill.

El usuario aprobó agrupar las referencias, distinguir preparación de trabajo iniciado, registrar tiempos de ocurrencia cuando se conocen y conservar relaciones explícitas cuando se pueden observar. El visor tiene su propio repositorio, especificación y plan; esta entrega modifica únicamente la skill.

## Restricciones globales

- Python 3.10 o superior; helpers con biblioteca estándar y pruebas con unittest.
- Worktree de desarrollo dentro de `.worktrees/`, desde main actualizado; `.worktrees/` permanece ignorado por Git.
- Nuevo archivo interno: schema 5; lectura compatible con schemas 1, 2, 3 y 4, sin migración automática.
- Contrato final de review: schema 7; packets: schema 1; trazabilidad: schema 1, sin campos nuevos.
- Solo el coordinador persiste la trazabilidad mediante el helper o una alternativa nativa equivalente autorizada por el contrato.
- `recorded_at` conserva el instante real de registro; `occurred_at` desconocido permanece null.
- Sin nuevas mediciones, sondeos de contadores, heartbeats, agentes ni barridos de contexto obligatorios.
- Revisiones cerradas y archivos históricos permanecen inmutables.
- El visor se mantiene en su proyecto separado y no se implementa ni modifica aquí.
- Crear PR para revisión humana; no fusionar, etiquetar ni publicar release sin autorización posterior.

## Enfoque y alternativas consideradas

Se conserva la división actual: `review_artifacts.py` posee la transacción y el cierre; `review_trace.py` normaliza y verifica eventos sin escribir archivos. Se aprovechan los hitos ya registrados para cambiar de estado, evitando un comando de inicio adicional.

Un heartbeat permitiría observar actividad reciente, pero añadiría procesos, escrituras y una señal que no demuestra que un agente siga ejecutándose. Un nuevo esquema de eventos tampoco es necesario: schema 1 ya contiene tiempos, participantes y relaciones. Se mantiene ese contrato y se mejora cómo se emite.

## 1. Organización de references

Mover los 20 archivos existentes según esta tabla. Cada archivo mantiene una sola ubicación canónica.

| Carpeta | Archivos |
|---|---|
| `workflow/` | scopes.md, profiles.md, capabilities.md, reading-strategy.md, re-review.md, review-areas.md |
| `execution/` | reviewers.md, worker-packets.md, workspaces.md, external-cli.md |
| `contracts/` | result-contract.md, identifiers.md |
| `archive/` | artifacts.md, lifecycle-trace.md |
| `reporting/` | report-format.md, publication.md, delivery.md, handoff.md |
| `maintenance/` | evaluation.md, measurements.md |

Actualizar enlaces y rutas operativas en SKILL.md, README.md, docs, referencias y pruebas. Los enlaces Markdown de documentos históricos deben seguir resolviendo; sus narrativas, versiones y decisiones originales no se reescriben como si fueran actuales. Las menciones históricas de rutas usadas entonces pueden permanecer como texto cuando no sean instrucciones vigentes ni enlaces.

No dejar copias o archivos de redirección en la raíz. No introducir un índice que los agentes deban leer completo. El coordinador sigue cargando por fase; los workers siguen leyendo únicamente su contrato de packet y brief. Los enlaces entre referencias que cambian de carpeta usan destinos relativos correctos.

## 2. Estado de cierre y comienzo efectivo

Los nuevos runs usan esta secuencia:

`prepared → processing → retaining → closing → complete`

`prepared` significa que existe un archivo propio y un alcance fijado, pero aún no hay un hito registrado de trabajo de revisión. `processing` significa que el trabajo comenzó según la evidencia registrada. No significa que un proceso esté vivo ni que haya ejecución continua.

El helper cambia de `prepared` a `processing` en la misma transacción del primer evento externo cuyo kind sea `agent`, `discovery`, `check` o `grouped-verification`, y cuyo status sea `started`, `completed`, `passed`, `failed`, `blocked` o `skipped`. Estos dos últimos estados solo se emiten después de observar un intento o una decisión de ejecución, no al anticipar un posible impedimento. La mera selección de perfil, planificación, autorización, registro de recursos o validación preparatoria no inicia la revisión.

En el flujo normal, el coordinador registra un `discovery/started` antes de comenzar el descubrimiento o un `agent/started` después de observar el lanzamiento de un worker. Este registro sustituye un hito equivalente si ya existía: no se duplican eventos solo para cambiar de estado. Un resultado terminal conocido también permite iniciar `processing` cuando el harness solo expone el resultado.

Registrar recursos propios se permite en `prepared` y `processing` antes de la retención. Retener directamente desde `prepared` conserva compatibilidad para callers que aportan un resultado ya construido; no se sintetizan agentes ni descubrimientos previos para explicar ese resultado. Esta posibilidad no sustituye el registro de inicio en las nuevas ejecuciones de la skill.

Los eventos posteriores al inicio no regresan el estado. Un checkpoint en `closing` no vuelve a `processing`. Se conserva el bloqueo de mutaciones durante retención interrumpida y la inmutabilidad de `complete`. `closing` con cleanup pendiente permanece pendiente; no se afirma cierre completo.

El estado y el evento se unen a la recuperación transaccional existente. Si se interrumpe la escritura, el gate de validación falla y una mutación permitida recupera los bytes y tiempos ya preparados. No se declara una transición validada mientras exista un intent pendiente.

## 3. Compatibilidad de esquemas

`prepare` emite schema 5. Un conjunto explícito de schemas con trace (`4` y `5`) sustituye condiciones que hoy dependen de igualdad con 4. Todas las rutas de verificación, recuperación, registro, retención y cierre usan esa misma definición.

Solo schema 5 acepta `processing`. Schema 4 conserva su máquina de estados anterior, aun cuando el nuevo helper lo abra. Schemas 1–3 no adquieren trazas sintéticas. Un validador de schema 4 debe rechazar un manifest manipulado que declare `processing`.

No cambian schema 7 del resultado, schema 1 del packet ni schema 1 del JSONL. Los consumidores que solo conocen schemas 1–4 deben reconocer schema 5 como no soportado, sin interpretar automáticamente un estado nuevo. La documentación identifica la nueva versión del productor; no promete compatibilidad de un visor que todavía no está implementado.

## 4. Tiempos y procedencia

### Operaciones del helper

El helper captura `occurred_at` en UTC al construir el hito de una operación lógica que acaba de observar. Incluye `provenance={kind: helper, source: review_artifacts:<kind>}`. El tiempo describe ese hito lógico; no se presenta como el instante exacto de una escritura del sistema operativo. `recorded_at` se genera por separado al serializar el evento.

Una recuperación conserva el tiempo original del evento pendiente. Una segunda ejecución idempotente de cierre no añade un evento con tiempos nuevos.

### Operaciones externas

Se prefiere el tiempo del resultado nativo del harness o de la herramienta. Si no existe, se conserva null; no se usa la hora actual de ingestión como si fuera la de ejecución. Una fuente textual inventada tampoco convierte un tiempo desconocido en conocido.

Para el runner opcional, `record-event` puede recibir `--execution-metadata <run.json>`. Usa el metadata ya generado: `started_at` para `started`, y `finished_at` para estados terminales `completed`, `passed`, `failed`, `blocked` o `skipped`. Estos tiempos describen los límites de la invocación del wrapper, no la actividad interna del modelo. No se obliga a usar el runner, a copiar todo run.json ni a crear measurements.json.

Si un caller aporta tanto `occurred_at` como metadata, deben coincidir para el hito elegido; un desacuerdo falla explícitamente. Metadata inválido o un estado sin correspondencia temporal no se corrige mediante inferencias. Sin metadata, un tiempo externo no null requiere una procedencia con source identificable en emisiones nuevas de schema 5. La validación estructural histórica no invalida eventos antes aceptados.

Los tiempos requieren UTC explícito. No se ordenan ni rechazan automáticamente eventos por diferencias entre relojes de hosts: sequence sigue siendo el orden de registro. Si falta `occurred_at`, un consumidor usa ese orden como fallback y debe etiquetarlo como tal.

## 5. Participantes y relaciones

`recorder` identifica al helper escritor. `actor` identifica al responsable observado del hito y `executor` identifica al entorno o sesión que lo ejecutó cuando se conoce. Un worker se identifica con nombre y provider_id disponibles en el resultado o lanzamiento; IDs no expuestos permanecen null. La integración de metadata temporal no inventa ni sustituye actor o executor.

Las relaciones son opcionales y solo se agregan si una fuente permite afirmar el vínculo. No se deducen de eventos consecutivos, textos parecidos o letras ABCDE. Se conservan los tipos actuales y límites de 24 relaciones y 8 KiB por evento.

Para nuevos eventos, recomendar destinos locales `E000001`, `F001`, `C001`; para otra revisión con identidad conocida, `CR-<run_id>#F001`, `CR-<run_id>#C001` o `CR-<run_id>#E000001`. Los destinos heredados permanecen legibles, sin normalización retroactiva. Las referencias externas que no tengan ese formato se conservan como referencias explícitas acotadas, no se les asigna una identidad ficticia.

Un destino local con formato E y seis dígitos debe existir previamente en la misma traza; autorreferencias o destinos futuros fallan en emisiones nuevas de schema 5. Los F/C pueden referir a candidatos ya asignados que luego se descarten: no se exige un finding final ni se inventa un registro adicional. Los destinos de otra revisión no disparan búsquedas automáticas de otros archivos. La validación de formato e integridad no demuestra la veracidad semántica de una relación.

## 6. Documentación y coste

SKILL.md añade únicamente las instrucciones necesarias para iniciar el estado, preservar tiempos observados y usar las nuevas rutas. Los detalles, casos de compatibilidad y ejemplos viven en `references/archive/` y docs/usage.md. README.md mantiene una explicación breve de los artefactos y un enlace al uso detallado.

La evaluación de coste sigue siendo optativa. Ningún escenario normal necesita leer measurements.md ni consultar tokens/créditos. Tampoco se añaden campos obligatorios al packet, nuevas rondas de verificación o reconstrucciones de historial.

## 7. Verificación y criterios de aceptación

- Los 20 archivos tienen una ubicación canónica y todos los enlaces locales vigentes resuelven.
- Un nuevo prepare emite schema 5 y prepared; un hito real produce processing, en una sola mutación.
- Selección, planificación y checkpoints preparatorios no producen processing.
- Register y retain funcionan durante processing; cierre y cleanup siguen preservando recursos ajenos.
- Fixtures de schemas 1–4 mantienen sus gates y no son migrados; una revisión complete no cambia ni un byte.
- Interrupciones antes y durante el reemplazo de trace/cierre conservan el gate de recuperación y los tiempos originales.
- Hitos del helper tienen tiempo UTC y fuente; eventos externos sin reloj observado mantienen occurred_at null.
- La integración opcional del runner conserva identidad, rechaza tiempos contradictorios y no activa mediciones.
- Eventos históricos con referencias/timestamps antes válidos siguen verificándose; nuevas referencias locales E inexistentes fallan.
- La suite completa pasa en un entorno Windows con temporal accesible y suficientemente corto; una prueba omitida por privilegios de symlink se informa como tal.
- Escenarios de presión verifican que la nueva estructura no causa lectura completa, métricas, timestamps inventados ni agentes adicionales.

## 8. Entrega y publicación

Preparar el cambio en `feat/artifact-lifecycle`, validar, revisar la rama completa y crear un PR con problema, comportamiento y evidencia. CHANGELOG incluye 2.9.0 como Unreleased mientras el PR esté pendiente. Tras aprobación y autorización de publicación, fijar la fecha real antes del commit/tag de release siguiendo el flujo del repositorio. No crear una release en esta etapa.

No ejecutar pruebas contra archivos reales de `~/.comprehensive-code-review`: usar fixtures independientes. No modificar el proyecto del visor ni limpiar recursos de otras sesiones.
