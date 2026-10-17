# Selección de perfiles, conservación provisional y recuperación de reviews

## Estado y propósito

Diseño de los ocho cambios aprobados en conversación. La revisión de esta especificación escrita precede al plan y a la implementación bajo Superpowers. Este documento no modifica la skill, recupera reviews reales ni autoriza merge/tag/release.

Base: `main` `5507c48715c558c9d366491f19fcce196780b37e`, release 2.11.0. Rama `feat/review-recovery-lifecycle`, worktree `.worktrees/review-recovery-lifecycle`. Preparar 2.12.0 pendiente de publicación durante la implementación; conservar enlaces de descarga de 2.11.0 hasta autorizar la publicación.

**Objetivo:** registrar la selección inicial antes del trabajo, conservar cambios de perfil y resultados parciales, y decidir de forma verificable si continuar, reiniciar o mostrar un review existente. Preservar la diferencia entre juicio del código, conservación de datos, cumplimiento observado y cierre de recursos.

## Evidencia que origina el cambio

- MR prosur-packages !42, `CR-682f6a09f65c467a8cec`: archive 6/skill 2.11.0; discovery empezó en E000002, el resumen ya mencionaba deep y el evento formal profile/selected llegó en E000005. El JSON final schema 9 es estructuralmente válido; la validación de fuentes falla por precedencia. Informe/evidencias/contexto existen en el worktree; el archivo durable permanece processing/retained=false y executors=[].
- MR console !785, `CR-9e905e93d7fb4b71987e`: discovery inició mencionando focused sin evento formal de selección. Solo se conservan cierre/traza. No hay error de retención que pruebe la misma causa exacta de !42.
- MR console !785, `CR-33e9e2bc24e1486ca186`: mismo scope/base/head, mismas dos rutas temporales, previous_run=null. Selección precede al trabajo; el resultado quedó retenido y pasa validate --require-complete. Las rutas ya no existen; el primer run quedó pendiente sin enlace de sustitución.
- En ambos repositorios existe ejecución correcta con 2.11.0. El fallo requiere mejorar los límites y recuperación del flujo, no atribuirlo al código revisado ni a ausencia de ejecutores.

Pruebas de estos hechos fueron de solo lectura. Los artifacts reales quedan fuera de las mutaciones de este proyecto; se usarán fixtures sintéticas equivalentes.

## Alcance y alternativas

Se implementa un único ciclo coordinado: selección/historial → gate temprano → checkpoints → inspección/recuperación → retención validada → limpieza observada → cierre. Los ocho puntos comparten scope, ownership y transacciones; no requieren ocho subsistemas ni agentes adicionales.

Alternativas evaluadas:

1. **Recomendada:** operaciones deterministas en helpers existentes, un módulo puro para perfiles y un módulo de recuperación con IO acotado. Facilita comportamiento comprobable y evita depender del recuerdo del agente.
2. Solo instrucciones más estrictas: coste inicial menor, pero permite descubrir nuevamente la omisión al final y no conserva estados recuperables.
3. Eliminar precedencia/gates de fuentes: reduce rechazos pero permitiría presentar historia reconstruida como cumplimiento observado. No satisface integridad ni trazabilidad.

Fuera de alcance: reparar automáticamente los dos proyectos reales, ejecutar nuevas reviews de sus MR, modificar permisos/configuración del harness, reconstruir memoria de agentes, emitir telemetría/heartbeats, estimar créditos, publicar comentarios o cambiar el visor independiente. Recuperar no autoriza corregir código, publicar, aprobar o mergear.

## 1. Contratos y separación de responsabilidades

Emitir archive **7** y final review **10**. Mantener lectura de archives 1–6 y resultados 1–9 sin migración ni reinterpretación de reglas. Trace **1**, packet **1** y manifest de workspace **1** conservan su estructura: reutilizar kinds/statuses/relations existentes para nuevos hitos; no añadir campos a eventos antiguos.

Archive 7 conserva ownership, scope, hashes, recursos y estados transaccionales actuales. Añade metadata acotada y validada:

| Metadata | Responsabilidad |
|---|---|
| profile_history | Selección inicial y transiciones inmutables, con identidad propia y referencia al evento que las registró |
| operation | Estado operativo open/paused/blocked/superseded/complete, motivo/fuente, fase pendiente y sucesor cuando corresponde |
| controller | Identidad del contexto coordinador declarada/observada y su fuente; no demuestra que un proceso esté vivo |
| checkpoint | Último snapshot provisional propio, inventario/hash, fase y errores conocidos de validación |
| lineage | new/restart/recovery y fuente exacta; previous_run conserva su vínculo y debe ser coherente |
| resource_claims | Recursos reclamados, vinculación a run/session y transferencia/liberación observada |

