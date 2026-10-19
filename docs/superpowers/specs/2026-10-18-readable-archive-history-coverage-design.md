# Archivo legible, consulta histórica y subaspectos ABCDE

## Estado, base y autorización

Especificación preparada a petición del usuario junto con su plan. El usuario aprobó las decisiones y autorizó la implementación en el worktree. No se modifican archivos reales de reviews, no se publica y el visor queda fuera del alcance.

Base: release 2.12.1, commit `715726377ad95acbb1cbad114d7a55968228ab79`. Rama `feat/archive-layout-portability`, worktree `.worktrees/archive-layout-portability`. El nombre `comprehensive-code-review` se conserva. No se asigna una nueva versión de release durante esta preparación.

La propuesta sustituye la migración discutida previamente: **no se mueven ni reescriben los archivos históricos**. Su formato se identifica como incompatible para operar; se ofrece una copia mínima de consulta cuando sus datos esenciales son verificables. El visor se actualizará por separado por el usuario.

## Objetivo y criterios de éxito

1. Identificar alcance, orden temporal y versión desde el árbol de directorios, sin abrir cada informe.
2. Reutilizar lookup/inspect/recover/restart actuales; añadir únicamente decisiones y cambios de formato necesarios.
3. Preguntar antes de repetir una revisión de las mismas entradas, salvo que la petición ya resuelva esa elección. Consultar no ejecuta una nueva revisión.
4. Permitir «mostrar el último resultado» como selección explícita y verificable del alcance exacto, sin confundir recencia con vigencia.
5. Conservar reviews antiguos como fuentes inmutables; opcionalmente portar un informe verificable a un paquete histórico mínimo, sin convertirlo en una ejecución actual.
6. Ampliar ABCDE con subaspectos, ejemplos y referencias selectivas, sin imponer cinco agentes ni nuevas puntuaciones.

## Restricciones globales

- Python 3.10+ y biblioteca estándar; Git solo para operaciones que ya lo requieren.
- Mantener final review schema 10, trace schema 1 y packet version 1. No reconstruir datos históricos para actualizar sus schemas.
- Emitir archive schema 8 con layout_version 2; los archivos nativos anteriores se clasifican como unsupported_layout para operación.
- Ninguna operación escribe en un archivo histórico ni migra sus carpetas, ownership, claims, trazas o transacciones.
- Portar produce únicamente informe.md, consulta.json y .ccr-history.json; no produce cierre.json, review.json, marcador de ownership ni traza nativa.
- Consultar y seleccionar son operaciones de solo lectura: no crean sesiones, worktrees, runs, locks ni entregas.
- No añadir fechas al contenido de informes nuevos; las fechas de rutas y selección conservan UTC explícito.
- Conservar el nombre comprehensive-code-review; el visor, publicaciones, merge, tags y release quedan fuera del alcance.

## 1. Situación actual y alternativas descartadas

Archive 7 agrupa por modo, referencia y hash del scope completo; base/head/snapshot cambian la carpeta. El nombre de ejecución solo contiene fecha y run_id. La versión 2.12.1 ya incorpora consulta paginada y acotada, comparación de entradas, inspección y recuperación exacta con locks, claims e intents. Estos mecanismos permanecen; no se crea otro motor de recuperación.

Se descartan migración general, renombrar carpetas activas, restaurar operaciones antiguas mediante una copia mínima y elegir automáticamente por fecha ante una petición ambigua. Un índice adicional no resuelve por sí solo la identificación del árbol y no es necesario en esta entrega.

## 2. Ubicación nativa nueva

```text
<archive-root>/<repository-group>/<logical-scope-group>/<created-utc>--<version-hint>--<run-id>/

repo-<stable-id>/mr-1010/20261018T150000Z--head-90e54abb1234--<20-hex-run-id>/
repo-<stable-id>/mr-1010/20261018T170000Z--head-90e54abb1234--<otro-run-id>/
```

