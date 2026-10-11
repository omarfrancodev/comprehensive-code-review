# Identidad canónica del harness y etiquetas de reporte

## Objetivo y autorización

Conservar el nombre original del entorno y permitir agrupar nuevas revisiones por un identificador estable sin confundir familia con interfaz. Completar los tres ajustes locales del usuario sobre IDs en negrita en todas las proyecciones equivalentes. El usuario aprobó el diseño conversacional y solicitó expresamente worktree, spec, plan, implementación y PR en esta sesión; la revisión humana pendiente es la del PR.

## Alcance y componentes

- `references/archive/harness-catalog.json`: catálogo local versionado, datos del producto, sin detección del equipo. Cada entrada contiene ID, nombre, familia, interfaz y alias inequívocos. IDs publicados no se reutilizan; cambiar alias o entradas incrementa la versión del catálogo.
- `scripts/review_harness.py`: carga/valida el catálogo y resuelve una sola vez identidad y procedencia. Sin red, telemetría, inspección de procesos ni dependencias externas.
- `scripts/review_artifacts.py`: archive schema 6, CLI de preparación y validación estructural. Final review 7 y trace 1 permanecen sin cambios.
- Renderizadores de reporte y entrega: IDs visibles en negrita, manteniendo sus valores, referencias, anclas y jerarquía actuales.

## Resolución

Preservar `harness` literalmente. Agregar `harness_id` (ID conocido o null), `harness_catalog_version` (1 inicialmente), `harness_source` (`kind`, `reference`) y `harness_diagnostics` (lista de códigos). Los kinds son `argument`, `environment`, `user`, `platform`, `alias`, `unknown`.

Los IDs declarados ignoran mayúsculas y espacios exteriores al buscar el ID canónico; no aceptan aliases legibles como IDs ni ocultan IDs desconocidos mediante fallback al nombre. Prioridad: `--harness-id` explícito, después `CCR_HARNESS_ID` configurado para esa sesión, después coincidencia exacta de nombre/ID/alias ignorando mayúsculas y espacios exteriores. Un nombre genérico conserva la interfaz desconocida: `claude-code` no equivale a Desktop ni a CLI. Un ID específico puede precisar un nombre genérico de la misma familia. Un ID genérico no degrada un nombre específico conocido. Diferencias de familia o dos interfaces conocidas incompatibles producen null y `identity_conflict`; IDs solicitados desconocidos producen null y `unknown_requested_id`. Sin coincidencia, null y `unknown_harness`. No modificar el veredicto por incertidumbre de identidad.

`--harness-source-file` acepta un objeto pequeño `{kind: user|platform, reference: texto}` junto con un ID explícito. Sin archivo, la procedencia identifica el argumento; el entorno identifica `CCR_HARNESS_ID`; el alias identifica el texto recibido. Fuentes malformadas son errores de entrada antes de crear el archivo. La declaración identifica la fuente, no prueba identidad real. No copiar recorded_at, inferir modelos ni detectar interfaz desde variables no documentadas.

Catálogo inicial ampliado por petición del usuario: Codex, Claude Code, Copilot, Kiro, KiroCrew, Cursor, Windsurf, Gemini CLI, OpenCode, Cline, Roo Code, Continue, Aider, Antigravity, Augment Code/Auggie, OpenHands y Devin. Incluir las variantes de interfaz registradas en el JSON; mantener nombres genéricos con interfaz desconocida y no usar nombres de modelos como alias. Interfaz desconocida se representa con null. Alias iniciales limitados a nombres legibles y el nombre compuesto Codex ya observado; no usar nombres ambiguos de proveedores. La configuración debe ser por sesión/perfil, pues Desktop y CLI pueden compartir configuración global.

Un `CCR_HARNESS_ID` vacío o compuesto solo por espacios se considera no configurado, por lo que aplica la resolución del nombre/alias. Un `--harness-id` explícito en blanco sigue siendo un error de entrada.

## Persistencia y compatibilidad

Resolver antes de crear el run; conservar el resultado durante register, recuperación, record-event, retain y close. Las cuatro propiedades quedan unidas al hash del cierre existente. Validar forma, tipos y vocabulario de procedencia en schema 6; al leer no volver a resolver contra el catálogo instalado ni reinterpretar versiones históricas. Los lectores aceptan schemas 1–6; schema 6 hereda processing, fuentes temporales y referencias locales de schema 5. Archivos 1–5 continúan sin migración ni campos sintéticos, incluidos completos inmutables. El fallback nativo respeta el mismo catálogo y reglas. No requiere medir consumo ni añade barridos de contexto.

## Presentación

Usar `**ID**` en etiquetas de checks, incertidumbres y seguimiento anterior del reporte de usuario/comentario, y en todos los IDs equivalentes del resumen breve, incluidos hallazgos confirmados. Mantener los IDs del contrato y enlaces tal cual; el contenido aportado sigue escapado. Entregas completas reutilizan el renderizador. No reescribir informes históricos.

## Validación y publicación

Probar variantes Desktop/nombre genérico/CLI, configuración y prioridad, conflictos y desconocidos, catálogo inválido, procedencia inválida, CLI real, persistencia de identidad durante todo el ciclo, lectura histórica sin catálogo, recuperación processing y rechazo de alteraciones. Probar negritas y anclas con texto hostil escapado. Ejecutar la suite completa, CLI y enlaces locales. Versión propuesta 2.10.0 pendiente de publicación; README sigue enlazando la release existente. Abrir PR y esperar aprobación; sin merge, tag, release ni cambios en el visor independiente en esta etapa. Documentar para consumidores el nuevo cierre sin cambiar final review ni trace.

## Fuentes para la ampliación del catálogo

Los IDs son convenciones CCR; registrar una interfaz no garantiza disponibilidad actual de la plataforma ni prueba compatibilidad automática con skills. Entornos no catalogados siguen siendo válidos con identidad desconocida. Un nombre genérico no infiere dónde se ejecutó. Mantener Windsurf y Devin como identidades separadas; no reinterpretar históricos por un cambio de marca.

- [Cursor IDE](https://cursor.com/docs), [CLI](https://cursor.com/docs/cli/overview) y [web](https://docs.cursor.com/en/background-agent/web-and-mobile).
- [Windsurf plugins](https://docs.windsurf.com/plugins) y [Devin Desktop](https://docs.devin.ai/desktop/getting-started).
- [Gemini CLI](https://geminicli.com/docs/cli/cli-reference/), [OpenCode e interfaces](https://opencode.ai/docs/), [Cline CLI y editores](https://cline.bot/blog/introducing-cline-cli-2-0), [Roo Code](https://roocodeinc.github.io/Roo-Code/).
- [Continue](https://docs.continue.dev/index), [Aider](https://aider.chat/docs/install.html), [Antigravity IDE](https://antigravity.google/docs/home).
- [Copilot IDEs](https://docs.github.com/en/copilot/concepts/copilot-surfaces/copilot-in-ides), [Auggie](https://github.com/augmentcode/auggie), [Augment VS Code](https://www.augmentcode.com/signup), [OpenHands UI](https://docs.openhands.dev/api-reference/get-conversation).
