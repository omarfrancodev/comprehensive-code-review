"""Pure duplicate grouping and typed identifier allocation."""
import copy
import re

from ccr.contracts.identifier_types import canonical_id
from ccr.contracts.review import validate


def deduplicate(findings, groups):
    """Group only coordinator-supplied same-cause IDs; preserve every original candidate."""
    if not isinstance(findings, list) or not isinstance(groups, list):
        raise ValueError('findings and groups must be arrays')
    by_id = {}
    for item in findings:
        if not isinstance(item, dict) or not isinstance(item.get('id'), str) or item['id'] in by_id:
            raise ValueError('candidate IDs must be unique strings')
        by_id[item['id']] = item
    used = set()
    output = []
    for group in groups:
        if not isinstance(group, list) or not group:
            raise ValueError('each group must be a nonempty ID array')
        if any(not isinstance(identifier, str) or identifier not in by_id or identifier in used for identifier in group) or len(set(group)) != len(group):
            raise ValueError('unknown or overlapping group ID')
        used.update(group)
        output.append({'id': group[0], 'member_ids': list(group), 'candidates': [by_id[i] for i in group]})
    output.extend({'id': identifier, 'member_ids': [identifier], 'candidates': [item]}
                  for identifier, item in by_id.items() if identifier not in used)
    return output

def canonicalize_ids(record, reserved_ids=None):
    """Allocate once, preserving published IDs; atomically remap typed references.

    Role-qualified provisional IDs are allocation inputs, never semantic aliases.
    Return a fresh record and source maps; caller must retain these maps as evidence.
    Existing canonical IDs and explicitly disclosed historical IDs remain unchanged.
    """
    if not isinstance(record, dict) or record.get('schema_version') not in (6, 7, 8, 9, 10):
        raise ValueError('canonical ID allocation requires schema 6–10')
    errors = [error for error in validate(record) if 'expected canonical' not in error]
    if errors:
        raise ValueError('; '.join(errors))
    result = copy.deepcopy(record)
    history = record.get('grandfathered_ids', {'findings': [], 'checks': []})
    reserved_ids = reserved_ids or {'findings': [], 'checks': []}
    if not isinstance(reserved_ids, dict) or set(reserved_ids) != {'findings', 'checks'}:
        raise ValueError('reserved_ids requires findings/checks arrays from the known review chain')
    for kind, prefix in (('findings', 'F'), ('checks', 'C')):
        if not isinstance(reserved_ids[kind], list) or any(not isinstance(identifier, str) or not identifier.strip() for identifier in reserved_ids[kind]):
            raise ValueError('reserved ID arrays require actual prior identifier strings')

    def allocate(identifiers, prefix, historic, reserved):
        identifiers = list(dict.fromkeys(identifiers))
        used = set(historic) | set(reserved)
        for identifier in identifiers:
            if canonical_id(identifier, prefix):
                used.add(identifier)
            elif identifier not in historic and (not isinstance(identifier, str) or not re.fullmatch(r'[A-Z][A-Z0-9]*-' + prefix + r'[0-9]{3,}', identifier) or int(identifier.rsplit('-', 1)[1][1:]) == 0):
                raise ValueError('only qualified provisional IDs may be allocated; disclose and preserve published historical IDs')
        mapping = {}
        next_number = max((int(identifier[1:]) for identifier in used if canonical_id(identifier, prefix)), default=0) + 1
        for identifier in identifiers:
            if canonical_id(identifier, prefix) or identifier in historic:
                mapping[identifier] = identifier
                continue
            while f'{prefix}{next_number:03d}' in used:
                next_number += 1
            mapping[identifier] = f'{prefix}{next_number:03d}'
            used.add(mapping[identifier])
        return mapping

    finding_sources = [item['id'] for item in result.get('findings', [])]
    if len(set(finding_sources)) != len(finding_sources):
        raise ValueError('duplicate finding IDs; qualify sources before allocation')
    check_sources = [item['id'] for item in result.get('checks', [])]
    if len(set(check_sources)) != len(check_sources):
        raise ValueError('duplicate check IDs; qualify sources before allocation')
    finding_sources += [item['id'] for item in result.get('rereview', [])]
    finding_sources += list(result.get('aliases', {}))
    finding_map = allocate(finding_sources, 'F', history.get('findings', []), reserved_ids['findings'])
    check_map = allocate(check_sources, 'C', history.get('checks', []), reserved_ids['checks'])

    def mapped(mapping, identifier):
        if identifier not in mapping:
            raise ValueError('unknown reference during atomic allocation: ' + str(identifier))
        return mapping[identifier]

    for item in result.get('findings', []):
        item['id'] = mapped(finding_map, item['id'])
        for ev in item.get('evidence', []):
            if ev.get('check_id') is not None:
                ev['check_id'] = mapped(check_map, ev['check_id'])
    for item in result.get('checks', []):
        item['id'] = mapped(check_map, item['id'])
    for area in result.get('coverage', {}).get('areas', []):
        area['finding_ids'] = [mapped(finding_map, identifier) for identifier in area.get('finding_ids', [])]
    for row in result.get('rereview', []):
        row['id'] = mapped(finding_map, row['id'])
        row['check_ids'] = [mapped(check_map, identifier) for identifier in row.get('check_ids', [])]
    result['aliases'] = {mapped(finding_map, source): mapped(finding_map, survivor)
                         for source, survivor in result.get('aliases', {}).items()}
    errors = validate(result)
    if errors:
        raise ValueError('; '.join(errors))
    return result, {'findings': finding_map, 'checks': check_map}
