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
from types import SimpleNamespace
from unittest.mock import patch


SCRIPTS_ROOT = Path(__file__).resolve().parents[1] / 'scripts'
CLI_AREAS = {
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
ENCODERS = {
    'manifest': 'archive_bytes',
    'layout': 'compact_bytes',
    'restart': 'compact_bytes',
    'trace': 'compact_bytes',
    'receipt': 'receipt_bytes',
    'setup': 'compact_bytes',
}


class _StopAtParser(BaseException):
    """Escape a CLI immediately after its ArgumentParser has been built."""


def enable_package_imports() -> None:
    """Add the skill's scripts directory to sys.path for tests only."""
    scripts = str(SCRIPTS_ROOT)
    if scripts not in sys.path:
        sys.path.insert(0, scripts)


def owner_api(*module_names: str, aliases: dict[str, str] | None = None) -> SimpleNamespace:
    """Build a test namespace from explicit domain owners, without importing a script facade."""
    enable_package_imports()
    namespace = SimpleNamespace()
    modules = {name: importlib.import_module(name) for name in module_names}
    for module in modules.values():
        for name, value in vars(module).items():
            if not name.startswith('__') and not hasattr(namespace, name):
                setattr(namespace, name, value)
    for alias, target in (aliases or {}).items():
        setattr(namespace, alias, modules[target])
    namespace.__file__ = str(SCRIPTS_ROOT / '__main__.py')
    return namespace


def archive_api() -> SimpleNamespace:
    """Collect the archive APIs used by historical tests from their current owners."""
    namespace = owner_api(
        'ccr.shared.encoding', 'ccr.shared.json_io', 'ccr.shared.git', 'ccr.shared.paths',
        'ccr.contracts.review', 'ccr.contracts.identifiers', 'ccr.contracts.validation',
        'ccr.contracts.scope', 'ccr.contracts.preflight', 'ccr.contracts.references',
        'ccr.contracts.execution', 'ccr.contracts.provenance', 'ccr.contracts.claims',
        'ccr.contracts.receipts', 'ccr.contracts.model_usage', 'ccr.contracts.reference_index',
        'ccr.contracts.semantic_references', 'ccr.archive.layout', 'ccr.archive.reader',
        'ccr.archive.integrity', 'ccr.archive.transactions', 'ccr.archive.evidence',
        'ccr.archive.checkpoints', 'ccr.archive.lifecycle', 'ccr.archive.retention',
        'ccr.archive.resources', 'ccr.archive.restart_contract', 'ccr.archive.restart_state',
        'ccr.archive.restart', 'ccr.archive.coordination', 'ccr.archive.restart_observations',
        'ccr.archive.inspection', 'ccr.archive.lookup', 'ccr.archive.history',
        'ccr.archive.trace', 'ccr.workflow.profiles', 'ccr.workflow.inputs',
        'ccr.workflow.builders', 'ccr.execution.claims', 'ccr.execution.workspaces',
        'ccr.execution.locks', 'ccr.execution.harness', 'ccr.execution.candidates',
        'ccr.execution.workspace_manifest', 'ccr.execution.checks', 'ccr.execution.runner',
        'ccr.reporting.markdown', 'ccr.reporting.projections', 'ccr.reporting.render',
        'ccr.reporting.delivery', 'ccr.reporting.comment', 'ccr.maintenance.metrics',
        aliases={
            'review_contract': 'ccr.contracts.review',
            'review_profiles': 'ccr.workflow.profiles',
            'review_trace': 'ccr.archive.trace',
            'review_layout': 'ccr.archive.layout',
            'review_model_usage': 'ccr.contracts.model_usage',
            'review_inputs': 'ccr.workflow.inputs',
            'review_references': 'ccr.contracts.references',
            'review_preflight': 'ccr.contracts.preflight',
            'review_check_receipts': 'ccr.contracts.receipts',
            'review_execution': 'ccr.contracts.execution',
            'review_check_provenance': 'ccr.contracts.provenance',
            'review_resource_claims': 'ccr.execution.claims',
            'review_restart': 'ccr.archive.restart_contract',
            'review_metrics': 'ccr.maintenance.metrics',
            'review_workspace': 'ccr.execution.workspaces',
            'review_run_lock': 'ccr.execution.locks',
            'review_harness': 'ccr.execution.harness',
        },
    )
    namespace.validate = importlib.import_module('ccr.archive.lifecycle').validate
    namespace.prepare = importlib.import_module('ccr.archive.lifecycle').prepare
    namespace.register = importlib.import_module('ccr.archive.lifecycle').register
    namespace.retain = importlib.import_module('ccr.archive.retention').retain
    namespace.close = importlib.import_module('ccr.archive.lifecycle').close
    namespace._json_bytes = importlib.import_module('ccr.shared.encoding').archive_bytes
    namespace.preflight_run = importlib.import_module('ccr.cli.artifacts').preflight_run
    namespace.review_contract = owner_api(
        'ccr.contracts.review', 'ccr.contracts.identifiers', 'ccr.reporting.render')
    namespace.profile_execution = owner_api('ccr.workflow.profiles', 'ccr.contracts.execution')
    return namespace


def recovery_api() -> SimpleNamespace:
    return owner_api('ccr.archive.inspection', 'ccr.archive.lookup', 'ccr.archive.history',
                     'ccr.archive.layout', 'ccr.workflow.inputs',
                     aliases={'review_layout': 'ccr.archive.layout',
                              'review_inputs': 'ccr.workflow.inputs'})


def workspace_api() -> SimpleNamespace:
    namespace = owner_api('ccr.execution.workspaces', 'ccr.archive.resources')
    namespace.record_artifact = importlib.import_module('ccr.archive.resources').record_artifact
    namespace.workspace_ops = importlib.import_module('ccr.execution.workspaces')
    namespace.cleanup = importlib.import_module('ccr.archive.resources').cleanup_workspace
    return namespace


def contract_api() -> SimpleNamespace:
    return owner_api('ccr.contracts.review', 'ccr.contracts.identifiers', 'ccr.reporting.render')


def setup_api() -> SimpleNamespace:
    return owner_api('ccr.workflow.builders', 'ccr.workflow.setup',
                     'ccr.execution.candidates')


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
    if area not in CLI_AREAS:
        raise ValueError(f'unknown CLI area: {area}')
    return CLI_AREAS[area]


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
    return {area: _capture_parser(area) for area in CLI_AREAS}


def run_cli(area: str, argv: list[str], *, cwd: Path) -> subprocess.CompletedProcess:
    """Run one CLI area through the scripts package dispatcher."""
    if area not in CLI_AREAS:
        raise ValueError(f'unknown CLI area: {area}')
    command = [sys.executable, '-B', str(SCRIPTS_ROOT), area, *argv]
    return subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding='utf-8',
        check=False,
    )


