# Cobertura explícita de dimensiones ABCDE

## Estado y propósito

Propuesta documental preparada junto con su plan por petición del usuario. Pendiente de revisión; preparar estos documentos no autoriza ejecutar la implementación. Base: `main`, commit `09eeb03`, CCR 2.13.0. Rama de preparación: `docs/explicit-dimensions-spec`.

El usuario quiere saber qué dimensiones se aprovecharon en cada revisión y evitar que se omitan silenciosamente. Acepta expresarlas en `details` o mediante otro mecanismo. Esta propuesta elige un contrato estructurado obligatorio que también se muestra en el informe. Se distingue una decisión explícita de aplicabilidad de la inspección efectiva y de la confirmación de un defecto.

## 1. Situación actual y alternativas

Las referencias de `dimensions/` aportan preguntas sobre 27 subaspectos de las áreas A–E. Los briefs deben nombrar los relevantes, pero packet version 1 conserva únicamente flujos y limitaciones; final schema 10 conserva cinco filas de `coverage.areas`. El validador exige `details` no vacío, sin poder detectar que falta una dimensión. El renderer y el visor muestran ese texto; no reconstruyen las preguntas que se inspeccionaron.

Opciones consideradas:

| Opción | Ventaja | Limitación |
|---|---|---|
| Plantilla obligatoria dentro de `details` | Conserva schema 10 | Requiere interpretar prosa para detectar ausencias; ambiguo entre idiomas y formatos |
| Lista estructurada solo de dimensiones seleccionadas | Poco volumen | Una dimensión olvidada puede confundirse con una exclusión intencional |
| Catálogo completo con decisión por dimensión, opción elegida | Detecta ausencias, duplicados y contradicciones; permite renderizar estados explícitos | Requiere final schema 11 y actualizar sus consumidores internos |

No se intenta inferir desde código que una dimensión realmente no aplica ni certificar la verdad de un texto de evidencia. La garantía mecánica es que ninguna dimensión del catálogo desaparece del resultado ni queda implícita en el estado global de un área.

## 2. Restricciones globales

- Python 3.10+ y biblioteca estándar; no agregar dependencias de producto.
- Los nuevos resultados finales usan schema 11; los schemas 1–10 conservan sus reglas y bytes históricos.
- Mantener archive schema 8, layout version 2, trace schema 1 y packet version 1.
- No migrar, reabrir ni reescribir archivos reales de revisiones para completar dimensiones antiguas.
- Mantener perfiles, independencia, gates de proyecto, IDs de hallazgos/checks y reglas de veredicto existentes.
- Los comentarios públicos omiten la taxonomía ABCDE y de dimensiones; las brechas materiales conservan su impacto público.
- El visor externo no se modifica ni se declara compatible con schema 11 en esta entrega.
- No asignar versión de release, publicar, hacer merge ni modificar datos reales de reviews durante esta preparación.

## 3. Catálogo estable, ligado a schema 11

El catálogo tiene 27 IDs, nombres en inglés en la referencia operativa y etiquetas españolas para los renderers existentes. Cada ID pertenece a una sola área. Su significado no se recicla; cambiar el conjunto obligatorio exige otra revisión explícita del contrato, no modificar retrospectivamente schema 11.

| Área | IDs y significado |
|---|---|
| A | `A01` Boundaries and ownership; `A02` Dependency direction; `A03` Lifecycle and state; `A04` Failure isolation; `A05` Test seams |
| B | `B01` Preconditions and postconditions; `B02` Validation and branching; `B03` Invariants and edge cases; `B04` Fallback behavior; `B05` User-visible outcome |
| C | `C01` API/event shape; `C02` Producer-consumer agreement; `C03` Serialization; `C04` Compatibility/versioning; `C05` Ordering and rollout |
| D | `D01` Identity and ownership; `D02` Query/filter semantics; `D03` Transactions; `D04` Constraints and migrations; `D05` Consistency and recovery |
| E | `E01` Authentication and authorization; `E02` Tenant and resource isolation; `E03` Trust boundaries and validation; `E04` Error disclosure; `E05` Concurrency and idempotency; `E06` Lifecycle and cleanup; `E07` Performance |

`scripts/review_dimensions.py` será la fuente mecánica del catálogo, sus etiquetas y la agregación. Las referencias existentes explicarán sus preguntas; pruebas de correspondencia impedirán IDs ausentes o cambiados accidentalmente. No crear una segunda lista de IDs en el renderer ni en los tests.

## 4. Registro final

Schema 11 conserva el envelope y los campos de schema 10 y añade `dimensions` obligatorio en cada fila de `coverage.areas`. No introduce un campo raíz ni modifica el formato de hallazgos. Cada fila mantiene `area`, `status`, `details`, `material` y `finding_ids`.

Cada dimensión contiene exactamente:

