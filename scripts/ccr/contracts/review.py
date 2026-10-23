"""Validation and pure semantic checks for review result records."""
import json
import re

from ccr.contracts.execution import validate_execution, validate_profile_execution
from ccr.contracts.findings import validate_checks, validate_findings
from ccr.contracts.identifier_types import canonical_id, review_id
from ccr.contracts.provenance import validate_check_execution
from ccr.contracts.scope import validate_scope
from ccr.contracts.validation import (
    AREAS, AREA_STATUS, CURRENT_PROFILES, DESCRIPTION, PRIORITIES, REREVIEW_STATUS,
    REVIEW_KINDS, STATES, VERDICTS, VERIFICATION, ValidationState,
)
from ccr.reporting.projections import public_url


def validate_reference_semantics(record, context, reference_index, sources, packets=None):
    """Validate opt-in guided-reference semantics without changing record schemas."""
    from ccr.contracts.material_inputs import validate_material_inputs
    from ccr.contracts.semantic_references import validate_semantic_references
    diagnostics = validate_semantic_references(record, packets or [], reference_index, sources)
    diagnostics.extend(validate_material_inputs(record, context, reference_index, sources))
    messages = [f"{item['field']}: {item['message']}" for item in diagnostics]
    return list(dict.fromkeys(messages))

