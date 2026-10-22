# Validación de la modularización de scripts

Validación final del spec [scripts-modularity-design](../superpowers/specs/2026-10-21-scripts-modularity-design.md) y el [plan](../superpowers/plans/2026-10-21-scripts-modularity.md), ejecutada en la copia de trabajo `scripts-modularity-spec-plan` sobre la versión del skill `2.14.0`.

## Comandos y resultados

| Comprobación | Resultado | Evidencia |
|---|---|---|
| Contratos de CLI, ruta y dispatcher | OK | `tests.test_script_cli`: entrada única, sufijo preservado, root help sin cargar servicios, doce áreas y copia con espacios desde cwd ajeno. Captura de un check con exit 7 conserva ese código en el recibo y devuelve éxito de captura. |
| Instalación y recursos | OK | La prueba aislada confirma `skill_root`, catálogo y `catalog_version` desde la copia instalada, la versión leída de su `SKILL.md` y el rechazo de una raíz de archivo dentro de la instalación. No usa `PYTHONPATH`. |
| Índice y registro | OK | `tests.test_script_layout`: 12 áreas, ausencia de `scripts/review_*.py` y registro de los 73 módulos de implementación en `scripts/README.md`. |
| Grafo y límites de dependencia | OK | `tests.test_script_dependencies`: detección de ciclos/self-loops, imports absolutos/relativos/locales, aristas del registro de CLI, cero ciclos y cero imports legacy; contracts no importan servicios ni IO bloqueados. |
| Integridad de bytes y replay | Cubierto por regresiones | `tests.test_script_shared`, `tests.test_script_characterization`, `tests.test_review_restart_v2` y `tests.test_review_history` comprueban bytes deterministas, identidad de replay y lectura de historia. |
| Retención, cleanup y ownership | Cubierto por regresiones | `tests.test_review_checkpoints`, `tests.test_review_resource_claims`, `tests.test_review_restart_resources`, `tests.test_review_session_operations` y `tests.test_review_atomic_recovery` ejercitan operaciones interrumpidas y su recuperación. |
| Contratos operativos 2.14.0 | Cubierto por regresiones | `tests.test_review_references`, `tests.test_review_reference_index`, `tests.test_review_setup`, `tests.test_review_check_receipts`, `tests.test_review_model_usage` y `tests.test_review_comment`. |
| Enlaces y guía de migración | OK | `tests.test_reference_layout` verifica enlaces locales; `docs/script-migration.md` recoge comandos, ruptura de imports, las doce áreas y sustitutos de las rutas retiradas. `docs/usage.md` enlaza el índice. |
| Suite completa y formato del diff | OK | `python -B -X utf8 -m unittest discover -s tests -v`: 752 pruebas en 4470.557 s, `OK (skipped=7)`. `git diff --check` pasa. |

Los 7 skips dependen del entorno Windows: no se pudieron crear enlaces simbólicos/junctions/hard links y una prueba de clonación requiere un objeto de sincronización Win32 no disponible en Git Bash. Las pruebas restantes, incluidas ambas matrices completas de replay de recursos, pasaron.

La suite del baseline previo se inició antes de modificar producto, pero se interrumpió después de más de 15 minutos dentro de la matriz de replay de transferencias. No se presenta como una corrida base completa; la corrida final sí cubrió la suite completa.

## Criterios de aceptación del spec §9

| # | Criterio | Evidencia |
|---:|---|---|
| 1 | Las doce áreas usan la entrada única; no hay fachadas `review_*.py` ni imports activos de ellas. | `test_script_cli`, `test_script_layout`, `test_script_dependencies`; prueba del mapa estático y grep AST del grafo. |
| 2 | Área ausente/inválida, ayuda raíz, ayuda por área y argumentos con espacios mantienen el contrato acordado; ayuda raíz no importa servicios. | `test_script_cli`, incluyendo copia con cwd ajeno y paths con espacios. |
| 3 | Parsers, resultados y códigos conservan la caracterización, con el prefijo `ccr AREA` documentado. | `test_script_characterization`, `test_script_cli`, fixture `tests/fixtures/scripts_cli_contracts.json`. |
| 4 | Contratos/preflight siguen puros; inspección no muta; el grafo carece de ciclos y dependencias de implementación a CLI. | `test_script_dependencies`, `test_script_contract_boundaries`, `test_script_read_only_flows`, `test_review_artifact_layout`. |
| 5 | Bytes, hashes e identidad de replay v2 conservan equivalencia; paquetes históricos no se reescriben. | `test_script_characterization`, `test_script_shared`, `test_review_restart_v2`, `test_review_history`. |
| 6 | Checkpoint/retención, transferencia, restart y cleanup conservan ownership y rutas de recuperación. | Suites de checkpoints, claims, restart/refusal/resources, cleanup, recuperación atómica incluidas en la suite completa. |
| 7 | Referencias, setup, recibos, modelo y comentario mantienen sus garantías; capturar exit distinto de cero no cuenta como falla del helper si el recibo se guardó. | Suites de referencias, setup, receipts, model usage y comment; `test_checks_cli_reports_successful_capture_of_exit_seven`. |
| 8 | Copia completa instalada resuelve catálogo/versión y raíz desde su propia ubicación y rechaza archivo bajo la instalación. | `test_installed_copy_works_from_foreign_cwd`; prueba `-c` aislada sin `PYTHONPATH`; ejecuta las doce ayudas. |
| 9 | Índice, áreas, instrucciones actuales, guía de ruptura e historia/enlaces son coherentes. | `test_script_layout`, `test_reference_layout`, `scripts/README.md`, `docs/usage.md`, `docs/script-migration.md`; changelog mantiene el cambio como no publicado. |
| 10 | Suite completa y `git diff --check` pasan antes de integrar y registran omisiones ambientales. | `unittest discover -s tests -v`: 752 pruebas, 4470.557 s, `OK (skipped=7)`; `git diff --check` pasa. Los siete skips ambientales están descritos arriba. |

La comprobación cubre una copia completa del checkout y no el ZIP o artefacto de distribución externo, porque ese generador no forma parte del repositorio disponible. Por ello el reporte no certifica una release empaquetada.
