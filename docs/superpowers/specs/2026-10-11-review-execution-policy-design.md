# Publicación y cumplimiento de perfiles de CCR

Fecha: 2026-10-11. Estado: propuesta escrita para revisión; implementación pendiente.

## Objetivo y alcance acordado

Evitar que los comentarios públicos expongan la mecánica interna de la revisión y que una ejecución se presente como `deep`/`extended` cumplida sin los contextos independientes que exige el perfil. Mantener la evidencia necesaria para evaluar el cambio y auditar el proceso. Invocar CCR solicita las delegaciones necesarias del perfil dentro de las capacidades y permisos existentes; no requiere añadir «usa subagentes» a cada petición.

El usuario aprobó la propuesta conceptual y solicitó preparar nueva rama, worktree, spec y plan mientras valida el PR #14. Esta preparación no cambia la skill instalada, los artifacts históricos ni el comentario del PR. Los documentos escritos y su método de ejecución se revisan antes de implementar.

## Base y dependencia de integración

- Rama: `feat/review-execution-policy`.
- Worktree: `.worktrees/review-execution-policy`, excluido por `.gitignore`.
- Base: `origin/main`, commit `d54be59e2d09117d59c5a8664fcb1a68d6649bb5`.
- PR [#14](https://github.com/omarfrancodev/comprehensive-code-review/pull/14) pendiente al preparar esta propuesta; HEAD observado `3f7a4032aef58c3411f1cf4738479e4123f1d508`.
- Actualizar esta rama desde `origin/main` después de integrar #14, conservando sus cambios de catálogo, archive schema 6 y presentación. No incorporar ni modificar su rama durante esta preparación.
- Resultado nuevo: schema 8, frente a schema 7 actual. Packet schema 1 y trace schema 1 permanecen independientes. No añadir campos obligatorios a `cierre.json` por este cambio; adoptar archive schema 6 de #14 cuando se integre.
- La versión de release se decide contra el `main` integrado; no reservar ni publicar una versión durante la preparación.

## Evidencia y límites del diagnóstico

El comentario de #14 publica una incertidumbre sobre no haber autorizado revisores independientes. `render(..., 'comment')` copia todas las limitaciones y el validador la acepta. La política textual de publicación ya prohíbe mecánica de workers, pero `public_projection()` solo elimina comandos y rutas privadas: no distingue el propósito de cada limitación.

Se contrastaron seis runs locales de Claude, skill 2.9.1: dos `deep` y cuatro `standard`, todos con `same_session`. Algunos justifican no delegar porque el usuario no pidió subagentes. No se encontró un run `extended` en ese conjunto. Los artifacts no documentan una denegación concreta; tampoco permiten asegurar que cada sesión original tenía todas las capacidades disponibles. No reconstruir autorizaciones ni ejecuciones ausentes.

La instalación de Claude y `main` coinciden en sus instrucciones de perfiles/capacidades. «Cuando esté disponible y autorizado» y un fallback no justificado explican la ambigüedad. Además, la traza de #14 comienza describiendo `standard` y el resultado registra `deep` sin transición documentada.

Las referencias oficiales sobre delegación y restricciones son [Claude subagents](https://code.claude.com/docs/en/sub-agents) y [Claude permissions](https://code.claude.com/docs/en/permissions). El diseño usa herramientas realmente disponibles, no nombres de API supuestos ni lanzamiento de otro CLI por defecto.

## Alternativas evaluadas

1. **Separación estructurada y gate de ejecución — elegida.** Clasificar limitaciones y registrar plan/resultados compactos; el renderer selecciona por audiencia y el cierre contrasta referencias existentes. Introduce schema 8 pero proporciona un comportamiento comprobable.
2. **Solo instrucciones.** Barato de implementar, mantiene el hueco demostrado: los helpers siguen aceptando `same_session` sin fundamento y publicando narrativas internas.
3. **Filtros de palabras y más auditorías/agentes.** Los filtros confunden sesiones del producto con sesiones del reviewer; una auditoría adicional aumenta consumo sin resolver la separación de datos. No se adopta.

## 1. Limitaciones y audiencia

En finales schema 8, cada `coverage.limitations` contiene exactamente:

| Campo | Valores / propósito |
|---|---|
| `kind` | `behavior`, `validation`, `execution` |
| `detail` | Explicación completa, no vacía, conservada internamente |
| `material` | Booleano; conserva su efecto real en el veredicto |
| `public_summary` | Texto o null, según las reglas siguientes |

`behavior` corresponde a requisitos o comportamiento del cambio; `validation`, a comprobaciones relevantes pendientes o bloqueadas; `execution`, a capacidades, permisos y mecánica del reviewer. El coordinador clasifica los deltas de workers al finalizar, sin volver a descubrir el repositorio ni alterar packet schema 1.

- `behavior`/`validation`: publicar `public_summary` cuando exista, o `detail` cuando ya sea apto para publicación. No exigir una segunda copia del mismo texto.
- `execution` no material: `public_summary` debe ser null; omitir del comentario público y conservar en informe/JSON.
- `execution` material: exigir un `public_summary` que explique la prueba/comportamiento/gate pendiente; publicar ese resumen y conservar `detail` solo internamente. No convertirlo en una reserva ni bajar su materialidad.
- Si falta la validación requerida, comunicar esa carencia. Si solo existe una ejecución degradada con cobertura suficiente, no inventar una incertidumbre del código.
- Los gaps materiales de la matriz ABCDE siguen siendo visibles en el comentario mediante su impacto, aunque la matriz solo se muestre en el informe.
- Deduplicar el mismo gap al combinar límites y matriz; no repetir un resumen en incertidumbres y reservas.

Ejemplo interno no material: «Agent no disponible en esta sesión; verificación escéptica realizada por el coordinador». Se conserva en artifacts, sin incertidumbre pública. Ejemplo material: detalle interno de denegación con resumen «No se completó la verificación independiente exigida por la política del proyecto». El resumen explica una condición pendiente sin identidades, herramientas o motivos privados.

## 2. Política de todos los campos públicos

El comentario conserva título, veredicto, ID, alcance/versiones, responsables/autores, descripción, Hallazgos, validación útil, incertidumbres materiales y seguimiento anterior. Omitir perfiles, modelos, harness, número/nombre de workers, razonamientos de autorización y rutas privadas.

`verdict_reason`, `reservations`, textos de hallazgos, `checks.evidence`, motivos de reutilización y re-review deben describir producto, evidencia o condiciones de aceptación. Los motivos internos van en `coverage.execution`, limitaciones `execution` y fuentes existentes, nunca como reserva funcional. Una sesión/agente que pertenezca al producto revisado puede aparecer: no redactar mediante una lista negra de palabras.

La estructura hace determinista la selección de limitaciones; no demuestra que una frase arbitraria sea semánticamente segura. El coordinador mantiene un único pase de lectura del borrador público, revisando estos campos antes de la publicación ya autorizada. Sin agente adicional ni otro barrido del código. Renderizado manual, `render-comment` y cualquier proyección pública de handoff deben usar la misma política. Una entrega privada explícita conserva los datos internos correspondientes.

## 3. Delegación incluida en el perfil

Invocar CCR solicita las delegaciones necesarias del perfil explícito o seleccionado automáticamente. Usar la herramienta nativa disponible. Respetar restricciones superiores, prohibiciones del usuario y permisos reales: una skill no habilita herramientas ni concede autorización para acciones remotas o ejecutores externos.

Independencia significa un contexto de revisión separado con inputs neutrales y código fuente accesible, sin resultados de otros descubridores ni transcript completo del coordinador. No requiere otro chat, otro modelo ni un equipo de procesos externos. Dos pases mentales del mismo agente no son independientes. El `context_id` de los packets vincula inputs y puede compartirse; no identifica por sí solo un contexto de agente independiente.

| Perfil | Plan ordinario |
|---|---|
| focused | Un descubridor, potencialmente coordinador, y verificación escéptica en el mismo contexto |
| standard | Un descubridor; verificador fresco para candidatos sustantivos/dudas materiales; excepción existente de descripción mecánica y cierre limpio |
| deep | Dos descubridores frescos, un tercero por necesidad distinta, y un verificador fresco agrupado, incluso sin hallazgos |
| extended | Automático: cuatro/cinco descubridores justificados; explícito: dos a cinco necesarios; un verificador fresco agrupado |

Los gates independientes del proyecto permanecen separados, con fuente verificada; no sirven para disfrazar descubridores opcionales ni ampliar límites. Pocos slots requieren tandas de contextos frescos, no degradación por sí solos. Workers no delegan.

## 4. Registro compacto de cumplimiento

Finales schema 8 requieren `coverage.execution`. Su finalidad es enlazar las observaciones ya producidas, no iniciar otra auditoría o generar un archivo adicional.

| Campo | Contrato |
|---|---|
| `selection_source` | `explicit` / `automatic` |
| `status` | `fulfilled` / `degraded` |
| `plan` | Array de asignaciones: `{id, role, independent, required, reference}` |
| `results` | Array de observaciones: `{assignment_id, reviewer_context, provider_id, reference}` |
| `fallbacks` | Array de impedimentos: `{assignments, reason, detail, source}` |

Asignación: `id` único no vacío; `role` es `discovery`, `verification` o `project_gate`; `independent`/`required` son booleanos. `reference` apunta al plan/brief existente, con preguntas y justificación. Las asignaciones ordinarias necesarias son obligatorias; el tercer descubridor y los adicionales de extended precisan su justificación existente. Los gates señalan su política propia.

Resultado: `reviewer_context` es una etiqueta interna de un contexto realmente observado, distinta del input `context_id`; `provider_id` es el ID expuesto o null; `reference` apunta a un resultado/observación retenido que acredita el pase completado. No fabricar IDs ni inferir frescura por nombres diferentes. Una herramienta sin ID aún puede acreditar independencia mediante su dispatch y resultado observados. El mismo contexto repetido no cuenta como dos revisores. Reintentos fallidos van en traza/fallback, no como resultados completados.

Fallback: `assignments` enumera IDs del plan afectados; `reason` es `tool_unavailable`, `explicit_restriction`, `dispatch_failed` o `quota_exhausted`; `detail` es interno y `source` identifica la evidencia ya disponible del impedimento. «El usuario no pidió subagentes» y «pocos slots» no son motivos válidos. Una restricción explícita del usuario sí lo es. No reintentar indefinidamente ni consultar historiales para completar datos ausentes.

`fulfilled` exige cumplir el plan y sus requisitos de independencia. `degraded` exige un fallback verificable para cada requisito no cumplido, preservando el perfil solicitado y los resultados realmente obtenidos. Una observación del coordinador puede cubrir un pase escéptico de fallback, pero no satisfacer independencia. No rebajar el perfil después del descubrimiento para eludir gates.

El validador del registro comprueba estructura, cardinalidad por perfil, identidad/reutilización de contextos y correspondencia con `coverage.verification`. El gate de retención contrasta referencias existentes con contexto/traza/evidencias retenidas. Ninguno demuestra que un reviewer leyó correctamente el código ni trata el hash como prueba de verdad.

## 5. Veredictos, transición y traza

Mantener precedencia: bloqueante confirmado → `not_approvable`; sin bloqueantes pero cobertura inadecuada, versión obsoleta o gap material → `insufficient_evidence`; reservas funcionales no bloqueantes → `approvable_with_reservations`; de otro modo → `approvable`.

La degradación no constituye un defecto del producto ni genera automáticamente una reserva pública. Un gate independiente obligatorio incumplido o prueba material pendiente sí impide un veredicto favorable. `same_session` describe lo realizado; no acredita un perfil cumplido cuando requería independencia. `unavailable` identifica ausencia de pase, no un pase escéptico ya completado.

Seleccionar y registrar el perfil antes del dispatch. Una escalación automática posterior registra hecho y transición mediante `profile` en trace schema 1 y actualiza plan/contexto, reutilizando revisores válidos. No inferir una transición por el resultado final. Registrar los dispatch/resultados observados con los milestones existentes; no un evento por búsqueda, nuevos contadores o heartbeats. Usar timestamps de fuente o null; mantener fallback por orden de registro.

## 6. Compatibilidad y publicación histórica

Leer/validar y renderizar el informe privado de schemas 1–7 sin migración ni reescritura. Los nuevos finales usan schema 8; versiones y hashes históricos permanecen intactos. Delivery full/brief conserva la versión y la identidad de su fuente.

Una limitación histórica `{detail, material}` carece de clasificación. No inferir su categoría mediante palabras ni republicarla automáticamente sin revisión. `render-comment` y handoff público exigirán clasificación explícita en memoria mediante `--publication-context` cuando el registro histórico tenga limitaciones.

Contexto de publicación efímero: `{source_sha256, limitations}`. `source_sha256` vincula el JSON canónico de entrada; `limitations` contiene una fila por índice original `{index, kind, public_summary}`. Materialidad y detalle proceden de la fuente; no se permite modificarlos. Aplicar las mismas reglas de audiencia, rechazar índices duplicados/ausentes o hash incorrecto. No guardar este archivo por defecto, tocar el original ni reconstruir `coverage.execution` de una review pasada. Si el agente no puede clasificar una limitación, dejar la publicación pendiente y explicar el motivo en privado.

No prometer compatibilidad del visor independiente con schema 8 sin validación propia. Anunciar el nuevo formato y sus consumidores en documentación/changelog del futuro PR; la implementación del visor queda fuera.

## 7. Límites de coste y de alcance

Reutilizar contexto, briefs, resultados y traza; clasificación y gate son trabajo del coordinador. No añadir un reviewer de perfiles, auditor de ejecución, medida de créditos, sondeo temporal, instalación de dependencias o segundo equipo de revisión. La delegación solo cubre asignaciones necesarias; verificación agrupada, sin un verifier por hallazgo/área.

No modificar reviews cerradas, comentarios de otros autores, configuración del harness, el PR #14 ni la skill instalada durante esta preparación. No publicar/mergear/releasear esta rama antes del gate humano. Conservar worktrees de otras revisiones y limpiar únicamente recursos propios al cerrar el flujo autorizado.

## Aceptación

1. Un `execution` no material aparece en informe/JSON y no en comentario; un material comunica su impacto y conserva su efecto en el veredicto.
2. Incertidumbres del producto/validación siguen visibles; palabras como «sesión» del producto no se eliminan.
3. `deep` disponible sin petición adicional usa dos contextos frescos y un verifier; `extended` automático respeta las asignaciones justificadas.
4. `standard` con candidato de código P3 usa verifier fresco; `focused` no delega por defecto.
5. Slots limitados ejecutan tandas; impedimentos reales permiten degradación trazable, sin afirmar independencia ni inventar defectos.
6. Reutilizar un contexto o declarar `same_session` sin impedimento verificable no pasa como `fulfilled`.
7. Perfil/contexto/traza/resultados concuerdan, incluidas escalaciones y gates independientes.
8. Retención, entrega y canonicalización admiten schema 8 con binding de review ID; registros históricos no cambian y publicación histórica incompleta falla antes de enviar.

## Revisión del documento

Comprobados alcance, requisitos, independencia de schemas, costes, permisos y compatibilidad histórica. Este documento fija las interfaces propuestas; sus decisiones requieren revisión antes de ejecutar el plan.
