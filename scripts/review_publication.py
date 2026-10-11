"""Select limitations by audience; historical classification is source-bound."""
import hashlib
import json


def publication_digest(record):
    return hashlib.sha256(json.dumps(record, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def public_limitations(record, classification=None):
    original = record['coverage']['limitations']
    if record['schema_version'] == 8:
        if classification is not None:
            raise ValueError('schema 8 already contains limitation classification')
        rows = original
    elif classification is None:
        if original:
            raise ValueError('historical public limitations require bound publication context')
        rows = []
    else:
        if (not isinstance(classification, dict) or set(classification) != {'source_sha256', 'limitations'}
                or classification['source_sha256'] != publication_digest(record)
                or not isinstance(classification['limitations'], list)
                or len(classification['limitations']) != len(original)):
            raise ValueError('publication context does not match the source record')
        indexed = {}
        for row in classification['limitations']:
            if (not isinstance(row, dict) or set(row) != {'index', 'kind', 'public_summary'}
                    or type(row['index']) is not int or not 0 <= row['index'] < len(original)
                    or row['index'] in indexed):
                raise ValueError('publication context requires each original index exactly once')
            indexed[row['index']] = row
        rows = [dict(item, kind=indexed[i]['kind'], public_summary=indexed[i]['public_summary'])
                for i, item in enumerate(original)]
    selected = []
    for row in rows:
        if row['kind'] not in ('behavior', 'validation', 'execution'):
            raise ValueError('invalid public limitation kind')
        summary = row['public_summary']
        if summary is not None and (not isinstance(summary, str) or not summary.strip()):
            raise ValueError('public_summary must be nonempty text or null')
        if row['kind'] == 'execution':
            if row['material']:
                if summary is None:
                    raise ValueError('material execution requires a public impact summary')
            else:
                if summary is not None:
                    raise ValueError('nonmaterial execution must not have a public summary')
                continue
        selected.append(dict(detail=summary if summary is not None else row['detail'], material=row['material']))
    return selected
