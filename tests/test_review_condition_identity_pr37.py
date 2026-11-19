"""Portable dispositions retain identity without publishing secret verifiers."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import unittest

from test_review_assessment import assessed, guided_v2, NOTE, PROOF
from test_review_assessment_projection2 import grouped_record
import test_review_compact_archive as compact_fixtures
from ccr.archive import compact
from ccr.contracts import review
from ccr.contracts.check_disclosure import input_identity_for
from ccr.contracts.references import parse_reference
from ccr.reporting import delivery
from ccr.reporting.render import render
from ccr.reporting.text_projection import _Projection
from ccr.shared.git import repository_identity
from ccr.workflow.builders import build_check_disclosure


PRIVATE = 'password=1234'
PUBLIC = 'password=[omitido]'
# Text copied literally from a delivery made by the previous implementation.
OLD_PUBLIC = 'password=[omitido] [condición retenida: 0526d20138aa467a]'


def decisions_record(second=PUBLIC):
    value = grouped_record()
    first = value['assessment']['findings'][0]['resolution'][0]
    first['conditions'] = [PRIVATE]
    other = copy.deepcopy(first)
    other['conditions'] = [second]
    value['assessment']['findings'][0]['resolution'] = [first, other]
    value['assessment']['lineage'][0]['resolution'] = copy.deepcopy(first)
    value['assessment']['lineage'][1]['resolution'] = copy.deepcopy(other)
    return value


def project(value):
    disclosure = build_check_disclosure(value, input_identity_for(value), {}, {})
    return _Projection(value, {}, '', 'a' * 64, check_disclosure_context=disclosure,
                       check_disclosure_sources={}).value(value)


def authorized_record():
    value = decisions_record()
    assessment = value['assessment']
    assessment.update(schema_version=3, history_incomplete=False, authorizations=[])
    for index, decision in enumerate(assessment['findings'][0]['resolution']):
        identifier = 'AU00' + str(index + 1)
        assessment['authorizations'].append(dict(id=identifier,
            member_id=assessment['lineage'][index]['id'], review_id=value['review_id'],
            scope={name: value['scope'][name] for name in ('base', 'head', 'snapshot')},
            decision=copy.deepcopy(decision)))
        decision['authorization_id'] = identifier
        assessment['lineage'][index]['resolution']['authorization_id'] = identifier
    return value


class ConditionIdentityTests(unittest.TestCase):
    def test_redacted_condition_has_no_public_secret_verifier(self):
        value = assessed()
        value['assessment']['findings'][0]['resolution']['conditions'] = [PRIVATE]
        portable = project(value)
        conditions = portable['assessment']['findings'][0]['resolution']['conditions']
        self.assertEqual(conditions, [PUBLIC])
        serialized = json.dumps(portable)
        for spelling in ('1234', '0526d20138aa467a', hashlib.sha256(b'1234').hexdigest()):
            self.assertNotIn(spelling, serialized)
        self.assertEqual(review.validate(portable), [])

    def test_equal_visible_conditions_remain_distinct_with_shared_provenance(self):
        value = decisions_record()
        before = copy.deepcopy(value)
        self.assertEqual(review.validate(value), [])
        portable = project(value)
        self.assertEqual(review.validate(portable), [])
        decisions = portable['assessment']['findings'][0]['resolution']
        self.assertEqual([item['conditions'] for item in decisions], [[PUBLIC], [PUBLIC]])
        self.assertNotEqual(decisions[0]['source']['reference'], decisions[1]['source']['reference'])
        first_name, first_fragment = parse_reference(decisions[0]['source']['reference'], field='first')
        second_name, second_fragment = parse_reference(decisions[1]['source']['reference'], field='second')
        self.assertEqual(first_name, second_name)
        self.assertNotEqual(first_fragment, second_fragment)
        for index, member in enumerate(portable['assessment']['lineage']):
            self.assertEqual(member['resolution'], decisions[index])
        self.assertEqual(value, before)

    def test_literal_copy_of_old_projection_is_valid_user_text(self):
        portable = project(decisions_record(OLD_PUBLIC))
        self.assertEqual(review.validate(portable), [])
        decisions = portable['assessment']['findings'][0]['resolution']
        self.assertEqual(decisions[0]['conditions'], [PUBLIC])
        self.assertEqual(decisions[1]['conditions'], [OLD_PUBLIC])
        self.assertNotEqual(decisions[0]['source']['reference'], decisions[1]['source']['reference'])

    def test_public_identity_does_not_change_with_private_secret_spelling(self):
        public_views = []
        for secret in ('5678', 'guest'):
            value = decisions_record('password=' + secret)
            portable = project(value)
            self.assertEqual(review.validate(portable), [])
            decisions = portable['assessment']['findings'][0]['resolution']
            self.assertEqual([item['conditions'] for item in decisions], [[PUBLIC], [PUBLIC]])
            self.assertNotEqual(decisions[0]['source']['reference'], decisions[1]['source']['reference'])
            public_views.append(decisions)
        self.assertEqual(public_views[0], public_views[1])

    def test_actual_duplicate_decisions_are_still_rejected(self):
        value = decisions_record()
        decisions = value['assessment']['findings'][0]['resolution']
        decisions[1] = copy.deepcopy(decisions[0])
        errors = review.validate(project(value))
        self.assertTrue(any('distinct list' in error for error in errors), errors)

    def test_source_fragments_have_one_valid_portable_decision_fragment(self):
        value = decisions_record()
        decisions = value['assessment']['findings'][0]['resolution']
        for item in decisions:
            item['source']['reference'] += '#owner-note'
        for index, member in enumerate(value['assessment']['lineage']):
            member['resolution'] = copy.deepcopy(decisions[index])
        portable = project(value)
        self.assertEqual(review.validate(portable), [])
        for item in portable['assessment']['findings'][0]['resolution']:
            reference = item['source']['reference']
            self.assertEqual(reference.count('#'), 1)
            parse_reference(reference, field='portable decision')

    def test_v3_ledger_and_active_dispositions_share_structural_identity(self):
        value = authorized_record()
        self.assertEqual(review.validate(value), [])
        portable = project(value)
        self.assertEqual(review.validate(portable), [])
        decisions = portable['assessment']['findings'][0]['resolution']
        authorizations = portable['assessment']['authorizations']
        self.assertEqual([item['conditions'] for item in decisions], [[PUBLIC], [PUBLIC]])
        self.assertNotEqual(decisions[0]['source']['reference'], decisions[1]['source']['reference'])
        for index, authorization in enumerate(authorizations):
            self.assertEqual(authorization['decision'],
                {key: item for key, item in decisions[index].items() if key != 'authorization_id'})
            self.assertEqual(authorization['id'], decisions[index]['authorization_id'])
            self.assertEqual(portable['assessment']['lineage'][index]['resolution'], decisions[index])

    def test_v3_inactive_authorization_is_projected_without_its_retained_note(self):
        value = authorized_record()
        inactive = copy.deepcopy(value['assessment']['authorizations'][0])
        inactive.update(id='AU003', review_id='CR-' + 'c' * 20)
        inactive['decision']['source'] = {'reference': 'evidence/old-note.txt#owner-note',
                                          'sha256': 'f' * 64}
        value['assessment']['authorizations'].append(inactive)
        value['assessment']['observed_hashes'].append('f' * 64)
        self.assertEqual(review.validate(value), [])
        portable = project(value)
        self.assertEqual(review.validate(portable), [])
        decision = portable['assessment']['authorizations'][2]['decision']
        self.assertEqual(decision['conditions'], [PUBLIC])
        self.assertNotIn('old-note', json.dumps(portable))
        self.assertNotIn('1234', json.dumps(portable))
        self.assertEqual(decision['source']['reference'].count('#'), 1)
        parse_reference(decision['source']['reference'], field='inactive decision')


class ConditionIdentityDeliveryTests(unittest.TestCase):
    setUp = compact_fixtures.CompactPrepareTests.setUp
    prepare = compact_fixtures.CompactPrepareTests.prepare
    record_and_sources = compact_fixtures.CompactPrepareTests.record_and_sources

    def retained_v2(self, second):
        self.repo = self.root / ('repo-' + str(len(second)))
        self.repo.mkdir()
        subprocess.run(['git', 'init', '-q', str(self.repo)], check=True)
        inputs = dict(self.inputs, sources={'evidence/note.txt': hashlib.sha256(NOTE).hexdigest()})
        prepared = self.prepare(inputs=inputs, operation_id='conditions-' + str(len(second)),
                                repo_identity=repository_identity(self.repo),
                                archive_root=self.root / 'archive')
        value, selected = self.record_and_sources(prepared)
        assessed(value)
        guided_v2(value)
        first = value['assessment']['findings'][0]['resolution']
        first['conditions'] = [PRIVATE]
        other = copy.deepcopy(first)
        other['conditions'] = [second]
        value['assessment']['findings'][0]['resolution'] = [first, other]
        value['assessment']['lineage'][0]['resolution'] = copy.deepcopy([first, other])
        self.assertEqual(review.validate(value), [])
        # Explicit report imports remain compatible with previously emitted v2.
        saved = compact.create_compact(prepared, value, render(value), current_inputs=inputs,
            sources={**selected, 'evidence/note.txt': NOTE, 'evidence/proof.txt': PROOF})
        return Path(saved['run_dir'])

    def assert_deliverable(self, second):
        run = self.retained_v2(second)
        before = {p.relative_to(run): p.read_bytes() for p in run.rglob('*') if p.is_file()}
        for mode in ('full', 'brief'):
            with self.subTest(mode=mode):
                target = delivery.deliver(run, mode, self.repo, self.root / mode)
                report = (target / ('informe.md' if mode == 'full' else 'resumen.md')).read_text(encoding='utf-8')
                self.assertNotIn('1234', report)
                if second == PUBLIC:
                    self.assertNotIn('0526d20138aa467a', report)
                if mode == 'full':
                    portable = json.loads((target / 'review.json').read_bytes())
                    self.assertEqual(review.validate(portable), [])
                    decisions = portable['assessment']['findings'][0]['resolution']
                    self.assertEqual(decisions[0]['conditions'], [PUBLIC])
                    self.assertEqual(decisions[1]['conditions'], [second])
                    self.assertEqual(portable['assessment']['lineage'][0]['resolution'], decisions)
        self.assertEqual(before, {p.relative_to(run): p.read_bytes() for p in run.rglob('*') if p.is_file()})

    def test_legacy_v2_full_and_brief_deliver_equal_visible_conditions(self):
        self.assert_deliverable(PUBLIC)

    def test_legacy_v2_full_and_brief_deliver_literal_old_projection(self):
        self.assert_deliverable(OLD_PUBLIC)
