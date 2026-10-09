#!/usr/bin/env python3
"""Validate review records, render Spanish reports, or group explicit duplicate candidates.

Python 3.10+, standard library only. Structural checks never establish finding truth.
"""
import argparse
import copy
import html
import json
from pathlib import Path
import re
import sys
from urllib.parse import quote, urlsplit


MODES = {'pr', 'mr', 'commit', 'range', 'staged', 'unstaged', 'working', 'module', 'feature'}
STATES = {'candidate', 'confirmed', 'rejected', 'unresolved'}
VERDICTS = {
    'approvable': 'APROBABLE',
    'approvable_with_reservations': 'APROBABLE CON RESERVAS',
    'not_approvable': 'NO APROBABLE',
    'insufficient_evidence': 'EVIDENCIA INSUFICIENTE',
}
PRIORITIES = {'P0': '🔴 P0 — Crítico', 'P1': '🟠 P1 — Alto',
              'P2': '🟡 P2 — Importante', 'P3': '🔵 P3 — Menor'}
DESCRIPTION = {'aligned': 'coherente', 'needs_update': 'requiere actualización',
               'unverified': 'sin verificar', 'not_applicable': 'no aplica'}
VERIFICATION = {'independent': 'independiente', 'same_session': 'misma sesión',
                'skipped': 'omitida según perfil', 'unavailable': 'no disponible'}
ORIGINS = {'introduced': 'introducido', 'preexisting': 'preexistente', 'unknown': 'desconocido'}
CHECK_STATUS = {'passed': 'aprobada', 'failed': 'falló', 'blocked': 'bloqueada', 'not_run': 'no ejecutada'}
FAILURE_KINDS = {'product': 'producto', 'fixture': 'fixture', 'environment': 'entorno'}
PROFILES = {'economy': 'económico', 'balanced': 'equilibrado',
            'focused': 'focused (enfocado)', 'standard': 'standard (estándar)',
            'deep': 'profundo', 'extended': 'extendido'}
CURRENT_PROFILES = {'focused', 'standard', 'deep', 'extended'}
PROFILE_ALIASES = {'economy': 'focused', 'balanced': 'standard'}
MODE_LABELS = {'pr': 'PR', 'mr': 'MR', 'commit': 'commit', 'range': 'rango de commits',
               'staged': 'cambios preparados', 'unstaged': 'cambios sin preparar',
               'working': 'cambios locales', 'module': 'módulo',
               'feature': 'implementación de funcionalidad'}
REREVIEW_STATUS = {'resolved': 'resuelto', 'still_valid': 'vigente', 'withdrawn': 'retirado', 'new': 'nuevo'}
REREVIEW_STATUS['not_reevaluated'] = 'no reevaluado'
AREAS = {'A': 'Arquitectura y diseño', 'B': 'Comportamiento y negocio',
         'C': 'Contratos e integración', 'D': 'Datos y persistencia',
         'E': 'Seguridad y operación'}
AREA_STATUS = {'covered': 'Cubierta', 'partial': 'Parcial',
               'not_evaluated': 'No evaluada', 'not_applicable': 'No aplica'}
REVIEW_KINDS = {'review': 'Code Review', 'rereview': 'Re-review',
                'complement': 'Complement Code Review'}


def normalize_profile(value):
    """Resolve request aliases only; never rewrite a retained historical record."""
    if not isinstance(value, str):
        raise ValueError('expected a supported profile name')
    normalized = PROFILE_ALIASES.get(value, value)
    if normalized not in CURRENT_PROFILES:
        raise ValueError('expected focused, standard, deep or extended (economy/balanced aliases accepted)')
    return normalized


def canonical_id(identifier, prefix):
    if not isinstance(identifier, str) or not re.fullmatch(prefix + r'[0-9]{3,}', identifier):
        return False
    digits = identifier[1:]
    significant = digits.lstrip('0')
    # Avoid integer conversion: hostile numeric strings can exceed Python's limit.
    return bool(significant) and digits == significant.zfill(3)


def review_id(identifier):
    return isinstance(identifier, str) and bool(re.fullmatch(r'CR-[0-9a-f]{20}', identifier))


