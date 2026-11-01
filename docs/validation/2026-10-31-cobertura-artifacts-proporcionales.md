# Evaluación de cobertura agrupada y artifacts proporcionales

Medición sintética reproducible con `tests/profile_topology_fixtures.py:record12` y `tests/test_review_coverage13.py:record13`: perfil focused, una asignación de discovery y una de verificación, mismas decisiones cubiertas y mismo contenido general. Se codificaron los registros con `archive_bytes` y los informes con `render`, en UTF-8.

| Proyección | Schema 12 | Schema 13 | Variación |
|---|---:|---:|---:|
| Registro JSON | 9.773 bytes | 6.127 bytes | −37,3 % |
| Informe Markdown | 4.016 bytes | 1.869 bytes | −53,5 % |

El caso usa datos sintéticos y detalles repetidos; no mide archivos adicionales, reservas, locks, tiempo, tokens ni costo del modelo. No demuestra un ahorro equivalente en revisiones reales ni en todos los artifacts. La selección de persistencia no reduce obligaciones ni sustituye validaciones necesarias.

El visor independiente inspeccionado declara soporte para finales 1–7 y archives 1–5. Su adaptador clasifica `final 7/archive 5` como `supported` y `final 12/archive 8` y `final 13/archive 8` como `limited`. Con un fixture compacto sintético, el descubrimiento encontró una corrida y el adaptador devolvió `limited`, sin reconocer un schema de cierre. No se ha actualizado ni validado como lector íntegro de compactos; la integración del visor es trabajo separado.

## Validación de implementación

La suite se ejecutó por sus 107 módulos `test_*.py`, en procesos con directorios temporales aislados. En esa corrida pasaron 104 módulos; fallaron tres comprobaciones por referencias documentales al schema anterior, un ciclo de dependencias y la ausencia de módulos nuevos en el índice. Los tres módulos se corrigieron y pasaron en una reejecución conjunta posterior. La corrida original y su registro no se presentan como una única corrida sin fallos. El ejecutor por módulos no conservó el detalle de skips de cada módulo.

Tras las correcciones pasaron nuevamente 24 pruebas de cobertura/render, 31 de compactos/promoción, 7 de selección de persistencia, el ciclo completo de archive 8 con final 13, y las comprobaciones de dependencias, índice, políticas y caracterización CLI. Se probó la negativa a modificar un archivo externo enlazado mediante hardlink con permisos de Windows que permiten crearlo. `git diff --check` no reportó errores.

## Correcciones posteriores al code review

Se corrigieron los seis hallazgos: staging reservado en promoción, handoff privado de final 13, resolución de aliases, uso del disclosure retenido en ambas entregas, proyección del ledger de modelos en el informe compacto y límite de 256 KiB sobre los bytes originales del ledger. La recuperación de promoción se comprobó terminando un subproceso con `os._exit` antes de reemplazar el primer marcador, y reintentando luego el mismo destino.

Pasaron 185 pruebas en 14 grupos de validación, sin skips reportados: compactos/promoción/regresiones, cobertura 13, entregas históricas y URLs sensibles, disclosure/credenciales, modelos/captura, integración de topología 12, archivo completo 13, render histórico, dependencias, contratos CLI y transacciones. Esta validación usó temporales cortos y aislados en Windows; no se repitió toda la suite general. Una ejecución con temporales largos detectó una discrepancia preexistente de representación `C:\...` frente a `\\?\C:\...` en una prueba concurrente; no se presenta como resuelta por estas correcciones.
