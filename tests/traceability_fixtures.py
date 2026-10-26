"""Synthetic data for explicit coverage; never migrate retained records."""
from ccr.contracts.dimensions import DIMENSIONS

PURPOSE = 'Verificar que una reclamación conserve una sola ejecución.'


def receipt2_bundle():
    from test_review_check_receipts import valid_receipt, valid_binding
    receipt = valid_receipt()
    receipt.update(schema_version=2, purpose=PURPOSE)
    check, executors = valid_binding()
    check['purpose'] = PURPOSE
    sources = {receipt['stdout']['reference']: b'', receipt['stderr']['reference']: b''}
    return receipt, sources, check, executors


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
