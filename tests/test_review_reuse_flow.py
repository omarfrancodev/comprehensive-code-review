"""Admission against real, retained archive-8 reviews and immutable Git objects."""
import copy
import hashlib
import json
from pathlib import Path
import unittest

import test_review_artifacts as archive_tests
from test_review_reuse_archive import current_sources
from ccr.archive.reuse import assess_reuse
from ccr.archive.layout import logical_scope
from ccr.execution.change_scope import collect_effective_changes, collect_context_files
from ccr.workflow.reuse import build_review_context,CONTEXT
from recovery_fixtures import selection_input
from test_review_contract import finding


class ReuseFlowTests(unittest.TestCase):
    git=archive_tests.ArchiveTests.git
    write=archive_tests.ArchiveTests.write
    read=archive_tests.ArchiveTests.read
    retain=archive_tests.ArchiveTests.retain
    close=archive_tests.ArchiveTests.close

    def setUp(self):
        archive_tests.ArchiveTests.setUp(self)
        (self.repo/'consumer.py').write_text('consumer = 1\n')
        self.git('add','consumer.py')
        self.git('commit','-m','consumer baseline')
        self.base=self.git('rev-parse','HEAD')
        self.git('branch','target')
        self.git('checkout','-b','feature')
        (self.repo/'code.txt').write_text('reviewed change\n')
        self.git('add','code.txt')
        self.git('commit','-m','feature')
        self.actual_scope=dict(repository='example/service',mode='mr',base=self.base,
            head=self.git('rev-parse','HEAD'),snapshot=None,target='target',
            reference='https://git.example/example/service/-/merge_requests/42')
        self.scope=self.write('scope.json',self.actual_scope)

    def capture(self,scope=None,materials=None,extra=None):
        scope=scope or self.actual_scope
        descriptor=collect_effective_changes(self.repo,scope,target_head=scope['base'])
        inputs,material_map,sources=current_sources(scope,descriptor,materials,extra)
        return dict(current_inputs=inputs,effective_changes=descriptor,current_materials=material_map,current_sources=sources)

    def archive(self,guided=True,complete=True,kind='review',identities=None,
                capture=None,final_update=None):
        capture=capture or self.capture()
        sources=copy.deepcopy(capture['current_sources'])
        inputs=copy.deepcopy(capture['current_inputs'])
        inputs.update(identities or {})
        if guided:
            files=collect_context_files(self.repo,capture['effective_changes']['comparison'],[
                dict(side='head',path_b64='Y29kZS50eHQ='),dict(side='head',path_b64='Y29uc3VtZXIucHk=')])
            context=build_review_context(self.actual_scope,files,capture['current_materials']['entries'],
                logical_scope_identity=logical_scope(self.actual_scope)['identity'],complete=True,diagnostics=[])
            sources[CONTEXT]=json.dumps(context).encode()
        else:
            sources={'evidence/reference-index.json':json.dumps(dict(schema_version=1,aliases={},inputs=[])).encode()}
            inputs['sources']={k:hashlib.sha256(v).hexdigest() for k,v in sources.items()}
        run=Path(archive_tests.artifacts.prepare(self.repo,self.scope,'3.1.0','codex',
            output_root=self.output,profile_input=selection_input(),current_inputs=inputs))
        if complete:
            if kind!='review' or final_update is not None:
                final=self.read(self.final)
                final['presentation']['kind']=kind
                if final_update is not None:
                    final_update(final)
                self.final=self.write('partial-final.json',final)
            paths=[]
            for ref,raw in sources.items():
                path=self.root/Path(ref).name
                path.write_bytes(raw)
                paths.append(path)
            extra_context=self.write('extra-context.json',dict(reference_index='evidence/reference-index.json'))
            self.retain(run,context_input=extra_context,evidence_inputs=paths)
            self.close(run)
        return run

    def assess(self,capture=None):
        capture=capture or self.capture()
        return assess_reuse(self.repo,capture['current_inputs']['scope'],archive_root=self.output,**capture)

    def test_empty_commit_reuses_verified_result_without_relabeling_checks(self):
        run=self.archive()
        before={p.relative_to(run):p.read_bytes() for p in run.rglob('*') if p.is_file()}
        self.git('commit','--allow-empty','-m','history only')
        scope=dict(self.actual_scope,head=self.git('rev-parse','HEAD'))
        result=self.assess(self.capture(scope))
        self.assertEqual(result['action'],'offer_choice',result)
        self.assertTrue(result['metadata_only'])
        self.assertEqual(before,{p.relative_to(run):p.read_bytes() for p in run.rglob('*') if p.is_file()})

    def test_real_edit_automatically_starts_review(self):
        self.archive()
        (self.repo/'code.txt').write_text('additional modification\n')
        self.git('add','code.txt'); self.git('commit','-m','real change')
        result=self.assess(self.capture(dict(self.actual_scope,head=self.git('rev-parse','HEAD'))))
        self.assertEqual(result['action'],'new_review',result)
        self.assertEqual(result['code_equivalence'],'different')

    def test_rebase_equal_diff_with_changed_consumed_context_starts_review(self):
        self.archive()
        self.git('checkout','target')
        (self.repo/'consumer.py').write_text('consumer = 2\n')
        self.git('add','consumer.py'); self.git('commit','-m','upstream consumer')
        base=self.git('rev-parse','HEAD')
        self.git('checkout','feature'); self.git('rebase','target')
        result=self.assess(self.capture(dict(self.actual_scope,base=base,head=self.git('rev-parse','HEAD'))))
        self.assertEqual(result['code_equivalence'],'equivalent',result)
        self.assertEqual(result['action'],'new_review',result)
        self.assertEqual(result['applicability'],'changed')

    def test_new_material_note_starts_review_at_same_head(self):
        self.archive()
        data=b'new review claim'
        row=dict(key='note:17',purpose='notes',reference='evidence/notes.txt',sha256=hashlib.sha256(data).hexdigest())
        result=self.assess(self.capture(materials=[row],extra={'evidence/notes.txt':data}))
        self.assertEqual(result['code_equivalence'],'equivalent',result)
        self.assertEqual(result['action'],'new_review')

    def test_legacy_review_without_sidecars_can_prove_equal_trees(self):
        self.archive(guided=False)
        self.git('commit','--allow-empty','-m','rebuilt metadata')
        result=self.assess(self.capture(dict(self.actual_scope,head=self.git('rev-parse','HEAD'))))
        self.assertEqual(result['action'],'offer_choice',result)

    def test_open_review_is_not_reusable_or_mutated(self):
        run=self.archive(complete=False)
        before=(run/'cierre.json').read_bytes()
        result=self.assess()
        self.assertEqual(result['action'],'new_review',result)
        self.assertEqual((run/'cierre.json').read_bytes(),before)

    def test_explicit_incompatible_profile_starts_review(self):
        self.archive()
        capture=self.capture()
        capture['current_inputs']['profile']='deep'
        result=self.assess(capture)
        self.assertEqual(result['action'],'new_review',result)
        self.assertIn('profile_changed',{r['code'] for r in result['reasons']})

    def test_partial_complement_is_not_reused_as_ordinary_mr_review(self):
        self.archive(kind='complement')
        result=self.assess()
        self.assertEqual(result['action'],'new_review',result)
        self.assertIn('previous_scope_partial',{r['code'] for r in result['reasons']})

    def test_opaque_configuration_identity_change_starts_review(self):
        self.archive(identities={'configuration_identity':'deployment-A'})
        capture=self.capture()
        capture['current_inputs']['configuration_identity']='deployment-B'
        result=self.assess(capture)
        self.assertEqual(result['action'],'new_review',result)
        self.assertIn('material_identity_changed',{r['code'] for r in result['reasons']})

    def test_omitted_known_configuration_identity_is_not_equivalent(self):
        self.archive(identities={'configuration_identity':'deployment-A'})
        capture=self.capture()
        capture['current_inputs'].pop('configuration_identity')
        result=self.assess(capture)
        self.assertEqual(result['action'],'new_review',result)
        self.assertEqual(result['applicability'],'unknown')

    def pending_area(self, record, status='partial', material=True):
        record['coverage']['areas'][0].update(status=status,material=material,
            details='Required producer coverage remains pending')
        if material:
            record['verdict']='insufficient_evidence'

    def test_material_partial_area_requires_new_review(self):
        self.archive(final_update=self.pending_area)
        result=self.assess()
        self.assertEqual(result['action'],'new_review',result)

    def test_material_not_evaluated_area_requires_new_review(self):
        self.archive(final_update=lambda r:self.pending_area(r,'not_evaluated'))
        result=self.assess()
        self.assertEqual(result['action'],'new_review',result)

    def test_material_limitation_requires_new_review(self):
        def update(record):
            record['coverage']['limitations']=[dict(kind='validation',detail='Required check remains pending',
                material=True,public_summary=None)]
            record['verdict']='insufficient_evidence'
        self.archive(final_update=update)
        result=self.assess()
        self.assertEqual(result['action'],'new_review',result)

    def test_bounded_rereview_without_full_coverage_is_not_ordinary_review(self):
        self.archive(kind='rereview',final_update=lambda r:self.pending_area(r,'not_evaluated',False))
        result=self.assess()
        self.assertEqual(result['action'],'new_review',result)

    def test_full_rereview_remains_reusable(self):
        self.archive(kind='rereview')
        self.assertEqual(self.assess()['action'],'offer_choice')

    def test_nonmaterial_reservations_do_not_disqualify_complete_review(self):
        def update(record):
            record['coverage']['limitations']=[dict(kind='validation',detail='Optional platform not executed',
                material=False,public_summary=None)]
            record['reservations']=['Optional platform coverage remains limited']
            record['verdict']='approvable_with_reservations'
        self.archive(final_update=update)
        self.assertEqual(self.assess()['action'],'offer_choice')

    def blocker(self, record):
        row=finding(blocking=True)
        row['id']='F001'
        row['location']['path']='code.txt'
        record['findings']=[row]
        record['verdict']='not_approvable'

    def test_confirmed_blocker_alone_does_not_disqualify_complete_review(self):
        self.archive(final_update=self.blocker)
        self.assertEqual(self.assess()['action'],'offer_choice')

    def test_confirmed_blocker_does_not_hide_material_coverage_gap(self):
        def update(record):
            self.pending_area(record)
            self.blocker(record)
        self.archive(final_update=update)
        result=self.assess()
        self.assertEqual(result['action'],'new_review',result)

    def test_64_indexed_sources_plus_derived_context_remain_reusable(self):
        extra={f'evidence/source-{n:02}.txt':f'material {n}'.encode() for n in range(61)}
        rows=[dict(key=ref,purpose='other',reference=ref,sha256=hashlib.sha256(raw).hexdigest())
              for ref,raw in extra.items()]
        capture=self.capture(materials=rows,extra=extra)
        self.assertEqual(len(capture['current_sources']),64)
        run=self.archive(capture=capture)
        self.assertIn(CONTEXT,self.read(run/'cierre.json')['hashes'])
        result=self.assess(capture)
        self.assertEqual(result['action'],'offer_choice',result)


if __name__=='__main__':
    unittest.main()
