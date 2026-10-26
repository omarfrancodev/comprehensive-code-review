# Equivalencia de revisiones y cobertura de CCR

Estado: implementación y validación integradas completadas en el worktree; 868 casos, 865 aprobados y 3 omitidos por privilegio Windows, sin publicación. Fecha: 2026-10-25, America/Mexico_City.

Base: CCR 3.1.0, `main` en `4fab30695bb3c0c47071eb887b38f92328b03ea2`.

[Diagnóstico y evidencia](../../analysis/2026-10-25-review-reuse-and-coverage-diagnosis.md) · [Plan](../plans/2026-10-25-review-equivalence-and-coverage.md).

## 1. Intención y límites

La reutilización depende de la equivalencia de los cambios revisados, no de la existencia de una revisión previa ni únicamente de los commits o SHA.

Para una solicitud ordinaria de CCR de MR/PR, comparar el alcance actual con el último resultado verificable del mismo alcance lógico antes de preguntar. Cambios efectivos nuevos, retirados o modificados, o equivalencia no demostrable, autorizan iniciar automáticamente un CCR nuevo con el alcance actual. Solo ofrecer repetir/consultar cuando la reutilización sea demostrablemente admisible.

También se mejoran las preguntas de descubrimiento y la disposición de observaciones a partir del MR 97. No se implementan arreglos de aquel proyecto, migración de archives, cambios de modelos, agentes adicionales por defecto, publicación remota ni medición de costos. No se retocan los gates de cierre e identidad de dispatch publicados en 3.1.0.

El usuario autorizó implementar este spec y plan en el worktree. La evidencia y los límites de validación se conservan en el [registro de implementación](../../validation/2026-10-25-review-equivalence-and-coverage.md).

## 2. Enfoque

Se recomienda un descriptor determinista del diff, dos comparaciones separadas y selección histórica verificada. Una regla de prompt sin evidencia no resuelve el problema. `patch-id` aislado no conserva toda la información necesaria. Comparar árboles completos como único criterio rechaza todo rebase con cambios upstream ajenos al análisis.

Se conserva la arquitectura Python/stdlib por capas. Módulos propuestos: `contracts/effective_changes.py` valida el descriptor; `execution/change_scope.py` obtiene bytes Git; `workflow/reuse.py` compara y decide; `archive/reuse.py` integra lookup y archivos verificados. Las CLIs actuales delegan en ellos.

No se cambian archive 8/layout 2, final review schema 10, trace schema 1 ni packet version 1. Nuevos sidecars privados usan schema 1 y los mecanismos existentes de selección, hashes y ownership. Una versión de release se decidirá al implementar, sin atribuir estas capacidades a 3.1.0.

## 3. Identidades distintas

1. **Exacta:** `scope`, fuentes capturadas y hashes originales. Sigue siendo obligatoria para resume/recover, transacciones, receipts, retención y cierre. `compare_inputs()` no se convierte en un comparador tolerante.
2. **Cambio efectivo:** rutas, clases/modos de archivo y hunks/contenido realmente revisados. Puede ser igual con base/head distintos.
3. **Aplicabilidad:** además del cambio efectivo, comprueba requisitos, descripción, instrucciones, configuración, contexto consumido y alcance autorizado. Un mismo diff no prueba que un consumidor modificado siga siendo seguro.

Un complemento acotado no acredita una revisión ordinaria completa del MR; tampoco una cobertura insuficiente u obsoleta. En esos casos se inicia una revisión nueva. Un resultado reutilizado conserva su ID, base/head, ubicaciones y revisiones de checks originales. Se comunica «cambios equivalentes a la revisión X» y la versión actual comparada, sin editar el informe histórico ni afirmar que se ejecutaron pruebas en el nuevo HEAD. La publicación remota sigue necesitando autorización y su verificación actual.

## 4. Alcance Git autoritativo

El coordinador identifica repositorio normalizado, proveedor/MR o PR, rama destino, commits de origen/destino observados y base efectiva del diff. Para MR/PR ordinarios, la comparación es `diff_base..head`, donde `diff_base` es la merge-base única entre target y source, contrastada con las referencias de diff del proveedor cuando están disponibles. No comparar solo `old_head..new_head`.

