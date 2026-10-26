"""Pure material/context contracts and conservative reuse policy."""
import copy
import hashlib
import json

from ccr.archive.layout import logical_scope
from ccr.contracts.effective_changes import HASH, MODES, MAX_ENTRIES, decode_path, diagnostics as validate_diagnostics, normalize_effective_changes
from ccr.contracts.reference_index import canonical_reference, validate_reference_selection
from ccr.contracts.reference_types import INPUT_PURPOSES
from ccr.contracts.references import parse_reference
from ccr.contracts.scope import require_scope

CHANGES = 'evidence/effective-changes.json'
MATERIALS = 'evidence/reuse-materials.json'
CONTEXT = 'evidence/review-context.json'
GENERATED = {CHANGES, MATERIALS}


def _materials(rows):
    if not isinstance(rows, list) or len(rows) > 128:
        raise ValueError('material map exceeds bounded size')
    seen = set()
    for row in rows:
        if (not isinstance(row, dict) or set(row) != {'key','purpose','reference','sha256'}
                or not isinstance(row['key'],str) or not row['key'] or len(row['key']) > 500
                or any(ord(c)<32 for c in row['key']) or row['key'] in seen
                or row['purpose'] not in INPUT_PURPOSES):
            raise ValueError('invalid or duplicate material key')
        seen.add(row['key'])
        if row['reference'] is None:
            if row['sha256'] is not None:
                raise ValueError('absent material must have no digest')
        else:
            path, fragment = parse_reference(row['reference'], field='reuse material', allow_alias_key=True)
            if fragment is not None or not path.startswith('evidence/') or path in GENERATED:
                raise ValueError('material must identify a selected source')
            if not isinstance(row['sha256'],str) or not HASH.fullmatch(row['sha256']):
                raise ValueError('invalid material digest')
    return sorted(copy.deepcopy(rows), key=lambda r:r['key'])


def build_material_map(materials, *, complete, diagnostics: list):
    if type(complete) is not bool:
        raise ValueError('material completeness must be boolean')
    validate_diagnostics(diagnostics)
    return dict(schema_version=1, complete=complete, entries=_materials(materials), diagnostics=copy.deepcopy(diagnostics))


def normalize_material_map(value):
    if (not isinstance(value,dict) or set(value) != {'schema_version','complete','entries','diagnostics'}
            or type(value['schema_version']) is not int or value['schema_version'] != 1):
        raise ValueError('invalid material map schema')
    return build_material_map(value['entries'],complete=value['complete'],diagnostics=value['diagnostics'])


def validate_material_map(value, index, sources):
    value = normalize_material_map(value)
    issues = validate_reference_selection(index,sources)
    if issues:
        raise ValueError('invalid selected material bytes: ' + '; '.join(i['message'] for i in issues))
    aliases = index.get('aliases',{})
    required = {(r['reference'],r['purpose'],r['sha256']) for r in index['inputs']
                if r['reference'] not in GENERATED}
    observed = set()
    for row in value['entries']:
        if row['reference'] is None:
            continue
        ref = canonical_reference(row['reference'],aliases)
        key = (ref,row['purpose'],row['sha256'])
        if key not in required or hashlib.sha256(sources[ref]).hexdigest() != row['sha256']:
            raise ValueError('material map differs from captured sources')
        if key in observed:
            raise ValueError('one material source cannot have multiple semantic keys')
        observed.add(key)
    if observed != required:
        raise ValueError('material map does not cover every selected material source')
    return value


