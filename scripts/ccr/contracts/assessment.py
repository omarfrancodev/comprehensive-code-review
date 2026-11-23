"""Source-bound scope and finding decisions for final schema 13."""
import copy
import hashlib
import re

from ccr.contracts.references import parse_reference, resolve_reference
from ccr.contracts.identifier_types import canonical_id, review_id
from ccr.contracts.validation import ValidationState
from ccr.shared.encoding import decode_json


VERIFICATION_FIELDS = {'obligation', 'trigger', 'consequence', 'consumer', 'question'}
REOPENING_REASONS = {'new_evidence', 'condition_changed', 'pending_gate'}
RESOLUTION_LABELS = {'accepted_debt': 'Deuda aceptada', 'out_of_scope': 'Resolución fuera del alcance'}
MATERIAL_STATUSES = {'confirmed', 'unresolved', 'rejected', 'resolved', 'withdrawn', 'unknown'}
TERMINAL_STATUSES = {'rejected', 'resolved', 'withdrawn'}


def resolution_decisions(value):
    """Normalize a valid null/object/list disposition without combining its facts."""
    return [] if value is None else list(value) if isinstance(value, list) else [value]


def _same_decisions(left, right):
    before, after = resolution_decisions(left), resolution_decisions(right)
    return len(before) == len(after) and all(decision in after for decision in before)


def _rows(record, field):
    rows = record.get(field)
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _by_id(rows):
    return {row['id']: row for row in rows if isinstance(row.get('id'), str)}


def _decisive_observation(observation, checks):
    if observation.get('kind') == 'static':
        return True
    if observation.get('kind') != 'check':
        return False
    identifier = observation.get('check_id')
    check = checks.get(identifier, {}) if isinstance(identifier, str) else {}
    return (check.get('reused') is False
            and (check.get('status') == 'passed' and check.get('failure_kind') is None
                 or check.get('status') == 'failed' and check.get('failure_kind') == 'product'))


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
    value = record['assessment']
    version = value.get('schema_version') if isinstance(value, dict) else None
    fields = {'schema_version', 'scope', 'previous', 'findings'}
    if version in (2, 3):
        fields |= {'lineage', 'observed_hashes'}
        if 'history_incomplete' in value:
            fields.add('history_incomplete')
    if version == 3:
        fields |= {'history_incomplete', 'authorizations'}
    assessment = state.fields(value, fields, 'assessment')
    if type(version) is not int or version not in (1, 2, 3):
        state.error('assessment.schema_version', 'expected assessment version 1, 2 or 3')
    if version in (2, 3) and 'history_incomplete' in assessment:
        state.boolean(assessment['history_incomplete'], 'assessment.history_incomplete')
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
        bound_refs = set()
        for j, descriptor in enumerate(state.array(item.get('sources'), path + '.sources')):
            _source(descriptor, state, f'{path}.sources[{j}]')
            ref = descriptor.get('reference') if isinstance(descriptor, dict) else None
            if not isinstance(ref, str) or ref not in refs:
                state.error(path + '.sources', 'each source must identify an observation in this delta entry')
            elif isinstance(descriptor.get('sha256'), str):
                bound_refs.add(ref)
                delta_sources.update((key, ref, descriptor['sha256']) for key in ids
                                     if key in evidence and evidence[key].get('reference') == ref)
        if version in (2, 3) and not {ref for ref in refs if ref.startswith('evidence/')} <= bound_refs:
            state.error(path + '.sources', 'each local evidence observation requires a source descriptor')
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
                or (status == 'still_valid' and (version in (2, 3) or finding)
                    and finding.get('status') != 'confirmed')):
            state.error(path + '.id', 'current finding conflicts with the follow-up outcome')
        verification = row.get('verification')
        if confirmed or status in ('resolved', 'withdrawn') or relation == 'affected_consumer' or verification is not None:
            validate_verification(verification, relation, confirmed, state,
                                  path + '.verification', evidence_ids=delta_ids)
            if status in ('resolved', 'withdrawn') and (not isinstance(verification, dict) or not verification.get('evidence_ids')):
                state.error(path + '.verification.evidence_ids', 'resolution requires observed evidence')
            if version in (2, 3) and status in ('resolved', 'withdrawn'):
                linked = verification.get('evidence_ids') if isinstance(verification, dict) else None
                if not isinstance(linked, list) or not any(
                        isinstance(key, str) and key in delta_ids
                        and _decisive_observation(evidence.get(key, {}), checks) for key in linked):
                    state.error(path + '.verification.evidence_ids', 'resolution requires a decisive current observation')
        if row.get('resolution') is not None:
            _validate_resolutions(row['resolution'], finding, state, path + '.resolution', multiple=version in (2, 3), authorization=version == 3)
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
    if version in (2, 3):
        _validate_lineage(record, assessment, identifiers, current, state)
    if version == 3:
        _validate_authorizations(record, assessment, state)


