# Validación de equivalencia y cobertura

Fecha local: 2026-10-25, America/Mexico_City.

Base: CCR 3.1.0 / `4fab30695bb3c0c47071eb887b38f92328b03ea2`. Rama: `docs/review-equivalence-and-coverage`. Implementación y correcciones finales: hasta `3027103e968b8440cd8b97ac052d462711202224`; documentación de cierre posterior. Capacidades `unreleased`, sin instalación ni publicación.

[Spec](../superpowers/specs/2026-10-25-review-equivalence-and-coverage-design.md) · [Plan](../superpowers/plans/2026-10-25-review-equivalence-and-coverage.md) · [Diagnóstico de base](../analysis/2026-10-25-review-reuse-and-coverage-diagnosis.md).

## Estado

Implementación y validación completadas. Inventario completo: **868 casos en 80 módulos; estado final 865 aprobados, 3 omitidos y ningún fallo ni error pendiente**. Se ejecutaron tres lotes disjuntos; el tercero requirió completar el índice documental y repetir las 7 comprobaciones afectadas. No se afirma una única corrida monolítica verde.

Inventario reproducible de módulos y resultados: [suite JSON](2026-10-25-review-equivalence-and-coverage-suite.json). Python 3.12.14 / unittest.

## Evidencia observada

| Grupo | Resultado observado |
|---|---|
| Baseline 3.1.0 inputs/latest | 16 pruebas aprobadas |
| Identidad canónica inicial | RED por módulo inexistente; GREEN 6/6 |
| Captura Git real inicial | RED por módulo inexistente; GREEN 11/11; ampliada luego con configuración que oculta gitlinks |
| Contexto/setup/selección/preflight | RED por rutas nuevas ausentes; GREEN 44/44 |
| Decisión/exact-inputs | RED por función ausente; GREEN 11/11 |
| Archivo/latest/CLI/caracterización | GREEN 25/25 con TEMP Windows canónico |
| Flujo Git/archives reales, inputs, latest, referencias | GREEN 56/56 |
| Builder final con ownership/contexto registrados | GREEN 11/11; rechaza hashes inventados y materiales nuevos |
| Proyección existente | 32/32 más comprobación directa: P3 no bloqueante y behavior no material visibles; rejected privado. No se cambió el renderer |
| Política de skill | Baseline independiente pidió confirmación ante cambios reales; agente fresco con la política nueva ejecutó `new_review` sin preguntar y ofreció elección solo para `offer_choice` |
| CLI real, sesión propia y repositorio sintético | `new_review` sin resultado anterior; `offer_choice` para resultado equivalente; `blocked_current_scope` ante objetos actuales ausentes |

Las cifras de grupos se superponen; no deben sumarse como casos únicos. La primera ejecución de latest fue bloqueada por ACL del TEMP del sandbox; se repitió con permisos normales. Un test de instalación comparaba una ruta Windows larga con el alias 8.3 de TEMP: se canonicalizó TEMP en el runner, sin modificar assertions ni producto.

## Resultado integrado

| Ejecución | Casos | Fallos iniciales | Errores | Omitidos | Duración observada |
|---|---:|---:|---:|---:|---:|
| Lote 1, 27 módulos | 290 | 0 | 0 | 2 | 1143.476 s |
| Lote 2, 26 módulos | 289 | 0 | 0 | 1 | 2294.390 s |
| Lote 3, 27 módulos | 289 | 4 subcasos de una prueba de inventario documental | 0 | 0 | 798.715 s |
| Repetición tras completar las cuatro filas del índice | 7, ya incluidos en el inventario anterior | 0 | 0 | 0 | 0.873 s |

Las tres omisiones son tests existentes que requieren enlaces simbólicos reales: dos de lock-file safety y uno de archive roots/inputs/files. Windows devolvió WinError 1314. No se deshabilitó ninguna prueba ni se relajaron sus assertions. La repetición documental cubrió `test_script_layout.py`, `test_reference_layout.py` y `test_script_dependencies.py`; no cambió código de ejecución después de los lotes.

`git diff --check` aprobó. El checkout principal seguía limpio en `main` / `4fab30695bb3c0c47071eb887b38f92328b03ea2`; los cambios pertenecen al worktree solicitado. Los regresores de complementos e identidades opacas pasaron dentro del inventario completo. Los checks reales de las tres decisiones CLI también aprobaron.

## Trazabilidad de aceptación

| Criterio del spec | Evidencia implementada |
|---|---|
| 1. Merge, rebase, commit vacío y cambios reales | `test_review_change_scope.py` y `test_review_reuse_flow.py`: repositorios Git y archives reales, con routing de las tres decisiones |
| 2. Bytes, modos y nombres de ruta | `test_review_effective_changes.py` y `test_review_change_scope.py`: binarios, symlink, gitlink, whitespace, CR, newline, NUL y configuración Git adversa |
| 3. Hunks desplazados y contexto relevante | `test_shifted_hunk_keeps_identity_but_changed_context_does_not`, `test_rebase_equal_diff_with_changed_consumed_context_starts_review` y pruebas de materiales |
| 4. Identidad semántica frente a recuperación exacta | `test_exact_recovery_remains_changed_when_code_is_equivalent`, suite de inputs y suites heredadas de recovery/restart; los checks retenidos no cambian de revisión |
| 5. Selección y archivos anteriores | `test_review_reuse_archive.py` y flujo: reconstrucción demostrada, ausencia, corrupción, empate, límite, candidato nuevo y run abierto; sin mutar historia |
| 6. Captura y retención verificadas | `test_review_reuse_context.py`, flujo real prepare/retain/close, source-selection/preflight e inventario de referencias; ownership y fuentes iniciales obligatorios |
| 7. Preguntas y disposición de observaciones | Ocho escenarios en `docs/examples/review-scenario-disposition.md`, pruebas existentes de áreas/presentación/comment y observaciones RED/GREEN de la política de skill; no mide recall del modelo |
| 8. Compatibilidad integrada | Inventario completo de 80 módulos y 868 casos, repartidos sin solapamiento por módulo en tres procesos; resultado final abajo |

