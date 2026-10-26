# Lecturas acotadas de blobs

El usuario autorizó implementar la mejora menor identificada en la validación de equivalencia y publicar la rama mediante push y PR. Se conserva el worktree existente y la base CCR 3.1.0.

## Diseño

La clasificación de texto solo necesita los primeros 8000 bytes. Hoy `_blob_info` calcula y descarta hashes completos de texto, y un mismo objeto puede leerse de nuevo por cada ruta y lado del contexto.

Se mantiene Python/stdlib y el adaptador streaming actual: detener la lectura de texto una vez observado el prefijo de clasificación; el adaptador entrega bloques de hasta 64 KiB y cierra el proceso al terminar anticipadamente. Conservar lectura completa para hashes de binarios, symlinks y contexto. Cachear resultados únicamente durante una invocación de cada colector, por OID, incluyendo la posibilidad de completar un hash parcial si un cambio binario lo requiere. No compartir caché entre capturas, repositorios ni evaluaciones.

Alternativas consideradas: un protocolo cat-file batch reduciría procesos pero ampliaría el cambio y su parser; una caché persistente añadiría estado e invalidación. La decisión del implementador es usar prefijo acotado y caché local para resolver el coste identificado sin esos contratos adicionales.

## Compatibilidad y aceptación

- No cambiar `ccr-effective-diff-v1`, schemas, contenido de los descriptores, límites, decisiones de reutilización ni archivos históricos.
- Conservar la clasificación NUL en los primeros 8000 bytes, incluso cuando el NUL está en el límite o después.
- Ante transición texto/binario, conservar SHA-256 completo de ambos lados; nunca persistir un hash de prefijo como hash completo.
- Para texto grande duplicado, observar lectura acotada por objeto único; para binarios y contexto duplicados, observar un hash completo por objeto único y captura.
- Cerrar streams al terminar anticipadamente o fallar. No suprimir la recaptura que verifica integridad del descriptor actual.
- Contar bytes entregados por el adaptador real en tests; no inferir latencia o ahorro de CPU, ni evitar las lecturas de Git que necesita el diff.
- Ejecutar regresiones de Git/equivalencia/contexto/archivo, suite completa y comprobar PR remoto tras crearlo.
