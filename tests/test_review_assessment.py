import copy
import hashlib
import json
from pathlib import Path
import unittest

from script_test_support import enable_package_imports
enable_package_imports()
from ccr.contracts import review
from ccr.contracts.check_disclosure import input_identity_for
from ccr.reporting.render import render
from ccr.shared.encoding import archive_bytes
from ccr.workflow.builders import build_check_disclosure
from test_review_contract import finding
from test_review_coverage13 import record13
from test_review_topology_integration import contexts12
import test_review_compact_archive as compact_fixtures


NOTE = b'Owner decision: accept duplicate delivery while writes are disabled.'
PROOF = b'Producer and consumer paths inspected at the pinned version.'
NEW = b'Current supported consumer can now write after duplicate delivery.'


def source(name, data):
    return dict(reference='evidence/' + name, sha256=hashlib.sha256(data).hexdigest())


def assessed(record=None):
    record = record if record is not None else record13()
    record['findings'] = [dict(finding(), id='F001', origin='preexisting',
                               title='Duplicate delivery in a read-only consumer')]
    record['coverage']['evidence'][0]['reference'] = 'evidence/proof.txt'
    record['assessment'] = dict(schema_version=1,
        scope={**{key: record['scope'][key] for key in ('base', 'head', 'snapshot')},
               'delta': [dict(detail='Inspected the existing consumer', evidence_ids=['EV001'],
                              sources=[source('proof.txt', PROOF)])]},
        previous=None, findings=[dict(id='F001', cause='duplicate-delivery', relation='affected_consumer',
            verification=dict(obligation='One delivery per event', trigger='Supported read-only consumer retries',
                consequence='The same event appears twice', consumer='Existing subscriber',
                question='Can a retry deliver the event again?', evidence_ids=['EV001']),
            resolution=dict(status='accepted_debt', scope='logical_scope', authority='scope_owner',
                channel='comment', source=source('note.txt', NOTE), conditions=['Writes stay disabled']),
            reopening=None)])
    return record


def followup(previous=None):
    previous = previous or assessed()
    raw = archive_bytes(previous)
    record = copy.deepcopy(previous)
    record['review_id'] = 'CR-' + 'f' * 20
    record['presentation']['kind'] = 'rereview'
    prior = dict(review_id=previous['review_id'], reference='https://example.org/pr/42#note-23244', verified=True)
    record['previous_reviews'] = [prior]
    record['rereview'] = [dict(id='F001', status='still_valid', details='Risk remains under the same conditions',
        previous_review_id=prior['review_id'], previous_reference=prior['reference'],
        previous_finding_id='F001', previous_title=previous['findings'][0]['title'], previous_url=None,
        check_ids=[])]
    record['assessment']['previous'] = dict(review_id=previous['review_id'], source=source('prior.json', raw))
    return record, {'evidence/prior.json': raw, 'evidence/note.txt': NOTE, 'evidence/proof.txt': PROOF}



def two_published_findings(record=None):
    record = assessed(record)
    record['findings'].append(dict(record['findings'][0], id='F002',
                                    title='Second report of duplicate delivery'))
    decision = copy.deepcopy(record['assessment']['findings'][0])
    decision.update(id='F002', cause='second-report-of-duplicate-delivery')
    record['assessment']['findings'].append(decision)
    return record


def consolidated_followup(previous):
    current, sources = followup(previous)
    current['findings'] = [row for row in current['findings'] if row['id'] == 'F001']
    current['assessment']['findings'] = [
        row for row in current['assessment']['findings'] if row['id'] == 'F001']
    current['aliases'] = {alias: 'F001' if target == 'F002' else target
                          for alias, target in current['aliases'].items()}
    current['aliases']['F002'] = 'F001'
    current['rereview'][0]['details'] = (
        'Both published reports were inspected and establish the same delivery cause.')
    return current, sources


def rendered(record, audience):
    disclosure = build_check_disclosure(record, input_identity_for(record), {}, {})
    contexts = contexts12(record) if audience == 'comment' else {}
    return render(record, audience, check_disclosure_context=disclosure, check_disclosure_sources={}, **contexts)


