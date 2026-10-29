# Validación de topología, checks publicables y modelos

Base: CCR 3.4.0, `1d2626048a882cab510a59fd10fdbca7cf16dda5`. Implementación en la rama `docs/profile-session-topology`; versión preparada 3.5.0, sin publicación, tag ni push.

Estado: implementación completada y revisada; las nueve tareas del plan están cerradas. La repetición completa verificó 1048 pruebas en 98 módulos: 1045 aprobadas y tres omitidas por privilegios de symlink, sin fallos ni errores.

## Comportamiento implementado

- Final 12 conserva exactamente la forma de 11, incluidos propósito y 27 dimensiones. Los contratos publicados 1–11 no se migran.
- Deep usa dos descubridores; extended usa tres a cinco para ambas fuentes y uno o dos lotes finales. Los límites finales se aplican después de separar historia/finales; todas las verificaciones activas siguen afectando al agregado.
- La frescura usa el despacho original con identidad completa. Las anotaciones y segundos starts no refrescan trabajo temprano; degraded no omite el orden de trabajo final presente.
- El mapa de recursos se captura con el fingerprint inicial del workspace y se fija antes del trabajo. Las rutas standalone requieren prueba Git del commit/tree/blob o un archive con identidad inicial verificada. Comandos y recursos acreditados se muestran saneados; CCR-created/modified y origen desconocido reciben explicación.
- Draft 3 y delivery receipt 2 ligan la proyección a fuentes seleccionadas. Command receipt 2, model ledger 1, archive 8/layout 2, trace 1 y packet 1 conservan sus versiones.
- La captura de modelos usa metadata suministrada mediante la operación de setup y las instrucciones del coordinador. No es un detector automático de modelos del proveedor. Configurado, observado y desconocido se distinguen; se muestran ausencias por participantes realmente observados, sin inventar ledger histórico.
- Informe privado y entrega local muestran el resumen de modelos y su procedencia saneada; comentario público/handoff público y JSON portable no exportan ese ledger.

## Pruebas y revisiones

Las pruebas se ejecutaron con Python incluido en el entorno, `-B`, desde `tests/`, y un temporal corto para evitar el límite de rutas de Windows. Los comandos del plan usan `python -B -m unittest ...`; no se instalaron dependencias y las pruebas no invocaron proveedores de modelos ni harnesses externos. La revisión editorial se realizó por separado con agentes independientes.

Resultados específicos observados durante la implementación:

| Superficie | Evidencia |
|---|---|
| Forma inicial e historia congelada | 108 pruebas aprobadas |
| Adopción integrada de 12 | 67 pruebas aprobadas |
| Límites de descubrimiento | 72 pruebas aprobadas |
| Agregado de verificaciones | 67 pruebas aprobadas |
| Auditoría ampliada de topología | 30 casos específicos y 133 pruebas de regresión aprobados |
| Exposición tras primera revisión | 100 pruebas aprobadas; cinco hallazgos reproducidos RED→GREEN y aprobados en recheck |
| Modelos y ausencia de ledger | 82 pruebas enfocadas y 14 casos finales aprobados; hallazgo de participantes ausentes corregido y aprobado |
| Documentación/estructura | Cierre: 22 documentos, 133 enlaces locales y cinco bloques JSON de ejemplos verificados; nueve tareas y 46 pasos cerrados, con las nueve decisiones aprobadas conservadas |

Estos conteos corresponden a ejecuciones distintas con cobertura superpuesta; no se suman como un total de pruebas únicas. La repetición completa aprobó los 98 módulos en 843.703 s de tiempo de pared con cuatro procesos; los conteos de cada módulo coincidieron con el descubrimiento de 1048 identidades únicas. Los resultados desglosados y el commit probado constan en [la evidencia de suite](2026-10-28-profile-session-topology-suite.json).

La primera ejecución global se interrumpió deliberadamente cuando la revisión final reprodujo defectos adicionales; su progreso no se presenta como una suite aprobada. Las revisiones finales detectaron y motivaron pruebas para claves sensibles de URL escapadas por Markdown, helpers anidados no acreditados y eventos de finalización que solo referencian resultados. La última corrección pasó 104 pruebas enfocadas en 127.446 s y su recheck aprobó los tres hallazgos, sin nuevos problemas importantes. La aceptación global se completó con la repetición íntegra descrita abajo.

Una ejecución dentro del sandbox encontró tres fallos al crear clones parciales: Windows bloqueó `sh.exe` de Git antes de las aserciones del producto. Las tres pruebas exactas pasaron fuera del sandbox, sin cambios de código. La ejecución global usa ese entorno capaz de crear los fixtures, con Git 2.45.0.windows.1 y un temporal aislado.

La ejecución del ejemplo mantenido detectó después que su montaje aún construía final 10 mientras el comando documentado exigía 12. Se actualizó únicamente ese caso de productor actual a final 12 sin checks ejecutados, preservando los builders y escenarios históricos; la prueba pasó y una revisión independiente aprobó el ajuste. Los intentos interrumpidos se conservaron como diagnóstico, sin presentarlos como ejecuciones globales aprobadas.