def build_review_context(scope, files, materials, *, logical_scope_identity, complete, diagnostics):
    require_scope(scope)
    if logical_scope(scope)['identity'] != logical_scope_identity or type(complete) is not bool:
        raise ValueError('context logical scope or completeness differs')
    validate_diagnostics(diagnostics)
    if not isinstance(files,list) or len(files)>MAX_ENTRIES:
        raise ValueError('context files exceed bounded size')
    seen = set()
    for row in files:
        if (not isinstance(row,dict) or set(row) != {'side','path_b64','mode','content_sha256'}
                or row['side'] not in ('base','head') or row['mode'] not in MODES
                or not isinstance(row['content_sha256'],str) or not HASH.fullmatch(row['content_sha256'])):
            raise ValueError('invalid context file')
        key = (row['side'], decode_path(row['path_b64']))
        if key in seen:
            raise ValueError('duplicate context file')
        seen.add(key)
    return dict(schema_version=1, logical_scope_identity=logical_scope_identity, scope=copy.deepcopy(scope),
        files=sorted(copy.deepcopy(files),key=lambda r:(r['side'],decode_path(r['path_b64']))),
        materials=_materials(materials),complete=complete,diagnostics=copy.deepcopy(diagnostics))


def normalize_review_context(value):
    if (not isinstance(value,dict) or set(value) != {'schema_version','logical_scope_identity','scope',
            'files','materials','complete','diagnostics'} or type(value['schema_version']) is not int
            or value['schema_version'] != 1):
        raise ValueError('invalid review context schema')
    return build_review_context(**{k:v for k,v in value.items() if k!='schema_version'})


def compare_review_context(retained,current):
    try:
        old,new = normalize_review_context(retained),normalize_review_context(current)
    except (ValueError,TypeError,KeyError):
        return dict(applicability='unknown',reasons=[dict(code='context_unknown',detail='Review context inventory is unavailable.')])
    if not old['complete'] or not new['complete']:
        return dict(applicability='unknown',reasons=[dict(code='context_incomplete',detail='Review context is not explicitly complete.')])
    def projection(value):
        return (value['logical_scope_identity'],value['files'],
                [{k:v for k,v in r.items() if k!='reference'} for r in value['materials']])
    same = projection(old)==projection(new)
    return dict(applicability='applicable' if same else 'changed', reasons=[] if same else
                [dict(code='material_context_changed',detail='A consumed file or material requirement changed.')])


def validate_reuse_evidence(scope,index,sources,*,require_context=False):
    """Optional sidecars extend evidence, never the archive/review schema."""
    if not any(name in sources for name in GENERATED | {CONTEXT}):
        return
    if not GENERATED.issubset(sources):
        raise ValueError('reuse evidence needs both initial sidecars')
    descriptor = normalize_effective_changes(json.loads(sources[CHANGES]))
    if (descriptor['logical_scope_identity'] != logical_scope(scope)['identity']
            or descriptor['comparison']['head'] != scope['head']
            or descriptor['comparison']['base'] != scope['base']
            or descriptor['comparison']['diff_base'] != scope['base']):
        raise ValueError('effective changes differ from pinned review scope')
    materials = validate_material_map(json.loads(sources[MATERIALS]),index,sources)
    if CONTEXT in sources:
        context = normalize_review_context(json.loads(sources[CONTEXT]))
        if context['scope'] != scope or context['materials'] != materials['entries']:
            raise ValueError('review context differs from captured inputs')
        if context['complete'] and not materials['complete']:
            raise ValueError('incomplete materials cannot certify complete review context')
    elif require_context:
        raise ValueError('guided reuse evidence needs final review context')


def decide_reuse(code,context,*,has_prior,current_scope_ready):
    if code.get('code_equivalence') not in ('equivalent','different','unknown') or context.get('applicability') not in ('applicable','changed','unknown'):
        raise ValueError('invalid reuse comparison state')
    action = ('blocked_current_scope' if not current_scope_ready else
              'offer_choice' if has_prior and code['code_equivalence']=='equivalent'
              and context['applicability']=='applicable' else 'new_review')
    reasons = copy.deepcopy(code.get('reasons',[])+context.get('reasons',[]))
    if not current_scope_ready:
        reasons.append(dict(code='current_scope_unknown',detail='Acquire the current scope before review.'))
    elif not has_prior:
        reasons.append(dict(code='no_reusable_result',detail='No unambiguous verified previous result.'))
    return dict(action=action,code_equivalence=code['code_equivalence'],
        applicability=context['applicability'],reasons=reasons,
        changed_paths=copy.deepcopy(code.get('changed_paths',[])),metadata_only=code.get('metadata_only',False))
