"""Check evidence layout and cleanup against the unchanged workspace safety guards."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


HELPER = Path(__file__).resolve().parents[1] / 'scripts' / 'review_workspace.py'


@unittest.skipUnless(shutil.which('git'), 'Git is required for workspace integration')
class WorkspaceLayoutTests(unittest.TestCase):
    def test_owned_evidence_and_registered_fixture_cleanup_preserve_main(self):
        with tempfile.TemporaryDirectory(prefix='review-layout-') as directory:
            repo = Path(directory).resolve()
            # Do not inherit or edit the user's identity, aliases, hooks or exclusions.
            env = os.environ.copy()
            for key in list(env):
                if key.startswith('GIT_'):
                    del env[key]
            env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull,
                       GIT_CONFIG_NOSYSTEM='1', PYTHONUTF8='1')

            def run(command, success=True):
                result = subprocess.run(command, cwd=repo, env=env, capture_output=True,
                                        text=True, encoding='utf-8')
                if success:
                    self.assertEqual(result.returncode, 0, result.stderr)
                return result

            run(['git', 'init', '-q'])
            run(['git', 'config', 'user.name', 'Fixture Reviewer'])
            run(['git', 'config', 'user.email', 'fixture@example.invalid'])
            product = repo / 'product.py'
            product.write_text('answer = 42\n', encoding='utf-8')
            run(['git', 'add', 'product.py'])
            run(['git', 'commit', '-qm', 'fixture baseline'])
            original = product.read_bytes()
            prefix = [sys.executable, '-B', str(HELPER)]
            manifest = json.loads(run(prefix + ['prepare', '--repo', str(repo), '--role', 'discovery']).stdout)
            session = Path(manifest['session_dir'])
            self.assertTrue(session.is_relative_to(repo / '.worktrees'))
            evidence = session / 'evidence'
            evidence.mkdir()
            for name in ('context.json', 'checks.json', 'discovery-discovery.json', 'verification.json'):
                (evidence / name).write_text('{}', encoding='utf-8')
            workspace = Path(manifest['workspaces'][0]['path'])
            fixture = workspace / 'reproduction.py'
            fixture.write_text('assert 42 == 42\n', encoding='utf-8')
            # A new unregistered file must stop cleanup and preserve all resources.
            refused = run(prefix + ['cleanup', '--manifest', manifest['manifest']], success=False)
            self.assertEqual(refused.returncode, 1)
            self.assertTrue(fixture.exists())
            self.assertTrue(session.exists())
            run(prefix + ['record-artifact', '--manifest', manifest['manifest'], '--path', str(fixture)])
            result = json.loads(run(prefix + ['cleanup', '--manifest', manifest['manifest']]).stdout)
            self.assertTrue(result['all_registered_removed'])
            self.assertFalse(result['main_changed'])
            self.assertFalse(session.exists())
            self.assertEqual(product.read_bytes(), original)
            self.assertEqual(len(result['remaining_worktrees']), 1)


if __name__ == '__main__':
    unittest.main()
