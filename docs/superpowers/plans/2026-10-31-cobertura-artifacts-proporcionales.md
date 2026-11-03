# Plan de implementación: cobertura eficiente y artifacts proporcionales

> **Para ejecución futura:** seguir `superpowers:executing-plans` o el mecanismo de delegación que el usuario autorice. Este documento es un plan; sus casillas no afirman implementación ni pruebas ejecutadas.

**Objetivo:** disminuir la elaboración y repetición de cobertura y crear automáticamente un artifact durable compacto o completo según la evaluación, en todos los scopes, sin perder cobertura necesaria ni alterar artifacts existentes.

**Arquitectura:** final 13 normaliza cobertura por grupos y referencias compartidas. Una política selecciona compact/full por hechos del alcance y obligaciones, no por entrega ni harness. El compacto tiene contrato de manifiesto y publicación propios; el full conserva sus gates. Los lectores y proyecciones despachan por modalidad y versión.

**Tecnología:** Python 3.10+, biblioteca estándar, unittest, Git y Markdown; CLI existente `python <skill>/scripts <area> ...`.

**Spec:** [Cobertura eficiente y artifacts proporcionales](../specs/2026-10-31-cobertura-artifacts-proporcionales-design.md).

**Base verificada al redactar:** `cc9cb81fe17c28b0a624d50604ce3f8102c00542` (CCR 3.5.0), `main` y `origin/main`; worktree local `.worktrees/ccr-cobertura-eficiente`, HEAD separado. No crear commits ni publicar por este plan sin autorización independiente.

## Restricciones globales

- Conservar semántica y lectura de finales 1–12, archive 8/layout 2, trace 1, packet 1, receipt de comando 2 y proyecciones históricas; no migrar ni modificar bytes históricos.
- Usar final 13 sólo si sigue libre; si no, elegir el siguiente número y actualizar spec/plan/fixtures antes de escribir datos. Versionar por separado el manifiesto compacto y cualquier recibo de delivery que cambie.
- Mantener reglas 3.5.0 de topología/independencia, veredictos, privacy `project-resources-v1`, modelo observado/configurado y atribución sin inventar datos.
- Compacto no es archive 8 completo; no saltar gates de archive 8, ni usar un registro legado para evitar una validación fallida. Datos faltantes son desconocidos, no cero ni éxito.
- Identidad/snapshot, scopes, checks, requerimientos, gates, aislamiento y fuentes se preservan independientemente de compact/full y de `brief`/`full`.
- Probar desde la raíz con `python -B -m unittest discover -s tests -p <patrón> -v`. Usar `python -B -m unittest discover -s tests -v` para el cierre; consultar `python <skill>/scripts <area> --help` antes de nuevas rutas CLI. Usar un intérprete Python funcional y TEMP escribible; comunicar omisiones o bloqueos sin afirmar éxito.

## Riesgos que las pruebas deben cubrir

1. Un aspecto omitido se interpreta como cubierto o no aplicable, o desaparece una brecha material. Tareas 1 y 5.
2. La modalidad compacta rebaja el perfil, omite una verificación independiente o aparenta una ejecución. Tareas 2 y 4.
3. Un crash, corrupción o colisión deja un resultado parcial visible como completo o elimina recursos ajenos. Tarea 3.
4. La selección latest/reuse equipara una revisión compacta con evidencia completa o elige un registro equivocado. Tareas 3 y 6.
5. Una entrega compacta expone credenciales o presenta un comando/modelo sin procedencia. Tareas 6 y 7.
6. Una transición compact→full inventa hitos anteriores o elude el gate de archive 8. Tarea 4.

## Tarea 0 — Confirmar base y preparar fixtures

**Archivos:** `SKILL.md`, `references/contracts/result-contract.md`, `tests/fixtures/review_inputs.json`; sin editar en este paso.

- [ ] Confirmar `git status --short`, `git rev-parse HEAD`, estado de `main` y versión de contrato; si la base se movió, adaptar el plan a la revisión real antes de implementar.
- [ ] Ejecutar las suites existentes de dimensiones, contrato, archive 8, entrega y perfil; guardar sólo resultados autorizados y reportar cualquier limitación de entorno.
- [ ] Preparar fixtures sintéticas para todos los modos de scope enumerados en el spec, incluyendo snapshot local, sin copiar artifacts privados reales.

