# Scripts modulares y entrada única de CCR

**Fecha:** 2026-10-21.
**Base:** `main`, commit `fd38df82f2ea8ef2a921dd8a89e66540f0f01bfb`, CCR 2.14.0.
**Worktree:** `.worktrees/scripts-modularity-spec-plan`.
**Rama:** `docs/scripts-modularity-spec-plan`.
**Estado:** spec para revisión. El usuario eligió la recomendación de entrada única y solicitó expresamente spec y plan juntos; esto autoriza su preparación, no la implementación. El plan asociado sigue sujeto a la revisión de este spec.

## 1. Intención y resultado

Hacer que los helpers sean localizables por responsabilidad, como las referencias, y que cada módulo pueda comprenderse sin recorrer el coordinador completo. Separar contratos, lectura, operaciones durables, ejecución y presentación. La fragmentación debe reducir acoplamiento real y funciones con varias responsabilidades.

Se elimina la duplicidad entre lanzadores `scripts/review_*.py` y parsers internos. La interfaz soportada será una entrada única, invocable desde cualquier directorio y sin instalar un paquete Python:

```bash
python /ruta/skill/scripts artifacts prepare ...
python /ruta/skill/scripts recovery --run-dir ...
python /ruta/skill/scripts setup context --input ... --output ...
```

La base tiene 27 módulos Python, 12 CLI y 12,927 líneas físicas. `review_artifacts.py` concentra 4,521 y `review_recovery.py`, 818. Las cifras del análisis anterior —21 módulos y 9 CLI— correspondían a 2.13.0 y no definen este alcance.

El diseño incorpora lo publicado en 2.14.0: preflight, constructores de preparación, referencias e índice, recibos de checks, comentarios públicos y registro de modelos. La [especificación de consistencia de ejecución](2026-10-19-review-execution-consistency-design.md) explica sus reglas vigentes; sus rutas de scripts se sustituyen en instrucciones actuales, no en el registro histórico de esa decisión.

## 2. Restricciones globales

- Python 3.10+ y biblioteca estándar; no añadir dependencias de ejecución ni exigir instalación Python.
- Usar `python /ruta/skill/scripts <área> ...` como interfaz soportada, desde cualquier cwd y con rutas que contengan espacios.
- Retirar los 27 archivos `scripts/review_*.py` al completar la migración; no conservar fachadas, aliases en sys.modules ni imports legacy como interfaz soportada.
- Conservar archive schema 8/layout 2, result schemas 1–10 y trace schema 1; no migrar ni reescribir archivos históricos.
- Los layouts anteriores siguen sin soporte operativo nativo; su consulta histórica conserva paquetes de tres archivos y nunca habilita resume/restart por conservar un validador legible.
- Preservar identidades, bytes canónicos, hashes, reservas, nombres de artefactos y replay nativo v2; un cambio de módulo no cambia la identidad lógica del productor.
- Mantener locks, reentrancia, orden de adquisición, ownership, gates, idempotencia y causas/tipos de errores de coordinación.
- Preflight, diagnóstico, búsqueda y ayuda son de sólo lectura: no crean runs, locks, eventos, worktrees ni procesos de trabajo.
- Conservar selección explícita de latest, sus empates y búsqueda incompleta; no convertir inputs desconocidos o cambiados en aplicables.
- Mantener setup en sesiones propias, captura explícita sin shell y comentario público verificado por sus bytes; ninguna operación publica remotamente por este cambio.
- No activar mediciones, sondeos de modelos, instalación de herramientas ni dispatch adicional.
- No modificar el visor independiente ni las skills globales de Superpowers o todo.
- Mantener documentos históricos como evidencia; actualizar instrucciones vigentes, enlaces locales y guías de migración sin atribuirles comportamiento posterior.

## 3. Interfaz pública y ruptura deliberada

