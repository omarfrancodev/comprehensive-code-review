# Consistencia de preparación, evidencia y continuidad de CCR

Estado: diseño aprobado para implementación por solicitud del usuario del 2026-10-20.

Base de trabajo actualizada: `main`, commit `09eeb034af211af4481206eb943abb6b85fd38db` (CCR 2.13.0). Worktree: `.worktrees/review-execution-consistency`; rama: `docs/review-execution-consistency`. La propuesta original partió de 2.12.1; esta revisión incorpora los contratos integrados por los PR 25 y 26.

## 1. Objetivo y evidencia de origen

Reducir reinicios y trabajo duplicado causados por errores administrativos de CCR. Detectar entradas incompatibles antes del primer dispatch; preservar una relación verificable entre planes, resultados, checks y evidencias; ofrecer una continuación explícita que conserve la historia y sus límites.

La auditoría local del 19 de octubre de 2026 encontró 11 runs de CCR 2.12.1 para siete alcances exactos, seis completos y cuatro ejecuciones adicionales en tres alcances sin cambios de código. Los seis cierres completos superaron entonces `validate --require-complete`, pero uno conserva referencias semánticas inconsistentes. Las conclusiones describen esa muestra, no una tasa histórica del producto ni una validación con el helper 2.13.0. Aquellos archives schema 7 son ahora fuentes históricas no operables por el helper nativo actual.

| Caso observado | Mecanismo | Requisito |
|---|---|---|
| MR 781, `CR-d718147ce173412584c9` | Selección con `evidence/scope.json` sin fragmento que resuelva al perfil | R1: validación temprana de referencias |
| MR 781, `CR-fdbfa5e1beec44128eac` | Plan vacío seguido de eventos de trabajo | R2: barrera previa al trabajo |
| PR 1, `CR-796066d846fc4d76b08c` → `CR-c25e9b1dc5e348918f5e` | Referencia de selección externa; repetición real de dos descubrimientos y un verificador | R3: continuidad sin trabajo nuevo implícito |
| MR 47, `CR-165ab2d1412b477f9a68` | Captura permite rutas anidadas que retain rechaza | R1: gramática compartida |
| MR 47, `CR-81445a2fc62445848645` | C004 huérfano y referencias `producer/` después de aplanar nombres | R4: coherencia semántica y alias explícitos |
| MR 781, `CR-4a88ee1728db4d38ae44` | Fuentes de descripción ausentes y logs silenciosos sin recibos separados | R5: entradas y ejecución auditables |
| Runs abandonados y publicación posterior a retain | Estado distribuido entre snapshot, cierre y traza | R6: disposición y vista operativa coherentes |
| API core MR 1021, `CR-8e2587c220c14691ae44` | El render público emite referencias relativas y el motivo interno de reintento; el agente reporta recortar la salida antes de publicar | R7: proyección pública canónica y publicación sin retoques |
| Requisito adicional del usuario | Se conoce el harness, pero falta vincular el modelo disponible a cada actividad/actor | R8: procedencia de modelo por actividad, cuando el entorno la exponga |

La auditoría detallada permanece en el workspace local que la generó. No incorporar transcripts, rutas personales, archivos de MR ni evidencias privadas al repositorio. Las regresiones usarán fixtures sintéticos equivalentes.

El caso MR 1021 complementa, sin recalcular, la muestra inicial: es un run de 2.13.0/archive 8. Su registro final valida y sus hashes seleccionados coinciden. La edición del comentario remoto procede del relato humano; se reprodujo localmente la salida que la provoca, sin consultar ni modificar el MR. No se afirma que todas las publicaciones se editen.

## 2. Enfoques evaluados y decisión

1. **Sólo documentación:** ejemplos mejores y recordatorios del orden. Es pequeño, pero sigue aceptando entradas que fallarán tarde y depende de que cada agente reconstruya correctamente los contratos.
2. **Contratos compartidos y preparación guiada — elegido:** validadores puros comunes a preflight y retención, builders que producen candidatos locales y barreras en mutadores existentes. Reduce ensayo y error sin reescribir el protocolo durable.
3. **Nuevo workflow engine o reparación general del archivo:** ampliaría esquemas, migraciones y transacciones entre runs. El coste y la superficie de recuperación exceden la evidencia disponible; queda fuera de esta entrega.

La continuidad administrativa se limita a regenerar candidatos todavía no retenidos y a usar las operaciones existentes cuando sus condiciones se cumplen. No se incorpora una operación para cambiar hechos ya capturados.

### 2.1 Contratos de 2.13.0 que se reutilizan

