# Plan de implementación: redacción pública y proyección editorial

> **Para agentes ejecutores:** usar `superpowers:executing-plans` o, si se selecciona ejecución delegada, `superpowers:subagent-driven-development`, tarea por tarea. Las casillas pendientes no afirman implementación ni validación. El usuario autorizó implementar el 2026-11-04; commit, push y publicación no forman parte de esta ejecución.

**Objetivo:** corregir falsos positivos de saneamiento y presentar hallazgos mediante un contexto editorial verificable, preservando íntegros los artifacts originales.

**Arquitectura:** sanear texto original según su sintaxis antes de escapar Markdown. Una vista editorial dispersa, ligada al digest del registro original, alimenta únicamente las audiencias públicas. Draft 4 fija la política nueva y sus contextos; un lector separado conserva la verificación exacta de drafts 2/3.

**Tecnología:** Python 3.10+, biblioteca estándar, unittest, Git y CLI `python <skill>/scripts <area> ...`.

**Spec:** [Redacción pública fiel y proyección editorial de hallazgos](../specs/2026-11-04-redaccion-proyeccion-editorial-design.md).

**Base comprobada:** `main` local, `0b1d5203b77585c66740bbb5eddebd1a941d4c9b`, CCR 3.6.0. Worktree `.worktrees/redaccion-proyeccion-editorial`, rama `fix/redaccion-proyeccion-editorial`. No se hizo fetch. Si la base cambia antes de implementar, contrastar y ajustar ambos documentos sin asumir que los schemas siguen libres.

**Seguimiento de ejecución:** las seis tareas están implementadas. Las pruebas, correcciones de revisión y límites observados se conservan en el [informe de validación](../../validation/2026-11-04-redaccion-proyeccion-editorial.md). La ejecución amplia terminó con 1237 pruebas, tres expectativas antiguas corregidas y revalidadas en sus módulos completos (23 pruebas aprobadas), y tres omisiones por permisos de symlinks. No quedan fallos pendientes en la validación combinada. Las casillas reflejan las tareas ejecutadas; las unidades de commit siguen pendientes; no sustituyen los resultados reales ni afirman que se hayan creado commits.

## Restricciones globales

- Python 3.10+ y biblioteca estándar; sin dependencias nuevas.
- Los artifacts originales, completos o compactos, y sus hashes permanecen idénticos byte a byte.
- El registro fuente validado sigue siendo la autoridad para identidades, estados, evidencia y juicio técnico.
- No se ejecutan comandos ni se consultan servicios para mejorar la redacción o inferir secretos/procedencia.
- Los valores sensibles conocidos se ocultan también si aparecen en texto editorial, con sus formas codificadas y solapamientos ya soportados.
- El contexto editorial no acredita comandos, recursos, ejecuciones, cuentas ni resultados.
- Los borradores históricos no se reescriben; su verificación conserva la política de representación que les corresponde.
- La fidelidad semántica y la autorización de publicación requieren la pasada editorial existente; un hash correcto no las demuestra.
- Finales 1–13, archive 8/layout 2, manifiesto compacto, trace, checks y sidecars existentes no cambian de versión ni se migran. Draft 4 es un contrato independiente.
- No editar artifacts de proyectos reales ni incorporar sus datos a fixtures. Commits del plan son propuestas futuras sujetas a autorización, no acciones realizadas.

## Riesgos de revisión y pruebas asignadas

