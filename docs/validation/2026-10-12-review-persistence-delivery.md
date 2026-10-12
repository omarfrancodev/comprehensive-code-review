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
- 64 enlaces relativos a archivos Markdown modificados: destinos presentes; no se verificaron sitios remotos ni todas las anclas.
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

Una revisión fresca de toda la rama (base indicada → c4a6204), en lectura y con reproducciones puras, señaló tres defectos importantes y uno etiquetado menor. Se reclasificó la colisión de description.identity como importante porque destruye la identidad de la descripción capturada y su comparación de frescura. Los cuatro entraron en un único pase de corrección, sin segundo reviewer:

| Hallazgo | Regresión |
|---|---|
| Rutas privadas incrustadas en identidades | `test_embedded_private_identity_refuses_both_deliveries`: cuatro variantes Unix/Windows/UNC/file; origen intacto y destino ausente |
| description.identity tratada como prosa | `test_description_identity_is_preserved_or_refused_as_structure`: preservar hash seguro o rechazar ruta privada |
| Snapshot atribuido a una revisión limpia | `test_snapshot_executor_cannot_claim_clean_revision`: rechazo de baseline/HEAD con snapshot; controles positivos anteriores |
| Cierre propio bloqueado entre marker/manifest | `test_close_recovers_owned_marker_manifest_interruption`: interrupción antes/después, reintento e idempotencia; `test_close_recovery_refuses_foreign_manifest_bytes` conserva rechazo de bytes ajenos |

RED: delivery 5 fallos en 25 tests; provenance 2 fallos en 11 tests; archivo 1 error en 45 tests y 1 omisión. Los fallos corresponden a los escenarios señalados. GREEN: delivery 25 tests en 43.269 s; provenance 11 en 13.372 s; archivo 45 en 66.177 s (44 aprobados/1 omitido). Suite posterior: 315 tests en 237.047 s, 314 aprobados/1 omitido, exit 0. AST 8/enlaces relativos 64/diff check revalidados.

Decisiones sobre asuntos apartados por el reviewer:

- Visor independiente: fuera del alcance aprobado; se documenta necesidad de schema 9. Coste si falla: actualizar ese consumidor.
- Reviewer no ejecutó la suite que escribe ni symlinks: respetó lectura; se usa la evidencia de ejecución del implementador. Coste: symlinks omitidos permanecen sin verificar en este host.
- PR/publicación/release: se verificará el PR remoto tras corregir; publicación de la versión espera autorización. Coste: integración permanece pendiente.

Sin menores diferidos. No se solicitó otra review tras el pase de correcciones.

## Entrega para revisión humana

[PR #17](https://github.com/omarfrancodev/comprehensive-code-review/pull/17) creado y adjunto al chat; base main, rama fix/review-persistence-delivery. Cuerpo y head remoto comprobados. Worktree conservado para comentarios; merge, tag y release 2.11.0 esperan autorización. El scratch exclusivo del plan se elimina después de persistir este registro; otras rutas y planes permanecen intactos.

## Feedback del PR #17: F001, rutas UNC normalizadas

El [comentario CCR](https://github.com/omarfrancodev/comprehensive-code-review/pull/17#issuecomment-6130566362), sobre el head `0e1079a4190377d06058e225fb2e364afa8edd6c`, señaló que `scope.snapshot` con una ruta `//servidor/recurso/snapshot` pasaba la proyección estructural y se publicaba en full/brief. Se reprodujo: el detector cubría UNC con barras invertidas y rutas absolutas con una sola barra, pero no la representación normalizada con dos barras.

La corrección detecta `//` en los segmentos que no son URLs HTTP(S) válidas. Rechaza la identidad con un diagnóstico que identifica el campo sin revelar su valor, antes de crear el destino. No cambia schemas ni reescribe fuentes retenidas.

- RED: `python -B -X utf8 -m unittest discover -s tests -p test_review_delivery.py -k unc_snapshot -v`: un test con tres subcasos fallidos en 2.835 s; no se lanzaba el rechazo esperado.
- GREEN focalizado: `python -B -X utf8 -m unittest discover -s tests -p test_review_delivery.py -v`: 27 tests aprobados en 50.470 s, exit 0.
- Las regresiones cubren rutas UNC completas, incrustadas y con separadores mixtos en full/brief; verifican destino ausente, origen idéntico byte a byte y diagnóstico sin la identidad privada. Controles positivos preservan URLs HTTP(S) con dobles barras en su path y nombres relativos.
- Suite integrada posterior al feedback: `python -B -X utf8 -m unittest discover -s tests -v`: 317 tests en 226.251 s; 316 aprobados y una omisión por permisos de symlinks en Windows, exit 0. AST de los dos Python del ajuste y `git diff --check` correctos. Este resultado complementa las ejecuciones históricas anteriores.

## Integración y preparación de publicación

El usuario autorizó merge y publicación tras el [re-review aprobable](https://github.com/omarfrancodev/comprehensive-code-review/pull/17#issuecomment-6132344988) de `48e362a8ff91ccaf1bac0b5039329433993635b2`, que confirma F001 resuelto. Antes de integrar se repitió la suite completa sobre ese head: 317 tests en 226.475 s; 316 aprobados y una omisión por permisos de symlinks en Windows, exit 0.

El PR #17 se fusionó en `14aac4ff3c55f3b317d8d66ebe0006b2d51f1e55`. `main` local se actualizó mediante fast-forward; `git diff --exit-code 48e362a8ff91ccaf1bac0b5039329433993635b2 HEAD` confirmó árboles idénticos. El commit de preparación de release solo fecha 2.11.0, actualiza los enlaces de README/instalación y conserva este registro; no modifica runtime ni pruebas. La comprobación del ZIP y los resultados de publicación se informan en la release, sin atribuir verificación al visor independiente.
