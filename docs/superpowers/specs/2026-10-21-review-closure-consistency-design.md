# Consistencia de fuentes, despachos y cierre de revisiones

Fecha: 2026-10-21. Revisión: 2026-10-23. Estado: implementación terminada; pruebas focalizadas aprobadas y suite completa inconclusa.

## 1. Intención y alcance

Se busca que una revisión con entradas válidas llegue desde preparación hasta cierre sin perder fuentes seleccionadas ni volver a registrar despachos y resultados para satisfacer una validación tardía. Los errores de preparación deben aparecer antes de lanzar revisores; una corrección administrativa debe conservar los resultados ya obtenidos y su procedencia.

El usuario solicitó crear un worktree desde main y producir este spec y su plan; después pidió implementar los documentos actualizados. La implementación se realiza en el mismo worktree, con validación y evidencia registradas en el plan y el informe de validación.

Base: `9c3fd6bd7e3a21226e2fcd6dca65c42f512bceea`, main, CCR 3.0.0. Rama documental: `docs/review-closure-consistency`.

## 2. Evidencia y límites del diagnóstico

El caso auditado quedó retenido con `state=closing`, `retained=true` y limpieza pendiente. El índice inicial declaraba una descripción y notas, pero `review_inputs.sources` sólo incluía el propio índice. Ambos documentos sí estaban en el inventario de evidencia retenida con sus hashes. La validación posterior rechazó ambas entradas como fuentes no seleccionadas.

También se observaron cuatro despachos originales sin `executor`, cuatro resultados originales y ocho eventos posteriores que repetían las parejas despacho/resultado. Los resúmenes identificaban el re-registro y el uso de los mismos paquetes. La traza demuestra re-registro; no demuestra otra ejecución de los revisores. No se inspeccionó una transcripción completa del proveedor que permita certificar la identidad real de los procesos o sus modelos.

El diagnóstico original se realizó sobre CCR 2.14.0 (`fd38df82`). La revisión contra main del 2026-10-23 confirma que CCR 3.0.0 ya modulariza los scripts, pero conserva los cuatro mecanismos siguientes. La modularización y la entrada CLI única no son trabajo pendiente de este spec.

Mecanismos que permanecen en la base actual:

- `scripts/ccr/workflow/setup.py::_validate_session_reference_index` comprueba archivos y hashes, pero sólo exige capturar el digest del índice en `review_inputs.sources`.
- `scripts/ccr/contracts/material_inputs.py::validate_material_inputs` exige captura inicial de la descripción para declarar `aligned` o `needs_update`; una descripción `unverified` no adquiere esa certificación por estar archivada después.
- `scripts/ccr/archive/retention.py::_execution_gate` recibe los bytes seleccionados durante retain. Al ser llamado con `contents={}` desde validate/close, reconstruye las referencias solicitadas sin incorporar todas las entradas del índice. Por ello retain y la validación posterior pueden resolver conjuntos diferentes.
- `scripts/ccr/contracts/preflight.py::validate_assignment_event` exige el brief, pero admite un despacho independiente sin identidad de ejecutor. La falta se descubre en `scripts/ccr/contracts/execution.py::validate_execution_sources`, que exige un despacho con el mismo contexto/proveedor y secuencia anterior al resultado.

La decisión de conservar workspaces cuando falla el gate de retención fue correcta. Este trabajo no cambia ese comportamiento.

## 3. Enfoques considerados

1. Mejorar sólo las instrucciones: coste pequeño, pero seguirían siendo posibles la asimetría retain/validate y los rechazos tardíos.
2. Compartir la selección de fuentes, construir la captura inicial y validar despachos al registrarlos; ofrecer una anotación acotada para identidad omitida. Es el enfoque elegido: corrige los puntos de entrada y conserva las garantías existentes.
3. Completar retrospectivamente inputs, reescribir eventos o repetir toda la revisión. Se descarta: cambiaría la procedencia inicial o gastaría ejecución para corregir metadata.

## 4. Restricciones globales

