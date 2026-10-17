# Validación del noveno CCR del PR 19 — 2026-10-16

Fuente: [CR-558a05cecb09454b8c5f](https://github.com/omarfrancodev/comprehensive-code-review/pull/19#issuecomment-6227750986), HEAD revisado ae19410.

## Correcciones

| ID | Resultado | Comprobación |
|---|---|---|
| F061 | Git common dir se consulta sin --path-format; respuestas relativas se anclan al checkout y las absolutas se conservan | Registro, transferencia y cleanup reales con una interfaz Git que rechaza la opción, en ambas variantes de respuesta |
| F062 | La autoridad de una segunda selección explícita tampoco puede ser sustituida por una recaptura automática del mismo perfil | Historia deep explícito → focused explícito → focused automático, con autoridad automática nula y no nula |
| F063 | Las aserciones identifican el guard de transición; la sustitución explícita válida pasa por select_profile | Dos filas conservadas, perfil/source correctos y evento profile vinculado al ID del historial |
| F064 | record_artifact se excluye con los otros mutadores de sesión y recarga antes de guardar | Dos procesos reales: conflicto sin mutación, cleanup excluido durante el commit, reintento que conserva ambos registros y cleanup final |

F050/F052 siguen como reservas; no hay rollback nuevo, migraciones, merge ni release. Archive 7/final 10 y 2.12.0 pendiente permanecen.

## RED/GREEN

La primera tanda de ocho pruebas falló con dos errores de subcaso del ciclo Git (la interfaz rechaza --path-format al registrar) y dos fallos por ausencia del rechazo esperado al registrar un artefacto bajo un lock ajeno. Los casos adicionales de autoridad pasaron: cubren comportamiento ya correcto, no un defecto vivo.

Tras las dos correcciones mínimas, los módulos test_review_session_operations y test_review_authority_and_claim_safety ejecutaron **17 pruebas en 77.647 s: todas aprobadas, sin omisiones**.

Una comprobación aislada compiló en memoria dos versiones defectuosas de validate_selection: volver a condicionar el guard a que cambie el perfil, y aceptar una selección automática si trae texto de autoridad. La prueba nueva de historia transitiva detectó ambos mutantes por aserción, sin errores de fixture ni cambios en los archivos productivos. Esos ejercicios no se suman al inventario de la suite.

## Suite completa y reanudación

El inventario descubierto contiene 556 IDs únicos. Los tres grupos son disjuntos (186/185/185); sus inventarios completos coinciden y su unión no duplica casos. Los grupos 0 y 1 terminaron con exit 0: 186 pruebas en 563.847 s sin omisiones, y 185 en 699.284 s con una omisión por privilegios de symlink.

La interrupción de la sesión detuvo el tercer proceso después de 172 casos aprobados, incluida la matriz completa de transferencia. Esa ejecución no tiene resultado final y no se presenta como un grupo aprobado. Se extrajeron los IDs con resultado explícito del log y se reanudaron únicamente los 13 IDs restantes; el caso de adopción interrumpido se vuelve a ejecutar completo. No se alteraron fuentes Python ni fixtures de prueba entre ambos intentos. Las tandas focales y las mutaciones aisladas no se suman al inventario global.

La reanudación terminó con exit 0: **13 pruebas en 186.771 s, 11 aprobadas y dos omitidas**. Se comprobaron los IDs de cada resultado observado contra el inventario original: **556 casos únicos cubiertos, 553 aprobados, cero fallos/errores y tres omisiones**, sin duplicados ni casos pendientes. Este resultado combina las dos ejecuciones completas, los 172 casos con resultado de la ejecución interrumpida y los 13 de su complemento; no se atribuye un exit 0 al proceso interrumpido ni una duración de pared a la suma de procesos.

| Parte | Casos con resultado | Omitidos | Duración informada | Estado |
|---|---:|---:|---:|---|
| Grupo 0 | 186 | 0 | 563.847 s | OK, exit 0 |
| Grupo 1 | 185 | 1 | 699.284 s | OK, exit 0 |
| Grupo 2 antes de la interrupción | 172 | 0 | No disponible | Casos aprobados; proceso interrumpido |
| Complemento del grupo 2 | 13 | 2 | 186.771 s | OK, exit 0 |

Las tres omisiones son test_symlink_roots_inputs_and_archived_files_are_refused y las dos pruebas de symlink del archivo final del lock. Las pruebas reales de hardlink pasaron. Ambas matrices de reemplazos durables (transferencia y adopción) pasaron; también la secuencia que ejecuta los comandos documentados y la conservación del checkout principal tras registrar fixtures y limpiar.

Los controles estáticos verifican sintaxis de los cuatro archivos Python modificados/nuevos, enlaces relativos de los seis Markdown, scopes/categorías del changelog y git diff --check. El worktree se conserva para la revisión del PR.

## Límites

Windows y Python 3.12.14, con repositorios, sesiones y artefactos desechables. No hay un binario antiguo de Git instalado: se controla únicamente esa frontera de consulta, conservando las operaciones reales del resto del ciclo. La variante relativa representa `.git` y la absoluta su ruta completa. No se afirma una ejecución en Git antiguo ni POSIX.

No se eximen rutas enlazadas de los guards existentes. Un Git common directory enlazado sigue siendo rechazado deliberadamente, coherente con las rutas de sesión/coordinación admitidas. Los locks son cooperativos entre helpers; no detienen un proceso externo que escriba directamente una fixture. El conflicto pide reintentar y no borra archivos de coordinación. No se modifican reviews reales.
