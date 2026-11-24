# Publicación de comentarios desde runs compactos sin sidecar

## Problema

Un run compacto de esquema 13 puede cerrar correctamente con checks y sin `check_disclosure_reference`. En CCR 3.6.0, `comment prepare` y `comment verify` reciben el registro y, si se proporciona, un catálogo explícito de divulgación. Con checks de esquema 12 o 13, el renderizador exige ese contexto. Si el run compacto no conservó un sidecar, reconstruirlo con `setup check-disclosure` requiere la sesión de captura original. El flujo de entrega `brief` y `full` ya resuelve esta ausencia con una explicación por check.

La base verificada el 24 de noviembre de 2026 es `main` en `0a459b6` (CCR 3.8.0). Esta versión ya incluye la proyección editorial y el borrador 4 del PR #36. La CLI todavía requiere `--input` y, para un registro de esquema 13 con checks, el par de divulgación. Las dos entregas conservan el fallback explicativo.

## Contrato de publicación

`comment prepare` y `comment verify` aceptarán `--run-dir <compacto>` como alternativa a `--input <review.json>`. Ambos argumentos son mutuamente excluyentes. Con `--run-dir`, el archivo retenido es la fuente de la divulgación. Se rechaza combinarlo con `--check-disclosure-context` o `--check-disclosure-sources`. Con `--input`, se conserva el contrato actual del par explícito y la validación del renderizador. Un `review.json` suelto no permite comprobar si hubo una referencia declarada.

El modo nuevo aplica a compactos completos de esquema 13 cuyo alcance ya admita el archivo compacto, incluidos PR/MR, rangos, commits y módulos. Rigen las condiciones de elegibilidad del modo compacto, incluida la persistencia completa para los perfiles `deep` y `extended`. La publicación en un destino remoto sigue su flujo habitual y requiere el contexto del destino que corresponda. `comment prepare` conserva la sesión de publicación propia y la escritura exclusiva del borrador dentro de ella. Puede ser una sesión nueva para la revisión retenida. `comment verify` es de solo lectura. La sesión de captura original no se necesita para ninguno de los dos comandos.

## Resolución de la divulgación

Se lee el compacto con `read_compact`. El lector valida la propiedad, el estado completo, el manifiesto, el inventario, los hashes, la identidad del registro y del alcance, las fuentes de evaluación y seguimiento cuando corresponda, la evidencia retenida y el informe canónico. Cada operación llama al lector una vez. El resolver trabaja con el registro y los bytes seleccionados que devuelve ese lector, sin reabrir archivos individuales. Cualquier fallo de lectura o validación se devuelve como error antes de resolver el fallback.

| Estado tras validar el compacto | Resultado |
| --- | --- |
| Referencia declarada y válida | Usar el sidecar retenido y sus pruebas referenciadas. Conservar los requisitos actuales de identidad inicial, integridad y procedencia de recursos. |
| Referencia declarada con nombre o tipo incorrecto, sidecar ausente o inválido, prueba ausente o inválida | Bloquear preparación y verificación. |
| Referencia ausente o nula y sidecar canónico presente en el inventario | Bloquear por selección incoherente. |
| Referencia ausente o nula, sidecar ausente y uno o más checks | Construir en memoria la misma divulgación explicativa que usa la entrega. |
| Referencia ausente o nula, sidecar ausente y cero checks | Usar la vista vacía habitual del renderizador, sin construir contexto. |

El fallback compartido usa el constructor existente, la identidad del head o snapshot del registro y un conjunto vacío de observaciones. La vista resultante queda vinculada al registro y contiene exactamente una fila por check en modo `explanation`, sin comandos, recursos ni referencias de reproducción. La proyección pública conserva los estados y resultados registrados, incluidas las ejecuciones externas, fallidas y los checks omitidos. Los contextos editoriales conservan las reglas de texto, redacción y atribución del renderizador. La ausencia de evidencia de divulgación nunca concede permiso para reconstruir o mostrar un comando.

Cuando hay sidecar, la selección para el comentario se limita al propio sidecar y las pruebas que referencia. Se aplican las mismas comprobaciones de procedencia que a la evidencia retenida. Una identidad de snapshot copiada del contexto no se considera una autorización de recursos. El flujo de entrega conserva su selección de fuentes y su comportamiento para archivos compactos y completos.

## Compatibilidad e integridad

- El borrador nuevo usa el esquema 4 y el renderizador editorial vigente, con las mismas huellas del registro y del cuerpo. La verificación con `--run-dir` vuelve a leer el compacto y a resolver la divulgación, compara la vista con la del borrador y exige que el cuerpo coincida con un render nuevo. La comparación local exige los bytes exactos. La opción `--remote` acepta CRLF y, para un borrador 4 con `--remote-transport gitlab`, también admite que el servicio omita exactamente el LF final.
- Los borradores 2 y 3 se verifican con `--input` y su política histórica. El diagnóstico del esquema 1 se conserva. Un borrador 4 existente puede verificarse con `--run-dir` si coincide con el registro, la divulgación y el render canónico del compacto.
- Se mantiene la exigencia de divulgación del renderizador para esquemas 12 y 13 con checks. Se conservan los contratos de `contract render-comment`, los archivos completos y el uso explícito de catálogos externos.
- La única escritura nueva que permite el flujo es el borrador en la sesión de publicación. No se persiste un sidecar sintético ni se migra el registro, el informe, el manifiesto, la evidencia o los borradores históricos. Los comandos de preparación y verificación no publican en remoto.

## Aceptación

1. Un compacto cerrado con checks y sin sidecar, cuya sesión original ya no está disponible, genera un borrador 4 verificable con una sesión de publicación nueva. El cuerpo muestra la explicación de cada check y excluye los comandos privados y la evidencia de reproducción.
2. Un compacto con sidecar válido conserva la divulgación acreditada. Si hay una referencia declarada inválida, un sidecar huérfano o falla la integridad del compacto, los dos comandos fallan. La preparación no deja un borrador.
3. Los contextos editoriales siguen aplicándose. Fallan un borrador de otro run y un cuerpo editado, incluso si se recalcula su hash. La igualdad del cuerpo por sí sola no sustituye la identidad del registro.
4. Los artefactos retenidos se conservan byte por byte, incluido un compacto producido con CCR 3.6.0. Las entregas y los borradores históricos siguen superando sus pruebas de regresión. La documentación conduce al harness por el modo de archivo cuando dispone de un compacto cerrado.

## Referencias del repositorio

- [Validador y lector del archivo compacto](../../../scripts/ccr/archive/compact.py)
- [Fallback de entrega](../../../scripts/ccr/reporting/delivery.py)
- [Preparación y verificación del comentario](../../../scripts/ccr/cli/comment.py)
- [Flujo documentado de publicación](../../../references/reporting/publication.md)
