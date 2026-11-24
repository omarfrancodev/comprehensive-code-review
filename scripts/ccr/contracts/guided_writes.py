"""Admission rules for new guided records, separate from historical reading."""


def require_followup_assessment(record):
    if (isinstance(record, dict) and record.get('schema_version') == 13
            and 'assessment' in record
            and (not isinstance(record['assessment'], dict)
                 or record['assessment'].get('schema_version') != 3)):
        raise ValueError('new guided writes require assessment version 3; versions 1 and 2 are historical')
    if (isinstance(record, dict) and record.get('schema_version') == 13
            and isinstance(record.get('presentation'), dict)
            and (record['presentation'].get('kind') in ('rereview', 'complement')
                 or record.get('rereview') or record.get('previous_reviews'))
            and 'assessment' not in record):
        raise ValueError('guided follow-up requires the source-bound assessment')
