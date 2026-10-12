# Validación de publicación y cumplimiento de perfiles

## Alcance

Rama `feat/review-execution-policy`, aislada y actualizada desde main 28ef2fa antes de implementar. El usuario autorizó ejecución nativa e incorporar los cambios a 2.10.0 pendiente; este PR no crea tag ni release. Archive schema 6 y catálogo del PR #14 se conservan. El nuevo final usa schema 8; lectura privada histórica 1–7, packet/trace 1 permanecen independientes.

## Evidencia de implementación

- Tasks 1–2: RED por ausencia de soporte schema 8; GREEN de limitaciones clasificadas, cardinalidad, contextos/proveedores reutilizados, fallback observado, verificación real y fuentes de transiciones. Commit conjunto evita habilitar un envelope sin gate.
- Task 3: RED reprodujo detalle de mecánica interna en comentario/handoff y falta de clasificación histórica. GREEN: selección por audiencia, impacto material preservado, deduplicación, contexto efímero con hash/índices exactos y CLI. JSON fuente permanece intacto; vocabulario de sesiones del producto no se elimina.
- Task 4: RED de binding de review ID, fuentes ausentes/perfil discordante y receipt portable. GREEN: retención verifica fuentes seleccionadas y traza antes de escribir; lectura vuelve a contrastarlas. Full/brief preservan schema/identidad/procedencia estructural sin resolver fuentes de otro equipo; fuente original inmutable.
- Regresión adicional: un candidato de código P3 todavía no resuelto también requiere verificador fresco en standard; RED observado antes de corregir la selección del gate.
- Regresión de procedencia: el contexto automático no puede presentarse como selección explícita para eludir la cardinalidad de extended; RED observado y selección contrastada con la fuente retenida.
- Suites focalizadas observadas: contrato 34, trazabilidad 19, perfiles 10, publicación 8, política/archivo schema 8 22, áreas 15, extended 9, archive 38 (una omisión del host), entrega 20; sin fallos en sus ejecuciones finales.

## Prueba de flujo acotada

Fuente sintética ajena a producto/MRs reales: contrato de centavos y filtrado por propietario. Dos descubridores nativos separados, con inputs neutrales y áreas B/D y C/E, se ejecutaron por tandas desde una petición deep sin solicitud adicional de subagentes. Cada uno devolvió su propio candidato estático; no recibió el hallazgo del otro ni el transcript del coordinador. IDs de proveedor y tiempos de fuente no expuestos permanecen null. Un verificador fresco confirmó ambos candidatos juntos contra los contratos estáticos. No demuestra defectos introducidos respecto a un baseline ni una ejecución de tests del producto.

Ese verificador también aplicó las instrucciones a escenarios de prohibición explícita (sin dispatch, deep degradado con fuente y gate pendiente), un solo slot (tandas frescas) y tres necesidades distintas (deep con tercer descubridor justificado; insuficiente para extended automático). La revisión final de la rama se realiza por separado porque ese agente ya no estaba disponible al reanudar la sesión.

Las pruebas de contrato cubren prohibición explícita con fallback, sin independencia inventada, y extended automático de cuatro/cinco asignaciones frente a explícito de dos a cinco. Estos escenarios estructurales no demuestran permisos ni disponibilidad reales de Claude Code u otros harness. No se consultan historiales ni se reconstruyen las sesiones diagnosticadas.

## Comprobaciones y estado

- AST de scripts y enlaces relativos de documentación modificada válidos.
- Tres helpers CLI `--help` y diff check válidos.
- `skill-creator/scripts/quick_validate.py` no pudo iniciarse: el intérprete disponible carece de PyYAML. No se instaló dependencia adicional. El frontmatter se contrasta con main; nombre, descripción y versión 2.10.0 se conservan.
- Suite integrada y revisión independiente: pendientes al preparar este registro; se actualizará con el resultado observado antes del PR.

## Límites

Las etiquetas y hashes no prueban que un revisor haya leído correctamente el código. El gate contrasta estructura, fuentes y observaciones retenidas; el coordinador hace un único pase sobre la prosa pública. No hay filtro semántico universal, auditor adicional, medición de créditos o migration de históricos. El visor independiente deberá aceptar final schema 8 además de archive 6; su compatibilidad no se valida ni modifica aquí.