def _validate_resolutions(value, finding, state, path, *, multiple, authorization=False):
    if isinstance(value, list):
        if not multiple or not value or any(item in value[:i] for i, item in enumerate(value)):
            state.error(path, 'expected a nonempty distinct list of complete resolution decisions')
        for i, decision in enumerate(value):
            _resolution(decision, finding, state, f'{path}[{i}]', authorization=authorization)
    else:
        _resolution(value, finding, state, path, authorization=authorization)


def _validate_lineage(record, assessment, decisions, current, state):
    rows = state.array(assessment.get('lineage'), 'assessment.lineage')
    members = _by_id(row for row in rows if isinstance(row, dict))
    if len(rows) != len(members):
        state.error('assessment.lineage', 'expected distinct published member IDs')
    causes = set()
    historic = record.get('grandfathered_ids')
    historic = historic.get('findings', []) if isinstance(historic, dict) else []
    for i, value in enumerate(rows):
        path = f'assessment.lineage[{i}]'
        member = state.fields(value, {'id', 'cause', 'survivor', 'title', 'last_status', 'resolution'}, path)
        identifier, survivor = member.get('id'), member.get('survivor')
        if not canonical_id(identifier, 'F') and identifier not in historic:
            state.error(path + '.id', 'expected canonical finding ID or disclosed historical ID')
        target = members.get(survivor, {}) if isinstance(survivor, str) else {}
        if not target or target.get('survivor') != survivor:
            state.error(path + '.survivor', 'expected a direct surviving lineage member')
        cause = member.get('cause')
        if cause is not None:
            if (not isinstance(cause, str) or not re.fullmatch(r'[a-z0-9][a-z0-9._-]{0,119}', cause)
                    or cause in causes):
                state.error(path + '.cause', 'expected a distinct stable cause or unknown historical cause')
            else:
                causes.add(cause)
        state.text(member.get('title'), path + '.title', nullable=True)
        state.enum(member.get('last_status'), MATERIAL_STATUSES, path + '.last_status')
        if member.get('resolution') is not None:
            _validate_resolutions(member['resolution'], {}, state, path + '.resolution', multiple=True,
                                  authorization=assessment['schema_version'] == 3)
            if member.get('last_status') in TERMINAL_STATUSES:
                state.error(path + '.resolution', 'terminal lineage member has no current disposition')
    for identifier, decision in decisions.items():
        member = members.get(identifier, {})
        if member.get('survivor') != identifier or member.get('cause') != decision.get('cause'):
            state.error('assessment.lineage', 'current decisions require their own matching lineage member')
        finding = current.get(identifier)
        if finding and member.get('title') != finding.get('title'):
            state.error('assessment.lineage', 'current finding title must match its published lineage title')
    hashes = state.array(assessment.get('observed_hashes'), 'assessment.observed_hashes')
    valid = {digest for digest in hashes if isinstance(digest, str) and re.fullmatch(r'[0-9a-f]{64}', digest)}
    if len(hashes) != len(valid):
        state.error('assessment.observed_hashes', 'expected distinct observed SHA-256 digests')


