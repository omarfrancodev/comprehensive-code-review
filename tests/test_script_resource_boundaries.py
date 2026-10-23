"""Workspace cleanup primitives stay below archive services."""
import unittest


class ResourceBoundaryTests(unittest.TestCase):
    def test_physical_workspace_actions_do_not_import_archive_services(self):
        from script_test_support import module_dependencies

        deps = module_dependencies('ccr.execution.workspaces')
        self.assertFalse(deps & {'ccr.archive.resources', 'ccr.archive.restart', 'ccr.archive.lifecycle'})
        self.assertFalse(any(name.startswith('review_') for name in deps))

    def test_claim_module_exposes_public_cross_module_operations(self):
        import sys
        from script_test_support import SCRIPTS_ROOT
        sys.path.insert(0, str(SCRIPTS_ROOT))
        from ccr.execution import claims
        required = (
            'inspect_workspace', 'read_claim', 'preflight_unbound',
            'normalize_authority', 'make_claim_row', 'encode_claim',
            'digest_claim', 'validate_sidecar',
        )
        self.assertTrue(all(callable(getattr(claims, name, None)) for name in required))


if __name__ == '__main__':
    unittest.main()