Se conserva repository-group y el root actual/CCR_ARTIFACTS_DIR. created-utc se deriva del created_at original del nuevo run en UTC con formato YYYYMMDDTHHMMSSZ. run-id mantiene 20 hex y la identidad CR-<run-id>. Los hints no establecen identidad ni orden causal. El mkdir exclusivo sigue siendo la frontera de colisiones.

version-hint: head-<12 caracteres seguros> para commits inmutables; base-<12>-head-<12> para range; snap-<12> para snapshots. Los valores completos permanecen en scope. Las entradas no hex de fixtures se convierten con el slug seguro existente, sin permitir traversal, nombres reservados o componentes demasiado largos.

### Alcance lógico

Archive 8 fija un descriptor logical_scope `{mode, selector, hint, identity}`. identity es SHA-256 del JSON canónico de `{mode, selector}`; hint se deriva, no es una segunda identidad editable. Máximo 64 límites, strings de 500 caracteres y JSON de 64 KiB. Se añade logical_scope_identity a las entradas comparables, sin cambiar el scope del resultado 10.

Formas exactas de selector: MR/PR `{reference}`; commit `{head, base}`; range simbólico `{kind: refs, base_ref, head_ref}` o exacto `{kind: commits, base, head}`; module/feature `{reference, boundaries}`; local `{boundaries}`. reference y base admiten null solo donde scope ya lo permite; module/feature requieren boundaries no vacío. Los límites se expresan como paths relativos POSIX dentro del repositorio, sin `..`, paths absolutos ni enlaces seguidos. Los límites locales [] significan el alcance completo, no una selección todavía desconocida. No mezclar resolved_base/resolved_head con el selector estable: son comprobaciones de entrada, no parte de identity.

hint conserva un máximo de 36 caracteres seguros; grupos un máximo de 80 y nombres de run un máximo de 128. No se trunca el digest ni run_id para acomodar paths completos: un límite del host produce un diagnóstico sin crear una ruta alternativa.

| Modo | Selector estable | Grupo visible |
|---|---|---|
| mr/pr | Referencia normalizada dentro del repositorio verificado | mr-1010/pr-123 si la referencia se reconoce sin ambigüedad; en otro caso modo-hint-<16 hex de identity> |
| commit | SHA completo seleccionado y padre/base de comparación | commit-<12 de head>-<16 de identity> |
| range | Referencias simbólicas base/head explícitas y verificadas contra el scope, o extremos exactos si solo hay SHA | range-hint-<16 de identity> |
| module/feature | Referencia suministrada y límites relativos normalizados, ordenados y sin duplicados | modo-hint-<16 de identity> |
| working/staged/unstaged | Modalidad y límites relativos seleccionados; [] significa todo el alcance solicitado | modo-hint-<16 de identity> |

Para MR/PR la referencia numérica debe provenir de la referencia fijada; no extraer un número de un título. La normalización es local y no hace consultas de red. Una referencia de proveedor/repositorio contradictoria es error; una forma opaca usa sufijo de identidad. El mismo MR con otra base, destino o head comparte grupo, pero nunca coincidencia exacta.

prepare y restart aceptarán `--logical-scope-input` cuando no pueda derivarse el selector del scope (obligatorio para module/feature y selección parcial local). El documento contiene `{mode, selector}`; en rangos simbólicos también `{resolved_base, resolved_head}`, que deben coincidir con scope. No se inventa una identidad funcional para rangos de SHA. Un restart de iguales límites puede reutilizar el descriptor; cambiar límites requiere otra entrada y un nuevo grupo.

Un módulo con iguales límites y otro head comparte grupo. Dos módulos distintos en el mismo commit no. Un snapshot local nuevo comparte grupo si modalidad/límites coinciden, aunque sus entradas exactas difieran. El hash del scope completo continúa disponible para comparación y ownership.

### Contrato y escritura

Archive 8 añade layout_version=2 y logical_scope al manifiesto y su binding al ownership marker. Mantiene todas las obligaciones de archive 7. Una función única calcula grupos y nombres para prepare, restart/reserva, validación, lookup y entrega. No se reconstruyen rutas separadamente en recovery. El resultado final sigue siendo schema 10; su validador histórico puro permanece disponible para leer contenido, no para operar archivos antiguos.