Los estados prepared/processing/retaining/closing/complete describen la transacción de almacenamiento. operation describe su disposición; open/processing no significa actividad viva. retained=true significa resultado canónico validado, no mera existencia de archivos. cleanup sigue pendiente hasta verificar la observación correspondiente.

Final 10 conserva IDs/veredictos/presentación/check.execution y amplía coverage.execution para enlazar historial de selección y asignaciones. El contrato documentará campos exactos, límites y normalización; cada asignación identifica la selección que la originó y una eventual sustitución autorizada. El historial final debe coincidir con los valores capturados en cierre y con sus eventos. profile es el perfil efectivo final, no un reemplazo de la selección inicial.

Los módulos de validación del resultado/procedencia siguen siendo puros. review_artifacts sigue siendo el único escritor durable; recovery coordina sus operaciones y verifica únicamente runs/recursos seleccionados. No crear un framework genérico ni redistribuir funciones ajenas al cambio.

## 2. Selección inicial y cambios de perfil

Extender el bootstrap autorizado a scope y selección mínima, dentro de la misma sesión propia: perfil, selection_source explicit/automatic, motivo concreto, fuente y actor conocido. No necesita repetir discovery ni crear un archivo permanente de planificación.

prepare acepta --profile-input con esa selección ya determinada y registra en una misma transacción la preparación y profile/selected. El fragmento de selección se conserva en profile_history de cierre, con ID estable S001, S002…; las referencias apuntan a ese fragmento propio. El tiempo del helper representa registro/captura lógica, no el momento inventado de una decisión humana. New archive 7 exige selección inicial; una entrada inválida falla antes de crear el run.

select-profile --selection-input registra una transición posterior en el mismo run. Incluye perfil anterior/nuevo, origen, motivo/fuente, fase, actor/autoridad pertinente y asignaciones afectadas. Captura la nueva selección y su evento atómicamente antes de utilizarla. Repetir la misma operación verificada es idempotente; una confirmación posterior no reemplaza la primera selección ni cambia su precedencia.

Reglas:

- Canonicalizar aliases economy/balanced al recibir la solicitud; nombres actuales focused/standard/deep/extended permanecen.
- Un perfil explícito cambia únicamente por una instrucción posterior del usuario vinculada a la transición. Esto respeta una modificación expresa del perfil solicitado, sin convertirla en selección automática.
- Una selección automática puede subir o bajar por hechos verificables que cambien su justificación, incluida una justificación inicial demostrada incorrecta. Urgencia, slots, cuota, costes o ausencia de findings no justifican downgrade.
- Un cambio de scope/base/head/snapshot no se disfraza de downgrade: requiere otro run y comparación de fuentes.
- Las asignaciones iniciadas/completadas y sus resultados conservan sus identidades/contextos. Un downgrade no borra evidencia ni cambia el perfil bajo el que se ejecutaron.
- Solo asignaciones todavía no iniciadas, cuya necesidad dejó de aplicar por una fuente concreta, pueden marcarse sustituidas. No se cancelan project gates ni verificaciones obligatorias ya adquiridas por trabajo iniciado.
- La cardinalidad y las reglas de independencia se comprueban sobre el historial y las obligaciones efectivas, no aplicando el último perfil retroactivamente a todos los resultados. La verificación más fuerte pendiente se mantiene cuando el historial la exige; no debe clasificarse como incumplimiento de focused por ser independiente.
- Una escalada reutiliza trabajo válido y modifica únicamente asignaciones necesarias; no inicia automáticamente otra revisión completa.

El reporte privado presenta perfil inicial y efectivo; añade la secuencia/motivos cuando difieren. El comentario público conserva su audiencia actual, sin metadata interna de perfiles o recuperación.

## 3. Gate temprano y registro de ejecutores

Antes de discovery/started, dispatch o checks, validar selección inicial capturada, scope, sesión propia y estado operativo que permite continuar. El record-event de archive 7 también aplica la precondición al primer trabajo; fallo conserva bytes/estado y devuelve un diagnóstico accionable. El coordinador registra discovery/started antes de despachar; el helper no puede interceptar herramientas arbitrarias fuera del flujo autorizado.

Un resumen libre con «perfil seleccionado» no sustituye la selección estructurada. Retención vuelve a comprobar historial, fuentes y obligaciones; el gate temprano no elimina el final.