def validate(record, *, reference_index=None, reference_sources=None,
             reference_context=None, packets=None):
    """Return all observable contract errors; never modify the supplied record."""
    state = ValidationState()
    errors = state.errors
    error, fields, array, text = state.error, state.fields, state.array, state.text
    boolean, enum = state.boolean, state.enum
    if not isinstance(record, dict):
        return ['record: expected object']
    stage = record.get('stage')
    schema_version = record.get('schema_version')
    base_fields = {'schema_version', 'stage', 'scope', 'findings', 'checks', 'coverage'}
    final_fields = {'profile', 'profile_reason', 'responsible', 'description', 'verdict',
                    'verdict_reason', 'reservations', 'rereview', 'aliases', 'resources'}
    if schema_version in (3, 4, 5, 6, 7, 8, 9, 10):
        final_fields.add('change_authors')
    if schema_version in (4, 5, 6, 7, 8, 9, 10):
        final_fields.add('presentation')
    if schema_version in (6, 7, 8, 9, 10):
        final_fields |= {'review_id', 'previous_reviews', 'grandfathered_ids'}
    fields(record, base_fields | final_fields if stage == 'final' else base_fields, 'record')
    if type(schema_version) is not int or schema_version not in {1, 2, 3, 4, 5, 6, 7, 8, 9, 10}:
        error('schema_version', 'unsupported version')
    enum(stage, {'discovery', 'verification', 'final'}, 'stage')
    scope = record.get('scope')
    errors.extend(validate_scope(scope))
    scope = scope if isinstance(scope, dict) else {}
    versions = {v for key in ('head', 'base', 'snapshot') if isinstance(v := scope.get(key), str)}

    prior_reviews = []
    historical = {'findings': [], 'checks': []}
    if schema_version in (6, 7, 8, 9, 10) and stage == 'final':
        if not review_id(record.get('review_id')):
            error('review_id', 'expected CR- followed by 20 lowercase hexadecimal run identity characters')
        for i, raw in enumerate(array(record.get('previous_reviews'), 'previous_reviews')):
            path = f'previous_reviews[{i}]'
            prior = fields(raw, {'review_id', 'reference', 'verified'}, path)
            if prior.get('review_id') is not None and not review_id(prior.get('review_id')):
                error(path + '.review_id', 'expected known review ID or null; never invent legacy IDs')
            text(prior.get('reference'), path + '.reference')
            boolean(prior.get('verified'), path + '.verified')
            if prior.get('verified') is not True:
                error(path + '.verified', 'previous report reference must be verified')
            if prior.get('review_id') == record.get('review_id'):
                error(path, 'review cannot reference itself')
            if prior in prior_reviews:
                error(path, 'duplicate previous report reference')
            prior_reviews.append(prior)
        historical = dict(fields(record.get('grandfathered_ids'), {'findings', 'checks'}, 'grandfathered_ids'))
        for kind in ('findings', 'checks'):
            identifiers = array(historical.get(kind), 'grandfathered_ids.' + kind)
            seen = set()
            for identifier in identifiers:
                text(identifier, 'grandfathered_ids.' + kind)
                if isinstance(identifier, str):
                    if identifier in seen:
                        error('grandfathered_ids.' + kind, 'duplicate historical ID')
                    seen.add(identifier)
            historical[kind] = identifiers
    checks = validate_checks(record, schema_version, historical, prior_reviews, versions, state)
    findings, finding_ids = validate_findings(record, schema_version, stage, historical, checks, state)
    coverage_fields = {'flows', 'limitations'}
    if stage == 'final':
        coverage_fields |= {'adequate', 'verification', 'stale'}
        if schema_version in (8, 9, 10):
            coverage_fields.add('execution')
        if schema_version in (2, 3, 4, 5, 6, 7, 8, 9, 10):
            coverage_fields.add('areas')
    coverage = fields(record.get('coverage'), coverage_fields, 'coverage')
    for i, flow in enumerate(array(coverage.get('flows'), 'coverage.flows')):
        text(flow, f'coverage.flows[{i}]')
    limitations = []
    for i, raw in enumerate(array(coverage.get('limitations'), 'coverage.limitations')):
        path = f'coverage.limitations[{i}]'
        names = {'detail', 'material'} | ({'kind', 'public_summary'} if schema_version in (8, 9, 10) else set())
        limitation = fields(raw, names, path)
        text(limitation.get('detail'), f'coverage.limitations[{i}].detail')
        boolean(limitation.get('material'), f'coverage.limitations[{i}].material')
        if schema_version in (8, 9, 10):
            enum(limitation.get('kind'), {'behavior', 'validation', 'execution'}, path + '.kind')
            text(limitation.get('public_summary'), path + '.public_summary', nullable=True)
            if limitation.get('kind') == 'execution':
                if limitation.get('material') is True and not limitation.get('public_summary'):
                    error(path + '.public_summary', 'material execution requires public impact summary')
                elif limitation.get('material') is False and limitation.get('public_summary') is not None:
                    error(path + '.public_summary', 'nonmaterial execution must remain private')
        limitations.append(limitation)
    if stage != 'final':
        return errors

    if schema_version in (8, 9, 10):
        errors.extend(validate_execution(record))
    if schema_version in (9, 10):
        errors.extend(validate_check_execution(record))
    if schema_version == 10:
        errors.extend(validate_profile_execution(record))

    material_area_gap = False
    if schema_version in (2, 3, 4, 5, 6, 7, 8, 9, 10):
        area_ids = set()
        public_finding_ids = {f['id'] for f in findings if isinstance(f, dict)
                              and isinstance(f.get('id'), str) and f.get('status') != 'rejected'}
        for i, raw in enumerate(array(coverage.get('areas'), 'coverage.areas')):
            path = f'coverage.areas[{i}]'
            row = fields(raw, {'area', 'status', 'details', 'material', 'finding_ids'}, path)
            enum(row.get('area'), AREAS, f'{path}.area')
            code = row.get('area')
            if isinstance(code, str):
                if code in area_ids:
                    error(f'{path}.area', 'duplicate area')
                area_ids.add(code)
            enum(row.get('status'), AREA_STATUS, f'{path}.status')
            text(row.get('details'), f'{path}.details')
            boolean(row.get('material'), f'{path}.material')
            if row.get('material') is True:
                if row.get('status') in ('covered', 'not_applicable'):
                    error(f'{path}.material', 'only pending applicable coverage can be a material gap')
                material_area_gap = True
            references = array(row.get('finding_ids'), f'{path}.finding_ids')
            seen_references = set()
            for j, identifier in enumerate(references):
                if not isinstance(identifier, str) or identifier not in public_finding_ids:
                    error(f'{path}.finding_ids[{j}]', 'must reference a retained non-rejected finding')
                elif identifier in seen_references:
                    error(f'{path}.finding_ids[{j}]', 'duplicate finding reference')
                else:
                    seen_references.add(identifier)
            if row.get('status') == 'not_applicable' and references:
                error(f'{path}.finding_ids', 'nonapplicable areas cannot reference findings')
        if area_ids != set(AREAS):
            error('coverage.areas', 'exactly one row for each area A through E is required')

    profile_choices = (CURRENT_PROFILES if schema_version in (7, 8, 9, 10) else
                       {'economy', 'balanced', 'deep', 'extended'} if schema_version in (5, 6) else
                       {'economy', 'balanced', 'deep'})
    enum(record.get('profile'), profile_choices, 'profile')
    text(record.get('profile_reason'), 'profile_reason')
    boolean(coverage.get('adequate'), 'coverage.adequate')
    boolean(coverage.get('stale'), 'coverage.stale')
    enum(coverage.get('verification'), VERIFICATION, 'coverage.verification')
    if record.get('profile') in ('deep', 'extended') and coverage.get('verification') == 'skipped':
        error('coverage.verification', 'deep/extended invariants cannot be skipped')
    substantive = any(isinstance(f, dict) and f.get('type') == 'code' and f.get('status') == 'confirmed' for f in findings)
    if (record.get('profile') in ('balanced', 'standard') and coverage.get('verification') == 'skipped'
            and (substantive or material_area_gap or any(l.get('material') is True for l in limitations))):
        error('coverage.verification', f"{record.get('profile')} code findings/material questions require verification or disclosed unavailability")
    def identity(raw, path, author=False):
        names = {'name', 'username', 'verified', 'source'} | ({'commits'} if author else set())
        person = fields(raw, names, path)
        for key in ('name', 'username', 'source'):
            text(person.get(key), f'{path}.{key}', nullable=True)
        boolean(person.get('verified'), f'{path}.verified')
        if person.get('verified') is True:
            if not person.get('source') or not (person.get('name') or person.get('username')):
                error(path, 'verified identity requires identity and source')
            username = person.get('username')
            if username is not None and (not isinstance(username, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', username)):
                error(f'{path}.username', 'invalid account identifier; omit @ prefix')
        if author:
            commits = array(person.get('commits'), f'{path}.commits')
            if not commits:
                error(f'{path}.commits', 'at least one reviewed commit or snapshot identity required')
            seen = set()
            for j, commit in enumerate(commits):
                text(commit, f'{path}.commits[{j}]')
                if isinstance(commit, str):
                    if commit in seen:
                        error(f'{path}.commits[{j}]', 'duplicate commit identity')
                    seen.add(commit)
        return person

    identity(record.get('responsible'), 'responsible')
    if schema_version in (4, 5, 6, 7, 8, 9, 10):
        presentation = fields(record.get('presentation'), {'kind', 'subject'}, 'presentation')
        enum(presentation.get('kind'), REVIEW_KINDS, 'presentation.kind')
        text(presentation.get('subject'), 'presentation.subject')
        if isinstance(presentation.get('subject'), str) and any(c in presentation['subject'] for c in '\r\n'):
            error('presentation.subject', 'expected a single-line functional subject')
    if schema_version in (3, 4, 5, 6, 7, 8, 9, 10):
        seen_authors = set()
        for i, author in enumerate(array(record.get('change_authors'), 'change_authors')):
            identity(author, f'change_authors[{i}]', author=True)
            if isinstance(author, dict):
                key = json.dumps(author, sort_keys=True, ensure_ascii=False)
                if key in seen_authors:
                    error(f'change_authors[{i}]', 'duplicate author entry')
                seen_authors.add(key)
    description = fields(record.get('description'), {'status', 'identity', 'details'}, 'description')
    enum(description.get('status'), DESCRIPTION, 'description.status')
    text(description.get('details'), 'description.details', empty=True)
    text(description.get('identity'), 'description.identity', nullable=True)
    remote = isinstance(scope.get('mode'), str) and scope['mode'] in {'pr', 'mr'}
    if remote and description.get('status') == 'not_applicable':
        error('description.status', 'MR/PR description must be checked or unverified')
    if not remote and description.get('status') != 'not_applicable':
        error('description.status', 'local/commit scope has no MR/PR description')
    if isinstance(description.get('status'), str) and description['status'] in {'aligned', 'needs_update'} and not description.get('identity'):
        error('description.identity', 'captured text/hash identity required')
    reservations = array(record.get('reservations'), 'reservations')
    for i, reservation in enumerate(reservations):
        text(reservation, f'reservations[{i}]')
    enum(record.get('verdict'), VERDICTS, 'verdict')
    text(record.get('verdict_reason'), 'verdict_reason')
    blockers = any(isinstance(f, dict) and f.get('status') == 'confirmed' and f.get('blocking') is True for f in findings)
    uncertain = (coverage.get('stale') is True or coverage.get('adequate') is not True
                 or material_area_gap or any(l.get('material') is True for l in limitations))
    expected = ('not_approvable' if blockers else 'insufficient_evidence' if uncertain
                else 'approvable_with_reservations' if reservations else 'approvable')
    if record.get('verdict') != expected:
        error('verdict', f'inconsistent with blockers/coverage/reservations; expected {expected}')
    previous_ids = set()
    historical_sources = set()
    for i, raw in enumerate(array(record.get('rereview'), 'rereview')):
        path = f'rereview[{i}]'
        names = {'id', 'status', 'details'}
        if schema_version in (6, 7, 8, 9, 10):
            names |= {'previous_review_id', 'previous_reference', 'previous_finding_id', 'previous_title', 'previous_url', 'check_ids'}
        item = fields(raw, names, path)
        text(item.get('id'), f'rereview[{i}].id')
        if isinstance(item.get('id'), str):
            previous_ids.add(item['id'])
        enum(item.get('status'), set(REREVIEW_STATUS) if schema_version in (6, 7, 8, 9, 10) else {'resolved', 'still_valid', 'withdrawn', 'new'}, f'rereview[{i}].status')
        text(item.get('details'), f'rereview[{i}].details')
        if schema_version in (6, 7, 8, 9, 10):
            identifier = item.get('id')
            if not canonical_id(identifier, 'F') and identifier not in historical['findings']:
                error(path + '.id', 'expected canonical finding ID or disclosed historical ID')
            if isinstance(identifier, str) and sum(isinstance(row, dict) and row.get('id') == identifier for row in record['rereview']) > 1:
                error(path + '.id', 'duplicate re-review ID')
            for key in ('previous_review_id', 'previous_reference', 'previous_finding_id', 'previous_title', 'previous_url'):
                text(item.get(key), path + '.' + key, nullable=True)
            if item.get('status') == 'new':
                if any(item.get(key) is not None for key in ('previous_review_id', 'previous_reference', 'previous_finding_id', 'previous_title', 'previous_url')):
                    error(path, 'new finding has no previous report identity')
                if not isinstance(identifier, str) or identifier not in finding_ids:
                    error(path + '.id', 'new row must reference a retained current finding')
            else:
                if not item.get('previous_finding_id') or not item.get('previous_title'):
                    error(path, 'prior finding identity and original title required')
                if not isinstance(identifier, str) or identifier != item.get('previous_finding_id'):
                    error(path + '.id', 'same-cause followup must preserve the exact previously published finding ID')
                matching = [prior for prior in prior_reviews if prior.get('verified') is True and
                            prior.get('reference') == item.get('previous_reference') and
                            (item.get('previous_review_id') is None or prior.get('review_id') == item['previous_review_id'])]
                if not matching:
                    error(path, 'prior finding must trace to verified previous report identity/reference')
                if item.get('previous_url') is not None and not public_url(item['previous_url']):
                    error(path + '.previous_url', 'expected verified public source URL or null')
                if isinstance(identifier, str) and identifier == item.get('previous_finding_id') and matching:
                    historical_sources.add(identifier)
            seen = set()
            for j, identifier in enumerate(array(item.get('check_ids'), path + '.check_ids')):
                if not isinstance(identifier, str) or identifier not in checks:
                    error(path + f'.check_ids[{j}]', 'unknown check reference')
                elif identifier in seen:
                    error(path + '.check_ids', 'duplicate check reference')
                else:
                    seen.add(identifier)
    historical_aliases = set()
    aliases = record.get('aliases')
    if schema_version in (6, 7, 8, 9, 10) and isinstance(aliases, dict):
        for alias, survivor in aliases.items():
            if (isinstance(alias, str) and isinstance(survivor, str)
                    and alias in historical['findings'] and survivor in historical_sources
                    and survivor in finding_ids | previous_ids and survivor not in aliases
                    and alias not in finding_ids | previous_ids):
                historical_aliases.add(alias)
    if schema_version in (6, 7, 8, 9, 10):
        for identifier in historical['findings']:
            if (not isinstance(identifier, str) or (identifier not in historical_aliases
                    and (identifier not in historical_sources or identifier not in finding_ids | previous_ids))):
                error('grandfathered_ids.findings', 'historical ID requires retained original identity and verified prior finding provenance')
        for identifier in historical['checks']:
            if not isinstance(identifier, str) or identifier not in checks:
                error('grandfathered_ids.checks', 'historical check ID must be retained')
    if not isinstance(aliases, dict):
        error('aliases', 'expected direct alias-to-surviving-ID object')
    else:
        for alias, survivor in aliases.items():
            text(alias, 'aliases key')
            text(survivor, f'aliases.{alias}')
            if schema_version in (6, 7, 8, 9, 10) and not canonical_id(alias, 'F') and alias not in historical_aliases:
                error(f'aliases.{alias}', 'expected canonical alias ID or explicitly declared historical alias with verified survivor provenance')
            if (not isinstance(survivor, str) or survivor not in finding_ids | previous_ids
                    or survivor in aliases or alias in finding_ids | previous_ids):
                error(f'aliases.{alias}', 'alias must directly identify a retained finding or re-review ID')
    resources = fields(record.get('resources'), {'cleanup', 'residuals', 'publication'}, 'resources')
    enum(resources.get('cleanup'), {'complete', 'not_needed', 'pending'}, 'resources.cleanup')
    enum(resources.get('publication'), {'not_requested', 'draft', 'published', 'failed'}, 'resources.publication')
    residuals = array(resources.get('residuals'), 'resources.residuals')
    for i, residual in enumerate(residuals):
        text(residual, f'resources.residuals[{i}]')
    if residuals and resources.get('cleanup') != 'pending':
        error('resources.cleanup', 'residual resources require pending cleanup')
    if reference_index is not None:
        errors.extend(validate_reference_semantics(
            record, reference_context, reference_index,
            reference_sources if isinstance(reference_sources, dict) else {}, packets))
    return errors
