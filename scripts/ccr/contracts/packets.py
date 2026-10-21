"""Pure compact-packet validation and decision-delta merging."""
import copy

from ccr.contracts.review import validate as validate_review
from ccr.contracts.validation import PRIORITIES


def validate(packet, *, reference_index=None, reference_sources=None,
             known_check_ids=None):
    errors = []

    def fail(path, message):
        errors.append(f'{path}: {message}')

    def obj(value, required, optional, path):
        if not isinstance(value, dict):
            fail(path, 'expected object')
            return {}
        if set(value) - required - optional or required - set(value):
            fail(path, 'missing or unknown fields')
        return value

    def text(value, path):
        if not isinstance(value, str) or not value.strip():
            fail(path, 'expected nonempty text')

    def array(value, path):
        if not isinstance(value, list):
            fail(path, 'expected array')
            return []
        return value

    def choice(value, allowed, path):
        if not isinstance(value, str) or value not in allowed:
            fail(path, 'invalid value')

    def location(value, kind, path):
        value = obj(value, set(), {'path', 'line', 'url', 'section'}, path)
        for key in ('path', 'url', 'section'):
            if value.get(key) is not None:
                text(value[key], f'{path}.{key}')
        line = value.get('line')
        if line is not None and (type(line) is not int or line < 1):
            fail(path, 'expected positive line or null')
        if kind == 'code' and (not value.get('path') or line is None):
            fail(path, 'code needs actual path/line')
        if kind == 'description' and not value.get('section'):
            fail(path, 'description needs section')

    def evidence(value, path, check_ids):
        entries = array(value, path)
        if not entries:
            fail(path, 'evidence required')
        for i, entry in enumerate(entries):
            p = f'{path}[{i}]'
            entry = obj(entry, {'kind', 'details'}, {'check_id'}, p)
            choice(entry.get('kind'), {'static', 'executed'}, p + '.kind')
            text(entry.get('details'), p + '.details')
            identifier = entry.get('check_id')
            if entry.get('kind') == 'static' and identifier is not None:
                fail(p, 'static evidence cannot reference an executed check')
            if entry.get('kind') == 'executed' and (not isinstance(identifier, str) or identifier not in check_ids):
                fail(p, 'executed evidence needs a referenced check_id')

    if not isinstance(packet, dict):
        return ['packet: expected object']
    stage = packet.get('stage')
    key = 'findings' if stage == 'discovery' else 'decisions'
    obj(packet, {'packet_version', 'stage', 'context_id', key, 'check_ids', 'coverage'}, set(), 'packet')
    if type(packet.get('packet_version')) is not int or packet.get('packet_version') != 1:
        fail('packet_version', 'unsupported version')
    choice(stage, {'discovery', 'verification'}, 'stage')
    text(packet.get('context_id'), 'context_id')
    check_ids = array(packet.get('check_ids'), 'check_ids')
    seen_checks = set()
    for identifier in check_ids:
        text(identifier, 'check_ids')
        if isinstance(identifier, str):
            if identifier in seen_checks:
                fail('check_ids', 'duplicate check id')
            seen_checks.add(identifier)
    coverage = obj(packet.get('coverage'), {'flows', 'limitations'}, set(), 'coverage')
    for flow in array(coverage.get('flows'), 'coverage.flows'):
        text(flow, 'coverage.flows')
    for limitation in array(coverage.get('limitations'), 'coverage.limitations'):
        limitation = obj(limitation, {'detail', 'material'}, set(), 'coverage.limitations')
        text(limitation.get('detail'), 'coverage.limitations.detail')
        if type(limitation.get('material')) is not bool:
            fail('coverage.limitations.material', 'expected boolean')
    seen = set()
    for i, entry in enumerate(array(packet.get(key), key)):
        path = f'{key}[{i}]'
        required = {'id', 'type', 'location', 'scenario', 'impact', 'evidence'} if stage == 'discovery' else {'id', 'status', 'evidence'}
        entry = obj(entry, required, set() if stage == 'discovery' else {'updates'}, path)
        identifier = entry.get('id')
        text(identifier, path + '.id')
        if isinstance(identifier, str):
            if identifier in seen:
                fail(path, 'duplicate finding/decision id')
            seen.add(identifier)
        evidence(entry.get('evidence'), path + '.evidence', seen_checks)
        if stage == 'discovery':
            choice(entry.get('type'), {'code', 'description'}, path + '.type')
            location(entry.get('location'), entry.get('type'), path + '.location')
            for field in ('scenario', 'impact'):
                text(entry.get(field), path + '.' + field)
        else:
            choice(entry.get('status'), {'confirmed', 'rejected', 'unresolved'}, path + '.status')
            allowed = {'location', 'scenario', 'impact', 'priority', 'origin', 'title', 'correction', 'blocking', 'blocking_reason'}
            updates = obj(entry.get('updates', {}), set(), allowed, path + '.updates')
            for field in ('scenario', 'impact', 'title', 'correction'):
                if field in updates:
                    text(updates[field], path + '.updates.' + field)
            if 'priority' in updates:
                choice(updates['priority'], set(PRIORITIES), path + '.updates.priority')
            if 'origin' in updates:
                choice(updates['origin'], {'introduced', 'preexisting', 'unknown'}, path + '.updates.origin')
            if 'location' in updates:
                location(updates['location'], None, path + '.updates.location')
            if 'blocking' in updates and type(updates['blocking']) is not bool:
                fail(path, 'blocking must be boolean')
            if updates.get('blocking_reason') is not None:
                text(updates['blocking_reason'], path + '.updates.blocking_reason')
            if updates.get('blocking') is True and (entry.get('status') != 'confirmed' or not updates.get('blocking_reason')):
                fail(path, 'blocking needs confirmed status and explicit reason')
    if reference_index is not None:
        from ccr.contracts.semantic_references import validate_semantic_references
        identifiers = (known_check_ids if known_check_ids is not None else check_ids)
        semantic_record = {'checks': [{'id': identifier} for identifier in identifiers
                                      if isinstance(identifier, str)],
                           'coverage': {}}
        diagnostics = validate_semantic_references(
            semantic_record, [packet], reference_index,
            reference_sources if isinstance(reference_sources, dict) else {})
        errors.extend(f"{item['field']}: {item['message']}" for item in diagnostics)
    return list(dict.fromkeys(errors))

