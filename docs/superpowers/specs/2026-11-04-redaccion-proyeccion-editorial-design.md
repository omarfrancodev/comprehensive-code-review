# Redacción pública fiel y proyección editorial de hallazgos

**Estado:** implementado y validado el 2026-11-04; resultados y tres omisiones por permisos de symlinks en el [informe de validación](../../validation/2026-11-04-redaccion-proyeccion-editorial.md). **Base local:** `main`, commit `0b1d5203b77585c66740bbb5eddebd1a941d4c9b`, CCR 3.6.0. **Worktree:** `.worktrees/redaccion-proyeccion-editorial`, rama `fix/redaccion-proyeccion-editorial`. La base es la rama local comprobada; esta tarea no consulta ni sincroniza el remoto.

## 1. Propósito y alcance

Corregir los falsos positivos que corrompen identificadores y frases al redactar un comentario y permitir una presentación editorial de los hallazgos vinculada al registro fuente, incluso después de cerrar la revisión. Se conserva el archivo original completo o compacto, sin cambiar su contenido, hashes, estado, evidencia ni historial. Preparar otra presentación no requiere repetir discovery, verificación de código ni checks cuando el resultado sigue siendo aplicable.

El alcance incluye las funciones públicas de presentación, `contract render-comment`, `comment prepare/verify` y la política de saneamiento compartida con entregas. La edición de hallazgos se aplica sólo a audiencias públicas; los informes privados y las entregas full/brief mantienen el registro fuente. El saneamiento correcto sí debe proteger todas las salidas que ya usan esa política. El API de handoff público debe usar la misma vista editorial cuando se le suministre; no se añade una modalidad CLI ni se activa una entrega implícita.

No se cambia el proyecto revisado, el veredicto, la prioridad, las condiciones técnicas de aceptación, la autoría, la política de menciones ni los schemas finales 1–13. No se publica ningún comentario, se migran archivos históricos ni se inicia una revisión nueva por un problema puramente editorial. La autorización posterior del usuario cubre implementación y validación; commit, push, release y publicación quedan fuera de esta ejecución.

## 2. Diagnóstico que fundamenta el diseño

El incidente se comprobó contra un resultado schema 13 y un draft 3 producidos por CCR 3.6.0. No se copiarán sus artifacts, personas, repositorio ni reproducciones privadas al corpus del producto.