- `review_layout.py` es la autoridad de archive schema 8/layout 2, `logical_scope`, nombres y límites. El alcance lógico agrupa versiones, pero no establece igualdad de head/base/snapshot ni frescura. No crear un segundo normalizador ni reconstruir `run_dir`.
- `review_inputs.py` y `_capture_review_inputs` ya vinculan `logical_scope_identity` a las entradas. El preflight y los builders deben conservar esa identidad y rechazar contradicciones, sin derivarla de hints ni títulos.
- La consulta previa del mismo alcance lógico y `lookup --select latest` ya existen. Mantener su decisión explícita de rerun/consulta y sus rechazos por empate, barrido incompleto o candidato no verificable; no implementar otro selector de última revisión.
- `review_history.py` y [history.md](../../../references/archive/history.md) separan la consulta histórica de un run nativo. Un paquete HP de tres archivos nunca recibe un índice, recibos, claims, continuidad ni publicación nativos.
- El replay de intents nativos v2 ya admite la codificación original sin el campo derivado `logical_scope_identity`, conservando bytes, hashes, reserva e identidad. El preflight no debe reserializar esos intents ni convertir su comparación normalizada en una migración.
- Los subaspectos ABCDE y sus referencias selectivas ya están integrados. El índice de evidencia no añade revisores ni sustituye ese mapa de cobertura.

## 3. Restricciones globales

- Python 3.10+ y biblioteca estándar; no añadir dependencias de ejecución.
- Mantener archive schema 8/layout 2 nativo, result schemas 1–10 legibles y trace schema 1; no migrar ni reescribir archivos históricos.
- Los archives anteriores a schema 8/layout 2 son unsupported_layout para operación; la consulta histórica usa review_history.py y sus paquetes exactos de tres archivos.
- Conservar logical_scope_identity y el replay nativo v2 existentes; no recalcular identidades persistidas ni seleccionar la última revisión de forma implícita.
- Los runs completos son inmutables; ninguna corrección administrativa altera sus bytes.
- Preflight, diagnóstico y vista operativa son de sólo lectura: no crean runs, locks, eventos, worktrees ni procesos.
- Sólo el coordinador modifica metadata durable, usando locks, transacciones y comprobaciones de ownership existentes.
- No inferir autoridad, independencia, identidad de actor, éxito de comandos ni disponibilidad de procesos.
- No reutilizar resultados con scope, inputs, configuración o procedencia desconocidos o cambiados.
- No relajar gates de retención, aislamiento, cleanup, perfil ni requisitos independientes del proyecto.
- No implementar cambios en el visor independiente ni en las skills globales de Superpowers o todo.
- No activar medición de tokens, precios o contadores; usar sólo hechos operativos ya registrados.
- Conservar la procedencia interna completa; publicar los bytes del render público verificado sin ediciones posteriores al render.
- Registrar modelos sólo con datos ya expuestos por el entorno; no inferirlos, sondear APIs ni activar mediciones para completar ese registro.

## 4. Componentes y límites

| Componente | Responsabilidad |
|---|---|
| `scripts/review_references.py` — nuevo | Parseo puro de referencias locales, resolución sobre un mapa de bytes y diagnóstico de enlaces/IDs |
| `scripts/review_preflight.py` — nuevo | Validación por fase de selección, contexto, asignaciones, inputs y candidato final; sin filesystem |
| `scripts/review_setup.py` — nuevo | Construir selección, contexto y eventos válidos como candidatos en una sesión propia ya autorizada; sin dispatch ni archive writes |
| `scripts/review_check_receipts.py` — nuevo | Validar recibos y capturar un comando explícito con argv, cwd y logs propios; sin shell ni instalación implícita |
| `scripts/review_artifacts.py` — existente | Leer fuentes con límites actuales e integrar preflight en las operaciones existentes; único punto CLI durable |
| `scripts/review_recovery.py` — existente | Calcular una vista de estado posterior y la ruta válida de continuación; no ejecutar decisiones |
| `scripts/review_layout.py`, `review_history.py`, `review_restart.py` — existentes | Autoridades reutilizadas de layout/selector, consulta histórica y replay; no sustituir sus protocolos |
| `scripts/review_contract.py`, `review_execution.py`, `review_packets.py` — existentes | Consumir validación de referencias y generar proyecciones coherentes |
| `scripts/review_publication.py` — existente | Proyectar checks por audiencia y validar clasificación pública vinculada al registro |
| `scripts/review_comment.py` — nuevo | Preparar y verificar un borrador público canónico por hash; sin operaciones remotas |
| `scripts/review_model_usage.py` — nuevo | Normalizar observaciones de modelo por actividad y validar su registro privado vinculado al harness |

