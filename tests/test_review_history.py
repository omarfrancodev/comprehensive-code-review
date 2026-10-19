"""Minimal historical consultation package tests using synthetic archives."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import review_artifacts as artifacts
import review_contract
import review_history
from recovery_fixtures import record10


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'archive'
        self.identity = 'origin:https://git.example/acme/service.git'
        repository_key = hashlib.sha256(self.identity.encode('utf-8')).hexdigest()[:20]
        self.run_id = '0123456789abcdefabcd'
        self.run = self.root / artifacts._repository_group(self.identity) / 'mr-1010-legacy' / ('20261018T150000-' + self.run_id)
        self.run.mkdir(parents=True)
        self.scope = {'repository': 'example/service', 'mode': 'mr', 'base': 'base-a',
                      'head': 'head-a', 'snapshot': None, 'target': 'develop',
                      'reference': 'https://git.example/acme/service/merge_requests/1010'}
        review = record10('focused', 'automatic')
        review['scope'] = self.scope
        review['review_id'] = 'CR-' + self.run_id
        review['description'] = {'status': 'aligned', 'identity': 'synthetic-description-id', 'details': 'Synthetic'}
        self.review_bytes = artifacts._json_bytes(review)
        self.report_bytes = review_contract.render(review).encode('utf-8')
        self.manifest = {'schema_version': 7, 'skill_version': '2.12.1', 'scope': self.scope,
                         'repository_identity': self.identity,
                         'repository_key': repository_key, 'archive_root': str(self.root),
                         'run_id': self.run_id, 'owner_id': 'a' * 32,
                         'created_at': '2026-10-18T15:00:00+00:00', 'state': 'complete',
                         'retained': True, 'cleanup': 'not_needed',
                         'hashes': {'review.json': hashlib.sha256(self.review_bytes).hexdigest(),
                                    'informe.md': hashlib.sha256(self.report_bytes).hexdigest()}}
        self.write('review.json', self.review_bytes)
        self.write('informe.md', self.report_bytes)
        self.write('cierre.json', artifacts._json_bytes(self.manifest))
        marker = {'owner_id': self.manifest['owner_id'], 'run_dir': str(self.run),
                  'archive_root': str(self.root), 'repository_key': self.manifest['repository_key'],
                  'scope_sha256': hashlib.sha256(artifacts._json_bytes(self.scope)).hexdigest(),
                  'manifest_sha256': hashlib.sha256(artifacts._json_bytes(self.manifest)).hexdigest()}
        self.write(artifacts.MARKER, artifacts._json_bytes(marker))

    def write(self, name, data):
        path = self.run / name
        path.write_bytes(data if isinstance(data, bytes) else data.encode('utf-8'))
        return path

    def snapshot(self, root=None):
        root = root or self.run
        return {str(path.relative_to(root)): path.read_bytes() for path in root.rglob('*') if path.is_file()}

    def test_port_contains_only_three_files_and_preserves_source_bytes(self):
        before = self.snapshot()
        destination_root = Path(self.temp.name) / 'history'
        result = review_history.port_review(self.run, destination_root)
        self.assertEqual(result['status'], 'created')
        self.assertEqual(Path(result['history_dir']).relative_to(destination_root).parts[0], '.historical')
        self.assertEqual(set(self.snapshot(Path(result['history_dir']))), {'informe.md', 'consulta.json', '.ccr-history.json'})
        self.assertEqual((Path(result['history_dir']) / 'informe.md').read_bytes(), self.report_bytes)
        self.assertEqual(self.snapshot(), before)

    def test_missing_or_changed_selected_bytes_are_not_ported(self):
        (self.run / 'informe.md').write_bytes(b'edited')
        with self.assertRaisesRegex(ValueError, 'hash'):
            review_history.port_review(self.run, Path(self.temp.name) / 'history')
        self.assertFalse((Path(self.temp.name) / 'history').exists())

    def test_pending_transaction_is_rejected_and_pending_cleanup_is_preserved(self):
        self.manifest['checkpoint_transaction'] = {'status': 'pending'}
        self.rewrite_manifest()
        with self.assertRaisesRegex(ValueError, 'pending'):
            review_history.port_review(self.run, Path(self.temp.name) / 'history')
        self.manifest.pop('checkpoint_transaction')
        self.manifest['cleanup'] = 'pending'
        self.rewrite_manifest()
        result = review_history.port_review(self.run, Path(self.temp.name) / 'history')
        consulta = json.loads((Path(result['history_dir']) / 'consulta.json').read_text(encoding='utf-8'))
        self.assertEqual(consulta['source']['cleanup'], 'pending')

    def rewrite_manifest(self):
        data = artifacts._json_bytes(self.manifest)
        (self.run / 'cierre.json').write_bytes(data)
        marker = json.loads((self.run / artifacts.MARKER).read_text(encoding='utf-8'))
        marker['manifest_sha256'] = hashlib.sha256(data).hexdigest()
        (self.run / artifacts.MARKER).write_bytes(artifacts._json_bytes(marker))

    def test_existing_port_is_verified_and_show_survives_source_removal(self):
        target = Path(self.temp.name) / 'history'
        first = review_history.port_review(self.run, target)
        second = review_history.port_review(self.run, target)
        self.assertEqual(second['status'], 'existing')
        source_report = review_history.show_history(first['history_dir'])
        self.assertIn('consulta histórica', source_report)
        self.run.rename(Path(self.temp.name) / 'source-removed')
        self.assertIn(self.report_bytes.decode('utf-8'), review_history.show_history(first['history_dir']))

    def test_destination_changes_are_never_overwritten(self):
        target = Path(self.temp.name) / 'history'
        first = review_history.port_review(self.run, target)
        report = Path(first['history_dir']) / 'informe.md'
        report.write_bytes(b'foreign')
        with self.assertRaisesRegex(ValueError, 'modified'):
            review_history.port_review(self.run, target)
        self.assertEqual(report.read_bytes(), b'foreign')

    def test_interrupted_staging_retry_is_idempotent(self):
        output = Path(self.temp.name) / 'history'
        first = review_history.port_review(self.run, output)
        destination = Path(first['history_dir'])
        stage = destination.parent / ('.staging-' + first['port_id'])
        destination.rename(stage)
        retried = review_history.port_review(self.run, output)
        self.assertEqual(retried['status'], 'created')
        self.assertEqual(retried['history_dir'], first['history_dir'])
        self.assertEqual(set(self.snapshot(destination)), {'informe.md', 'consulta.json', '.ccr-history.json'})

    def test_source_change_between_reads_blocks_publication(self):
        original = review_history._source_snapshot
        calls = 0
        def change_after_first(path):
            nonlocal calls
            value = original(path)
            calls += 1
            if calls == 1:
                (self.run / 'informe.md').write_bytes(b'concurrent change')
            return value
        with patch.object(review_history, '_source_snapshot', side_effect=change_after_first):
            with self.assertRaisesRegex(ValueError, 'hash'):
                review_history.port_review(self.run, Path(self.temp.name) / 'history')
        self.assertFalse((Path(self.temp.name) / 'history').exists())

    def test_tampered_ownership_or_package_inventory_is_rejected(self):
        marker = json.loads((self.run / artifacts.MARKER).read_text(encoding='utf-8'))
        marker['scope_sha256'] = 'f' * 64
        (self.run / artifacts.MARKER).write_bytes(artifacts._json_bytes(marker))
        with self.assertRaisesRegex(ValueError, 'ownership marker'):
            review_history.port_review(self.run, Path(self.temp.name) / 'history')

    def test_package_inventory_is_exact(self):
        target = Path(self.temp.name) / 'history'
        result = review_history.port_review(self.run, target)
        (Path(result['history_dir']) / 'extra.json').write_text('{}', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'inventory'):
            review_history.verify_history(result['history_dir'])


if __name__ == '__main__':
    unittest.main()