## 3. Formatos anteriores: detección sin adopción

Los helpers operativos requieren archive 8/layout 2. Ante una ruta anterior devuelven un diagnóstico estructurado con código unsupported_layout, estado historical_source y acciones port_history/new_review/preserve según los datos comprobados. No llaman recuperación antigua, limpian claims ni hacen takeover. Un archivo ilegible o malformado es invalid/unknown, no simplemente deprecado.

lookup reconoce nombres de grupos anteriores solo dentro del repositorio y referencia consultados para señalar candidatos incompatibles. Esto es inventario histórico acotado, no compatibilidad operativa ni exploración global. No debe crear locks ni analizar una transacción para adoptarla. La portada histórica es una operación explícita diferente.

No se elimina soporte de schemas históricos en el validador puro del contenido, el renderizador ni las entregas ya emitidas. Una entrega portable no es un run y nunca se ofrece como recuperable. Para recuperar un run antiguo, el diagnóstico remite a su versión productora fuera de este flujo; esta implementación no instala ni ejecuta esa versión.

## 4. Portabilidad mínima de consulta

Nuevo helper `review_history.py`, operaciones inspect/port/show. CLI propuesta:

```text
python scripts/review_history.py inspect --source-run <ruta-exacta>
python scripts/review_history.py port --source-run <ruta-exacta> --output-root <raiz-historica>
python scripts/review_history.py show --history-dir <paquete-exacto>
```

Destino por defecto: `<archive-root>/.historical/<repository-group>/<scope-hint>--<source-date-or-undated>--<port-id>/`. source-date solo procede de un created_at válido; ausencia se presenta como undated. port-id es HP-<primeros 20 hex de SHA-256 de la identidad de fuente y hashes de los dos archivos seleccionados>. No es un CR inventado. Una segunda exportación de los mismos bytes recupera el paquete idéntico tras validarlo; nunca sobrescribe cambios del destino.

### Condiciones de lectura

Se seleccionan exactamente cierre.json, ownership marker, review.json e informe.md, con límites de 1 MiB para cada metadata y 8 MiB para cada resultado/informe. Se rechazan enlaces/reparse, traversal, claves JSON duplicadas, hashes ausentes o contradictorios y schemas desconocidos. El lector histórico verifica ownership/manifiesto y hashes de review.json/informe.md, validez pura del resultado, coincidencia de scope e ID cuando el schema los exige. No ejecuta scripts, resuelve evidence externa ni declara haber validado la ejecución completa.

Debe existir un resultado retenido estable, sin transacción pendiente de retain/close/checkpoint/trace/restart/transfer/cleanup identificable. Se leen de nuevo manifiesto/marker/resultado al terminar; cualquier cambio impide publicar el paquete. Esta lectura optimista no promete exclusión frente a escritores antiguos: solo se porta una fuente sin escritores activos según la condición operativa indicada al usuario. Los demás casos se conservan y explican, sin modo force.

Cleanup pendiente por sí solo puede coexistir con un resultado retenido estable; en ese caso se preserva explícitamente y no se presenta como cierre completo. Sin review.json o informe retenido verificable no existe portada válida: solo diagnóstico. No se sintetiza un veredicto a partir de un checkpoint.

### Archivos y semántica

| Archivo | Contenido |
|---|---|
| informe.md | Bytes del informe original verificado; no regenerar ni modernizar su contenido |
| consulta.json | historical_schema=1; port_id; original_review_id/null; scope completo original; presentation/null; verdict y reason; source_created_at/null; estado/disposición/retención/cleanup originales conocidos; limites de consulta y procedencia |
| .ccr-history.json | kind=historical_review; schema_version=1; identidad/hashes de fuente y hashes de informe.md/consulta.json; operación de portabilidad e inventario exacto |

