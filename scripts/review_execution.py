"""Pure validation of observed reviewer assignments; no dispatch, IO or inference."""

from review_profiles import validate_profile_execution


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

    schema_version = record.get('schema_version')
    execution_fields = {'selection_source', 'status', 'plan', 'results', 'fallbacks'}
    if schema_version == 10:
        execution_fields.add('profile_history')
    if not isinstance(execution, dict) or set(execution) != execution_fields:
        return [prefix + ': exact execution fields required']
    if not isinstance(execution['selection_source'], str) or execution['selection_source'] not in ('explicit', 'automatic'):
        fail('invalid selection_source')
    if not isinstance(execution['status'], str) or execution['status'] not in ('fulfilled', 'degraded'):
        fail('invalid status')
    plan_fields = {'id', 'role', 'independent', 'required', 'reference'}
    if schema_version == 10:
        plan_fields |= {'selection_id', 'superseded_by'}
    plan = rows('plan', plan_fields)
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
        if not isinstance(row['role'], str) or row['role'] not in ('discovery', 'verification', 'project_gate'):
            fail('invalid assignment role')
            continue
        if type(row['independent']) is not bool or type(row['required']) is not bool:
            fail('assignment flags must be booleans')
            continue
        if schema_version == 10 and (not isinstance(row.get('selection_id'), str)
                                     or row.get('superseded_by') is not None
                                     and not isinstance(row.get('superseded_by'), str)):
            fail('assignment selection/supersession IDs must be text or null')
            continue
        if row['required'] is not True and not (schema_version == 10 and row['required'] is False
                                                 and isinstance(row.get('superseded_by'), str)):
            fail('planned assignments must be required; omit unnecessary passes')
        if row['role'] == 'project_gate' and row['independent'] is not True:
            fail('project_gate must be independent with a policy reference')
        if schema_version == 10 and row.get('superseded_by') is not None and row.get('role') == 'project_gate':
            fail('project_gate cannot be superseded')
    if errors:
        return errors
    active_plan = [row for row in plan if row.get('superseded_by') is None]
    discovery = [row for row in active_plan if row['role'] == 'discovery']
    verification = [row for row in active_plan if row['role'] == 'verification']
    profile = record.get('profile') if isinstance(record.get('profile'), str) else None
    profile_source = execution['selection_source']
    if schema_version == 10 and isinstance(execution.get('profile_history'), list):
        history_by_id = {row.get('id'): row for row in execution['profile_history']
                         if isinstance(row, dict) and isinstance(row.get('id'), str)}
        active_rows = [row for row in plan if row.get('superseded_by') is None]
        rank = {'focused': 0, 'standard': 1, 'deep': 2, 'extended': 3}
        active_profiles = [history_by_id[row.get('selection_id')]['profile'] for row in active_rows
                           if isinstance(row.get('selection_id'), str)
                           and row.get('selection_id') in history_by_id
                           and isinstance(history_by_id[row.get('selection_id')].get('profile'), str)
                           and history_by_id[row.get('selection_id')]['profile'] in rank]
        if isinstance(record.get('profile'), str) and record['profile'] in rank:
            active_profiles.append(record['profile'])
        if active_profiles:
            profile = max(active_profiles, key=lambda item: rank.get(item, -1))
            selected = next((row for row in reversed(execution['profile_history'])
                             if isinstance(row, dict) and row.get('profile') == profile), None)
            if selected is not None:
                profile_source = selected.get('selection_source', profile_source)
    if schema_version == 10 and profile == 'extended' and isinstance(execution.get('profile_history'), list):
        history_by_id = {row.get('id'): row for row in execution['profile_history']
                         if isinstance(row, dict) and isinstance(row.get('id'), str)}
        if any(row.get('superseded_by') is None and isinstance(row.get('selection_id'), str)
               and history_by_id.get(row.get('selection_id'), {}).get('profile') == 'extended'
               and history_by_id.get(row.get('selection_id'), {}).get('selection_source') == 'automatic'
               for row in plan):
            profile_source = 'automatic'
    limits = {'focused': (1, 1), 'standard': (1, 1), 'deep': (2, 3),
              'extended': (4, 5) if profile_source == 'automatic' else (2, 5)}
    minimum, maximum = limits.get(profile, (0, 0)) if isinstance(profile, str) else (0, 0)
    qualifying_discovery = ([row for row in discovery if row['independent'] is True]
                            if schema_version == 10 and profile in ('deep', 'extended') else discovery)
    if not minimum <= len(qualifying_discovery) <= maximum:
        fail('discovery cardinality does not match profile/selection')
    independent_profile = profile in ('deep', 'extended')
    substantive = any(isinstance(row, dict) and row.get('type') == 'code' and row.get('status') in ('confirmed', 'unresolved')
                      for row in (record.get('findings') if isinstance(record.get('findings'), list) else []))
    material = any(isinstance(row, dict) and row.get('material') is True
                   for key in ('limitations', 'areas') for row in (coverage.get(key) or [])
                   if isinstance(coverage.get(key), list))
    needs_fresh = independent_profile or profile == 'standard' and (substantive or material)
    needs_verifier = profile == 'focused' or needs_fresh or coverage.get('verification') not in ('skipped', 'unavailable')
    if schema_version == 10:
        if needs_verifier and not verification:
            fail('verification requires a grouped assignment when applicable')
        if independent_profile and not any(row['independent'] is True for row in verification):
            fail('verification independence required by profile')
        if needs_fresh and not any(row['independent'] is True for row in verification):
            fail('verification independence required by final acquired strategy')
    else:
        if len(verification) != (1 if needs_verifier else 0):
            fail('verification requires one grouped assignment when applicable')
        if independent_profile and any(row['independent'] is not True for row in discovery):
            fail('discovery independence required by profile')
        if needs_fresh and any(row['independent'] is not True for row in verification):
            fail('verification independence required by profile')
    if profile == 'focused' and (schema_version != 10 or not independent_profile) and any(
            row['independent'] is not False for row in discovery + verification):
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
    active_ids = {row['id'] for row in active_plan}
    missing = active_ids - set(observed)
    if any(identifier in assignments and assignments[identifier].get('superseded_by') is not None
           for identifier in observed):
        fail('superseded assignment cannot have a completed result')
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
    if schema_version == 10:
        latest_verifier = verification[-1] if verification else None
        latest_result = observed.get(latest_verifier['id']) if latest_verifier is not None else None
        effective = ('unavailable' if latest_result is None else 'independent' if
                     latest_verifier['id'] not in missing and latest_verifier['independent'] is True
                     else 'same_session')
    else:
        verifiers = [observed[row['id']] for row in verification if row.get('id') in observed]
        effective = ('unavailable' if not verifiers else 'independent' if
                     all(row['id'] not in missing and row['independent'] is True for row in verification)
                     else 'same_session')
    if not verification and coverage.get('verification') == 'skipped':
        effective = 'skipped'
    if coverage.get('verification') != effective:
        fail('coverage.verification contradicts completed verification/independence')
    unmet_gates = [row for row in active_plan if row['role'] == 'project_gate' and row.get('id') in missing]
    if unmet_gates and not material:
        fail('unmet required project_gate needs a material coverage gap')
    return errors