def public_url(value):
    if not isinstance(value, str):
        return False
    try:
        parsed = urlsplit(value)
        return parsed.scheme in {'http', 'https'} and bool(parsed.netloc) and not parsed.username and not parsed.password
    except ValueError:
        return False


def validate(record):
    """Return all observable contract errors; never modify the supplied record."""
    errors = []

    def error(path, message):
        errors.append(f'{path}: {message}')

    def fields(value, names, path):
        if not isinstance(value, dict):
            error(path, 'expected object')
            return {}
        for name in names:
            if name not in value:
                error(f'{path}.{name}', 'required field missing')
        for name in value:
            if name not in names:
                error(f'{path}.{name}', 'unknown field')
        return value

    def array(value, path):
        if not isinstance(value, list):
            error(path, 'expected array')
            return []
        return value

    def text(value, path, nullable=False, empty=False):
        if nullable and value is None:
            return
        if not isinstance(value, str) or (not empty and not value.strip()):
            error(path, 'expected nonempty text' if not empty else 'expected text')

    def boolean(value, path):
        if type(value) is not bool:
            error(path, 'expected boolean')

    def enum(value, choices, path):
        if not isinstance(value, str) or value not in choices:
            error(path, 'invalid value')

    if not isinstance(record, dict):
        return ['record: expected object']
    stage = record.get('stage')
    schema_version = record.get('schema_version')
    base_fields = {'schema_version', 'stage', 'scope', 'findings', 'checks', 'coverage'}
    final_fields = {'profile', 'profile_reason', 'responsible', 'description', 'verdict',
                    'verdict_reason', 'reservations', 'rereview', 'aliases', 'resources'}
    if schema_version in (3, 4, 5, 6, 7):
        final_fields.add('change_authors')
    if schema_version in (4, 5, 6, 7):
        final_fields.add('presentation')
    if schema_version in (6, 7):
        final_fields |= {'review_id', 'previous_reviews', 'grandfathered_ids'}
    fields(record, base_fields | final_fields if stage == 'final' else base_fields, 'record')
    if type(schema_version) is not int or schema_version not in {1, 2, 3, 4, 5, 6, 7}:
        error('schema_version', 'unsupported version')
    enum(stage, {'discovery', 'verification', 'final'}, 'stage')
    scope = fields(record.get('scope'), {'repository', 'mode', 'base', 'head', 'snapshot', 'target', 'reference'}, 'scope')
    text(scope.get('repository'), 'scope.repository')
    enum(scope.get('mode'), MODES, 'scope.mode')
    for key in ('base', 'head', 'snapshot', 'target', 'reference'):
        text(scope.get(key), f'scope.{key}', nullable=True)
    if not scope.get('head') and not scope.get('snapshot'):
        error('scope', 'head or snapshot identity required')
    if isinstance(scope.get('mode'), str) and scope['mode'] in {'staged', 'unstaged', 'working'} and not scope.get('snapshot'):
        error('scope.snapshot', 'local edits require captured snapshot identity')
    versions = {v for key in ('head', 'base', 'snapshot') if isinstance(v := scope.get(key), str)}

    prior_reviews = []
    historical = {'findings': [], 'checks': []}
    if schema_version in (6, 7) and stage == 'final':
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

    checks = {}
    for i, raw in enumerate(array(record.get('checks'), 'checks')):
        path = f'checks[{i}]'
        check_names = {'id', 'command', 'revision', 'status', 'failure_kind', 'evidence', 'reused', 'reuse_reason', 'rerun_reason'}
        if schema_version in (6, 7):
            check_names.add('reference')
        check = fields(raw, check_names, path)
        for key in ('id', 'command', 'revision'):
            text(check.get(key), f'{path}.{key}')
        identifier = check.get('id')
        if schema_version in (6, 7):
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

    finding_ids = set()
    findings = array(record.get('findings'), 'findings')
    for i, raw in enumerate(findings):
        path = f'findings[{i}]'
        item = fields(raw, {'id', 'type', 'status', 'priority', 'blocking', 'blocking_reason', 'origin',
                            'title', 'location', 'scenario', 'impact', 'evidence', 'correction'}, path)
        for key in ('id', 'title', 'scenario', 'impact', 'correction'):
            text(item.get(key), f'{path}.{key}')
        identifier = item.get('id')
        if schema_version in (6, 7) and not canonical_id(identifier, 'F') and identifier not in historical['findings']:
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

    coverage_fields = {'flows', 'limitations'}
    if stage == 'final':
        coverage_fields |= {'adequate', 'verification', 'stale'}
        if schema_version in (2, 3, 4, 5, 6, 7):
            coverage_fields.add('areas')
    coverage = fields(record.get('coverage'), coverage_fields, 'coverage')
    for i, flow in enumerate(array(coverage.get('flows'), 'coverage.flows')):
        text(flow, f'coverage.flows[{i}]')
    limitations = []
    for i, raw in enumerate(array(coverage.get('limitations'), 'coverage.limitations')):
        limitation = fields(raw, {'detail', 'material'}, f'coverage.limitations[{i}]')
        text(limitation.get('detail'), f'coverage.limitations[{i}].detail')
        boolean(limitation.get('material'), f'coverage.limitations[{i}].material')
        limitations.append(limitation)
    if stage != 'final':
        return errors

    material_area_gap = False
    if schema_version in (2, 3, 4, 5, 6, 7):
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

    profile_choices = (CURRENT_PROFILES if schema_version == 7 else
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
    if schema_version in (4, 5, 6, 7):
        presentation = fields(record.get('presentation'), {'kind', 'subject'}, 'presentation')
        enum(presentation.get('kind'), REVIEW_KINDS, 'presentation.kind')
        text(presentation.get('subject'), 'presentation.subject')
        if isinstance(presentation.get('subject'), str) and any(c in presentation['subject'] for c in '\r\n'):
            error('presentation.subject', 'expected a single-line functional subject')
    if schema_version in (3, 4, 5, 6, 7):
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
        if schema_version in (6, 7):
            names |= {'previous_review_id', 'previous_reference', 'previous_finding_id', 'previous_title', 'previous_url', 'check_ids'}
        item = fields(raw, names, path)
        text(item.get('id'), f'rereview[{i}].id')
        if isinstance(item.get('id'), str):
            previous_ids.add(item['id'])
        enum(item.get('status'), set(REREVIEW_STATUS) if schema_version in (6, 7) else {'resolved', 'still_valid', 'withdrawn', 'new'}, f'rereview[{i}].status')
        text(item.get('details'), f'rereview[{i}].details')
        if schema_version in (6, 7):
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
    if schema_version in (6, 7) and isinstance(aliases, dict):
        for alias, survivor in aliases.items():
            if (isinstance(alias, str) and isinstance(survivor, str)
                    and alias in historical['findings'] and survivor in historical_sources
                    and survivor in finding_ids | previous_ids and survivor not in aliases
                    and alias not in finding_ids | previous_ids):
                historical_aliases.add(alias)
    if schema_version in (6, 7):
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
            if schema_version in (6, 7) and not canonical_id(alias, 'F') and alias not in historical_aliases:
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
    return errors


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
    if not isinstance(record, dict) or record.get('schema_version') not in (6, 7):
        raise ValueError('canonical ID allocation requires schema 6 or 7')
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


def one_line(value):
    return ' '.join(str(value).splitlines()).strip()


def table_cell(value):
    return one_line(value).replace('|', '\\|')


def markdown_text(value):
    """Keep untrusted metadata inside one literal Markdown block."""
    return re.sub(r'([\\`*{}\[\]()#+!_|>~])', r'\\\1', html.escape(one_line(value), quote=False))


def reference_text(value):
    raw = one_line(value)
    try:
        parsed = urlsplit(raw)
        if parsed.scheme in ('http', 'https') and parsed.netloc and not parsed.username:
            return '[Ver referencia](' + quote(raw, safe='/:#?&=%-._~') + ')'
    except ValueError:
        pass
    return markdown_text(raw)


def person_text(person):
    if person['verified'] is not True:
        return 'No identificado'
    # Validated account characters are safe and must remain intact for mentions.
    return '@' + person['username'] if person['username'] else markdown_text(person['name'])


def previous_reviews_text(record, audience):
    """Preserve parent identity without publishing private archive references."""
    references = []
    for prior in record.get('previous_reviews', []):
        parts = [prior['review_id']] if prior.get('review_id') else []
        reference = prior.get('reference')
        if reference and (audience == 'user' or (prior.get('verified') is True and public_url(reference))):
            parts.append(reference_text(reference))
        references.append(' · '.join(parts) or 'Fuente verificada conservada en el registro')
    return '; '.join(references)


def public_projection(text, record):
    """Exclude recorded raw commands and private absolute paths from publication."""
    for check in record.get('checks', []):
        command = one_line(check.get('command', ''))
        if command:
            text = text.replace(command, '[comprobación registrada]')
            text = text.replace(markdown_text(command), '[comprobación registrada]')
    urls = []

    def preserve_url(match):
        urls.append(match.group(0))
        return f'PUBLICURLPLACEHOLDER{len(urls) - 1}END'

    text = re.sub(r'https?://[^\s<>)\]]+', preserve_url, text)
    text = re.sub(r'(?i)(?<![a-z0-9])[a-z]:[\\/][^\s;|<>)]+', '[ruta privada]', text)
    text = re.sub(r'(?<![\w:#/<])/(?!/)[^\s;|<>)\]]+', '[ruta privada]', text)
    text = re.sub(r'\\\\[^\s;|<>)]+', '[ruta privada]', text)
    for index, url in enumerate(urls):
        text = text.replace(f'PUBLICURLPLACEHOLDER{index}END', url)
    return text


def confirmed_counts_text(findings):
    """Format the shared priority/icon summary, counting confirmed findings only."""
    return ' · '.join(
        f"{label.split()[0]} {priority}: "
        f"{sum(item['status'] == 'confirmed' and item['priority'] == priority for item in findings)}"
        for priority, label in PRIORITIES.items())


def render(record, audience='user'):
    errors = validate(record)
    if errors or record.get('stage') != 'final':
        raise ValueError('; '.join(errors) if errors else 'only final records can be rendered')
    if audience not in {'user', 'comment'}:
        raise ValueError('audience must be user or comment')
    scope = record['scope']
    responsible = record['responsible']
    version = scope['snapshot'] or scope['head']
    remote = scope['mode'] in {'mr', 'pr'}
    responsibility = 'Responsable del MR/PR' if remote else 'Responsable'
    presentation = record.get('presentation')
    title = (REVIEW_KINDS[presentation['kind']] + ' — ' + markdown_text(presentation['subject'])
             if presentation else 'Code Review')
    lines = ['## ' + title, '', f"### Veredicto: **{VERDICTS[record['verdict']]}**", '',
             markdown_text(record['verdict_reason']), '',
             f"- **Alcance:** {markdown_text(scope['repository'])} · {MODE_LABELS[scope['mode']]}",
             f"- **Versión:** {markdown_text(scope['base'] or 'sin comparación')} → {markdown_text(version)}"]
    if record.get('review_id'):
        lines.append('- **ID de revisión:** ' + record['review_id'])
    if record.get('previous_reviews'):
        lines.append('- **Revisiones previas:** ' + previous_reviews_text(record, audience))
    if scope['target']:
        lines.append(f"- **Destino:** {markdown_text(scope['target'])}")
    lines.append(f'- **{responsibility}:** {person_text(responsible)}')
    if record['schema_version'] in (3, 4, 5, 6, 7):
        authors = '; '.join(person_text(author) for author in record['change_authors']) or 'No identificados'
        lines.append('- **Autores del cambio:** ' + authors)
    if scope['reference']:
        reference_label = 'MR/PR' if scope['mode'] in {'mr', 'pr'} else 'Referencia'
        lines.append(f"- **{reference_label}:** {reference_text(scope['reference'])}")
    if audience == 'user':
        lines.extend([f"- **Perfil:** {PROFILES[record['profile']]} — {markdown_text(record['profile_reason'])}.",
                      f"- **Verificación:** {VERIFICATION[record['coverage']['verification']]}."])
    description = record['description']
    if description['status'] != 'not_applicable':
        lines.append(f"- **Descripción:** {DESCRIPTION[description['status']]} — {markdown_text(description['details'])}")
    else:
        lines.append('- **Descripción:** No aplica; revisión local.')
    confirmed = sorted((f for f in record['findings'] if f['status'] == 'confirmed'),
                       key=lambda f: (f['priority'], f['id']))
    counts = confirmed_counts_text(record['findings'])
    lines.extend(['', '### Hallazgos', '', '**Confirmados:** ' + counts])
    if confirmed:
        for ordinal, item in enumerate(confirmed, 1):
            location = item['location']
            label = f"{location['path']}:{location['line']}" if item['type'] == 'code' else location['section']
            if location['url']:
                label = f"[{one_line(label)}]({location['url']})"
            ledger = {check['id']: check for check in record['checks']}
            evidence = '; '.join(('Comprobación' if ev['check_id'] and ev['details'] == ledger[ev['check_id']]['evidence'] else one_line(ev['details']))
                                 + (f" [{ev['check_id']}]" if ev['check_id'] else '') for ev in item['evidence'])
            lines.extend(['', '<a id="' + html.escape(item['id'], quote=True) + '"></a>', '',
                          f"### {PRIORITIES[item['priority']]} — {one_line(item['id'])}", '',
                          f"#### {ordinal}. {one_line(item['title'])}", '',
                          f"- **Ubicación:** {label} · **Origen:** {ORIGINS[item['origin']]}",
                          f"- **Escenario:** {one_line(item['scenario'])}",
                          f"- **Impacto:** {one_line(item['impact'])}",
                          f'- **Evidencia:** {evidence}', f"- **Corrección requerida:** {one_line(item['correction'])}",
                          '- **Bloqueante:** ' + ('sí — ' + one_line(item['blocking_reason']) if item['blocking'] else 'no')])
    else:
        lines.extend(['', 'No se confirmaron defectos bloqueantes dentro del alcance revisado.'])
    unresolved = [f for f in record['findings'] if f['status'] == 'unresolved']
    limitations = [dict(item) for item in record['coverage']['limitations']]
    lines.extend(['', '### Validación', ''])
    if record['checks']:
        for check in record['checks']:
            lines.extend(['', '<a id="' + html.escape(check['id'], quote=True) + '"></a>', ''])
            reuse = ' · evidencia reutilizada: ' + one_line(check['reuse_reason']) if check['reused'] else ''
            repeat = f" · repetición: {one_line(check['rerun_reason'])}" if check['rerun_reason'] else ''
            classification = f" · fallo de {FAILURE_KINDS[check['failure_kind']]}" if check['failure_kind'] else ''
            command = f" `{one_line(check['command'])}` —" if audience == 'user' else ''
            lines.append(f"- {check['id']}:{command} {CHECK_STATUS[check['status']]} · versión {one_line(check['revision'])}{classification}{reuse}{repeat}")
            if check.get('evidence'):
                lines.append('  - **Evidencia:** ' + markdown_text(check['evidence']))
            if check.get('reference'):
                lines.append('  - **Referencia de ejecución:** ' + reference_text(check['reference']))
    else:
        lines.append('- Inspección estática; no se ejecutaron comprobaciones.')
    if audience == 'user' and record['coverage']['flows']:
        lines.extend(['', '**Cobertura:** ' + '; '.join(one_line(flow) for flow in record['coverage']['flows']) + '.'])
    areas = record['coverage'].get('areas', [])
    if audience == 'user' and areas:
        lines.extend(['', '### Matriz ABCDE', '',
                      '| Área | Estado | Evidencia o motivo | Hallazgos |',
                      '|---|---|---|---|'])
        for row in sorted(areas, key=lambda item: item['area']):
            references = ', '.join(table_cell(identifier) for identifier in row['finding_ids']) or '—'
            lines.append(f"| {row['area']} — {AREAS[row['area']]} | {AREA_STATUS[row['status']]} | {table_cell(row['details'])} | {references} |")
    known_limits = {one_line(item['detail']): i for i, item in enumerate(limitations)}
    for row in areas:
        detail = one_line(row['details'])
        if row['material']:
            if detail in known_limits:
                limitations[known_limits[detail]]['material'] = True
            else:
                known_limits[detail] = len(limitations)
                limitations.append({'detail': detail, 'material': True})
    if unresolved or limitations:
        lines.extend(['', '### Incertidumbres', ''])
        lines.extend(f"- {f['id']}: {one_line(f['title'])} — {one_line(f['scenario'])}" for f in unresolved)
        lines.extend(f"- {one_line(item['detail'])}" + (' [material]' if item['material'] else '') for item in limitations)
    conditions = [f"{f['id']}: {one_line(f['correction'])}" for f in confirmed if f['blocking']]
    conditions.extend(one_line(r) for r in record['reservations'])
    if conditions:
        lines.extend(['', '### Condiciones y reservas', ''])
        lines.extend('- [ ] ' + condition for condition in conditions)
    if record['rereview']:
        lines.extend(['', '### Re-review', ''])
        for item in record['rereview']:
            source = ''
            if item.get('previous_finding_id'):
                source = f" · anterior {markdown_text(item['previous_finding_id'])}: {markdown_text(item['previous_title'])}"
                reference = item.get('previous_url') or item.get('previous_reference')
                if reference and (audience == 'user' or public_url(reference)):
                    source += ' · ' + reference_text(reference)
                if item.get('previous_review_id'):
                    source += ' · ' + item['previous_review_id']
            checks = ' · comprobaciones: ' + ', '.join(item['check_ids']) if item.get('check_ids') else ''
            lines.append(f"- {item['id']}: {REREVIEW_STATUS[item['status']]}{source} — {one_line(item['details'])}{checks}")
    if audience == 'user' and (record['resources']['residuals'] or record['resources']['publication'] in {'published', 'failed'}):
        lines.extend(['', '### Recursos y publicación', ''])
        lines.extend('- Recurso pendiente: ' + one_line(p) for p in record['resources']['residuals'])
        if record['resources']['publication'] in {'published', 'failed'}:
            lines.append('- Publicación: ' + record['resources']['publication'])
    output = '\n'.join(lines) + '\n'
    return public_projection(output, record) if audience == 'comment' else output


def render_handoff(record, context=None, audience='user'):
    """Render an explicitly requested contextual index, never an authorization."""
    errors = validate(record)
    if errors or record.get('stage') != 'final':
        raise ValueError('; '.join(errors) if errors else 'only final records can be rendered')
    if audience not in {'user', 'comment'}:
        raise ValueError('audience must be user or comment')
    context = context or {}
    allowed = {'source_record', 'source_report', 'requirements', 'plan', 'decisions_pending'}
    if not isinstance(context, dict) or set(context) - allowed:
        raise ValueError('unknown handoff context fields')
    scope = record['scope']
    lines = ['## Transferencia contextual de revisión', '',
             '- **ID de revisión:** ' + record.get('review_id', 'ID histórico no disponible'),
             '- **Alcance:** ' + markdown_text(scope['repository']) + ' · ' + MODE_LABELS[scope['mode']]]
    if record.get('previous_reviews'):
        lines.append('- **Revisiones previas:** ' + previous_reviews_text(record, audience))
    for key, label in [('base', 'Base'), ('head', 'Head'), ('snapshot', 'Snapshot'), ('target', 'Destino')]:
        if scope.get(key):
            lines.append(f'- **{label}:** ' + markdown_text(scope[key]))
    if scope.get('reference'):
        lines.append('- **Referencia del alcance:** ' + reference_text(scope['reference']))
    for key, label in [('source_record', 'Registro fuente'), ('source_report', 'Informe fuente')]:
        if context.get(key):
            if not isinstance(context[key], str):
                raise ValueError(key + ' must be a reference string')
            lines.append(f'- **{label}:** ' + reference_text(context[key]))
    lines.extend(['', '### Índice de hallazgos confirmados', ''])
    confirmed = [item for item in record['findings'] if item['status'] == 'confirmed']
    for item in sorted(confirmed, key=lambda item: (item['priority'], item['id'])):
        correction_reference = ''
        if context.get('source_report'):
            target = context['source_report'].split('#')[0] + '#' + item['id']
            correction_reference = ' · [Corrección ' + markdown_text(item['id']) + '](' + quote(target, safe='/:#?&=%-._~') + ')'
        lines.append(f"- {item['id']} · {item['priority']} · bloqueante: {'sí' if item['blocking'] else 'no'} · "
                     + markdown_text(item['title']) + ' · corrección requerida: ' + markdown_text(item['correction']) + correction_reference)
    if not confirmed:
        lines.append('- Ningún hallazgo confirmado.')
    uncertainties = [item['id'] + ': ' + item['title'] for item in record['findings'] if item['status'] == 'unresolved']
    uncertainties += [item['detail'] for item in record['coverage']['limitations']]
    uncertainties += [row['details'] for row in record['coverage'].get('areas', []) if row['status'] in {'partial', 'not_evaluated'}]
    pending = context.get('decisions_pending', [])
    if not isinstance(pending, list) or any(not isinstance(item, str) for item in pending):
        raise ValueError('decisions_pending must be a text array')
    lines.extend(['', '### Incertidumbres y decisiones pendientes', ''])
    lines.extend('- ' + markdown_text(item) for item in dict.fromkeys(uncertainties + pending + record['reservations']))
    if not uncertainties and not pending and not record['reservations']:
        lines.append('- Ninguna registrada.')
    lines.extend(['', '### Comprobaciones y referencias', ''])
    for check in record['checks']:
        evidence_ref = (' · referencia: ' + reference_text(check['reference']) if check.get('reference') else
                        ' · [Evidencia ' + check['id'] + '](' + quote(context['source_report'].split('#')[0] + '#' + check['id'], safe='/:#?&=%-._~') + ')' if context.get('source_report') else
                        ' · evidencia: véase Validación del informe fuente')
        lines.append(f"- {check['id']} · {CHECK_STATUS[check['status']]} · versión {markdown_text(check['revision'])}" +
                     evidence_ref)
    if not record['checks']:
        lines.append('- Inspección estática; sin comprobaciones ejecutadas.')
    for key, label in [('requirements', 'Requisitos y especificaciones'), ('plan', 'Plan')]:
        entries = context.get(key, [])
        if not isinstance(entries, list):
            raise ValueError(key + ' must be an array of collected provenance')
        if entries:
            lines.extend(['', '### ' + label, ''])
        for item in entries:
            if isinstance(item, str):
                lines.append('- ' + reference_text(item))
            elif isinstance(item, dict) and set(item) == {'title', 'reference', 'identity'} and all(isinstance(item[key], str) and item[key].strip() for key in item):
                lines.append('- ' + markdown_text(item['title']) + ' · ' + reference_text(item['reference']) + ' · identidad: ' + markdown_text(item['identity']))
            else:
                raise ValueError('provenance needs title, reference and captured identity')
    lines.extend(['', 'Antes de continuar, comprobar que base, head y snapshot coincidan con la versión actual y repetir las comprobaciones afectadas o pendientes con un nuevo ID de ejecución.',
                  'La transferencia conserva el contexto; cualquier corrección, commit o publicación requiere la autorización correspondiente.'])
    output = '\n'.join(lines) + '\n'
    return public_projection(output, record) if audience == 'comment' else output


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('validate', 'render-user', 'render-comment', 'render-handoff', 'canonicalize-ids', 'deduplicate'))
    parser.add_argument('--input', required=True, help='Record JSON; for deduplicate: findings array JSON')
    parser.add_argument('--groups', help='Explicit same-cause ID groups JSON; required for deduplicate')
    parser.add_argument('--context', help='Optional explicitly collected handoff provenance JSON')
    parser.add_argument('--reserved-ids', help='Known review-chain finding/check ID arrays for monotonic allocation')
    args = parser.parse_args()
    try:
        value = json.loads(Path(args.input).read_text(encoding='utf-8'))
        if args.command == 'validate':
            errors = validate(value)
            print(json.dumps({'valid': not errors, 'errors': errors}, ensure_ascii=False))
            return 1 if errors else 0
        if args.command == 'deduplicate':
            if not args.groups:
                raise ValueError('--groups is required')
            groups = json.loads(Path(args.groups).read_text(encoding='utf-8'))
            print(json.dumps(deduplicate(value, groups), ensure_ascii=False))
        elif args.command == 'canonicalize-ids':
            reserved = json.loads(Path(args.reserved_ids).read_text(encoding='utf-8')) if args.reserved_ids else None
            record, mapping = canonicalize_ids(value, reserved_ids=reserved)
            print(json.dumps({'record': record, 'source_mapping': mapping}, ensure_ascii=False))
        elif args.command == 'render-handoff':
            context = json.loads(Path(args.context).read_text(encoding='utf-8')) if args.context else None
            print(render_handoff(value, context=context), end='')
        else:
            print(render(value, 'user' if args.command == 'render-user' else 'comment'), end='')
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