No extraer ni reorganizar el protocolo completo de `review_artifacts.py`. Los módulos nuevos encapsulan las reglas compartidas de este alcance y evitan añadir otro motor de estados.

## 5. R1: referencias y validación por fase

### 5.1 Gramática única

Las fuentes locales seleccionables usan la gramática vigente: `evidence/<basename>` plano, UTF-8 y sin traversal, query, autoridad URL, barras invertidas, separadores codificados, enlaces ni reparse points. Se mantienen los nombres reservados que el archivo ya permite, como `trazabilidad.jsonl`. No se amplía soporte a carpetas anidadas en esta ronda.

Los fragmentos JSON siguen las reglas de claves/índices y escapes `~0`/`~1` que usa el gate actual. Los fragmentos de traza identifican eventos observados. La validación de forma y la resolución de bytes son fases distintas: prepare no puede exigir un resultado o evento que todavía no existe.

La selección inicial S001 usa `evidence/context.json#profile`. Una transición S002 o posterior apunta a su fila inmutable `evidence/context.json#profile_history/<n>/profile`, donde `<n>` es el índice cero basado en el ID (S002 → 1). `prepare` rechaza URL o una referencia que no corresponda al ID antes de asignar identidad durable. En `register`, el contexto ya existe y el fragmento debe resolver exactamente al perfil de esa fila; el mismo resolver se vuelve a usar en `retain`.

### 5.2 Diagnóstico estable

Cada problema tiene exactamente `code`, `field`, `reference`, `message`, `expected`. `reference` puede ser null. Códigos iniciales: `invalid_reference`, `missing_source`, `missing_fragment`, `profile_mismatch`, `missing_assignment`, `unregistered_assignment`, `unknown_check`, `missing_input`, `invalid_receipt`, `input_changed`.

Preflight devuelve `{phase, ready, issues}`; `ready` sólo es true si no hay issues. Orden determinista por campo y código. Acumular problemas independientes dentro de documentos seguros ya parseados; errores de permisos, integridad o ownership detienen el acceso al documento y no provocan exploración adicional. Límite: 100 issues, con una indicación de truncamiento en el último mensaje si se excede.

El CLI nuevo `review_artifacts.py preflight --run-dir <run> --context-input <context> --phase register|discovery|retain [--input <final>] [--evidence-input <file> ...]` carga únicamente fuentes expresamente seleccionadas de un run nativo schema 8/layout 2. Un plan vacío puede estar listo en `register` mientras continúa la planificación; `discovery` requiere al menos una asignación requerida activa en el registro durable. Un origen incompatible devuelve `unsupported_layout` sin intentar recuperación ni fallback a validación operativa legacy. Exit 0 significa ready; exit 1, errores de contrato; exit 2, error de acceso/parseo/integridad o layout no operable. No se registra un checkpoint por ejecutarlo. No se muestra como un preflight de retención completo si no recibió el candidato final y las evidencias requeridas.

La operación prepare utiliza la validación de selección previa a asignación; no necesita crear un run temporal para invocar el CLI de preflight. Reutiliza `review_layout.logical_scope(scope, logical_scope_input)` y los guards actuales para el selector: límites explícitos de módulo/feature o selección local parcial no se infieren. Validar `logical_scope_identity` contra el descriptor antes de asignar el run; no tratar dos versiones del mismo grupo lógico como inputs idénticos.

## 6. R2: preparación guiada y barrera antes del trabajo

`review_setup.py` ofrece dos constructores de biblioteca y un constructor de evento. Nunca inventan providers, tiempos de ejecución, autoridad ni resultados. Reciben selección y datos de contexto observados; después de prepare, copian el historial exacto devuelto por cierre, sin anticipar S001 ni un event ID.

El contexto generado incluye `executors=[]` cuando no hay ejecutores, un plan explícito de las asignaciones que van a empezar y el objeto `review_inputs` exacto capturado por el archivo 8, incluyendo `logical_scope_identity`. Si todavía no se capturaron entradas, la primera captura sigue la regla actual anterior al trabajo; una identidad contradictoria no se corrige silenciosamente. Un estado preparado o registrado puede tener plan vacío mientras aún se planifica; el preflight de discovery requiere al menos una asignación requerida activa. Todo evento de `agent`, `discovery` o `grouped-verification` que observe trabajo (`started`, `completed`, `passed`, `failed`, `blocked`, `skipped`) debe identificar una asignación activa previamente registrada. La referencia vacía no permite saltarse esa barrera. Las decisiones de check siguen su contrato de ejecutores; no se convierten en asignaciones de reviewers.

