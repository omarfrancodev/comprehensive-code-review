# Validación de replay de reservas nativas v2 — F005

Se verificó el hallazgo F005 del
[CCR CR-d8219e1f78c04b7d981b](https://github.com/omarfrancodev/comprehensive-code-review/pull/25#issuecomment-6273761906),
emitido sobre `bdec8e4dfc23fb0a8579817d5d55d07cf8372bdf`.
Ese CCR declaró resueltos F001–F004 y detectó que la normalización nueva impedía
leer las reservas nativas v2 emitidas sin `logical_scope_identity` por `9e5bf72`.

## Corrección y garantías

Commit de producto: `c487aee`.

- El lector verifica los hashes, la operación y la forma original de la petición
  v2 persistida; admite la omisión histórica del campo derivado. No cambia sus bytes.
- La comparación entre la petición actual y la reservada deriva la identidad en
  memoria. Las demás identidades y decisiones siguen sujetas a comparación exacta.
- La creación de intenciones nuevas exige una petición completamente canónica.
- El retry usa el descriptor activo o busca únicamente los dos nombres calculados
  para esa petición exacta. Así conserva el recibo y el sucesor después de retirar
  el descriptor. Sin descriptor activo, dos nombres ocupados producen un conflicto.
- Un archivo de intención ausente solo se reconstruye desde su descriptor validado,
  con los bytes originales. No se reemplaza por otra intención normalizada.

Las nuevas regresiones reprodujeron `restart intent request is not normalized`
antes de la corrección. Cubren lectura, recover y retry antes y después de preparar
el sucesor, reconstrucción del archivo ausente, retry después de completar,
rechazo de entradas cambiadas, hashes alterados y peticiones contradictorias aun
con hashes recalculados, creación canónica nueva y colisiones entre codificaciones.

La fixture reutiliza el escritor real de reservas, firmas y descriptores,
restaurando solo las dos diferencias del productor anterior: omisión de la
identidad derivada y retorno ignorado de captura en restart. Sus aserciones de
lectura y replay se ejecutan después de restaurar los helpers actuales.

## Validación

Windows, Python del runtime empaquetado, sin instalar dependencias. Se utilizaron
repositorios y sesiones sintéticos, fuera del sandbox por la restricción de
Git/MSYS ya reproducida. `TEMP` y `TMP` apuntaron a
`%USERPROFILE%/.agents/skills/ccr-tmp`, una ruta propia más corta para evitar el
problema de longitud de rutas temporales observado en el re-review.

Desde `tests/`:

```text
python -B -m unittest test_review_restart test_review_restart_v2 test_review_recovery test_review_recovery_followup test_review_recovery_reservations test_review_recovery_route_consistency test_review_recovery_diagnostics test_review_recovery_exit_guidance test_review_recovery_sequences test_review_restart_phase_consistency test_review_restart_refusals test_review_archive8 -v
```

Resultado: **151 pruebas aprobadas, 0 omisiones, 0 fallos y 0 errores**, exit 0,
en 831.490 segundos. Incluye las regresiones de F005 y las de reinicio F001–F002.

Se ejecutó además un contraste independiente con los archivos exactos
`scripts/review_restart.py` y `scripts/review_artifacts.py` obtenidos mediante
`git show` de `9e5bf727aac5aeb204142c8d9bda19a4dbd6e2a5`:
**cuatro casos aprobados**, exit 0. El productor anterior reservó un restart con
otro head, interrumpido antes de prepare o antes de link; el código actual completó
cada reserva por recover o retry y verificó el retry posterior. En todos se
conservaron bytes, hashes, operación y sucesor originales. Este contraste no usa
la emulación de la fixture y no introduce una dependencia del historial Git en
las pruebas mantenidas.

Logs locales en el directorio de temporales indicado:

| Archivo | SHA-256 |
|---|---|
| `pr25-f005-validation.log` | `be131afb5685ac349d718bd61bf3173087a0a16ed11977f37b8193a0cd3cd8f8` |
| `f005-previous-producer.log` | `b3331ea3cf0c634bd72efac75509c9f63aff8c96d71d015978ec460783f97db0` |

Tras el cierre documental se comprobó `test_reference_layout` y `git diff --check`.

## Límites

No se repitieron la suite completa ni las matrices extensas de reemplazos de
transferencias/adopción; sus rutas de escritura no cambiaron. Se ejecutaron las
baterías afectadas de coordinación y replay. No se certifica ejecución POSIX.
Las validaciones de [F001–F004](2026-10-19-pr25-ccr-adjustments.md) y de la
[suite completa anterior](2026-10-18-readable-archive-history-coverage.md)
conservan sus versiones y resultados, sin atribuirlos al nuevo head.

No se habilita la operación de archivos históricos incompatibles ni se migran
sus estructuras. No se portaron reviews reales, no se modificó el visor ni se
cambiaron los contratos de informe, traza o packet. La corrección no constituye
una nueva aprobación del CCR ni incluye merge o release.