- Python 3.10+ y biblioteca estándar; no añadir dependencias de ejecución.
- Respetar el paquete `scripts/ccr`, las 12 áreas CLI existentes y la entrada `python <skill>/scripts AREA SUBCOMMAND`; no restaurar scripts `review_*.py` ni facades agregadas.
- Mantener contratos puros sin IO, sin imports de `ccr.cli` desde módulos de implementación y sin ciclos; `archive.resources` coordina cleanup y `execution.workspaces` las operaciones físicas. Documentar cada módulo nuevo en `scripts/README.md`.
- Mantener archive schema 8/layout 2, final schema 10 y trace schema 1; añadir sólo el tipo externo explícito dispatch-identity para las anotaciones nuevas, sin migrar ni reescribir historia. Los helpers anteriores necesitan actualizarse para leer ese valor nuevo.
- Los runs completos son inmutables; ningún cambio de este trabajo modifica sus bytes.
- No inferir identidades, timestamps, modelos, independencia ni resultados a partir de nombres de archivos, briefs o resúmenes.
- Las lecturas se limitan a fuentes explícitamente seleccionadas o declaradas en el inventario de hashes del run exacto; no recorrer otros archives, historias del proveedor ni árboles completos.
- Mantener los límites existentes de 64 fuentes/archivos seleccionados y 64 MiB agregados, así como los guards de rutas, links, ownership, locks y transacciones.
- Un gate de retención fallido conserva los recursos; cleanup y close siguen requiriendo observación y recibos válidos.
- No modificar el run auditado, sus workspaces, el MR, el visor independiente ni las skills globales de Superpowers.
- Registrar modelos sólo si la ejecución ya expone metadata; su ausencia no bloquea una revisión ni origina probes o despachos adicionales.

## 5. Fuentes seleccionadas coherentes

### 5.1 Una selección acotada para todas las fases

`ccr.contracts.reference_index` será la autoridad pura para enumerar las rutas de `reference-index.inputs` y los destinos canónicos de sus aliases. Reutilizará la gramática existente; no abrirá archivos. El índice no podrá referenciarse a sí mismo como input ni introducir chains, traversal o rutas externas.

La selección incluye el índice, cada input material y cada destino de alias requerido para validar el índice. Los aliases de resultados no se convierten por eso en inputs iniciales: sólo `inputs` representa fuentes materiales que deben fijarse antes del trabajo.

Al reconstruir los bytes seleccionados, conservar la clave original de cada entrada material aunque también sea un alias. Resolver el destino para sus consumidores no sustituye la entrada original ni sus comprobaciones de digest. Preflight rechaza cualquier índice JSON que no sea objeto, incluso si su hash coincide con el capturado.

El adaptador de archivo cargará cada ruta enumerada únicamente desde los bytes candidatos explícitos o desde una entrada hash-verificada de `cierre.hashes`, con prioridad de los candidatos. Preflight CLI y retención comparten este lector con el gate de ejecución; un run closing puede volver a retener su selección inventariada sin resuministrar evidencia. Un candidato discrepante se rechaza y nunca se sustituye silenciosamente por el archivo previo. La existencia de un archivo sin entrada de inventario no autoriza su lectura como evidencia seleccionada.

`validate_reference_selection` aplica en el builder y preflight la autoridad común de rutas y límites: índice más destinos únicos e inputs materiales no exceden 64 archivos ni 64 MiB agregados. Los aliases que comparten destino cuentan sus bytes una sola vez; el contexto u otros bytes ajenos al índice no se añaden a ese presupuesto. No se importarán todos los archivos del directorio para ocultar una referencia ausente.

Preflight de retención, retain, validate y close usarán esa misma selección y los validadores semánticos existentes. Para un mismo snapshot e inventario válido debe cumplirse: retain exitoso implica validate --require-retained exitoso. Esto no implica limpieza completa ni garantiza el resultado de un posterior --require-complete.

Los diagnósticos preservan `ReferenceIssue` (`code`, `field`, `reference`, `message`, `expected`), orden determinista y códigos existentes `missing_input`, `missing_source`, `input_changed` e `invalid_reference`. El error debe nombrar el archivo concreto, sin sugerir relanzar revisores.

### 5.2 Construir la captura antes de prepare

Añadir `python <skill>/scripts setup inputs --input <envelope> --output <new-evidence.json>`. Usa el mismo envelope `{session, arguments}`, sesión propia, salida directa en `evidence/`, rechazo de colisiones y política de links de los builders existentes.

`arguments` contiene exactamente `scope`, `reference_index`, `source_set_complete` e `identities`. `reference_index` es `{reference: "evidence/reference-index.json", sha256: <digest>}`; `identities` admite sólo los campos de identidad opcionales ya definidos por `review_inputs`, sin `scope`, `sources`, `profile` ni `logical_scope_identity`. `source_set_complete` es booleano o null; null omite la declaración, sin convertir desconocimiento en completitud.

