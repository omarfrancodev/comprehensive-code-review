# Persistencia verificable, procedencia de checks y entrega portable

## Objetivo y alcance aprobado

Corregir la sanitización que puede invalidar una entrega y reforzar dos garantías: no declarar cierre durable sin resultado retenido y conservar la procedencia de ejecuciones nuevas cuando corresponda. El usuario solicitó implementar las tres mejoras mediante el flujo habitual: worktree desde main, especificación, plan, implementación, verificación y PR para revisión humana.

Base: main `eba4c54c4d40df7a877b22f79c572c4272b90eec`, release 2.10.0. Rama `fix/review-persistence-delivery`, en `.worktrees/review-persistence-delivery`. Esta especificación propone preparar 2.11.0 pendiente; no autoriza merge, tag ni publicación antes de revisar el PR.

No modificar los archivos de reviews existentes, comentarios remotos, instalaciones externas, configuración de harness ni el visor independiente. No añadir sondeos, agentes de auditoría, mediciones, heartbeat o un registro por cada comando de exploración.

## Evidencia y límites del diagnóstico

- `prepare`, `record-event` y `retain` son operaciones separadas. Una traza con hitos terminados no produce por sí sola el informe, el JSON final ni las evidencias.
- El gate de fuentes schema 8 rechaza selección inicial posterior al trabajo, fuentes faltantes y contradicciones del perfil. Estos errores son compatibles con un run prepared/processing que conserve únicamente sus archivos iniciales.
- `close` ya rechaza archivos finales ausentes. No eliminar esa protección ni presentar el problema como ausencia de toda validación; mejorar el gate final y las instrucciones de respuesta/reanudación.
- `cierre.executors` se proyecta desde `--context-input`; registrar temporales o eventos no completa automáticamente esa lista. Un evento también admite executor null. Los dos registros tienen propósitos distintos.
- `_Projection.value` sanitiza cadenas estructurales y `_Projection.text` reemplaza textos de comandos globalmente. Casos sintéticos inicialmente válidos producen errores de perfil, estado o ID después de proyectar.
- De 34 cierres locales inspeccionados, todos tenían informe y JSON final. No se identificó el run exacto del primer síntoma. El refuerzo cubre las causas demostradas; no atribuye una causa concreta a ese caso sin su ruta/error.
- Las revisiones 2.10.0 con schema 7 observadas preceden la publicación de esa versión. La etiqueta de versión suministrada al prepare no prueba qué revisión de los helpers se ejecutó.

## Alternativas y decisión propuesta

1. **Recomendación: proyección tipada y check con procedencia explícita en final schema 9.** Permite verificar las relaciones sin inferir ejecución desde palabras o statuses. Conserva lectura histórica, pero requiere que consumidores acepten schema 9.
2. Mantener schema 8 y añadir únicamente información al contexto interno: menos impacto externo, pero la relación del check con su ejecución no viaja de forma estructurada y el gate depende de un segundo contrato implícito.
3. Cambiar solo instrucciones: evita cambiar contratos, pero deja la colisión de sanitización y las omisiones de procedencia sin una garantía mecánica suficiente.

La opción 1 mantiene archive schema 6, packet schema 1 y trace schema 1. No migrar schemas anteriores ni reinterpretar como defectos los datos que legítimamente no existían en ellos.

## 1. Proyección portable por campo

Separar campos estructurales, prosa, comandos y referencias mediante rutas semánticas explícitas. No introducir filtros de palabras para intentar reconocer enums o identidades.

- Copiar sin sanitización IDs, enums, flags, versiones/snapshots, identidades de commits, relaciones entre IDs y los nombres/IDs de procedencia necesarios para validar el contrato. La proyección no inventa una nueva revisión ni nuevas identidades de ejecución.
- Esa copia no autoriza filtrar datos privados: si una identidad estructural contiene una ruta privada y no puede preservarse sin divulgarla, rechazar la entrega antes de escribir con un diagnóstico del campo, sin incluir su valor. No alterar IDs canónicos o versiones para disfrazar el problema ni tratar identidades como prosa.
- Omitir cada campo de comando mediante el marcador actual. Redactar sus apariciones en la prosa sin aplicar esa sustitución a campos estructurales. Mantener las reglas actuales de rutas privadas y URLs en los campos donde corresponden.
- Tratar referencias/localizadores por su semántica. Conservar URLs públicas válidas y ubicaciones relativas al repositorio. Sustituir referencias internas no distribuidas por labels de procedencia estables; la misma referencia fuente produce la misma representación.
- Mantener binding de revisiones anteriores, referencias de checks y relaciones de ejecución. La lectura de la entrega verifica estructura; la resolución de fuentes reales corresponde al archivo original.
- Proyectar únicamente el resultado portable; no modificar el archivo retenido ni relajar la validación para hacer pasar datos corruptos.
- Full y brief usan la misma proyección. Brief sigue validando su fuente y el resultado que renderiza, aunque no entregue review.json. Completar lecturas, proyección y renderizado antes de crear el destino.

