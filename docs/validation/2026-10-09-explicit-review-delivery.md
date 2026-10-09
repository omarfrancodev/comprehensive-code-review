# Validación de entrega explícita

Se preparó una revisión del comportamiento de transferencia y de la documentación pública, conservando los contratos del archivo interno.

## Base e instrucciones

- Base: main en e51dcb3a72afc123916cd90bdea277b9d494f9ed, release 2.7.0.
- Suite de base: 195 pruebas en 115.631 segundos; 194 aprobadas y una omitida por privilegios de enlaces simbólicos en Windows.
- Una simulación independiente sobre las instrucciones de base detectó que full/brief no tenían contrato y que --output podía confundirse con la raíz del archivo interno.
- Una simulación independiente de las instrucciones nuevas distinguió full con checkout persistente, brief sin Spec/Plan, output sin modalidad y transferencia de un review cerrado. No ejecutó revisiones reales ni publicó contenido.
- Se corrigieron las incoherencias señaladas: handoff reservado a compatibilidad explícita, separación de destinos, versión del ejemplo de preparación y contenido requerido del resumen.

## Comprobaciones de implementación

Los tests de entrega se escribieron antes del helper y fallaron por su ausencia. Cubren exportación desde registros retenidos/cerrados sin alterar el origen, proyección portable, IDs/versiones/resultados, conteos y límites materiales en el resumen, contexto suministrado y ausencia de Spec/Plan, compatibilidad de registros históricos, destinos persistentes y selección explícita.

Las pruebas de rutas y escritura comprueban rechazo de destinos existentes, traversal, enlaces/reparse points, raíz de otro repositorio, archivo fuente y temporales registrados; una escritura interrumpida limpia únicamente archivos/directorios creados por la propia operación. La entrega no copia logs, fixtures o reproducciones ni activa otra revisión.

El README se redujo de 185 a 95 líneas. Instalación/actualización y uso avanzado se separaron en docs/installation.md y docs/usage.md, manteniendo referencias operativas canónicas. El enlace de descarga corresponde a la última release publicada hasta aprobar la siguiente publicación.

Estos checks verifican comportamiento estructural y de archivos; no prueban que los hallazgos de un producto sean correctos ni constituyen una medición de ahorro de tokens/créditos. La validación de frontmatter con PyYAML permanece limitada por disponibilidad de esa dependencia; se comprueban sintaxis, metadatos declarados y enlaces por separado.

## Integración anterior al renombrado

- Suite completa: 214 tests en 162.119 segundos, 213 aprobados y uno omitido por privilegios de enlaces simbólicos en Windows. Se ejecutó con repositorios temporales fuera de la instalación; la suite incluye un test real de junctions de Windows.
- Sintaxis correcta de ocho scripts, siete interfaces --help comprobadas y metadatos declarados para 2.8.0.
- Los 60 enlaces locales comprobados antes de añadir el plan no presentaron errores; las guías de instalación y uso conservan sus anclas.
- El plan se documentó después de iniciar el trabajo, tras la observación del usuario; no se atribuye retrospectivamente una aprobación previa a ese documento.

## Nombres de perfiles y gate final

Se incorporó a este mismo PR la decisión explícita del usuario: focused/standard/deep/extended, con economy → focused y balanced → standard como alias de petición. Las estrategias, límites, selección y gates permanecen iguales. El contrato final 7 conserva el resto de reglas del 6; los registros 1–6 mantienen sus enums y renderer originales, sin migración.

Diez pruebas nuevas cubren normalización de petición, rechazo de nombres antiguos en nuevos registros canónicos, tipos malformados, representación histórica, verificación sustantiva standard/P3 y dudas materiales, invariantes deep/extended sin candidatos, IDs, CLI y retención/cierre/entrega con identidad real. Se observaron fallos antes de añadir el normalizador y soporte de schema 7; las diez pruebas aprobaron tras implementarlos. La suite de entrega también exporta registros 1–7 manteniendo su esquema e identidad.

- Gate final: 224 tests en 159.616 segundos; 223 aprobados y uno omitido por privilegios de enlaces simbólicos en Windows.
- Sintaxis de ocho scripts y siete interfaces --help correctas; 63 enlaces/anclas locales sin errores; git diff --check correcto.
- README final: 95 líneas. Plan con Global Constraints, Review Focus, Tasks, Files, Interfaces, Steps numerados, pruebas/comandos/resultados y Self-Review.
- La comprobación auxiliar con PyYAML sigue indisponible; no se instalaron dependencias adicionales ni se atribuye a ese validador un resultado aprobado.