| CLI actual | Área nueva | Sufijo preservado |
|---|---|---|
| `review_artifacts.py` | `artifacts` | prepare, register, transfer-resources, inspect, preflight, lookup, pause, block, resume, recover, restart, abandon-restart, record-restart-refusal, select-profile, validate, record-event, checkpoint, retain y close; sus argumentos |
| `review_contract.py` | `contract` | validate, render-user, render-comment, render-handoff, canonicalize-ids, deduplicate; sus argumentos |
| `review_delivery.py` | `delivery` | argumentos existentes, sin inventar un subcomando |
| `review_history.py` | `history` | inspect, port y show; sus argumentos |
| `review_metrics.py` | `metrics` | record y summarize; sus argumentos |
| `review_packets.py` | `packets` | validate y merge; sus argumentos |
| `review_recovery.py` | `recovery` | --run-dir y --current-inputs; no añadir inspect obligatorio |
| `review_runner.py` | `runner` | argumentos existentes |
| `review_workspace.py` | `workspace` | prepare, inspect, record-artifact y cleanup; sus argumentos |
| `review_setup.py` | `setup` | profile, context y event; sus argumentos |
| `review_check_receipts.py` | `checks` | run --request ... --output-dir ... |
| `review_comment.py` | `comment` | prepare y verify; sus argumentos |

La tabla enumera 12 áreas exactas. `review_preflight`, `review_references` y `review_model_usage` no son CLI en la base; no se convierten en comandos adicionales.

`scripts/__main__.py` sólo llama `ccr.cli.main.main()` y propaga el código de salida. `ccr.cli.main` contiene un registro explícito de las 12 áreas y sus módulos, interpreta únicamente el primer token y entrega el resto sin reordenar, dividir ni volver a citar argumentos. La importación del área es diferida y limitada a ese registro estático; no hay descubrimiento de plugins ni importación basada en rutas del usuario.

Todos los parsers de área exponen `main(argv: list[str] | None = None, *, prog: str | None = None) -> int`. Usan `parse_args(argv)`, sin modificar globalmente `sys.argv`. El prog raíz es `ccr`; la ayuda de área usa `ccr <área>`. Los `SystemExit` normales de argparse para ayuda/uso conservan 0/2 y sólo se traducen en el punto de entrada del proceso, sin convertirlos en errores de negocio.

- `python /ruta/skill/scripts --help`: exit 0 y lista de las 12 áreas; sin cargar servicios de trabajo.
- Sin área o con área desconocida: exit 2 y orientación de uso, sin efectos.
- `<área> --help`: exit 0, ayuda específica y mismos argumentos de la CLI anterior.
- Fuera del prefijo de invocación/prog y las instrucciones efímeras que lo mencionen, se mantienen payloads de salida, mensajes de contrato y códigos de salida por operación. No unificar todos los errores en un envelope nuevo.
- `checks run` continúa retornando 0 ante una captura válida aunque el comando capturado termine distinto de cero; el resultado del check está en el recibo.

La retirada de rutas CLI e imports Python anteriores es una ruptura deliberada. Debe explicarse en uso/instalación/changelog de la futura implementación y destacarse al preparar su release; no se fija ahora una versión futura ni se publica una release con este trabajo documental. La compatibilidad de los archivos persistidos permanece independiente de esta ruptura de interfaz.

## 4. Organización y propietarios

Los siguientes nombres fijan los límites del plan. Cada subpaquete tiene `__init__.py` mínimo y no reexporta todo su árbol. `scripts/README.md` registra área, API propietaria, efectos, referencia del contrato y pruebas; no se convierte en lectura obligatoria completa para cada revisión.

