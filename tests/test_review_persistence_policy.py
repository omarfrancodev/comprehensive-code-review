import unittest
import contextlib
import io
import json
from pathlib import Path
import tempfile

from script_test_support import enable_package_imports

enable_package_imports()
from ccr.workflow import persistence
from ccr.cli import artifacts


def facts():
    return {'inputs_pinned': True, 'scope_identified': True, 'requirements_known': True,
            'consumers_known': True, 'bounded_flows': True, 'evidence_preservable': True,
            'privacy_preservable': True, 'full_archive_required': False,
            'granular_recovery_required': False, 'independent_verification_required': False,
            'discovery_assignments': 1}


class PersistencePolicyTests(unittest.TestCase):
    def test_fully_observed_bounded_review_is_compact(self):
        self.assertEqual(persistence.select_persistence(facts())['mode'], 'compact')

    def test_scope_type_and_delivery_do_not_change_selection(self):
        for scope in ('pr', 'mr', 'commit', 'range', 'staged', 'unstaged', 'working', 'module', 'feature'):
            for delivery in ('brief', 'full', None):
                observed = dict(facts(), scope_mode=scope, delivery=delivery)
                with self.subTest(scope=scope, delivery=delivery):
                    self.assertEqual(persistence.select_persistence(observed)['mode'], 'compact')

    def test_unknown_or_false_required_facts_choose_full(self):
        for key in ('inputs_pinned', 'scope_identified', 'requirements_known', 'consumers_known',
                    'bounded_flows', 'evidence_preservable', 'privacy_preservable'):
            for value in (False, None, 'true'):
                observed = facts()
                observed[key] = value
                with self.subTest(key=key, value=value):
                    self.assertEqual(persistence.select_persistence(observed)['mode'], 'full')
            observed = facts()
            del observed[key]
            self.assertEqual(persistence.select_persistence(observed)['mode'], 'full')

    def test_full_obligations_and_missing_observations_choose_full(self):
        for key in ('full_archive_required', 'granular_recovery_required', 'independent_verification_required'):
            for value in (True, None, 'false'):
                observed = facts()
                observed[key] = value
                self.assertEqual(persistence.select_persistence(observed)['mode'], 'full')
        for count in (0, 2, None, True):
            observed = facts()
            observed['discovery_assignments'] = count
            self.assertEqual(persistence.select_persistence(observed)['mode'], 'full')

    def test_result_has_explanatory_reason_and_no_mutation(self):
        observed = facts()
        before = dict(observed)
        result = persistence.select_persistence(observed)
        self.assertEqual(set(result), {'mode', 'reason'})
        self.assertTrue(result['reason'].strip())
        self.assertEqual(observed, before)
        self.assertEqual(persistence.select_persistence(None)['mode'], 'full')

    def test_new_obligation_promotes_but_full_never_silently_downgrades(self):
        selection = {'mode': 'compact', 'reason': 'Acotado'}
        self.assertEqual(persistence.promotion_decision(selection, facts())['mode'], 'compact')
        observed = facts()
        observed['independent_verification_required'] = True
        self.assertEqual(persistence.promotion_decision(selection, observed)['mode'], 'full')
        self.assertEqual(persistence.promotion_decision({'mode': 'full', 'reason': 'Obligatorio'}, facts())['mode'], 'full')
        with self.assertRaises(ValueError):
            persistence.promotion_decision({'mode': 'unknown', 'reason': 'x'}, facts())

    def test_cli_selects_automatically_from_observed_facts(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'facts.json'
            source.write_text(json.dumps(facts()), encoding='utf-8')
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = artifacts.main(['select-persistence', '--facts-input', str(source)])
            self.assertEqual(result, 0)
            self.assertEqual(json.loads(output.getvalue())['mode'], 'compact')


if __name__ == '__main__':
    unittest.main()
