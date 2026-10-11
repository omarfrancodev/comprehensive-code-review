# Validación: identidad del harness y etiquetas de reporte

## Alcance y estado

Base `main` d54be59e2d09117d59c5a8664fcb1a68d6649bb5; rama `feat/harness-catalog`, worktree local aislado. Versión preparada 2.10.0, pendiente de revisión del PR y publicación. Los tres ajustes originales del usuario siguen intactos y sin commit en el checkout principal; sus equivalentes se incorporaron en esta rama.

Catálogo inicial versión 1: 52 identidades, 17 familias. Resolución una vez al preparar el cierre schema 6; texto original preservado, procedencia y diagnósticos explícitos. Archivo 1–5 compatible, final review 7 y trace 1 sin cambios. Ningún archivo histórico o proyecto externo se modificó.

## Evidencia de implementación

- RED inicial: resolver ausente, kwargs/CLI de identidad inexistentes; GREEN: diez pruebas de harness, incluyendo CLI real, desconocidos, conflictos, configuración, alias, procedencia inválida, conservación del texto original, identidad durante processing/retain/close y lectura histórica sin campos sintéticos.
- Ampliación solicitada durante la implementación: la prueba de nuevas identidades falló antes de añadirlas y pasó con el catálogo ampliado. Pruebas distinguen familias genéricas, superficies específicas y nombres de modelos/editores sin identidad de harness.
- RED de brief: faltaban negritas en hallazgos/checks/incertidumbres/seguimiento. GREEN: etiquetas y escape; las anclas conservan líneas en blanco y enlaces/IDs históricos. La prueba de incertidumbre encontró contenido sin escape en el renderer compartido; se corrigió el texto aportado sin escapar las etiquetas generadas.
- Trace: 27 pruebas pasaron, incluidas recuperación transaccional, processing, fuentes de tiempo, referencias locales e inmutabilidad.
- Primera suite completa: 247 pruebas, dos fallos por expectativas antiguas del cierre schema 5. Actualizadas a 6 sin cambiar los asserts del contrato final histórico ni la ausencia de mediciones.

## Revisión independiente

Una única revisión final de solo lectura, sin archivos ni suite duplicada, identificó aceptación indebida de `--harness-source-file` con JSON null. La regresión CLI falló antes de la corrección; ahora se rechaza antes de escribir, con o sin ID explícito. No hubo otros defectos materiales reportados. La ampliación posterior del catálogo se verificó con pruebas de datos, alias y conflictos; no se lanzó otra revisión completa.

## Resultado final

`python -B -X utf8 -m unittest discover -s tests -v`: **249 pruebas en 202.425 segundos, 248 aprobadas, una omitida; sin errores ni fallos**. La omisión corresponde a enlaces simbólicos no permitidos por el usuario de Windows; la comprobación de junctions sí pasó.

- AST válido para nueve scripts Python; cuatro invocaciones CLI help, incluidas las nuevas opciones de prepare.
- Enlaces Markdown locales, frontmatter/versión y `git diff --check` válidos.
- Inventario y contenido originales de main conservados; identidad Git `omarfrancodev` / `fofe2803@gmail.com`.
- Pruebas usan registros y repositorios sintéticos; no se publican reviews privados, logs del equipo ni credenciales.

## Límites y seguimiento

El catálogo identifica declaraciones, no detecta procesos ni certifica integración con cada plataforma. Entornos personalizados siguen aceptados con texto original e ID desconocido. Lectores preservan ID/versión almacenados y no consultan el catálogo actual para reinterpretarlos. La incertidumbre de metadatos no cambia el veredicto de código. Sin mediciones, telemetría ni barridos nuevos.

El visor independiente conserva su documentación previa y deberá aceptar archive schema 6 cuando se actualice ese proyecto; no forma parte de este PR. README/instalación siguen enlazando la última release publicada. Merge, tag, release, actualización local y limpieza del worktree esperan aprobación humana.
