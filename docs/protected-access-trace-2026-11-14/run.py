from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib,json,subprocess,tempfile
root=Path('/workspace/tprm-legacy-coordination');w=root.parent;out=w/'.tprm-dryrun/protected-trace-archived-20261114';out.mkdir(parents=True,exist_ok=True)
refs=json.loads((root/'docs/source-head-transition-2026-11-13.json').read_text())['groups'];builds=json.loads((root/'docs/builds-verifier-followup-2026-11-13/index.json').read_text())['groups'];manifest=json.loads((root/'docs/legacy-dry-run-1.0.0/release-manifest.json').read_text());jobs=[]
with tempfile.TemporaryDirectory(prefix='tprm-protected-sources-') as tmp:
 source_root=Path(tmp)
 for group in manifest['groups']:
  name=group['id'];repo=w/(('tprm-review-'+name) if name in ('1.21.11','26.1-26.2','26.3') else ('tprm-legacy-'+('1.14' if name=='1.14-1.14.4' else name)));sha=refs[name]['new_head'];assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()==sha
  src=source_root/name;src.mkdir();archive=source_root/(name+'.tar');subprocess.run(['git','archive','--format=tar','--output',str(archive),sha,'--','scripts'],cwd=repo,check=True);subprocess.run(['tar','-xf',str(archive),'-C',str(src)],check=True);archive.unlink()
  jar=w/'.tprm-dryrun/class-linkage-builds'/name/builds[name]['artifact'];assert hashlib.sha256(jar.read_bytes()).hexdigest()==builds[name]['sha256']
  script_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((src/'scripts').glob('*.py'))}
  for version in group['minecraft']:jobs.append((name,src,sha,jar,builds[name]['sha256'],version,script_hashes))
 def run(job):
  group,src,sha,jar,digest,version,script_hashes=job;result=out/(version+'.json');log=out/(version+'.log')
  with log.open('w') as f:p=subprocess.run(['python3','/tmp/tprm-protected-worker.py',str(src),str(jar),version,str(result)],cwd=src,stdout=f,stderr=subprocess.STDOUT)
  if not result.exists():print('MISSING',group,version,p.returncode,flush=True);return {'version':version,'group':group,'exit_code':p.returncode}
  row=json.loads(result.read_text());row.update({'group':group,'source_commit':sha,'artifact_sha256':digest,'archived_script_sha256':script_hashes});result.write_text(json.dumps(row,indent=2)+'\n');cross=[x for x in row['protected_uses'] if not x['same_package'] and not x['static'] and x['operation'] not in ('invokespecial','newinvokespecial')]
  print(group,version,'exit',p.returncode,'calls',row['validated_uses'],'protected',len(row['protected_uses']),'cross-package instance',len(cross),flush=True);return row
 with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(run,jobs))
 print('Completed',sum(r.get('exit_code')==0 for r in results),'of',len(results),'versions',flush=True)