def guided_v2(record, previous=None):
    """Author complete v2 input fixtures for the real archive-writing tests."""
    assessment = record['assessment']
    old = (previous or {}).get('assessment', {})
    members = copy.deepcopy(old.get('lineage', []))
    rows = {row['id']: row for row in assessment['findings']}
    findings = {row['id']: row for row in record['findings']}
    tracking = {row['id']: row for row in record['rereview']}
    if not members:
        members = [dict(id=row['id'], cause=row['cause'], survivor=row['id'],
            title=findings.get(row['id'], {}).get('title') or tracking[row['id']]['previous_title'],
            last_status='confirmed', resolution=copy.deepcopy(row['resolution']))
            for row in assessment['findings']]
        for alias, target in record['aliases'].items():
            member = copy.deepcopy(next(item for item in members if item['id'] == target))
            member['id'] = alias
            members.append(member)
    for member in members:
        target = record['aliases'].get(member['survivor'], member['survivor'])
        member['survivor'] = target
        if target in rows:
            value = rows[target]['resolution']
            choices = value if isinstance(value, list) else [] if value is None else [value]
            if member['resolution'] not in choices:
                member['resolution'] = copy.deepcopy(value)
    descriptors = [item for delta in assessment['scope']['delta'] for item in delta['sources']]
    if assessment['previous']:
        descriptors.append(assessment['previous']['source'])
    for row in assessment['findings']:
        value = row['resolution']
        descriptors.extend(item['source'] for item in (value if isinstance(value, list)
                           else [] if value is None else [value]))
    assessment.update(schema_version=2, lineage=members,
        observed_hashes=sorted(set(old.get('observed_hashes', []))
                               | {item['sha256'] for item in descriptors}))
    return record