def _authorization_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'AU[0-9]{3,}', value):
        return False
    digits = value[2:]
    significant = digits.lstrip('0')
    return bool(significant) and digits == significant.zfill(3)


def _resolution(value, finding, state, path, *, authorization=False):
    names = {'status', 'scope', 'authority', 'channel', 'source', 'conditions'}
    value = state.fields(value, names | ({'authorization_id'} if authorization else set()), path)
    if authorization and not _authorization_id(value.get('authorization_id')):
        state.error(path + '.authorization_id', 'expected a retained authorization ID')
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


def _plain_decision(decision):
    return {key: value for key, value in decision.items() if key != 'authorization_id'}


def _validate_authorizations(record, assessment, state):
    entries = state.array(assessment.get('authorizations'), 'assessment.authorizations')
    ledger = _by_id(row for row in entries if isinstance(row, dict))
    if len(entries) != len(ledger):
        state.error('assessment.authorizations', 'expected distinct immutable authorization IDs')
    members = _by_id(_rows(assessment, 'lineage'))
    grants = []
    for i, entry in enumerate(entries):
        path = f'assessment.authorizations[{i}]'
        entry = state.fields(entry, {'id', 'member_id', 'review_id', 'scope', 'decision'}, path)
        grant = {key: value for key, value in entry.items() if key != 'id'}
        if grant in grants:
            state.error(path, 'duplicate authorization grant cannot be assigned another ID')
        grants.append(grant)
        identifier = entry.get('id')
        if not _authorization_id(identifier):
            state.error(path + '.id', 'expected an AU authorization ID with at least three digits')
        if not isinstance(entry.get('member_id'), str) or entry['member_id'] not in members:
            state.error(path + '.member_id', 'authorization requires its original lineage member')
        if not review_id(entry.get('review_id')):
            state.error(path + '.review_id', 'expected the original authorizing review ID')
        scope = state.fields(entry.get('scope'), {'base', 'head', 'snapshot'}, path + '.scope')
        for field in ('base', 'head', 'snapshot'):
            state.text(scope.get(field), path + '.scope.' + field, nullable=True)
        if not scope.get('head') and not scope.get('snapshot'):
            state.error(path + '.scope', 'authorization requires a pinned head or snapshot')
        _resolution(entry.get('decision'), {}, state, path + '.decision')
        decision = entry.get('decision')
        descriptor = decision.get('source') if isinstance(decision, dict) else None
        digest = descriptor.get('sha256') if isinstance(descriptor, dict) else None
        hashes = assessment.get('observed_hashes')
        if isinstance(digest, str) and isinstance(hashes, list) and digest not in hashes:
            state.error('assessment.observed_hashes', 'must retain every authorization source digest')
    for collection in ('findings', 'lineage'):
        for i, row in enumerate(_rows(assessment, collection)):
            for decision in resolution_decisions(row.get('resolution')):
                if not isinstance(decision, dict):
                    continue
                identifier = decision.get('authorization_id')
                authorization = ledger.get(identifier, {}) if isinstance(identifier, str) else {}
                if authorization.get('decision') != _plain_decision(decision):
                    state.error(f'assessment.{collection}[{i}].resolution',
                                'active resolution must retain its exact authorization decision')
                member_id = authorization.get('member_id')
                original = members.get(member_id, {}) if isinstance(member_id, str) else {}
                survivor = row.get('survivor', row.get('id'))
                if original.get('survivor') != survivor:
                    state.error(f'assessment.{collection}[{i}].resolution',
                                'authorization belongs to a different original member group')