El builder verifica el digest del índice y sus archivos materiales, genera `sources` con el índice y todos los inputs, conserva las identidades explícitas sin inventarlas y normaliza mediante `ccr.workflow.inputs.normalize_inputs`. Si una identidad de contenido suministrada con formato SHA-256 contradice su input único correspondiente, falla; las identidades opacas conservan la normalización existente sin atribuirles un digest. El caller sigue siendo responsable de declarar si el conjunto externo está completo: el builder sólo conoce los inputs que recibió.

La salida se pasa a prepare como `--current-inputs`. El adaptador de contexto y preflight de register/discovery, mientras el run siga `prepared`, rechazan una entrada del índice ausente o con hash distinto en el mapa capturado. `source_set_complete=true` nunca sustituye esta comprobación. El fallo ocurre antes de dispatch y no modifica entradas inmutables ni crea un sucesor automáticamente.

La implementación separa responsabilidades: `workflow.builders` construye inputs sin IO; `workflow.setup.run_command` carga únicamente fuentes de la sesión propia y delega escritura nueva a `execution.candidates.write_new_json`; `cli.setup` sólo expone el comando. `contracts.material_inputs` conserva la validación de captura y `contracts.preflight` la consume. El adaptador `cli.artifacts.preflight_run` suministra bytes explícitos a los contratos, sin convertirse en dependencia de archivo o workflow.

### 5.3 Compatibilidad de runs ya iniciados

En un run existente `processing` o `closing`, reconstruir la selección desde su índice y sus hashes no añade fuentes al snapshot inicial. Si una descripción no estaba capturada, seguirá `unverified`. Las reglas actuales para `aligned`, `needs_update` y requirements continúan vigentes.

No imponer retrospectivamente a esos runs la nueva exigencia de captura completa de todos los propósitos. Pueden superar el gate de evidencia cuando los bytes ya retenidos coincidan con el índice y las limitaciones originales sigan siendo honestas. Una fuente ausente, cambiada o sin hash de inventario sigue bloqueando. Los layouts históricos conservan su política actual y no adquieren capacidades operativas.

## 6. Identidad del despacho y corrección sin repetir trabajo

### 6.1 Registro inicial

Un evento nuevo `agent/started` que cite una asignación independiente activa debe incluir `executor.name` como contexto realmente observado. `provider_id` puede ser null. El builder y el mutador durable rechazan la omisión antes de añadir el evento; no deducen el nombre del brief.

Un inicio estático del coordinador (`discovery/started`) no requiere ejecutor externo. Si el harness no expone un contexto identificable para el trabajo independiente, se documenta el impedimento y el fallback real; no se declara independencia cumplida ni se relanza el trabajo sólo para obtener metadata.

La admisión de eventos nuevos y la revalidación de historia son operaciones distintas. `validate_assignment_event` conserva la exigencia de executor para una emisión nueva. Al registrar de nuevo recursos/contexto, `validate_assignment_history` valida primero las anotaciones contra los inicios originales, aplica la proyección en memoria y comprueba los briefs capturados sin readmitir esos inicios. Un despacho histórico sin identidad permanece desconocido y no certifica independencia: los gates de retención siguen exigiendo evidencia o fallback. La historia inválida falla antes de reclamar recursos o escribir el registro. Añadir un recurso propio o re-registrar el contexto de una transición de perfil conserva los bytes y las secuencias anteriores.

### 6.2 Anotación acotada en una traza abierta

`is_identity_annotation` reconoce exclusivamente kind=dispatch-identity, incluso si el status o los demás campos son inválidos. Productor, builder, preflight, proyección, replay y selección/verificación de fuentes comparten ese predicado. Toda observación histórica agent/unchanged conserva su significado, incluso con procedencia recovered, enlaces records a E locales o campos que se parezcan a una anotación: no proyecta identidad ni requiere seleccionar su source como evidencia de despacho. Un payload nuevo con tipo explícito incompleto sigue rechazándose; no se infiere la intención a partir de campos antiguos.

Para un despacho original existente cuyo `executor` sea null, permitir una anotación con los campos de trace schema 1 y el nuevo tipo externo dispatch-identity:

```json
{
  "kind": "dispatch-identity", "status": "unchanged",
  "summary": "Identidad observada del despacho original; sin nueva ejecución",
  "actor": {"kind": "coordinator", "name": "coordinator", "provider_id": null},
  "executor": {"name": "worker-a", "provider_id": null},
  "provenance": {"kind": "recovered", "source": "evidence/dispatch.json#D1"},
  "occurred_at": null,
  "evidence": ["evidence/briefs.json#D1", "evidence/dispatch.json#D1"],
  "relations": [{"relation": "records", "target": "E000004"}]
}
```

