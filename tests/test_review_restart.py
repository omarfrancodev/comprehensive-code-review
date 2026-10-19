"""Pure restart request and intent contracts."""
import copy
from pathlib import Path
import sys
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))

import review_restart
import review_layout
from recovery_fixtures import selection_input


class ReviewRestartTests(unittest.TestCase):
    def request(self):
        return review_restart.normalize_restart_request(
            selection_input('deep', 'explicit'),
            {'identity': {'kind': 'coordinator', 'name': 'Restart owner', 'provider_id': 'codex'},
             'source': 'current session'},
            'User requested a fresh review',
            {'scope': {'repository': 'example/service', 'mode': 'commit', 'head': 'a' * 40,
                       'base': None, 'snapshot': None, 'target': None, 'reference': None},
             'sources': {}, 'source_set_complete': True},
            [],
            {'harness': 'Claude Code Desktop', 'harness_id': 'claude-code-desktop',
             'harness_source': {'kind': 'user', 'reference': '--harness-id'}})

    def source(self):
        return {'run_dir': 'C:/archive/source', 'run_id': 'a' * 20, 'owner_id': 'b' * 32,
                'repository_key': 'c' * 20, 'repository_path': 'C:/repo',
                'archive_root': 'C:/archive'}

    def successor(self):
        return {'run_dir': 'C:/archive/successor', 'run_id': 'd' * 20,
                'owner_id': 'e' * 32, 'reservation_id': 'f' * 32, 'created_at': '2026-10-14T12:00:00Z'}

    def test_normalize_restart_request_captures_current_harness(self):
        request = self.request()
        self.assertEqual(request['harness']['harness'], 'Claude Code Desktop')
        self.assertEqual(request['harness']['harness_id'], 'claude-code-desktop')
        self.assertEqual(request['harness']['harness_source']['kind'], 'user')

    def test_normalize_restart_request_captures_destination_logical_identity(self):
        request = self.request()
        self.assertEqual(request['current_inputs'].get('logical_scope_identity'),
                         review_layout.logical_scope(request['current_inputs']['scope'])['identity'])

    def test_intent_digest_is_stable_and_changes_with_scope(self):
        first = review_restart.build_restart_intent(self.source(), self.request(), self.successor())
        replay_source = dict(self.source(), updated_at='later')
        replay = review_restart.build_restart_intent(replay_source, self.request(), self.successor())
        self.assertEqual(first['request_sha256'], replay['request_sha256'])
        changed = copy.deepcopy(self.request())
        changed['current_inputs']['scope']['head'] = '9' * 40
        changed['current_inputs']['logical_scope_identity'] = review_layout.logical_scope(
            changed['current_inputs']['scope'])['identity']
        other = review_restart.build_restart_intent(self.source(), changed, self.successor())
        self.assertNotEqual(first['request_sha256'], other['request_sha256'])

    def test_validate_restart_intent_rejects_tampering(self):
        intent = review_restart.build_restart_intent(self.source(), self.request(), self.successor())
        self.assertEqual(review_restart.validate_restart_intent(intent), [])
        intent['successor']['run_dir'] = 'C:/foreign'
        self.assertTrue(review_restart.validate_restart_intent(intent))


if __name__ == '__main__':
    unittest.main()
