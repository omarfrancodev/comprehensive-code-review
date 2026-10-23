"""Git queries with structural environment variables isolated."""
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import urlsplit

from ccr.shared.paths import safe_path


def git(repo, *args, optional=False):
    structural = {'GIT_DIR', 'GIT_WORK_TREE', 'GIT_COMMON_DIR', 'GIT_INDEX_FILE',
                  'GIT_OBJECT_DIRECTORY', 'GIT_ALTERNATE_OBJECT_DIRECTORIES', 'GIT_NAMESPACE',
                  'GIT_IMPLICIT_WORK_TREE', 'GIT_PREFIX', 'GIT_GRAFT_FILE', 'GIT_SHALLOW_FILE',
                  'GIT_CONFIG', 'GIT_CONFIG_PARAMETERS', 'GIT_CONFIG_COUNT', 'GIT_REPLACE_REF_BASE'}
    environment = {key: value for key, value in os.environ.items() if key.upper() not in structural
                   and not key.upper().startswith(('GIT_CONFIG_KEY_', 'GIT_CONFIG_VALUE_'))}
    environment.update(GIT_OPTIONAL_LOCKS='0', GIT_TERMINAL_PROMPT='0', GIT_NO_REPLACE_OBJECTS='1')
    process = subprocess.run(['git', '-c', 'safe.directory=' + str(repo), *args], cwd=repo,
                             env=environment, capture_output=True, text=True,
                             encoding='utf-8', errors='replace', check=False)
    if process.returncode:
        if optional:
            return None
        raise ValueError('repository cannot be resolved by Git')
    return process.stdout.strip()


def repository_identity(repo):
    """Use normalized origin, or shared common directory for absent/relative origins."""
    repo = safe_path(repo)
    common = git(repo, 'rev-parse', '--git-common-dir')
    common_path = Path(common)
    if not common_path.is_absolute():
        common_path = repo / common_path
    common_identity = 'common-dir:' + os.path.normcase(str(common_path.resolve()))
    remote = git(repo, 'remote', 'get-url', 'origin', optional=True)
    if remote:
        if '://' in remote:
            parsed = urlsplit(remote)
            if parsed.hostname:
                host = parsed.hostname.lower()
                if parsed.port and parsed.port not in (22, 80, 443):
                    host += ':' + str(parsed.port)
                identity = host + '/' + parsed.path.strip('/')
            else:
                identity = str(Path(parsed.path).resolve())
        elif re.match(r'^(?:[^/@:]+@)?[^/:]+:', remote) and not re.match(r'^[A-Za-z]:[\\/]', remote):
            host, name = remote.split(':', 1)
            identity = host.rsplit('@', 1)[-1].lower() + '/' + name.strip('/')
        else:
            # Shared relative configuration is interpreted against different
            # checkout paths by Git; group this repository by its common directory.
            if not Path(remote).is_absolute():
                return common_identity
            identity = os.path.normcase(str(Path(remote).resolve()))
        identity = identity.rstrip('/')
        if identity.endswith('.git'):
            identity = identity[:-4]
        return 'origin:' + identity
    return common_identity