`record-event` aplica la barrera incluso si el caller omite `evidence`; devuelve `missing_assignment` en lugar de aceptar trabajo sin identidad. El coordinador registra el plan antes del dispatch real; tras observarlo registra el hito. El helper no despacha agentes y no registra un inicio ficticio.

El constructor de eventos recibe una referencia de brief y un actor observados y valida sus enums con `review_trace.event_input`. El fallo de un constructor no cambia el run. El ejemplo canónico `archive8-lifecycle.md` incorpora preflight y conserva lookup/decisión explícita antes de prepare, construcción de contexto desde cierre, register, dispatch observado y record-event. El ejemplo archive 7 permanece como documentación histórica, sin convertirlo en flujo operativo actual.

## 7. R3: continuación y corrección administrativa limitada

| Estado observado | Acción permitida | Trabajo independiente nuevo |
|---|---|---|
| Candidato final de run nativo 8/2 no retenido tiene JSON, referencias o proyección incorrectos; inputs/plan capturados válidos | Regenerar candidato en la sesión propia, preflight y reintentar retain | No |
| Transacción helper pendiente, con bytes y hashes originales | `recover` exacto conforme a las reglas existentes | No |
| Run íntegro detenido, inputs completos idénticos y autoridad exigida disponible | `resume` existente y continuar sólo gates incompletos | No volver a etiquetar resultados existentes como nuevos |
| Perfil inicial capturado inválido, plan de trabajo ausente, inputs cambiados o frescura desconocida | Preservar origen y proponer restart enlazado con su razón | Sólo según el nuevo plan y autorización aplicable |
| Run completo | Mostrar historia verificada o nueva operación enlazada | Nunca reabrir ni reparar en sitio |
| Origen anterior a schema 8/layout 2 o paquete de consulta HP | Preservar; usar inspect/show/port de review_history.py cuando corresponda; una review actual es un nuevo run nativo independiente | Sin resume/recover/restart ni lineage nativo desde el paquete histórico |

No crear `repair`, `amend`, `force`, rollback general, transferencia automática de sesiones de evidencia ni reutilización entre runs nueva. La construcción de un plan diagnóstico no autoriza su ejecución. Las restricciones actuales sobre adopción de workspaces se mantienen.

Los fixtures de PR 1 deben demostrar que una referencia externa se rechaza antes del primer dispatch. Los fixtures de candidato mal serializado deben demostrar que la corrección no necesita un sucesor. No se promete eliminar el restart de cualquier archivo antiguo que ya capturó identidad inválida.

## 8. R4: coherencia semántica y normalización de evidencia

Crear un sidecar seleccionado `evidence/reference-index.json`, schema 1, para los flujos guiados nuevos. No modificar el esquema exacto de `review.json` ni añadir campos no permitidos a paquetes históricos. El índice tiene exactamente `schema_version`, `aliases`, `inputs`. `aliases` mapea cada referencia local original a `{reference, sha256}`, con destino canónico y digest observado de sus bytes originales; `inputs` contiene `{reference, purpose, sha256}`, donde purpose es `description|requirements|notes|plan|configuration|other`.

Alias: sólo un salto, sin ciclos, sin self-alias, sin URL, sin `..` ni autoridad de otro run. El destino debe existir y coincidir con el digest observado antes del renombrado; no inventar ese digest cuando ya se perdió la fuente. Una referencia anidada sólo puede aparecer como clave de alias de lectura, nunca como destino seleccionable. No se modifica el paquete original; se conserva y se resuelve mediante el alias explícito. El índice no concede permisos sobre ninguna ruta del filesystem.

Validar IDs tipados existentes (`check_ids`, `check_id` y referencias de ejecución) contra sus registros. Además, en los campos narrativos internos que afirman cobertura o resultados —detalles de áreas, re-review y evidencia de checks/findings de los paquetes seleccionados— un token aislado `C` seguido de tres o más dígitos debe identificar un check actual. Una referencia histórica debe estar en la estructura histórica correspondiente, con su review de origen, y no contar como check actual. No aplicar esta regla a código fuente externo, descripciones capturadas ni documentos de ejemplo.

Validar referencias locales explícitas y enlaces Markdown de los briefs/resultados seleccionados. Las menciones de texto que no sean referencias explícitas se diagnostican como observaciones de lint, sin afirmar que se resolvió su significado. El caso observado C004 pertenece a los campos de evidencia/cobertura anteriores y debe fallar; el enlace de productor debe resolverse al alias retenido o fallar.

