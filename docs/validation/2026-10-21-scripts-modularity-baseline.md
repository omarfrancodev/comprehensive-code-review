# Baseline de los scripts de CCR

- **Fecha:** 2026-10-21
- **Base de código:** `main`, `fd38df82f2ea8ef2a921dd8a89e66540f0f01bfb` (CCR 2.14.0).
- **Worktree:** `.worktrees/scripts-modularity-spec-plan`, rama `docs/scripts-modularity-spec-plan`.
- **Propósito:** fijar la superficie de CLI, formatos y orden de coordinación antes de extraer los módulos.

## Superficie de CLI

Se inspeccionaron los parsers reales de las doce áreas, sin ejecutar handlers. `tests/fixtures/scripts_cli_contracts.json` fija descripciones, opciones, posición de argumentos, acciones, defaults, choices, required, grupos mutuamente excluyentes y los argumentos de cada subcomando.

Las áreas existentes son `artifacts`, `contract`, `delivery`, `history`, `metrics`, `packets`, `recovery`, `runner`, `workspace`, `setup`, `checks` y `comment`. La superficie más amplia vive en `artifacts` con 19 subcomandos; `contract` mantiene seis acciones de primer nivel, `workspace` cuatro subcomandos, `history` tres, `setup` tres y `comment` dos. `checks` expone `run`; `delivery`, `metrics` y `packets` conservan su argumento de operación existente. `recovery` y `runner` siguen como parsers de opciones.

La captura detiene `argparse` al comenzar `parse_args`; así el inventario no prepara archivos, worktrees, procesos ni eventos. La prueba compara la salida de `cli_inventory()` con el fixture bloqueado y verifica las doce áreas.

## Bytes de los encoders

`tests/fixtures/scripts_encoding_contracts.json` almacena el valor de entrada determinista `{"x":1,"ñ":"café"}` y los bytes UTF-8 en hexadecimal que producen los encoders de base.

| Rol | Propietario actual | Formato observado |
|---|---|---|
| manifest | `review_artifacts._json_bytes` | JSON ordenado, indentación 2, salto LF final |
| layout | `review_layout._canonical` | JSON compacto ordenado, sin salto final; límite de 64 KiB |
| restart | `review_restart._json` | JSON compacto ordenado, sin salto final |
| trace | `review_trace.encoded` | JSON compacto ordenado, sin salto final |
| receipt | `review_check_receipts._json_bytes` | JSON compacto ordenado, salto LF final |
| setup | `review_setup._json_bytes` | JSON compacto ordenado, sin salto final |

Los tres formatos distintos de salto final son contratos; esta extracción no los unifica. La prueba invoca los encoders, no carga sus expectativas desde el fixture.

## Orden de locks observado

- `run_locks` elimina rutas duplicadas, ordena varios runs de forma estable y permite reentrada del mismo hilo.
- `session_claim_locks` agrupa sesiones por Git common dir, adquiere esos grupos por ruta normalizada y vuelve a verificar la identidad de cada sesión dentro del lock.
- La limpieza de un workspace entra primero a `session_claim_locks`; si la sesión está reclamada, después toma el lock del run propietario.
- `transfer_resources` toma los locks de source y successor antes de `session_claim_locks` para las sesiones seleccionadas.
- `restart` toma primero el lock del source. Al preparar/replay, la transferencia puede reentrar en ese lock y adquirir el del successor antes de bloquear las sesiones.

La dirección de estas dependencias es deliberada. Una extracción debe mantener la misma sección crítica y revalidación antes de efectos laterales.

## Resultado de la línea base en este host

La suite completa no terminó como una ejecución de baseline concluyente. En el primer intento, el `TEMP` predeterminado de Windows produjo errores `WinError 5` durante cleanup de `TemporaryDirectory`; el resumen fue `Ran 717 tests; FAILED (errors=864)`, así que no se tomó como resultado funcional válido. Al ubicar temporales dentro del repo, varias pruebas de ownership quedaron condicionadas por estar anidadas en el checkout. Usar la raíz scratch permitida y más corta evita ambos problemas de ruta.

Con ese scratch, se aislaron estas limitaciones previas al cambio:

- `git clone --local` no puede iniciar `sh.exe`: el sandbox deniega `NtCreateDirectoryObject` (`0xC0000022`). El test de dos clones falla al clonar.
- Dos pruebas de hardlinks fallan al llamar `os.link` con `WinError 5`. Las pruebas de symlink/junction que detectan la restricción los omiten con `WinError 1314` o acceso denegado.
- `test_receipt_preserves_literal_argv_and_previous_attempt` falló con `fatal: '$GIT_DIR' too big` cuando el scratch era más profundo y pasó al usar la raíz scratch más corta.
- El baseline de `unittest discover` se interrumpió durante `test_claimed_workspace_all_transfer_replacements`, que recorre cada reemplazo durable y cuatro rutas de replay. Los volcados de `faulthandler` mostraron avance por `safe_path`, `transfer_resources` y Git, sin una espera de lock. Se decidió reservar la suite completa para el gate de integración de Task 13.

Pruebas focalizadas ejecutadas con el código de base: `test_review_run_lock.py` pasó 3/3; el test de receipt anterior pasó 1/1 con el scratch corto. `test_script_characterization.py` pasó 4/4 después de introducir los helpers de test y fixtures. No se afirma que la suite completa de 717 tests haya quedado verde.

La ejecución final deberá reportar las limitaciones que sigan presentes en este host y conservar el comando completo como gate de integración.
