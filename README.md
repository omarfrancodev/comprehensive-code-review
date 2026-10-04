# Comprehensive Code Review

Skill para revisar código, cambios locales, commits y MR/PR con hallazgos verificables, perfiles de revisión y una matriz de cobertura ABCDE.

Combina contexto compartido, verificación según el perfil y revisiones incrementales para evitar repetir análisis y comprobaciones. El ahorro real de tokens depende del modelo, el proyecto y el entorno; no se ha medido un porcentaje de ahorro.

## Instalación con npx

Instala desde GitHub sin clonar manualmente el repositorio:

```bash
npx skills add omarfrancodev/comprehensive-code-review
```

El instalador permite seleccionar el agente y el método de instalación. Por defecto, la instalación pertenece al proyecto actual; añade `-g` para instalar a nivel de usuario.

```bash
# Codex, instalación global
npx skills add omarfrancodev/comprehensive-code-review -g -a codex

# Claude Code, instalación global
npx skills add omarfrancodev/comprehensive-code-review -g -a claude-code

# Copia en un proyecto, sin enlaces simbólicos ni preguntas
npx skills add omarfrancodev/comprehensive-code-review -a codex --copy -y
```

`npx` requiere Node.js/npm; la versión comprobada del instalador, `skills` 1.7.0, requiere Node.js 22.20 o posterior. Para reproducir esa versión, sustituye `npx skills` por `npx skills@1.7.0`. El instalador puede utilizar Git internamente al obtener un repositorio. No se necesita publicar ni instalar un paquete npm propio de esta skill.

