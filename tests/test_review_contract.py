import copy
import importlib.util
from pathlib import Path
import unittest
import json
import subprocess
import sys
import tempfile


MODULE_PATH = Path(__file__).resolve().parents[1] / 'scripts' / 'review_contract.py'
spec = importlib.util.spec_from_file_location('review_contract', MODULE_PATH)
contract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contract)


def clean_record():
    return {
        'schema_version': 1, 'stage': 'final',
        'scope': {'repository': 'example/service', 'mode': 'pr', 'base': 'base-123',
                  'head': 'head-456', 'snapshot': None, 'target': 'main',
                  'reference': 'https://example.test/pr/12'},
        'profile': 'balanced', 'profile_reason': 'One isolated validation rule',
        'responsible': {'name': 'Ana Perez', 'username': 'ana', 'verified': True,
                        'source': 'PR assignee metadata'},
        'findings': [], 'checks': [],
        'description': {'status': 'aligned', 'identity': 'sha256:description-1',
                        'details': 'Accurately summarizes the changed validation'},
        'coverage': {'adequate': True, 'flows': ['request validation'],
                     'limitations': [], 'verification': 'independent', 'stale': False},
        'verdict': 'approvable', 'verdict_reason': 'No blocking defects confirmed',
        'reservations': [], 'rereview': [], 'aliases': {},
        'resources': {'cleanup': 'not_needed', 'residuals': [], 'publication': 'draft'},
    }


def finding(status='confirmed', blocking=False, kind='code'):
    return {
        'id': 'R001', 'type': kind, 'status': status, 'priority': 'P2',
        'blocking': blocking, 'blocking_reason': 'Required contract breaks' if blocking else None,
        'origin': 'introduced', 'title': 'Removed response field breaks consumer',
        'location': {'path': 'src/api.py', 'line': 12, 'url': None, 'section': None}
        if kind == 'code' else {'path': None, 'line': None, 'url': None, 'section': 'PR description'},
        'scenario': 'Existing consumer reads response id; field is absent',
        'impact': 'Consumer cannot navigate to the created object',
        'evidence': [{'kind': 'static', 'details': 'Producer omits id; consumer requires it',
                      'check_id': None}],
        'correction': 'Preserve id or migrate affected consumers',
    }