```text
scripts/
  __main__.py
  README.md
  ccr/
    __init__.py
    shared/       encoding.py, paths.py, json_io.py, git.py, installation.py
    workflow/     inputs.py, profiles.py, builders.py, setup.py
    contracts/    validation.py, scope.py, review.py, findings.py, identifier_types.py, identifiers.py,
                  execution.py, provenance.py, reference_types.py, references.py,
                  reference_index.py, semantic_references.py, material_inputs.py,
                  preflight.py, receipts.py, model_usage.py, packets.py, claims.py
    archive/      layout.py, trace.py, reader.py, integrity.py, intent_contracts.py,
                  restart_state.py, coordination.py, transactions.py, evidence.py,
                  checkpoints.py, lifecycle.py, retention.py, resources.py,
                  restart_contract.py, restart.py, inspection.py, lookup.py, history.py
    execution/    locks.py, workspace_manifest.py, workspaces.py, claims.py,
                  candidates.py, checks.py, runner.py, harness.py
    reporting/    markdown.py, projections.py, render.py, delivery.py, comment.py
    maintenance/  metrics.py
    cli/          main.py, artifacts.py, contract.py, delivery.py, history.py,
                  metrics.py, packets.py, recovery.py, runner.py, workspace.py,
                  setup.py, checks.py, comment.py
```

Se crean módulos por responsabilidad, no por máximo de líneas. Se conservan juntas las unidades pequeñas de layout, trace, locks, harness, métricas, normalización de inputs y contrato de restart. No se crean capas de repositorios genéricas, contenedores de servicios ni un nuevo motor de estados.

### Mapa exhaustivo de los 27 módulos actuales

| Origen `scripts/` | Propietarios nuevos bajo `scripts/ccr/` |
|---|---|
| `review_artifacts.py` | shared IO/Git; contracts.scope; archive reader/integrity/transactions/evidence/checkpoints/lifecycle/retention/resources/restart; cli.artifacts |
| `review_contract.py` | contracts validation/scope/review/findings/identifier_types/identifiers; reporting markdown/projections/render; cli.contract |
| `review_recovery.py` | archive inspection/lookup; workflow.inputs; cli.recovery |
| `review_workspace.py` | execution workspace_manifest/workspaces; archive.resources para coordinación de sesiones reclamadas; cli.workspace |
| `review_resource_claims.py` | contracts.claims para forma/planes; execution.claims para verificación con IO; archive.resources para aplicación durable |
| `review_execution.py` | contracts.execution y contracts.provenance |
| `review_delivery.py` | reporting delivery/markdown/projections; cli.delivery |
| `review_profiles.py` | workflow.profiles; validación de cumplimiento final en contracts.execution/provenance |
| `review_history.py` | archive.history y cli.history |
| `review_packets.py` | contracts.packets y cli.packets |
| `review_run_lock.py` | execution.locks, sin reescribir sus primitivas |
| `review_layout.py` | archive.layout, puro |
| `review_restart.py` | archive.restart_contract, puro; distinto del servicio durable archive.restart |
| `review_trace.py` | archive.trace, puro; persistencia/replay en archive.transactions |
| `review_runner.py` | execution.runner y cli.runner |
| `review_restart_refusal.py` | archive.restart; recibos y validación en intent_contracts/restart_state según sus efectos |
| `review_metrics.py` | maintenance.metrics y cli.metrics |
| `review_harness.py` | execution.harness y shared.installation para el catálogo |
| `review_inputs.py` | workflow.inputs y contracts.scope |
| `review_publication.py` | reporting.projections |
| `review_check_provenance.py` | contracts.provenance |
| `review_references.py` | contracts reference_types/references/reference_index/semantic_references/material_inputs |
| `review_preflight.py` | contracts.preflight |
| `review_setup.py` | workflow.builders (puro), workflow.setup (servicio), execution.candidates (sesión/escritura), cli.setup |
| `review_check_receipts.py` | contracts.receipts (puro), execution.checks (captura), cli.checks |
| `review_comment.py` | reporting.comment (preparar/verificar), execution.candidates para salida propia y cli.comment |
| `review_model_usage.py` | contracts.model_usage, puro y sin añadir CLI |

