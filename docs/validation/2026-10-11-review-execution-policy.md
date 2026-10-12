# Validación de publicación y cumplimiento de perfiles

## Alcance

Rama `feat/review-execution-policy`, aislada y actualizada desde main 28ef2fa antes de implementar. El usuario autorizó ejecución nativa e incorporar los cambios a 2.10.0 pendiente; este PR no crea tag ni release. Archive schema 6 y catálogo del PR #14 se conservan. El nuevo final usa schema 8; lectura privada histórica 1–7, packet/trace 1 permanecen independientes.

## Evidencia de implementación

- Tasks 1–2: RED por ausencia de soporte schema 8; GREEN de limitaciones clasificadas, cardinalidad, contextos/proveedores reutilizados, fallback observado, verificación real y fuentes de transiciones. Commit conjunto evita habilitar un envelope sin gate.
- Task 3: RED reprodujo detalle de mecánica interna en comentario/handoff y falta de clasificación histórica. GREEN: selección por audiencia, impacto material preservado, deduplicación, contexto efímero con hash/índices exactos y CLI. JSON fuente permanece intacto; vocabulario de sesiones del producto no se elimina.
- Task 4: RED de binding de review ID, fuentes ausentes/perfil discordante y receipt portable. GREEN: retención verifica fuentes seleccionadas y traza antes de escribir; lectura vuelve a contrastarlas. Full/brief preservan schema/identidad/procedencia estructural sin resolver fuentes de otro equipo; fuente original inmutable.
- Regresión adicional: un candidato de código P3 todavía no resuelto también requiere verificador fresco en standard; RED observado antes de corregir la selección del gate.
- Regresión de procedencia: el contexto automático no puede presentarse como selección explícita para eludir la cardinalidad de extended; RED observado y selección contrastada con la fuente retenida.
- Suites focalizadas observadas: contrato 34, trazabilidad 19, perfiles 10, publicación 10, política/archivo schema 8 26, áreas 15, extended 9, archive 38 (una omisión del host), entrega 20; sin fallos en sus ejecuciones finales.

## Prueba de flujo acotada

Fuente sintética ajena a producto/MRs reales: contrato de centavos y filtrado por propietario. Dos descubridores nativos separados, con inputs neutrales y áreas B/D y C/E, se ejecutaron por tandas desde una petición deep sin solicitud adicional de subagentes. Cada uno devolvió su propio candidato estático; no recibió el hallazgo del otro ni el transcript del coordinador. IDs de proveedor y tiempos de fuente no expuestos permanecen null. Un verificador fresco confirmó ambos candidatos juntos contra los contratos estáticos. No demuestra defectos introducidos respecto a un baseline ni una ejecución de tests del producto.

Ese verificador también aplicó las instrucciones a escenarios de prohibición explícita (sin dispatch, deep degradado con fuente y gate pendiente), un solo slot (tandas frescas) y tres necesidades distintas (deep con tercer descubridor justificado; insuficiente para extended automático). La revisión final de la rama se realiza por separado porque ese agente ya no estaba disponible al reanudar la sesión.

Las pruebas de contrato cubren prohibición explícita con fallback, sin independencia inventada, y extended automático de cuatro/cinco asignaciones frente a explícito de dos a cinco. Estos escenarios estructurales no demuestran permisos ni disponibilidad reales de Claude Code u otros harness. No se consultan historiales ni se reconstruyen las sesiones diagnosticadas.

## Comprobaciones y estado

- AST de scripts y enlaces relativos de documentación modificada válidos.
- Tres helpers CLI `--help` y diff check válidos.
- `skill-creator/scripts/quick_validate.py` no pudo iniciarse: el intérprete disponible carece de PyYAML. No se instaló dependencia adicional. El frontmatter se contrasta con main; nombre, descripción y versión 2.10.0 se conservan.
- Suite integrada anterior a la revisión final: 282 tests en 215.260 s, 281 aprobados y uno omitido por symlinks en Windows; incluye las correcciones de los dos fixtures históricos y las regresiones adicionales.
- Revisión independiente de la rama: dos hallazgos importantes (focused/gate de proyecto e historial de perfil) y una duplicación reclasificada como importante por poder reintroducir un detalle ya clasificado como interno. Una sola pasada de corrección, sin segunda revisión: regresiones nuevas observadas RED→GREEN; 26 tests de ejecución y 10 de publicación pasan.
- Suite completa posterior a las correcciones: 288 tests en 200.902 s, 287 aprobados y una omisión por symlinks en Windows. No hay hallazgos críticos/importantes sin atender ni menores diferidos de esta revisión.

## Correcciones de revisión final

