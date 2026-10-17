# Validación del octavo CCR del PR 19 — 2026-10-16

Fuente: [CR-be2068928e0b4527b105](https://github.com/omarfrancodev/comprehensive-code-review/pull/19#issuecomment-6221922736), HEAD revisado 46038d1.

## Correcciones

| ID | Comportamiento corregido | Evidencia |
|---|---|---|
| F058 | Una recaptura automática del mismo perfil no elimina la autoridad explícita; el historial y los gates finales rechazan esa cadena | Validación pura, historia/final y select_profile sin escrituras; transición explícita posterior válida |
| F059 | Registro, transferencia y cleanup se excluyen por sesión además del run | Dos procesos reales no pueden comprometer propietarios incompatibles; el perdedor conserva sidecar/manifiesto |
| F060 | Apertura del archivo final sin seguimiento de enlaces y comprobación del descriptor antes de escribir | Hardlink existente e insertado tras precheck rechazados sin tocar target; dos pruebas de symlink omitidas por WinError 1314 |

F050 y F052 permanecen reservas del rollback de adopción/transferencia durable; no se presentan como resueltas ni se limpia ninguna review real. Archive 7/final 10 y 2.12.0 pendiente no cambian.

## RED/GREEN

El primer run de ocho pruebas reprodujo tres fallos de autoridad y el doble propietario entre dos procesos (B terminaba registered después del commit de A). La creación de hardlinks estaba restringida por el sandbox; fuera de él, la prueba reprodujo la adquisición insegura del archivo ajeno. Los symlinks no pudieron crearse por privilegio del sistema incluso fuera del sandbox; son omisiones, no reproducciones aprobadas.

Dos regresiones adicionales reprodujeron problemas dentro de la primera solución: sesiones predeclaradas no se bloqueaban con register([]), y el lock hermano de la sesión alteraba el baseline del checkout. El inventario completo se bloquea ahora antes del preflight; la coordinación vive en git-common-dir/ccr-session-locks sin editar .gitignore ni configuración del producto.

La revisión estática independiente encontró que exigir una sola ruta de repo rechazaba sesiones válidas de varios worktrees. Se reprodujo el rechazo y se agrupa por Git common directory con ExitStack; el validador existente de identidad de repositorio sigue decidiendo la admisibilidad. También se verifican clones locales con el mismo origin. El primer intento de clonar dentro del sandbox falló por NtCreateDirectoryObject de Git/MSYS; no se cuenta como fallo de producto ni como RED del control. Fuera del sandbox, ambas variantes pasan. La relectura estática no señaló defecto residual concreto; el revisor no ejecutó tests ni escribió archivos.

La tanda focal definitiva terminó **OK: 16 pruebas en 69.658 s, 14 aprobadas y dos omitidas**, exit 0. Las 25 pruebas existentes de perfiles y las tres de locks también pasaron. La selección preliminar de resource_claims se interrumpió al cambiar la raíz de coordinación; no se cuenta como aprobada ni sustituye la suite final.

## Casos ejecutados

- test_review_authority_and_claim_safety.py: continuidad explícita en selección, historia y gate final; nueva selección explícita válida; rechazo sin escrituras en el run.
- `test_concurrent_registration_commits_only_one_session_owner` y `test_concurrent_registration_also_locks_predeclared_sessions`: procesos independientes, barrera real después de leer digest y antes de escribir sidecar. A compromete su claim, B falla sin sobrescribirlo ni añadir filas. No se simula la lógica de ownership.
- `test_transfer_conflicting_with_session_lock_preserves_both_runs` y `test_bootstrap_cleanup_conflicting_with_session_lock_preserves_session`: un segundo proceso mantiene el lock; los mutadores rechazan sin tocar recursos. Cleanup posterior sí termina y no reporta cambio del checkout.
- `test_claim_coordination_does_not_change_checkout_baseline`, `test_registration_accepts_sessions_from_two_worktrees` y `test_registration_accepts_sessions_from_two_clones_of_same_repository`: baseline estable y compatibilidad con distintas vistas del repositorio.
- `test_session_locks_release_after_baseexception_and_reenter_in_stable_order`: KeyboardInterrupt, orden múltiple, duplicados y reentrancia.
- `test_final_hardlink_is_refused_before_writing_foreign_bytes` y `test_hardlink_inserted_after_precheck_is_refused_by_opened_identity`: enlaces reales y target intacto.
- `test_existing_final_symlink_is_refused_without_touching_target` y `test_final_link_replacement_after_identity_check_is_refused`: **omitidas**, no hay privilegio Windows para crearlos. La variante hardlink no sustituye su cobertura de reparse points.

## Suite completa y controles

La primera ejecución completa terminó con **551 pruebas en 2208.969 s: 547 aprobadas, un error y tres omisiones**. El error fue `test_cleanup_crash_after_delete_recovers_own_intent`: el nuevo wrapper convertía el OSError de una interrupción de E/S en ReviewError y alteraba el contrato de recuperación. Se limita el wrapper a errores de verificación/lock; la E/S vuelve a propagarse como antes. El caso original pasó después en 15.757 s, exit 0. No se omite ni se atribuye este fallo al entorno.

La repetición completa posterior terminó **OK: 551 pruebas únicas, 548 aprobadas, cero fallos/errores y tres omisiones**, exit 0 en los tres procesos. Se comprobó igualdad de inventarios, ausencia de duplicados y unión exacta de las 551 pruebas; las tandas focales no se suman otra vez.

| Grupo de módulos | Ejecutadas | Omitidas | Duración del proceso | Resultado |
|---|---:|---:|---:|---|
| 0 | 184 | 2 | 1637.033 s | OK |
| 1 | 184 | 1 | 768.859 s | OK |
| 2 | 183 | 0 | 414.940 s | OK |

Los grupos se ejecutaron en paralelo; sus duraciones no se presentan como una única duración de pared. Incluyen ambas matrices extensas de reemplazos de transferencia/adopción y la regresión original de recuperación después de borrado. El inventario de la repetición coincide con el de la primera ejecución completa.

Las tres omisiones corresponden a privilegios de symlink: las dos pruebas nuevas de archivo final y test_symlink_roots_inputs_and_archived_files_are_refused. Las variantes reales de hardlink sí pasaron.

Pasaron AST de los siete archivos Python modificados/nuevos, enlaces relativos de seis documentos, existencia de tests referenciados y git diff --check. No se cambió código del producto tras iniciar la repetición completa. Se conserva el PR abierto y el worktree para revisión humana.

## Límites

Windows con Python 3.12.14, biblioteca estándar y Git con repositorios/archivos temporales; la suite completa se lanza fuera del sandbox porque restringe Git/MSYS y hardlinks locales. No se verifican runtime POSIX ni symlinks de archivo en este equipo. El rechazo nativo de reparse points se apoya en apertura Windows sin seguimiento y atributos del handle, sin atribuirle una prueba omitida: [CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew), [reparse points](https://learn.microsoft.com/en-us/windows/win32/fileio/reparse-points-and-file-operations).

La exclusión es cooperativa entre los helpers, no una defensa frente a procesos externos que manipulen por su cuenta los recursos. Los conflictos no esperan ni borran locks: requieren reintentar con autoridad vigente. Los archivos de coordinación permanecen tras soltar el lock para conservar un único inodo. No se ejecutan merge ni release en esta ronda.
