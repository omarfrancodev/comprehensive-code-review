"""Pure normalization and applicability appraisal for review inputs."""
import copy
import re


HASH = re.compile(r'[0-9a-f]{64}')
INPUT_FIELDS = {'scope', 'sources', 'source_set_complete', 'description_identity',
                'requirements_identity', 'plan_identity', 'configuration_identity', 'profile',
                'logical_scope_identity'}
IDENTITY_FIELDS = ('description_identity', 'requirements_identity', 'plan_identity',
                   'configuration_identity', 'profile', 'logical_scope_identity')
CALLER_SOURCE_LIMIT = 64
RETAINED_SOURCE_LIMIT = 4096


def _scope(value):
    from ccr.contracts.scope import require_scope
    require_scope(value)
    return copy.deepcopy(value)


def normalize_inputs(raw: dict, *, caller: bool = True) -> dict:
    """Validate and copy a common input document without filesystem access."""
    if not isinstance(raw, dict) or set(raw) - INPUT_FIELDS or not {'scope', 'sources'}.issubset(raw):
        raise ValueError('review inputs require scope and sources and only supported optional fields')
    result = {'scope': _scope(raw['scope'])}
    sources = raw['sources']
    limit = CALLER_SOURCE_LIMIT if caller else RETAINED_SOURCE_LIMIT
    if not isinstance(sources, dict) or len(sources) > limit:
        raise ValueError(f'review inputs sources must be a map of at most {limit} entries')
    normalized_sources = {}
    by_path = {}
    for reference, digest in sources.items():
        if (not isinstance(reference, str) or not reference.strip() or len(reference) > 500
                or any(ord(char) < 32 for char in reference)
                or not isinstance(digest, str) or not HASH.fullmatch(digest)):
            raise ValueError('review input sources must map bounded references to lowercase SHA-256 hashes')
        path = reference.split('#', 1)[0]
        previous = by_path.get(path)
        if previous is not None and previous != digest:
            raise ValueError('review input fragments for one source disagree on its SHA-256 identity')
        by_path[path] = digest
        normalized_sources[reference] = digest
    result['sources'] = normalized_sources
    if 'source_set_complete' in raw:
        if type(raw['source_set_complete']) is not bool:
            raise ValueError('source_set_complete must be a boolean when supplied')
        result['source_set_complete'] = raw['source_set_complete']
    for field in IDENTITY_FIELDS:
        if field not in raw:
            continue
        value = raw[field]
        if field == 'profile' and value is not None:
            import review_profiles
            value = review_profiles._canonical(value)
        elif field == 'logical_scope_identity' and value is not None and (
                not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{64}', value)):
            raise ValueError('logical_scope_identity must be lowercase SHA-256 or null')
        elif value is not None and (not isinstance(value, str) or not value.strip()
                                    or len(value) > 1000 or any(ord(char) < 32 for char in value)):
            raise ValueError(field + ' must be bounded nonempty text or null')
        result[field] = value
    return result


def compare_inputs(retained: dict | None, current: dict) -> dict:
    """Compare known inputs; omitted or uncaptured identities remain unknown."""
    current = normalize_inputs(current)
    if retained is None:
        return {'applicability': 'unknown', 'differences': [
            {'field': 'review_inputs', 'status': 'unknown',
             'reason': 'The archive did not capture the review inputs.'}]}
    retained = normalize_inputs(retained, caller=False)
    differences = []
    for field in sorted(set(retained['scope']) | set(current['scope'])):
        if field not in retained['scope'] or field not in current['scope']:
            differences.append({'field': 'scope.' + field, 'status': 'unknown',
                                'reason': 'A pinned scope identity is missing.'})
        elif retained['scope'][field] != current['scope'][field]:
            differences.append({'field': 'scope.' + field, 'status': 'changed',
                                'reason': 'The pinned review scope differs.'})

    if retained.get('source_set_complete') is not True or current.get('source_set_complete') is not True:
        differences.append({'field': 'source_set_complete', 'status': 'unknown',
                            'reason': 'The archived or current source set is not explicitly complete.'})
    else:
        old_by_path = {reference.split('#', 1)[0]: digest
                       for reference, digest in retained['sources'].items()}
        new_by_path = {reference.split('#', 1)[0]: digest
                       for reference, digest in current['sources'].items()}
        for path in sorted(set(old_by_path) | set(new_by_path)):
            if path not in old_by_path or path not in new_by_path:
                differences.append({'field': 'sources.' + path, 'status': 'changed',
                                    'reason': 'The complete source set added or removed a source.'})
            elif old_by_path[path] != new_by_path[path]:
                differences.append({'field': 'sources.' + path, 'status': 'changed',
                                    'reason': 'The source content identity differs.'})

    for field in IDENTITY_FIELDS:
        if field == 'logical_scope_identity' and field not in retained and field not in current:
            # Archives created before layout 2 and ordinary callers that do not
            # need an explicit selector have no independent logical identity to compare.
            continue
        if field not in retained or field not in current:
            differences.append({'field': field, 'status': 'unknown',
                                'reason': 'The identity was not explicitly observed on both sides.'})
        elif retained[field] != current[field]:
            differences.append({'field': field, 'status': 'changed',
                                'reason': 'The recorded review input differs.'})
    status = ('changed' if any(row['status'] == 'changed' for row in differences)
              else 'unknown' if differences else 'applicable')
    return {'applicability': status, 'differences': differences}


def candidate_inputs(manifest, record=None):
    captured = manifest.get('review_inputs')
    retained = (copy.deepcopy(captured) if isinstance(captured, dict) else
                {'scope': copy.deepcopy(manifest.get('scope')), 'sources': {},
                 'source_set_complete': False})
    retained.setdefault('scope', manifest.get('scope'))
    history = manifest.get('profile_history')
    if isinstance(history, list) and history and isinstance(history[-1], dict):
        retained['profile'] = history[-1].get('profile')
    elif isinstance(record, dict) and isinstance(record.get('profile'), str):
        retained['profile'] = record['profile']
    return retained


def validate_current_inputs(current_inputs, manifest, *, require_same_scope=True, compare_sources=True,
                            require_applicable=False):
    """Validate common caller inputs and optionally require unchanged captured identities."""
    normalized = normalize_inputs(current_inputs)
    if require_same_scope and normalized['scope'] != manifest.get('scope'):
        raise ValueError('current scope differs from the pinned review scope; restart is required')
    # Callers that resume the exact pinned scope may omit this newer field. The
    # archive's normalized selector is authoritative in that case; changed
    # scopes still need an explicit selector identity and remain unknown.
    if (normalized['scope'] == manifest.get('scope')
            and 'logical_scope_identity' not in normalized):
        logical = manifest.get('logical_scope')
        if isinstance(logical, dict) and isinstance(logical.get('identity'), str):
            normalized['logical_scope_identity'] = logical['identity']
    retained = candidate_inputs(manifest)
    if not compare_sources and retained is not None:
        retained = copy.deepcopy(retained)
        retained['sources'] = copy.deepcopy(normalized['sources'])
        retained['source_set_complete'] = normalized.get('source_set_complete')
    appraisal = compare_inputs(retained, normalized)
    if require_applicable and appraisal['applicability'] != 'applicable':
        raise ValueError('current review inputs are ' + appraisal['applicability']
                         + '; resume requires applicable inputs, use restart when they changed or are unknown')
    return normalized