El contexto guiado declara `reference_index="evidence/reference-index.json"`; su digest figura en `review_inputs.sources` antes del primer trabajo. El índice no se incluye a sí mismo en su lista inputs, evitando un hash circular. La retención guiada selecciona y hashea el índice; validate vuelve a verificarlo cuando existe. Los runs nativos schema 8/layout 2 ya creados sin índice conservan su contrato de integridad existente. Esto no habilita validate operativo sobre archivos anteriores a schema 8: se mantiene `unsupported_layout`. Los paquetes HP conservan exactamente sus tres archivos y no resuelven evidence antigua. Un caller nativo que no declara índice conserva el gate sin auditoría semántica nueva; la skill y los ejemplos nuevos utilizan el flujo guiado y etiquetan esa diferencia explícitamente.

## 9. R5: fuentes materiales y recibos de ejecución

### 9.1 Fuentes

En un flujo guiado nuevo, la descripción `aligned` o `needs_update` necesita una entrada `purpose=description` seleccionada, hash verificado e identidad consistente con `description.identity`. El adaptador acepta el hash hexadecimal existente o su forma `sha256:<hash>` sólo para la comparación; no reescribe identidades históricas. `sources={}` no acredita una descripción observada. Cuando no hay contenido verificable, registrar `unverified` y la limitación que corresponda al impacto real.

El índice debe corresponder a `review_inputs.sources`; no añade silenciosamente una fuente después de comenzar trabajo. Una entrada ausente puede corregirse antes del inicio, pero no sustituir el conjunto capturado después. Notes/requirements usados materialmente se seleccionan o se declaran como limitación; el sistema no inventa su contenido ni intenta recuperarlo de un repositorio remoto.

### 9.2 Recibos

Un recibo nuevo tiene exactamente `schema_version=1`, `check_id`, `argv`, `cwd`, `revision`, `executor`, `started_at`, `finished_at`, `exit_code`, `stdout`, `stderr`. stdout/stderr contienen `{reference, sha256, bytes}`. El `cwd` debe coincidir con `workspace` del executor registrado, tanto al capturar como al validar el recibo retenido. El campo `check.command` debe ser el render determinista `shlex.join(argv)` y el helper rechaza discrepancias antes de iniciar el proceso. Los campos temporales son observaciones, nunca estimaciones. `exit_code=null` representa ejecución no terminada y no acredita passed/failed.

La función de ejecución recibe argv explícito, su texto `command`, `cwd`, el `executor_workspace` registrado, revisión, ejecutor e ID de check; utiliza `subprocess` sin shell y no expande variables ni acepta una cadena shell. Antes de consultar Git o iniciar un proceso, el helper lee `evidence/context.json` de la sesión, exige una sola entrada registrada con ese ID de executor y compara su workspace normalizado con `cwd` y `executor_workspace`. Los `.cmd`, `.bat` y `.ps1` requieren un intérprete explícito y no se infiere que citar argv elimine la semántica de ese intérprete. Ningún comando se ejecuta al validar un recibo. No capturar entorno completo ni secretos en metadata; la selección de logs sigue la política actual de evidencia necesaria.

El check existente puede apuntar al recibo mediante `reference`; los logs se seleccionan separadamente. El texto de comando mostrado deriva del argv exacto del recibo, sin placeholders ni edición manual. Logs vacíos son válidos con hash y exit observados. Reintentos tienen recibos y razones distintos; no se sobreescriben logs anteriores ni se cambia la revisión del check reutilizado.

## 10. R6: disposición y vista operativa

Usar el `restart` transaccional nativo 8/2 existente para crear una sustitución, de modo que origen y sucesor queden vinculados. Los ejemplos dejan de usar `prepare --previous-run` como sustituto de restart para abandonar un procesamiento existente. Una nueva revisión legítima puede enlazar otro run nativo compatible sin afirmar que lo reemplaza; un paquete HP o un archive no operable no es un `--previous-run` válido. La consulta previa y la selección explícita de rerun/latest conservan el contrato 2.13.0; un grupo lógico compartido no permite continuar inputs diferentes.

`inspect` incorpora para runs nativos una proyección adicional `operational_summary` con exactamente `disposition`, `phase`, `successor`, `cleanup`, `publication`. Sus valores proceden del cierre y eventos verificados. Un sucesor mencionado sólo en prosa permanece desconocido; no se persiste un enlace inferido. La vista no deduce liveness a partir de processing ni convierte blocked en trabajo pendiente del usuario por defecto. En rutas unsupported_layout se conserva el diagnóstico actual antes de intentar leer estado operativo nativo. La proyección no selecciona candidatos ni cambia las garantías de `select_latest`.

La publicación posterior se muestra con su evento y tiempo observados; `review.json.resources.publication` conserva el estado del snapshot retenido. Si no existe evidencia posterior, usar ese snapshot; si las fuentes discrepan o son inaccesibles, mostrar unknown con razón, sin publicar ni modificar el original. No se implementa la UI del visor en esta rama.

