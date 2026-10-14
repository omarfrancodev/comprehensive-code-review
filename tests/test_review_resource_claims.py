"""Resource ownership and transfer cannot cross review runs implicitly."""
import argparse
import copy
import json
from datetime import datetime, timezone
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
import review_recovery


class ResourceClaimTests(unittest.TestCase):
    setUp = archive.ArchiveTests.setUp
    git = archive.ArchiveTests.git
    write = archive.ArchiveTests.write
    read = archive.ArchiveTests.read
    snapshot = archive.ArchiveTests.snapshot
    prepare_legacy = archive.ArchiveTests.prepare
    profile_input = archive.Archive7Tests.profile_input

    def workspace_session(self):
        value = review_workspace.prepare(argparse.Namespace(
            repo=str(self.repo), ref='HEAD', mode='commit', role=['review'], include_untracked=[]))
        return Path(value['session_dir'])

    def create_run(self, temporary_paths=(), *, previous_run=None):
        path = artifacts.prepare(self.repo, self.scope, '2.12.0', 'codex', output_root=self.output,
                                 profile_input=self.profile_input(), temporary_paths=list(temporary_paths),
                                 previous_run=previous_run)
        return Path(path)

    def context(self, run, name):
        manifest = self.read(run / 'cierre.json')
        selection = manifest['profile_history'][0]
        return self.write(name, {'profile': selection['profile'],
                                 'selection_source': selection['selection_source'],
                                 'profile_reference': selection['reference'],
                                 'profile_history': manifest['profile_history'],
                                 'execution_plan': [], 'executors': []})

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

    def test_prepare_and_retain_refuse_foreign_claim_before_mutation(self):
        session = self.workspace_session()
        owner = self.create_run([session])
        self.register(owner, session, 'owner-context.json')
        before_session = self.snapshot(session)
        before_owner = self.snapshot(owner)
        before_runs = sorted(path.as_posix() for path in self.output.rglob('cierre.json'))
        with self.assertRaisesRegex(ValueError, 'already claimed|another review run|transfer-resources'):
            artifacts.prepare(self.repo, self.scope, '2.12.0', 'codex', output_root=self.output,
                profile_input=self.profile_input(), temporary_paths=[session])
        self.assertEqual(before_session, self.snapshot(session))
        self.assertEqual(before_owner, self.snapshot(owner))
        self.assertEqual(before_runs, sorted(path.as_posix() for path in self.output.rglob('cierre.json')))

        receiver = self.create_run()
        before_receiver = self.snapshot(receiver)
        with self.assertRaisesRegex(ValueError, 'already claimed|another review run|transfer-resources'):
            artifacts.retain(receiver, self.write('foreign-final.json', {}),
                              temporary_paths=[str(session)])
        self.assertEqual(before_session, self.snapshot(session))
        self.assertEqual(before_receiver, self.snapshot(receiver))

    def test_register_preflights_all_resources_before_claiming_any(self):
        bootstrap = self.workspace_session()
        foreign = self.workspace_session()
        owner = self.create_run([foreign])
        self.register(owner, foreign, 'owner-context.json')
        receiver = self.create_run()
        before = (self.snapshot(receiver), self.snapshot(bootstrap), self.snapshot(foreign))

        with self.assertRaisesRegex(ValueError, 'already claimed|another review run|transfer-resources'):
            artifacts.register(receiver, [str(bootstrap), str(foreign)],
                               context_input=self.context(receiver, 'receiver-context.json'))

        self.assertEqual(before, (self.snapshot(receiver), self.snapshot(bootstrap), self.snapshot(foreign)))
        self.assertEqual(self.read(bootstrap / claims.CLAIM_NAME)['status'], 'bootstrap')

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
        before_replay = (self.snapshot(source), self.snapshot(successor), self.snapshot(session))
        replay = artifacts.transfer_resources(source, successor, [str(session)],
            authority='User requested a restart; previous review will not continue', controller=self.controller())
        self.assertEqual(replay['transfer_id'], result['transfer_id'])
        self.assertEqual(before_replay, (self.snapshot(source), self.snapshot(successor), self.snapshot(session)))

    def test_cleanup_source_refuses_claim_transferred_to_successor(self):
        session = self.workspace_session()
        source = self.create_run([session])
        self.register(source, session, 'source-context.json')
        successor = self.create_run()
        artifacts.register(successor, [], context_input=self.context(successor, 'successor-context.json'))
        artifacts.transfer_resources(source, successor, [str(session)],
            authority='User authorized transfer', controller=self.controller())
        before = (self.snapshot(source), self.snapshot(successor), self.snapshot(session),
                  review_workspace.registrations(self.repo))

        with self.assertRaisesRegex(review_workspace.ReviewError, 'claim|owner|verification'):
            review_workspace.cleanup(argparse.Namespace(
                manifest=str(session / 'manifest.json'), run_dir=str(source)))

        self.assertEqual(before, (self.snapshot(source), self.snapshot(successor), self.snapshot(session),
                                  review_workspace.registrations(self.repo)))

    def test_register_after_incoming_transfer_is_idempotent(self):
        session = self.workspace_session()
        source = self.create_run([session])
        self.register(source, session, 'source-context.json')
        successor = self.create_run()
        artifacts.register(successor, [], context_input=self.context(successor, 'successor-context.json'))
        artifacts.transfer_resources(source, successor, [str(session)],
            authority='User authorized transfer', controller=self.controller())
        transfer_id = self.read(successor / 'cierre.json')['resource_transfers'][0]['transfer_id']

        manifest = self.register(successor, session, 'successor-replay-context.json')

        self.assertEqual(len(manifest['resource_claims']), 1)
        self.assertEqual(manifest['resource_claims'][0]['transfer_id'], transfer_id)
        self.assertEqual(claims.verify_claim(session, successor)['run_id'], manifest['run_id'])

    def test_second_outgoing_transfer_preserves_incoming_history(self):
        session = self.workspace_session()
        source = self.create_run([session])
        self.register(source, session, 'source-context.json')
        middle = self.create_run()
        artifacts.register(middle, [], context_input=self.context(middle, 'middle-context.json'))
        first = artifacts.transfer_resources(source, middle, [str(session)],
            authority='User authorized first transfer', controller=self.controller())
        middle_manifest = self.read(middle / 'cierre.json')
        incoming = middle_manifest.pop('resource_transfers')[0]
        middle_manifest['resource_transfer'] = incoming
        artifacts._save_manifest(middle, middle_manifest, self.read(middle / artifacts.MARKER))
        before_legacy_read = self.snapshot(middle)
        self.assertEqual(artifacts.normalize_transfer_history(self.read(middle / 'cierre.json')), [incoming])
        self.assertEqual(before_legacy_read, self.snapshot(middle))
        self.register(middle, session, 'middle-replay-context.json')
        successor = self.create_run()
        artifacts.register(successor, [], context_input=self.context(successor, 'successor-context.json'))

        second = artifacts.transfer_resources(middle, successor, [str(session)],
            authority='User authorized second transfer', controller=self.controller())

        self.assertNotEqual(first['transfer_id'], second['transfer_id'])
        history = self.read(middle / 'cierre.json')['resource_transfers']
        self.assertEqual([row['transfer_id'] for row in history],
                         [first['transfer_id'], second['transfer_id']])
        self.assertNotIn('resource_transfer', self.read(middle / 'cierre.json'))
        self.assertEqual(claims.verify_claim(session, successor)['run_id'],
                         self.read(successor / 'cierre.json')['run_id'])

    def test_partial_transfer_is_refused_without_mutation(self):
        first_session = self.workspace_session()
        second_session = self.workspace_session()
        source = self.create_run([first_session, second_session])
        self.register(source, first_session, 'first-context.json')
        self.register(source, second_session, 'second-context.json')
        successor = self.create_run()
        artifacts.register(successor, [], context_input=self.context(successor, 'successor-context.json'))
        before = (self.snapshot(source), self.snapshot(successor),
                  self.snapshot(first_session), self.snapshot(second_session))

        with self.assertRaisesRegex(ValueError, 'every active|partial|all active'):
            artifacts.transfer_resources(source, successor, [str(first_session)],
                authority='User requested a partial transfer', controller=self.controller())

        self.assertEqual(before, (self.snapshot(source), self.snapshot(successor),
                                  self.snapshot(first_session), self.snapshot(second_session)))

    def test_completed_transfer_changed_request_is_conflict(self):
        session = self.workspace_session()
        source = self.create_run([session])
        self.register(source, session, 'source-context.json')
        successor = self.create_run()
        artifacts.register(successor, [], context_input=self.context(successor, 'successor-context.json'))
        artifacts.transfer_resources(source, successor, [str(session)],
            authority='User authorized transfer', controller=self.controller())
        before = (self.snapshot(source), self.snapshot(successor), self.snapshot(session))

        with self.assertRaisesRegex(ValueError, 'request|inputs|transfer'):
            artifacts.transfer_resources(source, successor, [str(session)],
                authority='Different authority changes the request', controller=self.controller())

        self.assertEqual(before, (self.snapshot(source), self.snapshot(successor), self.snapshot(session)))

    def test_transfer_rejects_retaining_and_closing_runs(self):
        for state in ('retaining', 'closing'):
            with self.subTest(state=state):
                session = self.workspace_session()
                source = self.create_run([session])
                self.register(source, session, 'source-context.json')
                successor = self.create_run()
                artifacts.register(successor, [], context_input=self.context(successor, 'successor-context.json'))
                manifest = self.read(source / 'cierre.json')
                marker = self.read(source / artifacts.MARKER)
                manifest['state'] = state
                artifacts._save_manifest(source, manifest, marker)
                before = (self.snapshot(source), self.snapshot(successor), self.snapshot(session))

                with self.assertRaisesRegex(ValueError, 'retaining|closing|open'):
                    artifacts.transfer_resources(source, successor, [str(session)],
                        authority='User authorized transfer', controller=self.controller())

                self.assertEqual(before, (self.snapshot(source), self.snapshot(successor), self.snapshot(session)))

    def test_transfer_rejects_conflicting_previous_run(self):
        session = self.workspace_session()
        source = self.create_run([session])
        self.register(source, session, 'source-context.json')
        unrelated = self.create_run()
        successor = self.create_run(previous_run=unrelated)
        artifacts.register(successor, [], context_input=self.context(successor, 'successor-context.json'))
        before = (self.snapshot(source), self.snapshot(successor), self.snapshot(session))

        with self.assertRaisesRegex(ValueError, 'previous|lineage|source'):
            artifacts.transfer_resources(source, successor, [str(session)],
                authority='User authorized transfer', controller=self.controller())

        self.assertEqual(before, (self.snapshot(source), self.snapshot(successor), self.snapshot(session)))

    def test_transfer_history_limit_is_checked_before_mutation(self):
        session = self.workspace_session()
        source = self.create_run([session])
        self.register(source, session, 'source-context.json')
        successor = self.create_run()
        artifacts.register(successor, [], context_input=self.context(successor, 'successor-context.json'))
        manifest = self.read(source / 'cierre.json')
        marker = self.read(source / artifacts.MARKER)
        history = []
        for index in range(64):
            claim_id = 'RC-' + f'{index:032x}'
            transfer_id = 'RT-' + f'{index:032x}'
            new_claim = {'claim_id': claim_id}
            history.append({'schema_version': 1, 'transfer_id': transfer_id, 'status': 'complete',
                'source_run': str(self.root / f'old-source-{index}'),
                'successor_run': str(self.root / f'old-successor-{index}'),
                'source_run_id': f'{index + 1:020x}', 'successor_run_id': f'{index + 65:020x}',
                'source_owner_id': f'{index + 1:032x}', 'successor_owner_id': f'{index + 65:032x}',
                'repository_key': manifest['repository_key'], 'authority': 'Historical test transfer',
                'controller': self.controller(), 'completed_at': datetime.now(timezone.utc).isoformat(),
                'items': [{'session_dir': str(self.root / f'old-session-{index}'), 'claim_id': claim_id,
                           'old_claim_sha256': 'a' * 64, 'new_claim': new_claim,
                           'new_claim_sha256': artifacts._digest(claims._encoded(new_claim))}]})
        manifest['resource_transfers'] = history
        artifacts._save_manifest(source, manifest, marker)
        before = (self.snapshot(source), self.snapshot(successor), self.snapshot(session))

        with self.assertRaisesRegex(ValueError, '64|history|limit'):
            artifacts.transfer_resources(source, successor, [str(session)],
                authority='User authorized transfer', controller=self.controller())

        self.assertEqual(before, (self.snapshot(source), self.snapshot(successor), self.snapshot(session)))

    def test_legacy6_workspace_register_keeps_historical_fields(self):
        session = self.workspace_session()
        legacy = self.prepare_legacy()
        manifest = artifacts.register(legacy, [str(session)])

        self.assertEqual(manifest['schema_version'], 6)
        self.assertEqual(manifest['temporary_paths'], [str(session)])
        self.assertNotIn('resource_claims', manifest)
        self.assertNotIn('resource_transfers', manifest)
        self.assertNotIn('assignment_registry', manifest)
        self.assertNotIn('review_inputs', manifest)

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

    def test_cleanup_claim_requires_run_dir(self):
        session = self.workspace_session()
        owner = self.create_run([session])
        self.register(owner, session, 'owner-context.json')
        before = (self.snapshot(session), review_workspace.registrations(self.repo))

        with self.assertRaisesRegex(review_workspace.ReviewError, 'requires its owning --run-dir'):
            review_workspace.cleanup(argparse.Namespace(manifest=str(session / 'manifest.json')))

        self.assertTrue(session.exists())
        self.assertEqual(before, (self.snapshot(session), review_workspace.registrations(self.repo)))

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

    def test_released_receipt_replay_requires_exact_identity(self):
        session = self.workspace_session()
        run = self.create_run([session])
        self.register(run, session, 'context.json')
        manifest = self.read(run / 'cierre.json')
        claim = manifest['resource_claims'][0]
        receipt = {'session_id': claim['session_id'], 'run_id': manifest['run_id'],
                   'claim_id': claim['claim_id'], 'claim_sha256': claim['claim_sha256']}
        manifest['resource_claims'] = claims.validate_release_observation(manifest, [], [receipt])

        replay = claims.validate_release_observation(manifest, [], [receipt])

        self.assertEqual(replay, manifest['resource_claims'])
        altered = dict(receipt, claim_sha256='0' * 64)
        with self.assertRaisesRegex(ValueError, 'receipt|release'):
            claims.validate_release_observation(manifest, [], [altered])

    def test_archive7_with_pre_receipt_released_claim_remains_readable(self):
        session = self.workspace_session()
        run = self.create_run([session])
        self.register(run, session, 'legacy-release-context.json')
        manifest = self.read(run / 'cierre.json')
        claim = manifest['resource_claims'][0]
        shutil.rmtree(session)
        claim.update(status='released', released_by='review_workspace.cleanup',
                     release_claim_sha256=claim['claim_sha256'])
        manifest.pop('resource_cleanup')
        manifest.pop('cleanup_receipts')
        marker = self.read(run / artifacts.MARKER)
        artifacts._save_manifest(run, manifest, marker)

        loaded = artifacts._load_run(run)[1]
        replay = claims.validate_release_observation(loaded, [], [])

        self.assertEqual(replay, loaded['resource_claims'])

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

    def test_workspace_claim_diagnostic_becomes_invalid_preserve(self):
        session = self.workspace_session()
        run = self.create_run([session])
        self.register(run, session, 'claimed-context.json')

        with patch.object(review_workspace, 'load',
                          side_effect=review_workspace.ReviewError('owner marker is malformed')):
            inspected = review_recovery.inspect_run(run)
            with self.assertRaises(ValueError) as captured:
                claims._workspace(session)

        self.assertEqual(inspected['integrity']['status'], 'invalid')
        self.assertTrue(any(item['action'] == 'preserve' for item in inspected['actions']))
        self.assertIsInstance(captured.exception.__cause__, review_workspace.ReviewError)


if __name__ == '__main__':
    unittest.main()