## Revisión independiente y pasada de corrección

Se revisó estáticamente `4fab306..2e9a58f` en un contexto fresco configurado con gpt-6-astra/high. No ejecutó pruebas ni modificó archivos. Se reprodujeron antes de corregir:

- Un `presentation.kind=complement` podía ofrecerse para reutilización como una revisión ordinaria completa. `test_partial_complement_is_not_reused_as_ordinary_mr_review` falló y luego pasó; ahora fuerza revisión nueva.
- Una identidad opaca de configuración modificada u omitida podía pasar inadvertida con materiales de bytes iguales. `test_opaque_configuration_identity_change_starts_review` y `test_omitted_known_configuration_identity_is_not_equivalent` fallaron y luego pasaron; se comparan también las cuatro identidades observadas de material.

La pasada focalizada posterior aprobó los regresores de producto; un fixture dejó review.json al reutilizar su directorio y se corrigió usando directorios únicos. Su regresión focalizada pasó. La suite completa posterior es la autoridad de cierre; no se solicitó otra revisión del mismo diff.

El tercer lote encontró cuatro subcasos fallidos de una única prueba de inventario: los módulos nuevos no figuraban en scripts/README.md. Se completaron sus cuatro filas y se repitieron estructura, referencias y dependencias: 7/7 aprobadas, sin cambiar código de ejecución. El resultado inicial y su repetición quedan diferenciados en el inventario JSON.

## Compatibilidad y límites

- Archive 8/layout 2, review schema 10, trace schema 1 y packet version 1 se conservan. No se modifican archivos de revisión históricos.
- La comparación exacta de inputs, resume/recover, recibos, ownership, selección inicial y dispatch-identity de 3.1.0 mantienen sus gates.
- Los archivos anteriores sin sidecars siguen siendo consultables. Solo se reutilizan con reconstrucción verificable; evidencia insuficiente inicia revisión nueva. Hay una integración real de reconstrucción con árboles iguales y fuentes completas.
- `lookup --select latest` conserva consulta histórica explícita. La CLI nueva decide; no despacha agentes ni publica comentarios.
- La equivalencia de programas arbitrarios y la calidad de descubrimiento de los modelos no se deducen de hashes o tests verdes.

## Decisiones de ejecución y revisión

| Decisión, en orden de ejecución | Motivo y límite | Coste si la decisión resulta insuficiente |
|---|---|---|
| Ejecución inline y una revisión final fresca | TDD y commits preservan límites; se usó un reviewer independiente final | Menos aislamiento por tarea que con implementadores separados |
| Ledger y estados inline | No existe herramienta todo; se aplicó su alternativa opcional | Menor visibilidad del progreso que un checklist nativo |
| Contexto final desde la claim del run | La firma planeada no aporta run_dir: se obtiene de ownership verificado y se preservan sus inputs originales | La aplicabilidad depende de la identidad y fuentes originales verificadas |
| TEMP canónico en el runner | Resuelve diferencias 8.3 de Windows sin cambiar producto ni assertions | No se ensaya además el spelling 8.3 que confundía el fixture anterior |
| Resolver review-context como evidencia derivada | Se carga desde selección/inventario retenido al revalidar y cerrar; no altera entradas iniciales | Un material externo nuevo debe seguir rechazándose y recapturarse en otro run |
| Integridad no prueba verdad del review | Se confía en observaciones retenidas del coordinador y su completitud; no hay certificación criptográfica de las lecturas | Sidecars históricos coherentes pero falsificados pueden declarar un inventario falso |
| Frescura remota a cargo del coordinador | El helper valida objetos fijados; readquirir refs antes de actuar sobre una decisión demorada | Una captura remota vieja puede dejar una decisión obsoleta |
| Sin arreglo adicional de carrera posterior al chequeo final | No se encontró un flujo normal demostrado | Cambios externos posteriores requieren una nueva admisión; la evaluación no congela el proveedor remoto |
| Ejemplos no equivalen a benchmark de modelos | Se prueban reglas y proyección, sin prometer recall ni ahorro | La calidad de descubrimiento del reviewer sigue sin cuantificarse |
| Suite completa en tres lotes de procesos | Inventario disjunto de todos los módulos test_*.py, incluidos casos heredados | No se ensaya adicionalmente el orden monolítico ni interferencia entre módulos en un único proceso |


**Mejora menor diferida:** el colector lee/hashea ambos blobs textuales completos al clasificarlos y luego conserva solo hunks; la recaptura actual repite trabajo. Es I/O adicional concreto para archivos grandes. No se midió latencia. Una mejora posterior puede separar prefijos de hashes completos y agrupar consultas, con pruebas de preservación de bytes. No afecta las decisiones conservadoras de esta entrega.
