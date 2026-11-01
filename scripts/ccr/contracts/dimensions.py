"""Dimension catalog and pure coverage coherence checks."""

import re

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


def summarize_area13(area: dict) -> dict:
    """Aggregate validated grouped decisions without inferring applicability."""
    groups = area['groups']
    states = [group['status'] for group in groups if group['status'] != 'not_applicable']
    if area['applicability'] == 'undetermined':
        status = 'not_evaluated'
    elif not states:
        status = 'not_applicable'
    elif all(state == 'covered' for state in states):
        status = 'covered'
    elif all(state == 'not_evaluated' for state in states):
        status = 'not_evaluated'
    else:
        status = 'partial'
    return {'status': status, 'material': any(group['material'] for group in groups),
            'finding_ids': sorted({ref for group in groups for ref in group['finding_ids']})}


def display_areas13(areas: list[dict]) -> list[dict]:
    """Build concise derived rows from already validated grouped areas."""
    result = []
    for area in areas:
        summary = summarize_area13(area)
        reasons = list(dict.fromkeys(', '.join(group['ids']) + ': ' + group['reason'] for group in area['groups']
                                     if group['status'] in ('partial', 'not_evaluated') and group['reason']))
        if not reasons and area['applicability_reason']:
            reasons = [area['applicability_reason']]
        if not reasons and summary['status'] == 'not_applicable':
            reasons = list(dict.fromkeys(group['reason'] for group in area['groups'] if group['reason']))
        evidence_ids = sorted({ref for group in area['groups'] for ref in group['evidence_ids']})
        result.append({'area': area['area'], **summary, 'evidence_ids': evidence_ids,
                       'details': '; '.join(reasons) if reasons else 'Aspectos aplicables inspeccionados'})
    return result


def validate_evidence13(rows: object, check_ids: set[str]) -> list[str]:
    """Validate shared evidence identities and bindings to existing checks."""
    if not isinstance(rows, list):
        return ['coverage.evidence: expected array']
    errors = []
    seen = set()
    for index, row in enumerate(rows):
        field = f'coverage.evidence[{index}]'
        if not isinstance(row, dict) or set(row) != {'id', 'kind', 'detail', 'check_id', 'reference'}:
            errors.append(field + ': invalid evidence fields')
            continue
        identifier = row['id']
        if not isinstance(identifier, str) or not re.fullmatch(r'EV(?!000)[0-9]{3}', identifier):
            errors.append(field + '.id: expected EV followed by a nonzero three-digit identity')
        elif identifier in seen:
            errors.append(field + '.id: duplicate evidence identity')
        else:
            seen.add(identifier)
        kind = row['kind']
        if kind not in ('static', 'check'):
            errors.append(field + '.kind: expected static or check')
        check_id = row['check_id']
        if kind == 'check' and (not isinstance(check_id, str) or check_id not in check_ids):
            errors.append(field + '.check_id: expected existing check')
        elif kind == 'static' and check_id is not None:
            errors.append(field + '.check_id: static evidence requires null')
        detail = row['detail']
        if not isinstance(detail, str) or not detail.strip():
            errors.append(field + '.detail: nonempty evidence required')
        reference = row['reference']
        if reference is not None and (not isinstance(reference, str) or not reference.strip()):
            errors.append(field + '.reference: expected nonempty reference or null')
    return errors


def validate_coverage13(areas: object, finding_ids: set[str], evidence_ids: set[str]) -> list[str]:
    """Check grouped coverage structure; inspecting the underlying facts remains the reviewer's job."""
    if not isinstance(areas, list):
        return ['coverage.areas: expected array']
    errors = []
    seen_areas = set()
    for index, area in enumerate(areas):
        path = f'coverage.areas[{index}]'
        if not isinstance(area, dict) or set(area) != {'area', 'applicability', 'applicability_reason', 'groups'}:
            errors.append(path + ': expected area, applicability, applicability_reason and groups')
            continue
        code = area['area']
        if not isinstance(code, str) or code not in DIMENSIONS:
            errors.append(path + '.area: expected area A through E')
            continue
        if code in seen_areas:
            errors.append(path + '.area: duplicate area')
        seen_areas.add(code)
        applicability = area['applicability']
        if not isinstance(applicability, str) or applicability not in {'applicable', 'not_applicable', 'undetermined'}:
            errors.append(path + '.applicability: unsupported value')
        reason = area['applicability_reason']
        if applicability == 'applicable':
            if reason is not None:
                errors.append(path + '.applicability_reason: expected null for applicable area')
        elif not isinstance(reason, str) or not reason.strip():
            errors.append(path + '.applicability_reason: reason required')
        groups = area['groups']
        if not isinstance(groups, list) or not groups:
            errors.append(path + '.groups: nonempty array required')
            continue
        seen_ids = set()
        states = []
        for number, group in enumerate(groups):
            field = path + f'.groups[{number}]'
            if not isinstance(group, dict) or set(group) != {'ids', 'status', 'reason', 'evidence_ids', 'finding_ids', 'material'}:
                errors.append(field + ': invalid group fields')
                continue
            ids = group['ids']
            if not isinstance(ids, list) or not ids:
                errors.append(field + '.ids: nonempty array required')
            else:
                for identifier in ids:
                    if not isinstance(identifier, str) or identifier not in DIMENSIONS[code]:
                        errors.append(field + '.ids: unknown dimension or incorrect area')
                    elif identifier in seen_ids:
                        errors.append(field + '.ids: duplicate dimension')
                    else:
                        seen_ids.add(identifier)
            status = group['status']
            if not isinstance(status, str) or status not in STATUSES:
                errors.append(field + '.status: unsupported value')
            else:
                states.append(status)
            reason = group['reason']
            if status == 'covered':
                if reason is not None:
                    errors.append(field + '.reason: expected null for covered group')
            elif not isinstance(reason, str) or not reason.strip():
                errors.append(field + '.reason: pending or applicability reason required')
            material = group['material']
            if type(material) is not bool:
                errors.append(field + '.material: expected boolean')
            elif material and status not in ('partial', 'not_evaluated'):
                errors.append(field + '.material: only pending coverage may be material')
            for key, known in (('evidence_ids', evidence_ids), ('finding_ids', finding_ids)):
                refs = group[key]
                if not isinstance(refs, list):
                    errors.append(field + '.' + key + ': expected array')
                    continue
                seen_refs = set()
                for ref in refs:
                    if not isinstance(ref, str) or ref not in known or ref in seen_refs:
                        errors.append(field + '.' + key + ': expected distinct known references')
                    else:
                        seen_refs.add(ref)
                if key == 'evidence_ids' and status == 'covered' and not refs:
                    errors.append(field + '.evidence_ids: covered group requires evidence')
                if key == 'finding_ids' and status == 'not_applicable' and refs:
                    errors.append(field + '.finding_ids: nonapplicable group cannot reference findings')
        if seen_ids != set(DIMENSIONS[code]):
            errors.append(path + '.groups: exactly one decision for every area dimension required')
        if applicability == 'not_applicable' and any(state != 'not_applicable' for state in states):
            errors.append(path + '.applicability: nonapplicable area cannot contain applicable groups')
        if applicability == 'applicable' and states and all(state == 'not_applicable' for state in states):
            errors.append(path + '.applicability: applicable area requires an applicable group')
    if seen_areas != set(DIMENSIONS):
        errors.append('coverage.areas: exactly one row for each area A through E required')
    return errors