## Tarea 1 — Contrato final 13 y cobertura sin duplicación

**Modificar:** `scripts/ccr/contracts/dimensions.py`, `review.py`, `semantic_references.py`, `identifiers.py`, `execution.py`, `provenance.py`, `references/contracts/result-contract.md`, `references/workflow/review-areas.md`. **Pruebas:** `tests/test_review_dimensions.py`, `tests/test_review_contract.py`, `tests/test_review_traceability_reference_semantics.py`; añadir `tests/test_review_coverage13.py`.

**Interfaces:** `validate_coverage13(areas: object, finding_ids: set[str], evidence_ids: set[str]) -> list[str]`; `summarize_area13(area: dict) -> dict` devuelve estado, materialidad e IDs derivados. Final 13 hereda los campos y gates de 12 y emite áreas `{area, applicability, applicability_reason, groups}`, grupos `{ids, status, reason, evidence_ids, finding_ids, material}` y evidencia compartida `{id, kind, detail, check_id, reference}` conforme a spec §3. Las funciones históricas no cambian de semántica.

- [ ] Escribir tests de grupos con evidencia compartida, duplicados, ID de otra área, razón de no aplicación, pendiente material, evidencia inexistente y área `undetermined`; omitir cualquier ID impide la retención y nunca lo cubre ni lo descarta. Probar A01 `covered` con A02–A05 omitidos y con A02–A05 `not_evaluated`: el primero falla, el segundo no permite área `covered`.
- [ ] Verificar fallo de esos tests en la base y añadir final 13 con las reglas §3 del spec, sin cambiar la interpretación de 1–12.
- [ ] Probar que `covered` requiere determinación explícita y los 27 IDs clasificados en grupos, con todos los aspectos aplicables cubiertos; no se exige una redacción por ID. El validador no pretende demostrar verdad semántica.
- [ ] Extender las listas/gates de `execution.py` y `provenance.py` para que final 13 herede las garantías de 12. Probar standard con candidato sin verifier, focused sin pase escéptico, verifier anterior al último discovery y check local sin executor válido: todos deben rechazarse o quedar degradados según las reglas 12, nunca pasar por ausencia de versión.
- [ ] Adaptar los gates heredados de 12 que consumen `status`, `material` o `finding_ids` del área para que en final 13 usen el agregado calculado de `summarize_area13`; conservar el acceso original para schemas 1–12. Probar que una brecha material del grupo afecta al veredicto tanto en compacto como en completo.
- [ ] Ejecutar `python -B -m unittest discover -s tests -p 'test_review_coverage13.py' -v`, `test_review_dimensions.py` y `test_review_contract.py`; registrar resultados.

## Tarea 2 — Selección automática basada en hechos

**Crear:** `scripts/ccr/workflow/persistence.py`, `tests/test_review_persistence_policy.py`. **Modificar:** `SKILL.md`, `references/workflow/profiles.md`, `references/workflow/capabilities.md`, `references/execution/reviewers.md` y `references/execution/worker-packets.md`.

**Interfaz:** `select_persistence(facts: dict) -> dict` devuelve exactamente `{mode, reason}`, donde `mode` es `compact` o `full`; la evaluación de hechos desconocidos nunca satisface un requisito de compacto. Los hechos son datos observados, no deducciones del tamaño o del nombre de scope. Se decide antes de preparar o despachar.

- [ ] Escribir tests para cada scope, requisitos conocidos/desconocidos, una asignación, verificación independiente requerida, reglas externas y los mismos hechos con `brief`/`full`: la entrega no cambia la selección.
- [ ] Implementar los criterios de la sección 2 del spec y preservar selección de perfil, gates y permisos. Un resultado estructural de selección no prueba por sí mismo que los hechos sean verdaderos.
- [ ] Ejecutar `python -B -m unittest discover -s tests -p 'test_review_persistence_policy.py' -v` y las suites de perfiles/topología.

## Tarea 3 — Formato compacto, escritura y lectura segura

**Crear:** `scripts/ccr/archive/compact.py`, `tests/test_review_compact_archive.py`. **Modificar:** `scripts/ccr/archive/layout.py`, `lookup.py`, `reader.py`, `inspection.py`, CLI `scripts/ccr/cli/artifacts.py`, `references/archive/artifacts.md` y `references/archive/recovery.md` donde corresponda.