## 11. R7: comentario canónico sin reparación manual del Markdown

### 11.1 Causa y evidencia de MR 1021

En la base 09eeb03, `review_contract.py:789–797` agrega reuse_reason, rerun_reason, evidence y reference para ambas audiencias; sólo command depende de audience. `public_projection` (`:673–692`) reemplaza comandos y rutas absolutas, pero no las referencias relativas del archivo. `review_publication.py` ya clasifica limitaciones por audiencia; los checks no tienen una separación equivalente. `report-format.md` pide resultados/reutilización y `publication.md` prohíbe rutas/mecánica interna: el agente intenta cumplir ambas después del render.

En MR 1021 el registro conserva correctamente `evidence/test-scheduling.log`, `evidence/repro-head.log`, `evidence/repro-base.log` y, en C003, el fallo inicial CS2012 con su log y el reintento `-m:1`. El render comment emite esas tres referencias y el motivo completo. Un fixture válido con evidence de producto limpia y sólo reference relativa también lo reproduce. No es suficiente atribuirlo a un «registro sucio»: vaciar reference/rerun_reason perdería trazabilidad legítima.

El renderer es determinista en esta reproducción. Falta la frontera de audiencia y una comprobación entre sus bytes y los enviados, no otro análisis del código revisado. La evidencia local no incluye el cuerpo remoto publicado: comparar ese cuerpo forma parte de la mejora futura y no de una afirmación histórica no verificada.

### 11.2 Proyección tipada de checks antes de renderizar

Extender `review_publication.py` con `public_checks(record, classification=None)`. Retorna filas con exactamente `{id, revision, status, failure_kind, evidence, reused, reuse_reason, rerun_reason, reference}`. ID, revisión original —incluida base—, resultado, failure_kind y reused vienen siempre del registro y no son editables por la proyección.

La referencia local del check es privada por construcción: comment no la emite. Una URL HTTP(S) pública del propio check puede conservarse; una clasificación no convierte una ruta local en una URL ni introduce enlaces nuevos. El informe privado conserva command, referencias, intentos y razones completos. No intentar resolver el problema añadiendo más reemplazos regex al Markdown ya generado.

Si no hay razones de reuso/reintento ni contaminación conocida de texto, la proyección pública usa la evidencia de producto existente y excluye los campos privados. Si hay razones libres que necesitan clasificación o texto que contiene referencias internas conocidas/comandos, exigir una entrada pública explícita antes del render. No adivinar materialidad desde palabras como sessions/agents ni filtrar rutas del producto por contener esos términos.

Entrada nueva e independiente de la clasificación legacy de limitaciones: `check_publication_context` tiene exactamente `{source_sha256, checks}`; digest canónico calculado por publication_digest. Una fila por check, sin omisiones ni duplicados, con campos exactos `{id, evidence, reuse_reason, rerun_reason, reference}`. evidence es texto público no vacío cuando existe evidencia original. reuse_reason requiere resumen público si reused=true. rerun_reason puede ser null sólo cuando el motivo es mecánica no material; una repetición que modifica el alcance o deja una validación material pendiente debe conservar su impacto público. reference es null para fuentes locales, o la misma URL pública original. No se pueden cambiar estados, IDs, versiones ni el veredicto con esta entrada.

Esta clasificación se prepara en la sesión propia de la operación de publicación, incluso si el review ya está cerrado; nunca se añade al archive completo ni modifica review.json. El nuevo argumento `--check-publication-context` de render-comment y el keyword `check_publication_context=None` de render son distintos de `--publication-context`: conservar el rechazo actual de un override legacy de limitaciones en schemas 8–10. La lectura histórica privada sigue disponible.

### 11.3 Borrador verificable y cadena de bytes

`review_comment.py` prepara un borrador schema 1 con exactamente `{schema_version, source_sha256, publication_context, check_publication_context, body, body_sha256}`. Ambos contextos pueden ser null según los contratos anteriores. body es la salida exacta de render(comment), sin `.replace`, `.strip`, recortes ni regeneración por el coordinador; body_sha256 se calcula sobre sus bytes UTF-8.

CLI `prepare --input <record> --session <owned-session> --output <draft.json> [--publication-context <json>] [--check-publication-context <json>]` escribe sólo en esa sesión de publicación propia verificada y destino nuevo. `verify --input <record> --draft <draft.json> --body <body.md> [--remote]` es read-only: comprueba hash de fuente, forma del borrador, hashes, re-render con los contextos declarados e igualdad del cuerpo. Cualquier cambio o clasificación desactualizada devuelve error; no publica ni corrige el archivo. Antes de enviar se exige igualdad UTF-8 exacta; sólo `--remote`, para el cuerpo leído de la respuesta API, permite normalizar CRLF→LF. Ninguna otra normalización de Markdown, espacios o texto es aceptable. Exit 0 significa preparado/verificado, exit 1 contrato o diferencia, exit 2 acceso/parseo; ninguno significa publicado.

