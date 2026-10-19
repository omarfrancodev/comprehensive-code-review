"""Synthetic scope factories shared by archive layout tests."""
import copy


def native_scope(mode='mr', **overrides):
    scope = {'repository': 'https://git.example/acme/api', 'mode': mode,
             'base': 'def9876543210', 'head': 'abc1234567890', 'snapshot': None,
             'target': 'develop', 'reference': 'https://git.example/acme/api/merge_requests/1010'}
    scope.update(overrides)
    return scope


def selector_input(mode='module', **overrides):
    if mode in ('module', 'feature'):
        selector = {'reference': 'feature/file-cleanup', 'boundaries': ['src/a']}
    elif mode in ('working', 'staged', 'unstaged'):
        selector = {'boundaries': []}
    else:
        raise ValueError('explicit fixture selectors are defined for module/feature/local scopes')
    selector.update(overrides)
    return {'mode': mode, 'selector': copy.deepcopy(selector)}