class AssessmentTests(unittest.TestCase):
    def test_confirmed_needs_reachable_obligation_and_an_inspected_consumer(self):
        record = assessed()
        self.assertEqual(review.validate(record), [])
        row = record['assessment']['findings'][0]
        row['verification']['trigger'] = None
        self.assertTrue(any('trigger' in error for error in review.validate(record)))
        row['verification']['trigger'] = 'Concrete supported retry'
        row['verification']['question'] = None
        self.assertTrue(any('question' in error for error in review.validate(record)))
        row['verification']['question'] = 'Is the consumer affected?'
        row['relation'] = 'outside_scope'
        self.assertTrue(any('outside' in error for error in review.validate(record)))

    def test_same_revision_can_have_distinct_verdict_scope_and_no_required_debt_fix(self):
        original = assessed()
        current, _ = followup(original)
        current['findings'][0]['location']['line'] = 88
        self.assertEqual(review.validate(current), [])
        for audience in ('user', 'comment'):
            self.assertIn('Revisión completa', rendered(original, audience))
            output = rendered(current, audience)
            self.assertIn('Seguimiento acotado', output)
            self.assertIn('F001', output)
            self.assertIn('Deuda aceptada', output)
            self.assertIn('Writes stay disabled', output)
            self.assertNotIn('Corrección requerida', output)
        self.assertNotIn('evidence/note.txt', rendered(current, 'comment'))

    def test_accepted_debt_requires_material_new_evidence_and_keeps_id(self):
        from ccr.contracts.assessment import verify_sources
        current, sources = followup()
        verify_sources(current, sources.__getitem__)
        row = current['assessment']['findings'][0]
        resolution = row['resolution']
        row['resolution'] = None
        with self.assertRaisesRegex(ValueError, 'reopening'):
            verify_sources(current, sources.__getitem__)
        row['reopening'] = dict(reason='condition_changed', detail='Writes were enabled',
            condition=resolution['conditions'][0], evidence_id='EV001', source=source('proof.txt', PROOF))
        with self.assertRaisesRegex(ValueError, 'already used'):
            verify_sources(current, sources.__getitem__)
        row['reopening']['source'] = source('new.txt', NEW)
        current['coverage']['evidence'][0]['reference'] = 'evidence/new.txt'
        current['assessment']['scope']['delta'][0]['sources'] = [source('new.txt', NEW)]
        sources['evidence/new.txt'] = NEW
        self.assertEqual(review.validate(current), [])
        verify_sources(current, sources.__getitem__)
        self.assertEqual(current['findings'][0]['id'], 'F001')
        self.assertIn('Corrección requerida', rendered(current, 'user'))
        row['cause'] = 'unrelated-cause'
        with self.assertRaisesRegex(ValueError, 'cause'):
            verify_sources(current, sources.__getitem__)

    def test_same_cause_is_not_reintroduced_under_another_id(self):
        from ccr.contracts.assessment import verify_sources
        current, sources = followup()
        duplicate = dict(current['findings'][0], id='F002')
        current['findings'].append(duplicate)
        current['assessment']['findings'].append(dict(current['assessment']['findings'][0], id='F002'))
        with self.assertRaisesRegex(ValueError, 'published ID'):
            verify_sources(current, sources.__getitem__)

    def test_consolidation_preserves_published_aliases_and_shared_accepted_debt(self):
        from ccr.contracts.assessment import verify_sources
        previous = two_published_findings()
        previous['aliases'] = {'F003': 'F002'}
        current, sources = consolidated_followup(previous)
        self.assertEqual(review.validate(previous), [])
        self.assertEqual(review.validate(current), [])
        verify_sources(current, sources.__getitem__, captured_inputs={'sources': {}})
        self.assertEqual(current['aliases'], {'F002': 'F001', 'F003': 'F001'})
        for audience in ('user', 'comment'):
            output = rendered(current, audience)
            self.assertIn('Deuda aceptada', output)
            self.assertIn('Writes stay disabled', output)
            self.assertNotIn('Corrección requerida', output)
        for removed in ('F002', 'F003'):
            missing = copy.deepcopy(current)
            missing['aliases'].pop(removed)
            with self.subTest(removed=removed), self.assertRaises(ValueError):
                verify_sources(missing, sources.__getitem__)

    def test_consolidation_inherits_debt_from_the_aliased_member_without_recapture(self):
        from ccr.contracts.assessment import verify_sources
        previous = two_published_findings()
        previous['assessment']['findings'][0]['resolution'] = None
        current, sources = consolidated_followup(previous)
        current['assessment']['findings'][0]['resolution'] = copy.deepcopy(
            previous['assessment']['findings'][1]['resolution'])
        self.assertEqual(review.validate(current), [])
        verify_sources(current, sources.__getitem__, captured_inputs={'sources': {}})
        decision = current['assessment']['findings'][0]
        for field, changed in (('resolution', None),
                               ('resolution', dict(decision['resolution'], conditions=[]))):
            altered = copy.deepcopy(current)
            altered['assessment']['findings'][0][field] = changed
            with self.subTest(changed=changed), self.assertRaisesRegex(ValueError, 'reopening'):
                verify_sources(altered, sources.__getitem__, captured_inputs={'sources': {}})

    def test_consolidation_cannot_discard_a_different_accepted_condition(self):
        from ccr.contracts.assessment import verify_sources
        previous = two_published_findings()
        previous['assessment']['findings'][1]['resolution']['conditions'] = [
            'Consumer remains read-only']
        current, sources = consolidated_followup(previous)
        self.assertEqual(review.validate(current), [])
        with self.assertRaisesRegex(ValueError, 'reopening'):
            verify_sources(current, sources.__getitem__)

    def test_consolidation_can_reopen_aliased_debt_with_new_condition_evidence(self):
        from ccr.contracts.assessment import verify_sources
        previous = two_published_findings()
        previous['assessment']['findings'][0]['resolution'] = None
        current, sources = consolidated_followup(previous)
        row = current['assessment']['findings'][0]
        row['reopening'] = dict(reason='condition_changed', detail='Writes were enabled',
            condition='Writes stay disabled', evidence_id='EV001', source=source('new.txt', NEW))
        current['coverage']['evidence'][0]['reference'] = 'evidence/new.txt'
        current['assessment']['scope']['delta'][0]['sources'] = [source('new.txt', NEW)]
        sources['evidence/new.txt'] = NEW
        self.assertEqual(review.validate(current), [])
        verify_sources(current, sources.__getitem__, captured_inputs={'sources': {}})
        row['reopening']['condition'] = 'An unrelated condition'
        with self.assertRaisesRegex(ValueError, 'original accepted condition'):
            verify_sources(current, sources.__getitem__)

    def test_consolidation_needs_current_verification_of_the_survivor(self):
        from ccr.contracts.assessment import verify_sources
        current, sources = consolidated_followup(two_published_findings())
        current['findings'] = []
        current['rereview'][0]['status'] = 'not_reevaluated'
        current['assessment']['findings'][0].update(relation='outside_scope', verification=None)
        self.assertEqual(review.validate(current), [])
        with self.assertRaisesRegex(ValueError, 'consolidation'):
            verify_sources(current, sources.__getitem__)

    def test_consolidation_cannot_reassign_a_published_member_to_a_new_id(self):
        from ccr.contracts.assessment import verify_sources
        current, sources = consolidated_followup(two_published_findings())
        current['findings'].append(dict(current['findings'][0], id='F004'))
        decision = copy.deepcopy(current['assessment']['findings'][0])
        decision.update(id='F004', cause='new-cause')
        current['assessment']['findings'].append(decision)
        current['rereview'].append(dict(
            id='F004', status='new', details='New independent cause',
            previous_review_id=None, previous_reference=None, previous_finding_id=None,
            previous_title=None, previous_url=None, check_ids=[]))
        current['aliases']['F002'] = 'F004'
        self.assertEqual(review.validate(current), [])
        with self.assertRaisesRegex(ValueError, 'published survivor'):
            verify_sources(current, sources.__getitem__)

    def test_consolidation_keeps_one_review_exclusions_expired(self):
        from ccr.contracts.assessment import verify_sources
        previous = two_published_findings()
        previous['assessment']['findings'][0]['resolution'] = None
        previous['assessment']['findings'][1]['resolution'].update(
            status='out_of_scope', scope='this_review')
        current, sources = consolidated_followup(previous)
        current['assessment']['findings'][0]['resolution'] = copy.deepcopy(
            previous['assessment']['findings'][1]['resolution'])
        self.assertEqual(review.validate(current), [])
        with self.assertRaisesRegex(ValueError, 'this_review'):
            verify_sources(current, sources.__getitem__)
        current['assessment']['findings'][0]['resolution'] = None
        verify_sources(current, sources.__getitem__, captured_inputs={'sources': {}})

    def test_group_chooses_the_previously_published_id(self):
        from ccr.contracts.identifiers import deduplicate
        groups = deduplicate([dict(id='D1-F001'), dict(id='F009')],
                             [['D1-F001', 'F009']], prior_ids=['F009'])
        self.assertEqual(groups[0]['id'], 'F009')

    def test_id_allocation_updates_the_assessment_with_the_same_canonical_id(self):
        from ccr.contracts.identifiers import canonicalize_ids
        record = assessed()
        record['findings'][0]['id'] = 'D1-F001'
        record['assessment']['findings'][0]['id'] = 'D1-F001'
        final, mapping = canonicalize_ids(record, {'findings': ['F009'], 'checks': []})
        self.assertEqual(mapping['findings']['D1-F001'], 'F010')
        self.assertEqual(final['assessment']['findings'][0]['id'], final['findings'][0]['id'])

    def test_outside_delta_stays_not_reevaluated_and_keeps_debt(self):
        from ccr.contracts.assessment import verify_sources
        current, sources = followup()
        current['findings'] = []
        current['rereview'][0]['status'] = 'not_reevaluated'
        current['assessment']['findings'][0].update(relation='outside_scope', verification=None)
        self.assertEqual(review.validate(current), [])
        verify_sources(current, sources.__getitem__)
        self.assertIn('Deuda aceptada', rendered(current, 'user'))
        self.assertIn('no reevaluado', rendered(current, 'user'))
        current['assessment']['findings'][0]['resolution'] = None
        with self.assertRaisesRegex(ValueError, 'reopening'):
            verify_sources(current, sources.__getitem__)

    def test_resolution_exclusion_for_one_review_expires(self):
        from ccr.contracts.assessment import verify_sources
        original = assessed()
        original['assessment']['findings'][0]['resolution'].update(status='out_of_scope', scope='this_review')
        current, sources = followup(original)
        with self.assertRaisesRegex(ValueError, 'this_review'):
            verify_sources(current, sources.__getitem__, captured_inputs={'sources': {}})
        current['assessment']['findings'][0]['resolution'] = None
        verify_sources(current, sources.__getitem__, captured_inputs={'sources': {}})

    def test_verifier_records_explicit_obligation_before_confirming(self):
        from ccr.contracts.packets import validate
        row = assessed()['assessment']['findings'][0]
        verification = {key: value for key, value in row['verification'].items() if key != 'evidence_ids'}
        packet = dict(packet_version=1, stage='verification', context_id='same-scope', check_ids=[],
            coverage=dict(flows=[], limitations=[]), decisions=[dict(id='F001', status='confirmed',
            evidence=[dict(kind='static', details='Producer and consumer inspected', check_id=None)],
            assessment=dict(cause=row['cause'], relation=row['relation'], verification=verification))])
        self.assertEqual(validate(packet), [])
        verification['obligation'] = None
        self.assertTrue(any('obligation' in error for error in validate(packet)))

    def test_resolution_channels_require_authority_and_captured_decision(self):
        from ccr.contracts.assessment import verify_sources
        record = assessed()
        decision = record['assessment']['findings'][0]['resolution']
        selected = {'evidence/note.txt': NOTE, 'evidence/proof.txt': PROOF}
        captured = {'sources': {'evidence/note.txt': decision['source']['sha256']}}
        for channel in ('chat', 'comment', 'description', 'document'):
            with self.subTest(channel=channel):
                decision['channel'] = channel
                self.assertEqual(review.validate(record), [])
                verify_sources(record, selected.__getitem__, captured_inputs=captured)
        with self.assertRaisesRegex(ValueError, 'initially captured'):
            verify_sources(record, selected.__getitem__, captured_inputs={'sources': {}})
        decision['authority'] = 'author_proposal'
        self.assertTrue(any('authority' in error for error in review.validate(record)))

    def test_portable_and_brief_keep_scope_without_private_evidence_path(self):
        from ccr.reporting.text_projection import _Projection
        from ccr.reporting.delivery import _brief
        current, _ = followup()
        disclosure = build_check_disclosure(current, input_identity_for(current), {}, {})
        portable = _Projection(current, {}, '', 'a' * 64, check_disclosure_context=disclosure,
                               check_disclosure_sources={}).value(current)
        self.assertEqual(review.validate(portable), [])
        output = _brief(portable)
        self.assertIn('Seguimiento acotado', output)
        self.assertIn('Deuda aceptada', output)
        self.assertNotIn('evidence/note.txt', json.dumps(portable))
        self.assertNotIn('Corrección requerida', output)

    def test_followup_delta_does_not_certify_ordinary_coverage(self):
        from ccr.workflow.reuse import coverage_reuse_issue
        original = assessed()
        current, _ = followup(original)
        self.assertIsNone(coverage_reuse_issue(original))
        self.assertEqual(coverage_reuse_issue(current)['code'], 'ordinary_coverage_unproven')
        current['presentation']['kind'] = 'review'
        current['coverage']['evidence'].append(dict(current['coverage']['evidence'][0], id='EV002'))
        current['coverage']['areas'][0]['groups'][0]['evidence_ids'] = ['EV002']
        self.assertEqual(coverage_reuse_issue(current)['code'], 'previous_coverage_incomplete')