**Interfaces:** `prepare_compact(root, repository_identity, scope, logical_scope_input, review_inputs, selection, operation_id) -> dict` fija identidades iniciales y devuelve reserva/run, selector y hashes antes de discovery; `create_compact(prepared, record, report) -> dict` comprueba esa reserva y publica los archivos y el marcador definidos en spec §4, y devuelve `review_id`, ruta, hashes y modalidad sólo tras validar publicación; `read_compact(run_dir) -> dict` comprueba el hash externo del manifiesto, integridad, identidad cruzada, schema y referencias antes de devolver el resultado. Los parámetros de selector y snapshot son datos iniciales, no valores reconstruidos al finalizar. No borrar ni sustituir recursos ajenos.

- [ ] Escribir tests de dos módulos/features con el mismo `reference` y diferentes boundaries; range por refs frente a SHA; snapshot con staged/unstaged diferentes y cambios durante captura; identidad idéntica al scope fijado y serialización estable.
- [ ] Probar reserva/colisión, symlink/reparse point, cambio JSON válido de fecha o identidad del manifiesto, corrupción, archivo faltante, fallo antes/después de publicación, respuesta perdida, publicadores concurrentes y lookup durante staging; jamás devolver un parcial como completo.
- [ ] Implementar staging propio, hashes, validación previa y publicación atómica soportada en el mismo volumen; si no puede garantizarse, fallar de forma explícita y preservar evidencia. No modificar en sitio un archive histórico.
- [ ] Integrar lookup/inspect con discriminación de modalidad, límites y empates sin debilitar readers de archive 8. `latest` sólo presenta un candidato completo y aplicable.
- [ ] Ejecutar `test_review_compact_archive.py`, `test_review_latest.py`, `test_review_archive8.py`, `test_review_layout_v2.py` y pruebas de seguridad/rutas existentes.

## Tarea 4 — Promoción y manejo de recursos

**Modificar:** `scripts/ccr/workflow/persistence.py`, `scripts/ccr/archive/compact.py`, `archive/retention.py`, `archive/lifecycle.py` y componentes de `resources.py`, `restart.py` estrictamente necesarios; `references/archive/artifacts.md`, `references/execution/workspaces.md`, `SKILL.md`. **Crear:** `tests/test_review_compact_promotion.py`, `tests/test_review_archive_full13.py`.

**Interfaz:** `promotion_decision(selection: dict, observed_facts: dict) -> dict` indica si continúa compacto o debe iniciar full y la razón; el coordinador conserva los hechos y entradas ancladas. La promoción no fabrica una traza archive 8 ni cambia identidad histórica de un resultado ya publicado.

- [ ] Probar que un nuevo riesgo, necesidad de independencia o gate de procedencia provoca full antes del trabajo dependiente. Una promoción tras actividad conserva lo observado y falla el cierre completo si no puede acreditar sus gates.
- [ ] Implementar la decisión de spec §2: siempre crear un nuevo run full enlazado al intento compacto, antes o después de publicación. Anclar la operación a la reserva original y los inputs originales; conservar resultados verificables y repetir sólo obligaciones que no puedan acreditarse bajo los gates full, aunque sus inputs sean aplicables. Si cambian los inputs, abrir scope/run nuevo sin mezclarlos.
- [ ] Admitir final 13 en los gates de `retention.py` y `lifecycle.py` preservando los de final 12. Probar el ciclo real `prepare → register → retain(final13) → close → validate(require_complete)` y rechazar ausencia de fuente, independencia o procedencia exigidas.
- [ ] Verificar retry idempotente con respuesta perdida, promoción concurrente, interrupción en cada fase, propiedad de recursos, aislamiento de tests y ausencia de borrado ajeno.
- [ ] Ejecutar `test_review_compact_promotion.py`, `test_review_archive_full13.py`, suites de `test_review_recovery*.py`, `test_review_resource_claims.py` y `test_review_profile_topology.py`.

## Tarea 5 — Proyección de cobertura y reporte

