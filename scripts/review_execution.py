"""Pure validation of observed reviewer assignments; no dispatch, IO or inference."""


def _text(value):
    return isinstance(value, str) and bool(value.strip()) and len(value) <= 4000


def validate_execution(record):
    errors = []
    coverage = record.get('coverage', {})
    execution = coverage.get('execution') if isinstance(coverage, dict) else None
    prefix = 'coverage.execution'

    def fail(detail):
        errors.append(prefix + ': ' + detail)

    def rows(key, fields):
        values = execution.get(key)
        if not isinstance(values, list):
            fail(key + ' must be an array')
            return []
        valid = []
        for row in values:
            if not isinstance(row, dict) or set(row) != fields:
                fail('invalid ' + key + ' fields')
            else:
                valid.append(row)
        return valid

    if not isinstance(execution, dict) or set(execution) != {'selection_source', 'status', 'plan', 'results', 'fallbacks'}:
        return [prefix + ': exact execution fields required']
    if execution['selection_source'] not in ('explicit', 'automatic'):
        fail('invalid selection_source')
    if execution['status'] not in ('fulfilled', 'degraded'):
        fail('invalid status')
    plan = rows('plan', {'id', 'role', 'independent', 'required', 'reference'})
    results = rows('results', {'assignment_id', 'reviewer_context', 'provider_id', 'reference'})
    fallbacks = rows('fallbacks', {'assignments', 'reason', 'detail', 'source'})
    assignments = {}
    for row in plan:
        if not all(_text(row[key]) for key in ('id', 'reference')):
            fail('plan ID/reference must be nonempty text')
            continue
        if row['id'] in assignments:
            fail('duplicate assignment ID')
        assignments[row['id']] = row
        if row['role'] not in ('discovery', 'verification', 'project_gate'):
            fail('invalid assignment role')
        if type(row['independent']) is not bool or type(row['required']) is not bool:
            fail('assignment flags must be booleans')
        if row['required'] is not True:
            fail('planned assignments must be required; omit unnecessary passes')
        if row['role'] == 'project_gate' and row['independent'] is not True:
            fail('project_gate must be independent with a policy reference')
    if errors:
        return errors
    discovery = [row for row in plan if row['role'] == 'discovery']
    verification = [row for row in plan if row['role'] == 'verification']
    profile = record.get('profile')
    limits = {'focused': (1, 1), 'standard': (1, 1), 'deep': (2, 3),
              'extended': (4, 5) if execution['selection_source'] == 'automatic' else (2, 5)}
    minimum, maximum = limits.get(profile, (0, 0)) if isinstance(profile, str) else (0, 0)
    if not minimum <= len(discovery) <= maximum:
        fail('discovery cardinality does not match profile/selection')
    independent_profile = profile in ('deep', 'extended')
    substantive = any(isinstance(row, dict) and row.get('type') == 'code' and row.get('status') in ('confirmed', 'unresolved')
                      for row in (record.get('findings') if isinstance(record.get('findings'), list) else []))
    material = any(isinstance(row, dict) and row.get('material') is True
                   for key in ('limitations', 'areas') for row in (coverage.get(key) or [])
                   if isinstance(coverage.get(key), list))
    needs_fresh = independent_profile or profile == 'standard' and (substantive or material)
    needs_verifier = profile == 'focused' or needs_fresh or coverage.get('verification') not in ('skipped', 'unavailable')
    if len(verification) != (1 if needs_verifier else 0):
        fail('verification requires one grouped assignment when applicable')
    if independent_profile and any(row['independent'] is not True for row in discovery):
        fail('discovery independence required by profile')
    if needs_fresh and any(row['independent'] is not True for row in verification):
        fail('verification independence required by profile')
    if profile == 'focused' and any(row['independent'] is not False for row in discovery + verification):
        fail('focused uses one discovery and same-context skeptical verification')
    observed = {}
    for row in results:
        if not all(_text(row[key]) for key in ('assignment_id', 'reviewer_context', 'reference')):
            fail('result identity/reference must be nonempty text')
            continue
        if row['provider_id'] is not None and not _text(row['provider_id']):
            fail('provider_id must be observed text or null')
        if row['assignment_id'] not in assignments or row['assignment_id'] in observed:
            fail('unknown or duplicate completed assignment')
        observed[row['assignment_id']] = row
    ordinary_ids = {row['id'] for row in discovery + verification}
    if profile == 'focused' and len({row['reviewer_context'] for identifier, row in observed.items()
                                     if identifier in ordinary_ids}) > 1:
        fail('focused skeptical verification must use the same context as discovery')
    impeded = set()
    for row in fallbacks:
        ids = row['assignments']
        if not isinstance(ids, list) or not ids or any(not _text(item) for item in ids):
            fail('fallback assignments must be nonempty IDs')
            continue
        if len(set(ids)) != len(ids) or any(item not in assignments for item in ids):
            fail('unknown or duplicate fallback assignment')
        if row['reason'] not in ('tool_unavailable', 'explicit_restriction', 'dispatch_failed', 'quota_exhausted'):
            fail('invalid fallback reason')
        if not _text(row['detail']) or not _text(row['source']):
            fail('fallback needs observed source and internal detail')
        impeded.update(ids)
    missing = set(assignments) - set(observed)
    for identifier, row in observed.items():
        assignment = assignments.get(identifier)
        if assignment is None or assignment['independent'] is not True:
            continue
        repeated = [other_id for other_id, other in observed.items() if other_id != identifier and
                    (other['reviewer_context'] == row['reviewer_context'] or
                     row['provider_id'] is not None and other['provider_id'] == row['provider_id'])]
        if repeated:
            missing.add(identifier)
    if execution['status'] == 'fulfilled' and (missing or fallbacks):
        fail('fulfilled requires every assignment and reviewer independence, without fallbacks')
    if execution['status'] == 'degraded' and (not fallbacks or missing - impeded):
        fail('degraded requires observed fallback for every unmet assignment/independence requirement')
    if execution['status'] == 'degraded':
        # An observed fallback pass does not satisfy the planned fresh context.
        missing.update(impeded)
    verifiers = [observed[row['id']] for row in verification if row.get('id') in observed]
    effective = ('unavailable' if not verifiers else 'independent' if
                 all(row['id'] not in missing and row['independent'] is True for row in verification)
                 else 'same_session')
    if not verification and coverage.get('verification') == 'skipped':
        effective = 'skipped'
    if coverage.get('verification') != effective:
        fail('coverage.verification contradicts completed verification/independence')
    unmet_gates = [row for row in plan if row['role'] == 'project_gate' and row.get('id') in missing]
    if unmet_gates and not material:
        fail('unmet required project_gate needs a material coverage gap')
    return errors


