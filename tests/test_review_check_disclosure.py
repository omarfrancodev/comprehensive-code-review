"""Selected input and execution bytes establish disclosure, never an origin label."""
import copy
import hashlib
import json
import shlex
import unittest
from script_test_support import enable_package_imports
enable_package_imports()
from profile_topology_fixtures import record12


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def fixture(argv=None, files=None):
    record = record12('focused', 'automatic', discovery=1)
    argv = argv or ['pytest', '/private/home/repo/tests/test_queue.py', '-k', 'retry']
    files = files or {'tests/test_queue.py': b'assert retry()\n'}
    check = record['checks'][0]
    check['command'] = shlex.join(argv)
    objects = {}
    def git_object(kind, raw):
        oid = hashlib.sha1(kind.encode() + b' ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        objects[oid] = dict(kind=kind, data=raw.hex())
        return oid
    tree = {}
    for path, data in files.items():
        node = tree
        for part in path.split('/')[:-1]: node = node.setdefault(part, {})
        node[path.split('/')[-1]] = git_object('blob', data)
    def tree_object(node):
        raw = b''
        for name, item in sorted(node.items()):
            kind = isinstance(item, dict)
            oid = tree_object(item) if kind else item
            raw += (b'40000' if kind else b'100644') + b' ' + name.encode() + b'\0' + bytes.fromhex(oid)
        return git_object('tree', raw)
    head = git_object('commit', b'tree ' + tree_object(tree).encode() + b'\n\nsynthetic pinned input\n')
    record['scope']['head'] = head
    check['revision'] = head
    identity = {'head': record['scope']['head'], 'snapshot': record['scope']['snapshot']}
    pinned = dict(identity, files={path: hashlib.sha256(data).hexdigest() for path, data in files.items()})
    identity['resource_manifest_sha256'] = hashlib.sha256(encoded(pinned)).hexdigest()
    execution = dict(check_id=check['id'], argv=argv, cwd='/private/home/repo',
                     revision=check['revision'], resources=[dict(path=path, executed_sha256=hashlib.sha256(data).hexdigest(), content=data.hex(), git_objects=objects) for path, data in files.items()])
    sources = {'evidence/pinned-resources.json': encoded(pinned), 'evidence/execution.json': encoded(execution)}
    observations = {check['id']: dict(execution_reference='evidence/execution.json',
        evidence_reference='evidence/pinned-resources.json', explanation='Se comprobó que el reintento conserva el identificador; resultado observado.')}
    return record, identity, observations, sources


class DisclosureTests(unittest.TestCase):
    def test_capture_uses_input_map_pinned_before_ccr_changes(self):
        import pathlib
        import sys
        import tempfile
        from test_review_check_receipts import CaptureCheckTests
        from ccr.execution import checks
        helper = CaptureCheckTests()
        with tempfile.TemporaryDirectory() as directory:
            _, manifest, cwd = helper.make_workspace(pathlib.Path(directory).resolve())
            self.assertIn('resource_baseline', manifest['workspaces'][0])
            pinned = manifest['workspaces'][0]['resource_baseline']
            self.assertIn('product.py', pinned['files'])
            (cwd / 'product.py').write_text('print("generated reproduction")\n')
            (cwd / 'generated.py').write_text('print("generated")\n')
            session = pathlib.Path(manifest['session_dir']); evidence = session / 'evidence'; evidence.mkdir()
            (evidence / 'context.json').write_text(json.dumps({'executors': [{'executor': 'X1', 'workspace': str(cwd)}]}))
            argv = [sys.executable, 'product.py']
            checks.capture_check(check_id='C001', purpose='Verify captured original resource identity', argv=argv,
                command=shlex.join(argv), cwd=str(cwd), executor_workspace=str(cwd), revision=manifest['head'],
                executor='X1', output_dir=str(evidence / 'attempt'))
            observation = json.loads((evidence / 'attempt' / 'attempt-C001-disclosure.json').read_bytes())
            self.assertNotEqual(observation['resources'][0]['executed_sha256'], pinned['files']['product.py'])
            self.assertEqual(json.loads((evidence / 'attempt' / 'attempt-C001-inputs.json').read_bytes()), pinned)

    def build(self, bundle):
        from ccr.workflow.builders import build_check_disclosure
        from ccr.reporting.check_disclosure import project_check_disclosure
        record, identity, observations, sources = bundle
        disclosure = build_check_disclosure(record, identity, observations, sources)
        view = project_check_disclosure(record, disclosure, sources, identity)
        return disclosure, view

    def test_original_project_command_is_selectively_visible(self):
        _, view = self.build(fixture())
        self.assertEqual(view['checks'][0]['command'], 'pytest tests/test_queue.py -k retry')
        self.assertEqual(view['checks'][0]['resources'], ['tests/test_queue.py'])
        self.assertNotIn('/private/home', json.dumps(view))

    def test_named_project_task_requires_original_manifest(self):
        _, view = self.build(fixture(['npm', 'test', '--', '--runInBand'], {'package.json': b'{"scripts":{"test":"jest"}}'}))
        self.assertEqual(view['checks'][0]['command'], 'npm test -- --runInBand')
        _, view = self.build(fixture(['npm', 'test'], {'package.json': b'{"scripts":{"build":"jest"}}'}))
        self.assertIsNone(view['checks'][0]['command'])

    def test_generated_entrypoint_and_opaque_shell_are_explained(self):
        for argv in (['python', '/private/session/repro.py'], ['bash', '-c', 'pytest tests/test_queue.py']):
            with self.subTest(argv=argv):
                _, view = self.build(fixture(argv))
                self.assertEqual(view['checks'][0]['mode'], 'explanation')
                self.assertIsNone(view['checks'][0]['command'])
                self.assertNotIn('repro.py', json.dumps(view))

    def test_mixed_check_and_secrets(self):
        argv = ['python', 'tests/test_queue.py', '--fixture', '/private/session/input.json', '--token', 'SUPERSECRET']
        _, view = self.build(fixture(argv))
        row = view['checks'][0]
        self.assertEqual(row['mode'], 'mixed')
        self.assertIn('tests/test_queue.py', row['command'])
        self.assertIn('[omitido]', row['command'])
        self.assertNotIn('SUPERSECRET', json.dumps(view))
        self.assertNotIn('input.json', json.dumps(view))

    def test_secret_repeated_in_project_resource_and_selector_is_redacted(self):
        _, view = self.build(fixture(['pytest', 'tests/SECRET_TEST.py', '-k', 'SECRET_TEST', '--token', 'SECRET_TEST'],
            {'tests/SECRET_TEST.py': b'assert retry()\n'}))
        self.assertNotIn('SECRET_TEST', json.dumps(view))

    def test_forged_origin_hash_or_changed_execution_is_rejected(self):
        from ccr.contracts.check_disclosure import validate_check_disclosure
        bundle = fixture()
        disclosure, _ = self.build(bundle)
        record, identity, _, sources = bundle
        for mutation in ('digest', 'source', 'argv', 'identity', 'resource'):
            bad, selected = copy.deepcopy(disclosure), dict(sources)
            if mutation == 'digest': bad['source_sha256'] = '0' * 64
            if mutation == 'source': selected['evidence/pinned-resources.json'] = b'{}'
            if mutation == 'argv':
                execution = json.loads(selected['evidence/execution.json']); execution['argv'][-1] = 'other'
                selected['evidence/execution.json'] = encoded(execution)
            if mutation == 'identity': bad['input_identity']['head'] = 'forged'
            if mutation == 'resource': bad['checks'][0]['resources'][0]['project_sha256'] = '0' * 64
            with self.subTest(mutation=mutation):
                self.assertTrue(validate_check_disclosure(record, bad, selected, identity))

    def test_traversal_external_and_sensitive_paths_are_not_original(self):
        for path in ('../tests/test_queue.py', '/outside/tests/test_queue.py', 'tests/../../secret.py'):
            _, view = self.build(fixture(['pytest', path]))
            self.assertIsNone(view['checks'][0]['command'])

    def test_unknown_is_explanation_and_preserves_real_check_id(self):
        record, identity, _, sources = fixture()
        _, view = self.build((record, identity, {}, sources))
        self.assertEqual(view['checks'][0]['id'], record['checks'][0]['id'])
        self.assertIsNone(view['checks'][0]['command'])

    def test_duplicate_resource_cannot_launder_forged_content_at_pinned_head(self):
        from ccr.workflow.builders import build_check_disclosure
        from ccr.reporting.check_disclosure import disclosure_view
        record, identity, observations, sources = fixture()
        execution = json.loads(sources['evidence/execution.json'])
        resource = execution['resources'][0]
        content = b'CCR generated file added after initial snapshot'
        resource.update(content=content.hex(), executed_sha256=hashlib.sha256(content).hexdigest())
        del resource['git_objects']
        pinned = json.loads(sources['evidence/pinned-resources.json'])
        pinned['files'][resource['path']] = resource['executed_sha256']
        sources['evidence/pinned-resources.json'] = encoded(pinned)
        identity['resource_manifest_sha256'] = hashlib.sha256(encoded(pinned)).hexdigest()
        decoy = copy.deepcopy(resource)
        decoy.update(executed_sha256='0' * 64, git_objects={'garbage': 'not authenticated'})
        execution['resources'].append(decoy)
        sources['evidence/execution.json'] = encoded(execution)
        with self.assertRaises(ValueError):
            disclosure = build_check_disclosure(record, identity, observations, sources)
            disclosure_view(record, disclosure, sources)

    def test_generated_dotnet_entrypoint_is_explained(self):
        _, view = self.build(fixture(['dotnet', 'repro.dll', 'tests/test_queue.py']))
        self.assertEqual(view['checks'][0]['mode'], 'explanation')
        self.assertIsNone(view['checks'][0]['command'])
        self.assertNotIn('repro.dll', json.dumps(view))

    def test_named_task_manifest_redirection_is_explained(self):
        for argv, files in ((['npm', 'test', '--prefix', '/private/ccr'], {'package.json': b'{"scripts":{"test":"jest"}}'}),
                            (['npm', '--workspace=private', 'test'], {'package.json': b'{"scripts":{"test":"jest"}}'}),
                            (['make', 'check', '-f', 'private.mk'], {'Makefile': b'check:\n\tpytest tests/test_queue.py\n'}),
                            (['make', 'check', '-C', '/private/ccr'], {'Makefile': b'check:\n\tpytest tests/test_queue.py\n'})):
            with self.subTest(argv=argv):
                _, view = self.build(fixture(argv, files))
                self.assertEqual(view['checks'][0]['mode'], 'explanation')
                self.assertIsNone(view['checks'][0]['command'])

    def test_bare_private_fixture_is_omitted_and_known_selector_preserved(self):
        _, view = self.build(fixture(['python', 'tests/test_queue.py', '-k', 'retry', '--fixture', 'private_input.json']))
        self.assertEqual(view['checks'][0]['mode'], 'mixed')
        self.assertNotIn('private_input.json', json.dumps(view))
        self.assertIn('-k retry', view['checks'][0]['command'])
        self.assertIn('tests/test_queue.py', view['checks'][0]['command'])