**Modificar:** `scripts/ccr/reporting/render.py`, `projections.py`, `references/reporting/report-format.md`, `references/reporting/publication.md`. **Pruebas:** `tests/test_review_traceability_rendering.py`, `tests/test_review_traceability_comments.py`, nuevo `tests/test_review_coverage13_rendering.py`.

- [ ] Probar una sola vista ABCDE compacta, evidencia compartida no repetida, parcial con dimensión y motivo, hallazgos enlazados y materialidad visible en la incertidumbre pertinente.
- [ ] Renderizar final 13 desde el mismo registro para compacto y completo; mantener la proyección histórica por versión y la política pública existente de privacidad.
- [ ] Ejecutar las tres suites indicadas y `test_review_presentation.py`; verificar que ningún texto histórico cambió por usar un schema nuevo.

## Tarea 6 — Deliveries, continuidad y divulgación segura

**Modificar:** `scripts/ccr/reporting/delivery.py`, `check_disclosure.py`, `models.py`, `scripts/ccr/archive/reuse.py`, `scripts/ccr/workflow/reuse.py`, `references/reporting/delivery.md`, `references/workflow/reuse.md`, `references/workflow/re-review.md`. **Pruebas:** `tests/test_review_delivery.py`, `test_review_delivery_sensitive_urls.py`, `test_review_reuse_flow.py`; nuevo `tests/test_review_compact_delivery.py`.

- [ ] Escribir tests para compact/full × brief/full, identidad/hash de fuente, historial y límites de capacidad. Un full delivery de compacto no inventa trazas; equivalencia desconocida exige revisión nueva.
- [ ] Despachar por formato validado, conservar `project-resources-v1`, identidad de input inicialmente fijada y fuentes de divulgación; si no hay prueba válida, emitir explicación segura, no un comando inventado. Probar snapshot local con prueba inicial ausente o discordante y evidencia compartida con rutas/credenciales en ambas entregas y salida pública. Modelos privados sólo con observaciones reales y ausencia explícita cuando aplique.
- [ ] Si el receipt cambia, crear nueva versión y mantener la lectura y semántica de los receipts anteriores. No convertir una entrega en fuente de retención o recuperación.
- [ ] Ejecutar los tests señalados, `test_review_check_disclosure.py`, `test_review_disclosure_credentials.py` y suites de reuse.

## Tarea 7 — Contratos, documentación e integración con consumidores

**Modificar:** `SKILL.md`, referencias pertinentes, `README.md`, `docs/usage.md`, `CHANGELOG.md` en `unreleased`, fixtures CLI y tests de políticas. **Consumidor externo:** `comprehensive-code-review-viewer` se inspecciona y se actualiza sólo dentro de la autorización y workspace disponibles; no se infiere compatibilidad hacia delante.

- [ ] Eliminar instrucciones contradictorias que obliguen a 27 textos o archive 8 en compacto; conservar profundidad, alcance y precedencia de usuario. Documentar formatos, capacidades, decisiones y errores con ejemplos de distintos scopes.
- [ ] Verificar ayuda/contratos CLI, enlaces y lectura sin cambios de fixtures históricos de schemas 1–12; mantener los casos de privacidad y topología de 3.5.0.
- [ ] Ejercitar el viewer con fixtures sintéticos nuevo/anteriores: o los procesa de manera correcta o muestra incompatibilidad explícita. Documentar el resultado real y la necesidad de adaptación sin declarar soporte no probado.

## Tarea 8 — Validación final y medición

- [ ] Ejecutar `python -B -m unittest discover -s tests -v` y `git diff --check`; registrar salida, fallos y omisiones reales. No afirmar cobertura completa si hay fallos, skips relevantes o suite incompleta.
- [ ] Comparar casos con inputs, revisión y perfil fijados: control limpio, defecto conocido, brecha material, scope pequeño y cambio con consumidores/riesgo independiente. Contrastar causas detectadas, falsos positivos, evidencia y veredicto.
- [ ] Medir bytes del registro/informe y, si el harness expone cifras atribuibles, tiempo y tokens/costos para ambas variantes; desconocido permanece desconocido. No prometer ahorro de modelo derivado sólo de bytes.
- [ ] Revisar diff y plan de compatibilidad; documentar riesgos restantes, validación real y ausencia o resultado de la integración del viewer. No crear commit, publicación ni release sin instrucción separada.
