"""Schema-11 dimension catalog and pure coverage coherence checks."""

DIMENSIONS = {a: tuple(f'{a}{i:02d}' for i in range(1, n + 1))
              for a, n in [('A', 5), ('B', 5), ('C', 5), ('D', 5), ('E', 7)]}
DIMENSION_LABELS = dict(zip((i for ids in DIMENSIONS.values() for i in ids), (
    'Límites y responsabilidades', 'Dirección de dependencias', 'Ciclo de vida y estado',
    'Aislamiento de fallos', 'Puntos de prueba', 'Precondiciones y postcondiciones',
    'Validación y bifurcaciones', 'Invariantes y casos límite', 'Comportamiento de fallback',
    'Resultado visible para el usuario', 'Forma de API y eventos', 'Acuerdo productor-consumidor',
    'Serialización', 'Compatibilidad y versionado', 'Orden y despliegue', 'Identidad y propiedad',
    'Semántica de consultas y filtros', 'Transacciones', 'Restricciones y migraciones',
    'Consistencia y recuperación', 'Autenticación y autorización', 'Aislamiento de tenants y recursos',
    'Límites de confianza y validación', 'Divulgación de errores', 'Concurrencia e idempotencia',
    'Ciclo de vida y limpieza', 'Rendimiento')))
STATUSES = {'covered', 'partial', 'not_evaluated', 'not_applicable'}
FIELDS = {'id', 'status', 'details', 'material', 'finding_ids'}


def dimension_summary(dimensions: list[dict]) -> dict:
    """Aggregate validated decisions without inferring evidence/applicability."""
    states = [r['status'] for r in dimensions if r['status'] != 'not_applicable']
    if not states:
        status = 'not_applicable'
    elif all(s == 'covered' for s in states):
        status = 'covered'
    elif all(s == 'not_evaluated' for s in states):
        status = 'not_evaluated'
    else:
        status = 'partial'
    return dict(status=status, material=any(r['material'] for r in dimensions),
                finding_ids=sorted({i for r in dimensions for i in r['finding_ids']}))


def validate_dimensions(areas: object, finding_ids: set[str]) -> list[str]:
    errors = []
    def fail(path, message):
        errors.append(path + ': ' + message)
    if not isinstance(areas, list):
        return ['coverage.areas: expected array']
    seen_areas = set()
    for index, area in enumerate(areas):
        path = f'coverage.areas[{index}]'
        if not isinstance(area, dict):
            fail(path, 'expected object')
            continue
        code = area.get('area')
        if not isinstance(code, str) or code not in DIMENSIONS:
            fail(path + '.area', 'expected area A through E')
            continue
        if code in seen_areas:
            fail(path + '.area', 'duplicate area')
        seen_areas.add(code)
        rows = area.get('dimensions')
        if not isinstance(rows, list):
            fail(path + '.dimensions', 'complete dimension array required')
            continue
        start = len(errors)
        seen = set()
        for number, row in enumerate(rows):
            field = path + f'.dimensions[{number}]'
            if not isinstance(row, dict) or set(row) != FIELDS:
                fail(field, 'exact id, status, details, material and finding_ids required')
                continue
            identifier = row['id']
            if not isinstance(identifier, str) or identifier not in DIMENSIONS[code]:
                fail(field + '.id', 'unknown dimension or incorrect area')
            elif identifier in seen:
                fail(field + '.id', 'duplicate dimension')
            else:
                seen.add(identifier)
            state = row['status']
            if not isinstance(state, str) or state not in STATUSES:
                fail(field + '.status', 'unsupported dimension status')
            if not isinstance(row['details'], str) or not row['details'].strip():
                fail(field + '.details', 'nonempty evidence, gap or applicability reason required')
            if type(row['material']) is not bool:
                fail(field + '.material', 'expected boolean')
            elif row['material'] and state not in ('partial', 'not_evaluated'):
                fail(field + '.material', 'only pending applicable coverage can be material')
            refs = row['finding_ids']
            if not isinstance(refs, list):
                fail(field + '.finding_ids', 'expected array')
            else:
                found = set()
                for offset, ref in enumerate(refs):
                    if not isinstance(ref, str) or ref not in finding_ids or ref in found:
                        fail(field + f'.finding_ids[{offset}]', 'distinct retained non-rejected finding ID required')
                    else:
                        found.add(ref)
                if state == 'not_applicable' and refs:
                    fail(field + '.finding_ids', 'nonapplicable dimensions cannot reference findings')
        if seen != set(DIMENSIONS[code]):
            fail(path + '.dimensions', 'exactly one decision per canonical dimension required')
        if len(errors) == start:
            summary = dimension_summary(rows)
            for key in ('status', 'material'):
                if type(area.get(key)) is not type(summary[key]) or area.get(key) != summary[key]:
                    fail(path + '.' + key, 'area contradicts its dimensions')
            refs = area.get('finding_ids')
            if (not isinstance(refs, list) or any(not isinstance(r, str) for r in refs)
                    or len(refs) != len(summary['finding_ids']) or sorted(refs) != summary['finding_ids']):
                fail(path + '.finding_ids', 'exact dimension finding union required')
    if seen_areas != set(DIMENSIONS):
        fail('coverage.areas', 'exactly one row for each area A through E required')
    return errors
