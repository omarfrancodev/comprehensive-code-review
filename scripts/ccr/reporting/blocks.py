"""Pure Markdown blocks shared by private and editorial public renderers."""
from urllib.parse import quote

from ccr.reporting.markdown import markdown_text


def evidence_groups(evidence: list[dict], checks: dict[str, dict]) -> list[dict]:
    groups, by_check, static = [], {}, set()
    for item in evidence:
        identifier, detail = item['check_id'], item['details']
        if identifier is None:
            if detail not in static:
                static.add(detail)
                groups.append(dict(check_id=None, details=[detail]))
            continue
        if identifier not in by_check:
            group = dict(check_id=identifier, details=[])
            groups.append(group)
            by_check[identifier] = group
        details = by_check[identifier]['details']
        if detail != checks[identifier]['evidence'] and detail not in details:
            details.append(detail)
    return groups


def evidence_lines(groups: list[dict]) -> list[str]:
    lines = []
    for group in groups:
        identifier = group['check_id']
        if identifier is None:
            lines.extend('  - **Inspección estática** — ' + markdown_text(detail) for detail in group['details'])
        else:
            lines.append('  - **[' + markdown_text(identifier) + '](#' + quote(identifier, safe='') + ')** — Resultado en Validación.')
            lines.extend('    - ' + markdown_text(detail) for detail in group['details'])
    return lines


def coverage_lines(flows: list[str]) -> list[str]:
    return ['- **Cobertura:**'] + ['  - ' + markdown_text(flow) for flow in
        (flows or ['Sin flujos de cobertura registrados.'])]
