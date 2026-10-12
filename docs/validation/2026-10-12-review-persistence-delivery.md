# Validación: persistencia, procedencia y delivery

Fecha de ejecución: 2026-10-12. Rama `fix/review-persistence-delivery`, base `eba4c54c4d40df7a877b22f79c572c4272b90eec`.

## Alcance

Implementación de la [spec](../superpowers/specs/2026-10-12-review-persistence-delivery-design.md) y el [plan](../superpowers/plans/2026-10-12-review-persistence-delivery.md) aprobados. Final schema 9; archive 6 y packet/trace 1 conservados. Versión 2.11.0 pendiente de aprobación e integración. No se migraron archivos del usuario ni se verificó el visor independiente.

## Regresiones y resultados

Pruebas con Python estándar (`-B -X utf8`) y repositorios/worktrees Git sintéticos desechables, sin modelos, servicios de CI ni reviews reales del usuario.

| Comprobación | RED observado | GREEN observado |
|---|---|---|
| Delivery tipado | 6 fallos y 1 error: colisiones de comandos con perfil/estado/IDs/revisión, identidad privada y relación histórica | 23 tests, 35.078 s; repetidos tras schema 9: 23 tests, 36.247 s |
| Procedencia schema 9 | Schema no admitido y módulo nuevo inexistente; 8 casos nuevos rechazados | 8 tests, 7.156 s |
| Compatibilidad de perfiles/fuentes schema 8 | Controles existentes | 29 tests, 11.892 s |
| Publicación | Controles existentes | 11 tests, 0.315 s |
| Gates de archivo | Flags/firmas ausentes y rechazo CLI; 5 regresiones nuevas | 43 tests, 61.018 s: 42 aprobados y 1 omitido |
| Cierre/procedencia y expectativa histórica | Close aceptaba un check local sin ejecutor vinculado; expectativa de schema ausente | 10 tests, 11.712 s |

La prueba con worktree real retiene un check ligado a HEAD, elimina ese worktree y revalida desde contexto/cierre conservados. Las pruebas de fallo verifican que no se escriba un destino de delivery ni se alteren bytes del archivo fuente. Los gates distinguen eventos sin resultado final, retención interrumpida y cierre pendiente; `--require-complete` es de solo lectura y comprueba coherencia de recursos.

Suite integrada: `python -B -X utf8 -m unittest discover -s tests -v`, 310 tests en 224.474 s; 309 aprobados y una omisión de symlinks en Windows, exit 0. La suite base antes de implementar tuvo 292 tests (291 aprobados/1 omitido); ese resultado no se atribuye a esta rama.

## Comprobaciones complementarias

- AST de 8 archivos Python modificados: válido.
- 62 enlaces relativos a archivos Markdown modificados: destinos presentes; no se verificaron sitios remotos ni todas las anclas.
- Help de contract/delivery y archive retain/validate: operativo; muestra `--expected-schema {1,...,9}` y `--require-complete`.
- `git diff --check`: sin errores.
- Main remoto continúa en la base indicada; identidad local `omarfrancodev` / `fofe2803@gmail.com`.

## Decisiones y límites

- Se usó seguimiento nativo con Python en lugar de los scripts Bash de Superpowers, que terminaban sin arrancar en este host. Se conservaron las mismas rutas del plan, ownership, ledger y logs; el coste si esta adaptación falla es seguimiento manual del progreso. No cambia los helpers del producto.
- El patrón inicial `test_review_publication.py` no seleccionó tests: se corrigió a `test_review_publication_policy.py`; el resultado informado corresponde a los 11 tests reales.
- La omisión de Windows corresponde al privilegio de crear symlinks; no se cuenta como prueba aprobada. Las pruebas disponibles de junction/reparse se conservan.
- Los hashes y bindings comprueban integridad/procedencia declarada respecto a fuentes retenidas; no prueban la verdad del review, ejecutan checks ni capturan recursos faltantes retrospectivamente.
- No se midieron tokens/créditos ni se añadió telemetría. La compatibilidad del visor con schema 9 corresponde al proyecto independiente.

## Revisión independiente

Pendiente de la única revisión final de toda la rama y, si procede, de su pase de correcciones con regresiones.
