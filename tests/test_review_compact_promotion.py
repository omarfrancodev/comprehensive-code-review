import copy
import json
from pathlib import Path
import subprocess
import tempfile
import sys
import unittest
from unittest.mock import patch

from script_test_support import enable_package_imports
enable_package_imports()
from ccr.archive import compact, promotion, lifecycle
from ccr.shared.git import repository_identity
from recovery_fixtures import selection_input
from test_review_coverage13 import record13
from profile_topology_fixtures import source_fixture12
from ccr.reporting.render import render


class CompactPromotionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='promotion-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        subprocess.run(['git', 'init', '-q', str(self.repo)], check=True, capture_output=True)
        self.inputs = {'scope': record13()['scope'], 'sources': {}, 'source_set_complete': True}
        self.profile = selection_input('focused', 'explicit')
        self.prepared = compact.prepare_compact(self.root / 'archive', repository_identity(self.repo),
            self.inputs['scope'], None, self.inputs, {'mode': 'compact', 'reason': 'Acotado'}, 'source',
            profile_input=self.profile, skill_version='3.5.0', harness='codex')

    def promote(self, **kwargs):
        options = dict(repo=self.repo, prepared=self.prepared, current_inputs=self.inputs,
                       operation_id='promote-1', reason='Se requiere revisión independiente',
                       profile_input=self.profile, skill_version='3.5.0', harness='codex',
                       prepare_full=lifecycle.prepare)
        options.update(kwargs)
        return promotion.promote_compact(**options)

    def test_retry_reserves_exact_full_run_and_unchanged_source(self):
        result = self.promote()
        self.assertEqual(result, self.promote())
        self.assertTrue(Path(self.prepared['staging_dir']).exists())
        status = lifecycle.validate(result['run_dir'])
        self.assertFalse(status['retained'])
        manifest = json.loads((Path(result['run_dir']) / 'cierre.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['compact_promotion']['source_review_id'], self.prepared['review_id'])
        self.assertEqual(manifest['review_inputs'], self.prepared['request']['review_inputs'])
        with self.assertRaises(ValueError):
            lifecycle.validate(result['run_dir'], require_complete=True)

    def test_changed_input_or_same_operation_with_changed_reason_is_refused(self):
        result = self.promote()
        with self.assertRaises(ValueError):
            self.promote(reason='Diferente')
        changed = dict(self.inputs, requirements_identity='changed')
        with self.assertRaises(ValueError):
            self.promote(current_inputs=changed)
        self.assertTrue(Path(result['run_dir']).is_dir())

    def test_pinned_profile_is_checked_and_promotes_without_losing_it(self):
        inputs = dict(self.inputs, profile='focused')
        prepared = compact.prepare_compact(self.root / 'profile-archive', repository_identity(self.repo),
            inputs['scope'], None, inputs, {'mode': 'compact', 'reason': 'Acotado'}, 'profile-source',
            profile_input=self.profile, skill_version='3.5.0', harness='codex')
        result = self.promote(prepared=prepared, current_inputs=inputs)
        self.assertTrue(Path(result['run_dir']).is_dir())

    def test_interruption_after_intent_reuses_exact_reserved_destination(self):
        with patch('ccr.archive.lifecycle.prepare', side_effect=OSError('interrupted')):
            with self.assertRaises(OSError):
                self.promote()
        intent = json.loads((Path(self.prepared['staging_dir']) / 'promotion.json').read_text(encoding='utf-8'))
        result = self.promote()
        self.assertEqual(result['run_dir'], intent['successor']['run_dir'])

    def test_unpublished_compact_cannot_publish_after_promotion(self):
        self.promote()
        with self.assertRaisesRegex(ValueError, 'promoted'):
            compact.create_compact(self.prepared, {}, '', self.inputs, {})

    def test_published_compact_remains_immutable_and_linked(self):
        record = record13()
        record['review_id'] = self.prepared['review_id']
        record['coverage']['execution']['profile_history'][0] = copy.deepcopy(self.prepared['request']['profile_selection'])
        context, events, _ = source_fixture12(record)
        context['review_inputs'] = copy.deepcopy(self.prepared['request']['review_inputs'])
        execution = record['coverage']['execution']
        sources = {
            'evidence/context.json': json.dumps(context).encode(),
            'evidence/compact-execution.json': json.dumps(events).encode(),
            'evidence/briefs.json': json.dumps({row['id']: {'question': 'Revisar'} for row in execution['plan']}).encode(),
            'evidence/results.json': json.dumps({row['assignment_id']: {'result': 'Revisado'} for row in execution['results']}).encode(),
        }
        compact.create_compact(self.prepared, record, render(record), self.inputs, sources)
        before = (Path(self.prepared['run_dir']) / 'manifest.json').read_bytes()
        result = self.promote()
        self.assertEqual(result, self.promote())
        retried = compact.create_compact(self.prepared, record, render(record), self.inputs, sources)
        self.assertEqual(retried['run_dir'], self.prepared['run_dir'])
        self.assertEqual((Path(self.prepared['run_dir']) / 'manifest.json').read_bytes(), before)
        self.assertEqual(compact.read_compact(self.prepared['run_dir'])['record']['review_id'], self.prepared['review_id'])

    def test_abrupt_crash_during_initial_marker_is_recoverable(self):
        code = r"""
import json, os, sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / 'scripts'))
from ccr.archive import promotion, lifecycle, transactions
original = transactions.atomic_write
def crash(path, data, **kwargs):
    if path.name == '.review-ownership.json':
        staged = kwargs.get('staging_path') or path.parent / '.random-unrecoverable.tmp'
        with staged.open('xb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        os._exit(99)
    return original(path, data, **kwargs)
transactions.atomic_write = crash
options = json.loads(sys.argv[1])
promotion.promote_compact(**options, prepare_full=lifecycle.prepare)
"""
        options = dict(repo=str(self.repo), prepared=self.prepared, current_inputs=self.inputs,
                       operation_id='promote-1', reason='Se requiere revisión independiente',
                       profile_input=self.profile, skill_version='3.5.0', harness='codex')
        result = subprocess.run([sys.executable, '-B', '-c', code, json.dumps(options)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 99, result.stderr)
        intent = json.loads((Path(self.prepared['staging_dir']) / 'promotion.json').read_text(encoding='utf-8'))
        run = Path(intent['successor']['run_dir'])
        self.assertTrue(list(run.glob('*.tmp')))
        promoted = self.promote()
        self.assertEqual(promoted['run_dir'], str(run))
        self.assertEqual(list(run.glob('*.tmp')), [])
        self.assertFalse(lifecycle.validate(run)['retained'])