La información de fuente incluye archive/result schema, skill version conocida, repository key, hashes observados y ruta exacta original en metadata privada. No añade autores, pruebas, historial de perfil, hallazgos estructurados ni evidence porque el informe original ya permite consultar el resultado. original_review_id desconocido queda null. Los tres archivos son locales/privados, sin publicación automática.

La escritura usa staging exclusivo verificado dentro del destino; al reintentar solo elimina staging inequívocamente propio. Publica el directorio completo mediante rename sin overwrite en el mismo volumen. Un fallo no modifica la fuente ni produce un paquete aceptado parcialmente. No hace backup/migración/rollback del origen porque no lo modifica.

show valida el paquete, muestra un aviso externo al informe («consulta histórica; no revalidada; evidencias y enlaces originales pueden no estar disponibles») y reproduce informe.md. Integridad del paquete no demuestra vigencia ni corrección del veredicto original. La copia sigue consultable si desaparece la fuente; esto no se confunde con nueva verificación de procedencia.

No hay continue/resume/recover/restart/cleanup/transfer/retain/publication/delivery nativa desde un paquete histórico. Una revisión nueva usa prepare normal, fresh recursos y referencias de procedencia al paquete si el ID es conocido; no pasa el paquete como --previous-run ni inventa lineage operativa. Si el ID original es desconocido, la referencia histórica lo dice.

## 5. Guard y «último resultado»

Se reutiliza find_candidates y compare_inputs. Una petición genérica mantiene elección explícita; una petición inequívoca de repetir resuelve el guard. «Mostrar el último resultado» habilita `lookup --select latest`: exclusivamente para consulta, no continuación, restart ni aprobación.

El selector considera solo native layout 2 con resultado retenido completo verificable, scope exacto y logical_scope_identity coincidente. Ordena por created_at verificado en UTC, no por mtime, cursor, ID ni nombre de carpeta. Muestra la appraisal applicable/changed/unknown de las demás entradas, sin convertir fecha en vigencia. Campos de scope distintos excluyen; perfil/requisitos/configuración distintos se muestran como diferencias históricas y nunca autorizan continuidad.

El resultado es selected/no_match/ambiguous/incomplete_search. Un empate de created_at entre dos IDs es ambiguous. La selección recorre páginas dentro del grupo solicitado; máximo 10.000 candidatos. Si no termina por ese límite o error de lectura de un candidato cuya elegibilidad no puede decidirse, devuelve incomplete_search y no selecciona. No ignora en silencio un resultado posiblemente más reciente. Una integridad conocida como inválida lo excluye y lo informa.

Los candidatos legacy y los paquetes históricos nunca compiten automáticamente con nativos por ser «el último». `--include-history` permite listarlos para elección explícita y show histórico; una consulta explícita de un HP concreto no requiere el origen. Lookup conserva separación de repositorios, límites de página 1–100, ausencia de red y cero mutaciones. El cursor nuevo es versionado y se rechazan los anteriores con instrucción de reiniciar la consulta.

Antes de mostrar, se inspecciona otra vez el candidato seleccionado para detectar cambios. El informe no recibe fechas nuevas ni un nuevo ID. Ninguna consulta dispara --delivery, comentarios, agentes o checks. Un formato antiguo se ofrece para portar o iniciar una revisión nueva, nunca se presenta como resultado nativo actual.

## 6. Subaspectos ABCDE y referencias

| Área | Subaspectos explícitos |
|---|---|
| A | Responsabilidades, dependencias, cohesión/acoplamiento, patrones, mantenibilidad y complejidad con consecuencia |
| B | Requisitos, invariantes, validaciones/límites, errores, testabilidad y escenarios de prueba |
| C | APIs, eventos, serialización, consumidores, compatibilidad y orden de despliegue |
| D | Consultas, integridad, transacciones, migraciones, concurrencia de datos y recuperación |
| E | Autorización, aislamiento, recursos/memoria, concurrencia, rendimiento, resiliencia y observabilidad |