register acepta --context-input para incorporar ejecutores verificados antes de sus comandos. Preserva el contrato de executor, revisión/snapshot, manifest, aislamiento y dependencias; static-only usa executors=[]. Revalida fuentes vivas antes de retener y bindings conservados después de limpiar. El cierre pendiente muestra ejecutores conocidos aunque falle la retención final.

La operación está pausada/bloqueada/sustituida: un nuevo trabajo requiere resume/recover con la autoridad y condiciones aplicables. Publicar o entregar requiere resultado canónico validado, aunque exista un checkpoint con veredicto.

## 4. Checkpoints y conservación provisional

checkpoint conserva únicamente contexto/packets/evidencias explícitamente seleccionados, con ownership, nombres seguros, límites y hashes. Puede incluir un JSON final estructuralmente válido y su informe generado aun cuando falle un gate de procedencia. Sin resultado final conserva contexto/packets parciales; no fabrica un veredicto ni renderiza un JSON incompleto como informe final.

Layout provisional propio: pending/context.json, pending/evidence/<basename>, opcional pending/review.json y pending/informe.md. Estos nombres nunca sustituyen los canónicos review.json/informe.md/evidence. El manifest distingue hashes provisionales y validados; el lector/visor puede reconocerlo por archive 7.

El checkpoint se actualiza con intención transaccional/hashes conocidos, rechazando datos ajenos o modificados. Conservar la selección/historial inmutable y las fuentes necesarias para sus obligaciones. No copiar dependencias, árboles de build, credenciales, scratch completo ni historia sin pertinencia.

Momentos: finalización de una tanda de discovery, verificación agrupada, pausa controlada o fallo de retención. Reutilizar esos hitos; no guardar cada búsqueda/llamada. El coste es IO seleccionado, sin más agentes ni sondeos.

Un crash puede perder trabajo posterior al último checkpoint; el diagnóstico lo expresa. Un fallo de ownership/hash no autoriza escribir dentro del run dañado. Se preservan las fuentes existentes y se informa qué recuperación queda bloqueada.

retain valida y promueve desde inputs/checkpoint propio comprobado. Los gates completos siguen siendo obligatorios; un registro tardío puede quedar conservado provisionalmente pero no volverse fulfilled/complete alterando la historia. No usar schemas antiguos, escritura nativa o fallbacks ficticios para eludir el rechazo.

## 5. Inspección, pausa y recuperación

inspect es de solo lectura: run/scope, integridad, selección, checkpoint, transacción pendiente, fuentes disponibles, recursos presentes/ausentes, obligaciones incompletas y acciones posibles con motivos. No restaura ni ejecuta agentes/checks. Información corrupta/ajena produce diagnóstico de integridad sin adoptarla como metadata fiable.

pause registra una parada solicitada, fuente/autoridad y fase; bloque registra un fallo observado y su causa. Un crash no registrado se describe como actividad desconocida/incompletitud observada, nunca como «fallo del harness» inferido del reloj. No inferir liveness a partir de processing ni consultar counters/PIDs periódicamente.

resume conserva el mismo ID cuando el scope no cambió y ownership/fuentes son verificables. Una pausa explícita requiere una instrucción de continuar; la invocación original no la revoca. Otro contexto/harness puede recuperar artifacts, pero no adquiere la memoria ni identidad de workers anteriores. Declara nuevo controller y preserva la procedencia original.

recover completa transacciones propias con sus bytes originales o presenta un plan acotado de continuación. Reutiliza packets/checks cuando su integridad e inputs son aplicables; las verificaciones restantes conservan sus requisitos de independencia. Ningún packet recuperado acredita un nuevo dispatch. Si faltan fuentes indispensables, repetir solo lo necesario; si la identidad/scope no puede establecerse, ofrecer reinicio.

Registro tardío: permitir preservar/inspeccionar las fuentes y la irregularidad, sin mover eventos, interpretar un summary como perfil estructurado ni inventar occurred_at. Cuando evidencia previa verificable permite continuar, capturar su fuente como recovered y mantener la reserva de procedencia. Si no permite satisfacer el gate de historial, el resultado sigue provisional y se ofrece un nuevo run vinculado con trabajo reutilizado explícitamente; no se certifica el historial original como íntegro.

restart crea un nuevo run con perfil inicial correcto y lineage/previous_run hacia la fuente. Reutilizar evidencia existente requiere copias seleccionadas/hashes y declarar su origen/reuso; las obligaciones de un review nuevo no se satisfacen inventando agentes nuevos. Un review completo es inmutable; repetirlo crea otro ID.

