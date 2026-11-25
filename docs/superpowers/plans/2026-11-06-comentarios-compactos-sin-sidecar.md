# Publicación de comentarios desde runs compactos Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task by task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Objetivo.** Preparar y verificar comentarios desde un compacto cerrado aunque no conserve sidecar, manteniendo el bloqueo si la selección declarada es inválida.

**Arquitectura.** Validar el compacto mediante el lector existente, resolver la divulgación en una sola ruta de entrada para `prepare` y `verify`, y reutilizar el constructor explicativo de entrega. Los renderizadores reciben el contexto resuelto por su API actual.

**Tecnología.** Python, `argparse`, `unittest` y los lectores, validadores y fixtures de CCR.

**Spec.** [Publicación de comentarios desde runs compactos sin sidecar](../specs/2026-11-06-comentarios-compactos-sin-sidecar-design.md).

## Global Constraints

- La base revisada es `0a459b6` de `main` (CCR 3.8.0), con el contrato editorial de borrador 4 integrado.
- Conservar los esquemas, los artefactos originales, la separación de las sesiones, los permisos de publicación y la semántica de `--input`, incluidos los borradores históricos.
- Seleccionar el fallback solo por ausencia comprobada. Los errores del lector, del sidecar y de sus pruebas son bloqueantes.
- Mantener `contract render-comment` y las entregas `brief` y `full` compatibles. No ejecutar checks ni operaciones de red en las pruebas.
- Ejecutar los comandos desde la raíz del repo. En Windows, usar un directorio temporal de pruebas corto y privado si los fixtures de Git exceden el límite de ruta.

## Review Focus

| Riesgo | Cobertura requerida |
| --- | --- |
| Una referencia defectuosa se confunde con ausencia | Tarea 2, casos de referencia errónea, sidecar perdido o huérfano, prueba inválida y manifiesto alterado en ambos comandos. |
| El fallback filtra comandos o altera el resultado | Tareas 1 y 2, paridad con entrega, selección sin pruebas y checks ejecutados, externos, fallidos u omitidos. |
| El borrador pierde su vínculo con el registro o la verificación se relaja | Tarea 2, otro compacto, edición con hash recalculado, CRLF, LF final omitido en GitLab y recreación de la vista de divulgación. |
| Una ruta nueva modifica el archivo o usa la sesión equivocada | Tarea 2, retiro de la sesión original, nueva sesión propia, salida exclusiva y comparación byte por byte. |
| Cambian la entrega o los consumidores históricos | Tareas 1 y 3, `--input` con y sin par explícito, borradores 2/3/4, render directo, entrega completa y breve. |

## Tarea 1. Compartir la construcción explicativa

**Archivos.** `scripts/ccr/reporting/check_disclosure.py`, `scripts/ccr/reporting/delivery.py`, `tests/test_review_check_disclosure.py`.

- [x] Agregar primero una prueba del constructor compartido con checks de Git y snapshot. Afirmar que vincula la vista al registro, produce una fila por check y deja vacíos el comando, los recursos y las referencias. Ejecutar la selección y confirmar que falla por el punto de entrada faltante.

  ```powershell
  python -B -X utf8 -m unittest discover -s tests -p 'test_review_check_disclosure.py'
  ```

- [x] Extraer `build_explanation_only_disclosure(record)` alrededor de `build_check_disclosure`. Conservar la identidad `head`/`snapshot` y pasar observaciones vacías. Reemplazar únicamente la construcción equivalente en entrega. Conservar la selección de fuentes que entrega pasa a la proyección y las demás ramas de divulgación.
- [x] Ejecutar la prueba anterior y las dos suites de regresión. Verificar que ambas entregas conservan el resultado explicativo sin sidecar y la divulgación acreditada cuando sí hay sidecar.

  ```powershell
  python -B -X utf8 -m unittest discover -s tests -p 'test_review_compact_archive.py'
  python -B -X utf8 -m unittest discover -s tests -p 'test_review_compact_fixes.py'
  ```

## Tarea 2. Resolver la publicación desde un compacto verificado

**Archivos.** `scripts/ccr/cli/comment.py` y nuevo `tests/test_review_compact_comment.py`. El lector y el verificador de borradores existentes se reutilizan.

- [x] Agregar primero pruebas de los comandos con un fixture compacto publicado y una sesión de publicación nueva. Cubrir la ausencia del sidecar y de la sesión de captura original, un compacto con divulgación acreditada y uno sin checks. Usar casos de MR y range o commit, con al menos un caso de snapshot en la cobertura del fallback. Afirmar que la explicación preserva los estados y que el cuerpo pasa la verificación exacta. Ejecutar y confirmar el fallo inicial por ausencia de `--run-dir`.

  ```powershell
  python -B -X utf8 -m unittest discover -s tests -p 'test_review_compact_comment.py'
  ```

