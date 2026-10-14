# Validación de ciclo de perfil y recuperación

## Alcance y base

Esta validación corresponde a `feat/review-recovery-lifecycle`, preparada como actualización 2.12.0 pendiente de publicación. La base de diseño fue `main` en `5507c48715c558c9d366491f19fcce196780b37e`; la suite anterior a la implementación registró 317 pruebas, 316 aprobadas y una omitida por permisos de symlink en Windows. Ese resultado es únicamente la línea base, no evidencia de esta rama.

## Resultado de la implementación

La suite integrada ejecutada después de los cambios funcionales terminó con **385 pruebas: 383 aprobadas, 2 omitidas, exit 0**, en 480.667 segundos:

```text
python -B -X utf8 .superpowers/sdd/review-recovery-lifecycle/run-unittest.py discover -s tests -v
```

Las omisiones fueron las pruebas de symlink y junction: el host no concede los privilegios necesarios. No se reportan como cobertura aprobada.

Comprobaciones adicionales:

- `test_review_profiles.py`: 13/13; incluye transiciones de perfil, obligaciones tras downgrade, publicación schema 10 y visibilidad privada del perfil inicial/efectivo.
- `test_review_artifact_layout.py`: 17/17; incluye el registro de una ruta planeada antes de que exista.
- `test_reference_layout.py`: 1/1; valida ubicaciones y enlaces Markdown locales.
- Parseo AST de los nueve archivos Python modificados: aprobado, sin generar bytecode.
- Ayuda CLI de lookup, inspect, pause, block, resume, recover, restart, validate, render-user, render-comment, deduplicate y delivery: 12/12.
- Tras el ajuste de texto del diagnóstico de publicación, `test_review_profiles.py` pasó 13/13 y `test_reference_layout.py` pasó 1/1.
- `git diff --check`: aprobado; Git informa que normalizará CRLF a LF en `scripts/review_contract.py` en una futura escritura.

## Revisión de los riesgos del plan

1. La primera selección se conserva como S001; una selección tardía o repetida no la reemplaza. Las transiciones identifican perfil, fase, actor, autoridad, motivo, evento y asignaciones afectadas.
2. Una transición a un perfil menor no borra asignaciones o verificaciones adquiridas por trabajo iniciado. Las obligaciones activas del perfil más fuerte siguen aplicando y las asignaciones supersedidas permanecen enlazadas.
3. Las mutaciones y recuperaciones usan los locks/transacciones del helper y conservan bytes pendientes; la suite cubre límites de interrupción y reintentos.
4. La recuperación exige el run exacto, compara scope/fuentes, conserva identidad de workers y requiere autoridad para continuar una pausa o adoptar/transferir recursos.
5. El lookup se limita al repositorio/scope solicitado, pagina con cursor, expone truncación y cambios de base/head/description/fuentes/perfil, y no selecciona automáticamente por fecha. Un reporte completo se verifica con sus hashes y contrato antes de ofrecerlo como reporte conservado.

La prueba de registro de recursos confirmó que una ruta futura puede quedar registrada antes de crearla; no se crea la ruta ni se reclama como sesión hasta que existe un workspace verificable.

Se inspeccionó manualmente el diff funcional frente a esos cinco riesgos. No se invocó una revisión desde un contexto independiente en este turno; queda pendiente como revisión humana del PR. Esta limitación no se presenta como aprobación independiente.

El visor independiente no forma parte de este repositorio y su compatibilidad no se verificó. No se modificaron artifacts reales de reviews, configuración de harness ni el visor.
