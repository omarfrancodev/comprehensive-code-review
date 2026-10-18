# Validación de correcciones posteriores a 2.12.0

Base: `6d520f7a2e51ec8ab5894a1c21f8a687d1939327` (`v2.12.0`). Rama: `fix/2.12.0-issues-20-21-22`. Fecha: 2026-10-17, America/Mexico_City.

## Alcance implementado

- **#22 / F068–F070:** los once rechazos explícitos restantes del lock y la creación de su directorio usan `CoordinationError`, con causa de E/S encadenada. La identidad de sesión se revalida bajo lock con ese tipo. Los tres wrappers conservan contexto de preservación, diferenciando contención reintentable de precondiciones fallidas. Restart reintenta exclusivamente `LockConflictError` y conserva el tipo al añadir el contexto del origen.
- **#20 / F050:** se implementó la alternativa de negativa explícita admitida por sus criterios, con fase `adoption_committed`, razón y una operación opt-in para registrar autoridad, evidencia y recibo idempotente en la traza del origen. No se implementó un rollback general de ownership ni se afirma que una adopción comprometida haya sido deshecha.
- **#21 / F052:** la negativa distingue la transferencia durable incluso cuando desaparece el sucesor; también cubre una adopción cuyo claim quedó registrado antes de desaparecer el workspace. La ausencia conserva `missing_unknown` y no crea cleanup, liberación ni recibos de cancelación exitosos.

El comando `record-restart-refusal` registra una decisión `refused`; su exit 0 certifica el registro, no la cancelación. Las operaciones de cancelación rechazadas siguen saliendo con JSON y exit 1. El restart original permanece pendiente. Las issues remotas no se cerraron ni editaron.

## RED/GREEN y revisión independiente

Las siete primeras regresiones de coordinación reprodujeron errores sin tipar, ausencia de guía de preservación y reintentos dependientes del texto. Pasaron después del cambio; se añadieron casos del wrapper de cleanup del archive y de reparse points.

Las cuatro regresiones iniciales de negativa durable fallaron porque no existía `record_restart_refusal`; después pasaron. Cubren adopción parcial con otro owner, transferencia ausente, autoridad/intent y replay de las siete sustituciones de archivos del origen.

Una revisión independiente estática detectó dos defectos de la implementación nueva: el gate genérico de transferencia impedía obtener la negativa tipada de CLI, y un sidecar ausente o degradado podía tratarse como un recurso sin owner pese a existir prueba durable del claim. Ambos se reprodujeron y corrigieron. La segunda pasada detectó que permitir transferencias en el gate podía cancelar el restart si faltaba el sucesor; se reprodujo RED y se añadió el rechazo desde la prueba durable del origen antes de comprobar si existe ese sucesor. Las tres regresiones específicas pasaron después de sus correcciones.

La prueba de ownership usa dos sesiones reales de fixture y comprueba tanto la eliminación como la degradación a `bootstrap` del sidecar presente. No modifica sesiones de reviews reales. La revisión independiente fue una inspección estática, sin afirmar ejecución propia ni un veredicto formal de CCR.

## Suite completa

Se descubrieron **581 IDs únicos**, asignados a cuatro particiones disjuntas: 290 y 289 casos generales, una matriz extensa de transferencia y una matriz extensa de adopción. La unión de inventarios y resultados por ID coincide con los 581 IDs, sin duplicados ni pendientes. Se conservaron inventarios, resultados, logs y hashes de fuentes Python en el directorio de validación ignorado del worktree principal.

| Grupo | Casos | Resultado inicial | Duración |
| --- | ---: | --- | ---: |
| General 0 | 290 | Todos aprobados | 873.531 s |
| General 1 | 289 | 285 aprobados, 3 omitidos y 1 fallo de mensaje | 834.562 s |
| Matriz de transferencia | 1 | Aprobada | 885.172 s |
| Matriz de adopción | 1 | Aprobada | 204.031 s |

La pasada completa obtuvo **577 aprobados, 3 omitidos y 1 fallo**: `test_abandon_cannot_orphan_prepared_successor` conservaba el rechazo seguro, pero el nuevo mensaje de selección vacía perdió su orientación a recuperar el sucesor preparado. Se restauró esa orientación y el caso aprobó en una tanda final de diez pruebas, todas aprobadas en 1.679 s, exit 0. También se endureció el reloj simulado del test que exige no reintentar un `ValueError` cuyo mensaje mencione contención: un mutante en memoria que restaura la discriminación por texto provoca el fallo esperado, sin errores de fixture ni cambios a archivos productivos.

El estado final combina la suite completa con esa reejecución focal: **578 IDs aprobados y 3 omitidos, sin fallos pendientes**. No se repitió toda la suite después del ajuste textual y del endurecimiento de la prueba. La comparación de hashes comprobó que esos fueron los únicos dos cambios Python posteriores a la pasada congelada; al invertir exactamente ambas sustituciones se recuperan sus hashes originales. El resto de fuentes permaneció idéntico.

Las tres omisiones corresponden a privilegios de symlink de Windows: `test_symlink_roots_inputs_and_archived_files_are_refused`, `test_existing_final_symlink_is_refused_without_touching_target` y `test_final_link_replacement_after_identity_check_is_refused`. Los hardlinks y la contención real sí se ejecutaron.

Los procesos usan Python 3.12 del runtime disponible y temporales propios. La ejecución fuera del sandbox permite comprobar los hardlinks reales bloqueados en la preparación. No se instalaron dependencias.

## Controles y límites

Pasaron el parseo AST de nueve archivos Python modificados/nuevos, la comprobación final de cinco enlaces relativos de los documentos afectados y `git diff --check`. El CHANGELOG añade una sección `unreleased` sin alterar la release publicada.

No se ejecutó runtime POSIX: la rama de `fcntl.flock` conserva su cobertura pendiente en ese entorno. Las pruebas de interrupción nuevas observan estados después de reemplazos atómicos del origen; no equivalen a una prueba de todos los cortes posibles del sistema operativo ni a certificar recuperación de datos ausentes. Un caso sin evidencia durable de claim no se convierte artificialmente en ownership conocido.

La observación de negativa se retiene como evento hash-bound de la traza, con autoridad e identidades/hashes de sus entradas. No certifica la vigencia futura del estado observado. La evidencia y los ownership records de sucesores y sesiones se conservan sin reescritura; únicamente cambia la traza del origen y su manifiesto/marker de integridad al registrar explícitamente la decisión.

Esta validación no incluyó merge, push, release ni activación sobre reviews reales. La creación de commits y del PR corresponde a una operación posterior; no cambia los resultados de pruebas registrados aquí.

Se utilizó seguimiento por estados en el chat porque no había herramienta de tareas disponible.