Capturar objetos inmutables antes de leer. Si la política del proveedor difiere, las bases múltiples no permiten determinar el rango, hay objetos ausentes, un diff remoto está truncado, la búsqueda es incompleta o las refs cambian durante la captura, no certificar equivalencia. No hacer fetch silencioso dentro del comparador: adquisición de referencias y permisos siguen perteneciendo al coordinador.

Un cambio de target que altere los hunks produce `different`, incluso con HEAD idéntico. Un merge vacío, rebase o cambio de mensajes/autor que conserve cambios y contexto material permite `equivalent`. Un historial con commits reales luego revertidos a los mismos cambios finales no exige review por mera historia; se conservan sus metadatos sin confundirlos con el cambio final.

## 5. Evidencia persistente

### 5.1 `evidence/effective-changes.json`

Se captura antes de discovery, dentro de la sesión propia de bootstrap. Campos exactos:

| Campo | Forma / significado |
|---|---|
| `schema_version` | `1` |
| `algorithm` | `ccr-effective-diff-v1` |
| `logical_scope_identity` | Digest existente del selector lógico |
| `comparison` | `{kind, base, head, target_head, diff_base, object_format}`; `kind=merge-base-to-head` para MR/PR; commits completos; object format observado |
| `complete` | Booleano; solo true si se capturó íntegra la comparación |
| `entries` | Lista ordenada de entradas de archivo definida abajo |
| `changes_sha256` | SHA-256 de la proyección canónica de entries, no de los SHA de provenance |
| `diagnostics` | Lista acotada de `{code, detail}`; nunca oculta una captura incompleta |

Cada entry contiene exactamente `{old_path_b64, new_path_b64, old_mode, new_mode, kind, old_blob, new_blob, payload}`. Las rutas son bytes Git codificados base64, case-sensitive, sin normalizar mayúsculas ni reemplazar caracteres inválidos. `kind` es `text|binary|symlink|gitlink`. Las altas/bajas usan null para el lado ausente; los OID reales y modos se conservan como procedencia.

`payload` es `{patch_b64}` para texto y `{old_sha256, new_sha256}` para binarios/symlinks, con null si falta un lado. Para gitlinks es `{old_commit, new_commit}`: el commit de submódulo sí forma parte del contenido revisado. El cambio de tipo/modo nunca se pierde.

La proyección canónica excluye `old_blob/new_blob`, comparison y diagnostics. Incluye rutas, modos, kind y payload, ordenados por bytes de ruta. Se codifica JSON UTF-8 con claves ordenadas, separadores compactos y sin NaN. Dos digests iguales requieren además validar la forma y comparar la proyección completa; un digest suministrado no es evidencia suficiente.

### 5.2 Canonicalización y límites

Obtener nombres/modos mediante Git NUL-delimited con detección de renames deshabilitada: un rename es una baja y un alta deterministas, sin heurísticas sensibles a versión/configuración. Capturar el patch textual con `--no-ext-diff --no-textconv --no-color --no-renames --full-index --diff-algorithm=myers --unified=3`; los adaptadores manejan bytes, no el helper textual que usa `errors=replace` y `.strip()`.

Por entrada, quitar solo cabeceras de transporte/rutas redundantes, líneas `index` y coordenadas `@@`; conservar en orden cada hunk, sus bytes de contexto, líneas añadidas/eliminadas y marcadores de falta de newline. No eliminar whitespace, CR, espacios finales ni líneas de contexto. Rebasar con desplazamiento de líneas sin alterar hunks admite equivalencia. Cambiar contexto de un hunk invalida esa equivalencia conservadoramente.

Límites iniciales: 10.000 entradas, 32 MiB de patch agregado sin codificar, 64 MiB para descriptor serializado y 100 diagnósticos. Binarios se hashean en streaming sin retener su payload. El colector corta y devuelve `complete=false` al exceder límites; nunca acepta un prefijo como comparación completa. Se respetan además los límites existentes de selección: 64 fuentes y 64 MiB agregados, incluido reference-index; se aplica el límite más restrictivo.

