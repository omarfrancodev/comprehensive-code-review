"""Test-only helpers for characterizing the standalone review scripts."""
from __future__ import annotations

import argparse
import ast
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch


SCRIPTS_ROOT = Path(__file__).resolve().parents[1] / 'scripts'
LEGACY_CLI_MODULES = {
    'artifacts': 'review_artifacts',
    'contract': 'review_contract',
    'delivery': 'review_delivery',
    'history': 'review_history',
    'metrics': 'review_metrics',
    'packets': 'review_packets',
    'recovery': 'review_recovery',
    'runner': 'review_runner',
    'workspace': 'review_workspace',
    'setup': 'review_setup',
    'checks': 'review_check_receipts',
    'comment': 'review_comment',
}
LEGACY_ENCODERS = {
    'manifest': ('review_artifacts', '_json_bytes'),
    'layout': ('review_layout', '_canonical'),
    'restart': ('review_restart', '_json'),
    'trace': ('review_trace', 'encoded'),
    'receipt': ('review_check_receipts', '_json_bytes'),
    'setup': ('review_setup', '_json_bytes'),
}


class _StopAtParser(BaseException):
    """Escape a CLI immediately after its ArgumentParser has been built."""


def enable_package_imports() -> None:
    """Add the skill's scripts directory to sys.path for tests only."""
    scripts = str(SCRIPTS_ROOT)
    if scripts not in sys.path:
        sys.path.insert(0, scripts)


def _portable_value(value):
    if value is argparse.SUPPRESS:
        return '<argparse.SUPPRESS>'
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [_portable_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _portable_value(item) for key, item in value.items()}
    if callable(value):
        return getattr(value, '__name__', type(value).__name__)
    return repr(value)


def _parser_inventory(parser: argparse.ArgumentParser) -> dict:
    groups = []
    action_groups = {}
    for group_index, group in enumerate(parser._mutually_exclusive_groups):
        groups.append({
            'required': group.required,
            'actions': [action.dest for action in group._group_actions],
        })
        for action in group._group_actions:
            action_groups.setdefault(id(action), []).append(group_index)

    actions = []
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            choices = list(action.choices)
        else:
            choices = _portable_value(action.choices)
        row = {
            'kind': type(action).__name__,
            'options': list(action.option_strings),
            'dest': action.dest,
            'nargs': _portable_value(action.nargs),
            'required': bool(getattr(action, 'required', False)),
            'default': _portable_value(action.default),
            'type': _portable_value(action.type),
            'choices': choices,
            'const': _portable_value(getattr(action, 'const', None)),
            'metavar': _portable_value(action.metavar),
            'help': _portable_value(action.help),
            'mutex_groups': action_groups.get(id(action), []),
        }
        if isinstance(action, argparse._SubParsersAction):
            row['subparsers'] = {
                name: _parser_inventory(child)
                for name, child in action.choices.items()
            }
        actions.append(row)
    return {
        'description': parser.description,
        'defaults': _portable_value(parser._defaults),
        'actions': actions,
        'mutually_exclusive_groups': groups,
    }


def _cli_module(area: str) -> str:
    if area not in LEGACY_CLI_MODULES:
        raise ValueError(f'unknown CLI area: {area}')
    if (SCRIPTS_ROOT / f'{LEGACY_CLI_MODULES[area]}.py').is_file():
        return LEGACY_CLI_MODULES[area]
    return f'ccr.cli.{area}'


def _capture_parser(area: str) -> dict:
    enable_package_imports()
    module_name = _cli_module(area)
    module = importlib.import_module(module_name)
    captured = []

    def stop_at_parse(parser, *args, **kwargs):
        captured.append(parser)
        raise _StopAtParser()

    old_argv = sys.argv
    sys.argv = [module_name, '--help']
    try:
        with patch.object(argparse.ArgumentParser, 'parse_args', stop_at_parse), \
                patch.object(argparse.ArgumentParser, 'parse_known_args', stop_at_parse):
            try:
                if module_name.startswith('ccr.cli.'):
                    module.main(['--help'], prog=f'ccr {area}')
                else:
                    module.main()
            except _StopAtParser:
                pass
    finally:
        sys.argv = old_argv
    if len(captured) != 1:
        raise RuntimeError(f'{module_name} built {len(captured)} argument parsers')
    return _parser_inventory(captured[0])


def cli_inventory() -> dict:
    """Inspect each real CLI parser without executing its selected operation."""
    return {area: _capture_parser(area) for area in LEGACY_CLI_MODULES}


def run_cli(area: str, argv: list[str], *, cwd: Path) -> subprocess.CompletedProcess:
    """Run one legacy CLI directly; after Task 12 route through scripts/__main__.py."""
    module_name = _cli_module(area)
    if module_name.startswith('ccr.cli.'):
        command = [sys.executable, '-B', str(SCRIPTS_ROOT), area, *argv]
    else:
        script = SCRIPTS_ROOT / f'{module_name}.py'
        command = [sys.executable, '-B', str(script), *argv]
    return subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding='utf-8',
        check=False,
    )


