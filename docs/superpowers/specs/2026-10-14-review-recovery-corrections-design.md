# Review Recovery Corrections Design

**Estado:** propuesta escrita y autorrevisada; pendiente de aprobación antes de implementar.

**Objetivo:** corregir las garantías de recuperación, perfiles, recursos y vigencia de la 2.12.0 pendiente, atendiendo el review del PR #19 sin convertir resultados provisionales en revisiones certificadas.

**Base:** `feat/review-recovery-lifecycle`, commit `b758c559143776b610469e2103a24be48ef2c182`, en `.worktrees/review-recovery-lifecycle`.

**Referencias:** [review del PR #19](https://github.com/omarfrancodev/comprehensive-code-review/pull/19#issuecomment-6159108237), [diseño aprobado](2026-10-13-profile-lifecycle-recovery-design.md), [plan original](../plans/2026-10-13-profile-lifecycle-recovery.md).

## 1. Contexto, alcance y enfoque

El review registró 33 hallazgos: 3 P1, 15 P2 y 15 P3. Cuatro se marcaron bloqueantes: F003, F010, F032 y F033. Las comprobaciones focalizadas confirmaron los cuatro y otros escenarios de alias 8.3, nombres insensibles a mayúsculas, recibos repetidos, compatibilidad de register, transferencias encadenadas/parciales, reinicios huérfanos y discrepancias entre lookup e inspect. No se repitió la suite completa ni se alteraron artifacts reales.

La suite anterior de 385 pruebas es evidencia de aquella ejecución, no prueba de estas garantías. Sus dos omisiones corresponden a los permisos de aquel host; la ejecución externa con una omisión no invalida ese registro. Los nuevos resultados se documentarán por separado.

Se consideraron tres enfoques:

1. **Corregir causas y cubrir secuencias completas, recomendado.** Mantiene el subsistema existente, unifica criterios y añade únicamente el estado durable necesario para reintentos. Cada tarea contiene regresiones de comportamiento.
2. **Parchear los 33 síntomas aisladamente.** Menor cambio inicial, pero deja discrepancias entre registro, transferencia, cleanup, reinicio y vigencia; aumenta el riesgo de otra review con los mismos problemas.
3. **Sustituirlo por un gestor general de workflows.** Implica migración, dependencias y más mantenimiento del que requiere el problema; queda fuera del alcance.

Esta especificación complementa y, donde precisa una regla, reemplaza el diseño anterior para estas correcciones. No autoriza implementar, fusionar, publicar ni modificar otros proyectos. El usuario solicitó crear conjuntamente spec y plan; ambos se presentan para revisión antes de ejecutar.

### Restricciones globales

- Mantener 2.12.0 pendiente, archive schema **7**, final schema **10**, trace **1**, packet **1** y workspace manifest **1**. Los campos privados adicionales pertenecen al contrato 7 aún no publicado; documentarlos antes del merge.
- Conservar lectura y comportamiento histórico de archives **1–6** y resultados **1–9**, sin migración ni campos nuevos escritos retroactivamente en esos archives. Un archivo completo permanece inmutable.
- Python **3.10+**, biblioteca estándar, Git y unittest; sin dependencias nuevas, daemon, polling, métricas, índice global ni un agente por hallazgo.
- Cambios en el mismo worktree/rama/PR. No tocar artifacts reales, configuración de harness, el visor ni main. No merge/tag/release durante la implementación.
- Los módulos de validación no escriben archivos. `review_artifacts.py` sigue siendo el escritor del archivo durable; workspace cleanup elimina exclusivamente sus recursos verificados y comunica observaciones al helper.
- Ninguna ruta ausente acredita por sí sola cleanup. Un archivo temporal con un nombre parecido no acredita ownership. No reconstruir dispatch, identidad, tiempos de ocurrencia ni autoridad desde texto libre.
- La recuperación de una transacción no acredita vigencia ni cumplimiento del perfil. Cambiar scope/base/head/snapshot requiere otro run.

## 2. Exclusión, escrituras y checkpoints

### 2.1 Identidad del lock y rechazo sin efectos

Derivar identidad y ubicación de locks de la misma ruta canónica que verifica el archivo: comprobar enlaces/reparse points, resolver la ruta y aplicar normcase. Las grafías larga/corta 8.3 de un mismo run comparten lock, también entre procesos. Mantener locks no bloqueantes y reentrada del mismo contexto; operaciones entre runs adquieren el conjunto en orden estable.

Los mutadores verifican marker/manifest en modo lectura antes de crear locks o cualquier directorio. Después de adquirirlos vuelven a cargar/verificar los datos. Una ruta ajena o incompleta sin una intención de preparación propia se rechaza sin escribir `.review-locks` en su padre.

### 2.2 Staging atribuible

`atomic_write` elimina su staging en `finally` ante fallos ordinarios de write, flush, fsync, validación o replace, conservando el destino previo y el error original. Si la eliminación también falla, el diagnóstico informa el staging conservado; no declara éxito.

Para checkpoint, la intención durable declara antes de escribir cada staging exacto, su destino y hash esperado. Un staging es desechable, nunca evidencia comprometida ni una fuente válida. La lectura reconoce únicamente nombres incluidos en esa intención verificada; no acepta ni borra archivos por una expresión regular de nombre.

`inspect` no elimina staging. `recover` puede retirar un staging regular autorizado por la intención y reintentar desde bytes completos con hash válido, o pedir los inputs originales cuando falten. Un staging parcial no se promueve. Una ruta ajena, enlace o destino fuera de la intención produce preserve. Transactions 7 previas sin este inventario siguen siendo inspeccionables; sus temporales no registrados no adquieren ownership por actualización.

### 2.3 Inventario y límites antes de mutar

Deduplicar nombres de destino con casefold, tanto en checkpoint como en retención, incluyendo contexto y nombres reservados. Validar todo el inventario antes de guardar una intención. Una colisión no deja un checkpoint pendiente.

Mantener el límite existente de **64** evidencias seleccionadas y **64 MiB** de evidencia de checkpoint. Comprobar tamaño contra el presupuesto restante antes de leer; la lectura usa un tope de presupuesto+1 para detectar crecimiento concurrente. Contexto y resultado JSON también se leen con sus límites respectivos antes del parseo. Archivos grandes o cambiados fallan sin mutar el run ni cargar sus bytes completos.

Un checkpoint interrumpido no bloquea un reinicio enlazado si su intención/ownership y los bytes disponibles son verificables como provisionales. Recuperar sus bytes propios tampoco requiere fingir que el HEAD actual sigue siendo el original. Si ownership y scope del origen siguen verificados pero sus fuentes no lo están, un reinicio explícito puede conservar únicamente el vínculo: no copia/promueve sus bytes ni reescribe ese origen. Esta separación elimina el rechazo circular recover→restart→checkpoint.

## 3. Asignaciones iniciadas y obligaciones de perfil

Capturar `execution_plan` en el contexto antes del trabajo por asignación, con las mismas filas del plan final: `id`, `role`, `independent`, `required`, `reference`, `selection_id`, `superseded_by`. Archive 7 conserva un `assignment_registry` derivado de esa captura. No se crea otro archivo de auditoría.

El registro conserva filas previas y sus referencias, selección e identidad; agregar asignaciones no permite eliminar las anteriores. Una sustitución solo se admite con selección/fuente válida, necesidad que dejó de aplicar y ausencia de trabajo iniciado/completado. Project gates no se sustituyen. Retención contrasta registro, contexto, plan final, packets y eventos; el contexto final tampoco puede borrar filas para eludir este gate.

Las fuentes de eventos observados se resuelven contra el registro completo, no solo contra las filas que sobrevivieron en el plan final. Una asignación iniciada/completada ausente del plan final es error. Las referencias y resultados de esa asignación siguen seleccionados para conservación. Una transición no puede preceder ficticiamente su trabajo ni cambiar sus IDs/contextos.

Un hito general de preparación o `discovery/started` sin fuente de asignación no demuestra por sí solo una asignación independiente y no obliga a inventarla. Los eventos usados para acreditar trabajo por asignación necesitan el brief/resultado registrado. Una fuente que identifica un brief observado pero no tiene identidad de asignación verificable se diagnostica como faltante; nunca se ignora para declarar fulfilled.

Las obligaciones son el máximo de los mínimos de discovery y requisitos de independencia/verificación de las selecciones que adquirieron trabajo, junto con la selección efectiva final. `extended` automático adquirido mantiene su mínimo de **4**; una fila posterior explícita no lo reduce a **2**. Reusar discovery válido permite satisfacer obligaciones; no exige repetirlo.

Conservar una pasada de focused no la convierte en descubrimiento independiente de deep: se mantiene como trabajo previo y no cuenta para su cuota de perspectivas independientes. Los máximos se aplican a las asignaciones que satisfacen la estrategia efectiva, no a la cantidad de filas históricas conservadas. Una verificación completada antes de nuevos discoveries se conserva, pero no sustituye la verificación agrupada posterior; debe existir una verificación efectiva para la tanda final, sin borrar las anteriores para conseguir cardinalidad uno.

Toda selección explícita requiere una fuente de usuario verificable. Una selección posterior explícita requiere autoridad incluso si conserva el mismo nombre de perfil o solo cambia automatic→explicit. La selección inicial, los IDs S001… y sus eventos permanecen inmutables. Un downgrade automático justificado sigue permitido; urgencia, coste, slots o ausencia de findings no son justificación.

Validadores comprueban tipos antes de usar dict/set: perfiles, IDs, fases, actor, eventos y vínculos malformados devuelven errores acotados, no TypeError. Final 10 mantiene su forma; el registro durable y las fuentes aportan el contraste que un JSON final aislado no puede demostrar.

## 4. Un criterio de inputs, integridad y vigencia

### 4.1 Forma común

Lookup, inspect, resume, recover y restart aceptan el mismo archivo de inputs actuales:

```json
{
  "scope": {"repository": "group/project", "mode": "mr", "base": "base-sha", "head": "head-sha", "snapshot": null, "target": "develop", "reference": "https://git.example/group/project/-/merge_requests/42"},
  "sources": {"evidence/requirements.md": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},
  "source_set_complete": true,
  "description_identity": "captured-description",
  "requirements_identity": "captured-requirements",
  "plan_identity": "captured-plan",
  "configuration_identity": "captured-configuration",
  "profile": "standard"
}
```

Scope y sources son obligatorios. `source_set_complete` y las identidades adicionales son opcionales: omitir completitud produce unknown, no verified. Se acepta la forma mínima histórica `{scope, sources}` para lectura/diagnóstico, sin interpretarla como confirmación completa.

Fuentes externas pertinentes son los inputs de la revisión, no todo lo guardado en evidence. Archive 7 conserva `review_inputs` desde prepare o el contexto inicial de register: conjunto de fuentes declaradas, completitud e identidades realmente observadas. Se verifica el vínculo entre hash declarado y bytes seleccionados al hacer checkpoint/retain. Contexto, briefs, resultados y reproducciones generados por el run conservan integridad propia pero no se convierten automáticamente en inputs externos.

La captura inicial puede completarse antes del trabajo; después no se sobrescriben identidades conocidas para hacer parecer vigente un review. Un cambio real conduce a re-review/restart. El perfil actual se compara con el historial autorizado; modificarlo no reescribe la selección inicial.

### 4.2 Appraisal compartida

Normalizar y comparar inputs en un solo módulo puro. Resultado: `applicable`, `changed` o `unknown`, con diferencias por campo. Inspect expone freshness `verified` únicamente para applicable; scope igual y sources vacío sin completitud no basta. Un conjunto vacío explícitamente completo puede ser applicable cuando realmente no hay fuentes externas pendientes. Una identidad pertinente capturada en el origen pero omitida en los inputs actuales deja unknown; null solo acredita no aplicabilidad cuando fue observado y declarado en ambos, no por ausencia del campo.

Resume/trabajo nuevo exige applicable. Recover puede completar bytes de una intención propia aunque los inputs actuales hayan cambiado, pero devuelve el cambio y dirige a restart; no devuelve permiso de continuar. Restart admite cambio dentro del mismo repositorio y conserva el original.

El límite de **64** entradas corresponde al mapa del llamador. No se aplica al inventario completo de evidencia retenida para clasificar integridad. Un archive con 65 o 70 evidencias no pasa a invalid por ese motivo. La lectura histórica sin captura de fuentes/identidades permanece unknown; no reconstruye información desde prosa ni exige recapturar artefactos internos como si fueran inputs actuales.

Integridad, vigencia y disponibilidad de recursos son resultados diferentes. Reporte íntegro con inputs desconocidos puede mostrarse como histórico; ningún indicador declara un proceso vivo. Mantener lookup local, paginación y ausencia de selección automática.

## 5. Registro y transferencia de workspaces

Preflight de prepare/register/retain usa el mismo verificador de sesión/claim. Una sesión reclamada por otro run se rechaza antes de mutar. Prepare puede vincular un bootstrap válido; una sesión histórica sin claim exige adopción autorizada. Retain no adopta recursos tarde: pide registro previo. Para schemas 1–6 se conserva la ruta histórica de registro y no se agregan claims ni campos 7.

Conservar transferencias por `transfer_id` en `resource_transfers`, máximo **64** por run y una pendiente como máximo. Cada registro guarda origen, destino, rutas exactas, autoridad, controlador y hashes. Un límite alcanzado falla antes de mutar; no descarta historial. Una lectura del slot 7 anterior `resource_transfer` se normaliza para diagnóstico/reintento, sin reescribir automáticamente el archivo.

Una transferencia completada se reintenta solo con el mismo request verificado. Rutas, autoridad, controlador o runs distintos producen conflicto explícito; nunca éxito con las rutas de una petición anterior. Una nueva transferencia B→C puede coexistir con la entrada completada A→B.

Para sustituir un run, deben seleccionarse todos sus claims activos presentes. Se rechaza transferencia parcial antes de crear intención o modificar ownership; esta política evita claims huérfanos en un origen superseded. Recursos ausentes se diagnostican separadamente conforme a §6, no se simulan como transferidos.

Origen y sucesor deben estar prepared/processing y operativamente compatibles, en el mismo repositorio/scope; nunca retaining/closing/complete. El sucesor tiene previous_run nulo o igual al origen y lineage coherente. Register del receptor conserva transfer_id y no altera los campos verificados del sidecar. La secuencia A→B→register(B)→C es soportada.

Cambio de scope con workspaces existentes: restart conserva esos recursos en el origen, sin transferirlos ni usarlos como workspace de la nueva versión. No obliga a eliminar evidencia del origen para crear el review nuevo.

## 6. Cleanup, recibos y recursos ausentes

Workspace cleanup con claim requiere `--run-dir`. Adquiere el lock canónico de ese run durante verificación, eliminación y registro del resultado; no puede competir con una transferencia.

Antes de eliminar registra una intención durable ligada al claim verificado y a las worktree registrations esperadas. Después registra el recibo de liberación observado en el archive, antes de retornar. El recibo conserva `session_id`, `run_id`, `claim_id`, `claim_sha256`; su ejecución no depende de que la sesión borrada sobreviva para guardar un archivo.

Si hay fallo entre eliminación y persistencia final, el intento propio permite recuperar la observación mediante ausencia verificada de sesión y registrations esperadas. Se registra como observación recuperada, sin inventar quién ejecutó cada instrucción ni occurred_at. Si hay bytes ajenos, rutas presentes modificadas o falta intención/recibo, preservar.

Close consume recibos durables por defecto. Se mantiene `--cleanup-file` con `{cleanup, residuals, released_claims}` para observaciones existentes; se añade `--released-claims-input` a la vía inline. No requiere construir recibos a mano ni autoriza fabricarlos. Errores nombran el claim y el campo/operación faltante.

Validar un recibo ya aplicado, exactamente igual, es idempotente; uno diferente o de otro run falla. Interrupciones antes/después de reescribir review/informe/manifest y replay de close sobre complete mantienen el mismo resultado y hashes. La aceptación de un replay no evita el gate de integridad/fuentes completas.

Una sesión ausente sin recibo se expone como `missing_unknown`. No se marca released/cleanup complete. Con autoridad explícita puede crearse un reinicio enlazado sin transferir esa ruta, preservando el diagnóstico del origen. Continuar el mismo run necesita inputs aplicables y recursos nuevos verificados para cualquier ejecución pendiente; los ejecutores anteriores no se relabelan. Inspect anuncia las mismas condiciones que aplican los mutadores.

Un claim transferred no significa que su ruta deba desaparecer: su propietario es el sucesor registrado. Nunca se elimina desde el origen. La verificación contrasta el destino y su sidecar, no transforma su presencia en un supuesto recurso reaparecido del origen.

## 7. Reinicio durable y controladores

Mantener una intención acotada de reinicio por petición, antes de crear el sucesor. Vive bajo `.restart-intents` en el grupo local de scope de origen; su identidad deriva del origen canónico y del digest de la petición normalizada. Es metadata privada de una operación, no un índice global ni un nuevo review.

La intención, protegida por ownership/hash, contiene source, request digest, selección, autoridad, controlador, inputs actuales, transfer_paths y la identidad/ruta exacta reservada del sucesor. Así se puede reintentar sin buscar runs por fecha ni crear otro ID. Para orígenes históricos/completos se usa esta operación separada y no se altera el original.

El directorio local de ese origen conserva `active.json`, un descriptor propio de la única operación pendiente. Vincula el intent exacto y sus hashes anteriores/nuevos autorizados; el mismo protocolo de ownership/intención protege interrupciones entre reemplazos. Los mutadores consultan únicamente ese descriptor bajo el lock del origen y rechazan trabajo/cleanup/transfer ajenos mientras esté pendiente. No necesitan buscar todas las intenciones ni escribir un flag nuevo en un source histórico/completo. Finalizar conserva el intent y retira el bloqueo operativo de forma reintentable; pendiente no significa proceso vivo.

Secuencia: preflight de todos los inputs/recursos → guardar intención bajo lock del origen → reservar destino con su marker de preparación propio → adquirir locks del par en orden estable → completar prepare del destino exacto → transferir/adoptar y enlazar → marcar operación completada. Ningún sucesor inicia trabajo mientras su preparación de reinicio esté pendiente.

Un crash en cualquier límite deja una intención recuperable. Dos coordinadores con la misma petición obtienen conflicto o el mismo sucesor; una petición incompatible no sobrescribe la primera. No borrar un sucesor con evidencia para resolver un fallo. Si la reserva está ocupada por datos ajenos, preservar y diagnosticar, sin escoger otro destino silenciosamente.

Register acepta contexto estructurado mediante la API interna existente de inputs objeto/ruta. La rama de adopción valida antes de crear el sucesor y no trata un dict como path. El linaje registra el origen exacto; no copia findings/checks/resultados como trabajo actual.

Un controlador diferente requiere autoridad y un evento de takeover durable, común a resume/recover. Recover no debe aceptar B y devolver ready mientras sigue registrando A. Completar una intención no simula dispatch ni memoria de workers anteriores. Para un original completo no se actualiza su controlador; un sucesor registra el suyo.

Restart recibe el harness de la ejecución actual, por argumentos explícitos o resolución del entorno vigente, con su harness_source real. La identidad del origen permanece en el linaje/archivo original. No copia su ID rotulándolo como un argumento que nadie pasó.

## 8. Diagnóstico, documentación y entrega

Validar objetos/tipos antes de pre-gates. Retain/checkpoint/final validator producen errores JSON/listas acotadas para listas, cadenas, coverage/execution malformados y campos no hashables. Normalizar `review_workspace.ReviewError` en la frontera de claims; inspect devuelve invalid/preserve, no traceback. Archives 1–2 sin run_id devuelven review_id null, sin inventarlo.

Actualizar referencias y ejemplos completos: prepare con selección e inputs, register con contexto/historial/plan, select-profile con fases/campos/autoridad/límite **32**, checkpoint, lookup/inspect comunes, cleanup con run-dir y recibos, close inline/file y recovery/restart. `record-event` no registra selecciones de perfil de archive 7; eso corresponde a select-profile.

Precisar el downgrade válido en profiles.md; F012 es una aclaración de la política aprobada, no autorización para evadir verificación. Full conserva JSON, historial y bindings; brief conserva su síntesis y vínculo con el original, sin prometer un historial completo que no entrega. No aumentar el brief con metadata de ejecución. El comentario público sigue excluyendo mechanics de recuperación/ejecución.

Actualizar la descripción del PR alrededor del comportamiento corregido y de los límites verificados. No cambiar fechas/resultado de validaciones anteriores para hacerlas coincidir con otra máquina.

## 9. Cobertura del feedback y aceptación

| Causa | Hallazgos | Exigencia principal |
|---|---|---|
| Locks/staging/checkpoint | F001, F002, F003, F004, F009 | Exclusión canónica, rechazo sin escrituras, staging propio recuperable y lecturas acotadas |
| Asignaciones/perfiles | F010, F011, F015 | Registro contrastado con trabajo observado; autoridad y obligaciones no eludibles |
| Registro/transferencia | F006, F018, F019, F020, F021, F029, F031 | Compatibilidad, cadenas, replay exacto y ownership/linaje coherentes |
| Cleanup/disponibilidad | F005, F017, F033 | Recibos durables/idempotentes; ausencia desconocida no es cleanup |
| Reinicio/controlador/harness | F007, F025, F027, F028, F032 | Un sucesor por intento, mantenimiento separado de vigencia y takeover observable |
| Inputs/vigencia | F022, F023, F024, F035 | Igual appraisal entre operaciones; fuentes externas separadas de outputs |
| Diagnóstico/históricos | F008, F026, F034 | Errores estructurados e inspección de todos los schemas legibles |
| Documentación/proyección | F012, F013, F014 | Ejemplos ejecutables y promesas acordes con full/brief |

Probar fallos internos de write/fsync/replace, no únicamente excepciones antes/después de atomic_write. Probar eventos omitidos, transferencias entrantes/salientes, cleanup repetido, cambio de controlador/harness, inputs modificados con mismo HEAD, muchos outputs y reinicio con checkpoint pendiente.

Pruebas integradas obligatorias: A→B→register(B)→C→retain(C)→cleanup(C)→close(C)→close(C); interrupciones de restart/cleanup/checkpoint y reintento; source completo/histórico permanece byte a byte igual. Una review nueva no hereda cumplimiento ficticio de sus predecesores.

Gate: RED→GREEN por causa, suite integrada después del último cambio funcional, CLI help/ejemplos, AST, enlaces y diff check; actualizar el mismo PR. Una revisión independiente posterior debe contrastar estas secuencias en el HEAD corregido antes de aprobar/mergear. Registrar pruebas omitidas, límites de plataforma y casos no reproducidos.

## 10. Autorrevisión y handoff

- Los 33 IDs quedan mapeados; no se consideran 33 tareas independientes.
- Se preservan provisional/retained, integridad/vigencia, missing/released y heredado/actual como distinciones verificables.
- Nuevos registros privados tienen responsabilidad concreta: assignments, inputs, transfer/release/restart intents. No añaden telemetría ni barridos globales.
- Los campos/CLI se implementarán en la 2.12.0 aún no publicada, con compatibilidad histórica explícita y sin migración automática.
- Estado: spec autorrevisada; el [plan de correcciones](../plans/2026-10-14-review-recovery-corrections.md) se presenta junto a ella por solicitud expresa del usuario. Ambos requieren revisión antes de implementar; no atribuir aprobación al acto de crear los documentos.
