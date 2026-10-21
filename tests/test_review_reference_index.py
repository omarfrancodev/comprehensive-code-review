"""Semantic and integrity checks for guided retained-reference indexes."""
import hashlib
import json
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ccr.contracts.reference_index import canonical_reference, validate_reference_index
from ccr.contracts.semantic_references import validate_semantic_references
from ccr.contracts.material_inputs import validate_material_inputs
import review_contract
import review_packets
import review_artifacts

from recovery_fixtures import context10, record10


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded_index(index):
    return json.dumps(index, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':')).encode('utf-8')


class ReferenceIndexTests(unittest.TestCase):
    def test_current_c004_is_required_but_external_example_is_not(self):
        record = record10()
        record['coverage']['areas'][0]['details'] = 'Comprobado por C004'
        issues = validate_semantic_references(record, [], None, {})
        self.assertIn('unknown_check', {i['code'] for i in issues})

        record['coverage']['areas'][0]['details'] = 'Inspección estática'
        issues = validate_semantic_references(record, [], None,
            {'evidence/example.py': b'# Example C004'})
        self.assertNotIn('unknown_check', {i['code'] for i in issues})

    def test_typed_check_ids_are_checked_against_current_ledger(self):
        record = record10()
        record['checks'] = [{'id': 'C001'}]
        record['checks'][0].update({'evidence': 'ok'})
        packet = {'check_ids': ['C001', 'C004'], 'findings': [],
                  'decisions': [{'evidence': [{'kind': 'executed', 'check_id': 'C009'}]}]}
        issues = validate_semantic_references(record, [packet], None, {})
        self.assertIn('unknown_check', {i['code'] for i in issues})
        self.assertTrue(any(issue['reference'] in {'C004', 'C009'} for issue in issues))

    def test_contract_and_packet_validators_expose_guided_semantics(self):
        record = record10()
        record['coverage']['execution']['plan'] = []
        record['coverage']['execution']['results'] = []
        record['coverage']['areas'][0]['details'] = 'Comprobado por C004'
        index = {'schema_version': 1, 'aliases': {}, 'inputs': []}
        messages = review_contract.validate_reference_semantics(record, {}, index, {})
        self.assertTrue(any('coverage.areas[0].details' in message
                            and 'typed check reference' in message for message in messages))

        packet = {'packet_version': 1, 'stage': 'discovery', 'context_id': 'ctx',
                  'findings': [{'id': 'X1', 'type': 'code',
                                'location': {'path': 'src/a.py', 'line': 1},
                                'scenario': 'Observed', 'impact': 'Failure',
                                'evidence': [{'kind': 'static', 'details': 'Comprobado por C004'}]}],
                  'check_ids': [], 'coverage': {'flows': [], 'limitations': []}}
        errors = review_packets.validate(packet, reference_index=index,
                                         reference_sources={}, known_check_ids=[])
        self.assertTrue(any('packets[0].findings[0].evidence[0].details' in error
                            and 'typed check reference' in error for error in errors))

    def test_execution_gate_enforces_guided_semantics_but_ignores_external_examples(self):
        record = record10()
        record['schema_version'] = 8
        record['description'] = {'status': 'unverified', 'identity': None,
                                 'details': 'No captured description'}
        context = context10(record)
        index = {'schema_version': 1, 'aliases': {}, 'inputs': []}
        index_bytes = json.dumps(index, sort_keys=True, separators=(',', ':')).encode('utf-8')
        context['reference_index'] = 'evidence/reference-index.json'
        context['review_inputs']['sources'] = {
            'evidence/reference-index.json': digest(index_bytes)}
        context['review_inputs']['description_identity'] = None
        contents = {
            'evidence/reference-index.json': index_bytes,
            'evidence/briefs.json': json.dumps({'D1': {}, 'V1': {}}).encode('utf-8'),
            'evidence/results.json': json.dumps({'D1': {}, 'V1': {}}).encode('utf-8'),
            'evidence/example.py': b'# Example C004; not an executed review assertion',
            'trazabilidad.jsonl': b'',
        }
        contents['evidence/context.json'] = json.dumps(
            context, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        identity = context['review_inputs']['logical_scope_identity']
        manifest = {'schema_version': 8, 'review_inputs': context['review_inputs'],
                    'scope': record['scope'],
                    'profile_history': record['coverage']['execution']['profile_history'],
                    'logical_scope': {'identity': identity},
                    'assignment_registry': context['execution_plan'], 'executors': [], 'hashes': {}}

        with patch.object(review_artifacts, 'validate_execution_sources', return_value=[]):
            review_artifacts._execution_gate(Path('.'), manifest, record, contents)
            record['coverage']['areas'][0]['details'] = 'Coverage references C004'
            with self.assertRaisesRegex(ValueError, 'typed check reference'):
                review_artifacts._execution_gate(Path('.'), manifest, record, contents)

    def test_execution_gate_preserves_initial_profile_through_transition(self):
        for initial_reference in (
                'evidence/context.json#profile_history/0/profile',
                'evidence/context.json#profile'):
            with self.subTest(initial_reference=initial_reference):
                record = record10('deep')
                record['schema_version'] = 8
                record['description'] = {'status': 'unverified', 'identity': None,
                                         'details': 'No captured description'}
                execution = record['coverage']['execution']
                execution['plan'] = []
                execution['results'] = []
                initial = dict(execution['profile_history'][0], profile='focused',
                               reference=initial_reference)
                transition = dict(initial, id='S002', profile='deep',
                                  reference='evidence/context.json#profile_history/1/profile',
                                  phase='discovery', changed_from='focused', event_id='E000003')
                history = [initial, transition]
                execution['profile_history'] = history
                record['profile'] = 'deep'
                context = context10(record)
                context.update(profile='deep', profile_history=history,
                               profile_reference=transition['reference'], execution_plan=[])
                index = {'schema_version': 1, 'aliases': {}, 'inputs': []}
                index_bytes = encoded_index(index)
                context['reference_index'] = 'evidence/reference-index.json'
                context['review_inputs']['sources'] = {
                    'evidence/reference-index.json': digest(index_bytes)}
                contents = {
                    'evidence/reference-index.json': index_bytes,
                    'evidence/briefs.json': b'{}',
                    'evidence/results.json': b'{}',
                    'trazabilidad.jsonl': b'',
                    'evidence/context.json': encoded_index(context),
                }
                manifest = {'schema_version': 8, 'review_inputs': context['review_inputs'],
                            'scope': record['scope'], 'profile_history': history,
                            'logical_scope': {'identity': context['review_inputs']['logical_scope_identity']},
                            'assignment_registry': [], 'executors': [], 'hashes': {}}

                with patch.object(review_artifacts, 'validate_execution_sources', return_value=[]):
                    review_artifacts._execution_gate(Path('.'), manifest, record, contents)

    def test_execution_gate_hashes_captured_alias_at_its_canonical_target(self):
        record = record10()
        record['schema_version'] = 8
        record['description'] = {'status': 'unverified', 'identity': None,
                                 'details': 'No captured description'}
        alias = 'evidence/producer/notes.md'
        canonical = 'evidence/notes.md'
        alias_bytes = b'captured reviewer notes'
        index = {'schema_version': 1, 'aliases': {
            alias: {'reference': canonical, 'sha256': digest(alias_bytes)}}, 'inputs': []}
        index_bytes = json.dumps(index, sort_keys=True, separators=(',', ':')).encode('utf-8')
        context = context10(record)
        context['reference_index'] = 'evidence/reference-index.json'
        context['review_inputs']['sources'] = {
            'evidence/reference-index.json': digest(index_bytes),
            alias: digest(alias_bytes),
        }
        context['review_inputs']['description_identity'] = None
        contents = {
            'evidence/reference-index.json': index_bytes,
            canonical: alias_bytes,
            'evidence/briefs.json': json.dumps({'D1': {}, 'V1': {}}).encode('utf-8'),
            'evidence/results.json': json.dumps({'D1': {}, 'V1': {}}).encode('utf-8'),
            'evidence/example.py': b'# Example C004; not an executed review assertion',
            'trazabilidad.jsonl': b'',
        }
        contents['evidence/context.json'] = json.dumps(
            context, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        identity = context['review_inputs']['logical_scope_identity']
        manifest = {'schema_version': 8, 'review_inputs': context['review_inputs'],
                    'scope': record['scope'],
                    'profile_history': record['coverage']['execution']['profile_history'],
                    'logical_scope': {'identity': identity},
                    'assignment_registry': context['execution_plan'], 'executors': [], 'hashes': {}}

        with patch.object(review_artifacts, 'validate_execution_sources', return_value=[]):
            review_artifacts._execution_gate(Path('.'), manifest, record, contents)

    def test_selected_brief_markdown_links_resolve_against_retained_sources(self):
        record = record10()
        sources = {
            'evidence/briefs.json': b'{"D1":{"detail":"See [the result](results.json#D1)"}}',
            'evidence/results.json': b'{"D1":{"status":"completed"},"V1":{}}',
        }
        self.assertFalse(any(issue['code'] == 'missing_source' for issue in
                             validate_semantic_references(record, [], None, sources)))
        sources['evidence/briefs.json'] = b'{"D1":{"detail":"See [the result](missing.json#D1)"}}'
        self.assertIn('missing_source', {issue['code'] for issue in
                                         validate_semantic_references(record, [], None, sources)})

    def test_renamed_source_requires_matching_original_digest(self):
        data = b'original producer bytes'
        aliases = {'evidence/producer/handler.cs': {
            'reference': 'evidence/producer-handler.cs', 'sha256': digest(data)}}
        index = {'schema_version': 1, 'aliases': aliases, 'inputs': []}
        self.assertEqual(validate_reference_index(index,
            {'evidence/producer-handler.cs': data}), [])
        self.assertEqual(canonical_reference(
            'evidence/producer/handler.cs', aliases), 'evidence/producer-handler.cs')
        self.assertTrue(validate_reference_index(index,
            {'evidence/producer-handler.cs': b'changed'}))

    def test_alias_chains_and_cycles_fail_even_when_digests_match(self):
        sources = {'evidence/a': b'', 'evidence/b': b'', 'evidence/c': b''}
        checksum = digest(b'')
        for aliases in (
                {'evidence/a': {'reference': 'evidence/b', 'sha256': checksum},
                 'evidence/b': {'reference': 'evidence/c', 'sha256': checksum}},
                {'evidence/a': {'reference': 'evidence/b', 'sha256': checksum},
                 'evidence/b': {'reference': 'evidence/a', 'sha256': checksum}}):
            index = {'schema_version': 1, 'aliases': aliases, 'inputs': []}
            issues = validate_reference_index(index, sources)
            self.assertTrue(issues)

    def test_aligned_description_requires_selected_content(self):
        record = record10()
        context = context10(record)
        record['description']['status'] = 'aligned'
        record['description']['identity'] = 'sha256:' + 'a' * 64
        index = {'schema_version': 1, 'aliases': {}, 'inputs': []}
        issues = validate_material_inputs(record, context, index, {})
        self.assertIn('missing_input', {i['code'] for i in issues})

    def test_aligned_description_must_match_selected_content_and_context_identity(self):
        record = record10()
        context = context10(record)
        data = b'captured merge request description'
        checksum = digest(data)
        record['description']['status'] = 'aligned'
        record['description']['identity'] = 'sha256:' + checksum
        context['reference_index'] = 'evidence/reference-index.json'
        index = {'schema_version': 1, 'aliases': {}, 'inputs': [
            {'reference': 'evidence/description.md', 'purpose': 'description',
             'sha256': checksum}]}
        index_bytes = encoded_index(index)
        context['review_inputs']['sources'] = {
            'evidence/reference-index.json': digest(index_bytes),
            'evidence/description.md': checksum}
        sources = {'evidence/reference-index.json': index_bytes,
                   'evidence/description.md': data}
        self.assertEqual(validate_material_inputs(record, context, index, sources), [])

        context['review_inputs']['sources']['evidence/description.md'] = 'b' * 64
        issues = validate_material_inputs(record, context, index, sources)
        self.assertTrue(issues)

    def test_aligned_description_accepts_captured_source_through_validated_alias(self):
        record = record10()
        context = context10(record)
        data = b'captured merge request description'
        checksum = digest(data)
        alias = 'evidence/producer/description.md'
        canonical = 'evidence/description.md'
        record['description']['status'] = 'aligned'
        record['description']['identity'] = 'sha256:' + checksum
        context['reference_index'] = 'evidence/reference-index.json'
        index = {'schema_version': 1, 'aliases': {
            alias: {'reference': canonical, 'sha256': checksum}}, 'inputs': [
            {'reference': canonical, 'purpose': 'description', 'sha256': checksum}]}
        index_bytes = encoded_index(index)
        context['review_inputs']['sources'] = {
            'evidence/reference-index.json': digest(index_bytes), alias: checksum}
        sources = {'evidence/reference-index.json': index_bytes, canonical: data}

        self.assertEqual(validate_material_inputs(record, context, index, sources), [])

        context['review_inputs']['sources'].pop(alias)
        context['review_inputs']['sources']['evidence/unrelated.md'] = checksum
        issues = validate_material_inputs(record, context, index, sources)
        self.assertTrue(any(issue['field'] == 'description' for issue in issues))

    def test_requirements_accept_captured_source_through_validated_alias(self):
        record = record10()
        record['description'] = {'status': 'unverified', 'identity': None,
                                 'details': 'No captured description'}
        context = context10(record)
        data = b'captured requirements'
        checksum = digest(data)
        alias = 'evidence/producer/requirements.md'
        canonical = 'evidence/requirements.md'
        context['review_inputs']['requirements_identity'] = 'sha256:' + checksum
        context['reference_index'] = 'evidence/reference-index.json'
        index = {'schema_version': 1, 'aliases': {
            alias: {'reference': canonical, 'sha256': checksum}}, 'inputs': [
            {'reference': canonical, 'purpose': 'requirements', 'sha256': checksum}]}
        index_bytes = encoded_index(index)
        context['review_inputs']['sources'] = {
            'evidence/reference-index.json': digest(index_bytes), alias: checksum}
        sources = {'evidence/reference-index.json': index_bytes, canonical: data}

        self.assertEqual(validate_material_inputs(record, context, index, sources), [])


if __name__ == '__main__':
    unittest.main()
