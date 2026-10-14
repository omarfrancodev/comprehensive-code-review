"""Crash boundaries and bounded reads for review archive checkpoints."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import test_review_artifacts as archive

artifacts = archive.artifacts
SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))

from review_run_lock import run_locks


class AtomicRecoveryTests(unittest.TestCase):
    setUp = archive.ArchiveTests.setUp
    git = archive.ArchiveTests.git
    write = archive.ArchiveTests.write
    read = archive.ArchiveTests.read
    snapshot = archive.ArchiveTests.snapshot
    prepare7 = archive.Archive7Tests.prepare7
    profile_input = archive.Archive7Tests.profile_input

    def start_run(self):
        from test_review_checkpoints import CheckpointTests
        return CheckpointTests.start_run(self)

    def packet_files(self, profile='focused'):
        from test_review_checkpoints import CheckpointTests
        return CheckpointTests.packet_files(self, profile)

    def test_alias_83_conflicts_between_processes(self):
        if os.name != 'nt':
            self.skipTest('Windows 8.3 aliases are only available on Windows')
        with tempfile.TemporaryDirectory(prefix='ccr alias ') as directory:
            run = Path(directory) / 'review run'
            run.mkdir()
            ctypes = __import__('ctypes')
            buffer = ctypes.create_unicode_buffer(32768)
            length = ctypes.windll.kernel32.GetShortPathNameW(
                str(run), buffer, len(buffer))
            if not length or buffer.value.lower() == str(run).lower():
                self.skipTest('the host did not provide an 8.3 path for the test directory')
            alias = Path(buffer.value)
            code = (
                'import sys;sys.path.insert(0,' + repr(str(SCRIPTS)) + ');'
                'from pathlib import Path;from review_run_lock import run_locks;'
                'run=Path(' + repr(str(alias)) + ');'
                '\ntry:\n with run_locks([run]): print("acquired")\n'
                'except ValueError as exc:\n print("conflict" if "conflict" in str(exc) else str(exc))'
            )
            with run_locks([run]):
                result = subprocess.run([sys.executable, '-B', '-X', 'utf8', '-c', code],
                                        capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), 'conflict')

    def test_foreign_run_rejection_creates_no_locks(self):
        foreign = self.root / 'foreign-parent' / 'run'
        foreign.mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, 'foreign or incomplete'):
            artifacts.register(foreign, [])
        self.assertFalse((foreign.parent / '.review-locks').exists())

    def test_fsync_and_replace_failure_remove_owned_staging(self):
        for operation in ('fsync', 'replace'):
            with self.subTest(operation=operation):
                target = self.root / (operation + '.json')
                target.write_bytes(b'old bytes')
                with patch.object(artifacts.os, operation, side_effect=PermissionError(operation)):
                    with self.assertRaisesRegex(PermissionError, operation):
                        artifacts.atomic_write(target, b'new bytes')
                self.assertEqual(target.read_bytes(), b'old bytes')
                self.assertEqual(list(target.parent.glob('.' + target.name + '.*.tmp')), [])

    def test_crash_staging_recovery_requires_exact_intent(self):
        run, context = self.start_run()
        packets = self.packet_files()
        original = artifacts.atomic_write
        interrupted = False

        def leave_partial_stage(path, data, **kwargs):
            nonlocal interrupted
            target = Path(path)
            if not interrupted and target.name == 'context.json' and 'pending' in target.parts:
                interrupted = True
                stage = kwargs.get('staging_path')
                if stage is None:
                    stage = target.parent / '.context.json.unowned-crash.tmp'
                Path(stage).write_bytes(b'partial bytes')
                raise OSError('simulated process interruption')
            return original(path, data, **kwargs)

        with patch.object(artifacts, 'atomic_write', side_effect=leave_partial_stage):
            with self.assertRaisesRegex(OSError, 'simulated process interruption'):
                artifacts.checkpoint(run, context_input=context, evidence_inputs=packets,
                                     phase='discovery')
        manifest = self.read(run / 'cierre.json')
        transaction = manifest['checkpoint_transaction']
        self.assertIn('staging', transaction,
                      'checkpoint intent must declare the exact staging paths before writes')
        staged = transaction['staging']['pending/context.json']
        staging_path = run / staged['name']
        self.assertEqual(staging_path.read_bytes(), b'partial bytes')
        result = artifacts.checkpoint(run, context_input=context, evidence_inputs=packets,
                                      phase='discovery')
        self.assertEqual(result['id'], 'K001')
        self.assertFalse(staging_path.exists())
        self.assertIsNone(self.read(run / 'cierre.json').get('checkpoint_transaction'))

    def test_foreign_staging_pattern_is_preserved(self):
        run, context = self.start_run()
        artifacts.checkpoint(run, context_input=context, evidence_inputs=self.packet_files(),
                             phase='discovery')
        foreign = run / 'pending' / '.context.json.looks-owned.tmp'
        foreign.write_bytes(b'foreign bytes')
        with self.assertRaisesRegex(ValueError, 'foreign'):
            artifacts.validate(run)
        self.assertEqual(foreign.read_bytes(), b'foreign bytes')

    def test_casefold_collision_rejected_before_intent(self):
        run, context = self.start_run()
        first_dir, second_dir = self.root / 'case-a', self.root / 'case-b'
        first_dir.mkdir()
        second_dir.mkdir()
        first, second = first_dir / 'Brief.json', second_dir / 'brief.json'
        first.write_text('{}', encoding='utf-8')
        second.write_text('{"other":true}', encoding='utf-8')
        before = self.snapshot(run)
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            artifacts.checkpoint(run, context_input=context, evidence_inputs=[first, second],
                                 phase='discovery')
        self.assertEqual(self.snapshot(run), before)
        self.assertNotIn('checkpoint_transaction', self.read(run / 'cierre.json'))

    def test_checkpoint_input_size_checked_before_read(self):
        run, context = self.start_run()
        large = self.write('too-large-before-read.bin', {'value': 'x' * 100})
        original = Path.read_bytes

        def forbid_full_read(path):
            if Path(path) == large:
                raise AssertionError('oversized evidence was read before checking its size')
            return original(path)

        with patch.object(Path, 'read_bytes', autospec=True, side_effect=forbid_full_read):
            with self.assertRaisesRegex(ValueError, 'limit'):
                artifacts.checkpoint(run, context_input=context, evidence_inputs=[large],
                                     phase='discovery', max_evidence_bytes=8)

    def test_growing_input_cannot_exceed_read_budget(self):
        reader = getattr(artifacts, 'read_bounded', None)
        self.assertTrue(callable(reader), 'bounded input reader must exist')
        source = self.root / 'growing-input.bin'
        source.write_bytes(b'1234')
        original_open = Path.open
        grew = False

        def grow_after_stat(path, *args, **kwargs):
            nonlocal grew
            if Path(path) == source and not grew:
                grew = True
                with original_open(path, 'ab') as stream:
                    stream.write(b'56')
            return original_open(path, *args, **kwargs)

        with patch.object(Path, 'open', autospec=True, side_effect=grow_after_stat):
            with self.assertRaisesRegex(ValueError, 'limit'):
                reader(source, 4)


if __name__ == '__main__':
    unittest.main()
