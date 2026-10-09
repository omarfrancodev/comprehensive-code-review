# Comprehensive Code Review

Skill para revisar código, cambios locales, commits y MR/PR con hallazgos verificables. Un **perfil** define la estrategia de descubrimiento y verificación; la **matriz ABCDE** muestra qué áreas se inspeccionaron; los **artefactos** conservan el resultado y su evidencia.

## Instalación

Desde el proyecto:

```bash
npx skills add omarfrancodev/comprehensive-code-review
```

El instalador permite elegir agentes y método. La instalación pertenece al proyecto actual; `-g` la instala a nivel de usuario:

```bash
npx skills add omarfrancodev/comprehensive-code-review -g -a codex
npx skills add omarfrancodev/comprehensive-code-review -g -a claude-code
npx skills add omarfrancodev/comprehensive-code-review -a codex --copy -y
```

Requiere Node.js/npm. Consulta la [guía de instalación y actualización](docs/installation.md) para requisitos comprobados, descarga ZIP, agentes y precauciones al actualizar copias.

## Uso

Invoca la skill desde un agente compatible; algunos admiten `$comprehensive-code-review`. Indica repositorio y alcance cuando no sean inequívocos:

```text
Usa comprehensive-code-review para revisar los cambios actuales.
Usa comprehensive-code-review --profile standard para revisar el PR 123.
Usa comprehensive-code-review --profile focused para comprobar las correcciones del PR 123.
Usa comprehensive-code-review --profile deep --delivery full para revisar estos commits.
Usa comprehensive-code-review --delivery brief --output docs/revisiones para revisar este MR.
```

`--profile`, `--delivery` y `--output` son convenciones de la petición que interpreta el agente: no forman un ejecutable de la skill ni son opciones de `npx`. También puedes pedir «perfil standard» o «entrega completa/breve» en español. Revisar no autoriza modificar código, publicar comentarios, aprobar ni fusionar cambios.

## Perfiles

| Perfil | Profundidad y verificación |
|---|---|
| focused | Un revisor y comprobación escéptica en la misma sesión para un alcance acotado demostrado. |
| standard | Un revisor; verificador independiente para candidatos sustantivos o dudas materiales. |
| deep | Dos revisores independientes sobre flujos e invariantes; un tercero solo por una necesidad distinta, y verificación independiente agrupada. |
| extended | Automático: cuatro o cinco asignaciones justificadas; explícito: dos a cinco según necesidades, y una verificación independiente agrupada. |

Sin perfil solicitado, la selección es automática según mecanismos, requisitos y cobertura. Un perfil explícito permanece fijo. Ningún perfil elimina los checks obligatorios, la persistencia ni el aislamiento de ejecuciones. La [guía de uso](docs/usage.md) explica selección, límites y revisiones incrementales.

Los nombres anteriores `economy` y `balanced` siguen funcionando como alias de `focused` y `standard`.

## Cobertura ABCDE

| Área | Qué se revisa |
|---|---|
| A | Arquitectura y diseño |
| B | Comportamiento y negocio |
| C | Contratos e integración |
| D | Datos y persistencia |
| E | Seguridad y operación |

Cada área queda **Cubierta**, **Parcial**, **No evaluada** o **No aplica**, con evidencia o motivo. Cubierta significa inspeccionada y puede contener defectos. Las cinco áreas no requieren cinco agentes. El informe separa defectos confirmados P0–P3 de incertidumbres y usa IDs estables para seguir hallazgos y checks.

## Entrega explícita

El archivo interno se conserva en cada revisión. Solo una petición explícita de modalidad `full`/completa o `brief`/breve crea una copia portable para el proyecto u otro destino; la modalidad controla la presentación, no la profundidad:

| Modalidad | Archivos y propósito |
|---|---|
| `full` / completa | `informe.md` y `review.json`: informe completo y registro portable del resultado. |
| `brief` / breve | `resumen.md`: resultado autocontenido con alcance, veredicto, hallazgos, checks y pendientes; sirve también para transferir la revisión a otro agente. |

Ambas incluyen `.ccr-delivery.json` para vincular el origen y comprobar la integridad de los archivos. `contexto.md` es opcional y aporta únicamente contexto adicional relevante ya recopilado.

El destino predeterminado es `<checkout-persistente>/docs/ccr/reviews/<alcance>/<review-id>/`, fuera del worktree temporal que ejecuta los checks. `--output <raíz>` cambia la raíz de una entrega solicitada; por sí solo no autoriza entregar ni redirige el archivo interno. Las entregas no copian evidence, logs ni reproducciones. Consulta [entregas y contexto](docs/usage.md#entrega-portable) y su [contrato operativo](references/delivery.md).

## Archivo interno

Por defecto se conserva en `<home>/.comprehensive-code-review/reviews/<proyecto>-<id-repositorio>/<alcance>/<fecha>-<id-ejecucion>/`, separado de las entregas y los temporales.

| Artefacto | Propósito |
|---|---|
| `informe.md` | Informe legible de la revisión. |
| `review.json` | Registro final ligado a la versión revisada, con IDs y decisiones. |
| `cierre.json` | Identidad, recursos, integridad y estado observado de cierre. |
| `trazabilidad.jsonl` | Hitos de la revisión y referencias a su evidencia. |
| `evidence/` | Evidencia seleccionada necesaria para reproducir o auditar resultados. |

El archivo se verifica antes de limpiar recursos propios. Una revisión cerrada permanece inmutable; otra revisión crea un registro enlazado y una entrega posterior conserva el vínculo con el original. Las mediciones son optativas, solo para una evaluación de coste solicitada. Consulta [archivo y ejecución](docs/usage.md#archivo-interno-y-ejecución).

## Guías y versiones

- [Uso y comportamiento avanzado](docs/usage.md): veredictos, IDs, re-review, publicación, helpers y validación.
- [Instalación y actualización](docs/installation.md): npx, ZIP, actualización y desinstalación.
- [SKILL.md](SKILL.md): instrucciones operativas del agente y referencias canónicas.
- [CHANGELOG.md](CHANGELOG.md): cambios de la skill.
- [Última release publicada: 2.8.0](https://github.com/omarfrancodev/comprehensive-code-review/releases/tag/v2.8.0), o [todas las releases](https://github.com/omarfrancodev/comprehensive-code-review/releases).