Es un patrón semántico explícito, no otro despacho ni una corrección de contenido del MR. El destino debe ser un `agent/started` previo del mismo run con el mismo brief de una asignación independiente activa y `executor=null`. La anotación exige una fuente local explícita ya observada en dispatch/result metadata del harness que registre la identidad del despacho; un paquete de hallazgos, nombre de workspace o resumen no basta. El fragmento seleccionado contiene un objeto con `executor: {name, provider_id}` coincidente con la anotación, capturado del dato observado y con su procedencia conservada. Su referencia y bytes se seleccionan y verifican al retener.

No aceptar destinos inexistentes, futuros, de asignaciones no independientes, de otra asignación, con identidad ya declarada o anotaciones divergentes. Los runs completos rechazan toda anotación. El replay del mismo payload canónico es idempotente y no añade otro evento. La ausencia de evidencia auténtica mantiene la limitación; no permite fabricar un despacho.

En `closing`, resolver primero el alias con el índice retenido, verificar los bytes inventariados y su digest, resolver el fragmento y cotejar su `executor` antes de escribir. Un fragmento inexistente o una identidad discrepante falla sin cambiar el archivo; después puede registrarse la anotación correcta. El replay idéntico con alias devuelve el ID y sequence de la anotación original sin añadir eventos.

La gramática pura de la anotación admite claves de alias anidadas seguras, como `evidence/harness/dispatch.json#D1`. Builder y proyección no las rechazan por su profundidad; el mutador de closing y la retención exigen que el índice las resuelva a una fuente plana seleccionada y verificable. Rutas externas, traversal, separadores codificados, alias no declarado, digest discrepante y fragmentos inexistentes conservan sus rechazos.

La proyección de ejecución completa sólo la identidad del despacho original en memoria y conserva su `sequence`, actor, evidencia y `occurred_at`. Así puede emparejarlo con el resultado original, aunque la anotación se haya registrado después. No se modifica la línea original ni se añade otro resultado. La anotación no cambia perfil, assignments, inputs, timestamps ni estado de cleanup.

Todos los consumidores de inicios en `validate_execution_sources` comparten esa vista: orden de selección de perfil, emparejamiento independiente y verificador del lote final. Tanto D1 como V1 pueden recuperar su identidad. Para V1, el inicio original y su resultado deben seguir siendo posteriores al último discovery; la posición tardía de la anotación no convierte en válido un inicio anticipado.

Para una asignación independiente, el emparejamiento y la frescura usan el primer `agent/started` proyectado que coincida con el brief, `executor.name` y `executor.provider_id` del resultado, y que preceda a su hito de finalización. El provider desconocido conserva null y se compara como parte de la identidad. Ese despacho debe ser posterior al último discovery. Un `grouped-verification/started` tardío, una coincidencia sólo por actor/nombre o repetir el despacho del mismo contexto no sustituyen un despacho original anticipado. En verificación estática/same-session sigue admitiéndose el inicio de etapa correspondiente, posterior al discovery y anterior al resultado.

El nuevo módulo puro `ccr.contracts.dispatch` valida y proyecta estas anotaciones; se registra en el índice de módulos de `scripts/README.md`. Se usa `python <skill>/scripts artifacts record-event` mediante `archive.lifecycle.record_event` bajo sus guards existentes. No se aceptan anotaciones sobre runs completos ni se eluden transacciones pendientes. Los consumidores antiguos seguirán leyendo JSON schema 1, pero necesitan el helper actualizado para reconocer la anotación como procedencia de un resultado independiente.

## 7. Workflow y comunicación

Actualizar el flujo de la skill y el ejemplo archive8 para usar inputs → prepare → context → preflight → dispatch con identidad → resultados → preflight retain → retain → validate --require-retained → cleanup observado → close → validate --require-complete.

Un rechazo de candidato o proyección no dispara discovery, verificación ni restart. Se corrige sólo el candidato no retenido si sus inputs siguen siendo los fijados. Un cambio real de inputs conserva la política de run vinculado existente.

Los checks del coordinador con recibo observado se registran como `check` con referencia al recibo y relación `records` a C###. Los checks contenidos en un paquete de worker ya registrado pueden quedar bajo ese resultado compacto; no se duplican nueve eventos por obligación retrospectiva. El recibo mantiene tiempos y resultado; desconocido sigue null. La ausencia de modelo no se convierte en fallo ni se confunde `harness_id` con modelo.

