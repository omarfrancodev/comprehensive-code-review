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

Descarga `comprehensive-code-review-v2.4.1.zip` desde [la release 2.4.1](https://github.com/omarfrancodev/comprehensive-code-review/releases/tag/v2.4.1), o consulta [todas las releases](https://github.com/omarfrancodev/comprehensive-code-review/releases).

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
| economy, explícito o automático para alcance acotado demostrado | Un revisor, que puede ser el coordinador | Comprobación escéptica en la misma sesión |
| balanced, alternativa automática cuando economy no se justifica | Un revisor, que puede ser el coordinador | Verificador independiente para candidatos sustantivos o dudas materiales; se omite si no quedan y la cobertura es suficiente |
| deep | Dos revisores con flujos concretos; un tercero solo por necesidad distinta | Verificación independiente de candidatos e invariantes asignadas |

Desde 2.5.0, un perfil solicitado explícitamente se respeta y no escala sin autorización. Sin perfil, se decide con el contexto ya descubierto: deep por mecanismos materiales observables; economy para un alcance acotado con requisitos claros, consumidores identificados, sin incertidumbres materiales ni gates independientes; balanced cuando esa elegibilidad no está demostrada. No se añade otro agente de preevaluación. El modo automático puede escalar si aparecen hechos nuevos, sin repetir lo ya comprobado ni reducir el perfil para eludir verificación.

Deep concentra sus revisores en los flujos e invariantes que lo requieren; las partes ajenas conservan cobertura habitual por un responsable existente. Sus candidatos sustantivos y dudas materiales siguen requiriendo verificación independiente. El reporte conserva un solo perfil efectivo y el motivo de selección.

El número de líneas, una urgencia o un nombre de tecnología no determinan el perfil. Ningún perfil elimina worktrees para ejecuciones que escriben, cobertura, persistencia o validaciones obligatorias. Sin capacidad de delegación, se declara la alternativa en una sola sesión y cualquier limitación. Las áreas ABCDE no requieren cinco agentes.

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

El comentario público incluye responsable del MR/PR, autores del cambio, alcance, versión, consistencia de la descripción, hallazgos, validación e incertidumbres pertinentes. La asignación del MR y la autoría de los commits se declaran por separado; los nombres de Git no se convierten en menciones sin verificar la cuenta. Omite la matriz ABCDE y las rutas internas de ejecución. Solo se publica con autorización explícita.

Los veredictos son **Aprobable**, **Aprobable con reservas**, **No aprobable** o **Evidencia insuficiente**. La prioridad P0–P3, el carácter bloqueante y el origen del hallazgo se declaran por separado. En MR/PR también se verifica que la descripción refleje correctamente los cambios.

## Artefactos persistentes

Desde la versión 2.3.0, la skill conserva cada revisión en una carpeta por usuario, independiente de Codex/Kiro, de la instalación de la skill y de los worktrees temporales:

```text
<home>/.comprehensive-code-review/reviews/
  <proyecto>-<id-repositorio>/<alcance>/<fecha>-<id-ejecucion>/
    informe.md
    review.json
    cierre.json
```

Una ubicación solicitada explícitamente tiene prioridad; después se utiliza `CCR_ARTIFACTS_DIR`, y finalmente la ruta anterior. Cada entorno debe disponer de permisos para escribir en la ubicación elegida. Una ruta bloqueada se informa como limitación; no se cambia silenciosamente a `docs/` o al scratch del proveedor. Los nombres e identificadores distinguen repositorios, alcances y ejecuciones; una re-review crea otro registro enlazado al anterior.

`cierre.json` se inicia antes de ejecutar la revisión y conserva versión de la skill, alcance, recursos temporales registrados, hashes y estado observado de limpieza. Desde 2.4.0, el archivo predeterminado contiene esos tres documentos. Las mediciones son opcionales para evaluaciones de coste solicitadas: no se crea `measurements.json` ni se buscan contadores en revisiones normales. Los archivos anteriores conservan sus mediciones. No hay captura automática de tokens/créditos en Codex/Kiro.

El reporte, registro y evidencia necesaria se guardan y comprueban antes de limpiar los recursos temporales propios. El archivo persistente permanece; su eliminación es explícita. Las reproducciones conservadas son evidencia, no modificaciones al producto. El helper no borra worktrees ni reutiliza contexto de revisiones anteriores como caché. La ubicación real se entrega al usuario y se omite del comentario público. Consulta [artifacts.md](references/artifacts.md); para una evaluación explícita de coste, [measurements.md](references/measurements.md).

Desde 2.4.1, el helper de artifacts es obligatorio cuando puede ejecutarse dentro de los permisos disponibles. Se usa exactamente el `run_dir` devuelto: las rutas históricas no definen la convención. La evidencia temporal se crea en `evidence/` de una sesión propia registrada; `register` permite añadir sesiones antes de usarlas. Una alternativa nativa por indisponibilidad debe comprobar el mismo contrato. La closure schema 3 conserva las identidades necesarias para verificar el layout sin depender del checkout original; schemas 1/2 siguen compatibles sin migrar archivos.

`review_artifacts.py validate --run-dir <ruta>` comprueba propiedad, layout y hashes sin escribir; añade `--require-retained` antes de limpiar para exigir informe, registro final y scope coherentes. También se valida el layout al retener/cerrar. La evidencia necesaria se selecciona explícitamente con `--evidence-input`; `--context-input` conserva procedencia de ejecutores, no copia automáticamente los archivos. Un fallo conserva el run y temporales para recuperación, sin afirmar cierre correcto.

Después de observar la limpieza, `close --run-dir <ruta> --cleanup complete` registra el cierre sin crear otro temporal. Si quedan recursos, usa `--cleanup pending --residual <ruta-absoluta>` por cada residuo registrado. La entrada anterior mediante `--cleanup-file` sigue disponible para archivos existentes permitidos.

Los metadatos y campos de cada hallazgo usan listas Markdown para conservar su separación al renderizarse. El veredicto aparece como encabezado con su motivo en un párrafo independiente, y los valores visibles se traducen; los enums permanecen en el JSON.

## Ejecución y presentación desde 2.4.0

Builds, tests, instalaciones y reproducciones se ejecutan en worktrees propios del proyecto, preferentemente su ubicación establecida (`.worktrees`). Las lecturas estáticas pueden usar objetos Git. Si no se puede crear el worktree, se informa la validación bloqueada; una copia en scratch requiere autorización explícita. Las dependencias/cachés compartidas y junctions siguen permitidas si son compatibles; ante conflictos se usan dependencias, cachés y salidas propias del ejecutor afectado. La procedencia se conserva en el contexto/cierre existentes, sin otro agente de auditoría.

El registro final usa schema 4 y guarda una sola identidad de presentación: tipo y asunto funcional. Reporte y comentario comparten un título H2 (`Code Review`, `Re-review` o `Complement Code Review`), veredicto H3, prioridad/color/ID H3 y título del hallazgo H4; escenario e impacto van separados. Los metadatos siguen como lista. ABCDE permanece solo en el reporte del usuario; responsable y autores siguen separados. Los schemas anteriores y archivos de 2.3.0 continúan siendo compatibles.

## Requisitos y helpers

La lectura de instrucciones no requiere ejecutar los helpers. La preparación/retención/cierre de artifacts usa su helper cuando puede ejecutarse; los demás helpers siguen siendo opcionales. Según el alcance, el agente necesita acceso al código y, para MR/PR, a sus metadatos mediante un conector o CLI autenticado.

Los helpers usan Python 3.10+ y su biblioteca estándar:

- `scripts/review_contract.py`: valida registros, agrupa candidatos explícitos y genera reportes en español. Nuevos registros finales usan schema 4 con autores y presentación separados; schemas 1/2/3 siguen siendo compatibles como entradas.
- `scripts/review_packets.py`: valida candidatos compactos y decisiones incrementales; combina evidencia sin inventar prioridad, origen, corrección ni veredicto. El formato de los paquetes internos tiene su propia versión; el registro final añade autores y presentación en schema 4.
- `scripts/review_metrics.py`: registra contadores suministrados por fase y agrega uso sin duplicar caché/razonamiento. Los datos no disponibles permanecen desconocidos.
- `scripts/review_artifacts.py`: prepara, conserva y cierra archivos persistentes con identidad, hashes y estado observado; no elimina recursos. El uso del script es opcional; el contrato de conservación se aplica también con herramientas nativas.
- `scripts/review_workspace.py`: crea y limpia snapshots temporales con comprobaciones de propiedad; requiere Git.
- `scripts/review_runner.py`: ejecuta un adaptador CLI previamente configurado; no selecciona ni configura automáticamente un proveedor.

Ejecuta cada helper con `--help`. Las comprobaciones que escriban archivos usan espacios aislados. La evidencia estática concluyente puede demostrar un defecto; los checks omitidos, bloqueados o fallidos por el entorno se identifican sin presentarlos como pruebas aprobadas. Un validador de estructura no determina si un hallazgo es verdadero.

## Actualizar o desinstalar

Para instalaciones gestionadas por el CLI:

```bash
npx skills@latest update comprehensive-code-review -p
npx skills@latest update comprehensive-code-review -g
npx skills remove comprehensive-code-review
```

Usa `-p` desde el proyecto para actualizar su instalación, o `-g` para la global. Las actualizaciones son explícitas; publicar una release no reemplaza automáticamente una instalación. `@latest` selecciona la versión actual del instalador; la ayuda comprobada de `skills@1.7.0` admite estos comandos y coincide con las [opciones documentadas](https://github.com/vercel-labs/skills#skills-update). Añade `-g` a remove para desinstalar globalmente. Conserva cualquier personalización antes de actualizar; no ejecutes el instalador sobre un checkout de desarrollo editable. Para una instalación manual, descarga la release elegida y reemplaza solo la carpeta instalada. Consulta [CHANGELOG.md](CHANGELOG.md).

Si instalaste con `--copy`, puedes refrescar explícitamente las copias de los agentes repitiendo la instalación con el mismo alcance:

```bash
# Desde el proyecto; añade -g si tu instalación es global
npx skills@latest add omarfrancodev/comprehensive-code-review -a codex claude-code --copy
```

Con `skills` 1.7.0 y Node.js 24.15.0 en Windows, la prueba de `update -p` terminó con un error al cerrar y una copia conservó 2.1.1. Repetir `add` con ambos agentes y `--copy` terminó correctamente y actualizó las dos a 2.2.0. Esta alternativa reemplaza los archivos instalados; conserva tus personalizaciones y selecciona únicamente los agentes que uses. El comando obtiene la fuente del repositorio, sin esperar a una actualización automática por release.

## Validación y mantenimiento

Desde una copia del código fuente:

```bash
python -B -m unittest discover -s tests -v
```

Las pruebas cubren contratos, CLI, matriz ABCDE, compatibilidad, escenarios ejecutables y limpieza de workspaces en un repositorio temporal. Git es necesario para la prueba de integración; sin él se informa una omisión. Para evaluar precisión y coste del modelo, usa el protocolo de [evaluation.md](references/evaluation.md); las pruebas mecánicas no son un benchmark de tokens ni una garantía de integridad del producto.

La guía operativa comienza en [SKILL.md](SKILL.md). La última release publicada enlazada arriba es 2.4.1; esta rama prepara 2.5.0 con selección automática de perfiles y profundidad acotada por flujo. Conserva el layout y la retención verificada de artifacts de 2.4.1, worktrees del proyecto, mediciones optativas, presentación canónica, independencia, paquetes internos compactos y matriz ABCDE. No incorpora caché de proyectos ni modifica el esfuerzo del modelo. El runner captura uso normalizado cuando el adaptador lo suministra; en Codex/Kiro los contadores dependen del entorno. No se ha medido un porcentaje de ahorro.
