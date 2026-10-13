"""Resource ownership and transfer cannot cross review runs implicitly."""
import argparse
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from unittest.mock import patch

import test_review_artifacts as archive

artifacts = archive.artifacts
SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))

import review_workspace
import review_resource_claims as claims


class ResourceClaimTests(unittest.TestCase):
    setUp = archive.ArchiveTests.setUp
    git = archive.ArchiveTests.git
    write = archive.ArchiveTests.write
    read = archive.ArchiveTests.read
    snapshot = archive.ArchiveTests.snapshot
    profile_input = archive.Archive7Tests.profile_input

    def workspace_session(self):
        value = review_workspace.prepare(argparse.Namespace(
            repo=str(self.repo), ref='HEAD', mode='commit', role=['review'], include_untracked=[]))
        return Path(value['session_dir'])

    def create_run(self, temporary_paths=()):
        path = artifacts.prepare(self.repo, self.scope, '2.12.0', 'codex', output_root=self.output,
                                 profile_input=self.profile_input(), temporary_paths=list(temporary_paths))
        return Path(path)

    def context(self, run, name):
        manifest = self.read(run / 'cierre.json')
        selection = manifest['profile_history'][0]
        return self.write(name, {'profile': selection['profile'],
                                 'selection_source': selection['selection_source'],
                                 'profile_reference': selection['reference'],
                                 'profile_history': manifest['profile_history'], 'executors': []})

    def register(self, run, session, name):
        return artifacts.register(run, [str(session)], context_input=self.context(run, name))

    def controller(self):
        return {'identity': {'kind': 'coordinator', 'name': 'test coordinator', 'provider_id': None},
                'source': 'synthetic transfer test'}

    def test_duplicate_resource_claim_is_refused_without_mutation(self):
        session = self.workspace_session()
        source = self.create_run([session])
        self.register(source, session, 'source-context.json')
        successor = self.create_run()
        before = (self.snapshot(source), self.snapshot(successor), self.snapshot(session))

        with self.assertRaisesRegex(ValueError, 'already claimed|different review'):
            self.register(successor, session, 'successor-context.json')

        self.assertEqual(before, (self.snapshot(source), self.snapshot(successor), self.snapshot(session)))

    def test_transfer_records_both_runs_and_rebinds_claim(self):
        session = self.workspace_session()
        source = self.create_run([session])
        self.register(source, session, 'source-context.json')
        successor = self.create_run()
        context = self.context(successor, 'successor-context.json')
        artifacts.register(successor, [], context_input=context)

        result = artifacts.transfer_resources(source, successor, [str(session)],
            authority='User requested a restart; previous review will not continue', controller=self.controller())

        self.assertEqual(result['status'], 'transferred')
        self.assertEqual(claims.verify_claim(session, successor)['run_id'], self.read(successor / 'cierre.json')['run_id'])
        with self.assertRaisesRegex(ValueError, 'claim|owner'):
            claims.verify_claim(session, source)
        old = self.read(source / 'cierre.json')
        new = self.read(successor / 'cierre.json')
        self.assertEqual(old['operation']['disposition'], 'superseded')
        self.assertEqual(old['operation']['successor'], str(successor))
        self.assertEqual(new['resource_claims'][0]['status'], 'owned')

    def test_transfer_crash_boundaries_are_recoverable(self):
        original = artifacts.atomic_write
        for timing in ('before', 'after'):
            with self.subTest(timing=timing):
                session = self.workspace_session()
                source = self.create_run([session])
                self.register(source, session, 'source-context.json')
                successor = self.create_run()
                artifacts.register(successor, [], context_input=self.context(successor, 'successor-context.json'))
                interrupted = False

                def fail_once(path, data):
                    nonlocal interrupted
                    if not interrupted and Path(path).name == '.review-run-owner.json':
                        interrupted = True
                        if timing == 'after':
                            original(path, data)
                        raise OSError('injected claim transfer interruption')
                    original(path, data)

                args = (source, successor, [str(session)])
                kwargs = {'authority': 'User authorized transfer after stopping the source run',
                          'controller': self.controller()}
                with patch.object(artifacts, 'atomic_write', side_effect=fail_once), self.assertRaises(OSError):
                    artifacts.transfer_resources(*args, **kwargs)
                result = artifacts.transfer_resources(*args, **kwargs)
                self.assertEqual(result['status'], 'transferred')
                self.assertEqual(claims.verify_claim(session, successor)['run_id'],
                                 self.read(successor / 'cierre.json')['run_id'])
                events = [json.loads(row) for row in (source / 'trazabilidad.jsonl').read_text(encoding='utf-8').splitlines()]
                self.assertEqual(sum(event['kind'] == 'handoff' for event in events), 1)

    def test_workspace_cleanup_refuses_a_different_run_claim(self):
        session = self.workspace_session()
        owner = self.create_run([session])
        self.register(owner, session, 'owner-context.json')
        other = self.create_run()
        manifest = review_workspace.load(session / 'manifest.json')
        before = self.snapshot(session)
        registered = review_workspace.registrations(self.repo)

        with self.assertRaisesRegex(review_workspace.ReviewError, 'claim|owner|run'):
            review_workspace.cleanup(argparse.Namespace(manifest=str(session / 'manifest.json'), run_dir=str(other)))

        self.assertEqual(before, self.snapshot(session))
        self.assertEqual(registered, review_workspace.registrations(self.repo))

    def test_missing_resource_does_not_prove_own_cleanup(self):
        session = self.workspace_session()
        run = self.create_run([session])
        self.register(run, session, 'context.json')
        manifest = self.read(run / 'cierre.json')
        claim = manifest['resource_claims'][0]
        shutil.rmtree(session)

        with self.assertRaisesRegex(ValueError, 'release|cleanup|claim'):
            claims.validate_release_observation(manifest, [], [])
        receipt = {'session_id': claim['session_id'], 'run_id': manifest['run_id'],
                   'claim_id': claim['claim_id'], 'claim_sha256': claim['claim_sha256']}
        released = claims.validate_release_observation(manifest, [], [receipt])
        self.assertEqual(released[0]['status'], 'released')

    def test_legacy_session_adoption_requires_authority(self):
        session = self.workspace_session()
        (session / claims.CLAIM_NAME).unlink()
        run = self.create_run([session])
        manifest = self.read(run / 'cierre.json')

        with self.assertRaisesRegex(ValueError, 'authority|adoption'):
            claims.plan_claim(session, run, manifest)
        planned = claims.plan_claim(session, run, manifest,
                                    authority='User explicitly authorized adoption of this legacy review session')
        self.assertEqual(planned['action'], 'adopt')

    def test_claim_reparse_or_foreign_owner_preserves_files(self):
        session = self.workspace_session()
        run = self.create_run([session])
        owner = self.read(session / '.owner.json')
        owner['owner_token'] = 'f' * 32
        (session / '.owner.json').write_text(json.dumps(owner), encoding='utf-8')
        before = self.snapshot(session)
        with self.assertRaises((ValueError, review_workspace.ReviewError)):
            self.register(run, session, 'context.json')
        self.assertEqual(before, self.snapshot(session))
        self.assertEqual(self.read(run / 'cierre.json')['resource_claims'], [])


if __name__ == '__main__':
    unittest.main()
