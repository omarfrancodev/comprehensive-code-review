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

Los helpers opcionales usan una entrada única, `python /ruta/skill/scripts <área> ...`, desde cualquier directorio; no necesitan instalación Python. Consulta [uso y migración de scripts](docs/script-migration.md) para las doce áreas y la ruptura de imports anterior.

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
| deep | Exactamente dos descubridores independientes y un verificador final; una tercera perspectiva necesaria exige extended. |
| extended | Automático y explícito: tres a cinco descubridores independientes; uno o dos lotes finales, combinados o particionados en candidatos e invariantes. |

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

El destino predeterminado es `<checkout-persistente>/docs/ccr/reviews/<alcance>/<review-id>/`, fuera del worktree temporal que ejecuta los checks. `--output <raíz>` cambia la raíz de una entrega solicitada; por sí solo no autoriza entregar ni redirige el archivo interno. Las entregas no copian evidence, logs ni reproducciones. Consulta [entregas y contexto](docs/usage.md#entrega-portable) y su [contrato operativo](references/reporting/delivery.md).

## Archivo interno

Por defecto se conserva en `<home>/.comprehensive-code-review/reviews/<repository-group>/<logical-scope-group>/<UTC-created>--<version-hint>--<run-id>/`, separado de las entregas y los temporales. Por ejemplo, las versiones de un MR comparten `mr-1010/`; cada ejecución muestra la fecha UTC, la cabeza revisada y su ID único en la carpeta. Los informes no reciben fechas adicionales.

| Artefacto | Propósito |
|---|---|
| `informe.md` | Informe legible de la revisión. |
| `review.json` | Registro final ligado a la versión revisada, con IDs y decisiones. |
| `cierre.json` | Identidad, recursos, integridad y estado observado de cierre. |
| `trazabilidad.jsonl` | Hitos de la revisión y referencias a su evidencia. |
| `evidence/` | Evidencia seleccionada necesaria para reproducir o auditar resultados. |

El archivo se verifica antes de limpiar recursos propios. Una revisión cerrada permanece inmutable; otra revisión crea un registro enlazado y una entrega posterior conserva el vínculo con el original. Las mediciones son optativas, solo para una evaluación de coste solicitada. Consulta [archivo y ejecución](docs/usage.md#archivo-interno-y-ejecución).

Antes de ofrecer repetir o consultar un resultado anterior, CCR verifica que los cambios efectivos, el contexto y los materiales sigan siendo equivalentes. Los cambios reales o la evidencia insuficiente inician una revisión nueva sin confirmación adicional. La selección explícita compara vigencia y puede devolver empate o búsqueda incompleta; nunca decide por el orden de carpetas. Los resultados históricos incompatibles se preservan y pueden portarse como consulta mínima. Consulta [recuperación y continuidad](references/archive/recovery.md).

## Guías y versiones

Las referencias operativas se agrupan por flujo, ejecución, contratos, archivo, presentación y mantenimiento. El agente consulta solo las necesarias en cada fase; la [guía de uso](docs/usage.md#organización-de-referencias) explica la organización.

- [Uso y comportamiento avanzado](docs/usage.md): veredictos, IDs, re-review, publicación, helpers y validación.
- [Instalación y actualización](docs/installation.md): npx, ZIP, actualización y desinstalación.
- [SKILL.md](SKILL.md): instrucciones operativas del agente y referencias canónicas.
- [CHANGELOG.md](CHANGELOG.md): cambios de la skill.
- [Release 3.5.0](https://github.com/omarfrancodev/comprehensive-code-review/releases/tag/v3.5.0), o [todas las releases](https://github.com/omarfrancodev/comprehensive-code-review/releases).

## Contribuciones

Consulta [CONTRIBUTING.md](CONTRIBUTING.md) para el formato de descripciones de PR/MR y el uso de las plantillas del repositorio.

## Licencia

Este proyecto se distribuye bajo la [licencia MIT](LICENSE).


## Reutilización por equivalencia en 3.2.0

La versión 3.2.0 incorpora [admisión por cambios efectivos](references/workflow/reuse.md). Para una petición ordinaria de MR/PR, cambios de contenido o contexto y evidencia insuficiente inician una nueva revisión sin confirmación adicional. Un merge vacío o rebase puede reutilizar el resultado cuando el diff y sus insumos materiales son equivalentes; HEAD por sí solo no decide. `artifacts assess-reuse` es de solo lectura y la consulta explícita del último informe conserva su carácter histórico.

Los sidecars nuevos no migran archivos anteriores ni modifican archive 8/layout 2, review schema 10, trace schema 1 o packet version 1. Cuando una revisión antigua carezca de prueba suficiente, se conserva como histórica y se realiza una nueva. Las ejecuciones reutilizadas conservan su revisión original. Véase [el diagnóstico](docs/analysis/2026-10-25-review-reuse-and-coverage-diagnosis.md) y [los ejemplos de cobertura](docs/examples/review-scenario-disposition.md). La reutilización de un re-review exige acreditar cobertura ordinaria completa y aplicable mediante su cadena nativa explícita; una matriz de seguimiento cubierta no basta.

## Calibración de prioridades en 3.4.0

La [rúbrica canónica](references/contracts/priority-calibration.md) define P0–P3 según la consecuencia sustentada y separa confirmación, origen y bloqueo. Los nuevos hallazgos confirmados justifican su prioridad en `impact`, sin campos ni schemas nuevos. La guía se carga en verificación y consolidación; el corpus sintético no se carga en cada review ordinario. Consulta los [ejemplos de frontera](docs/examples/priority-calibration.md) y la [evaluación con sus límites](docs/validation/2026-10-26-priority-calibration-evaluation.md).

## Trazabilidad explícita en 3.3.0

Los resultados nuevos usan final schema 12: cada check declara propósito antes de ejecutarse, la captura lo conserva en recibo 2 y las cinco áreas muestran sus 27 dimensiones con evidencia o motivo. El informe y los comentarios usan sublistas para evidencias y cobertura; cada evidencia enlaza su check real o conserva su origen estático. Propósito, resultado e impacto del hallazgo se presentan por separado.

Los comentarios requieren resúmenes editoriales ligados al registro para propósito y cada flujo; los drafts de la proyección nueva usan schema 3. Draft 2 conserva su política histórica; un draft 1 se conserva y se prepara de nuevo desde la misma fuente vigente. Finales 1–11, recibos 1 y reglas de reutilización mantienen su contrato; archive 8/layout 2, trace 1 y packet 1 no cambian. Los consumidores de nuevos resultados deben admitir final 12; la compatibilidad del visor independiente queda fuera de esta implementación. Véanse [contrato](references/contracts/result-contract.md), [publicación](references/reporting/publication.md) y [validación](docs/validation/2026-10-26-check-evidence-coverage-implementation.md).
