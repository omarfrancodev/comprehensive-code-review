# Validación previa a la publicación de 2.14.0

La [re-review final del PR 27](https://github.com/omarfrancodev/comprehensive-code-review/pull/27#issuecomment-6318546248) declaró APROBABLE `60273749c4969153e0375f757d88bd089229700d`, sin hallazgos confirmados. La preparación de publicación conservó los scripts de esa versión y corrigió cuatro fixtures detectadas por la suite completa.

## Suite completa y alcance del resultado

```text
python -B -u -m unittest discover -s tests -v
Ran 717 tests in 4302.417s
FAILED (failures=7, errors=12, skipped=3)
```

La corrida global finalizó todos los **717 casos**, con **698 casos aprobados**, **3 omitidos** y **16 casos distintos afectados** por las cuatro fixtures siguientes. Los contadores de fallos/errores también incluyen subcasos; no equivalen a métodos distintos. Ambas matrices extensas de transferencias y adopción pasaron.

| Fixture corregida | Causa y comprobación final |
|---|---|
| `test_review_history.py` | El TEMP abreviado 8.3 quedaba escrito literalmente en el marcador sintético y no coincidía con la ruta canónica comprobada por el lector. La fixture ahora crea su directorio sobre TEMP resuelto. Las 15 pruebas pasaron manteniendo TEMP 8.3. |
| `test_superseded_assignment_cannot_start` | S002 usaba `#profile` en lugar de su fila histórica. Con `#profile_history/1/profile`, el test alcanza y confirma el rechazo de la asignación supersedida. |
| `test_started_or_nonempty_successor_cannot_be_abandoned` | La fixture intentaba iniciar discovery sin asignación registrada en un sucesor con adopción conflictiva. Ahora observa el inicio de un check permitido sin adoptar la sesión ajena, exige estado `processing`, el motivo concreto de rechazo y la preservación de todos los recursos. Pasó 1/1 en 15.496 segundos. |
| `test_review_traceability_contract.py` | Dos escenarios todavía esperaban sanitización implícita de evidencia interna. Ahora exigen el contexto público ligado al digest del registro y comprueban privacidad y escape literal de Markdown/HTML. El módulo pasó 19/19 en 0.155 segundos. |

El primer log focalizado conserva 17 casos: 16 aprobaron y la primera preparación del escenario de sucesor fue rechazada por ownership. El log definitivo del sucesor acredita su corrección. Junto con las 19 pruebas de trazabilidad, los IDs aprobados cubren todos los casos afectados de la corrida global.

En conjunto quedaron comprobados **714 casos distintos aprobados y 3 omisiones**. No se volvió a ejecutar toda la suite después de modificar las fixtures; no se presenta una única corrida global verde. Los scripts operativos conservaron sus blobs Git del head aprobado y los cambios de prueba afectan a 19 casos de las cuatro fixtures verificadas.

Las omisiones corresponden al permiso de symlinks de Windows:

- `test_review_artifacts.ArchiveTests.test_symlink_roots_inputs_and_archived_files_are_refused`.
- `test_review_lock_file_safety.LockFileSafetyTests.test_existing_final_symlink_is_refused_without_touching_target`.
- `test_review_lock_file_safety.LockFileSafetyTests.test_final_link_replacement_after_identity_check_is_refused`.

## Entorno y evidencia

Python 3.12.14 y Git 2.45.0.windows.1 en Windows. Se usaron repositorios y sesiones sintéticos, un TEMP propio corto y ejecución fuera del sandbox para Git/MSYS. Para futuras ejecuciones debe resolverse TEMP antes de construir identidades sintéticas que exijan rutas canónicas.

Los logs locales conservados tienen estos SHA-256:

- `v2.14.0-full-validation.log`: `0f0f25134425b8671631234bca91aac21b197f2a891147f98d9397731f084545`.
- `v2.14.0-fixture-validation.log`: `23804290efb08047fcdc2a39294a5cfea21f47e4a2c8bf91d2f66bc3be85081b`.
- `v2.14.0-successor-validation.log`: `44edc30b8f18ddb72e4ea052713f047bd5be08eaae3e5714edb21694f97359a6`.
- `v2.14.0-traceability-validation.log`: `ccde98c629b265a5ad1389db6298ac76cc365f2b73b4a11ae9581f60bf10ea3a`.

## Integración y preparación del paquete

El commit de fixtures `be8abfe911d61f2bbf1a7965c995356a342e7d31` conserva el árbol `scripts/` de `60273749c4969153e0375f757d88bd089229700d`. El PR 27 se integró mediante `7b78f7b1556d7e7ca3c07ee6c247561fbebe6a37`. La preparación de 2.14.0 cambia solo metadatos de versión, changelog, enlaces de distribución, la versión del ejemplo archive 8 y este registro.

Sobre esta preparación pasaron `test_reference_layout.py` (1/1, 0.066 segundos) y el ejemplo documentado archive 8 (1/1, 6.890 segundos). `git diff --check` terminó con exit 0.

El ZIP debe generarse del commit final con LF, contrastar su inventario y cada archivo con los blobs Git y verificar que todos sus archivos Python coincidan con la versión validada. Desde el paquete extraído se ejecutan enlaces locales, el ejemplo archive 8 y las ayudas CLI; las notas de la release registran sus resultados y el checksum observado.

Se conservan archive 8/layout 2, final review schema 10, trace schema 1 y packet version 1. Los runs nativos anteriores sin índice mantienen su contrato de integridad; los archivos históricos anteriores siguen la ruta de consulta existente. Esta validación no certifica ejecución POSIX ni revisión de un MR real.
