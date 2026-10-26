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

## Task 3: compatibilidad y aceptación

Se ejecutaron 125 tests distintos de selección focalizada: 14 nuevos (5 corpus/integridad, 3 rutas de política, 6 transporte), 11 paquetes, 34 contrato, 62 trazabilidad y 4 propósito. Todos pasaron. Las suites existentes fallaron primero por WinError 5 al crear/limpiar fixtures temporales en sandbox; se conservaron esos intentos en el workspace de ejecución y se repitieron con permisos revisados, sin tocar producto. No se ejecutó toda la suite del proyecto. [Resultados y comandos](priority-calibration-evidence/validation-results.json).

Los tests de transporte caracterizan comportamiento que ya existía: GREEN inicial, no RED inventado. La prueba nueva de integridad sí hizo RED: Git normalizaba respuestas congeladas y cambiaba sus bytes. Se añadió una excepción -text acotada a los artefactos de evaluación en .gitattributes; luego hizo GREEN. Es el único ajuste fuera del mapa inicial de archivos, para conservar la evidencia ligada a hashes. No se cambió scripts/ccr ni el contrato final 11.

| Muestra | Baseline | Candidato | Alcance de la comparación |
|---|---:|---:|---|
| Desarrollo | 15/20 | 20/20 | Corrige dos sobreclasificaciones P1→P0, dos subclasificaciones P1→P2 y una P2→P3 frente a referencia ratificada |
| Aceptación reservada | 8/8 | 8/8 | Conserva acierto; no demuestra ganancia de precisión en esta muestra |
| Inversión de PC01/02 y PC03/04 | 2/4 | 4/4 | Ninguna etiqueta cambia respecto de la ejecución normal de cada condición |

En desarrollo, subclasificaciones de positivos P0/P1: baseline 2/10 y candidato 0/10; sobreclasificaciones a P0/P1: baseline 2/20 y candidato 0/20. Las tres parejas same_priority de desarrollo mantienen igualdad en ambas condiciones. En aceptación, cada condición omite 0/2 positivos P0, produce 0/6 falsos P0 y confirma indebidamente 0/1 casos no resueltos. No hubo omisiones ni respuestas inválidas en las seis salidas de clasificadores.

[Aceptación por caso y revisión semántica del custodio](priority-calibration-evidence/acceptance-assessment.json), [respuestas candidato](priority-calibration-evidence/candidate-acceptance.json), [comparación de orden inverso](priority-calibration-evidence/reverse-assessment.json), [baseline inverso](priority-calibration-evidence/baseline-reverse.json), [candidato inverso](priority-calibration-evidence/candidate-reverse.json), [inputs inversos](priority-calibration-evidence/reverse-cases.json). Los hashes del corpus/referencias permanecieron intactos.

El custodio encontró justificaciones fieles en aceptación y dos matices: el uso de “global” no debe interpretarse como requisito universal para P0, y una explicación condensa la secuencia causal de borrado/conversión. Se conservan las respuestas originales; estos matices no cambian clasificación ni justifican editar la guía con aceptación.

### Conclusión acotada

La propuesta pasó los criterios de esta muestra ratificada, con candidato congelado antes de abrir aceptación y contextos nuevos por condición. No prueba calibración general, rendimiento en producción o capacidad de descubrir defectos. La inversión usa cuatro casos en vez del lote de veinte: describe estabilidad observada de esas parejas, no aísla estadísticamente todos los efectos de orden/contexto. El modelo efectivo no fue expuesto por la plataforma; no puede verificarse independientemente igualdad de versión de modelo aunque todas las clasificaciones heredaron la configuración de sesión sin override.

La implementación permanece en la rama y el worktree solicitados, con changelog unreleased. No se publicó, instaló ni integró a main. La revisión independiente final de implementación se registra tras su ejecución.

## Revisión final y conservación

[Revisión independiente](priority-calibration-evidence/final-review.md): no hubo problemas materiales ni menores accionables en el rango de implementación. El autor mantiene los límites que el revisor separó de su juicio: precisión general/discovery/producción no medidos, productos históricos sin reclasificar, modelo efectivo no expuesto e integración/publicación no solicitadas. No se requieren cambios de política ni una nueva ronda de evaluación.

Se retuvieron los cinco logs satisfactorios, las seis salidas originales de clasificadores y sus entradas/instrucciones pertinentes. [Inventario SHA-256 de evidencia retenida](priority-calibration-evidence/retained-inventory.json), sin auto-referencia. Los logs de fallos de entorno y material auxiliar del plan se trataron como scratch; sus resultados están resumidos arriba.

Seguimiento: no existe API de todo en esta sesión; se usó el fallback inline permitido y ledger por tarea. El worktree y la rama del usuario se conservan. La excepción Git solo preserva bytes de evidencia; no modifica las reglas generales de saltos de línea.

Comprobación final de rango: los CRLF y la línea vacía terminal originales de algunos prompts/logs congelados activaban advertencias de whitespace. La excepción se acotó a esa carpeta: reconocer CR al final y permitir líneas vacías terminales, conservando checks de espacios al final y espacios antes de tabulaciones. El comando git diff --check sobre d119fbc..HEAD y las 14 pruebas nuevas pasaron después; los 23 hashes retenidos permanecieron idénticos. Este ajuste de atributos posterior a la revisión no cambia la guía ni las respuestas evaluadas.