Archives 1–6: inspect/read y recuperación de sus transacciones ya admitidas se conservan. Nuevos campos no se escriben retroactivamente. Una recuperación ampliada/reinicio crea archive 7 vinculado y retiene fuentes históricas seleccionadas intactas. La operación sucesora describe qué reemplaza sin hacer pasar el historial anterior por archive 7.

## 6. Exclusión y continuidad de recursos

Todas las mutaciones de un run necesitan un bloqueo de operación exclusivo con liberación al terminar/fallar. Para operaciones entre dos runs, adquirir sus bloqueos en orden estable; no mantener un proceso auxiliar ni heartbeat. Otro escritor recibe conflicto y conserva los datos.

controller identifica quién conduce el run, no prueba liveness. Un contexto distinto no toma control silenciosamente: debe establecer que el anterior terminó o recibir confirmación explícita para la recuperación. Una instrucción clara de continuar/reiniciar puede aportar autoridad; con actividad concurrente desconocida se solicita aclaración antes de despachar o limpiar.

Para sesiones temporales propias, añadir un claim lateral separado del manifest de workspace 1: .review-run-owner.json, vinculado a session/owner token y run durable. Es metadata privada de ownership. El bootstrap sin run permite preparación acotada; prepare/register completa el claim antes del trabajo. Dos runs no pueden reclamar silenciosamente el mismo recurso.

Transferir recursos a un sucesor exige identidad/ownership verificados, autorización de reinicio/recuperación y un intento transaccional bound a ambos runs y al claim original. Registrar origen/destino y estado sustituido del run abierto compatible. Un fallo entre escrituras deja intención verificable; ningún run continúa ni limpia hasta terminarla. No crear un índice global de recursos ni recorrer todos los proyectos.

El cleanup solo elimina recursos cuyo claim corresponde al run que lo solicita. Registrar la eliminación/liberación observada antes de cerrar. La ausencia de una ruta ajena no acredita cleanup propio. Para archivos históricos sin claim, la adopción requiere comprobación de la sesión y autoridad explícita, registrada en el sucesor; fuentes históricas permanecen intactas.

## 7. Detección de reviews existentes y vigencia

Antes de prepare, buscar candidatos únicamente bajo repository_key y grupo de scope/MR solicitado, leyendo primero cierres. Un CR/run explícito tiene prioridad. La coincidencia incluye modo, base/head/snapshot, target y límites solicitados; comparar fuentes relevantes de descripción, requisitos/spec/plan, configuración y estrategia solicitada antes de declarar aplicabilidad.

Mismo MR, SHA o finding ID no demuestra vigencia. El review disponible puede seguir conteniendo defectos: «vigente» significa aplicable a esos inputs, no aprobable. No llamar actual a un reporte si no se contrastó con las fuentes actuales disponibles.

| Caso | Decisión del coordinador |
|---|---|
| Completo, íntegro y aplicable | Preguntar mostrar reporte existente o revisar de nuevo; una solicitud explícita de repetir resuelve la elección |
| Incompleto recuperable | Mostrar fase/datos disponibles y preguntar continuar o reiniciar |
| Varios candidatos | Identificar IDs/relaciones y pedir selección; no escoger únicamente por timestamp |
| Inputs cambiados | Proponer re-review vinculado, reusar evidencia no afectada y comprobar el delta |
| Integridad/fuentes no verificables | Explicar límite y ofrecer reinicio conservando lo existente |
| Petición solo de mostrar reporte | Leer y mostrar el ID/versión solicitados; no ejecutar reviews ni afirmar frescura desconocida |

Una petición general de review no implica reutilización automática de uno anterior. Mostrar solo el reporte no publica, entrega full/brief ni limpia recursos. Un perfil solicitado distinto a la cobertura existente se comunica antes de ofrecerlo como sustituto.

Lookup tiene paginación/límites explícitos y expone candidatos adicionales; no considera exhaustiva una página truncada. No recorre todo el archivo, carga todos los informes, añade caché de contexto entre reviews ni hace llamadas remotas redundantes.

## 8. Diagnóstico, documentación e integración

Errores mantienen mensaje compatible y añaden código, fase, run/review ID, inventario disponible, gate fallido y acciones válidas. Cuando sea seguro, incluir las rutas exactas en diagnóstico privado; no exponer datos privados en comentario/delivery.

