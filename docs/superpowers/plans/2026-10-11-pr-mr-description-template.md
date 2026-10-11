# PR/MR Description Template Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Estandarizar las descripciones de contribuciones al repositorio sin cambiar CCR ni crear una release de la skill.

**Architecture:** Una plantilla GitHub canónica y una copia GitLab idéntica usan tres secciones obligatorias y dos opcionales. Una guía breve explica el contenido y su uso explícito por CLI/API; README solo enlaza esa guía.

**Tech Stack:** Markdown, Git; sin scripts, dependencias o pipeline nuevos.

**Spec:** [2026-10-11-pr-mr-description-template-design.md](../specs/2026-10-11-pr-mr-description-template-design.md).

## Global Constraints

- Alcance: únicamente `omarfrancodev/comprehensive-code-review`; no un criterio nuevo de review para otros proyectos.
- Idioma de la plantilla y guía: español.
- Tres secciones obligatorias en orden: `## Resumen`, `## Cambios`, `## Validación`.
- `## Compatibilidad e integración` y `## Referencias` son opcionales y se eliminan cuando no aporten información.
- `.github/PULL_REQUEST_TEMPLATE.md` es la fuente canónica; `.gitlab/merge_request_templates/Default.md` contiene el mismo cuerpo.
- Sin cambios a scripts, schemas, perfiles, archivos históricos, configuración remota o comentarios existentes.
- Este cambio documental/de contribución no requiere una versión/release nueva de la skill.
- CLI/API/agentes leen la plantilla y preparan un cuerpo explícito; no asumir relleno automático ni añadir enforcement/configuración de harness.

## Review Focus

1. PR pequeño de documentación: las secciones no obligan a inventar prueba de comportamiento o compatibilidad.
2. PR que altera schemas: la sección opcional sí informa consumidores y condiciones pendientes, sin presumir compatibilidad externa.
3. PR creado por API/CLI: cuerpo final proporcionado explícitamente; no confiar en que la plataforma aplica el archivo.
4. GitLab con defaults configurados: su configuración puede prevalecer; documentar límite sin cambiar settings ni crear un mirror.
5. Evolución de la plantilla: comparar copias y enlaces al modificarlas; no acumular tres fuentes del cuerpo o múltiples variantes.

## Preparación observada

- [x] Usuario confirmó «Plantilla para este repositorio».
- [x] Crear `docs/pr-mr-description-template` desde origin/main `d54be59`, en `.worktrees/pr-mr-description-template`, ignorado por Git.
- [x] Verificar base: 34 pruebas focalizadas aprobadas; repetición fuera del sandbox tras dos errores de permisos TEMP.
- [x] Redactar spec y plan; plantilla activa todavía pendiente.
- [x] Usuario autorizó implementar spec/plan y abrir PR el 2026-10-11; ejecución nativa.

### Task 1: Plantillas equivalentes

**Files:**
- Create: `.github/PULL_REQUEST_TEMPLATE.md`.
- Create: `.gitlab/merge_request_templates/Default.md`.

**Interfaces:**
- Consumes: bloque «Plantilla propuesta» de la spec.
- Produces: archivos UTF-8 con el mismo cuerpo, apto para formularios web y preparación explícita de descripciones.

- [x] **Step 1: Actualizar esta rama desde main vigente.** Fetch/merge de origin/main; main sigue en d54be59, sin conflictos.
- [x] **Step 2: Crear ambas plantillas con el bloque exacto de la spec.** Sin resultados precargados, checklists de aprobación, variables/quick actions, referencias ficticias ni secciones adicionales.
- [x] **Step 3: Comprobar identidad de archivos y formato.** Copias idénticas y cuerpo igual al aprobado; enlaces y diff check válidos. Rutas/nombres respaldados por las fuentes oficiales de la spec. Sin tests permanentes de texto ni suite de producto nueva.
- [x] **Step 4: Commit.** Plantillas guardadas en 4ee590a, con stage de rutas explícitas.

### Task 2: Guía y presentación del propio PR

**Files:**
- Create: `CONTRIBUTING.md`.
- Modify: `README.md` (enlace de contribución).

**Interfaces:**
- Consumes: plantillas de Task 1 y reglas de título/contenido de la spec.
- Produces: guía breve accesible desde README, sin duplicar el cuerpo de la plantilla ni las instrucciones de CCR.

- [x] **Step 1: Escribir CONTRIBUTING.** Guía breve con secciones, título, validación factual y links a las dos plantillas.
- [x] **Step 2: Documentar CLI/API y límites.** Cuerpo explícito UTF-8/--body-file y comprobación remota; prioridad de configuraciones GitLab y consumo desde default branch; sin enforcement/configuración de agente.
- [x] **Step 3: Añadir enlace breve desde README.** Sin cambios a SKILL.md, docs/usage.md o changelog.
- [x] **Step 4: Revisión manual de dos muestras efímeras.** Cuerpo del propio PR documental y muestra hipotética de contrato en scratch: secciones útiles, ninguna evidencia inventada ni datos privados. No PRs de prueba ni nuevas muestras permanentes.
- [x] **Step 5: Verificar enlaces y diff completo; commit.** Enlaces, igualdad de plantillas, cuerpo aprobado y diff válidos. Guía y README guardados en 6c89166; cambios limitados a los archivos previstos.
- [x] **Step 6: Publicar rama y crear/adjuntar PR con el formato propuesto.** [PR #15](https://github.com/omarfrancodev/comprehensive-code-review/pull/15) creado y adjuntado; base main y cuerpo remoto verificados. Pendiente de validación humana antes de merge; sin tag/release. Worktree conservado hasta integración autorizada.

## Execution ledger

Usuario autorizó implementación y PR el 2026-10-11. Base main d54be59; Task 1 completada en 4ee590a y Task 2 en 6c89166. Plantillas idénticas y fieles a spec, enlaces/diff válidos y dos escenarios documentales revisados. Revisión independiente del rango d54be59..6c89166 sin hallazgos accionables. PR #15 publicado con descripción explícita y verificado en GitHub; validación humana e integración pendientes. No cambios de versión ni modificaciones a PR #14 desde esta rama.

- Ruling: No probar integración real con GitLab — ninguna instancia forma parte del alcance y la precedencia está documentada — si difiere la configuración, habrá que verificarla en la instancia correspondiente.
- Ruling: Activación web pendiente de merge a la rama predeterminada — no afirmar que ya está activa — cualquier discrepancia de plataforma se comprobará después de integrar.
- Ruling: No repetir la suite de producto para Markdown de contribución — plan y alcance aprobados requieren comprobaciones documentales — cambios posteriores de comportamiento requerirían pruebas de producto.
- Ruling: La publicación era una entrega pendiente, no un defecto del contenido — PR creado y cuerpo remoto verificado — la integración conserva su validación humana.

El scratch de ejecución de este plan se elimina tras registrar aquí los resultados; el worktree y los archivos publicados permanecen disponibles para la revisión del PR.
