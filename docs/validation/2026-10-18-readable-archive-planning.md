# Preparación de archivo legible, consulta histórica y cobertura ABCDE

## Alcance observado

Preparación documental del 18 de octubre de 2026, America/Mexico_City. Base `715726377ad95acbb1cbad114d7a55968228ab79` / 2.12.1; rama `feat/archive-layout-portability`; worktree `.worktrees/archive-layout-portability`.

Se redactaron [spec](../superpowers/specs/2026-10-18-readable-archive-history-coverage-design.md) y [plan](../superpowers/plans/2026-10-18-readable-archive-history-coverage.md). El usuario pidió ambos documentos en esta misma preparación. No se implementaron helpers, schemas ni tests nuevos, no se modificaron archivos reales de reviews y no se cambió el visor.

## Worktree y entorno

- Main estaba limpio y el worktree apunta a su commit 2.12.1, en una rama propia. `.worktrees/` está ignorado por Git.
- La herramienta nativa devolvió «Not a git repository» por el directorio contenedor del chat. Se creó el worktree con Git dentro del repositorio identificado.
- El alias python.exe de WindowsApps no pudo ejecutarse. Se usó el runtime Python empaquetado bajo `%USERPROFILE%/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`.
- TEMP y TMP se fijaron solo para cada proceso de pruebas a `.worktrees/archive-layout-portability-validation`, fuera del checkout principal. Los logs de la preparación se conservan allí, ignorados por Git; no forman parte de la distribución.

## Comprobaciones

Los comandos `python` de esta tabla representan el ejecutable efectivo anterior. Se ejecutaron desde el worktree aislado con `-B` y no se instalaron dependencias.

| Comprobación | Resultado |
|---|---|
| `python -B -m unittest discover -s tests -p test_review_contract.py -v` | 34 pruebas, OK, exit 0 |
| `python -B -m unittest discover -s tests -p test_review_areas.py -v` | 15 pruebas, OK, exit 0 |
| `python -B -m unittest discover -s tests -p test_reference_layout.py -v` | 1 prueba, OK, exit 0; enlaces locales de spec, plan y este registro incluidos |
| `git diff --check` y comprobación directa de whitespace de documentos nuevos | Sin errores |

Se intentó la suite completa: la primera ejecución dentro del sandbox encontró permisos denegados en su temporal, no una base validada. Se reinició con runtime y temporales propios; después se interrumpió deliberadamente al comprobar que la suite contiene matrices extensas. No terminó y no se declara aprobada. El código de producto permaneció intacto. La implementación posterior debe ejecutar la suite y verificar todos sus IDs, incluidas ambas matrices, antes de declarar completado el cambio.

Las comprobaciones focalizadas validan contratos y documentación existentes, no demuestran el comportamiento propuesto. No se evaluó runtime POSIX ni compatibilidad del visor.

## Revisión propia de spec y plan

- La decisión vigente es no migrar ni reestructurar fuentes antiguas; el port mínimo tiene inventario exacto de tres archivos y no habilita mutaciones nativas.
- Los contratos finales/packet/trace permanecen; el layout nuevo requiere archive 8 y descriptor lógico enlazado a ownership. La separación entre selector estable y scope exacto está definida.
- Latest solo responde a una selección explícita, respeta alcance/selector y no oculta búsqueda incompleta ni vigencia desconocida.
- Prepare, reserva de restart, lookup, gates y entrega comparten el contrato de ubicación; no se abandona la coordinación de 2.12.1.
- Las cinco clases de Review Focus tienen tests asignados en las tareas correspondientes. El plan identifica interfaces, archivos y ciclos RED/GREEN; no afirma haberlos ejecutado.
- La ampliación de referencias incluye actualizar el catálogo exacto de test_reference_layout al implementar. Los documentos actuales solo enlazan archivos existentes.
- El nombre de la skill, las fechas fuera del contenido del informe y el visor separado se conservan.

Pendiente: revisión del usuario de los documentos y elección del método de implementación. Preparar estos archivos no autoriza portar datos reales, modificar el visor, publicar ni ejecutar la implementación.