No depende de diff settings del usuario, checkout CRLF, filtros externos o comandos ejecutables de `.gitattributes`. No modifica worktree/index ni ejecuta código de producto. La revisión de submódulos sigue acotada al gitlink salvo alcance explícito adicional.

### 5.3 Materiales actuales antes de discovery

El coordinador captura `evidence/reuse-materials.json` en el bootstrap previo al lookup. Campos exactos: `{schema_version, complete, entries, diagnostics}`, con schema_version 1 y entries de forma `{key, purpose, reference, sha256}`. Las keys, ausencia observada y propósitos tienen la semántica de la sección siguiente. Incluye todas las fuentes materiales del índice inicial; se excluyen únicamente los sidecars generados effective-changes y reuse-materials. El reference-index no se indexa a sí mismo. Una fuente other aportada por el usuario no se excluye por su propósito.

`setup materials` recibe `{session, arguments}` con arguments `{materials, complete, diagnostics, reference_index}`. `reference_index` identifica el índice propio ya seleccionado; verifica cobertura exacta del conjunto de entradas materiales y cada referencia/digest contra sus bytes, permitiendo aliases validados. La completitud es una observación del coordinador sobre las fuentes requeridas, no una inferencia del builder basada en un conjunto vacío. Si no puede acreditarse una key estable para entradas múltiples o hay fuentes materiales desconocidas, `complete=false`.

Los nuevos envelopes de materials/reuse-context se leen con límite de 64 MiB, sin ampliar el límite de 128 KiB de los comandos setup anteriores. Los límites de fuentes/selección siguen aplicándose antes de escribir; excederlos impide declarar una captura completa.

La secuencia evita una dependencia circular: seleccionar fuentes externas e índice provisional -> validar/capturar mapa y descriptor Git -> añadir ambos sidecars generados al índice final con purpose=other -> `setup inputs` captura el índice final y bytes antes de prepare/discovery. Los gates de preparación verifican la versión final del índice. No se vuelve a modificar después del inicio. El evaluador verifica que el mapa cubra el índice final, excepto esos dos sidecars generados.

### 5.4 `evidence/review-context.json`

Se completa al consolidar discovery, a partir de lecturas efectivas de objetos Git ya fijados; no modifica entradas capturadas inicialmente. Campos exactos: `{schema_version, logical_scope_identity, scope, files, materials, complete, diagnostics}`. `schema_version=1`; `scope` conserva los siete campos actuales exactos.

`files` contiene `{side, path_b64, mode, content_sha256}`, con `side=base|head`, para archivos completos inspeccionados: productores/consumidores, instrucciones Git, configuración y tests relevantes. El lado se resuelve contra diff_base/head registrados. No asignar `complete=true` solo por enumerar los archivos cambiados; el coordinador recoge el inventario de lecturas de cada owner. La ausencia de inventario completo impide reutilización general. No se necesita registrar cada comando ni crear un trace paralelo.

Por prudencia, cambios upstream fuera del hunk pero dentro de un archivo completo que sustentó el análisis cambian el contexto. En ese caso el diff puede seguir equivalente y el resultado requiere revisión nueva por contexto; el caso de rebase reutilizable es aquel que no altera esos insumos, aunque cambien árboles ajenos a ellos.

`materials` conserva los entries del reuse-materials inicial para las entradas no Git que influyeron: description, requirements, notes, plan, configuration u other. `key` es una identidad semántica estable observada (por ejemplo `mr-description`, URI de requisito o ID de nota); `reference` apunta a bytes seleccionados por el reference-index original y el digest debe coincidir. No emparejar documentos múltiples por orden ni por nombre de archivo casual. Una entrada opcional observada como ausente se representa mediante su key/purpose, reference null y sha256 null; omitir una entrada desconocida no prueba ausencia.

Los sidecars son evidencia privada, seleccionada y hash-verificada por `cierre.json`. El descriptor y reuse-materials iniciales se incluyen en `review_inputs.sources` e index `purpose=other`. El review-context final es evidencia de consumo de Git fijado, no una nueva fuente material que se invente después del inicio. Si discovery encuentra un requisito material no capturado, se aplica el gate existente para entradas nuevas; no se añade retroactivamente al índice inicial.

## 6. Decisión antes de preguntar

