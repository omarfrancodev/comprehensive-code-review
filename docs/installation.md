# Instalación y actualización

## Instalación con npx

Instala desde GitHub sin clonar manualmente el repositorio:

```bash
npx skills add omarfrancodev/comprehensive-code-review
```

El instalador permite seleccionar agente y método. Por defecto, la instalación pertenece al proyecto actual. Añade `-g` para instalar a nivel de usuario; `-a` selecciona agentes:

```bash
# Codex, instalación global
npx skills add omarfrancodev/comprehensive-code-review -g -a codex

# Claude Code, instalación global
npx skills add omarfrancodev/comprehensive-code-review -g -a claude-code

# Copia en un proyecto, sin enlaces simbólicos ni preguntas
npx skills add omarfrancodev/comprehensive-code-review -a codex --copy -y
```

`npx` requiere Node.js/npm. La versión comprobada del instalador, `skills` 1.7.0, requiere Node.js 22.20 o posterior. Para reproducir esa versión, sustituye `npx skills` por `npx skills@1.7.0`. El instalador puede utilizar Git internamente al obtener un repositorio. No se necesita publicar ni instalar un paquete npm propio de esta skill.

Consulta las [opciones del instalador](https://github.com/vercel-labs/skills#options) y sus [agentes compatibles](https://github.com/vercel-labs/skills#supported-agents). La disponibilidad de agentes, permisos y herramientas determina qué operaciones puede realizar cada entorno. La instalación no añade conectores, credenciales ni capacidad de delegación.

Los argumentos de estos comandos pertenecen al instalador. Las convenciones `--profile`, `--delivery` y `--output` de las [peticiones de revisión](usage.md#peticiones-de-revisión) las interpreta el agente; no se añaden a `npx skills add`.

## Descarga de una versión

Descarga `comprehensive-code-review-v2.8.0.zip` desde [la release 2.8.0](https://github.com/omarfrancodev/comprehensive-code-review/releases/tag/v2.8.0), o consulta [todas las releases](https://github.com/omarfrancodev/comprehensive-code-review/releases). El [CHANGELOG](../CHANGELOG.md) puede describir trabajo pendiente de publicación; comprueba la release antes de elegir un ZIP.

El ZIP contiene la carpeta `comprehensive-code-review/`, con `SKILL.md`, referencias, scripts, documentación y pruebas. Puedes extraerla en el directorio de skills del agente sin usar Git ni Node.js. Para Codex, una ubicación a nivel de usuario es `~/.codex/skills/comprehensive-code-review/`; para Claude Code, `~/.claude/skills/comprehensive-code-review/`. Sigue las reglas de carga de tu agente y comprueba que la carpeta final contiene directamente `SKILL.md`.

La release incluye `SHA256SUMS.txt` para comprobar el archivo descargado. Extrae o instala en una ubicación nueva si ya mantienes allí una copia editable; conserva tus cambios antes de reemplazarla. No mezcles una instalación gestionada por `skills` con una extracción manual sobre la misma carpeta.

## Actualizar o desinstalar

Para instalaciones gestionadas por el CLI:

```bash
npx skills@latest update comprehensive-code-review -p
npx skills@latest update comprehensive-code-review -g
npx skills remove comprehensive-code-review
```

Usa `-p` desde el proyecto para actualizar su instalación, o `-g` para la global. Añade `-g` a `remove` para desinstalar globalmente. Las actualizaciones son explícitas: publicar una release no reemplaza automáticamente una instalación.

`@latest` selecciona la versión actual del instalador. La ayuda comprobada de `skills@1.7.0` admite estos comandos y coincide con las [opciones documentadas](https://github.com/vercel-labs/skills#skills-update). Conserva cualquier personalización antes de actualizar; no ejecutes el instalador sobre un checkout de desarrollo editable. Para una instalación manual, descarga la release elegida y reemplaza solo la carpeta instalada.

### Refrescar instalaciones con --copy

Puedes refrescar explícitamente las copias de los agentes repitiendo la instalación con el mismo alcance:

```bash
# Desde el proyecto; añade -g si tu instalación es global
npx skills@latest add omarfrancodev/comprehensive-code-review -a codex claude-code --copy
```

En la comprobación con `skills` 1.7.0 y Node.js 24.15.0 en Windows, `update -p` terminó con un error al cerrar y una copia conservó 2.1.1. Repetir `add` con ambos agentes y `--copy` terminó correctamente y actualizó las dos a 2.2.0. Es un resultado de ese entorno, no una garantía para otras versiones del instalador.

Esta alternativa reemplaza los archivos instalados: conserva tus personalizaciones y selecciona únicamente los agentes que uses. El comando obtiene la fuente del repositorio; comprueba la versión resultante en `SKILL.md`.

## Requisitos de ejecución

La lectura de las instrucciones no requiere helpers. Estos usan Python 3.10+ y su biblioteca estándar; el helper de workspaces y las pruebas de integración necesitan Git. Para MR/PR, el agente necesita acceso a los metadatos mediante un conector o CLI autenticado, además del código.

La preparación, retención y cierre del archivo interno usan su helper cuando puede ejecutarse dentro de los permisos disponibles; una alternativa nativa por indisponibilidad debe comprobar el mismo contrato. Las limitaciones de escritura, aislamiento o herramientas se declaran en el resultado. Consulta [uso y helpers](usage.md#helpers-y-validación), [capacidades](../references/workflow/capabilities.md) y [artefactos](../references/archive/artifacts.md).
