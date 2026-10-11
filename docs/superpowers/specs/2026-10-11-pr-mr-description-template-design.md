# Plantilla de descripciones de PR/MR del repositorio

Fecha: 2026-10-11. Estado: aprobada para implementación; plantillas implementadas, pendientes de integrar en main mediante PR.

## Objetivo y alcance

Estandarizar las descripciones de contribuciones a `omarfrancodev/comprehensive-code-review` para que expliquen el problema, el comportamiento final y su validación de forma breve y comparable. El usuario confirmó «Plantilla para este repositorio»; no se introduce un formato obligatorio para proyectos revisados mediante CCR ni un criterio nuevo de hallazgo/veredicto.

Preparación: rama `docs/pr-mr-description-template`, worktree `.worktrees/pr-mr-description-template`, desde `origin/main` en `d54be59e2d09117d59c5a8664fcb1a68d6649bb5`. Independiente de PR #14 y de `feat/review-execution-policy`. La preparación solo añade esta spec y su plan; implementación y PR se realizan tras revisar la propuesta escrita.

## Diseño elegido y alternativas

**Elegido:** una estructura común, plantilla nativa por plataforma y guía corta de contribución. `.github/PULL_REQUEST_TEMPLATE.md` es la fuente canónica; `.gitlab/merge_request_templates/Default.md` contiene el mismo cuerpo, sin variables o acciones específicas de plataforma. Comparar ambas al modificarlas, sin añadir un generador o pipeline para dos archivos pequeños.

Solo una guía documental no rellena los formularios de las plataformas. Usar exclusivamente una plantilla GitHub cubre el alojamiento actual pero no ofrece el equivalente MR solicitado. Variantes por tipo de cambio y checklists extensos multiplican mantenimiento y generan campos sin información útil; no se adoptan.

