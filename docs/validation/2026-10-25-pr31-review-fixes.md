# Validación de ajustes del review del PR 31

Revisión atendida: [comentario F001–F005](https://github.com/omarfrancodev/comprehensive-code-review/pull/31#issuecomment-6408128291), sobre `993c3c0`. Implementación del ajuste: `52aa200`. [Plan](../superpowers/plans/2026-10-25-pr31-review-fixes.md) · [Inventario y resultados](2026-10-25-pr31-review-fixes-suite.json).

## Estado

Los cinco escenarios se reprodujeron y corrigieron. Validación completa: **893 casos en 80 módulos, 890 aprobados y 3 omitidos por permisos Windows, cero fallos y errores**. También aprobaron 55 casos focalizados y la revisión estática independiente no encontró hallazgos. Ajustes publicados en el PR #31 y descripción actualizada, sin merge.

## Diagnóstico y correcciones

| Hallazgo | Causa comprobada | Cambio y prueba responsable |
|---|---|---|
| F001, cobertura material | El gate anterior solo miraba adequate/stale/kind; un resultado final insuficiente puede ser íntegro y completo como archivo | Política pura central exige matriz ABCDE cubierta/no aplicable y ausencia de incertidumbre material. Casos reales independientes para área partial material, not_evaluated material, limitación material, blocker que enmascara gap y rereview acotado |
| F004, lazy fetch | Leer un blob promisor ausente adquiría objetos en las consultas de captura, contexto y API textual | GIT_NO_LAZY_FETCH=1 y allowlist vacía de transportes en el entorno de helpers. Partial clones file:// reales verifican ausencia de objetos y packs nuevos, preservación de blobs ausentes y resultado incompleto/error |
| F002, GIT_DIFF_OPTS | El entorno heredado cambiaba el contexto de los hunks para los mismos objetos | Eliminar el override del entorno; capturas idénticas con/sin --unified=0 heredado |
| F003, archivo/directorio | El pathspec de una fila incluía sus descendientes y mezclaba varios patches | Diff de modificación por pares exactos de blobs; alta/baja a partir del blob individual, sin crear objetos vacíos. Ambas direcciones independientes y controles de archivo vacío, CR y ausencia de newline |
| F005, 64 fuentes | El lector sumaba el contexto derivado al conteo inicial aunque los productores no lo incluyen | El selector común impone 64 indexadas contando el índice y aliases; el contexto conserva su coste dentro de los 64 MiB agregados. Archivo canónico con 64 fuentes más contexto reutilizable; 65 indexadas y exceso de bytes siguen rechazados |

La elegibilidad de cobertura no depende de que el veredicto sea aprobable: un blocker confirmado por sí solo sigue siendo reutilizable con cobertura completa; un blocker junto a incertidumbre material exige revisión nueva. Las limitaciones y reservas no materiales tampoco se rechazan por sí solas. Un rereview completo sigue siendo admisible; sin cobertura ordinaria demostrada no se hereda solo por un vínculo de identidad anterior.

## Evidencia RED → GREEN

- Captura Git: 24 casos, seis fallos de producto esperados antes de corregir: GIT_DIFF_OPTS, ambas transiciones y tres rutas de partial clone. Cero errores de fixture. La captura inicial adquirió los dos blobs ausentes; las consultas de contexto y textual no rechazaron el objeto ausente.
- Admisión real: 19 casos, seis fallos esperados antes de corregir: cinco escenarios de cobertura insuficiente y el caso válido de 64 fuentes más contexto. Los controles positivos de blocker aislado, reservas no materiales y rereview completo ya pasaban.
- GREEN Git/archivo: 36/36 casos. Incluye controles nuevos de límite de bytes, 65 fuentes rechazadas, formato de altas/bajas y cambio después del byte 2.250.000 con prefijo igual.
- GREEN admisión real: 19/19 casos, con prepare/retain/close nativos y fuentes verificadas. Ninguna omisión ni error en estos grupos.

Son tres módulos distintos en la fase GREEN (26 de captura, 10 de archivo, 19 de flujo); los 55 casos están incluidos también en la suite completa y no se suman como casos extra.

Los escenarios del comentario se ejecutan en métodos de prueba separados para que el fallo de uno no evite ejecutar otro. Los controles complementarios de formato usan subtests por fixture. Los resultados RED y GREEN se distinguen de la revisión estática y de la suite global aún pendiente.

## Resultado de la suite completa

| Lote | Módulos | Casos | Fallos | Errores | Omitidos | Duración observada |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 1 | 9 | 0 | 0 | 0 | 1472.440 s |
| 2 | 39 | 442 | 0 | 0 | 2 | 1159.887 s |
| 3 | 40 | 442 | 0 | 0 | 1 | 1533.342 s |

Los tres procesos devolvieron exit 0. Las tres omisiones corresponden a tests existentes de symlinks reales (dos de lock-file safety y uno de archivos/inputs/roots); Windows devolvió WinError 1314. Ninguna prueba se deshabilitó ni se relajaron assertions. El inventario JSON conserva módulos exactos, runner, fallos RED y resultados GREEN reproducibles. No se afirma una corrida adicional de orden monolítico.

Aprobó la comprobación de enlaces documentales y git diff --check. El código de ejecución permanece en 52aa200 desde antes de esta suite; los cambios posteriores son documentales.

## Compatibilidad y límites

Los schemas, el algoritmo ccr-effective-diff-v1 y la identidad por cambios efectivos se conservan. Los hashes completos de binarios, enlaces y contexto, el prefijo textual, los límites y las cachés por captura siguen vigentes. No se reescribe ningún archivo anterior. Lookup histórico sigue consultando resultados insuficientes; el gate nuevo restringe únicamente su reutilización ordinaria.

El patch de altas/bajas reproduce el hunk normalizado completo, incluido el marcador de falta de newline, sin escribir un empty blob en el repositorio. Los objetos requeridos ausentes se declaran incompletos/desconocidos; el coordinador debe adquirirlos explícitamente fuera de los helpers. El entorno se construye para sus subprocesses y no altera la configuración persistida ni el entorno del coordinador.

La protección Git se comprobó con Git 2.45.0.windows.1 y remotos file:// sintéticos. No se contactaron servidores externos para las pruebas de partial clone. La [documentación de Git](https://raw.githubusercontent.com/git/git/v2.45.0/Documentation/git.txt) describe GIT_NO_LAZY_FETCH y GIT_ALLOW_PROTOCOL; la allowlist vacía añade un rechazo de transportes aunque una versión ignore la primera variable.

## Revisión independiente

Revisión estática de solo lectura de `993c3c0..52aa200`, con el paquete de la rama y los requisitos del comentario, en contexto fresco configurado con gpt-6-astra/high. Cero hallazgos críticos, importantes o menores y ningún comportamiento dejado fuera del juicio. Inspeccionó consumidores de Git, selección del índice, lookup histórico, contrato de cobertura y tests modificados. No ejecutó pruebas y condicionó su recomendación a la suite completa del coordinador.

## Decisiones registradas

| Decisión | Motivo y coste si resulta insuficiente |
|---|---|
| Corregir F001–F005, incluidos P3 | El usuario pidió los ajustes del comentario completo; mayor alcance que resolver únicamente bloqueantes |
| Progreso inline | Alternativa opcional ante ausencia de herramienta todo; sin checklist nativo |
| Una tanda coordinada de correcciones | Módulos compartidos y cada fallo reproducido por separado; requiere validar el estado combinado |
| No inferir cobertura heredada por lineage | Una identidad no demuestra cobertura ordinaria; puede exigir una revisión nueva conservadora |
| Desactivar lazy fetch y transportes en helpers | Adquisición explícita a cargo del coordinador; un fetch intencional debe ejecutarse fuera del helper |
| Pares de blobs y formato propio de alta/baja | Evitar pathspec recursivo sin escribir objetos; exige preservar exactamente CR/newline y hunks normalizados |
| Inventario completo en tres procesos | Todos los módulos/casos heredados incluidos; no se añade una corrida de orden monolítico |

## Publicación

Push normal de la rama existente y actualización de la descripción del [PR #31](https://github.com/omarfrancodev/comprehensive-code-review/pull/31). Se verificaron desde GitHub el head inicial del ajuste 9efde51, la base main/4fab306, la rama y el cuerpo actualizado. PR abierto y sin conflictos observados; no se publicó respuesta ni se alteró el comentario original. El cierre documental posterior no cambia el código de ejecución probado en 52aa200.
