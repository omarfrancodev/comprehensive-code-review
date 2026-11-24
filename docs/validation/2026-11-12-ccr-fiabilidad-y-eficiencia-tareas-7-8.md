# Validación de las tareas 7 y 8 de CCR

Se probó la selección técnica antes de evaluar capacidad. Los hechos de alcance eligen `deep` para el mecanismo que requiere independencia, aunque el harness tenga cero slots. Un intento de reducir el perfil usando el impedimento observado se rechaza antes de cambiar el historial. Una reducción con evidencia técnica nueva sigue disponible. Las selecciones explícitas conservan la autoridad del usuario.

La retención guiada de final 13 exige una limitación material de ejecución cuando falta una obligación independiente. El fixture conserva el plan independiente de `deep`, registra el fallback observado, indica verificación no disponible y produce evidencia insuficiente. Quitar la fuente del fallback o intentar sustituir la independencia por un contexto ordinario hace fallar la validación. Un `standard` limpio conserva verificación omitida cuando sus obligaciones no requieren un verificador.

La selección de persistencia conserva el modo completo para `deep` y `extended`. Preparar compacto con esos perfiles falla antes de reservar. Una obligación independiente descubierta después de preparar un compacto promovió el run a completo y actualizó el perfil antes de registrar el trabajo dependiente.

| Cuerpo observado | Verificación local | Remota ordinaria | GitLab con draft 4 |
|---|---|---|---|
| UTF-8 idéntico | Acepta | Acepta | Acepta |
| CRLF con el mismo contenido | Rechaza | Acepta | Acepta |
| Falta solo el LF final | Rechaza | Rechaza | Acepta |
| CRLF y falta solo el LF final | Rechaza | Rechaza | Acepta |
| Texto, enlace, acento, puntuación, espacio o byte adicional o perdido | Rechaza | Rechaza | Rechaza |

El CLI leyó cuerpos de prueba como archivos UTF-8. El recibo remoto conserva el SHA-256 del borrador canónico y el del cuerpo observado antes de normalizar, además del transporte y las transformaciones exactas. Un cuerpo inválido en UTF-8 se rechaza. Los fixtures de borradores 2 y 3 conservan la política histórica de comparación. La verificación fue local con cuerpos simulados de lectura remota.

Pasaron 346 casos en cuatro grupos de regresión y otros dos casos de integración ejecutados por separado. El host omitió dos pruebas, una por la sincronización Win32 de Git Bash y otra por permisos de enlaces duros. La regresión incluyó perfiles, recuperación, retención, promoción, privacidad, disclosure, render editorial, borradores históricos y el contrato del CLI.

[Plan](../superpowers/plans/2026-11-12-ccr-fiabilidad-y-eficiencia.md) · [Pruebas de perfil](../../tests/test_review_profile_topology.py) · [Pruebas del CLI de comentarios](../../tests/test_review_comment.py)

## Lectura real de una nota de GitLab

La nota existente facilitada para la prueba se recuperó mediante una consulta de solo lectura. Su cuerpo UTF-8 no terminaba en LF. Se regeneró el borrador 4 con el registro retenido y los contextos de la publicación original. Los hashes del registro y del cuerpo canónico coincidieron con el recibo original, y el hash del cuerpo de GitLab coincidió con el observado en aquel recibo.

El CLI devolvió `verified: true` con `--remote --remote-transport gitlab` y registró únicamente `gitlab_missing_terminal_lf`. La comparación remota genérica rechazó el mismo cuerpo. El selector GitLab también rechazó una copia local con un espacio añadido. La prueba utilizó una sola nota existente y no modificó el MR.