La respuesta privada separa juicio del código, conservación provisional/validada, cumplimiento y cierre. El informe incorpora perfil inicial/efectivo e historial necesario. El resultado canónico no cambia un veredicto de código solo porque el registro durable falló; una falta material de evidencia/gate del proyecto mantiene sus consecuencias habituales.

Mantener SKILL.md como router breve. Documentar operaciones/contratos en references/archive/artifacts.md y una referencia de recuperación cargada solo ante continuidad/candidatos; política de perfiles en profiles.md; adaptar workspaces, ejecución, report-format, re-review y contratos/delivery/publicación. README explica finalidad con brevedad y enlaza docs/usage; detalles CLI/ejemplos viven en docs/referencias.

Los consumidores deben admitir archive 7/final 10 para nuevos resultados y pending; avisarlo en changelog/compatibilidad. No afirmar que el visor independiente ya lo admite ni modificarlo en este proyecto. Históricos conservan lectura/renderizado y hashes; ninguna migración automática.

## 9. Validación y aceptación

TDD con Python estándar, repositorios/worktrees y packets sintéticos. No usar artifacts reales como destino ni repetir suites/product reviews para probar el helper. Pruebas de comportamiento/bytes/efectos, no assertions que solo repitan instrucciones.

| Escenario | Resultado exigido |
|---|---|
| Inicio sin selección válida | Falla antes de crear run/iniciar trabajo según la operación; datos anteriores intactos |
| Prepare + selección y crash en escritura | Recuperación propia idempotente; sin evento omitido/duplicado ni adopción ajena |
| Selección repetida | La primera selección permanece; reintento no altera precedencia |
| Upgrade/downgrade antes y después de trabajo | Historial completo, resultados preservados y obligaciones no eludidas |
| Perfil explícito cambia sin instrucción | Rechazo; cambio autorizado queda vinculado a su fuente |
| Retain falla como !42 | Resultado seleccionado recuperable en pending, retained=false, fuentes/traza intactas, delivery/cierre bloqueados |
| Pausa solicitada | Sin nueva ejecución hasta autorización de continuar |
| Crash antes/después de checkpoint/retain/close | Inspección read-only; recuperación de bytes propios, sin timestamps reconstruidos |
| Recovery en otro harness | Reuso de artifacts con origen; sin memoria/independencia nueva ficticia |
| Dos writers/claims como !785 | Conflicto o transferencia explícita; continuidad y cleanup atribuibles |
| Recursos ausentes, modificados o ajenos | Diagnóstico específico; ninguna eliminación ni adopción automática |
| Mismo scope completo | Elección mostrar/nuevo, sin discovery/ejecución por mostrar |
| Head/base/snapshot/description/requisitos cambiados | Diferencia identificada; reuso acotado o nuevo review, sin vigencia falsa |
| Fuentes sin integridad | Preservación del original; ninguna certificación/fallback legacy |
| Archives 1–6/resultados 1–9 | Lectura y comportamiento histórico conservados; sin cambios de bytes |

Gate final: tests focalizados RED→GREEN, suite integrada, CLI help, AST, enlaces locales y diff check. Una revisión independiente acotada de la rama completa antes del PR, con correcciones/regresiones para causas confirmadas. No barridos completos duplicados, agentes por cada gate ni mediciones de tokens.

Entrega: commits descriptivos, push y PR conforme a la plantilla, adjunto al chat y abierto para validación humana. Conservar worktree mientras llegan comentarios. Merge/tag/release y limpieza posterior siguen la autorización correspondiente; main tiene regla de cambios mediante PR.

## Base y autorrevisión de esta especificación

Suite antes de implementación sobre `5507c48`: 317 tests en 264.225 s, 316 aprobados/1 omitido por permisos de symlinks en Windows, exit 0. Este resultado no se atribuye a una implementación nueva.

- Cobertura: selección/transiciones y gate temprano (§2–3), conservación provisional (§4), recuperación/estado (§5), recursos (§6), detección/vigencia (§7), diagnóstico y validación (§8–9).
- Separación: provisional no equivale a retenido; operation no equivale a proceso vivo; cambiar perfil no altera scope ni eventos antiguos.
- Compatibilidad: nuevos contratos delimitados; fuentes históricas y completed runs permanecen intactos; módulos puros no hacen IO.
- Economía: lectura por necesidad, checkpoints en hitos existentes, reutilización explicitada y control sin polling/caché/telemetría.
- Estado: especificación escrita, autorrevisada y aprobada por el usuario el 2026-10-13. Preparar el plan; su revisión precede a la implementación.