def _sources(assessment):
    previous = assessment['previous']
    if previous:
        yield previous['source']
    for entry in assessment['scope']['delta']:
        yield from entry['sources']
    for row in assessment['findings']:
        for decision in resolution_decisions(row['resolution']):
            yield decision['source']
        if row['reopening'] is not None:
            yield row['reopening']['source']
    for member in assessment.get('lineage', []):
        for decision in resolution_decisions(member['resolution']):
            yield decision['source']


def source_references(record, *, include_history=False):
    """Select active source bytes; projection may also redact historical locators."""
    assessment = record.get('assessment')
    if not assessment:
        return set()
    references = {descriptor['reference'] for descriptor in _sources(assessment)}
    if include_history:
        references.update(entry['decision']['source']['reference']
                          for entry in assessment.get('authorizations', []))
    return references


def verify_sources(record, read_source, *, captured_inputs=None):
    """Verify selected bytes and follow-up continuity, without consulting external paths."""
    assessment = record.get('assessment')
    if assessment is None:
        return
    if assessment.get('schema_version') in (2, 3):
        state = ValidationState()
        validate_shape(record, state)
        if state.errors:
            raise ValueError('assessment is invalid: ' + state.errors[0])
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
        if assessment['schema_version'] == 2 and (previous.get('assessment') or {}).get('schema_version') == 3:
            raise ValueError('follow-up of assessment version 3 cannot downgrade authorization history')
        if assessment['schema_version'] == 1:
            if (previous.get('assessment') or {}).get('schema_version') in (2, 3):
                raise ValueError('follow-up of assessment version 2 or 3 requires lineage continuity')
            _verify_continuity(record, assessment, previous)
    if assessment['schema_version'] in (2, 3):
        try:
            _verify_lineage_continuity(record, assessment, previous)
        except ValueError:
            if assessment['schema_version'] != 2 or 'history_incomplete' in assessment:
                raise
            # Both historical v2 emitters used this same shape. Their v1
            # outcome interpretation differed; retain the union for reading.
            _verify_lineage_continuity(record, assessment, previous, legacy_v2=True)
    if assessment['schema_version'] == 3:
        _verify_authorization_continuity(record, assessment, previous)
    if captured_inputs is not None:
        initial = {key.split('#', 1)[0]: digest for key, digest in captured_inputs.get('sources', {}).items()}
        old = _by_id(_rows(previous.get('assessment') or {}, 'findings'))
        for row in assessment['findings']:
            for decision in resolution_decisions(row['resolution']):
                inherited = any(decision in resolution_decisions(prior_row['resolution'])
                                for identifier, prior_row in old.items()
                                if record['aliases'].get(identifier, identifier) == row['id'])
                if assessment['schema_version'] in (2, 3):
                    inherited = any(decision in resolution_decisions(member['resolution'])
                        for member in _continuity_baseline(previous, assessment).values()
                        if record['aliases'].get(member['survivor'], member['survivor']) == row['id'])
                if decision['scope'] == 'this_review':
                    inherited = False
                if not inherited:
                    descriptor = decision['source']
                    if initial.get(descriptor['reference'].split('#', 1)[0]) != descriptor['sha256']:
                        raise ValueError('new resolution decision must be bound to an initially captured source')


def _material_status(finding, tracked, previous='unknown'):
    status = tracked.get('status')
    if status == 'not_reevaluated':
        return previous
    if status in ('resolved', 'withdrawn'):
        return status
    return finding.get('status') if finding.get('status') in MATERIAL_STATUSES else previous