Se seleccionan solo mecanismos afectados. Un subaspecto puede cruzar áreas, con una causa/hallazgo único. Missing tests, estilo, número de líneas o mera presencia de un patrón no prueban un defecto. No se agregan puntuaciones ni se fija severidad por dimensión.

Se amplía review-areas.md como índice y se crean tres referencias especializadas pequeñas: design-testability.md, contracts-data.md y security-operation.md, en references/dimensions/. Las cargan solo los revisores asignados cuando la pregunta/flujo las requiere. Contienen disparadores, preguntas, evidencia y ejemplos concisos; no reglas particulares de ACE Engine aplicadas universalmente.

Los briefs registran subaspectos junto a flujos e invariantes antes del trabajo. Contexto y asignaciones del perfil actual conservan su selección/autoridad; incorporar un foco nuevo a trabajo iniciado usa las reglas existentes de asignaciones/transiciones, sin relabel retrospectivo. coverage.areas mantiene cinco filas y sus estados; details expresa evidencia y gaps relevantes. Packet/final schemas permanecen iguales. El reporte privado conserva la matriz; comentarios públicos no reciben la taxonomía interna.

## 7. Componentes y documentación

- `review_layout.py`: lógica pura única de descriptor, nombres, reconocimiento y validación de layout 2.
- `review_history.py`: lector histórico acotado, portabilidad de tres archivos y consulta verificable; no importa mutadores legacy.
- `review_artifacts.py`, `review_restart.py`, `review_resource_claims.py`: archive 8 y todas las rutas de creación/reserva/validación; preservar las transacciones actuales exclusivamente nativas.
- `review_recovery.py`, `review_inputs.py`: lookup actualizado, identidad lógica, latest e inventario histórico explícito.
- `review_delivery.py`: consumir clasificación/rutas nuevas para archivos nativos; no aceptar HP como run. No reescribir entregas existentes.
- Referencias, SKILL.md, README y usage: guard, restricciones de formatos antiguos, CLI, dimensiones y límites del visor.

El test_reference_layout actual exige un catálogo exacto de referencias. Su catálogo se actualiza con los tres nuevos documentos de dimensiones y archive/history.md, y todos los enlaces locales siguen verificándose. Los documentos históricos de diseño describen versiones previas y no se reescriben como si hubieran adoptado el contrato nuevo.

## 8. Pruebas y aceptación

Usar fixtures sintéticas públicas; no inspeccionar ni portar archives reales durante la implementación. Windows y POSIX son objetivos; symlinks que el host no permita se informan como skips, no como validación positiva.

Cobertura mínima: nombres ordenables; mismo MR con dos heads y dos ejecuciones del mismo head; límites distintos; colisiones de abreviaturas; Windows/traversal/longitud; prepare y restart reservando exactamente el mismo formato; recuperación sin duplicación; claims y locks intactos; old layout rechazado antes de mutar; latest con páginas, empate, unknown/changed e inspección posterior; fuente histórica intacta; copia idempotente e interrupción; fuente ausente tras portar; hashes alterados; informe sin datos esenciales; pendientes no exportables; port no aceptado por mutadores; cinco filas ABCDE sin escalada ni hallazgos duplicados.

No basta cambiar tests para que acepten menos: los gates de ejecución, perfiles, locks y fuentes de 2.12.1 siguen siendo obligatorios en nativos. Las pruebas anteriores de operación legacy pasan a probar rechazo tipado; las de validación de contenido histórico permanecen. Suite completa y matrices extensas documentadas antes de declarar implementado; el visor no se verifica aquí.

## 9. Orden y entrega

Implementar primero contrato puro y rutas nativas, después clasificación histórica/portabilidad, consulta latest, subaspectos y cierre documental/integrado. Se conservan baseline y resultados observados en un registro de validación de implementación; estos documentos no afirman que el producto propuesto exista.

La versión futura registrará un cambio incompatible de formato de archivo con su guía de actualización. La numeración de release se decide al preparar su publicación; no se publica desde este trabajo preparatorio. Ejecución nativa o por subagentes queda pendiente de elección explícita del usuario.
