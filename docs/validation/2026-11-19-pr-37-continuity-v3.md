# Continuidad v3 y cierre del re-review del PR 37

Fecha: 2026-11-19. Rama: `docs/ccr-fiabilidad-y-eficiencia`. Base de estas correcciones: `94746a9337fd5d1b2855973e15383951e1b35e06`.

Este seguimiento atiende F015 y F018–F022 de [CR-7de6bc7acc3447189bec](https://github.com/omarfrancodev/comprehensive-code-review/pull/37#issuecomment-7022671589). Los resultados anteriores permanecen en los informes del [18 de noviembre](2026-11-18-pr-37-comments.md) y del [seguimiento anterior del 19 de noviembre](2026-11-19-pr-37-followup.md), sin atribuirles las correcciones actuales.

## Comportamiento corregido

| ID | Corrección | Regresión |
| --- | --- | --- |
| F018 | Separar contratos históricos v1/v2 de las nuevas escrituras v3. Leer un resultado histórico no deriva retrospectivamente un flag que su escritor no exigía. Al usarlo como antecedente v3 se conserva la incertidumbre que la evidencia disponible permite establecer. | Compacto real generado y leído con `7f05898`, lectura actual y seguimiento guiado v3; integridad y bytes del payload sin cambios. |
| F019 | Conservar autorizaciones independientes por miembro y origen. La caducidad de una exclusión no invalida una deuda lógica de la misma nota. | Consolidación con exclusión temporal y deuda independiente que comparten hash y fragmento. |
| F020 | Retener autorizaciones caducadas en un ledger inmutable. Cada resolución referencia su autorización y su primera procedencia acreditada; una exclusión se limita a la revisión original. | A→B→C/D; rechazo de recapturas, renombrados, fragmentos, cambios de tipo/alcance/condiciones, IDs nuevos, reescritura o eliminación del ledger y uso del JSON previo como autoridad nueva. |
| F021 | Eliminar la huella derivada de la condición privada. Asignar ordinales de decisión que no dependen de los caracteres del secreto. | Valores sensibles sintéticos distintos producen las mismas decisiones portables tras redactar; no aparece el antiguo hash de condición generado. |
| F022 | Mantener identidad estructural separada del texto visible mediante una etiqueta ordinal en el localizador portable. La misma decisión conserva su identidad en fila, lineage y ledger. | Condición literal copiada de una entrega anterior, texto visible coincidente, full/brief reales e inmutabilidad; rechazo de duplicados auténticos, incluidos AU distintos para el mismo acto de autorización. |
| F015 | Reconocer una observación terminal guardada en `closing`, también antes de crear el último evento pendiente. Summary y finish validan los mismos hechos antes de recomendar o efectuar el replay. | Interrupciones antes/después de la escritura final, recursos y recibos reales, observación temprana, plan de ejecución inválido y variantes explícitas de finish. |

## Contrato y coste del archivo

Las escrituras guiadas nuevas usan `assessment` **3** dentro de final 13. La lectura v1/v2 conserva las interpretaciones publicadas, incluidas las dos variantes v2 del PR. No se migran ni reescriben los resultados históricos. Los lectores estrictos necesitan actualizarse junto con sus productores; el visor independiente mantiene su límite de integración.

El ledger `authorizations` conserva IDs AU, miembro original, revisión, scope fijado y decisión completa. Su igualdad con el antecedente hasheado acredita las entradas heredadas. Los hashes de fuentes inactivas siguen reservados sin exigir volver a seleccionar ni abrir cada nota antigua. Las resoluciones activas y las autorizaciones nuevas conservan sus gates de bytes y captura inicial. El coordinador acredita la autoridad y su aplicabilidad actual; un digest nunca observado no basta por sí solo para demostrar una autorización humana nueva.

No hay archivos adicionales de workflow ni un recorrido recursivo de todos los ancestros. El ledger vive en el mismo resultado y el antecedente inmediato sigue siendo la fuente de continuidad. Se conserva el perfil, la independencia, las comprobaciones de fuentes, cobertura, identidad, reapertura, retención y limpieza. La captura rutinaria del modelo permanece retirada. Este cambio no mide un ahorro nuevo de tokens.

Las decisiones portables usan identidades ordinales en referencias de presentación. Estas etiquetas no son localizadores de prueba nativa ni hashes de las condiciones; no alteran el archivo retenido. El texto visible puede coincidir sin perder decisiones distintas.

## Archivo histórico y prueba de no regresión

El fixture [7f05898](../../tests/fixtures/pr37_legacy_v2/README.md) contiene A v1, B v1 y C v2 guiado, creado por el código real `7f0589853ae854bc0bf6678ba30bd2e9f8f2591f` extraído con `git archive`, sin cambiar el checkout. Se verificó con dos lectores aislados sobre la misma copia: `7f05898` aprobó y `94746a9` rechazó por `history_incomplete`. El lector ajustado acepta el payload y lo usa para una nueva retención v3.

Las rutas absolutas de ownership exigen adaptar la envoltura de ubicación de la copia de prueba. El helper de fixtures cambia solamente `archive_root`, `run_dir` y el digest del manifiesto en esa envoltura, conservando todos los bytes y hashes originales de resultado, informe y evidencia. La prueba compara snapshots antes/después y rechaza una evidencia alterada. El generador y los digests quedaron versionados; los tests ordinarios no dependen de conservar el commit antiguo en Git.

La comprobación independiente encontró dos brechas adyacentes durante la implementación: duplicar un acto de autorización con otro AU y recomendar replay final con un plan inválido. Se agregaron regresiones para ambas. La segunda incluye que ningún archivo cambie antes del rechazo, tanto en el replay automático como en los parámetros explícitos de finish.

## Validación

Se ejecutaron los **1,486 tests distintos de 135 módulos** descubiertos, repartidos sin duplicados ni exclusiones entre ocho procesos: **1,481 aprobados, cero fallos de aserción, dos errores y tres omisiones**. Tiempo transcurrido: **980.045 s**. La corrida global conserva resultado de error; no se presenta como una ejecución íntegramente verde. El fingerprint final confirmó que scripts, tests, referencias y fixture ZIP no cambiaron durante la ejecución.

Los dos errores fueron `WinError 5` al reemplazar archivos en la preparación de fixtures, antes de alcanzar las comprobaciones objetivo:

- `test_review_coordination_errors.CoordinationErrorTests.test_git_coordination_errors_keep_operation_context_without_lock_advice`: reemplazo de `manifest.tmp` por `manifest.json`.
- `test_review_delivery.DeliveryTests.test_context_typed_references_hide_absolute_paths_and_are_bounded`: reemplazo de `.cierre.json.tmp` por `cierre.json`.

Ambos casos pasaron en una repetición aislada **2/2**, sin cambiar fuentes: **6.239 s** de proceso, 4.334 s de unittest, exit 0. Este recibo se conserva separado de los errores originales. No se determinó la causa específica del acceso denegado y no se atribuye una corrección de producto a esa repetición.

Las tres omisiones corresponden al privilegio de symlinks de Windows (`WinError 1314`): `LockFileSafetyTests.test_final_link_replacement_after_identity_check_is_refused`, `LockFileSafetyTests.test_existing_final_symlink_is_refused_without_touching_target` y `ArchiveTests.test_symlink_roots_inputs_and_archived_files_are_refused`. No acreditan esas variantes de enlaces en este host.

La ejecución usó Python 3.14.3, `-B -X utf8`, `PYTHONPATH=tests` y TEMP/TMP separados. Se descubrió la suite equivalente a `python -B -X utf8 -m unittest discover -s tests`; la invocación real fue el runner de ocho procesos con selecciones JSON verificadas por SHA-256. Dos matrices extensas de reinicio ocuparon un proceso cada una; los 1,484 IDs restantes se distribuyeron entre los otros seis. El runner comprobó la igualdad exacta de los contadores de selección y ejecución. Este reparto no permite inferir una mejora de rendimiento frente a corridas anteriores.

Recibos locales: `.ccr-test-tmp/r3-rc77i7jf/summary.json`, `*-selection.json`, `*-result.json`, `*-process.json` y logs separados por proceso; `retry-permission.json` y sus logs conservan la repetición. El directorio se encuentra bajo el padre local `.agents/skills`, fuera del paquete de la skill. Copia del runner: `runner.py`, SHA-256 `3a4213b5c8ebf0e3734f78930784627bf78aac0c2dc0ca26193244a0259eaf0d`.

Selecciones focalizadas, independientes de la corrida global: continuidad **88/88** (18.474 s); identidad de condición **10/10** (4.831 s); recuperación de cierre **24/24** (782.903 s); fixture histórico, redacción e inspección **19/19** (42.110 s). La comprobación independiente aprobó **51/51** (129.427 s) y verificó los rechazos sin mutación ante observación explícita distinta, campo inválido y cleanup discordante. Su selección se ejecutó antes de ampliar las variantes de cierre; la suite global posterior sí incluyó todas las variantes finales.

La validación propia se realiza en Windows. Los casos POSIX reproducidos desde este host no son una ejecución nativa Linux. El ZIP definitivo y la integración integral del visor independiente siguen fuera de este seguimiento del PR. Estas comprobaciones no constituyen una aprobación formal de release.
