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
- [ ] Revisar documentos con el usuario antes de implementar; ejecución nativa sugerida por tratarse de archivos documentales pequeños y dependientes.

### Task 1: Plantillas equivalentes

**Files:**
- Create: `.github/PULL_REQUEST_TEMPLATE.md`.
- Create: `.gitlab/merge_request_templates/Default.md`.

**Interfaces:**
- Consumes: bloque «Plantilla propuesta» de la spec.
- Produces: archivos UTF-8 con el mismo cuerpo, apto para formularios web y preparación explícita de descripciones.

- [ ] **Step 1: Actualizar esta rama desde main vigente.** Fetch/merge de origin/main en este worktree; no incorporar ramas pendientes ni alterar sus PRs. Revisar conflictos si afectan README/contribución. Detenerse ante una decisión no cubierta.
- [ ] **Step 2: Crear ambas plantillas con el bloque exacto de la spec.** Sin resultados precargados, checklists de aprobación, variables/quick actions, referencias ficticias ni secciones adicionales.
- [ ] **Step 3: Comprobar identidad de archivos y formato.** Comparar bytes de ambas plantillas y revisar separación Markdown; `git diff --check` debe pasar. Verificar rutas/nombres contra las fuentes oficiales enlazadas en la spec. No añadir tests que busquen frases ni una suite de producto para esta documentación.
- [ ] **Step 4: Commit.** Stage explícito de ambas rutas y commit `docs(contrib): añadir plantilla común de PR y MR`.

### Task 2: Guía y presentación del propio PR

**Files:**
- Create: `CONTRIBUTING.md`.
- Modify: `README.md` (enlace de contribución).

**Interfaces:**
- Consumes: plantillas de Task 1 y reglas de título/contenido de la spec.
- Produces: guía breve accesible desde README, sin duplicar el cuerpo de la plantilla ni las instrucciones de CCR.

- [ ] **Step 1: Escribir CONTRIBUTING.** Explicar título orientado al cambio final, tres secciones obligatorias, opcionales, validación factual, compatibilidad relevante y fuente canónica/copia sincronizada. Enlazar ambas plantillas usando rutas relativas.
- [ ] **Step 2: Documentar CLI/API y límites.** El cuerpo se prepara explícitamente con archivo UTF-8/`--body-file` cuando se usa gh; publicar/mergear requieren autorización del flujo. Native templates se consumen desde default branch y pueden tener precedencia externa en GitLab. No prometer prueba web en una instancia no disponible ni enforcement de agentes.
- [ ] **Step 3: Añadir enlace breve desde README.** Mantener la explicación extensa en CONTRIBUTING; no cambiar SKILL.md, docs/usage.md ni changelog de versiones.
- [ ] **Step 4: Revisión manual de dos muestras efímeras.** Probar formato para cambio documental pequeño y para contrato/schema; confirmar información útil, supresión de secciones vacías y ausencia de detalles privados/resultado inventado. No crear PRs de prueba, tests de texto o muestras permanentes redundantes.
- [ ] **Step 5: Verificar enlaces y diff completo; commit.** Comprobar enlaces relativos de los nuevos archivos y README, igualdad de plantillas y `git diff --check`; comprobar que los únicos cambios son los previstos. Commit `docs(contrib): explicar descripciones y uso de plantillas`.
- [ ] **Step 6: Publicar rama y crear/adjuntar PR con el formato propuesto.** Describir resultado, validación documental y alcance; título convencional en español. No reclamar suite completa nueva ni modificar PRs existentes. Esperar validación humana antes de merge; sin tag/release. Limpiar este worktree únicamente después de la integración autorizada.

## Execution ledger

Preparación: rama separada de main, base y portabilidad consultadas; solo documentos de diseño/plan creados. Implementación pendiente de revisión. No cambios de versión ni necesidad de modificar PR #14.