`artifacts assess-reuse` es de solo lectura. Consume repo, scope-file, current-inputs, descriptor actual, `--current-materials` y `--session` del bootstrap propio. Resuelve fuentes únicamente dentro de esa sesión y verifica su índice final contra current-inputs, con los límites existentes. Reproduce el inventario Git completo del review-context anterior contra los objetos actuales y lo compara con los materials actuales ya capturados: no necesita discovery actual para efectuar esta comprobación. Sin inventario anterior completo o mapa actual acreditado, la aplicabilidad permanece unknown.

Consulta el grupo exacto con el mismo límite de 10.000 candidatos de lookup. Usa el último resultado nativo completo y hash-verificado con timestamp de metadata único. Reutiliza el algoritmo de selección, sin duplicar sus reglas ni buscar una revisión más antigua que casualmente sea equivalente. No usa mtime, orden de carpetas o run ID. Un perfil explícito incompatible con el resultado previo requiere revisión nueva; no se certifica un perfil solicitado con uno distinto por mera igualdad de código.

La salida contiene `{schema_version:1, action, code_equivalence, applicability, prior_run, reasons, changed_paths, metadata_only}`. `action=offer_choice|new_review|blocked_current_scope`; `code_equivalence=equivalent|different|unknown`; `applicability=applicable|changed|unknown`. `prior_run` solo identifica el candidato revalidado, o null. `metadata_only` registra diferencias de commits sin fingir diferencias de código.

| Condición | Decisión de una solicitud ordinaria |
|---|---|
| No hay resultado completo previo | `new_review`, sin pregunta |
| Mismo diff y contexto/entradas materiales comprobados | `offer_choice`: iniciar nueva revisión / consultar último resultado |
| Cambios efectivos distintos, en cualquier archivo o hunk | `new_review`, sin pregunta, alcance actual completo con análisis incremental justificado |
| Diff equivalente, contexto o entradas materiales cambiados | `new_review`, sin pregunta; el motivo distingue contexto de código |
| Falta evidencia anterior, captura incompleta, empate o integridad inválida | `new_review`, sin reutilizar el resultado ni inventar previous-run |
| Alcance actual ni siquiera puede fijarse | `blocked_current_scope`: explicar adquisición faltante; no fingir que se revisó un alcance desconocido |

Las identidades observadas de descripción, requisitos, plan y configuración se comparan también cuando son etiquetas opacas: cambiar una etiqueta es cambio material; omitir una identidad conocida deja aplicabilidad desconocida. No basta que sus bytes seleccionados coincidan.

Un cambio solo de descripción/requisito/nota material genera una revisión enlazada acotada a ese impacto; el código y checks intactos pueden reutilizarse con razones explícitas. No se exige un review completo adicional solo por cambiar metadata generada, aliases, timestamp, responsables o mensajes de commit. Metadata pública se vuelve a comprobar al mostrar/publicar.

«Haz nueva revisión» siempre inicia una nueva. «Muéstrame la última» conserva consulta histórica explícita: mostrar el resultado verificado con su vigencia/limitación, sin iniciar otro CCR por sorpresa. La nueva decisión automática se aplica a solicitudes ordinarias de revisión, no a consultas históricas.

Antes de ejecutar la opción elegida, revalidar candidato y scope/refs actuales; si cambiaron, recalcular una vez para esa nueva captura y no reutilizar la decisión vieja. Los runs incompletos no son resultados reutilizables. Sus operaciones/recursos pendientes no se recuperan, adoptan o limpian automáticamente: usar recursos nuevos y las rutas de preparación existentes; si un gate legítimo bloquea la creación, conservarlo y comunicarlo.

## 7. Compatibilidad histórica

Sin sidecar, intentar reconstruir únicamente desde objetos exactos base/head disponibles y evidencia retenida que demuestre el rango revisado. No asumir que cualquier `delta.diff` corresponde al MR. No escribir metadata en el archive histórico ni certificar una reconstrucción como captura contemporánea.

Para contexto, se admite demostrar igualdad de los árboles base/head completos y de todas las entradas externas conocidas, o reconstruir un inventario cuya completitud esté acreditada en evidencia existente. No convertir un inventario ausente o fuentes incompletas en igualdad. Si no se puede demostrar, `unknown -> new_review`.

