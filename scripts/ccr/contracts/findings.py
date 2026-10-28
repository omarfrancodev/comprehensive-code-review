"""Validation of check and finding rows in review result records."""
from ccr.contracts.identifier_types import canonical_id
from ccr.contracts.validation import PRIORITIES, STATES
from ccr.contracts.checks import purpose_errors


def validate_checks(record, schema_version, historical, prior_reviews, versions, state):
    errors = state.errors
    error, fields, array, text = state.error, state.fields, state.array, state.text
    boolean, enum = state.boolean, state.enum
    checks = {}
    for i, raw in enumerate(array(record.get('checks'), 'checks')):
        path = f'checks[{i}]'
        check_names = {'id', 'command', 'revision', 'status', 'failure_kind', 'evidence', 'reused', 'reuse_reason', 'rerun_reason'}
        if schema_version in (6, 7, 8, 9, 10, 11, 12):
            check_names.add('reference')
        if schema_version in (9, 10, 11, 12):
            check_names.add('execution')
        if schema_version in (11, 12):
            check_names.add('purpose')
        check = fields(raw, check_names, path)
        if schema_version in (11, 12):
            errors.extend(purpose_errors(check.get('purpose'), path + '.purpose'))
        for key in ('id', 'command', 'revision'):
            text(check.get(key), f'{path}.{key}')
        identifier = check.get('id')
        if schema_version in (6, 7, 8, 9, 10, 11, 12):
            if not canonical_id(identifier, 'C') and identifier not in historical['checks']:
                error(path + '.id', 'expected canonical check ID C001 (at least three digits, nonzero)')
            text(check.get('reference'), path + '.reference', nullable=check.get('reused') is not True)
            if check.get('reused') is True and check.get('rerun_reason') is not None:
                error(path, 'one execution cannot be both reused and rerun; record rerun with a new ID')
            if identifier in historical['checks'] and (check.get('reused') is not True or not prior_reviews or not check.get('reference')):
                error(path + '.id', 'historical check requires verified previous report and actual execution reference')
        if isinstance(identifier, str):
            if identifier in checks:
                error(path, 'duplicate check id')
            checks[identifier] = check
        enum(check.get('status'), {'passed', 'failed', 'blocked', 'not_run'}, f'{path}.status')
        if check.get('failure_kind') is not None:
            enum(check['failure_kind'], {'product', 'fixture', 'environment'}, f'{path}.failure_kind')
        if check.get('status') == 'failed' and check.get('failure_kind') is None:
            error(f'{path}.failure_kind', 'failed check requires failure classification')
        if check.get('status') != 'failed' and check.get('failure_kind') is not None:
            error(f'{path}.failure_kind', 'only failed checks have failure classification')
        text(check.get('evidence'), f'{path}.evidence', nullable=check.get('status') == 'not_run')
        boolean(check.get('reused'), f'{path}.reused')
        text(check.get('reuse_reason'), f'{path}.reuse_reason', nullable=check.get('reused') is not True)
        if check.get('reused') is not True and check.get('reuse_reason') is not None:
            error(f'{path}.reuse_reason', 'only reused checks have reuse justification')
        text(check.get('rerun_reason'), f'{path}.rerun_reason', nullable=True)
        if not isinstance(check.get('revision'), str) or (check['revision'] not in versions and check.get('reused') is not True):
            error(f'{path}.revision', 'does not match reviewed inputs and is not justified reused evidence')
    return checks


def validate_findings(record, schema_version, stage, historical, checks, state):
    errors = state.errors
    error, fields, array, text = state.error, state.fields, state.array, state.text
    boolean, enum = state.boolean, state.enum
    finding_ids = set()
    findings = array(record.get('findings'), 'findings')
    for i, raw in enumerate(findings):
        path = f'findings[{i}]'
        item = fields(raw, {'id', 'type', 'status', 'priority', 'blocking', 'blocking_reason', 'origin',
                            'title', 'location', 'scenario', 'impact', 'evidence', 'correction'}, path)
        for key in ('id', 'title', 'scenario', 'impact', 'correction'):
            text(item.get(key), f'{path}.{key}')
        identifier = item.get('id')
        if schema_version in (6, 7, 8, 9, 10, 11, 12) and not canonical_id(identifier, 'F') and identifier not in historical['findings']:
            error(path + '.id', 'expected canonical finding ID F001 (at least three digits, nonzero)')
        if isinstance(identifier, str):
            if identifier in finding_ids:
                error(path, 'duplicate finding id')
            finding_ids.add(identifier)
        enum(item.get('type'), {'code', 'description'}, f'{path}.type')
        enum(item.get('status'), STATES, f'{path}.status')
        enum(item.get('priority'), PRIORITIES, f'{path}.priority')
        enum(item.get('origin'), {'introduced', 'preexisting', 'unknown'}, f'{path}.origin')
        boolean(item.get('blocking'), f'{path}.blocking')
        text(item.get('blocking_reason'), f'{path}.blocking_reason', nullable=not item.get('blocking'))
        if item.get('blocking') and item.get('status') != 'confirmed':
            error(f'{path}.blocking', 'only confirmed findings can be blockers')
        if stage == 'discovery' and item.get('status') == 'confirmed':
            error(f'{path}.status', 'discovery emits candidates; confirmation belongs to verification')
        if stage == 'final' and item.get('status') == 'candidate':
            error(f'{path}.status', 'final candidates must be resolved or marked unresolved')
        location = fields(item.get('location'), {'path', 'line', 'url', 'section'}, f'{path}.location')
        for key in ('path', 'url', 'section'):
            text(location.get(key), f'{path}.location.{key}', nullable=True)
        line = location.get('line')
        if line is not None and (type(line) is not int or line < 1):
            error(f'{path}.location.line', 'expected positive line or null')
        if item.get('type') == 'code' and (not location.get('path') or line is None):
            error(f'{path}.location', 'code findings require path and line')
        if item.get('type') == 'description' and not location.get('section'):
            error(f'{path}.location.section', 'description section required; no fabricated code line')
        evidence = array(item.get('evidence'), f'{path}.evidence')
        if not evidence:
            error(f'{path}.evidence', 'evidence required')
        supporting = False
        for j, raw_evidence in enumerate(evidence):
            ev_path = f'{path}.evidence[{j}]'
            ev = fields(raw_evidence, {'kind', 'details', 'check_id'}, ev_path)
            enum(ev.get('kind'), {'static', 'executed'}, f'{ev_path}.kind')
            text(ev.get('details'), f'{ev_path}.details')
            text(ev.get('check_id'), f'{ev_path}.check_id', nullable=ev.get('kind') == 'static')
            if ev.get('kind') == 'static':
                supporting = True
                if ev.get('check_id') is not None:
                    error(f'{ev_path}.check_id', 'static evidence does not reference an executed check')
            elif ev.get('kind') == 'executed':
                check_id = ev.get('check_id')
                check = checks.get(check_id) if isinstance(check_id, str) else None
                if check is None:
                    error(f'{ev_path}.check_id', 'unknown check_id')
                elif not isinstance(check.get('status'), str) or check['status'] not in {'passed', 'failed'}:
                    error(f'{ev_path}.check_id', 'check was not executed')
                elif check.get('failure_kind') is None or (isinstance(check.get('failure_kind'), str) and check['failure_kind'] not in {'fixture', 'environment'}):
                    supporting = True
        if item.get('status') == 'confirmed' and not supporting:
            error(f'{path}.evidence', 'fixture/environment failures do not confirm product defects')
    return findings, finding_ids
