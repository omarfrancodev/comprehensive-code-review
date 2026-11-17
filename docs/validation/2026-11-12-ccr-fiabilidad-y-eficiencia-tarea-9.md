# Evaluación de la tarea 9 de CCR

Se comparó CCR 3.7.0, commit `1ff71c50a7d1d1d6d83cfb811ec893f2f61a5feb`, con las tareas 1 a 8 del worktree `docs/ccr-fiabilidad-y-eficiencia`. La evaluación mide el tramo de archivo que cambió. Las revisiones completas con descubrimiento, verificación independiente y archivo requieren otra muestra para estimar el ahorro por revisión o el efecto en una cuota de cinco horas.

## Método

- Se ejecutaron los helpers reales de ambas versiones sobre fixtures sintéticos. Se fijaron alcance, candidato, perfil, observaciones y evidencia seleccionada. La variante anterior usó los scripts exportados de Git y la nueva usó los del worktree. Cada par se ejecutó con procesos nuevos y el orden se alternó entre pares.
- En completo ordinario y reintento se usó perfil `deep`, schema 13, evidencia material, registro de ejecución y cierre sin recursos pendientes. En compacto se usó perfil `focused`, schema 13, con y sin disclosure. El escenario de recuperación usó un archivo completo de schema 12 y una sesión gestionada. La interrupción ocurrió después del reemplazo del disclosure, con el cleanup ya acreditado.
- Se midió desde el arranque de cada proceso hasta su salida. La preparación de fixtures, la inyección de la interrupción, la restauración del candidato y la comparación posterior quedan fuera. La columna de lecturas cuenta aperturas instrumentadas de las entradas seleccionadas y de archivos del run. Las llamadas Git cuentan subprocessos lanzados por el helper, aparte de las llamadas CLI del coordinador. Los bytes corresponden a stdout UTF-8. El tiempo incluye arranque de Python y se midió en Windows mientras corría la regresión.
- Se compararon registro, informe y evidencia después de verificar el cierre. Se normalizaron los IDs de revisión y los datos propios de cada reserva para comparar dos runs distintos. Los lectores comprobaron las identidades y hashes en cada archivo. Los disclosures también se verificaron contra el registro de su propio run antes de comparar el contenido común.

## Comparación mecánica

Se completaron **25 pares equivalentes**, cinco por escenario. Una repetición adicional de cada ruta compacta también comparó la identidad lógica del alcance y el hash de los insumos fijados en la reserva. El tiempo es la mediana de la suma de fases de cada run, con mínimo y máximo entre paréntesis. Todas las columnas muestran anterior → nuevo.

| Escenario | Llamadas CLI | Subprocesos Git | Lecturas | Renders | Stdout, bytes | Tiempo, segundos |
|---|---:|---:|---:|---:|---:|---|
| Completo | 5 → 3 | 0 → 0 | 184 → 126 | 3 → 2 | 9720 → 5132 | 8,99 (7,69–19,25) → 4,10 (3,85–5,57) |
| Completo, candidato rechazado y corregido | 6 → 4 | 0 → 0 | 201 → 142 | 3 → 2 | 10193 → 5132 | 9,88 (9,31–10,97) → 5,61 (5,33–8,39) |
| Compacto | 2 → 2 | 0 → 0 | 24 → 24 | 5 → 3 | 1134 → 576 | 3,16 (2,81–4,08) → 2,36 (2,24–9,75) |
| Compacto con disclosure | 4 → 4 | 1 → 2 | 30 → 32 | 5 → 3 | 5659 → 1185 | 5,70 (4,71–6,24) → 5,11 (4,76–5,21) |
| Completo, recuperación del cierre | 2 → 1 | 0 → 0 | 66 → 63 | 2 → 2 | 6975 → 359 | 3,13 (2,40–3,46) → 1,94 (1,76–2,01) |