1. Un escape de Markdown inventa una ruta en un identificador o una forma Unicode. Tarea 2: `test_markdown_escape_does_not_create_local_path`.
2. Corregir prosa permite filtrar una credencial desconocida pero estructurada, o una conocida que cruza delimitadores. Tarea 2: `test_structured_credentials_and_overlapping_known_values_remain_private`.
3. Una edición incompleta omite un hallazgo/evidencia o hace divergir corrección y condiciones. Tareas 3/4: `test_sparse_edits_inherit_all_unedited_source_fields` y `test_conditions_and_public_handoff_share_edited_correction`.
4. Cambiar el saneamiento invalida un draft histórico o permite verificarlo sólo por su hash. Tareas 1/5: `test_legacy_drafts_rerender_under_their_policy` y `test_legacy_body_tampering_still_fails`.
5. Una operación después del cierre escribe en el archivo original o liga un contexto a otro resultado. Tarea 6: `test_closed_full_and_compact_archives_unchanged_on_success_and_failure`.

## Comandos de validación

Ejecutar desde la raíz del worktree con un intérprete Python funcional. Usar `-B` y `-X utf8`; consultar el `--help` de la CLI antes de sus rutas nuevas. Para una suite concreta: `python -B -X utf8 -m unittest discover -s tests -p test_review_comment.py -v`. Para casos específicos añadir `tests` al import path mediante el runner de unittest o ejecutar discovery del módulo completo; no inventar paquetes `tests` si no existen.

Los tests que crean repositorios/sesiones requieren TEMP/TMP escribibles y suficientemente cortos en Windows. No instalar dependencias ni ejecutar servicios del proyecto del incidente. Un fallo de entorno se informa con sus efectos; nunca se convierte en éxito ni se cambia un test para evitar una aserción legítima.

## Tarea 1 — Fijar compatibilidad antes de cambiar la representación

**Archivos a crear:** `tests/fixtures/publication_legacy/draft2.json`, `draft3.json`, sus registros/contextos/pruebas sintéticos seleccionados, `tests/test_review_publication_legacy.py`, `scripts/ccr/reporting/publication_legacy.py`.

**Archivos a modificar:** `scripts/ccr/reporting/projections.py`, `render.py`, `comment.py`, `check_disclosure.py`, `tests/test_review_comment.py`.

**Interfaces:** `legacy_public_projection(text, record, check_disclosure_context=None, check_disclosure_sources=None) -> str`. El dispatcher interno selecciona la política por la versión del draft verificado; no añade una opción para preparar con política antigua. `verify_public_comment` conserva su firma pública y su rerender obligatorio.

- [x] Capturar fixtures **sintéticos** con el helper de la base, antes de modificar código. Incluir draft 2, draft 3 con explicación/disclosure seleccionado y ambos falsos positivos, más cuerpos legítimos; conservar los bytes fuente del sidecar para probar su digest real. La explicación del sidecar también incluye prosa con el falso positivo, para detectar cambios transitivos en el view y no sólo en el cuerpo final.
- [x] Añadir `test_legacy_drafts_rerender_under_their_policy`: los fixtures verifican, mantienen sus hashes y una modificación del cuerpo con hash recalculado sigue fallando por rerender. Añadir el caso draft 1 → `stale_draft`.
- [x] Extraer la proyección legacy mínima de la base sin alterar sus resultados; fijar dependencias necesarias para que las nuevas reglas de prosa no entren por un helper compartido, incluyendo la recolección de valores y el saneamiento de comandos/recursos/explicaciones del view de disclosure. Tanto la comparación del view como el rerender del cuerpo usan ese dispatch. No duplicar todo el renderer ni debilitar la validación del registro/disclosure.
- [x] Ejecutar `test_review_publication_legacy.py`, `test_review_comment.py` y `test_review_disclosure_integration.py`; exigir cero fallos y detallar cualquier omisión. Esta tarea puede pasar desde su primera ejecución: es un refactor con caracterización, no una corrección ya declarada.
- [ ] Preparar como unidad de commit futura: `refactor(publication): aislar la verificación histórica de borradores`.

## Tarea 2 — Corregir privacidad sobre texto original

**Crear:** `scripts/ccr/contracts/disclosure_text.py`, `scripts/ccr/reporting/text_projection.py`, `scripts/ccr/reporting/public_text.py`, `tests/test_review_public_text.py`. Extraer el proyector puro existente conserva el alias de delivery y evita una dependencia del renderer en IO de entregas.

