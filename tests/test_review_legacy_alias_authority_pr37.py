"""Historical aliases preserve claim continuity and the original authority."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import unittest

from script_test_support import run_cli
from test_review_assessment import NOTE, PROOF, assessed, followup, guided_current, rendered, source
from test_review_assessment_lineage import following, root_v2
import test_review_compact_archive as compact_fixtures
from ccr.archive import compact
from ccr.archive.assessment import read_followup_baseline
from ccr.contracts import review
from ccr.contracts.assessment import verify_sources
from ccr.contracts.check_disclosure import input_identity_for
from ccr.reporting.render import render
from ccr.reporting.text_projection import _Projection
from ccr.shared.encoding import archive_bytes
from ccr.shared.git import repository_identity
from ccr.workflow.builders import build_check_disclosure


def authorization(previous, identifier, member, decision):
    return dict(id=identifier, member_id=member, review_id=previous['review_id'],
                scope={key: previous['scope'][key] for key in ('base', 'head', 'snapshot')},
                decision=copy.deepcopy(decision))


def adopt_v1(previous):
    current, sources = followup(previous)
    assessment = current['assessment']
    resolution = assessment['findings'][0]['resolution']
    grant = authorization(previous, 'AU001', 'F001', resolution)
    resolution['authorization_id'] = 'AU001'
    assessment.update(schema_version=3, history_incomplete=False, authorizations=[grant],
        observed_hashes=sorted({assessment['previous']['source']['sha256'],
                                assessment['scope']['delta'][0]['sources'][0]['sha256'],
                                resolution['source']['sha256']}),
        lineage=[dict(id='F001', cause='duplicate-delivery', survivor='F001',
                      title=current['findings'][0]['title'], last_status='confirmed',
                      resolution=copy.deepcopy(resolution))]
                 + [dict(id=alias, cause=None, survivor='F001', title=None, last_status='confirmed',
                         resolution=copy.deepcopy(resolution)) for alias in previous['aliases']])
    return current, sources


def v2_alias_copy(previous):
    record, sources = adopt_v1(previous)
    assessment = record['assessment']
    assessment['schema_version'] = 2
    assessment.pop('authorizations')
    assessment.pop('history_incomplete')
    for row in assessment['lineage'] + assessment['findings']:
        row['resolution'].pop('authorization_id')
    return record, sources


def adopt_v2_copy(previous, original, *, select_history):
    record, sources = following(previous, 'c')
    assessment = record['assessment']
    decision = assessment['findings'][0]['resolution']
    baseline = original if select_history else previous
    assessment.update(schema_version=3, history_incomplete=True,
        authorizations=[authorization(baseline, 'AU001', 'F001', decision)])
    for row in assessment['findings'] + assessment['lineage']:
        row['resolution']['authorization_id'] = 'AU001'
    if select_history:
        raw = archive_bytes(original)
        assessment['previous']['legacy_source'] = source('legacy.json', raw)
        sources['evidence/legacy.json'] = raw
    return record, sources


class LegacyAliasAuthorityTests(unittest.TestCase):
    def test_v2_inherited_alias_uses_the_grant_in_its_selected_predecessor(self):
        original = assessed()
        original['aliases'] = {'F002': 'F001'}
        previous, previous_sources = v2_alias_copy(original)
        verify_sources(previous, previous_sources.__getitem__)
        current, sources = adopt_v2_copy(previous, original, select_history=True)
        self.assertEqual(review.validate(current), [])
        verify_sources(current, sources.__getitem__, captured_inputs={'sources': {}})
        self.assertEqual(rendered(current, 'user').count('Writes stay disabled'), 1)
        later, sources = following(current, 'd')
        verify_sources(later, sources.__getitem__, captured_inputs={'sources': {}})
        self.assertEqual(later['assessment']['authorizations'], current['assessment']['authorizations'])

    def test_missing_v2_provenance_does_not_create_an_alias_grant(self):
        original = assessed()
        original['aliases'] = {'F002': 'F001'}
        previous, _ = v2_alias_copy(original)
        current, sources = adopt_v2_copy(previous, original, select_history=False)
        self.assertEqual(review.validate(current), [])
        verify_sources(current, sources.__getitem__, captured_inputs={'sources': {}})
        self.assertTrue(current['assessment']['history_incomplete'])
        self.assertEqual(rendered(current, 'user').count('Writes stay disabled'), 1)

    def test_v2_provenance_has_to_match_the_previous_record_commitment(self):
        original = assessed()
        original['aliases'] = {'F002': 'F001'}
        previous, _ = v2_alias_copy(original)
        current, sources = adopt_v2_copy(previous, original, select_history=True)
        changed = copy.deepcopy(original)
        changed['description']['reason'] = 'Different predecessor bytes'
        raw = archive_bytes(changed)
        current['assessment']['previous']['legacy_source'] = source('legacy.json', raw)
        sources['evidence/legacy.json'] = raw
        current['assessment']['observed_hashes'].append(hashlib.sha256(raw).hexdigest())
        with self.assertRaisesRegex(ValueError, 'legacy predecessor bytes'):
            verify_sources(current, sources.__getitem__)

    def test_portable_projection_redacts_the_selected_predecessor_locator(self):
        original = assessed()
        original['aliases'] = {'F002': 'F001'}
        previous, _ = v2_alias_copy(original)
        current, _ = adopt_v2_copy(previous, original, select_history=True)
        disclosure = build_check_disclosure(current, input_identity_for(current), {}, {})
        portable = _Projection(current, {}, '', 'a' * 64, check_disclosure_context=disclosure,
                               check_disclosure_sources={}).value(current)
        self.assertEqual(review.validate(portable), [])
        before = current['assessment']['previous']['legacy_source']
        after = portable['assessment']['previous']['legacy_source']
        self.assertNotEqual(after['reference'], before['reference'])
        self.assertEqual(after['sha256'], before['sha256'])
        self.assertNotIn(before['reference'], json.dumps(portable))

    def test_guided_fixture_keeps_one_debt_from_v1_through_two_v3_generations(self):
        previous = assessed()
        previous['aliases'] = {'F002': 'F001'}
        current, sources = followup(previous)
        guided_current(current, previous)
        later, later_sources = following(current, 'c')
        guided_current(later, current)
        for record, selected in ((current, sources), (later, later_sources)):
            with self.subTest(review_id=record['review_id']):
                self.assertEqual([(item['id'], item['member_id'])
                                  for item in record['assessment']['authorizations']], [('AU001', 'F001')])
                self.assertEqual(review.validate(record), [])
                verify_sources(record, selected.__getitem__, captured_inputs={'sources': {}})
                self.assertEqual(rendered(record, 'user').count('Writes stay disabled'), 1)

    def test_guided_fixture_preserves_an_existing_v3_alias_authorization_link(self):
        previous = assessed()
        previous['aliases'] = {'F002': 'F001'}
        adopted, _ = adopt_v1(previous)
        current, sources = following(adopted, 'c')
        guided_current(current, adopted)
        self.assertEqual(review.validate(current), [])
        verify_sources(current, sources.__getitem__, captured_inputs={'sources': {}})

        self.assertEqual(current['assessment']['authorizations'], adopted['assessment']['authorizations'])

    def test_single_original_authorization_survives_followups_and_renders_one_debt(self):
        previous = assessed()
        previous['aliases'] = {'F002': 'F001', 'F003': 'F001'}
        self.assertEqual(review.validate(previous), [])
        verify_sources(previous, {'evidence/note.txt': NOTE, 'evidence/proof.txt': PROOF}.__getitem__)
        current, sources = adopt_v1(previous)
        later, later_sources = following(current, 'c')
        for record, selected in ((current, sources), (later, later_sources)):
            with self.subTest(review_id=record['review_id']):
                self.assertEqual(review.validate(record), [])
                verify_sources(record, selected.__getitem__, captured_inputs={'sources': {}})
                self.assertEqual(record['aliases'], {'F002': 'F001', 'F003': 'F001'})
                report = rendered(record, 'user')
                self.assertEqual(report.count('Deuda aceptada'), 1)
                self.assertEqual(report.count('Writes stay disabled'), 1)

    def test_copied_v1_alias_disposition_cannot_accredit_its_own_grant(self):
        previous = assessed()
        previous['aliases'] = {'F002': 'F001'}
        current, sources = adopt_v1(previous)
        assessment = current['assessment']
        original = assessment['authorizations'][0]
        copied = dict(copy.deepcopy(original), id='AU002', member_id='F002')
        assessment['authorizations'].append(copied)
        assessment['lineage'][1]['resolution']['authorization_id'] = 'AU002'
        resolution = assessment['findings'][0]['resolution']
        assessment['findings'][0]['resolution'] = [
            resolution, dict(copy.deepcopy(resolution), authorization_id='AU002')]
        self.assertEqual(review.validate(current), [])
        with self.assertRaisesRegex(ValueError, 'reopening|authorization'):
            verify_sources(current, sources.__getitem__, captured_inputs={'sources': {}})

    def test_v2_published_member_decisions_keep_separate_grants_even_when_identical(self):
        original = root_v2(two=True)
        first, second = original['assessment']['lineage']
        second['resolution'] = copy.deepcopy(first['resolution'])
        original['assessment']['findings'][1]['resolution'] = copy.deepcopy(first['resolution'])
        original['assessment']['observed_hashes'] = sorted(
            {first['resolution']['source']['sha256'],
             original['assessment']['scope']['delta'][0]['sources'][0]['sha256']})
        previous, published_sources = following(original, 'b')
        previous['assessment']['lineage'][1]['survivor'] = 'F001'
        previous['findings'].pop()
        previous['rereview'].pop()
        previous['assessment']['findings'].pop()
        previous['aliases'] = {'F002': 'F001'}
        self.assertEqual(review.validate(previous), [])
        verify_sources(previous, published_sources.__getitem__, captured_inputs={'sources': {}})

        current, sources = following(previous, 'c')
        assessment = current['assessment']
        assessment['previous']['legacy_source'] = source('legacy.json', published_sources['evidence/prior.json'])
        sources['evidence/legacy.json'] = published_sources['evidence/prior.json']
        assessment.update(schema_version=3, history_incomplete=True,
            authorizations=[authorization(original, 'AU001', 'F001', first['resolution']),
                            authorization(original, 'AU002', 'F002', second['resolution'])])
        for member, identifier in zip(assessment['lineage'], ('AU001', 'AU002')):
            member['resolution']['authorization_id'] = identifier
        assessment['findings'][0]['resolution'] = [
            copy.deepcopy(member['resolution']) for member in assessment['lineage']]
        self.assertEqual(review.validate(current), [])
        verify_sources(current, sources.__getitem__, captured_inputs={'sources': {}})
        self.assertEqual(rendered(current, 'user').count('Writes stay disabled'), 2)
        assessment['authorizations'].pop()
        assessment['lineage'][1]['resolution']['authorization_id'] = 'AU001'
        assessment['findings'][0]['resolution'] = copy.deepcopy(assessment['lineage'][0]['resolution'])
        with self.assertRaisesRegex(ValueError, 'reopening|authorization'):
            verify_sources(current, sources.__getitem__, captured_inputs={'sources': {}})

    def test_another_v2_generation_keeps_distinct_member_decisions(self):
        original = root_v2(two=True)
        previous, selected = following(original, 'b')
        previous['findings'].pop()
        previous['rereview'].pop()
        previous['assessment']['findings'].pop()
        previous['aliases'] = {'F002': 'F001'}
        previous['assessment']['lineage'][1]['survivor'] = 'F001'
        previous['assessment']['findings'][0]['resolution'] = [
            copy.deepcopy(member['resolution']) for member in previous['assessment']['lineage']]
        verify_sources(previous, selected.__getitem__)
        later, selected = following(previous, 'c')
        verify_sources(later, selected.__getitem__)
        current, sources = following(later, 'd')
        assessment = current['assessment']
        assessment['previous']['legacy_source'] = source('legacy.json', selected['evidence/prior.json'])
        sources['evidence/legacy.json'] = selected['evidence/prior.json']
        assessment.update(schema_version=3, history_incomplete=True, authorizations=[
            authorization(previous, f'AU{index:03d}', member['id'], member['resolution'])
            for index, member in enumerate(assessment['lineage'], 1)])
        for index, member in enumerate(assessment['lineage'], 1):
            member['resolution']['authorization_id'] = f'AU{index:03d}'
        assessment['findings'][0]['resolution'] = [
            copy.deepcopy(member['resolution']) for member in assessment['lineage']]
        verify_sources(current, sources.__getitem__, captured_inputs={'sources': {}})
        report = rendered(current, 'user')
        self.assertEqual(report.count('Writes stay disabled'), 1)
        self.assertEqual(report.count('Subscriber remains read-only'), 1)


class RetainedLegacyAliasAuthorityTests(unittest.TestCase):
    setUp = compact_fixtures.CompactPrepareTests.setUp
    prepare = compact_fixtures.CompactPrepareTests.prepare
    record_and_sources = compact_fixtures.CompactPrepareTests.record_and_sources

    def bind_followup(self, record, prior_run, prepared):
        fresh, selected = self.record_and_sources(prepared)
        record.pop('compact_identity', None)
        record['review_id'] = fresh['review_id']
        record['coverage']['execution'] = fresh['coverage']['execution']
        path = str(Path(prior_run) / 'review.json')
        record['previous_reviews'][0]['reference'] = path
        record['rereview'][0]['previous_reference'] = path
        return selected

    def publish_v1_alias(self, *, repo_identity=None):
        self.inputs['sources'] = {'evidence/note.txt': source('note.txt', NOTE)['sha256']}
        prepared = self.prepare(operation_id='v1-alias-pinned', repo_identity=repo_identity)
        seed, selected = self.record_and_sources(prepared)
        original = assessed(seed)
        original['aliases'] = {'F002': 'F001'}
        saved = compact.create_compact(prepared, original, render(original), self.inputs,
            sources={**selected, 'evidence/proof.txt': PROOF, 'evidence/note.txt': NOTE})
        self.inputs['sources'] = {}
        return saved['run_dir'], compact.read_compact(saved['run_dir'])['record']

    def test_compact_reader_accepts_preliminary_v3_but_writer_rejects_its_alias_grant(self):
        prior_run, original = self.publish_v1_alias()
        prepared = self.prepare(operation_id='intermediate-v3')
        current, sources = adopt_v1(original)
        selected = self.bind_followup(current, prior_run, prepared)
        saved = compact.create_compact(prepared, current, current_inputs=self.inputs,
                                      sources={**selected, **sources})
        retained = compact.read_compact(saved['run_dir'])
        old = retained['record']
        assessment = old['assessment']
        assessment['authorizations'].append(
            dict(copy.deepcopy(assessment['authorizations'][0]), id='AU002', member_id='F002'))
        assessment['lineage'][1]['resolution']['authorization_id'] = 'AU002'
        assessment['findings'][0]['resolution'] = [
            copy.deepcopy(member['resolution']) for member in assessment['lineage']]

        next_prepared = self.prepare(operation_id='reject-preliminary-new-write')
        rejected = copy.deepcopy(old)
        selected = self.bind_followup(rejected, prior_run, next_prepared)
        with self.assertRaisesRegex(ValueError, 'reopening|authorization'):
            compact.create_compact(next_prepared, rejected, current_inputs=self.inputs,
                                   sources={**selected, **sources})

        # Reproduce the historical bytes under the same native envelope.
        run = Path(saved['run_dir'])
        manifest = retained['manifest']
        payload = {'review.json': archive_bytes(old),
                   'informe.md': compact._render_compact(old, manifest['request'],
                                                        retained['sources']).encode('utf-8')}
        for name, raw in payload.items():
            (run / name).write_bytes(raw)
            manifest['hashes'][name] = hashlib.sha256(raw).hexdigest()
        manifest_raw = archive_bytes(manifest)
        (run / 'manifest.json').write_bytes(manifest_raw)
        (run / '.review-ownership.json').write_bytes(archive_bytes({
            'schema_version': 1, 'mode': 'compact', 'run_id': manifest['run_id'],
            'run_dir': str(run), 'manifest_sha256': hashlib.sha256(manifest_raw).hexdigest()}))
        self.assertEqual(compact.read_compact(run)['record'], old)
        self.assertEqual((run / 'review.json').read_bytes(), payload['review.json'])
        prior = run / assessment['previous']['source']['reference']
        prior.write_bytes(prior.read_bytes() + b' ')
        with self.assertRaisesRegex(ValueError, 'hash differs'):
            compact.read_compact(run)

    def test_guided_compact_adopts_the_v2_selected_predecessor_as_local_evidence(self):
        repo = self.root / 'repo'
        repo.mkdir()
        subprocess.run(['git', 'init', '-q', str(repo)], check=True)
        repository = repository_identity(repo)
        first_run, original = self.publish_v1_alias(repo_identity=repository)
        prepared = self.prepare(operation_id='intermediate-v2', repo_identity=repository)
        previous, sources = v2_alias_copy(original)
        selected = self.bind_followup(previous, first_run, prepared)
        saved = compact.create_compact(prepared, previous, render(previous), self.inputs,
                                      sources={**selected, **sources})
        prior_run = Path(saved['run_dir'])
        prior = compact.read_compact(prior_run)
        repository_key = hashlib.sha256(prepared['request']['repository_identity'].encode()).hexdigest()[:20]
        baseline = read_followup_baseline(prior_run, prepared['logical_scope'], repository_key,
                                          compact_reader=compact.read_compact)
        scope_file = self.root / 'scope.json'
        scope_file.write_bytes(archive_bytes(self.scope))
        output = run_cli('artifacts', ['followup-baseline', '--run-dir', str(prior_run),
                                      '--repo', str(repo), '--scope-file', str(scope_file)], cwd=self.root)
        self.assertEqual(output.returncode, 0, output.stderr)
        self.assertEqual(json.loads(output.stdout), baseline)
        ancestor = baseline['legacy_previous']
        self.assertEqual(ancestor['review_id'], original['review_id'])
        self.assertEqual(ancestor['sha256'], previous['assessment']['previous']['source']['sha256'])
        raw = Path(ancestor['review_file']).read_bytes()
        self.assertEqual(raw, archive_bytes(original))
        (Path(first_run) / 'review.json').unlink()

        prepared = self.prepare(operation_id='current-after-v2', repo_identity=repository)
        current, sources = adopt_v2_copy(prior['record'], original, select_history=True)
        selected = self.bind_followup(current, prior_run, prepared)
        sources['evidence/legacy.json'] = raw
        saved = compact.create_compact(prepared, current, current_inputs=self.inputs,
                                      sources={**selected, **sources})
        (prior_run / 'review.json').unlink()
        result = compact.read_compact(saved['run_dir'])
        self.assertEqual(result['record']['assessment']['authorizations'],
                         current['assessment']['authorizations'])
        self.assertEqual(result['sources']['evidence/legacy.json'], raw)
        report = rendered(result['record'], 'user')
        self.assertEqual(report.count('Writes stay disabled'), 1)
        self.assertNotIn('evidence/legacy.json', report)
        (Path(saved['run_dir']) / 'evidence/legacy.json').write_bytes(raw + b' ')
        with self.assertRaisesRegex(ValueError, 'hash differs'):
            compact.read_compact(saved['run_dir'])

if __name__ == '__main__':
    unittest.main()
