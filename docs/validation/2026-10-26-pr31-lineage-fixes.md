# Validación del linaje ordinario y argumentos Git del PR 31

Comentario atendido: [F001 residual y F006](https://github.com/omarfrancodev/comprehensive-code-review/pull/31#issuecomment-6409107394), sobre `eea23b0`. Implementación: `4922b4b`. [Plan](../superpowers/plans/2026-10-26-pr31-lineage-fixes.md) · [Resultados reproducibles](2026-10-26-pr31-lineage-fixes-suite.json).

## Diagnóstico

La corrección previa de F001 seguía suponiendo que cinco áreas covered en un re-review acreditaban todo el alcance ordinario. Esa matriz puede describir únicamente el seguimiento de X aunque Y siga pendiente. La integridad del archivo y el vínculo con su antecedente prueban procedencia, no cobertura ordinaria.

Ahora un re-review necesita un antecedente ordinario suficiente, retenido y completo, alcanzado por su cadena nativa explícita y vinculado a su previous_reviews verificado. Cada antecedente utilizado debe seguir siendo equivalente y aplicable al alcance actual: diff completo, inventario de contexto original, materiales e identidad de configuración y perfil explícito. El inventario incluye Y aunque no aparezca en el seguimiento. Se revalidan manifiestos/hashes de la prueba después de seleccionar de nuevo el latest canónico. No se sustituye el resultado latest por uno anterior conveniente.

F006 se debía a que Git interpretaba ambiguamente OID/ruta cuando existía un archivo local llamado igual que un objeto. Se reprodujo tanto para los dos blobs como para los commits base/head. Ambos diffs delimitan ahora las revisiones mediante --.

## Evidencia RED → GREEN

- F001: cuatro fallos de producto en 25 casos con archivos reales: Y pendiente, Y cambiado fuera del seguimiento, identidad declarada discordante y re-review sin prueba ordinaria. Ambos archivos de cada pareja pasan validate(require_complete=True).
- Revalidación: un caso detectó que el informe del antecedente cambiaba durante la selección final; se movió la revalidación de testigos después de esa selección. El regresor pasó después.
- F006: dos subcasos fallaron por archivos llamados como old_blob/new_blob; posteriormente otros dos por base/head. Los cuatro pasan en la regresión final.
- Regresiones focalizadas finales: 86 casos aprobados, cero fallos, errores u omisiones. Incluyen herencia válida, commit vacío, rebase equivalente y límite del recorrido.
- Prueba adicional aislada: Y existe en la rama destino antes de la revisión ordinaria; cambia upstream y se rebasa la feature. El diff efectivo sigue siendo equivalente y el seguimiento solo consume X. Las funciones originales de archive/workflow de eea23b0, cargadas mediante git show sin modificar el checkout, ofrecen reutilización (un fallo, cero errores); el código corregido exige revisión nueva (un caso aprobado).

La prueba aislada fortalece el mismo método de contexto de la suite, sin añadir casos al total. La suite completa ejecuta el código de producto de 4922b4b; el fortalecimiento posterior modifica únicamente ese fixture y tiene su ejecución RED/GREEN independiente. Los resultados focalizados no se suman al total global.

## Suite completa

**902 casos en 80 módulos: 899 aprobados, 3 omitidos, cero fallos y errores.** Los tres procesos devolvieron exit 0.

| Lote | Módulos | Casos | Omitidos | Duración |
|---|---:|---:|---:|---:|
| 1 | 36 | 310 | 0 | 1335.945 s |
| 2 | 43 | 583 | 3 | 1502.031 s |
| 3 | 1 | 9 | 0 | 1491.712 s |

Las omisiones son las tres pruebas existentes de enlaces simbólicos reales sin privilegio Windows (WinError 1314), identificadas individualmente en el JSON. No hubo omisiones en las 86 regresiones focalizadas ni en la prueba aislada. Los inventarios son disjuntos, incluyen los 80 módulos descubiertos y suman exactamente 902 casos. `git diff --check` no presentó errores.

## Revisión independiente

Una revisión de contexto nuevo con gpt-6-astra/high inspeccionó toda la rama 4fab306..4922b4b: implementación, integración, compatibilidad, documentación y decisiones. No encontró hallazgos accionables; Declined to judge: ninguno. No volvió a ejecutar la suite. Sus límites quedan separados de la validación ejecutada.

## Compatibilidad y límites

No cambian schemas, layout, algoritmo de equivalencia ni contratos públicos CLI. Los archivos históricos permanecen inmutables y consultables. Las revisiones ordinarias anteriores conservan reconstrucción exacta y fallback de árboles completos cuando hay evidencia suficiente. Un re-review heredado solo es reutilizable si puede comprobarse toda la cobertura ordinaria aplicable; de lo contrario exige revisión nueva.

Se conservan las protecciones contra lazy fetch, GIT_DIFF_OPTS, paths recursivos y límites de fuentes. Las declaraciones de cobertura/contexto siguen siendo evidencia declarada por sus autores; la admisión no demuestra semántica del programa ni sustituye un CCR. La captura fija objetos locales: la frescura remota sigue siendo responsabilidad del coordinador.

## Decisiones

| Decisión | Motivo y coste |
|---|---|
| Seguimiento en ledger local sin todo nativo | La herramienta no está disponible; no existe checklist nativo |
| Acreditar herencia mediante metadatos existentes | Evita inventar un marcador histórico; prueba incompleta puede provocar una revisión conservadora |
| Máximo 32 padres explícitos y revalidación tras seleccionar latest | No recorrer todo el archivo ni escoger otro resultado; linaje ausente/cíclico/profundo/cambiado exige revisión nueva |
| Incluir OID de commits en F006 | Mismo defecto reproducido; se corrigen ambos parsers de diff |
| Suite en tres procesos con inventarios disjuntos y balance por coste | Se cubren todos los módulos; no se valida el orden entre procesos |

Sin hallazgos menores diferidos en esta pasada. Worktree conservado; sin merge, instalación ni release.
