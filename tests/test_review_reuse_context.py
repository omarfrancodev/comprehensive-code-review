"""Reusable context must cover real sources, not generated transport metadata."""
import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path
import unittest

from test_review_effective_changes import b64
from recovery_fixtures import record10
from ccr.archive.layout import logical_scope
from ccr.workflow.reuse import (
    build_material_map, build_review_context, compare_review_context, validate_material_map,
)
from ccr.workflow import setup
import test_review_change_scope as git_tests


def material_fixture():
    data = b'requirement'
    row = dict(key='requirement:1', purpose='requirements', reference='evidence/spec.md',
               sha256=hashlib.sha256(data).hexdigest())
    index = dict(schema_version=1, aliases={}, inputs=[{k:v for k,v in row.items() if k!='key'}])
    sources = {'evidence/spec.md': data, 'evidence/reference-index.json': json.dumps(index).encode()}
    return row, index, sources


def context_fixture(**updates):
    scope = record10()['scope']
    row, _, _ = material_fixture()
    args = dict(scope=scope, logical_scope_identity=logical_scope(scope)['identity'],
        files=[dict(side='head', path_b64=b64(b'consumer.py'), mode='100644', content_sha256='1'*64)],
        materials=[row], complete=True, diagnostics=[])
    args.update(updates)
    return build_review_context(**args)


class ReuseContextTests(unittest.TestCase):
    def test_changed_consumer_or_requirement_changes_applicability(self):
        old = context_fixture()
        for part, field, value in [('files','content_sha256','2'*64), ('materials','sha256','2'*64)]:
            new = copy.deepcopy(old)
            new[part][0][field] = value
            self.assertEqual(compare_review_context(old,new)['applicability'], 'changed')

    def test_absent_inventory_is_unknown(self):
        self.assertEqual(compare_review_context(None, context_fixture())['applicability'], 'unknown')
        self.assertEqual(compare_review_context(context_fixture(complete=False), context_fixture())['applicability'], 'unknown')

    def test_stable_material_keys_ignore_transport_names(self):
        old = context_fixture()
        new = copy.deepcopy(old)
        new['scope']['head'] = 'different-commit'
        new['materials'][0]['reference'] = 'evidence/renamed.md'
        self.assertEqual(compare_review_context(old,new)['applicability'], 'applicable')

    def test_optional_material_absence_differs_from_unknown(self):
        absent = dict(key='optional-spec', purpose='requirements', reference=None, sha256=None)
        old = context_fixture(materials=[absent])
        self.assertEqual(compare_review_context(old, old)['applicability'], 'applicable')
        self.assertEqual(compare_review_context(old, context_fixture(materials=[]))['applicability'], 'changed')

    def test_material_key_collision_is_rejected(self):
        row, _, _ = material_fixture()
        with self.assertRaises(ValueError):
            build_material_map([row,row],complete=True,diagnostics=[])

    def test_material_map_bootstrap_and_final_index_have_no_cycle(self):
        row, index, sources = material_fixture()
        value = build_material_map([row],complete=True,diagnostics=[])
        validate_material_map(value,index,sources)
        for path in ('evidence/reuse-materials.json','evidence/effective-changes.json'):
            sources[path] = b'generated'
            index['inputs'].append(dict(reference=path,purpose='other',sha256=hashlib.sha256(b'generated').hexdigest()))
        validate_material_map(value,index,sources)

    def test_unmapped_other_source_prevents_complete_materials(self):
        row, index, sources = material_fixture()
        sources['evidence/user-data.txt'] = b'data'
        index['inputs'].append(dict(reference='evidence/user-data.txt',purpose='other',sha256=hashlib.sha256(b'data').hexdigest()))
        with self.assertRaises(ValueError):
            validate_material_map(build_material_map([row],complete=True,diagnostics=[]),index,sources)

    def test_context_is_derived_from_pinned_objects_not_new_material(self):
        row,index,sources = material_fixture()
        changed = dict(row,sha256='a'*64)
        with self.assertRaises(ValueError):
            validate_material_map(build_material_map([changed],complete=True,diagnostics=[]),index,sources)
        with self.assertRaises(ValueError):
            context_fixture(files=[dict(side='head',path_b64=b64(b'../outside'),mode='100644',content_sha256='1'*64)])


