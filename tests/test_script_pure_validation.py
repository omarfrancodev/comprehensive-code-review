"""Pure-validation contract boundaries for extracted CCR packages."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))


class PureValidationBoundaryTests(unittest.TestCase):
    def test_preflight_does_not_execute_a_command(self):
        from ccr.contracts.preflight import validate_preflight
        with patch('subprocess.run', side_effect=AssertionError('unexpected process')):
            result = validate_preflight(phase='prepare', manifest=None,
                logical_scope=None, selection=None, context=None, record=None, sources={})
        self.assertEqual(result['phase'], 'prepare')
        self.assertFalse(result['ready'])
        self.assertEqual(set(result['issues'][0]), {'code', 'field', 'reference', 'message', 'expected'})

    def test_reference_resolution_uses_only_supplied_bytes(self):
        from ccr.contracts.references import parse_reference, resolve_reference
        sources = {'evidence/context.json': b'{"profile":"focused"}'}
        self.assertEqual(resolve_reference('evidence/context.json#profile', sources, field='profile'), 'focused')
        with self.assertRaises(ValueError):
            parse_reference('../context.json', field='profile')


if __name__ == '__main__':
    unittest.main()
