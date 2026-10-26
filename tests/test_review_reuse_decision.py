"""A prior result alone never authorizes reuse of current changes."""
import unittest
from test_review_effective_changes import descriptor
from test_review_reuse_context import context_fixture
from ccr.workflow.reuse import decide_reuse, compare_review_context
from ccr.contracts.effective_changes import compare_effective_changes
from ccr.workflow.inputs import compare_inputs


class ReuseDecisionTests(unittest.TestCase):
    def decide(self, code='equivalent', context='applicable', prior=True, ready=True):
        return decide_reuse(dict(code_equivalence=code,reasons=[],changed_paths=[],metadata_only=False),
            dict(applicability=context,reasons=[]),has_prior=prior,current_scope_ready=ready)

    def test_only_equivalent_and_applicable_offers_choice(self):
        self.assertEqual(self.decide()['action'],'offer_choice')
        for code in ('equivalent','different','unknown'):
            for context in ('applicable','changed','unknown'):
                if (code,context) != ('equivalent','applicable'):
                    self.assertEqual(self.decide(code,context)['action'],'new_review')

    def test_no_prior_starts_review_and_missing_current_scope_blocks(self):
        self.assertEqual(self.decide(prior=False)['action'],'new_review')
        self.assertEqual(self.decide(ready=False)['action'],'blocked_current_scope')

    def test_exact_recovery_remains_changed_when_code_is_equivalent(self):
        old,new = context_fixture(),context_fixture()
        new['scope']['head']='new-head'
        old_inputs = dict(scope=old['scope'],sources={},source_set_complete=True)
        new_inputs = dict(scope=new['scope'],sources={},source_set_complete=True)
        self.assertEqual(compare_inputs(old_inputs,new_inputs)['applicability'],'changed')
        code = compare_effective_changes(descriptor(),descriptor())
        context = compare_review_context(old,new)
        self.assertEqual(decide_reuse(code,context,has_prior=True,current_scope_ready=True)['action'],'offer_choice')

    def test_invalid_states_do_not_silently_offer_reuse(self):
        with self.assertRaises(ValueError):
            self.decide(code='equal-ish')


if __name__=='__main__':
    unittest.main()