Una ruta desconocida de un nuevo campo debe revisarse explícitamente al ampliar el contrato. No convertir todas las cadenas a prosa como fallback inadvertido. Incluir regresiones para hashes/IDs que coincidan con comandos, estados, perfiles, URL/rutas y relaciones de re-review.

## 2. Procedencia explícita de checks nuevos

Final schema 9 conserva los campos de schema 8 y añade a cada check `execution: {kind, executor}`. La información se recopila en el ledger ya existente; no se infiere desde `command`, ni se añade otro archivo obligatorio.

| kind | Significado | executor |
|---|---|---|
| local | Build, test, instalación, reproducción u otra validación ejecutada localmente que escribe o requiere el entorno aislado propio | ID del entorno propio si se ejecutó; puede ser null cuando blocked/not_run y no llegó a disponer de entorno |
| static | Inspección de código/diff u otra comprobación de solo lectura sin entorno de ejecución que deba registrarse | null |
| external | Observación de un resultado ejecutado por un sistema externo, por ejemplo CI | null; la referencia identifica la fuente externa |
| reused | Evidencia de una comprobación anterior, sin nueva ejecución en este run | null; la referencia y revisión conservan la procedencia histórica |

Reglas:

- `reused=true` requiere kind reused, y viceversa; conservar los gates de referencia/revisión/justificación existentes.
- Local passed/failed exige un executor no vacío. Local blocked/not_run no se presenta como ejecución terminada; si declara un executor, también debe existir en la procedencia del run.
- External passed/failed exige una referencia a la fuente observada. No copiar un ID de CI a la lista de worktrees propios ni atribuir el resultado al coordinador.
- El ID de executor debe encontrarse en context.executors y en el cierre proyectado. El executor permite comprobar método, raíz Git/repositorio, revisión/snapshot, registro del recurso y estrategia de dependencias mediante los gates existentes.
- La versión del check debe corresponder a la del executor. Para checks sobre snapshots locales, conservar el vínculo exacto con el snapshot; para baseline, usar su HEAD real y snapshot null.
- Varios checks pueden compartir un entorno. Un nuevo contexto de reviewer no exige automáticamente otro worktree: los revisores de solo lectura pueden compartir inputs fijados.
- Un check estático, externo, reutilizado o no ejecutado no provoca la creación de un executor ficticio. Una revisión sin checks conserva la lista vacía como caso válido.
- El campo de ejecución es procedencia interna. No agregar worktrees, rutas o mecánica de ejecución al comentario público. La entrega portable mantiene IDs/tipos y las relaciones necesarias, omitiendo las evidencias y rutas del cierre original.

Los schemas 1–8 conservan sus campos y validación histórica. Lectura, delivery y re-review históricos no deducen execution ni modifican el archivo. Nuevo resultado schema 9 permite verificar esta garantía; un archivo antiguo con executors vacío no se corrige retrospectivamente.

## 3. Retención y cierre durable

Conservar la separación entre juicio de código, retención e higiene de recursos. Un veredicto aprobable no establece que la persistencia haya terminado.

