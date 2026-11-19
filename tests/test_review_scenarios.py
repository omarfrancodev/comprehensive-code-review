"""Executable ground truth for evaluation artifacts; these are not model scores."""
import json
from pathlib import Path
import unittest


CASES = {case['id']: case for case in json.loads(
    (Path(__file__).parent / 'fixtures' / 'review_inputs.json').read_text(encoding='utf-8'))['cases']}


def load_case(identifier, version):
    namespace = {}
    exec(compile(CASES[identifier][version], identifier + '-' + version + '.py', 'exec'), namespace)
    exec(compile(CASES[identifier]['consumer'], identifier + '-consumer.py', 'exec'), namespace)
    return namespace


class ScenarioGroundTruthTests(unittest.TestCase):
    def test_response_regression_fails_only_after_change(self):
        before = load_case('response-contract', 'before')
        self.assertEqual(before['navigate'](before['create']), '/objects/7')
        after = load_case('response-contract', 'after')
        with self.assertRaises(KeyError):
            after['navigate'](after['create'])

    def test_normalization_is_a_compatible_clean_change(self):
        for version in ('before', 'after'):
            functions = load_case('normalization-control', version)
            self.assertEqual(functions['navigate'](functions['create']), '/objects/7')
            for name in ('', '   '):
                with self.assertRaises(ValueError):
                    functions['create'](name)
        after = load_case('normalization-control', 'after')
        self.assertEqual(after['create'](' demo ')['name'], 'demo')

    def test_timeout_change_matches_requirement_but_not_description(self):
        for version, expected in (('before', 10), ('after', 20)):
            functions = load_case('description-only', version)
            self.assertEqual(functions['timeout'](), expected)
            self.assertEqual(functions['configured'](functions['timeout']), 5)


    def test_wrapped_integer_identifier_still_supports_the_consumer(self):
        for version in ('before', 'after'):
            functions = load_case('future-contract', version)
            self.assertEqual(functions['navigate'](functions['read']), '/objects/7')

    def test_accepted_duplicates_are_observable_with_writes_disabled(self):
        for version in ('before', 'after'):
            functions = load_case('accepted-residual', version)
            self.assertEqual(functions['observe'](functions['dispatch']), [7, 7])
        with self.assertRaisesRegex(ValueError, 'read-only'):
            functions['dispatch']([{'id': 7, 'kind': 'write'}])


if __name__ == '__main__':
    unittest.main()