| Campo | Contrato |
|---|---|
| `id` | ID canónico perteneciente al área contenedora |
| `status` | `covered`, `partial`, `not_evaluated` o `not_applicable` |
| `details` | Texto no vacío de evidencia, brecha o motivo de exclusión |
| `material` | Booleano; solo puede ser verdadero en `partial` o `not_evaluated` |
| `finding_ids` | IDs distintos de hallazgos retenidos y no rechazados, o lista vacía |

Cada área contiene exactamente sus cinco dimensiones, salvo E, que contiene siete. Se rechazan IDs faltantes, repetidos, desconocidos o colocados en otra área, tipos inválidos y campos extra. Orden de entrada libre; salida en orden A–E e ID ascendente. Los errores identifican la ruta del campo, sin volcar el documento privado.

Semántica de `details`:

- `covered`: flujo y fuente decisiva observados, con ruta/símbolo o check ID real cuando corresponda. Cubierta no significa libre de defectos.
- `partial`: parte inspeccionada y pregunta pendiente concreta; no ocultarla tras evidencia de otra dimensión.
- `not_evaluated`: mecanismo aplicable y razón de que no se inspeccionara.
- `not_applicable`: motivo vinculado al alcance; no equivale a falta de tiempo, herramientas o conocimiento.

No se agrega un parser de prosa. Un texto no vacío satisface la forma, pero su precisión se verifica en la revisión escéptica ya requerida por el perfil. No se inventan rutas, checks, resultados ni evidencia para completar el catálogo. Una prueba ausente, por sí sola, no convierte `A05` en defecto.

Ejemplo ilustrativo de una dimensión, no de un registro final completo:

```json
{
  "id": "E05",
  "status": "partial",
  "details": "Se inspeccionó la clave de idempotencia en src/jobs.py:claim_job. Falta establecer qué ocurre si dos procesos reclaman el mismo job antes de persistirla.",
  "material": true,
  "finding_ids": []
}
```

### Agregación obligatoria por área

Se excluyen `not_applicable` para calcular las dimensiones aplicables. El estado del área es:

1. `not_applicable` si no hay dimensiones aplicables.
2. `covered` si todas las aplicables están cubiertas.
3. `not_evaluated` si todas las aplicables están sin evaluar.
4. `partial` en los demás casos, incluida cualquier dimensión parcial.

`area.material` es el OR de los booleanos de sus dimensiones. `area.finding_ids` es exactamente la unión, sin duplicados, de sus referencias. Una dimensión no aplicable tiene `material=false` y ninguna referencia a hallazgos. Los detalles del área siguen siendo un resumen no vacío; no sustituyen las filas individuales.

El validador rechaza un resumen contradictorio; no lo corrige ni inventa dimensiones. La precedencia actual de veredicto usa la brecha agregada: una brecha material impide aprobar, salvo que un bloqueante confirmado ya determine `not_approvable`. Un mismo hallazgo puede referenciarse desde varias dimensiones/áreas sin duplicarse.

## 5. Uso durante una run

1. Al fijar alcance, el coordinador considera el catálogo completo. Clasifica mecanismos afectados y registra motivos de no aplicabilidad. Esto no obliga a inspeccionar 27 mecanismos ni a cargar todas las referencias.
2. Cada mecanismo aplicable se asigna a un responsable ya existente en el perfil. Los briefs nombran IDs, flujo, pregunta/invariante y evidencia esperada. Ningún ID añade automáticamente un revisor, sesión o check.
3. Los workers conservan packet version 1. En sus campos de texto existentes, `coverage.flows` nombra IDs inspeccionados con fuentes; `coverage.limitations[].detail` nombra IDs pendientes. Las evidencias pueden servir a varias dimensiones. No se interpreta un packet sin mención de un ID asignado como cobertura completa.
4. El coordinador consolida observaciones en las 27 filas. Un ID aplicable sin respuesta permanece `not_evaluated`, con causa y materialidad honesta, hasta resolverse; nunca `not_applicable` por omisión. Las dimensiones imprevistas se incorporan por las reglas de asignación vigentes.
5. La verificación existente contrasta estados, motivos y fuentes con los resultados observados. No se crea una auditoría ni un agente adicional por dimensiones.
6. Antes de retener, valida schema 11 y usa `retain --expected-schema 11`. Un resultado incompleto se corrige o se conserva como brecha explícita; no se rebaja a schema 10 para sortear un fallo.

En re-review se vuelve a clasificar el alcance actual. La cobertura anterior puede reutilizarse solo con evidencia, versiones y justificación existentes; una revisión antigua sin dimensiones no prueba los 27 estados actuales. No se rellena el catálogo desde el estado agregado anterior.

## 6. Reporte y entrega

El reporte privado conserva la matriz ABCDE de cinco filas. Inmediatamente después añade `### Dimensiones evaluadas`, con un subtítulo por área y una tabla de ID, dimensión, estado, evidencia o motivo y hallazgos. Se muestran también `partial`, `not_evaluated` y `not_applicable`; no se ocultan por ausencia de hallazgos. Son 27 filas explícitas, no un porcentaje ni una puntuación.

