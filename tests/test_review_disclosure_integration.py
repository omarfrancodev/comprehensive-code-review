"""New-policy comment, handoff and portable delivery share one checked view."""
import copy
import json
import unittest
from script_test_support import enable_package_imports
enable_package_imports()
from test_review_check_disclosure import fixture, encoded
from test_review_topology_integration import contexts12
from ccr.workflow.builders import build_check_disclosure
from ccr.reporting import comment, render, delivery


def bundle():
    record, identity, observations, sources = fixture()
    disclosure = build_check_disclosure(record, identity, observations, sources)
    sources['evidence/check-disclosure.json'] = encoded(disclosure)
    return record, disclosure, sources


class DisclosureIntegrationTests(unittest.TestCase):
    def test_cleanup_rebinds_source_digest_without_reclassifying_checks(self):
        from ccr.archive.retention import rebind_disclosure_for_cleanup
        from ccr.contracts.check_disclosure import validate_check_disclosure
        record, disclosure, sources = bundle()
        next_record = copy.deepcopy(record)
        next_record['resources'].update(cleanup='complete', residuals=[])
        retained_context = dict(check_disclosure_reference='evidence/check-disclosure.json',
            check_disclosure_input_identity=disclosure['input_identity'])
        all_sources = dict(sources, **{'evidence/context.json': encoded(retained_context)})
        updated = rebind_disclosure_for_cleanup(record, next_record, retained_context, lambda name: all_sources[name])
        rebound = json.loads(updated['evidence/check-disclosure.json'])
        self.assertEqual(rebound['checks'], disclosure['checks'])
        self.assertEqual(validate_check_disclosure(next_record, rebound, sources, disclosure['input_identity']), [])
        next_record['checks'][0]['command'] = 'invented command'
        with self.assertRaisesRegex(ValueError, 'only cleanup'):
            rebind_disclosure_for_cleanup(record, next_record, retained_context, lambda name: all_sources[name])

    def test_setup_builds_sidecar_from_owned_selected_capture(self):
        import pathlib
        import tempfile
        import hashlib
        from test_review_check_receipts import CaptureCheckTests
        from ccr.workflow.setup import run_command
        record, identity, observations, sources = fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory).resolve()
            _, workspace, _ = CaptureCheckTests().make_workspace(root)
            session = pathlib.Path(workspace['session_dir'])
            evidence = session / 'evidence'; evidence.mkdir()
            selection = {}
            for reference, raw in sources.items():
                (session / reference).write_bytes(raw)
                selection[reference] = dict(reference=reference, sha256=hashlib.sha256(raw).hexdigest())
            request = root / 'request.json'
            request.write_bytes(encoded(dict(session=workspace['manifest'], arguments=dict(record=record,
                input_identity=identity, execution_observations=observations, sources=selection))))
            result = run_command('check-disclosure', request, str(evidence / 'check-disclosure.json'))
            actual = json.loads(pathlib.Path(result['output']).read_bytes())
            self.assertEqual(actual, build_check_disclosure(record, identity, observations, sources))
            self.assertEqual(actual['checks'][0]['id'], 'C001')
            self.assertEqual(actual['checks'][0]['command'], 'pytest tests/test_queue.py -k retry')
            self.assertEqual([item['path'] for item in actual['checks'][0]['resources']], ['tests/test_queue.py'])

    def test_delivery_receipt2_preserves_canonical_source(self):
        from test_review_topology_integration import TopologyIntegrationTests
        from profile_topology_fixtures import record12
        helper = TopologyIntegrationTests()
        case = helper.archive()
        self.addCleanup(case.doCleanups)
        run = case.prepare()
        helper.retain12(case, run, record12('focused', 'automatic', discovery=1))
        case.close(run)
        before = case.snapshot(run)
        for mode in ('full', 'brief'):
            target = delivery.deliver(run, mode, case.repo, case.root / mode)
            receipt = case.read(target / '.ccr-delivery.json')
            self.assertEqual(receipt['schema_version'], 2)
            self.assertEqual(receipt['projection_policy'], 'project-resources-v1')
            import hashlib
            self.assertEqual(receipt['check_disclosure_sha256'], hashlib.sha256((run / 'evidence/check-disclosure.json').read_bytes()).hexdigest())
            self.assertIsNone(receipt['model_usage_sha256'])
            text = (target / ('informe.md' if mode == 'full' else 'resumen.md')).read_text(encoding='utf-8')
            self.assertIn('Explicación del check', text)
        self.assertEqual(case.snapshot(run), before)

    def test_forged_sidecar_and_all_rehashed_sources_cannot_replace_initial_capture(self):
        from test_review_topology_integration import TopologyIntegrationTests
        from profile_topology_fixtures import record12
        from ccr.archive.retention import _execution_gate
        helper = TopologyIntegrationTests()
        case = helper.archive()
        self.addCleanup(case.doCleanups)
        run = case.prepare()
        helper.retain12(case, run, record12('focused', 'automatic', discovery=1))
        value = case.read(run / 'review.json')
        manifest = case.read(run / 'cierre.json')
        context = case.read(run / 'evidence/context.json')
        identity = dict(head=value['scope']['head'], snapshot=value['scope']['snapshot'], resource_manifest_sha256='a' * 64)
        context['check_disclosure_input_identity'] = identity
        forged = build_check_disclosure(value, identity, {}, {})
        contents = {'evidence/context.json': encoded(context), 'evidence/check-disclosure.json': encoded(forged)}
        with self.assertRaisesRegex(ValueError, 'not captured before review work'):
            _execution_gate(run, manifest, value, contents)

    def test_one_projection_for_comment_full_brief_handoff_json(self):
        record, disclosure, sources = bundle()
        kwargs = dict(check_disclosure_context=disclosure, check_disclosure_sources=sources)
        text = render.render(record, 'comment', **contexts12(record), **kwargs)
        self.assertIn('pytest tests/test_queue.py -k retry', text.replace('\\_', '_'))
        self.assertIn('Recursos del proyecto', text)
        self.assertNotIn('/private/home', text)
        handoff = render.render_handoff(record, audience='comment', **contexts12(record), **kwargs)
        self.assertIn('pytest tests/test_queue.py -k retry', handoff.replace('\\_', '_'))
        projection = delivery._Projection(record, {}, None, 'a' * 64, **kwargs)
        portable = projection.value(record)
        self.assertEqual(portable['checks'][0]['command'], 'pytest tests/test_queue.py -k retry')
        for text in (render.render_portable(portable, {}), delivery._brief(portable)):
            self.assertIn('pytest tests/test_queue.py -k retry', text.replace('\\_', '_'))

    def test_draft3_is_bound_to_disclosure_and_selected_sources(self):
        record, disclosure, sources = bundle()
        kwargs = dict(check_disclosure_context=disclosure, check_disclosure_sources=sources)
        draft = comment.prepare_public_comment(record, **contexts12(record), **kwargs)
        self.assertEqual(draft['schema_version'], 3)
        self.assertTrue(comment.verify_public_comment(record, draft, draft['body'], **kwargs)['verified'])
        with self.assertRaises(ValueError):
            comment.verify_public_comment(record, draft, draft['body'])
        changed = copy.deepcopy(sources)
        changed['evidence/execution.json'] = b'{}'
        with self.assertRaises(ValueError):
            comment.verify_public_comment(record, draft, draft['body'], check_disclosure_context=disclosure, check_disclosure_sources=changed)
        bad = copy.deepcopy(draft)
        bad['check_disclosure_context']['checks'][0]['command'] = 'other'
        with self.assertRaises(ValueError):
            comment.verify_public_comment(record, bad, bad['body'], **kwargs)

    def test_secrets_are_filtered_from_all_public_prose(self):
        from ccr.reporting.projections import publication_digest
        from test_review_check_disclosure import fixture
        record, identity, observations, sources = fixture(['python', 'tests/test_queue.py', '--token', 'SUPERSECRET'])
        record['verdict_reason'] += ' SUPERSECRET https://host.test/?token=SUPERSECRET'
        record['checks'][0]['evidence'] = 'SUPERSECRET /private/home/sensitive'
        disclosure = build_check_disclosure(record, identity, observations, sources)
        contexts = contexts12(record)
        contexts['check_publication_context']['checks'][0]['evidence'] = record['checks'][0]['evidence']
        text = render.render(record, 'comment', **contexts, check_disclosure_context=disclosure, check_disclosure_sources=sources)
        self.assertNotIn('SUPERSECRET', text)
        self.assertNotIn('/private/home', text)

    def test_fully_rehashed_self_asserted_snapshot_catalog_cannot_publish(self):
        record, identity, observations, sources = fixture()
        execution = json.loads(sources['evidence/execution.json'])
        for resource in execution['resources']:
            del resource['git_objects']
        sources['evidence/execution.json'] = encoded(execution)
        disclosure = build_check_disclosure(record, identity, observations, sources)
        with self.assertRaisesRegex(ValueError, 'independently registered initial input anchor'):
            render.render(record, 'comment', **contexts12(record),
                check_disclosure_context=disclosure, check_disclosure_sources=sources)

    def test_markdown_escaped_secrets_are_hidden_in_comment_and_handoff(self):
        for secret in ('secret_TOKEN', 'secret`TOKEN', 'secret[TOKEN]'):
            with self.subTest(secret=secret):
                record, identity, observations, sources = fixture(['python', 'tests/test_queue.py', '--token', secret])
                record['verdict_reason'] += ' observed ' + secret + ' in output'
                record['checks'][0]['evidence'] = 'Observed ' + secret
                disclosure = build_check_disclosure(record, identity, observations, sources)
                kwargs = dict(check_disclosure_context=disclosure, check_disclosure_sources=sources)
                contexts = contexts12(record)
                contexts['check_publication_context']['checks'][0]['evidence'] = 'Observed ' + secret
                from ccr.reporting.markdown import markdown_text
                comment_text = render.render(record, 'comment', **contexts, **kwargs)
                handoff = render.render_handoff(record, {'decisions_pending': ['Observed ' + secret]},
                    audience='comment', **contexts, **kwargs)
                for text in (comment_text, handoff):
                    self.assertNotIn(secret, text)
                    self.assertNotIn(markdown_text(secret), text)
                    self.assertIn('[omitido]', text)

    def test_selected_source_catalog_reads_only_explicit_hashed_files(self):
        import pathlib
        import tempfile
        import hashlib
        from ccr.execution.disclosure import read_selected_disclosure
        record, disclosure, sources = bundle()
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            sidecar = root / 'check-disclosure.json'; sidecar.write_bytes(encoded(disclosure))
            catalog = dict(input_identity=disclosure['input_identity'], sources={})
            for number, reference in enumerate(('evidence/execution.json', 'evidence/pinned-resources.json')):
                path = root / str(number); path.write_bytes(sources[reference])
                catalog['sources'][reference] = dict(path=str(path), sha256=hashlib.sha256(sources[reference]).hexdigest())
            selection = root / 'catalog.json'; selection.write_bytes(encoded(catalog))
            actual, selected = read_selected_disclosure(sidecar, selection)
            text = render.render(record, 'comment', **contexts12(record), check_disclosure_context=actual, check_disclosure_sources=selected)
            self.assertIn('tests/test\\_queue.py', text)
            catalog['sources']['evidence/execution.json']['sha256'] = '0' * 64
            selection.write_bytes(encoded(catalog))
            with self.assertRaisesRegex(ValueError, 'SHA-256 differs'):
                read_selected_disclosure(sidecar, selection)