Consulta las [opciones del instalador](https://github.com/vercel-labs/skills#options) y sus [agentes compatibles](https://github.com/vercel-labs/skills#supported-agents). La disponibilidad de agentes, permisos y herramientas determina qué operaciones puede realizar cada entorno.

## Descarga directa de una versión

Descarga `comprehensive-code-review-v2.1.1.zip` desde [la release 2.1.1](https://github.com/omarfrancodev/comprehensive-code-review/releases/tag/v2.1.1), o consulta [todas las releases](https://github.com/omarfrancodev/comprehensive-code-review/releases).

El ZIP contiene la carpeta `comprehensive-code-review/`, con `SKILL.md`, referencias, scripts, documentación y pruebas. Puedes extraerla en el directorio de skills de tu agente sin usar Git ni Node.js. Para Codex, una ubicación de instalación a nivel de usuario es `~/.codex/skills/comprehensive-code-review/`; para Claude Code, `~/.claude/skills/comprehensive-code-review/`. Sigue las reglas de carga de tu agente y comprueba que la carpeta final contiene directamente `SKILL.md`.

La release incluye `SHA256SUMS.txt` para comprobar el archivo descargado. Extrae o instala en una ubicación nueva si ya mantienes allí una copia editable; conserva tus cambios antes de reemplazarla. No mezcles una instalación gestionada por `skills` con una extracción manual sobre la misma carpeta.

## Uso

Invoca la skill desde un agente que admita skills. Ejemplos:

```text
Usa comprehensive-code-review para revisar los cambios actuales con perfil balanced.
Reporta tus hallazgos sin modificar código ni publicar comentarios.
```

```text
En el proyecto core, revisa los MR 995 y 997 con comprehensive-code-review.
Comprueba la integridad de los cambios y reporta los hallazgos de cada MR.
```

```text
Usa comprehensive-code-review con perfil economy para volver a revisar este PR.
Conserva los IDs anteriores y comprueba las correcciones pendientes.
```

En entornos con invocación mediante `$`, también puedes usar `$comprehensive-code-review`. Indica el repositorio, alcance o referencia cuando no sean inequívocos. Revisar no autoriza modificar código, publicar comentarios, aprobar ni fusionar cambios.

## Perfiles

| Perfil | Descubrimiento | Verificación |
|---|---|---|
| economy | Un revisor, que puede ser el coordinador | Comprobación escéptica en la misma sesión |
| balanced, predeterminado | Un revisor, que puede ser el coordinador | Verificador independiente para candidatos sustantivos o dudas materiales; se omite si no quedan y la cobertura es suficiente |
| deep | Dos o tres revisores con flujos distintos | Verificación independiente de candidatos e invariantes asignadas |

Los mecanismos afectados pueden justificar deep; el número de líneas o una urgencia no lo determinan por sí solos. Sin capacidad de delegación, se declara la alternativa en una sola sesión y cualquier limitación. Las áreas ABCDE no requieren cinco agentes.

## Cobertura y resultados

El reporte al usuario incluye una matriz con estado, evidencia o motivo y referencias a los hallazgos:

| Área | Alcance |
|---|---|
| A | Arquitectura y diseño |
| B | Comportamiento y negocio |
| C | Contratos e integración |
| D | Datos y persistencia |
| E | Seguridad y operación |

Cada área queda como **Cubierta**, **Parcial**, **No evaluada** o **No aplica**. Cubierta significa inspeccionada; puede contener defectos. Un mismo hallazgo puede afectar varias áreas y conserva un solo bloque. No se añade una puntuación global ni un nivel de riesgo del cambio.

El comentario público incluye responsable, alcance, versión, consistencia de la descripción, hallazgos, validación e incertidumbres pertinentes. Omite la matriz ABCDE y las rutas internas de ejecución. Solo se publica con autorización explícita.

Los veredictos son **Aprobable**, **Aprobable con reservas**, **No aprobable** o **Evidencia insuficiente**. La prioridad P0–P3, el carácter bloqueante y el origen del hallazgo se declaran por separado. En MR/PR también se verifica que la descripción refleje correctamente los cambios.

## Requisitos y helpers

La lectura de instrucciones no requiere ejecutar los helpers. Según el alcance, el agente necesita acceso al código y, para MR/PR, a sus metadatos mediante un conector o CLI autenticado.

Los helpers usan Python 3.10+ y su biblioteca estándar:

- `scripts/review_contract.py`: valida registros, agrupa candidatos explícitos y genera reportes en español. Nuevos registros usan schema 2; schema 1 sigue siendo compatible.
- `scripts/review_workspace.py`: crea y limpia snapshots temporales con comprobaciones de propiedad; requiere Git.
- `scripts/review_runner.py`: ejecuta un adaptador CLI previamente configurado; no selecciona ni configura automáticamente un proveedor.

Ejecuta cada helper con `--help`. Las comprobaciones que escriban archivos usan espacios aislados. La evidencia estática concluyente puede demostrar un defecto; los checks omitidos, bloqueados o fallidos por el entorno se identifican sin presentarlos como pruebas aprobadas. Un validador de estructura no determina si un hallazgo es verdadero.

## Actualizar o desinstalar

Para instalaciones gestionadas por el CLI:

```bash
npx skills update comprehensive-code-review
npx skills remove comprehensive-code-review
```

Añade `-g` para operar sobre una instalación global. Para una instalación manual, descarga la release elegida y conserva cualquier personalización antes de reemplazar la carpeta; para desinstalarla, elimina únicamente la carpeta que instalaste. Las versiones y sus cambios están en [CHANGELOG.md](CHANGELOG.md).

## Validación y mantenimiento

Desde una copia del código fuente:

```bash
python -B -m unittest discover -s tests -v
```

Las pruebas cubren contratos, CLI, matriz ABCDE, compatibilidad, escenarios ejecutables y limpieza de workspaces en un repositorio temporal. Git es necesario para la prueba de integración; sin él se informa una omisión. Para evaluar precisión y coste del modelo, usa el protocolo de [evaluation.md](references/evaluation.md); las pruebas mecánicas no son un benchmark de tokens ni una garantía de integridad del producto.

La guía operativa comienza en [SKILL.md](SKILL.md). La publicación 2.1.1 añade documentación y empaquetado; mantiene el flujo de revisión de 2.1.0.
