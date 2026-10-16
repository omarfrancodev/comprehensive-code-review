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
