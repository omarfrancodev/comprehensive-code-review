# Presentación editorial de un resultado conservado

Una corrección de redacción se prepara en una sesión de publicación separada sin modificar `review.json`, el informe privado, sus pruebas, el manifiesto ni el cierre. Primero se comprueba la integridad y aplicabilidad del resultado original. El contexto no vuelve actual una revisión de otro head ni autoriza publicar.

Este ejemplo usa exclusivamente el registro sintético de `tests/fixtures/publication_legacy/draft2.json`. Calcula su digest real con el mismo algoritmo del helper:

```python
import hashlib
import json
from pathlib import Path

record = json.loads(Path('tests/fixtures/publication_legacy/draft2.json').read_text(encoding='utf-8'))['record']
source_sha256 = hashlib.sha256(json.dumps(
    record, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
    allow_nan=False).encode('utf-8')).hexdigest()
context = {
    'schema_version': 1,
    'source_sha256': source_sha256,
    'findings': [{
        'id': 'R001',
        'evidence': [{'index': 0, 'summary':
                     'La limpieza de la reserva no comprueba quién es su propietario.'}]
    }]
}
# Guardar context en un archivo nuevo de la sesión propia de publicación.
```

Cada edición conserva los campos omitidos, todos los hallazgos y las evidencias originales. Puede reformular título, escenario, impacto, corrección, una razón de bloqueo existente y detalles de evidencia por índice original. No puede cambiar estados, prioridades, bloqueo, ubicaciones, IDs, checks, resultados ni autores. El coordinador comprueba la fidelidad de la nueva redacción; un hash correcto no la demuestra.

Con un resultado real se usan sus IDs y registro exactos. Los otros contextos y pruebas siguen ligados a ese mismo registro. Consultar `--help` antes de las rutas CLI:

```text
python <skill>/scripts comment prepare --input <review.json> --session <sesion/manifest.json> --output <sesion/evidence/comentario-nuevo.json> --finding-publication-context <sesion/evidence/editorial.json> --coverage-publication-context <sesion/evidence/flujos.json>
python <skill>/scripts comment verify --input <review.json> --draft <sesion/evidence/comentario-nuevo.json> --body <cuerpo-exacto-a-enviar.md>
```

Los paths entre ángulos son entradas seleccionadas, no comandos listos para ejecutar. El primer comando necesita también checks/disclosure cuando el registro los requiera. `contract render-comment` acepta el contexto editorial; las rutas privadas lo rechazan. El handoff público por API usa la misma vista y corrección; full/brief conserva el registro original.

Prepare emite draft 4, política `publication-editorial-v1`, contexto normalizado, digest editorial y hash del cuerpo. Verify usa el contexto embebido y las pruebas seleccionadas de disclosure; no necesita otra copia del contexto editorial. No se retoca el cuerpo verificado: se prepara otro archivo nuevo. Los drafts 2/3 conservan su política histórica; draft 1 requiere regeneración. Lectores anteriores no reconocen draft 4.

La privacidad se aplica antes de escapar Markdown. `jobs_service.py:_publish_pending_job` conserva su contenido visible; «por token: puede borrar» no es una asignación. Credenciales estructuradas, URLs sensibles y valores conocidos siguen ocultos, incluso cuando el resumen repite un valor marcado sólo en la evidencia original. Una identidad estructural sensible bloquea la proyección.

El contexto admite 256 KiB de JSON UTF-8 original y normalizado y 16 KiB por texto. Rechaza campos extra, claves JSON duplicadas, índices inválidos, versiones desconocidas y otro registro fuente. Un fallo no autoriza cambiar el archivo histórico ni repetir checks para mejorar su explicación.

Antes de un envío autorizado se revisa todo el comentario, incluidos campos sin override, incertidumbres y referencias. Verify comprueba integridad, no calidad ni permiso. Después se verifica el cuerpo devuelto y se registra una observación separada enlazada al resultado original.
