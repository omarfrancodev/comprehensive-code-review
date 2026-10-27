# Actualización del worktree y replanteamiento de trazabilidad

## Alcance y base observada

Se actualizó el worktree `explicit-dimensions-spec`, rama `docs/explicit-dimensions-spec`, a petición del usuario. Main local y origin/main coincidían en `559fc5c0f8eb2e9677ff738ed86c703017b4bf17`; metadata y changelog indicaban CCR 3.2.0. No se declara una comprobación adicional de releases remotas.

Antes de la integración la rama tenía dos commits propios (`42a052b`, `6fc1821`) y main 82 commits nuevos. `git merge --no-edit main` generó `bc7d5b6`, sin conflictos. Se conserva historia documental; no se hizo reset, rebase ni merge de esta rama a main.

Se actualizaron en sitio el [spec](../superpowers/specs/2026-10-20-explicit-dimension-coverage-design.md) y [plan](../superpowers/plans/2026-10-20-explicit-dimension-coverage.md), conservando sus enlaces. El [análisis actual](../analysis/2026-10-26-check-evidence-coverage-analysis.md) documenta modelo/captura/merge/render/publicación. Los documentos de preparación del 20 de octubre permanecen históricos.

## Decisiones incorporadas

- Rutas/imports `scripts/ccr`, doce áreas CLI, preflight, selección de fuentes, recibos y dispatch-identity de 3.2.0 reemplazan los supuestos anteriores de helpers monolíticos.
- Final 11 propuesto combina 27 dimensiones y propósito obligatorio. Captura local nueva conserva propósito en recibo 2; recibos 1 y resultados 1–10 se leen por su contrato, sin inventar declaraciones históricas.
- Se mantiene packet 1 y se actualiza explícitamente su ledger neutral, que hoy usa schema 2 y no admitiría un check completo 11.
- Bloques Markdown compartidos separan evidencia/origen, propósito/resultado y cobertura. La agrupación solo afecta presentación, no decisiones ni JSON original.
- Propósito y cobertura públicos requieren contexto editorial ligado al resultado; draft 2 verifica ese cuerpo. Draft 1 se conserva con diagnóstico explícito de regeneración, sin otro review ni edición remota.
- No se alteran reglas de admisión/reuso, límites de materiales, severidades o resultados del review. La implementación y release futura permanecen sin iniciar/asignar.

## Builder check y revisión propia

Se aplicó el builder check de brainstorming 7.0.1 mediante un revisor independiente y de solo lectura. Señaló una ambigüedad importante: exigir recibo 2 indiscriminadamente podía forzar nueva ejecución de un check histórico reutilizado. Se aclaró en §4 del spec que la exigencia corresponde a ejecución local nueva; una reutilización conserva su referencia/kind y el recibo 1 validado en origen, sin afirmar captura pasada de propósito.

El plan mantiene estructura writing-plans: ocho tareas con Files exactos, Consumes/Produces, tests con aserciones, RED/GREEN y commits. Se contrastaron firmas vigentes y se separó runner de la captura local. La prueba de fuente/cuerpo de comentarios y la política de campos portátiles tienen tareas propias. El método de implementación no fue elegido.

## Validación observada

Se usó Python empaquetado con `-B`. No se instalaron dependencias ni se cambió código de producto.

La primera ejecución focalizada desde el worktree y con TEMP/TMP largos ejecutó 87 casos: 85 aprobados y dos errores `fatal: '$GIT_DIR' too big` en fixtures que crean worktrees (captura de checks y CLI de comentarios). No se presenta esa ejecución como aprobada.

Se repitieron las mismas seis suites con CWD/TEMP/TMP propios de ruta más corta: `C:/Users/Developer.INSCORSOF2/.agents/skills/.ccr-planning-20261026`. Se importaron las rutas absolutas a tests/scripts del worktree original, sin copiar código. Resultado: **87 casos, cero fallos, cero errores, cero omisiones**, exit 0, 37.585 segundos.

Suites de ese baseline:

- `test_review_contract.py`
- `test_review_areas.py`
- `test_review_check_receipts.py`
- `test_review_comment.py`
- `test_review_preflight.py`
- `test_reference_layout.py`

La suite completa no se ejecutó en esta preparación documental. Los bloques de tests del plan describen el comportamiento futuro: su comprobación de sintaxis no acredita final 11 ni la implementación propuesta.

La comprobación documental final aprobó ocho tareas con Files/Consumes/Produces, pasos consecutivos y ciclos RED/GREEN/commit; restricciones globales idénticas al spec y rutas existentes o creadas por tareas anteriores. Los ocho bloques Python se analizaron con `ast.parse`, sin ejecutar la funcionalidad futura. Se volvió a ejecutar `test_reference_layout.py`: una prueba aprobada, exit 0, incluyendo los cuatro documentos actualizados. Se normalizó el formato de los documentos a UTF-8/LF y se comprobó `git diff --check` antes del commit. Main permanece como ancestro de la rama.

## Límites y cierre de preparación

Solo se modifican análisis/spec/plan y este registro, además del merge solicitado desde main. No se implementan módulos, no se modifican registros reales de review ni el visor, y no se publican comentarios. El seguimiento de pasos fue en línea mediante el fallback de todo-workflow-controller, sin herramienta todo disponible. La revisión del usuario de los documentos precede a cualquier ejecución del plan.
