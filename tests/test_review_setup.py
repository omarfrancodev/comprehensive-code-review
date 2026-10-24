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
from script_test_support import setup_api
setup = setup_api()
from ccr.workflow import builders
from ccr.archive import lifecycle as archive_lifecycle

from recovery_fixtures import context10, current_inputs, record10, selection_input


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
            with self.assertRaisesRegex(ValueError, 'not fully captured'):
                setup._validate_session_reference_index(
                    session, descriptor, captured, require_material=True)
            captured['sources']['evidence/description.md'] = material_hash
            self.assertEqual(setup._validate_session_reference_index(
                session, descriptor, captured, require_material=True), index)

            (evidence / 'description.md').write_bytes(b'changed description')
            with self.assertRaisesRegex(ValueError, 'invalid'):
                setup._validate_session_reference_index(session, descriptor, captured)

    def test_inputs_builder_pins_every_material_source_and_preserves_unknowns(self):
        scope = record10()['scope']
        description, notes = b'description-v1', b'notes-v1'
        index = {'schema_version': 1, 'aliases': {}, 'inputs': [
            {'reference': 'evidence/description.md', 'purpose': 'description',
             'sha256': hashlib.sha256(description).hexdigest()},
            {'reference': 'evidence/notes.json', 'purpose': 'notes',
             'sha256': hashlib.sha256(notes).hexdigest()}]}
        raw = json.dumps(index, sort_keys=True, separators=(',', ':')).encode()
        sources = {'evidence/description.md': description, 'evidence/notes.json': notes}
        description_hash = hashlib.sha256(description).hexdigest()

        result = builders.build_review_inputs(
            scope, raw, sources, source_set_complete=None,
            identities={'description_identity': description_hash})
        self.assertEqual(result['scope'], scope)
        self.assertEqual(result['sources'], {
            'evidence/reference-index.json': hashlib.sha256(raw).hexdigest(),
            'evidence/description.md': description_hash,
            'evidence/notes.json': hashlib.sha256(notes).hexdigest()})
        self.assertNotIn('source_set_complete', result)
        self.assertEqual(result['description_identity'], description_hash)
        self.assertNotIn('logical_scope_identity', result)
        with self.assertRaisesRegex(ValueError, 'description_identity'):
            builders.build_review_inputs(
                scope, raw, sources, source_set_complete=False,
                identities={'description_identity': '0' * 64})
        with self.assertRaisesRegex(ValueError, 'unsupported'):
            builders.build_review_inputs(
                scope, raw, sources, source_set_complete=True, identities={'profile': 'focused'})

    def test_input_builder_rejects_more_than_64_captured_sources(self):
        scope = record10()['scope']
        content = b'x'
        checksum = hashlib.sha256(content).hexdigest()
        index = {'schema_version': 1, 'aliases': {}, 'inputs': [
            {'reference': f'evidence/input-{number}.txt', 'purpose': 'other',
             'sha256': checksum} for number in range(64)]}
        raw = json.dumps(index, sort_keys=True, separators=(',', ':')).encode()
        sources = {row['reference']: content for row in index['inputs']}
        with self.assertRaisesRegex(ValueError, 'at most 64'):
            builders.build_review_inputs(scope, raw, sources,
                                         source_set_complete=True, identities={})

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

    def test_assignment_builder_preserves_late_identity_annotation_facts(self):
        assignment = record10('deep')['coverage']['execution']['plan'][0]
        source = 'evidence/dispatch.json#D1'
        raw = {'kind': 'dispatch-identity', 'status': 'unchanged',
               'summary': 'Observed identity for original dispatch; no new execution',
               'actor': {'kind': 'coordinator', 'name': 'coordinator', 'provider_id': None},
               'executor': {'name': 'worker-a', 'provider_id': None},
               'provenance': {'kind': 'recovered', 'source': source},
               'occurred_at': None,
               'evidence': [assignment['reference'], source],
               'relations': [{'relation': 'records', 'target': 'E000004'}]}

        event = setup.build_assignment_event(raw, assignment)

        self.assertEqual(event['actor'], raw['actor'])
        self.assertEqual(event['executor'], raw['executor'])
        self.assertEqual(event['occurred_at'], raw['occurred_at'])
        for mutation in (
                {'evidence': [source]},
                {'provenance': {'kind': 'recovered', 'source': None}},
                {'relations': []}):
            invalid = dict(raw, **mutation)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                setup.build_assignment_event(invalid, assignment)

    def test_documented_identity_annotation_builds_with_explicit_kind(self):
        import re

        root = Path(__file__).resolve().parents[1]
        assignment = record10('deep')['coverage']['execution']['plan'][0]
        for relative in ('references/archive/lifecycle-trace.md', 'docs/examples/archive8-lifecycle.md'):
            with self.subTest(document=relative):
                blocks = re.findall(r'```json\s*\n(.*?)\n```', (root / relative).read_text(encoding='utf-8'), re.S)
                annotations = [row for row in map(json.loads, blocks)
                               if isinstance(row, dict) and isinstance(row.get('provenance'), dict)
                               and row['provenance'].get('kind') == 'recovered']
                self.assertEqual(len(annotations), 1)
                self.assertEqual(annotations[0]['kind'], 'dispatch-identity')
                self.assertEqual(setup.build_assignment_event(annotations[0], assignment),
                                 dict(annotations[0], authority=None))
        for relative in ('SKILL.md', 'references/archive/artifacts.md', 'references/execution/worker-packets.md'):
            with self.subTest(document=relative):
                self.assertTrue('dispatch-identity/unchanged' in (root / relative).read_text(encoding='utf-8'), relative)

    def test_model_usage_update_links_private_sidecar_and_preserves_history(self):
        _, context, manifest, _, _ = fixture_context()
        original = copy.deepcopy(context)
        actor = {'kind': 'coordinator', 'name': 'coordinator', 'provider_id': None}
        linked, ledger = setup.build_model_usage_update(
            context, None, {'model': 'configured-coordinator'}, actor=actor,
            phase='discovery', activity='coordination', review_id='CR-' + 'a' * 20,
            harness_id='codex-desktop')
        self.assertEqual(context, original)
        self.assertEqual(linked['model_usage_reference'], 'evidence/model-usage.json')
        self.assertNotIn('model-usage', linked['review_inputs']['sources'])
        self.assertEqual(ledger['entries'][0]['status'], 'configured_only')

        updated, same_ledger = setup.build_model_usage_update(
            linked, ledger, {'model': 'configured-coordinator'}, actor=actor,
            phase='discovery', activity='coordination', review_id='CR-' + 'a' * 20,
            harness_id='codex-desktop')
        self.assertEqual(len(same_ledger['entries']), 1)
        self.assertEqual(updated['model_usage_reference'], linked['model_usage_reference'])

    def test_model_usage_capture_limits_add_bounded_nonblocking_diagnostics(self):
        context = {'existing': 'preserved'}
        linked, ledger = setup.build_model_usage_update(
            context, None, {'model': 'm' * 201},
            actor={'kind': 'coordinator', 'name': 'coordinator', 'provider_id': None},
            phase='report', activity='reporting', review_id='CR-' + 'a' * 20,
            harness_id=None)
        self.assertEqual(ledger, None)
        self.assertNotIn('model_usage_reference', linked)
        self.assertEqual(context, {'existing': 'preserved'})
        self.assertEqual(len(linked['model_usage_diagnostics']), 1)
        self.assertLessEqual(len(linked['model_usage_diagnostics'][0]), 500)


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

            workspace_helper = SCRIPTS
            result = run([sys.executable, str(workspace_helper), 'workspace', 'prepare', '--repo', str(repo), '--role', 'review'])
            self.assertEqual(result.returncode, 0, result.stderr)
            manifest = json.loads(result.stdout)
            session = Path(manifest['session_dir'])
            evidence = session / 'evidence'
            evidence.mkdir()
            input_file = root / 'input.json'
            input_file.write_text(json.dumps({'session': manifest['manifest'],
                                              'arguments': selection_input()}), encoding='utf-8')
            helper = SCRIPTS
            existing = evidence / 'profile-selection.json'
            existing.write_bytes(b'previous bytes')
            outside = root / 'outside.json'

            def snapshot():
                return {str(path.relative_to(session)): path.read_bytes()
                        for path in session.rglob('*') if path.is_file()}

            try:
                before = snapshot()
                collision = run([sys.executable, str(helper), 'setup', 'profile', '--input', str(input_file),
                                 '--output', str(existing)])
                self.assertNotEqual(collision.returncode, 0)
                self.assertEqual(snapshot(), before)

                escape = run([sys.executable, str(helper), 'setup', 'profile', '--input', str(input_file),
                              '--output', str(outside)])
                self.assertNotEqual(escape.returncode, 0)
                self.assertFalse(outside.exists())
                self.assertEqual(snapshot(), before)

                output = evidence / 'profile.json'
                success = run([sys.executable, str(helper), 'setup', 'profile', '--input', str(input_file),
                               '--output', str(output)])
                self.assertEqual(success.returncode, 0, success.stderr)
                self.assertEqual(json.loads(output.read_text(encoding='utf-8'))['profile'], 'focused')

                description, notes = b'description-v1', b'notes-v1'
                (evidence / 'description.md').write_bytes(description)
                (evidence / 'notes.json').write_bytes(notes)
                index = {'schema_version': 1, 'aliases': {}, 'inputs': [
                    {'reference': 'evidence/description.md', 'purpose': 'description',
                     'sha256': hashlib.sha256(description).hexdigest()},
                    {'reference': 'evidence/notes.json', 'purpose': 'notes',
                     'sha256': hashlib.sha256(notes).hexdigest()}]}
                index_bytes = json.dumps(index, sort_keys=True, separators=(',', ':')).encode()
                index_file = evidence / 'reference-index.json'
                index_file.write_bytes(index_bytes)
                descriptor = {'reference': 'evidence/reference-index.json',
                              'sha256': hashlib.sha256(index_bytes).hexdigest()}
                for complete in (True, False, None):
                    envelope = root / f'inputs-{complete}.json'
                    envelope.write_text(json.dumps({
                        'session': manifest['manifest'],
                        'arguments': {'scope': record10()['scope'],
                                      'reference_index': descriptor,
                                      'source_set_complete': complete,
                                      'identities': {'description_identity': hashlib.sha256(description).hexdigest()}}}),
                        encoding='utf-8')
                    candidate = evidence / f'inputs-{complete}.json'
                    result = run([sys.executable, str(helper), 'setup', 'inputs',
                                  '--input', str(envelope), '--output', str(candidate)])
                    self.assertEqual(result.returncode, 0, result.stderr)
                    value = json.loads(candidate.read_text(encoding='utf-8'))
                    self.assertEqual(set(value['sources']), {
                        'evidence/reference-index.json', 'evidence/description.md',
                        'evidence/notes.json'})
                    if complete is None:
                        self.assertNotIn('source_set_complete', value)
                    else:
                        self.assertIs(value['source_set_complete'], complete)

                duplicate = evidence / 'inputs-True.json'
                original_candidate = duplicate.read_bytes()
                collision = run([sys.executable, str(helper), 'setup', 'inputs',
                                 '--input', str(root / 'inputs-True.json'),
                                 '--output', str(duplicate)])
                self.assertNotEqual(collision.returncode, 0)
                self.assertEqual(duplicate.read_bytes(), original_candidate)

                outside_inputs = root / 'outside-inputs.json'
                escape = run([sys.executable, str(helper), 'setup', 'inputs',
                              '--input', str(root / 'inputs-True.json'),
                              '--output', str(outside_inputs)])
                self.assertNotEqual(escape.returncode, 0)
                self.assertFalse(outside_inputs.exists())

                invalid_envelope = root / 'inputs-invalid-identity.json'
                invalid_envelope.write_text(json.dumps({
                    'session': manifest['manifest'],
                    'arguments': {'scope': record10()['scope'], 'reference_index': descriptor,
                                  'source_set_complete': True, 'identities': {'unknown': 'x'}}}),
                    encoding='utf-8')
                invalid_output = evidence / 'inputs-invalid-identity.json'
                invalid = run([sys.executable, str(helper), 'setup', 'inputs',
                               '--input', str(invalid_envelope), '--output', str(invalid_output)])
                self.assertNotEqual(invalid.returncode, 0)
                self.assertFalse(invalid_output.exists())

                run_inputs = {'scope': record10()['scope'],
                              'sources': {'evidence/reference-index.json': descriptor['sha256']},
                              'source_set_complete': True}
                scope_file = root / 'scope.json'
                scope_file.write_text(json.dumps(record10()['scope']), encoding='utf-8')
                archive = Path(archive_lifecycle.prepare(
                    repo, scope_file, '3.0.0', 'codex', output_root=root / 'archives',
                    profile_input=selection_input(), current_inputs=run_inputs))
                archive_manifest = json.loads((archive / 'cierre.json').read_text(encoding='utf-8'))
                context_envelope = root / 'context-incomplete.json'
                context_envelope.write_text(json.dumps({
                    'session': manifest['manifest'],
                    'arguments': {'run_dir': str(archive),
                                  'execution_plan': archive_manifest['assignment_registry'],
                                  'executors': [], 'review_inputs': archive_manifest['review_inputs'],
                                  'reference_index': descriptor}}), encoding='utf-8')
                context_output = evidence / 'context-incomplete.json'
                archive_before = {str(path.relative_to(archive)): path.read_bytes()
                                  for path in archive.rglob('*') if path.is_file()}
                incomplete = run([sys.executable, str(helper), 'setup', 'context',
                                  '--input', str(context_envelope), '--output', str(context_output)])
                self.assertNotEqual(incomplete.returncode, 0)
                self.assertIn('not fully captured', incomplete.stderr)
                self.assertFalse(context_output.exists())
                self.assertEqual({str(path.relative_to(archive)): path.read_bytes()
                                  for path in archive.rglob('*') if path.is_file()}, archive_before)

                changed_envelope = root / 'inputs-changed.json'
                changed_envelope.write_text(envelope.read_text(encoding='utf-8'), encoding='utf-8')
                (evidence / 'notes.json').write_bytes(b'changed')
                changed_output = evidence / 'inputs-changed.json'
                changed = run([sys.executable, str(helper), 'setup', 'inputs',
                               '--input', str(changed_envelope), '--output', str(changed_output)])
                self.assertNotEqual(changed.returncode, 0)
                self.assertFalse(changed_output.exists())
            finally:
                cleanup = run([sys.executable, str(workspace_helper), 'workspace', 'cleanup',
                               '--manifest', manifest['manifest']])
                self.assertEqual(cleanup.returncode, 0, cleanup.stderr)


if __name__ == '__main__':
    unittest.main()