def validate_execution_sources(record, context, trace_events, retained_references):
    """Contrast declared passes with retained facts and existing trace milestones."""
    errors = validate_execution(record)
    if errors:
        return errors
    execution = record['coverage']['execution']
    prefix = 'coverage.execution.sources: '
    if not isinstance(context, dict) or context.get('profile') != record['profile']:
        return [prefix + 'context profile differs from final profile']
    if context.get('selection_source') != execution['selection_source']:
        return [prefix + 'selection_source differs from observed context']
    history = context.get('profile_history', [dict(profile=context.get('profile'), reference=context.get('profile_reference'))])
    if not isinstance(history, list) or not history:
        return [prefix + 'observed profile source required']
    previous_sequence = -1
    previous_profile = None
    rank = {'focused': 0, 'standard': 1, 'deep': 2, 'extended': 3}
    work = [event for event in trace_events if event.get('kind') in ('agent', 'discovery', 'grouped-verification')
            and event.get('status') in ('started', 'completed', 'passed', 'failed', 'blocked', 'skipped')]
    ordinary_refs = {row['reference'] for row in execution['plan'] if row['role'] != 'project_gate'}
    starts = [event for event in work if event.get('status') == 'started'
              and ordinary_refs.intersection(event.get('evidence', []))]
    for index, row in enumerate(history):
        if (not isinstance(row, dict) or set(row) != {'profile', 'reference'} or not _text(row.get('reference'))
                or row.get('profile') not in ('focused', 'standard', 'deep', 'extended')):
            errors.append(prefix + 'invalid profile transition source')
            continue
        if execution['selection_source'] == 'explicit' and row['profile'] != record['profile']:
            errors.append(prefix + 'explicit profile must remain fixed')
        if previous_profile is not None and rank[row['profile']] < rank[previous_profile]:
            errors.append(prefix + 'automatic profile history must not downgrade')
        previous_profile = row['profile']
        matches = [event for event in trace_events if event.get('kind') == 'profile'
                   and row['reference'] in event.get('evidence', []) and event.get('status') in ('selected', 'completed')]
        if row['reference'] not in retained_references or not matches:
            errors.append(prefix + 'profile transition needs retained source and observed milestone')
        elif matches[-1].get('sequence', 0) <= previous_sequence:
            errors.append(prefix + 'profile transitions must follow observed recording order')
        else:
            previous_sequence = matches[-1].get('sequence', 0)
            if index == 0 and any(event.get('sequence', 0) <= previous_sequence for event in work):
                errors.append(prefix + 'initial profile selection must precede observed review work')
            if index > 0 and not any(event.get('sequence', 0) > previous_sequence for event in (starts or work)):
                errors.append(prefix + 'profile escalation must precede subsequent ordinary review work')
    if not isinstance(history[-1], dict) or history[-1].get('profile') != record['profile']:
        errors.append(prefix + 'last observed profile must match final profile')
    for row in execution['plan']:
        if row['reference'] not in retained_references:
            errors.append(prefix + 'assignment brief/policy source is not retained: ' + row['id'])
    for result in execution['results']:
        assignment = next(row for row in execution['plan'] if row['id'] == result['assignment_id'])
        kind = 'discovery' if assignment['role'] == 'discovery' else 'grouped-verification'
        matches = [event for event in trace_events if event.get('kind') == kind
                   and event.get('status') in ('completed', 'passed')
                   and result['reference'] in event.get('evidence', [])
                   and event.get('actor', {}).get('name') == result['reviewer_context']
                   and event.get('actor', {}).get('provider_id') == result['provider_id']]
        if result['reference'] not in retained_references or not matches:
            errors.append(prefix + 'completed reviewer result lacks matching observed milestone/source')
            continue
        if assignment['independent'] and assignment['id'] not in {item for row in execution['fallbacks'] for item in row['assignments']}:
            dispatches = [event for event in trace_events if event.get('kind') == 'agent'
                          and event.get('status') == 'started' and assignment['reference'] in event.get('evidence', [])
                          and (event.get('executor') or {}).get('name') == result['reviewer_context']
                          and (event.get('executor') or {}).get('provider_id') == result['provider_id']
                          and event.get('sequence', 0) < matches[-1].get('sequence', 0)]
            if not dispatches:
                errors.append(prefix + 'independent result lacks observed dispatch')
    for row in execution['fallbacks']:
        if row['source'] not in retained_references or not any(event.get('kind') in ('agent', 'interruption')
                and event.get('status') in ('failed', 'blocked', 'skipped') and row['source'] in event.get('evidence', [])
                for event in trace_events):
            errors.append(prefix + 'fallback lacks retained observed impediment source')
    return errors