def _baseline_lineage(previous, *, legacy_v2=False):
    """Read one selected baseline; never infer an unavailable historical outcome."""
    assessment = previous.get('assessment') or {}
    if assessment.get('schema_version') in (2, 3):
        return _by_id(_rows(assessment, 'lineage'))
    findings, tracked = _by_id(_rows(previous, 'findings')), _by_id(_rows(previous, 'rereview'))
    decisions = _by_id(_rows(assessment, 'findings'))
    aliases = previous.get('aliases', {})
    result = {}
    for identifier in findings.keys() | tracked.keys() | decisions.keys() | aliases.keys():
        finding, tracking, decision = findings.get(identifier, {}), tracked.get(identifier, {}), decisions.get(identifier, {})
        status = _material_status(finding, tracking)
        if not legacy_v2 and status in ('resolved', 'withdrawn') and assessment.get('schema_version') == 1:
            evidence = _by_id(_rows(previous.get('coverage') or {}, 'evidence'))
            checks = _by_id(_rows(previous, 'checks'))
            verification = decision.get('verification') or {}
            if not any(_decisive_observation(evidence.get(key, {}), checks)
                       for key in verification.get('evidence_ids', [])):
                status = 'unknown'
        result[identifier] = dict(id=identifier, cause=decision.get('cause'),
            survivor=aliases.get(identifier, identifier),
            title=finding.get('title') or tracking.get('previous_title'),
            last_status=status, resolution=decision.get('resolution'))
    # A published direct alias establishes the same claim as its known target.
    # It does not recover the alias's original cause key or title.
    for identifier, survivor in aliases.items():
        if identifier in result and survivor in result:
            result[identifier]['last_status'] = result[survivor]['last_status']
            result[identifier]['resolution'] = result[survivor]['resolution']
    return result


def baseline_authorizations(previous):
    """Import only decisions demonstrated by the selected prior review bytes."""
    assessment = previous.get('assessment') or {}
    version = assessment.get('schema_version')
    if version == 3:
        return copy.deepcopy(assessment['authorizations'])
    # V1 publishes group dispositions on survivors. The copies made for
    # lineage continuity do not establish grants on those alias IDs.
    members = _by_id(_rows(assessment, 'lineage' if version == 2 else 'findings'))
    entries = []
    for identifier, member in sorted(members.items()):
        for decision in resolution_decisions(member['resolution']):
            entries.append(dict(id=f'AU{len(entries) + 1:03d}', member_id=identifier,
                review_id=previous['review_id'],
                scope={key: previous['scope'][key] for key in ('base', 'head', 'snapshot')},
                decision=copy.deepcopy(decision)))
    return entries


def _continuity_baseline(previous, assessment, *, legacy_v2=False):
    members = copy.deepcopy(_baseline_lineage(previous, legacy_v2=legacy_v2))
    previous_version = (previous.get('assessment') or {}).get('schema_version')
    if assessment['schema_version'] != 3 or previous_version == 3:
        return members
    ledger = baseline_authorizations(previous)
    for member in members.values():
        original = member['id'] if previous_version == 2 else member['survivor']
        bound = []
        for decision in resolution_decisions(member['resolution']):
            identifier = next((entry['id'] for entry in ledger
                               if entry['member_id'] == original and entry['decision'] == decision), None)
            if identifier is None:
                raise ValueError('legacy resolution requires a decision on its published authorization member')
            bound.append(dict(decision, authorization_id=identifier))
        member['resolution'] = bound if isinstance(member['resolution'], list) else bound[0] if bound else None
    return members


def _observed_hashes(assessment):
    if not assessment:
        return set()
    return (set(assessment.get('observed_hashes', []))
            | {descriptor['sha256'] for descriptor in _sources(assessment)})


def _unbound_historical_observations(previous):
    assessment = previous.get('assessment') or {}
    if assessment.get('schema_version') != 1:
        return False
    if assessment['previous'] is not None:
        # V1 binds its immediate inputs, but has no accumulated hash ledger.
        # A prior source digest cannot establish the hashes of its ancestors.
        return True
    evidence = _by_id(_rows(previous.get('coverage') or {}, 'evidence'))
    for entry in assessment['scope']['delta']:
        bound = {descriptor['reference'] for descriptor in entry['sources']}
        if any(evidence.get(key, {}).get('reference') not in bound for key in entry['evidence_ids']):
            return True
    return False


