"""Synthetic data for explicit coverage; never migrate retained records."""
from ccr.contracts.dimensions import DIMENSIONS


def dimension_row(identifier, status='covered', **updates):
    row = dict(id=identifier, status=status, details='Inspected synthetic boundary',
               material=False, finding_ids=[])
    row.update(updates)
    return row


def dimension_areas():
    return [dict(area=area, status='covered', details='Inspected synthetic flow',
                 material=False, finding_ids=[],
                 dimensions=[dimension_row(identifier) for identifier in identifiers])
            for area, identifiers in DIMENSIONS.items()]