**Modificar:** `scripts/ccr/contracts/check_disclosure.py`, `scripts/ccr/reporting/projections.py`, `render.py`, `check_disclosure.py`, `delivery.py`, `tests/test_review_disclosure_credentials.py`, `tests/test_review_delivery_privacy_regressions.py`.

**Interfaces:** mantener `safe_text(value, secrets=(), *, redact_paths=True, syntax='prose')`; `syntax` acepta sólo `prose|structured`. `sensitive_values_from_text(value: str, *, syntax='prose') -> set[str]` se ubica en `disclosure_text.py`; contracts no importa reporting. `public_sensitive_values(record, view=None, sources=None, *, editorial_texts=()) -> set[str]` en `reporting/projections.py` combina campos originales, fuentes existentes y una secuencia de strings editoriales ya validados. El renderer nuevo sanea campos dinámicos originales antes de `markdown_text`; su filtro final no redetecta rutas/pares genéricos a partir de escapes.

- [x] Añadir `test_markdown_escape_does_not_create_local_path` con `jobs_service.py:_publish_pending_job`, su versión con línea, rutas relativas y Unicode. La igualdad se comprueba sobre el contenido visible y los escapes Markdown esperados, no eliminando placeholders a posteriori.
- [x] Añadir `test_prose_token_colon_does_not_consume_next_word`: `safe_text('sin comprobar propiedad por token: puede borrar la reserva')` devuelve ese mismo texto; repetir en comentario canónico nuevo y delivery.
- [x] Añadir `test_structured_credentials_and_overlapping_known_values_remain_private`: campo de línea `token: demo`, JSON, asignación `token=demo`, valor entrecomillado, encabezado Authorization, URL con credenciales, comando con clave escapada y secreto conocido/codificado que cruza delimitadores. Exigir omisión del secreto y conservación de vecinos legítimos.
- [x] Añadir pruebas unitarias de recolección: `sensitive_values_from_text('token=SECRETO')` incluye `SECRETO`; `sensitive_values_from_text('por token: puede borrar')` devuelve un conjunto vacío. `public_sensitive_values` aprende el valor marcado únicamente en evidencia original, sin comandos/proofs y sin un contexto de hallazgos todavía. Recopilar los campos exactos de spec §5.1 y probar límite de trabajo; la integración con contexto editorial se prueba en tarea 4.
- [x] Ejecutar esos tests y observar fallos por los dos defectos antes de corregirlos. Ajustar clasificación según spec §5; enumerar los call sites de `safe_text` y marcar la sintaxis de comandos/recursos correctamente, sin reducir la prueba de procedencia.
- [x] Implementar saneamiento previo al escape para la ruta nueva y defensa final acotada. Cubrir comentarios sin hallazgos, campos no editados, referencias/URLs, disclosure y handoff público; no aplicar la política nueva al lector legacy de tarea 1.
- [x] Ejecutar `test_review_public_text.py`, `test_review_disclosure_credentials.py`, `test_review_check_disclosure.py`, `test_review_publication_policy.py` y todas las suites `test_review_delivery*.py`. Deben seguir pasando los controles de spans originales, autoridad HTTP/local, rutas entrecomilladas, solapamientos, URL privada y comandos completos.
- [ ] Preparar como unidad de commit futura: `fix(publication): sanear la fuente antes de escapar Markdown`.

## Tarea 3 — Contrato disperso y vista editorial pura

**Crear:** `scripts/ccr/reporting/finding_publication.py`, `tests/test_review_finding_publication.py`.

**Interfaces:** `normalize_finding_publication_context(record: dict, context: dict | None) -> dict | None`; `finding_publication_digest(context: dict | None) -> str | None`; `project_public_findings(record: dict, context: dict | None = None) -> list[dict]`. Un contexto inválido produce `ValueError` con prefijo estable `invalid_finding_context`; hash de otro registro produce `finding_context_mismatch`. Las funciones no escriben ni mutan entradas.