- La selección inicial se registra antes del trabajo; los aliases se normalizan al interpretar la petición. Usar el perfil explícito fijo o la selección automática y su historial observado, sin insertar transiciones después para superar el gate.
- Las nuevas instrucciones de retención usan una expectativa explícita de schema 9. Proponer `retain --expected-schema 9` como comprobación del resultado suministrado, sin confiar en la cadena skill_version del cierre. Su ausencia mantiene compatibilidad de llamadas históricas; las nuevas invocaciones CCR deben suministrarla.
- Antes de escribir el resultado, validar contrato, alcance, identidad, perfil/fuentes, procedencia de checks y evidencia seleccionada. Schema 9 requiere el contexto de ejecución ya existente, incluso si executors está vacío por no haber ejecuciones locales.
- No imponer logs o reproducciones a una inspección estática. Retener las fuentes necesarias del resultado y del gate; no retener todos los archivos de scratch por defecto.
- Con un gate fallido, conservar el run exacto y sus recursos propios, comunicar la fase y el error observado y no anunciar retención ni cierre exitosos. Reintentar tras corregir la causa; no cambiar de run silenciosamente, degradar el perfil a posteriori o eliminar recursos para evadir el gate.
- En close, aplicar el gate completo de resultado retenido antes de finalizar. Al terminar, el coordinador obtiene una comprobación read-only de estado completo y evidencia íntegra: `validate --require-complete`, que implica require-retained.
- Require-complete exige state complete, retained true, cleanup complete/not_needed, ausencia de residuals declarados y coherencia del estado de recursos del resultado con cierre. No escribir eventos ni recuperar transacciones en una validación read-only.
- Pending cleanup permanece closing y se comunica como pendiente, aunque el informe y JSON ya estén retenidos. Prepared/processing/retaining no son estados de cierre durable. Mantener recuperación transaccional de operaciones interrumpidas y no crear un estado falso de éxito.
- Para limitar operaciones repetidas, el gate final reemplaza la comprobación genérica de cierre del coordinador; no añadir un nuevo barrido, auditor ni otra review.

Un helper no puede impedir que el agente abandone el run o afirme algo incorrecto en prosa. Las garantías combinan validación mecánica de sus entradas/estados y una instrucción precisa: la respuesta final distingue revisión realizada, resultado retenido y cierre pendiente/completo usando el estado observado.

## Compatibilidad y publicación

- Preparar versión 2.11.0 pendiente y explicar final schema 9 en changelog/uso. Mantener enlaces a 2.10.0 como última release publicada hasta autorizar la siguiente publicación.
- Mantener archive 6, trace/packet 1 y lectura de final schemas 1–8. Las expectativas de schema son específicas de una nueva operación; no invalidan registros cerrados por haber sido emitidos con una versión anterior.
- El visor independiente debe admitir final schema 9. Registrar esa necesidad sin cambiar su repositorio ni afirmar compatibilidad no verificada.
- No tocar ni entregar nuevamente archivos de reviews del usuario para validar estos cambios. Las reproducciones usan fixtures sintéticos y temporales propios.

## Criterios de aceptación

1. Un registro válido sigue válido tras full/brief aun si un comando coincide con perfil, status, ID o una parte de una identidad; enums e IDs permanecen iguales.
2. Comandos/rutas privadas quedan omitidos en los campos de presentación correspondientes; URLs públicas y ubicaciones relativas útiles se conservan. Las relaciones de re-review/ejecución permanecen válidas y la fuente retenida conserva sus bytes.
3. Schema 9 rechaza local passed/failed sin executor y retención rechaza executors inexistentes o con revisión/snapshot incompatible, antes de copiar el resultado.
4. Checks estáticos, CI externos, reutilizados y no ejecutados admiten ausencia de executor según las reglas; los mismos casos históricos conservan validación y representación sin migración.
5. Un run con eventos pero sin resultado no supera require-complete. Un cierre pending tampoco. Un run cerrado válido sí pasa sin alterar bytes o eventos.
6. Una interrupción de retención no se declara completa y conserva recuperación. Destinos ajenos, evidencia modificada, ownership y temporales siguen protegidos.
7. La suite completa, pruebas focalizadas RED→GREEN, AST, enlaces modificados y CLI de los helpers afectados pasan; documentar omisiones reales de plataforma.
8. PR describe los tres problemas, cambios de contrato y validación efectiva. Esperar aprobación humana antes de merge/release/limpieza del worktree de desarrollo.

## Revisión de esta especificación

Contraste inline: conserva el alcance de las tres mejoras, diferencia inspección/CI/reuso de ejecución propia y evita migraciones. Los gates no seleccionan perfiles ni prueban la verdad de las observaciones. No hay otro sistema de almacenamiento o auditoría. La implementación empezará después de revisar esta especificación y el plan escrito.

Preparación verificada: suite base de 292 pruebas en 209.807 s; 291 aprobadas y una omitida por permisos de symlinks en Windows. Worktree propio desde main actualizado, `.worktrees/` ignorado e identidad Git `omarfrancodev` / `fofe2803@gmail.com`. Seguimiento inline bajo el fallback opcional del controlador de tareas: preparación completada; especificación escrita y revisión humana pendiente; plan e implementación pendientes.