class ReuseSetupTests(unittest.TestCase):
    setUp = git_tests.ChangeScopeTests.setUp
    git = git_tests.ChangeScopeTests.git
    put = git_tests.ChangeScopeTests.put
    commit = git_tests.ChangeScopeTests.commit

    def test_capture_descriptor_before_discovery_and_retain_it(self):
        scripts = Path(__file__).resolve().parents[1]/'scripts'
        run = subprocess.run([sys.executable,'-B',str(scripts),'workspace','prepare',
            '--repo',str(self.repo),'--role','review'],capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stderr)
        workspace = json.loads(run.stdout)
        session = Path(workspace['session_dir'])
        evidence = session/'evidence'
        evidence.mkdir()
        def build(command,args,name):
            envelope = self.repo/(command+'-input.json')
            envelope.write_text(json.dumps(dict(session=workspace['manifest'],arguments=args)))
            output = evidence/name
            setup.run_command(command,envelope,output)
            return json.loads(output.read_text())
        descriptor = build('changes',dict(repo=str(self.repo),scope=self.scope,target_head=self.base),
                           'effective-changes.json')
        self.assertTrue(descriptor['complete'])
        row,index,sources = material_fixture()
        for ref,raw in sources.items():
            (session/ref).write_bytes(raw)
        materials = build('materials',dict(materials=[row],complete=True,diagnostics=[],
            reference_index=dict(reference='evidence/reference-index.json',
                sha256=hashlib.sha256(sources['evidence/reference-index.json']).hexdigest())),
            'reuse-materials.json')
        self.assertTrue(materials['complete'])
        for filename in ('effective-changes.json','reuse-materials.json'):
            ref = 'evidence/'+filename
            index['inputs'].append(dict(reference=ref,purpose='other',
                sha256=hashlib.sha256((session/ref).read_bytes()).hexdigest()))
        raw = json.dumps(index).encode()
        (evidence/'reference-index.json').write_bytes(raw)
        inputs = build('inputs',dict(scope=self.scope,reference_index=dict(
            reference='evidence/reference-index.json',sha256=hashlib.sha256(raw).hexdigest()),
            source_set_complete=True,identities={}), 'current-inputs.json')
        self.assertIn('evidence/reuse-materials.json',inputs['sources'])
        before = (evidence/'effective-changes.json').read_bytes()
        with self.assertRaises(FileExistsError):
            build('changes',dict(repo=str(self.repo),scope=self.scope,target_head=self.base),'effective-changes.json')
        self.assertEqual((evidence/'effective-changes.json').read_bytes(),before)
        with self.assertRaises(ValueError):
            build('changes',dict(repo=str(self.repo),scope=self.scope,target_head=self.base),'../escape.json')

    def test_envelope_limits_preserve_legacy_bound(self):
        path = self.repo/'large-envelope.json'
        raw = json.dumps(dict(session='session',arguments={'padding':'x'*131073}))
        path.write_text(raw)
        with self.assertRaises(ValueError):
            setup._read_input(path)
        self.assertIsInstance(setup._read_input(path,max_bytes=64*1024*1024),dict)
        with path.open('w') as stream:
            stream.truncate(64*1024*1024+1)
        with self.assertRaises(ValueError):
            setup._read_input(path,max_bytes=64*1024*1024)

    def test_final_context_requires_real_claim_and_initial_materials(self):
        from ccr.archive.lifecycle import prepare,register
        from ccr.execution.change_scope import collect_effective_changes,collect_context_files
        from recovery_fixtures import selection_input
        from test_review_reuse_archive import current_sources
        scripts=Path(__file__).resolve().parents[1]/'scripts'
        run=subprocess.run([sys.executable,'-B',str(scripts),'workspace','prepare','--repo',str(self.repo),
                            '--role','review'],capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stderr)
        workspace=json.loads(run.stdout)
        session=Path(workspace['session_dir']); (session/'evidence').mkdir()
        descriptor=collect_effective_changes(self.repo,self.scope,target_head=self.base)
        inputs,materials,sources=current_sources(self.scope,descriptor)
        for ref,raw in sources.items(): (session/ref).write_bytes(raw)
        files=collect_context_files(self.repo,descriptor['comparison'],[dict(side='head',path_b64=b64(b'file.txt'))])
        args=dict(scope=self.scope,logical_scope_identity=descriptor['logical_scope_identity'],
                  files=files,materials=[],complete=True,diagnostics=[])
        envelope=self.repo/'context-envelope.json'
        def build():
            envelope.write_text(json.dumps(dict(session=workspace['manifest'],arguments=args)))
            return setup.run_command('reuse-context',envelope,session/'evidence/review-context.json')
        with self.assertRaises(ValueError): build()
        archive=prepare(self.repo,self.scope,'3.1.0','codex',output_root=self.repo/'archive',
                temporary_paths=[session],profile_input=selection_input(),current_inputs=inputs)
        manifest=json.loads((Path(archive)/'cierre.json').read_bytes())
        context=setup.build_context(manifest,execution_plan=[],executors=[],
            review_inputs=manifest['review_inputs'],reference_index=dict(reference='evidence/reference-index.json',
                sha256=inputs['sources']['evidence/reference-index.json']))
        context_path=session/'evidence/context.json'
        context_path.write_text(json.dumps(context))
        register(archive,[session],context_input=context_path)
        args['files'][0]['content_sha256']='f'*64
        with self.assertRaises(ValueError): build()
        args['files']=files=collect_context_files(self.repo,descriptor['comparison'],files)
        args['materials']=[dict(key='late',purpose='requirements',reference=None,sha256=None)]
        with self.assertRaises(ValueError): build()
        args['materials']=[]
        build()
        self.assertEqual(json.loads((session/'evidence/review-context.json').read_bytes())['files'],files)


if __name__ == '__main__':
    unittest.main()
