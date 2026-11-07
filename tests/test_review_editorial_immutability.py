"""Post-close publication operates beside full/compact archives, never in them."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from script_test_support import enable_package_imports

enable_package_imports()
from ccr.reporting import comment, render
from ccr.reporting.projections import publication_digest
from ccr.archive import compact
from ccr.execution.candidates import write_new_json
import test_review_archive_full13 as full13_tests
import test_review_compact_archive as compact_tests


def inventory(root):
    return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


class EditorialImmutabilityTests(unittest.TestCase):
    def test_closed_full_and_compact_archives_unchanged_on_success_and_failure(self):
        full = full13_tests.Full13ArchiveTests()
        self.addCleanup(full.doCleanups)
        case, full_run = full.complete_archive()
        helper = compact_tests.CompactPrepareTests()
        helper.setUp(); self.addCleanup(helper.doCleanups)
        prepared = helper.prepare()
        record, sources = helper.record_and_sources(prepared)
        result = compact.create_compact(prepared,record,render.render(record),helper.inputs,sources)
        compact_run = Path(result['run_dir'])
        for run in (full_run,compact_run):
            with self.subTest(run=run.name),tempfile.TemporaryDirectory() as directory:
                original = inventory(run)
                record = json.loads((run/'review.json').read_bytes())
                context = dict(schema_version=1,source_sha256=publication_digest(record),findings=[])
                coverage = dict(source_sha256=publication_digest(record),flows=[dict(index=i,summary=flow)
                                for i,flow in enumerate(record['coverage']['flows'])])
                from ccr.workflow.builders import build_check_disclosure
                from ccr.contracts.check_disclosure import input_identity_for
                from test_review_topology_integration import contexts12
                disclosure=build_check_disclosure(record,input_identity_for(record),{},{})
                kwargs=dict(**contexts12(record),check_disclosure_context=disclosure)
                with patch('subprocess.run',side_effect=AssertionError('publication executed a process')):
                    draft = comment.prepare_public_comment(record,finding_publication_context=context,
                                                           **kwargs)
                    self.assertTrue(comment.verify_public_comment(record,draft,draft['body'],check_disclosure_context=disclosure)['verified'])
                    with self.assertRaises(ValueError):
                        comment.prepare_public_comment(record,finding_publication_context=dict(context,source_sha256='0'*64),
                                                       **kwargs)
                    with self.assertRaises(ValueError):
                        comment.verify_public_comment(record,draft,draft['body']+' altered',check_disclosure_context=disclosure)
                    session = Path(directory); (session/'evidence').mkdir()
                    output=write_new_json(session,str(session/'evidence/public-comment.json'),draft)
                    previous=output.read_bytes()
                    with self.assertRaises(FileExistsError):
                        write_new_json(session,str(output),draft)
                    self.assertEqual(output.read_bytes(),previous)
                self.assertEqual(inventory(run),original)
