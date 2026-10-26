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

    def archive(self,guided=True,complete=True,kind='review',identities=None):
        capture=self.capture()
        sources=copy.deepcopy(capture['current_sources'])
        inputs=copy.deepcopy(capture['current_inputs'])
        inputs.update(identities or {})
        if guided:
            files=collect_context_files(self.repo,capture['effective_changes']['comparison'],[
                dict(side='head',path_b64='Y29kZS50eHQ='),dict(side='head',path_b64='Y29uc3VtZXIucHk=')])
            context=build_review_context(self.actual_scope,files,[],
                logical_scope_identity=logical_scope(self.actual_scope)['identity'],complete=True,diagnostics=[])
            sources[CONTEXT]=json.dumps(context).encode()
        else:
            sources={'evidence/reference-index.json':json.dumps(dict(schema_version=1,aliases={},inputs=[])).encode()}
            inputs['sources']={k:hashlib.sha256(v).hexdigest() for k,v in sources.items()}
        run=Path(archive_tests.artifacts.prepare(self.repo,self.scope,'3.1.0','codex',
            output_root=self.output,profile_input=selection_input(),current_inputs=inputs))
        if complete:
            if kind!='review':
                final=self.read(self.final)
                final['presentation']['kind']=kind
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


if __name__=='__main__':
    unittest.main()
