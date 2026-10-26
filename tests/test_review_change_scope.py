"""Git-backed equivalence, including history-only changes and moving targets."""
import copy
from contextlib import contextmanager
import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_review_effective_changes import b64, compare_effective_changes
from ccr.execution.change_scope import collect_effective_changes, collect_context_files, parse_raw
from ccr.execution import change_scope
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

    def test_user_diff_configuration_cannot_hide_gitlink(self):
        self.git('update-index','--add','--cacheinfo','160000',self.base,'module')
        self.git('commit','-m','module added')
        scope=dict(self.scope,head=self.git('rev-parse','HEAD'))
        expected=self.capture(scope)
        self.git('config','diff.ignoreSubmodules','all')
        self.git('config','diff.interHunkContext','100')
        actual=self.capture(scope)
        self.assertEqual(compare_effective_changes(expected,actual)['code_equivalence'],'equivalent')
        self.assertIn('gitlink',{r['kind'] for r in actual['entries']})

    def large_scope(self, before, after):
        for name in ('large.txt', 'copy.txt'):
            self.put(name, before)
        self.commit()
        base = self.git('rev-parse', 'HEAD')
        for name in ('large.txt', 'copy.txt'):
            self.put(name, after)
        self.commit()
        return dict(self.scope, base=base, head=self.git('rev-parse', 'HEAD')), base

    @contextmanager
    def observe_blob_reads(self):
        # Observe actual bytes crossing the Git adapter, without replacing Git data.
        original = change_scope.iter_git_bytes
        reads = []
        def observed(repo, *args):
            stream = original(repo, *args)
            row = None
            if args[:2] == ('cat-file', 'blob'):
                row = dict(oid=args[2], size=0, closed=False)
                reads.append(row)
            try:
                for chunk in stream:
                    if row is not None:
                        row['size'] += len(chunk)
                    yield chunk
            finally:
                stream.close()
                if row is not None:
                    row['closed'] = True
        with patch.object(change_scope, 'iter_git_bytes', side_effect=observed):
            yield reads

    def test_large_text_capture_reads_only_bounded_prefix_per_unique_blob(self):
        tail = b'line\n' * 400000
        scope, base = self.large_scope(b'first\n' + tail, b'changed\n' + tail)
        with self.observe_blob_reads() as reads:
            value = self.capture(scope, base)
        self.assertTrue(value['complete'], value['diagnostics'])
        self.assertEqual(len(value['entries']), 2)
        for row in value['entries']:
            self.assertEqual(row['kind'], 'text')
            self.assertEqual(row['payload'], {'patch_b64': b64(b'@@\n-first\n+changed\n line\n line\n line\n')})
        self.assertTrue(all(row['size'] <= 65536 for row in reads), reads)
        self.assertEqual(len(reads), 2, reads)
        self.assertTrue(all(row['closed'] for row in reads), reads)

    def test_duplicate_large_binary_blobs_are_fully_hashed_once(self):
        before, after = b'\0old' + b'z' * 2000000, b'\0new' + b'z' * 2000000
        scope, base = self.large_scope(before, after)
        with self.observe_blob_reads() as reads:
            value = self.capture(scope, base)
        self.assertTrue(value['complete'], value['diagnostics'])
        for row in value['entries']:
            self.assertEqual(row['kind'], 'binary')
            self.assertEqual(row['payload'], dict(old_sha256=hashlib.sha256(before).hexdigest(),
                new_sha256=hashlib.sha256(after).hexdigest()))
        self.assertEqual(sorted(row['size'] for row in reads), [len(before), len(after)])
        self.assertTrue(all(row['closed'] for row in reads), reads)

    def test_binary_transition_keeps_full_hash_of_text_counterpart(self):
        before = b'a' * 7999 + b'x' + b'tail\n' * 400000
        after = b'a' * 7999 + b'\0' + b'tail\n' * 400000
        scope, base = self.large_scope(before, after)
        with self.observe_blob_reads() as reads:
            value = self.capture(scope, base)
        self.assertTrue(value['complete'], value['diagnostics'])
        for row in value['entries']:
            self.assertEqual(row['kind'], 'binary')
            self.assertEqual(row['payload'], dict(old_sha256=hashlib.sha256(before).hexdigest(),
                new_sha256=hashlib.sha256(after).hexdigest()))
        self.assertLessEqual(sum(row['size'] for row in reads), len(before) + len(after) + 65536)
        self.assertTrue(all(row['closed'] for row in reads), reads)

    def test_context_shared_large_blob_is_hashed_once_per_capture(self):
        content = b'context\n' * 250000
        for name in ('shared.txt', 'duplicate.txt'):
            self.put(name, content)
        self.commit()
        base = self.git('rev-parse', 'HEAD')
        self.put('file.txt', b'changed again\n')
        self.commit()
        comparison = dict(diff_base=base, head=self.git('rev-parse', 'HEAD'))
        files = [dict(side=side, path_b64=b64(name))
            for side in ('base', 'head') for name in (b'shared.txt', b'duplicate.txt')]
        with self.observe_blob_reads() as reads:
            first = collect_context_files(self.repo, comparison, files)
            second = collect_context_files(self.repo, comparison, files)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 4)
        self.assertTrue(all(row['content_sha256'] == hashlib.sha256(content).hexdigest() for row in first))
        self.assertEqual([row['size'] for row in reads], [len(content), len(content)])
        self.assertTrue(all(row['closed'] for row in reads), reads)

    def test_nul_after_classification_prefix_still_uses_legacy_text_patch(self):
        before, after = b'a' * 8000 + b'\0old\n', b'a' * 8000 + b'\0new\n'
        scope, base = self.large_scope(before, after)
        value = self.capture(scope, base)
        self.assertTrue(value['complete'], value['diagnostics'])
        for row in value['entries']:
            self.assertEqual(row['kind'], 'text')
            self.assertEqual(row['payload'], {'patch_b64': b64(b'@@\n-' + before + b'+' + after)})

    def test_failed_binary_stream_closes_and_cannot_certify_partial_hash(self):
        scope, base = self.large_scope(b'\0before' + b'x' * 100000, b'\0after' + b'x' * 100000)
        original = change_scope.iter_git_bytes
        closed = []
        def interrupted(repo, *args):
            stream = original(repo, *args)
            try:
                for chunk in stream:
                    yield chunk
                    raise ValueError('interrupted blob read')
            finally:
                stream.close()
                closed.append(True)
        with patch.object(change_scope, 'iter_git_bytes', side_effect=interrupted):
            value = self.capture(scope, base)
        self.assertFalse(value['complete'])
        self.assertEqual(value['entries'], [])
        self.assertEqual(value['diagnostics'][0]['code'], 'capture_incomplete')
        self.assertTrue(closed)


if __name__ == '__main__':
    unittest.main()
