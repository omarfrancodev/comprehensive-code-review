"""Resolve declared harness identity once from a bundled, versioned catalog.

No process, provider, model or undocumented environment detection. Stored records
are structurally validated without reinterpreting them using today's catalog.
"""
import json
import os
from pathlib import Path
import re

CATALOG = Path(__file__).resolve().parents[1] / 'references' / 'archive' / 'harness-catalog.json'
ID = re.compile(r'[a-z][a-z0-9]*(?:-[a-z0-9]+)*\Z')
SOURCE_KINDS = frozenset({'argument', 'environment', 'user', 'platform', 'alias', 'unknown'})
DIAGNOSTICS = frozenset({'unknown_harness', 'unknown_requested_id', 'identity_conflict'})


def _text(value):
    return isinstance(value, str) and bool(value.strip()) and len(value) <= 1024


def _identifier(value):
    return isinstance(value, str) and len(value) <= 80 and ID.fullmatch(value) is not None


def validate_catalog(catalog):
    if (not isinstance(catalog, dict) or set(catalog) != {'catalog_version', 'entries'}
            or type(catalog['catalog_version']) is not int or catalog['catalog_version'] < 1
            or not isinstance(catalog['entries'], list) or not catalog['entries']):
        raise ValueError('invalid harness catalog')
    by_id, aliases = {}, {}
    for entry in catalog['entries']:
        if (not isinstance(entry, dict) or set(entry) != {'id', 'name', 'family', 'interface', 'aliases'}
                or not _identifier(entry['id']) or not _identifier(entry['family']) or not _text(entry['name'])
                or (entry['interface'] is not None and not _identifier(entry['interface']))
                or not isinstance(entry['aliases'], list) or any(not _text(item) for item in entry['aliases'])):
            raise ValueError('invalid harness catalog entry')
        if entry['id'] in by_id:
            raise ValueError('duplicate harness catalog ID')
        by_id[entry['id']] = entry
        for name in [entry['id'], entry['name'], *entry['aliases']]:
            key = name.strip().casefold()
            if key in aliases and aliases[key]['id'] != entry['id']:
                raise ValueError('ambiguous duplicate harness alias: ' + name)
            aliases[key] = entry
    return by_id, aliases


def load_catalog():
    catalog = json.loads(CATALOG.read_text(encoding='utf-8'))
    validate_catalog(catalog)
    return catalog


def _source(value, kinds=SOURCE_KINDS):
    if (not isinstance(value, dict) or set(value) != {'kind', 'reference'}
            or not isinstance(value['kind'], str) or value['kind'] not in kinds
            or not _text(value['reference'])):
        raise ValueError('invalid harness source: kind and nonempty reference are required')


def validate_identity(manifest):
    """Validate schema6 identity shape; never load or match the current catalog."""
    identifier = manifest.get('harness_id')
    version = manifest.get('harness_catalog_version')
    if ('harness_id' not in manifest or (identifier is not None and not _identifier(identifier))
            or type(version) is not int or version < 1):
        raise ValueError('invalid canonical harness identity/version')
    _source(manifest.get('harness_source'))
    codes = manifest.get('harness_diagnostics')
    if (not isinstance(codes, list) or any(not isinstance(code, str) or code not in DIAGNOSTICS for code in codes)
            or len(codes) != len(set(codes)) or (identifier is not None and codes) or (identifier is None and not codes)):
        raise ValueError('invalid harness diagnostics')


def resolve(harness, harness_id=None, source=None, environ=None):
    if not _text(harness):
        raise ValueError('nonempty harness text (up to 1024 characters) is required')
    if harness_id is not None and not _text(harness_id):
        raise ValueError('nonempty explicit harness ID is required')
    if source is not None:
        _source(source, {'user', 'platform'})
        if harness_id is None:
            raise ValueError('harness source requires an explicit harness ID')
    catalog = load_catalog()
    by_id, aliases = validate_catalog(catalog)
    known = aliases.get(harness.strip().casefold())
    environment = os.environ if environ is None else environ
    requested = harness_id if harness_id is not None else environment.get('CCR_HARNESS_ID') or None
    provenance = dict(source) if source is not None else (
        {'kind': 'argument', 'reference': '--harness-id'} if harness_id is not None else
        {'kind': 'environment', 'reference': 'CCR_HARNESS_ID'} if requested is not None else
        {'kind': 'alias' if known else 'unknown', 'reference': harness})
    chosen, diagnostics = known, []
    if requested is not None:
        chosen = by_id.get(requested) if isinstance(requested, str) else None
        if chosen is None:
            diagnostics = ['unknown_requested_id']
        elif known is not None:
            if (known['family'] != chosen['family'] or
                    (known['interface'] is not None and chosen['interface'] is not None
                     and known['interface'] != chosen['interface'])):
                chosen, diagnostics = None, ['identity_conflict']
            elif chosen['interface'] is None and known['interface'] is not None:
                chosen = known
                provenance = {'kind': 'alias', 'reference': harness}
    elif chosen is None:
        diagnostics = ['unknown_harness']
    return {'harness_id': chosen['id'] if chosen is not None else None,
            'harness_catalog_version': catalog['catalog_version'],
            'harness_source': provenance, 'harness_diagnostics': diagnostics}
