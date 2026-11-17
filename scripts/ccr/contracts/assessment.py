"""Source-bound scope and finding decisions for final schema 13."""
import hashlib
import re

from ccr.contracts.references import parse_reference, resolve_reference
from ccr.contracts.validation import ValidationState
from ccr.shared.encoding import decode_json


VERIFICATION_FIELDS = {'obligation', 'trigger', 'consequence', 'consumer', 'question'}
REOPENING_REASONS = {'new_evidence', 'condition_changed', 'pending_gate'}
RESOLUTION_LABELS = {'accepted_debt': 'Deuda aceptada', 'out_of_scope': 'Resolución fuera del alcance'}


def _rows(record, field):
    rows = record.get(field)
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _by_id(rows):
    return {row['id']: row for row in rows if isinstance(row.get('id'), str)}


def validate_verification(value, relation, confirmed, state, path, *, evidence_ids=None):
    names = VERIFICATION_FIELDS | ({'evidence_ids'} if evidence_ids is not None else set())
    value = state.fields(value, names, path)
    for field in VERIFICATION_FIELDS:
        required = ((field in {'obligation', 'trigger', 'consequence'} and confirmed)
                    or (field in {'consumer', 'question'} and relation == 'affected_consumer'))
        state.text(value.get(field), path + '.' + field, nullable=not required)
    if evidence_ids is not None:
        _evidence_ids(value.get('evidence_ids'), evidence_ids, state, path, required=confirmed)


def _evidence_ids(value, known, state, path, *, required=True):
    items = state.array(value, path + '.evidence_ids')
    identifiers = {item for item in items if isinstance(item, str)}
    if len(items) != len(identifiers) or not identifiers <= known or (required and not items):
        state.error(path + '.evidence_ids', 'expected distinct observed evidence IDs in scope')
    return identifiers


def _source(value, state, path, *, whole=False):
    value = state.fields(value, {'reference', 'sha256'}, path)
    try:
        name, fragment = parse_reference(value.get('reference'), field='assessment source')
        if not name.startswith('evidence/') or (whole and (fragment or not name.endswith('.json'))):
            raise ValueError('expected selected evidence' + (' JSON file' if whole else ''))
    except ValueError as exc:
        state.error(path + '.reference', str(exc))
    digest = value.get('sha256')
    if not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest):
        state.error(path + '.sha256', 'expected SHA-256 of selected bytes')


