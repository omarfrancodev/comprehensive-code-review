"""Owned-session builders preserve captured review facts and authority."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import review_setup as setup

from recovery_fixtures import context10, record10, selection_input


def fixture_context():
    record = record10()
    context = context10(record)
    sidecar = {'schema_version': 1, 'aliases': {}, 'inputs': []}
    sidecar_bytes = json.dumps(sidecar, sort_keys=True, separators=(',', ':')).encode('utf-8')
    import hashlib
    sidecar_hash = hashlib.sha256(sidecar_bytes).hexdigest()
    context['review_inputs']['sources']['evidence/reference-index.json'] = sidecar_hash
    manifest = {'schema_version': 8, 'layout_version': 2,
                'scope': record['scope'],
                'profile_history': copy.deepcopy(record['coverage']['execution']['profile_history']),
                'logical_scope': {'identity': context['review_inputs']['logical_scope_identity']},
                'assignment_registry': [], 'review_inputs': copy.deepcopy(context['review_inputs'])}
    return record, context, manifest, sidecar, sidecar_hash


class SetupTests(unittest.TestCase):
    def test_session_reference_index_verifies_captured_sidecar_and_material_bytes(self):
        with tempfile.TemporaryDirectory(prefix='review-setup-index-') as directory:
            session = Path(directory)
            evidence = session / 'evidence'
            evidence.mkdir()
            material = b'captured description'
            material_hash = hashlib.sha256(material).hexdigest()
            (evidence / 'description.md').write_bytes(material)
            index = {'schema_version': 1, 'aliases': {}, 'inputs': [
                {'reference': 'evidence/description.md', 'purpose': 'description',
                 'sha256': material_hash}]}
            index_bytes = json.dumps(index, sort_keys=True, separators=(',', ':')).encode('utf-8')
            (evidence / 'reference-index.json').write_bytes(index_bytes)
            descriptor = {'reference': 'evidence/reference-index.json',
                          'sha256': hashlib.sha256(index_bytes).hexdigest()}
            captured = {'sources': {'evidence/reference-index.json': descriptor['sha256']}}

            self.assertEqual(setup._validate_session_reference_index(
                session, descriptor, captured), index)

            (evidence / 'description.md').write_bytes(b'changed description')
            with self.assertRaisesRegex(ValueError, 'invalid'):
                setup._validate_session_reference_index(session, descriptor, captured)

    def test_authority_is_required_and_execution_facts_are_not_invented(self):
        explicit = selection_input(source='explicit')
        with self.assertRaises(ValueError):
            setup.build_profile_selection(dict(explicit, authority=None))
        self.assertEqual(setup.build_profile_selection(explicit)['authority'],
                         explicit['authority'])

        assignment = record10()['coverage']['execution']['plan'][0]
        event = setup.build_assignment_event({
            'kind': 'discovery', 'status': 'started', 'summary': 'Observed start',
            'actor': {'kind': 'coordinator', 'name': 'coordinator', 'provider_id': None},
            'occurred_at': None, 'evidence': [assignment['reference']]}, assignment)
        self.assertIsNone(event['actor']['provider_id'])
        self.assertIsNone(event['occurred_at'])
        self.assertEqual(event['evidence'], [assignment['reference']])

    def test_context_preserves_captured_values_and_registry(self):
        record, original_context, manifest, sidecar, sidecar_hash = fixture_context()
        original_manifest = copy.deepcopy(manifest)
        context = setup.build_context(
            manifest, execution_plan=record['coverage']['execution']['plan'],
            executors=[], review_inputs=manifest['review_inputs'],
            reference_index={'reference': 'evidence/reference-index.json', 'sha256': sidecar_hash})
        self.assertEqual(context['profile_history'], manifest['profile_history'])
        self.assertEqual(context['review_inputs'], manifest['review_inputs'])
        self.assertEqual(context['review_inputs']['logical_scope_identity'],
                         manifest['logical_scope']['identity'])
        self.assertEqual(context['reference_index'], 'evidence/reference-index.json')
        self.assertEqual(context['execution_plan'], record['coverage']['execution']['plan'])
        self.assertEqual(manifest, original_manifest)

    def test_context_rejects_changed_capture_or_uncaptured_index(self):
        record, _, manifest, _, sidecar_hash = fixture_context()
        changed = copy.deepcopy(manifest['review_inputs'])
        changed['description_identity'] = 'different-description'
        with self.assertRaisesRegex(ValueError, 'captured'):
            setup.build_context(manifest, execution_plan=[], executors=[],
                                review_inputs=changed,
                                reference_index={'reference': 'evidence/reference-index.json',
                                                 'sha256': sidecar_hash})
        with self.assertRaisesRegex(ValueError, 'captured'):
            setup.build_context(manifest, execution_plan=[], executors=[],
                                review_inputs=manifest['review_inputs'],
                                reference_index={'reference': 'evidence/reference-index.json',
                                                 'sha256': '0' * 64})

    def test_assignment_event_cannot_omit_or_change_its_brief(self):
        assignment = record10()['coverage']['execution']['plan'][0]
        raw = {'kind': 'discovery', 'status': 'started', 'summary': 'Observed start',
               'actor': {'kind': 'coordinator', 'name': 'coordinator', 'provider_id': None},
               'evidence': []}
        with self.assertRaisesRegex(ValueError, 'assignment'):
            setup.build_assignment_event(raw, assignment)
        raw['evidence'] = ['evidence/briefs.json#other']
        with self.assertRaisesRegex(ValueError, 'active required assignment brief'):
            setup.build_assignment_event(raw, assignment)


@unittest.skipUnless(shutil.which('git'), 'Git is required for owned-session CLI integration')
class SetupCliTests(unittest.TestCase):
    def test_cli_rejects_collision_and_escape_without_session_writes(self):
        with tempfile.TemporaryDirectory(prefix='review-setup-') as directory:
            root = Path(directory).resolve()
            repo = root / 'repo'
            repo.mkdir()
            env = os.environ.copy()
            for key in list(env):
                if key.upper().startswith('GIT_'):
                    del env[key]
            env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull,
                       GIT_CONFIG_NOSYSTEM='1', PYTHONUTF8='1')

            def run(command, cwd=root):
                return subprocess.run(command, cwd=cwd, env=env, capture_output=True,
                                      text=True, encoding='utf-8')

            for command in (['git', 'init', '-q'],
                            ['git', 'config', 'user.name', 'Fixture Reviewer'],
                            ['git', 'config', 'user.email', 'fixture@example.invalid']):
                result = run(command, cwd=repo)
                self.assertEqual(result.returncode, 0, result.stderr)
            (repo / 'product.py').write_text('answer = 42\n', encoding='utf-8')
            for command in (['git', 'add', 'product.py'], ['git', 'commit', '-qm', 'fixture baseline']):
                result = run(command, cwd=repo)
                self.assertEqual(result.returncode, 0, result.stderr)

            workspace_helper = SCRIPTS / 'review_workspace.py'
            result = run([sys.executable, str(workspace_helper), 'prepare', '--repo', str(repo), '--role', 'review'])
            self.assertEqual(result.returncode, 0, result.stderr)
            manifest = json.loads(result.stdout)
            session = Path(manifest['session_dir'])
            evidence = session / 'evidence'
            evidence.mkdir()
            input_file = root / 'input.json'
            input_file.write_text(json.dumps({'session': manifest['manifest'],
                                              'arguments': selection_input()}), encoding='utf-8')
            helper = SCRIPTS / 'review_setup.py'
            existing = evidence / 'profile-selection.json'
            existing.write_bytes(b'previous bytes')
            outside = root / 'outside.json'

            def snapshot():
                return {str(path.relative_to(session)): path.read_bytes()
                        for path in session.rglob('*') if path.is_file()}

            try:
                before = snapshot()
                collision = run([sys.executable, str(helper), 'profile', '--input', str(input_file),
                                 '--output', str(existing)])
                self.assertNotEqual(collision.returncode, 0)
                self.assertEqual(snapshot(), before)

                escape = run([sys.executable, str(helper), 'profile', '--input', str(input_file),
                              '--output', str(outside)])
                self.assertNotEqual(escape.returncode, 0)
                self.assertFalse(outside.exists())
                self.assertEqual(snapshot(), before)

                output = evidence / 'profile.json'
                success = run([sys.executable, str(helper), 'profile', '--input', str(input_file),
                               '--output', str(output)])
                self.assertEqual(success.returncode, 0, success.stderr)
                self.assertEqual(json.loads(output.read_text(encoding='utf-8'))['profile'], 'focused')
            finally:
                cleanup = run([sys.executable, str(workspace_helper), 'cleanup',
                               '--manifest', manifest['manifest']])
                self.assertEqual(cleanup.returncode, 0, cleanup.stderr)


if __name__ == '__main__':
    unittest.main()