class AssessmentCompactTests(unittest.TestCase):
    setUp = compact_fixtures.CompactPrepareTests.setUp
    prepare = compact_fixtures.CompactPrepareTests.prepare
    record_and_sources = compact_fixtures.CompactPrepareTests.record_and_sources

    def test_compact_roundtrip_keeps_distinct_member_decisions_and_sources(self):
        from ccr.archive import compact
        second_note = b'Second owner: accept the duplicate while the subscriber is read-only.'
        decisions = {'evidence/note.txt': NOTE, 'evidence/second-note.txt': second_note,
                     'evidence/proof.txt': PROOF}
        inputs = dict(self.inputs, sources={key: hashlib.sha256(raw).hexdigest()
                      for key, raw in decisions.items() if key != 'evidence/proof.txt'})
        prepared = self.prepare(inputs=inputs)
        original, selected = self.record_and_sources(prepared)
        two_published_findings(original)
        original['assessment']['findings'][1]['resolution'].update(
            source=source('second-note.txt', second_note), conditions=['Subscriber remains read-only'])
        guided_v2(original)
        saved = compact.create_compact(prepared, original, current_inputs=inputs,
                                       sources={**selected, **decisions})
        prior_file = Path(saved['run_dir']) / 'review.json'
        prior_bytes = prior_file.read_bytes()
        previous = compact.read_compact(saved['run_dir'])['record']
        prepared = self.prepare(operation_id='member-decisions-followup')
        fresh, selected = self.record_and_sources(prepared)
        current, proof = consolidated_followup(previous)
        current.pop('compact_identity')
        current['review_id'] = fresh['review_id']
        current['coverage']['execution'] = fresh['coverage']['execution']
        current['previous_reviews'][0]['reference'] = str(prior_file)
        current['rereview'][0]['previous_reference'] = str(prior_file)
        current['assessment']['findings'][0]['resolution'] = [
            copy.deepcopy(row['resolution']) for row in previous['assessment']['findings']]
        guided_v2(current, previous)
        kept = compact.create_compact(prepared, current, current_inputs=self.inputs,
                                      sources={**selected, **proof, **decisions})
        result = compact.read_compact(kept['run_dir'])['record']
        self.assertEqual(result['aliases'], {'F002': 'F001'})
        resolutions = result['assessment']['findings'][0]['resolution']
        self.assertEqual([decision['conditions'] for decision in resolutions],
                         [['Writes stay disabled'], ['Subscriber remains read-only']])
        self.assertEqual([item['source']['reference'] for item in resolutions],
                         ['evidence/note.txt', 'evidence/second-note.txt'])
        report = (Path(kept['run_dir']) / 'informe.md').read_text(encoding='utf8')
        self.assertIn('Writes stay disabled', report)
        self.assertIn('Subscriber remains read-only', report)
        self.assertNotIn('Corrección requerida', report)
        self.assertEqual(prior_file.read_bytes(), prior_bytes)

    def test_compact_consolidation_preserves_ids_debt_and_previous_bytes(self):
        from ccr.archive import compact
        for legacy in (True, False):
            with self.subTest(legacy=legacy):
                inputs = dict(self.inputs, sources={
                    'evidence/note.txt': source('note.txt', NOTE)['sha256']})
                prepared = self.prepare(inputs=inputs, operation_id='prior-' + str(legacy))
                record, selected = self.record_and_sources(prepared)
                two_published_findings(record)
                guided_v2(record)
                assessment = copy.deepcopy(record['assessment'])
                if legacy:
                    record.pop('assessment')
                saved = compact.create_compact(
                    prepared, record, render(record), current_inputs=inputs,
                    sources={**selected, 'evidence/note.txt': NOTE, 'evidence/proof.txt': PROOF})
                old_file = Path(saved['run_dir']) / 'review.json'
                old_bytes = old_file.read_bytes()
                previous = compact.read_compact(saved['run_dir'])['record']
                previous['assessment'] = assessment
                next_inputs = inputs if legacy else self.inputs
                prepared = self.prepare(inputs=next_inputs, operation_id='merged-' + str(legacy))
                fresh, selected = self.record_and_sources(prepared)
                current, sources = consolidated_followup(previous)
                current.pop('compact_identity')
                current['review_id'] = fresh['review_id']
                current['coverage']['execution'] = fresh['coverage']['execution']
                current['previous_reviews'][0]['reference'] = str(old_file)
                current['rereview'][0]['previous_reference'] = str(old_file)
                current['assessment']['previous']['source'] = source('prior.json', old_bytes)
                sources['evidence/prior.json'] = old_bytes
                guided_v2(current, previous)
                if legacy:
                    # The legacy duplicate did not publish a stable cause key.
                    current['assessment']['lineage'][1]['cause'] = None
                self.assertEqual(review.validate(current), [])
                kept = compact.create_compact(
                    prepared, current, current_inputs=next_inputs, sources={**selected, **sources})
                retained = compact.read_compact(kept['run_dir'])['record']
                self.assertEqual(retained['aliases'], {'F002': 'F001'})
                self.assertEqual([row['id'] for row in retained['findings']], ['F001'])
                self.assertEqual(retained['assessment']['findings'][0]['resolution'],
                                 assessment['findings'][0]['resolution'])
                output = (Path(kept['run_dir']) / 'informe.md').read_text(encoding='utf-8')
                self.assertIn('Deuda aceptada', output)
                self.assertIn('Writes stay disabled', output)
                self.assertNotIn('Corrección requerida', output)
                self.assertEqual(old_file.read_bytes(), old_bytes)

    def test_followup_baseline_checks_selected_archive_before_prepare(self):
        import subprocess
        from ccr.shared.git import repository_identity
        from script_test_support import run_cli

        repo = self.root / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "remote", "add", "origin",
                        "https://example.test/team/repo"], check=True)
        prepared = self.prepare(repo_identity=repository_identity(repo))
        record, selected = self.record_and_sources(prepared)
        kept = compact_fixtures.compact.create_compact(
            prepared, record, current_inputs=self.inputs, sources=selected)
        prior = Path(kept["run_dir"]) / "review.json"
        raw = prior.read_bytes()
        scope_file = self.root / "scope.json"
        scope_file.write_bytes(archive_bytes(self.scope))

        args = ["followup-baseline", "--run-dir", str(prior.parent), "--repo", str(repo),
                "--scope-file", str(scope_file)]
        result = run_cli("artifacts", args, cwd=self.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {
            "review_id": record["review_id"], "review_file": str(prior),
            "sha256": hashlib.sha256(raw).hexdigest(),
        })
        scope_file.write_bytes(archive_bytes(dict(
            self.scope, reference="https://example.test/team/repo/pull/999")))
        other = run_cli("artifacts", args, cwd=self.root)
        self.assertNotEqual(other.returncode, 0)
        self.assertIn("another repository or logical scope", other.stderr)
        self.assertEqual(prior.read_bytes(), raw)

    def test_retention_verifies_the_actual_prior_and_preserves_accepted_debt(self):
        from ccr.archive import compact
        sources = {'evidence/note.txt': NOTE, 'evidence/proof.txt': PROOF}
        inputs = dict(self.inputs, sources={'evidence/note.txt': source('note.txt', NOTE)['sha256']})
        prepared = self.prepare(inputs=inputs)
        original, selected = self.record_and_sources(prepared)
        assessed(original)
        guided_v2(original)
        kept = compact.create_compact(prepared, original, current_inputs=inputs, sources={**selected, **sources})
        old_file = Path(kept['run_dir']) / 'review.json'
        previous = json.loads(old_file.read_bytes())
        prepared = self.prepare(operation_id='followup')
        fresh, selected = self.record_and_sources(prepared)
        current, proof = followup(previous)
        current.pop('compact_identity')
        current['review_id'] = fresh['review_id']
        current['coverage']['execution'] = fresh['coverage']['execution']
        for item in [current['previous_reviews'][0], current['rereview'][0]]:
            key = 'reference' if item is current['previous_reviews'][0] else 'previous_reference'
            item[key] = str(old_file)
        selected.update(proof)
        guided_v2(current, previous)
        dropped = copy.deepcopy(current)
        dropped['assessment']['findings'][0]['resolution'] = None
        dropped['assessment']['lineage'][0]['resolution'] = None
        with self.assertRaisesRegex(ValueError, 'reopening'):
            compact.create_compact(prepared, dropped, current_inputs=self.inputs, sources=selected)
        forged = copy.deepcopy(previous)
        forged['verdict_reason'] = 'Changed previous result'
        forged = archive_bytes(forged)
        wrong = copy.deepcopy(current)
        wrong['assessment']['previous']['source'] = source('prior.json', forged)
        wrong['assessment']['observed_hashes'] = sorted(
            (set(wrong['assessment']['observed_hashes'])
             - {hashlib.sha256(old_file.read_bytes()).hexdigest()})
            | {hashlib.sha256(forged).hexdigest()})
        with self.assertRaisesRegex(ValueError, 'verified prior archive'):
            compact.create_compact(prepared, wrong, current_inputs=self.inputs,
                                   sources={**selected, 'evidence/prior.json': forged})
        self.assertFalse(Path(prepared['run_dir']).exists())
        saved = compact.create_compact(prepared, current, current_inputs=self.inputs, sources=selected)
        self.assertEqual(compact.read_compact(saved['run_dir'])['record']['findings'][0]['id'], 'F001')
        output = (Path(saved['run_dir']) / 'informe.md').read_text(encoding='utf-8')
        self.assertIn('Seguimiento acotado', output)
        self.assertIn('Deuda aceptada', output)

        other_scope = dict(self.scope, reference='https://example.test/team/repo/pull/999')
        other_inputs = dict(self.inputs, scope=other_scope)
        other = self.prepare(scope=other_scope, inputs=other_inputs, operation_id='another-scope')
        other_record, other_sources = self.record_and_sources(other)
        mismatched = copy.deepcopy(current)
        mismatched['scope'] = other['request']['scope']
        mismatched['review_id'] = other_record['review_id']
        mismatched['coverage']['execution'] = other_record['coverage']['execution']
        with self.assertRaisesRegex(ValueError, 'another repository or logical scope'):
            compact.create_compact(other, mismatched, current_inputs=other_inputs, sources={**other_sources, **proof})
