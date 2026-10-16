# Contribuir al repositorio

Las descripciones de PR/MR de este repositorio siguen la [plantilla de GitHub](.github/PULL_REQUEST_TEMPLATE.md). La [plantilla de GitLab](.gitlab/merge_request_templates/Default.md) contiene el mismo cuerpo. Al cambiar el formato, actualiza ambas y comprueba que sean idénticas.

## Título y descripción

Usa `tipo(scope): resultado concreto`, o `tipo: resultado concreto` cuando no haya un scope útil. Describe el cambio final en español; no inventes tickets o versiones ni repitas el título dentro del cuerpo.

Completa estas secciones en orden:

| Sección | Contenido |
|---|---|
| Resumen | Problema y resultado. Usa antes/después cuando ayude a entender el comportamiento. |
| Cambios | Cambios relevantes para evaluar el diff, sin narrar commits o conversaciones. |
| Validación | Comprobaciones realizadas, resultados observados y omisiones, fallos o bloqueos conocidos. |

Añade **Compatibilidad e integración** cuando haya contratos, schemas, consumidores, migraciones o pasos pendientes que deban conocer los revisores. Añade **Referencias** para issues, spec/plan o registros de validación existentes y accesibles. Elimina las secciones opcionales que no apliquen y sustituye o elimina los comentarios guía antes de enviar.

Adapta el detalle al cambio. Un ajuste documental puede describirse brevemente y validarse mediante enlaces y coherencia; no necesita resultados de pruebas de comportamiento inventados. Identifica el alcance real de las pruebas: una ejecución focalizada no equivale a la suite completa. Si no ejecutaste pruebas, explica qué verificaste y por qué. No declares una release pendiente como publicada ni compatibilidad externa como verificada sin evidencia.

Mantén la descripción centrada en el cambio: evita rutas absolutas locales, credenciales, logs privados, artifacts de otros proyectos y detalles internos del agente. Las referencias deben ayudar al reviewer sin duplicar el contenido enlazado.

## Changelog

Organiza [CHANGELOG.md](CHANGELOG.md) por **release → categoría → scope funcional**: encabezado H2 para la versión, H3 para la categoría, H4 para el scope y una lista de cambios debajo. Conserva las versiones en orden descendente. Una versión pendiente usa `unreleased`; al publicarla, registra la fecha verificada de GitHub en `America/Mexico_City`. Mantén «Sin publicación registrada» cuando no exista una release histórica; no deduzcas su fecha del commit.

Usa estas categorías, en este orden, omitiendo las que estén vacías:

| Categoría | Uso |
|---|---|
| Added | Capacidades nuevas, incluidas herramientas, contratos y documentación. |
| Changed | Cambios deliberados del comportamiento o de las reglas existentes. |
| Fixed | Correcciones de comportamientos que funcionaban incorrectamente. |
| Deprecated | Funcionalidades que siguen disponibles pero cuyo uso se desaconseja ante una retirada prevista. |
| Removed | Funcionalidades eliminadas. |
| Security | Cambios que corrigen vulnerabilidades o refuerzan específicamente la seguridad; evita repetirlos en Fixed o Changed. |

Dentro de cada categoría, usa estos scopes en el orden indicado, omitiendo los vacíos:

| Scope | Contenido |
|---|---|
| Perfiles y ejecución | Selección de perfiles, revisores, delegación y verificación. |
| Ciclo de vida y recuperación | Preparación, continuación, reinicios, transferencias y recuperación de interrupciones. |
| Artefactos y contratos | Persistencia, schemas, trazabilidad, integridad y compatibilidad histórica. |
| Workspaces y recursos | Worktrees, ownership, dependencias, bloqueos y limpieza. |
| Reportes y entregas | Informe, comentario público, Markdown y entregas completas o breves. |
| Harness e integraciones | Identidad del entorno, catálogo y adaptación a sus capacidades. |
| Distribución y documentación | Instalación, actualización, empaquetado, README y guías. |

Los scopes describen áreas funcionales estables y no tienen que coincidir con el scope del commit. No crees uno por cada PR o archivo. Cada cambio aparece una sola vez, en su categoría y scope principal; separa entradas que mezclen resultados independientes. Describe el resultado final y consolida correcciones sucesivas del mismo comportamiento en la versión pendiente, conservando límites y compatibilidad relevantes. Menciona pruebas cuando aporten evidencia concreta al cambio, sin entradas genéricas de pruebas.

Al reorganizar versiones publicadas, conserva el significado, las fechas, los nombres históricos y los contratos de esa versión; no les atribuyas capacidades posteriores. La estructura también se aplica a las notas de futuras releases. Una reorganización del changelog no cambia por sí misma las notas ya publicadas en GitHub ni requiere una nueva versión de la skill.

## Web, CLI y API

Las plataformas consumen las plantillas del repositorio desde su rama predeterminada. GitLab puede priorizar una configuración de proyecto o grupo sobre `Default.md`; incluir la plantilla no configura una instancia ni crea un mirror. Consulta la documentación de [GitHub](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/creating-a-pull-request-template-for-your-repository) y [GitLab](https://docs.gitlab.com/user/project/description_templates/).

Si creas un PR/MR mediante CLI, API o un agente, lee la plantilla local y proporciona explícitamente el cuerpo final. No supongas que el cliente rellena la descripción. Para `gh`, guarda el contenido en un archivo UTF-8 y pásalo con `--body-file`; comprueba la descripción remota después de crear el PR. La plantilla sin completar no constituye una descripción.

La estructura guía la contribución; no valida sus afirmaciones ni autoriza publicación, aprobación o merge. Respeta la autorización del flujo correspondiente. Estas normas se aplican a contribuciones a este repositorio y no imponen un formato a los proyectos revisados por CCR. Los cambios exclusivamente de contribución no requieren una release de la skill.