class ValidationTests(unittest.TestCase):
    def test_aliases_survive_consolidation_and_cannot_chain_or_point_to_unknown_ids(self):
        record = clean_record()
        record['findings'] = [finding()]
        record['aliases'] = {'R002': 'R001'}
        self.assertEqual(contract.validate(record), [])
        record['aliases'] = {'R002': 'missing'}
        self.assertTrue(contract.validate(record))
        record['aliases'] = {'R002': 'R003', 'R003': 'R001'}
        self.assertTrue(contract.validate(record))

    def test_balanced_code_findings_cannot_skip_verification_even_for_p3(self):
        record = clean_record()
        record['coverage']['verification'] = 'skipped'
        item = finding()
        item['priority'] = 'P3'
        record['findings'] = [item]
        self.assertTrue(contract.validate(record))
        record['coverage']['verification'] = 'same_session'
        self.assertEqual(contract.validate(record), [])

    def test_balanced_material_questions_cannot_skip_verification(self):
        record = clean_record()
        record['coverage']['verification'] = 'skipped'
        record['coverage']['limitations'] = [{'detail': 'Required behavior unknown', 'material': True}]
        record['verdict'] = 'insufficient_evidence'
        self.assertTrue(contract.validate(record))
        record['coverage']['verification'] = 'unavailable'
        self.assertEqual(contract.validate(record), [])

    def test_prior_revision_reuse_needs_explicit_unchanged_input_justification(self):
        record = clean_record()
        record['checks'] = [{'id': 'C001', 'command': 'python regression.py', 'revision': 'prior-head',
                             'status': 'passed', 'failure_kind': None, 'evidence': 'Consumer works',
                             'reused': True, 'reuse_reason': 'Only description changed; producer, consumer and fixture hashes unchanged',
                             'rerun_reason': None}]
        self.assertEqual(contract.validate(record), [])
        check = record['checks'][0]
        check['reuse_reason'] = None
        self.assertTrue(contract.validate(record))
        check.update(reused=False, reuse_reason=None)
        self.assertTrue(contract.validate(record))

    def test_malformed_json_types_produce_errors_instead_of_crashing(self):
        variants = [(['scope', 'mode'], []), (['checks'], [{'revision': []}]),
                    (['description', 'status'], {}), (['findings'], [None])]
        for path, value in variants:
            record = clean_record()
            target = record
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            self.assertTrue(contract.validate(record))

    def test_local_edits_require_snapshot_identity_not_only_head(self):
        record = clean_record()
        record['scope'].update(mode='staged', reference=None)
        record['description'] = {'status': 'not_applicable', 'identity': None, 'details': ''}
        self.assertTrue(contract.validate(record))
        record['scope']['snapshot'] = 'captured-staged-hash'
        self.assertEqual(contract.validate(record), [])

    def test_deep_profile_cannot_skip_invariant_verification(self):
        record = clean_record()
        record['profile'] = 'deep'
        record['coverage']['verification'] = 'skipped'
        self.assertTrue(contract.validate(record))
        record['coverage']['verification'] = 'independent'
        self.assertEqual(contract.validate(record), [])
    def test_clean_static_review_is_valid_without_execution(self):
        record = clean_record()
        record['coverage']['verification'] = 'skipped'
        self.assertEqual(contract.validate(record), [])

    def test_missing_field_and_invalid_enum_are_reported(self):
        record = clean_record()
        del record['responsible']
        record['profile'] = 'unlimited'
        errors = contract.validate(record)
        self.assertTrue(any('responsible' in e for e in errors))
        self.assertTrue(any('profile' in e for e in errors))

    def test_duplicate_finding_ids_are_rejected(self):
        record = clean_record()
        record['findings'] = [finding(), finding()]
        self.assertTrue(any('duplicate' in e for e in contract.validate(record)))

    def test_unresolved_claim_cannot_be_blocking_confirmed_defect(self):
        record = clean_record()
        record['findings'] = [finding(status='unresolved', blocking=True)]
        self.assertTrue(any('blocking' in e for e in contract.validate(record)))

    def test_severity_does_not_automatically_make_finding_blocking(self):
        record = clean_record()
        record['findings'] = [finding(blocking=False)]
        self.assertEqual(contract.validate(record), [])

    def test_blocker_requires_not_approvable_verdict(self):
        record = clean_record()
        record['findings'] = [finding(blocking=True)]
        self.assertTrue(any('verdict' in e for e in contract.validate(record)))
        record['verdict'] = 'not_approvable'
        self.assertEqual(contract.validate(record), [])

    def test_material_uncertainty_and_staleness_preclude_approval(self):
        for change in ('stale', 'inadequate', 'material'):
            record = clean_record()
            if change == 'stale':
                record['coverage']['stale'] = True
            elif change == 'inadequate':
                record['coverage']['adequate'] = False
            else:
                record['coverage']['limitations'] = [{'detail': 'Tenant isolation unverified', 'material': True}]
            self.assertTrue(any('verdict' in e for e in contract.validate(record)))
            record['verdict'] = 'insufficient_evidence'
            self.assertEqual(contract.validate(record), [])

    def test_executed_evidence_requires_actual_version_matched_check(self):
        record = clean_record()
        item = finding()
        item['evidence'] = [{'kind': 'executed', 'details': 'Reproduction fails', 'check_id': 'C001'}]
        record['findings'] = [item]
        self.assertTrue(any('check_id' in e for e in contract.validate(record)))
        check = {'id': 'C001', 'command': 'python reproduce.py', 'revision': 'head-456',
                 'status': 'failed', 'failure_kind': 'product', 'evidence': 'Expected id, missing',
                 'reused': False, 'reuse_reason': None, 'rerun_reason': None}
        record['checks'] = [check]
        self.assertEqual(contract.validate(record), [])
        check['revision'] = 'unrelated-old-head'
        self.assertTrue(any('revision' in e for e in contract.validate(record)))

    def test_fixture_failure_or_unexecuted_check_cannot_confirm_product_bug(self):
        for status, failure_kind in [('blocked', None), ('not_run', None), ('failed', 'fixture')]:
            record = clean_record()
            item = finding()
            item['evidence'] = [{'kind': 'executed', 'details': 'Assertion fails', 'check_id': 'C001'}]
            record['findings'] = [item]
            record['checks'] = [{'id': 'C001', 'command': 'python reproduce.py', 'revision': 'head-456',
                                  'status': status, 'failure_kind': failure_kind, 'evidence': 'Setup incomplete',
                                  'reused': False, 'reuse_reason': None, 'rerun_reason': None}]
            self.assertTrue(contract.validate(record))

    def test_description_finding_does_not_require_fake_code_line(self):
        record = clean_record()
        record['findings'] = [finding(kind='description')]
        record['description']['status'] = 'needs_update'
        self.assertEqual(contract.validate(record), [])

    def test_local_scope_has_no_pr_description_requirement(self):
        record = clean_record()
        record['scope']['mode'] = 'staged'
        record['scope']['reference'] = None
        record['scope']['snapshot'] = 'staged-snapshot'
        record['description'] = {'status': 'not_applicable', 'identity': None, 'details': ''}
        self.assertEqual(contract.validate(record), [])

    def test_discovery_packet_is_minimal_and_cannot_publish_confirmed_claims(self):
        final = clean_record()
        packet = {key: final[key] for key in ('schema_version', 'scope', 'findings', 'checks')}
        packet.update(stage='discovery', coverage={'flows': ['validation'], 'limitations': []})
        packet['findings'] = [finding(status='candidate')]
        self.assertEqual(contract.validate(packet), [])
        packet['findings'][0]['status'] = 'confirmed'
        self.assertTrue(contract.validate(packet))

    def test_reservations_and_cleanup_are_consistent(self):
        record = clean_record()
        record['reservations'] = ['Optional consumer not executed; static path covered']
        self.assertTrue(contract.validate(record))
        record['verdict'] = 'approvable_with_reservations'
        self.assertEqual(contract.validate(record), [])
        record['resources']['residuals'] = ['owned/worktree']
        self.assertTrue(contract.validate(record))