Los layouts no soportados siguen siendo consulta histórica; esta función no los migra ni los habilita para resume/restart. El vínculo de una revisión nueva usa `previous-run` solo cuando el candidato cumple los gates nativos; una ruta corrupta/ambigua se conserva como diagnóstico, sin enlace operativo inventado.

## 8. Calidad del descubrimiento y consolidación

Aplicar las mejoras dentro de briefs, `coverage.flows/limitations`, candidatos y findings existentes; sin nuevos campos de review.json ni nuevas cuotas de agentes.

| Cambio observado | Preguntas que se incorporan al owner existente |
|---|---|
| Validaciones/autenticación | Orden completo antes/después de demostrar credencial; respuesta, costo sensible y auditoría de cada rechazo |
| Transiciones de estado | Estado permitido distinto del nominal, transición repetida, fallo entre almacenes y efectos ya confirmados |
| Corrección previa | Mecanismo añadido, todos sus consumidores y sus nuevas obligaciones; no limitarse al escenario del finding original |
| Nuevo índice/cache/recurso | Creación, renovación, logout/borrado, expiración, error y limpieza; crecimiento por operación |
| Datos anteriores/despliegue | Productor anterior vs. lector nuevo, campos ausentes y ventana real de compatibilidad |
| Parámetros de integridad | Omisión en consumidores actuales o nuevos; un riesgo hipotético de futuro no se presenta como defecto confirmado actual |
| Lecturas/cadenas/lotes | Operaciones por petición y por N elementos; duplicación y transporte de datos sensibles |
| Tests verdes | Verificar si las assertions codifican el requisito o el comportamiento discutido; fixture exitoso no resuelve un contrato incorrecto |

Separar cuatro decisiones: observación, confirmación por escenario/consecuencia, prioridad, bloqueo. Un defecto confirmado puede ser P3 no bloqueante y sigue apareciendo. Compatibilidad relevante incierta usa limitación behavior con public_summary; una sugerencia especulativa queda privada con razón. Falta de métricas no elimina evidencia estática de crecimiento sin limpieza o N consultas adicionales; tampoco permite inventar latencia, caída o escala medida.

No publicar todos los candidatos ni aceptar literalmente todo comentario externo. No convertir «cubierta» en «todos los escenarios posibles demostrados»: derivar la matriz de escenarios/lecturas concretas y declarar los límites materiales. La verificación fresca recibe los candidatos y los invariantes asignados, incluyendo los efectos nuevos de las correcciones, conservando la topología de perfiles de 3.1.0.

## 9. Aceptación

1. Fixtures Git reales: HEAD nuevo por commit vacío/merge sin cambio y rebase equivalente ofrecen elección; modificación efectiva, edición de archivo ya revisado y base móvil que altera el diff inician revisión sin pregunta.
2. Comparación sensible a modos, binarios, gitlinks, symlinks, espacios, CR y newline final; rutas con espacios/tab/newline/Unicode no colisionan ni ejecutan texto.
3. Diff textual con mismos hunks desplazados conserva identidad; cambio de contexto o del consumidor inspeccionado impide reutilización general. El comparador no promete equivalencia semántica de programas arbitrarios.
4. Distintos SHA no contaminan la comparación semántica, pero resume/recover con SHA distinto siguen rechazados. Checks históricos conservan la revisión de ejecución.
5. Archives completos, antiguos reconstruibles, antiguos insuficientes, corrupción, empate, límite y run abierto tienen decisiones explícitas sin mutaciones.
6. Captura, retención y lectura verifican los sidecars y las fuentes indexadas; datos desconocidos y pruebas no ejecutadas no se convierten en cobertura ni en resultados nuevos.
7. Casos de política inspirados en MR 97 distinguen defecto no bloqueante, limitación relevante y propuesta refutada; usan fixtures sintéticos y no copian código o datos privados del proyecto.
8. La suite actual de recuperación, contratos, referencias, publicación, perfiles y cierre sigue válida. La implementación y sus resultados observados se detallan en el registro de validación, sin atribuir ejecuciones nuevas a revisiones históricas.