Flujo: autorización existente → frescura de base/head/descripción → clasificación/pasada editorial antes del render → borrador canónico → verificación del cuerpo que se enviará → envío autorizado → lectura de la respuesta remota → verificación del cuerpo remoto y registro de evidencia. Los helpers nuevos no envían nada y no conceden autoridad. Si el contenido no es publicable, corregir la entrada pública y volver a renderizar; no borrar la procedencia retenida, editar la salida final ni repetir discovery/verificación de código por una corrección editorial.

Si la respuesta remota difiere o el resultado del envío es incierto, conservar la observación y consultar el comentario existente antes de reintentar; no crear duplicados automáticamente. El registro de publicación observado sigue la regla actual de traza abierta u operación separada después del cierre. No afirmar publicado por haber generado/verificado un borrador.

### 11.4 Criterios de aceptación

Los fixtures equivalentes a C001–C003 de MR 1021 deben producir un comentario sin `evidence/…`, CS2012 ni `-m:1` cuando esos datos se clasifiquen como mecánica no material, conservando C002 failed/product, C003 passed/base y la evidencia funcional. El informe privado y los bytes del registro original conservan todos esos datos. Un motivo de reuso sustantivo y una validación material pendiente permanecen visibles con resumen público; no se «arregla» la salida escondiendo un fallo.

La edición manual posterior al render, hash de fuente incorrecto, contexto incompleto/duplicado, URL añadida, cambio de estado intentado y respuesta remota distinta deben fallar sin escritura, envío ni nuevo dispatch. Mismo registro y contextos producen los mismos bytes; un borrador válido no requiere retoques. Mantener el orden público fijo, conteos/IDs y ausencia de ABCDE/perfil/rutas privadas.

## 12. R8: modelo observado por actividad del harness

La identidad del harness y la del modelo son independientes. No agregar modelos al catálogo de harnesses ni reutilizar actor.provider_id como nombre de modelo: ese campo identifica el contexto/proveedor de ejecución que ya exponga la plataforma. Un mismo harness/actor puede usar modelos distintos en momentos distintos y varios actores pueden compartir modelo sin perder ni adquirir independencia por ello.

Cuando esté disponible, registrar la información junto a la actividad concreta: coordinación, descubrimiento, verificación, redacción del informe o publicación. Los checks ejecutados por dotnet/Python/Git no tienen modelo propio: se marcan no aplicables; la generación de una reproducción por un LLM pertenece a su actividad de autoría, no al proceso de tests. No atribuir a todos los pasos el modelo del coordinador ni deducirlo de la familia del harness, del plan o del nombre de un agente.

Guardar `evidence/model-usage.json`, schema 1, con exactamente `{schema_version, review_id, harness_id, entries}`. Es evidencia privada de ejecución, seleccionada y hasheada por checkpoint/retain e identificable mediante `cierre.json.hashes` y el campo opcional `context.model_usage_reference`. No es un nuevo review_input inmutable: las observaciones pueden acumularse durante el trabajo sin modificar la identidad del código revisado. No cambiar archive 8, trace 1, el catálogo ni los campos exactos del resultado 10 para añadir este dato.

Cada entrada tiene exactamente `{id, phase, activity, assignment_id, check_id, actor, configured_model, observed_model, status, source, occurred_at}`. actor conserva `{kind, name, provider_id}` observados; assignment_id/check_id son IDs existentes o null. activity es `coordination|discovery|verification|reporting|publication|check|other`; phase corresponde a la fase observada. id es un identificador administrativo M0001… asignado por el helper, no un ID inferido del proveedor. occurred_at es tiempo de la fuente o null.

configured_model conserva el modelo solicitado/configurado/declarado, si se conoce; observed_model sólo se completa con metadata explícita del modelo efectivamente usado. Ambos son texto acotado a 200 caracteres o null, sin normalización de alias ni inferencia de versiones. source es `{kind, reference}`: kind `platform|adapter_observed|dispatch|runner_argument|user|unavailable|not_applicable`; reference identifica la observación ya disponible o es null si no existe. No copiar transcripts completos, secretos ni entorno global.

