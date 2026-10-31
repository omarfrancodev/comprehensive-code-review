"""Bounded explicit source selection for check disclosure CLI operations."""
from ccr.contracts.check_disclosure import digest


class SelectedDisclosureSources(dict):
    """Selected bytes with a separately verified initial archive trust anchor."""
    input_identity = None

def read_selected_disclosure(sidecar_path, catalog_path):
    """Read only named, hash-bound sources; never search a checkout or evaluate argv."""
    import json
    from ccr.shared.paths import safe_path
    from ccr.shared.json_io import read_bounded
    from ccr.contracts.check_disclosure import MAX_BYTES, _relative
    raw = read_bounded(safe_path(sidecar_path), MAX_BYTES)
    disclosure = json.loads(raw.decode('utf-8'))
    catalog = json.loads(read_bounded(safe_path(catalog_path), MAX_BYTES).decode('utf-8'))
    if (not isinstance(catalog, dict) or set(catalog) - {'input_identity', 'sources', 'run_dir'}
            or not {'input_identity', 'sources'}.issubset(catalog)
            or catalog['input_identity'] != disclosure.get('input_identity') or not isinstance(catalog['sources'], dict)):
        raise ValueError('disclosure source catalog must preserve the initially pinned input identity')
    references = {row[field] for row in disclosure['checks'] for field in ('execution_reference', 'evidence_reference') if row.get(field) is not None}
    if len(references) > 64 or set(catalog['sources']) != references:
        raise ValueError('disclosure catalog must select exactly the referenced evidence sources')
    selected = SelectedDisclosureSources({'evidence/check-disclosure.json': raw})
    if catalog.get('run_dir') is not None:
        from ccr.archive.reader import load_run
        from ccr.archive.integrity import verify_files
        run, manifest, _ = load_run(catalog['run_dir'])
        verify_files(run, manifest)
        if disclosure.get('review_id') != 'CR-' + manifest['run_id']:
            raise ValueError('disclosure catalog belongs to another review')
        if manifest.get('check_disclosure_input_identity') != catalog['input_identity']:
            raise ValueError('disclosure catalog differs from the initially registered input identity')
        selected.input_identity = manifest['check_disclosure_input_identity']
    total = len(raw)
    for reference in references:
        if _relative(reference) is None or not reference.startswith('evidence/'):
            raise ValueError('unsafe disclosure evidence reference')
        row = catalog['sources'][reference]
        if not isinstance(row, dict) or set(row) != {'path', 'sha256'}:
            raise ValueError('disclosure source selection requires path and SHA-256')
        payload = read_bounded(safe_path(row['path']), MAX_BYTES)
        if digest(payload) != row['sha256']:
            raise ValueError('selected disclosure source SHA-256 differs')
        selected[reference] = payload
        total += len(payload)
        if total > 16 * MAX_BYTES:
            raise ValueError('selected disclosure sources exceed 16 MiB')
    return disclosure, selected