- [x] Añadir `test_sparse_edits_inherit_all_unedited_source_fields`: editar sólo evidencia índice 1 de F003; título, demás evidencias, otros hallazgos, IDs y metadata quedan idénticos, con copias independientes. Ordenar filas por orden fuente y evidencias por índice antes del digest.
- [x] Añadir pruebas de `schema_version=1`, digest canónico del registro completo y contexto; exigir tamaño original/normalizado ≤256 KiB y cada texto ≤16 KiB UTF-8, incluyendo Unicode y surrogate inválido. El lector JSON rechaza claves duplicadas y valores no finitos antes de normalizar; los APIs no convierten booleanos en enteros ni valores a strings.
- [x] Añadir rechazo de IDs nuevos/rechazados/duplicados, índices negativos/fuera de rango/booleanos/duplicados, filas sin edición, listas de evidencia vacías, strings vacíos, null supresor, campos extra o estructurales, versión bool/desconocida y razón de bloqueo inexistente en origen.
- [x] Comprobar los fallos antes de implementar las tres interfaces. Usar whitelist de campos según spec §6; heredar todo campo omitido, sin inferencia semántica ni búsqueda por similitud.
- [x] Ejecutar `test_review_finding_publication.py` y `test_review_contract.py`; exigir cero fallos. Verificar `deepcopy` del original y su `publication_digest` antes/después tanto en éxito como en error.
- [ ] Preparar como unidad de commit futura: `feat(publication): añadir contexto editorial ligado a los hallazgos`.

## Tarea 4 — Integrar la vista en todas sus apariciones públicas

**Modificar:** `scripts/ccr/reporting/render.py`, `projections.py`, `tests/test_review_traceability_comments.py`, `tests/test_review_publication_policy.py`, `tests/test_review_finding_publication.py`.

**Interfaces:** añadir keyword-only `finding_publication_context=None` a `render`, su `_render` y `render_handoff`. Sólo `audience='comment'` lo admite. Consumir `project_public_findings` de tarea 3 manteniendo siempre el registro original para validación, disclosure, digest, cantidades y decisiones estructurales.

- [x] Añadir `test_conditions_and_public_handoff_share_edited_correction`: la corrección editada aparece en el hallazgo, en su condición bloqueante y en el handoff público; no queda una condición original contradictoria.
- [x] Añadir pruebas de títulos/escenarios/impacto/evidencia/razón de bloqueo y títulos de incertidumbres. La edición conserva `kind`, `check_id`, índices originales, prioridad, status, blocking, localizaciones, orden y todos los hallazgos/evidencias omitidos del contexto.
- [x] Añadir `test_editorial_text_cannot_restore_sensitive_source_values`: secretos aprendidos del registro original permanecen ocultos en cualquier resumen, incluso si se editaron todas las apariciones visibles. La prueba de comandos nunca se calcula sobre un registro alterado.
- [x] Añadir `test_values_marked_only_in_original_prose_are_learned_before_projection`: una evidencia fuente contiene `token=SECRETO`, sin ese valor en comandos/proofs; el contexto la reemplaza por `La respuesta contiene SECRETO`. La copia editorial queda oculta, también al trasladarla a otro campo. Pasar los textos normalizados a `public_sensitive_values` antes de aplicar la vista; un secreto en identidad estructural falla en vez de reescribirla.
- [x] Observar fallo de integración, aplicar la vista por campo y usar las funciones de saneamiento de tarea 2. Rechazar contexto en audiencia privada; no introducir edición en `render_portable`/full/brief ni alterar el JSON fuente.
- [x] Ejecutar `test_review_finding_publication.py`, `test_review_traceability_comments.py`, `test_review_publication_policy.py`, `test_review_traceability_delivery.py` y `test_review_coverage13_rendering.py`.
- [ ] Preparar como unidad de commit futura: `feat(reporting): proyectar hallazgos editoriales sin cambiar el resultado`.

