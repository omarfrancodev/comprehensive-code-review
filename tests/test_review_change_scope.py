"""Git-backed equivalence, including history-only changes and moving targets."""
import copy
import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_review_effective_changes import b64, compare_effective_changes
from ccr.execution.change_scope import collect_effective_changes, collect_context_files, parse_raw
from ccr.shared.git import git_bytes


class ChangeScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ccr-diff-')
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.git('init', '-b', 'main')
        self.git('config', 'user.name', 'Review Test')
        self.git('config', 'user.email', 'review@example.test')
        self.git('config', 'core.autocrlf', 'false')
        self.put('file.txt', b'one\ntwo\nthree\n')
        self.git('add', '.')
        self.git('commit', '-m', 'base')
        self.base = self.git('rev-parse', 'HEAD')
        self.git('checkout', '-b', 'feature')
        self.put('file.txt', b'one\nchanged\nthree\n')
        self.commit()
        self.scope = dict(repository='example/service', mode='mr', base=self.base,
            head=self.git('rev-parse', 'HEAD'), snapshot=None, target='main',
            reference='https://git.example/example/service/-/merge_requests/1')

    def git(self, *args, data=None):
        p = subprocess.run(['git', *args], cwd=self.repo, input=data,
                           capture_output=True, check=True)
        return p.stdout.decode('utf-8').strip()

    def put(self, name, data):
        path = self.repo / name
        path.parent.mkdir(exist_ok=True, parents=True)
        path.write_bytes(data)

    def commit(self):
        self.git('add', '.')
        self.git('commit', '-m', 'change')

    def capture(self, scope=None, target=None):
        return collect_effective_changes(self.repo, scope or self.scope,
                                         target_head=target or self.base)

    def test_empty_commit_is_equivalent(self):
        old = self.capture()
        before = self.git('status', '--porcelain')
        self.git('commit', '--allow-empty', '-m', 'empty')
        new = self.capture(dict(self.scope, head=self.git('rev-parse', 'HEAD')))
        self.assertEqual(compare_effective_changes(old, new)['code_equivalence'], 'equivalent')
        self.assertEqual(self.git('status', '--porcelain'), before)

    def test_no_change_merge_is_equivalent(self):
        old = self.capture()
        self.git('checkout', 'main')
        self.git('commit', '--allow-empty', '-m', 'target metadata')
        target = self.git('rev-parse', 'HEAD')
        self.git('checkout', 'feature')
        self.git('merge', '--no-ff', 'main', '-m', 'merge empty')
        new = self.capture(dict(self.scope, head=self.git('rev-parse', 'HEAD'), base=target), target)
        self.assertEqual(compare_effective_changes(old, new)['code_equivalence'], 'equivalent')

    def test_rebase_with_equivalent_change_is_equivalent(self):
        old = self.capture()
        self.git('checkout', 'main')
        self.put('unrelated.txt', b'upstream\n')
        self.commit()
        target = self.git('rev-parse', 'HEAD')
        self.git('checkout', 'feature')
        self.git('rebase', 'main')
        new = self.capture(dict(self.scope, head=self.git('rev-parse', 'HEAD'), base=target), target)
        self.assertEqual(compare_effective_changes(old, new)['code_equivalence'], 'equivalent')

    def test_new_content_and_edit_of_reviewed_file_are_different(self):
        old = self.capture()
        self.put('file.txt', b'one\nnew change\nthree\n')
        self.commit()
        new = self.capture(dict(self.scope, head=self.git('rev-parse', 'HEAD')))
        self.assertEqual(compare_effective_changes(old, new)['code_equivalence'], 'different')

    def test_target_advance_changes_effective_diff_at_same_head(self):
        self.put('second.txt', b'new\n')
        self.commit()
        head = self.git('rev-parse', 'HEAD')
        old = self.capture(dict(self.scope, head=head))
        new = self.capture(dict(self.scope, head=head, base=self.scope['head']), self.scope['head'])
        self.assertEqual(compare_effective_changes(old, new)['code_equivalence'], 'different')

    def test_shifted_hunk_keeps_identity_but_changed_context_does_not(self):
        # Enough unchanged lines to put upstream edits outside the hunk context.
        self.git('checkout', 'main')
        lines = b''.join(f'{n}\n'.encode() for n in range(30))
        self.put('file.txt', lines)
        self.commit()
        base = self.git('rev-parse', 'HEAD')
        self.git('checkout', '-b', 'shift')
        self.put('file.txt', lines.replace(b'20\n', b'changed\n'))
        self.commit()
        old = self.capture(dict(self.scope, base=base, head=self.git('rev-parse', 'HEAD')), base)
        self.git('checkout', 'main')
        self.put('file.txt', b'prefix\n' + lines)
        self.commit()
        target = self.git('rev-parse', 'HEAD')
        self.git('checkout', 'shift')
        self.git('rebase', 'main')
        new = self.capture(dict(self.scope, base=target, head=self.git('rev-parse', 'HEAD')), target)
        self.assertEqual(compare_effective_changes(old, new)['code_equivalence'], 'equivalent')
        self.put('file.txt', (b'prefix\n' + lines).replace(b'19\n', b'context\n').replace(b'20\n', b'changed\n'))
        self.commit()
        changed = self.capture(dict(self.scope, base=target, head=self.git('rev-parse', 'HEAD')), target)
        self.assertEqual(compare_effective_changes(new, changed)['code_equivalence'], 'different')

    def test_binary_mode_symlink_gitlink_and_rename(self):
        self.put('binary.dat', b'\0binary\xff')
        blob = self.git('hash-object', '-w', '--stdin', data=b'file.txt')
        self.git('update-index', '--add', '--cacheinfo', '120000', blob, 'link')
        self.git('update-index', '--add', '--cacheinfo', '160000', self.base, 'module')
        self.git('add', 'binary.dat')
        self.git('update-index', '--chmod=+x', 'file.txt')
        self.git('commit', '-m', 'typed objects')
        value = self.capture(dict(self.scope, head=self.git('rev-parse', 'HEAD')))
        self.assertEqual({row['kind'] for row in value['entries']}, {'text','binary','symlink','gitlink'})
        self.assertIn('100755', {r['new_mode'] for r in value['entries']})
        self.git('mv', 'file.txt', 'renamed.txt')
        self.git('commit', '-m', 'rename')
        new = self.capture(dict(self.scope, head=self.git('rev-parse', 'HEAD')))
        self.assertTrue(any(r['old_path_b64'] == b64(b'file.txt') and r['new_path_b64'] is None for r in new['entries']))

    def test_significant_whitespace_and_missing_newline(self):
        old = self.capture()
        for data in (b'one\nchanged \nthree\n', b'one\nchanged\nthree', b'one\r\nchanged\r\nthree\r\n'):
            self.put('file.txt', data)
            self.commit()
            self.assertEqual(compare_effective_changes(old, self.capture(dict(self.scope,
                head=self.git('rev-parse', 'HEAD'))))['code_equivalence'], 'different')

    def test_nul_paths_and_external_diff_are_safe(self):
        raw = b':100644 100644 ' + b'1'*40 + b' ' + b'2'*40 + b' M\0odd\tname\n\xff\0'
        self.assertEqual(parse_raw(raw)[0]['path'], b'odd\tname\n\xff')
        self.put('literal [x].txt', b'hello\n')
        self.commit()
        self.git('config', 'diff.external', 'this-command-must-never-run')
        value = self.capture(dict(self.scope, head=self.git('rev-parse', 'HEAD')))
        self.assertTrue(value['complete'])
        self.assertEqual(len(value['entries']), 2)

    def test_missing_objects_multiple_bases_and_limits_never_equal(self):
        missing = self.capture(dict(self.scope, head='a'*40))
        self.assertFalse(missing['complete'])
        with patch('ccr.execution.change_scope.MAX_ENTRIES', 0):
            self.assertFalse(self.capture()['complete'])
        with patch('ccr.execution.change_scope.git', wraps=__import__('ccr.shared.git', fromlist=['git']).git) as query:
            original = query._mock_wraps
            query.side_effect = lambda repo, *args, **kw: (self.base + '\n' + 'a'*40
                if args[:2] == ('merge-base', '--all') else original(repo, *args, **kw))
            self.assertFalse(self.capture()['complete'])
        with self.assertRaises(ValueError):
            git_bytes(self.repo, 'show', self.scope['head']+':file.txt', max_output_bytes=1)

    def test_context_files_use_pinned_trees(self):
        value = self.capture()
        rows = collect_context_files(self.repo, value['comparison'],
            [{'side':'head', 'path_b64':b64(b'file.txt')}])
        self.assertEqual(rows[0]['content_sha256'], hashlib.sha256(b'one\nchanged\nthree\n').hexdigest())


if __name__ == '__main__':
    unittest.main()
