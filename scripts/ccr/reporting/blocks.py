"""Pure Markdown blocks shared by private and editorial public renderers."""
from urllib.parse import quote

from ccr.reporting.markdown import markdown_text


def evidence_groups(evidence: list[dict], checks: dict[str, dict], *,
                    projected_evidence: list[dict] | None = None, edited_indices=()) -> list[dict]:
    """Group original rows, then display the text of their selected indices."""
    groups, by_check, seen = [], {}, {}
    for index, item in enumerate(evidence):
        identifier, detail = item['check_id'], item['details']
        displayed = detail if projected_evidence is None else projected_evidence[index]['details']
        original_details = seen.setdefault(identifier, set())
        edited = index in edited_indices
        if identifier is None:
            if edited or detail not in original_details:
                original_details.add(detail)
                groups.append(dict(check_id=None, details=[displayed]))
            continue
        if identifier not in by_check:
            group = dict(check_id=identifier, details=[])
            groups.append(group)
            by_check[identifier] = group
        if edited or (detail != checks[identifier]['evidence'] and detail not in original_details):
            original_details.add(detail)
            by_check[identifier]['details'].append(displayed)
    return groups


def evidence_lines(groups: list[dict], *, format_text=markdown_text, format_id=None) -> list[str]:
    format_id = format_id or format_text
    lines = []
    for group in groups:
        identifier = group['check_id']
        if identifier is None:
            lines.extend('  - **Inspección estática** — ' + format_text(detail) for detail in group['details'])
        else:
            lines.append('  - **[' + format_id(identifier) + '](#' + quote(identifier, safe='') + ')** — Resultado en Validación.')
            lines.extend('    - ' + format_text(detail) for detail in group['details'])
    return lines


def coverage_lines(flows: list[str], *, format_text=markdown_text) -> list[str]:
    return ['- **Cobertura:**'] + ['  - ' + format_text(flow) for flow in
        (flows or ['Sin flujos de cobertura registrados.'])]
