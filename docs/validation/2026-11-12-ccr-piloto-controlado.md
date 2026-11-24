# Piloto controlado del archivo de CCR

El piloto compara CCR 3.7.0, commit `1ff71c50a7d1d1d6d83cfb811ec893f2f61a5feb`, con las tareas 1 a 8 del worktree `docs/ccr-fiabilidad-y-eficiencia`. La unidad de comparación es la fase de archivo de una revisión sintética con candidato, perfil, alcance y evidencia ya preparados. El piloto mide la coordinación del archivo y la ejecución de sus validaciones. La exactitud de descubrimiento y el consumo total de una revisión requieren muestras aparte.

## Ejecución

Se usó Codex app-server 0.166.0, con `gpt-6.1-sol`, esfuerzo `high` y un hilo efímero nuevo para cada muestra. El modelo pidió cada paso por nombre a una herramienta dinámica. El controlador ejecutó el helper real, con argumentos fijos sobre el fixture desechable, y devolvió su stdout, stderr y código de salida al modelo. Cada paso requirió una llamada independiente. Este mecanismo permitió usar el mismo harness en ambos lados sin depender de su lanzador de PowerShell. [OpenAI Docs sobre herramientas dinámicas](https://learn.chatgpt.com/docs/app-server#dynamic-tool-calls-experimental)

Se fijó el mismo perfil, esquema, candidato, evidencia y alcance dentro de cada par. El completo usó `deep` y esquema 13 con prueba sintética de ejecución independiente. Los compactos usaron `focused` y esquema 13, con y sin disclosure. Cada variante conservó su procedimiento de retención y cierre. Se alternó el orden anterior/nuevo dentro de cada escenario para reducir el efecto de secuencia. La caché del proveedor operó normalmente.

La latencia se midió desde el arranque de app-server hasta el evento de turno completado. El tiempo de turno excluye el arranque del servidor. La preparación de insumos y la comparación posterior se hicieron fuera del turno. El contador de llamadas corresponde a invocaciones de la herramienta dinámica que ejecutaron helpers de CCR. Los tokens proceden del último total que notificó el harness para cada hilo de un solo turno. La entrada ya incluye la caché y la salida ya incluye el razonamiento. La cuota y los cargos atribuibles al piloto quedaron sin medir.

## Resultados

Los seis pares completaron el cierre y pasaron la comparación de archivos. La tabla muestra medianas de dos muestras por variante. Las flechas indican anterior → nuevo.

| Ruta | Llamadas | Bytes de stdout | Tiempo total | Turno activo | Tokens totales | Entrada sin caché |
|---|---:|---:|---:|---:|---:|---:|
| Completo | 5 → 3 | 9.720 → 5.132 | 19,20 → 11,69 s | 17,62 → 10,40 s | 152.873,5 → 95.871 (−37,3 %) | 28.091,5 → 37.543 |
| Compacto | 2 → 2 | 1.134 → 576 | 11,86 → 12,37 s | 10,49 → 11,27 s | 71.419,5 → 67.955,5 (−4,9 %) | 12.825 → 8.392 |
| Compacto con disclosure | 4 → 4 | 5.659 → 1.185 | 24,72 → 15,79 s | 22,99 → 14,33 s | 124.558,5 → 119.094,5 (−4,4 %) | 38.807,5 → 36.535 |

En el completo bajaron los tokens totales en ambos pares. La entrada sin caché bajó en uno y subió en el otro. En el compacto ordinario el tiempo total bajó en un par y subió en el otro. En el compacto con disclosure el anterior tardó 13,99 s y 35,45 s, frente a 13,46 s y 18,13 s del nuevo. La segunda retención anterior tardó 12,77 s en el helper. La dispersión limita cuánto se puede generalizar sobre la latencia de esta ruta.

### Contadores del harness por muestra

| Ruta | Par | Variante | Entrada | Caché | Salida | Razonamiento | Total | Tiempo total |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| Completo | 1 | Anterior | 152658 | 124544 | 208 | 0 | 152866 | 18,02 s |
| Completo | 1 | Nueva | 91795 | 67968 | 153 | 0 | 91948 | 10,97 s |
| Completo | 2 | Anterior | 152613 | 124544 | 268 | 61 | 152881 | 20,38 s |
| Completo | 2 | Nueva | 99643 | 48384 | 151 | 0 | 99794 | 12,40 s |
| Compacto | 1 | Anterior | 71241 | 70016 | 173 | 47 | 71414 | 11,44 s |
| Compacto | 1 | Nueva | 64839 | 57472 | 176 | 42 | 65015 | 10,98 s |
| Compacto | 2 | Anterior | 71273 | 46848 | 152 | 14 | 71425 | 12,28 s |
| Compacto | 2 | Nueva | 70729 | 61312 | 167 | 36 | 70896 | 13,76 s |
| Compacto con disclosure | 1 | Anterior | 124378 | 98304 | 182 | 0 | 124560 | 13,99 s |
| Compacto con disclosure | 1 | Nueva | 118926 | 94208 | 180 | 0 | 119106 | 13,46 s |
| Compacto con disclosure | 2 | Anterior | 124373 | 72832 | 184 | 0 | 124557 | 35,45 s |
| Compacto con disclosure | 2 | Nueva | 118880 | 70528 | 203 | 22 | 119083 | 18,13 s |

## Validación de archivos

- **Completo.** La ruta anterior ejecutó preflight explícito, retención de esquema 13, lectura del retenido, cierre y lectura completa. La nueva integró el preflight en la retención, mantuvo la lectura del retenido y ejecutó el cierre con lectura independiente mediante `finish`. Ambas contrastaron los bytes de la descripción, notas, índice, alias y evidencia de ejecución contra las fuentes fijadas. El perfil, el plan de ejecución, la cobertura, el veredicto y el informe coinciden por par.
- **Compacto.** Ambas variantes retuvieron el registro con su evidencia y ejecutaron `validate --require-complete`. Coincidieron el check `C001`, su propósito y resultado, la identidad lógica, el hash de insumos fijados, el informe y los bytes de las fuentes seleccionadas.
- **Disclosure.** Se ejecutaron binding y construcción del disclosure en ambos lados. La ruta nueva comprobó el hash del recibo de archivo. Cada disclosure acreditó el ID y el hash del registro retenido en su propio run. Se comparó el resto del contenido entre variantes.

La regresión focalizada pasó los **64 casos** de retención completa, salidas compactas, consistencia de cierre, recuperación del disclosure, disposiciones y escenarios con causa conocida. Incluyó rechazo de evidencia alterada, ejecución faltante, fallo de la lectura final e interrupciones antes y después de reemplazar el disclosure. [Evaluación mecánica](2026-11-12-ccr-fiabilidad-y-eficiencia-tarea-9.md)

## Recomendación

Usar la nueva secuencia de archivo completo en el siguiente despliegue controlado. En compacto, conservar el recibo breve y usar binding a archivo cuando el disclosure ya cuente con una sesión gestionada. Mantener la lectura independiente de cierre en ambos modos. La reducción de tokens totales es una observación de esta muestra. La diferencia de caché y el tamaño de muestra dejan abierta la estimación de cuota y del costo de una revisión de principio a fin.

Los eventos originales, el resumen por fase y los scripts de reproducción se guardaron en `.superpowers/sdd/2026-11-12-ccr-fiabilidad-y-eficiencia/` dentro del worktree. El resumen del piloto está en `controlled-pilot/summary.json`. Para repetirlo desde ese worktree con el Codex local autenticado, use una salida nueva.

```powershell
$pilot = '.superpowers/sdd/2026-11-12-ccr-fiabilidad-y-eficiencia'
python -B -X utf8 "$pilot/run_controlled_pilot.py" --pairs 2 --output "$pilot/controlled-pilot-repeat"
```