## Tarea 5 — Draft 4, CLI y verificación versionada

**Modificar:** `scripts/ccr/reporting/comment.py`, `scripts/ccr/cli/comment.py`, `scripts/ccr/cli/contract.py`, `tests/test_review_comment.py`.

**Crear:** `tests/test_review_comment_editorial.py`.

**Interfaces:** `prepare_public_comment(..., finding_publication_context=None) -> dict` emite draft 4 con forma exacta de spec §7 y política `publication-editorial-v1`. `verify_public_comment` selecciona por versión y lee el contexto embebido. `comment prepare` y `contract render-comment` aceptan `--finding-publication-context`; los demás subcomandos de contract lo rechazan. CLI verify no necesita un segundo archivo de contexto editorial.

- [x] Añadir tests con y sin contexto: siempre draft 4, campos null coherentes, digest normalizado y cuerpo determinista. El disclosure conserva su hash de bytes reales, no uno reconstruido con otro whitespace.
- [x] Añadir alteraciones de fuente, contexto, digest, política, disclosure, cuerpo y campos extra. Exigir fallo de rerender aunque se recalcule `body_sha256` sobre un texto manualmente retocado. Probar CRLF remoto permitido y local rechazado, política desconocida y límite de 2 MiB aplicado también al preparar.
- [x] Comprobar que verify exige el contexto embebido ya normalizado, con filas e índices en orden fuente, y que el lector del contexto editorial rechaza claves duplicadas/tamaño excesivo sin crear salida.
- [x] Añadir CLI tests con sesión propia: nuevo output sin sobrescribir el anterior; contexto demasiado grande rechazado antes de salida; flag inválido en render-user/handoff/validate; prepare nunca publica. Probar handoff público por API con la interfaz de tarea 4, sin inventar una CLI pública de handoff.
- [x] Observar fallos, implementar dispatch de versiones y lectura acotada del nuevo archivo. Conservar códigos de error CLI existentes para lectura/escritura (2) y error de contenido (1) de comment.
- [x] Ejecutar `test_review_comment_editorial.py`, `test_review_comment.py`, `test_review_publication_legacy.py`, `test_review_disclosure_integration.py` y `test_script_cli.py`. Ajustar aserciones de prepare a draft 4 y conservar verificaciones históricas explícitas, sin borrar expectativas incompatibles para ocultar una regresión.
- [ ] Preparar como unidad de commit futura: `feat(comment): vincular la proyección editorial en borradores versionados`.

## Tarea 6 — Cierre inmutable, documentación y validación integrada

**Crear:** `tests/test_review_editorial_immutability.py`, `docs/examples/finding-publication-context.md`.

**Modificar:** `references/reporting/publication.md`, `delivery.md`, `report-format.md`, `SKILL.md`, `CHANGELOG.md` en `unreleased` con el formato de CONTRIBUTING. No asignar release ni fecha de publicación desde este plan.