El informe distingue juicio de código, retención verificada y cleanup/cierre. Un error de archivo no degrada arbitrariamente un hallazgo de producto; una descripción sin captura inicial permanece sin certificación.

El ciclo completo usa `execution.workspaces.prepare` y `archive.resources.cleanup_workspace`; `archive.lifecycle` conserva validate/close y `archive.retention` conserva el gate común. No trasladar la coordinación de recursos a execution ni importar adaptadores CLI desde esos módulos.

## 8. Aceptación y validación

| ID | Resultado observable |
|---|---|
| A1 | Un índice con descripción y notas produce un mapa inicial con los tres hashes, sin editar el índice ni las identidades dadas. |
| A2 | Un input omitido, cambiado o no seleccionado falla antes del primer dispatch; las lecturas y preflight no modifican el run. |
| A3 | Tras retain, validate --require-retained vuelve a resolver inputs y aliases desde el inventario exacto, conserva la entrada material original aunque tenga alias y pasa sin volver a suministrar --evidence-input. |
| A4 | Un archivo presente sin inventario, alterado, link o ruta insegura no se acepta; fallar no inicia cleanup ni crea un nuevo run. |
| A5 | Un run ya iniciado con captura directa incompleta y descripción unverified puede verificar sus bytes retenidos; su snapshot y descripción no se reescriben. |
| A6 | Un despacho independiente nuevo sin executor falla sin añadir eventos; provider_id y tiempos desconocidos siguen null. |
| A7 | Una sola anotación válida permite usar el despacho y resultado originales de discovery o del verificador final; todos los gates consultan el inicio proyectado con su secuencia original. El resultado independiente se vincula al primer despacho de su identidad completa: un inicio anterior al último discovery sigue rechazándose aunque exista otro started posterior del mismo contexto. El flujo same-session mantiene su inicio de etapa. Replay idéntico, también con alias en closing, devuelve el evento original sin aumentar la traza y los conflictos fallan. |
| A8 | Una anotación no fabrica dispatch ausente, independencia ni evidencia; en closing rechaza fragmentos inexistentes o ejecutores discrepantes antes de escribir, mantiene el orden y los bytes previos y permite después una anotación correcta. |
| A9 | Un ciclo sintético completo conserva fuentes tras eliminar su sesión propia y pasa --require-complete con recibos de cleanup auténticos. |
| A10 | Documentación distingue check, modelo, retención y cierre; no recomienda duplicar hitos, sondear metadata ni borrar recursos tras un fallo. Hitos agent/unchanged genéricos siguen admitidos y no se reinterpretan al retener, validar o cerrar; los runs históricos completos se validan sin cambiar bytes. |

Pruebas con unittest y fixtures sintéticos: validadores puros de fuentes/dispatch, CLI inputs/context/preflight, integración retain/validate/close, replay e inmutabilidad. No usar el archivo auditado ni un MR real como fixture. Las pruebas de guard de links conservan los skips de privilegios Windows que ya use el proyecto y los declaran explícitamente.

Validación histórica del 2026-10-21 sobre CCR 2.14.0 (no representa una ejecución sobre CCR 3.0.0): 8 pruebas de setup, 13 de reference index y 9 de preflight aprobadas. Los primeros intentos de setup/preflight fallaron por permisos del TEMP del sandbox; se repitieron fuera de él y pasaron. No se ejecutó la suite completa ni se validó una implementación nueva.

Revalidación del 2026-10-23 sobre main `9c3fd6b` (CCR 3.0.0): 40 pruebas aprobadas, sin skips, en 16.127 s. Comando: `python -B -m unittest discover -s tests -p <patrón>`, agrupado con unittest para `test_review_setup.py`, `test_review_reference_index.py`, `test_review_preflight.py`, `test_script_dependencies.py`, `test_script_layout.py`, `test_script_pure_validation.py` y `test_script_resource_boundaries.py`. Se usó el Python del runtime con acceso al TEMP. Esta batería comprueba la base y sus límites de arquitectura; no demuestra las mejoras propuestas ni sustituye la suite completa.

## 9. Fuera de alcance

Reparar o cerrar el run real, limpiar sus recursos, publicar comentarios, cambiar modelos, reejecutar revisores, modificar el producto revisado, actualizar versiones/release o implementar el visor. La implementación de este spec sigue el plan asociado y mantiene estos elementos fuera de alcance.
