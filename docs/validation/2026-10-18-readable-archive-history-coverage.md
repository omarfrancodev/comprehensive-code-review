# Validación de archivo legible, consulta histórica y cobertura ABCDE

## Alcance y entorno

Validación de la implementación en `feat/archive-layout-portability`, basada en
`715726377ad95acbb1cbad114d7a55968228ab79` (2.12.1), dentro del worktree aislado.
Referencias: [spec](../superpowers/specs/2026-10-18-readable-archive-history-coverage-design.md)
y [plan](../superpowers/plans/2026-10-18-readable-archive-history-coverage.md).

Se utilizó Python del runtime empaquetado, bajo
`%USERPROFILE%/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`,
sin instalar dependencias. `TEMP` y `TMP` apuntaron a
`%USERPROFILE%/.agents/skills/comprehensive-code-review-validation` para cada proceso.
Todas las fuentes de reviews y sesiones de prueba fueron sintéticas y desechables.

La prueba de clonación local falló dentro del sandbox de Windows con
`NtCreateDirectoryObject ... 0xC0000022` en Git/MSYS; la misma prueba pasó al
ejecutarla fuera del sandbox. La corrida final utiliza ese segundo entorno con
los mismos temporales propios. No se omitió la prueba para resolver el bloqueo.

## Correcciones verificadas

- Se eliminaron caracteres literales al final de dos helpers que impedían importarlos.
- Las entradas no observadas permanecen sin capturar hasta disponer de contexto;
  una identidad lógica suministrada que contradice el selector fijado se rechaza.
- Lookup, inspección, reanudación y replay de un reinicio reservado normalizan la
  identidad lógica de forma consistente, conservando el rechazo de entradas cambiadas.
- Latest devuelve `incomplete_search` si no puede leer el grupo, verificar un
  candidato nativo o revalidar el resultado seleccionado; no elige un resultado
  anterior tras ignorar esos errores. La prueba del límite de escaneo usa un
  candidato elegible para comprobar el límite, sin fallar antes por otro motivo.
- La portabilidad histórica rechaza transacciones pendientes de ownership,
  retención o transferencia, además de directorios de staging enlazados/reparse.
- Las lecturas históricas aplican su presupuesto de bytes sobre el stream abierto;
  `show` contrasta también los bytes leídos después de verificar el paquete.
- La adopción de sesiones valida la pertenencia al repositorio antes de crear una
  intención de reinicio, utilizando el esquema nativo vigente en su preflight.
- El helper que registra rechazos de cancelación también usa el esquema nativo
  vigente; conserva la verificación de ownership, locks y pruebas de fase durable.

Las pruebas operativas utilizan fixtures de archive 8 y final schema 10 con
selección, contexto y ejecución registrados. Los escenarios de contratos antiguos
conservan sus pruebas puras de validación/proyección; las operaciones sobre archives
antiguos comprueban rechazo `unsupported_layout` y preservación de bytes. La
construcción de fixtures actuales no se expone como migración del producto.

## Comprobaciones

Los comandos `python` siguientes representan el ejecutable efectivo descrito arriba.

| Comprobación | Resultado observado |
|---|---|
| Captura de entradas, archive 8 y checkpoint afectado | 8 pruebas, OK, exit 0 |
| Comparación común de entradas, archive 8 e inspección | 15 pruebas, OK, exit 0 |
| Trazabilidad nativa y rechazo histórico | 27 pruebas, OK, exit 0 |
| Entrega, perfiles, harness, flujo y ejemplo de inicio | 53 pruebas, OK, exit 0 |
| Portabilidad histórica y latest, incluidos los nuevos casos de regresión | 20 pruebas, OK, exit 0 |
| Historial después de reforzar lectura y consulta | 13 pruebas, OK, exit 0 |
| Módulo completo de recuperación y frescura | 56 pruebas, OK, exit 0 |
| Fases de transferencia y registro de rechazos de cancelación | 13 pruebas, OK, exit 0 |
| Recuperación reservada y rechazo de entradas cambiadas | 3 pruebas, OK, exit 0 |
| Adopción de otro repositorio y conservación de ownership parcial | 2 pruebas, OK, exit 0 |
| `review_artifacts.py lookup --help` y `review_history.py --help` | Exit 0; argumentos y comandos previstos presentes |
| `python -B -m unittest discover -s tests -v` | 621 casos: 618 aprobados, 3 omitidos, 0 fallos y 0 errores; 1620.539 s; `OK (skipped=3)`, exit 0 |
| `git diff --check` | Sin errores |

Las baterías enfocadas se solapan y no se suman como si fueran casos distintos.
Las corridas diagnósticas fallidas o interrumpidas no se presentan como suites aprobadas.
Se verificó que la corrida completa contiene exactamente una aparición de cada
ID siguiente, ambos terminados en `... ok`, sin un filtro opt-in:

- `test_review_restart_resources.RestartResourceReplayTests.test_claimed_workspace_all_transfer_replacements`
- `test_review_restart_resources.RestartResourceReplayTests.test_unclaimed_workspace_all_adoption_replacements`

El log completo se conserva localmente como `pr25-final-validation.log` en el
directorio de temporales indicado. SHA-256:
`9c5db3897b76ac71787e172dbdf716f7c81e73a9fe4a60b9bd5c1f6d3e33fa8e`.
Las correcciones de producto verificadas llegan hasta `50fb9ec`; los cambios de
cierre posteriores solo actualizan documentación.

## Límites y alcance de integración

Esta validación se ejecutó en Windows; no certifica ejecución POSIX. Los tres
skips se debieron a falta de privilegios para crear symlinks (`WinError 1314`):

- `ArchiveTests.test_symlink_roots_inputs_and_archived_files_are_refused`.
- `LockFileSafetyTests.test_existing_final_symlink_is_refused_without_touching_target`.
- `LockFileSafetyTests.test_final_link_replacement_after_identity_check_is_refused`.

La prueba de junctions sí se ejecutó y pasó fuera del sandbox.
El PR no tiene checks de CI configurados ni revisiones pendientes registradas al
realizar estas comprobaciones. El resultado de pruebas no constituye una aprobación
del juicio que emita la skill en revisiones futuras.

No se cambiaron final schema 10, trace schema 1 ni packet version 1; tampoco el
renderer del informe. La fecha visible pertenece a la ruta y metadata de la
ejecución, sin fechas nuevas añadidas al contenido del reporte. Latest permite
consultar el resultado de un MR cuyo head cambió y conserva `applicability=changed`;
esa consulta no habilita continuación ni presenta el snapshot anterior como vigente.

No se modificó el repositorio independiente del visor, no se portaron reviews
reales y no se publicó una release ni se hizo merge.