- [x] Extender las pruebas con una referencia de nombre o tipo inválido, un sidecar seleccionado que falta, bytes alterados, una identidad inicial distinta y una prueba referenciada inválida. Incluir un sidecar canónico en el inventario sin referencia. Para las pruebas semánticas, conservar hashes e inventario coherentes en la fixture para llegar al validador correspondiente. Verificar fallo de ambos comandos, ausencia de éxito y ausencia de un archivo de salida de preparación. Repetir el fallo si se alteran el manifiesto, `review.json` o una fuente obligatoria de evaluación de seguimiento.
- [x] Añadir a ambos comandos un grupo requerido y excluyente para `--input` o `--run-dir`. Mantener el par de divulgación manual en `--input` y rechazar sus flags con `--run-dir`. Probar las combinaciones inválidas y la ruta de `--input` sin sidecar para esquemas 12/13 con checks.
- [x] Incorporar un resolver privado que llame una vez a `read_compact` por operación y entregue registro, contexto de divulgación y fuentes. Conservar íntegra la validación del lector, incluidas las fuentes de evaluación y seguimiento retenidas. Resolver la referencia leyendo `evidence/context.json` de la selección validada. Si se declaró, pasar el sidecar y el mismo inventario de evidencia verificada que usó el lector. Las fuentes auxiliares pueden afectar el saneamiento aunque el sidecar no las referencie directamente. Si la referencia está ausente o es nula, bloquear un sidecar canónico huérfano, usar la construcción explicativa si hay checks o la vista vacía en caso contrario. Propagar las excepciones de lectura y validación al manejo de errores de entrada existente, sin intentar el fallback.
- [x] Conectar el resolver antes de preparar y antes de verificar. Usar el mismo verificador de cuerpo y limitar el modo de archivo al borrador 4 con un diagnóstico que dirija los borradores 2/3 a `--input`. Mantener la validación de sesión y la escritura exclusiva en preparación. Usar una fixture con contextos editoriales para comprobar que el modo nuevo los aplica.
- [x] Probar la verificación con un borrador de otro compacto, la vista de divulgación cambiada y un cuerpo cambiado con su hash recalculado. Probar la igualdad exacta local, CRLF con `--remote` y la omisión de un único LF final con `--remote --remote-transport gitlab` en borrador 4. Comprobar el rechazo si se omite el LF sin seleccionar GitLab, si se pierde otro carácter o si se usa `--remote-transport` sin `--remote`. Capturar inventario y bytes del compacto antes y después de ambas operaciones y probar que una salida existente o una sesión no válida no se sobrescriben. Ejecutar la suite de la tarea hasta que pase.

## Tarea 3. Documentar el flujo y validar compatibilidad

**Archivos.** `references/reporting/publication.md`, `references/archive/artifacts.md` y, si remite a la secuencia anterior, la sección correspondiente de `SKILL.md`.

- [x] Documentar `python scripts comment prepare --run-dir <compacto> --session <sesión-de-publicación> --output <borrador>` y `python scripts comment verify --run-dir <compacto> --draft <borrador> --body <cuerpo>`. Incluir los contextos editoriales aplicables y un ejemplo para una nota observada en GitLab con `--remote --remote-transport gitlab`. Indicar que la CLI elige el fallback tras validar el archivo y que un sidecar declarado inválido detiene el flujo. Mantener la ruta de catálogo explícito para registros sueltos y explicar la separación de sesiones.
- [x] Verificar en modo archivo un compacto con checks sin sidecar producido por el escritor de CCR 3.6.0. Conservar su inventario y bytes completos durante el ciclo de preparación y verificación con el código actualizado. Usar un compacto sintético con rutas generadas por el escritor histórico para respetar el vínculo de propiedad.
- [x] Ejecutar las regresiones focalizadas, después la suite completa y la validación de cambios. Confirmar borradores 2/3 por `--input`, borrador 4 por ambas rutas cuando la divulgación coincide, render directo, y entregas con y sin sidecar.

  ```powershell
  python -B -X utf8 -m unittest discover -s tests -p 'test_review_publication_legacy.py'
  python -B -X utf8 -m unittest discover -s tests -p 'test_review_comment*.py'
  python -B -X utf8 -m unittest discover -s tests -p 'test_review_disclosure_integration.py'
  python -B -X utf8 -m unittest discover -s tests -p 'test_review_compact*.py'
  python -B -X utf8 -m unittest discover -s tests -p 'test_review_assessment_followup_pr37.py'
  python -B -X utf8 -m unittest discover -s tests
  git diff --check
  ```

- [x] Comparar los resultados contra los cuatro criterios del spec. Registrar los comandos y sus resultados, revisar que los cambios de código se limiten a compartir el fallback y resolver la fuente de comentarios, y comprobar que la documentación del harness cubre el caso sin sesión de captura.

## Validación de la implementación

- Pasaron 74 pruebas focalizadas de comentarios, divulgación, entrega y evaluación de seguimiento. También pasaron las cuatro pruebas de caracterización de la CLI y la prueba de referencias Markdown.
- La CLI actual preparó y verificó un borrador 4 a partir de un compacto sintético creado con el escritor de CCR 3.6.0. Se comprobó la igualdad del inventario y de los bytes retenidos antes y después.
- Las pruebas de errores cubren un sidecar malformado con una fila nula. El lector del compacto devuelve un error estructurado y bloquea el comentario.
- La suite completa descubrió 1529 pruebas y ejecutó las 1529 en ocho procesos aislados. Pasaron 1526 y se omitieron tres por permisos de creación de symlinks en Windows. La repetición usó temporales separados y excluyó de los procesos de prueba los overrides de Git inyectados por el harness.
- Tras F001 del PR #38, el caso de regresión confirmó que ambos comandos rechazaban un sidecar válido cuyo saneamiento dependía de una fuente auxiliar. Con el inventario verificado completo, ambos pasaron y el valor sensible quedó fuera del comentario. Pasaron 80 pruebas focalizadas, incluido ese caso.