status es `observed|configured_only|unknown|not_applicable|conflict`. Una configuración o argumento de dispatch no acredita el modelo real. En particular, `review_runner.py` conserva hoy `model=args.model` en run.json: ese dato suministrado por el caller no prueba por sí solo la respuesta del proveedor. Un cambio solicitado→observado por routing se conserva en ambos campos y no es por sí solo un conflicto; evidencias observadas incompatibles para la misma ejecución se conservan con conflicto explícito, sin elegir silenciosamente una.

Si el harness no expone el modelo, usar observed_model=null y status=unknown o configured_only, según lo disponible. La ausencia no bloquea el review, no modifica su veredicto, no provoca nuevos agentes, lecturas de historial, llamadas API, reintentos ni mediciones. Preservar la forma exacta de observaciones anteriores al añadir una nueva; un cambio de modelo se registra como otra observación de actividad. Límite: 256 entradas y 256 KiB; ante desbordamiento se conserva el prefijo válido y se registra captura incompleta en context.model_usage_diagnostics (hasta 32 textos de 500 caracteres), nunca una revisión fallida ni una recopilación adicional.

Registrar una observación inicial del coordinador y las de workers/actividades posteriores sólo con lo que sus dispatch/respuestas ya expongan. En checkpoints se conserva el estado observado hasta entonces; al retener, el último registro seleccionado. Un run completo no se rellena retrospectivamente. La publicación posterior al cierre registra su modelo, si se conoce, en la operación separada vinculada al review; no reabre el archive. Un paquete HP mantiene exactamente sus tres archivos. Esta metadata es privada y no se incorpora al comentario público ni activa evaluación de costes.

Aceptación: distinguir modelo configurado de observado; dos workers con modelos distintos quedan ligados a sus asignaciones; un cambio de modelo conserva ambas observaciones; ausencia produce null sin trabajo adicional; un proceso de tests es not_applicable; el modelo no sustituye actor/harness IDs ni demuestra independencia. Validar vínculo de review/harness, límites y conservación del historial sin reescribir archives existentes.

## 13. Pruebas y aceptación

R1–R8 deben cubrirse con unittest y repositorios temporales sintéticos; nunca mutar los archivos reales de la auditoría. Antes/después de cada operación read-only comparar inventario y hashes, incluyendo ausencia de locks nuevos. Para R7, mocks de envío demuestran cero llamadas ante mismatch; no enviar comentarios de prueba al MR real. Para R8, metadata ausente no dispara probes, subagentes ni recopilación de consumo.

Casos obligatorios: perfil externo y sin fragmento; ruta anidada capturada; perfil correcto que todavía no tiene context antes de prepare; plan vacío preparado y rechazo de su primer evento; evento completed sin inicio/identidad; C004 huérfano; alias cíclico o hash distinto; ejemplo externo que menciona C004 sin crear un check; descripción sin contenido; log vacío con exit 0 y recibo válido; salida incompleta que no acredita éxito; rutas Windows con espacios y caracteres `$`/backticks; nuevo input después del inicio; origen completo; restart pendiente e idempotencia; publicación posterior; source inaccesible; permiso denegado sin bypass. Añadir regresiones de identidad lógica contradictoria, límites de módulo distintos en el mismo head, mismo MR con otro head, rechazo operativo de archive 7 sin escrituras, paquete HP sin archivos añadidos, latest ambiguo/incompleto y replay nativo v2 anterior con los mismos bytes y reserva.

Éxito significa que los defectos administrativos reproducidos fallan antes de dispatch, los candidatos regenerables conservan un solo run, los enlaces retenidos resuelven y ninguna prueba gana esos resultados relajando ownership o independencia. No equivale a garantizar cero reruns: nuevos inputs, evidencia nueva y gates incompletos pueden exigir trabajo adicional.

## 14. Entrega por fases y exclusiones

Fase 1: gramática, preflight y barrera de asignaciones. Fase 2: índice, semántica y fuentes. Fase 3: builders/recibos, proyección pública, registro pasivo de modelos y continuidad/vista operativa. Cada fase conserva lectura pura de resultados históricos, soporte operativo sólo de archivo nativo 8/2 y el lector HP separado; aporta regresiones antes de integrar la siguiente.

No incluir reparación de archives antiguos, migración global, investigación de consumo, política de cuota, cambio de modelos, eliminación de revisiones ni envío automático de comentarios. R7 sólo prepara/verifica bytes para la publicación ya autorizada; no reemplaza conectores ni crea una publicación. Los resultados de validación de implementación se escribirán cuando se ejecuten; este spec no declara tests futuros como aprobados.

El [plan de implementación](../plans/2026-10-19-review-execution-consistency.md) concreta este diseño. Su ejecución inline inició después de la autorización del usuario.
