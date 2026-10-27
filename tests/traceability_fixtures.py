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


def record11(profile='focused', source='automatic'):
    from recovery_fixtures import record10
    from test_review_traceability_contract import check
    value = record10(profile, source)
    value['schema_version'] = 11
    value['coverage']['areas'] = dimension_areas()
    value['checks'] = [dict(check(), command='python -V', revision=value['scope']['head'],
        reference=None, execution={'kind': 'static', 'executor': None},
        evidence='Resultado observado', purpose=PURPOSE)]
    return value


def set_dimension(record, identifier, **updates):
    from ccr.contracts.dimensions import dimension_summary
    area = next(row for row in record['coverage']['areas'] if row['area'] == identifier[0])
    dimension = next(row for row in area['dimensions'] if row['id'] == identifier)
    dimension.update(updates)
    area.update(dimension_summary(area['dimensions']))


def publication_contexts(record):
    from publication_fixtures import check_classification, coverage_classification
    checks = check_classification(record)
    for row, source in zip(checks['checks'], record['checks']):
        if record['schema_version'] == 11:
            row['purpose'] = source['purpose']
    return dict(check_publication_context=checks,
                coverage_publication_context=coverage_classification(record))