- Focused conserva descubrimiento/verificación ordinarios en el mismo contexto y permite el gate independiente requerido por el proyecto; reutilizar el contexto del coordinador para el gate sigue fallando.
- Historial explícito fijo y automático sin descensos. Selección inicial anterior al trabajo; escalación anterior al trabajo ordinario posterior, permitiendo reutilizar descubrimiento previo válido.
- Gaps ABCDE coincidentes se agrupan por detalle original antes de elegir el resumen público, también en handoff e históricos. Un gap material no puede ocultarse tras una clasificación execution no material sin resumen; la publicación queda bloqueada y la fuente privada intacta.
- Fuera del juicio mecánico: semántica arbitraria de prosa (un pase del coordinador), veracidad/competencia del reviewer (provenance no la prueba), compatibilidad del visor independiente y disponibilidad del validador opcional. Estos límites se mantienen explícitos; no se añaden filtros por palabras, auditorías ni dependencias.

## Límites

Las etiquetas y hashes no prueban que un revisor haya leído correctamente el código. El gate contrasta estructura, fuentes y observaciones retenidas; el coordinador hace un único pase sobre la prosa pública. No hay filtro semántico universal, auditor adicional, medición de créditos o migration de históricos. El visor independiente deberá aceptar final schema 8 además de archive 6; su compatibilidad no se valida ni modifica aquí.

## Entrega

[PR #16](https://github.com/omarfrancodev/comprehensive-code-review/pull/16) abierto contra main y adjunto al chat. Entrega inicial verificada con implementación validada en eb3020f; la atención posterior a comentarios CCR y sus comprobaciones se registran abajo. Sin merge/tag/release; versión 2.10.0 pendiente. Los worktrees ya fusionados se retiraron y el worktree de esta rama permanece para la revisión humana. Scratch propio se elimina después de guardar su validación/decisiones en Git.
## Atención del code review del PR #16

Fuente: [comentario CCR CR-9bb16936270f43f4aa4f](https://github.com/omarfrancodev/comprehensive-code-review/pull/16#issuecomment-6117979206), sobre 14487d3. Los tres hallazgos se contrastaron con código y regresiones; no se modificó el comentario original ni reviews cerradas.

| Hallazgo | Corrección y evidencia |
|---|---|
| F001, bloqueante | El contexto automático comparte el guard de propiedad de evidencia seleccionada. Rechaza el destino sin inventariar antes de escribir y conserva snapshot/bytes ajenos. Reintentos con hashes planificados o ya inventariados siguen funcionando, incluido un fallo real después de escribir el contexto propio. |
| F003 | Brief schema 8 muestra ejecución cumplida/degradada además de verificación. Un deep degradado válido con verificador independiente conserva ambas observaciones; los formatos históricos no adquieren el nuevo campo. |
| F002 | Comentario y handoff deduplican reservas contra detalle fuente y texto público proyectado. Una condición distinta sigue visible; detalle privado, veredicto y JSON original permanecen intactos. Incluye clasificación histórica vinculada. |

RED observado: F001 sobrescribe el archivo ajeno; F003 omite ambos estados; F002 repite detalle/resumen en schema 8 e histórico. GREEN focalizado: 29 tests de ejecución/archivo y 11 de publicación. Suite integrada posterior: 292 tests en 186.415 s, 291 aprobados y uno omitido por symlinks en Windows. AST, enlaces modificados y diff check válidos. Las incidencias de entorno del code review externo no se trataron como defectos de producto; esta suite local se informa por separado. Correcciones incorporadas a 2.10.0 pendiente, sin cambios de schemas ni nuevas dependencias.

## Decisiones de la implementación inicial

- Continuar la ejecución nativa autorizada y adelantar la integración de main: respeta el flujo elegido y adopta archive 6 antes del código dependiente. Coste si la interpretación del método fuera incorrecta: cambiar el método antes de integrar; adelantar la dependencia no cambia producto.
- Resolver fragmentos únicamente en fuentes seleccionadas y distinguir procedencia portable de acceso a archivos: evita un nuevo barrido/auditor. Coste: enlaces no seleccionados o fragmentos no soportados requieren corregir la selección antes de retener.
- Actualizar también maintenance/evaluation por su afirmación de schema actual: evita documentación contradictoria. Coste: ampliación documental del alcance.
- Sustituir el reviewer indisponible al reanudar: había evaluado solo los probes; un nuevo contexto hizo la única revisión de implementación. Coste: un dispatch adicional.
- El helper de cierre de Task 5 consumió el resultado integrado ya observado y comprobó AST, sin repetir la suite sin cambios: el runtime/tests permanecía igual. Coste: riesgo de evidencia obsoleta, acotado al contraste del árbol; las correcciones posteriores sí requieren otra suite completa.
- Mantener el pase semántico de prosa en el coordinador: no añadir un filtro por palabras. Coste: prosa no clasificada puede filtrar mecánica si falla el pase del borrador.
- Provenance no acredita veracidad ni competencia del reviewer: se conserva el alcance mecánico aprobado. Coste: observaciones fabricadas podrían satisfacer estructura/hashes.
- Mantener el visor independiente fuera de alcance y declarar schema 8: no presumir compatibilidad. Coste: actualizar un consumidor antiguo antes de leer los nuevos resultados.
- Documentar PyYAML ausente y symlinks omitidos sin instalar dependencias: conservar checks alternativos y frontmatter idéntico. Coste: esas comprobaciones quedan sin ejecutar en este host.