Los archivos de plantilla deben estar en la rama predeterminada para el consumo nativo. GitLab permite `Default.md`, con prioridad de otras configuraciones del proyecto/grupo sobre el archivo. El repositorio actual está en GitHub: añadir el archivo GitLab no crea un mirror ni demuestra su configuración en una instancia concreta. [GitHub templates](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/creating-a-pull-request-template-for-your-repository), [GitLab templates](https://docs.gitlab.com/user/project/description_templates/).

## Contrato de presentación

- Idioma de la plantilla y guía: español.
- Título: `tipo(scope): resultado concreto` cuando existe un scope útil; en otro caso `tipo: resultado concreto`. Describir el cambio final; no repetir el título como encabezado del cuerpo. No inventar ticket/versión ni imponerlos a todas las contribuciones.
- Tres secciones obligatorias en orden: `## Resumen`, `## Cambios`, `## Validación`.
- Después, `## Compatibilidad e integración` y `## Referencias`, únicamente cuando aportan información. El autor elimina encabezado/comentario de las secciones opcionales que no apliquen.
- Markdown portable: H2 para secciones, párrafos y listas con separación en blanco. Sin iconos de prioridad, etiquetas F/C, HTML, puntuaciones de riesgo o matriz ABCDE; esos elementos pertenecen a la revisión de código.
- Escalar detalle a complejidad: un cambio pequeño puede usar un párrafo de resumen, un cambio y una comprobación. No exigir un número fijo de palabras o de bullets.

## Plantilla propuesta

El contenido entre comentarios HTML guía al autor y se sustituye o elimina al preparar el cuerpo. No hay resultados precargados, casillas de aprobación ni evidencias ficticias.

```markdown
## Resumen

<!-- Explica el problema y el resultado del cambio en uno o dos párrafos breves. Usa antes/después cuando ayude. -->

## Cambios

<!-- Enumera solo cambios relevantes para valorar el diff; evita narrar commits, iteraciones o conversaciones. -->

## Validación

<!-- Indica comprobaciones realizadas y resultados observados. Declara omisiones, fallos o bloqueos con su alcance. Si no ejecutaste pruebas, explica qué se verificó y por qué. -->

## Compatibilidad e integración

<!-- Opcional: contratos/schemas afectados, consumidores, migración o condiciones pendientes de integración/publicación. Elimina la sección si no aplica. -->

## Referencias

<!-- Opcional: issue, spec/plan, registro de validación o revisión verificable. Usa referencias accesibles a los revisores y elimina la sección si no aplica. -->
```

## Reglas de contenido

1. **Resumen:** por qué hace falta y qué comportamiento queda. No explicar el historial de conversación, enfoques abandonados ni nombres de workers.
2. **Cambios:** componentes o decisiones que ayudan al reviewer; no duplicar todo el diff o listar todos los archivos por rutina.
3. **Validación:** comando/comprobación y resultado útil, con la revisión real cuando sea relevante. Una suite focalizada no se declara como suite completa. Incluir omisiones/fallos conocidos; un check no ejecutado no se presenta como aprobado. La documentación puede validarse por enlaces, coherencia y Markdown sin inventar pruebas de comportamiento.
4. **Compatibilidad e integración:** informar cambios de contrato, datos/schema, consumidores o pasos necesarios cuando existan. Distinguir publicación pendiente de release/tag existentes. No asegurar compatibilidad de otro proyecto sin evidencia ni convertir cada PR de documentación en una release.
5. **Referencias:** incluir solo fuentes existentes que ayuden al reviewer. Enlaces a spec/plan y validación cuando correspondan; no copiar su contenido. No exponer rutas absolutas locales, credenciales, logs privados o artifacts de otros proyectos.
6. **Formato común, sin automatización implícita:** una plantilla guía; no verifica la verdad, autoriza merge/release ni sustituye la revisión humana. Sin nuevo CI, validador semántico o cambios de permisos.

## Uso desde web, CLI y agentes

`CONTRIBUTING.md` explica la estructura, secciones opcionales y fuente canónica. Incluir un enlace breve desde README, sin aumentar la guía de uso de CCR ni modificar SKILL.md.

Al crear el PR/MR desde CLI/API/agente, leer la plantilla local y preparar el cuerpo explícitamente: no asumir que una API lo rellena. Para `gh`, usar un archivo UTF-8 con el contenido final y `--body-file`; no enviar los comentarios guía como descripción vacía. Revisar el cuerpo remoto tras crearlo. La guía es una norma de contribución; no instalar configuraciones de agente ni prometer enforcement automático.

La incorporación de estas plantillas no actualiza PRs abiertos. El nuevo PR de esta rama puede utilizar el formato antes de integrarse; no reescribir PR #14 ni la otra rama como efecto secundario.

## Verificación y aceptación

- Plantillas GitHub/GitLab no vacías, mismo contenido y nombres/rutas correctos.
- Una única guía breve explica sección obligatoria/opcional, título y flujo CLI/API.
- README enlaza a la guía; enlaces locales válidos y `git diff --check` limpio.
- Revisión manual de una descripción pequeña de documentación y una de contrato/schema confirma que no obliga a inventar tests, riesgos, tickets o releases. Estas muestras no se publican como PRs de prueba.
- Sin modificaciones a scripts, schemas, perfiles, archivos históricos, configuración remota o comentarios existentes.
- Este cambio documental/de contribución no requiere una versión/release nueva de la skill; se integra mediante PR con el gate humano habitual.

## Evidencia base y estado

Sin plantillas de PR/MR ni guía CONTRIBUTING en main observado. Suite focalizada `test_review_contract.py`: 34 pruebas aprobadas, 0.313 s; el primer intento presentó dos errores de permisos en TEMP dentro del sandbox y la repetición permitida pasó. No se repitió la suite completa por preparar documentos sin cambiar código.

Spec revisada por alcance, alternativas, formato, portabilidad y mantenimiento. El usuario autorizó su implementación el 2026-10-11. Las plantillas se consumen desde main después de aprobar e integrar el PR.
