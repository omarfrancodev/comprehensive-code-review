# Validación de publicación de 3.0.0

La re-review del [PR 29](https://github.com/omarfrancodev/comprehensive-code-review/pull/29) declaró APROBABLE `c899ff4708394e2e89adb4c417f1417f9e8fb9c2`, con F001 resuelto y cero hallazgos confirmados. Las cinco pruebas afectadas pasaron sin `PYTHONPATH` en la re-review.

La [validación de implementación](2026-10-21-scripts-modularity.md) registra la suite completa de ese árbol: 752 casos en 3494.885 s, `OK (skipped=7)`, sin `PYTHONPATH`; ambas matrices de replay pasaron. Los siete skips corresponden al entorno Windows/Git Bash y están documentados allí.

## Preparación de publicación

Se asigna 3.0.0 por la ruptura de comandos e imports legacy. Se actualizan changelog, versión del skill, enlaces de descarga, ejemplo archive 8 y la expectativa de versión del test de instalación. El código de `scripts/` conserva el árbol aprobado. No se repitió la suite completa después de estos cambios de metadatos.

Comprobaciones sobre la preparación final, con `PYTHONPATH` sin definir:

| Comprobación | Resultado |
|---|---|
| `test_script_cli.py` | 4/4, OK, 10.556 s; copia instalada con espacios desde cwd ajeno y ayudas de las doce áreas. |
| `test_reference_layout.py` | 1/1, OK, 0.100 s; ubicaciones y enlaces locales. |
| `test_review_recovery_followup.py -k extracted_documented` | 1/1, OK, 7.546 s; comandos documentados archive 8 de extremo a extremo. |

El paquete se genera del commit integrado con `git archive`, fijando LF mediante configuración del comando. Antes de publicar se contrasta el inventario y cada archivo con sus blobs Git, se comprueba la compilación de todos los Python y se ejecutan desde la extracción los enlaces locales, el ejemplo archive 8 y las trece ayudas (raíz y doce áreas). Las notas de la release registran los resultados observados y el SHA-256 del ZIP final.

Se mantienen archive 8/layout 2, final review schema 10, trace schema 1 y packet version 1. La guía de migración documenta la sustitución de `scripts/review_*.py` por `python scripts <área> ...`. La validación corresponde a Windows y no certifica ejecución POSIX.
