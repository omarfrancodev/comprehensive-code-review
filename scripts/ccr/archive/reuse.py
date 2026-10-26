"""Read-only admission based on verified history and content, never just a SHA."""
import copy
import hashlib
import json

from ccr.archive.integrity import verify_files
from ccr.archive.lookup import latest_verified_candidate
from ccr.archive.reader import load_run
from ccr.archive.layout import logical_scope
from ccr.contracts.effective_changes import normalize_effective_changes, compare_effective_changes
from ccr.contracts.material_inputs import validate_captured_material_sources
from ccr.contracts.reference_index import reference_source_paths
from ccr.execution.change_scope import collect_effective_changes, collect_context_files
from ccr.shared.git import git
from ccr.shared.json_io import read_bounded
from ccr.workflow.inputs import normalize_inputs
from ccr.workflow.reuse import (CHANGES,MATERIALS,CONTEXT,build_material_map,normalize_material_map,
    normalize_review_context,build_review_context,compare_review_context,decide_reuse,
    validate_material_map,validate_reuse_evidence,compare_material_identities,coverage_reuse_issue)

LIMIT=64*1024*1024
INDEX='evidence/reference-index.json'


def _source(run,manifest,reference):
    expected=manifest.get('hashes',{}).get(reference)
    if not expected:
        raise ValueError('previous source was not retained')
    data=read_bounded(run/reference,LIMIT)
    if hashlib.sha256(data).hexdigest()!=expected:
        raise ValueError('previous evidence differs from retained hash')
    return data


def _retained_sources(run,manifest):
    sources={}
    if INDEX in manifest['hashes']:
        sources[INDEX]=_source(run,manifest,INDEX)
        index=json.loads(sources[INDEX])
        for ref in reference_source_paths(index):
            sources[ref]=_source(run,manifest,ref)
    for ref in (CHANGES,MATERIALS,CONTEXT):
        if ref in manifest['hashes']:
            sources[ref]=_source(run,manifest,ref)
    # reference_source_paths already enforces 64 indexed files including INDEX.
    # Derived context is outside that selection, but remains in the byte budget.
    if sum(map(len,sources.values()))>LIMIT:
        raise ValueError('previous selected evidence exceeds reuse limits')
    return sources


def _legacy_materials(manifest,sources,current_materials):
    captured=manifest.get('review_inputs') or {}
    if captured.get('source_set_complete') is not True:
        raise ValueError('historical source completeness is unknown')
    fields=('description_identity','requirements_identity','plan_identity','configuration_identity')
    if any(k not in captured for k in fields):
        raise ValueError('historical optional identities are unknown')
    if INDEX not in sources:
        if captured.get('sources') or any(captured[k] is not None for k in fields):
            raise ValueError('historical material sources unavailable')
        index=dict(schema_version=1,aliases={},inputs=[])
    else:
        index=json.loads(sources[INDEX])
        if validate_captured_material_sources(captured,index,sources):
            raise ValueError('historical material inventory is not verified')
    rows=[r for r in index['inputs'] if r['reference'] not in (CHANGES,MATERIALS)]
    current=normalize_material_map(current_materials)
    result=[]
    for row in current['entries']:
        matching=[r for r in rows if r['purpose']==row['purpose']]
        if row['reference'] is None and not matching:
            result.append(copy.deepcopy(row))
        elif len(matching)==1:
            result.append(dict(key=row['key'],**matching[0]))
        else:
            raise ValueError('historical semantic material identity cannot be reconstructed')
    if len([r for r in result if r['reference']])!=len(rows):
        raise ValueError('historical materials differ from current set')
    return build_material_map(result,complete=True,diagnostics=[])


def _full_tree_context(repo,old_scope,current_scope,old_materials,identity):
    for key in ('base','head'):
        if git(repo,'rev-parse',old_scope[key]+'^{tree}') != git(repo,'rev-parse',current_scope[key]+'^{tree}'):
            raise ValueError('historical context inventory missing and trees differ')
    return build_review_context(old_scope,[],old_materials['entries'],
        logical_scope_identity=identity,complete=old_materials['complete'],diagnostics=[])