Ejemplo de presentación de una fila:

```text
E05 | Concurrencia e idempotencia | Parcial | Inspeccionada la clave de idempotencia; pendiente la reclamación concurrente… | —
```

El renderer genera nombres y estados desde el catálogo y escapa pipes, saltos de línea y HTML como los campos equivalentes actuales. No modifica el JSON de entrada. En schemas 1–10 no añade filas ni una sección de dimensiones inventadas; conserva su representación histórica.

Entrega full: conserva las 27 dimensiones en JSON portátil y el desglose completo en Markdown. Entrega brief: añade un resumen por área con todos sus IDs agrupados por estado, más motivos de las dimensiones pendientes o no aplicables; no reproduce toda la evidencia cubierta. Su carácter resumido y la identidad del resultado fuente quedan explícitos. No debe presentar el silencio como cobertura.

Los comentarios públicos omiten tablas, IDs y etiquetas internas de dimensiones. Siguen mostrando los hallazgos y las incertidumbres materiales sobre el producto. Las brechas llegan por el resumen agregado del área usando las reglas actuales, sin duplicar una incertidumbre ya representada en limitaciones. No borrar del comentario una condición material solo por ocultar la taxonomía.

Las nuevas rutas de la proyección portátil tienen política explícita: `dimensions[].id`, `.status` y `.finding_ids[]` son identidades/enums; `.details` es prosa; `.material` es booleano. Conservar IDs y relaciones, sanear texto privado y rechazar identidades privadas como hoy. Un campo desconocido no adquiere una política permisiva.

## 7. Compatibilidad y persistencia

El nuevo helper acepta final schemas 1–11 según sus contratos respectivos. Schema 11 hereda íntegramente la historia de perfiles, bindings de asignación y provenance de checks de schema 10: ampliar las ramas de versión de `review_contract`, `review_profiles`, `review_execution`, `review_check_provenance` y `review_publication` sin omitir validaciones.

Archive 8 mantiene su formato y su disposición. Checkpoint, retain y validate admiten final 10 y 11, conservando todos los gates de identidad, historial, fuentes y ejecutores. Los archivos schema 10 de 2.13.0 siguen siendo válidos, consultables y recuperables según las reglas actuales. Las runs iniciadas por el flujo actualizado deben producir 11; el guard `--expected-schema 11` impide aceptar accidentalmente 10 en esa finalización. No se elimina el soporte explícito de 10 necesario para operaciones anteriores; no constituye una actualización de su cobertura.

La ampliación debe alcanzar también lookup/latest, diagnóstico de checkpoint, recuperación de bytes reservados, history/port, render_handoff y delivery. No se altera la reserva de operaciones ni se recomputan resultados para añadir dimensiones. En recovery se conserva el schema y los bytes de la operación existente; únicamente una nueva run vinculada aplica el contrato nuevo.

Un helper de 2.13.0 puede rechazar schema 11; no se garantiza lectura por consumidores antiguos. El visor se actualizará en su repositorio aparte. La documentación de compatibilidad indicará esa dependencia y la disponibilidad del Markdown y JSON originales.

## 8. Criterios de aceptación

| ID | Resultado comprobable |
|---|---|
| AC1 | Un final 11 válido contiene exactamente las 27 dimensiones canónicas en sus áreas |
| AC2 | Eliminar cualquier dimensión, duplicarla, cambiar su área o dejar `details` vacío causa error específico |
| AC3 | Ningún resumen de área puede ocultar brechas o contradecir la unión de hallazgos |
| AC4 | Brechas materiales y bloqueantes conservan la precedencia de veredicto existente |
| AC5 | Informe privado y full muestran todas las dimensiones; brief enumera todos los IDs y explica pendientes/exclusiones |
| AC6 | Comentario público conserva impacto material sin taxonomía ni duplicados |
| AC7 | Retención/recovery de 10 y 11 conservan IDs, fuentes, perfiles, ejecutores, hashes y bytes históricos |
| AC8 | Briefs y packets existentes permiten seguir IDs desde asignación hasta evidencia o brecha, sin nuevo agente |
| AC9 | Proyección portátil protege datos privados dentro de los nuevos campos sin cambiar identidades |
| AC10 | Schemas 1–10 siguen válidos sin dimensiones; no se modifica ningún archivo real de revisión |

Tests mecánicos prueban completitud y coherencia, no la calidad del juicio del revisor. Escenarios documentados de asignación, omisión de respuesta y re-review complementan las pruebas del contrato. La implementación deberá registrar resultados observados, incluida la suite completa, antes de afirmar que la capacidad está disponible.

## 9. Alcance de la preparación y siguiente paso

Esta entrega contiene únicamente este spec, el [plan de implementación](../plans/2026-10-20-explicit-dimension-coverage.md) y su registro de preparación. No cambia aún SKILL, contratos, helpers, tests ni visor. El usuario revisará los documentos y seleccionará el método de implementación antes de ejecutar el plan.
