# Implementación y evaluación de prioridades — 2026-10-26

Base: CCR 3.3.0, d119fbc781312bd15c2eaf5e04f3768f542de7cc. [Protocolo](priority-calibration-protocol.md), [spec](../superpowers/specs/2026-10-26-priority-calibration-design.md).

## Task 1: corpus y baseline

Se crearon 20 casos de desarrollo y ocho reservados por custodio separado. Los cuatro tests del corpus hicieron RED por archivos ausentes y luego GREEN (4/4). Las referencias fueron ratificadas por el usuario tras revisarlas mediante respuesta directa en este chat. El implementador no leyó hechos ni respuestas de aceptación antes de congelar la guía.

Baseline: dos contextos nuevos, sin reference ni conversación del implementador, con extractos exactos de las reglas de rol de 3.3.0. Es una prueba de verificación sobre hechos suministrados, no una ejecución completa de CCR ni medición de discovery. Modelo efectivo no expuesto; ambas condiciones usan configuración heredada sin override.

Desarrollo baseline: 15/20 decisiones coinciden con la referencia propuesta. PC01/02: P0 en vez de P1; PC05/06: P2 en vez de P1; PC08: P3 en vez de P2. El origen y reconocimiento del riesgo no cambiaron las parejas invariantes en esta ejecución. No se alteraron referencias por los desacuerdos. La aceptación baseline queda retenida sin mostrar sus resultados al autor de la guía.

Fuentes y hashes: [instrucciones baseline](priority-calibration-evidence/baseline-instructions.md), [manifiesto de fuentes](priority-calibration-evidence/baseline-manifest.json), [inputs/contextos](priority-calibration-evidence/input-manifest.json), [respuestas desarrollo](priority-calibration-evidence/baseline-development.json), [evaluación desarrollo](priority-calibration-evidence/baseline-development-assessment.json), [respuestas aceptación baseline](priority-calibration-evidence/baseline-acceptance.json).

La ratificación de referencias está registrada; la calibración sigue pendiente del resultado del candidato y la aceptación. Las mediciones restantes se registrarán tras congelar candidato.

## Task 2: guía y desarrollo

Las rutas de prioridad hicieron RED por ausencia de referencia/enlace y luego GREEN (3/3); trazabilidad 3.3.0 sigue GREEN (3/3). La guía es fuente canónica, se carga en verificación/consolidación y conserva impact, packet 1 y final 11.

Candidato de desarrollo: 20/20 decisiones coincidentes con referencia ratificada, frente a 15/20 del baseline. Una muestra por condición; no es mejora estadística general. Se conservaron todas las referencias. La guía no se ajustó tras este resultado.

[Candidato congelado](priority-calibration-evidence/candidate-instructions.md), [manifiesto](priority-calibration-evidence/candidate-manifest.json), [respuestas](priority-calibration-evidence/candidate-development.json), [evaluación por caso](priority-calibration-evidence/candidate-development-assessment.json). Los inputs concretos de aceptación todavía no se abrieron al autor antes de esta congelación.