La selección de carpeta no impone una capa única: `workflow.builders` es puro y `workflow.setup` hace IO; `reporting.render` es puro y `reporting.delivery` escribe una entrega. Las dependencias se validan a nivel de módulo.

## 5. Dependencias y APIs internas

Las funciones puras sólo consumen objetos/bytes suministrados y no importan servicios, CLI, lectores de disco o módulos que capturan comandos. `contracts.preflight` depende de `contracts.receipts`, nunca de `execution.checks`. `contracts.reference_types` posee `ReferenceIssue`, evitando que los validadores se importen mutuamente sólo por ese tipo.

`contracts.scope` es autónomo y no importa `contracts.review`; su validación conserva las reglas/diagnósticos de scope actuales. `workflow.inputs` lo usa sin importar el escritor. `workflow.profiles` conserva sus APIs puras de selección y registro; las reglas que necesitan el resultado completo pertenecen a los validadores de ejecución.

`contracts.identifier_types` posee canonical_id/review_id y otras comprobaciones elementales de IDs. `contracts.review` puede usarlas sin importar `contracts.identifiers`; este último compone asignación/deduplicación y puede invocar review.validate como precondición. Así se evita introducir un ciclo nuevo al extraer canonicalize_ids.

`archive.reader` y `archive.integrity` pueden usar contratos de intents/claims y utilidades de IO; no importan lifecycle, restart, resources ni workflow.setup. `archive.restart_state` lee descriptores e intents y verifica sus identidades, sin llamar mutadores ni volver a cargar el run mediante reader. Los contratos de esos documentos residen en `intent_contracts`. La inspección reutiliza estas APIs de lectura, no importa el servicio para descubrir qué ocurrió.

Interfaces nuevas que estabilizan los cortes:

| Módulo | API |
|---|---|
| shared.installation | `skill_root() -> Path`, `resource_path(relative: str) -> Path`; raíz anclada a la ubicación conocida de ccr, no al cwd ni a una búsqueda por padres |
| contracts.scope | `validate_scope(scope: object) -> list[str]`, `require_scope(scope: object) -> None`; conservar errores y campos exactos actuales |
| workflow.inputs | `candidate_inputs(manifest: dict, record: dict | None = None) -> dict` y `validate_current_inputs(current_inputs, manifest, *, require_same_scope=True, compare_sources=True, require_applicable=False) -> dict`; trasladadas de recovery como reglas puras compartidas |
| archive.reader | `load_run(run_dir: str | Path) -> tuple[Path, dict, dict]`; mantiene run, manifest y marker verificados sin escribir |
| archive.integrity | `verify_files(run, manifest, required=False, *, allow_checkpoint_transaction=False, allow_resource_transfer=False, allow_pending_trace=False) -> None` |
| execution.workspace_manifest | `load(manifest_path) -> dict`, `owned_session(session_path) -> tuple[Path, Path, dict]`; la segunda conserva la semántica actual de setup._owned_session |
| execution.candidates | `write_new_json(session_dir: Path, output: str, value: dict) -> Path`; conserva formato, límites y rechazo de sobrescritura de setup |
| archive.coordination | `owned_run_locks(run_dirs, *, reservation=None)` como context manager, con las mismas revalidaciones y resultados del helper actual |
| archive.resources | `cleanup_workspace(args) -> dict`; coordina sesión reclamada o no reclamada y llama acciones físicas sin que execution importe servicios de archive |
| execution.workspaces | `plan_cleanup(args, manifest: dict, *, claim: dict | None = None) -> dict`, `remove_workspaces(plan: dict) -> dict`; validación total y acciones físicas llamadas dentro de la coordinación, sin buscar un run por su cuenta |
| ccr.cli.main | `main(argv: list[str] | None = None) -> int`; registro estático y delegación del sufijo intacto |

Los demás mutadores preservan sus nombres, argumentos, valores por defecto y formas de resultado al trasladarse a su propietario. Un cambio de firma no enumerado requiere ajustar primero spec/plan, no inventar un parámetro general que pase el módulo escritor entero.