def _verify_lineage_continuity(record, assessment, previous, *, legacy_v2=False):
    old = _continuity_baseline(previous, assessment, legacy_v2=legacy_v2)
    if any(identifier not in old for identifier in record.get('grandfathered_ids', {}).get('findings', [])):
        raise ValueError('historical ID requires its own published provenance in the selected previous result')
    members = _by_id(assessment['lineage'])
    decisions = _by_id(assessment['findings'])
    findings, tracking = _by_id(_rows(record, 'findings')), _by_id(_rows(record, 'rereview'))
    aliases = record['aliases']
    expected_ids = old.keys() | decisions.keys() | aliases.keys()
    if members.keys() != expected_ids:
        raise ValueError('lineage must preserve every published ID and only observed current members')
    old_assessment = previous.get('assessment') or {}
    incomplete = (old_assessment.get('history_incomplete', False)
                  or _unbound_historical_observations(previous))
    if assessment['schema_version'] == 3:
        # Old chained formats did not retain expired authorizations, even
        # when their observed-hash ledger happened to be complete.
        incomplete = incomplete or (old_assessment.get('schema_version') in (1, 2)
                                     and old_assessment.get('previous') is not None)
        incomplete = incomplete or bool(previous and not old_assessment)
    enforce_history = assessment['schema_version'] == 3 or 'history_incomplete' in assessment
    if enforce_history and assessment.get('history_incomplete', False) != incomplete:
        raise ValueError('history_incomplete must preserve unknown historical observation hashes')
    if not enforce_history:
        incomplete = False
    old_hashes = _observed_hashes(old_assessment)
    if assessment['previous'] is not None:
        old_hashes.add(assessment['previous']['source']['sha256'])
    expected_hashes = old_hashes | {descriptor['sha256'] for descriptor in _sources(assessment)}
    if set(assessment['observed_hashes']) != expected_hashes:
        raise ValueError('observed_hashes must preserve exactly the accumulated observed sources')
    old_causes = {member['cause']: identifier for identifier, member in old.items() if member['cause'] is not None}
    prior_id = assessment['previous']['review_id'] if assessment['previous'] is not None else None
    for identifier, row in decisions.items():
        before = old.get(identifier)
        tracked = tracking.get(identifier)
        if row['cause'] in old_causes and old_causes[row['cause']] != identifier:
            raise ValueError('same cause must preserve its published ID')
        if before:
            if before['survivor'] != identifier:
                raise ValueError('a published alias cannot be reused as a finding ID')
            if before['cause'] is not None and before['cause'] != row['cause']:
                raise ValueError('published ID cannot be reassigned to a different cause')
            if (not tracked or tracked['status'] == 'new' or tracked['previous_review_id'] != prior_id
                    or before['title'] is not None and tracked['previous_title'] != before['title']):
                raise ValueError('follow-up must trace the published ID and title to the exact previous review')
        elif tracked and tracked['status'] != 'new':
            raise ValueError('follow-up ID is absent from the selected previous review')
        reopening = row['reopening']
        if reopening is not None:
            if reopening['reason'] == 'new_evidence' and incomplete:
                raise ValueError('historical observation hashes are unknown; establish a current condition or pending gate')
            if reopening['source']['sha256'] in old_hashes:
                raise ValueError('reopening source was already used by a previous assessment')
            original = [decision for member in old.values()
                        if aliases.get(member['survivor'], member['survivor']) == identifier
                        for decision in resolution_decisions(member['resolution'])]
            if (reopening['reason'] == 'condition_changed'
                    and not any(reopening['condition'] in decision['conditions'] for decision in original)):
                raise ValueError('reopening must identify the original accepted condition')
    for identifier, member in members.items():
        before = old.get(identifier)
        old_survivor = before['survivor'] if before else identifier
        survivor = aliases.get(old_survivor, old_survivor)
        if identifier in aliases:
            if before and old_survivor != identifier and aliases[identifier] != survivor:
                raise ValueError('assessment must preserve the published alias survivor group')
            survivor = aliases[identifier]
        if member['survivor'] != survivor:
            raise ValueError('lineage must preserve the direct published survivor and alias map')
        row, tracked, finding = decisions.get(survivor), tracking.get(survivor, {}), findings.get(survivor, {})
        inherited_alias = before is not None and before['survivor'] != identifier
        if inherited_alias and row is not None and aliases.get(identifier) != survivor:
            raise ValueError('assessment must preserve published aliases for tracked findings')
        consolidation = before is not None and survivor != old_survivor
        if consolidation:
            if survivor not in old or old[survivor]['survivor'] != survivor:
                raise ValueError('consolidation requires a published survivor')
            if (not row or not tracked or tracked['status'] in ('new', 'not_reevaluated')
                    or row['relation'] == 'outside_scope' or not row['verification']
                    or not row['verification']['evidence_ids']):
                raise ValueError('consolidation requires current verification of the published survivor')
        old_status = before['last_status'] if before else 'unknown'
        expected_status = _material_status(finding, tracked, old_status) if row else old_status
        if member['last_status'] != expected_status:
            raise ValueError('lineage must preserve the last material outcome across omission or not_reevaluated')
        expected_cause = before['cause'] if before else None
        if identifier == survivor and identifier in decisions and expected_cause is None:
            expected_cause = decisions[identifier]['cause']
        if member['cause'] != expected_cause:
            raise ValueError('lineage cannot change or invent a published cause')
        expected_title = before['title'] if before else None
        if identifier == survivor and finding:
            expected_title = finding['title']
        if member['title'] != expected_title:
            raise ValueError('lineage must retain the exact member title')
        old_resolution = before['resolution'] if before else None
        protected = [decision for decision in resolution_decisions(old_resolution)
                     if decision['scope'] == 'logical_scope']
        active = old_status not in TERMINAL_STATUSES
        required = before is not None and (protected or active and record['presentation']['kind'] in ('rereview', 'complement'))
        if required and (row is None or not tracked):
            raise ValueError('assessment must preserve each applicable published ID, including accepted debt')
        if row is None:
            remaining = protected if protected else []
            if not _same_decisions(member['resolution'], remaining):
                raise ValueError('omitted member must preserve applicable dispositions and expire this_review exclusions')
            continue
        current = resolution_decisions(member['resolution'])
        group = resolution_decisions(row['resolution'])
        if any(decision not in group for decision in current):
            raise ValueError('member resolution must appear exactly in the surviving finding disposition')
        reopening = row['reopening']
        for decision in resolution_decisions(old_resolution):
            if assessment['schema_version'] == 3:
                # V3 checks lifetime by immutable authorization identity,
                # independently of other decisions in a consolidated group.
                continue
            if decision['scope'] == 'this_review' and any(
                    decision['source']['sha256'] == item['source']['sha256']
                    and decision['source']['reference'].partition('#')[2] == item['source']['reference'].partition('#')[2]
                    for item in (current if legacy_v2 else group)):
                raise ValueError('a this_review exclusion expires and needs a new applicable decision')
        changed = [decision for decision in protected if decision not in current]
        if protected and (expected_status in ('resolved', 'withdrawn')
                          or any(decision not in resolution_decisions(old_resolution) for decision in current)):
            changed = protected
        revived = old_status in TERMINAL_STATUSES | {'unknown'} and expected_status == 'confirmed'
        if before is not None and (changed or revived) and reopening is None:
            raise ValueError('reopening requires new material evidence for this published finding')
        if reopening is not None and changed and reopening['reason'] == 'condition_changed':
            if any(reopening['condition'] not in decision['conditions'] for decision in changed):
                raise ValueError('reopening must identify the original accepted condition')
    for identifier, row in decisions.items():
        projected = [decision for member in members.values() if member['survivor'] == identifier
                     for decision in resolution_decisions(member['resolution'])]
        if any(decision not in projected for decision in resolution_decisions(row['resolution'])):
            raise ValueError('survivor disposition requires an exact member decision in lineage')


