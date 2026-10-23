"""Dispatch stable review-helper areas without importing their services for help."""
from importlib import import_module
import argparse
import sys


AREAS = {
    'artifacts': 'ccr.cli.artifacts',
    'contract': 'ccr.cli.contract',
    'delivery': 'ccr.cli.delivery',
    'history': 'ccr.cli.history',
    'metrics': 'ccr.cli.metrics',
    'packets': 'ccr.cli.packets',
    'recovery': 'ccr.cli.recovery',
    'runner': 'ccr.cli.runner',
    'workspace': 'ccr.cli.workspace',
    'setup': 'ccr.cli.setup',
    'checks': 'ccr.cli.checks',
    'comment': 'ccr.cli.comment',
}


def _parser():
    parser = argparse.ArgumentParser(
        prog='ccr',
        description='Run one review helper area. Use "ccr AREA --help" for area options.',
    )
    parser.add_argument('area', choices=tuple(AREAS))
    return parser


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    parser = _parser()
    if not args:
        parser.print_usage(sys.stderr)
        print('ccr: error: the following arguments are required: area', file=sys.stderr)
        return 2
    if args[0] in ('-h', '--help'):
        parser.print_help()
        return 0
    area = args[0]
    if area not in AREAS:
        parser.error(f"argument area: invalid choice: {area!r} (choose from {', '.join(repr(item) for item in AREAS)})")
    module = import_module(AREAS[area])
    return module.main(args[1:], prog=f'ccr {area}')