def encoding_inventory() -> dict:
    """Return the owner encoder bytes for one fixed JSON value as hex."""
    value = {'x': 1, 'ñ': 'café'}
    encoding = importlib.import_module('ccr.shared.encoding')
    encoders = {role: getattr(encoding, name) for role, name in ENCODERS.items()}
    return {role: encoders[role](value).hex() for role in ENCODERS}


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


def _implementation_modules(scripts_root: Path) -> dict[str, Path]:
    scripts_root = Path(scripts_root).resolve()
    modules = {}
    for path in scripts_root.rglob('*.py'):
        relative = path.relative_to(scripts_root)
        if path.name == '__init__.py':
            module_name = '.'.join(relative.parent.parts)
        else:
            module_name = '.'.join(relative.with_suffix('').parts)
        modules[module_name] = path
    return modules


def _local_imports(tree: ast.AST, module_name: str, is_package: bool,
                   modules: dict[str, Path]) -> set[str]:
    package_parts = module_name.split('.') if is_package else module_name.split('.')[:-1]
    dependencies = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in modules:
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
            if base in modules:
                dependencies.add(base)
            for alias in node.names:
                if alias.name == '*':
                    continue
                candidate = f'{base}.{alias.name}' if base else alias.name
                if candidate in modules:
                    dependencies.add(candidate)
    dependencies.discard(module_name)
    return dependencies


def import_graph(scripts_root: Path) -> dict[str, set[str]]:
    """Resolve local Python imports and the fixed CLI registry from source ASTs."""
    modules = _implementation_modules(scripts_root)
    graph = {}
    for module_name, path in modules.items():
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        graph[module_name] = _local_imports(
            tree, module_name, path.name == '__init__.py', modules)

    main_path = modules.get('ccr.cli.main')
    if main_path is not None:
        tree = ast.parse(main_path.read_text(encoding='utf-8'), filename=str(main_path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                if not any(isinstance(target, ast.Name) and target.id == 'AREAS'
                           for target in targets):
                    continue
                try:
                    areas = ast.literal_eval(node.value)
                except (ValueError, TypeError):
                    continue
                if isinstance(areas, dict):
                    graph['ccr.cli.main'].update(
                        target for target in areas.values()
                        if isinstance(target, str) and target in modules)
                break
    return {name: graph[name] for name in sorted(graph)}


def cyclic_components(graph: dict[str, set[str]]) -> list[tuple[str, ...]]:
    """Return sorted strongly connected components that contain a cycle."""
    nodes = set(graph)
    nodes.update(dependency for dependencies in graph.values() for dependency in dependencies)
    next_index = 0
    indices = {}
    lowlinks = {}
    stack = []
    on_stack = set()
    cycles = []

    def visit(node: str) -> None:
        nonlocal next_index
        indices[node] = lowlinks[node] = next_index
        next_index += 1
        stack.append(node)
        on_stack.add(node)
        for dependency in sorted(graph.get(node, set())):
            if dependency not in indices:
                visit(dependency)
                lowlinks[node] = min(lowlinks[node], lowlinks[dependency])
            elif dependency in on_stack:
                lowlinks[node] = min(lowlinks[node], indices[dependency])
        if lowlinks[node] == indices[node]:
            component = []
            while True:
                member = stack.pop()
                on_stack.remove(member)
                component.append(member)
                if member == node:
                    break
            component = tuple(sorted(component))
            if len(component) > 1 or node in graph.get(node, set()):
                cycles.append(component)

    for node in sorted(nodes):
        if node not in indices:
            visit(node)
    return sorted(cycles)


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
