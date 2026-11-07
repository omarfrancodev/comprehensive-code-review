# Validación: redacción pública y proyección editorial

**Estado:** implementación y validación completadas, con tres pruebas de symlinks omitidas por permisos del host. **Base:** `0b1d5203b77585c66740bbb5eddebd1a941d4c9b`, CCR 3.6.0. **Rama:** `fix/redaccion-proyeccion-editorial`. Cambios locales sin commit ni publicación.

## Alcance implementado

- Saneamiento sobre texto original y clasificación prosa/structured antes de Markdown; conservar identificadores y frases narrativas sin reducir la protección de valores marcados/conocidos.
- Contexto editorial disperso ligado al digest del registro original, con límites UTF-8, campos permitidos e índices de evidencia. Los artifacts originales completos y compactos no se modifican.
- Draft 4, política `publication-editorial-v1`, contexto/digest embebidos y verificación exacta del cuerpo. Lectura de drafts 2/3 bajo su política histórica y de sidecars 1 con reconstrucción de procedencia compatible.
- Proyector de spans puro compartido entre publicación y delivery; conservar el alias de delivery. Ninguna preparación ejecuta checks, publica o repite la revisión.

Spec y plan: [diseño](../superpowers/specs/2026-11-04-redaccion-proyeccion-editorial-design.md), [plan](../superpowers/plans/2026-11-04-redaccion-proyeccion-editorial.md).

## Resultados observados por fase

No se presenta la selección inicial como una ejecución limpia. Los resultados siguientes conservan fallos de desarrollo y reejecuciones, sin ocultarlos ni sumarlos como casos únicos.

| Ejecución | Tests | Fallos | Errores | Omitidos |
|---|---:|---:|---:|---:|
| `focal-1` | 174 | 6 | 0 | 0 |
| `editorial-cli-immutability` | 45 | 1 | 1 | 0 |
| `editorial-cli-immutability-recheck` | 5 | 0 | 0 | 0 |
| `integration-recheck` | 25 | 0 | 0 | 0 |
| `script-boundaries` | 47 | 1 | 0 | 0 |
| `strict-context-red` | 9 | 2 | 0 | 0 |
| `strict-context-green` | 9 | 0 | 0 | 0 |
| `final-review-red` | 4 | 7 | 0 | 0 |
| `final-review-green` | 15 | 0 | 0 | 0 |
| `emitter-remaining-rechecks` | 23 | 0 | 0 | 0 |
| `full-suite-final` | 1237 | 3 | 0 | 3 |

`focal-1` señaló expectativas antiguas de versión/escape; `editorial-cli-immutability` detectó el contexto no reenviado por la CLI y un fixture compacto sin disclosure requerido. Se corrigió el reenvío y se suministró la explicación/proof adecuada al fixture; no se debilitó el gate. `script-boundaries` señaló el inventario CLI: se verificó que sólo cambiaban dos opciones antes de actualizarlo (32 líneas añadidas).

Las primeras invocaciones con TEMP del sandbox fallaron por permisos. Las pruebas que escriben se ejecutaron después con un TEMP propio, corto y escribible y los mismos asserts. Los logs detallados permanecen en el workspace ignorado del plan. No se utilizaron ni alteraron los artifacts del proyecto del incidente; todas las fixtures son sintéticas.

## Revisión independiente y correcciones

Un revisor fresco (`gpt-6-astra`, razonamiento high) evaluó spec, plan, diff y archivos nuevos sin modificarlos. Encontró cuatro defectos de implementación:

1. Una credencial JSON escapada no enseñaba su valor decodificado antes del resumen.
2. El contexto del handoff no protegía copias entre sus propios campos.
3. Enlaces derivados de `source_report` podían conservar una ruta privada aunque la cabecera se ocultara.
4. La validación transitiva de disclosure usaba reglas nuevas durante la verificación histórica.

Se reprodujeron en `test_review_editorial_regressions.py`: cuatro tests con siete fallos reportados, incluyendo subcasos, antes de la única pasada de corrección; después pasaron los cuatro y la selección asociada de 15 pruebas, sin fallos, errores ni omisiones. No se hizo una segunda revisión por otro agente.

La fidelidad semántica de ediciones humanas sigue en la pasada editorial. La compatibilidad de consumidores externos no está certificada: un lector de comentarios debe reconocer draft 4; los contratos finales 1–13 y artifacts históricos no se migran.

## Cierre amplio

La primera ejecución amplia se interrumpió deliberadamente al confirmar los cuatro defectos, para conservar su log como incompleto y reiniciar sobre código corregido. No cuenta como una suite aprobada.

La ejecución final usa `python -B -X utf8 -m unittest discover -s tests -v`, desde la raíz del worktree, con Python y Git funcionales y TEMP escribible. Durante ella se encontraron tres expectativas restantes del emisor (schema 13, priority roundtrip y topology integration) que esperaban draft 2/3. Se actualizaron sólo a draft 4, conservando las comprobaciones de privacidad, impacto y procedencia, y se reejecutaron sus módulos completos: 23 pruebas pasaron. El código de producto permanece estable durante esa ejecución final. La validación combinada no debe confundirse con una sola invocación limpia.

La ejecución amplia terminó en **3035,280 segundos**: 1237 pruebas, 1231 aprobadas, tres fallos de expectativas antiguas del emisor y tres omisiones. Los tres fallos fueron exactamente los de `test_review_coverage13_rendering`, `test_review_priority_roundtrip` y `test_review_topology_integration`; unittest había importado sus aserciones antes de actualizarlas. Sus módulos completos, con las expectativas corregidas, pasaron en la reejecución de 23 pruebas citada arriba. No quedan fallos pendientes en la validación combinada; no se afirma una única invocación completa limpia.

Las tres omisiones corresponden a `test_symlink_roots_inputs_and_archived_files_are_refused`, `test_existing_final_symlink_is_refused_without_touching_target` y `test_final_link_replacement_after_identity_check_is_refused`. Windows devolvió `WinError 1314` al crear symlinks. No se modificaron ni desactivaron esos tests; su comportamiento no quedó comprobado en este host.

Comprobaciones adicionales: 103 módulos Python compilados en memoria sin errores; `test_reference_layout.py` aprobado (enlaces locales incluidos); inventario CLI compatible salvo las dos opciones nuevas; `git diff --check` sin errores. Los tests de inmutabilidad full/compact, rerender histórico, contratos y límites de módulos pasaron en la ejecución amplia. Se conserva la evidencia de ejecución en el workspace ignorado porque los cambios aún no están comprometidos.