- **Completo.** Las medianas de preflight y retención eran 1,14 s y 2,15 s. La retención con preflight integrado tardó 1,53 s. La lectura retenida pasó de 1,64 s a 0,91 s. Cierre y lectura final tenían medianas de 2,22 s y 1,50 s. `finish` hizo ambos en 1,64 s.
- **Reintento de candidato.** El rechazo tardó 1,13 → 0,88 s. Su diagnóstico pasó de 473 bytes de stdout a 117 bytes de stderr. El resto siguió los mismos pasos del completo.
- **Compacto.** La retención tardó 1,79 → 1,45 s y la lectura independiente 1,32 → 0,96 s. El peor tiempo nuevo superó al anterior en esta muestra. La reducción de renders y salida se mantuvo en todos los pares.
- **Compacto con disclosure.** Binding 1,11 → 1,05 s, construcción del disclosure 1,13 → 0,96 s, retención 1,81 → 1,90 s y lectura final 1,47 → 1,14 s. El binding a archivo verificó la sesión, con un Git adicional. El flujo leyó el archivo de candidato y mantuvo cuatro llamadas CLI. La salida total pasó de 5655 a 1185 caracteres.
- **Recuperación.** Las medianas del cierre anterior y su lectura completa fueron 2,05 s y 1,14 s. El `finish` de recuperación tardó 1,94 s y reutilizó la observación durable de limpieza. Se conservó la lectura completa.

## Piloto guiado y tokens

Este apartado registra el intento original de Codex CLI. La medición posterior con helpers operativos está en el [piloto controlado con Codex app-server](2026-11-12-ccr-piloto-controlado.md).

Se intentó un par completo y uno compacto en sesiones efímeras de Codex CLI 0.166.0, con el mismo modelo `gpt-6.1-sol`, esfuerzo `high`, permisos y perfil por par. Los cuatro turnos obtuvieron contadores reales, pero todos los comandos del harness fallaron al lanzar PowerShell con `registered Core launch requires an installed app`. Ningún helper arrancó ni se verificó el cierre. Una prueba de shell alternativo con PowerShell instalado reprodujo el fallo. El otro CLI disponible no tenía sesión autenticada.

| Intento bloqueado | Arranque / turno activo, s | Comandos intentados / ejecutados | Entrada | Entrada en caché | Salida | Razonamiento |
|---|---:|---:|---:|---:|---:|---:|
| Completo anterior | 2,87 / 37,50 | 5 / 0 | 140157 | 109952 | 873 | 166 |
| Completo nuevo | 2,25 / 38,15 | 5 / 0 | 156684 | 132096 | 917 | 173 |
| Compacto anterior | 2,55 / 37,89 | 5 / 0 | 169023 | 123264 | 780 | 183 |
| Compacto nuevo | 3,90 / 46,99 | 4 / 0 | 142411 | 122240 | 808 | 98 |

La tabla reproduce los contadores del turno bloqueado, sin sumar caché o razonamiento como categorías adicionales. El consumo de una ejecución guiada exitosa y su efecto en cuota quedan sin medir. La observación de 5–7 reviews con archivo frente a 8–12 inline en cinco horas es una referencia operativa aportada por el usuario. Falta un control emparejado con los mismos cambios y perfiles para atribuir esa diferencia al archivo.

## Equivalencia y controles

El completo anterior hacía preflight explícito, retención, lectura retenida, cierre y lectura completa. La nueva retención ejecuta el preflight sobre los bytes que va a escribir. Después de la lectura retenida, `finish` cierra y ejecuta la lectura completa por el lector independiente. En compacto, el binding a archivo y el recibo corto cambian el transporte de la salida. El disclosure sigue sujeto a hash, ruta y tamaño, y la retención sigue seguida de `validate --require-complete`.