def validate_execution_sources(record, context, trace_events, retained_references, *, assignment_registry=None):
    """Contrast declared passes with retained facts and existing trace milestones."""
    errors = validate_execution(record)
    if errors:
        return errors
    execution = record['coverage']['execution']
    schema10 = record.get('schema_version') == 10
    prefix = 'coverage.execution.sources: '
    if not isinstance(context, dict) or context.get('profile') != record.get('profile'):
        return [prefix + 'context profile differs from final profile']
    if context.get('selection_source') != execution['selection_source']:
        return [prefix + 'selection_source differs from observed context']
    registry = assignment_registry
    if schema10:
        context_plan = context.get('execution_plan')
        if not isinstance(context_plan, list):
            return [prefix + 'context execution_plan is required for schema 10']
        if registry is None:
            registry = context_plan
        if context_plan != registry:
            errors.append(prefix + 'context execution_plan differs from the durable assignment registry')
        errors.extend(validate_profile_execution(record, trace_events, assignment_registry=registry))
        if context.get('profile_history') != execution.get('profile_history'):
            errors.append(prefix + 'profile history differs from the captured context')
    history = (execution.get('profile_history') if schema10 else
               context.get('profile_history', [dict(profile=context.get('profile'), reference=context.get('profile_reference'))]))
    if not isinstance(history, list) or not history:
        return [prefix + 'observed profile source required']
    if not isinstance(trace_events, list):
        return errors + [prefix + 'trace events must be an array']
    normalized_events = []
    for index, event in enumerate(trace_events):
        if not isinstance(event, dict):
            errors.append(prefix + f'trace event {index} must be an object')
            continue
        current = event
        if not isinstance(event.get('evidence', []), list) or any(
                not isinstance(item, str) for item in event.get('evidence', [])):
            errors.append(prefix + f'trace event {index} evidence must be an array of text references')
            current = dict(current, evidence=[])
        if current.get('sequence') is not None and type(current.get('sequence')) is not int:
            errors.append(prefix + f'trace event {index} sequence must be an integer')
            current = dict(current, sequence=-1)
        normalized_events.append(current)
    trace_events = normalized_events
    previous_sequence = -1
    previous_profile = None
    rank = {'focused': 0, 'standard': 1, 'deep': 2, 'extended': 3}
    work = [event for event in trace_events if isinstance(event, dict)
            and event.get('kind') in ('agent', 'discovery', 'grouped-verification')
            and event.get('status') in ('started', 'completed', 'passed', 'failed', 'blocked', 'skipped')]
    observed_plan = registry if schema10 and isinstance(registry, list) else execution['plan']
    ordinary_refs = {row['reference'] for row in observed_plan if isinstance(row, dict)
                     and isinstance(row.get('reference'), str) and row.get('role') != 'project_gate'}
    starts = [event for event in work if event.get('status') == 'started'
              and isinstance(event.get('evidence'), list)
              and ordinary_refs.intersection(event.get('evidence', []))]
    for index, row in enumerate(history):
        if (not isinstance(row, dict) or (not schema10 and set(row) != {'profile', 'reference'})
                or not _text(row.get('reference'))
                or row.get('profile') not in ('focused', 'standard', 'deep', 'extended')):
            errors.append(prefix + 'invalid profile transition source')
            continue
        if not schema10 and execution['selection_source'] == 'explicit' and row['profile'] != record['profile']:
            errors.append(prefix + 'explicit profile must remain fixed')
        if not schema10 and previous_profile is not None and rank[row['profile']] < rank[previous_profile]:
            errors.append(prefix + 'automatic profile history must not downgrade')
        previous_profile = row['profile']
        matches = [event for event in trace_events if event.get('kind') == 'profile'
                   and row['reference'] in event.get('evidence', []) and event.get('status') in ('selected', 'completed')
                   and (not schema10 or event.get('event_id') == row.get('event_id'))]
        if row['reference'] not in retained_references or not matches:
            errors.append(prefix + 'profile transition needs retained source and observed milestone')
        elif matches[-1].get('sequence', 0) <= previous_sequence:
            errors.append(prefix + 'profile transitions must follow observed recording order')
        else:
            previous_sequence = matches[-1].get('sequence', 0)
            if index == 0 and any(event.get('sequence', 0) <= previous_sequence for event in work):
                errors.append(prefix + 'initial profile selection must precede observed review work')
            if schema10 and index > 0:
                assigned_refs = {item['reference'] for item in observed_plan if isinstance(item, dict)
                                 and item.get('selection_id') == row.get('id')
                                 and isinstance(item.get('reference'), str)}
                if any(event.get('sequence', 0) <= previous_sequence and assigned_refs.intersection(event.get('evidence', []))
                       for event in starts):
                    errors.append(prefix + 'profile transition must precede work under its selection')
            if not schema10 and index > 0 and not any(event.get('sequence', 0) > previous_sequence for event in (starts or work)):
                errors.append(prefix + 'profile escalation must precede subsequent ordinary review work')
    if not isinstance(history[-1], dict) or history[-1].get('profile') != record['profile']:
        errors.append(prefix + 'last observed profile must match final profile')
    for row in execution['plan']:
        if row['reference'] not in retained_references:
            errors.append(prefix + 'assignment brief/policy source is not retained: ' + row['id'])
    if schema10:
        for row in observed_plan:
            if isinstance(row, dict) and isinstance(row.get('reference'), str) and row['reference'] not in retained_references:
                errors.append(prefix + 'captured assignment brief/policy source is not retained: ' + str(row.get('id')))
    for result in execution['results']:
        assignment = next(row for row in execution['plan'] if row['id'] == result['assignment_id'])
        kind = 'discovery' if assignment['role'] == 'discovery' else 'grouped-verification'
        matches = [event for event in trace_events if event.get('kind') == kind
                   and event.get('status') in ('completed', 'passed')
                   and result['reference'] in event.get('evidence', [])
                   and isinstance(event.get('actor'), dict)
                   and event.get('actor', {}).get('name') == result['reviewer_context']
                   and event.get('actor', {}).get('provider_id') == result['provider_id']]
        if result['reference'] not in retained_references or not matches:
            errors.append(prefix + 'completed reviewer result lacks matching observed milestone/source')
            continue
        if assignment['independent'] and assignment['id'] not in {item for row in execution['fallbacks'] for item in row['assignments']}:
            dispatches = [event for event in trace_events if event.get('kind') == 'agent'
                          and event.get('status') == 'started' and assignment['reference'] in event.get('evidence', [])
                          and isinstance(event.get('executor'), dict)
                          and event['executor'].get('name') == result['reviewer_context']
                          and event['executor'].get('provider_id') == result['provider_id']
                          and event.get('sequence', 0) < matches[-1].get('sequence', 0)]
            if not dispatches:
                errors.append(prefix + 'independent result lacks observed dispatch')

    if schema10:
        active_plan = [row for row in execution['plan'] if row.get('superseded_by') is None]
        rank = {'focused': 0, 'standard': 1, 'deep': 2, 'extended': 3}
        history_by_id = {row['id']: row for row in history if isinstance(row, dict)
                         and isinstance(row.get('id'), str)}
        selected_profiles = [history_by_id[row['selection_id']]['profile'] for row in active_plan
                             if isinstance(row.get('selection_id'), str)
                             and row.get('selection_id') in history_by_id
                             and isinstance(history_by_id[row['selection_id']].get('profile'), str)
                             and history_by_id[row['selection_id']]['profile'] in rank]
        if isinstance(record.get('profile'), str) and record['profile'] in rank:
            selected_profiles.append(record['profile'])
        if not selected_profiles:
            return errors + [prefix + 'profile history has no recognized selection']
        strongest = max(selected_profiles, key=rank.get)
        findings_rows = record.get('findings') if isinstance(record.get('findings'), list) else []
        coverage_data = record.get('coverage') if isinstance(record.get('coverage'), dict) else {}
        substantive = any(isinstance(row, dict) and row.get('type') == 'code'
                         and row.get('status') in ('confirmed', 'unresolved') for row in findings_rows)
        material = any(isinstance(row, dict) and row.get('material') is True
                       for key in ('limitations', 'areas')
                       for row in (coverage_data.get(key) if isinstance(coverage_data.get(key), list) else []))
        final_discoveries = [row for row in active_plan if row.get('role') == 'discovery']
        discovery_sequences = []
        for assignment in final_discoveries:
            result = next((item for item in execution['results']
                           if item.get('assignment_id') == assignment['id']), None)
            if result is None:
                continue
            matches = [event for event in trace_events if isinstance(event, dict)
                       and event.get('kind') == 'discovery'
                       and event.get('status') in ('completed', 'passed')
                       and isinstance(event.get('evidence'), list)
                       and result['reference'] in event['evidence']]
            sequences = [event.get('sequence') for event in matches if type(event.get('sequence')) is int]
            if sequences:
                discovery_sequences.append(max(sequences))
        last_discovery = max(discovery_sequences, default=-1)
        final_candidates = []
        require_independent = strongest in ('deep', 'extended') or (
            strongest == 'standard' and (substantive or material))
        for assignment in active_plan:
            if assignment.get('role') != 'verification' or (require_independent
                    and assignment.get('independent') is not True):
                continue
            assignment_selection = history_by_id.get(assignment.get('selection_id'), {})
            if assignment_selection.get('profile') != strongest:
                continue
            result = next((item for item in execution['results']
                           if item.get('assignment_id') == assignment['id']), None)
            if result is None:
                continue
            completions = [event for event in trace_events if isinstance(event, dict)
                           and event.get('kind') == 'grouped-verification'
                           and event.get('status') in ('completed', 'passed')
                           and isinstance(event.get('evidence'), list)
                           and result['reference'] in event['evidence']
                           and isinstance(event.get('actor'), dict)
                           and (event.get('actor') or {}).get('name') == result['reviewer_context']
                           and (event.get('actor') or {}).get('provider_id') == result['provider_id']]
            starts_for_verifier = [event for event in trace_events if isinstance(event, dict)
                                   and event.get('status') == 'started'
                                   and event.get('kind') in ('agent', 'grouped-verification')
                                   and isinstance(event.get('evidence'), list)
                                   and assignment['reference'] in event['evidence']
                                   and ((isinstance(event.get('executor'), dict)
                                         and event['executor'].get('name') == result['reviewer_context'])
                                        or (isinstance(event.get('actor'), dict)
                                            and event['actor'].get('name') == result['reviewer_context']))]
            if any(type(event.get('sequence')) is int and event['sequence'] > last_discovery
                   for event in completions) and any(type(event.get('sequence')) is int
                                                     and event['sequence'] > last_discovery
                                                     for event in starts_for_verifier):
                final_candidates.append(assignment)
        if len(final_candidates) != 1:
            if execution.get('status') == 'fulfilled':
                errors.append(prefix + 'fulfilled review requires one fresh verifier after the final discovery batch')
            elif record.get('coverage', {}).get('verification') != 'unavailable':
                errors.append(prefix + 'degraded review without a fresh final-batch verifier must report verification unavailable')
        else:
            expected = 'independent' if final_candidates[0].get('independent') is True else 'same_session'
            if record.get('coverage', {}).get('verification') != expected:
                errors.append(prefix + 'fresh final-batch verifier status contradicts its independent context')
    for row in execution['fallbacks']:
        if row['source'] not in retained_references or not any(event.get('kind') in ('agent', 'interruption')
                and event.get('status') in ('failed', 'blocked', 'skipped') and row['source'] in event.get('evidence', [])
                for event in trace_events):
            errors.append(prefix + 'fallback lacks retained observed impediment source')
    return errors