La primera ejecución global que llegó al final ejecutó 1048 pruebas en 2380.097 s: 1044 aprobadas, tres omitidas por privilegios de symlink y un fallo en el inventario CLI esperado. El diff recursivo aisló exclusivamente las ampliaciones autorizadas: schema 12, flags de disclosure y las dos operaciones nuevas de setup. Se actualizó ese fixture conservando la comparación exacta de todo el inventario; 35 pruebas enfocadas pasaron en 18.629 s y la revisión independiente aprobó el diff. No cambió código de producción. La repetición completa distribuye las mismas 1048 identidades únicas descubiertas en 98 módulos entre cuatro procesos, con temporales separados; cada módulo debe conservar su conteo y terminar con código cero. La repetición terminó con código cero, 1048 pruebas cubiertas, tres omisiones y ningún fallo ni error. El descubrimiento equivale a `python -B -m unittest discover -s . -v`; cada uno de los 98 módulos se ejecutó una vez mediante `python -B -m unittest <módulo> -v`, con cuatro procesos y verificación de sus conteos. El código probado corresponde a `5bb712f`; el código de producción no cambió desde `a5365c2`.

| Caso corregido por revisión | Verificación |
|---|---|
| Secuencia de traza nula/malformada | Rechazo de schema 12 sin excepción; matriz de topología y recheck aprobados |
| Recurso duplicado con prueba Git engañosa | Reproductor de contenido/mapa rehasheados rechazado; asociación por bytes/path/hash exactos |
| Secretos escapados por Markdown y claves sensibles de URL | Reproductores en comentario, evidencia y handoff RED→GREEN |
| Entry point dotnet no acreditado, npm/Make redirigido y fixture privado | Explicación u ocultación; comando/selector original válido conservado |
| Helper anidado ausente/modificado | Prueba de bytes originales requerida; casos acreditados y runner soportado conservados |
| Modelo ausente para todos los participantes de un final nuevo | Unknown por identidad realmente observada, sin fabricar ledger ni digest; histórico sin backfill |
| Finalización que solo enlaza el resultado | Asignación, rol e identidad exacta recuperados de las fuentes; actores ajenos excluidos |
| Instrucción residual de final 11 y registro de módulos | Productor 12 e índice de los cuatro módulos nuevos coherentes; controles enfocados aprobados |

Las revisiones finales no dejaron hallazgos Critical/Important abiertos ni una lista de comportamientos descartados sin juzgar. El resultado global confirmó el cierre sin nuevas correcciones de producción. `git diff --check` terminó sin errores; los fixtures congelados `recovery_fixtures.py`, `traceability_fixtures.py` y `test_review_execution_policy.py` siguen idénticos a main. Los cambios posteriores a la suite se limitan al estado documental y su evidencia.

## Decisiones de implementación

1. Se usa final 12 porque main ya publicó 11 con propósito y dimensiones. No se reutiliza un número publicado ni se cambian registros históricos.
2. El entorno no pudo iniciar Git Bash para los helpers de seguimiento; se conservó un registro equivalente por plan y se ejecutaron las pruebas directamente con Python.
3. Se usó un temporal corto tras observar permisos y límites de longitud de rutas de Windows. Esto no cambia código ni expectativas del producto.
4. La operación de modelos, independiente de disclosure, se completó antes de cerrar toda la exposición; la integración y los digests se verificaron en conjunto.
5. Las tareas de exposición y modelos comparten retención, cierre y rendering; se integraron en un commit conjunto conservando informes y revisiones separados.
6. La lectura de fuentes queda en ejecución/CLI; los contratos y la proyección pura no hacen IO. La identidad inicial no puede sustituirse por hashes declarados después del check.
7. Los adapters de tareas son deliberadamente acotados: un helper anidado necesita prueba de bytes originales; shells, invocaciones dinámicas o selectores de otro manifiesto no acreditados usan explicación. No se construyó un intérprete ni un servicio de análisis de dependencias.
8. La captura de modelos depende de invocar la operación del coordinador con metadata real o ausencia explícita. No se sondean APIs, historiales, costes ni configuración global. Ignorar la captura deja unknown visible, sin cambiar el veredicto del producto.
9. Las revisiones y pruebas globales se prepararon contra código congelado; la aceptación siempre requiere ambos resultados. Las correcciones finales requieren nueva verificación de su código.

## Límites

La pertenencia y los hashes no demuestran por sí solos que la conclusión de una revisión sea verdadera. La explicación editorial y la partición efectiva de briefs siguen sujetas a la revisión existente. No se certifica compatibilidad del viewer externo, no se rellenan corridas históricas y no se realizó publicación remota. Las tres omisiones fueron `test_symlink_roots_inputs_and_archived_files_are_refused`, `test_existing_final_symlink_is_refused_without_touching_target` y `test_final_link_replacement_after_identity_check_is_refused`: el host no permite crear symlinks (`WinError 1314`). No se omitieron por selección manual. Las pruebas de junctions y hardlinks sí se ejecutaron.