def encoding_inventory() -> dict:
    """Return the original encoder bytes for one fixed JSON value as hex."""
    value = {'x': 1, 'ñ': 'café'}
    if (SCRIPTS_ROOT / 'review_artifacts.py').is_file():
        encoders = {
            role: getattr(importlib.import_module(module), name)
            for role, (module, name) in LEGACY_ENCODERS.items()
        }
    else:
        encoding = importlib.import_module('ccr.shared.encoding')
        encoders = {
            'manifest': encoding.archive_bytes,
            'layout': encoding.compact_bytes,
            'restart': encoding.compact_bytes,
            'trace': encoding.compact_bytes,
            'receipt': encoding.receipt_bytes,
            'setup': encoding.compact_bytes,
        }
    return {role: encoders[role](value).hex() for role in LEGACY_ENCODERS}


def _module_path(module: str | Path) -> tuple[str, Path]:
    candidate = Path(module)
    if candidate.is_absolute():
        path = candidate.resolve()
        relative = path.relative_to(SCRIPTS_ROOT.resolve())
    else:
        text = str(module).replace('\\', '/')
        if text.endswith('.py') or '/' in text:
            relative = Path(text)
            if relative.parts and relative.parts[0] == 'scripts':
                relative = Path(*relative.parts[1:])
            path = SCRIPTS_ROOT / relative
        else:
            relative = Path(*text.split('.'))
            path = SCRIPTS_ROOT / relative
            if not path.is_file() and not path.with_suffix('.py').is_file():
                path = path / '__init__.py'
            elif path.suffix != '.py':
                path = path.with_suffix('.py')
    if path.suffix != '.py' and path.name != '__init__.py':
        path = path.with_suffix('.py')
    if path.name == '__init__.py':
        module_name = '.'.join(path.parent.relative_to(SCRIPTS_ROOT).parts)
    else:
        module_name = '.'.join(path.relative_to(SCRIPTS_ROOT).with_suffix('').parts)
    if not path.is_file():
        raise FileNotFoundError(path)
    return module_name, path


def _local_module_exists(module_name: str) -> bool:
    if not module_name:
        return False
    path = SCRIPTS_ROOT.joinpath(*module_name.split('.'))
    return path.with_suffix('.py').is_file() or (path / '__init__.py').is_file()


def module_dependencies(module: str) -> set[str]:
    """Read local Python dependencies from AST without importing the target."""
    module_name, path = _module_path(module)
    tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    is_package = path.name == '__init__.py'
    package_parts = module_name.split('.') if is_package else module_name.split('.')[:-1]
    dependencies = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _local_module_exists(alias.name):
                    dependencies.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                keep = max(0, len(package_parts) - node.level + 1)
                base_parts = package_parts[:keep]
                if node.module:
                    base_parts.extend(node.module.split('.'))
                base = '.'.join(base_parts)
            else:
                base = node.module or ''
            if _local_module_exists(base):
                dependencies.add(base)
            for alias in node.names:
                if alias.name == '*':
                    continue
                candidate = f'{base}.{alias.name}' if base else alias.name
                if _local_module_exists(candidate):
                    dependencies.add(candidate)
    dependencies.discard(module_name)
    return dependencies


def owned_check_request(root: Path, *, exit_code: int = 0) -> dict:
    """Create a real owned workspace and a request for one explicit check."""
    import shlex
    from ccr.execution import workspaces

    root = Path(root).resolve()
    repo = root / 'repo'
    repo.mkdir(parents=True)
    env = {key: value for key, value in os.environ.items()
           if not key.upper().startswith('GIT_')}
    env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull,
               GIT_CONFIG_NOSYSTEM='1')

    def git(*args):
        result = subprocess.run(['git', *args], cwd=repo, env=env,
                                capture_output=True, text=True, encoding='utf-8')
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or 'Git fixture setup failed')
        return result.stdout.strip()

    git('init', '-q')
    git('config', 'user.name', 'Fixture Reviewer')
    git('config', 'user.email', 'fixture@example.invalid')
    (repo / 'product.py').write_text('answer = 42\n', encoding='utf-8')
    git('add', 'product.py')
    git('commit', '-qm', 'fixture baseline')
    manifest = workspaces.prepare(argparse.Namespace(
        repo=str(repo), mode='commit', ref='HEAD', role=['executor'],
        include_untracked=[]))
    session_dir = Path(manifest['session_dir'])
    evidence_dir = session_dir / 'evidence'
    evidence_dir.mkdir()
    cwd = Path(manifest['workspaces'][0]['path'])
    revision = workspaces.out(cwd, 'rev-parse', 'HEAD').decode('utf-8').strip()
    (evidence_dir / 'context.json').write_text(json.dumps({
        'executors': [{'executor': 'X1', 'workspace': str(cwd)}]
    }), encoding='utf-8')
    argv = [sys.executable, '-c', f'raise SystemExit({int(exit_code)})']
    return {'check_id': 'C001', 'argv': argv, 'command': shlex.join(argv),
            'cwd': str(cwd), 'executor_workspace': str(cwd), 'revision': revision,
            'executor': 'X1', 'output_dir': str(evidence_dir / 'attempt-1')}