def merge(context, discoveries, verification=None, *, reference_index=None,
          reference_sources=None):
    """Return a consolidation bundle, NOT a final/canonical record. Preserve inputs."""
    if not isinstance(context, dict) or not isinstance(context.get('context_id'), str) or not context['context_id'].strip():
        raise ValueError('context requires a nonempty context_id')
    neutral = {'schema_version': 2, 'stage': 'discovery', 'scope': context.get('scope'),
               'findings': [], 'checks': context.get('checks', []), 'coverage': {'flows': [], 'limitations': []}}
    errors = validate_review(neutral)
    if errors:
        raise ValueError('invalid scope/check ledger: ' + '; '.join(errors))
    if not isinstance(discoveries, list) or not discoveries:
        raise ValueError('at least one discovery packet required')
    all_packets = discoveries + ([verification] if verification is not None else [])
    known_check_ids = {item.get('id') for item in context.get('checks', [])
                       if isinstance(item, dict) and isinstance(item.get('id'), str)}
    for index, packet in enumerate(all_packets):
        errors = validate(packet, reference_index=reference_index,
                           reference_sources=reference_sources,
                           known_check_ids=known_check_ids)
        if errors:
            raise ValueError('; '.join(errors))
        expected = 'discovery' if index < len(discoveries) else 'verification'
        if packet['stage'] != expected or packet['context_id'] != context['context_id']:
            raise ValueError('stage/context mismatch: use exact pinned inputs')
    candidates = {}
    for packet in discoveries:
        for item in packet['findings']:
            if item['id'] in candidates:
                raise ValueError('colliding finding IDs: remap once before merge')
            candidates[item['id']] = copy.deepcopy(item)
    if verification is None and any(item['material'] for packet in discoveries for item in packet['coverage']['limitations']):
        raise ValueError('material questions require an explicit verification packet')
    decisions = {item['id']: item for item in verification['decisions']} if verification is not None else {}
    if set(decisions) != set(candidates):
        raise ValueError('every candidate needs exactly one explicit decision; unknown decisions prohibited')
    referenced = set(identifier for packet in all_packets for identifier in packet['check_ids'])
    ledger = {item['id']: item for item in neutral['checks']}
    if referenced - set(ledger):
        raise ValueError('unknown check reference in shared ledger')
    findings, amendments = [], []
    for identifier, candidate in candidates.items():
        decision = decisions[identifier]
        for ev in candidate['evidence'] + decision['evidence']:
            if ev['kind'] == 'executed' and ledger[ev['check_id']]['status'] not in {'passed', 'failed'}:
                raise ValueError('evidence references an unexecuted check')
        decisive = any(ev['kind'] == 'static' or ledger[ev['check_id']]['failure_kind'] not in {'fixture', 'environment'}
                       for ev in decision['evidence'])
        if decision['status'] == 'confirmed' and not decisive:
            raise ValueError('fixture/environment failures cannot confirm a product defect')
        updates = decision.get('updates', {})
        previous = {key: copy.deepcopy(candidate[key]) for key, value in updates.items()
                    if key in candidate and candidate[key] != value}
        if previous:
            amendments.append({'id': identifier, 'previous': previous})
        candidate.update(copy.deepcopy(updates))
        candidate['status'] = decision['status']
        loc = candidate['location']
        if candidate['type'] == 'code' and (not loc.get('path') or type(loc.get('line')) is not int or loc['line'] < 1):
            raise ValueError('updated code location needs path/line')
        if candidate['type'] == 'description' and not loc.get('section'):
            raise ValueError('updated description location needs section')
        candidate['location'] = {key: loc.get(key) for key in ('path', 'line', 'url', 'section')}
        combined = []
        for raw in candidate['evidence'] + decision['evidence']:
            entry = {**raw, 'check_id': raw.get('check_id')}
            if entry not in combined:
                combined.append(entry)
        candidate['evidence'] = combined
        findings.append(candidate)
    flows, limitations = [], []
    for packet in all_packets:
        for flow in packet['coverage']['flows']:
            if flow not in flows:
                flows.append(flow)
        for raw in packet['coverage']['limitations']:
            item = next((item for item in limitations if item['detail'] == raw['detail']), None)
            if item is None:
                limitations.append(copy.deepcopy(raw))
            else:
                item['material'] = item['material'] or raw['material']
    return {'context_id': context['context_id'], 'scope': copy.deepcopy(context['scope']),
            'findings': findings, 'amendments': amendments,
            'checks': [copy.deepcopy(item) for item in neutral['checks'] if item['id'] in referenced],
            'coverage': {'flows': flows, 'limitations': limitations}}