class RenderingTests(unittest.TestCase):
    def test_public_validation_omits_internal_workspace_commands(self):
        record = clean_record()
        command = 'python C:/Users/Ana/.worktrees/private-session/reproduction.py'
        record['checks'] = [{'id': 'C001', 'command': command, 'revision': 'head-456',
                             'status': 'passed', 'failure_kind': None, 'evidence': 'Consumer works',
                             'reused': False, 'reuse_reason': None, 'rerun_reason': None}]
        self.assertNotIn('private-session', contract.render(record, audience='comment'))
        self.assertIn(command, contract.render(record, audience='user'))

    def test_reused_validation_discloses_original_execution_revision(self):
        record = clean_record()
        record['checks'] = [{'id': 'C001', 'command': 'python regression.py', 'revision': 'prior-head',
                             'status': 'passed', 'failure_kind': None, 'evidence': 'Consumer works',
                             'reused': True, 'reuse_reason': 'Only description changed', 'rerun_reason': None}]
        output = contract.render(record, audience='comment')
        self.assertIn('prior-head', output)
        self.assertIn('Only description changed', output)

    def test_validation_precedes_conditional_uncertainties(self):
        record = clean_record()
        record['coverage']['limitations'] = [{'detail': 'Optional external system not executed', 'material': False}]
        result = contract.render(record, audience='user')
        self.assertLess(result.index('### Validación'), result.index('### Incertidumbres'))

    def test_local_report_does_not_label_local_reference_as_pr(self):
        record = clean_record()
        record['scope'].update(mode='commit', reference='commit-reference')
        record['description'] = {'status': 'not_applicable', 'identity': None, 'details': ''}
        self.assertNotIn('**MR/PR:**', contract.render(record))
    def test_comment_includes_verified_responsible_description_and_version(self):
        result = contract.render(clean_record(), audience='comment')
        self.assertIn('@ana', result)
        self.assertIn('head-456', result)
        self.assertIn('Descripción', result)

    def test_unknown_identity_never_turns_email_or_name_into_mention(self):
        record = clean_record()
        record['responsible'] = {'name': None, 'username': 'invented', 'verified': False, 'source': None}
        result = contract.render(record, audience='comment')
        self.assertNotIn('@invented', result)
        self.assertIn('No identificado', result)

    def test_clean_comment_keeps_empty_findings_counts_and_omits_internal_mechanics(self):
        result = contract.render(clean_record(), audience='comment')
        self.assertIn('### Hallazgos', result)
        self.assertIn('**Confirmados:** 🔴 P0: 0 · 🟠 P1: 0 · 🟡 P2: 0 · 🔵 P3: 0', result)
        self.assertNotIn('balanced', result)
        self.assertNotIn('Limpieza', result)

    def test_user_report_discloses_profile_verification_and_only_residual_cleanup(self):
        record = clean_record()
        record['coverage']['verification'] = 'skipped'
        result = contract.render(record, audience='user')
        self.assertIn('equilibrado', result)
        self.assertIn('omitida', result)
        self.assertNotIn('### Recursos', result)
        record['resources'].update(cleanup='pending', residuals=['owned/temporary'])
        self.assertIn('owned/temporary', contract.render(record, audience='user'))

    def test_unresolved_claim_is_separate_from_confirmed_findings(self):
        record = clean_record()
        record['findings'] = [finding(status='unresolved')]
        record['coverage']['limitations'] = [{'detail': 'Consumer requirement unknown', 'material': True}]
        record['verdict'] = 'insufficient_evidence'
        output = contract.render(record, audience='comment')
        self.assertNotIn('### Hallazgos confirmados', output)
        self.assertIn('### Incertidumbres', output)

    def test_invalid_record_is_not_rendered_as_a_review(self):
        record = clean_record()
        record['findings'] = [finding(blocking=True)]
        with self.assertRaises(ValueError):
            contract.render(record, audience='comment')