`execution.claims` recibe manifest/marker/fuentes ya seleccionados para validar, y separa funciones puras de acceso. `archive.resources` coordina esa validación con el run y la sesión. No se entrega un diccionario como autorización suficiente para borrar: se revalidan identidades y ownership bajo lock antes del primer efecto.

El grafo final no contiene ciclos ni imports `review_*`; ningún módulo de implementación importa `ccr.cli`. La carga diferida del registro de áreas es la única resolución de módulos configurada por strings y usa exclusivamente la tabla fija del launcher.

## 6. Fragmentación de lógica extensa

- **Resultado:** `contracts.review.validate(record)` compone validadores de estructura/scope, checks/findings, cobertura/ejecución y metadatos finales. Devuelve todos los errores en el mismo orden y no muta entradas. `contracts.validation` ofrece utilidades de campo/array/tipo con estado local, sin singleton. IDs y deduplicación quedan separados del render.
- **Presentación:** `reporting.markdown` posee escapes/bloques; `projections` la selección de audiencia y clasificación pública; `render` la composición de informe y handoff. Conservar un origen para los bloques compartidos en vez de duplicar documentos enteros.
- **Referencias:** separar parseo/resolución, índice/aliases, vínculos semánticos de resultados/packets e inputs materiales. Mantener gramática, límites, truncamiento y orden de issues de 2.14.0; ninguna función pura abre archivos para resolver un enlace.
- **Recibos:** distinguir validación del recibo y de sus fuentes de la captura de proceso/ownership. Nunca hacer que preflight ejecute el comando que pretende validar.
- **Archivo:** `transactions` posee publicación/replay, `evidence` la preparación acotada, `checkpoints` el checkpoint y `retention` los gates y contenidos de retención. `lifecycle` compone preparación, perfil, pausa/bloqueo, continuidad ordinaria y cierre. Restart durable permanece separado de esas operaciones y de su contrato puro.
- **Recuperación:** `inspection` separa observación, resumen operativo y decisión de continuidad; `lookup` separa recorrido acotado/cursor, clasificación y selección explícita. `history` conserva consulta/portado verificado y no adopta semántica nativa.
- **Funciones superiores:** preparar, transferir, retener y reiniciar separan normalización/preflight, plan y aplicación, pero mantienen una sección crítica completa. No cerrar locks ni emitir commits durables adicionales entre helpers extraídos.

## 7. Protocolos que deben permanecer intactos

### Bytes y procedencia

`shared.encoding` ofrece formatos nombrados según los escritores actuales; no se impone una serialización común a layout, restart, manifest, recibos y setup. La extracción conserva separadores, Unicode, orden de claves, indentación y salto final de cada contrato. Los paths de módulos nuevos no sustituyen los producer/source IDs lógicos ya usados en eventos o hashes.

Los bytes de intents reservados se reutilizan en replay sin normalización destructiva, incluido el productor v2 anterior sin `logical_scope_identity` derivado. No se sintetizan tiempos, modelos, actores o eventos para completar metadata tras un movimiento de código.

### Locks, recursos e interrupciones

Se conserva la adquisición observada: la limpieza de sesión entra en session_claim_locks y, si está reclamada, adquiere el lock del run dentro de esa sección. Las primitivas de múltiples runs mantienen su orden estable/reentrancia. Transferencias y restart conservan sus combinaciones actuales; una refactorización no justifica cambiar ese orden.

La coordinación vive en archive; las acciones físicas y lectura de sesión en execution. Antes de eliminar el primer worktree se valida toda la sesión, sus registros Git, HEAD, snapshots, fixtures y ausencia de recursos inesperados. Un fallo después del borrado y antes de completar el recibo conserva la recuperación de cleanup. No se confunde atomicidad por archivo con commit de varios documentos.

