"""Admission uses verified latest history, never an older convenient match."""
import copy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import test_review_change_scope as git_tests
from ccr.archive import reuse
from ccr.archive.layout import logical_scope
from ccr.execution.change_scope import collect_effective_changes,collect_context_files
from ccr.workflow.reuse import build_material_map,build_review_context,CHANGES,MATERIALS,CONTEXT


def current_sources(scope,descriptor,materials=None,extra=None):
    material_map = build_material_map(materials or [],complete=True,diagnostics=[])
    sources = {CHANGES:json.dumps(descriptor).encode(), MATERIALS:json.dumps(material_map).encode(), **(extra or {})}
    purposes = {r['reference']:r['purpose'] for r in material_map['entries'] if r['reference']}
    index=dict(schema_version=1,aliases={},inputs=[dict(reference=k,purpose=purposes.get(k,'other'),
        sha256=hashlib.sha256(v).hexdigest()) for k,v in sources.items()])
    sources['evidence/reference-index.json']=json.dumps(index).encode()
    inputs=dict(scope=scope,sources={k:hashlib.sha256(v).hexdigest() for k,v in sources.items()},
        source_set_complete=True,description_identity=None,requirements_identity=None,
        plan_identity=None,configuration_identity=None)
    return inputs,material_map,sources


class ReuseArchiveTests(unittest.TestCase):
    setUp=git_tests.ChangeScopeTests.setUp
    git=git_tests.ChangeScopeTests.git
    put=git_tests.ChangeScopeTests.put
    commit=git_tests.ChangeScopeTests.commit

    def fixture(self):
        descriptor=collect_effective_changes(self.repo,self.scope,target_head=self.base)
        inputs,materials,sources=current_sources(self.scope,descriptor)
        files=collect_context_files(self.repo,descriptor['comparison'],[dict(side='head',path_b64='ZmlsZS50eHQ=')])
        context=build_review_context(self.scope,files,[],logical_scope_identity=logical_scope(self.scope)['identity'],complete=True,diagnostics=[])
        archive=Path(self.temp.name)/'archive'
        (archive/'evidence').mkdir(parents=True)
        old_sources={**sources,CONTEXT:json.dumps(context).encode()}
        for ref,raw in old_sources.items():
            (archive/ref).write_bytes(raw)
        manifest=dict(scope=copy.deepcopy(self.scope),review_inputs=copy.deepcopy(inputs),
            hashes={ref:hashlib.sha256(raw).hexdigest() for ref,raw in old_sources.items()})
        selected=dict(run_dir=str(archive),run_id='a'*20,review_id='CR-'+ 'a'*20,profile='deep')
        return descriptor,inputs,materials,sources,manifest,selected

    def assess(self, fixture, selection=None, change_manifest=False):
        descriptor,inputs,materials,sources,manifest,selected=fixture
        result=selection or dict(status='selected',selected=selected)
        with patch.object(reuse,'latest_verified_candidate',return_value=result), \
             patch.object(reuse,'load_run',return_value=(Path(selected['run_dir']),manifest,{})), \
             patch.object(reuse,'verify_files'):
            if change_manifest:
                other=copy.deepcopy(manifest)
                other['hashes']['changed']='b'*64
                with patch.object(reuse,'load_run',side_effect=[(Path(selected['run_dir']),manifest,{}),
                    (Path(selected['run_dir']),other,{})]):
                    return reuse.assess_reuse(self.repo,inputs['scope'],current_inputs=inputs,effective_changes=descriptor,
                        current_materials=materials,current_sources=sources)
            return reuse.assess_reuse(self.repo,inputs['scope'],current_inputs=inputs,effective_changes=descriptor,
                        current_materials=materials,current_sources=sources)

    def test_latest_selection_is_not_applicability(self):
        fixture=self.fixture()
        self.assertEqual(self.assess(fixture)['action'],'offer_choice')
        fixture[0]['complete']=False
        fixture[3][CHANGES]=json.dumps(fixture[0]).encode()
        fixture[1]['sources'][CHANGES]=hashlib.sha256(fixture[3][CHANGES]).hexdigest()
        # An incomplete current descriptor cannot certify reuse (index binding also fails).
        with self.assertRaises(ValueError):
            self.assess(fixture)

    def test_older_equivalent_review_does_not_hide_latest_different(self):
        fixture=list(self.fixture())
        self.put('file.txt',b'new content\n')
        self.commit()
        new_scope=dict(self.scope,head=self.git('rev-parse','HEAD'))
        fixture[0]=collect_effective_changes(self.repo,new_scope,target_head=self.base)
        fixture[1],fixture[2],fixture[3]=current_sources(new_scope,fixture[0])
        result=self.assess(fixture)
        self.assertEqual(result['action'],'new_review')
        self.assertEqual(result['code_equivalence'],'different')

    def test_tie_scan_limit_or_corruption_never_offer_reuse(self):
        for status in ('ambiguous','incomplete_search','no_match'):
            self.assertEqual(self.assess(self.fixture_unique(),dict(status=status,selected=None))['action'],'new_review')

    def fixture_unique(self):
        # Same fixture content; remove only the exact test-owned directory through TemporaryDirectory cleanup.
        path=Path(self.temp.name)/'archive/evidence'
        if path.exists():
            for p in path.iterdir():
                p.unlink()
            path.rmdir()
            path.parent.rmdir()
        return self.fixture()

    def test_candidate_changed_before_return_is_not_reused(self):
        self.assertEqual(self.assess(self.fixture(),change_manifest=True)['action'],'new_review')

    def test_absent_context_and_unproven_delta_are_unknown(self):
        fixture=self.fixture()
        path=Path(fixture[-1]['run_dir'])/CONTEXT
        path.unlink()
        fixture[-2]['hashes'].pop(CONTEXT)
        fixture[-2]['review_inputs']['source_set_complete']=False
        self.assertEqual(self.assess(fixture)['action'],'new_review')

    def test_assessment_never_mutates_previous_run(self):
        fixture=self.fixture()
        path=Path(fixture[-1]['run_dir'])
        before={str(p):p.read_bytes() for p in path.rglob('*') if p.is_file()}
        self.assess(fixture)
        self.assertEqual(before,{str(p):p.read_bytes() for p in path.rglob('*') if p.is_file()})

    def test_old_archive_reconstructs_only_proven_range(self):
        fixture=self.fixture()
        old_sources={k:v for k,v in fixture[3].items() if k not in (CHANGES,MATERIALS)}
        old_sources['evidence/reference-index.json']=json.dumps(dict(schema_version=1,aliases={},inputs=[])).encode()
        manifest=fixture[-2]
        manifest['review_inputs']['sources']={k:hashlib.sha256(v).hexdigest() for k,v in old_sources.items()}
        manifest['hashes']={k:hashlib.sha256(v).hexdigest() for k,v in old_sources.items()}
        for ref,raw in old_sources.items():
            (Path(fixture[-1]['run_dir'])/ref).write_bytes(raw)
        self.assertEqual(self.assess(fixture)['action'],'offer_choice')


if __name__=='__main__':
    unittest.main()
