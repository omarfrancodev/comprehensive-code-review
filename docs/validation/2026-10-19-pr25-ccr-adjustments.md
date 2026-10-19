# Validación de ajustes del CCR del PR 25

Registro de F001–F004 sobre el head `bdec8e4`. La validación posterior de F005
se documenta en [replay de reservas nativas v2](2026-10-19-pr25-native-v2-replay.md).

Se contrastaron y reprodujeron los cuatro hallazgos del
[CCR CR-d935b7d63c984b2e884c](https://github.com/omarfrancodev/comprehensive-code-review/pull/25#issuecomment-6269611153),
emitido sobre `9e5bf727aac5aeb204142c8d9bda19a4dbd6e2a5`.
Los cambios se realizaron en `feat/archive-layout-portability`, dentro del worktree
aislado, con fuentes y sesiones sintéticas. No se modificó el visor.

## Hallazgos y correcciones

| Hallazgo | Corrección | Regresión comprobada |
|---|---|---|
| F001 | La petición de restart captura la identidad lógica canónica antes de reservar la intención. Recover completa la identidad omitida con el selector reservado y compara exactamente las demás entradas. | Un restart interrumpido con otro head se recupera con la petición original y el mismo sucesor reservado. Se rechazan cambios de scope, fuentes, identidad lógica, descripción, requisitos, plan y configuración sin modificar el origen. El retry posterior es idempotente. |
| F002 | Restart deriva la identidad desde el selector de destino; no hereda la del origen por coincidir el snapshot. | Working con el mismo snapshot y nuevos límites `src` crea otro grupo, incluso mediante recuperación tras interrupción. Una identidad explícita contradictoria se rechaza antes de reservar. |
| F003 | `resource_cleanup.status=pending` se trata como transacción activa. | Inspect y port rechazan la fuente sin modificarla ni crear destino. La observación escalar `cleanup=pending` sigue siendo portable cuando no hay una transacción activa. |
| F004 | El CLI de historial configura stdout y stderr como UTF-8 antes de procesar argumentos o imprimir. | Show muestra el informe íntegro con la flecha de versión en un subprocess con salida redirigida y `PYTHONIOENCODING=cp1252`, `PYTHONUTF8=0` y `-X utf8=0`. |

Las pruebas nuevas de los cuatro escenarios fallaron antes de sus correcciones
por los síntomas descritos en el CCR y pasaron después. Se añadió también una
prueba pura de captura de la identidad de destino en la petición normalizada.
Los commits de producto son `f3aba41` (reinicio) y `d5c54fe` (historial).

## Validación ampliada

Se ejecutó desde `tests/`, con Python del runtime empaquetado y `TEMP`/`TMP` en
`%USERPROFILE%/.agents/skills/comprehensive-code-review-validation`:

```text
python -B -m unittest test_review_restart test_review_recovery test_review_recovery_followup test_review_recovery_reservations test_review_recovery_route_consistency test_review_recovery_diagnostics test_review_recovery_exit_guidance test_review_recovery_sequences test_review_restart_phase_consistency test_review_restart_refusals test_review_archive8 test_review_layout_v2 test_review_history test_review_latest -v
```

Resultado: **174 pruebas aprobadas, 0 omisiones, 0 fallos y 0 errores**, exit 0,
en 513.513 segundos. La batería incluye reservas, recuperación y cancelación de
reinicios, coordinación de recursos, recorridos CLI archive 8, selección latest,
layout y los 15 casos de consulta histórica. Tras el cierre documental pasó
`test_reference_layout` (1 prueba de enlaces locales) y `git diff --check`.

Log local: `pr25-ccr-validation.log`, en el directorio de temporales indicado.
SHA-256: `2f2c9498f29f881dc5a3311aff7bb2bafbe4717d494faf9c85b8aeec4996c771`.

## Límites

Esta ejecución fue en Windows, fuera del sandbox por la restricción ya reproducida
de Git/MSYS sobre repositorios temporales. No certifica ejecución POSIX.
No se repitieron la suite completa ni las dos matrices extensas de reemplazos
atómicos de transferencias/adopción: sus rutas de escritura no cambiaron; se
ejecutaron las baterías afectadas de coordinación y recuperación.
La [suite completa anterior al CCR](2026-10-18-readable-archive-history-coverage.md)
permanece como evidencia de la versión previa, sin atribuir sus 621 casos al nuevo head.

Los contratos final 10, trace 1 y packet 1, el contenido del renderer y la
clasificación de archivos históricos permanecen vigentes. No se migraron ni
portaron reviews reales. Estas correcciones no constituyen una nueva aprobación
del CCR ni incluyen merge o release.