def validate_shape(record, state):
    assessment = state.fields(record['assessment'], {'schema_version', 'scope', 'previous', 'findings'},
                              'assessment')
    if type(assessment.get('schema_version')) is not int or assessment['schema_version'] != 1:
        state.error('assessment.schema_version', 'expected assessment version 1')
    coverage = record.get('coverage')
    evidence = _by_id(_rows(coverage, 'evidence')) if isinstance(coverage, dict) else {}
    checks = _by_id(_rows(record, 'checks'))
    scope = state.fields(assessment.get('scope'), {'base', 'head', 'snapshot', 'delta'}, 'assessment.scope')
    actual_scope = record.get('scope')
    for field in ('base', 'head', 'snapshot'):
        if not isinstance(actual_scope, dict) or scope.get(field) != actual_scope.get(field):
            state.error('assessment.scope.' + field, 'must match the pinned final scope')
    delta = state.array(scope.get('delta'), 'assessment.scope.delta')
    if not 1 <= len(delta) <= 128:
        state.error('assessment.scope.delta', 'expected 1–128 inspected delta entries')
    delta_ids, delta_sources = set(), set()
    for i, item in enumerate(delta):
        path = f'assessment.scope.delta[{i}]'
        item = state.fields(item, {'detail', 'evidence_ids', 'sources'}, path)
        state.text(item.get('detail'), path + '.detail')
        ids = _evidence_ids(item.get('evidence_ids'), evidence.keys(), state, path)
        delta_ids.update(ids)
        refs = {evidence[key].get('reference') for key in ids if key in evidence
                and isinstance(evidence[key].get('reference'), str)}
        for j, descriptor in enumerate(state.array(item.get('sources'), path + '.sources')):
            _source(descriptor, state, f'{path}.sources[{j}]')
            ref = descriptor.get('reference') if isinstance(descriptor, dict) else None
            if not isinstance(ref, str) or ref not in refs:
                state.error(path + '.sources', 'each source must identify an observation in this delta entry')
            elif isinstance(descriptor.get('sha256'), str):
                delta_sources.update((key, ref, descriptor['sha256']) for key in ids
                                     if key in evidence and evidence[key].get('reference') == ref)
    previous = assessment.get('previous')
    presentation = record.get('presentation')
    kind = presentation.get('kind') if isinstance(presentation, dict) else None
    if previous is not None:
        previous = state.fields(previous, {'review_id', 'source'}, 'assessment.previous')
        _source(previous.get('source'), state, 'assessment.previous.source', whole=True)
        identifier = previous.get('review_id')
        if not isinstance(identifier, str) or sum(row.get('review_id') == identifier and row.get('verified') is True
                                                 for row in _rows(record, 'previous_reviews')) != 1:
            state.error('assessment.previous.review_id', 'expected exactly one verified prior result')
    elif kind in ('rereview', 'complement') or _rows(record, 'rereview') or _rows(record, 'previous_reviews'):
        state.error('assessment.previous', 'follow-up requires the verified prior result')

    current = _by_id(_rows(record, 'findings'))
    followup = _by_id(_rows(record, 'rereview'))
    rows = state.array(assessment.get('findings'), 'assessment.findings')
    identifiers = _by_id(row for row in rows if isinstance(row, dict))
    if len(rows) != len(identifiers) or identifiers.keys() != current.keys() | followup.keys():
        state.error('assessment.findings', 'expected exactly one decision per current or follow-up ID')
    causes = set()
    for i, row in enumerate(rows):
        path = f'assessment.findings[{i}]'
        row = state.fields(row, {'id', 'cause', 'relation', 'verification', 'resolution', 'reopening'}, path)
        identifier = row.get('id')
        finding = current.get(identifier, {}) if isinstance(identifier, str) else {}
        tracked = followup.get(identifier, {}) if isinstance(identifier, str) else {}
        cause = row.get('cause')
        if not isinstance(cause, str) or not re.fullmatch(r'[a-z0-9][a-z0-9._-]{0,119}', cause) or cause in causes:
            state.error(path + '.cause', 'expected a unique stable cause key')
        else:
            causes.add(cause)
        relation = row.get('relation')
        state.enum(relation, {'in_scope', 'affected_consumer', 'outside_scope'}, path + '.relation')
        status = tracked.get('status')
        confirmed = finding.get('status') == 'confirmed' or status == 'still_valid'
        if relation == 'outside_scope' and (finding.get('status') in ('confirmed', 'unresolved')
                                           or tracked and status != 'not_reevaluated'):
            state.error(path + '.relation', 'outside scope cannot affect the current verdict')
        if status == 'not_reevaluated' and finding.get('status') == 'confirmed':
            state.error(path + '.id', 'a claim not reevaluated cannot be confirmed in the current scope')
        if ((status in ('resolved', 'withdrawn') and finding.get('status') == 'confirmed')
                or (status == 'still_valid' and finding and finding.get('status') != 'confirmed')):
            state.error(path + '.id', 'current finding conflicts with the follow-up outcome')
        verification = row.get('verification')
        if confirmed or status in ('resolved', 'withdrawn') or relation == 'affected_consumer' or verification is not None:
            validate_verification(verification, relation, confirmed, state,
                                  path + '.verification', evidence_ids=delta_ids)
            if status in ('resolved', 'withdrawn') and (not isinstance(verification, dict) or not verification.get('evidence_ids')):
                state.error(path + '.verification.evidence_ids', 'resolution requires observed evidence')
        if row.get('resolution') is not None:
            _resolution(row['resolution'], finding, state, path + '.resolution')
            if status in ('resolved', 'withdrawn'):
                state.error(path + '.resolution', 'resolved or withdrawn claims have no current resolution disposition')
        if row.get('reopening') is not None:
            reopening = state.fields(row['reopening'],
                {'reason', 'detail', 'condition', 'evidence_id', 'source'}, path + '.reopening')
            state.enum(reopening.get('reason'), REOPENING_REASONS, path + '.reopening.reason')
            state.text(reopening.get('detail'), path + '.reopening.detail')
            state.text(reopening.get('condition'), path + '.reopening.condition',
                       nullable=reopening.get('reason') != 'condition_changed')
            descriptor = reopening.get('source')
            _source(descriptor, state, path + '.reopening.source')
            selected = (reopening.get('evidence_id'), descriptor.get('reference'), descriptor.get('sha256')
                        ) if isinstance(descriptor, dict) else ()
            linked = verification.get('evidence_ids') if isinstance(verification, dict) else None
            if (not all(isinstance(part, str) for part in selected) or selected not in delta_sources
                    or relation == 'outside_scope' or status in ('new', 'not_reevaluated') or not tracked
                    or not isinstance(linked, list) or reopening.get('evidence_id') not in linked):
                state.error(path + '.reopening', 'expected a prior cause and a source bound to the current delta')
            evidence_id = reopening.get('evidence_id')
            observation = evidence.get(evidence_id, {}) if isinstance(evidence_id, str) else {}
            check_id = observation.get('check_id')
            if observation.get('kind') == 'check':
                check = checks.get(check_id, {}) if isinstance(check_id, str) else {}
                if (check.get('status') not in ('passed', 'failed') or check.get('reused') is not False
                        or check.get('failure_kind') in ('fixture', 'environment')):
                    state.error(path + '.reopening.evidence_id', 'reopening needs a decisive new observation')