def _verify_authorization_continuity(record, assessment, previous):
    old = _by_id(baseline_authorizations(previous))
    ledger = _by_id(assessment['authorizations'])
    if any(identifier not in ledger or ledger[identifier] != entry for identifier, entry in old.items()):
        raise ValueError('authorization history must preserve every immutable published entry')
    observed = _observed_hashes(previous.get('assessment') or {})
    if assessment['previous'] is not None:
        observed.add(assessment['previous']['source']['sha256'])
    observed.update(entry['decision']['source']['sha256'] for entry in old.values())
    pinned = {key: record['scope'][key] for key in ('base', 'head', 'snapshot')}
    members = _by_id(assessment['lineage'])
    for identifier, entry in ledger.items():
        if identifier in old:
            continue
        if entry['review_id'] != record['review_id'] or entry['scope'] != pinned:
            raise ValueError('new authorization requires its current review and original pinned scope')
        if entry['decision']['source']['sha256'] in observed:
            raise ValueError('new authorization source was already observed; expired authority cannot be recaptured')
        original = members[entry['member_id']]
        if not any(decision['authorization_id'] == identifier
                   for decision in resolution_decisions(original['resolution'])):
            raise ValueError('new authorization requires an active decision on its original member')
    for collection in ('findings', 'lineage'):
        for row in assessment[collection]:
            for decision in resolution_decisions(row['resolution']):
                entry = ledger[decision['authorization_id']]
                if decision['scope'] == 'this_review' and entry['review_id'] != record['review_id']:
                    raise ValueError('a this_review authorization expires after its original review')


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
    published = old_findings.keys() | old_tracking.keys() | old_decisions.keys()
    survivors = {key: record['aliases'].get(key, key) for key in published}
    if any(survivors[key] not in tracking or survivors[key] not in new_decisions for key in required):
        raise ValueError('assessment must preserve each applicable published ID, including accepted debt')
    for identifier, survivor in survivors.items():
        if identifier == survivor:
            continue
        if survivor not in published:
            raise ValueError('consolidation requires a published survivor')
        row, tracked = new_decisions.get(survivor), tracking.get(survivor)
        if (not row or not tracked or tracked['status'] in ('new', 'not_reevaluated')
                or row['relation'] == 'outside_scope' or not row['verification']
                or not row['verification']['evidence_ids']):
            raise ValueError('consolidation requires current verification of the published survivor')
    aliases = previous.get('aliases', {})
    if not isinstance(aliases, dict):
        raise ValueError('previous assessment requires the published alias map')
    if any(record['aliases'].get(alias) != survivors.get(target, target)
           for alias, target in aliases.items() if survivors.get(target, target) in tracking):
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
        reopening = row['reopening']
        if (reopening is not None and reopening['reason'] == 'condition_changed'
                and not any(reopening['condition'] in (old_row['resolution'] or {}).get('conditions', [])
                            for key, old_row in old_decisions.items() if survivors[key] == identifier)):
            raise ValueError('reopening must identify the original accepted condition')
    # A consolidated decision must satisfy the policy of every published member.
    # Checking only the survivor could silently discard the aliased member's debt.
    for identifier, survivor in survivors.items():
        row = new_decisions.get(survivor)
        if row is None:
            continue
        old = old_decisions.get(identifier)
        tracked = tracking.get(survivor)
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
            if (changed_debt and reopening['reason'] == 'condition_changed'
                    and (old_resolution is None or reopening['condition'] not in old_resolution['conditions'])):
                raise ValueError('reopening must identify the original accepted condition')