def assess_reuse(repo,scope,*,current_inputs,effective_changes,current_materials,current_sources,
                 logical_scope_input=None,archive_root=None,max_scan=10000):
    inputs=normalize_inputs(current_inputs)
    descriptor=normalize_effective_changes(effective_changes)
    materials=normalize_material_map(current_materials)
    if inputs['scope']!=scope:
        raise ValueError('current input scope differs from requested scope')
    if INDEX not in current_sources:
        raise ValueError('current reference index must be selected')
    index=json.loads(current_sources[INDEX])
    if (hashlib.sha256(current_sources[INDEX]).hexdigest()!=inputs['sources'].get(INDEX)
            or validate_captured_material_sources(inputs,index,current_sources)):
        raise ValueError('current sources differ from captured inputs')
    validate_material_map(materials,index,current_sources)
    validate_reuse_evidence(scope,index,current_sources)
    if json.loads(current_sources[CHANGES])!=descriptor or json.loads(current_sources[MATERIALS])!=materials:
        raise ValueError('supplied comparison differs from captured evidence')
    if descriptor['complete'] and collect_effective_changes(repo,scope,
            target_head=descriptor['comparison']['target_head'])!=descriptor:
        raise ValueError('current descriptor no longer matches its Git objects')
    unknown_code=dict(code_equivalence='unknown',changed_paths=[],metadata_only=False,reasons=[])
    unknown_context=dict(applicability='unknown',reasons=[])
    scope_ready=not any(r['code']=='current_scope_unknown' for r in descriptor['diagnostics'])
    def finish(code=unknown_code,context=unknown_context,prior=None,reason=None):
        result=decide_reuse(code,context,has_prior=prior is not None,current_scope_ready=scope_ready)
        if reason:
            result['reasons'].append(dict(code='previous_result_unknown',detail=str(reason)[:2000]))
        return dict(schema_version=1,prior_run=prior,**result)
    if not scope_ready:
        return finish(reason='Current Git objects or effective base are unavailable.')
    selected=latest_verified_candidate(repo,scope,current_inputs=inputs,
        logical_scope_input=logical_scope_input,archive_root=archive_root,max_scan=max_scan)
    if selected['status']!='selected':
        return finish(reason=selected['status'])
    candidate=selected['selected']
    try:
        run,manifest,_=load_run(candidate['run_dir'])
        verify_files(run,manifest)
        if (manifest.get('review_inputs') or {}).get('source_set_complete') is not True:
            raise ValueError('previous material source completeness is unknown')
        initial_hashes=copy.deepcopy(manifest['hashes'])
        record=json.loads(_source(run,manifest,'review.json'))
        coverage_issue=coverage_reuse_issue(record)
        if coverage_issue is not None:
            return finish(context=dict(applicability='changed',reasons=[coverage_issue]))
        sources=_retained_sources(run,manifest)
        old_scope=manifest['scope']
        old=(normalize_effective_changes(json.loads(sources[CHANGES])) if CHANGES in sources else
             collect_effective_changes(repo,old_scope,target_head=old_scope['base']))
        if (old['comparison']['base']!=old_scope['base'] or old['comparison']['head']!=old_scope['head']
                or old['logical_scope_identity']!=logical_scope(old_scope)['identity']):
            raise ValueError('historical descriptor differs from reviewed scope')
        code=compare_effective_changes(old,descriptor)
        old_materials=(normalize_material_map(json.loads(sources[MATERIALS])) if MATERIALS in sources
                       else _legacy_materials(manifest,sources,materials))
        if MATERIALS in sources:
            validate_material_map(old_materials,json.loads(sources[INDEX]),sources)
        if CONTEXT in sources:
            old_context=normalize_review_context(json.loads(sources[CONTEXT]))
            if old_context['scope']!=old_scope or old_context['materials']!=old_materials['entries']:
                raise ValueError('previous context differs from captured scope/materials')
            current_files=collect_context_files(repo,descriptor['comparison'],old_context['files'])
        else:
            old_context=_full_tree_context(repo,old_scope,scope,old_materials,old['logical_scope_identity'])
            current_files=[]
        current_context=build_review_context(scope,current_files,materials['entries'],
            logical_scope_identity=descriptor['logical_scope_identity'],
            complete=old_context['complete'] and materials['complete'] and inputs.get('source_set_complete') is True,
            diagnostics=[])
        context=compare_review_context(old_context,current_context)
        identities=compare_material_identities(manifest['review_inputs'],inputs)
        states=[context['applicability'],identities['applicability']]
        context=dict(applicability='changed' if 'changed' in states else 'unknown' if 'unknown' in states else 'applicable',
                     reasons=context['reasons']+identities['reasons'])
        if inputs.get('profile') is not None and inputs['profile']!=candidate.get('profile'):
            context=dict(applicability='changed',reasons=[dict(code='profile_changed',detail='Requested profile differs from previous review.')])
        _,final_manifest,_=load_run(candidate['run_dir'])
        verify_files(run,final_manifest)
        if final_manifest['hashes']!=initial_hashes or final_manifest['scope']!=old_scope:
            raise ValueError('previous result changed during assessment')
        final_selection=latest_verified_candidate(repo,scope,current_inputs=inputs,
            logical_scope_input=logical_scope_input,archive_root=archive_root,max_scan=max_scan)
        if (final_selection.get('status')!='selected'
                or any(final_selection['selected'].get(k)!=candidate.get(k) for k in ('run_dir','run_id','created_at'))):
            raise ValueError('latest verified selection changed during assessment')
        return finish(code,context,dict(run_dir=candidate['run_dir'],review_id=candidate['review_id']))
    except (OSError,ValueError,TypeError,KeyError,UnicodeError) as exc:
        return finish(reason=exc)