- [x] Crear fixtures sintéticos de archivo full y compacto cerrado mediante las utilidades existentes. Inventariar y hashear todos sus archivos, el draft anterior y las pruebas de disclosure. Preparar/verificar un draft 4 en sesión separada y comparar inventarios y bytes al finalizar.
- [x] Añadir `test_closed_full_and_compact_archives_unchanged_on_success_and_failure`: contexto de otro registro, escritura en archivo existente, límites, fallo de disclosure y cuerpo modificado no alteran el origen ni dejan un draft parcial listo. Los mocks/espías de ejecuciones y publicaciones deben confirmar cero llamadas; no repetir una revisión para crear el comentario.
- [x] Documentar el recorrido de spec §8: la sesión separada contiene los contextos y el nuevo draft; cambios editoriales no modifican el run ni su trace. Mostrar ejemplo sintético con digest real calculado desde su fixture, además de pseudoejemplos claramente marcados.
- [x] Documentar el saneamiento estructurado/prosa, lectores draft 2/3 vs emisor 4, límites del juicio semántico, revisión de todos los campos públicos y manejo de datos faltantes. Mantener separados responsable, autor y mención, sin añadir una política nueva de cuentas.
- [x] Ejecutar las suites focales de tareas 1–5, `test_review_editorial_immutability.py`, `test_review_archive_full13.py`, `test_review_compact_archive.py`, `test_review_disclosure_close_recovery.py`, `test_script_reporting_boundaries.py`, `test_script_pure_validation.py` y `test_reference_layout.py` (este último comprueba también los enlaces locales de SKILL y docs). Confirmar nombres reales de estos módulos en el checkout antes de invocarlos y corregir referencias del plan si cambiaron.
- [x] Ejecutar el cierre amplio con `python -B -X utf8 -m unittest discover -s tests -v` cuando el entorno tenga los requisitos; registrar conteo real, fallos, skips y alcance. Ejecutar `git diff --check`; comprobar que el diff de implementación no incluye artifacts externos ni cambios históricos de contenido.
- [x] Comparar nuevamente fixtures legacy y hashes full/compact después del cierre. No declarar compatibilidad de consumidores externos; preparar una nota de adopción de draft 4 y requisitos de actualización de lectores.
- [x] Solicitar revisión de la implementación contra A01–A10 y resolver hallazgos antes de proponer publicación. Revisión independiente completada; cuatro defectos corregidos con pruebas RED → GREEN.
- [ ] Preparar como unidad de commit futura: `docs(publication): documentar la edición posterior al cierre y su compatibilidad`.

## Trazabilidad de aceptación

| Spec | Tareas | Evidencia principal |
|---|---|---|
| A01–A02 | 2, 4 | Casos exactos de prosa, identificadores y corpus de privacidad/spans existente. |
| A03, A04, A05 | 3, 4 | Contrato disperso, rechazo estructural, conservación de evidencias y condiciones. |
| A06–A07 | 1, 5 | Draft 4 íntegro, fixtures 2/3 congelados y detección de manipulación. |
| A08–A09 | 5, 6 | Inventario de archivos full/compact y cero ejecuciones/publicaciones. |
| A10 | 6 | Documentación, enlaces y fixtures sintéticos sin datos del incidente. |

## Revisión del plan antes de implementación

- [x] Verificar que cada campo, nombre y límite coincide con el spec y que cada A01–A10 tiene pruebas asignadas.
- [x] Confirmar que no se usa el registro proyectado como autoridad de hashes/disclosure y que las condiciones usan la corrección editorial.
- [x] Confirmar la rama/base y rutas reales, y revisar que sólo haya cambios propios de esta tarea antes de implementar.
- [x] Autorización recibida del usuario: «Procede a la implementación», 2026-11-04. Ejecución inline con revisión independiente final; sin integración ni publicación.


## Correcciones de la revisión independiente

La revisión final identificó cuatro defectos y la única pasada de corrección los reproduce en `tests/test_review_editorial_regressions.py`: credencial JSON escapada copiada sin marca, secreto declarado en el contexto del handoff y copiado entre campos, ruta privada en enlaces derivados de `source_report`, y validación transitiva legacy de disclosure. Se observaron fallos antes de corregir y los cuatro casos pasaron después. El cierre completo posterior a esas correcciones se ejecutó y sus resultados se registran en el informe de validación.

Los lectores durables de sidecar 1 reconocen ambas reconstrucciones exactas (histórica/actual) bajo el mismo gate de recursos; drafts 2/3 exigen la histórica. La recolección protege asimismo las formas JSON decodificadas y el contexto propio del handoff. La documentación de módulos registra las extracciones puras y las pruebas correspondientes.
