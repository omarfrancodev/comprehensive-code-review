# Corrección F001 del review del PR 23

Fecha: 2026-10-17, America/Mexico_City. Base revisada: `e3678dc8b631dd48b625808f2730b25b69f97d74`.

## Origen y comportamiento

El [review CR-9125374c35a7450db206](https://github.com/omarfrancodev/comprehensive-code-review/pull/23#issuecomment-6243700523) reportó F001 (P2): tras guardar el transfer `complete` en el origen y cortar antes de persistirlo en el sucesor, la desaparición de una sesión seleccionada producía `transfer_durable` en inspect/lookup/recover y en el recibo, pero `transfer_committed` en abandon-restart. Todas las rutas seguían rechazando la cancelación; el defecto era la inconsistencia del contrato de fase.

Se añadió una observación común que verifica ambos manifiestos disponibles y la identidad del sucesor reservado. Diagnóstico, abandono y registro de negativa utilizan esa observación y el clasificador existente: una entrada pendiente del transfer exacto tiene prioridad; solo entradas completas permiten `transfer_committed`. El abandono adquiere el lock del sucesor antes de leerlo para decidir, y lo conserva hasta rechazar o terminar la decisión aceptada. Si falta el sucesor, se conserva la prueba durable del origen y se sigue rechazando la cancelación.

No se cambian schemas, ownership, cleanup ni las reglas de rollback. Los rechazos siguen sin modificar archivos de dominio; el registro autorizado de una negativa sigue escribiendo exclusivamente la traza y metadatos de integridad del origen.

## RED/GREEN

La regresión principal interrumpe el helper real justo después de persistir `complete` en el origen; confirma que el sucesor aún registra `pending` y hace desaparecer únicamente la sesión desechable del fixture. Reproduce la divergencia entre nueve observaciones: inspect, lookup y recover desde origen/sucesor; API y CLI de abandono; y recibo durable. El subcaso con ambos commits completos también se verifica.

Antes de corregir, el subcaso de commit parcial falló exactamente por las dos rutas de abandono. Se reprodujo además que el abandono decidía su fase sin respetar un lock ya ocupado del sucesor. La primera versión de ese test intentaba leer el propio archivo de lock de Windows; se corrigió el fixture para comparar solo los archivos de dominio y entonces reprodujo el fallo esperado por tipo de excepción.

Después del cambio pasaron **cuatro pruebas nuevas en 45.186 s**, sin errores ni omisiones: igualdad entre rutas, contención real del lock del sucesor, identidad corrupta y sucesor ausente. La regresión principal comprueba además que no se crean recibos de cleanup/cancelación, que el restart permanece pendiente, que se preserva el sucesor y que el replay del recibo es idempotente.

Comando reproducible, con `scripts` y `tests` en `PYTHONPATH`: `python -B -X utf8 -m unittest -v test_review_restart_phase_consistency`.

## Regresiones y suite

Pasaron **46 pruebas focalizadas en 647.122 s**, sin errores ni omisiones, de `test_review_restart_refusals`, `test_review_recovery_route_consistency`, `test_review_recovery_exit_guidance`, `test_review_recovery_reservations` y `test_review_recovery_diagnostics`.

Comando reproducible, desde la raíz y con `scripts` y `tests` en `PYTHONPATH`:

```text
python -B -X utf8 -m unittest -v test_review_restart_refusals test_review_recovery_route_consistency test_review_recovery_exit_guidance test_review_recovery_reservations test_review_recovery_diagnostics
```

La suite completa del nuevo estado descubrió **585 IDs únicos**, ejecutados una sola vez en cuatro grupos disjuntos: los casos generales repartidos por índice par/impar y las dos matrices extensas aisladas. Se verificó la igualdad exacta entre el inventario descubierto, la unión de los grupos y los IDs observados al terminar.

| Grupo | Pruebas | Aprobadas | Omitidas | Duración (s) |
| --- | ---: | ---: | ---: | ---: |
| General 0 | 292 | 292 | 0 | 1068.985 |
| General 1 | 291 | 288 | 3 | 1031.937 |
| Matriz de transferencia | 1 | 1 | 0 | 1064.047 |
| Matriz de adopción | 1 | 1 | 0 | 225.594 |
| Total | 585 | 582 | 3 | Ejecución concurrente |

Resultado: **582 aprobadas, tres omitidas y cero fallos/errores**. Las omisiones son las tres pruebas de symlinks que requieren un privilegio ausente del host Windows (`WinError 1314`):

- `test_review_artifacts.ArchiveTests.test_symlink_roots_inputs_and_archived_files_are_refused`.
- `test_review_lock_file_safety.LockFileSafetyTests.test_existing_final_symlink_is_refused_without_touching_target`.
- `test_review_lock_file_safety.LockFileSafetyTests.test_final_link_replacement_after_identity_check_is_refused`.

Las matrices incluyen los cortes antes/después de cada reemplazo durable y ambas rutas de replay (`retry` y `recover`); un ID de matriz contiene varios subcasos. Las cuatro regresiones nuevas de F001 también quedaron incluidas en la suite completa. La orden equivalente para ejecutar toda la suite desde la raíz es:

```text
python -B -X utf8 -m unittest discover -s tests -v
```

Los hashes SHA-256 de los **64 archivos Python** en `scripts` y `tests` coinciden entre los cuatro inventarios y con las fuentes finales. No se modificó código Python durante la ejecución. También se verificó el parseo AST de los tres archivos Python modificados y `git diff --check`. Los resultados anteriores de 581 IDs corresponden a la implementación previa; esta ejecución verifica el estado que incluye F001.

## Pase independiente

Un pase estático independiente del delta respecto de `e3678dc8b631dd48b625808f2730b25b69f97d74` no encontró defectos accionables en F001. Inspeccionó los dos módulos modificados, sus dependencias inmediatas y las cuatro regresiones nuevas. Confirmó que el abandono observa ambos manifiestos antes de escribir y que el recibo conserva autoridad, evidencia e idempotencia. No ejecutó pruebas ni extendió la revisión a atomicidad global de diagnósticos sin locks o al resto del PR; este pase no sustituye un nuevo veredicto del review externo.

## Límites

Ejecución Windows con Python del runtime disponible, biblioteca estándar y fixtures Git propios bajo una ruta temporal corta. No se modificaron reviews reales ni se infirió cleanup a partir de recursos ausentes. El estado de contención se ejercita con un thread que adquiere el lock real del sucesor; no equivale a una ejecución POSIX.

El seguimiento de esta corrección se realizó por estados en el chat al no disponer de herramienta de tareas. La publicación del commit y la actualización del PR son posteriores a la validación registrada aquí.