def _resolution(value, finding, state, path):
    value = state.fields(value, {'status', 'scope', 'authority', 'channel', 'source', 'conditions'}, path)
    state.enum(value.get('status'), RESOLUTION_LABELS, path + '.status')
    state.enum(value.get('scope'), {'this_review', 'logical_scope'}, path + '.scope')
    state.enum(value.get('authority'), {'user', 'scope_owner'}, path + '.authority')
    state.enum(value.get('channel'), {'chat', 'comment', 'description', 'document'}, path + '.channel')
    _source(value.get('source'), state, path + '.source')
    for condition in state.array(value.get('conditions'), path + '.conditions'):
        state.text(condition, path + '.conditions')
    if value.get('status') == 'accepted_debt' and value.get('scope') != 'logical_scope':
        state.error(path + '.scope', 'accepted debt must identify the logical scope of the decision')
    if finding.get('blocking') is True:
        state.error(path, 'a finding excluded from resolution cannot block this scope')


def _sources(assessment):
    previous = assessment['previous']
    if previous:
        yield previous['source']
    for entry in assessment['scope']['delta']:
        yield from entry['sources']
    for row in assessment['findings']:
        for field in ('resolution', 'reopening'):
            if row[field] is not None:
                yield row[field]['source']


def source_references(record):
    assessment = record.get('assessment')
    return {descriptor['reference'] for descriptor in _sources(assessment)} if assessment else set()


def verify_sources(record, read_source, *, captured_inputs=None):
    """Verify selected bytes and follow-up continuity, without consulting external paths."""
    assessment = record.get('assessment')
    if assessment is None:
        return
    captured = {}
    for descriptor in _sources(assessment):
        reference, digest = descriptor['reference'], descriptor['sha256']
        path, _ = parse_reference(reference, field='assessment source')
        if path not in captured:
            try:
                captured[path] = read_source(path)
            except (KeyError, OSError) as exc:
                raise ValueError('assessment source is not selected: ' + path) from exc
        raw = captured[path]
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError('assessment source differs from selected SHA-256: ' + path)
        resolve_reference(reference, {path: raw}, field='assessment source')
    prior = assessment['previous']
    previous = {}
    if prior is not None:
        previous = decode_json(captured[prior['source']['reference']])
        if not isinstance(previous, dict) or previous.get('stage') != 'final' or previous.get('review_id') != prior['review_id']:
            raise ValueError('assessment previous source differs from the linked final result')
        if 'assessment' in previous:
            state = ValidationState()
            validate_shape(previous, state)
            if state.errors:
                raise ValueError('previous assessment is invalid: ' + state.errors[0])
        _verify_continuity(record, assessment, previous)
    if captured_inputs is not None:
        initial = {key.split('#', 1)[0]: digest for key, digest in captured_inputs.get('sources', {}).items()}
        old = _by_id(_rows(previous.get('assessment') or {}, 'findings'))
        for row in assessment['findings']:
            decision = row['resolution']
            if decision is not None and decision != old.get(row['id'], {}).get('resolution'):
                descriptor = decision['source']
                if initial.get(descriptor['reference'].split('#', 1)[0]) != descriptor['sha256']:
                    raise ValueError('new resolution decision must be bound to an initially captured source')


