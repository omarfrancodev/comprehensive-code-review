"""Rehome a frozen payload, changing only its native location envelope."""
import hashlib
import json
from pathlib import Path
import zipfile

from script_test_support import enable_package_imports
enable_package_imports()
from ccr.archive import compact, layout
from ccr.shared.encoding import archive_bytes
from ccr.shared.paths import safe_path


FIXTURE = Path(__file__).parent / 'fixtures/pr37_legacy_v2/chained-v1-7f05898.zip'
FIXTURE_SHA256 = '9e0ae5c409e866ddc40879b4897117eb9b7330348036b1ea46945b2ab6f4530e'


def unpack_legacy_v2(root):
    """Preserve every old result/evidence byte; bind owned fixture paths locally."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    root = safe_path(root)
    if hashlib.sha256(FIXTURE.read_bytes()).hexdigest() != FIXTURE_SHA256:
        raise ValueError('legacy fixture digest differs')
    with zipfile.ZipFile(FIXTURE) as saved:
        manifest = json.loads(saved.read('manifest.json'))
        marker = json.loads(saved.read('.review-ownership.json'))
        manifest['request']['archive_root'] = str(root)
        request = manifest['request']
        logical = layout.logical_scope(request['scope'], request['logical_scope_input'])
        run = safe_path(root / compact._repository_group(request['repository_identity'])
                        / layout.scope_group(logical)
                        / layout.run_name(request['scope'], manifest['created_at'], manifest['run_id'],
                                          request['logical_scope_input']))
        run.mkdir(parents=True)
        for name in saved.namelist():
            target = (run / name).resolve()
            if not target.is_relative_to(run.resolve()):
                raise ValueError('legacy fixture member escaped its owned run')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(saved.read(name))
        manifest_raw = archive_bytes(manifest)
        marker.update(run_dir=str(run), manifest_sha256=hashlib.sha256(manifest_raw).hexdigest())
        (run / 'manifest.json').write_bytes(manifest_raw)
        (run / '.review-ownership.json').write_bytes(archive_bytes(marker))
        for name, expected in manifest['hashes'].items():
            if hashlib.sha256((run / name).read_bytes()).hexdigest() != expected:
                raise ValueError('legacy payload differs after location binding')
        return run
