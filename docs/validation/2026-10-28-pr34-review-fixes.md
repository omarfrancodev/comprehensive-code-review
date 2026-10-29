# Correcciones del code review del PR 34

Estado: los siete hallazgos están corregidos y el recheck independiente está aprobado. Cierre del 2026-10-29 sobre `22fb380`: 1075 pruebas cubiertas, 1072 aprobadas y tres omitidas por privilegios de symlink. El último resultado de todos los módulos es satisfactorio tras repetir un bloque por un error de E/S de Windows, detallado abajo.

Fuente: [comentario de revisión CR-c0d69fe2d3e74f599f85](https://github.com/omarfrancodev/comprehensive-code-review/pull/34#issuecomment-6488607760), sobre `27842fe`. Se contrastaron los siete hallazgos y todos requirieron corrección. La rama sigue siendo `docs/profile-session-topology`, con destino `main`.

## Cambios y comprobaciones

| Hallazgo | Corrección y regresión |
|---|---|
| F003 — P1: credenciales en headers y URLs | Extraer credenciales Bearer/Basic de headers y todos los valores de query sensibles; conservar formas originales y decodificadas, incluidos nombres de parámetros codificados, HTML y esquemas en mayúsculas. Ocultar repeticiones en comando, recursos, explicación, evidencia, comentario, draft, handoff, JSON y full/brief. |
| F007 — P1: URLs sensibles en delivery, preexistente | Aplicar la política compartida antes de admitir referencias y URLs, también en contexto y sin sidecar. Omitir URLs opcionales sensibles y usar referencias retenidas seguras; rechazar identidades estructurales sensibles en vez de reescribirlas. Conservar enlaces públicos benignos. |
| F001 — P2: despacho final temprano sin resultado | Validar despachos originales presentes aunque falte el resultado. Incluir milestones de inicio/finalización del coordinador ligados a su fallback y a su nombre/provider; ignorar identidades ajenas y conservar `unavailable`, historia y controles de inicio tardío. |
| F002 — P2: cierre interrumpido con sidecar | Reconstruir únicamente el par review/disclosure y los contenidos old/planned autorizados por hashes. Validar un overlay coherente antes de escrituras, tras comprobar observación, recibos y claims. Probar ambas fronteras del sidecar, idempotencia, bytes alterados, inventario ampliado, handoff y modelo seleccionado. |
| F004 — P2: wrapper normalizado por basename | Un ejecutable con ruta no se acredita por llamarse pytest u otra herramienta permitida: usar explicación, conservando recursos originales probados por separado. Capturar argv[0] cuando es un recurso original. Mantener adaptadores conocidos invocados por nombre simple. |
| F006 — P2: envelope insuficiente para model-usage | Límite específico de 896 KiB para el request: 128 KiB de envelope más tres veces 256 KiB por expansión ASCII de JSON. El builder conserva 256 KiB/256 entradas, diagnósticos no bloqueantes y el prefijo previo. Las otras operaciones conservan sus límites. |
| F005 — P3: proceso homónimo oculta reviewer unknown | Separar procesos/tools de participantes que usan modelo al comparar cobertura; conservar la equivalencia deliberada coordinador/agent para el mismo revisor. |

Las nueve decisiones funcionales aprobadas y las versiones de los contratos se conservan. No se añadieron dependencias, migración, backfill histórico, detección automática de modelos ni compatibilidad certificada con el viewer externo.

## Verificación

Cada causa se reprodujo con pruebas que fallaron antes de la corrección y pasaron después. Los controles negativos incluyen secretos con codificación porcentual repetidos, wrappers con rutas, eventos de actores ajenos, reintentos tardíos, cambios no autorizados de inventario, recibos de cleanup distintos, límite real del ledger y conservación de enlaces benignos.

Resultados específicos, con cobertura superpuesta:

- Topología/modelos/setup/CLI: 112 pruebas en 86.487 s; caracterización CLI/encodings: cuatro en 0.457 s; boundaries: dos en 0.090 s.
- Disclosure e integración: 33 pruebas en 33.989 s; tras cubrir la forma codificada original de credenciales, 23 pruebas enfocadas en 11.846 s.
- Cierre/atomicidad/archive y cleanup: 25 pruebas en 162.561 s; conjunto final de siete regresiones del cierre en 123.231 s.
- Referencias sensibles: cinco pruebas en 0.068 s sobre la implementación integrada.
- Tras cubrir milestones del coordinador sin resultado: 68 pruebas de topología y ejecución en 23.897 s.

Estos conteos no se suman. La revisión independiente encontró inicialmente dos variantes residuales de F001/F003; ambas se corrigieron y su recheck las declaró ADDRESSED, sin problemas nuevos ni comportamientos descartados sin juzgar. La validación completa cubrió las 1075 identidades únicas descubiertas en 101 módulos. La primera pasada terminó en 1409.047 s con cero fallos de aserción, un error de E/S y tres omisiones. El error fue `PermissionError: WinError 5` en `os.replace` del archivo de trazabilidad de un fixture de `test_review_closure_consistency`; la ruta tenía 237 caracteres. El caso aislado pasó en 29.580 s y después el módulo completo de 25 pruebas pasó sin concurrencia en 152.891 s, usando el mismo código, expectativas y límite de temporal. No se determinó qué proceso provocó la denegación original. La primera pasada no se presenta como una ejecución global aprobada; la evidencia conserva su error y la repetición completa del módulo.

Las tres omisiones corresponden a privilegios de creación de symlinks de Windows (`WinError 1314`), sin exclusión manual. Los conteos por módulo, el commit, la huella de las identidades descubiertas y los intentos figuran en [la evidencia de suite](2026-10-29-pr34-review-fixes-suite.json).

La ejecución usa Python incluido, `-B`, temporales separados y cuatro procesos; cada módulo descubierto se ejecuta una vez con su conteo y código de salida comprobados. No se invocan proveedores de modelos ni harnesses externos mediante las pruebas.

Después de la validación únicamente se completó esta documentación/evidencia y se retiró una línea vacía final del nuevo test de recuperación; su AST no cambió. El código de producto permanece idéntico al commit probado. Los fixtures históricos y el inventario CLI congelado se conservan.
