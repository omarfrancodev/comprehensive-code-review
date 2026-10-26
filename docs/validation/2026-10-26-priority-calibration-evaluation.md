# Implementación y evaluación de prioridades — 2026-10-26

Base: CCR 3.3.0, d119fbc781312bd15c2eaf5e04f3768f542de7cc. [Protocolo](priority-calibration-protocol.md), [spec](../superpowers/specs/2026-10-26-priority-calibration-design.md).

## Task 1: corpus y baseline

Se crearon 20 casos de desarrollo y ocho reservados por custodio separado. Los cuatro tests del corpus hicieron RED por archivos ausentes y luego GREEN (4/4). Las referencias son propuestas del agente; ratificación humana pendiente. El implementador no leyó hechos ni respuestas de aceptación antes de congelar la guía.

Baseline: dos contextos nuevos, sin reference ni conversación del implementador, con extractos exactos de las reglas de rol de 3.3.0. Es una prueba de verificación sobre hechos suministrados, no una ejecución completa de CCR ni medición de discovery. Modelo efectivo no expuesto; ambas condiciones usan configuración heredada sin override.

Desarrollo baseline: 15/20 decisiones coinciden con la referencia propuesta. PC01/02: P0 en vez de P1; PC05/06: P2 en vez de P1; PC08: P3 en vez de P2. El origen y reconocimiento del riesgo no cambiaron las parejas invariantes en esta ejecución. No se alteraron referencias por los desacuerdos. La aceptación baseline queda retenida sin mostrar sus resultados al autor de la guía.

Fuentes y hashes: [instrucciones baseline](priority-calibration-evidence/baseline-instructions.md), [manifiesto de fuentes](priority-calibration-evidence/baseline-manifest.json), [inputs/contextos](priority-calibration-evidence/input-manifest.json), [respuestas desarrollo](priority-calibration-evidence/baseline-development.json), [evaluación desarrollo](priority-calibration-evidence/baseline-development-assessment.json), [respuestas aceptación baseline](priority-calibration-evidence/baseline-acceptance.json).

No se declara calibración conseguida o aptitud para distribuir. Las mediciones restantes se registrarán tras congelar candidato.