### Diagnóstico y salida

Se conserva la distinción entre observación read-only y replay autorizado, rechazo temporal de locks y fallo de coordinación. Se mantienen causas/tipos de error. Las sugerencias efímeras de invocación usan la entrada nueva; los comandos y hashes guardados como evidencia histórica permanecen inmutables.

## 8. Pruebas, documentación y distribución

Las pruebas importan `ccr` añadiendo una sola vez `scripts` a su bootstrap cuando unittest lo requiere. No se introducen ajustes de sys.path en módulos del producto. Se sustituyen imports con nombres antiguos, `spec_from_file_location` hacia esos archivos, scripts embebidos en subprocess y monkeypatches de globals por el propietario nuevo. No basta con renombrar imports si un test sigue parcheando un módulo que ya no ejecuta la operación.

Un inventario declarativo de áreas en `ccr.cli.main` es autoridad del dispatcher. `scripts/README.md` y la prueba de layout comprueban su correspondencia. La prueba de arquitectura inspecciona imports de módulo y locales, relativos resueltos y la tabla estática de carga diferida; rechaza ciclos, imports legacy y referencias de contratos puros a IO/servicios.

Actualizar SKILL.md, README, docs/usage.md, docs/installation.md y referencias operativas. Las explicaciones históricas en changelog, specs, planes, validaciones y ejemplos de schemas anteriores preservan las invocaciones de su época. Si un enlace Markdown apunta a un archivo retirado, sustituir su destino por la guía de migración que identifica su equivalente, sin reescribir el resultado histórico. Mantener la prueba existente de enlaces locales.

La copia/ZIP debe incluir scripts/__main__.py y todo scripts/ccr. Se prueba una copia completa en una ruta con espacios desde cwd ajeno, catálogo de harness y lectura de SKILL.md incluidos. La operación no depende del nombre del checkout ni del worktree donde se desarrolló. No se promete que ejecutar archivos individuales de ccr/cli sea otra interfaz pública.

## 9. Criterios de aceptación

1. Las 12 áreas son accesibles desde la entrada única; no quedan scripts/review_*.py ni imports legacy en producto o pruebas activas.
2. Sin área, área inválida, ayuda raíz, ayuda de área y argumentos con espacios tienen semántica explícita de §3; root help no importa servicios de trabajo.
3. La superficie de opciones de cada área y los resultados/códigos de operaciones conservan la base, salvo el prefijo y orientación CLI expresamente cambiados.
4. Contratos y preflight siguen puros; la inspección no muta el run y el grafo de implementación no tiene ciclos ni dependencias a CLI.
5. Identidades/hashes y replay v2 permanecen equivalentes con fixtures deterministas; runs completos y paquetes históricos no se reescriben.
6. Interrupción de checkpoint/retención, transferencia, restart y cleanup conserva la misma ruta de retry/recuperación y ownership.
7. Tests de referencias, índice, setup, recibos, modelo y comentario de 2.14.0 conservan sus garantías; checks capturados y borradores públicos no se convierten en ejecución/publicación implícita.
8. La copia instalada completa funciona desde cwd ajeno; catálogo, versión y rechazo de raíces no persistentes se resuelven desde la raíz instalada correcta.
9. Registro de módulos/áreas, instrucciones actuales y guía de ruptura son coherentes; historia conservada y enlaces locales válidos.
10. Suite completa unittest y git diff --check pasan antes de integrar; se reporta cualquier omisión ambiental. Una suite focalizada no se presenta como cobertura total.

## 10. Estado de esta entrega

Este spec y el [plan asociado](../plans/2026-10-21-scripts-modularity.md) son los únicos cambios previstos en el worktree de planificación. Su validación comprueba base, inventario, enlaces, cobertura de decisiones y coherencia de interfaces; no constituye ejecución ni validación funcional de la refactorización futura. La implementación requiere revisión de los documentos y elección de su método de ejecución.
