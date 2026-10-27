# Validación de publicación de 3.1.0

La [re-review final del PR 30](https://github.com/omarfrancodev/comprehensive-code-review/pull/30#issuecomment-6395229222) declaró APROBABLE `9b128e8ba62535231dda3e9c08d4e466e3a0bdc9`, sin hallazgos confirmados. Verificó 220 pruebas focalizadas y confirmó la corrección de F011. Esa evidencia no se presenta como una ejecución global.

## Preparación en el mismo PR

La publicación se prepara dentro del PR 30 antes de su merge: changelog, versión de la skill, enlaces de instalación y descarga, ejemplo archive 8, expectativa de versión de la prueba de instalación y este registro. El árbol `scripts/` conserva exactamente el del head aprobado.

Se asigna 3.1.0 por la incorporación del tipo público `dispatch-identity` para recuperar omisiones históricas con evidencia verificable. Se mantienen archive 8/layout 2, final review schema 10, trace schema 1 y packet version 1. Los helpers anteriores deben actualizarse para leer el nuevo tipo. La historia genérica `agent/unchanged` conserva su significado y los archivos completos no se reescriben; no se presume compatibilidad del visor independiente.

## Validación del candidato

Se ejecutó una única suite completa después de actualizar todos los metadatos de versión del candidato:

```text
unittest.defaultTestLoader.discover(<tests>, pattern='test_*.py')
unittest.TextTestRunner(verbosity=2).run(suite)
Ran 816 tests in 2189.148s
OK (skipped=3)
```

Resultado: **813 aprobados, 3 omitidos, cero fallos y cero errores; exit 0**. Incluye ambas matrices completas de replay de transferencia/adopción, las regresiones F001–F011, el ejemplo archive 8 y la prueba de instalación de 3.1.0 desde cwd ajeno sin `PYTHONPATH`. La carga de módulos usa rutas absolutas y el runner cambia al cwd temporal corto antes de ejecutar las pruebas; no modifica fixtures, aserciones ni omisiones.

Las tres omisiones requieren un privilegio de symlinks no disponible en Windows:

- `test_review_artifacts.ArchiveTests.test_symlink_roots_inputs_and_archived_files_are_refused`.
- `test_review_lock_file_safety.LockFileSafetyTests.test_existing_final_symlink_is_refused_without_touching_target`.
- `test_review_lock_file_safety.LockFileSafetyTests.test_final_link_replacement_after_identity_check_is_refused`.

El resultado se añadió a este documento después de terminar la suite; no se cambió código ni se repitió la corrida global. Se comprueban nuevamente enlaces locales y formato del diff antes del commit de preparación.

La ejecución usa Python administrado y Git en Windows, sin `PYTHONPATH`, con bytecode deshabilitado y un directorio temporal exclusivo de ruta corta como TEMP, TMP y cwd. Se mantienen las aserciones y reglas de omisión de las pruebas; los repositorios y recursos usados son sintéticos. La validación no certifica ejecución POSIX ni un MR real.

## Empaquetado y publicación

El ZIP se genera desde el commit integrado mediante `git archive`, con LF, y contiene únicamente archivos versionados bajo `comprehensive-code-review/`. Antes de publicar se contrasta el inventario y cada archivo con los blobs de ese commit, se compilan en memoria todos los Python y se verifican desde la extracción las trece ayudas CLI, las pruebas de instalación/CLI, los enlaces locales y el ejemplo archive 8 completo.

Las notas de la release registran los resultados observados, el commit integrado y el SHA-256 del ZIP final; se adjunta `SHA256SUMS.txt`. La fecha de publicación del changelog se contrasta con `publishedAt` de GitHub convertido a `America/Mexico_City`. La publicación no requiere un commit posterior de preparación.
