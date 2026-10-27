"""Architecture boundaries for durable reporting and public comments."""
import unittest

from publication_fixtures import coverage_classification

from script_test_support import enable_package_imports
enable_package_imports()


class ScriptReportingBoundaryTests(unittest.TestCase):
    def test_renderer_does_not_import_delivery_or_comment_io(self):
        from script_test_support import module_dependencies
        dependencies = module_dependencies('ccr.reporting.render')
        self.assertFalse(dependencies & {'ccr.reporting.delivery', 'ccr.reporting.comment'})

    def test_edited_public_body_is_not_canonical(self):
        from publication_fixtures import publication_record, check_classification
        from ccr.reporting.comment import prepare_public_comment, verify_public_comment
        record = publication_record()
        draft = prepare_public_comment(
            record, check_publication_context=check_classification(record), coverage_publication_context=coverage_classification(record))
        self.assertTrue(verify_public_comment(record, draft, draft['body'])['verified'])
        with self.assertRaisesRegex(ValueError, 'body_mismatch'):
            verify_public_comment(record, draft, draft['body'] + 'edited')


if __name__ == '__main__':
    unittest.main()
