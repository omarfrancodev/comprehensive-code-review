"""Regenerate the synthetic compact using only the actual 7f05898 writer."""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

WRITER = '7f0589853ae854bc0bf6678ba30bd2e9f8f2591f'
WORKER = r'''import copy,hashlib,json,pathlib,sys,zipfile
sys.path.insert(0,str(pathlib.Path.cwd()/'tests'))
from test_review_assessment import AssessmentCompactTests,assessed,followup,guided_v2,NOTE,PROOF,source
from ccr.archive import compact
from ccr.reporting.render import render
from ccr.shared.encoding import archive_bytes
fixture=AssessmentCompactTests();fixture.setUp()
try:
 previous=None;previous_file=None;stage=[]
 for index in range(3):
  inputs=dict(fixture.inputs,sources={'evidence/note.txt':hashlib.sha256(NOTE).hexdigest()}) if index==0 else fixture.inputs
  prepared=fixture.prepare(inputs=inputs,operation_id='legacy-generation-'+str(index))
  fresh,selected=fixture.record_and_sources(prepared)
  if previous is None:
   value=assessed(fresh)
   selected.update({'evidence/note.txt':NOTE,'evidence/proof.txt':PROOF})
  else:
   value,proof=followup(previous)
   value.pop('compact_identity',None)
   value['review_id']=fresh['review_id']
   value['coverage']['execution']=fresh['coverage']['execution']
   value['previous_reviews'][0]['reference']=str(previous_file)
   value['rereview'][0]['previous_reference']=str(previous_file)
   old_raw=previous_file.read_bytes()
   value['assessment']['previous']['source']=source('prior.json',old_raw)
   proof['evidence/prior.json']=old_raw
   selected.update(proof)
  if index==2:
   guided_v2(value,previous)
   old=previous['assessment']
   hashes={old['previous']['source']['sha256']}
   for delta in old['scope']['delta']:hashes.update(d['sha256'] for d in delta['sources'])
   for row in old['findings']:
    if row['resolution'] is not None:hashes.add(row['resolution']['source']['sha256'])
   value['assessment']['observed_hashes']=sorted(set(value['assessment']['observed_hashes'])|hashes)
  kept=(compact.create_compact(prepared,value,current_inputs=inputs,sources=selected) if index==2
        else compact.create_compact(prepared,value,render(value),current_inputs=inputs,sources=selected))
  previous=compact.read_compact(kept['run_dir'])['record'];previous_file=pathlib.Path(kept['run_dir'])/'review.json'
  stage.append({'assessment':previous['assessment']['schema_version'],'review_id':previous['review_id'],'sha256':hashlib.sha256(previous_file.read_bytes()).hexdigest()})
 run=previous_file.parent
 out=pathlib.Path(sys.argv[1]);out.parent.mkdir(parents=True,exist_ok=True)
 with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED) as z:
  for path in sorted(run.rglob('*')):
   if path.is_file():z.writestr(path.relative_to(run).as_posix(),path.read_bytes())
 print(json.dumps({'output':str(out),'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'bytes':out.stat().st_size,'stages':stage}))
finally:fixture.doCleanups()
'''


def main():
    repository = Path(__file__).resolve().parents[3]
    output = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).with_name('chained-v1-7f05898.zip')
    git = ['git', '--no-pager', '--no-optional-locks', '--no-lazy-fetch', '--no-replace-objects',
           '-c', 'core.fsmonitor=false', '-c', 'maintenance.auto=false', '-c', 'gc.auto=0',
           '-c', 'log.showSignature=false']
    archive = subprocess.run(git + ['archive', '--format=zip', WRITER], cwd=repository,
                             capture_output=True, check=True).stdout
    temp_root = Path(tempfile.gettempdir()).resolve()
    with tempfile.TemporaryDirectory(prefix='ccr-legacy-writer-') as raw:
        scratch = Path(raw).resolve()
        if not scratch.is_relative_to(temp_root):
            raise ValueError('writer scratch escaped its temporary root')
        legacy = scratch / 'legacy'
        legacy.mkdir()
        with zipfile.ZipFile(io.BytesIO(archive)) as source:
            for name in source.namelist():
                if not (legacy / name).resolve().is_relative_to(legacy):
                    raise ValueError('writer snapshot escaped its scratch directory')
            source.extractall(legacy)
        env = dict(os.environ, PYTHONPATH=str(legacy / 'tests'), PYTHONDONTWRITEBYTECODE='1',
                   TEMP=str(scratch), TMP=str(scratch))
        result = subprocess.run([sys.executable, '-B', '-X', 'utf8', '-c', WORKER, str(output)],
                                cwd=legacy, env=env, capture_output=True, check=True)
        receipt = json.loads(result.stdout.decode('utf-8'))
        receipt['writer_commit'] = WRITER
        # UUIDs and observed creation timestamps are intentionally produced by
        # the real writer. Refresh the checked fixture digest after regeneration.
        print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
