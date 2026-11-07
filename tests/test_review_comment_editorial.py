"""Draft4 binds the original result, editorial context and exact public body."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import contextlib
import io
from script_test_support import enable_package_imports

enable_package_imports()
from ccr.reporting import comment
from publication_fixtures import coverage_classification
from test_review_finding_publication import record_and_context


class EditorialCommentTests(unittest.TestCase):
    def prepare(self):
        record, context = record_and_context()
        draft = comment.prepare_public_comment(record, finding_publication_context=context,
            coverage_publication_context=coverage_classification(record))
        return record, context, draft

    def test_draft4_verifies_with_embedded_context_and_original_source(self):
        record, context, draft = self.prepare()
        self.assertEqual(draft['schema_version'], 4)
        self.assertEqual(draft['render_policy'], 'publication-editorial-v1')
        self.assertIsNone(draft['check_disclosure_context'])
        self.assertIn('Public second detail', draft['body'])
        self.assertTrue(comment.verify_public_comment(record,draft,draft['body'])['verified'])
        plain = comment.prepare_public_comment(record,coverage_publication_context=coverage_classification(record))
        self.assertEqual(plain['schema_version'],4)
        self.assertIsNone(plain['finding_publication_context'])
        self.assertIsNone(plain['finding_publication_sha256'])

    def test_tampering_fails_even_with_recomputed_body_hash(self):
        record, context, draft = self.prepare()
        before = copy.deepcopy(record)
        for field, value in [('render_policy','unknown'),('finding_publication_sha256','0'*64),
                             ('source_sha256','0'*64),('body',draft['body']+' edit'),('extra',True)]:
            bad = copy.deepcopy(draft);bad[field]=value
            bad['body_sha256']=hashlib.sha256(bad['body'].encode()).hexdigest()
            with self.subTest(field=field), self.assertRaises(ValueError):
                comment.verify_public_comment(record,bad,bad['body'])
        bad=copy.deepcopy(draft)
        bad['finding_publication_context']['findings'][0]['evidence'][0]['summary']='Changed'
        with self.assertRaises(ValueError):
            comment.verify_public_comment(record,bad,bad['body'])
        crlf=draft['body'].replace('\n','\r\n')
        with self.assertRaises(ValueError): comment.verify_public_comment(record,draft,crlf)
        self.assertTrue(comment.verify_public_comment(record,draft,crlf,remote=True)['verified'])
        self.assertEqual(record,before)

    def test_context_reader_rejects_duplicate_keys_nonfinite_and_oversized_input(self):
        from ccr.reporting.finding_publication import read_finding_publication_context
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'context.json'
            for raw in [b'{"schema_version":1,"schema_version":1}',b'{"x":NaN}',b' '* (256*1024+1),b'\xff',b'null',b'[]']:
                path.write_bytes(raw)
                with self.subTest(raw=raw[:30]),self.assertRaises(ValueError):
                    read_finding_publication_context(path)

    def test_cli_prepares_editorial_draft_and_refuses_invalid_modes_or_overwrite(self):
        from test_review_check_receipts import CaptureCheckTests
        from ccr.cli.comment import main as comment_main
        from ccr.cli.contract import main as contract_main
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve()
            _, workspace, _=CaptureCheckTests().make_workspace(root)
            evidence=Path(workspace['session_dir'])/'evidence'
            record,context=record_and_context()
            source=root/'review.json';source.write_text(json.dumps(record),encoding='utf-8')
            original=source.read_bytes()
            context_path=root/'editorial.json';context_path.write_text(json.dumps(context),encoding='utf-8')
            coverage=root/'coverage.json';coverage.write_text(json.dumps(coverage_classification(record)),encoding='utf-8')
            output=evidence/'new-comment.json'
            args=['prepare','--input',str(source),'--session',workspace['manifest'],'--output',str(output),
                  '--finding-publication-context',str(context_path),'--coverage-publication-context',str(coverage)]
            with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(comment_main(args),0)
                self.assertEqual(comment_main(args),2)
                body=json.loads(output.read_bytes())['body']
                outbound=root/'body.md';outbound.write_bytes(body.encode())
                self.assertEqual(comment_main(['verify','--input',str(source),'--draft',str(output),
                                               '--body',str(outbound)]),0)
                for mode in ('validate','render-user','render-handoff'):
                    self.assertEqual(contract_main([mode,'--input',str(source),
                        '--finding-publication-context',str(context_path)]),1)
                stream=io.StringIO()
                with contextlib.redirect_stdout(stream):
                    self.assertEqual(contract_main(['render-comment','--input',str(source),
                        '--finding-publication-context',str(context_path),'--coverage-publication-context',str(coverage)]),0)
                self.assertEqual(stream.getvalue(),body)
                context_path.write_bytes(b' '* (256*1024+1))
                bad_output=evidence/'oversized.json'
                bad_args=args.copy();bad_args[bad_args.index(str(output))]=str(bad_output)
                self.assertEqual(comment_main(bad_args),2)
                self.assertFalse(bad_output.exists())
            self.assertEqual(source.read_bytes(),original)