class DeduplicationTests(unittest.TestCase):
    def test_only_explicit_same_cause_groups_preserve_all_scenarios(self):
        first = finding(status='candidate')
        second = copy.deepcopy(first)
        second.update(id='R002', scenario='Second consumer expects the same field')
        third = copy.deepcopy(first)
        third.update(id='R003', title='Different defect in the same file')
        grouped = contract.deduplicate([first, second, third], [['R001', 'R002']])
        self.assertEqual(len(grouped), 2)
        self.assertEqual(grouped[0]['member_ids'], ['R001', 'R002'])
        self.assertEqual(len(grouped[0]['candidates']), 2)
        self.assertEqual(grouped[1]['member_ids'], ['R003'])

    def test_ambiguous_or_overlapping_groups_are_rejected(self):
        first = finding(status='candidate')
        second = copy.deepcopy(first)
        second['id'] = 'R002'
        for groups in ([['R001', 'missing']], [['R001', 'R002'], ['R001']]):
            with self.assertRaises(ValueError):
                contract.deduplicate([first, second], groups)


class CLITests(unittest.TestCase):
    def test_cli_validation_and_unicode_comment(self):
        with tempfile.TemporaryDirectory(prefix='review-contract-') as directory:
            path = Path(directory) / 'record.json'
            path.write_text(json.dumps(clean_record()), encoding='utf-8')
            command = [sys.executable, '-B', str(MODULE_PATH), 'validate', '--input', str(path)]
            result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(json.loads(result.stdout)['valid'])
            item = finding()
            record = clean_record()
            record['findings'] = [item]
            path.write_text(json.dumps(record), encoding='utf-8')
            command[3] = 'render-comment'
            result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('🟡 P2', result.stdout)

    def test_invalid_cli_record_has_failure_exit_and_no_approval_text(self):
        with tempfile.TemporaryDirectory(prefix='review-contract-') as directory:
            path = Path(directory) / 'record.json'
            record = clean_record()
            record['findings'] = [finding(blocking=True)]
            path.write_text(json.dumps(record), encoding='utf-8')
            result = subprocess.run([sys.executable, '-B', str(MODULE_PATH), 'render-comment',
                                     '--input', str(path)], capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, '')


if __name__ == '__main__':
    unittest.main()