def _verify_continuity(record, assessment, previous):
    old_findings = _by_id(_rows(previous, 'findings'))
    old_tracking = _by_id(_rows(previous, 'rereview'))
    old_assessment = previous.get('assessment')
    old_decisions = _by_id(_rows(old_assessment, 'findings')) if isinstance(old_assessment, dict) else {}
    old_causes = {row['cause']: identifier for identifier, row in old_decisions.items()}
    old_hashes = {descriptor['sha256'] for descriptor in _sources(old_assessment)} if old_decisions else set()
    old_hashes.add(assessment['previous']['source']['sha256'])
    new_decisions = _by_id(assessment['findings'])
    tracking = _by_id(_rows(record, 'rereview'))
    prior_id = assessment['previous']['review_id']
    active = {key for key in old_findings | old_tracking
              if old_findings.get(key, {}).get('status') != 'rejected'
              and old_tracking.get(key, {}).get('status') not in ('resolved', 'withdrawn')}
    protected = {key for key, row in old_decisions.items() if (row['resolution'] or {}).get('scope') == 'logical_scope'}
    required = protected | (active if record['presentation']['kind'] in ('rereview', 'complement') else set())
    if not required <= tracking.keys() or not required <= new_decisions.keys():
        raise ValueError('assessment must preserve each applicable published ID, including accepted debt')
    aliases = previous.get('aliases', {})
    if not isinstance(aliases, dict):
        raise ValueError('previous assessment requires the published alias map')
    if any(record['aliases'].get(alias) != target for alias, target in aliases.items() if target in tracking):
        raise ValueError('assessment must preserve published aliases for tracked findings')
    for identifier, row in new_decisions.items():
        old = old_decisions.get(identifier)
        tracked = tracking.get(identifier)
        if row['cause'] in old_causes and old_causes[row['cause']] != identifier:
            raise ValueError('same cause must preserve its published ID')
        if old and old['cause'] != row['cause']:
            raise ValueError('published ID cannot be reassigned to a different cause')
        if identifier in old_findings or identifier in old_tracking:
            original = old_findings.get(identifier, {}).get('title') or old_tracking.get(identifier, {}).get('previous_title')
            if (not tracked or tracked['status'] == 'new' or tracked['previous_review_id'] != prior_id
                    or not isinstance(original, str) or tracked['previous_title'] != original):
                raise ValueError('follow-up must trace the published ID and title to the exact previous review')
        elif tracked and tracked['status'] != 'new':
            raise ValueError('follow-up ID is absent from the selected previous review')
        if identifier in aliases:
            raise ValueError('a published alias cannot be reused as a finding ID')
        old_resolution = old['resolution'] if old else None
        decision = row['resolution']
        if old_resolution is not None and old_resolution['scope'] == 'this_review' and decision is not None:
            before, after = old_resolution['source'], decision['source']
            if (before['sha256'] == after['sha256']
                    and before['reference'].partition('#')[2] == after['reference'].partition('#')[2]):
                raise ValueError('a this_review exclusion expires and needs a new applicable decision')
        reopening = row['reopening']
        status = tracked['status'] if tracked else None
        changed_debt = identifier in protected and (row['resolution'] != old_resolution
                                                     or status in ('resolved', 'withdrawn'))
        revived = old_tracking.get(identifier, {}).get('status') in ('resolved', 'withdrawn') and status == 'still_valid'
        if (changed_debt or revived) and reopening is None:
            raise ValueError('reopening requires new material evidence for this published finding')
        if reopening is not None:
            if reopening['source']['sha256'] in old_hashes:
                raise ValueError('reopening source was already used by the previous assessment')
            if (reopening['reason'] == 'condition_changed'
                    and (old_resolution is None or reopening['condition'] not in old_resolution['conditions'])):
                raise ValueError('reopening must identify the original accepted condition')
