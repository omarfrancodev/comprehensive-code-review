"""Verify the selected baseline of an assessed review before retention."""
import hashlib
from pathlib import Path

from ccr.archive.integrity import CHECKPOINT_METADATA_LIMIT, verify_files
from ccr.archive.reader import load_run
from ccr.contracts.review import validate
from ccr.contracts.guided_writes import require_followup_assessment
from ccr.shared.json_io import decode_json, read_bounded
from ccr.shared.paths import safe_path


class PrecursorSelectionError(ValueError):
    """The verified archive offers exact precursor bytes required for adoption."""

    def __init__(self, message, reference):
        super().__init__(message)
        self.reference = reference


def verify_prior_archive(record, logical_scope, repository_key, *, previous_run=None,
                         compact_reader=None, read_source=None):
    assessment = record.get('assessment')
    if assessment is None or assessment['previous'] is None:
        return
    previous = assessment['previous']
    if previous_run is None:
        reference = next(row['reference'] for row in record['previous_reviews']
                         if row['review_id'] == previous['review_id'])
        if not Path(reference).is_absolute() or Path(reference).name != 'review.json':
            raise ValueError('assessment baseline requires the exact previous archive review.json')
        previous_run = Path(reference).parent
    baseline = read_followup_baseline(previous_run, logical_scope, repository_key,
                                      compact_reader=compact_reader)
    if previous['review_id'] != baseline['review_id']:
        raise ValueError('assessment baseline ID differs from the selected archive')
    if previous['source']['sha256'] != baseline['sha256']:
        raise ValueError('assessment baseline bytes differ from the verified prior archive')
    predecessor = baseline.get('legacy_previous')
    if assessment['schema_version'] == 3 and predecessor is not None:
        selected = previous.get('legacy_source')
        if selected is None or selected['sha256'] != predecessor['sha256']:
            raise PrecursorSelectionError(
                'v3 adoption requires the inventoried legacy predecessor in assessment.previous.legacy_source',
                predecessor['review_file'])
        if read_source is not None:
            try:
                raw = read_source(selected['reference'])
            except (OSError, KeyError, ValueError) as exc:
                raise PrecursorSelectionError(
                    'select the inventoried legacy predecessor as ' + selected['reference'],
                    predecessor['review_file']) from exc
            if hashlib.sha256(raw).hexdigest() != predecessor['sha256']:
                raise PrecursorSelectionError(
                    'selected legacy predecessor bytes differ from the inventoried digest',
                    predecessor['review_file'])


def read_followup_baseline(run_dir, logical_scope, repository_key, *, compact_reader):
    """Verify the selected archive and return the identity of its exact review bytes."""
    run = safe_path(run_dir)
    if (run / 'manifest.json').is_file() and compact_reader is not None:
        result = compact_reader(run)
        manifest = result['manifest']
        expected_repository = manifest['request']['repository_identity']
        expected_repository = hashlib.sha256(expected_repository.encode('utf-8')).hexdigest()[:20]
        expected_id = manifest['review_id']
        expected_scope = manifest['request']['scope']
    else:
        run, manifest, _ = load_run(run)
        if manifest['state'] != 'complete' or manifest.get('retained') is not True:
            raise ValueError('assessment baseline requires a completed retained result')
        verify_files(run, manifest, required=True)
        expected_repository = manifest['repository_key']
        expected_id = 'CR-' + manifest['run_id']
        expected_scope = manifest['scope']
    if expected_repository != repository_key or manifest.get('logical_scope') != logical_scope:
        raise ValueError('assessment baseline belongs to another repository or logical scope')
    raw = read_bounded(run / 'review.json', CHECKPOINT_METADATA_LIMIT)
    digest = hashlib.sha256(raw).hexdigest()
    if digest != manifest['hashes'].get('review.json'):
        raise ValueError('assessment baseline bytes differ from the verified prior archive')
    prior = decode_json(raw)
    if (validate(prior) or prior.get('review_id') != expected_id
            or prior.get('stage') != 'final' or prior.get('scope') != expected_scope):
        raise ValueError('assessment baseline is not a valid final result')
    selected = {'review_id': expected_id, 'review_file': str(run / 'review.json'), 'sha256': digest}
    assessment = prior.get('assessment') or {}
    link = assessment.get('previous')
    if assessment.get('schema_version') == 2 and link is not None and any(
            row['id'] != row['survivor'] and row['resolution'] is not None for row in assessment['lineage']):
        source = link['source']
        reference = source['reference']
        if manifest['hashes'].get(reference) == source['sha256']:
            selected['legacy_previous'] = {'review_id': link['review_id'],
                'review_file': str(safe_path(run / reference)), 'sha256': source['sha256']}
    return selected
