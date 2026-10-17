# Autoridad de perfiles y exclusión por sesión

Fuente: [CR-be2068928e0b4527b105](https://github.com/omarfrancodev/comprehensive-code-review/pull/19#issuecomment-6221922736), HEAD 46038d1, F058–F060.

## Requisitos

- F058: una selección automática, incluso del mismo perfil, no sustituye una decisión explícita. Solo una selección explícita posterior con autoridad del usuario permite cambiarla. La misma regla valida historia, selección mutante y gates finales schema 10; no cambia perfiles, IDs ni esquemas.
- F059: el preflight, lectura final y commit de un claim se excluyen por directorio canónico de sesión además del run. Dos registros concurrentes en runs diferentes tienen un único ganador; el perdedor no cambia el sidecar ni compromete una fila owned. Registrar varias sesiones adquiere sus locks en orden estable y conserva la prevalidación del conjunto.
- Transferencia y cleanup cooperan con ese mismo lock por sesión: ninguna operación puede modificar/borrar la sesión mientras otra decide su propiedad. Los locks son no bloqueantes, reentrantes en el mismo hilo y se liberan ante BaseException. Un conflicto pide reintentar, no concede propiedad. El lock vive fuera del directorio que cleanup puede eliminar.
- F060: el archivo final del lock debe ser regular y no enlazado; no escribir ni bloquear un target ajeno. Validar antes de abrir y validar el descriptor antes de escribir. En Windows abrir con FILE_FLAG_OPEN_REPARSE_POINT y sin compartir borrado; en POSIX usar O_NOFOLLOW. Rechazar hardlinks múltiples y cambios de identidad observados. Conservar las verificaciones existentes de ancestros y aliases.
- Python 3.10+, biblioteca estándar, sin servicios/dependencias nuevos. Archive 7/final 10 y 2.12.0 pendiente permanecen. No rollback F050/F052, merge, release ni cambios a reviews reales.

## Diseño

La protección de selección se aplica también cuando profile no cambia; validate_history reutiliza esa transición y los gates ya consumen la historia validada. Se reutiliza review_run_lock para exclusión por directorio canónico; review_resource_claims expone session_claim_locks para sesiones verificables existentes. register mantiene run antes de sesión; transfer mantiene ambos runs antes de sus sesiones. Cleanup adquiere sesión antes de comprobar claim/run: como todos los locks fallan inmediatamente ante conflicto, el orden no provoca esperas circulares y obliga a reintentar sin borrar.

La apertura segura pertenece a review_run_lock y sirve tanto para runs como sesiones. El check estático de path no sustituye la apertura sin seguimiento. Windows valida los atributos del handle con la API del sistema; POSIX valida fstat/lstat y regularidad. Un archivo inseguro o un conflicto conserva los recursos y no elimina archivos de coordinación.

## Verificación y límites

Pruebas de la cadena explicit/deep → automatic/deep → automatic/focused, rechazo sin mutación por select_profile e historia final manipulada; sustitución explícita autorizada y perfiles automáticos válidos siguen funcionando. Dos procesos reales se sincronizan después de leer el digest y antes de escribir; solo A registra y B conserva su archivo. Probar conflictos de la misma sesión durante transferencia y cleanup, liberación y orden múltiple. Probar enlace final preexistente, sustitución después del check inicial y archivo normal/reentrancia/conflicto entre procesos. Symlinks requieren privilegio del sistema; si faltan, registrar la omisión y ejecutar la variante hardlink sin fingir equivalencia total. Ejecutar la suite del proyecto y controles estáticos antes de subir el PR.

Fuentes de apertura Windows: [CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew) y [reparse points](https://learn.microsoft.com/en-us/windows/win32/fileio/reparse-points-and-file-operations).

## Decisión durante implementación

La prueba del baseline mostró que crear archivos de coordinación en .worktrees/.review-locks altera el estado Git de un checkout que no ignora .worktrees. Se sitúan los locks de sesión en git-common-dir/ccr-session-locks, con identidad por directorio canónico de sesión y raíz verificada. No se modifica .gitignore ni la configuración Git del producto. register bloquea también sesiones predeclaradas, no solo los argumentos nuevos.

Una invocación puede incluir sesiones de varios worktrees o clones de la misma identidad de repositorio. Se agrupan por directorio Git común real y se adquieren todos los grupos en orden estable, liberándolos mediante ExitStack ante rechazo o interrupción. La comprobación existente de repository_identity sigue decidiendo si el registro es válido; una ruta de checkout distinta no lo invalida.

## Seguimiento del noveno CCR: F061–F064

Fuente: [CR-558a05cecb09454b8c5f](https://github.com/omarfrancodev/comprehensive-code-review/pull/19#issuecomment-6227750986), HEAD ae19410. Las reservas F050/F052 y los contratos anteriores permanecen.

- F061: obtener el directorio Git común con `rev-parse --git-common-dir`, sin `--path-format`. Anclar una respuesta relativa al checkout que ejecutó Git; aceptar también respuestas absolutas. Mantener `_safe_path` y los guards de coordinación antes de resolver rutas: ni una respuesta de Git ni un `.git` enlazado autorizan saltarlos. Eliminar la dependencia de esa opción no equivale a certificar un binario antiguo no disponible.
- F062/F063: fijar la cadena explicit/deep → explicit/focused → automatic/focused, tanto sin autoridad como con una cadena no nula en la selección automática. Comprobar el diagnóstico específico de transición, su rechazo en la historia y la aceptación de una sustitución explícita mediante select_profile, incluyendo el evento de traza que la vincula al historial.
- F064: incluir record_artifact en la exclusión cooperativa por sesión. Cargar inicialmente solo para identificar la sesión, adquirir el lock existente y volver a cargar el manifiesto antes de decidir y guardar. El conflicto falla sin informar un registro exitoso ni sobrescribir entradas; el operador reintenta después de liberar el lock. Mientras el escritor está en el commit real, otro registro y cleanup deben fallar sin cambiar la sesión; tras el reintento se conservan ambos registros y cleanup puede completarse.

La exclusión coordina los helpers, no las escrituras arbitrarias de fixtures. Se mantiene la obligación de finalizar escrituras y detener workers antes de registrar o limpiar. No hay locks nuevos dentro del checkout, esperas bloqueantes, cambios de schema ni rollback adicional.

## Seguimiento del décimo CCR: F065–F067

Fuente: [CR-139ef46a80564e4a883c](https://github.com/omarfrancodev/comprehensive-code-review/pull/19#issuecomment-6229938583), HEAD 713e507. F050/F052 quedan fuera del alcance del PR por [decisión del mantenedor](https://github.com/omarfrancodev/comprehensive-code-review/pull/19#issuecomment-6228895961), con seguimiento en #20/#21; no se reevalúan ni son condiciones de aprobación.

- F065: distinguir la contención real mediante LockConflictError, compatible con ValueError. Los wrappers de registro y cleanup solo añaden la instrucción de preservar/reintentar ante ese tipo. Los fallos de consulta Git conservan contexto de coordinación mediante CoordinationError, también compatible con ValueError, por lo que la CLI devuelve su JSON de error incluso al ejecutarse el script como __main__. La apertura del archivo conserva la causa de E/S; errores del bloqueo distintos de EACCES/EAGAIN no se convierten en contención. Los errores de JSON, Unicode y E/S del cuerpo mantienen su tipo/identidad. Siguen vigentes los guards específicos de ownership, hashes e intents durables; ninguna clasificación de error autoriza borrar o saltarlos.
- F066: un escritor válido registra un artefacto después de que el otro haya tomado su snapshot inicial y antes de adquirir su lock. La operación exterior debe conservar ambas entradas al releer. Un mutante aislado que reutiliza el snapshot obsoleto debe perder una entrada y hacer fallar esa prueba; no se modifica el algoritmo de relectura, que ya era correcto.
- F067: el cuerpo del PR debe sustituir las reservas excluidas por una sección de fuera de alcance, enlazar la decisión y los issues, y reflejar el mismo criterio en compatibilidad e integración. La documentación histórica conserva lo que se verificó en cada revisión sin convertirlo en una reserva nueva del PR.