| Entrada legítima | Resultado defectuoso observado | Causa |
|---|---|---|
| `jobs_service.py:_publish_pending_job` | `jobs\_service.p[ruta privada]` | El escape Markdown introduce `y:\`; el filtro posterior lo interpreta como ruta Windows. |
| `sin comprobar propiedad por token: puede borrar la reserva` | `sin comprobar propiedad por token=[omitido] borrar la reserva` | Una expresión global interpreta `puede` como valor de credencial sin contexto de asignación. |

Los dos patrones de redacción ya existían en 3.5.0. La matriz y la persistencia proporcional no son su causa. `render.py` crea Markdown; `public_projection()` filtra el cuerpo completo después. `safe_text()` mezcla detección de rutas, valores conocidos y asignaciones léxicas. La corrección debe distinguir el texto original de su representación.

Por separado, el registro final puede conservar referencias provisionales y detalles de reproducción dentro de `scenario` o `evidence.details`. Los contextos existentes permiten resumir checks y flujos, pero no esos campos de hallazgos. El helper de comentario acepta cuerpos deterministas con defectos editoriales: su verificación prueba integridad, no fidelidad semántica ni autorización.

## 3. Alternativas y decisión de diseño propuesta

1. **Parchear el cuerpo generado o el registro cerrado.** Rompe el vínculo verificable o la inmutabilidad; descartado por el requisito del usuario.
2. **Ampliar únicamente expresiones regulares y limpiar todo al final.** Es menor en código, pero mantiene la confusión entre Markdown, prosa y credenciales y no permite corregir un hallazgo después del cierre.
3. **Saneamiento sobre fuentes tipadas y contexto editorial separado.** Recomendado: aplica privacidad antes de introducir escapes, conserva una verificación final acotada y permite presentar la misma conclusión sin reescribir el archivo original.

La tercera opción, los nombres de interfaces y los límites de este documento son propuestas del autor para revisión; no se atribuyen al usuario decisiones que aún no ha aprobado. El usuario autorizó proceder con esta implementación el 2026-11-04; no se amplía esa autorización a commit, publicación o integración.

## 4. Invariantes

- Python 3.10+ y biblioteca estándar; sin dependencias nuevas.
- Los artifacts originales, completos o compactos, y sus hashes permanecen idénticos byte a byte.
- El registro fuente validado sigue siendo la autoridad para identidades, estados, evidencia y juicio técnico.
- No se ejecutan comandos ni se consultan servicios para mejorar la redacción o inferir secretos/procedencia.
- Los valores sensibles conocidos se ocultan también si aparecen en texto editorial, con sus formas codificadas y solapamientos ya soportados.
- El contexto editorial no acredita comandos, recursos, ejecuciones, cuentas ni resultados.
- Los borradores históricos no se reescriben; su verificación conserva la política de representación que les corresponde.
- La fidelidad semántica y la autorización de publicación requieren la pasada editorial existente; un hash correcto no las demuestra.

## 5. Saneamiento de fuentes y falsos positivos

### 5.1 Separar entrada y representación

La ruta nueva trata por separado prosa, referencias/URLs, localizaciones, comandos acreditados y campos estructurales. La prosa se sanea sobre el texto original, después de seleccionar su resumen editorial y antes de `markdown_text()`. Las localizaciones conservan las reglas tipadas existentes. Un escape agregado por Markdown no puede convertirse en evidencia de una ruta o credencial.

El conjunto de valores sensibles se reúne **antes** de aplicar sustituciones editoriales. Además de comandos y proofs seleccionados ya soportados, el clasificador examina los textos originales seleccionados de `presentation.subject`, `verdict_reason`, `description.details`, `reservations`, `rereview.details/previous_title`, todos los textos de hallazgos (incluidos `blocking_reason`, evidencia y sección), checks y cobertura, y todos los textos suministrados por los contextos públicos. Sólo aprende asignaciones de credencial explícitas según §5.2; una referencia narrativa a un token no enseña la siguiente palabra como secreto. La clasificación de comandos sigue su camino estructurado, y no se recorre el archivo, logs ni historia para buscar más fuentes. El mismo conjunto protege todas las secciones públicas y la entrega que aplique esta política. Si una evidencia original contiene `token=SECRETO`, sustituirla por `La respuesta contiene SECRETO` no revela ese valor, aunque no figurara en comandos/proofs. Un valor sensible que coincida con una identidad estructural impide la proyección en vez de reescribir la identidad.

La función pública de contratos mantiene `safe_text(value, secrets=(), *, redact_paths=True, syntax='prose')`. `syntax` admite exactamente `prose` y `structured`; los consumidores de comandos y representaciones de credenciales deben indicar `structured`. Se crea `ccr/contracts/disclosure_text.py` para las reglas léxicas compartidas y su clasificación, con `sensitive_values_from_text(value: str, *, syntax='prose') -> set[str]`, sin importar módulos de reporting desde contracts. En reporting, `public_sensitive_values(record, view=None, sources=None, *, editorial_texts=()) -> set[str]` compone las fuentes existentes con los campos enumerados y los textos editoriales ya validados; no necesita un registro proyectado. La recolección reutiliza esa clasificación y el límite de trabajo del texto seleccionado, y falla antes de emitir una proyección parcialmente analizada. No se reescribe el parser de comandos ni las reglas del lexer. Al implementar, el proyector de spans de delivery se extrae a `reporting/text_projection.py` como unidad pura compartida; delivery conserva su alias y se verifica su corpus de regresiones.

Después de construir Markdown se permite defensa en profundidad para valores sensibles conocidos y URLs sensibles, preservando el manejo de escapes y codificaciones. Esa etapa no vuelve a interpretar barras introducidas por Markdown como rutas ni aplica un detector global de pares `token: palabra`. Las etiquetas y textos fijos del renderer quedan explícitamente clasificados; no se incorpora un fragmento dinámico sin sanear.

### 5.2 Credenciales frente a prosa

Se conserva la detección de valores conocidos en cualquier posición y la interpretación estructurada de URLs con credenciales, argumentos sensibles, asignaciones con `=`, JSON con claves de credencial, encabezados de autorización y valores explícitamente entrecomillados. No se decide por listas de palabras españolas como `puede`, ni por entropía, longitud o apariencia de un valor.

Para un valor desconocido, `token: valor` sin comillas tiene autoridad de asignación cuando aparece como campo estructurado: al inicio de una línea, tras el marcador de una lista de campos, dentro de JSON o dentro de código/comando explícito. En prosa continua, un nombre de concepto seguido de dos puntos y espacio no establece por sí solo una credencial. `por token: puede borrar` se conserva. `token=demo`, `token:"demo"`, `{"token": "demo"}`, un campo de línea `token: demo` y `Authorization: Bearer demo` se ocultan. El valor aprendido `demo` se oculta en cualquier posición, aunque no haya clave. Para un valor JSON entrecomillado se conservan tanto su grafía léxica como su string JSON decodificado válido, sin ejecutar texto.

Las APIs reciben la sintaxis de su fuente; no se transforma una fuente estructurada en prosa para evitar una redacción. Las claves escapadas/concatenadas de comandos, las copias codificadas, las URLs privadas y los límites de trabajo conservan sus garantías actuales. No se promete reconocer secretos arbitrarios y sin marcar dentro de lenguaje natural; una fuente identificada como credencial sigue siendo estructurada o suministra sus valores sensibles.

### 5.3 Casos de aceptación de privacidad

Conservar exactamente el contenido visible de `jobs_service.py:_publish_pending_job`, sus variantes con números de línea, rutas relativas del repositorio y Unicode. Ocultar rutas Windows/UNC/POSIX/file privadas reales y credenciales reales antes y después de añadir Markdown. Mantener delimitadores y vecinos HTTP legítimos según las pruebas existentes de spans, autoridad local, comandos completos y valores solapados. El contexto editorial no puede utilizar comillas, HTML, Markdown ni codificaciones para restituir datos privados.

## 6. Contexto editorial de hallazgos, versión 1

Se añade el argumento opcional `finding_publication_context` y la opción `--finding-publication-context <archivo.json>` en preparación de comentario y `contract render-comment`. No se sobrecarga `publication_context`, reservado para limitaciones históricas.

Forma exacta de la cabecera: `{schema_version: 1, source_sha256: <digest>, findings: [<ediciones>]}`. `source_sha256` es `publication_digest(record)` del registro original íntegro, nunca del registro proyectado. JSON usa el algoritmo canónico existente: UTF-8, `ensure_ascii=False`, claves ordenadas, separadores compactos y rechazo de NaN. Se calcula además el digest canónico del contexto normalizado para ligarlo al nuevo draft.

Cada edición es `{id, ...campos_editados}`. Se permite una entrada única por ID público existente (`confirmed` o `unresolved`); requiere al menos un campo editado. Los campos opcionales admitidos son `title`, `scenario`, `impact`, `correction`, `blocking_reason` y `evidence`. Los campos ausentes heredan el original. Los textos suministrados son strings UTF-8 no vacíos; `blocking_reason` sólo se edita cuando el original lo tiene. No se acepta null para suprimir una razón. `evidence` es una lista no vacía de `{index, summary}`, con índices originales de base cero, únicos, dentro de rango y resumen no vacío. Cada índice omitido conserva su detalle original.

La edición es **dispersa**: puede cambiar sólo dos detalles de evidencia sin duplicar todos los hallazgos ni la revisión. Omitir un hallazgo de `findings` no lo oculta. No se aceptan hallazgos nuevos, rechazados, IDs duplicados, índices booleanos, campos extra, versiones desconocidas ni hashes discrepantes. Las filas se normalizan al orden del registro y sus evidencias al orden de índice antes de calcular el digest del contexto.

Límites iniciales: 256 KiB de JSON UTF-8 original y de JSON canónico normalizado; 16 KiB UTF-8 por texto editado. No hay límite nuevo menor sobre el número de hallazgos del registro: el tamaño acota el contexto y se puede editar un subconjunto. El lector acotado rechaza UTF-8 inválido, claves JSON duplicadas y valores no finitos; los APIs de objetos comprueban asimismo textos y tipos sin coerción. Rechazar antes de producir salida; el límite vigente de 2 MiB para el cuerpo también se aplica en prepare y verify.

Ejemplo sintético; el digest de ceros ilustra la forma y debe sustituirse por el real:

```json
{
  "schema_version": 1,
  "source_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
  "findings": [
    {
      "id": "F003",
      "evidence": [
        {"index": 0, "summary": "El bloqueo de publicación se renueva una sola vez y puede expirar antes de finalizar el encolado."},
        {"index": 1, "summary": "La limpieza puede borrar la reserva de otro intento porque no comprueba quién la creó."}
      ]
    }
  ]
}
```

### 6.1 Qué conserva la vista

`project_public_findings(record, context=None) -> list[dict]` devuelve copias; no muta argumentos ni crea un nuevo registro de revisión. Un validador independiente normaliza el contexto antes de aplicar las ediciones. El renderer valida y usa el **registro original** para disclosure, hashes, cantidades, orden, prioridad, status, blocking, tipo, origen, localización, check IDs y referencias.

Cada evidencia sigue ligada al mismo índice, `kind` y `check_id`. No se sustituyen reproducciones por ejecuciones de proyecto ni se reclasifica una evidencia mediante prosa. Suprimir mecánica interna permite expresar qué se comprobó y qué ocurrió; no autoriza afirmar una comprobación nueva. Los campos estructurales no son editables: su presencia en un contexto es un error, aunque el valor sea igual al original.

El contexto propio del handoff también participa en la recolección global previa. Sus enlaces derivados de `source_report` sólo se construyen desde una URL HTTP(S) que supere la política de referencias públicas; una ruta local puede quedar omitida en la cabecera y nunca reaparecer como destino derivado.

La vista se usa en todos los lugares donde aparece un texto editado: título, escenario, impacto, evidencia, corrección, motivo de bloqueo, resumen de incertidumbres y condiciones de aceptación derivadas de `correction`. Las condiciones siguen existiendo para todos los bloqueantes originales. El handoff público que recibe el contexto usa la misma vista para sus campos visibles; el privado rechaza el argumento. La ausencia de contexto conserva los textos fuente, sujetos a saneamiento.

### 6.2 Límite de la validación

No hay comparador semántico ni blacklist global de `D1`, `V1`, `db3` o nombres de scripts. Esos textos pueden ser legítimos en otros productos. El coordinador traduce las referencias de procedencia conocidas a evidencia comprensible y realiza una sola pasada editorial sobre el comentario completo. Un contexto estructuralmente válido todavía puede mentir: el helper no acredita su fidelidad ni cambia el veredicto. Si se descubre un error técnico del registro, corresponde una corrección/revisión enlazada mediante el flujo existente, no un cambio editorial que lo esconda.

## 7. Draft 4 y compatibilidad

Los nuevos `comment prepare` emiten **draft 4**, con o sin edición, para fijar la nueva política de saneamiento. La forma contiene todos los campos previos: `schema_version`, `source_sha256`, `publication_context`, `check_publication_context`, `coverage_publication_context`, `check_disclosure_context`, `body`, `body_sha256`; y añade `render_policy`, `finding_publication_context`, `finding_publication_sha256`.

- `render_policy` es exactamente `publication-editorial-v1` y es asignado por el helper; no hay opción CLI para elegir la política histórica.
- `check_disclosure_context` es el view validado o null cuando no corresponde; mantiene todas sus pruebas y el digest de los bytes seleccionados.
- `finding_publication_context` contiene el contexto normalizado o null; su digest es el canónico de ese objeto o null, respectivamente.
- `body_sha256` sigue siendo SHA-256 de los bytes UTF-8 exactos de `body`.

`verify` despacha por versión, valida los campos exactos, el registro original, contexto/digest, disclosure, política y cuerpo reconstruido. Para draft 4 utiliza el contexto embebido y exige que ya esté normalizado; no necesita un archivo editorial externo después de preparar. Un cambio de contexto sin nuevo cuerpo/digest falla. Recalcular un hash no acredita semántica ni autorización. `remote=True` tolera sólo CRLF→LF para comparar el cuerpo observado; local conserva comparación exacta. Las versiones desconocidas se rechazan.

Los drafts 2 y 3 conservan su forma y se verifican con una ruta explícita de compatibilidad que reproduce la política de la base 3.6.0, incluidos los dos resultados antiguos. Esa ruta conserva también el saneamiento del view de disclosure (comando, recursos y explicación), la recolección antigua de valores y las dependencias transitivas que determinan sus bytes; congelar únicamente el filtro final sería insuficiente. La validación de fuente, hashes y procedencia sigue siendo obligatoria. Como sidecar 1 no llevaba una versión de saneamiento, los lectores durables reconocen la reconstrucción exacta actual o la histórica bajo el mismo gate de recursos; el lector de drafts 2/3 selecciona explícitamente la histórica. No se aceptan filas arbitrarias, ni se sustituye proof por hash. Su éxito no declara el texto apto para publicar; se recomienda regenerar un draft 4 si se necesita corregirlo. Draft 1 conserva `stale_draft`. No se transforman borradores históricos ni se cambia su `source_sha256`. El módulo `ccr/reporting/publication_legacy.py` encapsula sólo la proyección necesaria para esos lectores; los nuevos prepare no pueden utilizarla.

La compatibilidad no se resuelve aceptando únicamente el hash guardado ni saltando el rerender. Los fixtures históricos se capturan de la base antes de modificar código y deben seguir verificándose, incluso cuando su cuerpo contiene un falso positivo. Nuevos lectores entienden draft 4; lectores antiguos no lo entienden y deben rechazarlo. No se declara compatibilidad del viewer ni de consumidores externos sin comprobarla.

## 8. Flujo después del cierre

1. Seleccionar el registro original exacto y verificar su integridad/aplicabilidad con el flujo existente. Esta operación editorial no certifica que un head antiguo siga siendo actual.
2. Abrir o reutilizar una sesión de publicación propia, separada del archivo cerrado. Guardar en ella el contexto editorial y los otros contextos/proofs necesarios.
3. Preparar **otro archivo** de draft 4. No sobrescribir el borrador anterior ni añadir sidecars dentro del archivo original.
4. Revisar el texto público completo, incluidas incertidumbres y campos que no tienen override editorial. Verificar los bytes exactos que se enviarían.
5. Publicar sólo con autorización válida y registrar la observación separada, ligada a la revisión y al draft; verificar el cuerpo devuelto según el flujo existente.

Preparación y verificación no ejecutan checks, crean un nuevo run de revisión ni cambian closure/trace. Un error de contexto, privacidad o escritura conserva los archivos existentes y no deja un draft parcial considerado listo. No se añade un sistema de publicación nuevo.

## 9. Mapa de cambios futuros

| Unidad | Responsabilidad |
|---|---|
| `contracts/disclosure_text.py` (nuevo) y `contracts/check_disclosure.py` | Clasificación de prosa/credenciales y saneamiento sobre fuentes; conservar funciones y garantías de procedencia. |
| `reporting/text_projection.py` (nuevo) | Extraer el proyector de spans puro compartido, conservando `delivery._Projection` como alias y las reglas existentes. |
| `reporting/finding_publication.py` (nuevo) | Validar/normalizar el contexto disperso, digest y vista editorial pura. |
| `reporting/publication_legacy.py` (nuevo) | Política congelada de publicación para verificar drafts 2/3. |
| `reporting/projections.py`, `render.py`, `check_disclosure.py`, `delivery.py` | Separar saneamiento/escape, recorrer todos los campos dinámicos y aplicar la vista sólo donde corresponde. |
| `reporting/comment.py`, `cli/comment.py`, `cli/contract.py` | Draft 4, dispatch histórico y argumento opcional. |
| `references/reporting/publication.md`, `delivery.md`, `report-format.md`, `SKILL.md`, ejemplo sintético | Documentar edición, límites, semántica, privacidad y recuperación sin repetir revisión. |

## 10. Aceptación y validación

| ID | Resultado exigido |
|---|---|
| A01 | Las dos entradas legítimas de §2 conservan su texto visible, con y sin contexto editorial, en draft nuevo. |
| A02 | Credenciales estructuradas, conocidas/codificadas y rutas realmente privadas siguen ocultas; los controles negativos de spans/URLs conservan su comportamiento seguro. |
| A03 | Un contexto disperso permite explicar evidencia y quitar referencias de mecánica sin cambiar registro, metadata ni cantidades. |
| A04 | Contexto de otro registro, IDs/índices inválidos, campos estructurales, tamaños excesivos y versiones desconocidas fallan antes de escribir. |
| A05 | No desaparecen hallazgos, evidencias, bloqueantes ni incertidumbres por omitir filas; condiciones/handoff reflejan la misma corrección editorial. |
| A06 | Draft 4 liga registro, contexto, disclosure, política y cuerpo; detecta manipulación y conserva la diferencia local/remoto de CRLF. |
| A07 | Los fixtures de drafts 2/3 de la base siguen verificándose sin normalizarse; draft 1 sigue obsoleto. |
| A08 | En archivos completos y compactos cerrados, todos los bytes/hashes permanecen idénticos después de preparar/verificar, tanto al tener éxito como al fallar. |
| A09 | No se repiten discovery, verificaciones ni checks, ni se escribe fuera de la sesión seleccionada; ninguna API envía mensajes. |
| A10 | Los casos sintéticos no incluyen artifacts privados y las instrucciones distinguen integridad, fidelidad editorial y permiso de publicación. |

Las pruebas combinan unidades puras, integración CLI y fixtures sintéticos full/compact con inventario de hashes antes/después. El cierre usa las suites de comentarios, publicación, contratos, disclosure y delivery, además de límites entre módulos/enlaces. Se registra el comando y resultado reales de cada validación; no se confunde un subconjunto con la suite completa. Los archivos de planning son el único entregable de esta tarea; las pruebas de implementación se ejecutarán cuando se autorice implementarlo.