Los pares comparan los mismos veredictos, checks, decisiones de cobertura, informe privado y evidencia seleccionada. El rechazo de candidato conserva el archivo y su traza intactos. La recuperación conserva el resultado de la revisión, actualiza únicamente la observación de limpieza y comprueba el nuevo vínculo del disclosure. Los controles de contrato de las tareas anteriores cubren además fuentes alteradas, prueba de ejecución ausente, lectura final fallida, perfiles con independencia pendiente, límites del re-review, continuidad de IDs, deuda aceptada y diferencias adicionales en publicación de GitLab. [Tareas 1 y 2](2026-11-12-ccr-fiabilidad-y-eficiencia-tareas-1-2.md) · [Tareas 3 y 4](2026-11-12-ccr-fiabilidad-y-eficiencia-tareas-3-4.md) · [Tareas 5 y 6](2026-11-12-ccr-fiabilidad-y-eficiencia-tareas-5-6.md) · [Tareas 7 y 8](2026-11-12-ccr-fiabilidad-y-eficiencia-tareas-7-8.md)

Los fixtures con causa esperada cubren una regresión de contrato introducida, un caso limpio, un problema de descripción, un supuesto fuera de alcance y deuda aceptada. Sus resultados son controles deterministas. Los pares nativos parten de un candidato ya construido, por lo que la tasa de omisiones y falsos confirmados en revisiones nuevas queda sin medir. [Controles de efectividad](../../references/maintenance/evaluation.md)

## Regresión

Se descubrieron 1361 casos con `unittest` desde `tests` y se distribuyeron por ID en diez procesos. La corrida inicial encontró una entrada faltante en el índice de módulos. Se agregó `archive/assessment.py` al índice y su prueba pasó. Tres casos fallaron durante reemplazos de archivos en Windows con `WinError 5` y tres al iniciar Git Bash para clones locales. Los seis pasaron en las repeticiones focalizadas.

El resultado consolidado fue **1358 aprobados, tres omitidos y ningún fallo pendiente**. De los ocho casos omitidos inicialmente por permisos del host, cinco pasaron al repetirlos con acceso a los fixtures desechables. Los tres restantes requieren privilegios para enlaces simbólicos en Windows. Las dos matrices de recuperación de recursos pasaron, incluida la de interrupciones en cada reemplazo de una transferencia con propietario.

## Recomendación

Adoptar la ruta nueva de archivo en un piloto controlado. En el completo, integrar el preflight a la retención y usar `finish` después de verificar el retenido y acreditar la limpieza. En el compacto, usar el recibo corto y la lectura independiente. Reservar el binding a archivo para disclosure cuando ya exista una sesión gestionada, porque en ese caso reduce el texto que recibe el coordinador a cambio de verificar la sesión y releer el candidato.

Conservar el selector de perfil, las obligaciones de verificación y los gates de retención y cierre. Mantener la captura de modelo como dato opcional de medición. Antes de generalizar el despliegue o estimar ahorro de cuota, repetir los pares guiados en un harness con herramientas operativas y agregar revisiones ciegas de los fixtures con causas esperadas. Medir el archivo y el total de cada review por separado, con contadores reales y resultados de cierre.

## Reproducción

Desde el worktree, la comparación local usa solo Python y Git. La opción `--native` consume cuatro turnos del harness autenticado, con modelo y esfuerzo explícitos para ambos lados.

```powershell
python -B -X utf8 docs/validation/ccr-workflow-benchmark.py --base 1ff71c50a7d1d1d6d83cfb811ec893f2f61a5feb --pairs 5 --output .superpowers/tarea-9-local.json
python -B -X utf8 docs/validation/ccr-workflow-benchmark.py --base 1ff71c50a7d1d1d6d83cfb811ec893f2f61a5feb --native --model gpt-6.1-sol --effort high --output .superpowers/tarea-9-nativo
```

[Banco de pruebas](ccr-workflow-benchmark.py) · [Plan de implementación](../superpowers/plans/2026-11-12-ccr-fiabilidad-y-eficiencia.md) · [Criterios para los contadores](../../references/maintenance/measurements.md)

Los JSON por fase, eventos nativos y logs de regresión quedan en `.superpowers/sdd/2026-11-12-ccr-fiabilidad-y-eficiencia/` dentro del worktree.
